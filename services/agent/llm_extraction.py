"""LLM-assisted shot-context extraction for the chat coach."""

from __future__ import annotations

import json
import re
from typing import Any

from services.agent.schemas import ShotContext

EXTRACTABLE_FIELDS = {
    "machine",
    "grinder",
    "uses_built_in_grinder",
    "dose_g",
    "yield_g",
    "grind_setting",
    "roast_level",
    "taste",
    "video_s3_key",
    "total_shot_seconds",
}

SYSTEM_PROMPT = """You extract espresso shot setup details from user chat.
Return ONLY valid JSON. No markdown. No commentary.
Only include fields that are clearly stated or strongly implied by the latest user message.
Do not invent machine specs, grinder specs, shot timing, or recommendations.
Use null for fields you cannot infer.
Allowed JSON fields: machine, grinder, uses_built_in_grinder, dose_g, yield_g, grind_setting, roast_level, taste, video_s3_key, total_shot_seconds.
Roast level must be one of: light, medium, dark, or null.
If the user says built-in grinder, set uses_built_in_grinder true.
"""


def extract_context_with_bedrock(
    *,
    message: str,
    context: ShotContext,
    model_id: str,
    region: str,
) -> dict[str, Any]:
    """Ask Bedrock Claude to extract structured context from one user message."""
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use Bedrock chat extraction.") from error

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id.removeprefix("bedrock/"),
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": build_extraction_prompt(message=message, context=context)}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 700},
    )
    return sanitize_extraction(parse_json_object(bedrock_response_text(response)))


def build_extraction_prompt(*, message: str, context: ShotContext) -> str:
    return "\n\n".join(
        [
            "Current known shot context:",
            json.dumps(context.model_dump(), indent=2),
            "Latest user message:",
            message,
            "Return a JSON object with only newly observed or corrected fields.",
        ]
    )


def merge_extracted_context(context: ShotContext, extracted: dict[str, Any]) -> ShotContext:
    """Merge extracted fields into context without overwriting useful data with null."""
    updates: dict[str, Any] = {}
    for field, value in extracted.items():
        if field not in EXTRACTABLE_FIELDS or value in (None, ""):
            continue
        updates[field] = value

    if updates.get("uses_built_in_grinder") and context.machine and not updates.get("grinder") and not context.grinder:
        updates["grinder"] = f"{context.machine} built-in grinder"

    merged = context.model_copy(update=updates)
    if merged.uses_built_in_grinder and merged.machine and not merged.grinder:
        merged.grinder = f"{merged.machine} built-in grinder"
    if merged.total_shot_seconds is not None and merged.timing_confidence is None:
        merged.timing_confidence = 1
        merged.requires_manual_confirmation = False
    return merged


def sanitize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for field in EXTRACTABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value in (None, ""):
            cleaned[field] = None
        elif field in {"dose_g", "yield_g", "total_shot_seconds"}:
            try:
                cleaned[field] = float(value)
            except (TypeError, ValueError):
                cleaned[field] = None
        elif field == "uses_built_in_grinder":
            cleaned[field] = bool(value)
        else:
            cleaned[field] = str(value).strip()
    roast = cleaned.get("roast_level")
    if isinstance(roast, str) and roast.lower() not in {"light", "medium", "dark"}:
        cleaned["roast_level"] = None
    elif isinstance(roast, str):
        cleaned["roast_level"] = roast.lower()
    return cleaned


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM extraction must return a JSON object")
    return parsed


def bedrock_response_text(response: dict[str, Any]) -> str:
    content = response.get("output", {}).get("message", {}).get("content", [])
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))
