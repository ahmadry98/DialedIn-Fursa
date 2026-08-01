"""Audio timing wrappers used by the espresso MCP tools."""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from modeling import audio_analysis as modeling_audio

AUDIO_OUTPUT_DIR = Path(tempfile.gettempdir()) / "espresso_mcp_audio"


def extract_audio_track(video_s3_key: str, output_dir: str | None = None) -> dict[str, Any]:
    """Extract audio from a local video key/path into a WAV file.

    The MVP treats ``video_s3_key`` as a local file path during development. The
    later storage checkpoint can replace path resolution with S3 download/upload.
    """
    media_path = Path(video_s3_key)
    if not media_path.exists():
        raise FileNotFoundError(f"Video/audio key does not exist locally: {video_s3_key}")

    output_root = Path(output_dir) if output_dir else AUDIO_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    wav_path = output_root / f"{media_path.stem}.wav"
    modeling_audio.extract_audio_to_wav(media_path, wav_path)
    return {
        "video_s3_key": video_s3_key,
        "audio_s3_key": str(wav_path),
        "audio_path": str(wav_path),
        "sample_rate": modeling_audio.DEFAULT_SAMPLE_RATE,
        "status": "ok",
    }


def detect_machine_audio_window(audio_s3_key: str) -> dict[str, Any]:
    """Detect machine start/stop timing from an extracted WAV file."""
    result = modeling_audio.analyze_wav(Path(audio_s3_key))
    return asdict(result)


def calculate_total_shot_time(machine_start_time: float, machine_stop_time: float) -> dict[str, Any]:
    """Calculate total shot time from start and stop timestamps."""
    start = float(machine_start_time)
    stop = float(machine_stop_time)
    if stop <= start:
        raise ValueError("machine_stop_time must be greater than machine_start_time")
    return {
        "machine_start_time": round(start, 2),
        "machine_stop_time": round(stop, 2),
        "total_shot_seconds": round(stop - start, 2),
    }


def analyze_audio_timing(video_s3_key: str) -> dict[str, Any]:
    """Extract/analyze audio timing for a local video or WAV key/path."""
    result = modeling_audio.analyze_media(Path(video_s3_key))
    return asdict(result)
