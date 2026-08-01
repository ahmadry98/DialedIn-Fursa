"""Run profile candidate research through Amazon Bedrock.

Bedrock drafts profiles from a research packet plus optional evidence text. The
worker intentionally writes drafts back to profile_candidates.json for review;
it never edits trusted machine_profiles.json or grinder_profiles.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from services.espresso_mcp import profile_candidates, profile_research, profile_web_evidence

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience dependency.
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv is not None:
    load_dotenv()
    load_dotenv(Path(__file__).with_name(".env"))

DEFAULT_MODEL_ID = "bedrock/openai.gpt-oss-20b-1:0"
DEFAULT_REGION = "us-east-1"


def run_worker(
    *,
    candidate_key: str | None = None,
    evidence_dir: Path | None = None,
    model_id: str | None = None,
    region: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    web_evidence: bool | None = None,
) -> list[dict[str, Any]]:
    """Process queued profile candidates and return worker results."""
    candidates = _select_candidates(candidate_key, limit)
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        packet = profile_research.prepare_research_packet(candidate["candidate_key"])
        file_evidence = _load_evidence(evidence_dir, candidate) if evidence_dir else ""
        web_packet = _collect_web_evidence(candidate) if _web_evidence_enabled(web_evidence) else {"sources": [], "text": ""}
        evidence = _join_evidence(file_evidence, web_packet.get("text", ""))
        if web_packet.get("sources"):
            profile_research.attach_research_evidence(candidate["candidate_key"], web_packet)
        prompt = build_bedrock_prompt(packet, evidence)

        if dry_run:
            results.append(
                {
                    "candidate_key": candidate["candidate_key"],
                    "status": "dry_run",
                    "prompt": prompt,
                    "evidence_found": bool(evidence),
                    "evidence_sources": web_packet.get("sources", []),
                }
            )
            continue

        try:
            draft = call_bedrock_for_draft(
                prompt,
                model_id=model_id or os.getenv("MODEL") or os.getenv("BEDROCK_MODEL_ID") or DEFAULT_MODEL_ID,
                region=region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or DEFAULT_REGION,
            )
            updated = profile_research.attach_draft_profile(
                candidate["candidate_key"],
                draft,
                _source_summary(web_packet),
            )
            results.append(
                {
                    "candidate_key": candidate["candidate_key"],
                    "status": updated["status"],
                    "validation": updated.get("draft_validation"),
                }
            )
        except Exception as error:
            note = f"Profile research failed during Bedrock draft step: {type(error).__name__}: {error}"
            profile_candidates.add_profile_candidate_note(candidate["candidate_key"], note)
            raise RuntimeError(f"{candidate['candidate_key']}: {note}") from error

    return results


def build_bedrock_prompt(packet: dict[str, Any], evidence: str = "") -> str:
    """Build the final JSON-only prompt sent to Bedrock."""
    evidence_block = evidence.strip() or "No source evidence was provided. Use unknown/null for unverifiable fields and cite only URLs present in the evidence."
    return "\n\n".join(
        [
            "You are creating a draft espresso equipment profile for human review.",
            packet["instructions"],
            "Return ONLY valid JSON. Do not wrap it in markdown. Do not include commentary.",
            "Expected schema:",
            json.dumps(packet["expected_schema"], indent=2),
            "Observed app context for disambiguation only. Do not convert user-entered values into manufacturer facts:",
            json.dumps(packet.get("context", {}), indent=2),
            "Source evidence:",
            evidence_block,
        ]
    )


def call_bedrock_for_draft(prompt: str, *, model_id: str, region: str) -> dict[str, Any]:
    """Call Amazon Bedrock Converse and parse a JSON draft profile."""
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - covered by environment setup, not unit behavior.
        raise RuntimeError("Install boto3 with `python -m pip install boto3` or `pip install -r services/espresso_mcp/requirements.txt`.") from error

    bedrock_model_id = normalize_bedrock_model_id(model_id)
    client = boto3.client("bedrock-runtime", region_name=region)
    converse_args: dict[str, Any] = {
        "modelId": bedrock_model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "maxTokens": 2500},
    }
    extra_fields = additional_model_request_fields(model_id)
    if extra_fields:
        converse_args["additionalModelRequestFields"] = extra_fields
    response = client.converse(**converse_args)
    text = _bedrock_response_text(response)
    if not text.strip():
        stop_reason = response.get("stopReason", "unknown")
        usage = response.get("usage", {})
        content = response.get("output", {}).get("message", {}).get("content", [])
        raise ValueError(
            "Bedrock returned empty text; "
            f"stopReason={stop_reason}; usage={usage}; content_keys={_content_keys(content)}"
        )
    try:
        return parse_json_response(text)
    except Exception as error:
        preview = text[:500].replace("\n", " ")
        raise ValueError(f"Bedrock returned non-JSON text: {preview!r}") from error


def _content_keys(content: Any) -> list[list[str]]:
    if not isinstance(content, list):
        return []
    return [sorted(block.keys()) for block in content if isinstance(block, dict)]


def normalize_bedrock_model_id(model_id: str) -> str:
    """Support PolyAI-style MODEL values like bedrock/openai.gpt-oss-20b-1:0."""
    return model_id.removeprefix("bedrock/")


def additional_model_request_fields(model_id: str) -> dict[str, Any]:
    """Mirror PolyAI's extra Bedrock options for OpenAI OSS models."""
    normalized = normalize_bedrock_model_id(model_id)
    if normalized.startswith("openai."):
        return {"reasoning_effort": "low"}
    return {}


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, tolerating accidental fences."""
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
        raise ValueError("Bedrock response must be a JSON object")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Research unknown espresso gear profile candidates with Bedrock.")
    parser.add_argument("--candidate-key", help="Process one candidate key instead of every needs_research candidate.")
    parser.add_argument("--evidence-dir", type=Path, help="Directory of evidence .txt/.md files named after candidate keys.")
    parser.add_argument("--model-id", help=f"Bedrock model ID. Defaults to MODEL, BEDROCK_MODEL_ID, or {DEFAULT_MODEL_ID}.")
    parser.add_argument("--region", help=f"AWS region. Defaults to AWS_REGION/AWS_DEFAULT_REGION or {DEFAULT_REGION}.")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling Bedrock.")
    parser.add_argument("--limit", type=int, help="Maximum number of needs_research candidates to process.")
    parser.add_argument("--no-web-evidence", action="store_true", help="Skip automatic web search/fetch evidence collection.")
    args = parser.parse_args()

    results = run_worker(
        candidate_key=args.candidate_key,
        evidence_dir=args.evidence_dir,
        model_id=args.model_id,
        region=args.region,
        dry_run=args.dry_run,
        limit=args.limit,
        web_evidence=not args.no_web_evidence,
    )
    print(json.dumps(results, indent=2))


def _web_evidence_enabled(web_evidence: bool | None) -> bool:
    if web_evidence is not None:
        return web_evidence
    value = os.getenv("PROFILE_RESEARCH_WEB_EVIDENCE", "true").lower()
    return value in {"1", "true", "yes", "on"}


def _collect_web_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    try:
        return profile_web_evidence.collect_web_evidence(candidate)
    except Exception as error:
        return {"sources": [], "text": f"Web evidence collection failed: {error}"}


def _join_evidence(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _source_summary(web_packet: dict[str, Any]) -> str:
    sources = web_packet.get("sources") or []
    if not sources:
        return "Draft generated by Bedrock profile research worker without web evidence."
    urls = [str(source.get("url", "")) for source in sources if source.get("url")]
    return "Draft generated by Bedrock profile research worker using web evidence: " + ", ".join(urls[:4])


def _select_candidates(candidate_key: str | None, limit: int | None) -> list[dict[str, Any]]:
    candidates = profile_candidates.load_profile_candidates()
    if candidate_key:
        selected = [candidate for candidate in candidates if candidate.get("candidate_key") == candidate_key]
        if not selected:
            raise ValueError(f"Unknown candidate_key: {candidate_key}")
        return selected

    selected = [candidate for candidate in candidates if candidate.get("status") == "needs_research"]
    return selected[:limit] if limit else selected


def _load_evidence(evidence_dir: Path, candidate: dict[str, Any]) -> str:
    base = _candidate_file_stem(candidate["candidate_key"])
    chunks: list[str] = []
    for suffix in (".md", ".txt"):
        path = evidence_dir / f"{base}{suffix}"
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _candidate_file_stem(candidate_key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", candidate_key.lower()).strip("-")


def _bedrock_response_text(response: dict[str, Any]) -> str:
    try:
        blocks = response["output"]["message"]["content"]
    except KeyError as error:
        raise ValueError("Unexpected Bedrock Converse response shape") from error
    return "".join(block.get("text", "") for block in blocks)


if __name__ == "__main__":
    main()
