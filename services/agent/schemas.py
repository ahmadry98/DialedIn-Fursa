"""Pydantic schemas for the agent API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShotContext(BaseModel):
    user_id: str = "demo-user"
    audio_s3_key: str | None = None
    video_s3_key: str | None = None
    machine: str | None = None
    grinder: str | None = None
    uses_built_in_grinder: bool = False
    dose_g: float | None = None
    dose_unknown: bool = False
    yield_g: float | None = None
    grind_setting: str | None = None
    roast_level: str | None = None
    roast_unknown: bool = False
    taste: str | None = None
    timing_confidence: float | None = None
    total_shot_seconds: float | None = None
    requires_manual_confirmation: bool = False
    pending_gear_type: str | None = None
    pending_gear_name: str | None = None
    pending_gear_confidence: str | None = None


class AnalyzeShotRequest(ShotContext):
    pass


class AnalyzeShotResponse(BaseModel):
    timing: dict[str, Any]
    machine_profile: dict[str, Any]
    recommendation: dict[str, Any]
    missing_fields: list[str]
    profile_candidates: list[dict[str, Any]] = []
    saved_result: dict[str, Any]
    previous_comparison: dict[str, Any]
    message: str


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str
    image_base64: str | None = None
    image_media_type: str | None = None
    image_kind: str | None = Field(default=None, pattern="^(machine|grinder)$")


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    shot_context: ShotContext | None = None


class ChatResponse(BaseModel):
    response: str
    needs_shot_analysis: bool
    system_prompt: str
    shot_context: ShotContext | None = None
    analysis_result: AnalyzeShotResponse | None = None
    next_field: str | None = None
    missing_fields: list[str] = []
    image_guess: dict[str, Any] | None = None
    profile_candidates: list[dict[str, Any]] = []



class MediaUploadUrlRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    media_kind: str = Field(pattern="^(shot_audio|shot_video|machine_photo|grinder_photo)$")
    user_id: str = "demo-user"


class MediaUploadUrlResponse(BaseModel):
    media_key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    storage_mode: str
    expires_in_seconds: int


class MediaRegisterRequest(BaseModel):
    media_key: str
    media_kind: str = Field(pattern="^(shot_audio|shot_video|machine_photo|grinder_photo)$")
    storage_mode: str = Field(pattern="^(local|s3)$")
    content_type: str | None = None


class MediaRegisterResponse(BaseModel):
    media_key: str
    audio_s3_key: str | None = None
    video_s3_key: str | None = None
    media_kind: str
    storage_mode: str
    content_type: str | None = None



class MachineImageAttachRequest(BaseModel):
    media_key: str
    storage_mode: str = Field(pattern="^(local|s3)$")
    content_type: str | None = None
    source_url: str | None = None
    license_or_source_type: str = "admin_upload"
    status: str = "reviewed"
    review_notes: str | None = None


class ProfileCandidateUpdateRequest(BaseModel):
    draft_profile: dict[str, Any] | None = None
    review_notes: list[str] | None = None
    status: str | None = None

class HealthResponse(BaseModel):
    status: str
    service: str
    tool_count: int


class MetricsResponse(BaseModel):
    shot_analysis_requests_total: int
    chat_requests_total: int
    last_missing_fields_count: int
