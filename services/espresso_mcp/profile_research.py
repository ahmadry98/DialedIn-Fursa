"""Draft profile research workflow for unknown gear candidates.

This module does not mutate trusted machine/grinder profiles. It prepares a
research packet for an LLM/search worker and stores the reviewed draft back on
the candidate record.
"""

from __future__ import annotations

from typing import Any

from services.espresso_mcp import profile_candidates

MACHINE_REQUIRED_FIELDS = {
    "machine_name",
    "aliases",
    "specs",
    "brew_defaults",
    "grind_adjustment_notes",
    "sources",
}
MACHINE_SPEC_FIELDS = {"portafilter_mm", "pump_type", "pressure_type", "has_preinfusion"}
MACHINE_BREW_FIELDS = {"target_total_shot_seconds", "target_visible_flow_seconds", "typical_startup_delay_seconds"}
MACHINE_SOURCE_FIELDS = {"aliases", "portafilter_mm", "pump_type", "pressure_type", "has_preinfusion"}

GRINDER_REQUIRED_FIELDS = {
    "grinder_name",
    "aliases",
    "setting_type",
    "lower_is_finer",
    "small_step",
    "medium_step",
    "large_step",
    "min_setting",
    "max_setting",
    "espresso_range",
    "data_confidence",
    "notes",
    "source_urls",
}


def prepare_research_packet(candidate_key: str) -> dict[str, Any]:
    """Return the prompt and expected schema for one candidate."""
    candidate = _find_candidate(candidate_key)
    gear_type = candidate["type"]
    name = candidate["name_entered"]
    if gear_type == "machine":
        schema = _machine_schema()
    elif gear_type == "grinder":
        schema = _grinder_schema()
    else:
        raise ValueError("candidate type must be machine or grinder")

    return {
        "candidate_key": candidate_key,
        "type": gear_type,
        "name_entered": name,
        "status": candidate.get("status"),
        "instructions": _research_instructions(gear_type, name),
        "expected_schema": schema,
        "context": candidate.get("latest_context", {}),
    }


def attach_draft_profile(candidate_key: str, draft_profile: dict[str, Any], source_summary: str | None = None) -> dict[str, Any]:
    """Validate and attach an LLM-produced draft profile to a candidate."""
    candidates = profile_candidates.load_profile_candidates()
    for candidate in candidates:
        if candidate.get("candidate_key") == candidate_key:
            validation = validate_draft_profile(candidate["type"], draft_profile)
            candidate["draft_profile"] = draft_profile
            candidate["draft_validation"] = validation
            candidate["status"] = "draft_ready" if validation["is_valid"] else "draft_needs_review"
            if source_summary:
                candidate.setdefault("review_notes", []).append(source_summary)
            profile_candidates._write_candidates(candidates)  # type: ignore[attr-defined]
            return dict(candidate)
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def attach_research_evidence(candidate_key: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Store search/fetch evidence used to produce a draft profile."""
    candidates = profile_candidates.load_profile_candidates()
    for candidate in candidates:
        if candidate.get("candidate_key") == candidate_key:
            candidate["research_evidence"] = evidence
            profile_candidates._write_candidates(candidates)  # type: ignore[attr-defined]
            return dict(candidate)
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def validate_draft_profile(gear_type: str, draft_profile: dict[str, Any]) -> dict[str, Any]:
    """Validate draft shape before it can be reviewed and copied into profile JSON."""
    missing: list[str] = []
    warnings: list[str] = []

    if gear_type == "machine":
        missing.extend(_missing_keys(draft_profile, MACHINE_REQUIRED_FIELDS))
        specs = draft_profile.get("specs") if isinstance(draft_profile.get("specs"), dict) else {}
        brew = draft_profile.get("brew_defaults") if isinstance(draft_profile.get("brew_defaults"), dict) else {}
        sources = draft_profile.get("sources") if isinstance(draft_profile.get("sources"), dict) else {}
        missing.extend(f"specs.{field}" for field in _missing_keys(specs, MACHINE_SPEC_FIELDS))
        missing.extend(f"brew_defaults.{field}" for field in _missing_keys(brew, MACHINE_BREW_FIELDS))
        missing.extend(f"sources.{field}" for field in _missing_keys(sources, MACHINE_SOURCE_FIELDS))
        _warn_if_no_sources(sources, MACHINE_SOURCE_FIELDS, warnings)
    elif gear_type == "grinder":
        missing.extend(_missing_keys(draft_profile, GRINDER_REQUIRED_FIELDS))
        if not draft_profile.get("source_urls"):
            warnings.append("source_urls is empty")
    else:
        missing.append("unsupported candidate type")

    return {"is_valid": not missing, "missing_fields": missing, "warnings": warnings}


def _find_candidate(candidate_key: str) -> dict[str, Any]:
    for candidate in profile_candidates.load_profile_candidates():
        if candidate.get("candidate_key") == candidate_key:
            return candidate
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def _missing_keys(data: dict[str, Any], required: set[str]) -> list[str]:
    return sorted(field for field in required if field not in data)


def _warn_if_no_sources(sources: dict[str, Any], fields: set[str], warnings: list[str]) -> None:
    for field in sorted(fields):
        if not sources.get(field):
            warnings.append(f"sources.{field} is empty")


def _research_instructions(gear_type: str, name: str) -> str:
    if gear_type == "machine":
        return (
            "Use web search with official manufacturer pages and official manuals first. "
            "Retailer spec tables are allowed only when official sources do not provide a field. "
            "Do not guess unverifiable fields; use null or 'unknown'. "
            "Do not treat observed app context values, such as the current grind setting, as typical manufacturer data. "
            "For grind_adjustment_notes, avoid exact setting claims unless the evidence supports the setting range/direction. "
            "Return JSON only, matching expected_schema exactly. "
            f"Research espresso machine: {name}."
        )
    return (
        "Use official manufacturer pages/manuals first, then reputable grinder databases such as GrindDial or Coffee Chronicler. "
        "Do not guess direction/range if it cannot be supported; use conservative defaults with data_confidence 'D'. "
        "Return JSON only, matching expected_schema exactly. "
        f"Research espresso grinder: {name}."
    )


def _machine_schema() -> dict[str, Any]:
    return {
        "machine_name": "string",
        "aliases": ["string"],
        "specs": {
            "portafilter_mm": "number|null",
            "pump_type": "vibration|rotary|manual|unknown",
            "pressure_type": "string",
            "has_preinfusion": "boolean|null",
        },
        "brew_defaults": {
            "target_total_shot_seconds": [25, 32],
            "target_visible_flow_seconds": [20, 28],
            "typical_startup_delay_seconds": "[number, number]|null",
        },
        "grind_adjustment_notes": "string",
        "sources": {
            "aliases": ["url"],
            "portafilter_mm": ["url"],
            "pump_type": ["url"],
            "pressure_type": ["url"],
            "has_preinfusion": ["url"],
        },
    }


def _grinder_schema() -> dict[str, Any]:
    return {
        "grinder_name": "string",
        "aliases": ["string"],
        "setting_type": "numeric_integer|numeric_decimal",
        "lower_is_finer": "boolean",
        "small_step": "number",
        "medium_step": "number",
        "large_step": "number",
        "min_setting": "number|null",
        "max_setting": "number|null",
        "espresso_range": "[number, number]|null",
        "data_confidence": "A|B|C|D",
        "notes": "string",
        "source_urls": ["url"],
    }
