"""
Bitbucket webhook ingestion.

Handles Bitbucket push, pull request, issue, and pipeline events.
Bitbucket Cloud webhooks are signed using HMAC-SHA256.
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

router = APIRouter(prefix="/api/webhooks/bitbucket", tags=["bitbucket_webhook"])
logger = logging.getLogger(__name__)


def verify_bitbucket_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """Verify Bitbucket webhook HMAC-SHA256 signature."""
    if not secret:
        logger.warning("bitbucket_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature header")

    # Bitbucket uses "sha256=<signature>" format
    if signature.startswith("sha256="):
        signature = signature[7:]

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
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature"),
    x_event_key: Optional[str] = Header(None, alias="X-Event-Key"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Bitbucket webhooks.

    Bitbucket webhook events (X-Event-Key):
    - repo:push
    - pullrequest:created, pullrequest:updated, pullrequest:approved,
      pullrequest:unapproved, pullrequest:fulfilled, pullrequest:rejected
    - pullrequest:comment_created
    - issue:created, issue:updated
    - repo:commit_status_created, repo:commit_status_updated
    """
    body = await request.body()
    verify_bitbucket_signature(x_hub_signature, body, settings.bitbucket_webhook_secret)

    if not x_event_key:
        raise HTTPException(status_code=400, detail="Missing X-Event-Key header")

    payload = await request.json()
    org_id = x_org_id or settings.x_org_id

    # Extract repo info
    repo = payload.get("repository") or {}
    repo_full_name = repo.get("full_name") or "unknown"
    repo_url = (repo.get("links") or {}).get("html", {}).get("href") or ""

    try:
        if x_event_key == "repo:push":
            await _handle_push(payload, repo_full_name, repo_url, org_id, db)

        elif x_event_key.startswith("pullrequest:"):
            action = x_event_key.split(":")[1] if ":" in x_event_key else "unknown"
            await _handle_pull_request(
                payload, action, repo_full_name, repo_url, org_id, db
            )

        elif x_event_key.startswith("issue:"):
            action = x_event_key.split(":")[1] if ":" in x_event_key else "unknown"
            await _handle_issue(payload, action, repo_full_name, repo_url, org_id, db)

        elif x_event_key.startswith("repo:commit_status"):
            await _handle_commit_status(payload, repo_full_name, repo_url, org_id, db)

        else:
            logger.info(
                "bitbucket_webhook.unhandled_event",
                extra={"event": x_event_key},
            )

    except Exception as exc:
        logger.error(
            "bitbucket_webhook.error",
            extra={"event": x_event_key, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_push(
    payload: dict,
    repo_full_name: str,
    repo_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle push events."""
    push = payload.get("push") or {}
    changes = push.get("changes") or []

    actor = payload.get("actor") or {}
    actor_name = actor.get("display_name") or actor.get("username") or "unknown"

    for change in changes[:5]:  # Limit to 5 changes
        new = change.get("new") or {}
        branch = new.get("name") or "unknown"
        target = new.get("target") or {}
        commit_hash = target.get("hash", "")[:8]
        commit_message = target.get("message") or ""

        commits = change.get("commits") or []
        commit_count = len(commits)

        node = MemoryNode(
            org_id=org_id,
            node_type="bitbucket_push",
            title=f"Push to {repo_full_name}:{branch}",
            text=f"{actor_name} pushed {commit_count} commit(s).\nLatest: {commit_message[:100]}",
            meta_json={
                "repo": repo_full_name,
                "repo_url": repo_url,
                "branch": branch,
                "commit_hash": commit_hash,
                "commit_count": commit_count,
                "actor": actor_name,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(node)

    db.commit()

    logger.info(
        "bitbucket_webhook.push",
        extra={"repo": repo_full_name, "changes": len(changes)},
    )


async def _handle_pull_request(
    payload: dict,
    action: str,
    repo_full_name: str,
    repo_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle pull request events."""
    pr = payload.get("pullrequest") or {}
    pr_id = pr.get("id")
    title = pr.get("title") or ""
    description = pr.get("description") or ""
    state = pr.get("state") or "unknown"

    source = pr.get("source") or {}
    source_branch = source.get("branch", {}).get("name") or ""

    destination = pr.get("destination") or {}
    destination_branch = destination.get("branch", {}).get("name") or ""

    author = pr.get("author") or {}
    author_name = author.get("display_name") or author.get("username") or "unknown"

    links = pr.get("links") or {}
    pr_url = links.get("html", {}).get("href") or ""

    # Handle comment events
    comment = payload.get("comment") or {}
    comment_content = comment.get("content", {}).get("raw") or ""

    if action == "comment_created" and comment_content:
        comment_user = comment.get("user") or {}
        comment_user_name = comment_user.get("display_name") or "unknown"
        text = f"Comment by {comment_user_name}:\n{comment_content[:300]}"
    else:
        text = description[:500] if description else f"PR {action} by {author_name}"

    node = MemoryNode(
        org_id=org_id,
        node_type="bitbucket_pull_request",
        title=f"PR #{pr_id}: {title}",
        text=text,
        meta_json={
            "repo": repo_full_name,
            "repo_url": repo_url,
            "pr_id": pr_id,
            "action": action,
            "state": state,
            "source_branch": source_branch,
            "destination_branch": destination_branch,
            "author": author_name,
            "url": pr_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "bitbucket_webhook.pull_request",
        extra={
            "repo": repo_full_name,
            "pr_id": pr_id,
            "action": action,
            "state": state,
        },
    )


async def _handle_issue(
    payload: dict,
    action: str,
    repo_full_name: str,
    repo_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle issue events."""
    issue = payload.get("issue") or {}
    issue_id = issue.get("id")
    title = issue.get("title") or ""
    content = issue.get("content") or {}
    description = content.get("raw") or ""
    state = issue.get("state") or "unknown"
    priority = issue.get("priority") or "normal"
    kind = issue.get("kind") or "bug"

    reporter = issue.get("reporter") or {}
    reporter_name = (
        reporter.get("display_name") or reporter.get("username") or "unknown"
    )

    links = issue.get("links") or {}
    issue_url = links.get("html", {}).get("href") or ""

    actor = payload.get("actor") or {}
    actor_name = actor.get("display_name") or actor.get("username") or reporter_name

    node = MemoryNode(
        org_id=org_id,
        node_type="bitbucket_issue",
        title=f"Issue #{issue_id}: {title}",
        text=description[:500] if description else f"Issue {action} by {actor_name}",
        meta_json={
            "repo": repo_full_name,
            "repo_url": repo_url,
            "issue_id": issue_id,
            "action": action,
            "state": state,
            "priority": priority,
            "kind": kind,
            "reporter": reporter_name,
            "actor": actor_name,
            "url": issue_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "bitbucket_webhook.issue",
        extra={
            "repo": repo_full_name,
            "issue_id": issue_id,
            "action": action,
            "state": state,
        },
    )


async def _handle_commit_status(
    payload: dict,
    repo_full_name: str,
    repo_url: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle commit status (build/CI) events."""
    commit_status = payload.get("commit_status") or {}
    state = commit_status.get("state") or "unknown"
    name = commit_status.get("name") or ""
    description = commit_status.get("description") or ""
    url = commit_status.get("url") or ""

    commit = commit_status.get("commit") or {}
    commit_hash = commit.get("hash", "")[:8]

    # Map Bitbucket states
    state_map = {
        "SUCCESSFUL": "success",
        "FAILED": "failed",
        "INPROGRESS": "running",
        "STOPPED": "stopped",
    }
    normalized_state = state_map.get(state, state.lower())

    node = MemoryNode(
        org_id=org_id,
        node_type="bitbucket_commit_status",
        title=f"Build {name}: {normalized_state}",
        text=description[:500] if description else f"Build status for {commit_hash}",
        meta_json={
            "repo": repo_full_name,
            "repo_url": repo_url,
            "name": name,
            "state": normalized_state,
            "commit_hash": commit_hash,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "bitbucket_webhook.commit_status",
        extra={
            "repo": repo_full_name,
            "name": name,
            "state": normalized_state,
            "commit": commit_hash,
        },
    )
