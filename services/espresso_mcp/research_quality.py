"""Quality scoring for researched espresso equipment draft profiles."""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 55


def evaluate_research_quality(gear_type: str, draft_profile: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return score and status recommendation for a drafted profile."""
    evidence = evidence or {}
    if gear_type == "machine":
        return _evaluate_machine(draft_profile, evidence)
    if gear_type == "grinder":
        return _evaluate_grinder(draft_profile, evidence)
    return {
        "score": 0,
        "status": "research_failed",
        "reasons": [],
        "warnings": ["Unsupported candidate type."],
        "threshold": READY_THRESHOLD,
    }


def status_for_quality(validation: dict[str, Any], quality: dict[str, Any]) -> str:
    """Map schema validation and quality score into candidate status."""
    if quality.get("status") == "research_failed":
        return "research_failed"
    if not validation.get("is_valid"):
        return "draft_needs_review"
    if int(quality.get("score", 0)) > READY_THRESHOLD:
        return "draft_ready"
    return "draft_needs_review"


def _evaluate_machine(draft: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    specs = draft.get("specs") if isinstance(draft.get("specs"), dict) else {}
    sources = draft.get("sources") if isinstance(draft.get("sources"), dict) else {}
    source_urls = _source_urls_from_machine_sources(sources)
    evidence_sources = evidence.get("sources") if isinstance(evidence.get("sources"), list) else []
    evidence_urls = [str(source.get("url", "")) for source in evidence_sources if isinstance(source, dict) and source.get("url")]
    all_urls = set(source_urls + evidence_urls)
    evidence_text = str(evidence.get("text", "")).lower()

    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    if draft.get("machine_name"):
        score += 8
        reasons.append("machine_name present")
    if draft.get("aliases"):
        score += 6
        reasons.append("aliases present")
    if specs.get("portafilter_mm") is not None:
        score += 15
        reasons.append("portafilter_mm verified")
    else:
        warnings.append("portafilter_mm is unknown")
    if specs.get("pump_type") not in (None, "", "unknown"):
        score += 10
        reasons.append("pump_type verified")
    else:
        warnings.append("pump_type is unknown")
    if specs.get("pressure_type") not in (None, "", "unknown"):
        score += 8
        reasons.append("pressure_type present")
    else:
        warnings.append("pressure_type is unknown")
    if specs.get("has_preinfusion") is not None:
        score += 8
        reasons.append("has_preinfusion verified")
    else:
        warnings.append("has_preinfusion is unknown")
    if specs.get("has_built_in_grinder") is not None:
        score += 5
        reasons.append("has_built_in_grinder verified")
    if draft.get("grind_adjustment_notes") not in (None, "", "unknown"):
        score += 4
        reasons.append("grind_adjustment_notes present")

    filled_source_fields = sum(1 for field in ["aliases", "portafilter_mm", "pump_type", "pressure_type", "has_preinfusion", "has_built_in_grinder"] if sources.get(field))
    if filled_source_fields:
        score += min(18, filled_source_fields * 3)
        reasons.append(f"{filled_source_fields} machine fields have source URLs")
    if all_urls:
        score += min(12, len(all_urls) * 3)
        reasons.append(f"{len(all_urls)} unique source URL(s) available")
    else:
        warnings.append("no source URLs found")

    if _has_official_source(all_urls):
        score += 12
        reasons.append("official/manufacturer evidence found")
    if any(url.lower().endswith(".pdf") for url in all_urls):
        score += 8
        reasons.append("PDF/manual evidence found")
    if any(term in evidence_text for term in ["lelit58", "dual boiler", "preinfusion", "pre-infusion", "pump", "manometer", "technical data"]):
        score += 8
        reasons.append("technical evidence text contains espresso-specific fields")

    score = max(0, min(100, score))
    if not all_urls:
        status = "research_failed"
    elif score > READY_THRESHOLD:
        status = "draft_ready"
    else:
        status = "draft_needs_review"
    return {"score": score, "status": status, "reasons": reasons, "warnings": warnings, "threshold": READY_THRESHOLD}


def _evaluate_grinder(draft: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    source_urls = [str(url) for url in draft.get("source_urls", []) if url]
    evidence_sources = evidence.get("sources") if isinstance(evidence.get("sources"), list) else []
    evidence_urls = [str(source.get("url", "")) for source in evidence_sources if isinstance(source, dict) and source.get("url")]
    all_urls = set(source_urls + evidence_urls)
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    if draft.get("grinder_name"):
        score += 8
    if draft.get("aliases"):
        score += 6
    if draft.get("lower_is_finer") is not None:
        score += 12
        reasons.append("grind direction verified")
    if draft.get("min_setting") is not None and draft.get("max_setting") is not None:
        score += 14
        reasons.append("setting range present")
    else:
        warnings.append("setting range incomplete")
    if draft.get("espresso_range"):
        score += 14
        reasons.append("espresso range present")
    if draft.get("small_step") is not None:
        score += 8
    if draft.get("data_confidence") not in (None, "", "D"):
        score += 6
    if all_urls:
        score += min(18, len(all_urls) * 4)
        reasons.append(f"{len(all_urls)} source URL(s) available")
    else:
        warnings.append("no source URLs found")
    if _has_official_source(all_urls):
        score += 14
        reasons.append("official/manufacturer evidence found")

    score = max(0, min(100, score))
    if not all_urls:
        status = "research_failed"
    elif score > READY_THRESHOLD:
        status = "draft_ready"
    else:
        status = "draft_needs_review"
    return {"score": score, "status": status, "reasons": reasons, "warnings": warnings, "threshold": READY_THRESHOLD}


def _source_urls_from_machine_sources(sources: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for value in sources.values():
        if isinstance(value, list):
            urls.extend(str(url) for url in value if url)
    return urls


def _has_official_source(urls: set[str]) -> bool:
    official_markers = [
        "breville.com",
        "lelit.com",
        "gaggia.com",
        "ranciliogroup",
        "lamarzocco",
        "delonghi.com",
        "profitec-espresso.com",
        "ecm.de",
        "rocket-espresso.com",
        "assets.breville.com",
        "variabrewing.com",
        "baratza.com",
        "eureka.co.it",
    ]
    return any(any(marker in url.lower() for marker in official_markers) for url in urls)
