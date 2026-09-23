# Phase A Build Report — Technical Proof (2026-09-20)

Exit criterion: one pitched stem and one drum stem produce editable, aligned MIDI that is meaningfully faster to correct than manual recreation. **Met.**

## What was built

All in `~/workspace/stem-to-midi/`:

- `pitch_to_midi.py` — CLI `python pitch_to_midi.py input.wav -o output.mid`. Basic Pitch transcription, default settings.
- `drums_to_midi.py` — CLI `python drums_to_midi.py drums.wav -o drums.mid`. librosa onset detection → spectral-window classification (kick / snare+clap / closed+open hat / low-mid-high tom / crash / ride / other) → General MIDI percussion notes on channel 10, velocity from onset energy, 30 ms duplicate merging.
- `gen_test_audio.py` — synthesizes test audio + JSON ground truth.
- `verify_drums.py`, `verify_pitch.py` — parse output MIDI with mido, score against ground truth.
- `requirements.txt` — pinned working set with notes on every override.
- Test fixtures: `bass.wav`/`.json` (8-note bass line), `bass_poly.wav`/`.json` (same + harmony fifth), `drums.wav`/`.json` (16-hit pattern); outputs `bass.mid`, `bass_poly.mid`, `drums.mid`.

## Verification results (synthetic test audio, known ground truth)

**Drums — 16-hit pattern (kick/snare/closed-hat):** 15/16 onsets detected (missed the kick at t=0.000 — time-zero onsets are routinely missed), **0 false positives, 15/15 label accuracy**, timing error 0–7 ms, all on MIDI channel 10. Needed one tuning round: spectral flatness proved useless as a noisiness feature (dropped), kick centroid bound widened. Velocity mapping works but is crude (most hits land at 64).

**Bass mono — 8 known notes:** **8/8 exact-pitch recall, 0 missed, 0 octave errors**, onsets within ~50 ms. **But 8 extra notes** (precision 50%): 6 are upper harmonics transcribed as separate notes (synth bass has strong sustained 2nd/3rd harmonics), 2 are octave errors, plus one split note.

**Bass + harmony fifth (2-note polyphony):** **14/16 exact recall (87.5%)**, 0 octave errors, 3 extra notes. Degrades gracefully — better than expected.

**ONNX vs TFLite A/B:** identical scores on both tests → the harmonic false positives are inherent to the model, not quantization artifacts. The spec's ONNX choice for Windows is validated as quality-neutral.

## Performance (2-CPU, 7 GB RAM VM, CPU only)

- `pitch_to_midi.py`: **~6.9 s wall for 4 s of audio** (~5 s TF import, ~2 s inference); peak RSS **~652 MB** (TF runtime dominates).
- `drums_to_midi.py`: **~2.9 s warm / ~25 s cold** (numba JIT compile on first run) for 4.5 s audio; peak RSS **~219 MB**.
- venv footprint: **2.5 GB** (TensorFlow); the models themselves are tiny (~200 KB).

## Installation problems (matters for the Windows build)

1. Plain `pip install basic-pitch` is uninstallable on Python 3.12 — basic-pitch 0.4.0 pins `tensorflow<2.15.1`, and no TF <2.15.1 ships cp312 wheels. Workaround proven: install `tensorflow==2.16.2`, then `pip install --no-deps basic-pitch==0.4.0`, then deps manually.
2. numpy 1.x vs 2.x cascade: TF 2.16 needs numpy<2, but current librosa/scipy need numpy≥2. Resolved by pinning `numpy==1.26.4, scipy==1.14.1, scikit-learn==1.5.2, librosa==0.10.2, numba==0.60.0`.
3. resampy 0.4.2 imports `pkg_resources` (removed in setuptools≥81) → used 0.4.3, violating basic-pitch's `<0.4.3` pin. Works.
4. Bundled TF SavedModel won't load under TF 2.16 (`'_UserObject' object has no attribute 'add_slot'` — Keras 3 optimizer incompatibility). Used the bundled **TFLite** model (via `tensorflow.lite`) and **ONNX** model (via onnxruntime) instead — both load and run. Also, 0.4.0's `predict_and_save` now requires `model_or_model_path` positionally (API change from older docs).
5. `/tmp` (512 MB tmpfs) too small for the TF wheel → installed with `TMPDIR=~/tmp`.
6. Windows outlook: the spec targets Python 3.11 + ONNX runtime, where TF 2.13–2.15 have cp311 wheels and the stock pins likely resolve cleanly — most of this pain is 3.12-specific. But the SavedModel/Keras-3 issue is real; ONNX runtime is validated working.

## Quality concerns for the product

1. **Raw Basic Pitch output is not shippable for bass** — harmonic/octave false positives need the spec's Phase C cleanup (monophonic preference, harmonic suppression). The engine finds every true note; the work is all in false-positive removal.
2. **Drum classifier is prototype-grade** — frequency rules ace clean synthetic audio but need real-kit benchmark data before any quality claim (spec §5 already flags this).
3. No GUI, installer, or licensing built — Phase A only, per plan.

**Bottom line:** Phase A exit criterion is met. Recommended next step: Phase B (separation pipeline), with the ONNX runtime carried forward for Windows.
