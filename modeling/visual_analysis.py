#!/usr/bin/env python3
"""Visual timing fallback interface for future espresso video analysis.

The MVP is audio-first. This module gives the app a structured place to ask for
visual timing help when audio confidence is low, without pretending that visual
detection is implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VisualTimingHint:
    source_path: str
    available: bool
    method: str
    machine_start_time: float | None
    machine_stop_time: float | None
    first_flow_time: float | None
    flow_end_time: float | None
    confidence: float
    warnings: list[str]


def analyze_visual_timing(video_path: Path) -> VisualTimingHint:
    """Return a structured visual fallback placeholder for noisy audio cases.

    Future implementations can inspect frames for button press, machine light,
    visible first flow, and visible flow end. For now, the caller should use this
    result to trigger manual timestamp confirmation in the UI.
    """
    return VisualTimingHint(
        source_path=str(video_path),
        available=False,
        method="not_implemented",
        machine_start_time=None,
        machine_stop_time=None,
        first_flow_time=None,
        flow_end_time=None,
        confidence=0.0,
        warnings=[
            "Visual timing fallback is not implemented yet; ask the user to confirm timing."
        ],
    )


def should_try_visual_fallback(
    requires_manual_confirmation: bool,
    audio_quality: str = "",
) -> bool:
    """Return true when audio timing is unreliable enough to need visual help."""
    noisy_labels = {"talking", "noisy", "background_noise", "music"}
    return requires_manual_confirmation or audio_quality.strip().lower() in noisy_labels
