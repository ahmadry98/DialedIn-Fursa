"""FastAPI entrypoint for the DialedIN agent."""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.agent import agent_runner
from services.agent.config import get_settings
from services.agent.schemas import (
    AnalyzeShotRequest,
    AnalyzeShotResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MetricsResponse,
)
from services.espresso_mcp import app as espresso_tools
from services.espresso_mcp import profile_candidates
from services.espresso_mcp import profile_research_worker

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    response = agent_runner.chat(request)
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
