# Stem-to-MIDI Converter

## Version 1 product specification

**Product type:** Windows desktop utility  
**Primary user:** Producers working in Sonar/Cakewalk and other DAWs without a strong built-in audio-to-MIDI workflow  
**Core promise:** Drop in a full mix or isolated stem, separate the instruments when needed, and export editable, DAW-ready MIDI without uploading audio to a server.

---

## 1. Product vision

The app turns recorded audio into useful MIDI with the fewest possible steps. It is not a full DAW and does not pretend that automatic transcription is perfect. Its value is speed: it creates a clean starting point, exposes confidence and cleanup controls, and makes correction faster than rebuilding parts by ear.

### Product principles

- **Local-first:** Audio stays on the user's computer.
- **Focused:** Separation, transcription, cleanup, preview, and export only.
- **Honest:** Low-confidence notes and uncertain instrument labels are visible.
- **DAW-ready:** Exports open cleanly in Sonar/Cakewalk and other Windows DAWs.
- **Useful without a GPU:** CPU mode works; a supported NVIDIA GPU accelerates separation.

### Success statement

A producer can drag in a song, receive labeled stems, preview the detected notes, correct obvious mistakes, and export a multitrack MIDI file in one session.

---

## 2. Target customer and use cases

### Primary customer

A Windows-based bedroom producer, beatmaker, remixer, or musician who wants to:

- recover a bass line, melody, chord part, vocal melody, or drum pattern from audio;
- rebuild or remix a reference track;
- replace sounds while preserving the original performance;
- move detected parts into Sonar/Cakewalk without assembling several command-line tools.

### Main jobs to be done

1. **Single-stem conversion:** Convert an isolated bass, melody, vocal, piano, guitar, or drum recording to MIDI.
2. **Full-mix conversion:** Split a song into labeled stems, then transcribe each useful stem.
3. **Drum extraction:** Create General MIDI drum notes from a drum stem or full mix.
4. **Batch conversion:** Process several stems or songs with the same settings.
5. **Fast correction:** Delete false notes, adjust timing, quantize, change thresholds, and re-export.

---

## 3. Scope decisions

### Included in version 1

- Windows 10/11, 64-bit.
- Local file processing after required models are installed.
- WAV, FLAC, MP3, M4A, and OGG input through a bundled or installed FFmpeg runtime.
- Single audio file and batch queue.
- Isolated-stem and full-mix modes.
- Up to six production audio stems: vocals, drums, bass, guitar, piano, and other.
- Experimental seventh-stem research preview only if its quality and commercial-license gates pass.
- Pitched-instrument and vocal transcription.
- Drum onset detection and kit-piece mapping.
- Piano-roll preview with audio/MIDI A/B playback.
- Cleanup controls and editable note events.
- Separate MIDI files and one Type 1 multitrack MIDI file.
- WAV stem export.
- Crash-safe job recovery and cancel/retry.

### Explicitly excluded from version 1

- macOS, mobile, and browser versions.
- VST3/AU plugin operation inside a DAW.
- Cloud processing, accounts, social features, and project sharing.
- Real-time live-input transcription.
- Sheet-music engraving.
- Training a new source-separation model.
- Guaranteed perfect separation or note transcription.
- Copy-protection that requires a permanent internet connection.

---

## 4. Stem strategy

### Reliable mode: six stems

The baseline separator produces:

1. Vocals
2. Drums
3. Bass
4. Guitar
5. Piano
6. Other

The proposed prototype uses Demucs `htdemucs_6s`. Its own documentation describes this six-source layout and warns that the piano output can contain substantial bleeding and artifacts. The UI must therefore show stem confidence and allow relabeling rather than presenting every label as certain.

### Experimental mode: up to seven stems

A seventh useful audio stem is a product goal, not something the six-source model produces by itself. Version 1 should implement it as a separately switchable experiment:

- analyze the `other` stem for a dominant extra family, initially **synth/keys**;
- run a commercially cleared secondary separator only when the detector's confidence passes a tested threshold;
- output `synth-keys.wav` plus a residual `other.wav`;
- otherwise retain the original `other.wav` and explain that no reliable seventh stem was found.

**Rule:** Classification may rename or route audio, but it must not be described as separation. The seventh stem ships only after listening tests show that it contains meaningfully isolated audio and that the chosen model weights are cleared for commercial distribution.

### Instrument detection

- Trust the separator's native labels for vocals, drums, bass, guitar, and piano, while displaying confidence or quality warnings.
- Analyze `other` in short windows rather than assigning one label to an entire song.
- Use a small controlled label set: synth/keys, strings, brass/winds, percussion, effects/texture, and unknown.
- Show the top label and confidence; show **Mixed/Unknown** below threshold.
- Let the user rename every stem and manually choose its transcription profile.
- Do not use non-commercial model weights in the paid build without a separate commercial license.

---

## 5. Conversion engines

### Pitched instruments and vocals

Use Spotify Basic Pitch as the first transcription engine. It supports polyphonic, instrument-agnostic transcription and pitch bends, and its documentation says it works best on one instrument at a time. That is why separation happens before transcription for full mixes.

Each profile adjusts the same engine differently:

- **Bass:** restricted pitch range, monophonic preference, octave-error cleanup, longer minimum note.
- **Melody/vocal:** single-note preference, pitch-bend option, legato cleanup.
- **Piano/keys:** polyphonic mode, sustain-aware overlap, chord preservation.
- **Guitar:** polyphonic mode, short-note suppression, optional pitch bends.
- **Other:** broad range, conservative threshold, no aggressive cleanup by default.

### Drum engine

Drums require a separate path because pitched-note transcription is the wrong abstraction.

1. Detect onset candidates from the isolated drum stem.
2. Extract a short spectral window around each onset.
3. Classify each hit into a compact kit vocabulary.
4. Map classes to General MIDI percussion notes.
5. Estimate velocity from onset energy.
6. Merge duplicate detections and suppress implausibly close hits.

Initial drum classes:

- Kick
- Snare/clap
- Closed hi-hat
- Open hi-hat
- Low, mid, and high tom
- Crash
- Ride
- Other percussion

Default mappings follow the General MIDI percussion convention, but the user can remap every class and save a kit preset. Librosa's onset detector is suitable for the first prototype because it locates events by peak-picking an onset-strength envelope. Hit classification still requires benchmark data; frequency-only rules are acceptable for a prototype, not for a paid quality claim.

### Timing and cleanup

- Preserve detected timing by default.
- Optional quantize grid: off, 1/4, 1/8, 1/16, 1/32, and triplet variants.
- Quantize strength: 0–100%.
- Minimum note length and minimum gap.
- Note confidence threshold.
- Velocity curve and fixed-velocity option.
- Pitch range filter.
- Merge same-pitch overlaps.
- Remove isolated notes shorter than the configured threshold.
- Global timing offset for latency correction.

---

## 6. User experience

### Main flow

1. User drops one or more files into the app.
2. App asks **Full mix** or **Isolated stem**.
3. For a full mix, user chooses **Fast 4 stems**, **Detailed 6 stems**, or **Experimental 7 stems**.
4. App analyzes the file and shows duration, sample rate, estimated tempo, and processing device.
5. Background processing displays stages: decoding, separating, identifying, transcribing, cleaning, and ready.
6. Results open in a multitrack workspace.
7. User solos or mutes stems, switches between source audio and MIDI preview, and edits notes.
8. User exports selected stems, separate MIDI files, or one multitrack MIDI file.

### Main workspace

- **Left panel:** stem list, label, confidence, mute, solo, source/MIDI toggle.
- **Center:** waveform aligned above a piano roll or drum grid.
- **Right panel:** profile, threshold, quantize, note length, pitch range, drum map.
- **Bottom transport:** play, pause, stop, loop, tempo, metronome, zoom.
- **Top actions:** open, process, undo, redo, save session, export.

### Required correction tools

- Select, move, resize, delete, and add MIDI notes.
- Multi-select and box-select.
- Audition a selected note.
- Re-run one stem without repeating separation.
- Revert to raw detection.
- Rename tracks before export.
- Undo/redo for all edits.

### Error behavior

Errors must say what failed and preserve completed work. Examples:

- Unsupported or damaged input file.
- Not enough disk space.
- Model download interrupted.
- GPU unavailable; offer CPU fallback.
- GPU memory exhausted; retry with smaller segments or CPU.
- No usable onsets or pitched notes detected.
- Seventh-stem confidence too low; retain six-stem result.

---

## 7. Output contract

### Audio stems

- Stereo WAV at the source sample rate where practical.
- Stable names: `<song> - 01 Vocals.wav`, `<song> - 02 Drums.wav`, and so on.
- Preserve stem alignment and duration so files line up at bar 1 in a DAW.
- Optional normalized preview is separate from exported source-level audio.

### MIDI

- Standard MIDI File, Type 1 for multitrack export.
- One named track per stem.
- Tempo event when a reliable tempo is detected or the user enters one.
- Drum track on MIDI channel 10.
- Configurable ticks per quarter note; default 480.
- Optional pitch-bend events for melodic tracks.
- A plain note-only export option for maximum DAW compatibility.
- Separate `.mid` export for each selected stem.

### Session file

Store paths, model versions, settings, detected events, user edits, and export history in a small JSON-based project file. Do not embed the source audio by default. Missing-file recovery lets the user relink moved audio.

---

## 8. Proposed technical architecture

### Application stack

- **Language:** Python 3.11 for the first build.
- **Desktop UI:** PySide6/Qt, with all long jobs outside the UI thread.
- **Audio decode:** FFmpeg.
- **Separation prototype:** Demucs `htdemucs_6s`, with four-stem fallback.
- **Pitched transcription:** Basic Pitch using its Windows ONNX runtime.
- **Onset analysis:** Librosa plus NumPy/SciPy.
- **MIDI writing:** Mido.
- **Preview synth:** a redistributable SoundFont player selected after license review.
- **Packaging:** PyInstaller or an equivalent Windows-native packager, built on Windows.

### Process boundaries

```text
Desktop UI
  -> job controller
      -> decoder
      -> separator worker
      -> instrument-label worker
      -> pitched or drum transcriber
      -> cleanup engine
      -> session store
  -> synchronized audio/MIDI preview
  -> export engine
```

Run separation and transcription in worker processes so cancellation can terminate a hung model without freezing the interface. Cache model instances during a session to avoid repeated startup costs.

### Model delivery

Keep the installer relatively small by separating the app from optional model packs. On first use:

1. Show model name, purpose, download size, license notice, and storage location.
2. Download to the user's application-data directory.
3. Verify a published cryptographic digest.
4. Resume interrupted downloads.
5. Allow model removal from Settings.

After installation, local files must process without an internet connection.

### Hardware policy

- Auto-detect CUDA-capable NVIDIA GPUs.
- Always provide CPU fallback.
- Show the selected device before processing.
- Avoid promising a processing time until benchmarks exist.
- Use segmented inference to control memory use on long files.

---

## 9. Functional requirements

### Must have

- Drag-and-drop import and file picker.
- Full-mix and isolated-stem modes.
- Four- and six-stem separation.
- Pitched audio-to-MIDI for each non-drum stem.
- Drum-to-MIDI with editable mapping.
- Track-aligned preview and export.
- Confidence threshold, quantize, note-length, pitch-range, and velocity controls.
- Manual piano-roll/drum-grid editing.
- Session save/reopen.
- Batch queue, progress, cancel, retry, and failure recovery.
- CPU fallback.
- Export to separate MIDI files and one multitrack MIDI file.

### Should have

- Experimental seventh-stem pipeline.
- Automatic transcription-profile selection.
- User presets for cleanup and drum maps.
- Side-by-side raw versus cleaned MIDI.
- Automatic update check that can be disabled.

### Later

- VST3 drag-and-drop workflow.
- Direct MIDI routing to a DAW or hardware port.
- Mac build.
- Custom model training.
- Chord names and lead-sheet export.
- Cloud acceleration as an opt-in service.

---

## 10. Quality and acceptance criteria

### Functional release gate

A release candidate passes when all of the following work on a clean Windows machine:

- Installs and launches without a separate Python installation.
- Imports every supported format in the test set.
- Completes a CPU-only single-stem conversion.
- Completes a six-stem full-mix conversion.
- Produces valid MIDI that imports into Sonar/Cakewalk with track names and timing intact.
- Maps drums to channel 10 and preserves user remapping.
- Cancels an active job without corrupting completed outputs.
- Reopens a saved session and reproduces the same unedited MIDI export.
- Keeps source audio local during processing.

### Audio and MIDI benchmark set

Build a rights-cleared internal benchmark with at least:

- isolated bass, vocal, piano, guitar, synth, and melody recordings;
- isolated drum patterns across acoustic and electronic kits;
- full mixes from electronic, hip-hop, rock, and pop styles;
- clean audio plus difficult cases: distortion, reverb, sidechain pumping, dense chords, and heavy limiting;
- reference MIDI or human-annotated note/onset labels.

Track note precision, recall, F1, onset timing error, pitch errors, false drum hits, missed hits, processing time, peak memory, and crash rate. Establish paid-release thresholds from the first benchmark run rather than inventing accuracy claims.

### Seventh-stem release gate

Do not advertise seven-stem output until:

- the secondary model and weights pass commercial license review;
- the extra stem improves isolation over the unsplit `other` stem in blind listening tests;
- false extraction is handled by confidence fallback;
- reconstruction does not create unacceptable level changes or clipping;
- CPU and GPU memory behavior is measured on target hardware.

---

## 11. Privacy, rights, and licensing

- No source audio, stems, or MIDI leave the computer unless the user explicitly exports or shares them.
- Display a reminder that users must have the right to process and reuse source audio.
- Include third-party notices in the installer and About screen.
- Pin dependency and model versions and record checksums.
- Review code and model-weight licenses separately before sale.
- Demucs' repository states that its code is MIT licensed, but the project is archived and its pretrained-weight redistribution must still be checked before commercial packaging.
- Basic Pitch states Apache 2.0 licensing and provides a Windows ONNX path; pin the exact release and bundled model used.
- Avoid Essentia's published MTG model weights in the paid build unless a commercial license is obtained; its model page labels them CC BY-NC-SA 4.0.
- Confirm the preview SoundFont's redistribution rights before bundling it.

This section is an engineering checklist, not legal advice.

---

## 12. Product positioning and monetization

### Positioning

**A focused Windows tool that turns a song into editable multitrack MIDI for your DAW.**

The product should compete on workflow rather than claiming a unique algorithm. Free and open-source projects already provide stem separation, and at least one current project combines separation with MIDI extraction. The differentiators should be:

- native-feeling Windows installation;
- no command line, WSL, local server, or browser setup;
- best-in-class drum mapping and correction;
- clean multitrack export tested in Sonar/Cakewalk;
- confidence-aware results instead of unexplained mistakes;
- a narrow interface that reaches export quickly;
- reliable support, updates, and documentation.

### Revenue model hypothesis

- Free trial with short exports or a small conversion allowance.
- One-time personal license as the primary offer.
- Optional paid major-version upgrades rather than a required subscription.
- No per-minute fee for local processing.

A launch price should be tested with a landing page and producer interviews before it is fixed. The earlier working range of **$30–$50 one time** is a hypothesis, not a verified market price.

### Validation before a full build

Ask 10–15 Windows producers to try a clickable mockup or rough prototype. The strongest buying signal is not “cool idea”; it is a user successfully importing the exported MIDI into their DAW and asking to keep the tool.

---

## 13. Build plan

### Phase A: technical proof

- Convert isolated melodic audio to MIDI with Basic Pitch.
- Convert isolated drums to onset events and General MIDI notes.
- Import both outputs into Sonar/Cakewalk and verify timing.
- Measure CPU processing, memory, and output quality on real tracks.

**Exit:** One pitched stem and one drum stem produce editable, aligned MIDI that is meaningfully faster to correct than manual recreation.

### Phase B: full-mix pipeline

- Add four- and six-stem separation.
- Route each stem to the correct transcription profile.
- Export separate stems and a multitrack MIDI file.
- Add job progress, cancellation, cache cleanup, and error recovery.

**Exit:** A full song completes end to end on CPU and supported NVIDIA hardware.

### Phase C: correction workspace

- Add synchronized waveform and MIDI playback.
- Add piano-roll and drum-grid editing.
- Add thresholds, quantization, note cleanup, presets, and undo/redo.
- Save and reopen sessions.

**Exit:** Test users can fix typical errors without leaving the app.

### Phase D: seventh-stem research

- Select only models with commercially acceptable code and weight licenses.
- Benchmark synth/keys extraction from the `other` stem.
- Add confidence fallback and residual reconstruction.
- Keep the feature marked experimental until its release gate passes.

**Exit:** The extra stem is audibly useful on the target benchmark; otherwise the product remains a six-stem converter.

### Phase E: paid Windows release

- Build a clean installer on Windows.
- Add signed releases, licensing, update checks, crash logs with opt-in consent, and third-party notices.
- Run clean-machine, antivirus false-positive, and DAW import tests.
- Publish a trial and collect conversion-quality feedback.

---

## 14. Main risks and mitigations

- **Separation bleed creates false MIDI:** Keep confidence controls, make reprocessing per stem cheap, and optimize for editable starting points rather than perfection.

- **Drum classification confuses layered hits:** Allow multiple simultaneous classes, expose a drum grid, and make remapping fast.

- **The piano stem is weak:** Warn users, allow piano to remain in `other`, and benchmark alternative models before changing defaults.

- **Seven stems becomes a marketing trap:** Fall back to six stems and never create an empty or fake seventh file.

- **Installer becomes large:** Download optional model packs after installation and allow users to remove them.

- **CPU processing feels slow:** Provide a faster four-stem mode, segment long audio, cache models, and show honest progress.

- **GPU compatibility causes support burden:** Support a narrow tested CUDA matrix first and keep CPU fallback.

- **Open-source competition reduces willingness to pay:** Sell installation, correction speed, drum quality, Sonar-tested export, and support—not access to free models.

- **Model licensing blocks commercialization:** Treat every checkpoint as a separate dependency requiring provenance, license text, and redistribution approval.

---

## 15. Assumptions made for this specification

- Version 1 is a standalone Windows desktop app, not a plugin.
- Processing is local and offline after model installation.
- Drum conversion is mandatory in the first sellable version.
- Six labeled audio stems are the reliable baseline.
- A seventh stem is experimental until quality and commercial licensing are proven.
- Sonar/Cakewalk is the primary compatibility target, but exports use standard MIDI and WAV formats.
- The initial business model is a one-time license with a free trial.

---

## 16. Source notes

- [Demucs official repository](https://github.com/facebookresearch/demucs/blob/HEAD/README.md) — six-source model, Windows notes, model limitations, and MIT code license.
- [Spotify Basic Pitch](https://github.com/spotify/basic-pitch/blob/HEAD/README.md) — polyphonic audio-to-MIDI, pitch bends, Windows ONNX runtime, supported audio formats, and Apache 2.0 license.
- [Librosa onset detection](https://librosa.org/doc/main/_modules/librosa/onset.html) — onset-strength and peak-picking behavior used in the drum prototype.
- [Mido](https://github.com/mido/mido/blob/HEAD/README.rst) — MIDI message and file support under the MIT license.
- [PyInstaller documentation](https://github.com/pyinstaller/pyinstaller/blob/HEAD/doc/index.rst) — standalone packaging and the requirement to build Windows packages on Windows.
- [Essentia model documentation](https://essentia.upf.edu/models.html) — published licensing restriction for MTG model weights.
- [StemForge](https://github.com/tsondo/StemForge) — current open-source competitor combining stem separation and MIDI extraction.
- [StemDeck](https://github.com/stemdeckapp/stemdeck/blob/HEAD/README.md) — current local stem-separation competitor and Windows setup comparison.
