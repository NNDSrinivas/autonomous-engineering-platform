"""
Docs/ADR/Confluence/Notion ingestion webhook.
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

router = APIRouter(prefix="/api/webhooks/docs", tags=["docs_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    org_ctx: dict = Depends(require_org),
):
    verify_shared_secret(
        x_webhook_secret, settings.DOCS_WEBHOOK_SECRET, connector="docs"
    )

    title = payload.get("title") or ""
    body = payload.get("body") or ""
    url = payload.get("url")
    source = payload.get("source") or "doc"
    anchor = payload.get("anchor")

    if not title and not body:
        raise HTTPException(status_code=400, detail="Missing title/body")

    node = MemoryNode(
        org_id=org_ctx["org_id"],
        node_type=source,
        title=title,
        text=body,
        meta_json={"url": url, "anchor": anchor, "source": source},
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    # Invalidate packets referencing keys present in title/body (simple heuristic for JIRA keys)
    import re

    for match in re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", f"{title} {body}"):
        invalidate_context_packet_cache(match, org_ctx["org_id"])

    return {"status": "ok"}
