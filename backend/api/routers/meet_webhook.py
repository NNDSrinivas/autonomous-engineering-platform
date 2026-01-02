"""
Google Meet (Calendar) webhook ingestion.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.db import get_db
from backend.services import connectors as connectors_service
from backend.services.meet_ingestor import (
    list_meet_events,
    store_meet_events,
    store_meet_transcripts,
)

router = APIRouter(prefix="/api/webhooks/meet", tags=["meet_webhook"])


@router.post("")
async def ingest(
    db: Session = Depends(get_db),
    x_goog_channel_id: str | None = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_id: str | None = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_token: str | None = Header(None, alias="X-Goog-Channel-Token"),
    x_goog_resource_state: str | None = Header(None, alias="X-Goog-Resource-State"),
):
    if settings.meet_webhook_secret and x_goog_channel_token != settings.meet_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid Meet webhook token")

    connector = None
    if x_goog_channel_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="meet", key="channel_id", value=x_goog_channel_id
        )
    if not connector and x_goog_resource_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="meet", key="resource_id", value=x_goog_resource_id
        )
    if not connector:
        raise HTTPException(status_code=404, detail="Meet connector not found")

    cfg = connector.get("config") or {}
    secrets = connector.get("secrets") or {}
    user_id = connector.get("user_id")
    org_id = cfg.get("org_id")
    calendar_id = cfg.get("calendar_id") or "primary"

    last_sync_raw = cfg.get("last_sync")
    last_sync = None
    if last_sync_raw:
        try:
            last_sync = datetime.fromisoformat(str(last_sync_raw).replace("Z", "+00:00"))
        except Exception:
            last_sync = None

    events = await list_meet_events(
        db=db,
        user_id=str(user_id),
        org_id=org_id,
        calendar_id=calendar_id,
        days_back=30,
        updated_min=last_sync,
    )
    event_ids = await store_meet_events(db=db, user_id=str(user_id), events=events)
    scopes = cfg.get("scopes") or []
    if any("drive" in str(scope) for scope in scopes):
        try:
            await store_meet_transcripts(
                db=db,
                user_id=str(user_id),
                org_id=org_id,
                events=events,
            )
        except Exception:
            # Best effort; calendar updates should still succeed
            pass

    connectors_service.save_meet_connection(
        user_id=str(user_id),
        org_id=org_id,
        calendar_id=calendar_id,
        scopes=cfg.get("scopes"),
        access_token=secrets.get("access_token") or secrets.get("token"),
        refresh_token=secrets.get("refresh_token"),
        expires_at=cfg.get("expires_at"),
        channel_id=cfg.get("channel_id"),
        resource_id=cfg.get("resource_id"),
        channel_token=cfg.get("channel_token"),
        last_sync=datetime.now(timezone.utc).isoformat(),
        db=db,
    )

    return {
        "status": "ok",
        "resource_state": x_goog_resource_state,
        "processed": len(event_ids),
    }
