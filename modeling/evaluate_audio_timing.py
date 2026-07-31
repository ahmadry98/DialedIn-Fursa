#!/usr/bin/env python3
"""Evaluate audio timing against manual CSV labels."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import audio_analysis
import visual_analysis

NOISY_AUDIO_QUALITIES = {"talking", "noisy", "background_noise", "music"}


@dataclass(frozen=True)
class EvaluationRow:
    video_id: str
    manual_start: float
    manual_stop: float
    audio_quality: str
    detected_start: float | None
    detected_stop: float | None
    detected_total: float | None
    start_error: float | None
    stop_error: float | None
    total_error: float | None
    confidence: float
    requires_manual_confirmation: bool
    visual_fallback_recommended: bool
    confirmation_reason: str | None
    warnings: list[str]

    @property
    def is_noisy(self) -> bool:
        return self.audio_quality.strip().lower() in NOISY_AUDIO_QUALITIES


def load_labels(labels_path: Path) -> dict[str, dict[str, str]]:
    with labels_path.open(encoding="utf-8", newline="") as labels_file:
        return {row["video_id"]: row for row in csv.DictReader(labels_file)}


def _manual_stop(row: dict[str, str]) -> float:
    if row.get("machine_stop_time"):
        return float(row["machine_stop_time"])
    return float(row["flow_end_time"])


def evaluate_video(video_path: Path, label: dict[str, str]) -> EvaluationRow:
    manual_start = float(label["machine_start_time"])
    manual_stop = _manual_stop(label)
    manual_total = manual_stop - manual_start
    audio_quality = label.get("audio_quality", "").strip()
    result = audio_analysis.analyze_media(video_path)

    visual_fallback_recommended = visual_analysis.should_try_visual_fallback(
        result.requires_manual_confirmation,
        audio_quality,
    )

    if result.machine_start_time is None or result.machine_stop_time is None:
        return EvaluationRow(
            video_id=video_path.stem,
            manual_start=manual_start,
            manual_stop=manual_stop,
            audio_quality=audio_quality,
            detected_start=None,
            detected_stop=None,
            detected_total=None,
            start_error=None,
            stop_error=None,
            total_error=None,
            confidence=result.start_confidence,
            requires_manual_confirmation=True,
            visual_fallback_recommended=True,
            confirmation_reason=result.confirmation_reason,
            warnings=result.warnings,
        )

    detected_total = result.total_shot_seconds
    assert detected_total is not None
    return EvaluationRow(
        video_id=video_path.stem,
        manual_start=manual_start,
        manual_stop=manual_stop,
        audio_quality=audio_quality,
        detected_start=result.machine_start_time,
        detected_stop=result.machine_stop_time,
        detected_total=detected_total,
        start_error=round(result.machine_start_time - manual_start, 2),
        stop_error=round(result.machine_stop_time - manual_stop, 2),
        total_error=round(detected_total - manual_total, 2),
        confidence=result.start_confidence,
        requires_manual_confirmation=result.requires_manual_confirmation,
        visual_fallback_recommended=visual_fallback_recommended,
        confirmation_reason=result.confirmation_reason,
        warnings=result.warnings,
    )


def evaluate_dataset(video_dir: Path, labels_path: Path) -> list[EvaluationRow]:
    labels = load_labels(labels_path)
    rows = []
    for video_path in sorted(video_dir.glob("*.mp4")):
        label = labels.get(video_path.stem)
        if label is None:
            continue
        rows.append(evaluate_video(video_path, label))
    return rows


def format_table(rows: list[EvaluationRow]) -> str:
    header = (
        "video_id | audio_quality | manual_start | manual_stop | detected_start | "
        "detected_stop | start_err | stop_err | total_err | confidence | confirm | visual_fallback | warnings"
    )
    separator = "--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---"
    lines = [header, separator]
    for row in rows:
        warning_text = "; ".join(row.warnings)
        audio_quality = row.audio_quality or "clean"
        lines.append(
            f"{row.video_id} | "
            f"{audio_quality} | "
            f"{row.manual_start:.2f} | "
            f"{row.manual_stop:.2f} | "
            f"{_fmt(row.detected_start)} | "
            f"{_fmt(row.detected_stop)} | "
            f"{_fmt(row.start_error, signed=True)} | "
            f"{_fmt(row.stop_error, signed=True)} | "
            f"{_fmt(row.total_error, signed=True)} | "
            f"{row.confidence:.2f} | "
            f"{_yes_no(row.requires_manual_confirmation)} | "
            f"{_yes_no(row.visual_fallback_recommended)} | "
            f"{warning_text}"
        )
    return "\n".join(lines)


def summarize(rows: list[EvaluationRow], label: str = "All videos") -> str:
    if not rows:
        return f"{label}: no videos."

    detected = [row for row in rows if row.total_error is not None]
    if not detected:
        return f"{label}: no videos produced a detection."

    avg_start = sum(abs(row.start_error or 0) for row in detected) / len(detected)
    avg_stop = sum(abs(row.stop_error or 0) for row in detected) / len(detected)
    avg_total = sum(abs(row.total_error or 0) for row in detected) / len(detected)
    within_total = sum(1 for row in detected if abs(row.total_error or 0) <= 3.0)
    low_confidence = sum(1 for row in detected if row.confidence < 0.35)
    manual_confirm = sum(1 for row in rows if row.requires_manual_confirmation)
    visual_fallback = sum(1 for row in rows if row.visual_fallback_recommended)
    return (
        f"{label}: detected {len(detected)}/{len(rows)} videos. "
        f"Average absolute start error: {avg_start:.2f}s. "
        f"Average absolute stop error: {avg_stop:.2f}s. "
        f"Average absolute total-time error: {avg_total:.2f}s. "
        f"Within 3s total-time target: {within_total}/{len(rows)}. "
        f"Low confidence detections: {low_confidence}/{len(detected)}. "
        f"Manual confirmation needed: {manual_confirm}/{len(rows)}. "
        f"Visual fallback recommended: {visual_fallback}/{len(rows)}."
    )


def summarize_groups(rows: list[EvaluationRow]) -> str:
    clean_rows = [row for row in rows if not row.is_noisy]
    noisy_rows = [row for row in rows if row.is_noisy]
    lines = [
        summarize(rows, "All videos"),
        summarize(clean_rows, "Clean videos only"),
        summarize(noisy_rows, "Noisy/talking videos only"),
    ]
    return "\n".join(lines)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _fmt(value: float | None, signed: bool = False) -> str:
    if value is None:
        return ""
    if signed:
        return f"{value:+.2f}"
    return f"{value:.2f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate audio timing labels.")
    parser.add_argument("--video-dir", type=Path, default=Path("data/raw-videos"))
    parser.add_argument("--labels", type=Path, default=Path("data/labels/shot_labels.csv"))
    parser.add_argument("--output", type=Path, help="Optional Markdown report path.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = evaluate_dataset(args.video_dir, args.labels)
    report = (
        "# Audio Timing Evaluation\n\n"
        + summarize_groups(rows)
        + "\n\n"
        + format_table(rows)
        + "\n"
    )
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
