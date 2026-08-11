"""LLM-assisted source discovery for profile research.

This step asks an LLM for likely official manufacturer domains, product pages,
manual/support URLs, and focused search queries. The web evidence collector still
confirms/fetches the sources before Bedrock extracts a profile, so discovery hints
are useful leads rather than trusted facts.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

DEFAULT_MODEL_ID = "bedrock/openai.gpt-oss-20b-1:0"
DEFAULT_REGION = "us-east-1"
DISCOVERY_SCHEMA = {
    "manufacturer": "string|null",
    "official_domains": ["domain"],
    "product_urls": ["url"],
    "manual_urls": ["url"],
    "support_urls": ["url"],
    "search_queries": ["string"],
    "confidence": "high|medium|low",
    "notes": "string",
}


def source_discovery_enabled(value: str | None = None) -> bool:
    raw = value if value is not None else os.getenv("PROFILE_RESEARCH_SOURCE_DISCOVERY", "true")
    return raw.lower() in {"1", "true", "yes", "on"}


def build_source_discovery_prompt(candidate: dict[str, Any]) -> str:
    """Build a JSON-only prompt for finding likely official source leads."""
    gear_type = str(candidate.get("type", "")).strip() or "gear"
    name = str(candidate.get("name_entered", "")).strip()
    context = candidate.get("latest_context", {}) if isinstance(candidate.get("latest_context"), dict) else {}
    return "\n\n".join(
        [
            "You are helping an espresso equipment profile research pipeline find source leads.",
            (
                "Return ONLY valid JSON. Do not wrap in markdown. Do not extract the final profile. "
                "Find likely official manufacturer domains and exact official product/manual/support URLs for the entered gear. "
                "Prefer the company that actually makes the product over lookalike domains, retailers, marketplaces, forums, or review sites. "
                "If you are not sure, leave URLs empty and set confidence to low."
            ),
            f"Gear type: {gear_type}",
            f"Entered name: {name}",
            "Observed app context for disambiguation only:",
            json.dumps(context, indent=2),
            "Expected JSON schema:",
            json.dumps(DISCOVERY_SCHEMA, indent=2),
        ]
    )


def discover_source_hints(
    candidate: dict[str, Any],
    *,
    model_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Ask Bedrock for source leads and return a normalized discovery packet."""
    prompt = build_source_discovery_prompt(candidate)
    response = call_bedrock_for_discovery(
        prompt,
        model_id=model_id or os.getenv("PROFILE_RESEARCH_DISCOVERY_MODEL") or os.getenv("MODEL") or os.getenv("BEDROCK_MODEL_ID") or DEFAULT_MODEL_ID,
        region=region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or DEFAULT_REGION,
    )
    return normalize_discovery_packet(response)


def call_bedrock_for_discovery(prompt: str, *, model_id: str, region: str) -> dict[str, Any]:
    """Call Bedrock Converse for the discovery JSON."""
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - environment setup concern.
        raise RuntimeError("Install boto3 to use source discovery.") from error

    bedrock_model_id = model_id.removeprefix("bedrock/")
    client = boto3.client("bedrock-runtime", region_name=region)
    converse_args: dict[str, Any] = {
        "modelId": bedrock_model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "maxTokens": 900},
    }
    if bedrock_model_id.startswith("openai."):
        converse_args["additionalModelRequestFields"] = {"reasoning_effort": "low"}
    response = client.converse(**converse_args)
    text = "".join(block.get("text", "") for block in response.get("output", {}).get("message", {}).get("content", []))
    if not text.strip():
        return {"confidence": "low", "notes": "Bedrock returned no source discovery text."}
    return parse_json_response(text)


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Source discovery response must be a JSON object")
    return parsed


def normalize_discovery_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Sanitize model output into predictable source-hint fields."""
    domains = _unique([_clean_domain(value) for value in _as_list(packet.get("official_domains"))])
    product_urls = _unique([_clean_url(value) for value in _as_list(packet.get("product_urls"))])
    manual_urls = _unique([_clean_url(value) for value in _as_list(packet.get("manual_urls"))])
    support_urls = _unique([_clean_url(value) for value in _as_list(packet.get("support_urls"))])
    queries = _unique([_clean_query(value) for value in _as_list(packet.get("search_queries"))])[:8]
    confidence = str(packet.get("confidence", "low")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {
        "manufacturer": _clean_text(packet.get("manufacturer")),
        "official_domains": domains,
        "product_urls": product_urls,
        "manual_urls": manual_urls,
        "support_urls": support_urls,
        "search_queries": queries,
        "confidence": confidence,
        "notes": _clean_text(packet.get("notes")),
    }


def discovery_urls(packet: dict[str, Any]) -> list[str]:
    return _unique([*packet.get("product_urls", []), *packet.get("manual_urls", []), *packet.get("support_urls", [])])


def discovery_domains(packet: dict[str, Any]) -> list[str]:
    domains = list(packet.get("official_domains", []))
    for url in discovery_urls(packet):
        domain = _clean_domain(urlparse(url).netloc)
        if domain:
            domains.append(domain)
    return _unique(domains)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _clean_url(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl()


def _clean_domain(value: Any) -> str:
    text = _clean_text(value).lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).netloc
    text = text.removeprefix("www.").strip("/ ")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", text):
        return ""
    return text


def _clean_query(value: Any) -> str:
    text = _clean_text(value)
    return text if 4 <= len(text) <= 180 else ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
