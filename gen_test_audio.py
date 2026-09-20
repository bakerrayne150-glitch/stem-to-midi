#!/usr/bin/env python3
"""gen_test_audio.py — synthesize test audio with known ground truth.

(a) bass.wav: 8-note bass line (sine + harmonics), ground truth in bass.json
(b) drums.wav: 16-hit drum pattern (kick/snare/hats), ground truth in drums.json
(c) bass_poly.wav: same bass line + a harmony fifth above each note (2-note polyphony)
"""
import json
import numpy as np
import soundfile as sf

SR = 44100


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def bass_note(midi, dur, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    f = note_freq(midi)
    env = np.minimum(1.0, t / 0.01) * np.exp(-t * 2.2)
    sig = (np.sin(2 * np.pi * f * t)
           + 0.4 * np.sin(2 * np.pi * 2 * f * t)
           + 0.2 * np.sin(2 * np.pi * 3 * f * t)) * env
    return sig / (np.abs(sig).max() + 1e-12) * 0.8


# (a) bass line: A1 A1 C2 E2 | G1 G1 E2 C2  (MIDI 33,33,36,40,31,31,40,36)
bass_midis = [33, 33, 36, 40, 31, 31, 40, 36]
note_dur, gap = 0.45, 0.05
bass = np.array([], dtype=np.float64)
bass_truth = []
cursor = 0.0
for m in bass_midis:
    bass_truth.append({"midi": m, "start": round(cursor, 3), "dur": note_dur})
    bass = np.concatenate([bass, bass_note(m, note_dur),
                           np.zeros(int(gap * SR))])
    cursor += note_dur + gap
sf.write("bass.wav", bass.astype(np.float32), SR)
json.dump(bass_truth, open("bass.json", "w"), indent=1)
print(f"bass.wav: {len(bass_midis)} notes, {cursor:.2f}s")

# (c) polyphonic: bass + perfect fifth above (7 semitones)
poly = np.array([], dtype=np.float64)
poly_truth = []
cursor = 0.0
for m in bass_midis:
    n1, n2 = bass_note(m, note_dur), bass_note(m + 7, note_dur) * 0.6
    poly = np.concatenate([poly, n1 + n2, np.zeros(int(gap * SR))])
    poly_truth.append({"midis": sorted([m, m + 7]), "start": round(cursor, 3), "dur": note_dur})
    cursor += note_dur + gap
poly = poly / (np.abs(poly).max() + 1e-12) * 0.85
sf.write("bass_poly.wav", poly.astype(np.float32), SR)
json.dump(poly_truth, open("bass_poly.json", "w"), indent=1)
print(f"bass_poly.wav: {len(poly_truth)} two-note chords")


# (b) drum pattern: 2 bars of 8th notes @120bpm (0.25s step), 16 steps
def kick(dur=0.30):
    t = np.arange(int(dur * SR)) / SR
    f = 150 * np.exp(-t * 30) + 45
    phase = 2 * np.pi * np.cumsum(f) / SR
    env = np.exp(-t * 18)
    return (np.sin(phase) * env * 0.9).astype(np.float64)


def snare(dur=0.22):
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(len(t))
    # band emphasis around 2kHz via simple resonant-ish shaping: highpass + lowpass combo
    from scipy.signal import butter, sosfilt
    sos = butter(4, [400, 6000], btype="band", fs=SR, output="sos")
    shaped = sosfilt(sos, noise)
    env = np.exp(-t * 22)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    sig = shaped / (np.abs(shaped).max() + 1e-12) * 0.7 * env + body
    return sig


def hat(dur=0.06):
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(13)
    noise = rng.standard_normal(len(t))
    from scipy.signal import butter, sosfilt
    sos = butter(6, 7000, btype="highpass", fs=SR, output="sos")
    shaped = sosfilt(sos, noise)
    env = np.exp(-t * 120)
    return shaped / (np.abs(shaped).max() + 1e-12) * 0.5 * env


# pattern over 16 eighth-note steps: K = kick, S = snare, H = closed hat
pattern = [
    ("kick",), ("hat",), ("hat",), ("kick",),
    ("snare",), ("hat",), ("kick",), ("hat",),
    ("kick",), ("hat",), ("hat",), ("snare",),
    ("hat",), ("kick",), ("snare",), ("hat",),
]
step = 0.25
total = step * 16 + 0.5
drums = np.zeros(int(total * SR))
drum_truth = []
synth = {"kick": kick, "snare": snare, "hat": hat}
for i, hits in enumerate(pattern):
    t0 = i * step
    for h in hits:
        s = synth[h]()
        idx = int(t0 * SR)
        drums[idx:idx + len(s)] += s
        drum_truth.append({"label": h, "start": round(t0, 3)})
drums = drums / (np.abs(drums).max() + 1e-12) * 0.85
sf.write("drums.wav", drums.astype(np.float32), SR)
json.dump(drum_truth, open("drums.json", "w"), indent=1)
print(f"drums.wav: {len(drum_truth)} hits, {total:.2f}s")
