"""Agent service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentSettings:
    app_name: str = "DialedIN Agent"
    local_upload_dir: Path = Path("data/raw-videos")
    require_confirm_below_confidence: float = 0.35


def get_settings() -> AgentSettings:
    upload_dir = Path(os.getenv("DIALEDIN_LOCAL_UPLOAD_DIR", "data/raw-videos"))
    confidence = float(os.getenv("DIALEDIN_CONFIRM_CONFIDENCE", "0.35"))
    return AgentSettings(local_upload_dir=upload_dir, require_confirm_below_confidence=confidence)
