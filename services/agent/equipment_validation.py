"""LLM validation for user-entered espresso equipment names."""

from __future__ import annotations

import json
import re
from typing import Any

from services.espresso_mcp import grinder_profiles, machine_profiles, profile_candidates

SYSTEM_PROMPT = """You validate espresso equipment names.
Return ONLY valid JSON. No markdown. No commentary.
Decide whether the text is plausibly an actual espresso machine or coffee grinder model name.
Reject random words, gibberish, greetings, dimensions, taste notes, generic chat, and brand/company names without a specific model.
Accept known or plausible brand+model names, even if the exact model may need later research.
If the text is only a brand, set is_equipment false and explain that the exact model is needed.
If the text appears to be a typo of a real espresso machine or grinder model, provide corrected_name.
Allowed confidence values: high, medium, low.
JSON schema: {"is_equipment": boolean, "confidence": "high|medium|low", "corrected_name": string|null, "reason": string}
"""


def validate_equipment_name(
    *,
    name: str | None,
    gear_type: str,
    model_id: str,
    region: str,
) -> dict[str, Any]:
    """Return whether a user-entered machine/grinder name looks real."""
    cleaned = _clean_name(name)
    if gear_type not in {"machine", "grinder"}:
        raise ValueError("gear_type must be 'machine' or 'grinder'")
    if not cleaned:
        return _invalid("No equipment name was provided.")

    known_name = _known_profile_name(cleaned, gear_type)
    if known_name:
        return {"is_equipment": True, "confidence": "high", "corrected_name": known_name, "reason": "Matched a curated profile."}

    invalid_known_model = _invalid_known_brand_model(cleaned, gear_type)
    if invalid_known_model:
        return _invalid(invalid_known_model)

    if _too_weak_for_llm_validation(cleaned):
        return _invalid("This does not look like a machine or grinder model name.")

    try:
        return _validate_with_bedrock(name=cleaned, gear_type=gear_type, model_id=model_id, region=region)
    except Exception as error:  # pragma: no cover - external model failures should not break chat.
        if profile_candidates.is_plausible_gear_name(gear_type, cleaned):
            return {
                "is_equipment": True,
                "confidence": "low",
                "corrected_name": cleaned,
                "reason": f"Validation unavailable; keeping plausible unknown name for later research: {type(error).__name__}.",
            }
        return _invalid(f"Validation unavailable and the name was too weak to keep: {type(error).__name__}.")


def _validate_with_bedrock(*, name: str, gear_type: str, model_id: str, region: str) -> dict[str, Any]:
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use Bedrock equipment validation.") from error

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id.removeprefix("bedrock/"),
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": _build_prompt(name=name, gear_type=gear_type)}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 220},
    )
    return sanitize_validation(parse_json_object(_bedrock_response_text(response)), fallback_name=name)


def _build_prompt(*, name: str, gear_type: str) -> str:
    label = "espresso machine" if gear_type == "machine" else "coffee grinder"
    examples = (
        "Examples: 'Rancilio Silvia', 'Lelit Bianca V3', and 'Breville Bambino Plus' are machine models; "
        "'Rancilio', 'Lelit', and 'Breville' alone are only brands."
        if gear_type == "machine"
        else "Examples: 'Varia VS3', 'DF54', and 'Eureka Mignon Specialita' are grinder models; "
        "'Varia', 'Eureka', and 'Niche' alone are only brands."
    )
    return (
        f"User entered this as a {label} name: {name!r}.\n"
        f"{examples}\n"
        "Is this an actual or plausible specific equipment model, not just a brand/company name? Return JSON only."
    )


def sanitize_validation(data: dict[str, Any], fallback_name: str = "") -> dict[str, Any]:
    is_equipment = bool(data.get("is_equipment"))
    confidence = str(data.get("confidence") or "low").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    corrected = data.get("corrected_name")
    corrected_name = str(corrected).strip() if corrected not in (None, "") else None
    reason = str(data.get("reason") or "No reason provided.").strip()
    if is_equipment and not corrected_name:
        corrected_name = fallback_name or None
    return {
        "is_equipment": is_equipment,
        "confidence": confidence,
        "corrected_name": corrected_name,
        "reason": reason,
    }


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
        raise ValueError("Equipment validation must return a JSON object")
    return parsed


def _bedrock_response_text(response: dict[str, Any]) -> str:
    content = response.get("output", {}).get("message", {}).get("content", [])
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))


def _too_weak_for_llm_validation(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    compact = normalized.replace(" ", "")
    if len(compact) < 3 or len(compact) > 80:
        return True
    if not any(character.isalpha() for character in compact):
        return True
    if re.fullmatch(r"[a-z]?\d+", compact):
        return True
    return False


def _invalid_known_brand_model(name: str, gear_type: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    if gear_type == "grinder":
        varia_match = re.fullmatch(r"(?:varia\s+)?v?s(\d+)", normalized) or re.fullmatch(r"varia\s+v(\d+)", normalized)
        if varia_match and varia_match.group(1) not in {"3", "4", "6"}:
            return "Varia grinder models supported here are VS3, VS4, and VS6; VS2 is not a known Varia grinder model."
        if normalized == "varia":
            return "Varia is the brand. Please enter the exact grinder model, like Varia VS3, Varia VS4, or Varia VS6."
    return None


def _known_profile_name(name: str, gear_type: str) -> str | None:
    if gear_type == "machine":
        profile = machine_profiles.get_machine_profile(name)
        if profile.get("machine_name") != machine_profiles.GENERIC_PROFILE_NAME:
            return str(profile.get("machine_name"))
    else:
        profile = grinder_profiles.get_grinder_profile(name)
        if profile.get("grinder_name") != grinder_profiles.GENERIC_GRINDER_NAME:
            return str(profile.get("grinder_name"))
    return None


def _clean_name(name: str | None) -> str:
    return " ".join(str(name or "").strip().split())


def _invalid(reason: str) -> dict[str, Any]:
    return {"is_equipment": False, "confidence": "high", "corrected_name": None, "reason": reason}
