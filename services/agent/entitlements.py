"""Subscription entitlement and usage-limit enforcement."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from services.agent.config import AgentSettings


@dataclass(frozen=True)
class UsageStatus:
    tier: str
    period: str
    used: int
    limit: int
    remaining: int


_memory_events: set[str] = set()
_memory_usage: dict[tuple[str, str], int] = {}
_memory_entitlements: dict[str, int] = {}
_memory_lock = Lock()


def _period(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    return value.strftime("%Y-%m")


def _table(settings: AgentSettings):
    if not settings.usage_table_name:
        raise RuntimeError("DIALEDIN_USAGE_TABLE is required when usage storage is dynamodb")
    import boto3

    return boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.usage_table_name)


def _pro_active(user_id: str, settings: AgentSettings, now: datetime | None = None) -> bool:
    timestamp = int((now or datetime.now(UTC)).timestamp())
    if settings.usage_storage == "memory":
        return _memory_entitlements.get(user_id, 0) > timestamp
    response = _table(settings).get_item(Key={"user_id": user_id, "record_key": "ENTITLEMENT"}, ConsistentRead=True)
    item = response.get("Item") or {}
    return item.get("entitlement") == "pro" and int(item.get("expires_at", 0)) > timestamp


def usage_status(user_id: str, settings: AgentSettings, now: datetime | None = None) -> UsageStatus:
    period = _period(now)
    tier = "pro" if _pro_active(user_id, settings, now) else "free"
    limit = settings.pro_monthly_analysis_limit if tier == "pro" else settings.free_monthly_analysis_limit
    if not settings.quota_enabled:
        return UsageStatus(tier=tier, period=period, used=0, limit=limit, remaining=limit)

    if settings.usage_storage == "memory":
        used = _memory_usage.get((user_id, period), 0)
    else:
        response = _table(settings).get_item(
            Key={"user_id": user_id, "record_key": f"USAGE#{period}"},
            ConsistentRead=True,
        )
        used = int((response.get("Item") or {}).get("analysis_count", 0))
    return UsageStatus(tier=tier, period=period, used=used, limit=limit, remaining=max(0, limit - used))


def require_available(user_id: str, settings: AgentSettings) -> UsageStatus:
    status = usage_status(user_id, settings)
    if settings.quota_enabled and status.remaining <= 0:
        raise QuotaExceeded(status)
    return status


def consume_analysis(user_id: str, settings: AgentSettings) -> UsageStatus:
    before = require_available(user_id, settings)
    if not settings.quota_enabled:
        return before

    if settings.usage_storage == "memory":
        with _memory_lock:
            key = (user_id, before.period)
            used = _memory_usage.get(key, 0)
            if used >= before.limit:
                raise QuotaExceeded(UsageStatus(before.tier, before.period, used, before.limit, 0))
            _memory_usage[key] = used + 1
            used += 1
    else:
        try:
            response = _table(settings).update_item(
                Key={"user_id": user_id, "record_key": f"USAGE#{before.period}"},
                UpdateExpression="SET analysis_count = if_not_exists(analysis_count, :zero) + :one, updated_at = :now",
                ConditionExpression="attribute_not_exists(analysis_count) OR analysis_count < :limit",
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                    ":limit": before.limit,
                    ":now": datetime.now(UTC).isoformat(),
                },
                ReturnValues="ALL_NEW",
            )
            used = int(response["Attributes"]["analysis_count"])
        except Exception as error:
            if error.__class__.__name__ == "ConditionalCheckFailedException":
                raise QuotaExceeded(usage_status(user_id, settings)) from error
            raise
    return UsageStatus(before.tier, before.period, used, before.limit, max(0, before.limit - used))


def apply_revenuecat_event(event: dict[str, Any], settings: AgentSettings) -> bool:
    event_id = str(event.get("id") or "")
    user_id = str(event.get("app_user_id") or "")
    if not event_id or not user_id:
        raise ValueError("RevenueCat event requires id and app_user_id")
    entitlement_ids = event.get("entitlement_ids") or []
    expires_at = int(event.get("expiration_at_ms") or 0) // 1000 if "pro" in entitlement_ids else 0

    if settings.usage_storage == "memory":
        with _memory_lock:
            if event_id in _memory_events:
                return False
            _memory_entitlements[user_id] = expires_at
            _memory_events.add(event_id)
            return True

    table = _table(settings)
    existing = table.get_item(
        Key={"user_id": user_id, "record_key": f"EVENT#{event_id}"},
        ConsistentRead=True,
    ).get("Item")
    if existing:
        return False
    table.put_item(
        Item={
            "user_id": user_id,
            "record_key": "ENTITLEMENT",
            "entitlement": "pro" if expires_at > 0 else "free",
            "expires_at": expires_at,
            "source": "revenuecat",
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    table.put_item(
        Item={
            "user_id": user_id,
            "record_key": f"EVENT#{event_id}",
            "event_type": str(event.get("type") or "UNKNOWN"),
            "ttl": int(datetime.now(UTC).timestamp()) + 90 * 24 * 60 * 60,
        },
        ConditionExpression="attribute_not_exists(record_key)",
    )
    return True


def set_memory_entitlement(user_id: str, expires_at: int) -> None:
    with _memory_lock:
        _memory_entitlements[user_id] = expires_at


def reset_memory_store() -> None:
    with _memory_lock:
        _memory_events.clear()
        _memory_usage.clear()
        _memory_entitlements.clear()


class QuotaExceeded(Exception):
    def __init__(self, status: UsageStatus):
        self.status = status
        super().__init__("Monthly analysis allowance reached")


def public_status(status: UsageStatus) -> dict[str, Any]:
    return asdict(status)

