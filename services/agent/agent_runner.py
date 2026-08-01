"""Agent orchestration for DialedIN.

The MVP runner calls the espresso MCP tool functions directly. Checkpoint 7 made
those functions MCP-callable; future work can swap these direct calls for real MCP
client transport without changing the API response shape.
"""

from __future__ import annotations

from typing import Any

from services.agent.prompts import SYSTEM_PROMPT
from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatRequest, ChatResponse
from services.espresso_mcp import app as espresso_tools

REQUIRED_CONTEXT_FIELDS = ["machine", "grinder", "dose_g", "yield_g", "grind_setting", "roast_level", "taste"]
METRICS = {
    "shot_analysis_requests_total": 0,
    "chat_requests_total": 0,
    "last_missing_fields_count": 0,
}


def analyze_shot(request: AnalyzeShotRequest) -> AnalyzeShotResponse:
    """Analyze a shot and return timing, profile, recommendation, and explanation."""
    METRICS["shot_analysis_requests_total"] += 1

    timing = _timing_from_request(request)
    machine_profile = espresso_tools.get_machine_profile(request.machine)
    shot_context = _recommendation_context(request, timing, machine_profile)
    recommendation = espresso_tools.recommend_grind_adjustment(shot_context)
    missing_fields = _missing_fields(request)
    METRICS["last_missing_fields_count"] = len(missing_fields)

    result = {
        "timing": timing,
        "machine_profile": machine_profile,
        "recommendation": recommendation,
        "missing_fields": missing_fields,
    }
    saved = espresso_tools.save_shot_result(request.user_id, result)
    comparison = espresso_tools.compare_previous_shots(request.user_id, timing)

    return AnalyzeShotResponse(
        timing=timing,
        machine_profile=machine_profile,
        recommendation=recommendation,
        missing_fields=missing_fields,
        saved_result=saved,
        previous_comparison=comparison,
        message=_build_message(timing, recommendation, missing_fields),
    )


def chat(request: ChatRequest) -> ChatResponse:
    """Return a lightweight agent response for chat requests."""
    METRICS["chat_requests_total"] += 1
    latest_user_message = ""
    for message in reversed(request.messages):
        if message.role == "user":
            latest_user_message = message.content
            break

    if request.shot_context and (request.shot_context.video_s3_key or request.shot_context.total_shot_seconds):
        missing = _missing_fields(request.shot_context)
        if missing:
            response = "I can analyze the shot, but I still need: " + ", ".join(missing) + "."
        else:
            response = "I have enough shot context to analyze timing and recommend one next adjustment."
        return ChatResponse(response=response, needs_shot_analysis=True, system_prompt=SYSTEM_PROMPT)

    response = latest_user_message or "Send me an espresso shot video path and shot details when you are ready."
    return ChatResponse(
        response="Send a shot video plus machine, grinder, dose, yield, grind setting, roast, and taste so I can analyze it.",
        needs_shot_analysis=False,
        system_prompt=SYSTEM_PROMPT,
    )


def metrics() -> dict[str, int]:
    return dict(METRICS)


def _timing_from_request(request: AnalyzeShotRequest) -> dict[str, Any]:
    if request.video_s3_key:
        return espresso_tools.analyze_audio_timing(request.video_s3_key)

    if request.total_shot_seconds is not None:
        confidence = request.timing_confidence if request.timing_confidence is not None else 1.0
        return {
            "source_path": "manual",
            "machine_start_time": None,
            "machine_stop_time": None,
            "total_shot_seconds": request.total_shot_seconds,
            "start_confidence": confidence,
            "stop_confidence": confidence,
            "audio_method": "manual_total_time",
            "requires_manual_confirmation": request.requires_manual_confirmation,
            "confirmation_reason": None,
            "warnings": [],
        }

    raise ValueError("Either video_s3_key or total_shot_seconds is required")


def _recommendation_context(
    request: AnalyzeShotRequest,
    timing: dict[str, Any],
    machine_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "machine": request.machine,
        "machine_profile": machine_profile,
        "grinder": request.grinder,
        "dose_g": request.dose_g,
        "yield_g": request.yield_g,
        "grind_setting": request.grind_setting,
        "roast_level": request.roast_level,
        "taste": request.taste,
        "total_shot_seconds": timing.get("total_shot_seconds"),
        "timing_confidence": min(
            float(timing.get("start_confidence") or 0),
            float(timing.get("stop_confidence") or 0),
        ),
        "requires_manual_confirmation": bool(timing.get("requires_manual_confirmation")),
    }


def _missing_fields(context: AnalyzeShotRequest) -> list[str]:
    return [field for field in REQUIRED_CONTEXT_FIELDS if getattr(context, field) in (None, "")]


def _build_message(timing: dict[str, Any], recommendation: dict[str, Any], missing_fields: list[str]) -> str:
    if timing.get("requires_manual_confirmation"):
        return "Timing confidence is low. Confirm the detected start and stop before changing grind."

    total = timing.get("total_shot_seconds")
    action = recommendation.get("adjustment", "review the shot context")
    if missing_fields:
        return f"Detected a {total}s shot. Next likely action: {action}. Add missing context for a stronger recommendation."
    return f"Detected a {total}s shot. Next action: {action}. Keep the listed variables fixed for the next test."
