"""Agent service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional for deployed envs.
    load_dotenv = None


def load_local_env() -> None:
    if load_dotenv is None:
        return

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    load_dotenv(PROJECT_ROOT / "services" / "agent" / ".env", override=True)
    load_dotenv(PROJECT_ROOT / "services" / "espresso_mcp" / ".env", override=True)


@dataclass(frozen=True)
class AgentSettings:
    app_name: str = "DialedIN Agent"
    local_upload_dir: Path = Path("data/raw-videos")
    require_confirm_below_confidence: float = 0.35
    profile_research_autorun: bool = False
    profile_research_autorun_limit: int = 1
    chat_llm_extraction_enabled: bool = False
    chat_llm_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    aws_region: str = "us-east-1"


def get_settings() -> AgentSettings:
    load_local_env()

    upload_dir = Path(os.getenv("DIALEDIN_LOCAL_UPLOAD_DIR", "data/raw-videos"))
    confidence = float(os.getenv("DIALEDIN_CONFIRM_CONFIDENCE", "0.35"))
    autorun = os.getenv("PROFILE_RESEARCH_AUTORUN", "false").lower() in {"1", "true", "yes", "on"}
    autorun_limit = int(os.getenv("PROFILE_RESEARCH_AUTORUN_LIMIT", "1"))
    chat_llm_enabled = os.getenv("CHAT_LLM_EXTRACTION", "false").lower() in {"1", "true", "yes", "on"}
    chat_llm_model = os.getenv("CHAT_LLM_MODEL") or os.getenv("MODEL") or "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    return AgentSettings(
        local_upload_dir=upload_dir,
        require_confirm_below_confidence=confidence,
        profile_research_autorun=autorun,
        profile_research_autorun_limit=max(1, autorun_limit),
        chat_llm_extraction_enabled=chat_llm_enabled,
        chat_llm_model_id=chat_llm_model.removeprefix("bedrock/"),
        aws_region=region,
    )
