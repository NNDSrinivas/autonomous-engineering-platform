"""
CircleCI webhook ingestion.

Handles CircleCI workflow and job completion events.
CircleCI webhooks are signed using HMAC-SHA256.
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

router = APIRouter(prefix="/api/webhooks/circleci", tags=["circleci_webhook"])
logger = logging.getLogger(__name__)


def verify_circleci_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """Verify CircleCI webhook HMAC-SHA256 signature."""
    if not secret:
        logger.warning("circleci_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing Circleci-Signature header")

    # CircleCI signature format: v1=<signature>
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
    circleci_signature: Optional[str] = Header(None, alias="Circleci-Signature"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest CircleCI webhooks.

    CircleCI webhook events:
    - workflow-completed: A workflow has finished
    - job-completed: A job has finished
    """
    body = await request.body()
    verify_circleci_signature(circleci_signature, body, settings.circleci_webhook_secret)

    payload = await request.json()

    event_type = payload.get("type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        if event_type == "workflow-completed":
            await _handle_workflow_completed(payload, org_id, db)

        elif event_type == "job-completed":
            await _handle_job_completed(payload, org_id, db)

        else:
            logger.info(
                "circleci_webhook.unhandled_event",
                extra={"event": event_type},
            )

    except Exception as exc:
        logger.error(
            "circleci_webhook.error",
            extra={"event": event_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_workflow_completed(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle workflow completion events."""
    workflow = payload.get("workflow") or {}
    pipeline = payload.get("pipeline") or {}
    project = payload.get("project") or {}

    workflow_id = workflow.get("id") or ""
    workflow_name = workflow.get("name") or "unknown"
    workflow_status = workflow.get("status") or "unknown"
    workflow_url = workflow.get("url") or ""

    pipeline_id = pipeline.get("id") or ""
    pipeline_number = pipeline.get("number") or 0

    project_slug = project.get("slug") or ""
    project_name = project.get("name") or ""

    # VCS info
    vcs = pipeline.get("vcs") or {}
    branch = vcs.get("branch") or ""
    commit_sha = vcs.get("revision", "")[:8] if vcs.get("revision") else ""
    commit_message = (vcs.get("commit", {}).get("subject") or "")[:100]
    author = vcs.get("commit", {}).get("author", {}).get("name") or ""

    # Timing
    created_at = workflow.get("created_at") or ""
    stopped_at = workflow.get("stopped_at") or ""

    # Status emoji for quick visual
    status_emoji = {
        "success": "success",
        "failed": "failed",
        "canceled": "canceled",
        "on_hold": "on_hold",
    }.get(workflow_status, workflow_status)

    node = MemoryNode(
        org_id=org_id,
        node_type="circleci_workflow",
        title=f"CircleCI: {workflow_name} [{status_emoji}]",
        text=f"Workflow '{workflow_name}' {workflow_status} for {project_name}. "
             f"Branch: {branch}, Commit: {commit_sha}",
        meta_json={
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": workflow_status,
            "url": workflow_url,
            "pipeline_id": pipeline_id,
            "pipeline_number": pipeline_number,
            "project_slug": project_slug,
            "project_name": project_name,
            "branch": branch,
            "commit_sha": commit_sha,
            "commit_message": commit_message,
            "author": author,
            "created_at": created_at,
            "stopped_at": stopped_at,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "circleci_webhook.workflow_completed",
        extra={
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": workflow_status,
            "project": project_slug,
            "branch": branch,
        },
    )


async def _handle_job_completed(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle job completion events."""
    job = payload.get("job") or {}
    workflow = payload.get("workflow") or {}
    pipeline = payload.get("pipeline") or {}
    project = payload.get("project") or {}

    job_id = job.get("id") or ""
    job_name = job.get("name") or "unknown"
    job_number = job.get("number") or 0
    job_status = job.get("status") or "unknown"

    workflow_id = workflow.get("id") or ""
    workflow_name = workflow.get("name") or "unknown"

    pipeline_id = pipeline.get("id") or ""
    pipeline_number = pipeline.get("number") or 0

    project_slug = project.get("slug") or ""
    project_name = project.get("name") or ""

    # VCS info
    vcs = pipeline.get("vcs") or {}
    branch = vcs.get("branch") or ""
    commit_sha = vcs.get("revision", "")[:8] if vcs.get("revision") else ""

    # Timing
    started_at = job.get("started_at") or ""
    stopped_at = job.get("stopped_at") or ""

    # Calculate duration if possible
    duration_text = ""
    if started_at and stopped_at:
        try:
            from datetime import datetime as dt
            start = dt.fromisoformat(started_at.replace("Z", "+00:00"))
            stop = dt.fromisoformat(stopped_at.replace("Z", "+00:00"))
            duration = stop - start
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            duration_text = f"{minutes}m {seconds}s"
        except Exception:
            pass

    status_emoji = {
        "success": "success",
        "failed": "failed",
        "canceled": "canceled",
        "infrastructure_fail": "infra_fail",
        "timedout": "timeout",
    }.get(job_status, job_status)

    text = f"Job '{job_name}' {job_status} in workflow '{workflow_name}'"
    if duration_text:
        text += f" (took {duration_text})"

    node = MemoryNode(
        org_id=org_id,
        node_type="circleci_job",
        title=f"CircleCI Job: {job_name} [{status_emoji}]",
        text=text,
        meta_json={
            "job_id": job_id,
            "job_name": job_name,
            "job_number": job_number,
            "status": job_status,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "pipeline_id": pipeline_id,
            "pipeline_number": pipeline_number,
            "project_slug": project_slug,
            "project_name": project_name,
            "branch": branch,
            "commit_sha": commit_sha,
            "started_at": started_at,
            "stopped_at": stopped_at,
            "duration": duration_text,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "circleci_webhook.job_completed",
        extra={
            "job_id": job_id,
            "job_name": job_name,
            "status": job_status,
            "workflow": workflow_name,
            "project": project_slug,
        },
    )
