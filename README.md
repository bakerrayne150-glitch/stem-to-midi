# Stem-to-MIDI Converter

A Windows desktop utility that converts audio stems into multitrack MIDI for use in any DAW (Sonar/Cakewalk, Reaper, Ableton, ...).

## What it does

- **Full-mix mode:** separates a mixed track into stems, then transcribes each one to MIDI
- **Pitched audio -> MIDI:** melody/bass transcription with confidence thresholding
- **Drums -> MIDI:** drum stems mapped onto a kit grid
- **Correction workspace:** waveform + piano-roll / drum-grid editor with undo/redo, quantization, and cleanup tools

## The app

Built with PySide6. See [app/README.md](app/README.md) for the full workspace manual (layout, piano-roll editing, pipeline, session files).

## Builds

Windows portable and installer builds run automatically via GitHub Actions (`.github/workflows/build-windows.yml`).

## Tech

Python · PySide6 · GitHub Actions
