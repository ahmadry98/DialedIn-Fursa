#!/usr/bin/env python3
"""Extract timestamped frames from espresso shot videos.

The output format is designed for later dataset building:

    data/frames/shot_001/shot_001_t0000.00.jpg
    data/frames/shot_001/shot_001_t0000.50.jpg

By default the script refuses to write into a non-empty output directory. Use
--overwrite when you intentionally want to regenerate frames.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi"}
DEFAULT_OUTPUT_ROOT = Path("data/frames")
DEFAULT_FPS = 2.0


@dataclass(frozen=True)
class ExtractionResult:
    video_id: str
    source_video: str
    output_dir: str
    fps_requested: float
    source_fps: float
    source_frame_count: int
    source_duration_seconds: float
    frames_written: int


def discover_videos(input_path: Path) -> list[Path]:
    """Return one or more video paths from a file or directory."""
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
            raise ValueError(f"Unsupported video file: {input_path}")
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    videos = [
        path
        for path in sorted(input_path.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES
    ]
    if not videos:
        raise ValueError(f"No supported videos found in: {input_path}")
    return videos


def frame_filename(video_id: str, timestamp_seconds: float) -> str:
    """Build a stable frame filename that keeps the timestamp visible."""
    return f"{video_id}_t{timestamp_seconds:07.2f}.jpg"


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    """Create an output directory, refusing to clobber existing frames by default."""
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"Output directory already contains files: {output_dir}. "
                "Pass --overwrite to regenerate frames."
            )
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as error:  # pragma: no cover - exercised by real CLI use.
        raise RuntimeError(
            "OpenCV is required for frame extraction. Install it with "
            "`python -m pip install opencv-python`."
        ) from error
    return cv2


def extract_frames(
    video_path: Path,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    fps: float = DEFAULT_FPS,
    overwrite: bool = False,
) -> ExtractionResult:
    """Extract frames from one video at the requested FPS."""
    if fps <= 0:
        raise ValueError("fps must be greater than 0")

    video_path = video_path.resolve()
    video_id = video_path.stem
    output_dir = output_root / video_id
    prepare_output_dir(output_dir, overwrite)

    cv2 = _import_cv2()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if source_fps <= 0:
        capture.release()
        raise ValueError(f"Could not determine FPS for video: {video_path}")

    duration_seconds = source_frame_count / source_fps if source_frame_count else 0.0
    interval_seconds = 1.0 / fps
    next_timestamp = 0.0
    frames_written = 0

    while True:
        capture.set(cv2.CAP_PROP_POS_MSEC, next_timestamp * 1000.0)
        ok, frame = capture.read()
        if not ok:
            break

        output_path = output_dir / frame_filename(video_id, next_timestamp)
        if not cv2.imwrite(str(output_path), frame):
            capture.release()
            raise IOError(f"Could not write frame: {output_path}")

        frames_written += 1
        next_timestamp = round(next_timestamp + interval_seconds, 6)
        if duration_seconds and next_timestamp > duration_seconds:
            break

    capture.release()

    result = ExtractionResult(
        video_id=video_id,
        source_video=str(video_path),
        output_dir=str(output_dir),
        fps_requested=fps,
        source_fps=source_fps,
        source_frame_count=source_frame_count,
        source_duration_seconds=round(duration_seconds, 3),
        frames_written=frames_written,
    )

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(asdict(result), indent=2) + "\n")
    return result


def extract_many(
    videos: Iterable[Path],
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    fps: float = DEFAULT_FPS,
    overwrite: bool = False,
) -> list[ExtractionResult]:
    """Extract frames from multiple videos."""
    return [
        extract_frames(video, output_root=output_root, fps=fps, overwrite=overwrite)
        for video in videos
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract timestamped frames from espresso shot videos."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Video file or directory containing videos.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory for extracted frame folders. Defaults to data/frames.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=DEFAULT_FPS,
        help="Frames per second to extract. Defaults to 2.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing non-empty output directory.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    videos = discover_videos(args.input_path)
    results = extract_many(
        videos,
        output_root=args.output_root,
        fps=args.fps,
        overwrite=args.overwrite,
    )
    for result in results:
        print(
            f"{result.video_id}: wrote {result.frames_written} frames "
            f"to {result.output_dir}"
        )


if __name__ == "__main__":
    main()
