# Stem-to-MIDI Converter — Documentation Bundle

Compiled 2026-09-20. Everything produced so far for the Windows stem-to-MIDI converter project (passive-income app for Sonar/Cakewalk and other DAW users).

## What's in here

| File | Contents |
|---|---|
| `01-product-spec.md` | Full v1 product specification: vision, scope, stem strategy, conversion engines, UX, output contract, architecture, requirements, acceptance criteria, monetization, build plan, risks |
| `02-phase-a-report.md` | Phase A build report: pitched→MIDI and drum→MIDI proof of concept, verification numbers, install problems, performance |
| `03-phase-b-report.md` | Phase B build report: full-mix separation pipeline (6 stems → per-stem MIDI + multitrack MIDI), benchmark numbers, packaging concerns |
| `04-install-and-dependency-notes.md` | Working dependency set and every install problem hit so far, with workarounds |
| `05-license-review-checklist.md` | Third-party code/model license status and what must be reviewed before selling |
| `06-phase-c-report.md` | Phase C build report: PySide6 correction workspace, verification results, stubbed items, Windows complications |
| `07-update-report.md` | 2026-09-23 update: pyin bass engine, refined drum classifier, per-stem WAV/MIDI export choice, mixer-console UI restyle — with before/after verification numbers and current project structure |
| `code/` | Full source snapshot: pipeline scripts, Qt app (`code/app/`), test fixtures, verification scripts, `requirements.txt` |

## Project status

- **Phase A (technical proof):** done — pitched stem and drum stem both produce aligned, editable MIDI on CPU.
- **Phase B (full-mix pipeline):** done — `full_mix_to_midi.py` runs mix → 6 stems → MIDI end to end.
- **Phase C (desktop correction workspace):** in progress — PySide6 app with preview, editing, cleanup, sessions.
- **Phase D (7th-stem research), Phase E (paid Windows release):** not started.

## Code location

The full source snapshot is in `code/` in this bundle: all pipeline scripts (`separate.py`, `transcribe.py`, `full_mix_to_midi.py`, `pitch_to_midi.py`, `drums_to_midi.py`, `midi_out.py`), the in-progress Qt app (`code/app/`), test fixtures (synthetic WAVs + ground-truth JSON), verification scripts, and `requirements.txt`.

Not included (regenerable / too large): the Python venv (3.4 GB — reinstall from `requirements.txt`), the Demucs model weights (133 MB — download on first run), and `__pycache__`. Note `code/app/` is a mid-build snapshot — Phase C is still in progress.

The live source also lives in `~/workspace/stem-to-midi/` on the build machine.

## Key decisions on record

- Windows 10/11 64-bit, Python 3.11, PySide6 UI, local-only processing.
- Demucs `htdemucs_6s` for separation (6 stems); 4-stem fallback available.
- Basic Pitch via ONNX runtime for pitched transcription; librosa onset + spectral classification for drums.
- 7th stem stays experimental and unadvertised until quality + license gates pass.
- Trial + one-time purchase model (price TBD, $30–50 hypothesis untested).
- Demucs weights must NOT be bundled in a commercial installer until redistribution rights are reviewed — first-run download is the safe path.
