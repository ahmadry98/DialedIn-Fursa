"""Promote reviewed profile candidates into trusted profile JSON files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from services.espresso_mcp import grinder_profiles, machine_profiles, profile_candidates, profile_repository


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
        _require_reviewed_machine_image(draft, candidate_key)
        result = _upsert_profile(machine_profiles.PROFILE_PATH, draft, "machine_name", machine_profiles.GENERIC_PROFILE_NAME)
    elif candidate.get("type") == "grinder":
        result = _upsert_profile(grinder_profiles.PROFILE_PATH, draft, "grinder_name", grinder_profiles.GENERIC_GRINDER_NAME)
    else:
        raise ValueError("candidate type must be machine or grinder")

    remaining_candidates = [item for item in candidates if item.get("candidate_key") != candidate_key]
    profile_candidates._write_candidates(remaining_candidates)  # type: ignore[attr-defined]
    return {"candidate_key": candidate_key, "candidate_removed": True, **result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a reviewed profile candidate into trusted profile JSON.")
    parser.add_argument("candidate_key", help="Candidate key such as machine:meraki or grinder:kingrinder k6")
    args = parser.parse_args()
    print(json.dumps(promote_candidate(args.candidate_key), indent=2))


def _require_reviewed_machine_image(draft: dict[str, Any], candidate_key: str) -> None:
    image = draft.get("image")
    if not isinstance(image, dict):
        raise ValueError(f"Machine candidate {candidate_key} needs a reviewed image before promotion")
    if image.get("status") != "reviewed":
        raise ValueError(f"Machine candidate {candidate_key} image must be reviewed before promotion")
    if not any(image.get(key) for key in ("media_key", "url", "local_asset_key")):
        raise ValueError(f"Machine candidate {candidate_key} image needs media_key, url, or local_asset_key before promotion")


def _find_candidate(candidates: list[dict[str, Any]], candidate_key: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate.get("candidate_key") == candidate_key:
            return candidate
    raise ValueError(f"Unknown candidate_key: {candidate_key}")


def _upsert_profile(path: Path, draft: dict[str, Any], name_field: str, generic_name: str) -> dict[str, Any]:
    profile_type = "machine" if name_field == "machine_name" else "grinder"
    return profile_repository.upsert_profile(
        profile_type=profile_type,
        json_path=path,
        draft=draft,
        name_field=name_field,
        generic_name=generic_name,
        normalize=_normalize,
    )


def _normalize(value: Any) -> str:
    value = str(value).lower().replace("de'longhi", "delonghi")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


if __name__ == "__main__":
    main()
