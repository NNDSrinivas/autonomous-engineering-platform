"""
Vercel webhook ingestion.

Handles Vercel deployment events.
Vercel webhooks are signed using HMAC-SHA1.
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

router = APIRouter(prefix="/api/webhooks/vercel", tags=["vercel_webhook"])
logger = logging.getLogger(__name__)


def verify_vercel_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """Verify Vercel webhook HMAC-SHA1 signature."""
    if not secret:
        logger.warning("vercel_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing x-vercel-signature header")

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha1,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("")
async def ingest(
    request: Request,
    x_vercel_signature: Optional[str] = Header(None, alias="x-vercel-signature"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Vercel webhooks.

    Vercel webhook events:
    - deployment.created: New deployment started
    - deployment.succeeded: Deployment completed successfully
    - deployment.ready: Deployment is ready to serve traffic
    - deployment.promoted: Deployment promoted to production
    - deployment.canceled: Deployment was canceled
    - deployment.error: Deployment failed
    - project.created: New project created
    - project.removed: Project was deleted
    """
    body = await request.body()
    verify_vercel_signature(x_vercel_signature, body, settings.vercel_webhook_secret)

    payload = await request.json()

    event_type = payload.get("type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        if event_type.startswith("deployment."):
            action = event_type.split(".")[1] if "." in event_type else "unknown"
            await _handle_deployment_event(payload, action, org_id, db)

        elif event_type.startswith("project."):
            action = event_type.split(".")[1] if "." in event_type else "unknown"
            await _handle_project_event(payload, action, org_id, db)

        else:
            logger.info(
                "vercel_webhook.unhandled_event",
                extra={"event": event_type},
            )

    except Exception as exc:
        logger.error(
            "vercel_webhook.error",
            extra={"event": event_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_deployment_event(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle deployment events."""
    # Vercel payload structure varies, but typically has these fields
    deployment = payload.get("payload") or payload

    deployment_id = deployment.get("id") or deployment.get("deploymentId") or ""
    deployment_url = deployment.get("url") or ""
    if deployment_url and not deployment_url.startswith("http"):
        deployment_url = f"https://{deployment_url}"

    # Project info
    project_name = (
        deployment.get("project", {}).get("name") or deployment.get("name") or "unknown"
    )
    project_id = (
        deployment.get("project", {}).get("id") or deployment.get("projectId") or ""
    )

    # Target and meta
    target = deployment.get("target") or "preview"
    meta = deployment.get("meta") or {}

    # Git info
    git_source = meta.get("githubCommitRef") or meta.get("gitlabCommitRef") or ""
    git_sha = (meta.get("githubCommitSha") or meta.get("gitlabCommitSha") or "")[:8]
    git_message = (
        meta.get("githubCommitMessage") or meta.get("gitlabCommitMessage") or ""
    )[:100]
    git_author = (
        meta.get("githubCommitAuthorName") or meta.get("gitlabCommitAuthorName") or ""
    )

    # User info
    user = payload.get("user") or {}
    user_name = user.get("username") or user.get("name") or "system"

    # Team info
    team = payload.get("team") or {}
    team_name = team.get("name") or team.get("slug") or ""

    # Build status details
    state = deployment.get("state") or deployment.get("readyState") or action

    # Inspect URL for failed builds
    inspect_url = deployment.get("inspectorUrl") or ""

    # Status mapping for display
    status_map = {
        "created": "building",
        "building": "building",
        "succeeded": "success",
        "ready": "ready",
        "promoted": "promoted",
        "canceled": "canceled",
        "error": "failed",
    }
    display_status = status_map.get(action, action)

    # Build text description
    text_parts = [f"Deployment {action} for {project_name}"]
    if target == "production":
        text_parts.append("(production)")
    if git_source:
        text_parts.append(f"on branch {git_source}")
    if git_sha:
        text_parts.append(f"commit {git_sha}")
    if git_author:
        text_parts.append(f"by {git_author}")

    text = " ".join(text_parts)
    if git_message:
        text += f"\nCommit: {git_message}"

    node = MemoryNode(
        org_id=org_id,
        node_type="vercel_deployment",
        title=f"Vercel: {project_name} [{display_status}]",
        text=text,
        meta_json={
            "deployment_id": deployment_id,
            "action": action,
            "state": state,
            "display_status": display_status,
            "url": deployment_url,
            "inspect_url": inspect_url,
            "project_id": project_id,
            "project_name": project_name,
            "target": target,
            "git_branch": git_source,
            "git_sha": git_sha,
            "git_message": git_message,
            "git_author": git_author,
            "user": user_name,
            "team": team_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "vercel_webhook.deployment",
        extra={
            "deployment_id": deployment_id,
            "action": action,
            "project": project_name,
            "target": target,
            "branch": git_source,
        },
    )


async def _handle_project_event(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle project events."""
    project = payload.get("payload") or payload

    project_id = project.get("id") or ""
    project_name = project.get("name") or "unknown"
    project_slug = project.get("slug") or project_name

    # Framework
    framework = project.get("framework") or ""

    # User info
    user = payload.get("user") or {}
    user_name = user.get("username") or user.get("name") or "system"

    # Team info
    team = payload.get("team") or {}
    team_name = team.get("name") or team.get("slug") or ""

    # Git repository
    git_repo = project.get("link") or {}
    repo_type = git_repo.get("type") or ""
    repo_name = git_repo.get("repo") or ""

    text = f"Project '{project_name}' was {action}"
    if user_name:
        text += f" by {user_name}"
    if repo_name:
        text += f" (connected to {repo_type}: {repo_name})"

    node = MemoryNode(
        org_id=org_id,
        node_type="vercel_project",
        title=f"Vercel Project: {project_name} [{action}]",
        text=text,
        meta_json={
            "project_id": project_id,
            "project_name": project_name,
            "project_slug": project_slug,
            "action": action,
            "framework": framework,
            "repo_type": repo_type,
            "repo_name": repo_name,
            "user": user_name,
            "team": team_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "vercel_webhook.project",
        extra={
            "project_id": project_id,
            "project_name": project_name,
            "action": action,
            "user": user_name,
        },
    )
