# Building the Windows app

Everything here runs **on a Windows PC** — a Windows `.exe` can't be built
from Mac/Linux. You need ~10 GB free disk and an internet connection.

## What you need installed first

1. **Python 3.11** — https://www.python.org/downloads/
   - On the first installer screen tick **"Add python.exe to PATH"**.
   - Must be 3.11, not 3.12+: some audio libraries have no 3.12 Windows wheels.
2. *(Optional, for the installer step)* **Inno Setup 6** — https://jrsoftware.org/isinfo.php

## Build steps

1. Copy the whole project folder to the Windows PC (e.g. `C:\stem-to-midi`).
2. Double-click **`packaging\windows\build.bat`**.
3. It will:
   - create a virtual environment (`venv-win`),
   - install PyTorch **CPU** builds (small; the normal PyPI wheels are multi-GB CUDA),
   - install everything else, including Demucs and Basic Pitch **without**
     TensorFlow (the app uses Basic Pitch's lighter ONNX model on Windows),
   - run the headless smoke test — the build stops here if anything is broken,
   - run PyInstaller.
4. Result: **`dist\Stem2MIDI\Stem2MIDI.exe`** — double-click to run the app.

## Making an installer (optional)

1. Open `packaging\windows\installer.iss` in Inno Setup, press **Compile**.
2. You get `Stem2MIDI-Setup-0.1.0.exe` — the thing you hand to users.

## First launch notes

- **Model downloads:** Demucs' separation models (~50–150 MB) download
  automatically on first use into `%LOCALAPPDATA%\Stem2MIDI\models`.
  The first separation takes a while; later runs reuse the files.
- **Unsigned .exe:** Windows SmartScreen will warn on first run because the
  .exe isn't code-signed yet. Click *More info → Run anyway*. A code-signing
  certificate removes this before you sell it.
- **"DLL load failed" errors:** install the Microsoft C++ redistributable
  (https://aka.ms/vs/17/release/vc_redist.x64.exe) and re-run build.bat.

## What's already handled in the code

- `app/main.py` calls `multiprocessing.freeze_support()` and, in the frozen
  build, points model storage at `%LOCALAPPDATA%\Stem2MIDI\models` and forces
  the ONNX pitch model.
- `app/pipeline.py` uses the `spawn` process mode on Windows (`fork`
  doesn't exist there).

## Before selling

Still open from the launch checklist: code-signing certificate, the
trial/license-key system, the real-song accuracy benchmark, and the 7th-stem
experiment. The build this produces is the full working app, unlicensed.
