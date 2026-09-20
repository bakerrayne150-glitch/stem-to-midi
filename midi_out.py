#!/usr/bin/env python3
"""midi_out.py — shared MIDI writing helpers for the stem-to-midi converter.

note event format: (start_seconds, end_seconds, midi_pitch, velocity)
drum hit format:   (time_seconds, gm_note, velocity) with fixed 0.12s duration
"""
import mido

TICKS_PER_BEAT = 480
DRUM_CHANNEL = 9  # MIDI channel 10 (0-indexed 9)
DRUM_NOTE_LEN_S = 0.12


def sec_to_ticks(seconds, tempo_bpm, ticks_per_beat=TICKS_PER_BEAT):
    return int(seconds * ticks_per_beat * (tempo_bpm / 60.0))


def make_track(name, channel, notes, tempo_bpm, ticks_per_beat=TICKS_PER_BEAT, is_drum=False):
    """Build one mido.MidiTrack from note events.

    notes: iterable of (start_s, end_s, pitch, velocity). For drums, end_s may
    be None and a fixed duration is used.
    """
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm), time=0))

    events = []
    for n in notes:
        start_s, end_s, pitch, vel = n
        on = sec_to_ticks(start_s, tempo_bpm, ticks_per_beat)
        if is_drum or end_s is None:
            off = sec_to_ticks(start_s + DRUM_NOTE_LEN_S, tempo_bpm, ticks_per_beat)
        else:
            off = sec_to_ticks(max(end_s, start_s + 0.01), tempo_bpm, ticks_per_beat)
        pitch = int(max(0, min(127, round(pitch))))
        vel = int(max(1, min(127, round(vel))))
        # note_off sorted before note_on at the same tick
        events.append((on, 1, pitch, vel))
        events.append((off, 0, pitch, 0))
    events.sort(key=lambda e: (e[0], e[1]))

    last = 0
    for tick, kind, pitch, vel in events:
        delta = max(0, tick - last)
        if kind == 1:
            track.append(mido.Message("note_on", channel=channel, note=pitch,
                                      velocity=vel, time=delta))
        else:
            track.append(mido.Message("note_off", channel=channel, note=pitch,
                                      velocity=0, time=delta))
        last = tick
    return track


def make_multitrack(tracks, tempo_bpm, ticks_per_beat=TICKS_PER_BEAT):
    """Assemble a Type 1 MIDI file.

    tracks: list of dicts {name, channel, notes, is_drum}.
    Track 0 carries the tempo map only.
    """
    mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm), time=0))
    tempo_track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    mid.tracks.append(tempo_track)
    for t in tracks:
        mid.tracks.append(make_track(t["name"], t["channel"], t["notes"],
                                     tempo_bpm, ticks_per_beat,
                                     is_drum=t.get("is_drum", False)))
    return mid
