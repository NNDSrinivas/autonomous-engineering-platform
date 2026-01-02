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
from backend.core.config import settings
from backend.core.webhooks import verify_shared_secret
from backend.models.memory_graph import MemoryNode
from backend.agent.context_packet import invalidate_context_packet_cache
from backend.services import connectors as connectors_service
from backend.services.org_ingestor import ingest_confluence_page

router = APIRouter(prefix="/api/webhooks/docs", tags=["docs_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    x_org_id: str | None = Header(None, alias="X-Org-Id"),
):
    verify_shared_secret(
        x_webhook_secret, settings.docs_webhook_secret, connector="docs"
    )

    org_id = x_org_id
    user_id = None

    page = payload.get("page") or payload.get("content") or {}
    page_id = page.get("id") or payload.get("page_id") or payload.get("content_id")
    cloud_id = payload.get("cloudId") or payload.get("cloud_id")
    base_url = payload.get("baseUrl") or payload.get("base_url") or page.get("_links", {}).get("base")
    if base_url and not str(base_url).rstrip("/").endswith("/wiki"):
        base_url = f"{str(base_url).rstrip('/')}/wiki"

    connector = None
    if not org_id and cloud_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="confluence", key="cloud_id", value=cloud_id
        )
        if connector:
            org_id = (connector.get("config") or {}).get("org_id")
            user_id = connector.get("user_id")

    if not org_id and base_url:
        connector = connectors_service.find_connector_by_config(
            db, provider="confluence", key="base_url", value=str(base_url).rstrip("/")
        )
        if connector:
            org_id = (connector.get("config") or {}).get("org_id")
            user_id = connector.get("user_id")

    if page_id and user_id:
        await ingest_confluence_page(db=db, user_id=str(user_id), page_id=str(page_id))
        return {"status": "ok", "source": "confluence"}

    title = payload.get("title") or ""
    body = payload.get("body") or ""
    url = payload.get("url")
    source = payload.get("source") or "doc"
    anchor = payload.get("anchor")

    if not title and not body:
        raise HTTPException(status_code=400, detail="Missing title/body")
    if not org_id:
        raise HTTPException(status_code=404, detail="Org mapping not found for docs")

    node = MemoryNode(
        org_id=org_id,
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
        invalidate_context_packet_cache(match, org_id)

    return {"status": "ok"}
