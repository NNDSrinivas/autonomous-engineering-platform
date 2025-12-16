"""
CI webhook ingestion (build/test status).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.settings import settings
from backend.core.webhooks import verify_shared_secret
from backend.core.auth_org import require_org
from backend.models.memory_graph import MemoryNode
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/ci", tags=["ci_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    org_ctx: dict = Depends(require_org),
):
    verify_shared_secret(x_webhook_secret, settings.CI_WEBHOOK_SECRET, connector="ci")

    status = payload.get("status") or payload.get("state")
    job = payload.get("job") or payload.get("name")
    repo = payload.get("repo")
    sha = payload.get("sha")
    url = payload.get("url")
    summary = payload.get("summary") or payload.get("description") or ""

    if not status:
        raise HTTPException(status_code=400, detail="Missing status/state")

    node = MemoryNode(
        org_id=org_ctx["org_id"],
        node_type="ci_status",
        title=f"{repo}:{job}",
        text=summary or status,
        meta_json={
            "status": status,
            "job": job,
            "repo": repo,
            "sha": sha,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    # Invalidate packets for referenced keys/branches
    import re

    for match in re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", f"{summary} {job}"):
        invalidate_context_packet_cache(match, org_ctx["org_id"])

    return {"status": "ok"}
