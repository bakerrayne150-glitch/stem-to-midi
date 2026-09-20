#!/usr/bin/env python3
"""pipeline.py — importable Phase B pipeline stages for the GUI.

Separation runs in a child process (via multiprocessing) so Cancel can
terminate it for real; transcription runs in the caller's worker thread and
checks a threading.Event between stems.
"""
import os
import sys
import time
import queue as queue_mod
import multiprocessing as mp

# Engine modules live one level up (~/workspace/stem-to-midi/).
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

STEM_ORDER_6 = ["vocals", "drums", "bass", "guitar", "piano", "other"]
STEM_ORDER_4 = ["vocals", "drums", "bass", "other"]

PROFILE_FOR = {
    "vocals": "vocal",
    "drums": None,          # drum engine
    "bass": "bass",
    "guitar": "guitar",
    "piano": "piano",
    "other": "other",
}

CHANNEL_FOR = {
    "vocals": 0, "drums": 9, "bass": 1,
    "guitar": 2, "piano": 3, "other": 4,
}


def _separate_child(input_path, out_dir, n_stems, q, log_path):
    """Child-process target: runs Demucs, reports back on a queue.

    The child's stdout/stderr go to separation.log (the packaged app has no
    console), and *any* BaseException — including SystemExit from legacy
    fail() paths — is reported instead of killing the child silently.
    """
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    sys.stdout = log
    sys.stderr = log
    try:
        from separate import separate_to_wavs
        written = separate_to_wavs(input_path, out_dir, n_stems)
    except BaseException as e:  # noqa: BLE001 — must cross the process boundary
        q.put(("error", f"separation failed: {e}"))
    else:
        q.put(("done", written))
    finally:
        log.close()


def _read_log_tail(log_path, n=15):
    """Last n lines of the child log, for error reports. Never raises."""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        tail = [ln for ln in lines if ln.strip()][-n:]
        if tail:
            return "\n\nSeparation log (last lines):\n" + "\n".join(tail)
    except OSError:
        pass
    return ""


def separate_cancellable(input_path, out_dir, n_stems, cancel_event,
                         progress_cb, poll_s=0.2):
    """Run Demucs in a child process. Returns list of (label, wav_path).

    Raises CancelledError if cancel_event is set (child is terminated),
    RuntimeError on separation failure.
    """
    # Windows has no fork(); the packaged app must use spawn everywhere.
    # ("spawn" also requires freeze_support() in the entry point, which
    # app/main.py provides.)
    _ctx_name = "spawn" if os.name == "nt" else "fork"
    ctx = mp.get_context(_ctx_name)
    q = ctx.Queue()
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "separation.log")
    proc = ctx.Process(target=_separate_child,
                       args=(input_path, out_dir, n_stems, q, log_path))
    proc.start()
    try:
        while True:
            if cancel_event.is_set():
                raise CancelledError("separation cancelled by user")
            try:
                kind, payload = q.get(timeout=poll_s)
            except queue_mod.Empty:
                if not proc.is_alive():
                    raise RuntimeError(
                        "separation process exited without reporting a result"
                        + _read_log_tail(log_path))
                continue
            if kind == "done":
                return payload
            raise RuntimeError(payload + _read_log_tail(log_path))
    finally:
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=10)
        # drain so the Queue's feeder thread doesn't block process exit
        try:
            while True:
                q.get_nowait()
        except queue_mod.Empty:
            pass


class CancelledError(Exception):
    pass


def probe_audio(input_path):
    """Stage 'decoding': duration, sample rate, channels. Raises on failure."""
    import soundfile as sf
    try:
        info = sf.info(input_path)
    except Exception as e:
        raise RuntimeError(
            f"could not read audio file '{os.path.basename(input_path)}': {e}")
    if info.frames == 0:
        raise RuntimeError("audio file is empty")
    return {"duration": info.frames / info.samplerate,
            "sample_rate": info.samplerate,
            "channels": info.channels}


def estimate_tempo(input_path):
    """Estimate BPM; 120 fallback. Never raises."""
    try:
        import numpy as np
        import librosa
        y, sr = librosa.load(input_path, sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.atleast_1d(tempo)[0])
        if 50 <= tempo <= 220:
            return tempo
    except Exception:
        pass
    return 120.0


def transcribe_stem(wav_path, label, pitch_model=None):
    """Transcribe one stem WAV -> (notes, is_drum).

    Pitched: list of (start_s, end_s, midi_pitch, velocity).
    Drums:   list of (time_s, gm_note, velocity) — use
             models.drum_tuples_to_notes to get note dicts.
    """
    from transcribe import transcribe_pitched, transcribe_drums
    profile = PROFILE_FOR[label]
    if profile is None:
        return transcribe_drums(wav_path), True
    if pitch_model is None:
        from transcribe import load_pitch_model
        pitch_model = load_pitch_model()
    return transcribe_pitched(wav_path, profile=profile, model=pitch_model), False


def load_pitch_model_shared():
    from transcribe import load_pitch_model
    return load_pitch_model()


def model_versions():
    """Best-effort record of model/dependency versions for the session file."""
    info = {}
    try:
        import demucs
        info["demucs_code"] = getattr(demucs, "__version__", "unknown")
    except Exception:
        pass
    try:
        import basic_pitch
        info["basic_pitch_code"] = getattr(basic_pitch, "__version__", "unknown")
    except Exception:
        pass
    info["pitch_model"] = os.environ.get("BP_MODEL", "tflite")
    return info


def export_all(project, out_dir, per_stem=True, multitrack=True, wavs=True):
    """Write exports per the CLI naming contract. Returns list of paths."""
    import shutil
    import mido
    from midi_out import make_multitrack, make_track, TICKS_PER_BEAT
    os.makedirs(out_dir, exist_ok=True)
    song = project.song or "export"
    order = [s.label for s in project.stems]
    written = []

    tracks = []
    for i, stem in enumerate(project.stems, 1):
        notes = [(n["start"], n["end"], n["pitch"], n["vel"]) for n in stem.notes]
        tracks.append({"name": stem.display_name, "channel": stem.channel,
                       "notes": notes, "is_drum": stem.is_drum})
        if per_stem:
            mid = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
            mid.tracks.append(mido.MidiTrack())
            mid.tracks[0].append(mido.MetaMessage(
                "set_tempo", tempo=mido.bpm2tempo(project.tempo), time=0))
            t = tracks[-1]
            mid.tracks.append(make_track(t["name"], t["channel"], t["notes"],
                                         project.tempo, TICKS_PER_BEAT,
                                         is_drum=t["is_drum"]))
            p = os.path.join(out_dir, f"{song} - {i:02d} {stem.display_name}.mid")
            mid.save(p)
            written.append(p)
        if wavs and os.path.isfile(stem.wav_path):
            p = os.path.join(out_dir, f"{song} - {i:02d} {stem.display_name}.wav")
            shutil.copy2(stem.wav_path, p)
            written.append(p)

    if multitrack:
        multi = make_multitrack(tracks, tempo_bpm=project.tempo,
                                ticks_per_beat=TICKS_PER_BEAT)
        p = os.path.join(out_dir, f"{song} - multitrack.mid")
        multi.save(p)
        written.append(p)
    return written
