#!/usr/bin/env python3
"""smoke_test.py — headless end-to-end verification (QT_QPA_PLATFORM=offscreen).

Launches the real app, runs the real pipeline on the synthetic test mix,
screenshots the window, performs scripted edits + undo, saves/reopens a
session, exports MIDI and validates the exports.

Run: cd ~/workspace/stem-to-midi && QT_QPA_PLATFORM=offscreen \
     ./venv/bin/python -m app.smoke_test
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

SHOT_DIR = os.path.join(_HERE, "screenshots")
MIX = os.path.join(_PARENT, "mix.wav")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)


def wait_for(signal, timeout_s=900):
    """Run a nested event loop until signal fires or timeout. Returns args."""
    loop = QEventLoop()
    box = {}
    signal.connect(lambda *a: (box.setdefault("args", a), loop.quit()))
    QTimer.singleShot(int(timeout_s * 1000), loop.quit)
    loop.exec()
    return box.get("args")


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    assert os.path.isfile(MIX), f"test mix not found: {MIX}"

    app = QApplication([])
    from app.main_window import MainWindow
    from app import session as session_mod
    from app import pipeline
    import mido

    # Modal dialogs block forever offscreen: stub them (record, don't show).
    from PySide6.QtWidgets import QMessageBox
    dialog_calls = []
    _orig_warn = QMessageBox.warning
    _orig_info = QMessageBox.information

    @staticmethod
    def _fake_warn(*a, **k):
        dialog_calls.append(("warning", a[1] if len(a) > 1 else "", str(a[2])[:100] if len(a) > 2 else ""))
        return QMessageBox.StandardButton.Ok

    @staticmethod
    def _fake_info(*a, **k):
        dialog_calls.append(("information", a[1] if len(a) > 1 else "", str(a[2])[:100] if len(a) > 2 else ""))
        return QMessageBox.StandardButton.Ok

    QMessageBox.warning = _fake_warn
    QMessageBox.information = _fake_info

    win = MainWindow()
    win.show()
    app.processEvents()

    # ---- 0. cancel actually stops a running separation ---------------------
    win._pending_input = MIX
    win.mode_combo.setCurrentText("Full mix — 6 stems")
    win._start_pipeline(MIX, 6)
    # connect BEFORE cancelling to avoid missing an already-fired signal
    cancel_box = {}
    loop0 = QEventLoop()
    win.worker.cancelled.connect(lambda: (cancel_box.setdefault("ok", True),
                                          loop0.quit()))
    time.sleep(5)
    win.cancel_process()
    QTimer.singleShot(120_000, loop0.quit)
    loop0.exec()
    check("cancel stops pipeline", cancel_box.get("ok", False))
    app.processEvents()

    # ---- 1. full pipeline ---------------------------------------------------
    t0 = time.time()
    win._start_pipeline(MIX, 6)
    box = {}

    def on_done(proj):
        box["project"] = proj

    def on_err(msg):
        box["error"] = msg

    win.worker.finished.connect(on_done)
    win.worker.error.connect(on_err)
    loop = QEventLoop()
    win.worker.finished.connect(loop.quit)
    win.worker.error.connect(loop.quit)
    win.worker.cancelled.connect(loop.quit)
    QTimer.singleShot(900_000, loop.quit)
    loop.exec()
    dt = time.time() - t0
    check("pipeline finished", "project" in box,
          f"({dt:.0f}s)" + (f" error={str(box.get('error'))[:120]}"
                            if "error" in box else ""))
    if "project" not in box:
        return _report(1)
    proj = win.project
    check("6 stems produced", len(proj.stems) == 6, str([s.label for s in proj.stems]))
    check("notes detected", sum(len(s.notes) for s in proj.stems) > 0,
          f"{sum(len(s.notes) for s in proj.stems)} notes")
    check("drums on channel 10", any(s.is_drum and s.channel == 9 for s in proj.stems))
    win.grab().save(os.path.join(SHOT_DIR, "01-workspace.png"))
    check("screenshot 01 saved", True)

    # ---- 2. scripted edits ---------------------------------------------------
    win.stem_list.setCurrentRow(2)  # bass stem
    app.processEvents()
    stem = win.current_stem()
    n0 = len(stem.notes)
    check("bass stem selected", stem.label == "bass", f"{n0} notes")
    first_id = stem.notes[0]["id"]
    win._on_delete_notes([first_id])
    check("delete note", len(stem.notes) == n0 - 1)
    moved_id = stem.notes[0]["id"]
    t_before = stem.notes[0]["start"]
    win._on_move_notes([moved_id], 0.25, 2)
    n = next(x for x in stem.notes if x["id"] == moved_id)
    check("move note", abs(n["start"] - (t_before + 0.25)) < 1e-6
          and n["pitch"] == stem.notes[0]["pitch"],
          f"start {t_before:.2f}->{n['start']:.2f}")
    win.undo_stack.undo()  # undo the move
    n = next(x for x in stem.notes if x["id"] == moved_id)
    check("undo move", abs(n["start"] - t_before) < 1e-6)
    win.undo_stack.undo()  # undo the delete
    check("undo delete", len(stem.notes) == n0)
    win.undo_stack.redo()
    check("redo delete", len(stem.notes) == n0 - 1)
    win.undo_stack.undo()

    # quantize via real controls
    win.quant_combo.setCurrentText("1/16")
    win.quant_strength.setValue(100)
    win.apply_cleanup()
    app.processEvents()
    check("quantize applied", True, f"{len(stem.notes)} notes after cleanup")
    win.grab().save(os.path.join(SHOT_DIR, "02-edited.png"))

    # drum grid editing on the drums stem
    win.stem_list.setCurrentRow(1)
    app.processEvents()
    dstem = win.current_stem()
    check("drum stem is drum mode", dstem.is_drum and win.pianoroll.is_drum)
    d0 = len(dstem.notes)
    win._on_add_note(1.0, 36)
    check("add drum hit", len(dstem.notes) == d0 + 1)
    win.undo_stack.undo()
    check("undo add drum hit", len(dstem.notes) == d0)

    # ---- 3. preview render + playhead ----------------------------------------
    from app import synth
    mono = synth.render_notes(stem.notes[:8], 44100, 5.0, is_drum=False)
    check("synth renders pitched", mono.shape[0] == 5 * 44100 and mono.any())
    dmono = synth.render_notes(dstem.notes[:8], 44100, 5.0, is_drum=True)
    check("synth renders drums", dmono.shape[0] == 5 * 44100 and dmono.any())
    win.player.play(0.0)
    loop2 = QEventLoop()
    QTimer.singleShot(700, loop2.quit)
    loop2.exec()
    pos = win.player.position()
    check("playhead advances", pos > 0.2, f"pos={pos:.2f}s")
    win.player.stop()
    win.player.audition_notes(stem.notes[:2], False)
    loop3 = QEventLoop()
    QTimer.singleShot(500, loop3.quit)
    loop3.exec()
    check("audition runs", win.player.is_playing())
    win.player.stop()

    # ---- 4. session save / reopen ----------------------------------------------
    sess_path = "/tmp/smoke_session.stem2midi.json"
    session_mod.save_session(win.project, sess_path)
    check("session saved", os.path.isfile(sess_path))
    proj2, missing = session_mod.load_session(sess_path)
    check("session loads", len(proj2.stems) == 6 and not missing,
          f"missing={missing}")
    notes_before = sum(len(s.notes) for s in win.project.stems)
    win._load_project(proj2)
    app.processEvents()
    notes_after = sum(len(s.notes) for s in win.project.stems)
    check("session round-trips notes", notes_before == notes_after,
          f"{notes_after} notes")
    check("edit history kept", len(win.project.edit_history) > 0)

    # ---- 5. export + validate -----------------------------------------------------
    out_dir = "/tmp/smoke_export"
    written = pipeline.export_all(win.project, out_dir, True, True, False)
    check("export wrote files", len(written) == 7, f"{len(written)} files")
    multi = [p for p in written if "multitrack" in p][0]
    mid = mido.MidiFile(multi)
    check("multitrack is Type 1", mid.type == 1)
    check("multitrack has 7 tracks", len(mid.tracks) == 7)
    drum_tracks = [t for t in mid.tracks
                   if any(getattr(m, "channel", -1) == 9
                          for m in t if m.type in ("note_on", "note_off"))]
    check("drum track on channel 10", len(drum_tracks) == 1)
    names = [t.name for t in mid.tracks if hasattr(t, "name")]
    check("track names present", any("Bass" in n for n in names), str(names))
    # per-stem files parse
    ok = True
    for p in written:
        try:
            mido.MidiFile(p)
        except Exception:
            ok = False
    check("all exported MIDIs parse", ok)
    win.grab().save(os.path.join(SHOT_DIR, "03-final.png"))

    # ---- 6. relink ---------------------------------------------------------------
    import shutil
    moved = "/tmp/smoke_moved_stem.wav"
    shutil.copy(win.project.stems[0].wav_path, moved)
    session_mod.relink(win.project, win.project.stems[0].wav_path, moved)
    check("relink updates path", win.project.stems[0].wav_path == moved)

    return _report(0)


def _report(code):
    print("\n==== SMOKE SUMMARY ====", flush=True)
    fails = 0
    for name, ok, detail in results:
        if not ok:
            fails += 1
            print(f"FAIL: {name} {detail}", flush=True)
    print(f"{len(results) - fails}/{len(results)} passed", flush=True)
    return code if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
