"""Rule-based espresso grind recommendations.

The MVP keeps recommendations deterministic and explainable. The agent can pass
shot timing plus optional taste/yield context and receive one next action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:  # Support both package imports and direct test imports.
    from services.espresso_mcp import grinder_profiles
except ModuleNotFoundError:  # pragma: no cover - exercised by direct unittest imports.
    import grinder_profiles  # type: ignore

DEFAULT_TARGET_MIN_SECONDS = 25.0
DEFAULT_TARGET_MAX_SECONDS = 32.0
LOW_TIMING_CONFIDENCE_THRESHOLD = 0.35

UNDER_EXTRACTED_TASTE_WORDS = {
    "sour",
    "acidic",
    "sharp",
    "watery",
    "thin",
    "weak",
    "under-extracted",
    "under extracted",
}
OVER_EXTRACTED_TASTE_WORDS = {
    "bitter",
    "harsh",
    "dry",
    "astringent",
    "burnt",
    "over-extracted",
    "over extracted",
}
CHANNELING_WORDS = {
    "channeling",
    "spray",
    "spraying",
    "spurting",
    "uneven",
    "gusher",
}
GOOD_TASTE_WORDS = {"balanced", "sweet", "good", "nice", "smooth"}


@dataclass(frozen=True)
class RecommendationResult:
    recommendation: str
    adjustment: str
    reason: str
    confidence: str
    keep_fixed: list[str]
    needs_more_info: list[str]
    target_range_seconds: tuple[float, float]
    exact_grind_setting: dict[str, Any] | None = None
    calculation_explanation: list[str] = field(default_factory=list)
    confidence_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def recommend_grind_adjustment(shot_context: dict[str, Any]) -> dict[str, Any]:
    """Return one next espresso adjustment from timing and taste context."""
    target_min, target_max = _target_range(shot_context)
    total = _float_or_none(shot_context.get("total_shot_seconds"))
    timing_confidence = _timing_confidence(shot_context)
    taste_text = _normalize_text(shot_context.get("taste"))
    keep_fixed = _keep_fixed(shot_context)
    needs_more_info = _missing_context(shot_context)

    if total is None:
        return RecommendationResult(
            recommendation="confirm_timing",
            adjustment="enter the machine start and stop times manually",
            reason="Shot time was not available, so grind advice would be guessing.",
            confidence="low",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ).to_dict()

    if _requires_timing_confirmation(shot_context, timing_confidence):
        return RecommendationResult(
            recommendation="confirm_timing",
            adjustment="confirm or edit the detected shot timing before changing grind",
            reason="Audio timing confidence is low, so the recommendation should wait for confirmed timing.",
            confidence="low",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ).to_dict()

    if total < target_min:
        if _contains_any(taste_text, CHANNELING_WORDS):
            return RecommendationResult(
                recommendation="improve_puck_prep",
                adjustment="keep grind the same for one shot and fix puck prep/channeling first",
                reason="The shot ran fast, but channeling signs can make a shot fast even when grind is not the main problem.",
                confidence="medium",
                keep_fixed=keep_fixed,
                needs_more_info=needs_more_info,
                target_range_seconds=(target_min, target_max),
            ).to_dict()

        reason = "Shot ran faster than the target range."
        if _contains_any(taste_text, UNDER_EXTRACTED_TASTE_WORDS):
            reason += " Sour, watery, or thin taste also points toward under-extraction."
        adjustment = _timing_gap_adjustment_text("finer", total, target_min, target_max)
        return _with_exact_setting(RecommendationResult(
            recommendation="grind_finer",
            adjustment=adjustment,
            reason=reason,
            confidence="high" if timing_confidence >= 0.6 else "medium",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ), shot_context).to_dict()

    if total > target_max:
        reason = "Shot ran slower than the target range."
        if _contains_any(taste_text, OVER_EXTRACTED_TASTE_WORDS):
            reason += " Bitter, harsh, or dry taste also points toward over-extraction."
        adjustment = _timing_gap_adjustment_text("coarser", total, target_min, target_max)
        return _with_exact_setting(RecommendationResult(
            recommendation="grind_coarser",
            adjustment=adjustment,
            reason=reason,
            confidence="high" if timing_confidence >= 0.6 else "medium",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ), shot_context).to_dict()

    if _contains_any(taste_text, UNDER_EXTRACTED_TASTE_WORDS):
        return RecommendationResult(
            recommendation="increase_extraction",
            adjustment="keep grind close, then try a slightly longer yield or one small step finer",
            reason="Shot time is in range, but sour or thin taste suggests the coffee may still be under-extracted.",
            confidence="medium",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ).to_dict()

    if _contains_any(taste_text, OVER_EXTRACTED_TASTE_WORDS):
        return RecommendationResult(
            recommendation="reduce_extraction",
            adjustment="keep grind close, then try a slightly shorter yield or one small step coarser",
            reason="Shot time is in range, but bitter or dry taste suggests the coffee may be over-extracted.",
            confidence="medium",
            keep_fixed=keep_fixed,
            needs_more_info=needs_more_info,
            target_range_seconds=(target_min, target_max),
        ).to_dict()

    if _contains_any(taste_text, GOOD_TASTE_WORDS):
        reason = "Shot time is inside the target range and the taste note sounds positive."
    else:
        reason = "Shot time is inside the target range. Taste context can guide the next small adjustment."

    return RecommendationResult(
        recommendation="keep_settings",
        adjustment="keep the grind setting and repeat once for consistency",
        reason=reason,
        confidence="medium" if needs_more_info else "high",
        keep_fixed=keep_fixed,
        needs_more_info=needs_more_info,
        target_range_seconds=(target_min, target_max),
    ).to_dict()


def _target_range(shot_context: dict[str, Any]) -> tuple[float, float]:
    profile = shot_context.get("machine_profile") or {}
    brew_defaults = profile.get("brew_defaults") if isinstance(profile, dict) else {}
    if not isinstance(brew_defaults, dict):
        brew_defaults = {}
    target = (
        shot_context.get("target_total_shot_seconds")
        or brew_defaults.get("target_total_shot_seconds")
        or profile.get("target_total_shot_seconds")
    )

    if isinstance(target, (list, tuple)) and len(target) >= 2:
        low = _float_or_none(target[0])
        high = _float_or_none(target[1])
        if low is not None and high is not None and low < high:
            return low, high

    if isinstance(target, dict):
        low = _float_or_none(target.get("min") or target.get("low"))
        high = _float_or_none(target.get("max") or target.get("high"))
        if low is not None and high is not None and low < high:
            return low, high

    return DEFAULT_TARGET_MIN_SECONDS, DEFAULT_TARGET_MAX_SECONDS


def _with_exact_setting(result: RecommendationResult, shot_context: dict[str, Any]) -> RecommendationResult:
    exact_setting = grinder_profiles.suggest_grind_setting(
        grinder_name=shot_context.get("grinder"),
        current_setting=shot_context.get("grind_setting"),
        recommendation=result.recommendation,
        total_shot_seconds=shot_context.get("total_shot_seconds"),
        target_range_seconds=result.target_range_seconds,
    )
    suggested = exact_setting.get("setting_label")
    confidence_reasons = _confidence_reasons(shot_context, exact_setting, result.needs_more_info)
    if suggested is None:
        return RecommendationResult(**{
            **asdict(result),
            "exact_grind_setting": exact_setting,
            "confidence_reasons": confidence_reasons,
        })

    direction = "finer" if result.recommendation == "grind_finer" else "coarser"
    adjustment_detail = _relative_adjustment_detail(exact_setting, direction)

    if _uses_generic_grinder_profile(exact_setting):
        relative_setting = {**exact_setting, "suggested_setting": None, "setting_label": None}
        adjustment = f"move {adjustment_detail} from your current setting"
        return RecommendationResult(**{
            **asdict(result),
            "adjustment": adjustment,
            "exact_grind_setting": relative_setting,
            "calculation_explanation": _exact_setting_explanation(relative_setting, result.target_range_seconds),
            "confidence_reasons": confidence_reasons,
        })

    adjustment = f"try grind setting {suggested} next ({adjustment_detail})"
    return RecommendationResult(**{
        **asdict(result),
        "adjustment": adjustment,
        "exact_grind_setting": exact_setting,
        "calculation_explanation": _exact_setting_explanation(exact_setting, result.target_range_seconds),
        "confidence_reasons": confidence_reasons,
    })



def _relative_adjustment_detail(exact_setting: dict[str, Any], direction: str) -> str:
    estimated_steps = exact_setting.get("estimated_small_steps")
    if estimated_steps:
        step_word = "step" if estimated_steps == 1 else "steps"
        return f"about {estimated_steps} small {step_word} {direction}"
    size = exact_setting.get("adjustment_size")
    size_text = f"{size} move " if size else ""
    return f"{size_text}{direction}"


def _uses_generic_grinder_profile(exact_setting: dict[str, Any]) -> bool:
    profile = exact_setting.get("grinder_profile") or {}
    return profile.get("grinder_name") == grinder_profiles.GENERIC_GRINDER_NAME

def _exact_setting_explanation(exact_setting: dict[str, Any], target_range_seconds: tuple[float, float]) -> list[str]:
    explanation: list[str] = []
    current = exact_setting.get("current_setting")
    suggested = exact_setting.get("setting_label")
    seconds_gap = exact_setting.get("seconds_gap")
    estimated_steps = exact_setting.get("estimated_small_steps")
    seconds_per_step = exact_setting.get("seconds_per_small_step_estimate")
    grinder_profile = exact_setting.get("grinder_profile") or {}
    grinder_name = grinder_profile.get("grinder_name") or "grinder profile"

    if seconds_gap is not None:
        explanation.append(
            f"Shot was {seconds_gap:g}s outside the {target_range_seconds[0]:g}-{target_range_seconds[1]:g}s target range."
        )
    if seconds_per_step is not None and estimated_steps is not None:
        if grinder_name == grinder_profiles.GENERIC_GRINDER_NAME:
            explanation.append(
                f"Generic grinder timing estimate suggests about {estimated_steps} small steps, but the exact scale is unknown."
            )
        else:
            explanation.append(
                f"{grinder_name} is estimated at about {seconds_per_step:g}s per small grind step, so this uses about {estimated_steps} small steps."
            )
    if current not in (None, "") and suggested is not None:
        explanation.append(f"Current setting {current} becomes suggested setting {suggested}.")
    return explanation


def _confidence_reasons(
    shot_context: dict[str, Any],
    exact_setting: dict[str, Any] | None,
    needs_more_info: list[str],
) -> list[str]:
    reasons: list[str] = []
    timing = _timing_confidence(shot_context)
    reasons.append(f"Timing confidence is {timing * 100:.0f}%.")

    if exact_setting:
        profile = exact_setting.get("grinder_profile") or {}
        grinder_name = profile.get("grinder_name")
        if grinder_name == grinder_profiles.GENERIC_GRINDER_NAME:
            reasons.append("Generic grinder profile used, so the exact setting is a conservative estimate.")
        elif grinder_name:
            reasons.append(f"Known grinder profile used: {grinder_name}.")
        if exact_setting.get("seconds_per_small_step_estimate") is not None:
            reasons.append("Adjustment size uses estimated grinder sensitivity, not personal shot history yet.")

    if needs_more_info:
        reasons.append("Missing context may reduce recommendation confidence: " + ", ".join(needs_more_info) + ".")
    else:
        reasons.append("Core shot context is complete.")
    return reasons


def _timing_confidence(shot_context: dict[str, Any]) -> float:
    confidence = shot_context.get("timing_confidence")
    if confidence is None:
        confidence = shot_context.get("start_confidence")
    if confidence is None:
        confidence = shot_context.get("stop_confidence")
    parsed = _float_or_none(confidence)
    return 1.0 if parsed is None else max(0.0, min(parsed, 1.0))


def _requires_timing_confirmation(shot_context: dict[str, Any], timing_confidence: float) -> bool:
    return bool(shot_context.get("requires_manual_confirmation")) or timing_confidence < LOW_TIMING_CONFIDENCE_THRESHOLD


def _timing_gap_adjustment_text(direction: str, total: float, target_min: float, target_max: float) -> str:
    gap = target_min - total if total < target_min else total - target_max
    if gap >= 10:
        size = "large"
    elif gap >= 5:
        size = "medium"
    else:
        size = "small"
    return f"make a {size} grind adjustment {direction}"


def _keep_fixed(shot_context: dict[str, Any]) -> list[str]:
    present = [field for field in ["dose_g", "yield_g"] if shot_context.get(field) not in (None, "")]
    return [*present, "puck_prep"]


def _missing_context(shot_context: dict[str, Any]) -> list[str]:
    required = ["machine", "grinder", "grind_setting", "roast_level", "taste"]
    optional = ["dose_g"]
    return [field for field in [*required, *optional] if shot_context.get(field) in (None, "")]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item).lower() for item in value)
    return str(value).lower()


def _contains_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
