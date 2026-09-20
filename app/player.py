#!/usr/bin/env python3
"""player.py — A/B preview playback with a playhead.

Source mode: mixes the audible stems' WAVs. MIDI mode: renders the current
(possibly edited) notes of audible stems through the built-in synth.
The playhead is driven by a monotonic clock + QTimer, so it stays correct
even when no audio device exists (headless/offscreen). Audio output via
QAudioSink is best-effort and guarded.
"""
import time

import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer

from app import synth

SR = 44100


class Player(QObject):
    positionChanged = Signal(float)   # seconds
    stateChanged = Signal(str)        # "playing" | "paused" | "stopped"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._mode = "source"         # "source" or "midi"
        self._buf = None              # stereo float32 at SR
        self._pos = 0.0
        self._t0 = 0.0
        self._playing = False
        self._loop = False
        self._auditioning = False
        self._aud_dur = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._sink = None
        self._io = None
        self.audio_ok = False

    # -- setup -----------------------------------------------------------
    def set_project(self, project):
        self.stop()
        self._project = project
        self._buf = None

    def set_mode(self, mode):
        assert mode in ("source", "midi")
        was_playing = self._playing
        pos = self.position()
        self.stop()
        self._mode = mode
        self._buf = None
        if was_playing:
            self.play(pos)

    def set_loop(self, loop):
        self._loop = loop

    def invalidate(self):
        """Call after edits/mute/solo/preview changes; keeps position."""
        pos = self.position()
        was_playing = self._playing
        self.stop()
        self._buf = None
        if was_playing:
            self.play(pos)

    # -- transport -------------------------------------------------------
    def _build(self):
        """Render the audible mix for the current mode."""
        p = self._project
        dur = max(0.1, p.duration)
        mix = np.zeros((int(dur * SR), 2), dtype=np.float32)
        if self._mode == "source":
            for stem in p.audible_stems():
                data, sr = stem.load_audio()
                if sr != SR:
                    # cheap linear resample for preview only
                    idx = (np.arange(int(len(data) * SR / sr)) * sr / SR
                           ).astype(int)
                    idx = np.clip(idx, 0, len(data) - 1)
                    data = data[idx]
                n = min(len(mix), len(data))
                mix[:n] += data[:n]
        else:
            for stem in p.audible_stems():
                if stem.preview != "midi":
                    continue
                mono = synth.render_notes(stem.notes, SR, dur,
                                          is_drum=stem.is_drum)
                n = min(len(mix), len(mono))
                mix[:n, 0] += mono[:n]
                mix[:n, 1] += mono[:n]
        peak = np.abs(mix).max()
        if peak > 0.95:
            mix *= 0.95 / peak
        self._buf = mix

    def play(self, pos=None):
        if self._project is None or not self._project.stems:
            return
        if self._buf is None:
            self._build()
        if pos is not None:
            self._pos = max(0.0, min(pos, self._project.duration))
        if self._pos >= self._project.duration - 0.01:
            self._pos = 0.0
        self._start_audio()
        self._t0 = time.monotonic()
        self._playing = True
        self._timer.start()
        self.stateChanged.emit("playing")

    def pause(self):
        if not self._playing:
            return
        self._pos = self.position()
        self._playing = False
        self._timer.stop()
        self._stop_audio()
        self.stateChanged.emit("paused")
        self.positionChanged.emit(self._pos)

    def stop(self):
        self._playing = False
        self._timer.stop()
        self._stop_audio()
        self._pos = 0.0
        self.stateChanged.emit("stopped")
        self.positionChanged.emit(self._pos)

    def seek(self, pos):
        if self._project is None:
            return
        self._pos = max(0.0, min(pos, self._project.duration))
        if self._playing:
            self._t0 = time.monotonic()
            self._start_audio()
        self.positionChanged.emit(self._pos)

    def position(self):
        if self._playing:
            return self._pos + (time.monotonic() - self._t0)
        return self._pos

    def is_playing(self):
        return self._playing

    # -- audio output (best effort) --------------------------------------
    def _start_audio(self):
        self._stop_audio()
        if self._buf is None:
            return
        try:
            from PySide6.QtMultimedia import QAudioSink, QAudioFormat
            fmt = QAudioFormat()
            fmt.setSampleRate(SR)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
            self._sink = QAudioSink(fmt)
            start = int(self._pos * SR)
            pcm = self._buf[start:].tobytes()
            self._io = _BytesIO(pcm)
            self._sink.start(self._io)
            self.audio_ok = True
        except Exception:
            self._sink = None
            self.audio_ok = False

    def _stop_audio(self):
        try:
            if self._sink is not None:
                self._sink.stop()
        except Exception:
            pass
        self._sink = None
        self._io = None

    # -- audition ----------------------------------------------------------
    def audition_notes(self, notes, is_drum):
        """Render and play just the given notes (used for audition).

        Runs as a one-shot that does not disturb the loaded project.
        """
        if not notes:
            return
        self.stop()
        start = min(n["start"] for n in notes)
        dur = max(n["end"] for n in notes) - start + 0.3
        shifted = [dict(n, start=n["start"] - start, end=n["end"] - start)
                   for n in notes]
        mono = synth.render_notes(shifted, SR, dur, is_drum=is_drum)
        self._buf = synth.to_stereo(mono)
        self._auditioning = True
        self._aud_dur = dur
        self._pos = 0.0
        self._start_audio()
        self._t0 = time.monotonic()
        self._playing = True
        self._timer.start()
        self.stateChanged.emit("playing")

    def _tick(self):
        pos = self.position()
        if self._auditioning:
            if pos >= self._aud_dur:
                self._auditioning = False
                self._aud_dur = 0.0
                self._buf = None  # force rebuild of the real mix next play
                self.stop()
            return
        dur = self._project.duration if self._project else 0


class _BytesIO:
    """Minimal QIODevice-compatible byte reader for QAudioSink."""

    def __init__(self, data: bytes):
        from PySide6.QtCore import QIODevice, QBuffer, QByteArray
        self._buf = QBuffer()
        self._buf.setData(QByteArray(data))
        self._buf.open(QIODevice.OpenModeFlag.ReadOnly)

    def __getattr__(self, name):
        return getattr(self._buf, name)
