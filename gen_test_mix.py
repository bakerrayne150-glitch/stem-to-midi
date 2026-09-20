#!/usr/bin/env python3
"""gen_test_mix.py — synthesize a ~20s full mix with known ground truth.

mix.wav: 8 bars @100 BPM (19.2s)
  - bass: quarter-note line, known MIDI notes
  - drums: kick 1&3, snare 2&4, closed hats on 8ths, known hit times
  - pad: one triad per 2 bars (Am F C G), known chords
  - vocal: sine+vibrato melody, one note per bar, known notes
Ground truth -> mix_truth.json
"""
import json
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 44100
BPM = 100
BEAT = 60.0 / BPM
BARS = 8
TOTAL = BARS * 4 * BEAT  # 19.2s


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def place(buf, sig, t0):
    i = int(t0 * SR)
    n = min(len(sig), len(buf) - i)
    if n > 0:
        buf[i:i + n] += sig[:n]


def bass_note(midi, dur):
    t = np.arange(int(dur * SR)) / SR
    f = note_freq(midi)
    env = np.minimum(1.0, t / 0.01) * np.exp(-t * 2.2)
    sig = (np.sin(2 * np.pi * f * t)
           + 0.4 * np.sin(2 * np.pi * 2 * f * t)
           + 0.2 * np.sin(2 * np.pi * 3 * f * t)) * env
    return sig / (np.abs(sig).max() + 1e-12) * 0.8


def kick(dur=0.30):
    t = np.arange(int(dur * SR)) / SR
    f = 150 * np.exp(-t * 30) + 45
    phase = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(phase) * np.exp(-t * 18) * 0.9)


def snare(dur=0.22):
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(len(t))
    sos = butter(4, [400, 6000], btype="band", fs=SR, output="sos")
    shaped = sosfilt(sos, noise)
    env = np.exp(-t * 22)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    return shaped / (np.abs(shaped).max() + 1e-12) * 0.7 * env + body


def hat(dur=0.06):
    t = np.arange(int(dur * SR)) / SR
    rng = np.random.default_rng(13)
    noise = rng.standard_normal(len(t))
    sos = butter(6, 7000, btype="highpass", fs=SR, output="sos")
    shaped = sosfilt(sos, noise)
    return shaped / (np.abs(shaped).max() + 1e-12) * 0.5 * np.exp(-t * 120)


def pad_chord(midis, dur):
    """Soft detuned-saw-ish triad with slow attack (kind to separators)."""
    t = np.arange(int(dur * SR)) / SR
    sig = np.zeros_like(t)
    rng = np.random.default_rng(42)
    for m in midis:
        f = note_freq(m)
        tone = sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 2, 3))
        sig += tone * (0.5 + 0.5 * np.sin(2 * np.pi * 0.4 * t + rng.uniform(0, 6)))
    attack = np.minimum(1.0, t / 0.4)
    release = np.minimum(1.0, (dur - t) / 0.5).clip(0, 1)
    sig = sig * attack * release
    return sig / (np.abs(sig).max() + 1e-12) * 0.35


def vocal_note(midi, dur):
    """Sine + vibrato + breath of harmonic: a 'vocal-ish' melody line."""
    t = np.arange(int(dur * SR)) / SR
    f = note_freq(midi)
    vib = 1.0 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
    phase = 2 * np.pi * np.cumsum(f * vib) / SR
    env = np.minimum(1.0, t / 0.05) * np.minimum(1.0, (dur - t) / 0.08).clip(0, 1)
    sig = (np.sin(phase) + 0.25 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)) * env
    return sig / (np.abs(sig).max() + 1e-12) * 0.55


# ---- arrangement -----------------------------------------------------------
# bass roots per bar: Am F C G Am F C E  (quarter notes, root each beat)
bass_roots = [33, 29, 36, 31, 33, 29, 36, 28]  # A1 F1 C2 G1 A1 F1 C2 E1
# pad chords per 2 bars
pad_chords = [[57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62]]  # Am F C G
# vocal melody, one note per bar
vocal_midis = [64, 67, 69, 72, 71, 69, 67, 64]  # E4 G4 A4 C5 B4 A4 G4 E4

n_total = int((TOTAL + 0.5) * SR)
bass = np.zeros(n_total)
drum = np.zeros(n_total)
pad = np.zeros(n_total)
vox = np.zeros(n_total)
truth = {"tempo": BPM, "bass": [], "drums": [], "pad": [], "vocal": []}

for bar in range(BARS):
    t_bar = bar * 4 * BEAT
    # bass: quarter notes on the root
    root = bass_roots[bar]
    for beat in range(4):
        t0 = t_bar + beat * BEAT
        place(bass, bass_note(root, BEAT * 0.9), t0)
        truth["bass"].append({"midi": root, "start": round(t0, 3), "dur": round(BEAT * 0.9, 3)})
    # drums: kick 1&3, snare 2&4, hats on 8ths
    for beat in range(4):
        t0 = t_bar + beat * BEAT
        if beat in (0, 2):
            place(drum, kick(), t0)
            truth["drums"].append({"label": "kick", "start": round(t0, 3)})
        else:
            place(drum, snare(), t0)
            truth["drums"].append({"label": "snare", "start": round(t0, 3)})
        for half in (0, 1):
            th = t0 + half * BEAT / 2
            place(drum, hat(), th)
            truth["drums"].append({"label": "hat", "start": round(th, 3)})
    # pad chord (changes every 2 bars)
    chord = pad_chords[bar // 2]
    t_pad = t_bar if bar % 2 == 0 else None
    if t_pad is not None:
        place(pad, pad_chord(chord, 2 * 4 * BEAT), t_pad)
        for m in chord:
            truth["pad"].append({"midi": m, "start": round(t_pad, 3),
                                "dur": round(2 * 4 * BEAT, 3)})
    # vocal: one note per bar
    vm = vocal_midis[bar]
    place(vox, vocal_note(vm, 4 * BEAT * 0.92), t_bar)
    truth["vocal"].append({"midi": vm, "start": round(t_bar, 3),
                          "dur": round(4 * BEAT * 0.92, 3)})

mix = bass * 1.0 + drum * 0.9 + pad * 1.0 + vox * 1.0
mix = mix / (np.abs(mix).max() + 1e-12) * 0.85

sf.write("mix.wav", mix.astype(np.float32), SR)
# also write isolated parts for reference
sf.write("mix_bass_ref.wav", (bass / (np.abs(bass).max() + 1e-12) * 0.8).astype(np.float32), SR)
sf.write("mix_drums_ref.wav", (drum / (np.abs(drum).max() + 1e-12) * 0.8).astype(np.float32), SR)
sf.write("mix_pad_ref.wav", (pad / (np.abs(pad).max() + 1e-12) * 0.8).astype(np.float32), SR)
sf.write("mix_vocal_ref.wav", (vox / (np.abs(vox).max() + 1e-12) * 0.8).astype(np.float32), SR)
json.dump(truth, open("mix_truth.json", "w"), indent=1)
print(f"mix.wav: {TOTAL:.1f}s @ {BPM} BPM | "
      f"bass {len(truth['bass'])} notes, drums {len(truth['drums'])} hits, "
      f"pad {len(truth['pad'])} chord tones, vocal {len(truth['vocal'])} notes")
