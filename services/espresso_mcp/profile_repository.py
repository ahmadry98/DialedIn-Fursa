"""Repository helpers for trusted equipment profiles.

DynamoDB is the project default when a profile table is configured. JSON
remains available as an explicit local/test fallback by setting
DIALEDIN_PROFILE_STORAGE=json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROFILE_TYPE_NAMES = {"machine", "grinder"}


def load_profiles(profile_type: str, json_path: Path) -> list[dict[str, Any]]:
    """Load trusted profiles from the configured backend."""
    _validate_profile_type(profile_type)
    if _storage_mode() == "dynamodb":
        return _load_profiles_dynamodb(profile_type)
    return load_profiles_json(json_path)


def save_profiles(profile_type: str, profiles: list[dict[str, Any]], json_path: Path) -> None:
    """Persist trusted profiles to the configured backend and optional JSON seed."""
    _validate_profile_type(profile_type)
    if _storage_mode() == "dynamodb":
        _save_profiles_dynamodb(profile_type, profiles)
        if _sync_json_enabled():
            save_profiles_json(json_path, profiles)
        return
    save_profiles_json(json_path, profiles)


def upsert_profile(
    *,
    profile_type: str,
    json_path: Path,
    draft: dict[str, Any],
    name_field: str,
    generic_name: str,
    normalize,
) -> dict[str, Any]:
    """Insert or update one trusted profile while preserving generic fallback order."""
    profiles = load_profiles(profile_type, json_path)
    if not isinstance(profiles, list):
        raise ValueError(f"{json_path.name} must contain a list")

    draft_names = _profile_names(draft, name_field, normalize)
    for index, profile in enumerate(profiles):
        if not _profile_names(profile, name_field, normalize).isdisjoint(draft_names):
            profiles[index] = draft
            save_profiles(profile_type, profiles, json_path)
            return {"status": "updated", "path": _storage_target(json_path), "profile_name": draft.get(name_field)}

    insert_at = next((index for index, profile in enumerate(profiles) if profile.get(name_field) == generic_name), len(profiles))
    profiles.insert(insert_at, draft)
    save_profiles(profile_type, profiles, json_path)
    return {"status": "inserted", "path": _storage_target(json_path), "profile_name": draft.get(name_field)}


def load_profiles_json(json_path: Path) -> list[dict[str, Any]]:
    with json_path.open(encoding="utf-8") as profile_file:
        profiles = json.load(profile_file)
    if not isinstance(profiles, list):
        raise ValueError(f"{json_path.name} must contain a list")
    return profiles


def save_profiles_json(json_path: Path, profiles: list[dict[str, Any]]) -> None:
    json_path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")


def _load_profiles_dynamodb(profile_type: str) -> list[dict[str, Any]]:
    table = _dynamodb_table()
    try:
        from boto3.dynamodb.conditions import Key
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use DynamoDB profile storage.") from error

    response = table.query(KeyConditionExpression=Key("profile_type").eq(profile_type))
    profiles = [_profile_from_item(item) for item in response.get("Items", [])]
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=Key("profile_type").eq(profile_type),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        profiles.extend(_profile_from_item(item) for item in response.get("Items", []))
    return sorted(profiles, key=lambda profile: str(profile.get("machine_name") or profile.get("grinder_name") or "").lower())


def _save_profiles_dynamodb(profile_type: str, profiles: list[dict[str, Any]]) -> None:
    table = _dynamodb_table()
    with table.batch_writer() as batch:
        for profile in profiles:
            batch.put_item(Item=_item_from_profile(profile_type, profile))


def _dynamodb_table():
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use DynamoDB profile storage.") from error

    table_name = os.getenv("DIALEDIN_PROFILE_TABLE") or os.getenv("DIALEDIN_PROFILE_TABLE_NAME")
    if not table_name:
        raise RuntimeError("DIALEDIN_PROFILE_TABLE is required when DIALEDIN_PROFILE_STORAGE=dynamodb")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    return boto3.resource("dynamodb", region_name=region).Table(table_name)


def _item_from_profile(profile_type: str, profile: dict[str, Any]) -> dict[str, Any]:
    profile_id = _profile_id(profile_type, profile)
    return {
        "profile_type": profile_type,
        "profile_id": profile_id,
        "slug": str(profile.get("dialedin_slug") or profile_id),
        "profile_json": json.dumps(profile, sort_keys=True),
    }


def _profile_from_item(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("profile_json")
    if isinstance(raw, str):
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    data = item.get("profile")
    if isinstance(data, dict):
        return dict(data)
    raise ValueError("DynamoDB profile item is missing profile_json")


def _profile_id(profile_type: str, profile: dict[str, Any]) -> str:
    name = profile.get("machine_name") if profile_type == "machine" else profile.get("grinder_name")
    return _slug(str(profile.get("dialedin_slug") or name or "profile"))


def _profile_names(profile: dict[str, Any], name_field: str, normalize) -> set[str]:
    names = {normalize(profile.get(name_field, ""))}
    names.update(normalize(alias) for alias in profile.get("aliases", []))
    return {name for name in names if name}


def _storage_mode() -> str:
    explicit_mode = os.getenv("DIALEDIN_PROFILE_STORAGE")
    if explicit_mode:
        return explicit_mode.lower()
    if os.getenv("DIALEDIN_PROFILE_TABLE") or os.getenv("DIALEDIN_PROFILE_TABLE_NAME"):
        return "dynamodb"
    return "json"


def _storage_target(json_path: Path) -> str:
    if _storage_mode() == "dynamodb":
        table = os.getenv("DIALEDIN_PROFILE_TABLE") or os.getenv("DIALEDIN_PROFILE_TABLE_NAME") or "dynamodb"
        return f"{table} + {json_path}" if _sync_json_enabled() else table
    return str(json_path)


def _sync_json_enabled() -> bool:
    value = os.getenv("DIALEDIN_PROFILE_SYNC_JSON", "true").lower()
    return value in {"1", "true", "yes", "on"}


def _validate_profile_type(profile_type: str) -> None:
    if profile_type not in PROFILE_TYPE_NAMES:
        raise ValueError("profile_type must be 'machine' or 'grinder'")


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
