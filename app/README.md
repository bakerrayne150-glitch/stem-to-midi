# Stem-to-MIDI Workspace (Phase C)

Desktop correction workspace for the stem-to-midi converter.

## Launch

```bash
cd ~/workspace/stem-to-midi
./venv/bin/python -m app.main
```

Headless check:

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m app.smoke_test
```

## Layout

- **Top toolbar:** Open, mode (full mix 6/4 stems or isolated stem), Process,
  Cancel + progress, Undo/Redo, Save/Open session, Export, Audition selection.
- **Left:** stem list with note counts; selected-stem controls (Mute, Solo,
  Source/MIDI preview toggle, Rename).
- **Center:** waveform (click to seek) above the piano roll / drum grid,
  sharing one time axis, zoom slider and scrollbar.
- **Right:** transcription profile, confidence threshold, quantize grid +
  strength, min note/gap, pitch range, merge overlaps, fixed velocity;
  Apply cleanup, Re-run this stem (no re-separation), Revert to raw detection.
- **Bottom:** transport (Play/Pause/Stop/Loop), Source/MIDI A-B, tempo,
  position, zoom.

## Piano roll editing

- Click a note to select (Shift-click adds), drag empty area for box select.
- Drag a note to move it (time + pitch); drag its right edge to resize.
- Double-click empty space to add a note; Delete key removes selection.
- Right-click a note for fast delete.
- Drum stems show a drum grid; vertical moves snap to kit rows.
- All edits are undoable (Ctrl+Z / Ctrl+Y). `A` auditions the selection.

## Pipeline

Separation runs in a child process so Cancel terminates it for real;
transcription runs in a worker thread with per-stem progress. Engine code is
reused from `separate.py`, `transcribe.py`, `midi_out.py` — the GUI adds no
new transcription logic.

## Session files

`*.stem2midi.json` stores paths, model/settings versions, raw + current
notes, edit history and export history. Missing audio files prompt for
relinking on open.

## Module map

| file | purpose |
|---|---|
| `main.py` | entry point |
| `main_window.py` | window, toolbar, transport, undo commands, dialogs |
| `widgets.py` | waveform, piano roll / drum grid, stem list |
| `worker.py` | background pipeline job (thread + cancellable process) |
| `pipeline.py` | importable pipeline stages, export |
| `player.py` | A/B preview playback with playhead |
| `synth.py` | built-in MIDI preview synth (renders to buffer) |
| `cleanup.py` | pure cleanup functions (threshold, quantize, …) |
| `models.py` | StemTrack / Project data model |
| `session.py` | save/load/relink session JSON |
| `smoke_test.py` | headless end-to-end verification |
