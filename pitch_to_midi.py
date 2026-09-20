#!/usr/bin/env python3
"""pitch_to_midi.py — pitched audio -> MIDI via Spotify Basic Pitch.

Usage: python pitch_to_midi.py input.wav -o output.mid [--profile legacy|bass|melody|vocal|piano|guitar|other]

Refactored in Phase B: transcription core lives in transcribe.py, MIDI
writing in midi_out.py. Default --profile legacy preserves the exact Phase A
CLI behavior (stock Basic Pitch defaults); full-mix stems use the tuned
profiles via transcribe_pitched().
"""
import argparse
import os

import mido

from transcribe import transcribe_pitched, PROFILES
from midi_out import make_multitrack


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe pitched audio to MIDI with Basic Pitch.")
    ap.add_argument("input", help="Input audio file (wav/flac/mp3/ogg/m4a)")
    ap.add_argument("-o", "--output", required=True, help="Output .mid file path")
    ap.add_argument("--profile", default="legacy", choices=sorted(PROFILES),
                    help="Instrument profile (default: legacy = Phase A behavior)")
    args = ap.parse_args()

    notes = transcribe_pitched(args.input, profile=args.profile)
    mid = make_multitrack(
        [{"name": f"Pitched ({args.profile})", "channel": 0, "notes": notes}],
        tempo_bpm=120,
    )
    # single-stem file: drop the tempo-only conductor track
    single = mido.MidiFile(type=1, ticks_per_beat=mid.ticks_per_beat)
    single.tracks.append(mid.tracks[1])

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    single.save(out_path)
    print(f"wrote {out_path}: {len(notes)} notes (profile={args.profile})")


if __name__ == "__main__":
    main()
