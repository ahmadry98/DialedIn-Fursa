"""FastAPI entrypoint for the DialedIN agent."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

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

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, tool_count=len(espresso_tools.get_registered_tool_names()))


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(**agent_runner.metrics())


@app.post("/analyze-shot", response_model=AnalyzeShotResponse)
def analyze_shot(request: AnalyzeShotRequest) -> AnalyzeShotResponse:
    try:
        return agent_runner.analyze_shot(request)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return agent_runner.chat(request)
