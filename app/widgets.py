#!/usr/bin/env python3
"""widgets.py — WaveformWidget, PianoRollWidget (piano roll + drum grid),
StemListWidget. All share a TimeView (pixels-per-second + scroll offset)."""
import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QListWidget, QListWidgetItem

from app.theme import (BG, TEXT, TEXT_DIM, GRID_BEAT, GRID_BAR, ROW_ALT,
                       ROW_SEP, WAVEFORM, PLAYHEAD, FOCUS_LIGHT, accent_for)


class TimeView:
    """Shared horizontal time mapping for waveform + piano roll."""

    def __init__(self):
        self.pps = 60.0          # pixels per second
        self.x_offset = 0.0      # scroll offset in pixels
        self.playhead = 0.0      # seconds
        self.duration = 0.0

    def x_of(self, t):
        return t * self.pps - self.x_offset

    def t_of(self, x):
        return (x + self.x_offset) / self.pps


class WaveformWidget(QWidget):
    seekRequested = Signal(float)

    def __init__(self, timeview, parent=None):
        super().__init__(parent)
        self.tv = timeview
        self._peaks = None   # (mins, maxs) per pixel column at build pps
        self._build_pps = 0
        self._build_w = 0
        self.accent = QColor(WAVEFORM)  # set per selected stem by main window
        self.setMinimumHeight(90)

    def set_audio(self, wav_path):
        import soundfile as sf
        try:
            data, _sr = sf.read(wav_path, always_2d=True)
            mono = data.mean(axis=1).astype(np.float32)
        except Exception:
            mono = np.zeros(44100, dtype=np.float32)
        self._mono = mono
        self._peaks = None
        self.update()

    def _ensure_peaks(self):
        w = max(1, self.width())
        if self._peaks is not None and self._build_w == w \
                and abs(self._build_pps - self.tv.pps) < 1e-6:
            return
        mono = getattr(self, "_mono", np.zeros(44100, dtype=np.float32))
        sr = 44100  # peaks are resolution-based; exact sr only shifts slightly
        # peaks per output column for the visible time range
        total_s = len(mono) / sr
        cols = w
        col_s = (self.tv.duration or total_s) / max(1, cols)
        samp_per_col = max(1, int(col_s * sr))
        n_cols = int(np.ceil(len(mono) / samp_per_col))
        mins = np.empty(n_cols, dtype=np.float32)
        maxs = np.empty(n_cols, dtype=np.float32)
        for i in range(n_cols):
            chunk = mono[i * samp_per_col:(i + 1) * samp_per_col]
            if len(chunk):
                mins[i] = chunk.min()
                maxs[i] = chunk.max()
            else:
                mins[i] = maxs[i] = 0
        self._peaks = (mins, maxs, samp_per_col, sr)
        self._build_w = w
        self._build_pps = self.tv.pps

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))
        if not hasattr(self, "_mono"):
            p.setPen(QColor(TEXT_DIM))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No audio — open a file and press Process")
            return
        self._ensure_peaks()
        mins, maxs, samp_per_col, sr = self._peaks
        mid = self.height() / 2
        amp = self.height() / 2 - 4
        p.setPen(QPen(self.accent, 1))
        for x in range(self.width()):
            t = self.tv.t_of(x)
            idx = int(t * sr / samp_per_col)
            if 0 <= idx < len(mins):
                y1 = mid - maxs[idx] * amp
                y2 = mid - mins[idx] * amp
                p.drawLine(x, int(y1), x, int(max( y2, y1 + 1)))
        # playhead
        x = self.tv.x_of(self.tv.playhead)
        p.setPen(QPen(QColor(PLAYHEAD), 2))
        p.drawLine(int(x), 0, int(x), self.height())

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.seekRequested.emit(max(0.0, self.tv.t_of(ev.position().x())))


# Drum grid rows: the GM notes the drum engine can emit, in kit order.
DRUM_ROWS = [36, 38, 42, 46, 45, 47, 50, 49, 51, 70]
DRUM_NAMES = {36: "Kick", 38: "Snare", 42: "ClHat", 46: "OpHat",
              45: "LoTom", 47: "MidTom", 50: "HiTom", 49: "Crash",
              51: "Ride", 70: "Perc"}


class PianoRollWidget(QWidget):
    selectionChanged = Signal()
    noteActivated = Signal()      # double-clicked a note (audition)
    # edit intents -> main window turns them into undo commands
    moveRequested = Signal(list, float, int)   # note ids, dt, dpitch
    drumMoveRequested = Signal(list, float, dict)  # ids, dt, {id: new_pitch}
    resizeRequested = Signal(object, float)    # note id, new_end
    deleteRequested = Signal(list)             # note ids
    addRequested = Signal(float, int)          # t, pitch

    def __init__(self, timeview, parent=None):
        super().__init__(parent)
        self.tv = timeview
        self.notes = []          # list of note dicts; each needs unique "id"
        self.is_drum = False
        self.selection = set()   # note ids
        self.pitch_lo = 21
        self.pitch_hi = 108
        self._drag = None        # dict describing active drag
        self._rubber = None      # QRectF in widget coords
        self.accent = QColor(WAVEFORM)  # stem accent; set by main window
        self.setMinimumHeight(220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- geometry ----------------------------------------------------------
    def _row_h(self):
        n_rows = len(DRUM_ROWS) if self.is_drum else (self.pitch_hi - self.pitch_lo + 1)
        return max(6.0, self.height() / max(1, n_rows))

    def y_of_pitch(self, pitch):
        rh = self._row_h()
        if self.is_drum:
            idx = DRUM_ROWS.index(pitch) if pitch in DRUM_ROWS else 0
            return idx * rh
        return (self.pitch_hi - pitch) * rh

    def pitch_of_y(self, y):
        rh = self._row_h()
        if self.is_drum:
            idx = int(np.clip(y / rh, 0, len(DRUM_ROWS) - 1))
            return DRUM_ROWS[idx]
        return int(np.clip(self.pitch_hi - y / rh, self.pitch_lo, self.pitch_hi))

    def rect_of(self, note):
        x = self.tv.x_of(note["start"])
        w = max(4.0, (note["end"] - note["start"]) * self.tv.pps)
        if self.is_drum:
            rh = self._row_h()
            y = self.y_of_pitch(note["pitch"]) + rh * 0.15
            return QRectF(x, y, w, rh * 0.7)
        rh = self._row_h()
        y = self.y_of_pitch(note["pitch"])
        return QRectF(x, y + 1, w, rh - 2)

    def note_at(self, pos):
        for n in reversed(self.notes):
            if self.rect_of(n).contains(pos):
                return n
        return None

    # -- painting ----------------------------------------------------------
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))
        rh = self._row_h()
        label_font = QFont("sans", 9)
        # grid: rows
        if self.is_drum:
            p.setFont(label_font)
            for i, gm in enumerate(DRUM_ROWS):
                y = i * rh
                p.setPen(QPen(QColor(ROW_SEP), 1))
                p.drawLine(0, int(y), self.width(), int(y))
                p.setPen(QColor(TEXT_DIM))
                p.drawText(6, int(y + rh - 5), DRUM_NAMES.get(gm, str(gm)))
        else:
            for midi in range(self.pitch_lo, self.pitch_hi + 1):
                y = self.y_of_pitch(midi)
                is_black = (midi % 12) in (1, 3, 6, 8, 10)
                if is_black:
                    p.fillRect(0, int(y), self.width(), int(np.ceil(rh)),
                               QColor(ROW_ALT))
                if midi % 12 == 0:
                    p.setPen(QPen(QColor("#2e3442"), 1))
                    p.drawLine(0, int(y), self.width(), int(y))
                    p.setPen(QColor(TEXT_DIM))
                    p.setFont(label_font)
                    p.drawText(6, int(y + rh - 4), f"C{midi // 12 - 1}")
        # grid: beat lines (bar lines stronger — every 4th beat)
        # (beat lines need tempo; main window sets self.beat_s, default 0.5)
        beat_s = getattr(self, "beat_s", 0.5)
        if beat_s > 0:
            t0 = self.tv.t_of(0)
            first = int(t0 / beat_s)
            beat_pen = QPen(QColor(GRID_BEAT), 1)
            bar_pen = QPen(QColor(GRID_BAR), 1)
            i = first
            t = i * beat_s
            while t < self.tv.t_of(self.width()):
                x = self.tv.x_of(t)
                if x >= 0:
                    p.setPen(bar_pen if i % 4 == 0 else beat_pen)
                    p.drawLine(int(x), 0, int(x), self.height())
                i += 1
                t = i * beat_s
        # notes — drawn in the selected stem's accent color
        for n in self.notes:
            r = self.rect_of(n)
            if r.right() < 0 or r.left() > self.width():
                continue
            sel = n["id"] in self.selection
            low_conf = n.get("conf", 1.0) < 0.35
            fill = QColor(self.accent)
            if sel:
                fill = fill.lighter(115)
            if low_conf:
                fill.setAlpha(100)
            p.setBrush(QBrush(fill))
            if sel:
                p.setPen(QPen(QColor("#ffffff"), 2))
            else:
                p.setPen(QPen(QColor("#0c0e12"), 1))
            p.drawRect(r)
            if low_conf:
                # hatched overlay: uncertainty visible, note still legible
                hatch = QBrush(QColor(self.accent).lighter(140))
                hatch.setStyle(Qt.BrushStyle.BDiagPattern)
                p.setBrush(hatch)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(r.adjusted(1, 1, -1, -1))
            # resize handle
            p.fillRect(int(r.right()) - 4, int(r.top()), 4, int(r.height()),
                       QColor("#0c0e12"))
        # rubber band
        if self._rubber is not None:
            p.setPen(QPen(QColor(FOCUS_LIGHT), 1, Qt.PenStyle.DashLine))
            p.setBrush(QBrush(QColor(110, 168, 255, 40)))
            p.drawRect(self._rubber)
        # playhead
        x = self.tv.x_of(self.tv.playhead)
        p.setPen(QPen(QColor(PLAYHEAD), 2))
        p.drawLine(int(x), 0, int(x), self.height())

    # -- interaction -------------------------------------------------------
    def mousePressEvent(self, ev):
        pos = ev.position()
        note = self.note_at(pos)
        if ev.button() == Qt.MouseButton.LeftButton:
            if note is not None:
                nid = note["id"]
                if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.selection.symmetric_difference_update({nid})
                    self.selectionChanged.emit()
                    self.update()
                    return
                if nid not in self.selection:
                    self.selection = {nid}
                    self.selectionChanged.emit()
                r = self.rect_of(note)
                # resize if grabbing the right edge
                if abs(pos.x() - r.right()) < 6 and not self.is_drum:
                    self._drag = {"kind": "resize", "id": nid,
                                  "orig_end": note["end"]}
                else:
                    self._drag = {"kind": "move", "ids": list(self.selection),
                                  "start_pos": pos,
                                  "orig": {i: (nn["start"], nn["pitch"])
                                           for i, nn in
                                           ((nn["id"], nn) for nn in self.notes)
                                           if i in self.selection}}
                self.update()
            else:
                self.selection = set()
                self.selectionChanged.emit()
                self._drag = {"kind": "rubber", "start": pos}
                self._rubber = QRectF(pos, pos)
                self.update()
        elif ev.button() == Qt.MouseButton.RightButton:
            # right-click deletes the note under cursor (fast correction)
            if note is not None:
                self.deleteRequested.emit([note["id"]])

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        pos = ev.position()
        kind = self._drag["kind"]
        if kind == "rubber":
            self._rubber = QRectF(self._drag["start"], pos).normalized()
            self.update()
        elif kind in ("move", "resize"):
            # live visual feedback only; the undoable edit fires on release
            self._drag["cur"] = pos
            self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag is None:
            return
        d = self._drag
        self._drag = None
        if d["kind"] == "rubber":
            rb = self._rubber
            self._rubber = None
            if rb is not None:
                rb = rb.normalized()
                self.selection = {n["id"] for n in self.notes
                                  if rb.intersects(self.rect_of(n))}
                self.selectionChanged.emit()
            self.update()
        elif d["kind"] == "move":
            start = d["start_pos"]
            end = ev.position()
            dt = (end.x() - start.x()) / self.tv.pps
            if self.is_drum:
                # vertical motion snaps each note to the nearest drum row
                dy = end.y() - start.y()
                new_pitches = {}
                for nid in d["ids"]:
                    nn = next(x for x in self.notes if x["id"] == nid)
                    new_pitches[nid] = self.pitch_of_y(
                        self.y_of_pitch(nn["pitch"]) + dy)
                self.drumMoveRequested.emit(d["ids"], dt, new_pitches)
            else:
                rh = self._row_h()
                # vertical pixels -> semitones (y grows downward)
                dpitch = int(round((start.y() - end.y()) / rh))
                self.moveRequested.emit(d["ids"], dt, dpitch)
            self.update()
        elif d["kind"] == "resize":
            new_end = max(d["orig_end"] + 0.01,
                          self.tv.t_of(ev.position().x()))
            self.resizeRequested.emit(d["id"], new_end)
            self.update()

    def mouseDoubleClickEvent(self, ev):
        pos = ev.position()
        if self.note_at(pos) is None and \
                ev.button() == Qt.MouseButton.LeftButton:
            t = max(0.0, self.tv.t_of(pos.x()))
            pitch = self.pitch_of_y(pos.y())
            self.addRequested.emit(t, pitch)
        elif self.note_at(pos) is not None:
            self.noteActivated.emit()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.selection:
                self.deleteRequested.emit(list(self.selection))
        else:
            super().keyPressEvent(ev)


class StemListWidget(QListWidget):
    """Stem rows: name, M/S toggles, Src/MIDI preview toggle.

    Each row gets its stem's accent-color icon; the selected row is painted
    with the stem accent (not the default blue).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stems = []
        self._accents = {}
        self._recolor_connected = False

    def set_accents(self, accents):
        """accents: dict engine-label -> QColor. Presentation only."""
        self._accents = dict(accents)
        if not self._recolor_connected:
            self.currentRowChanged.connect(lambda _r: self._recolor())
            self._recolor_connected = True
        self._recolor()

    def set_stems(self, stems):
        self._stems = stems
        self.clear()
        for s in stems:
            item = QListWidgetItem(
                f"{s.display_name}  ({len(s.notes)} notes)")
            item.setData(Qt.ItemDataRole.UserRole, s.label)
            acc = self._accents.get(s.label, accent_for(s.label))
            pix = QPixmap(12, 12)
            pix.fill(acc)
            item.setIcon(QIcon(pix))
            self.addItem(item)
        if stems:
            self.setCurrentRow(0)
        self._recolor()

    def _recolor(self):
        cur = self.currentRow()
        for i in range(self.count()):
            item = self.item(i)
            label = item.data(Qt.ItemDataRole.UserRole)
            if i == cur:
                acc = self._accents.get(label, accent_for(label))
                item.setBackground(acc.darker(160))
                item.setForeground(QColor(TEXT))
            else:
                item.setBackground(QBrush())  # clear -> stylesheet default
                item.setForeground(QColor(TEXT))
