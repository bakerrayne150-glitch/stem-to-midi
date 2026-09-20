#!/usr/bin/env python3
"""full_mix_to_midi.py — Phase B: full mix -> labeled stems -> multitrack MIDI.

Usage: python full_mix_to_midi.py song.wav -o out_dir/ [--stems 6|4]

Pipeline:
  1. separate (Demucs) -> labeled stem WAVs
  2. transcribe each stem (drums -> drum engine on MIDI ch 10;
     everything else -> Basic Pitch with a per-stem profile)
  3. write one .mid per stem + one Type 1 multitrack MIDI

All processing is local, CPU only in Phase B.
"""
import argparse
import os
import sys
import time

import numpy as np
import librosa
import mido

from separate import separate_to_wavs, STEM_ORDER_6, STEM_ORDER_4
from transcribe import transcribe_pitched, transcribe_drums, load_pitch_model
from midi_out import make_multitrack, DRUM_CHANNEL, TICKS_PER_BEAT

# Demucs stem label -> Basic Pitch profile + MIDI channel
PROFILE_FOR = {
    "vocals": "vocal",
    "drums": None,          # drum engine
    "bass": "bass",
    "guitar": "guitar",
    "piano": "piano",
    "other": "other",
}


def fail(msg, code=2):
    print(f"full_mix_to_midi.py: error: {msg}", file=sys.stderr)
    sys.exit(code)


def estimate_tempo(audio_path):
    """Estimate BPM with librosa; fall back to 120 when not confident."""
    try:
        y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])
        if 50 <= tempo <= 220:
            return tempo
    except Exception as e:
        print(f"  tempo estimation failed ({e}); using 120 BPM", flush=True)
    return 120.0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert a full mix to labeled stems and multitrack MIDI.")
    ap.add_argument("input", help="Input audio file (full mix)")
    ap.add_argument("-o", "--output", required=True, help="Output directory")
    ap.add_argument("--stems", type=int, choices=(4, 6), default=6,
                    help="4 = fast, 6 = detailed (default)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        fail(f"input file not found: {args.input}")
    os.makedirs(args.output, exist_ok=True)
    song = os.path.splitext(os.path.basename(args.input))[0]
    order = STEM_ORDER_6 if args.stems == 6 else STEM_ORDER_4

    # ---- 1. separate -------------------------------------------------------
    t0 = time.perf_counter()
    print("stage 1/4: separating ...", flush=True)
    stems_dir = os.path.join(args.output, "stems")
    stem_files = separate_to_wavs(args.input, stems_dir, args.stems)
    by_label = dict(stem_files)
    t_sep = time.perf_counter() - t0

    # ---- 2. tempo ----------------------------------------------------------
    t0 = time.perf_counter()
    print("stage 2/4: estimating tempo ...", flush=True)
    tempo = estimate_tempo(args.input)
    print(f"  tempo: {tempo:.1f} BPM", flush=True)
    t_tempo = time.perf_counter() - t0

    # ---- 3. transcribe -----------------------------------------------------
    t0 = time.perf_counter()
    print("stage 3/4: transcribing stems ...", flush=True)
    model = load_pitch_model()  # load once, reuse for every pitched stem
    tracks = []
    per_stem_midis = []
    channel = 0
    stem_times = {}
    for i, label in enumerate(order, 1):
        ts = time.perf_counter()
        wav_path = by_label[label]
        profile = PROFILE_FOR[label]
        print(f"  stem {i}/{len(order)}: {label} ...", flush=True)
        if profile is None:
            # drums -> GM percussion on channel 10
            hits = transcribe_drums(wav_path)
            notes = [(t, t + 0.12, gm, vel) for t, gm, vel in hits]
            tracks.append({"name": label.capitalize(), "channel": DRUM_CHANNEL,
                           "notes": notes, "is_drum": True})
        else:
            notes = transcribe_pitched(wav_path, profile=profile, model=model)
            tracks.append({"name": label.capitalize(), "channel": channel,
                           "notes": notes, "is_drum": False})
            channel += 1
        print(f"    -> {len(notes)} events", flush=True)

        # per-stem MIDI file, named like the WAV
        stem_mid = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
        stem_mid.tracks.append(mido.MidiTrack())  # conductor
        stem_mid.tracks[0].append(
            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
        from midi_out import make_track
        t = tracks[-1]
        stem_mid.tracks.append(make_track(t["name"], t["channel"], t["notes"],
                                          tempo, TICKS_PER_BEAT,
                                          is_drum=t["is_drum"]))
        mid_name = f"{song} - {i:02d} {label.capitalize()}.mid"
        mid_path = os.path.join(args.output, mid_name)
        stem_mid.save(mid_path)
        per_stem_midis.append(mid_path)
        stem_times[label] = time.perf_counter() - ts
        print(f"    wrote {mid_name} ({stem_times[label]:.1f}s)", flush=True)
    t_trans = time.perf_counter() - t0

    # ---- 4. multitrack MIDI ------------------------------------------------
    print("stage 4/4: exporting multitrack MIDI ...", flush=True)
    multi = make_multitrack(tracks, tempo_bpm=tempo, ticks_per_beat=TICKS_PER_BEAT)
    multi_path = os.path.join(args.output, f"{song} - multitrack.mid")
    multi.save(multi_path)

    print(f"done. tempo={tempo:.1f} BPM, {len(tracks)} tracks -> {multi_path}", flush=True)
    print("timings: " + ", ".join(
        [f"separate={t_sep:.1f}s", f"tempo={t_tempo:.1f}s", f"transcribe={t_trans:.1f}s"]
        + [f"{lbl}={t:.1f}s" for lbl, t in stem_times.items()]), flush=True)


if __name__ == "__main__":
    main()
