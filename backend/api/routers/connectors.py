# backend/api/routers/connectors.py

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.auth.deps import get_current_user
from backend.schemas.connectors import (
    ConnectorStatusResponse,
    JiraConnectorRequest,
    SlackConnectorRequest,
    ConnectorConnectResponse,
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
) -> ConnectorStatusResponse:
    """
    Returns status for all known connectors (Jira, Slack, GitHub, etc.)
    for the current user.

    Used by the VS Code Connectors panel to show which tiles are connected.
    """
    items = connectors_service.get_connector_status_for_user(user_id=user_id)
    # Later, if we detect DB / dependency issues, we can set offline=True.
    return ConnectorStatusResponse(items=items, offline=False)


@router.get(
    "/marketplace/status",
    response_model=ConnectorStatusResponse,
    summary="Get connector status for marketplace (alternative endpoint)",
)
def marketplace_status(
    user_id: str = Depends(_current_user_id),
) -> ConnectorStatusResponse:
    """
    Alternative endpoint for marketplace compatibility.
    Returns same data as /status but at marketplace-friendly path.
    """
    items = connectors_service.get_connector_status_for_user(user_id=user_id)
    return ConnectorStatusResponse(items=items, offline=False)


@router.post(
    "/jira/connect",
    response_model=ConnectorConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Connect Jira for the current user",
)
def connect_jira(
    payload: JiraConnectorRequest,
    user_id: str = Depends(_current_user_id),
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
) -> ConnectorConnectResponse:
    """
    Save Slack connection details for the current user (dev-mode).

    For now we just persist a bot token; later we can upgrade to full OAuth.
    """
    try:
        connectors_service.save_slack_connection(
            user_id=user_id,
            bot_token=payload.bot_token,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save Slack connection: {exc}",
        ) from exc

    return ConnectorConnectResponse(ok=True, connector_id="slack")