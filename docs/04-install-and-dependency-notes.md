# Install & Dependency Notes (2026-09-20)

Working set from `~/workspace/stem-to-midi/requirements.txt`, plus every problem hit and its workaround. Environment so far: Linux, Python 3.12, CPU-only. **Windows target is Python 3.11**, where several of these problems should not occur — but re-verify.

## Working pins (Linux 3.12)

```
basic-pitch==0.4.0
tensorflow==2.16.2
ml_dtypes==0.5.4
numpy==1.26.4
scipy==1.14.1
scikit-learn==1.5.2
librosa==0.10.2
numba==0.60.0
resampy==0.4.3
soundfile==0.12.1
soxr==0.5.0
mido
pretty_midi
mir-eval
setuptools
torch==2.14.0+cpu
torchaudio==2.11.0+cpu
demucs==4.1.0
```

## Problems and workarounds

1. **basic-pitch uninstallable on Python 3.12.** basic-pitch 0.4.0 pins `tensorflow<2.15.1`; no TF <2.15.1 ships cp312 wheels. The resolver backtracked to ancient versions and died building numpy 1.23.5 from source (`No module named 'distutils'`). Workaround: install `tensorflow==2.16.2` first, then `pip install --no-deps basic-pitch==0.4.0`, then install its deps manually.
2. **numpy 1.x vs 2.x cascade.** TF 2.16 needs numpy<2 (`np.complex_` removal breaks it); current librosa/scipy want numpy≥2. Pinned `numpy==1.26.4, scipy==1.14.1, scikit-learn==1.5.2, librosa==0.10.2, numba==0.60.0` — a mutually compatible set.
3. **resampy 0.4.2 imports `pkg_resources`**, removed in setuptools≥81 → use 0.4.3 (violates basic-pitch's `<0.4.3` pin; works anyway).
4. **Bundled TF SavedModel won't load under TF 2.16** (`'_UserObject' object has no attribute 'add_slot'` — Keras 3 optimizer incompatibility). Used the bundled **TFLite** model (via `tensorflow.lite`) and **ONNX** model (via onnxruntime) instead. Also, 0.4.0's `predict_and_save` requires `model_or_model_path` positionally (API change vs older docs).
5. **`/tmp` too small** (512 MB tmpfs) for the TF wheel → install with `TMPDIR=~/tmp`.
6. **Torch CPU wheels don't come from PyPI.** Install from the PyTorch CPU index: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`. The CDN timed out twice during this build — retry with `--timeout 120 --retries 10`, or bundle wheels for the installer.
7. **Demucs weights download on first use** (~52 MB for `htdemucs_6s`) from `dl.fbaipublicfiles.com` into `./models/` (TORCH_HOME). demucs 4.1.0 itself installs from PyPI (pulls tqdm/pyyaml/einops/julius/huggingface-hub/lameenc).

## Footprint (Linux)

- venv: **3.4 GB** (TensorFlow dominates; torch CPU adds more).
- Demucs model cache: **133 MB**.
- Basic Pitch models themselves: ~200 KB.

## Windows build guidance

- Use **Python 3.11**: TF 2.13–2.15 ship cp311 wheels, so the stock basic-pitch pins likely resolve cleanly. Re-verify on a Windows machine.
- Ship the **ONNX** Basic Pitch model (`nmp.onnx` + onnxruntime) — validated quality-neutral vs TFLite, and avoids the SavedModel/Keras-3 problem entirely.
- Decide: bundle Demucs weights in the installer (needs license review — see `05-license-review-checklist.md`) or first-run download with digest verification and resume support.
