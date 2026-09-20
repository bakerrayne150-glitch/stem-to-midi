#!/usr/bin/env python3
"""transcribe.py — importable transcription cores (Phase A refactored for Phase B).

Pitched: Spotify Basic Pitch, one shared model instance, per-profile settings.
Drums:   librosa onset detection + spectral-window classification -> GM notes.

Public API:
    load_pitch_model() -> basic_pitch Model (cached)
    transcribe_pitched(path, profile="other", model=None)
        -> list of (start_s, end_s, midi_pitch, velocity)
    transcribe_drums(path) -> list of (time_s, gm_note, velocity)
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
    """Classify one onset window -> kit piece label. Frequency-only rules (prototype)."""
    if len(y_win) < 64:
        return "other"
    S = np.abs(librosa.stft(y_win, n_fft=1024, hop_length=256))
    mag = S.mean(axis=1)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)

    centroid = float(np.sum(freqs * mag) / (mag.sum() + 1e-12))
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

    # --- rules (tuned on synthetic ground truth, 2026-09-20; prototype only) ---
    if centroid < 600 and low > 0.5:
        return "kick"
    if centroid > 5200 and high > 0.5:
        return "open_hat" if not fast_decay else "closed_hat"
    if 900 < centroid < 5000 and mid > 0.25:
        return "snare"
    if 250 < centroid <= 900 and (low + lowmid) > 0.4:
        if centroid < 420:
            return "low_tom"
        if centroid < 650:
            return "mid_tom"
        return "high_tom"
    if centroid > 4200 and not fast_decay:
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
