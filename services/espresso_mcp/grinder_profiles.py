"""Curated grinder profile lookup and exact setting suggestions."""

from __future__ import annotations

import json
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

PROFILE_PATH = Path(__file__).with_name("grinder_profiles.json")
GENERIC_GRINDER_NAME = "Generic Numeric Grinder"


def get_grinder_profile(grinder_name: str | None) -> dict[str, Any]:
    """Return a grinder profile by exact name or alias, with a generic fallback."""
    profiles = _load_profiles()
    normalized = _normalize(grinder_name)

    if normalized:
        for profile in profiles:
            names = [profile.get("grinder_name", ""), *profile.get("aliases", [])]
            if normalized in {_normalize(name) for name in names}:
                return deepcopy(profile)

        fuzzy_match = _best_fuzzy_profile_match(normalized, profiles)
        if fuzzy_match is not None:
            return deepcopy(fuzzy_match)

    return deepcopy(_generic_profile(profiles))


def list_grinder_profiles() -> list[dict[str, Any]]:
    """Return all curated grinder profiles."""
    return [deepcopy(profile) for profile in _load_profiles()]


def validate_grind_setting(grinder_name: str | None, current_setting: Any) -> str | None:
    """Return an error message when a grind setting is invalid for a known grinder."""
    if current_setting in (None, ""):
        return None

    profile = get_grinder_profile(grinder_name)
    if profile.get("grinder_name") == GENERIC_GRINDER_NAME:
        return None if _float_or_none(current_setting) is not None else "Use a numeric grind setting."

    parsed = _float_or_none(current_setting)
    if parsed is None:
        return "Use a numeric grind setting so the next setting can be calculated."

    if profile.get("setting_type") == "numeric_integer" and not parsed.is_integer():
        return f"{profile['grinder_name']} accepts whole-number grind settings."

    minimum = _float_or_none(profile.get("min_setting"))
    maximum = _float_or_none(profile.get("max_setting"))
    if minimum is not None and parsed < minimum:
        return _range_error(profile)
    if maximum is not None and parsed > maximum:
        return _range_error(profile)

    return None


def suggest_grind_setting(
    grinder_name: str | None,
    current_setting: Any,
    recommendation: str,
    total_shot_seconds: Any,
    target_range_seconds: tuple[float, float] | list[float],
) -> dict[str, Any]:
    """Calculate the next grinder setting without using an LLM."""
    profile = get_grinder_profile(grinder_name)
    current = _float_or_none(current_setting)

    result = {
        "grinder_profile": profile,
        "current_setting": current_setting,
        "suggested_setting": None,
        "setting_label": None,
        "adjustment_size": None,
        "notes": profile.get("notes"),
    }

    if recommendation not in {"grind_finer", "grind_coarser"} or current is None:
        return result

    step_info = _step_for_shot_gap(profile, total_shot_seconds, target_range_seconds)
    step = step_info["step"]
    direction_multiplier = -1 if profile.get("lower_is_finer", True) else 1
    if recommendation == "grind_coarser":
        direction_multiplier *= -1

    raw_suggested = current + (direction_multiplier * step)
    clamped_suggested = _clamp(raw_suggested, profile.get("min_setting"), profile.get("max_setting"))
    was_clamped = clamped_suggested != raw_suggested
    suggested = _format_for_type(clamped_suggested, profile.get("setting_type"))

    result.update(
        {
            "suggested_setting": suggested,
            "setting_label": str(suggested),
            "raw_suggested_setting": _format_for_type(raw_suggested, profile.get("setting_type")),
            "was_clamped": was_clamped,
            "adjustment_size": step_info["adjustment_size"],
            "seconds_gap": step_info.get("seconds_gap"),
            "estimated_small_steps": step_info.get("estimated_small_steps"),
            "seconds_per_small_step_estimate": step_info.get("seconds_per_small_step_estimate"),
        }
    )
    return result


def _range_error(profile: dict[str, Any]) -> str:
    minimum = profile.get("min_setting")
    maximum = profile.get("max_setting")
    return f"{profile['grinder_name']} accepts settings from {minimum} to {maximum}."


def _best_fuzzy_profile_match(normalized_query: str, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a likely typo match while avoiding weak guesses."""
    query_value = normalized_query
    scores_by_profile: list[tuple[float, dict[str, Any]]] = []

    for profile in profiles:
        if profile.get("grinder_name") == GENERIC_GRINDER_NAME:
            continue
        profile_best = 0.0
        for name in [profile.get("grinder_name", ""), *profile.get("aliases", [])]:
            candidate = _normalize(name)
            if candidate:
                profile_best = max(profile_best, SequenceMatcher(None, query_value, candidate).ratio())
        if profile_best:
            scores_by_profile.append((profile_best, profile))

    scores_by_profile.sort(key=lambda item: item[0], reverse=True)
    if not scores_by_profile:
        return None

    best_score, best_profile = scores_by_profile[0]
    second_score = scores_by_profile[1][0] if len(scores_by_profile) > 1 else 0.0
    if best_score >= 0.9 and best_score - second_score >= 0.03:
        return best_profile
    return None

def _load_profiles() -> list[dict[str, Any]]:
    with PROFILE_PATH.open(encoding="utf-8") as profile_file:
        return json.load(profile_file)


def _generic_profile(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for profile in profiles:
        if profile.get("grinder_name") == GENERIC_GRINDER_NAME:
            return profile
    raise ValueError("Generic grinder profile is required")


def _step_for_shot_gap(profile: dict[str, Any], total_shot_seconds: Any, target_range_seconds: tuple[float, float] | list[float]) -> dict[str, Any]:
    total = _float_or_none(total_shot_seconds)
    target_min = _float_or_none(target_range_seconds[0]) if len(target_range_seconds) >= 2 else None
    target_max = _float_or_none(target_range_seconds[1]) if len(target_range_seconds) >= 2 else None
    small_step = float(profile.get("small_step") or 1)
    medium_step = float(profile.get("medium_step") or small_step)

    if total is None or target_min is None or target_max is None:
        return {"step": medium_step, "adjustment_size": _size_name(medium_step, profile)}

    gap = target_min - total if total < target_min else total - target_max
    estimate = _float_or_none(profile.get("seconds_per_small_step_estimate"))
    if estimate is not None and estimate > 0:
        step_count = max(1, int((gap / estimate) + 0.5))
        max_steps = int(_float_or_none(profile.get("max_recommended_small_steps")) or 6)
        step_count = min(step_count, max_steps)
        step = small_step * step_count
        return {
            "step": step,
            "adjustment_size": _size_name_from_small_steps(step_count),
            "seconds_gap": round(gap, 2),
            "estimated_small_steps": step_count,
            "seconds_per_small_step_estimate": estimate,
        }

    if gap >= 10:
        step = float(profile.get("large_step") or medium_step)
    elif gap >= 5:
        step = medium_step
    else:
        step = small_step
    return {"step": step, "adjustment_size": _size_name(step, profile), "seconds_gap": round(gap, 2)}


def _size_name(step: float, profile: dict[str, Any]) -> str:
    if step == float(profile.get("large_step") or -1):
        return "large"
    if step == float(profile.get("medium_step") or -1):
        return "medium"
    return "small"


def _size_name_from_small_steps(step_count: int) -> str:
    if step_count >= 4:
        return "large"
    if step_count >= 2:
        return "medium"
    return "small"


def _format_for_type(value: float, setting_type: str | None) -> int | float:
    if setting_type == "numeric_integer":
        return int(round(value))
    return round(value, 2)


def _clamp(value: float, minimum: Any, maximum: Any) -> float:
    min_value = _float_or_none(minimum)
    max_value = _float_or_none(maximum)
    if min_value is not None:
        value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).lower().replace("-", " ").split())
