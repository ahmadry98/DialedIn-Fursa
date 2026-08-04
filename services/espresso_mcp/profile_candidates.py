"""Capture unknown machine/grinder profile candidates for later research."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.espresso_mcp import grinder_profiles, machine_profiles

CANDIDATES_PATH = Path(__file__).with_name("profile_candidates.json")


def capture_unknown_gear(user_id: str, machine: str | None, grinder: str | None, shot_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Save plausible unknown machine/grinder names as reviewable profile candidates."""
    candidates: list[dict[str, Any]] = []
    if _is_unknown_machine(machine) and is_plausible_gear_name("machine", machine):
        candidates.append(save_profile_candidate("machine", machine or "", user_id, shot_context))
    if _is_unknown_grinder(grinder) and is_plausible_gear_name("grinder", grinder):
        candidates.append(save_profile_candidate("grinder", grinder or "", user_id, shot_context))
    return candidates



def is_plausible_gear_name(gear_type: str, name_entered: str | None) -> bool:
    """Reject obvious nonsense before creating automatic profile candidates."""
    if gear_type not in {"machine", "grinder"}:
        raise ValueError("gear_type must be 'machine' or 'grinder'")

    normalized = _normalize_candidate_name(name_entered)
    if not normalized:
        return False

    compact = normalized.replace(" ", "")
    if len(compact) < 5:
        return False
    if len(compact) > 60:
        return False
    if not any(character.isalpha() for character in compact):
        return False

    tokens = normalized.split()
    if any(token in _KNOWN_BRAND_OR_MODEL_TOKENS for token in tokens):
        return True
    if any(any(character.isdigit() for character in token) and any(character.isalpha() for character in token) for token in tokens):
        return True
    if len(tokens) >= 2 and all(len(token) >= 2 for token in tokens):
        return True
    if len(tokens) >= 3 and len(tokens[-1]) == 1 and all(len(token) >= 2 for token in tokens[:-1]):
        return True
    if _looks_like_random_text(compact):
        return False
    if len(compact) >= 8:
        return True
    return False


_KNOWN_BRAND_OR_MODEL_TOKENS = {
    "1zpresso",
    "acs",
    "anita",
    "ascaso",
    "baratza",
    "bezzera",
    "breville",
    "casabrews",
    "comandante",
    "dedica",
    "delonghi",
    "df54",
    "df64",
    "ecm",
    "eureka",
    "flair",
    "gaggia",
    "gevi",
    "kingrinder",
    "kinu",
    "la",
    "lelit",
    "marzocco",
    "mignon",
    "niche",
    "pavoni",
    "profitec",
    "quick",
    "rancilio",
    "rocket",
    "silvia",
    "timemore",
    "turin",
    "varia",
}


def _normalize_candidate_name(value: str | None) -> str:
    if value is None:
        return ""
    value = value.lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_random_text(compact: str) -> bool:
    if not compact.isalpha():
        return False
    vowels = sum(1 for character in compact if character in "aeiou")
    vowel_ratio = vowels / len(compact)
    consonant_runs = re.findall(r"[bcdfghjklmnpqrstvwxyz]{4,}", compact)
    return vowel_ratio < 0.2 or bool(consonant_runs)

def save_profile_candidate(gear_type: str, name_entered: str, user_id: str, shot_context: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a candidate without duplicating same type/name pairs."""
    if gear_type not in {"machine", "grinder"}:
        raise ValueError("gear_type must be 'machine' or 'grinder'")
    cleaned_name = " ".join(name_entered.split())
    if not cleaned_name:
        raise ValueError("name_entered is required")

    candidates = load_profile_candidates()
    key = _candidate_key(gear_type, cleaned_name)
    now = _now()
    snapshot = _context_snapshot(shot_context)

    for candidate in candidates:
        if candidate.get("candidate_key") == key:
            candidate["last_seen_at"] = now
            candidate["seen_count"] = int(candidate.get("seen_count", 1)) + 1
            if user_id and user_id not in candidate.setdefault("user_ids", []):
                candidate["user_ids"].append(user_id)
            candidate["latest_context"] = snapshot
            _write_candidates(candidates)
            return dict(candidate)

    candidate = {
        "candidate_key": key,
        "type": gear_type,
        "name_entered": cleaned_name,
        "status": "needs_research",
        "created_at": now,
        "last_seen_at": now,
        "seen_count": 1,
        "user_ids": [user_id] if user_id else [],
        "latest_context": snapshot,
        "research_prompt": build_research_prompt(gear_type, cleaned_name),
        "draft_profile": None,
        "review_notes": [],
    }
    candidates.append(candidate)
    _write_candidates(candidates)
    return dict(candidate)


def load_profile_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES_PATH.exists():
        return []
    with CANDIDATES_PATH.open(encoding="utf-8") as candidates_file:
        data = json.load(candidates_file)
    if not isinstance(data, list):
        raise ValueError("profile_candidates.json must contain a list")
    return data


def add_profile_candidate_note(candidate_key: str, note: str) -> None:
    candidates = load_profile_candidates()
    for candidate in candidates:
        if candidate.get("candidate_key") == candidate_key:
            candidate.setdefault("review_notes", []).append(note)
            _write_candidates(candidates)
            return
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def update_profile_candidate(
    candidate_key: str,
    *,
    draft_profile: dict[str, Any] | None = None,
    review_notes: list[str] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Update reviewable candidate fields from the admin UI."""
    candidates = load_profile_candidates()
    for candidate in candidates:
        if candidate.get("candidate_key") != candidate_key:
            continue
        if draft_profile is not None:
            candidate["draft_profile"] = draft_profile
        if review_notes is not None:
            candidate["review_notes"] = [str(note) for note in review_notes if str(note).strip()]
        if status is not None:
            candidate["status"] = status
        _write_candidates(candidates)
        return dict(candidate)
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def delete_profile_candidate(candidate_key: str) -> dict[str, Any]:
    """Remove a candidate from the review queue."""
    candidates = load_profile_candidates()
    remaining = [candidate for candidate in candidates if candidate.get("candidate_key") != candidate_key]
    if len(remaining) == len(candidates):
        raise ValueError(f"Unknown candidate_key: {candidate_key}")
    _write_candidates(remaining)
    return {"candidate_key": candidate_key, "deleted": True}


def build_research_prompt(gear_type: str, name_entered: str) -> str:
    if gear_type == "machine":
        return (
            "Search official manufacturer pages and manuals for this espresso machine. "
            "Extract aliases, portafilter size, pump type, pressure/preinfusion behavior, and source URLs. "
            f"Return a draft machine profile JSON for: {name_entered}."
        )
    return (
        "Search official manufacturer pages, manuals, and reputable grinder databases for this grinder. "
        "Extract aliases, setting type, finer direction, min/max setting, espresso range, step size, and source URLs. "
        f"Return a draft grinder profile JSON for: {name_entered}."
    )


def _is_unknown_machine(machine: str | None) -> bool:
    if not machine:
        return False
    return machine_profiles.get_machine_profile(machine).get("machine_name") == machine_profiles.GENERIC_PROFILE_NAME


def _is_unknown_grinder(grinder: str | None) -> bool:
    if not grinder:
        return False
    return grinder_profiles.get_grinder_profile(grinder).get("grinder_name") == grinder_profiles.GENERIC_GRINDER_NAME


def _context_snapshot(shot_context: dict[str, Any]) -> dict[str, Any]:
    fields = ["machine", "grinder", "dose_g", "yield_g", "grind_setting", "roast_level", "taste", "total_shot_seconds"]
    return {field: shot_context.get(field) for field in fields if shot_context.get(field) not in (None, "")}


def _candidate_key(gear_type: str, name_entered: str) -> str:
    normalized = " ".join(name_entered.lower().replace("-", " ").split())
    return f"{gear_type}:{normalized}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_candidates(candidates: list[dict[str, Any]]) -> None:
    CANDIDATES_PATH.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
