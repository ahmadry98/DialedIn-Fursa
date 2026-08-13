"""Mobile-safe equipment profile API formatting."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from services.espresso_mcp import grinder_profiles, machine_profiles


def list_machines(*, media_cdn_base_url: str | None = None) -> list[dict[str, Any]]:
    profiles = [profile for profile in machine_profiles.list_machine_profiles() if profile.get("machine_name") != machine_profiles.GENERIC_PROFILE_NAME]
    return sorted(
        (_machine_summary(profile, media_cdn_base_url=media_cdn_base_url) for profile in profiles),
        key=lambda item: item["display_name"].lower(),
    )


def get_machine(slug_or_alias: str, *, media_cdn_base_url: str | None = None) -> dict[str, Any]:
    profile = _machine_by_slug_or_alias(slug_or_alias)
    if profile.get("machine_name") == machine_profiles.GENERIC_PROFILE_NAME:
        raise ValueError(f"Machine profile not found: {slug_or_alias}")
    return _machine_detail(profile, media_cdn_base_url=media_cdn_base_url)


def list_grinders() -> list[dict[str, Any]]:
    profiles = [profile for profile in grinder_profiles.list_grinder_profiles() if profile.get("grinder_name") != grinder_profiles.GENERIC_GRINDER_NAME]
    return sorted((_grinder_summary(profile) for profile in profiles), key=lambda item: item["display_name"].lower())


def get_grinder(slug_or_alias: str) -> dict[str, Any]:
    profile = _grinder_by_slug_or_alias(slug_or_alias)
    if profile.get("grinder_name") == grinder_profiles.GENERIC_GRINDER_NAME:
        raise ValueError(f"Grinder profile not found: {slug_or_alias}")
    return _grinder_detail(profile)


def _machine_by_slug_or_alias(value: str) -> dict[str, Any]:
    query_slug = _slug(value)
    for profile in machine_profiles.list_machine_profiles():
        names = [profile.get("machine_name", ""), str(profile.get("dialedin_slug") or ""), *profile.get("aliases", [])]
        if query_slug in {_slug(name) for name in names if name}:
            return profile
    return machine_profiles.get_machine_profile(value)


def _grinder_by_slug_or_alias(value: str) -> dict[str, Any]:
    query_slug = _slug(value)
    for profile in grinder_profiles.list_grinder_profiles():
        names = [profile.get("grinder_name", ""), *profile.get("aliases", [])]
        if query_slug in {_slug(name) for name in names if name}:
            return profile
    return grinder_profiles.get_grinder_profile(value)


def _machine_summary(profile: dict[str, Any], *, media_cdn_base_url: str | None = None) -> dict[str, Any]:
    specs = profile.get("specs", {})
    brew_defaults = profile.get("brew_defaults", {})
    name = str(profile.get("machine_name") or "Unknown machine")
    slug = str(profile.get("dialedin_slug") or _slug(name))
    portafilter = specs.get("portafilter_mm")
    has_grinder = specs.get("has_built_in_grinder")
    tags = []
    if portafilter:
        tags.append(f"{portafilter}mm")
    if has_grinder is True:
        tags.append("Built-in grinder")
    elif has_grinder is False:
        tags.append("External grinder")
    if specs.get("has_preinfusion") is True:
        tags.append("Pre-infusion")

    return {
        "slug": slug,
        "display_name": name,
        "name": name,
        "subtitle": _machine_subtitle(specs),
        "aliases": profile.get("aliases", []),
        "tags": tags[:3],
        "has_image": _has_profile_image(profile),
        "image": profile.get("image") or None,
        "image_url": _profile_image_url(profile, media_cdn_base_url=media_cdn_base_url),
        "specs": specs,
        "brew_defaults": brew_defaults,
    }


def _machine_detail(profile: dict[str, Any], *, media_cdn_base_url: str | None = None) -> dict[str, Any]:
    summary = _machine_summary(profile, media_cdn_base_url=media_cdn_base_url)
    summary.update(
        {
            "grind_adjustment_notes": profile.get("grind_adjustment_notes"),
            "sources": profile.get("sources", {}),
        }
    )
    return summary


def _grinder_summary(profile: dict[str, Any]) -> dict[str, Any]:
    name = str(profile.get("grinder_name") or "Unknown grinder")
    espresso_range = profile.get("espresso_range")
    tags = []
    if profile.get("setting_type") == "numeric_integer":
        tags.append("Stepped")
    elif profile.get("setting_type") == "numeric_decimal":
        tags.append("Numeric")
    if espresso_range:
        tags.append(f"Espresso {espresso_range[0]}-{espresso_range[1]}")
    if profile.get("data_confidence"):
        tags.append(f"Data {profile['data_confidence']}")

    return {
        "slug": _slug(name),
        "display_name": name,
        "name": name,
        "aliases": profile.get("aliases", []),
        "tags": tags[:3],
        "setting_type": profile.get("setting_type"),
        "lower_is_finer": profile.get("lower_is_finer"),
        "min_setting": profile.get("min_setting"),
        "max_setting": profile.get("max_setting"),
        "espresso_range": espresso_range,
        "data_confidence": profile.get("data_confidence"),
        "small_step": profile.get("small_step"),
        "medium_step": profile.get("medium_step"),
        "large_step": profile.get("large_step"),
        "notes": profile.get("notes"),
    }


def _grinder_detail(profile: dict[str, Any]) -> dict[str, Any]:
    summary = _grinder_summary(profile)
    summary.update(
        {
            "small_step": profile.get("small_step"),
            "medium_step": profile.get("medium_step"),
            "large_step": profile.get("large_step"),
            "seconds_per_small_step_estimate": profile.get("seconds_per_small_step_estimate"),
            "notes": profile.get("notes"),
            "source_urls": profile.get("source_urls", []),
        }
    )
    return summary


def _profile_image_url(profile: dict[str, Any], *, media_cdn_base_url: str | None = None) -> str | None:
    image = _reviewed_profile_image(profile)
    if image is None:
        return None
    if image.get("url"):
        return str(image["url"])
    if image.get("storage_mode") == "s3" and image.get("media_key"):
        media_key = str(image["media_key"]).lstrip("/")
        if media_cdn_base_url and "/machine_photo/" in f"/{media_key}":
            return f"{media_cdn_base_url.rstrip('/')}/{quote(media_key, safe='/')}"
        slug = str(profile.get("dialedin_slug") or _slug(str(profile.get("machine_name") or "")))
        return f"/machines/{slug}/image"
    return None


def _has_profile_image(profile: dict[str, Any]) -> bool:
    image = _reviewed_profile_image(profile)
    return image is not None and bool(image.get("url") or image.get("local_asset_key") or image.get("media_key"))


def _reviewed_profile_image(profile: dict[str, Any]) -> dict[str, Any] | None:
    image = profile.get("image")
    if not isinstance(image, dict):
        return None
    if image.get("status") != "reviewed":
        return None
    return image


def _machine_subtitle(specs: dict[str, Any]) -> str:
    parts = []
    portafilter = specs.get("portafilter_mm")
    if portafilter:
        parts.append(f"{portafilter}mm")
    pump_type = specs.get("pump_type")
    if pump_type and pump_type != "unknown":
        parts.append(str(pump_type).title())
    if specs.get("has_built_in_grinder") is True:
        parts.append("Built-in grinder")
    return " · ".join(parts) if parts else "Espresso machine"


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
