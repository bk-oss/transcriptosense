# src/ingestion/preprocess.py
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

import torch
import numpy as np
import soundfile as sf


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
# Priority:
# 1) --ffmpeg argument
# 2) FFMPEG_PATH env var
# 3) local constant below (edit if needed)
DEFAULT_FFMPEG_PATH = r"C:\Users\mbaklouti1\Downloads\ffmpeg-8.1.2-essentials_build\ffmpeg-8.1.2-essentials_build\bin\ffmpeg.exe"


@dataclass
class SpeechSegment:
    start: float  # seconds
    end: float    # seconds


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def resolve_ffmpeg_path(cli_ffmpeg: Optional[str] = None) -> str:
    if cli_ffmpeg:
        ffmpeg = cli_ffmpeg
    else:
        ffmpeg = os.getenv("FFMPEG_PATH", DEFAULT_FFMPEG_PATH)

    ffmpeg_path = Path(ffmpeg)
    if not ffmpeg_path.exists():
        raise FileNotFoundError(
            f"ffmpeg not found at: {ffmpeg_path}\n"
            f"Set a valid path with:\n"
            f'  --ffmpeg "C:\\path\\to\\ffmpeg.exe"\n'
            f"or env var:\n"
            f'  $env:FFMPEG_PATH="C:\\path\\to\\ffmpeg.exe"'
        )
    return str(ffmpeg_path)


def run_ffmpeg_convert_to_16k_mono_wav(input_path: Path, output_wav: Path, ffmpeg_exe: str) -> None:
    """
    Convert any input audio to 16kHz mono WAV (PCM 16-bit) using ffmpeg.
    """
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(input_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(output_wav),
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffmpeg conversion failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr:\n{e.stderr}"
        ) from e


def load_audio_for_silero_vad(wav_path: Path, device: str) -> torch.Tensor:
    """
    Load WAV as float32 torch tensor [T] on selected device.
    Expects 16kHz mono wav (if stereo appears, converts to mono safely).
    """
    audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)

    if sr != 16000:
        raise ValueError(f"Expected 16kHz WAV, got {sr}Hz from {wav_path}")

    # stereo/multi-channel -> mono
    if isinstance(audio, np.ndarray) and audio.ndim == 2:
        audio = audio.mean(axis=1)

    audio_t = torch.from_numpy(audio.astype(np.float32))  # [T]
    return audio_t.to(device)


def run_silero_vad_segments(audio: torch.Tensor, device: str, sr: int = 16000) -> List[SpeechSegment]:
    """
    Run Silero VAD and return speech segments with timestamps in seconds.
    """
    try:
        from silero_vad import load_silero_vad, get_speech_timestamps
    except Exception as e:
        raise RuntimeError(
            "Could not import silero_vad. Install with:\n"
            "  pip install silero-vad"
        ) from e

    model = load_silero_vad()
    model = model.to(device)

    speech_timestamps = get_speech_timestamps(
        audio,
        model,
        sampling_rate=sr,
        return_seconds=False
    )

    segments: List[SpeechSegment] = []
    for seg in speech_timestamps:
        start = float(seg["start"]) / sr
        end = float(seg["end"]) / sr
        if end > start:
            segments.append(SpeechSegment(start=start, end=end))

    return segments


def merge_close_segments(segments: List[SpeechSegment], max_gap_sec: float = 0.20) -> List[SpeechSegment]:
    """
    Merge segments separated by tiny silences (<= max_gap_sec).
    """
    if not segments:
        return []

    merged = [segments[0]]
    for seg in segments[1:]:
        last = merged[-1]
        if seg.start - last.end <= max_gap_sec:
            last.end = max(last.end, seg.end)
        else:
            merged.append(seg)
    return merged


def filter_short_segments(segments: List[SpeechSegment], min_duration_sec: float = 0.15) -> List[SpeechSegment]:
    return [s for s in segments if (s.end - s.start) >= min_duration_sec]


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------
def preprocess_audio(
    input_audio_path: Path,
    work_dir: Path = Path("data"),
    ffmpeg_exe: Optional[str] = None,
    merge_gap_sec: float = 0.20,
    min_seg_sec: float = 0.15,
) -> Dict[str, Any]:
    """
    Bronze ingestion:
      raw audio -> 16kHz mono wav -> VAD segments -> JSON metadata
    """
    input_audio_path = input_audio_path.resolve()
    if not input_audio_path.exists():
        raise FileNotFoundError(f"Input audio not found: {input_audio_path}")

    ffmpeg_path = resolve_ffmpeg_path(ffmpeg_exe)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    interim_dir = (work_dir / "interim").resolve()
    interim_dir.mkdir(parents=True, exist_ok=True)

    wav_path = interim_dir / f"{input_audio_path.stem}_16k_mono.wav"
    vad_json_path = interim_dir / f"{input_audio_path.stem}_vad.json"

    # 1) Convert
    run_ffmpeg_convert_to_16k_mono_wav(input_audio_path, wav_path, ffmpeg_path)

    # 2) Load
    audio = load_audio_for_silero_vad(wav_path, device=device)

    # 3) VAD
    segments = run_silero_vad_segments(audio, device=device, sr=16000)
    segments = merge_close_segments(segments, max_gap_sec=merge_gap_sec)
    segments = filter_short_segments(segments, min_duration_sec=min_seg_sec)

    total_speech = float(sum(s.end - s.start for s in segments))

    out: Dict[str, Any] = {
        "source": str(input_audio_path),
        "wav_16k_mono": str(wav_path),
        "device": device,
        "ffmpeg": ffmpeg_path,
        "vad": {
            "sampling_rate": 16000,
            "merge_gap_sec": merge_gap_sec,
            "min_seg_sec": min_seg_sec,
            "num_segments": len(segments),
            "total_speech_sec": round(total_speech, 3),
        },
        "speech_segments": [asdict(s) for s in segments],
    }

    vad_json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion: ffmpeg -> 16k mono wav + Silero VAD JSON")
    parser.add_argument("--input", required=True, help="Path to input audio (.mp3/.m4a/.wav/...)")
    parser.add_argument("--work_dir", default="data", help="Project work dir (default: data)")
    parser.add_argument("--ffmpeg", default=None, help="Optional path to ffmpeg.exe")
    parser.add_argument("--merge_gap_sec", type=float, default=0.20, help="Merge adjacent VAD segments with gap <= this")
    parser.add_argument("--min_seg_sec", type=float, default=0.15, help="Drop VAD segments shorter than this")
    args = parser.parse_args()

    result = preprocess_audio(
        input_audio_path=Path(args.input),
        work_dir=Path(args.work_dir),
        ffmpeg_exe=args.ffmpeg,
        merge_gap_sec=args.merge_gap_sec,
        min_seg_sec=args.min_seg_sec,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
