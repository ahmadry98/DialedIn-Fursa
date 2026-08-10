"""Notification helpers for profile candidate review events."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

DEFAULT_REVIEW_EMAIL = "ahmadrayan1998@gmail.com"


def notify_new_profile_candidate(candidate: dict[str, Any]) -> bool:
    """Send a non-blocking email when a new machine candidate is captured.

    Notifications are intentionally optional. In dev/CI, leave
    PROFILE_CANDIDATE_EMAIL_ENABLED unset/false. In cloud, configure SMTP env
    vars in the Kubernetes secret to enable real delivery.
    """
    if candidate.get("type") != "machine":
        return False
    if not _enabled():
        return False

    host = os.getenv("SMTP_HOST")
    if not host:
        print("Profile candidate email skipped: SMTP_HOST is not configured")
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME") or None
    password = os.getenv("SMTP_PASSWORD") or None
    sender = os.getenv("SMTP_FROM") or username or f"DialedIN <{DEFAULT_REVIEW_EMAIL}>"
    recipient = os.getenv("PROFILE_CANDIDATE_EMAIL_TO") or DEFAULT_REVIEW_EMAIL

    message = EmailMessage()
    message["Subject"] = f"DialedIN new machine candidate: {candidate.get('name_entered', 'unknown')}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(_candidate_email_body(candidate))

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if _use_tls():
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except Exception as error:  # pragma: no cover - network failure should never block chat.
        print(f"Profile candidate email failed: {error}")
        return False


def _candidate_email_body(candidate: dict[str, Any]) -> str:
    context = candidate.get("latest_context") or {}
    lines = [
        "A new DialedIN machine profile candidate needs review.",
        "",
        f"Name: {candidate.get('name_entered')}",
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
    lines.extend(["", "Open the Profile Candidate Review admin page to research and promote it."])
    return "\n".join(lines)


def _enabled() -> bool:
    return os.getenv("PROFILE_CANDIDATE_EMAIL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _use_tls() -> bool:
    return os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
