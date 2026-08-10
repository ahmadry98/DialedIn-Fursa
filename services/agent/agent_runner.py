"""Agent orchestration for DialedIN.

The MVP runner calls the espresso MCP tool functions directly. Checkpoint 7 made
those functions MCP-callable; future work can swap these direct calls for real MCP
client transport without changing the API response shape.
"""

from __future__ import annotations

from typing import Any

from services.agent import conversation, observability
from services.agent.prompts import SYSTEM_PROMPT
from services.agent.schemas import AnalyzeShotRequest, AnalyzeShotResponse, ChatRequest, ChatResponse
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import grinder_profiles, machine_profiles

REQUIRED_CONTEXT_FIELDS = ["machine", "grinder", "grind_setting", "roast_level", "taste"]
METRICS = {
    "shot_analysis_requests_total": 0,
    "chat_requests_total": 0,
    "last_missing_fields_count": 0,
}


def analyze_shot(request: AnalyzeShotRequest) -> AnalyzeShotResponse:
    """Analyze a shot and return timing, profile, recommendation, and explanation."""
    METRICS["shot_analysis_requests_total"] += 1

    timing = _timing_from_request(request)
    observability.observe("dialedin_audio_total_shot_seconds", timing.get("total_shot_seconds"), source=timing.get("audio_method"))
    observability.observe(
        "dialedin_audio_timing_confidence",
        min(float(timing.get("start_confidence") or 0), float(timing.get("stop_confidence") or 0)),
        source=timing.get("audio_method"),
    )
    if timing.get("requires_manual_confirmation"):
        observability.increment("dialedin_audio_manual_confirmation_required_total", source=timing.get("audio_method"))
    canonical_machine = _canonical_machine_name(request.machine)
    canonical_grinder = _canonical_grinder_name(None if request.uses_built_in_grinder else request.grinder)
    machine_profile = espresso_tools.get_machine_profile(canonical_machine)
    shot_context = _recommendation_context(request, timing, machine_profile, canonical_machine, canonical_grinder)
    recommendation = espresso_tools.recommend_grind_adjustment(shot_context)
    missing_fields = _missing_fields(request)
    profile_candidates = espresso_tools.capture_unknown_gear(
        request.user_id,
        canonical_machine,
        None if request.uses_built_in_grinder else canonical_grinder,
        shot_context,
    )
    METRICS["last_missing_fields_count"] = len(missing_fields)
    observability.set_gauge("dialedin_last_missing_fields_count", len(missing_fields))
    observability.increment("dialedin_profile_candidates_captured_total", amount=len(profile_candidates))

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
        observability.set_gauge("dialedin_last_missing_fields_count", len(response.missing_fields))
    if response.image_guess:
        observability.increment(
            "dialedin_image_recognition_total",
            kind=response.image_guess.get("kind"),
            status=response.image_guess.get("status") or "unknown",
            confidence=response.image_guess.get("confidence") or "unknown",
        )
    return response


def metrics() -> dict[str, int]:
    return dict(METRICS)


def _timing_from_request(request: AnalyzeShotRequest) -> dict[str, Any]:
    if request.video_s3_key:
        observability.increment("dialedin_audio_analysis_requests_total", source="video")
        return observability.time_call(
            "dialedin_audio_analysis_duration_seconds",
            lambda: espresso_tools.analyze_audio_timing(request.video_s3_key),
            source="video",
        )

    if request.total_shot_seconds is not None:
        observability.increment("dialedin_audio_analysis_requests_total", source="manual")
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
    canonical_machine: str | None,
    canonical_grinder: str | None,
) -> dict[str, Any]:
    return {
        "machine": canonical_machine or request.machine,
        "machine_profile": machine_profile,
        "grinder": _effective_grinder_name(request, canonical_machine, canonical_grinder),
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


def _canonical_machine_name(machine_name: str | None) -> str | None:
    profile = machine_profiles.get_machine_profile(machine_name)
    if profile.get("machine_name") == machine_profiles.GENERIC_PROFILE_NAME:
        return machine_name
    return profile.get("machine_name") or machine_name


def _canonical_grinder_name(grinder_name: str | None) -> str | None:
    profile = grinder_profiles.get_grinder_profile(grinder_name)
    if profile.get("grinder_name") == grinder_profiles.GENERIC_GRINDER_NAME:
        return grinder_name
    return profile.get("grinder_name") or grinder_name


def _effective_grinder_name(
    request: AnalyzeShotRequest,
    canonical_machine: str | None,
    canonical_grinder: str | None,
) -> str | None:
    if request.uses_built_in_grinder:
        machine = canonical_machine or request.machine or "machine"
        return request.grinder or f"{machine} built-in grinder"
    return canonical_grinder or request.grinder


def _build_message(timing: dict[str, Any], recommendation: dict[str, Any], missing_fields: list[str]) -> str:
    confidence = min(
        float(timing.get("start_confidence") or 0),
        float(timing.get("stop_confidence") or 0),
    )
    if timing.get("requires_manual_confirmation") or (timing.get("audio_method") != "manual_total_time" and confidence < 0.7):
        return (
            f"Detected a {timing.get('total_shot_seconds')}s shot, but timing confidence is {confidence * 100:.0f}%. "
            "Confirm the detected start and stop, or send another video with less talking/background noise and a clear machine sound."
        )

    total = timing.get("total_shot_seconds")
    action = recommendation.get("adjustment", "review the shot context")
    if missing_fields:
        return f"Detected a {total}s shot. Next likely action: {action}. Add missing context for a stronger recommendation."
    return f"Detected a {total}s shot. Next action: {action}. Keep the listed variables fixed for the next test."
