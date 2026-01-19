"""
Sentry webhook ingestion.

Handles Sentry issue and event alerts.
Sentry webhooks use HMAC-SHA256 signatures.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/sentry", tags=["sentry_webhook"])
logger = logging.getLogger(__name__)


def verify_sentry_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """
    Verify Sentry webhook signature.

    Sentry uses HMAC-SHA256 with the signature in sentry-hook-signature header.
    """
    if not secret:
        logger.warning("sentry_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing sentry-hook-signature header")

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("")
async def ingest(
    request: Request,
    sentry_hook_signature: Optional[str] = Header(None, alias="sentry-hook-signature"),
    sentry_hook_resource: Optional[str] = Header(None, alias="sentry-hook-resource"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Sentry webhooks.

    Sentry webhook resources:
    - installation: App installed/uninstalled
    - event_alert: Alert rule triggered
    - issue: Issue created/resolved/assigned/ignored
    - metric_alert: Metric alert triggered/resolved
    - error: Error event received
    - comment: Comment added to issue
    """
    body = await request.body()
    verify_sentry_signature(sentry_hook_signature, body, settings.sentry_webhook_secret)

    payload = await request.json()

    resource = sentry_hook_resource or payload.get("resource") or "unknown"
    action = payload.get("action") or "triggered"
    org_id = x_org_id or settings.x_org_id

    try:
        if resource == "event_alert":
            await _handle_event_alert(payload, action, org_id, db)

        elif resource == "issue":
            await _handle_issue(payload, action, org_id, db)

        elif resource == "metric_alert":
            await _handle_metric_alert(payload, action, org_id, db)

        elif resource == "error":
            await _handle_error(payload, action, org_id, db)

        elif resource == "comment":
            await _handle_comment(payload, action, org_id, db)

        elif resource == "installation":
            await _handle_installation(payload, action, org_id, db)

        else:
            logger.info(
                "sentry_webhook.unhandled_resource",
                extra={"resource": resource, "action": action},
            )

    except Exception as exc:
        logger.error(
            "sentry_webhook.error",
            extra={"resource": resource, "action": action, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_event_alert(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle event alert webhooks (issue alert triggered)."""
    data = payload.get("data") or {}

    # Event details
    event = data.get("event") or {}
    event_id = event.get("event_id") or ""
    title = event.get("title") or "Unknown Error"
    message = event.get("message") or ""
    level = event.get("level") or "error"
    platform = event.get("platform") or ""
    timestamp = event.get("timestamp") or ""

    # Location info
    culprit = event.get("culprit") or ""
    location = event.get("location") or culprit

    # Tags
    tags = event.get("tags") or []
    tag_dict = {t[0]: t[1] for t in tags if len(t) >= 2}
    environment = tag_dict.get("environment", "")
    release = tag_dict.get("release", "")
    server_name = tag_dict.get("server_name", "")

    # Issue details
    issue_id = event.get("issue_id") or ""
    issue_url = event.get("web_url") or ""

    # Triggered rule
    triggered_rule = data.get("triggered_rule") or ""

    # Project
    project = event.get("project") or data.get("project") or ""
    project_name = project if isinstance(project, str) else project.get("name", "")
    project_slug = project if isinstance(project, str) else project.get("slug", "")

    # Exception info
    exception_info = _extract_exception_info(event)

    text = f"[{level.upper()}] {title}"
    if location:
        text += f"\nLocation: {location}"
    if exception_info:
        text += f"\n{exception_info}"
    if triggered_rule:
        text += f"\nRule: {triggered_rule}"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_event_alert",
        title=f"Sentry Alert: {title[:50]}",
        text=text,
        meta_json={
            "event_id": event_id,
            "issue_id": issue_id,
            "title": title,
            "message": message,
            "level": level,
            "platform": platform,
            "location": location,
            "culprit": culprit,
            "environment": environment,
            "release": release,
            "server_name": server_name,
            "project_name": project_name,
            "project_slug": project_slug,
            "triggered_rule": triggered_rule,
            "timestamp": timestamp,
            "url": issue_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.event_alert",
        extra={
            "event_id": event_id,
            "issue_id": issue_id,
            "level": level,
            "project": project_name,
            "rule": triggered_rule,
        },
    )


async def _handle_issue(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle issue webhooks (created, resolved, assigned, ignored)."""
    data = payload.get("data") or {}
    issue = data.get("issue") or {}

    issue_id = issue.get("id") or ""
    title = issue.get("title") or "Unknown Issue"
    culprit = issue.get("culprit") or ""
    level = issue.get("level") or "error"
    status = issue.get("status") or "unresolved"
    platform = issue.get("platform") or ""
    first_seen = issue.get("firstSeen") or ""
    last_seen = issue.get("lastSeen") or ""
    count = issue.get("count") or 0
    user_count = issue.get("userCount") or 0

    # Project info
    project = issue.get("project") or {}
    project_name = project.get("name") or ""
    project_slug = project.get("slug") or ""

    # URL
    issue_url = issue.get("permalink") or ""

    # Actor (who performed the action)
    actor = payload.get("actor") or {}
    actor_name = actor.get("name") or actor.get("email") or "System"
    actor_type = actor.get("type") or "unknown"

    # Build description
    if action == "created":
        text = f"[{level.upper()}] New issue: {title}"
    elif action == "resolved":
        text = f"Issue resolved by {actor_name}: {title}"
    elif action == "assigned":
        assignee = data.get("assignee") or {}
        assignee_name = assignee.get("name") or assignee.get("email") or "someone"
        text = f"Issue assigned to {assignee_name}: {title}"
    elif action == "ignored":
        text = f"Issue ignored by {actor_name}: {title}"
    elif action == "unresolved":
        text = f"Issue reopened: {title}"
    else:
        text = f"Issue {action}: {title}"

    if culprit:
        text += f"\nLocation: {culprit}"
    text += f"\nEvents: {count}, Users: {user_count}"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_issue",
        title=f"Sentry Issue: {title[:40]} [{action}]",
        text=text,
        meta_json={
            "issue_id": issue_id,
            "title": title,
            "culprit": culprit,
            "level": level,
            "status": status,
            "action": action,
            "platform": platform,
            "project_name": project_name,
            "project_slug": project_slug,
            "event_count": count,
            "user_count": user_count,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "actor_name": actor_name,
            "actor_type": actor_type,
            "url": issue_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.issue",
        extra={
            "issue_id": issue_id,
            "action": action,
            "level": level,
            "project": project_name,
            "actor": actor_name,
        },
    )


async def _handle_metric_alert(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle metric alert webhooks."""
    data = payload.get("data") or {}

    # Metric alert details
    metric_alert = data.get("metric_alert") or {}
    alert_id = metric_alert.get("id") or ""
    alert_name = metric_alert.get("alert_rule", {}).get("name") or "Unknown Alert"

    # Description info
    description_title = data.get("description_title") or alert_name
    description_text = data.get("description_text") or ""

    # Trigger info
    triggered_by = data.get("triggered_by") or "unknown"

    # Status
    status = "critical" if action == "critical" else ("warning" if action == "warning" else action)

    # Web URL
    web_url = data.get("web_url") or ""

    # Organization
    organization = payload.get("organization") or {}
    org_name = organization.get("name") or ""

    if action in ["critical", "warning"]:
        text = f"[{status.upper()}] Metric alert triggered: {description_title}"
    elif action == "resolved":
        text = f"Metric alert resolved: {description_title}"
    else:
        text = f"Metric alert {action}: {description_title}"

    if description_text:
        text += f"\n{description_text}"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_metric_alert",
        title=f"Sentry Metric: {alert_name[:40]} [{status}]",
        text=text,
        meta_json={
            "alert_id": alert_id,
            "alert_name": alert_name,
            "status": status,
            "action": action,
            "description_title": description_title,
            "description_text": description_text,
            "triggered_by": triggered_by,
            "org_name": org_name,
            "url": web_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.metric_alert",
        extra={
            "alert_id": alert_id,
            "alert_name": alert_name,
            "status": status,
            "action": action,
        },
    )


async def _handle_error(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle error event webhooks."""
    data = payload.get("data") or {}
    error = data.get("error") or data

    error_id = error.get("id") or error.get("event_id") or ""
    title = error.get("title") or error.get("message") or "Unknown Error"
    level = error.get("level") or "error"
    platform = error.get("platform") or ""
    culprit = error.get("culprit") or ""

    # Project
    project = error.get("project") or data.get("project") or {}
    project_name = project.get("name") if isinstance(project, dict) else str(project)

    # URL
    url = error.get("web_url") or error.get("url") or ""

    text = f"[{level.upper()}] {title}"
    if culprit:
        text += f"\nLocation: {culprit}"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_error",
        title=f"Sentry Error: {title[:50]}",
        text=text,
        meta_json={
            "error_id": error_id,
            "title": title,
            "level": level,
            "platform": platform,
            "culprit": culprit,
            "project_name": project_name,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.error",
        extra={
            "error_id": error_id,
            "level": level,
            "project": project_name,
        },
    )


async def _handle_comment(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle comment webhooks."""
    data = payload.get("data") or {}
    comment = data.get("comment") or ""

    # Issue info
    issue = data.get("issue") or {}
    issue_id = issue.get("id") or ""
    issue_title = issue.get("title") or "Unknown Issue"
    issue_url = issue.get("permalink") or ""

    # Project
    project = data.get("project") or issue.get("project") or {}
    project_name = project.get("name") if isinstance(project, dict) else str(project)

    # Actor
    actor = payload.get("actor") or {}
    actor_name = actor.get("name") or actor.get("email") or "Someone"

    text = f"{actor_name} commented on issue '{issue_title}':\n{comment[:500]}"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_comment",
        title=f"Sentry Comment: {issue_title[:40]}",
        text=text,
        meta_json={
            "issue_id": issue_id,
            "issue_title": issue_title,
            "comment": comment,
            "actor_name": actor_name,
            "project_name": project_name,
            "action": action,
            "url": issue_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.comment",
        extra={
            "issue_id": issue_id,
            "actor": actor_name,
            "project": project_name,
        },
    )


async def _handle_installation(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle installation webhooks."""
    data = payload.get("data") or {}
    installation = data.get("installation") or {}

    installation_id = installation.get("uuid") or ""
    app_name = installation.get("app", {}).get("name") or "Sentry App"

    # Organization
    organization = installation.get("organization") or {}
    org_name = organization.get("name") or organization.get("slug") or ""

    text = f"Sentry app '{app_name}' {action} for organization '{org_name}'"

    node = MemoryNode(
        org_id=org_id,
        node_type="sentry_installation",
        title=f"Sentry App: {app_name} [{action}]",
        text=text,
        meta_json={
            "installation_id": installation_id,
            "app_name": app_name,
            "org_name": org_name,
            "action": action,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "sentry_webhook.installation",
        extra={
            "installation_id": installation_id,
            "app_name": app_name,
            "action": action,
            "org": org_name,
        },
    )


def _extract_exception_info(event: dict) -> str:
    """Extract exception information from event."""
    entries = event.get("entries") or []
    for entry in entries:
        if entry.get("type") == "exception":
            exception_data = entry.get("data", {})
            values = exception_data.get("values", [])
            if values:
                exc = values[-1]
                exc_type = exc.get("type", "Error")
                exc_value = exc.get("value", "")

                # Get first frame of stacktrace
                stacktrace = exc.get("stacktrace", {})
                frames = stacktrace.get("frames", [])
                if frames:
                    last_frame = frames[-1]
                    filename = last_frame.get("filename", "")
                    lineno = last_frame.get("lineno", "")
                    function = last_frame.get("function", "")
                    return f"{exc_type}: {exc_value}\n  at {function} ({filename}:{lineno})"

                return f"{exc_type}: {exc_value}"

    return ""
