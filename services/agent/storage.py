"""Media upload storage helpers for DialChat.

The local mode lets Expo upload videos to the FastAPI service during
development. S3 mode uses the same API shape but returns a presigned PUT URL.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.agent.config import AgentSettings


SUPPORTED_MEDIA_KINDS = {"shot_video", "machine_photo", "grinder_photo"}


@dataclass(frozen=True)
class UploadTarget:
    media_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    storage_mode: str
    expires_in_seconds: int


@dataclass(frozen=True)
class MediaObject:
    payload: bytes
    content_type: str | None = None


def create_upload_target(
    *,
    settings: AgentSettings,
    base_url: str,
    user_id: str,
    filename: str,
    content_type: str,
    media_kind: str,
) -> UploadTarget:
    """Create a local or S3 upload target for client-side media upload."""
    if media_kind not in SUPPORTED_MEDIA_KINDS:
        raise ValueError(f"Unsupported media_kind: {media_kind}")

    safe_name = _safe_filename(filename)
    media_key = _media_key(settings.media_upload_prefix, user_id, media_kind, safe_name)
    headers = {"Content-Type": content_type or "application/octet-stream"}

    if settings.media_storage_mode == "s3":
        if not settings.media_upload_bucket:
            raise ValueError("DIALEDIN_MEDIA_UPLOAD_BUCKET is required when DIALEDIN_MEDIA_STORAGE_MODE=s3")
        return UploadTarget(
            media_key=media_key,
            upload_url=_s3_presigned_put_url(settings, media_key, headers["Content-Type"]),
            method="PUT",
            headers=headers,
            storage_mode="s3",
            expires_in_seconds=settings.media_upload_url_expires_seconds,
        )

    local_key = str(settings.local_media_upload_dir / media_key)
    upload_path = f"/media/local-upload/{local_key}"
    return UploadTarget(
        media_key=local_key,
        upload_url=f"{base_url.rstrip('/')}{upload_path}",
        method="PUT",
        headers=headers,
        storage_mode="local",
        expires_in_seconds=settings.media_upload_url_expires_seconds,
    )


def write_local_upload(*, settings: AgentSettings, media_key: str, payload: bytes) -> dict[str, Any]:
    """Persist an uploaded media file in the configured local upload directory."""
    target = Path(media_key)
    root = settings.local_media_upload_dir.resolve()
    resolved = target.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("media_key is outside the local upload directory")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"media_key": str(target), "size_bytes": len(payload), "storage_mode": "local"}


def register_uploaded_media(*, media_key: str, media_kind: str, storage_mode: str, content_type: str | None = None) -> dict[str, Any]:
    """Return normalized metadata for an uploaded media object."""
    if media_kind not in SUPPORTED_MEDIA_KINDS:
        raise ValueError(f"Unsupported media_kind: {media_kind}")
    if storage_mode not in {"local", "s3"}:
        raise ValueError(f"Unsupported storage_mode: {storage_mode}")
    return {
        "media_key": media_key,
        "video_s3_key": media_key if media_kind == "shot_video" else None,
        "media_kind": media_kind,
        "storage_mode": storage_mode,
        "content_type": content_type,
    }


def create_media_read_url(*, settings: AgentSettings, media_key: str) -> str | None:
    """Create a temporary read URL for a private S3 media object."""
    if not media_key or not settings.media_upload_bucket:
        return None

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as error:  # pragma: no cover - dependency exists only for S3 mode.
        raise RuntimeError("Install boto3 to read S3 media uploads.") from error

    session_kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if os.getenv("AWS_PROFILE"):
        session_kwargs["profile_name"] = os.environ["AWS_PROFILE"]
    try:
        session = boto3.Session(**session_kwargs)
        client = session.client("s3")
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.media_upload_bucket, "Key": media_key},
            ExpiresIn=settings.media_upload_url_expires_seconds,
        )
    except NoCredentialsError as error:
        raise RuntimeError("AWS credentials were not found, so I could not create an S3 image link.") from error
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", "S3Error"))
        if code in {"AccessDenied", "403"}:
            message = "I could not create an S3 image link. Check IAM permission for s3:GetObject on the media bucket."
        elif code in {"NoSuchBucket", "404", "NotFound"}:
            message = "The configured S3 media bucket was not found. Check DIALEDIN_MEDIA_UPLOAD_BUCKET."
        else:
            message = f"I could not create an S3 image link ({code})."
        raise RuntimeError(message) from error


def read_s3_media_object(*, settings: AgentSettings, media_key: str) -> MediaObject:
    """Read a private S3 media object through the trusted API."""
    if not media_key or not settings.media_upload_bucket:
        raise RuntimeError("S3 media bucket or media key is missing.")

    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as error:  # pragma: no cover - dependency exists only for S3 mode.
        raise RuntimeError("Install boto3 to read S3 media uploads.") from error

    session_kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if os.getenv("AWS_PROFILE"):
        session_kwargs["profile_name"] = os.environ["AWS_PROFILE"]
    try:
        session = boto3.Session(**session_kwargs)
        client = session.client("s3")
        response = client.get_object(Bucket=settings.media_upload_bucket, Key=media_key)
        return MediaObject(
            payload=response["Body"].read(),
            content_type=response.get("ContentType"),
        )
    except NoCredentialsError as error:
        raise RuntimeError("AWS credentials were not found, so I could not read the S3 image.") from error
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", "S3Error"))
        if code in {"AccessDenied", "403"}:
            message = "I could not read the S3 image. Check IAM permission for s3:GetObject on the media bucket."
        elif code in {"NoSuchBucket", "404", "NotFound", "NoSuchKey"}:
            message = "The configured S3 image was not found. Check the machine image media key."
        else:
            message = f"I could not read the S3 image ({code})."
        raise RuntimeError(message) from error


def sniff_media_content_type(payload: bytes, fallback: str | None = None) -> str:
    """Infer common image content types from bytes when uploaded metadata is wrong."""
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return "image/gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    if len(payload) >= 16 and payload[4:8] == b"ftyp" and payload[8:12] in {b"avif", b"avis"}:
        return "image/avif"
    return fallback or "application/octet-stream"


def _media_key(prefix: str, user_id: str, media_kind: str, filename: str) -> str:
    safe_user = _safe_path_part(user_id or "demo-user")
    safe_kind = _safe_path_part(media_kind)
    return f"{prefix.strip('/')}/{safe_user}/{safe_kind}/{uuid.uuid4().hex}-{filename}"


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return name or "upload"


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return cleaned or "unknown"


def _s3_presigned_put_url(settings: AgentSettings, media_key: str, content_type: str) -> str:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as error:  # pragma: no cover - dependency exists only for S3 mode.
        raise RuntimeError("Install boto3 to use S3 media uploads.") from error

    session_kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if os.getenv("AWS_PROFILE"):
        session_kwargs["profile_name"] = os.environ["AWS_PROFILE"]
    try:
        session = boto3.Session(**session_kwargs)
        client = session.client("s3")
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.media_upload_bucket,
                "Key": media_key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.media_upload_url_expires_seconds,
        )
    except NoCredentialsError as error:
        raise RuntimeError("AWS credentials were not found, so I could not create an S3 upload link.") from error
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", "S3Error"))
        if code in {"AccessDenied", "403"}:
            message = "I could not create an S3 upload link. Check IAM permission for s3:PutObject on the media bucket."
        elif code in {"NoSuchBucket", "404", "NotFound"}:
            message = "The configured S3 media bucket was not found. Check DIALEDIN_MEDIA_UPLOAD_BUCKET."
        else:
            message = f"I could not create an S3 upload link ({code})."
        raise RuntimeError(message) from error
