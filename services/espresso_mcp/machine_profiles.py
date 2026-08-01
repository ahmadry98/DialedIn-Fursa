"""Machine profile lookup for espresso recommendations."""

from __future__ import annotations

import json
import re
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
        names = [_normalize(profile["machine_name"]), *[_normalize(alias) for alias in profile.get("aliases", [])]]
        if any(query and (query in name or name in query) for name in names):
            return profile.copy()

    return generic.copy()


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


def _generic_profile(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for profile in profiles:
        if profile.get("machine_name") == GENERIC_PROFILE_NAME:
            return profile
    raise ValueError("Generic Espresso Machine profile is required")


def _normalize(value: str) -> str:
    value = value.lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
