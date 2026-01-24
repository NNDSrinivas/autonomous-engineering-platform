"""
GitLab webhook ingestion with token verification.

Handles GitLab push, merge request, issue, and pipeline events.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/gitlab", tags=["gitlab_webhook"])
logger = logging.getLogger(__name__)


def verify_gitlab_token(
    token: Optional[str],
    expected_token: Optional[str],
) -> None:
    """Verify GitLab webhook secret token."""
    if not expected_token:
        logger.warning("gitlab_webhook.no_secret_configured")
        return

    if not token:
        raise HTTPException(status_code=401, detail="Missing X-Gitlab-Token header")

    if not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid webhook token")


@router.post("")
async def ingest(
    request: Request,
    x_gitlab_token: Optional[str] = Header(None, alias="X-Gitlab-Token"),
    x_gitlab_event: Optional[str] = Header(None, alias="X-Gitlab-Event"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest GitLab webhooks (Push, MR, Issue, Pipeline).

    GitLab webhook events:
    - Push Hook
    - Merge Request Hook
    - Issue Hook
    - Pipeline Hook
    - Note Hook (comments)
    """
    verify_gitlab_token(x_gitlab_token, settings.gitlab_webhook_secret)

    if not x_gitlab_event:
        raise HTTPException(status_code=400, detail="Missing X-Gitlab-Event header")

    payload = await request.json()

    # Extract project info
    project = payload.get("project") or {}
    project_name = (
        project.get("path_with_namespace") or project.get("name") or "unknown"
    )
    project_url = project.get("web_url") or ""

    org_id = x_org_id or settings.x_org_id

    try:
        if x_gitlab_event == "Push Hook":
            await _handle_push(payload, project_name, project_url, org_id, db)

        elif x_gitlab_event == "Merge Request Hook":
            await _handle_merge_request(payload, project_name, project_url, org_id, db)

        elif x_gitlab_event == "Issue Hook":
            await _handle_issue(payload, project_name, project_url, org_id, db)

        elif x_gitlab_event == "Pipeline Hook":
            await _handle_pipeline(payload, project_name, project_url, org_id, db)

        elif x_gitlab_event == "Note Hook":
            await _handle_note(payload, project_name, project_url, org_id, db)

        else:
            logger.info(
                "gitlab_webhook.unhandled_event", extra={"event": x_gitlab_event}
            )

    except Exception as exc:
        logger.error(
            "gitlab_webhook.error",
            extra={"event": x_gitlab_event, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_push(
    payload: dict,
    project_name: str,
    project_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle push events."""
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
    commits = payload.get("commits") or []
    user_name = payload.get("user_name") or "unknown"

    commit_messages = [c.get("message", "")[:100] for c in commits[:5]]

    node = MemoryNode(
        org_id=org_id,
        node_type="gitlab_push",
        title=f"Push to {project_name}:{branch}",
        text=f"User {user_name} pushed {len(commits)} commit(s):\n"
        + "\n".join(commit_messages),
        meta_json={
            "project": project_name,
            "project_url": project_url,
            "branch": branch,
            "user": user_name,
            "commit_count": len(commits),
            "before": payload.get("before"),
            "after": payload.get("after"),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "gitlab_webhook.push",
        extra={"project": project_name, "branch": branch, "commits": len(commits)},
    )


async def _handle_merge_request(
    payload: dict,
    project_name: str,
    project_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle merge request events."""
    mr = payload.get("object_attributes") or {}
    action = mr.get("action") or payload.get("action", "unknown")
    mr_iid = mr.get("iid")
    title = mr.get("title") or ""
    description = mr.get("description") or ""
    state = mr.get("state") or "unknown"
    source_branch = mr.get("source_branch") or ""
    target_branch = mr.get("target_branch") or ""
    url = mr.get("url") or ""

    user = payload.get("user") or {}
    user_name = user.get("name") or user.get("username") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="gitlab_merge_request",
        title=f"MR !{mr_iid}: {title}",
        text=description[:500] if description else f"MR {action} by {user_name}",
        meta_json={
            "project": project_name,
            "project_url": project_url,
            "mr_iid": mr_iid,
            "action": action,
            "state": state,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "url": url,
            "user": user_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "gitlab_webhook.merge_request",
        extra={
            "project": project_name,
            "mr_iid": mr_iid,
            "action": action,
            "state": state,
        },
    )


async def _handle_issue(
    payload: dict,
    project_name: str,
    project_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle issue events."""
    issue = payload.get("object_attributes") or {}
    action = issue.get("action") or payload.get("action", "unknown")
    issue_iid = issue.get("iid")
    title = issue.get("title") or ""
    description = issue.get("description") or ""
    state = issue.get("state") or "unknown"
    url = issue.get("url") or ""

    user = payload.get("user") or {}
    user_name = user.get("name") or user.get("username") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="gitlab_issue",
        title=f"Issue #{issue_iid}: {title}",
        text=description[:500] if description else f"Issue {action} by {user_name}",
        meta_json={
            "project": project_name,
            "project_url": project_url,
            "issue_iid": issue_iid,
            "action": action,
            "state": state,
            "url": url,
            "user": user_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "gitlab_webhook.issue",
        extra={
            "project": project_name,
            "issue_iid": issue_iid,
            "action": action,
            "state": state,
        },
    )


async def _handle_pipeline(
    payload: dict,
    project_name: str,
    project_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle pipeline events."""
    pipeline = payload.get("object_attributes") or {}
    pipeline_id = pipeline.get("id")
    status = pipeline.get("status") or "unknown"
    ref = pipeline.get("ref") or ""
    sha = pipeline.get("sha") or ""
    duration = pipeline.get("duration")

    user = payload.get("user") or {}
    user_name = user.get("name") or user.get("username") or "unknown"

    # Get job details
    builds = payload.get("builds") or []
    failed_jobs = [b.get("name") for b in builds if b.get("status") == "failed"]

    text = f"Pipeline {status} on {ref}"
    if failed_jobs:
        text += f"\nFailed jobs: {', '.join(failed_jobs[:5])}"
    if duration:
        text += f"\nDuration: {duration}s"

    node = MemoryNode(
        org_id=org_id,
        node_type="gitlab_pipeline",
        title=f"Pipeline #{pipeline_id} {status}",
        text=text,
        meta_json={
            "project": project_name,
            "project_url": project_url,
            "pipeline_id": pipeline_id,
            "status": status,
            "ref": ref,
            "sha": sha[:8] if sha else None,
            "duration": duration,
            "failed_jobs": failed_jobs[:5] if failed_jobs else [],
            "user": user_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "gitlab_webhook.pipeline",
        extra={
            "project": project_name,
            "pipeline_id": pipeline_id,
            "status": status,
            "ref": ref,
        },
    )


async def _handle_note(
    payload: dict,
    project_name: str,
    project_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle note (comment) events."""
    note = payload.get("object_attributes") or {}
    note_id = note.get("id")
    noteable_type = note.get("noteable_type") or "unknown"
    body = note.get("note") or ""
    url = note.get("url") or ""

    user = payload.get("user") or {}
    user_name = user.get("name") or user.get("username") or "unknown"

    # Get the parent object info
    parent_title = ""
    parent_id = None
    if noteable_type == "MergeRequest":
        mr = payload.get("merge_request") or {}
        parent_title = mr.get("title") or ""
        parent_id = mr.get("iid")
    elif noteable_type == "Issue":
        issue = payload.get("issue") or {}
        parent_title = issue.get("title") or ""
        parent_id = issue.get("iid")
    elif noteable_type == "Commit":
        commit = payload.get("commit") or {}
        parent_title = commit.get("message", "")[:50]
        parent_id = commit.get("id", "")[:8]

    node = MemoryNode(
        org_id=org_id,
        node_type="gitlab_note",
        title=f"Comment on {noteable_type} {parent_id}: {parent_title[:50]}",
        text=body[:500],
        meta_json={
            "project": project_name,
            "project_url": project_url,
            "note_id": note_id,
            "noteable_type": noteable_type,
            "parent_id": parent_id,
            "url": url,
            "user": user_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "gitlab_webhook.note",
        extra={
            "project": project_name,
            "noteable_type": noteable_type,
            "parent_id": parent_id,
        },
    )
