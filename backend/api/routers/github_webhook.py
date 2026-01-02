"""
GitHub webhook ingestion with HMAC verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.core.webhooks import verify_hmac_signature
from backend.services import github as ghsvc
from backend.models.integrations import GhConnection, GhRepo
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/github", tags=["github_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    db: Session = Depends(get_db),
    x_org_id: str | None = Header(None, alias="X-Org-Id"),
):
    """
    Ingest GitHub webhooks (PRs, issues, comments, status).
    """
    body = await request.body()
    verify_hmac_signature(
        signature=x_hub_signature_256,
        payload=body,
        secret=settings.github_webhook_secret,
        connector="github",
    )

    event = request.headers.get("X-GitHub-Event")
    delivery = request.headers.get("X-GitHub-Delivery")
    if not event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    payload = await request.json()
    repo = payload.get("repository") or {}
    repo_full_name = repo.get("full_name")

    if not repo_full_name:
        raise HTTPException(status_code=400, detail="Missing repository info")

    repo_row = (
        db.query(GhRepo)
        .filter(GhRepo.repo_full_name == repo_full_name)
        .order_by(GhRepo.id.desc())
        .first()
    )
    if not repo_row:
        logger.warning(
            "github_webhook.no_repo", extra={"repo": repo_full_name, "event": event}
        )
        raise HTTPException(
            status_code=202, detail="Repo not indexed for this connection"
        )
    gh_conn = db.get(GhConnection, repo_row.connection_id) if repo_row else None
    org_id = gh_conn.org_id if gh_conn else x_org_id
    if not org_id:
        logger.warning(
            "github_webhook.no_connection",
            extra={"repo": repo_full_name, "event": event},
        )
        raise HTTPException(status_code=202, detail="No GitHub connection found")

    try:
        # Handle core event types
        if event in ("pull_request", "pull_request_review", "issue_comment", "issues"):
            pr = payload.get("pull_request") or payload.get("issue") or {}
            if pr:
                is_pr = event in ("pull_request", "pull_request_review") or bool(
                    pr.get("pull_request")
                )
                ghsvc.upsert_issuepr(
                    db,
                    repo_id=repo_row.id,
                    number=pr.get("number"),
                    type_="pr" if is_pr else "issue",
                    title=pr.get("title", ""),
                    body=pr.get("body", ""),
                    state=pr.get("state", "open"),
                    author=(pr.get("user") or {}).get("login"),
                    url=pr.get("html_url", ""),
                    updated=None,
                )
            if event == "pull_request_review":
                review = payload.get("review") or {}
                from backend.models.memory_graph import MemoryNode

                node = MemoryNode(
                    org_id=org_id,
                    node_type="github_pr_review",
                    title=f"{repo_full_name} PR#{pr.get('number')} review",
                    text=review.get("body", "") or review.get("state", ""),
                    meta_json={
                        "repo": repo_full_name,
                        "pr_number": pr.get("number"),
                        "state": review.get("state"),
                        "user": (review.get("user") or {}).get("login"),
                        "html_url": review.get("html_url"),
                    },
                    created_at=datetime.now(timezone.utc),
                )
                db.add(node)
                db.commit()
            invalidate_context_packet_cache(pr.get("title") or pr.get("html_url"), org_id)
        elif event == "status":
            # Store status as memory nodes for packet hydration
            commit = payload.get("commit") or {}
            state = payload.get("state")
            context = payload.get("context")
            description = payload.get("description")
            sha = commit.get("sha")
            from backend.models.memory_graph import MemoryNode

            node = MemoryNode(
                org_id=org_id,
                node_type="github_status",
                title=f"{repo_full_name}:{context}",
                text=description or state or "",
                meta_json={
                    "repo": repo_full_name,
                    "sha": sha,
                    "context": context,
                    "state": state,
                    "target_url": payload.get("target_url"),
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(node)
            db.commit()
            invalidate_context_packet_cache(sha, org_id)
        else:
            logger.info("github_webhook.unhandled_event", extra={"event": event})
    except Exception as exc:
        logger.error(
            "github_webhook.error", extra={"delivery": delivery, "error": str(exc)}
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}
