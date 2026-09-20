#!/usr/bin/env python3
"""separate.py — full-mix stem separation via Demucs (Phase B).

Usage: python separate.py input.wav -o stems_dir/ [--stems 6|4]

Writes stereo WAVs at the source sample rate with stable names:
    <song> - 01 Vocals.wav, <song> - 02 Drums.wav, <song> - 03 Bass.wav,
    <song> - 04 Guitar.wav, <song> - 05 Piano.wav, <song> - 06 Other.wav
(4-stem mode: vocals / drums / bass / other)

Models are cached under ./models/ (TORCH_HOME) so the project dir stays
self-contained. CPU only in Phase B.
"""
import argparse
import os
import sys
import tempfile

# Keep model weights inside the project dir (also keeps ~/.cache clean).
os.environ.setdefault(
    "TORCH_HOME", os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
)

import numpy as np
import soundfile as sf

STEM_ORDER_6 = ["vocals", "drums", "bass", "guitar", "piano", "other"]
STEM_ORDER_4 = ["vocals", "drums", "bass", "other"]
MODEL_FOR = {6: "htdemucs_6s", 4: "htdemucs"}


def fail(msg):
    """Fatal separation failure.

    Raises SeparationError (instead of sys.exit) so programmatic callers —
    e.g. the GUI's child process — receive the real message and can report
    it. The CLI converts it back to exit code 2.
    """
    raise SeparationError(msg)


class SeparationError(Exception):
    """Fatal, user-readable separation failure."""


def separate_to_wavs(input_path, out_dir, n_stems=6):
    """Run Demucs and write labeled stem WAVs. Returns list of (label, wav_path)."""
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    from demucs.audio import save_audio

    if not os.path.isfile(input_path):
        fail(f"input file not found: {input_path}")
    song = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(out_dir, exist_ok=True)

    order = STEM_ORDER_6 if n_stems == 6 else STEM_ORDER_4
    model_name = MODEL_FOR[n_stems]

    print(f"[1/3] decoding {input_path} ...", flush=True)
    try:
        wav, src_sr = sf.read(input_path, always_2d=True)
    except Exception as e:
        fail(f"could not decode input audio: {e}")
    wav = wav.T  # (channels, samples); demucs wants channels-first
    if wav.shape[0] == 1:
        wav = np.repeat(wav, 2, axis=0)
    elif wav.shape[0] > 2:
        wav = wav[:2]

    print(f"[2/3] loading model {model_name} (first run downloads weights) ...", flush=True)
    try:
        model = get_model(model_name)
    except Exception as e:
        fail(f"could not load/download Demucs model {model_name!r}: {e}\n"
             f"check your internet connection and retry.")
    model.cpu()
    model.eval()

    target_sr = model.samplerate
    mix = torch.from_numpy(wav).float()
    if src_sr != target_sr:
        import torchaudio
        mix = torchaudio.functional.resample(mix, src_sr, target_sr)

    print(f"[3/3] separating into {n_stems} stems (CPU) ...", flush=True)
    try:
        with torch.no_grad():
            sources = apply_model(model, mix[None], device="cpu",
                                  progress=True, num_workers=0)[0]
    except RuntimeError as e:
        fail(f"separation ran out of memory or crashed: {e}")
    # sources: (n_sources, channels, samples) at target_sr
    model_sources = list(model.sources)
    print(f"model source order: {model_sources}", flush=True)

    # Resample separated audio back to the source sample rate for export.
    written = []
    for idx, label in enumerate(order):
        num = order.index(label) + 1
        final_name = f"{song} - {num:02d} {label.capitalize()}.wav"
        final_path = os.path.join(out_dir, final_name)
        stem = sources[model_sources.index(label)]
        if target_sr != src_sr:
            import torchaudio
            stem = torchaudio.functional.resample(stem, target_sr, src_sr)
        # Atomic write: temp file then rename, so a crash never leaves a
        # half-written WAV masquerading as a finished stem.
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", dir=out_dir)
        os.close(fd)
        try:
            save_audio(stem, tmp_path, src_sr)
            os.replace(tmp_path, final_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        written.append((label, final_path))
        print(f"  wrote {final_name}", flush=True)

    print("done.", flush=True)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Separate a full mix into stems with Demucs.")
    ap.add_argument("input", help="Input audio file")
    ap.add_argument("-o", "--output", required=True, help="Output directory for stem WAVs")
    ap.add_argument("--stems", type=int, choices=(4, 6), default=6,
                    help="4 = fast (vocals/drums/bass/other), 6 = detailed (default)")
    args = ap.parse_args()
    try:
        separate_to_wavs(args.input, args.output, args.stems)
    except SeparationError as e:
        print(f"separate.py: error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
