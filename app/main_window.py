#!/usr/bin/env python3
"""main_window.py — the correction workspace main window (spec section 6)."""
import itertools
import os
import threading
from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import (QUndoStack, QUndoCommand, QAction, QKeySequence,
                            QFontDatabase)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QComboBox, QPushButton, QProgressBar, QLabel, QSlider,
    QScrollBar, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QLineEdit, QStatusBar, QInputDialog, QGridLayout, QFrame,
)

from app import pipeline, cleanup, session as session_mod
from app.models import Project
from app.theme import accent_for, apply_theme, TEXT_DIM
from app.widgets import TimeView, WaveformWidget, PianoRollWidget, StemListWidget
from app.worker import PipelineWorker
from app.player import Player


def _section_label(text):
    """Small-caps dim section header (stylesheet: QLabel[section="true"])."""
    lbl = QLabel(text.upper())
    lbl.setProperty("section", True)
    return lbl


# ---------------------------------------------------------------- undo ----

class _StemEditCommand(QUndoCommand):
    """Base: swaps a stem's note list between before/after snapshots."""

    def __init__(self, window, stem, before, after, text):
        super().__init__(text)
        self.window = window
        self.stem = stem
        self.before = before
        self.after = after

    def _apply(self, notes):
        self.stem.notes = [dict(n) for n in notes]
        self.window.refresh_notes_view()
        self.window.player.invalidate()

    def redo(self):
        self._apply(self.after)

    def undo(self):
        self._apply(self.before)


def _snapshot(stem):
    return [dict(n) for n in stem.notes]


class RenameStemCommand(QUndoCommand):
    def __init__(self, window, stem, new_name):
        super().__init__(f"Rename stem to {new_name}")
        self.window = window
        self.stem = stem
        self.new = new_name
        self.old = stem.display_name

    def redo(self):
        self.stem.display_name = self.new
        self.window.refresh_stem_list()

    def undo(self):
        self.stem.display_name = self.old
        self.window.refresh_stem_list()


# ------------------------------------------------------- re-run worker ----

class RetranscribeWorker(QObject):
    finished = Signal(object, list, bool)  # stem, note dicts, is_drum
    error = Signal(str)

    def __init__(self, stem, profile, parent=None):
        super().__init__(parent)
        self.stem = stem
        self.profile = profile

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            from app.models import pitched_tuples_to_notes, drum_tuples_to_notes
            # Temporarily map the chosen profile onto this stem's label so
            # the engine uses it without re-separating. Done inside the
            # worker thread to avoid a race with the caller.
            orig = pipeline.PROFILE_FOR.get(self.stem.label)
            pipeline.PROFILE_FOR[self.stem.label] = self.profile
            try:
                tuples, is_drum = pipeline.transcribe_stem(
                    self.stem.wav_path, self.stem.label)
            finally:
                pipeline.PROFILE_FOR[self.stem.label] = orig
            if is_drum:
                notes = drum_tuples_to_notes(tuples)
            else:
                notes = pitched_tuples_to_notes(tuples)
            self.finished.emit(self.stem, notes, is_drum)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))


# ------------------------------------------------------------- export -----

class ExportDialog(QDialog):
    def __init__(self, parent=None, stems=()):
        super().__init__(parent)
        self.setWindowTitle("Export")
        lay = QVBoxLayout(self)
        # per-stem keep/discard grid: MIDI and WAV checkboxes per stem
        self._stem_rows = []  # (label, midi_cb, wav_cb)
        if stems:
            grid = QGridLayout()
            grid.addWidget(QLabel("Stem"), 0, 0)
            grid.addWidget(QLabel("MIDI"), 0, 1)
            grid.addWidget(QLabel("WAV"), 0, 2)
            for r, stem in enumerate(stems, 1):
                grid.addWidget(QLabel(stem.display_name), r, 0)
                cb_midi = QCheckBox()
                cb_midi.setChecked(True)
                cb_wav = QCheckBox()
                cb_wav.setChecked(True)
                grid.addWidget(cb_midi, r, 1)
                grid.addWidget(cb_wav, r, 2)
                self._stem_rows.append((stem.label, cb_midi, cb_wav))
            lay.addLayout(grid)
        self.cb_multi = QCheckBox("Multitrack MIDI (Type 1)")
        self.cb_multi.setChecked(True)
        lay.addWidget(self.cb_multi)
        row = QHBoxLayout()
        self.dir_edit = QLineEdit(os.path.expanduser("~"))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.dir_edit)
        row.addWidget(browse)
        lay.addLayout(row)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def stem_exports(self):
        """{label: {"midi": bool, "wav": bool}} from the per-stem grid."""
        return {label: {"midi": cb_m.isChecked(), "wav": cb_w.isChecked()}
                for label, cb_m, cb_w in self._stem_rows}

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Export directory")
        if d:
            self.dir_edit.setText(d)


# ================================================================ window ==

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app)  # idempotent; ensures every entry point is themed
        self.setWindowTitle("Stem-to-MIDI Workspace")
        self.resize(1280, 800)
        self.project = None
        self.undo_stack = QUndoStack(self)
        self.tv = TimeView()
        self.player = Player(self)
        self.worker = None
        self._id_counter = itertools.count(1)
        self._session_path = None
        self._dirty = False

        self._build_ui()
        self._wire()
        self.setAcceptDrops(True)
        self._show_welcome(True)

    # -- welcome empty state -------------------------------------------------
    def _build_welcome(self):
        """Drop-zone card shown when no project is loaded."""
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumWidth(480)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(10)
        title = QLabel("Drop an audio file here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = title.font()
        f.setPointSize(f.pointSize() + 7)
        f.setBold(True)
        title.setFont(f)
        cl.addWidget(title)
        sub = QLabel("WAV, FLAC, MP3, M4A or OGG")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {TEXT_DIM};")
        cl.addWidget(sub)
        brow = QPushButton("or click to browse…")
        brow.clicked.connect(self.open_file)
        cl.addWidget(brow)
        self.welcome_mode = QComboBox()
        self.welcome_mode.addItems(["Full mix — 6 stems", "Full mix — 4 stems",
                                    "Isolated stem"])
        cl.addWidget(self.welcome_mode)
        self.welcome_process = QPushButton("Process")
        self.welcome_process.setDefault(True)
        pf = self.welcome_process.font()
        pf.setBold(True)
        self.welcome_process.setFont(pf)
        self.welcome_process.clicked.connect(self._welcome_process)
        cl.addWidget(self.welcome_process)
        wl.addWidget(card)
        return wrap

    def _show_welcome(self, show):
        self.welcome.setVisible(show)
        self.waveform.setVisible(not show)
        self.pianoroll.setVisible(not show)
        self.hscroll.setVisible(not show)

    def _welcome_process(self):
        self.mode_combo.setCurrentText(self.welcome_mode.currentText())
        self.process()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
                u.isLocalFile() and u.toLocalFile().lower().endswith(
                    (".wav", ".flac", ".mp3", ".m4a", ".ogg"))
                for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            path = u.toLocalFile()
            if path.lower().endswith((".wav", ".flac", ".mp3", ".m4a",
                                      ".ogg")):
                self._pending_input = path
                self.statusBar().showMessage(
                    f"Selected: {path} — press Process")
                break
        event.acceptProposedAction()

    # -- UI construction -------------------------------------------------
    def _build_ui(self):
        # top toolbar
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_open = QAction("Open…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.open_file)
        tb.addAction(act_open)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Full mix — 6 stems", "Full mix — 4 stems",
                                  "Isolated stem"])
        tb.addWidget(QLabel(" Mode:"))
        tb.addWidget(self.mode_combo)

        self.btn_process = QPushButton("Process")
        self.btn_process.clicked.connect(self.process)
        tb.addAction(tb.addWidget(self.btn_process))

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        tb.addWidget(self.progress)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_process)
        tb.addWidget(self.btn_cancel)

        tb.addSeparator()
        self.act_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_redo = self.undo_stack.createRedoAction(self, "Redo")
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()

        act_save = QAction("Save session", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.save_session)
        tb.addAction(act_save)
        act_open_sess = QAction("Open session", self)
        act_open_sess.triggered.connect(self.open_session)
        tb.addAction(act_open_sess)
        act_export = QAction("Export…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self.export)
        tb.addAction(act_export)
        tb.addSeparator()
        act_audition = QAction("Audition selection", self)
        act_audition.setShortcut(QKeySequence("A"))
        act_audition.triggered.connect(self.audition_selection)
        tb.addAction(act_audition)

        # main splitter: left | center | right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left panel
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(_section_label("Stems"))
        self.stem_list = StemListWidget()
        ll.addWidget(self.stem_list, 1)
        # per-stem controls for the selected stem
        ctl = QGroupBox("Selected stem")
        cl = QVBoxLayout(ctl)
        row = QHBoxLayout()
        self.btn_mute = QPushButton("Mute")
        self.btn_mute.setCheckable(True)
        self.btn_solo = QPushButton("Solo")
        self.btn_solo.setCheckable(True)
        row.addWidget(self.btn_mute)
        row.addWidget(self.btn_solo)
        cl.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Preview:"))
        self.btn_src = QPushButton("Source")
        self.btn_src.setCheckable(True)
        self.btn_mid = QPushButton("MIDI")
        self.btn_mid.setCheckable(True)
        row2.addWidget(self.btn_src)
        row2.addWidget(self.btn_mid)
        cl.addLayout(row2)
        self.btn_rename = QPushButton("Rename…")
        cl.addWidget(self.btn_rename)
        ll.addWidget(ctl)
        splitter.addWidget(left)

        # center panel
        center = QWidget()
        cl2 = QVBoxLayout(center)
        cl2.setContentsMargins(0, 0, 0, 0)
        self.welcome = self._build_welcome()
        cl2.addWidget(self.welcome, 1)
        self.waveform = WaveformWidget(self.tv)
        self.pianoroll = PianoRollWidget(self.tv)
        cl2.addWidget(self.waveform, 1)
        cl2.addWidget(self.pianoroll, 2)
        self.hscroll = QScrollBar(Qt.Orientation.Horizontal)
        cl2.addWidget(self.hscroll)
        splitter.addWidget(center)

        # right panel
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(_section_label("Transcription"))
        form = QFormLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["bass", "melody", "vocal", "piano",
                                     "guitar", "other", "legacy"])
        form.addRow("Profile:", self.profile_combo)
        self.conf_spin = QSpinBox()
        self.conf_spin.setRange(0, 100)
        self.conf_spin.setSuffix(" %")
        form.addRow("Confidence ≥:", self.conf_spin)
        self.quant_combo = QComboBox()
        self.quant_combo.addItems(["off", "1/4", "1/8", "1/16", "1/32",
                                   "1/4T", "1/8T", "1/16T"])
        form.addRow("Quantize:", self.quant_combo)
        self.quant_strength = QSlider(Qt.Orientation.Horizontal)
        self.quant_strength.setRange(0, 100)
        self.quant_strength.setValue(50)
        form.addRow("Q strength:", self.quant_strength)
        self.min_note_spin = QSpinBox()
        self.min_note_spin.setRange(0, 2000)
        self.min_note_spin.setSuffix(" ms")
        form.addRow("Min note:", self.min_note_spin)
        self.min_gap_spin = QSpinBox()
        self.min_gap_spin.setRange(0, 2000)
        self.min_gap_spin.setSuffix(" ms")
        form.addRow("Min gap:", self.min_gap_spin)
        prow = QHBoxLayout()
        self.pitch_min_spin = QSpinBox()
        self.pitch_min_spin.setRange(0, 127)
        self.pitch_max_spin = QSpinBox()
        self.pitch_max_spin.setRange(0, 127)
        self.pitch_max_spin.setValue(127)
        prow.addWidget(self.pitch_min_spin)
        prow.addWidget(QLabel("–"))
        prow.addWidget(self.pitch_max_spin)
        form.addRow("Pitch range:", prow)
        self.merge_cb = QCheckBox("Merge overlaps")
        self.merge_cb.setChecked(True)
        form.addRow(self.merge_cb)
        self.fixed_vel_spin = QSpinBox()
        self.fixed_vel_spin.setRange(0, 127)
        self.fixed_vel_spin.setSpecialValueText("off")
        form.addRow("Fixed velocity:", self.fixed_vel_spin)
        rl.addLayout(form)
        self.btn_apply = QPushButton("Apply cleanup")
        self.btn_rerun = QPushButton("Re-run this stem")
        self.btn_revert = QPushButton("Revert to raw detection")
        rl.addWidget(self.btn_apply)
        rl.addWidget(self.btn_rerun)
        rl.addWidget(self.btn_revert)
        rl.addStretch(1)
        splitter.addWidget(right)
        splitter.setSizes([220, 800, 260])

        # slim transport bar (mixer-console style); status bar keeps messages
        transport = QWidget()
        tl = QHBoxLayout(transport)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(6)
        self.btn_play = QPushButton("Play")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        self.btn_loop = QPushButton("Loop")
        self.btn_loop.setCheckable(True)
        self.ab_combo = QComboBox()
        self.ab_combo.addItems(["Source", "MIDI"])
        self.tempo_label = QLabel("— BPM")
        self.time_label = QLabel("0:00.0")
        # tabular figures so time/tempo readouts don't jitter
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.tempo_label.setFont(mono)
        self.time_label.setFont(mono)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(20, 400)
        self.zoom_slider.setValue(60)
        self.zoom_slider.setMaximumWidth(160)
        tl.addWidget(self.btn_play)
        tl.addWidget(self.btn_pause)
        tl.addWidget(self.btn_stop)
        tl.addWidget(self.btn_loop)
        tl.addWidget(QLabel("A/B:"))
        tl.addWidget(self.ab_combo)
        tl.addWidget(self.tempo_label)
        tl.addWidget(self.time_label)
        tl.addStretch(1)
        tl.addWidget(QLabel("Zoom:"))
        tl.addWidget(self.zoom_slider)

        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(splitter, 1)
        cv.addWidget(transport)
        self.setCentralWidget(central)

        # status bar: messages only
        self.setStatusBar(QStatusBar())

    # -- wiring ------------------------------------------------------------
    def _wire(self):
        self.stem_list.currentRowChanged.connect(self._on_stem_selected)
        self.stem_list.rowMuteToggled.connect(self._on_row_mute)
        self.stem_list.rowSoloToggled.connect(self._on_row_solo)
        self.btn_mute.toggled.connect(self._on_mute_toggled)
        self.btn_solo.toggled.connect(self._on_solo_toggled)
        self.btn_src.clicked.connect(lambda: self._set_preview("source"))
        self.btn_mid.clicked.connect(lambda: self._set_preview("midi"))
        self.btn_rename.clicked.connect(self._rename_stem)

        self.waveform.seekRequested.connect(self.player.seek)
        self.player.positionChanged.connect(self._on_position)
        self.player.stateChanged.connect(self._on_player_state)

        self.btn_play.clicked.connect(lambda: self.player.play())
        self.btn_pause.clicked.connect(self.player.pause)
        self.btn_stop.clicked.connect(self.player.stop)
        self.btn_loop.toggled.connect(self.player.set_loop)
        self.ab_combo.currentTextChanged.connect(
            lambda t: self.player.set_mode("source" if t == "Source" else "midi"))

        self.zoom_slider.valueChanged.connect(self._on_zoom)
        self.hscroll.valueChanged.connect(self._on_scroll)

        pr = self.pianoroll
        pr.moveRequested.connect(self._on_move_notes)
        pr.drumMoveRequested.connect(self._on_drum_move_notes)
        pr.resizeRequested.connect(self._on_resize_note)
        pr.deleteRequested.connect(self._on_delete_notes)
        pr.addRequested.connect(self._on_add_note)
        pr.selectionChanged.connect(lambda: None)
        pr.noteActivated.connect(self.audition_selection)

        self.btn_apply.clicked.connect(self.apply_cleanup)
        self.btn_rerun.clicked.connect(self.rerun_stem)
        self.btn_revert.clicked.connect(self.revert_stem)
        self.undo_stack.indexChanged.connect(lambda _i: self._mark_dirty())

    # -- helpers -----------------------------------------------------------
    def current_stem(self):
        if not self.project or not self.project.stems:
            return None
        row = self.stem_list.currentRow()
        if 0 <= row < len(self.project.stems):
            return self.project.stems[row]
        return None

    def _mark_dirty(self):
        self._dirty = True

    # -- file / pipeline ---------------------------------------------------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open audio file", "",
            "Audio (*.wav *.flac *.mp3 *.m4a *.ogg);;All files (*)")
        if path:
            self._pending_input = path
            self.statusBar().showMessage(f"Selected: {path} — press Process")

    def process(self):
        path = getattr(self, "_pending_input", None)
        if not path:
            self.open_file()
            path = getattr(self, "_pending_input", None)
        if not path:
            return
        mode_text = self.mode_combo.currentText()
        if mode_text.startswith("Isolated"):
            profile, ok = QInputDialog.getItem(
                self, "Isolated stem", "Transcription profile:",
                ["bass", "melody", "vocal", "piano", "guitar", "other",
                 "legacy"], 5, False)
            if not ok:
                return
            self._start_isolated(path, profile)
        else:
            n_stems = 4 if "4 stems" in mode_text else 6
            self._start_pipeline(path, n_stems)

    def _start_pipeline(self, path, n_stems):
        work_dir = os.path.join(os.path.dirname(os.path.abspath(path)),
                                ".stem2midi_work")
        os.makedirs(work_dir, exist_ok=True)
        self.worker = PipelineWorker(path, n_stems, work_dir)
        self.worker.stage.connect(self._on_stage)
        self.worker.progress.connect(self._on_progress)
        self.worker.stem_done.connect(self._on_stem_done)
        self.worker.finished.connect(self._on_pipeline_finished)
        self.worker.error.connect(self._on_pipeline_error)
        self.worker.cancelled.connect(self._on_pipeline_cancelled)
        self.progress.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.btn_process.setEnabled(False)
        self.worker.start()

    def _start_isolated(self, path, profile):
        """Isolated-stem mode: no separation, direct transcription."""
        self.progress.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.btn_process.setEnabled(False)
        self._iso_cancel = threading.Event()

        def run():
            try:
                info = pipeline.probe_audio(path)
                if self._iso_cancel.is_set():
                    self._iso_cancelled()
                    return
                from app.models import pitched_tuples_to_notes, StemTrack
                model = pipeline.load_pitch_model_shared()
                tuples = __import__("transcribe",
                                    fromlist=["transcribe_pitched"]
                                    ).transcribe_pitched(path, profile=profile,
                                                         model=model)
                # NOTE: import kept local so the GUI never imports torch.
                song = os.path.splitext(os.path.basename(path))[0]
                project = Project()
                project.source_path = os.path.abspath(path)
                project.song = song
                project.stems_mode = "isolated"
                project.tempo = pipeline.estimate_tempo(path)
                project.duration = info["duration"]
                project.sample_rate = info["sample_rate"]
                stem = StemTrack(label="stem", display_name=song,
                                 wav_path=os.path.abspath(path),
                                 profile=profile, channel=0, is_drum=False)
                stem.set_raw_notes(pitched_tuples_to_notes(tuples))
                project.stems.append(stem)
                self._on_pipeline_finished(project)
            except Exception as e:  # noqa: BLE001
                self._on_pipeline_error(str(e))

        threading.Thread(target=run, daemon=True).start()

    def _iso_cancelled(self):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_process.setEnabled(True)
        self.statusBar().showMessage("Cancelled")

    def cancel_process(self):
        if self.worker is not None:
            self.worker.cancel()
        if hasattr(self, "_iso_cancel"):
            self._iso_cancel.set()

    def _on_stage(self, text):
        self.statusBar().showMessage(text)

    def _on_progress(self, stage, current, total):
        if total > 0:
            self.progress.setValue(int(100 * current / total))

    def _on_stem_done(self, label, count):
        self.statusBar().showMessage(f"Stem {label}: {count} notes")

    def _hide_busy(self):
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_process.setEnabled(True)
        self.progress.setValue(0)

    def _on_pipeline_finished(self, project):
        self._hide_busy()
        self._load_project(project)
        self.statusBar().showMessage(
            f"Done: {len(project.stems)} stems, "
            f"{sum(len(s.notes) for s in project.stems)} notes")

    def _on_pipeline_error(self, msg):
        self._hide_busy()
        # keep any completed work: if a project exists, leave it on screen
        lines = msg.splitlines()[:8]
        QMessageBox.warning(self, "Processing error",
                            "Something failed:\n\n" + "\n".join(lines) +
                            "\n\nCompleted stems were kept.")

    def _on_pipeline_cancelled(self):
        self._hide_busy()
        self.statusBar().showMessage("Processing cancelled")

    def _load_project(self, project):
        self.player.set_project(project)
        self.project = project
        self.undo_stack.clear()
        self._dirty = False
        self._show_welcome(False)
        for stem in project.stems:
            for n in stem.notes:
                n["id"] = next(self._id_counter)
            for n in stem.raw_notes:
                if "id" not in n:
                    n["id"] = next(self._id_counter)
        self.tv.duration = project.duration
        self.tv.playhead = 0.0
        self.tv.pps = 60.0
        self.zoom_slider.setValue(60)
        self.tempo_label.setText(f"{project.tempo:.1f} BPM")
        self.pianoroll.beat_s = 60.0 / project.tempo if project.tempo else 0.5
        self.refresh_stem_list()
        self.stem_list.setCurrentRow(0)
        self._update_scrollbar()
        self._sync_cleanup_controls()

    # -- stem list / selection ---------------------------------------------
    def refresh_stem_list(self):
        if not self.project:
            return
        cur = self.stem_list.currentRow()
        accents = {s.label: accent_for(s.label) for s in self.project.stems}
        self.stem_list.set_accents(accents)
        self.stem_list.set_stems(self.project.stems)
        self.stem_list.setCurrentRow(max(0, cur))
        self._on_stem_selected(self.stem_list.currentRow())

    def _on_stem_selected(self, row):
        stem = self.current_stem()
        if stem is None:
            return
        acc = accent_for(stem.label)
        self.pianoroll.accent = acc
        self.waveform.accent = acc
        self.waveform.set_audio(stem.wav_path)
        self._show_stem_notes(stem)
        self.btn_mute.setChecked(stem.muted)
        self.btn_solo.setChecked(stem.solo)
        self.btn_src.setChecked(stem.preview == "source")
        self.btn_mid.setChecked(stem.preview == "midi")
        if stem.profile in [self.profile_combo.itemText(i)
                            for i in range(self.profile_combo.count())]:
            self.profile_combo.setCurrentText(stem.profile)

    def _show_stem_notes(self, stem):
        pr = self.pianoroll
        pr.is_drum = stem.is_drum
        pr.selection = set()
        if stem.is_drum:
            pr.pitch_lo, pr.pitch_hi = 0, 127
        else:
            pitches = [n["pitch"] for n in stem.notes]
            if pitches:
                pr.pitch_lo = max(0, min(pitches) - 5)
                pr.pitch_hi = min(127, max(pitches) + 5)
            else:
                pr.pitch_lo, pr.pitch_hi = 21, 108
        pr.notes = stem.notes
        pr.update()
        self.waveform.update()

    def refresh_notes_view(self):
        stem = self.current_stem()
        if stem:
            self._show_stem_notes(stem)
            # keep the strip note counts fresh without losing selection
            self.stem_list.refresh_counts(self.project.stems)

    def _on_row_mute(self, label, on):
        stem = self._stem_by_label(label)
        if stem:
            stem.muted = on
            self.player.invalidate()
            self._mark_dirty()
            if stem is self.current_stem():
                self.btn_mute.blockSignals(True)
                self.btn_mute.setChecked(on)
                self.btn_mute.blockSignals(False)

    def _on_row_solo(self, label, on):
        stem = self._stem_by_label(label)
        if stem:
            stem.solo = on
            self.player.invalidate()
            self._mark_dirty()
            if stem is self.current_stem():
                self.btn_solo.blockSignals(True)
                self.btn_solo.setChecked(on)
                self.btn_solo.blockSignals(False)

    def _stem_by_label(self, label):
        if not self.project:
            return None
        return next((s for s in self.project.stems if s.label == label), None)

    def _on_mute_toggled(self, on):
        stem = self.current_stem()
        if stem:
            stem.muted = on
            self.player.invalidate()
            self._mark_dirty()
            self.stem_list.refresh_counts(self.project.stems)

    def _on_solo_toggled(self, on):
        stem = self.current_stem()
        if stem:
            stem.solo = on
            self.player.invalidate()
            self._mark_dirty()
            self.stem_list.refresh_counts(self.project.stems)

    def _set_preview(self, mode):
        stem = self.current_stem()
        if stem:
            stem.preview = mode
            self.btn_src.setChecked(mode == "source")
            self.btn_mid.setChecked(mode == "midi")
            self.player.invalidate()
            self._mark_dirty()

    def _rename_stem(self):
        stem = self.current_stem()
        if not stem:
            return
        name, ok = QInputDialog.getText(self, "Rename stem", "Track name:",
                                        text=stem.display_name)
        if ok and name.strip():
            self.undo_stack.push(RenameStemCommand(self, stem, name.strip()))
            self._log_edit(f"renamed stem to '{name.strip()}'")

    def _log_edit(self, text):
        if self.project:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            self.project.edit_history.append(f"{ts} {text}")

    # -- note editing (undoable) --------------------------------------------
    def _push_notes_edit(self, stem, before, text):
        after = _snapshot(stem)
        if before != after:
            self.undo_stack.push(_StemEditCommand(self, stem, before, after,
                                                  text))
            self._log_edit(text)

    def _on_move_notes(self, ids, dt, dpitch):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        idset = set(ids)
        for n in stem.notes:
            if n["id"] in idset:
                n["start"] = max(0.0, n["start"] + dt)
                n["end"] = max(n["start"] + 0.03, n["end"] + dt)
                if not stem.is_drum:
                    n["pitch"] = int(max(0, min(127, n["pitch"] + dpitch)))
        self._push_notes_edit(stem, before, f"moved {len(ids)} note(s)")

    def _on_drum_move_notes(self, ids, dt, new_pitches):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        idset = set(ids)
        for n in stem.notes:
            if n["id"] in idset:
                n["start"] = max(0.0, n["start"] + dt)
                n["end"] = n["start"] + 0.12
                if n["id"] in new_pitches:
                    n["pitch"] = int(new_pitches[n["id"]])
        self._push_notes_edit(stem, before, f"moved {len(ids)} drum hit(s)")

    def _on_resize_note(self, nid, new_end):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        for n in stem.notes:
            if n["id"] == nid:
                n["end"] = max(n["start"] + 0.03, new_end)
        self._push_notes_edit(stem, before, "resized note")

    def _on_delete_notes(self, ids):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        idset = set(ids)
        stem.notes = [n for n in stem.notes if n["id"] not in idset]
        self.pianoroll.selection -= idset
        self._push_notes_edit(stem, before, f"deleted {len(ids)} note(s)")

    def _on_add_note(self, t, pitch):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        dur = 0.12 if stem.is_drum else 0.4
        stem.notes.append({"id": next(self._id_counter), "start": t,
                           "end": t + dur, "pitch": int(pitch),
                           "vel": 80, "conf": 1.0})
        stem.notes.sort(key=lambda n: (n["start"], n["pitch"]))
        self._push_notes_edit(stem, before, "added note")

    # -- cleanup -------------------------------------------------------------
    def _sync_cleanup_controls(self):
        s = self.project.cleanup_settings if self.project else {}
        self.conf_spin.setValue(s.get("confidence_threshold", 0))
        self.quant_combo.setCurrentText(s.get("quantize", "off"))
        self.quant_strength.setValue(s.get("quantize_strength", 50))
        self.min_note_spin.setValue(s.get("min_note_ms", 0))
        self.min_gap_spin.setValue(s.get("min_gap_ms", 0))
        self.pitch_min_spin.setValue(s.get("pitch_min", 0))
        self.pitch_max_spin.setValue(s.get("pitch_max", 127))
        self.merge_cb.setChecked(s.get("merge_overlaps", True))
        self.fixed_vel_spin.setValue(s.get("fixed_velocity", 0))

    def _read_cleanup_settings(self):
        return {
            "confidence_threshold": self.conf_spin.value(),
            "quantize": self.quant_combo.currentText(),
            "quantize_strength": self.quant_strength.value(),
            "min_note_ms": self.min_note_spin.value(),
            "min_gap_ms": self.min_gap_spin.value(),
            "pitch_min": self.pitch_min_spin.value(),
            "pitch_max": self.pitch_max_spin.value(),
            "merge_overlaps": self.merge_cb.isChecked(),
            "fixed_velocity": self.fixed_vel_spin.value(),
        }

    def apply_cleanup(self):
        stem = self.current_stem()
        if not stem:
            return
        settings = self._read_cleanup_settings()
        self.project.cleanup_settings = settings
        before = _snapshot(stem)
        cleaned, log = cleanup.apply_cleanup(stem.notes, settings,
                                             self.project.tempo)
        for n in cleaned:
            if "id" not in n:
                n["id"] = next(self._id_counter)
        stem.notes = cleaned
        stem.notes.sort(key=lambda n: (n["start"], n["pitch"]))
        self.undo_stack.push(_StemEditCommand(
            self, stem, before, _snapshot(stem),
            f"cleanup on {stem.display_name}: {'; '.join(log)}"))
        self._log_edit(f"cleanup on {stem.display_name}: {'; '.join(log)}")

    def revert_stem(self):
        stem = self.current_stem()
        if not stem:
            return
        before = _snapshot(stem)
        stem.notes = [dict(n) for n in stem.raw_notes]
        for n in stem.notes:
            if "id" not in n:
                n["id"] = next(self._id_counter)
        self.undo_stack.push(_StemEditCommand(
            self, stem, before, _snapshot(stem),
            f"reverted {stem.display_name} to raw detection"))
        self._log_edit(f"reverted {stem.display_name} to raw detection")

    def rerun_stem(self):
        stem = self.current_stem()
        if not stem:
            return
        chosen = self.profile_combo.currentText()
        stem.profile = chosen

        self.statusBar().showMessage(f"Re-transcribing {stem.display_name}…")
        self._rerun_before = _snapshot(stem)
        self._rerun_worker = RetranscribeWorker(stem, chosen)
        self._rerun_worker.finished.connect(self._on_rerun_finished)
        self._rerun_worker.error.connect(self._on_rerun_error)
        self._rerun_worker.start()

    def _on_rerun_finished(self, stem, notes, is_drum):
        for n in notes:
            n["id"] = next(self._id_counter)
        before = self._rerun_before
        stem.notes = notes
        self.undo_stack.push(_StemEditCommand(
            self, stem, before, _snapshot(stem),
            f"re-ran {stem.display_name} (profile {stem.profile})"))
        self._log_edit(f"re-ran {stem.display_name} with profile {stem.profile}")
        self.statusBar().showMessage(
            f"{stem.display_name}: {len(notes)} notes")

    def _on_rerun_error(self, msg):
        QMessageBox.warning(self, "Re-run failed", msg)

    # -- transport / view ------------------------------------------------------
    def _on_position(self, pos):
        self.tv.playhead = pos
        self.waveform.update()
        self.pianoroll.update()
        m = int(pos // 60)
        self.time_label.setText(f"{m}:{pos % 60:04.1f}")

    def _on_player_state(self, state):
        self.btn_play.setEnabled(state != "playing")

    def _on_zoom(self, value):
        self.tv.pps = float(value)
        self._update_scrollbar()
        self.waveform.update()
        self.pianoroll.update()

    def _on_scroll(self, value):
        self.tv.x_offset = float(value)
        self.waveform.update()
        self.pianoroll.update()

    def _update_scrollbar(self):
        total_px = int(self.tv.duration * self.tv.pps)
        view_px = self.pianoroll.width() or 800
        self.hscroll.setRange(0, max(0, total_px - view_px))
        self.hscroll.setPageStep(view_px)

    def audition_selection(self):
        stem = self.current_stem()
        if not stem:
            return
        sel = [n for n in stem.notes if n["id"] in self.pianoroll.selection]
        if not sel:
            QMessageBox.information(self, "Audition",
                                    "Select one or more notes first.")
            return
        self.player.audition_notes(sel, stem.is_drum)

    # -- session ---------------------------------------------------------------
    def save_session(self):
        if not self.project:
            QMessageBox.information(self, "Save session", "Nothing to save yet.")
            return
        path = self._session_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save session", f"{self.project.song}.stem2midi.json",
                "Session (*.stem2midi.json)")
            if not path:
                return
            self._session_path = path
        session_mod.save_session(self.project, path)
        self._dirty = False
        self.statusBar().showMessage(f"Session saved: {path}")

    def open_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open session", "", "Session (*.stem2midi.json)")
        if not path:
            return
        try:
            project, missing = session_mod.load_session(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Open session",
                                f"Could not read session file:\n{e}")
            return
        for mp_ in missing:
            new, ok = QInputDialog.getText(
                self, "Relink missing file",
                f"File not found:\n{mp_}\n\nEnter its new location (or cancel to skip):")
            if ok and new.strip() and os.path.isfile(new.strip()):
                session_mod.relink(project, mp_, new.strip())
        self._session_path = path
        self._load_project(project)
        self.statusBar().showMessage(f"Session opened: {path}")

    # -- export ------------------------------------------------------------------
    def export(self):
        if not self.project:
            QMessageBox.information(self, "Export", "Nothing to export yet.")
            return
        dlg = ExportDialog(self, self.project.stems)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        out_dir = dlg.dir_edit.text().strip() or os.path.expanduser("~")
        try:
            written = pipeline.export_all(
                self.project, out_dir,
                per_stem=True,
                multitrack=dlg.cb_multi.isChecked(),
                wavs=True,
                stem_exports=dlg.stem_exports())
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(e))
            return
        ts = datetime.now(timezone.utc).isoformat()
        self.project.export_history.append(
            {"time": ts, "kind": "export", "path": out_dir,
             "files": len(written)})
        self.statusBar().showMessage(f"Exported {len(written)} files to {out_dir}")
        QMessageBox.information(self, "Export",
                                f"Wrote {len(written)} files to:\n{out_dir}")
