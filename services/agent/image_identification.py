"""Photo-based machine/grinder identification through Bedrock Claude."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

SYSTEM_PROMPT = """You identify espresso equipment from a user photo.
Return ONLY valid JSON. No markdown. No commentary.
Classify the actual object in the image as either an espresso machine or a coffee grinder.
The user may have attached the wrong photo for the current chat step; do not force the requested type if the object is clearly the other type.
If you can only see a brand/company logo but not the exact model, return the brand as name with confidence "low" and explain that the exact model is needed.
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
                    {"text": f"The chat currently expects a {gear_type}, but classify the actual object in the image. Return only the JSON object."},
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
