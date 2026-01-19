"""
PagerDuty webhook ingestion.

Handles PagerDuty incident events (triggered, acknowledged, resolved, etc.).
PagerDuty V3 webhooks use HMAC-SHA256 signatures.
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

router = APIRouter(prefix="/api/webhooks/pagerduty", tags=["pagerduty_webhook"])
logger = logging.getLogger(__name__)


def verify_pagerduty_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """
    Verify PagerDuty webhook signature (V3).

    PagerDuty V3 uses HMAC-SHA256 with the signature in x-pagerduty-signature header.
    Format: v1=<signature>
    """
    if not secret:
        logger.warning("pagerduty_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing x-pagerduty-signature header")

    # Extract signature from v1=<signature> format
    if signature.startswith("v1="):
        signature = signature[3:]

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
    x_pagerduty_signature: Optional[str] = Header(None, alias="x-pagerduty-signature"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest PagerDuty webhooks (V3 format).

    PagerDuty V3 webhook events:
    - incident.triggered: New incident
    - incident.acknowledged: Incident acknowledged
    - incident.unacknowledged: Acknowledgement expired
    - incident.resolved: Incident resolved
    - incident.reassigned: Incident reassigned
    - incident.escalated: Incident escalated
    - incident.delegated: Incident delegated
    - incident.priority_updated: Priority changed
    - incident.responder.added: Responder added
    - incident.responder.replied: Responder replied
    - incident.status_update_published: Status update published
    """
    body = await request.body()
    verify_pagerduty_signature(x_pagerduty_signature, body, settings.pagerduty_webhook_secret)

    payload = await request.json()

    # V3 webhook format has "event" wrapper
    event = payload.get("event") or {}
    event_type = event.get("event_type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        if event_type.startswith("incident."):
            await _handle_incident_event(payload, event_type, org_id, db)
        else:
            logger.info(
                "pagerduty_webhook.unhandled_event",
                extra={"event": event_type},
            )

    except Exception as exc:
        logger.error(
            "pagerduty_webhook.error",
            extra={"event": event_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_incident_event(
    payload: dict,
    event_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle incident events."""
    event = payload.get("event") or {}
    event_data = event.get("data") or {}

    # Extract incident details
    incident = event_data.get("incident") or event_data
    incident_id = incident.get("id") or ""
    incident_number = incident.get("incident_number") or ""
    title = incident.get("title") or incident.get("summary") or "Untitled"
    status = incident.get("status") or "triggered"
    urgency = incident.get("urgency") or "high"
    priority = incident.get("priority") or {}
    priority_name = priority.get("summary") or ""

    # Service info
    service = incident.get("service") or {}
    service_name = service.get("summary") or service.get("name") or "Unknown Service"

    # Escalation policy
    escalation_policy = incident.get("escalation_policy") or {}
    escalation_name = escalation_policy.get("summary") or ""

    # Assignees
    assignees = incident.get("assignments") or []
    assignee_names = [
        a.get("assignee", {}).get("summary", "")
        for a in assignees
        if a.get("assignee", {}).get("summary")
    ]

    # Triggered at
    created_at_str = incident.get("created_at") or ""

    # HTML URL
    html_url = incident.get("html_url") or ""

    # Agent (who performed the action)
    agent = event.get("agent") or {}
    agent_type = agent.get("type") or "system"
    agent_name = agent.get("summary") or "System"

    # Build description based on event type
    action = event_type.replace("incident.", "")

    if action == "triggered":
        text = f"[{urgency.upper()}] Incident triggered on {service_name}: {title}"
        if priority_name:
            text = f"[{priority_name}] {text}"
    elif action == "acknowledged":
        text = f"{agent_name} acknowledged incident on {service_name}: {title}"
    elif action == "unacknowledged":
        text = f"Acknowledgement expired for incident on {service_name}: {title}"
    elif action == "resolved":
        text = f"{agent_name} resolved incident on {service_name}: {title}"
    elif action == "reassigned":
        assignees_str = ", ".join(assignee_names) if assignee_names else "unassigned"
        text = f"Incident reassigned to {assignees_str}: {title}"
    elif action == "escalated":
        text = f"Incident escalated on {service_name}: {title}"
        if escalation_name:
            text += f" (Policy: {escalation_name})"
    elif action == "delegated":
        text = f"Incident delegated on {service_name}: {title}"
    elif action == "priority_updated":
        text = f"Priority changed to {priority_name} for incident: {title}"
    elif action == "responder.added":
        responder = event_data.get("responder") or {}
        responder_name = responder.get("summary") or "Someone"
        text = f"{responder_name} added as responder to incident: {title}"
    elif action == "responder.replied":
        responder = event_data.get("responder") or {}
        responder_name = responder.get("summary") or "Someone"
        message = event_data.get("message") or ""
        text = f"{responder_name} replied to incident: {title}"
        if message:
            text += f"\nMessage: {message[:200]}"
    elif action == "status_update_published":
        status_update = event_data.get("status_update") or {}
        update_message = status_update.get("message") or ""
        text = f"Status update for incident {title}"
        if update_message:
            text += f": {update_message[:200]}"
    else:
        text = f"Incident {action} on {service_name}: {title}"

    node = MemoryNode(
        org_id=org_id,
        node_type="pagerduty_incident",
        title=f"PagerDuty: {title[:50]} [{status}]",
        text=text,
        meta_json={
            "incident_id": incident_id,
            "incident_number": incident_number,
            "title": title,
            "status": status,
            "urgency": urgency,
            "priority": priority_name,
            "service_name": service_name,
            "escalation_policy": escalation_name,
            "assignees": assignee_names,
            "event_type": event_type,
            "action": action,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "created_at": created_at_str,
            "url": html_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "pagerduty_webhook.incident",
        extra={
            "incident_id": incident_id,
            "incident_number": incident_number,
            "event_type": event_type,
            "service": service_name,
            "status": status,
            "urgency": urgency,
        },
    )


@router.post("/v2")
async def ingest_v2(
    request: Request,
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest PagerDuty V2 webhooks (legacy format).

    V2 webhooks don't have signatures but are still in use.
    """
    payload = await request.json()

    messages = payload.get("messages") or []
    org_id = x_org_id or settings.x_org_id

    for message in messages:
        event_type = message.get("event") or "unknown"
        message.get("incident") or {}

        try:
            await _handle_v2_incident(message, event_type, org_id, db)
        except Exception as exc:
            logger.error(
                "pagerduty_webhook_v2.error",
                extra={"event": event_type, "error": str(exc)},
            )

    return {"status": "ok"}


async def _handle_v2_incident(
    message: dict,
    event_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle V2 format incident."""
    incident = message.get("incident") or {}
    incident_id = incident.get("id") or ""
    incident_number = incident.get("incident_number") or ""
    title = incident.get("title") or "Untitled"
    status = incident.get("status") or "triggered"
    urgency = incident.get("urgency") or "high"

    service = incident.get("service") or {}
    service_name = service.get("name") or "Unknown Service"

    assignees = incident.get("assignments") or []
    assignee_names = [
        a.get("assignee", {}).get("summary", "")
        for a in assignees
        if a.get("assignee", {}).get("summary")
    ]

    html_url = incident.get("html_url") or ""

    # Map V2 event types
    action_map = {
        "incident.trigger": "triggered",
        "incident.acknowledge": "acknowledged",
        "incident.unacknowledge": "unacknowledged",
        "incident.resolve": "resolved",
        "incident.assign": "reassigned",
        "incident.escalate": "escalated",
        "incident.delegate": "delegated",
    }
    action = action_map.get(event_type, event_type)

    text = f"[{urgency.upper()}] Incident {action} on {service_name}: {title}"

    node = MemoryNode(
        org_id=org_id,
        node_type="pagerduty_incident",
        title=f"PagerDuty: {title[:50]} [{status}]",
        text=text,
        meta_json={
            "incident_id": incident_id,
            "incident_number": incident_number,
            "title": title,
            "status": status,
            "urgency": urgency,
            "service_name": service_name,
            "assignees": assignee_names,
            "event_type": event_type,
            "action": action,
            "webhook_version": "v2",
            "url": html_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "pagerduty_webhook_v2.incident",
        extra={
            "incident_id": incident_id,
            "event_type": event_type,
            "service": service_name,
        },
    )
