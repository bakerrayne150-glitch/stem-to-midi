# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Stem-to-MIDI Workspace (Windows, one-dir build).

Run via build.bat — do not run this file by hand unless the venv-win
environment from build.bat is active.
"""
import importlib.util
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

import basic_pitch

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
BP_DIR = os.path.dirname(basic_pitch.__file__)

# Demucs resolves its pretrained-model index at runtime from
# <package>/remote/files.txt (plus the bag-definition *.yaml files in the
# same dir). PyInstaller's module collection grabs demucs' .py files but NOT
# these data files, so without this entry get_model() dies on first run with
# FileNotFoundError: '...\\demucs\\remote\\files.txt'. find_spec locates the
# package directory without importing it (importing demucs pulls in torch,
# which is too heavy for spec time).
_demucs_spec = importlib.util.find_spec("demucs")
if _demucs_spec is None or not _demucs_spec.submodule_search_locations:
    raise RuntimeError("demucs package not found — install requirements-windows.txt first")
_demucs_dir = _demucs_spec.submodule_search_locations[0]

# torch ships DLLs + data that PyInstaller's stock hooks miss.
torch_datas, torch_binaries, torch_hidden = collect_all("torch")
_, ta_binaries, ta_hidden = collect_all("torchaudio")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "app", "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=torch_binaries + ta_binaries,
    datas=[
        # Basic Pitch neural-net weights in ONNX form. The app loads this via
        # BP_MODEL=onnx (forced on in app/main.py when frozen), so no
        # TensorFlow is bundled.
        (
            os.path.join(BP_DIR, "saved_models"),
            os.path.join("basic_pitch", "saved_models"),
        ),
        # Demucs pretrained-model index (remote/files.txt) + bag-definition
        # yamls. Without these, first-run model download cannot even start.
        (
            os.path.join(_demucs_dir, "remote"),
            os.path.join("demucs", "remote"),
        ),
    ]
    + torch_datas,
    hiddenimports=[
        # demucs is imported lazily inside a function — PyInstaller can't see it.
        "demucs",
        "demucs.pretrained",
        "demucs.apply",
        "demucs.audio",
        "demucs.hdemucs",
        "demucs.models",
        "demucs.utils",
        # pitch / audio stack
        "basic_pitch",
        "basic_pitch.inference",
        "basic_pitch.note_creation",
        "basic_pitch.commandline_printing",
        "basic_pitch.constants",
        "onnxruntime",
        "librosa",
        "soundfile",
        "soxr",
        "resampy",
        "numba",
        "scipy",
        "sklearn",
        "mido",
        "pretty_midi",
        "mir_eval",
    ]
    + collect_submodules("demucs")
    + torch_hidden
    + ta_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Deliberately NOT bundled: TensorFlow (unused — ONNX path), CoreML,
    # TFLite runtime, Tk, tests.
    excludes=[
        "tensorflow",
        "tensorboard",
        "coremltools",
        "tflite_runtime",
        "tkinter",
        "matplotlib",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Stem2MIDI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX breaks torch/onnx DLLs; keep it off
    console=False,  # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Stem2MIDI",
)
