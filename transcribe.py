#!/usr/bin/env python3
"""transcribe.py — importable transcription cores (Phase A refactored for Phase B).

Pitched: Spotify Basic Pitch, one shared model instance, per-profile settings.
Drums:   librosa onset detection + spectral/temporal classification -> GM notes.
Bass:    dedicated monophonic engine (librosa.pyin); Basic Pitch fallback.

Public API:
    load_pitch_model() -> basic_pitch Model (cached)
    transcribe_pitched(path, profile="other", model=None)
        -> list of (start_s, end_s, midi_pitch, velocity)
    transcribe_bass(path) -> list of (start_s, end_s, midi_pitch, velocity)
    transcribe_drums(path) -> list of (time_s, gm_note, velocity)
    merge_overlaps(notes) -> same-pitch overlap-merged note tuples
"""
import os
import pathlib

import numpy as np
import librosa

# ---------------------------------------------------------------- pitched ---

# Basic Pitch settings per instrument profile (spec section 5).
# minimum_note_length is in milliseconds (Basic Pitch default 127.7).
PROFILES = {
    # "legacy": exact Phase A CLI behavior — stock Basic Pitch 0.4.0 predict()
    # defaults (2026-09-20: 8/8 bass recall + 8 harmonic extras, 14/16 poly).
    # Kept so the single-stem CLI is reproducible; full-mix stems use the
    # conservative profiles below.
    "legacy": {"onset_threshold": 0.5, "frame_threshold": 0.30,
               "minimum_note_length": 127.7,
               "minimum_frequency": None, "maximum_frequency": None,
               "multiple_pitch_bends": False},
    "bass":   {"onset_threshold": 0.6, "frame_threshold": 0.35,
               "minimum_note_length": 200.0,
               "minimum_frequency": 27.5, "maximum_frequency": 330.0,
               "multiple_pitch_bends": False},
    "melody": {"onset_threshold": 0.5, "frame_threshold": 0.30,
               "minimum_note_length": 127.7,
               "minimum_frequency": 55.0, "maximum_frequency": 1568.0,
               "multiple_pitch_bends": True},
    "vocal":  {"onset_threshold": 0.5, "frame_threshold": 0.30,
               "minimum_note_length": 127.7,
               "minimum_frequency": 65.0, "maximum_frequency": 1046.0,
               "multiple_pitch_bends": True},
    "piano":  {"onset_threshold": 0.5, "frame_threshold": 0.30,
               "minimum_note_length": 127.7,
               "minimum_frequency": 27.5, "maximum_frequency": 4186.0,
               "multiple_pitch_bends": False},
    "guitar": {"onset_threshold": 0.55, "frame_threshold": 0.32,
               "minimum_note_length": 180.0,
               "minimum_frequency": 55.0, "maximum_frequency": 1318.0,
               "multiple_pitch_bends": True},
    "other":  {"onset_threshold": 0.6, "frame_threshold": 0.35,
               "minimum_note_length": 127.7,
               "minimum_frequency": None, "maximum_frequency": None,
               "multiple_pitch_bends": False},
}

_PITCH_MODEL = None


def _model_path():
    # Phase A finding: the TF SavedModel bundled with basic-pitch 0.4.0 cannot
    # be restored by TF 2.16 (Keras 3 optimizer slot incompatibility); the
    # bundled TFLite and ONNX models both work with identical quality.
    # Spec carries ONNX forward for the Windows build.
    import basic_pitch
    which = os.environ.get("BP_MODEL", "tflite")
    fname = "nmp.onnx" if which == "onnx" else "nmp.tflite"
    return pathlib.Path(basic_pitch.__file__).parent / "saved_models" / "icassp_2022" / fname


def load_pitch_model():
    """Load (once) and return the shared Basic Pitch model instance."""
    global _PITCH_MODEL
    if _PITCH_MODEL is None:
        from basic_pitch.inference import Model
        _PITCH_MODEL = Model(_model_path())
    return _PITCH_MODEL


def transcribe_pitched(audio_path, profile="other", model=None):
    """Transcribe pitched audio -> [(start_s, end_s, midi_pitch, velocity)].

    Uses one shared model instance across calls; safe to call per stem.
    """
    from basic_pitch.inference import predict
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose from {sorted(PROFILES)}")
    if model is None:
        model = load_pitch_model()
    p = PROFILES[profile]
    _, _, note_events = predict(
        str(audio_path),
        model_or_model_path=model,
        onset_threshold=p["onset_threshold"],
        frame_threshold=p["frame_threshold"],
        minimum_note_length=p["minimum_note_length"],
        minimum_frequency=p["minimum_frequency"],
        maximum_frequency=p["maximum_frequency"],
        multiple_pitch_bends=p["multiple_pitch_bends"],
        midi_tempo=120,
    )
    notes = []
    for start, end, pitch, amplitude, _bends in note_events:
        vel = int(np.clip(round(80 * float(amplitude) + 20), 1, 127))
        notes.append((float(start), float(end), int(pitch), vel))
    notes.sort(key=lambda n: (n[0], n[2]))
    return notes


# ------------------------------------------------------------------ bass ---

def transcribe_bass(audio_path):
    """Monophonic bass transcription via librosa.pyin.

    Returns [(start_s, end_s, midi_pitch, velocity)], the same tuple format
    as transcribe_pitched. Pipeline: pyin f0 (27.5-330 Hz) -> bridge unvoiced
    blips <= 60 ms -> median-filter pitch -> split segments on unvoiced gaps
    or sustained pitch jumps > 0.6 semitone -> drop segments < 120 ms ->
    MIDI = rounded segment median pitch, velocity from per-note RMS.

    Falls back to transcribe_pitched(profile="bass") when pyin finds no
    voiced frames at all (e.g. silence or a non-bass stem misrouted here).
    """
    from scipy.signal import medfilt  # ships with the librosa stack

    y, sr = librosa.load(audio_path, sr=SR, mono=True)
    if y.size == 0:
        return transcribe_pitched(audio_path, profile="bass")

    hop = 512  # librosa.pyin default hop_length
    f0, voiced, _prob = librosa.pyin(y, fmin=27.5, fmax=330.0, sr=sr)
    if f0 is None or not np.any(voiced):
        return transcribe_pitched(audio_path, profile="bass")

    frame_t = librosa.frames_to_time(np.arange(len(f0)), sr=sr,
                                     hop_length=hop)
    frame_s = hop / sr
    midi_c = np.full(len(f0), np.nan)
    midi_c[voiced] = 69.0 + 12.0 * np.log2(f0[voiced] / 440.0)

    # bridge unvoiced blips <= 60 ms so legato notes don't fragment
    max_gap = max(1, int(round(0.060 / frame_s)))
    v = voiced.copy()
    i = 0
    while i < len(v):
        if not v[i]:
            j = i
            while j < len(v) and not v[j]:
                j += 1
            if j - i <= max_gap and i > 0 and j < len(v):
                v[i:j] = True
                a, b = midi_c[i - 1], midi_c[j]
                midi_c[i:j] = np.linspace(a, b, j - i)
            i = j
        else:
            i += 1

    # median-filter pitch to kill jitter (kernel ~5 frames ~= 115 ms)
    filled = midi_c.copy()
    nan = np.isnan(filled)
    if np.any(nan):
        idx = np.arange(len(filled))
        filled[nan] = np.interp(idx[nan], idx[~nan], filled[~nan])
    smooth = medfilt(filled, kernel_size=5)

    # segment: split on unvoiced runs and on sustained pitch jumps > 0.6 st
    w = 3  # frames each side for the "sustained" jump test
    bounds = [0]
    for f in range(1, len(v)):
        if v[f] and not v[f - 1]:
            bounds.append(f)
        elif v[f - 1] and not v[f]:
            bounds.append(f)
        elif v[f] and v[f - 1]:
            a = np.median(smooth[max(0, f - w):f])
            b = np.median(smooth[f:f + w])
            if abs(float(b) - float(a)) > 0.6:
                bounds.append(f)
    bounds.append(len(v))

    # split segments on energy dips (re-articulated repeated notes): a local
    # RMS valley that is deep relative to its surroundings and followed by
    # recovery marks a new attack even when the pitch doesn't change.
    rms_frames = librosa.feature.rms(y=y, frame_length=2048,
                                     hop_length=hop)[0]
    n_fr = min(len(rms_frames), len(v))
    refined = [bounds[0]]
    for s, e in zip(bounds[:-1], bounds[1:]):
        e = min(e, n_fr)
        seg = rms_frames[s:e]
        cuts = []
        for f in range(4, len(seg) - 4):
            if seg[f] != seg[f - 2:f + 3].min():
                continue  # not a local valley over +-2 frames
            ctx_max = seg[f - 4:f + 4].max()
            if ctx_max <= 0:
                continue
            deep = seg[f] < 0.45 * ctx_max
            recovers = seg[f + 1:f + 5].max() > 0.6 * ctx_max
            if deep and recovers:
                cuts.append(s + f)
        refined.extend(sorted(set(cuts)))
        refined.append(e)
    bounds = sorted(set(refined))

    segments = []
    for s, e in zip(bounds[:-1], bounds[1:]):
        if not np.any(v[s:e]):
            continue
        start = float(frame_t[s])
        end = float(frame_t[e - 1] + frame_s)
        if end - start < 0.120:
            continue
        pitch = int(np.clip(round(float(np.median(smooth[s:e]))), 0, 127))
        s0 = int(s * hop)
        s1 = min(len(y), int(e * hop))
        rms = float(np.sqrt(np.mean(y[s0:s1] ** 2)) + 1e-12)
        segments.append((start, end, pitch, rms))

    if not segments:
        return transcribe_pitched(audio_path, profile="bass")

    max_rms = max(s[3] for s in segments)
    notes = []
    for start, end, pitch, rms in segments:
        n = rms / (max_rms + 1e-12)
        vel = int(np.clip(64 + 63 * n, 1, 127))
        notes.append((start, end, pitch, vel))
    notes.sort(key=lambda n: (n[0], n[2]))
    return notes


def merge_overlaps(notes):
    """Merge same-pitch notes whose time ranges overlap.

    notes: iterable of (start_s, end_s, midi_pitch, velocity) tuples.
    Returns a new list sorted by (start, pitch). Idempotent: a second pass
    changes nothing. Mirrors app/cleanup.py::merge_same_pitch_overlaps
    (tuple flavor); merges per pitch so interleaved pitches can't block it.
    """
    notes = sorted(notes, key=lambda n: (n[2], n[0]))
    merged = []
    for start, end, pitch, vel in notes:
        if merged and merged[-1][2] == pitch and start < merged[-1][1]:
            ps, pe, pp, pv = merged[-1]
            merged[-1] = (ps, max(pe, end), pp, max(pv, vel))
        else:
            merged.append((start, end, pitch, vel))
    merged.sort(key=lambda n: (n[0], n[2]))
    return merged


# ------------------------------------------------------------------ drums ---

SR = 22050

# GM percussion note numbers
GM = {
    "kick": 36,
    "snare": 38,      # snare/clap
    "closed_hat": 42,
    "open_hat": 46,
    "low_tom": 45,
    "mid_tom": 47,
    "high_tom": 50,
    "crash": 49,
    "ride": 51,
    "other": 70,      # maracas, fallback percussion
}

MIN_GAP_S = 0.030  # merge detections closer than this


def band_energy_ratio(mag, freqs, lo, hi):
    mask = (freqs >= lo) & (freqs < hi)
    total = mag.sum() + 1e-12
    return float(mag[mask].sum() / total)


def classify_hit(y_win, sr):
    """Classify one onset window -> kit piece label.

    Features: spectral centroid, band energy ratios, spectral rolloff,
    zero-crossing rate (noisy vs tonal), early/late decay ratio, and
    high-frequency sustain (open vs closed hats/cymbals).
    """
    if len(y_win) < 64:
        return "other"
    S = np.abs(librosa.stft(y_win, n_fft=1024, hop_length=256))
    mag = S.mean(axis=1)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)

    centroid = float(np.sum(freqs * mag) / (mag.sum() + 1e-12))
    rolloff = float(librosa.feature.spectral_rolloff(S=S, sr=sr)[0].mean())
    zcr = float(librosa.feature.zero_crossing_rate(
        y_win, frame_length=1024, hop_length=512).mean())
    low = band_energy_ratio(mag, freqs, 20, 250)
    lowmid = band_energy_ratio(mag, freqs, 250, 1000)
    mid = band_energy_ratio(mag, freqs, 1000, 4000)
    high = band_energy_ratio(mag, freqs, 4000, sr / 2)

    # decay: energy in first 20ms vs 20-60ms of the window
    n20 = int(0.020 * sr)
    n60 = int(0.060 * sr)
    e_early = float(np.sum(y_win[:n20] ** 2) + 1e-12)
    e_late = float(np.sum(y_win[n20:n60] ** 2) + 1e-12)
    decay_ratio = e_early / e_late  # large = fast decay
    fast_decay = decay_ratio > 4.0

    # high-frequency sustain: HF-band (>=6 kHz) energy late (40-75ms) vs
    # early (0-25ms). Open hats/crashes keep ringing; closed hats choke.
    hf = freqs >= 6000
    fr_t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=256)
    hf_early = S[np.ix_(hf, fr_t < 0.025)].mean() + 1e-12
    hf_late = S[np.ix_(hf, (fr_t >= 0.040) & (fr_t < 0.075))].mean() + 1e-12
    hf_sustain = float(hf_late / hf_early)
    # a true ring (open hat / crash) decays slowly AND keeps HF energy;
    # onset timing jitter makes the decay ratio alone unreliable
    sustained_ring = (not fast_decay) and hf_sustain > 0.15

    # --- rules (tuned on synthetic ground truth, 2026-09-20; refined
    # 2026-09-23: rolloff/ZCR added, HF-sustain for hat disambiguation) ---
    if centroid < 600 and low > 0.5:
        return "kick"
    if centroid > 5200 and high > 0.5:
        # hats live up here: HF ring sustained -> open, choked -> closed
        return "open_hat" if hf_sustain > 0.20 else "closed_hat"
    if 900 < centroid < 5000 and mid > 0.25:
        # snares are noisy (high ZCR); tonal midrange hits are high toms
        if zcr > 0.10:
            return "snare"
        if centroid < 1600 and (low + lowmid) > 0.35:
            return "high_tom"
        return "snare"
    if 250 < centroid <= 900 and (low + lowmid) > 0.4:
        if centroid < 420:
            return "low_tom"
        if centroid < 650:
            return "mid_tom"
        return "high_tom"
    if centroid > 4200 and rolloff > 9000 and sustained_ring:
        return "crash"
    if 2200 < centroid <= 7000 and not fast_decay:
        return "ride"
    return "other"


def transcribe_drums(audio_path):
    """Transcribe drum audio -> [(time_s, gm_note, velocity)]."""
    y, sr = librosa.load(audio_path, sr=SR, mono=True)
    hop = 256
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    times = librosa.frames_to_time(
        librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr, hop_length=hop,
            backtrack=True, units="frames",
        ),
        sr=sr, hop_length=hop,
    )

    hits = []
    for t in times:
        start = max(0, int((t - 0.010) * sr))
        end = min(len(y), int((t + 0.060) * sr))
        label = classify_hit(y[start:end], sr)
        frame = librosa.time_to_frames(t, sr=sr, hop_length=hop)
        energy = float(onset_env[min(frame, len(onset_env) - 1)])
        hits.append({"time": float(t), "label": label, "energy": energy})

    # merge implausibly close detections (keep the stronger)
    hits.sort(key=lambda h: h["time"])
    merged = []
    for h in hits:
        if merged and (h["time"] - merged[-1]["time"]) < MIN_GAP_S:
            if h["energy"] > merged[-1]["energy"]:
                merged[-1] = h
        else:
            merged.append(h)

    # velocity from normalized onset energy
    energies = np.array([h["energy"] for h in merged]) if merged else np.array([0.0])
    emin, emax = energies.min(), energies.max()
    out = []
    for h in merged:
        n = (h["energy"] - emin) / (emax - emin + 1e-12)
        vel = int(np.clip(64 + 63 * n, 1, 127))
        out.append((h["time"], GM[h["label"]], vel))
    out.sort(key=lambda e: e[0])
    return out
