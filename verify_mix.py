#!/usr/bin/env python3
"""verify_mix.py — score Phase B full-mix output against mix_truth.json.

Usage: python verify_mix.py out_dir/ mix_truth.json

Scores each per-stem MIDI against the matching ground truth part and
validates the multitrack MIDI structure. Prints honest per-stem numbers.
"""
import json
import os
import sys

import mido

PITCH_TOL_S = 0.15
DRUM_TOL_S = 0.10

GM_LABEL = {36: "kick", 38: "snare", 42: "closed_hat", 46: "open_hat",
            45: "low_tom", 47: "mid_tom", 50: "high_tom",
            49: "crash", 51: "ride", 70: "other"}
TRUTH_LABEL_TO_GM = {"kick": 36, "snare": 38, "hat": 42}


def file_tempo_bpm(mid_path, ticks_per_beat=480):
    """Read the first set_tempo event; default 120 BPM."""
    mid = mido.MidiFile(mid_path)
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                return mido.tempo2bpm(msg.tempo)
    return 120.0


def read_notes(mid_path, tempo_bpm=None, ticks_per_beat=480):
    """Return [(start_s, end_s, pitch, channel)] for note_on events (vel>0)."""
    if tempo_bpm is None:
        tempo_bpm = file_tempo_bpm(mid_path, ticks_per_beat)
    mid = mido.MidiFile(mid_path)
    notes = []
    for track in mid.tracks:
        abs_tick = 0
        open_notes = {}
        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes[(msg.note, msg.channel)] = abs_tick
            elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.note, msg.channel)
                if key in open_notes:
                    t0 = open_notes.pop(key)
                    s0 = mido.tick2second(t0, ticks_per_beat, mido.bpm2tempo(tempo_bpm))
                    s1 = mido.tick2second(abs_tick, ticks_per_beat, mido.bpm2tempo(tempo_bpm))
                    notes.append((s0, s1, msg.note, msg.channel))
    notes.sort(key=lambda n: n[0])
    return notes


def score_pitched(detected, truth, tol=PITCH_TOL_S):
    """detected: [(start,end,pitch,ch)], truth: [{'midi','start'}]."""
    det = [d for d in detected]
    tp = 0
    matched_det = set()
    for t in truth:
        best, best_dt = None, tol
        for i, d in enumerate(det):
            if i in matched_det:
                continue
            if d[2] == t["midi"] and abs(d[0] - t["start"]) <= best_dt:
                best, best_dt = i, abs(d[0] - t["start"])
        if best is not None:
            tp += 1
            matched_det.add(best)
    fp = len(det) - len(matched_det)
    fn = len(truth) - tp
    recall = tp / len(truth) if truth else 1.0
    prec = tp / len(det) if det else 0.0
    return tp, fp, fn, recall, prec


def score_drums(detected, truth, tol=DRUM_TOL_S):
    """detected: [(start,end,pitch,ch)] on ch 9; truth: [{'label','start'}]."""
    det = sorted(detected, key=lambda d: d[0])
    tp = fp_label = 0
    matched = set()
    for t in truth:
        want = TRUTH_LABEL_TO_GM[t["label"]]
        best, best_dt = None, tol
        for i, d in enumerate(det):
            if i in matched:
                continue
            if abs(d[0] - t["start"]) <= best_dt:
                best, best_dt = i, abs(d[0] - t["start"])
        if best is not None:
            matched.add(best)
            tp += 1
            if det[best][2] != want:
                fp_label += 1
    fp_extra = len(det) - len(matched)
    fn = len(truth) - tp
    recall = tp / len(truth) if truth else 1.0
    label_acc = (tp - fp_label) / tp if tp else 0.0
    return tp, fp_extra, fn, recall, label_acc


def main():
    out_dir, truth_path = sys.argv[1], sys.argv[2]
    truth = json.load(open(truth_path))
    song = "mix"  # matches gen_test_mix.py output naming

    def stem_mid(label, idx):
        p = os.path.join(out_dir, f"{song} - {idx:02d} {label.capitalize()}.mid")
        return p if os.path.exists(p) else None

    # order: vocals 01, drums 02, bass 03, guitar 04, piano 05, other 06
    print("=== per-stem verification ===")
    results = {}

    p = stem_mid("bass", 3)
    if p:
        det = read_notes(p)
        tp, fp, fn, rec, prec = score_pitched(det, truth["bass"])
        results["bass"] = (rec, prec)
        print(f"bass stem   : {len(truth['bass'])} truth notes -> "
              f"recall {rec:.2f} ({tp}/{len(truth['bass'])})  precision {prec:.2f} "
              f"(+{fp} extras, {fn} missed)")

    p = stem_mid("drums", 2)
    if p:
        det = [d for d in read_notes(p) if d[3] == 9]
        tp, fp_extra, fn, rec, lacc = score_drums(det, truth["drums"])
        results["drums"] = (rec, lacc)
        print(f"drums stem  : {len(truth['drums'])} truth hits -> "
              f"recall {rec:.2f} ({tp}/{len(truth['drums'])})  label-acc {lacc:.2f} "
              f"(+{fp_extra} extra hits, {fn} missed)")

    p = stem_mid("vocals", 1)
    if p:
        det = read_notes(p)
        tp, fp, fn, rec, prec = score_pitched(det, truth["vocal"])
        results["vocals"] = (rec, prec)
        print(f"vocals stem : {len(truth['vocal'])} truth notes -> "
              f"recall {rec:.2f} ({tp}/{len(truth['vocal'])})  precision {prec:.2f} "
              f"(+{fp} extras, {fn} missed)")

    # pad truth may land in piano or other — score both, report both
    for label, idx in (("piano", 5), ("other", 6), ("guitar", 4)):
        p = stem_mid(label, idx)
        if p:
            det = read_notes(p)
            tp, fp, fn, rec, prec = score_pitched(det, truth["pad"])
            print(f"{label:11s}: {len(truth['pad'])} pad chord-tones -> "
                  f"recall {rec:.2f} ({tp})  precision {prec:.2f} "
              f"(detected {len(det)} notes total, +{fp} extras)")
            # also check vocal bleed into this stem
            tpv, fpv, fnv, recv, _ = score_pitched(det, truth["vocal"])
            if recv > 0.2:
                print(f"             NOTE: {label} stem also captured "
                      f"{tpv}/{len(truth['vocal'])} vocal notes (cross-bleed)")

    print("\n=== multitrack MIDI validation ===")
    multi = os.path.join(out_dir, f"{song} - multitrack.mid")
    mid = mido.MidiFile(multi)
    names = []
    drum_ch_found = False
    tempo_found = False
    for tr in mid.tracks:
        for msg in tr:
            if msg.type == "track_name":
                names.append(msg.name)
            if msg.type == "set_tempo":
                tempo_found = True
            if msg.type == "note_on" and msg.channel == 9:
                drum_ch_found = True
    print(f"type={mid.type}, tracks={len(mid.tracks)}, tempo_event={tempo_found}, "
          f"drum_channel_10_notes={drum_ch_found}")
    print(f"track names: {names}")
    ok = (mid.type == 1 and len(mid.tracks) == 7 and tempo_found
          and drum_ch_found and len(names) == 6)
    print("multitrack:", "OK" if ok else "PROBLEM — see above")


if __name__ == "__main__":
    main()
