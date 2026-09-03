"""Deletion of data owned by an authenticated DialedIN user."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from services.agent.config import AgentSettings
from services.espresso_mcp import storage as shot_storage


def delete_user_data(user_id: str, settings: AgentSettings) -> dict[str, int]:
    if not user_id:
        raise ValueError("user_id is required")

    deleted = {
        "usage_records": _delete_dynamodb_partition(settings.usage_table_name, user_id, "record_key", settings),
        "shot_records": _delete_dynamodb_partition(_shot_table_name(), user_id, "shot_id", settings),
        "media_objects": _delete_media(settings, user_id),
    }
    shot_storage.SHOT_HISTORY.pop(user_id, None)
    return deleted


def _shot_table_name() -> str | None:
    import os

    return os.getenv("DIALEDIN_SHOT_RESULTS_TABLE") or os.getenv("DIALEDIN_SHOT_RESULTS_TABLE_NAME")


def _delete_dynamodb_partition(table_name: str | None, user_id: str, range_key: str, settings: AgentSettings) -> int:
    if not table_name:
        return 0

    import boto3
    from boto3.dynamodb.conditions import Key

    table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(table_name)
    deleted = 0
    query: dict[str, Any] = {
        "KeyConditionExpression": Key("user_id").eq(user_id),
        "ProjectionExpression": f"user_id, {range_key}",
    }
    while True:
        response = table.query(**query)
        with table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"user_id": user_id, range_key: item[range_key]})
                deleted += 1
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query["ExclusiveStartKey"] = last_key
    return deleted


def _delete_media(settings: AgentSettings, user_id: str) -> int:
    prefix = f"{settings.media_upload_prefix.strip('/')}/{user_id}/"
    if settings.media_storage_mode == "local":
        target = (settings.local_media_upload_dir / settings.media_upload_prefix / user_id).resolve()
        root = settings.local_media_upload_dir.resolve()
        if root in target.parents and target.exists():
            shutil.rmtree(target)
            return 1
        return 0

    if not settings.media_upload_bucket:
        return 0
    import boto3

    client = boto3.client("s3", region_name=settings.aws_region)
    deleted = 0
    for page in client.get_paginator("list_object_versions").paginate(Bucket=settings.media_upload_bucket, Prefix=prefix):
        objects = [
            {"Key": item["Key"], "VersionId": item["VersionId"]}
            for collection in ("Versions", "DeleteMarkers")
            for item in page.get(collection, [])
        ]
        if objects:
            client.delete_objects(Bucket=settings.media_upload_bucket, Delete={"Objects": objects, "Quiet": True})
            deleted += len(objects)
    return deleted

