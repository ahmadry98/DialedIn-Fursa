"""Shot result and media storage helpers for the espresso MCP tools."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

SHOT_HISTORY: dict[str, list[dict[str, Any]]] = {}


class MediaStorageError(RuntimeError):
    """Raised when uploaded media cannot be accessed for analysis."""


def save_shot_result(user_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Save a shot result for a user."""
    if not user_id:
        raise ValueError("user_id is required")

    table_name = _shot_results_table_name()
    if table_name:
        return _save_shot_result_dynamodb(user_id, result, table_name)

    stored_result = dict(result)
    SHOT_HISTORY.setdefault(user_id, []).append(stored_result)
    return {
        "status": "saved",
        "storage_mode": "memory",
        "user_id": user_id,
        "shot_count": len(SHOT_HISTORY[user_id]),
        "result": stored_result,
    }


def compare_previous_shots(user_id: str, current_result: dict[str, Any]) -> dict[str, Any]:
    """Compare current shot timing with the user's previous saved shot."""
    table_name = _shot_results_table_name()
    if table_name:
        return _compare_previous_shots_dynamodb(user_id, current_result, table_name)

    previous_shots = SHOT_HISTORY.get(user_id, [])
    if not previous_shots:
        return {
            "has_previous": False,
            "message": "No previous shots saved for this user.",
            "current_result": current_result,
        }

    previous = previous_shots[-1]
    return _compare_results(previous, current_result)


def resolve_media_key_to_local_path(media_key: str) -> Path:
    """Return a local path for a local media path or downloaded S3 object key."""
    path = Path(media_key)
    if path.exists():
        return path

    bucket = _media_upload_bucket()
    if not bucket:
        raise MediaStorageError(
            "I could not find that video locally. Choose a video file again, or check that the video path is correct."
        )

    return _download_s3_media(bucket=bucket, media_key=media_key)


def _save_shot_result_dynamodb(user_id: str, result: dict[str, Any], table_name: str) -> dict[str, Any]:
    table = _dynamodb_table(table_name)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stored_result = dict(result)
    shot_id = str(stored_result.get("shot_id") or f"{created_at}#{uuid.uuid4().hex}")
    item = {
        "user_id": user_id,
        "shot_id": shot_id,
        "created_at": created_at,
        "result": _to_dynamodb_value(stored_result),
    }
    table.put_item(Item=item)
    return {
        "status": "saved",
        "storage_mode": "dynamodb",
        "user_id": user_id,
        "shot_id": shot_id,
        "result": stored_result,
    }


def _compare_previous_shots_dynamodb(user_id: str, current_result: dict[str, Any], table_name: str) -> dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")

    try:
        from boto3.dynamodb.conditions import Key
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to compare DynamoDB shot history.") from error

    table = _dynamodb_table(table_name)
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
        Limit=2,
    )
    items = response.get("Items", [])
    if not items:
        return {
            "has_previous": False,
            "message": "No previous shots saved for this user.",
            "current_result": current_result,
        }

    # When called after save, the newest item is the current shot. Compare against
    # the next newest item if it exists; otherwise there is no useful history yet.
    previous_item = items[1] if len(items) > 1 else None
    if previous_item is None:
        return {
            "has_previous": False,
            "message": "This is the first saved shot for this user.",
            "current_result": current_result,
        }

    previous = _from_dynamodb_value(previous_item.get("result", {}))
    return _compare_results(previous, current_result)


def _compare_results(previous: dict[str, Any], current_result: dict[str, Any]) -> dict[str, Any]:
    previous_total = _float_or_none(previous.get("total_shot_seconds"))
    current_total = _float_or_none(current_result.get("total_shot_seconds"))
    total_delta = None
    if previous_total is not None and current_total is not None:
        total_delta = round(current_total - previous_total, 2)

    return {
        "has_previous": True,
        "previous_result": previous,
        "current_result": current_result,
        "total_shot_delta_seconds": total_delta,
    }


def _shot_results_table_name() -> str | None:
    mode = os.getenv("DIALEDIN_SHOT_HISTORY_STORAGE", "").lower()
    table_name = os.getenv("DIALEDIN_SHOT_RESULTS_TABLE") or os.getenv("DIALEDIN_SHOT_RESULTS_TABLE_NAME")
    if mode == "memory":
        return None
    if mode == "dynamodb" and not table_name:
        raise RuntimeError("DIALEDIN_SHOT_RESULTS_TABLE is required when DIALEDIN_SHOT_HISTORY_STORAGE=dynamodb")
    return table_name or None


def _media_upload_bucket() -> str | None:
    if os.getenv("DIALEDIN_MEDIA_STORAGE_MODE", "local").lower() != "s3":
        return None
    return os.getenv("DIALEDIN_MEDIA_UPLOAD_BUCKET") or None


def _dynamodb_table(table_name: str):
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise RuntimeError("Install boto3 to use DynamoDB shot history.") from error

    session_kwargs: dict[str, str] = {}
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        session_kwargs["region_name"] = region
    if os.getenv("AWS_PROFILE"):
        session_kwargs["profile_name"] = os.environ["AWS_PROFILE"]

    session = boto3.Session(**session_kwargs)
    return session.resource("dynamodb").Table(table_name)


def _download_s3_media(*, bucket: str, media_key: str) -> Path:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        raise MediaStorageError("Install boto3 to analyze uploaded S3 videos.") from error

    suffix = Path(media_key).suffix or ".media"
    safe_stem = Path(media_key).stem[:80] or "upload"
    target_dir = Path(tempfile.gettempdir()) / "dialchat_s3_media"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{safe_stem}-{abs(hash(media_key))}{suffix}"

    session_kwargs: dict[str, str] = {}
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        session_kwargs["region_name"] = region
    if os.getenv("AWS_PROFILE"):
        session_kwargs["profile_name"] = os.environ["AWS_PROFILE"]

    try:
        session = boto3.Session(**session_kwargs)
        client = session.client("s3")
        client.download_file(bucket, media_key, str(target))
    except NoCredentialsError as error:
        raise MediaStorageError("AWS credentials were not found, so I could not read the uploaded video from S3.") from error
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", "S3Error"))
        if code in {"AccessDenied", "403"}:
            message = "I could not read the uploaded video from S3. Check IAM permission for s3:GetObject on the media bucket."
        elif code in {"NoSuchKey", "404", "NotFound"}:
            message = "I could not find the uploaded video in S3. Please upload the video again."
        else:
            message = f"I could not read the uploaded video from S3 ({code})."
        raise MediaStorageError(message) from error
    except Exception as error:
        raise MediaStorageError(f"I could not read the uploaded video from S3: {error}") from error

    return target


def _to_dynamodb_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_dynamodb_value(item) for item in value]
    return value


def _from_dynamodb_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _from_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_value(item) for item in value]
    return value


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
