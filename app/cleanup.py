#!/usr/bin/env python3
"""cleanup.py — pure note-cleanup functions (wired to the right-panel controls).

All functions take/return lists of note dicts {start,end,pitch,vel,conf} and
never mutate their input.
"""
import copy

GRID_BEATS = {
    "1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125,
    "1/4T": 2.0 / 3.0, "1/8T": 1.0 / 3.0, "1/16T": 1.0 / 6.0,
}


def filter_confidence(notes, threshold_pct):
    """Drop notes whose confidence (0-100 scale) is below threshold."""
    if threshold_pct <= 0:
        return copy.deepcopy(notes)
    return [copy.deepcopy(n) for n in notes if n["conf"] * 100.0 >= threshold_pct]


def quantize(notes, grid, strength_pct, tempo_bpm):
    """Snap note starts (and ends) toward the grid.

    strength 0 = no change, 100 = full snap. Drums: only starts move.
    """
    if grid == "off" or strength_pct <= 0 or grid not in GRID_BEATS:
        return copy.deepcopy(notes)
    beat_s = 60.0 / tempo_bpm
    grid_s = GRID_BEATS[grid] * beat_s
    k = strength_pct / 100.0
    out = []
    for n in notes:
        m = copy.deepcopy(n)
        snapped = round(m["start"] / grid_s) * grid_s
        m["start"] = m["start"] + (snapped - m["start"]) * k
        dur = m["end"] - n["start"]
        snapped_end = round((n["start"] + dur) / grid_s) * grid_s
        new_end = (n["start"] + dur) + (snapped_end - (n["start"] + dur)) * k
        m["end"] = max(m["start"] + 0.01, new_end)
        out.append(m)
    return out


def min_length_and_gap(notes, min_note_ms, min_gap_ms):
    """Remove notes shorter than min_note_ms; merge notes of the same pitch
    separated by less than min_gap_ms."""
    notes = sorted(copy.deepcopy(notes), key=lambda n: (n["start"], n["pitch"]))
    if min_note_ms > 0:
        notes = [n for n in notes if (n["end"] - n["start"]) * 1000.0 >= min_note_ms]
    if min_gap_ms > 0:
        merged = []
        for n in notes:
            if (merged and merged[-1]["pitch"] == n["pitch"]
                    and (n["start"] - merged[-1]["end"]) * 1000.0 < min_gap_ms):
                merged[-1]["end"] = max(merged[-1]["end"], n["end"])
                merged[-1]["vel"] = max(merged[-1]["vel"], n["vel"])
            else:
                merged.append(n)
        notes = merged
    return notes


def pitch_range_filter(notes, pitch_min, pitch_max):
    return [copy.deepcopy(n) for n in notes
            if pitch_min <= n["pitch"] <= pitch_max]


def merge_same_pitch_overlaps(notes):
    """Merge overlapping notes of the same pitch into one."""
    notes = sorted(copy.deepcopy(notes), key=lambda n: (n["start"], n["pitch"]))
    merged = []
    for n in notes:
        if merged and merged[-1]["pitch"] == n["pitch"] \
                and n["start"] < merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], n["end"])
            merged[-1]["vel"] = max(merged[-1]["vel"], n["vel"])
            merged[-1]["conf"] = max(merged[-1]["conf"], n["conf"])
        else:
            merged.append(n)
    return merged


def apply_fixed_velocity(notes, velocity):
    if not velocity:
        return copy.deepcopy(notes)
    out = copy.deepcopy(notes)
    for n in out:
        n["vel"] = int(max(1, min(127, velocity)))
    return out


def apply_cleanup(notes, settings, tempo_bpm):
    """Run the full cleanup chain in a fixed order. Returns (notes, log)."""
    log = []
    before = len(notes)
    notes = filter_confidence(notes, settings.get("confidence_threshold", 0))
    if len(notes) != before:
        log.append(f"confidence: {before} -> {len(notes)}")
    notes = quantize(notes, settings.get("quantize", "off"),
                     settings.get("quantize_strength", 50), tempo_bpm)
    notes = min_length_and_gap(notes, settings.get("min_note_ms", 0),
                               settings.get("min_gap_ms", 0))
    notes = pitch_range_filter(notes, settings.get("pitch_min", 0),
                               settings.get("pitch_max", 127))
    if settings.get("merge_overlaps", True):
        notes = merge_same_pitch_overlaps(notes)
    notes = apply_fixed_velocity(notes, settings.get("fixed_velocity", 0))
    log.append(f"cleanup: {before} -> {len(notes)} notes")
    return notes, log
