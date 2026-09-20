#!/usr/bin/env python3
"""debug drums: dump spectral features at each ground-truth onset."""
import json
import numpy as np
import librosa

SR = 22050


def band_ratio(mag, freqs, lo, hi):
    m = (freqs >= lo) & (freqs < hi)
    return float(mag[m].sum() / (mag.sum() + 1e-12))


for name in ["drums"]:
    y, _ = librosa.load(f"{name}.wav", sr=SR, mono=True)
    truth = json.load(open(f"{name}.json"))
    print(f"== {name}.wav ==")
    for ev in truth:
        t = ev["start"]
        s = max(0, int((t - 0.010) * SR))
        e = min(len(y), int((t + 0.060) * SR))
        win = y[s:e]
        S = np.abs(librosa.stft(win, n_fft=1024, hop_length=256))
        mag = S.mean(axis=1)
        freqs = librosa.fft_frequencies(sr=SR, n_fft=1024)
        cent = float(np.sum(freqs * mag) / (mag.sum() + 1e-12))
        low = band_ratio(mag, freqs, 20, 250)
        lowmid = band_ratio(mag, freqs, 250, 1000)
        mid = band_ratio(mag, freqs, 1000, 4000)
        high = band_ratio(mag, freqs, 4000, SR / 2)
        n20, n60 = int(0.020 * SR), int(0.060 * SR)
        ee = float(np.sum(win[:n20] ** 2) + 1e-12)
        el = float(np.sum(win[n20:n60] ** 2) + 1e-12)
        flat = float(librosa.feature.spectral_flatness(S=S).mean())
        print(f"{ev['label']:6s} t={t:.2f} cent={cent:7.0f} "
              f"low={low:.2f} lowmid={lowmid:.2f} mid={mid:.2f} high={high:.2f} "
              f"decay={ee/el:6.1f} flat={flat:.2f}")
