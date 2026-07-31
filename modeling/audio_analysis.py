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
DEFAULT_THRESHOLD_RATIO = 0.12
DEFAULT_MIN_DURATION_SECONDS = 8.0
PUMP_BAND_LOW_HZ = 80.0
PUMP_BAND_HIGH_HZ = 1000.0
PREFERRED_MIN_SHOT_SECONDS = 15.0
PREFERRED_MAX_SHOT_SECONDS = 45.0
MANUAL_CONFIRMATION_CONFIDENCE_THRESHOLD = 0.35


@dataclass(frozen=True)
class AudioTimingResult:
    source_path: str
    machine_start_time: float | None
    machine_stop_time: float | None
    total_shot_seconds: float | None
    start_confidence: float
    stop_confidence: float
    audio_method: str
    requires_manual_confirmation: bool
    confirmation_reason: str | None
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
    return compute_window_features(
        samples,
        sample_rate,
        window_seconds=window_seconds,
        hop_seconds=hop_seconds,
    )[0:2]


def compute_window_features(
    samples: np.ndarray,
    sample_rate: int,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
    band_low_hz: float = PUMP_BAND_LOW_HZ,
    band_high_hz: float = PUMP_BAND_HIGH_HZ,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return timestamps plus broadband, pump-band, and high-band energies."""
    if samples.size == 0:
        empty = np.array([], dtype=np.float32)
        return empty, empty, empty, empty

    window_size = max(1, int(round(window_seconds * sample_rate)))
    hop_size = max(1, int(round(hop_seconds * sample_rate)))

    timestamps = []
    rms_energies = []
    pump_band_energies = []
    high_band_energies = []

    frequency_bins = np.fft.rfftfreq(window_size, d=1.0 / sample_rate)
    pump_mask = (frequency_bins >= band_low_hz) & (frequency_bins <= band_high_hz)
    high_mask = frequency_bins > band_high_hz

    for start in range(0, max(1, samples.size - window_size + 1), hop_size):
        window = samples[start : start + window_size]
        if window.size == 0:
            continue
        if window.size < window_size:
            window = np.pad(window, (0, window_size - window.size))

        tapered = window * np.hanning(window_size)
        spectrum = np.abs(np.fft.rfft(tapered)) ** 2
        rms = float(np.sqrt(np.mean(np.square(window))))
        pump_energy = float(np.mean(spectrum[pump_mask])) if np.any(pump_mask) else 0.0
        high_energy = float(np.mean(spectrum[high_mask])) if np.any(high_mask) else 0.0
        center_seconds = (start + window.size / 2) / sample_rate

        timestamps.append(center_seconds)
        rms_energies.append(rms)
        pump_band_energies.append(np.sqrt(pump_energy))
        high_band_energies.append(np.sqrt(high_energy))

    return (
        np.array(timestamps, dtype=np.float32),
        np.array(rms_energies, dtype=np.float32),
        np.array(pump_band_energies, dtype=np.float32),
        np.array(high_band_energies, dtype=np.float32),
    )


def build_pump_score(
    rms_energies: np.ndarray,
    pump_band_energies: np.ndarray,
    high_band_energies: np.ndarray,
) -> np.ndarray:
    """Score pump-like sound using band energy while down-weighting sharp noise."""
    if rms_energies.size == 0:
        return rms_energies

    rms_norm = rms_energies / max(float(np.percentile(rms_energies, 95)), 1e-6)
    pump_norm = pump_band_energies / max(float(np.percentile(pump_band_energies, 95)), 1e-6)
    high_norm = high_band_energies / max(float(np.percentile(high_band_energies, 95)), 1e-6)
    sharp_noise_penalty = np.clip(high_norm - pump_norm, 0.0, 1.0) * 0.25
    score = 0.35 * rms_norm + 0.65 * pump_norm - sharp_noise_penalty
    return np.clip(score, 0.0, None).astype(np.float32)


def smooth_energy(energies: np.ndarray, width: int = 5) -> np.ndarray:
    """Smooth energy values with a small moving average."""
    if energies.size == 0 or width <= 1:
        return energies
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(energies, kernel, mode="same")


def _true_runs(mask: Sequence[bool], min_frames: int) -> list[tuple[int, int]]:
    runs = []
    start = None
    for index, active in enumerate(mask):
        if active and start is None:
            start = index
        if (not active or index == len(mask) - 1) and start is not None:
            end = index if active and index == len(mask) - 1 else index - 1
            if end - start + 1 >= min_frames:
                runs.append((start, end))
            start = None
    return runs


def _fill_short_false_gaps(mask: np.ndarray, max_gap_frames: int) -> np.ndarray:
    if max_gap_frames <= 0 or mask.size == 0:
        return mask

    filled = mask.copy()
    index = 0
    while index < filled.size:
        if filled[index]:
            index += 1
            continue

        gap_start = index
        while index < filled.size and not filled[index]:
            index += 1
        gap_end = index - 1
        gap_len = gap_end - gap_start + 1
        has_active_before = gap_start > 0 and filled[gap_start - 1]
        has_active_after = index < filled.size and filled[index]
        if has_active_before and has_active_after and gap_len <= max_gap_frames:
            filled[gap_start : gap_end + 1] = True

    return filled


def _rolling_stability(values: np.ndarray, width: int = 15) -> np.ndarray:
    if values.size == 0:
        return values

    stability = np.zeros(values.size, dtype=np.float32)
    half_width = max(1, width // 2)
    for index in range(values.size):
        start = max(0, index - half_width)
        stop = min(values.size, index + half_width + 1)
        window = values[start:stop]
        mean = float(np.mean(window))
        std = float(np.std(window))
        stability[index] = 1.0 - min(std / max(mean, 1e-6), 1.0)
    return stability


def _refine_pump_start(
    start_index: int,
    stop_index: int,
    smoothed: np.ndarray,
    stability: np.ndarray,
    baseline: float,
    dynamic_range: float,
    hop_seconds: float,
) -> tuple[int, bool]:
    duration_seconds = (stop_index - start_index) * hop_seconds
    if duration_seconds < 38.0:
        return start_index, False

    max_shift_frames = max(1, int(round(8.0 / hop_seconds)))
    sustained_frames = max(1, int(round(2.5 / hop_seconds)))
    search_stop = min(stop_index - sustained_frames + 1, start_index + max_shift_frames)
    if search_stop <= start_index:
        return start_index, False

    strong_threshold = baseline + dynamic_range * 0.30
    steady_threshold = 0.58
    for candidate_start in range(start_index, search_stop + 1):
        window = smoothed[candidate_start : candidate_start + sustained_frames]
        steady_window = stability[candidate_start : candidate_start + sustained_frames]
        strong_ratio = float(np.mean(window >= strong_threshold))
        steady_ratio = float(np.mean(steady_window >= steady_threshold))
        if strong_ratio >= 0.75 and steady_ratio >= 0.55:
            shifted_seconds = (candidate_start - start_index) * hop_seconds
            if shifted_seconds >= 1.5:
                return candidate_start, True
            return start_index, False

    return start_index, False


def _score_candidate_run(
    start_index: int,
    stop_index: int,
    timestamps: np.ndarray,
    energies: np.ndarray,
    baseline: float,
) -> float:
    start_time = float(timestamps[start_index])
    stop_time = float(timestamps[stop_index])
    duration = max(0.0, stop_time - start_time)
    mean_energy = float(np.mean(energies[start_index : stop_index + 1]))
    contrast = max(0.0, mean_energy - baseline) / max(mean_energy, 1e-6)

    ideal_duration = 32.0
    if PREFERRED_MIN_SHOT_SECONDS <= duration <= PREFERRED_MAX_SHOT_SECONDS:
        duration_score = 1.0 - min(abs(duration - ideal_duration), 15.0) / 30.0
    else:
        nearest = (
            PREFERRED_MIN_SHOT_SECONDS
            if duration < PREFERRED_MIN_SHOT_SECONDS
            else PREFERRED_MAX_SHOT_SECONDS
        )
        duration_score = max(0.0, 0.5 - abs(duration - nearest) / nearest)

    duration_ratio = min(duration / PREFERRED_MAX_SHOT_SECONDS, 1.0)
    early_score = max(0.0, 1.0 - start_time / max(float(timestamps[-1]), 1.0))

    # The MVP cares most about total machine run time. Prefer plausible full-shot
    # windows over short loud fragments, with energy as a tie-breaker.
    return duration_score * 4.0 + duration_ratio * 1.25 + contrast * 0.5 + early_score * 0.2


def detect_machine_window(
    timestamps: np.ndarray,
    energies: np.ndarray,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
) -> tuple[float | None, float | None, float, float, bool, str | None, list[str]]:
    """Detect the sustained high-energy machine/pump window."""
    warnings: list[str] = []
    if timestamps.size == 0 or energies.size == 0:
        return None, None, 0.0, 0.0, True, "No audio samples were available.", ["No audio samples were available."]

    smoothed = smooth_energy(energies)
    stability = _rolling_stability(smoothed)
    max_energy = float(np.max(smoothed))
    baseline_count = max(3, min(int(round(2.0 / hop_seconds)), smoothed.size // 5 or 1))
    baseline = float(np.median(smoothed[:baseline_count]))
    dynamic_range = max_energy - baseline

    if dynamic_range <= 1e-4:
        return None, None, 0.0, 0.0, True, "Audio energy did not change enough to detect machine timing.", ["Audio energy did not change enough to detect machine timing."]

    min_frames = max(1, int(round(min_duration_seconds / hop_seconds)))
    max_gap_frames = max(1, int(round(1.5 / hop_seconds)))
    threshold_ratios = sorted({threshold_ratio, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35})

    candidates: list[tuple[float, int, int, float]] = []
    for candidate_ratio in threshold_ratios:
        threshold = baseline + dynamic_range * candidate_ratio
        active_mask = _fill_short_false_gaps(smoothed >= threshold, max_gap_frames)
        for start_index, stop_index in _true_runs(active_mask.tolist(), min_frames):
            score = _score_candidate_run(
                start_index,
                stop_index,
                timestamps,
                smoothed,
                baseline,
            )
            candidates.append((score, start_index, stop_index, candidate_ratio))

    if not candidates:
        return None, None, 0.0, 0.0, True, "No sustained machine-sound window was detected.", ["No sustained machine-sound window was detected."]

    _, start_index, stop_index, selected_ratio = max(candidates, key=lambda item: item[0])
    refined_start_index, prep_noise_shifted = _refine_pump_start(
        start_index,
        stop_index,
        smoothed,
        stability,
        baseline,
        dynamic_range,
        hop_seconds,
    )
    start_index = refined_start_index
    start_time = float(timestamps[start_index])
    stop_time = float(timestamps[stop_index])
    selected_mean = float(np.mean(smoothed[start_index : stop_index + 1]))
    confidence = min(1.0, max(0.0, selected_mean - baseline) / max(selected_mean, 1e-6))
    stability_mean = float(np.mean(stability[start_index : stop_index + 1]))

    if prep_noise_shifted:
        warnings.append("Ignored likely prep noise before sustained pump sound.")
    if selected_ratio <= 0.1:
        warnings.append("Audio threshold was low; ask the user to confirm timing.")
    if stability_mean < 0.45:
        warnings.append("Pump sound was not very stable; ask the user to confirm timing.")
    if confidence < 0.35:
        warnings.append("Audio confidence is low; ask the user to confirm timing.")
    if stop_time <= start_time:
        warnings.append("Detected stop time was not after start time.")
        return (
            None,
            None,
            confidence,
            confidence,
            True,
            "Detected stop time was not after start time.",
            warnings,
        )

    requires_manual_confirmation = confidence < MANUAL_CONFIRMATION_CONFIDENCE_THRESHOLD
    confirmation_reason = (
        "Audio confidence is low; user should confirm or adjust timing."
        if requires_manual_confirmation
        else None
    )

    return (
        round(start_time, 2),
        round(stop_time, 2),
        round(confidence, 2),
        round(confidence, 2),
        requires_manual_confirmation,
        confirmation_reason,
        warnings,
    )


def analyze_wav(wav_path: Path) -> AudioTimingResult:
    """Analyze one WAV file and return machine timing."""
    samples, sample_rate = read_wav_mono(wav_path)
    timestamps, rms, pump_band, high_band = compute_window_features(samples, sample_rate)
    pump_score = build_pump_score(rms, pump_band, high_band)
    (
        start,
        stop,
        start_conf,
        stop_conf,
        requires_manual_confirmation,
        confirmation_reason,
        warnings,
    ) = detect_machine_window(
        timestamps,
        pump_score,
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
        requires_manual_confirmation=requires_manual_confirmation,
        confirmation_reason=confirmation_reason,
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
            requires_manual_confirmation=result.requires_manual_confirmation,
            confirmation_reason=result.confirmation_reason,
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
