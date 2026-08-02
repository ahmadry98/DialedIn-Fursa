"""Agent orchestration for DialedIN.

The MVP runner calls the espresso MCP tool functions directly. Checkpoint 7 made
those functions MCP-callable; future work can swap these direct calls for real MCP
client transport without changing the API response shape.
"""

from __future__ import annotations

from typing import Any

from services.agent import conversation
from services.agent.prompts import SYSTEM_PROMPT
from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatRequest, ChatResponse
from services.espresso_mcp import app as espresso_tools

REQUIRED_CONTEXT_FIELDS = ["machine", "grinder", "dose_g", "grind_setting", "roast_level", "taste"]
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
    profile_candidates = espresso_tools.capture_unknown_gear(
        request.user_id,
        request.machine,
        None if request.uses_built_in_grinder else request.grinder,
        shot_context,
    )
    METRICS["last_missing_fields_count"] = len(missing_fields)

    result = {
        "timing": timing,
        "machine_profile": machine_profile,
        "recommendation": recommendation,
        "missing_fields": missing_fields,
        "profile_candidates": profile_candidates,
    }
    saved = espresso_tools.save_shot_result(request.user_id, result)
    comparison = espresso_tools.compare_previous_shots(request.user_id, timing)

    return AnalyzeShotResponse(
        timing=timing,
        machine_profile=machine_profile,
        recommendation=recommendation,
        missing_fields=missing_fields,
        profile_candidates=profile_candidates,
        saved_result=saved,
        previous_comparison=comparison,
        message=_build_message(timing, recommendation, missing_fields),
    )


def chat(request: ChatRequest) -> ChatResponse:
    """Run the guided espresso coach conversation."""
    METRICS["chat_requests_total"] += 1
    response = conversation.handle_chat(request, analyze_shot)
    response.system_prompt = SYSTEM_PROMPT
    if response.shot_context:
        METRICS["last_missing_fields_count"] = len(response.missing_fields)
    return response


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
        "grinder": _effective_grinder_name(request),
        "uses_built_in_grinder": request.uses_built_in_grinder,
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
    missing = [field for field in REQUIRED_CONTEXT_FIELDS if getattr(context, field) in (None, "")]
    if context.uses_built_in_grinder and context.machine not in (None, ""):
        missing = [field for field in missing if field != "grinder"]
    return missing


def _effective_grinder_name(request: AnalyzeShotRequest) -> str | None:
    if request.uses_built_in_grinder:
        machine = request.machine or "machine"
        return request.grinder or f"{machine} built-in grinder"
    return request.grinder


def _build_message(timing: dict[str, Any], recommendation: dict[str, Any], missing_fields: list[str]) -> str:
    if timing.get("requires_manual_confirmation"):
        return "Timing confidence is low. Confirm the detected start and stop before changing grind."

    total = timing.get("total_shot_seconds")
    action = recommendation.get("adjustment", "review the shot context")
    if missing_fields:
        return f"Detected a {total}s shot. Next likely action: {action}. Add missing context for a stronger recommendation."
    return f"Detected a {total}s shot. Next action: {action}. Keep the listed variables fixed for the next test."
