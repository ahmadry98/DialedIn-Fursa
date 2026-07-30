#!/usr/bin/env python3
"""Detect espresso machine timing from audio.

The MVP uses audio as the primary timing signal. It extracts or reads a mono WAV
track, computes short-window RMS energy, finds the sustained high-energy machine
window, and reports start/stop/total shot time.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi"}
SUPPORTED_AUDIO_SUFFIXES = {".wav"}
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_WINDOW_SECONDS = 0.25
DEFAULT_HOP_SECONDS = 0.10
DEFAULT_THRESHOLD_RATIO = 0.25
DEFAULT_MIN_DURATION_SECONDS = 1.0


@dataclass(frozen=True)
class AudioTimingResult:
    source_path: str
    machine_start_time: float | None
    machine_stop_time: float | None
    total_shot_seconds: float | None
    start_confidence: float
    stop_confidence: float
    audio_method: str
    warnings: list[str]


def discover_media(input_path: Path) -> list[Path]:
    """Return one or more supported media paths from a file or directory."""
    supported = SUPPORTED_VIDEO_SUFFIXES | SUPPORTED_AUDIO_SUFFIXES
    if input_path.is_file():
        if input_path.suffix.lower() not in supported:
            raise ValueError(f"Unsupported media file: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    media = [
        path
        for path in sorted(input_path.iterdir())
        if path.is_file() and path.suffix.lower() in supported
    ]
    if not media:
        raise ValueError(f"No supported media files found in: {input_path}")
    return media


def extract_audio_to_wav(
    media_path: Path,
    wav_path: Path,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> Path:
    """Extract mono WAV audio with ffmpeg, or copy an existing WAV file."""
    media_path = media_path.resolve()
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    if media_path.suffix.lower() == ".wav":
        if media_path.resolve() != wav_path.resolve():
            shutil.copyfile(media_path, wav_path)
        return wav_path

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            str(wav_path),
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return wav_path
        raise RuntimeError(
            "Could not extract audio with ffmpeg: " + completed.stderr.strip()
        )

    afconvert = shutil.which("afconvert")
    if afconvert is not None:
        command = [
            afconvert,
            str(media_path),
            str(wav_path),
            "-f",
            "WAVE",
            "-d",
            "LEI16",
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return wav_path
        raise RuntimeError(
            "Could not extract audio with afconvert. Install ffmpeg with "
            "`brew install ffmpeg` and rerun this command. afconvert error: "
            + completed.stderr.strip()
        )

    raise RuntimeError(
        "A media audio extractor is required. Install ffmpeg with "
        "`brew install ffmpeg`, then rerun this command."
    )


def read_wav_mono(wav_path: Path) -> tuple[np.ndarray, int]:
    """Read a WAV file and return mono float samples in [-1, 1]."""
    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if sample_width != 2:
        raise ValueError("Only 16-bit PCM WAV files are supported")

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, sample_rate


def compute_rms_envelope(
    samples: np.ndarray,
    sample_rate: int,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
) -> tuple[np.ndarray, np.ndarray]:
    """Return frame timestamps and RMS energy values."""
    if samples.size == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    window_size = max(1, int(round(window_seconds * sample_rate)))
    hop_size = max(1, int(round(hop_seconds * sample_rate)))

    timestamps = []
    energies = []
    for start in range(0, max(1, samples.size - window_size + 1), hop_size):
        window = samples[start : start + window_size]
        if window.size == 0:
            continue
        rms = float(np.sqrt(np.mean(np.square(window))))
        center_seconds = (start + window.size / 2) / sample_rate
        timestamps.append(center_seconds)
        energies.append(rms)

    return np.array(timestamps, dtype=np.float32), np.array(energies, dtype=np.float32)


def smooth_energy(energies: np.ndarray, width: int = 5) -> np.ndarray:
    """Smooth energy values with a small moving average."""
    if energies.size == 0 or width <= 1:
        return energies
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(energies, kernel, mode="same")


def _longest_true_run(mask: Sequence[bool], min_frames: int) -> tuple[int, int] | None:
    best = None
    best_len = 0
    start = None
    for index, active in enumerate(mask):
        if active and start is None:
            start = index
        if (not active or index == len(mask) - 1) and start is not None:
            end = index if active and index == len(mask) - 1 else index - 1
            run_len = end - start + 1
            if run_len >= min_frames and run_len > best_len:
                best = (start, end)
                best_len = run_len
            start = None
    return best


def detect_machine_window(
    timestamps: np.ndarray,
    energies: np.ndarray,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
) -> tuple[float | None, float | None, float, float, list[str]]:
    """Detect the sustained high-energy machine/pump window."""
    warnings: list[str] = []
    if timestamps.size == 0 or energies.size == 0:
        return None, None, 0.0, 0.0, ["No audio samples were available."]

    smoothed = smooth_energy(energies)
    max_energy = float(np.max(smoothed))
    baseline_count = max(3, min(int(round(2.0 / hop_seconds)), smoothed.size // 5 or 1))
    baseline = float(np.median(smoothed[:baseline_count]))
    dynamic_range = max_energy - baseline

    if dynamic_range <= 1e-4:
        return None, None, 0.0, 0.0, ["Audio energy did not change enough to detect machine timing."]

    threshold = baseline + dynamic_range * threshold_ratio
    active_mask = smoothed >= threshold
    min_frames = max(1, int(round(min_duration_seconds / hop_seconds)))
    run = _longest_true_run(active_mask.tolist(), min_frames)
    if run is None:
        return None, None, 0.0, 0.0, ["No sustained machine-sound window was detected."]

    start_index, stop_index = run
    start_time = float(timestamps[start_index])
    stop_time = float(timestamps[stop_index])
    confidence = min(1.0, dynamic_range / max(max_energy, 1e-6))

    if confidence < 0.35:
        warnings.append("Audio confidence is low; ask the user to confirm timing.")
    if stop_time <= start_time:
        warnings.append("Detected stop time was not after start time.")
        return None, None, confidence, confidence, warnings

    return (
        round(start_time, 2),
        round(stop_time, 2),
        round(confidence, 2),
        round(confidence, 2),
        warnings,
    )


def analyze_wav(wav_path: Path) -> AudioTimingResult:
    """Analyze one WAV file and return machine timing."""
    samples, sample_rate = read_wav_mono(wav_path)
    timestamps, energies = compute_rms_envelope(samples, sample_rate)
    start, stop, start_conf, stop_conf, warnings = detect_machine_window(
        timestamps,
        energies,
    )
    total = round(stop - start, 2) if start is not None and stop is not None else None
    return AudioTimingResult(
        source_path=str(wav_path),
        machine_start_time=start,
        machine_stop_time=stop,
        total_shot_seconds=total,
        start_confidence=start_conf,
        stop_confidence=stop_conf,
        audio_method="heuristic_energy",
        warnings=warnings,
    )


def analyze_media(media_path: Path) -> AudioTimingResult:
    """Extract audio when needed, then analyze machine timing."""
    if media_path.suffix.lower() == ".wav":
        return analyze_wav(media_path)

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / f"{media_path.stem}.wav"
        extract_audio_to_wav(media_path, wav_path)
        result = analyze_wav(wav_path)
        return AudioTimingResult(
            source_path=str(media_path),
            machine_start_time=result.machine_start_time,
            machine_stop_time=result.machine_stop_time,
            total_shot_seconds=result.total_shot_seconds,
            start_confidence=result.start_confidence,
            stop_confidence=result.stop_confidence,
            audio_method=result.audio_method,
            warnings=result.warnings,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect espresso shot timing from video/audio machine sound."
    )
    parser.add_argument("input_path", type=Path, help="Video/WAV file or directory.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON results instead of a compact text summary.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results = [analyze_media(path) for path in discover_media(args.input_path)]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
        return

    for result in results:
        print(
            f"{Path(result.source_path).stem}: "
            f"start={result.machine_start_time} "
            f"stop={result.machine_stop_time} "
            f"total={result.total_shot_seconds} "
            f"confidence={result.start_confidence}"
        )
        for warning in result.warnings:
            print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
