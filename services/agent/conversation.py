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

FIELD_ORDER = ["machine", "grinder", "grind_setting", "roast_level", "taste", "timing"]
TASTE_WORDS = {"sour", "bitter", "balanced", "thin", "watery", "harsh", "dry", "sweet", "acidic"}
ROAST_LEVELS = {"light", "medium", "dark"}
VIDEO_PATTERN = re.compile(r"(?:data/[^\s]+|[^\s]+\.(?:mp4|mov|m4v|wav))", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
BRAND_ONLY_NAMES = {
    "ascaso",
    "baratza",
    "bezzera",
    "breville",
    "comandante",
    "delonghi",
    "df",
    "ecm",
    "eureka",
    "flair",
    "gaggia",
    "gevi",
    "illy",
    "kingrinder",
    "kinu",
    "la marzocco",
    "la pavoni",
    "lelit",
    "niche",
    "profitec",
    "quick mill",
    "rancilio",
    "rocket",
    "sage",
    "turin",
    "varia",
}


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

    if is_small_talk(text) or is_media_attachment_message(text):
        return

    _apply_compact_setup_message(context, text, previous_missing)

    if is_built_in_grinder_reply(text):
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

    dose = _extract_labeled_number(text, ["dose", "in"])
    if dose is None:
        dose = _extract_dose_value(text)
    if dose is None and context.dose_g is None and previous_missing[:1] == ["dose_g"]:
        dose = _first_number(text)
    if dose is not None:
        context.dose_g = dose

    yield_value = _extract_labeled_number(text, ["yield", "out", "output"])
    if yield_value is not None:
        context.yield_g = yield_value

    grind = _extract_grind_setting(text)
    if grind is None and not context.grind_setting and previous_missing[:1] == ["grind_setting"]:
        grind = _first_tokenish_value(text)
    if grind:
        context.grind_setting = grind

    if not context.roast_level:
        roast = _extract_roast_level(text)
        if roast:
            context.roast_level = roast
        elif previous_missing[:1] == ["roast_level"] and lowered in ROAST_LEVELS:
            context.roast_level = lowered

    if not context.taste and not video and context.total_shot_seconds is None and not is_structured_field_correction(text):
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


def is_compact_setup_message(text: str) -> bool:
    parts = [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    return len(parts) >= 4 and any(_extract_dose_value(part) is not None for part in parts)


def _apply_compact_setup_message(context: ShotContext, text: str, previous_missing: list[str]) -> None:
    """Parse natural comma-separated setup replies.

    Example: "Lelit Anita, builtin, 18g, 2.1, medium, dark". This keeps the
    chat pleasant when the user gives the whole setup in one message instead of
    answering one field at a time.
    """
    parts = [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    if len(parts) < 3:
        return

    available_fields = previous_missing[:] or missing_chat_fields(context)
    if "machine" in available_fields and not context.machine and parts:
        first = parts[0]
        if looks_like_equipment_name(first, "machine"):
            context.machine = canonical_gear_name(first, "machine")
            parts = parts[1:]

    if parts and "grinder" in available_fields and not context.grinder:
        if is_built_in_grinder_reply(parts[0]):
            context.uses_built_in_grinder = True
            if context.machine:
                context.grinder = f"{context.machine} built-in grinder"
            parts = parts[1:]
        elif looks_like_equipment_name(parts[0], "grinder"):
            context.grinder = canonical_gear_name(parts[0], "grinder")
            parts = parts[1:]

    for part in parts[:]:
        dose = _extract_dose_value(part)
        if dose is not None:
            context.dose_g = dose
            parts.remove(part)
            break

    for part in parts[:]:
        if not context.grind_setting:
            grind = _extract_grind_setting(part) or _numeric_tokenish_value(part)
            if grind is not None:
                context.grind_setting = grind
                parts.remove(part)
                break

    for part in parts[:]:
        roast = _extract_roast_level(part)
        if roast and not context.roast_level:
            context.roast_level = roast
            parts.remove(part)
            break

    for part in parts:
        if not context.taste and not is_structured_field_correction(part) and not _looks_like_skip(_normalize_text(part)):
            context.taste = part
            break



def is_structured_field_correction(text: str) -> bool:
    """Return true when a message clearly updates a non-taste field."""
    lowered = text.strip().lower()
    if VIDEO_PATTERN.search(text) or _extract_seconds(text) is not None:
        return True
    return bool(
        _extract_labeled_number(text, ["dose", "in", "yield", "out", "output"]) is not None
        or _extract_grind_setting(text) is not None
        or re.search(r"\broast\b", lowered)
    )


def has_labeled_dose(text: str) -> bool:
    return _extract_labeled_number(text, ["dose", "in"]) is not None


def has_labeled_taste(text: str) -> bool:
    lowered = text.strip().lower()
    return bool(re.search(r"\b(?:taste|tasted|flavor|flavour)\b", lowered))


def is_vague_equipment_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return True
    if is_small_talk(text):
        return True
    return _is_generic_non_equipment_reply(normalized)


def is_media_attachment_message(text: str) -> bool:
    normalized = _normalize_text(text)
    return normalized in {
        "photo attached",
        "image attached",
        "picture attached",
        "shot video attached",
        "video attached",
    }


def is_brand_only_equipment_name(name: str) -> bool:
    """Return true for brand/company names that still need a model name."""
    normalized = _normalize_text(_clean_equipment_reply(name))
    return normalized in BRAND_ONLY_NAMES


def known_equipment_type(name: str) -> str | None:
    """Return the trusted profile type when a name clearly matches one side."""
    cleaned = _clean_equipment_reply(name)
    is_machine = _is_known_machine(cleaned)
    is_grinder = _is_known_grinder(cleaned)
    if is_machine and not is_grinder:
        return "machine"
    if is_grinder and not is_machine:
        return "grinder"
    return None


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
        "grind_setting": "What grind setting are you currently using? If you know the dose, you can include it too, like 18g.",
        "roast_level": "What roast level is the coffee: light, medium, or dark?",
        "taste": "How did the shot taste? Sour, bitter, balanced, thin, harsh, or anything you noticed.",
        "timing": "Attach or send your espresso shot video. If you timed it yourself, you can type the total time, like 27 seconds.",
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
    confidence = _analysis_timing_confidence(analysis)
    if _is_video_timing(analysis) and confidence is not None and confidence < 0.7:
        return (
            prefix
            + f"Timing confidence is only {confidence * 100:.0f}%. Please confirm the start and stop times, "
            + "or send another video with less talking/background noise and a clear machine sound."
        )
    if setting_label:
        return prefix + f"Next, set the grinder to {setting_label}. {recommendation.get('reason', '')}"
    return prefix + f"Next action: {recommendation.get('adjustment', 'review the shot')}. {recommendation.get('reason', '')}"


def _analysis_timing_confidence(analysis: AnalyzeShotResponse) -> float | None:
    values = [
        analysis.timing.get("timing_confidence"),
        analysis.timing.get("start_confidence"),
        analysis.timing.get("stop_confidence"),
    ]
    parsed = [_float_or_none(value) for value in values]
    available = [value for value in parsed if value is not None]
    return min(available) if available else None


def _is_video_timing(analysis: AnalyzeShotResponse) -> bool:
    return analysis.timing.get("audio_method") != "manual_total_time"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        "whats your name",
        "what is your name",
        "your name",
        "sup",
        "thank you",
        "thanks",
        "ok",
        "okay",
        "cool",
    }
    if lowered in small_talk:
        return True
    return lowered.startswith(("how are", "what can you do", "who are you", "what is your name", "whats your name"))



def is_built_in_grinder_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    return normalized in {
        "built in",
        "built it",
        "builtin",
        "built in grinder",
        "built it grinder",
        "integrated grinder",
        "internal grinder",
        "in the machine",
        "inside the machine",
    } or any(phrase in normalized for phrase in ["built in grinder", "built into", "built it", "integrated grinder"])

def looks_like_equipment_name(name: str, gear_type: str) -> bool:
    cleaned = _clean_equipment_reply(name)
    normalized = _normalize_text(cleaned)
    if not normalized or is_small_talk(cleaned):
        return False
    if _is_generic_non_equipment_reply(normalized):
        return False
    if is_brand_only_equipment_name(cleaned):
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
    elif lowered.startswith(("what is your name", "whats your name", "who are you")):
        prefix = "I'm DialedIN, your espresso shot coach."
    elif lowered.startswith("what can you do"):
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
        "ye",
        "y",
        "yeah",
        "yep",
        "yup",
        "ya",
        "no",
        "n",
        "nope",
        "wrong",
        "maybe",
        "sure",
        "correct",
        "right",
        "fine",
        "good",
        "bad",
        "ok",
        "okay",
        "cool",
        "test",
        "skip",
        "unknown",
        "none",
        "nothing",
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
    return text.strip().lower() in {
        "yes",
        "ye",
        "y",
        "yeah",
        "yep",
        "yup",
        "ya",
        "correct",
        "right",
        "sure",
        "ok",
        "okay",
        "use it",
        "that's right",
        "that is right",
        "looks right",
    }


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


def _extract_dose_value(text: str) -> float | None:
    match = re.search(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*g\b", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _extract_roast_level(text: str) -> str | None:
    lowered = text.lower()
    return next((level for level in ROAST_LEVELS if re.search(rf"\b{level}\b", lowered)), None)


def _numeric_tokenish_value(text: str) -> str | None:
    cleaned = text.strip().rstrip(".,")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return cleaned
    return None


def _first_tokenish_value(text: str) -> str | None:
    cleaned = text.strip().split()[0] if text.strip() else ""
    return cleaned.rstrip(".,") or None


def _clean_equipment_reply(text: str) -> str:
    cleaned = re.sub(r"^(i use|using|machine is|grinder is|it is|it's|my machine is|my grinder is)\s+", "", text.strip(), flags=re.IGNORECASE)
    return cleaned.strip(" .,;:-")
