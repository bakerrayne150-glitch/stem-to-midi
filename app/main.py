#!/usr/bin/env python3
"""Entry point: cd ~/workspace/stem-to-midi && ./venv/bin/python -m app.main"""
import multiprocessing as mp
import os
import sys

# Make sure the engine modules (separate.py, transcribe.py, ...) import.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_FROZEN = getattr(sys, "frozen", False)

if _FROZEN:
    # Windows/macOS packaged build: the bundle ships the ONNX pitch model
    # (no TensorFlow), and model weights must live somewhere user-writable.
    os.environ.setdefault("BP_MODEL", "onnx")
    _data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    os.environ.setdefault(
        "TORCH_HOME", os.path.join(_data, "Stem2MIDI", "models")
    )

from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
from app.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stem-to-MIDI Workspace")
    apply_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # Required for multiprocessing ("spawn") inside a PyInstaller bundle.
    mp.freeze_support()
    main()
