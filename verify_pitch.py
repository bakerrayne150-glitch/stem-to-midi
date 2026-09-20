#!/usr/bin/env python3
"""verify_pitch.py — parse a Basic Pitch MIDI, match notes to ground truth JSON.

Usage: verify_pitch.py output.mid truth.json [--poly]
--poly: ground truth entries have "midis" (list) instead of "midi".
"""
import json
import sys
import mido

mid_path, truth_path = sys.argv[1], sys.argv[2]
poly = "--poly" in sys.argv

mid = mido.MidiFile(mid_path)
notes = []  # (start_s, end_s, midi)
for track in mid.tracks:
    t = 0
    tempo = 500000
    open_notes = {}
    for msg in track:
        t += msg.time
        if msg.type == "set_tempo":
            tempo = msg.tempo
        if msg.type == "note_on" and msg.velocity > 0:
            open_notes[msg.note] = t
        elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in open_notes:
                start_tick = open_notes.pop(msg.note)
                s2t = lambda tk: mido.tick2second(tk, mid.ticks_per_beat, tempo)
                notes.append((s2t(start_tick), s2t(t), msg.note))
notes.sort()

truth = json.load(open(truth_path))
TOL = 0.080  # 80ms onset tolerance
OCT = 12

tp = oct_err = 0
used = {i: set() for i in range(len(truth))}  # pitches already credited per gt event
print(f"detected {len(notes)} notes, ground truth {len(truth)} events")
for (s, e, m) in notes:
    best, best_dt = None, 1e9
    for i, g in enumerate(truth):
        dt = abs(s - g["start"])
        if dt < best_dt:
            best, best_dt = i, dt
    if best_dt <= TOL:
        g = truth[best]
        want = g["midis"] if poly else [g["midi"]]
        if m in want and m not in used[best]:
            used[best].add(m)
            tp += 1
            flag = "OK  "
        elif any(abs(m - w) == OCT for w in want):
            oct_err += 1
            flag = "OCT "
        else:
            flag = "WRONG"
        print(f"{flag} det t={s:.3f} midi={m:3d} dur={e-s:.2f}s |= gt t={g['start']:.3f} {want}")
    else:
        print(f"FP   det t={s:.3f} midi={m:3d} dur={e-s:.2f}s (no gt within {TOL*1000:.0f}ms)")

total_want = sum(len(g["midis"]) if poly else 1 for g in truth)
extra = len(notes) - tp - oct_err
print(f"\nnote recall (exact pitch) = {tp}/{total_want}, octave errors = {oct_err}, "
      f"extra notes = {extra}")
