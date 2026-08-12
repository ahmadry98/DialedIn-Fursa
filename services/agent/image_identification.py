"""Photo-based machine/grinder identification through Bedrock Claude."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from services.espresso_mcp import grinder_profiles, machine_profiles

SYSTEM_PROMPT = """You identify espresso equipment from a user photo.
Return ONLY valid JSON. No markdown. No commentary.
Classify the actual object in the image as either an espresso machine or a coffee grinder.
The user may have attached the wrong photo for the current chat step; do not force the requested type if the object is clearly the other type.
Prefer a candidate from the provided known equipment list when the visual evidence matches it.
Use visible evidence: brand/logo text, button layout, knob placement, group head, steam wand, built-in grinder, hopper, burr grinder body, and model label.
If the model is not clearly identifiable, return null or a brand-only name with confidence "low".
For Varia grinders, valid model names include Varia VS3, Varia VS4, and Varia VS6. Do not return Varia VS2. If you only know the brand, return "Varia" with confidence "low".
If the image is unclear, return null for name and confidence "low".
Do not invent technical specifications.
Return this exact shape:
{
  "gear_type": "machine" | "grinder",
  "name": string | null,
  "confidence": "low" | "medium" | "high",
  "reason": string
}
"""


def identify_gear_image_with_bedrock(
    *,
    image_base64: str,
    media_type: str,
    gear_type: str,
    model_id: str,
    region: str,
) -> dict[str, Any]:
    """Ask Claude on Bedrock for a machine/grinder model guess from an image."""
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use Bedrock image identification.") from error

    image_bytes = base64.b64decode(strip_data_url_prefix(image_base64))
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id.removeprefix("bedrock/"),
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": build_user_prompt(gear_type)},
                    {
                        "image": {
                            "format": media_format(media_type),
                            "source": {"bytes": image_bytes},
                        }
                    },
                ],
            }
        ],
        inferenceConfig={"temperature": 0.0, "maxTokens": 500},
    )
    return sanitize_guess(parse_json_object(bedrock_response_text(response)), fallback_type=gear_type)


def build_user_prompt(gear_type: str) -> str:
    candidates = known_equipment_candidates()
    candidate_text = json.dumps(candidates, ensure_ascii=False)
    return (
        f"The chat currently expects a {gear_type}, but classify the actual object in the image. "
        "Compare the image against the known equipment candidates below. "
        "If one candidate is visually plausible, return that exact candidate name. "
        "If the image only proves a brand, return the brand with low confidence. "
        "If no candidate matches clearly, return null with low confidence. "
        "Return only the JSON object.\n\n"
        f"Known equipment candidates: {candidate_text}"
    )


def known_equipment_candidates(limit: int = 80) -> dict[str, list[str]]:
    machines = []
    for profile in machine_profiles.list_machine_profiles():
        name = profile.get("machine_name")
        if name and name != machine_profiles.GENERIC_PROFILE_NAME:
            aliases = [alias for alias in profile.get("aliases", []) if isinstance(alias, str)]
            machines.append(_candidate_label(str(name), aliases))

    grinders = []
    for profile in grinder_profiles.list_grinder_profiles():
        name = profile.get("grinder_name")
        if name and name != grinder_profiles.GENERIC_GRINDER_NAME:
            aliases = [alias for alias in profile.get("aliases", []) if isinstance(alias, str)]
            grinders.append(_candidate_label(str(name), aliases))

    return {
        "machines": sorted(machines, key=str.lower)[:limit],
        "grinders": sorted(grinders, key=str.lower)[:limit],
    }


def _candidate_label(name: str, aliases: list[str]) -> str:
    useful_aliases = [alias for alias in aliases[:3] if alias.lower() != name.lower()]
    if not useful_aliases:
        return name
    return f"{name} (aliases: {', '.join(useful_aliases)})"


def sanitize_guess(data: dict[str, Any], *, fallback_type: str) -> dict[str, Any]:
    gear_type = str(data.get("gear_type") or fallback_type).lower()
    if gear_type not in {"machine", "grinder"}:
        gear_type = fallback_type
    confidence = str(data.get("confidence") or "low").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    name = data.get("name")
    return {
        "gear_type": gear_type,
        "name": str(name).strip() if name else None,
        "confidence": confidence,
        "reason": str(data.get("reason") or "Image model guess; confirm before using."),
    }


def strip_data_url_prefix(value: str) -> str:
    if "," in value and value.lstrip().startswith("data:"):
        return value.split(",", 1)[1]
    return value


def media_format(media_type: str) -> str:
    lowered = media_type.lower()
    if "png" in lowered:
        return "png"
    if "webp" in lowered:
        return "webp"
    return "jpeg"


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
        raise ValueError("Image identification must return a JSON object")
    return parsed


def bedrock_response_text(response: dict[str, Any]) -> str:
    content = response.get("output", {}).get("message", {}).get("content", [])
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))
