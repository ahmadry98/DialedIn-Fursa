"""Deterministic chat-state flow for the DialedIN coach.

This is intentionally lightweight for the MVP. It collects structured espresso
shot context from chat replies, then calls the existing analysis runner when the
required fields are available. LLM-based extraction can replace parts of this
module later without changing the analysis engine.
"""

from __future__ import annotations

import re
from typing import Any

from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatRequest, ChatResponse, ShotContext
from services.espresso_mcp import grinder_profiles, machine_profiles

FIELD_ORDER = ["machine", "grinder", "dose_g", "grind_setting", "roast_level", "taste", "timing"]
TASTE_WORDS = {"sour", "bitter", "balanced", "thin", "watery", "harsh", "dry", "sweet", "acidic"}
ROAST_LEVELS = {"light", "medium", "dark"}
VIDEO_PATTERN = re.compile(r"(?:data/[^\s]+|[^\s]+\.(?:mp4|mov|m4v|wav))", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def handle_chat(request: ChatRequest, analyze_callback) -> ChatResponse:
    """Update conversation state and analyze when the shot context is ready."""
    from services.agent import graph

    return graph.run_chat_graph(request, analyze_callback)


def sanitize_context(context: ShotContext) -> ShotContext:
    if context.machine and (is_small_talk(context.machine) or not looks_like_equipment_name(context.machine, "machine")):
        context.machine = None
    if context.grinder and (is_small_talk(context.grinder) or not looks_like_equipment_name(context.grinder, "grinder")):
        context.grinder = None
    if context.taste and is_small_talk(context.taste):
        context.taste = None
    if context.video_s3_key and _looks_like_image_file(context.video_s3_key):
        context.video_s3_key = None
    return context


def missing_chat_fields(context: ShotContext) -> list[str]:
    if context.pending_gear_type and context.pending_gear_name:
        return [f"confirm_{context.pending_gear_type}"]
    missing: list[str] = []
    if not context.machine:
        missing.append("machine")
    if not context.uses_built_in_grinder and not context.grinder:
        missing.append("grinder")
    if context.dose_g is None:
        missing.append("dose_g")
    if not context.grind_setting:
        missing.append("grind_setting")
    if not context.roast_level:
        missing.append("roast_level")
    if not context.taste:
        missing.append("taste")
    if not context.video_s3_key and context.total_shot_seconds is None:
        missing.append("timing")
    return missing


def canonical_gear_name(name: str, gear_type: str) -> str:
    cleaned = _clean_equipment_reply(name)
    if gear_type == "machine":
        profile = machine_profiles.get_machine_profile(cleaned)
        if profile.get("machine_name") != machine_profiles.GENERIC_PROFILE_NAME:
            return str(profile["machine_name"])
    elif gear_type == "grinder":
        profile = grinder_profiles.get_grinder_profile(cleaned)
        if profile.get("grinder_name") != grinder_profiles.GENERIC_GRINDER_NAME:
            return str(profile["grinder_name"])
    return cleaned


def apply_message_to_context(context: ShotContext, message: str, previous_missing: list[str]) -> None:
    text = message.strip()
    lowered = text.lower()

    if context.pending_gear_type and context.pending_gear_name:
        _apply_pending_gear_reply(context, text)
        return

    if is_small_talk(text):
        return

    if any(term in lowered for term in ["built in", "built-in", "builtin"]):
        context.uses_built_in_grinder = True
        if context.machine and not context.grinder:
            context.grinder = f"{context.machine} built-in grinder"

    video = VIDEO_PATTERN.search(text)
    if video:
        context.video_s3_key = video.group(0).rstrip(".,")

    if context.total_shot_seconds is None:
        seconds = _extract_seconds(text)
        if seconds is not None:
            context.total_shot_seconds = seconds
            context.timing_confidence = 1
            context.requires_manual_confirmation = False

    if context.dose_g is None:
        dose = _extract_labeled_number(text, ["dose", "in"])
        if dose is None and previous_missing[:1] == ["dose_g"]:
            dose = _first_number(text)
        if dose is not None:
            context.dose_g = dose

    if context.yield_g is None:
        yield_value = _extract_labeled_number(text, ["yield", "out", "output"])
        if yield_value is not None:
            context.yield_g = yield_value

    if not context.grind_setting:
        grind = _extract_grind_setting(text)
        if grind is None and previous_missing[:1] == ["grind_setting"]:
            grind = _first_tokenish_value(text)
        if grind:
            context.grind_setting = grind

    if not context.roast_level:
        roast = next((level for level in ROAST_LEVELS if re.search(rf"\b{level}\b", lowered)), None)
        if roast:
            context.roast_level = roast
        elif previous_missing[:1] == ["roast_level"] and lowered in ROAST_LEVELS:
            context.roast_level = lowered

    if not context.taste and not video and context.total_shot_seconds is None:
        taste_words = [word for word in TASTE_WORDS if re.search(rf"\b{word}\b", lowered)]
        if taste_words:
            context.taste = ", ".join(sorted(taste_words))
        elif previous_missing[:1] == ["taste"] and not _looks_like_skip(lowered):
            context.taste = text

    if not context.machine and previous_missing[:1] == ["machine"] and not is_greeting(text) and not _is_general_dial_in_request(text):
        machine = _clean_equipment_reply(text)
        if looks_like_equipment_name(machine, "machine"):
            context.machine = canonical_gear_name(machine, "machine")
            if context.uses_built_in_grinder and not context.grinder:
                context.grinder = f"{context.machine} built-in grinder"

    if not context.grinder and not context.uses_built_in_grinder and previous_missing[:1] == ["grinder"]:
        grinder = _clean_equipment_reply(text)
        if looks_like_equipment_name(grinder, "grinder"):
            context.grinder = canonical_gear_name(grinder, "grinder")


def _reply(response: str, context: ShotContext, missing: list[str]) -> ChatResponse:
    return ChatResponse(
        response=response,
        needs_shot_analysis=not missing,
        system_prompt="",
        shot_context=context,
        analysis_result=None,
        next_field=missing[0] if missing else None,
        missing_fields=missing,
    )


def question_for(field: str, context: ShotContext) -> str:
    questions = {
        "machine": "What espresso machine are you using? You can type the model name for now.",
        "grinder": "What grinder are you using? If it is built into the machine, say built-in.",
        "dose_g": "What dose are you using in grams? For example: 18g.",
        "grind_setting": "What grind setting are you currently using?",
        "roast_level": "What roast level is the coffee: light, medium, or dark?",
        "taste": "How did the shot taste? Sour, bitter, balanced, thin, harsh, or anything you noticed.",
        "timing": "Send the shot video path, or type the total shot time in seconds if you timed it manually.",
    }
    if field.startswith("confirm_") and context.pending_gear_name:
        label = "machine" if context.pending_gear_type == "machine" else "grinder"
        return f"I think this is {context.pending_gear_name} ({context.pending_gear_confidence or 'unknown'} confidence). Is that your {label}? If not, reply like: no, it is Rancilio Silvia."
    if field == "grinder" and context.uses_built_in_grinder:
        return question_for("dose_g", context)
    return questions[field]


def analysis_reply(analysis: AnalyzeShotResponse) -> str:
    timing = analysis.timing.get("total_shot_seconds")
    recommendation = analysis.recommendation
    setting = recommendation.get("exact_grind_setting") or {}
    setting_label = setting.get("setting_label")
    prefix = f"I measured this as a {timing}s shot. " if timing is not None else "I analyzed the shot. "
    if setting_label:
        return prefix + f"Next, set the grinder to {setting_label}. {recommendation.get('reason', '')}"
    return prefix + f"Next action: {recommendation.get('adjustment', 'review the shot')}. {recommendation.get('reason', '')}"


def has_explicit_timing(text: str) -> bool:
    return bool(VIDEO_PATTERN.search(text) or _extract_seconds(text) is not None)


def latest_user_message(request: ChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content.strip()
    return ""


def is_empty_context(context: ShotContext) -> bool:
    data = context.model_dump()
    ignored = {"user_id", "uses_built_in_grinder", "requires_manual_confirmation"}
    return all(value in (None, "", False) for key, value in data.items() if key not in ignored)


def is_greeting(text: str) -> bool:
    return text.strip().lower() in {"hi", "hello", "hey", "hey there", "shalom"}


def is_small_talk(text: str) -> bool:
    lowered = re.sub(r"[^a-z0-9 ]+", "", text.strip().lower()).strip()
    small_talk = {
        "how are you",
        "how are you doing",
        "how r u",
        "whats up",
        "what is up",
        "sup",
        "thank you",
        "thanks",
        "ok",
        "okay",
        "cool",
    }
    if lowered in small_talk:
        return True
    return lowered.startswith(("how are", "what can you do", "who are you"))


def looks_like_equipment_name(name: str, gear_type: str) -> bool:
    cleaned = _clean_equipment_reply(name)
    normalized = _normalize_text(cleaned)
    if not normalized or is_small_talk(cleaned):
        return False
    if _is_generic_non_equipment_reply(normalized):
        return False
    if gear_type == "machine" and _is_known_machine(cleaned):
        return True
    if gear_type == "grinder" and _is_known_grinder(cleaned):
        return True
    if _has_equipment_keyword(normalized):
        return True
    tokens = normalized.split()
    has_modelish_token = any(any(char.isdigit() for char in token) for token in tokens)
    has_brandish_shape = len(tokens) >= 2 and all(len(token) >= 2 for token in tokens)
    return has_modelish_token or has_brandish_shape


def small_talk_reply(message: str, next_field: str | None, context: ShotContext) -> str | None:
    if not is_small_talk(message):
        return None

    lowered = re.sub(r"[^a-z0-9 ]+", "", message.strip().lower()).strip()
    if lowered.startswith("thank") or lowered in {"thanks", "ok", "okay", "cool"}:
        prefix = "Of course."
    elif lowered.startswith(("what can you do", "who are you")):
        prefix = "I can help identify your setup, collect shot details, analyze shot timing, and suggest the next grind setting."
    else:
        prefix = "I'm good, ready to help dial in your espresso."

    if next_field:
        return f"{prefix} {question_for(next_field, context)}"
    return prefix


def _is_known_machine(name: str) -> bool:
    profile = machine_profiles.get_machine_profile(name)
    return profile.get("machine_name") != machine_profiles.GENERIC_PROFILE_NAME


def _is_known_grinder(name: str) -> bool:
    profile = grinder_profiles.get_grinder_profile(name)
    return profile.get("grinder_name") != grinder_profiles.GENERIC_GRINDER_NAME


def _has_equipment_keyword(normalized: str) -> bool:
    return any(
        keyword in normalized.split()
        for keyword in {
            "espresso",
            "machine",
            "grinder",
            "grind",
            "breville",
            "sage",
            "rancilio",
            "gaggia",
            "lelit",
            "delonghi",
            "de",
            "longhi",
            "profitec",
            "eureka",
            "baratza",
            "niche",
            "turin",
            "df54",
            "df64",
            "kingrinder",
            "1zpresso",
            "comandante",
            "la",
            "marzocco",
            "rocket",
            "ecm",
            "ascaso",
            "bezzera",
            "flair",
            "kinu",
            "varia",
        }
    )


def _is_generic_non_equipment_reply(normalized: str) -> bool:
    generic_words = {
        "height",
        "weight",
        "yes",
        "no",
        "maybe",
        "fine",
        "good",
        "bad",
        "ok",
        "okay",
        "cool",
        "test",
        "photo",
        "picture",
        "video",
    }
    tokens = normalized.split()
    return len(tokens) == 1 and tokens[0] in generic_words


def _normalize_text(value: str) -> str:
    value = value.lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _is_general_dial_in_request(text: str) -> bool:
    lowered = text.strip().lower()
    return any(phrase in lowered for phrase in ["dial in", "help", "espresso", "shot"]) and " " in lowered


def _apply_pending_gear_reply(context: ShotContext, text: str) -> None:
    lowered = text.strip().lower()
    gear_type = context.pending_gear_type
    guessed_name = context.pending_gear_name
    corrected_name = _extract_correction_name(text)

    if _is_confirmation_yes(lowered):
        final_name = guessed_name
    elif corrected_name:
        final_name = corrected_name
    elif _is_confirmation_no(lowered):
        context.pending_gear_type = None
        context.pending_gear_name = None
        context.pending_gear_confidence = None
        return
    else:
        final_name = text

    if gear_type == "machine":
        context.machine = canonical_gear_name(str(final_name), "machine")
        if context.uses_built_in_grinder and not context.grinder:
            context.grinder = f"{context.machine} built-in grinder"
    elif gear_type == "grinder":
        context.grinder = canonical_gear_name(str(final_name), "grinder")
        context.uses_built_in_grinder = False

    context.pending_gear_type = None
    context.pending_gear_name = None
    context.pending_gear_confidence = None


def _is_confirmation_yes(text: str) -> bool:
    return text.strip().lower() in {"yes", "y", "yeah", "yep", "correct", "right", "use it", "that's right", "that is right"}


def is_confirmation_no(text: str) -> bool:
    return text.strip().lower() in {"no", "n", "nope", "wrong", "not it", "not correct"}


def _is_confirmation_no(text: str) -> bool:
    return is_confirmation_no(text)


def _extract_correction_name(text: str) -> str | None:
    match = re.search(
        r"\b(?:it is|it's|its|machine is|grinder is|this is|that is)\s+(.+)$",
        text.strip(),
        re.IGNORECASE,
    )
    if match:
        return _clean_equipment_reply(match.group(1))
    lowered = text.strip().lower()
    for prefix in ("no,", "no ", "wrong,", "wrong ", "nope,", "nope "):
        if lowered.startswith(prefix):
            return _clean_equipment_reply(text[len(prefix):])
    return None


def _looks_like_skip(text: str) -> bool:
    return text in {"skip", "unknown", "no", "none", "not sure"}


def _looks_like_image_file(value: str) -> bool:
    return bool(re.search(r"\.(?:png|jpe?g|webp|heic)$", value.strip(), re.IGNORECASE))


def _extract_seconds(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_labeled_number(text: str, labels: list[str]) -> float | None:
    for label in labels:
        match = re.search(rf"\b{label}\b\D{{0,12}}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _first_number(text: str) -> float | None:
    match = NUMBER_PATTERN.search(text)
    return float(match.group(0)) if match else None


def _extract_grind_setting(text: str) -> str | None:
    match = re.search(r"\bgrind(?:\s+setting)?\b\D{0,12}([a-z0-9.\-]+)", text, re.IGNORECASE)
    return match.group(1).rstrip(".,") if match else None


def _first_tokenish_value(text: str) -> str | None:
    cleaned = text.strip().split()[0] if text.strip() else ""
    return cleaned.rstrip(".,") or None


def _clean_equipment_reply(text: str) -> str:
    cleaned = re.sub(r"^(i use|using|machine is|grinder is|it is|it's|my machine is|my grinder is)\s+", "", text.strip(), flags=re.IGNORECASE)
    return cleaned.strip(" .,;:-")
