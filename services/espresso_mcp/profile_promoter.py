"""Promote reviewed profile candidates into trusted profile JSON files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from services.espresso_mcp import grinder_profiles, machine_profiles, profile_candidates


def promote_candidate(candidate_key: str) -> dict[str, Any]:
    """Copy a reviewed draft profile into the trusted machine/grinder profiles file."""
    candidates = profile_candidates.load_profile_candidates()
    candidate = _find_candidate(candidates, candidate_key)
    draft = candidate.get("draft_profile")
    if not isinstance(draft, dict):
        raise ValueError(f"Candidate {candidate_key} does not have a draft_profile")
    if candidate.get("status") not in {"draft_ready", "draft_needs_review", "promoted"}:
        raise ValueError(f"Candidate {candidate_key} is not ready for promotion")

    if candidate.get("type") == "machine":
        result = _upsert_profile(machine_profiles.PROFILE_PATH, draft, "machine_name", machine_profiles.GENERIC_PROFILE_NAME)
    elif candidate.get("type") == "grinder":
        result = _upsert_profile(grinder_profiles.PROFILE_PATH, draft, "grinder_name", grinder_profiles.GENERIC_GRINDER_NAME)
    else:
        raise ValueError("candidate type must be machine or grinder")

    candidate["status"] = "promoted"
    candidate.setdefault("review_notes", []).append(f"Promoted into {result['path']}.")
    profile_candidates._write_candidates(candidates)  # type: ignore[attr-defined]
    return {"candidate_key": candidate_key, **result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a reviewed profile candidate into trusted profile JSON.")
    parser.add_argument("candidate_key", help="Candidate key such as machine:meraki or grinder:kingrinder k6")
    args = parser.parse_args()
    print(json.dumps(promote_candidate(args.candidate_key), indent=2))


def _find_candidate(candidates: list[dict[str, Any]], candidate_key: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate.get("candidate_key") == candidate_key:
            return candidate
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def _upsert_profile(path: Path, draft: dict[str, Any], name_field: str, generic_name: str) -> dict[str, Any]:
    profiles = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profiles, list):
        raise ValueError(f"{path.name} must contain a list")

    draft_names = _profile_names(draft, name_field)
    for index, profile in enumerate(profiles):
        if not _profile_names(profile, name_field).isdisjoint(draft_names):
            profiles[index] = draft
            path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
            return {"status": "updated", "path": str(path), "profile_name": draft.get(name_field)}

    insert_at = next((index for index, profile in enumerate(profiles) if profile.get(name_field) == generic_name), len(profiles))
    profiles.insert(insert_at, draft)
    path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    return {"status": "inserted", "path": str(path), "profile_name": draft.get(name_field)}


def _profile_names(profile: dict[str, Any], name_field: str) -> set[str]:
    names = {_normalize(profile.get(name_field, ""))}
    names.update(_normalize(alias) for alias in profile.get("aliases", []))
    return {name for name in names if name}


def _normalize(value: Any) -> str:
    value = str(value).lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


if __name__ == "__main__":
    main()
