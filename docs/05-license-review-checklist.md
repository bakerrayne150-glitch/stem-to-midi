# License Review Checklist (2026-09-20)

Engineering notes only — **not legal advice**. Every item below must be cleared before a paid release.

## Status by dependency

| Component | Code license | Weights/model license | Status |
|---|---|---|---|
| Demucs (separator) | MIT (repo states; project is archived) | **Unclear** — README doesn't separately clarify pretrained-weight redistribution rights | ⛔ Do NOT bundle weights until reviewed; first-run download is the safe path |
| Basic Pitch (transcription) | Apache 2.0 | Bundled with the package (Apache 2.0 per repo) | ✅ Pin exact release + bundled model; include notices |
| `htdemucs_6s` model quality | — | Demucs docs flag it experimental, weak piano separation | ⚠️ UI must show confidence/warnings; don't oversell |
| Librosa (onset analysis) | ISC | n/a | ✅ Include notice |
| Mido (MIDI I/O) | MIT | n/a | ✅ Include notice |
| PySide6/Qt (UI) | LGPLv3 / commercial | n/a | ⚠️ Comply with LGPL (dynamic linking, license text) or buy commercial |
| PyInstaller | GPLv2 with exception | n/a | ✅ Exception covers bundled apps; include notices |
| Torch (CPU) | BSD-style | n/a | ✅ Include notice |
| Essentia MTG models | — | CC BY-NC-SA 4.0 (non-commercial) | ⛔ Do NOT use in the paid build without a separate commercial license |

## Rules for the build

- Pin every dependency and model version; record checksums.
- Review code and model-weight licenses **separately** — a permissive code license does not cover the weights.
- Include third-party notices in the installer and About screen.
- Confirm the preview SoundFont's redistribution rights before bundling it (not yet selected).
- Show users a reminder that they must have the right to process and reuse source audio.
- No Essentia MTG weights in the paid build.

## Open questions

1. Demucs pretrained-weight redistribution rights (the big one — blocks bundling).
2. PySide6 LGPL compliance vs commercial license cost.
3. Preview SoundFont selection + redistribution rights.
4. Whether first-run model download (with consent + digest verification) is acceptable UX vs bundling.
