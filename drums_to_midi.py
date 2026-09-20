#!/usr/bin/env python3
"""drums_to_midi.py — drum audio -> General MIDI drum notes.

Usage: python drums_to_midi.py drums.wav -o drums.mid

Refactored in Phase B: transcription core lives in transcribe.py, MIDI
writing in midi_out.py. CLI behavior unchanged from Phase A.
"""
import argparse
import os
from collections import Counter

import mido

from transcribe import transcribe_drums, GM
from midi_out import make_multitrack, DRUM_CHANNEL


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe drum audio to GM MIDI drums.")
    ap.add_argument("input", help="Input drum audio file")
    ap.add_argument("-o", "--output", required=True, help="Output .mid file path")
    args = ap.parse_args()

    hits = transcribe_drums(args.input)
    notes = [(t, t + 0.12, gm, vel) for t, gm, vel in hits]
    mid = make_multitrack(
        [{"name": "Drums", "channel": DRUM_CHANNEL, "notes": notes, "is_drum": True}],
        tempo_bpm=120,
    )
    # single-stem file: drop the tempo-only conductor track
    single = mido.MidiFile(type=1, ticks_per_beat=mid.ticks_per_beat)
    single.tracks.append(mid.tracks[1])

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    single.save(out_path)

    inv_gm = {v: k for k, v in GM.items()}
    counts = Counter(inv_gm.get(gm, gm) for _, gm, _ in hits)
    print(f"wrote {out_path}: {len(hits)} hits {dict(counts)}")


if __name__ == "__main__":
    main()
