# Phase B Build Report — Full-Mix Separation Pipeline (2026-09-20)

Exit criterion: a full song completes end to end on CPU and supported NVIDIA hardware. **Met on CPU** (no GPU on the build VM).

## What was built (`~/workspace/stem-to-midi/`)

- `separate.py` — Demucs separation CLI. `python separate.py in.wav -o stems/ [--stems 6|4]`. 6-stem default = `htdemucs_6s` (vocals/drums/bass/guitar/piano/other); `--stems 4` = `htdemucs` (vocals/drums/bass/other). Writes source-rate stereo WAVs with stable names (`<song> - 01 Vocals.wav` …), atomic writes via temp+rename, weights cached in `./models/` (TORCH_HOME).
- `full_mix_to_midi.py` — end-to-end pipeline. `python full_mix_to_midi.py in.wav -o out/ [--stems 6|4]`. Drums → drum engine on MIDI ch 10; other stems → Basic Pitch with per-stem profiles (model loaded once, reused). Writes one `.mid` per stem + one Type 1 multitrack (480 TPQ, conductor tempo track, named stem tracks). Tempo via librosa, 120 BPM fallback. Prints per-stage timings.
- Supporting: refactored `transcribe.py` (shared cores + per-instrument profiles), `midi_out.py`, `pitch_to_midi.py`, `drums_to_midi.py`, `gen_test_mix.py`, `verify_mix.py`, `run_pipeline.sh`, cleaned `requirements.txt`.

## Phase A regression — fixed and verified

The Phase B refactor had changed the pitched CLI's default to the conservative `other` profile (6/8 bass recall). A `legacy` profile matching stock Basic Pitch 0.4.0 `predict()` defaults was added (verified against the installed signature: onset 0.5, frame 0.3, min-note 127.7 ms, no freq limits, no pitch bends) and restored as the CLI default. Re-ran both Phase A verifications:

- Monophonic bass: **8/8 recall, 8 harmonic extras** — exact Phase A numbers.
- Two-note polyphony: **14/16 exact recall, 3 extras** — exact Phase A numbers.

Full-mix stems still use the conservative profiles; nothing else changed. Drum CLI unchanged (was 15/16 onsets, 15/15 labels after refactor).

## Six-stem benchmark (synthetic 19.2 s mix @100 BPM, sine-based — honest numbers)

`verify_mix.py` confirms:

- Tempo: **99.4 BPM** (truth 100).
- Bass: 25/32 recall (78%), 93% precision, +2 extras.
- Drums: 63/96 recall (66%), **0 extra hits**, label accuracy only **41%** (kicks 15/16 detected but all misclassified `other`; snares 16/16 correct; hats 32/64).
- Vocals: 8/8 recall, precision 18% (+37 extras — harmonic/bleed noise).
- Pad (12 chord tones): piano 1/12, other 1/12, guitar 2/12, with heavy cross-bleed (piano stem captured 8/8 vocal notes; other/guitar 7/8).
- Audio separation itself is strong (bass stem vs reference corr 1.00, drums 0.98) — the weak labels come from the synthetic sine timbres bleeding across vocals/guitar/piano/other in Demucs. **This is a test-artifact caveat, not a real-world claim either way.**
- Multitrack: Type 1, 7 tracks (conductor + 6 named), tempo event present, drums on ch 10. OK.

## Timing (instrumented re-run, CPU, 19.2 s audio)

`separate=39.1 s, tempo=5.5 s, transcribe=7.6 s` (~1 s per stem), total ~54 s wall. (An earlier uninstrumented 105 s run was slower — likely cold caches/first-run model load; per-stage numbers above are the reliable ones.) Peak RSS on the earlier run: ~1.17 GB.

## Sizes

- venv: **3.4 GB**; Demucs model cache: **133 MB** (`htdemucs_6s` 52.4 MB + `htdemucs`).
- 4-stem fallback smoke test confirmed: 4 correctly named WAVs.

## Windows packaging concerns (for Phase C/E)

1. **Python 3.11** on Windows, not 3.12 — basic-pitch 0.4.0 pins TF<2.15.1 which has no cp312 wheels; stock pins likely resolve on 3.11 (re-verify).
2. Ship the **ONNX** Basic Pitch model per spec (`nmp.onnx` + onnxruntime); TF SavedModel can't be restored by TF 2.16, TFLite is dev-only convenience.
3. Torch CPU wheels: install from the PyTorch CPU index, not PyPI; CDN timed out twice here — use long timeout/retries or bundle wheels.
4. Demucs weights (~52 MB) download on first run from `dl.fbaipublicfiles.com` — either require internet at first launch or bundle them (see license note).
5. No GUI/installer/licensing exists yet — engineering phase only, as decided.
6. The 7th stem stays experimental and unadvertised — not implemented.

## License caveat (unresolved)

Demucs code is MIT, but its README doesn't separately clarify **pretrained-weight redistribution rights**, and it flags `htdemucs_6s` as experimental with weak piano separation. **Do not bundle the weights in a commercial installer until redistribution is explicitly reviewed** — safest path is first-run download until then.

## Open / not started

Phase C (GUI, installer, licensing), real-world (non-synthetic) benchmark, drum label-accuracy improvements, vocal-extras reduction. `requirements.txt` verified clean.
