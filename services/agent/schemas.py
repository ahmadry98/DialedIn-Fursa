"""Pydantic schemas for the agent API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShotContext(BaseModel):
    user_id: str = "demo-user"
    video_s3_key: str | None = None
    machine: str | None = None
    grinder: str | None = None
    dose_g: float | None = None
    yield_g: float | None = None
    grind_setting: str | None = None
    roast_level: str | None = None
    taste: str | None = None
    timing_confidence: float | None = None
    total_shot_seconds: float | None = None
    requires_manual_confirmation: bool = False


class AnalyzeShotRequest(ShotContext):
    pass


class AnalyzeShotResponse(BaseModel):
    timing: dict[str, Any]
    machine_profile: dict[str, Any]
    recommendation: dict[str, Any]
    missing_fields: list[str]
    saved_result: dict[str, Any]
    previous_comparison: dict[str, Any]
    message: str


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    shot_context: ShotContext | None = None


class ChatResponse(BaseModel):
    response: str
    needs_shot_analysis: bool
    system_prompt: str


class HealthResponse(BaseModel):
    status: str
    service: str
    tool_count: int


class MetricsResponse(BaseModel):
    shot_analysis_requests_total: int
    chat_requests_total: int
    last_missing_fields_count: int
