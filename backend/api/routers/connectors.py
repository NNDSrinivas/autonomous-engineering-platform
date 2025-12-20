# backend/api/routers/connectors.py

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.auth.deps import get_current_user
from backend.core.db import get_db
from backend.schemas.connectors import (
    ConnectorStatusResponse,
    JiraConnectorRequest,
    SlackConnectorRequest,
    ConnectorConnectResponse,
    GenericConnectorRequest,
    GenericConnectorResponse,
    ConnectorListResponse,
)
from backend.services import connectors as connectors_service

router = APIRouter(
    prefix="/api/connectors",
    tags=["connectors"],
)


# --- Auth dependency shim -------------------------------------------------


def _current_user_id(current_user: Any = Depends(get_current_user)) -> str:
    """
    Normalise whatever get_current_user returns into a string user_id.

    In your current codebase, get_current_user likely returns a User model
    with an .id attribute. If it's different, adjust this function.
    """
    if hasattr(current_user, "id"):
        return str(current_user.id)
    if hasattr(current_user, "sub"):
        return str(current_user.sub)
    return str(current_user)


# --- Routes ---------------------------------------------------------------


@router.get(
    "/status",
    response_model=ConnectorStatusResponse,
    summary="Get connector status for the current user",
)
def connectors_status(
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorStatusResponse:
    """
    Returns status for all known connectors (Jira, Slack, GitHub, etc.)
    for the current user.

    Used by the VS Code Connectors panel to show which tiles are connected.
    """
    items = connectors_service.get_connector_status_for_user(user_id=user_id, db=db)
    offline = not connectors_service.connectors_available(db)
    return ConnectorStatusResponse(items=items, offline=offline)


@router.get(
    "/marketplace/status",
    response_model=ConnectorStatusResponse,
    summary="Get connector status for marketplace (alternative endpoint)",
)
def marketplace_status(
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorStatusResponse:
    """
    Alternative endpoint for marketplace compatibility.
    Returns same data as /status but at marketplace-friendly path.
    """
    items = connectors_service.get_connector_status_for_user(user_id=user_id, db=db)
    offline = not connectors_service.connectors_available(db)
    return ConnectorStatusResponse(items=items, offline=offline)


@router.post(
    "/jira/connect",
    response_model=ConnectorConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Connect Jira for the current user",
)
def connect_jira(
    payload: JiraConnectorRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorConnectResponse:
    """
    Save Jira connection details for the current user.

    Phase 1:
    - Stores credentials in-process (in-memory) for dev and local testing.
    - Does NOT yet validate the token against Jira.
    - No database writes.
    """
    try:
        connectors_service.save_jira_connection(
            user_id=user_id,
            base_url=str(payload.base_url),
            email=payload.email,
            api_token=payload.api_token,
            db=db,
        )
    except Exception as exc:  # pragma: no cover – defensive
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save Jira connection: {exc}",
        ) from exc

    return ConnectorConnectResponse(ok=True, connector_id="jira")


@router.post(
    "/slack/connect",
    response_model=ConnectorConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Connect Slack for the current user",
)
def connect_slack(
    payload: SlackConnectorRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorConnectResponse:
    """
    Save Slack connection details for the current user (dev-mode).

    For now we just persist a bot token; later we can upgrade to full OAuth.
    """
    try:
        connectors_service.save_slack_connection(
            user_id=user_id,
            bot_token=payload.bot_token,
            db=db,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save Slack connection: {exc}",
        ) from exc

    return ConnectorConnectResponse(ok=True, connector_id="slack")


@router.post(
    "/save",
    response_model=GenericConnectorResponse,
    status_code=status.HTTP_200_OK,
    summary="Save a connector (generic providers)",
)
def save_connector(
    payload: GenericConnectorRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> GenericConnectorResponse:
    """
    Save connector details for provider (github, gitlab, jenkins, etc.).
    """
    try:
        cfg = {}
        if payload.base_url:
            cfg["base_url"] = payload.base_url
        if payload.extra:
            cfg.update(payload.extra)
        secrets = {}
        if payload.token:
            secrets["token"] = payload.token
        connector_id = connectors_service.upsert_connector(
            db=db,
            user_id=user_id,
            provider=payload.provider,
            name=payload.name or "default",
            config=cfg,
            secrets=secrets,
            workspace_root=payload.workspace_root,
        )
        return GenericConnectorResponse(
            ok=True,
            connector_id=payload.provider,
            id=connector_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save connector: {exc}",
        ) from exc


@router.get(
    "",
    response_model=ConnectorListResponse,
    summary="List connectors for current user",
)
def list_connectors(
    workspace_root: str | None = None,
    provider: str | None = None,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorListResponse:
    items = connectors_service.list_connectors(
        db=db, user_id=user_id, workspace_root=workspace_root, provider=provider
    )
    return ConnectorListResponse(items=items)


@router.delete(
    "/{connector_id}",
    summary="Delete a connector by id",
)
def delete_connector(
    connector_id: int,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    deleted = connectors_service.delete_connector(db=db, user_id=user_id, connector_id=connector_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"ok": True}
