#!/usr/bin/env python3
"""verify_drums.py — parse drums.mid, match detected hits to drums.json ground truth."""
import json
import mido

TICKS_PER_BEAT = 480
TEMPO_BPM = 120

GM_LABEL = {36: "kick", 38: "snare", 42: "closed_hat", 46: "open_hat",
            45: "low_tom", 47: "mid_tom", 50: "high_tom",
            49: "crash", 51: "ride", 70: "other"}

mid = mido.MidiFile("drums.mid")
detected = []
for track in mid.tracks:
    t = 0
    for msg in track:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and msg.channel == 9:
            sec = t / TICKS_PER_BEAT / (TEMPO_BPM / 60.0)
            detected.append({"time": sec, "label": GM_LABEL.get(msg.note, f"note{msg.note}"),
                             "vel": msg.velocity})

truth = json.load(open("drums.json"))
TOL = 0.050
matched_gt = set()
tp = fp = 0
label_ok = 0
for d in detected:
    best, best_dt = None, 1e9
    for i, g in enumerate(truth):
        dt = abs(d["time"] - g["start"])
        if dt < best_dt:
            best, best_dt = i, dt
    if best_dt <= TOL and best not in matched_gt:
        tp += 1
        matched_gt.add(best)
        g = truth[best]
        ok = (d["label"] == g["label"]) or (g["label"] == "hat" and d["label"] in ("closed_hat", "open_hat"))
        label_ok += int(ok)
        flag = "OK " if ok else "WRONG"
        print(f"{flag} det t={d['time']:.3f} {d['label']:10s} vel={d['vel']:3d} "
              f"|= gt t={g['start']:.3f} {g['label']} (dt={best_dt*1000:.0f}ms)")
    else:
        fp += 1
        print(f"FP  det t={d['time']:.3f} {d['label']:10s} (no gt within {TOL*1000:.0f}ms)")

fn = len(truth) - len(matched_gt)
for i, g in enumerate(truth):
    if i not in matched_gt:
        print(f"FN  gt t={g['start']:.3f} {g['label']}")

print(f"\ndetected={len(detected)} gt={len(truth)}")
print(f"onset recall={len(matched_gt)}/{len(truth)}, false positives={fp}")
print(f"label accuracy on matched={label_ok}/{tp}")
