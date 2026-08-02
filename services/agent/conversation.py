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

FIELD_ORDER = ["machine", "grinder", "dose_g", "grind_setting", "roast_level", "taste", "timing"]
TASTE_WORDS = {"sour", "bitter", "balanced", "thin", "watery", "harsh", "dry", "sweet", "acidic"}
ROAST_LEVELS = {"light", "medium", "dark"}
VIDEO_PATTERN = re.compile(r"(?:data/[^\s]+|[^\s]+\.(?:mp4|mov|m4v|wav))", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def handle_chat(request: ChatRequest, analyze_callback) -> ChatResponse:
    """Update conversation state and analyze when the shot context is ready."""
    from services.agent import graph

    return graph.run_chat_graph(request, analyze_callback)


def missing_chat_fields(context: ShotContext) -> list[str]:
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


def apply_message_to_context(context: ShotContext, message: str, previous_missing: list[str]) -> None:
    text = message.strip()
    lowered = text.lower()

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
        context.machine = _clean_equipment_reply(text)
        if context.uses_built_in_grinder and not context.grinder:
            context.grinder = f"{context.machine} built-in grinder"

    if not context.grinder and not context.uses_built_in_grinder and previous_missing[:1] == ["grinder"]:
        context.grinder = _clean_equipment_reply(text)


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


def _is_general_dial_in_request(text: str) -> bool:
    lowered = text.strip().lower()
    return any(phrase in lowered for phrase in ["dial in", "help", "espresso", "shot"]) and " " in lowered


def _looks_like_skip(text: str) -> bool:
    return text in {"skip", "unknown", "no", "none", "not sure"}


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
    return cleaned.strip(" .")
