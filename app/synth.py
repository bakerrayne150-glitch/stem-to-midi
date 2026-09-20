#!/usr/bin/env python3
"""synth.py — minimal built-in synth: renders note events to a stereo WAV
buffer so the user can A/B the detected MIDI against the source audio.

Pitched notes: sine + 0.3*saw blend with a short attack/decay envelope.
Drums: per-GM-class filtered-noise / pitch-drop bursts (prototype quality,
good enough for preview, not a product sound).
"""
import numpy as np
from scipy.signal import butter, sosfilt

# GM classes the drum engine can emit (see transcribe.GM)
_KICK = {36}
_SNARE = {38}
_HATS = {42, 46}
_TOMS = {45, 47, 50}
_CYMBALS = {49, 51}


def midi_to_freq(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _envelope(n, sr, attack=0.005, release=0.03):
    t = np.arange(n) / sr
    a = np.minimum(1.0, t / max(attack, 1e-4))
    r = np.minimum(1.0, (n / sr - t) / max(release, 1e-4))
    return np.minimum(a, r)


def render_pitched_note(midi_pitch, vel, dur_s, sr):
    n = max(8, int(dur_s * sr))
    t = np.arange(n) / sr
    f = midi_to_freq(midi_pitch)
    sine = np.sin(2 * np.pi * f * t)
    saw = 2.0 * ((f * t) % 1.0) - 1.0
    sig = (sine + 0.3 * saw) * _envelope(n, sr)
    sig *= (vel / 127.0) * 0.5
    return sig.astype(np.float32)


def _noise_burst(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def render_drum_hit(gm_note, vel, sr, rng=None):
    rng = rng or np.random.default_rng(1234)
    amp = (vel / 127.0) * 0.6
    if gm_note in _KICK:
        n = int(0.30 * sr)
        t = np.arange(n) / sr
        f = 150 * np.exp(-t * 30) + 45
        sig = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 18)
    elif gm_note in _SNARE:
        n = int(0.22 * sr)
        t = np.arange(n) / sr
        sos = butter(4, [400, 6000], btype="band", fs=sr, output="sos")
        sig = sosfilt(sos, _noise_burst(n, rng)) * np.exp(-t * 22) * 0.8
        sig += np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    elif gm_note in _HATS:
        closed = gm_note == 42
        n = int((0.06 if closed else 0.30) * sr)
        t = np.arange(n) / sr
        sos = butter(6, 7000, btype="highpass", fs=sr, output="sos")
        sig = sosfilt(sos, _noise_burst(n, rng)) * np.exp(-t * (120 if closed else 18))
    elif gm_note in _TOMS:
        base = {45: 110, 47: 140, 50: 180}[gm_note]
        n = int(0.35 * sr)
        t = np.arange(n) / sr
        f = base * np.exp(-t * 12) + base * 0.5
        sig = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 10)
    elif gm_note in _CYMBALS:
        n = int(0.9 * sr)
        t = np.arange(n) / sr
        sos = butter(4, 5000, btype="highpass", fs=sr, output="sos")
        sig = sosfilt(sos, _noise_burst(n, rng)) * np.exp(-t * 6) * 0.7
    else:  # other percussion: short click
        n = int(0.12 * sr)
        t = np.arange(n) / sr
        sos = butter(4, [1500, 8000], btype="band", fs=sr, output="sos")
        sig = sosfilt(sos, _noise_burst(n, rng)) * np.exp(-t * 40)
    sig = sig / (np.abs(sig).max() + 1e-12)
    return (sig * amp).astype(np.float32)


def render_notes(notes, sr, duration_s, is_drum=False):
    """Render note dicts to a mono float32 buffer of duration_s."""
    n_total = int(duration_s * sr)
    buf = np.zeros(n_total, dtype=np.float32)
    rng = np.random.default_rng(99)
    for note in notes:
        start_i = int(note["start"] * sr)
        if start_i >= n_total:
            continue
        if is_drum:
            sig = render_drum_hit(note["pitch"], note["vel"], sr, rng)
        else:
            dur = max(0.03, note["end"] - note["start"])
            sig = render_pitched_note(note["pitch"], note["vel"], dur, sr)
        end_i = min(n_total, start_i + len(sig))
        buf[start_i:end_i] += sig[:end_i - start_i]
    peak = np.abs(buf).max()
    if peak > 0.95:
        buf *= 0.95 / peak
    return buf


def to_stereo(mono):
    return np.stack([mono, mono], axis=1)
