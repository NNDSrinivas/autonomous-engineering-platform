"""
Zoom webhook ingestion.
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.db import get_db
from backend.services import connectors as connectors_service
from backend.services.zoom_ingestor import ingest_zoom_meetings

router = APIRouter(prefix="/api/webhooks/zoom", tags=["zoom_webhook"])


def _verify_zoom_signature(
    *,
    timestamp: Optional[str],
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    if not secret:
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing Zoom signature headers")
    base = f"v0:{timestamp}:{payload.decode('utf-8')}"
    expected = hmac.new(secret.encode(), base.encode(), sha256).hexdigest()
    provided = signature.replace("v0=", "")
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid Zoom webhook signature")


@router.post("")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    x_zm_request_timestamp: str | None = Header(None, alias="x-zm-request-timestamp"),
    x_zm_signature: str | None = Header(None, alias="x-zm-signature"),
):
    body = await request.body()
    _verify_zoom_signature(
        timestamp=x_zm_request_timestamp,
        signature=x_zm_signature,
        payload=body,
        secret=settings.zoom_webhook_secret,
    )

    payload: Dict[str, Any] = await request.json()
    event = payload.get("event")

    if event == "endpoint.url_validation":
        plain_token = payload.get("payload", {}).get("plainToken")
        if not plain_token:
            raise HTTPException(status_code=400, detail="Missing plainToken")
        encrypted = hmac.new(
            settings.zoom_webhook_secret.encode(), plain_token.encode(), sha256
        ).hexdigest()
        return {"plainToken": plain_token, "encryptedToken": encrypted}

    account_id = payload.get("payload", {}).get("account_id") or payload.get("account_id")
    connector = None
    if account_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="zoom", key="account_id", value=account_id
        )
    if not connector:
        raise HTTPException(status_code=404, detail="Zoom connector not found")

    user_id = connector.get("user_id")
    zoom_object = payload.get("payload", {}).get("object", {}) or {}
    host_email = zoom_object.get("host_email") or zoom_object.get("host_id")
    start_time = zoom_object.get("start_time")

    if not host_email or not start_time:
        return {"status": "ignored"}

    try:
        meeting_date = datetime.fromisoformat(start_time.replace("Z", "+00:00")).date()
    except Exception:
        return {"status": "ignored"}

    await ingest_zoom_meetings(
        db=db,
        user_id=str(user_id),
        zoom_user=host_email,
        from_date=meeting_date,
        to_date=meeting_date,
        max_meetings=5,
    )

    return {"status": "ok"}
