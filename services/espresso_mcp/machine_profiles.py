"""Machine profile lookup for espresso recommendations."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

PROFILE_PATH = Path(__file__).with_name("machine_profiles.json")
GENERIC_PROFILE_NAME = "Generic Espresso Machine"


def get_machine_profile(machine_name: str | None) -> dict[str, Any]:
    """Return the best matching machine profile, or the generic fallback."""
    profiles = load_machine_profiles()
    generic = _generic_profile(profiles)
    if not machine_name:
        return generic.copy()

    query = _normalize(machine_name)
    for profile in profiles:
        if _normalize(profile["machine_name"]) == query:
            return profile.copy()

    for profile in profiles:
        aliases = [_normalize(alias) for alias in profile.get("aliases", [])]
        if query in aliases:
            return profile.copy()

    for profile in profiles:
        names = [_normalize(profile["machine_name"]), *[_normalize(alias)
         for alias in profile.get("aliases", [])]]
        if any(query and (query in name or name in query) for name in names):
            return profile.copy()

    fuzzy_match = _best_fuzzy_profile_match(query, profiles)
    if fuzzy_match is not None:
        return fuzzy_match.copy()

    return generic.copy()


def get_machine_profile_by_slug(dialedin_slug: str | None) -> dict[str, Any]:
    """Return a machine profile linked to a DialedIN mobile machine slug."""
    profiles = load_machine_profiles()
    generic = _generic_profile(profiles)
    if not dialedin_slug:
        return generic.copy()

    query = _normalize_slug(dialedin_slug)
    for profile in profiles:
        if _normalize_slug(str(profile.get("dialedin_slug") or "")) == query:
            return profile.copy()
    return generic.copy()


def _best_fuzzy_profile_match(query: str, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a likely typo match while avoiding weak guesses."""
    query_value = query
    scores_by_profile: list[tuple[float, dict[str, Any]]] = []

    for profile in profiles:
        if profile.get("machine_name") == GENERIC_PROFILE_NAME:
            continue
        profile_best = 0.0
        for name in [profile.get("machine_name", ""), *profile.get("aliases", [])]:
            candidate = _normalize(name)
            if candidate:
                profile_best = max(profile_best,
                                    SequenceMatcher(None, query_value, candidate).ratio())
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

@lru_cache(maxsize=1)
def load_machine_profiles() -> list[dict[str, Any]]:
    """Load curated machine profiles from JSON."""
    with PROFILE_PATH.open(encoding="utf-8") as profile_file:
        profiles = json.load(profile_file)
    if not isinstance(profiles, list):
        raise ValueError("machine_profiles.json must contain a list of profiles")
    if not profiles:
        raise ValueError("machine_profiles.json must contain at least one profile")
    return profiles


def list_machine_profiles() -> list[dict[str, Any]]:
    """Return all curated profiles."""
    return [profile.copy() for profile in load_machine_profiles()]


def update_machine_profile_image(slug_or_alias: str, image: dict[str, Any]) -> dict[str, Any]:
    """Attach reviewed image metadata to a curated machine profile."""
    query_slug = _normalize_slug(slug_or_alias)
    profiles = load_machine_profiles()
    updated: dict[str, Any] | None = None

    for profile in profiles:
        names = [profile.get("machine_name", ""), str(profile.get("dialedin_slug") or ""), *profile.get("aliases", [])]
        if query_slug in {_normalize_slug(str(name)) for name in names if name}:
            profile["image"] = {key: value for key, value in image.items() if value is not None and value != ""}
            updated = profile.copy()
            break

    if updated is None or updated.get("machine_name") == GENERIC_PROFILE_NAME:
        raise ValueError(f"Machine profile not found: {slug_or_alias}")

    PROFILE_PATH.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    load_machine_profiles.cache_clear()
    return updated


def _generic_profile(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for profile in profiles:
        if profile.get("machine_name") == GENERIC_PROFILE_NAME:
            return profile
    raise ValueError("Generic Espresso Machine profile is required")


def _normalize(value: str) -> str:
    value = value.lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
