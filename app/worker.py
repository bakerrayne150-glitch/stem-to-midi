#!/usr/bin/env python3
"""worker.py — PipelineWorker: runs the full mix pipeline off the UI thread.

Stages (progress signal): decoding -> separating -> tempo -> identifying ->
transcribing (per stem) -> cleaning -> ready. Cancel terminates the
separation child process and stops between transcription stems.
"""
import os
import threading
import time
import traceback

from PySide6.QtCore import QObject, Signal

from app import pipeline
from app.models import pitched_tuples_to_notes, drum_tuples_to_notes


class PipelineWorker(QObject):
    progress = Signal(str, int, int)   # stage label, current, total
    stage = Signal(str)                # human-readable stage label
    stem_done = Signal(str, int)       # label, note count
    finished = Signal(object)          # Project
    error = Signal(str)                # plain-language error, partial work kept
    cancelled = Signal()

    def __init__(self, input_path, stems_mode, work_dir, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.stems_mode = stems_mode      # 6 or 4
        self.work_dir = work_dir          # stems land in work_dir/"stems"
        self._cancel = threading.Event()
        self._thread = None

    # -- control ---------------------------------------------------------
    def start(self):
        import threading as th
        self._thread = th.Thread(target=self._run, daemon=True,
                                 name="pipeline-worker")
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    # -- run -------------------------------------------------------------
    def _run(self):
        from app.models import Project, StemTrack
        try:
            t0 = time.perf_counter()
            self.stage.emit("Decoding audio…")
            info = pipeline.probe_audio(self.input_path)
            self.progress.emit("decoding", 1, 1)

            self.stage.emit("Separating stems (CPU — this takes a while)…")
            stems_dir = os.path.join(self.work_dir, "stems")
            written = pipeline.separate_cancellable(
                self.input_path, stems_dir, self.stems_mode,
                self._cancel, progress_cb=None)
            self._check_cancel()

            self.stage.emit("Estimating tempo…")
            tempo = pipeline.estimate_tempo(self.input_path)
            self._check_cancel()

            self.stage.emit("Identifying stems…")
            # Labels come from the separator; per-stem profiles assigned here.
            self._check_cancel()

            self.stage.emit("Transcribing stems…")
            model = pipeline.load_pitch_model_shared()
            project = Project()
            project.source_path = os.path.abspath(self.input_path)
            project.song = os.path.splitext(os.path.basename(self.input_path))[0]
            project.stems_mode = self.stems_mode
            project.tempo = tempo
            project.duration = info["duration"]
            project.sample_rate = info["sample_rate"]

            order = (pipeline.STEM_ORDER_6 if self.stems_mode == 6
                     else pipeline.STEM_ORDER_4)
            by_label = dict(written)
            total = len(order)
            for i, label in enumerate(order, 1):
                self._check_cancel()
                self.progress.emit("transcribing", i, total)
                wav_path = by_label[label]
                tuples, is_drum = pipeline.transcribe_stem(
                    wav_path, label, pitch_model=model)
                stem = StemTrack(
                    label=label,
                    display_name=label.capitalize(),
                    wav_path=wav_path,
                    profile=pipeline.PROFILE_FOR[label],
                    channel=pipeline.CHANNEL_FOR[label],
                    is_drum=is_drum)
                if is_drum:
                    stem.set_raw_notes(drum_tuples_to_notes(tuples))
                else:
                    stem.set_raw_notes(pitched_tuples_to_notes(tuples))
                project.stems.append(stem)
                self.stem_done.emit(label, len(stem.notes))

            self._check_cancel()
            self.stage.emit("Cleaning up…")
            from app import cleanup
            for stem in project.stems:
                cleaned, _log = cleanup.apply_cleanup(
                    stem.notes, project.cleanup_settings, project.tempo)
                stem.notes = cleaned
            self.progress.emit("cleaning", 1, 1)

            self.stage.emit(
                f"Ready ({time.perf_counter() - t0:.0f}s total)")
            self.progress.emit("ready", 1, 1)
            self.finished.emit(project)
        except pipeline.CancelledError:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 — surfaced to the UI
            self.error.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")

    def _check_cancel(self):
        if self._cancel.is_set():
            raise pipeline.CancelledError("cancelled by user")
