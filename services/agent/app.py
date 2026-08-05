"""FastAPI entrypoint for the DialedIN agent."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from services.agent import agent_runner, storage
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
    MetricsResponse,
    ProfileCandidateUpdateRequest,
)
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import profile_candidates
from services.espresso_mcp import profile_promoter
from services.espresso_mcp import profile_research_worker

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_profile_research_background(*, limit: int) -> None:
    try:
        profile_research_worker.run_worker(limit=limit)
    except Exception as error:  # pragma: no cover - background failure should not break shot analysis.
        print(f"Profile research autorun failed: {error}")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, tool_count=len(espresso_tools.get_registered_tool_names()))


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**agent_runner.metrics())


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
        raise HTTPException(status_code=400, detail=str(error)) from error
    return MediaUploadUrlResponse(**target.__dict__)


@app.put("/media/local-upload/{media_key:path}")
async def upload_local_media(media_key: str, request: Request) -> dict[str, object]:
    try:
        payload = await request.body()
        return storage.write_local_upload(settings=settings, media_key=media_key, payload=payload)
    except Exception as error:
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
        raise HTTPException(status_code=400, detail=str(error)) from error
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
        results = profile_research_worker.run_worker(candidate_key=candidate_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
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
