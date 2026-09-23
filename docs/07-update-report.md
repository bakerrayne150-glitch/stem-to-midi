# 07 — Accuracy, per-stem export choice, and mixer-UI restyle (2026-09-23)

Third update to the Stem2MIDI Windows app, delivered as a single commit on top of
the Phase C codebase. Three scoped additions, all validated on CPU with the
existing synthetic test fixtures. One push → one Windows CI build.

## 1. Better MIDI transcription accuracy

### Bass: dedicated monophonic engine (`transcribe.py::transcribe_bass`)
Bass no longer goes through Basic Pitch. New pipeline:

- `librosa.pyin` (CPU), fmin 27.5 Hz – fmax 330 Hz at 22 050 Hz
- median-filtered pitch contour, short unvoiced gaps (≤ ~60 ms) bridged
- splits on sustained pitch changes > 0.6 semitone
- repeated same-pitch attacks split on local RMS valleys
- segments < 120 ms dropped; median Hz → rounded MIDI; per-note RMS → velocity
- falls back to the old Basic Pitch bass profile if pyin finds nothing

Routing: `app/pipeline.py::transcribe_stem` and `full_mix_to_midi.py::ENGINE_FOR`
send bass to the new engine; the `pitch_to_midi.py --profile bass` CLI is
unchanged (still Basic Pitch).

### Drums: refined classifier (`transcribe.py::classify_hit`)
Added spectral rolloff, zero-crossing rate, and high-frequency sustain to the
feature set — better open/closed hi-hat separation and cleaner noisy-snare vs
tonal-tom decisions. Hit count unchanged.

### Overlap cleanup (`transcribe.py::merge_overlaps`)
Merges overlapping same-pitch notes after each stem's transcription
(`full_mix_to_midi.py`), handling interleaved pitches and verified idempotent.

## 2. Per-stem WAV/MIDI keep choice

`app/pipeline.py::export_all(..., stem_exports=None)` — optional per-stem map
`{label: {"midi": bool, "wav": bool}}`. `None` (or a missing entry/key) falls
back to the old global `per_stem`/`wavs` flags, so existing callers are
unaffected.

The export dialog (`app/main_window.py::ExportDialog`) now shows one row per
stem with separate **MIDI** and **WAV** checkboxes (all on by default) plus the
global **Multitrack MIDI (Type 1)** checkbox. The main window passes
`stem_exports=dlg.stem_exports()` through.

## 3. Mixer-console UI restyle (stemconsole.ai spirit)

- **Welcome empty state:** when no project is loaded the center panel shows a
  drop-zone card — big "Drop an audio file here", "or click to browse…"
  (wired to the existing open-file flow), mode combo (6/4 stems / isolated),
  and a prominent Process button. The main window accepts OS drag-and-drop of
  audio files (`.wav .flac .mp3 .m4a .ogg`) into the existing open path.
- **Mixer channel strips:** the stem list is now per-row `StemRowWidget` cards
  via `setItemWidget` — left accent-color bar (existing stem accents), bold
  stem name + dim note count, small **M**/**S** toggle buttons per row wired to
  the existing mute/solo logic (row buttons and the "Selected stem" group box
  stay in sync both ways). Row height 44 px; selected row painted with the stem
  accent. The "Selected stem" group box (rename, Source/MIDI preview) is
  unchanged.
- **Transport bar:** Play/Pause/Stop/Loop, A/B combo, tempo + time labels
  (tabular-font readouts), and the zoom slider moved out of the `QStatusBar`
  into a dedicated slim bottom bar. The status bar now shows messages only.
- **Theme polish (`app/theme.py`):** 8 px card radius (`QFrame[card="true"]`,
  `QGroupBox`, `QListWidget`), small-caps dim section headers
  (`QLabel[section="true"]` → "STEMS", "TRANSCRIPTION"). Stylesheet only;
  `apply_theme` is now explicitly idempotent.

No new dependencies. No changes to the experimental 7th stem, code signing,
trial/licensing, or the landing page.

## Verification (all on CPU, synthetic fixtures)

| Check | Before | After |
|---|---|---|
| Bass, isolated (`bass.wav`, Basic Pitch → pyin) | recall 6/8, 2 extras | **recall 8/8, 0 extras** |
| Drums, isolated (`drums.wav`) | 15/16 recall, 3 hats mislabeled open | **15/16 recall, 8/8 hats correctly closed**, 0 FP |
| Bass, full mix (`verify_mix.py`) | recall 0.75 (24/32), prec 0.92 | **recall 0.97 (31/32), prec 0.97** |
| Drums, full mix | recall 0.66 (63/96), label-acc 0.40 | recall 0.66 (63/96), **label-acc 0.62** |
| Multitrack MIDI | valid Type 1, 7 tracks, drums ch 10 | valid Type 1, 7 tracks, drums ch 10 |
| GUI smoke test (`app/smoke_test.py`) | 34/34 | **36/36** (incl. 2 new per-stem-export checks) |

Notes: the full-mix vocal/pad stems show small count shifts vs the Sep-20
baseline output, traced to Demucs separation variance (stem WAVs differ;
Basic Pitch is deterministic run-to-run and `merge_overlaps` only ever
removes notes). Bass/drums comparisons above are the apples-to-apples
accuracy story. Accuracy claims still rest on synthetic fixtures, not real
songs (known open item from the sellability assessment).

## Project structure (post-update)

```
stem-to-midi/
├── separate.py            # Demucs full-mix → 6 stem WAVs
├── transcribe.py          # drum + pitched + NEW pyin bass engines, merge_overlaps
├── full_mix_to_midi.py    # CLI: mix → stems → per-stem MIDI + multitrack
├── drums_to_midi.py       # CLI: isolated drum stem → MIDI
├── pitch_to_midi.py       # CLI: isolated pitched stem → MIDI (Basic Pitch)
├── midi_out.py            # MIDI writers (single stem + Type 1 multitrack)
├── gen_test_audio.py      # synthetic fixture generators (drums.wav, bass.wav…)
├── gen_test_mix.py        # synthetic full-mix fixture (mix.wav + mix_truth.json)
├── verify_drums.py verify_pitch.py verify_mix.py
├── requirements.txt
├── app/
│   ├── main.py            # entry point (BP_MODEL=onnx)
│   ├── main_window.py     # welcome card, strips, transport bar, export dialog
│   ├── widgets.py         # WaveformWidget, PianoRollWidget, StemRowWidget/StemListWidget
│   ├── theme.py           # dark-studio theme (idempotent apply_theme)
│   ├── pipeline.py        # Qt pipeline worker, per-stem export_all
│   ├── player.py          # source/MIDI A-B audition engine
│   ├── models.py synth.py worker.py
│   └── smoke_test.py      # 36 headless GUI checks (QT_QPA_PLATFORM=offscreen)
├── .github/workflows/build-windows.yml   # CI: Windows .exe + installer (BP_MODEL=onnx)
└── packaging/             # PyInstaller spec, installer config
```
