"""Notification helpers for profile candidate review events."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

DEFAULT_REVIEW_EMAIL = "support@dialedin.me"
DEFAULT_FROM_EMAIL = "support@dialedin.me"
DEFAULT_ADMIN_REVIEW_URL = "http://ai-dev.dialedin.me/admin"


def notify_new_profile_candidate(candidate: dict[str, Any]) -> bool:
    """Send a non-blocking email when a new gear candidate is captured.

    Notifications are intentionally optional. In dev/CI, leave
    PROFILE_CANDIDATE_EMAIL_ENABLED unset/false. In cloud, configure SES or SMTP
    env vars to enable real delivery.
    """
    if not _enabled():
        return False

    message = _build_candidate_message(candidate)
    provider = _provider()
    if provider == "ses":
        return _send_with_ses(message)
    return _send_with_smtp(message)


def _build_candidate_message(candidate: dict[str, Any]) -> EmailMessage:
    gear_type = str(candidate.get("type") or "gear").lower()
    name = candidate.get("name_entered", "unknown")
    recipient = os.getenv("PROFILE_CANDIDATE_EMAIL_TO") or DEFAULT_REVIEW_EMAIL
    sender = os.getenv("PROFILE_CANDIDATE_EMAIL_FROM") or os.getenv("SMTP_FROM") or DEFAULT_FROM_EMAIL

    message = EmailMessage()
    message["Subject"] = f"DialedIN new {gear_type} candidate: {name}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(_candidate_email_body(candidate))
    return message


def _send_with_ses(message: EmailMessage) -> bool:
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - dependency setup issue.
        print(f"Profile candidate email skipped: boto3 is not installed: {error}")
        return False

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    try:
        client = boto3.client("sesv2", region_name=region)
        client.send_email(
            FromEmailAddress=str(message["From"]),
            Destination={"ToAddresses": [str(message["To"])]},
            Content={
                "Simple": {
                    "Subject": {"Data": str(message["Subject"]), "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": message.get_content(), "Charset": "UTF-8"}},
                }
            },
        )
        return True
    except Exception as error:  # pragma: no cover - network/AWS failure should never block chat.
        print(f"Profile candidate SES email failed: {error}")
        return False


def _send_with_smtp(message: EmailMessage) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        print("Profile candidate email skipped: SMTP_HOST is not configured")
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME") or None
    password = os.getenv("SMTP_PASSWORD") or None

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if _use_tls():
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except Exception as error:  # pragma: no cover - network failure should never block chat.
        print(f"Profile candidate SMTP email failed: {error}")
        return False


def _candidate_email_body(candidate: dict[str, Any]) -> str:
    context = candidate.get("latest_context") or {}
    gear_type = str(candidate.get("type") or "gear").lower()
    admin_url = os.getenv("PROFILE_CANDIDATE_ADMIN_URL") or DEFAULT_ADMIN_REVIEW_URL
    lines = [
        f"A new DialedIN {gear_type} profile candidate needs review.",
        "",
        "Research should already be queued/running automatically. Open admin, check the score, review evidence, add an image if it is a machine, then promote it.",
        "",
        f"Name: {candidate.get('name_entered')}",
        f"Type: {gear_type}",
        f"Candidate key: {candidate.get('candidate_key')}",
        f"Status: {candidate.get('status')}",
        f"Seen count: {candidate.get('seen_count')}",
        f"Created at: {candidate.get('created_at')}",
        "",
        "Latest shot context:",
    ]
    if context:
        lines.extend(f"- {key}: {value}" for key, value in sorted(context.items()))
    else:
        lines.append("- none")
    lines.extend(["", f"Admin review: {admin_url}"])
    return "\n".join(lines)


def _enabled() -> bool:
    return os.getenv("PROFILE_CANDIDATE_EMAIL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _provider() -> str:
    value = os.getenv("PROFILE_CANDIDATE_EMAIL_PROVIDER", "ses").lower()
    return value if value in {"ses", "smtp"} else "ses"


def _use_tls() -> bool:
    return os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
