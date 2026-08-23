"""FastAPI entrypoint for the DialedIN agent."""

from __future__ import annotations

import json
import logging
from time import perf_counter

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from services.agent import agent_runner, equipment_profiles, observability, storage
from services.agent.config import get_settings
from services.agent.schemas import (
    AnalyzeShotRequest,
    AnalyzeShotResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MediaRegisterRequest,
    MediaRegisterResponse,
    MediaUploadUrlRequest,
    MediaUploadUrlResponse,
    MachineImageAttachRequest,
    MetricsResponse,
    ProfileCandidateUpdateRequest,
)
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import machine_profiles
from services.espresso_mcp import profile_candidates
from services.espresso_mcp import profile_promoter
from services.espresso_mcp import profile_research
from services.espresso_mcp import profile_research_worker

settings = get_settings()
logger = logging.getLogger("dialedin.agent")
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_PATH_FAMILIES = (
    ("/machines/", "/machines/{slug}"),
    ("/grinders/", "/grinders/{slug}"),
    ("/profile-candidates/", "/profile-candidates/{candidate_key}"),
    ("/media/local-upload/", "/media/local-upload/{media_key}"),
)


def _path_family(path: str) -> str:
    if path.startswith("/machines/") and path.endswith("/image"):
        return "/machines/{slug}/image"
    if path.startswith("/api/machines/"):
        return "/api/machines/{slug}/"
    if path.startswith("/api/grinders/"):
        return "/api/grinders/{slug}/"
    if path.startswith("/profile-candidates/") and path.endswith("/research"):
        return "/profile-candidates/{candidate_key}/research"
    if path.startswith("/profile-candidates/") and path.endswith("/promote"):
        return "/profile-candidates/{candidate_key}/promote"
    for prefix, family in _PATH_FAMILIES:
        if path.startswith(prefix):
            return family
    return path


def _log_request(*, request: Request, status_code: int, duration_seconds: float, error: str | None = None) -> None:
    payload = {
        "event": "http_request",
        "method": request.method,
        "path": _path_family(request.url.path),
        "status_code": status_code,
        "duration_ms": round(duration_seconds * 1000, 2),
        "client_host": request.client.host if request.client else None,
    }
    if error:
        payload["error"] = error
    message = json.dumps(payload, sort_keys=True)
    if status_code >= 500:
        logger.error(message)
    elif status_code >= 400:
        logger.warning(message)
    else:
        logger.info(message)


@app.middleware("http")
async def record_http_observability(request: Request, call_next):
    start = perf_counter()
    path = _path_family(request.url.path)
    try:
        response = await call_next(request)
    except Exception as error:
        duration = perf_counter() - start
        observability.increment("dialedin_http_requests_total", method=request.method, path=path, status="500", status_family="5xx")
        observability.increment("dialedin_http_5xx_total", path=path)
        observability.observe("dialedin_http_request_seconds", duration, method=request.method, path=path, status="500", status_family="5xx")
        _log_request(request=request, status_code=500, duration_seconds=duration, error=error.__class__.__name__)
        raise

    duration = perf_counter() - start
    status = str(response.status_code)
    status_family = f"{response.status_code // 100}xx"
    observability.increment("dialedin_http_requests_total", method=request.method, path=path, status=status, status_family=status_family)
    observability.observe("dialedin_http_request_seconds", duration, method=request.method, path=path, status=status, status_family=status_family)
    if response.status_code >= 500:
        observability.increment("dialedin_http_5xx_total", path=path)
    _log_request(request=request, status_code=response.status_code, duration_seconds=duration)
    return response


def _run_profile_research_background(*, limit: int) -> None:
    try:
        observability.increment("dialedin_profile_research_runs_total", status="started")
        profile_research_worker.run_worker(limit=limit)
        observability.increment("dialedin_profile_research_runs_total", status="success")
    except Exception as error:  # pragma: no cover - background failure should not break shot analysis.
        observability.increment("dialedin_profile_research_runs_total", status="error")
        print(f"Profile research autorun failed: {error}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, tool_count=len(espresso_tools.get_registered_tool_names()))


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**agent_runner.metrics())


@app.get("/metrics.prometheus", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return observability.render_prometheus(agent_runner.metrics())


@app.get("/machines")
def list_machines() -> dict[str, object]:
    machines = equipment_profiles.list_machines(media_cdn_base_url=settings.media_cdn_base_url)
    return {"count": len(machines), "machines": machines}


@app.get("/machines/{slug_or_alias:path}/image")
@app.head("/machines/{slug_or_alias:path}/image")
def get_machine_image(slug_or_alias: str, request: Request) -> Response:
    try:
        machine = equipment_profiles.get_machine(slug_or_alias, media_cdn_base_url=settings.media_cdn_base_url)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    image = machine.get("image")
    if not isinstance(image, dict) or image.get("status") != "reviewed":
        raise HTTPException(status_code=404, detail="Machine image is not reviewed")
    if image.get("storage_mode") != "s3" or not image.get("media_key"):
        raise HTTPException(status_code=404, detail="Machine image is not stored in S3")

    try:
        media = storage.read_s3_media_object(settings=settings, media_key=str(image["media_key"]))
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    headers = {"Cache-Control": "public, max-age=86400"}
    content_type = storage.sniff_media_content_type(
        media.payload,
        fallback=media.content_type or str(image.get("content_type") or "application/octet-stream"),
    )
    content = b"" if request.method == "HEAD" else media.payload
    return Response(content=content, media_type=content_type, headers=headers)


@app.get("/machines/{slug_or_alias:path}")
def get_machine(slug_or_alias: str) -> dict[str, object]:
    try:
        return equipment_profiles.get_machine(slug_or_alias, media_cdn_base_url=settings.media_cdn_base_url)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/machines/{slug_or_alias:path}/image")
def attach_machine_image(slug_or_alias: str, request_body: MachineImageAttachRequest) -> dict[str, object]:
    try:
        image = {
            "media_key": request_body.media_key,
            "storage_mode": request_body.storage_mode,
            "content_type": request_body.content_type,
            "source_url": request_body.source_url or "admin upload",
            "license_or_source_type": request_body.license_or_source_type,
            "status": request_body.status,
            "review_notes": request_body.review_notes,
        }
        profile = machine_profiles.update_machine_profile_image(slug_or_alias, image)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "machine": equipment_profiles.get_machine(
            str(profile.get("dialedin_slug") or profile.get("machine_name")),
            media_cdn_base_url=settings.media_cdn_base_url,
        )
    }


@app.get("/grinders")
def list_grinders() -> dict[str, object]:
    grinders = equipment_profiles.list_grinders()
    return {"count": len(grinders), "grinders": grinders}


@app.get("/grinders/{slug_or_alias:path}")
def get_grinder(slug_or_alias: str) -> dict[str, object]:
    try:
        return equipment_profiles.get_grinder(slug_or_alias)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/machines/")
def list_machines_compat() -> list[dict[str, object]]:
    return equipment_profiles.list_machines(media_cdn_base_url=settings.media_cdn_base_url)


@app.get("/api/machines/{slug_or_alias:path}/")
def get_machine_compat(slug_or_alias: str) -> dict[str, object]:
    return get_machine(slug_or_alias)


@app.get("/api/grinders/")
def list_grinders_compat() -> list[dict[str, object]]:
    return equipment_profiles.list_grinders()


@app.get("/api/grinders/{slug_or_alias:path}/")
def get_grinder_compat(slug_or_alias: str) -> dict[str, object]:
    return get_grinder(slug_or_alias)


@app.post("/media/upload-url", response_model=MediaUploadUrlResponse)
def create_media_upload_url(request_body: MediaUploadUrlRequest, request: Request) -> MediaUploadUrlResponse:
    try:
        target = storage.create_upload_target(
            settings=settings,
            base_url=str(request.base_url),
            user_id=request_body.user_id,
            filename=request_body.filename,
            content_type=request_body.content_type,
            media_kind=request_body.media_kind,
        )
    except Exception as error:
        observability.increment("dialedin_media_upload_targets_total", kind=request_body.media_kind, storage="unknown", status="error")
        raise HTTPException(status_code=400, detail=str(error)) from error
    observability.increment("dialedin_media_upload_targets_total", kind=request_body.media_kind, storage=target.storage_mode, status="success")
    return MediaUploadUrlResponse(**target.__dict__)


@app.put("/media/local-upload/{media_key:path}")
async def upload_local_media(media_key: str, request: Request) -> dict[str, object]:
    try:
        payload = await request.body()
        result = storage.write_local_upload(settings=settings, media_key=media_key, payload=payload)
        observability.observe("dialedin_media_uploaded_bytes", result.get("size_bytes"), storage="local")
        observability.increment("dialedin_media_local_uploads_total", status="success")
        return result
    except Exception as error:
        observability.increment("dialedin_media_local_uploads_total", status="error")
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/media/register", response_model=MediaRegisterResponse)
def register_media_upload(request_body: MediaRegisterRequest) -> MediaRegisterResponse:
    try:
        metadata = storage.register_uploaded_media(
            media_key=request_body.media_key,
            media_kind=request_body.media_kind,
            storage_mode=request_body.storage_mode,
            content_type=request_body.content_type,
        )
    except Exception as error:
        observability.increment("dialedin_media_registered_total", kind=request_body.media_kind, storage=request_body.storage_mode, status="error")
        raise HTTPException(status_code=400, detail=str(error)) from error
    observability.increment("dialedin_media_registered_total", kind=request_body.media_kind, storage=request_body.storage_mode, status="success")
    return MediaRegisterResponse(**metadata)


@app.get("/profile-research/status")
def profile_research_status() -> dict[str, object]:
    candidates = profile_candidates.load_profile_candidates()
    queued = [candidate for candidate in candidates if candidate.get("status") == "needs_research"]
    return {
        "autorun": settings.profile_research_autorun,
        "autorun_limit": settings.profile_research_autorun_limit,
        "queued_count": len(queued),
        "queued_candidate_keys": [candidate.get("candidate_key") for candidate in queued],
    }




@app.get("/profile-candidates")
def list_profile_candidates() -> dict[str, object]:
    candidates = profile_candidates.load_profile_candidates()
    return {
        "count": len(candidates),
        "candidates": sorted(
            candidates,
            key=lambda candidate: (
                str(candidate.get("status", "")),
                str(candidate.get("last_seen_at", "")),
                str(candidate.get("candidate_key", "")),
            ),
            reverse=True,
        ),
    }


@app.patch("/profile-candidates/{candidate_key:path}")
def update_profile_candidate(candidate_key: str, request: ProfileCandidateUpdateRequest) -> dict[str, object]:
    try:
        candidate = profile_candidates.update_profile_candidate(
            candidate_key,
            draft_profile=request.draft_profile,
            review_notes=request.review_notes,
            status=request.status,
        )
        candidate = profile_research.refresh_candidate_quality(candidate_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"candidate": candidate}


@app.delete("/profile-candidates/{candidate_key:path}")
def delete_profile_candidate(candidate_key: str) -> dict[str, object]:
    try:
        return profile_candidates.delete_profile_candidate(candidate_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/profile-candidates/{candidate_key:path}/research")
def rerun_profile_candidate_research(candidate_key: str) -> dict[str, object]:
    try:
        observability.increment("dialedin_profile_research_runs_total", status="started", trigger="manual")
        results = profile_research_worker.run_worker(candidate_key=candidate_key)
    except ValueError as error:
        observability.increment("dialedin_profile_research_runs_total", status="not_found", trigger="manual")
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        observability.increment("dialedin_profile_research_runs_total", status="error", trigger="manual")
        raise HTTPException(status_code=400, detail=str(error)) from error
    observability.increment("dialedin_profile_research_runs_total", status="success", trigger="manual")
    return {"results": results}


@app.post("/profile-candidates/{candidate_key:path}/promote")
def promote_profile_candidate(candidate_key: str) -> dict[str, object]:
    try:
        return profile_promoter.promote_candidate(candidate_key)
    except ValueError as error:
        message = str(error)
        status_code = 404 if "Unknown candidate_key" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from error


@app.post("/analyze-shot", response_model=AnalyzeShotResponse)
def analyze_shot(request: AnalyzeShotRequest, background_tasks: BackgroundTasks) -> AnalyzeShotResponse:
    try:
        response = agent_runner.analyze_shot(request)
    except Exception as error:
        observability.increment("dialedin_mcp_tool_errors_total", tool="analyze_shot")
        raise HTTPException(status_code=400, detail=str(error)) from error

    if settings.profile_research_autorun and response.profile_candidates:
        print(
            "Profile research autorun scheduled: "
            f"limit={settings.profile_research_autorun_limit}, "
            f"candidates={[candidate.get('candidate_key') for candidate in response.profile_candidates]}"
        )
        background_tasks.add_task(
            _run_profile_research_background,
            limit=settings.profile_research_autorun_limit,
        )

    return response


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    try:
        response = agent_runner.chat(request)
    except Exception as error:
        observability.increment("dialedin_mcp_tool_errors_total", tool="chat")
        raise HTTPException(status_code=400, detail=str(error)) from error

    analysis = response.analysis_result
    if settings.profile_research_autorun and analysis and analysis.profile_candidates:
        print(
            "Profile research autorun scheduled from chat: "
            f"limit={settings.profile_research_autorun_limit}, "
            f"candidates={[candidate.get('candidate_key') for candidate in analysis.profile_candidates]}"
        )
        background_tasks.add_task(
            _run_profile_research_background,
            limit=settings.profile_research_autorun_limit,
        )
    return response
