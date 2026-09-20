#!/usr/bin/env python3
"""models.py — in-memory data model for the correction workspace.

Note event: dict(start, end, pitch, vel, conf)
  start/end: seconds (float), pitch: MIDI 0-127, vel: 1-127,
  conf: 0.0-1.0 estimated detection confidence.
Drum notes use the same shape; end = start + 0.12.
"""
import copy

# Engine tuple formats -> note dicts. The engine does not emit confidence, so
# we recover it from the velocity mapping used in transcribe.py:
#   pitched: vel = clip(round(80*amplitude + 20))  -> conf = (vel-20)/80
#   drums:   vel = clip(64 + 63*n)                 -> conf = (vel-64)/63


def pitched_tuples_to_notes(tuples):
    notes = []
    for start, end, pitch, vel in tuples:
        conf = min(1.0, max(0.0, (vel - 20) / 80.0))
        notes.append({"start": float(start), "end": float(end),
                      "pitch": int(pitch), "vel": int(vel), "conf": conf})
    return notes


def drum_tuples_to_notes(tuples):
    notes = []
    for t, gm, vel in tuples:
        conf = min(1.0, max(0.0, (vel - 64) / 63.0))
        notes.append({"start": float(t), "end": float(t) + 0.12,
                      "pitch": int(gm), "vel": int(vel), "conf": conf})
    return notes


class StemTrack:
    """One separated stem: audio file + detected/edited note events."""

    def __init__(self, label, display_name, wav_path, profile, channel,
                 is_drum=False):
        self.label = label            # engine label, e.g. "vocals"
        self.display_name = display_name
        self.wav_path = wav_path
        self.profile = profile        # Basic Pitch profile name or None (drums)
        self.channel = channel        # MIDI channel for export
        self.is_drum = is_drum
        self.raw_notes = []           # notes as first detected (revert target)
        self.notes = []               # current (edited/cleaned) notes
        self.muted = False
        self.solo = False
        self.preview = "source"       # "source" or "midi" (A/B per stem)
        self._audio = None            # cached (samples, sr)

    def load_audio(self):
        if self._audio is None:
            import soundfile as sf
            data, sr = sf.read(self.wav_path, always_2d=True)
            self._audio = (data.astype("float32"), sr)
        return self._audio

    def set_raw_notes(self, notes):
        self.raw_notes = copy.deepcopy(notes)
        self.notes = copy.deepcopy(notes)

    def clone_notes(self):
        return copy.deepcopy(self.notes)

    def to_dict(self):
        return {
            "label": self.label,
            "display_name": self.display_name,
            "wav_path": self.wav_path,
            "profile": self.profile,
            "channel": self.channel,
            "is_drum": self.is_drum,
            "raw_notes": self.raw_notes,
            "notes": self.notes,
            "muted": self.muted,
            "solo": self.solo,
            "preview": self.preview,
        }

    @classmethod
    def from_dict(cls, d):
        s = cls(d["label"], d["display_name"], d["wav_path"], d.get("profile"),
                d.get("channel", 0), d.get("is_drum", False))
        s.raw_notes = d.get("raw_notes", [])
        s.notes = d.get("notes", [])
        s.muted = d.get("muted", False)
        s.solo = d.get("solo", False)
        s.preview = d.get("preview", "source")
        return s


class Project:
    """Everything about the current conversion session."""

    def __init__(self):
        self.source_path = ""
        self.song = ""
        self.stems_mode = 6           # 6, 4, or "isolated"
        self.tempo = 120.0
        self.duration = 0.0
        self.sample_rate = 44100
        self.stems = []               # list[StemTrack]
        self.edit_history = []        # human-readable edit log entries
        self.export_history = []      # {"time": iso, "kind": str, "path": str}
        self.cleanup_settings = {
            "confidence_threshold": 0,
            "quantize": "off",        # off, 1/4, 1/8, 1/16, 1/32, + "T" triplets
            "quantize_strength": 50,
            "min_note_ms": 0,
            "min_gap_ms": 0,
            "pitch_min": 0,
            "pitch_max": 127,
            "merge_overlaps": True,
            "fixed_velocity": 0,      # 0 = off, else velocity value
        }

    def audible_stems(self):
        """Stems that contribute to preview playback (mute/solo logic)."""
        any_solo = any(s.solo for s in self.stems)
        return [s for s in self.stems
                if not s.muted and (s.solo or not any_solo)]

    def to_dict(self):
        return {
            "version": 1,
            "source_path": self.source_path,
            "song": self.song,
            "stems_mode": self.stems_mode,
            "tempo": self.tempo,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "cleanup_settings": self.cleanup_settings,
            "stems": [s.to_dict() for s in self.stems],
            "edit_history": self.edit_history,
            "export_history": self.export_history,
        }

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.source_path = d.get("source_path", "")
        p.song = d.get("song", "")
        p.stems_mode = d.get("stems_mode", 6)
        p.tempo = d.get("tempo", 120.0)
        p.duration = d.get("duration", 0.0)
        p.sample_rate = d.get("sample_rate", 44100)
        p.cleanup_settings.update(d.get("cleanup_settings", {}))
        p.stems = [StemTrack.from_dict(s) for s in d.get("stems", [])]
        p.edit_history = d.get("edit_history", [])
        p.export_history = d.get("export_history", [])
        return p
