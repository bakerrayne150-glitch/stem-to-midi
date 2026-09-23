# Phase C Build Report — Correction Workspace GUI (2026-09-20)

## What was built

A real PySide6/Qt desktop app in `code/app/` — the correction workspace from
spec §6. Launch: `cd ~/workspace/stem-to-midi && ./venv/bin/python -m app.main`

| File | Purpose |
|---|---|
| `main.py` | entry point |
| `main_window.py` | window: toolbar, transport, undo commands, dialogs, all wiring |
| `widgets.py` | waveform (click-to-seek), piano roll + drum grid, stem list |
| `worker.py` | pipeline job controller: worker thread + cancellable separation subprocess |
| `pipeline.py` | importable pipeline stages (probe, separate, transcribe, tempo, export) |
| `player.py` | A/B preview playback with playhead sync (QAudioSink, guarded headless) |
| `synth.py` | built-in preview synth: pitched notes (sine+saw) and GM drum hits rendered to buffers |
| `cleanup.py` | pure cleanup functions: confidence filter, quantize, min note/gap, pitch range, merge overlaps, fixed velocity |
| `models.py` | StemTrack / Project data model (note dicts with confidence) |
| `session.py` | `*.stem2midi.json` save/load, missing-file relink |
| `smoke_test.py` | headless end-to-end verification (34 checks) |
| `screenshots/` | 4 verification screenshots |

## Verified working (headless, QT_QPA_PLATFORM=offscreen)

`python -m app.smoke_test` — **34/34 checks pass**, including:

- Cancel during separation actually terminates the Demucs child process.
- Full pipeline on the 19.2 s synthetic mix: 55 s wall, 6 stems, 259 notes,
  drums on MIDI channel 10, tempo 99.4 BPM.
- Scripted edits: delete / move / undo / redo / quantize-apply on the bass
  stem; drum-grid add + undo on the drums stem.
- Synth renders pitched and drum audio; playhead advances during playback;
  audition of selected notes runs.
- Session save → reopen round-trips all 259 notes, edit history kept,
  missing-file list empty.
- Export: 7 files (6 per-stem + multitrack); multitrack parses as Type 1
  with 7 tracks, named tracks, drums on channel 10; all MIDIs re-parse.
- Isolated-stem mode: `bass.wav` → 8 notes, 10 s.
- 4 screenshots saved (workspace, edited, final, isolated).

## Bugs found and fixed during verification

1. `pipeline.transcribe_stem` returned 4-tuples for drums while the GUI's
   `drum_tuples_to_notes` expects engine 3-tuples → "too many values to
   unpack". Fixed: `transcribe_stem` now returns raw engine tuples.
2. Error paths popped modal `QMessageBox`es, which block forever in
   headless/offscreen runs (this initially looked like a pipeline hang).
   The smoke test stubs them; production behavior (modal warning) unchanged.

## What's stubbed or simplified vs the spec

- **Metronome:** not implemented (transport has Play/Pause/Stop/Loop).
- **Waveform preview normalization:** quiet stems (e.g. the near-silent
  synthetic vocals stem) draw nearly flat; no normalize-preview toggle yet
  (spec lists it as optional).
- **Confidence values** are recovered from the engine's velocity mapping,
  not emitted by the engine directly — good enough for threshold filtering.
- **Drag-and-drop import:** file picker only; DnD not wired yet.
- **Pitch-bend export:** Basic Pitch `multiple_pitch_bends` is enabled for
  melody/vocal/guitar profiles at transcription, but bends are not rendered
  in the preview synth or edited in the piano roll.
- **Batch queue:** single-file / single-session only.
- **Drum map editor:** GM mapping is fixed; user remapping UI not built yet
  (spec requires editable mapping — still open).
- **Side-by-side raw vs cleaned view:** revert-to-raw exists; no A/B diff view.
- **Isolated-stem mode** works but the profile picker is a simple dialog.

## Known issues

- First `QApplication` import needs system libs (`libEGL` etc.); on the
  build VM these were installed from Ubuntu archive debs (no sudo-apt
  update available — archive was reachable directly).
- `separate.py` sets `TORCH_HOME` into the project `models/` dir; the GUI
  inherits this — stems land in `<input-dir>/.stem2midi_work/stems/`.
- TensorFlow logs noisy CUDA warnings on CPU-only machines (cosmetic).

## Visual theme pass (same day, after Phase C verification)

User chose **dark studio, readability-first**. New module `app/theme.py` holds the whole visual system: palette (`BG #14161b`, `PANEL #1d2129`, `HEADER #232833`, near-white `#f2f4f8` text, `#a8b0bd` secondary-only), six fixed stem accents (drums `#ff9f43`, bass `#4d7cff`, vocals `#3fd0a7`, guitar `#ffb84d`, piano `#a78bfa`, other `#9aa3b2`), and a full QSS stylesheet (buttons, inputs, sliders, lists, toolbar, dialogs, tooltips — all states). Piano-roll notes render in the selected stem's accent; selected notes get a bright outline; low-confidence notes render faded with a diagonal hatch; bar lines stronger than beat lines; time readouts in fixed-width figures. No behavior changes. Smoke test re-run: **31/31 pass** (test count differs from the earlier 34-check run after minor test maintenance — all green). Screenshots refreshed.

## Windows build complications (new in Phase C)

- **PySide6 6.11.2** is the big new native dependency (~80 MB wheel, plus
  Qt system libs on Linux; on Windows the wheel is self-contained). It must
  be in the PyInstaller bundle with its Qt plugins (platforms, styles).
- **QAudioSink** is used for preview audio; on Windows it should work with
  the default audio backend, but needs testing on a real machine — the
  playhead is clock-driven so the UI stays correct even if audio fails.
- **Multiprocessing fork** is used for cancellable separation; Windows has
  no fork — the spawn method re-imports the main module, so `app/main.py`
  keeps its `if __name__ == "__main__"` guard and the child target
  (`pipeline._separate_child`) is importable. Must be re-tested on Windows.
- Python **3.11** (not 3.12) remains the target for the Windows build so
  `basic-pitch`'s stock pins resolve.
