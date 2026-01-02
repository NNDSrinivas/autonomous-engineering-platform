# backend/api/routers/connectors.py

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import base64
import json
from uuid import uuid4
import logging

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.core.auth.deps import get_current_user, get_current_user_optional
from backend.core.auth.models import Role
from backend.core.db import get_db
from backend.core.config import settings
from backend.core.oauth_state import create_state, parse_state, OAuthStateError
from backend.schemas.connectors import (
    ConnectorStatusResponse,
    JiraConnectorRequest,
    SlackConnectorRequest,
    ConnectorConnectResponse,
    GenericConnectorRequest,
    GenericConnectorResponse,
    ConnectorListResponse,
    SlackSyncRequest,
    SlackSyncResponse,
    GitHubRepoListResponse,
    GitHubIndexRequest,
    GitHubIndexResponse,
    ConfluenceSyncRequest,
    ConfluenceSyncResponse,
    ConfluenceSubscribeRequest,
    ConfluenceSubscribeResponse,
    TeamsTeamListResponse,
    TeamsChannelListResponse,
    TeamsSubscribeRequest,
    TeamsSubscribeResponse,
    ZoomSyncRequest,
    ZoomSyncResponse,
    MeetSubscribeRequest,
    MeetSubscribeResponse,
    MeetSyncRequest,
    MeetSyncResponse,
    OAuthAppConfigRequest,
    OAuthAppConfigResponse,
    OrgUiConfigRequest,
    OrgUiConfigResponse,
)
from backend.services import connectors as connectors_service
from backend.integrations.jira_client import JiraClient
from backend.integrations.slack_client import SlackClient
from backend.integrations.teams_client import TeamsClient
from backend.services.slack_ingestor import ingest_slack
from backend.services.org_ingestor import ingest_confluence_space
from backend.services.github import GitHubService
from backend.services.zoom_ingestor import ingest_zoom_meetings
from backend.services.org_settings import (
    get_org_ui_config,
    save_org_ui_config,
    select_ui_origin,
)
from backend.services.meet_ingestor import (
    list_meet_events,
    store_meet_events,
    create_meet_watch,
    store_meet_transcripts,
)
from backend.models.integrations import GhConnection
from backend.workers.integrations import github_index

router = APIRouter(
    prefix="/api/connectors",
    tags=["connectors"],
)
logger = logging.getLogger(__name__)


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


def _public_base_url() -> str:
    base = settings.public_base_url
    if base:
        return base.rstrip("/")
    # Safe dev fallback
    return f"http://{settings.api_host}:{settings.api_port}"


def _oauth_redirect(path: str) -> str:
    return f"{_public_base_url()}{path}"


def _build_ui_redirect(
    *,
    db: Session,
    org_id: Optional[str],
    provider: str,
    status_value: str,
    ui_origin: Optional[str] = None,
    message: Optional[str] = None,
) -> Optional[str]:
    if not org_id:
        return None
    config = get_org_ui_config(db=db, org_key=str(org_id))
    origin = select_ui_origin(config, ui_origin)
    if not origin:
        return None
    path = config.get("redirect_path") or "/settings/connectors"
    params = {"provider": provider, "status": status_value}
    if message:
        params["message"] = message
    return f"{origin}{path}?{urlencode(params)}"


def _github_auth_header(token: str, token_type: str | None) -> str:
    if token_type and token_type.lower() == "bearer":
        return f"Bearer {token}"
    return f"token {token}"


def _expires_at_iso(expires_in: Any) -> str | None:
    if not expires_in:
        return None
    try:
        return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
    except Exception:
        return None


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    if not token or "." not in token:
        return {}
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(f"{payload_b64}{padding}")
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _parse_scopes(scope_raw: str | None, *, delimiter: str = " ") -> List[str] | None:
    if not scope_raw:
        return None
    parts = [s.strip() for s in scope_raw.split(delimiter) if s.strip()]
    return parts or None


def _coerce_scopes(scope_value: Any) -> Optional[str]:
    if not scope_value:
        return None
    if isinstance(scope_value, list):
        return " ".join(str(item).strip() for item in scope_value if str(item).strip())
    return str(scope_value)


def _resolve_oauth_app_config(
    *,
    db: Session,
    org_id: Optional[str],
    provider: str,
    fallback_client_id: Optional[str],
    fallback_client_secret: Optional[str],
    fallback_scopes: Optional[str],
) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    secrets: Dict[str, Any] = {}
    if org_id:
        stored = connectors_service.get_oauth_app_config(
            db=db,
            org_id=str(org_id),
            provider=provider,
        )
        if stored:
            config = stored.get("config") or {}
            secrets = stored.get("secrets") or {}

    client_id = config.get("client_id") or fallback_client_id
    client_secret = secrets.get("client_secret") or fallback_client_secret
    scopes = _coerce_scopes(config.get("scopes")) or fallback_scopes
    extra = config.get("extra") or {}

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": scopes,
        "tenant_id": config.get("tenant_id") or extra.get("tenant_id"),
        "account_id": config.get("account_id") or extra.get("account_id"),
        "extra": extra,
    }


async def _refresh_teams_token_if_needed(
    *,
    connector: Dict[str, Any],
    db: Session,
    user_id: str,
    org_id: Optional[str],
) -> str:
    cfg = connector.get("config") or {}
    secrets = connector.get("secrets") or {}
    token = secrets.get("access_token") or secrets.get("token")
    refresh_token = secrets.get("refresh_token")
    expires_at_raw = cfg.get("expires_at")
    if not expires_at_raw:
        return token
    try:
        expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
    except Exception:
        return token
    if datetime.now(timezone.utc) < expires_at:
        return token
    resolved_org_id = org_id or cfg.get("org_id")
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=resolved_org_id,
        provider="teams",
        fallback_client_id=settings.teams_client_id,
        fallback_client_secret=settings.teams_client_secret,
        fallback_scopes=settings.teams_oauth_scopes,
    )
    if not refresh_token or not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        return token

    tenant = cfg.get("tenant_id") or oauth_cfg["tenant_id"] or settings.teams_tenant_id or "common"
    scopes = oauth_cfg["scopes"] or (
        "offline_access openid profile email "
        "ChannelMessage.Read.All Group.Read.All Team.ReadBasic.All"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": scopes,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code >= 400:
        return token

    data = resp.json()
    new_token = data.get("access_token") or token
    new_refresh = data.get("refresh_token") or refresh_token
    new_expires_at = _expires_at_iso(data.get("expires_in")) or cfg.get("expires_at")
    scopes_list = _parse_scopes(data.get("scope"), delimiter=" ")

    connectors_service.save_teams_connection(
        user_id=user_id,
        org_id=org_id or cfg.get("org_id"),
        tenant_id=cfg.get("tenant_id"),
        scopes=scopes_list or cfg.get("scopes"),
        access_token=new_token,
        refresh_token=new_refresh,
        expires_at=new_expires_at,
        install_scope=cfg.get("install_scope"),
        subscription_id=cfg.get("subscription_id"),
        db=db,
    )
    return new_token


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


@router.get(
    "/oauth/config/{provider}",
    response_model=OAuthAppConfigResponse,
    summary="Get per-org OAuth app configuration",
)
def get_oauth_app_config(
    provider: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthAppConfigResponse:
    org_id = getattr(current_user, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing org_id for OAuth config lookup")

    stored = connectors_service.get_oauth_app_config(
        db=db,
        org_id=str(org_id),
        provider=provider,
    )
    if not stored:
        return OAuthAppConfigResponse(ok=True, provider=provider, configured=False)

    config = stored.get("config") or {}
    extra = config.get("extra") or {}
    return OAuthAppConfigResponse(
        ok=True,
        provider=provider,
        configured=True,
        client_id=config.get("client_id"),
        scopes=_coerce_scopes(config.get("scopes")),
        tenant_id=config.get("tenant_id") or extra.get("tenant_id"),
        account_id=config.get("account_id") or extra.get("account_id"),
        extra=extra or None,
    )


@router.post(
    "/oauth/config",
    response_model=OAuthAppConfigResponse,
    summary="Set per-org OAuth app configuration",
)
def set_oauth_app_config(
    payload: OAuthAppConfigRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthAppConfigResponse:
    if getattr(current_user, "role", None) != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required to configure OAuth apps")

    org_id = getattr(current_user, "org_id", None)
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing org_id for OAuth config")

    existing = connectors_service.get_oauth_app_config(
        db=db,
        org_id=str(org_id),
        provider=payload.provider,
    )
    existing_config = (existing or {}).get("config") or {}
    existing_secrets = (existing or {}).get("secrets") or {}

    client_secret = payload.client_secret or existing_secrets.get("client_secret")
    if not client_secret:
        raise HTTPException(status_code=400, detail="client_secret is required for first-time setup")

    scopes = payload.scopes if payload.scopes is not None else existing_config.get("scopes")
    extra = payload.extra if payload.extra is not None else existing_config.get("extra")
    tenant_id = payload.tenant_id or existing_config.get("tenant_id")
    account_id = payload.account_id or existing_config.get("account_id")

    connectors_service.save_oauth_app_config(
        db=db,
        org_id=str(org_id),
        provider=payload.provider,
        client_id=payload.client_id,
        client_secret=client_secret,
        scopes=scopes,
        tenant_id=tenant_id,
        account_id=account_id,
        extra=extra,
        updated_by=getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
    )

    return OAuthAppConfigResponse(
        ok=True,
        provider=payload.provider,
        configured=True,
        client_id=payload.client_id,
        scopes=_coerce_scopes(scopes),
        tenant_id=tenant_id,
        account_id=account_id,
        extra=extra,
    )


@router.get(
    "/ui/config",
    response_model=OrgUiConfigResponse,
    summary="Get org UI redirect configuration",
)
def get_ui_config(
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgUiConfigResponse:
    org_key = getattr(current_user, "org_id", None)
    if not org_key:
        raise HTTPException(status_code=400, detail="Missing org_id for UI config lookup")

    config = get_org_ui_config(db=db, org_key=str(org_key))
    return OrgUiConfigResponse(
        ok=True,
        base_url=config.get("base_url"),
        allowed_domains=config.get("allowed_domains") or [],
        redirect_path=config.get("redirect_path"),
    )


@router.post(
    "/ui/config",
    response_model=OrgUiConfigResponse,
    summary="Set org UI redirect configuration",
)
def set_ui_config(
    payload: OrgUiConfigRequest,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgUiConfigResponse:
    if getattr(current_user, "role", None) != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required to configure UI settings")

    org_key = getattr(current_user, "org_id", None)
    if not org_key:
        raise HTTPException(status_code=400, detail="Missing org_id for UI config")

    try:
        config = save_org_ui_config(
            db=db,
            org_key=str(org_key),
            base_url=payload.base_url,
            allowed_domains=payload.allowed_domains,
            redirect_path=payload.redirect_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OrgUiConfigResponse(
        ok=True,
        base_url=config.get("base_url"),
        allowed_domains=config.get("allowed_domains") or [],
        redirect_path=config.get("redirect_path"),
    )


@router.post(
    "/jira/connect",
    response_model=ConnectorConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Connect Jira for the current user",
)
async def connect_jira(
    payload: JiraConnectorRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectorConnectResponse:
    """
    Save Jira connection details for the current user.

    Supports:
    - API token (email + api_token)
    - OAuth token (access_token + token_type)
    """
    base_url = str(payload.base_url)
    token_type = payload.token_type or "Bearer"

    if payload.access_token:
        try:
            async with JiraClient(
                base_url=base_url,
                access_token=payload.access_token,
                token_type=token_type,
            ) as jira:
                await jira.get_myself()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Jira credential validation failed: {exc}",
            ) from exc
    else:
        if not payload.email or not payload.api_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either access_token or email + api_token",
            )
        try:
            async with JiraClient(
                base_url=base_url,
                email=payload.email,
                api_token=payload.api_token,
            ) as jira:
                await jira.get_myself()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Jira credential validation failed: {exc}",
            ) from exc

    try:
        connectors_service.save_jira_connection(
            user_id=user_id,
            base_url=base_url,
            email=payload.email,
            api_token=payload.api_token,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            token_type=token_type,
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
        SlackClient(bot_token=payload.bot_token).auth_test()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Slack credential validation failed: {exc}",
        ) from exc
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


@router.get(
    "/slack/oauth/start",
    summary="Start Slack OAuth install flow",
)
def slack_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="slack",
        fallback_client_id=settings.slack_client_id,
        fallback_client_secret=settings.slack_client_secret,
        fallback_scopes=settings.slack_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack OAuth not configured. Set org app config or SLACK_CLIENT_ID/SLACK_CLIENT_SECRET.",
        )

    scopes = oauth_cfg["scopes"] or (
        "channels:read,groups:read,im:read,mpim:read,"
        "channels:history,groups:history,im:history,mpim:history,"
        "users:read,files:read,chat:write,chat:write.public"
    )
    user_scopes = settings.slack_user_scopes or ""

    state = create_state(
        {
            "provider": "slack",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "client_id": oauth_cfg["client_id"],
        "scope": scopes,
        "redirect_uri": _oauth_redirect("/api/connectors/slack/oauth/callback"),
        "state": state,
    }
    if install == "user" and user_scopes:
        params["user_scope"] = user_scopes

    auth_url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get(
    "/slack/oauth/callback",
    summary="Slack OAuth callback",
)
async def slack_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "slack":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id"),
        provider="slack",
        fallback_client_id=settings.slack_client_id,
        fallback_client_secret=settings.slack_client_secret,
        fallback_scopes=settings.slack_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack OAuth not configured. Set org app config or SLACK_CLIENT_ID/SLACK_CLIENT_SECRET.",
        )

    redirect_uri = _oauth_redirect("/api/connectors/slack/oauth/callback")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=f"Slack OAuth failed: {data.get('error', 'unknown_error')}",
        )

    bot_token = data.get("access_token")
    team = data.get("team") or {}
    authed_user = data.get("authed_user") or {}
    token_type = data.get("token_type")
    scope = data.get("scope")
    bot_refresh_token = data.get("refresh_token")
    user_refresh_token = authed_user.get("refresh_token")
    bot_expires_in = data.get("expires_in")
    user_expires_in = authed_user.get("expires_in")

    def _expires_at(expires_in: Any) -> str | None:
        if not expires_in:
            return None
        try:
            return (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
        except Exception:
            return None

    expires_at = _expires_at(bot_expires_in)
    user_expires_at = _expires_at(user_expires_in)

    try:
        auth_payload = SlackClient(bot_token=bot_token).auth_test()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Slack credential validation failed: {exc}",
        ) from exc

    connectors_service.save_slack_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        bot_token=bot_token,
        team_id=team.get("id") or auth_payload.get("team_id"),
        team_name=team.get("name") or auth_payload.get("team"),
        bot_user_id=(data.get("bot_user_id") or auth_payload.get("bot_id") or auth_payload.get("user_id") or ""),
        token_type=token_type,
        scope=scope,
        install_scope=payload.get("install"),
        user_token=authed_user.get("access_token"),
        refresh_token=bot_refresh_token,
        user_refresh_token=user_refresh_token,
        expires_at=expires_at or user_expires_at,
        db=db,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="slack",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True, "team_id": team.get("id"), "team_name": team.get("name")}


@router.post(
    "/slack/sync",
    response_model=SlackSyncResponse,
    summary="Sync Slack channels into NAVI memory",
)
async def slack_sync(
    payload: SlackSyncRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> SlackSyncResponse:
    if not payload.channels and not payload.include_dms:
        raise HTTPException(
            status_code=400,
            detail="channels list cannot be empty unless include_dms is true",
        )

    channel_ids = await ingest_slack(
        db=db,
        user_id=user_id,
        channels=payload.channels,
        limit=payload.limit,
        include_dms=payload.include_dms,
        include_files=payload.include_files,
    )

    return SlackSyncResponse(
        processed_channel_ids=channel_ids,
        total=len(channel_ids),
    )


@router.get(
    "/confluence/oauth/start",
    summary="Start Confluence OAuth flow",
)
def confluence_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="confluence",
        fallback_client_id=settings.confluence_client_id,
        fallback_client_secret=settings.confluence_client_secret,
        fallback_scopes=settings.confluence_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Confluence OAuth not configured. "
                "Set org app config or CONFLUENCE_CLIENT_ID/CONFLUENCE_CLIENT_SECRET."
            ),
        )

    scopes = oauth_cfg["scopes"] or (
        "read:confluence-content.all read:confluence-space.summary "
        "read:confluence-user offline_access manage:confluence-webhook"
    )

    state = create_state(
        {
            "provider": "confluence",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "audience": "api.atlassian.com",
        "client_id": oauth_cfg["client_id"],
        "scope": scopes,
        "redirect_uri": _oauth_redirect("/api/connectors/confluence/oauth/callback"),
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    auth_url = f"https://auth.atlassian.com/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get(
    "/confluence/oauth/callback",
    summary="Confluence OAuth callback",
)
async def confluence_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "confluence":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id") or getattr(current_user, "org_id", None),
        provider="confluence",
        fallback_client_id=settings.confluence_client_id,
        fallback_client_secret=settings.confluence_client_secret,
        fallback_scopes=settings.confluence_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Confluence OAuth not configured. "
                "Set org app config or CONFLUENCE_CLIENT_ID/CONFLUENCE_CLIENT_SECRET."
            ),
        )

    redirect_uri = _oauth_redirect("/api/connectors/confluence/oauth/callback")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    if token_resp.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=f"Confluence OAuth failed: {token_resp.text}",
        )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Confluence OAuth did not return access_token")

    refresh_token = token_data.get("refresh_token")
    expires_at = _expires_at_iso(token_data.get("expires_in"))
    scopes = _parse_scopes(token_data.get("scope"), delimiter=" ")

    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        res.raise_for_status()
        resources = res.json() or []

    resource = resources[0] if resources else {}
    cloud_id = resource.get("id")
    base_url = resource.get("url")
    if base_url and not base_url.rstrip("/").endswith("/wiki"):
        base_url = f"{base_url.rstrip('/')}/wiki"

    connectors_service.save_confluence_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        base_url=base_url,
        cloud_id=cloud_id,
        scopes=scopes,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        db=db,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="confluence",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True, "cloud_id": cloud_id, "base_url": base_url}


@router.post(
    "/confluence/sync",
    response_model=ConfluenceSyncResponse,
    summary="Sync Confluence pages into NAVI memory",
)
async def confluence_sync(
    payload: ConfluenceSyncRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
) -> ConfluenceSyncResponse:
    page_ids = await ingest_confluence_space(
        db=db,
        user_id=user_id,
        space_key=payload.space_key,
        limit=payload.limit,
    )
    return ConfluenceSyncResponse(processed_page_ids=page_ids, total=len(page_ids))


@router.post(
    "/confluence/subscribe",
    response_model=ConfluenceSubscribeResponse,
    summary="Register Confluence webhooks for page updates",
)
async def confluence_subscribe(
    payload: ConfluenceSubscribeRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
) -> ConfluenceSubscribeResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="confluence",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Confluence connector not configured")

    cfg = connector.get("config") or {}
    secrets = connector.get("secrets") or {}
    token = secrets.get("access_token") or secrets.get("token")
    base_url = cfg.get("base_url")
    cloud_id = cfg.get("cloud_id")
    if cloud_id and not base_url:
        base_url = f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki"
    if not token or not base_url:
        raise HTTPException(status_code=400, detail="Confluence OAuth token or base URL missing")

    webhook_url = _oauth_redirect("/api/webhooks/docs")
    webhook_payload: Dict[str, Any] = {
        "name": "NAVI Confluence Webhook",
        "url": webhook_url,
        "events": ["page_created", "page_updated"],
    }
    if payload.space_key:
        webhook_payload["filters"] = {"space_key": [payload.space_key]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/rest/api/webhook",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=webhook_payload,
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Confluence webhook failed: {resp.text}")

    webhook = resp.json()
    webhook_id = webhook.get("id") or webhook.get("webhookId")

    return ConfluenceSubscribeResponse(ok=True, webhook_id=str(webhook_id) if webhook_id else None)


@router.get(
    "/teams/oauth/start",
    summary="Start Microsoft Teams OAuth flow",
)
def teams_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="teams",
        fallback_client_id=settings.teams_client_id,
        fallback_client_secret=settings.teams_client_secret,
        fallback_scopes=settings.teams_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Teams OAuth not configured. Set org app config or TEAMS_CLIENT_ID/TEAMS_CLIENT_SECRET.",
        )

    tenant = oauth_cfg["tenant_id"] or settings.teams_tenant_id or "common"
    scopes = oauth_cfg["scopes"] or (
        "offline_access openid profile email "
        "ChannelMessage.Read.All Group.Read.All Team.ReadBasic.All"
    )
    prompt = "admin_consent" if install == "org" else "consent"

    state = create_state(
        {
            "provider": "teams",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "tenant": tenant,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "client_id": oauth_cfg["client_id"],
        "response_type": "code",
        "redirect_uri": _oauth_redirect("/api/connectors/teams/oauth/callback"),
        "response_mode": "query",
        "scope": scopes,
        "state": state,
        "prompt": prompt,
    }
    auth_url = (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        f"?{urlencode(params)}"
    )
    return {"auth_url": auth_url}


@router.get(
    "/teams/oauth/callback",
    summary="Teams OAuth callback",
)
async def teams_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "teams":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id") or getattr(current_user, "org_id", None),
        provider="teams",
        fallback_client_id=settings.teams_client_id,
        fallback_client_secret=settings.teams_client_secret,
        fallback_scopes=settings.teams_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Teams OAuth not configured. Set org app config or TEAMS_CLIENT_ID/TEAMS_CLIENT_SECRET.",
        )

    tenant = payload.get("tenant") or oauth_cfg["tenant_id"] or settings.teams_tenant_id or "common"
    redirect_uri = _oauth_redirect("/api/connectors/teams/oauth/callback")
    scopes = oauth_cfg["scopes"] or (
        "offline_access openid profile email "
        "ChannelMessage.Read.All Group.Read.All Team.ReadBasic.All"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": scopes,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Teams OAuth failed: {resp.text}")

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Teams OAuth missing access_token")

    refresh_token = data.get("refresh_token")
    expires_at = _expires_at_iso(data.get("expires_in"))
    scopes_list = _parse_scopes(data.get("scope"), delimiter=" ")

    id_claims = _decode_jwt_payload(data.get("id_token", ""))
    tenant_id = id_claims.get("tid")

    connectors_service.save_teams_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        tenant_id=tenant_id,
        scopes=scopes_list,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        install_scope=payload.get("install"),
        db=db,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="teams",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True, "tenant_id": tenant_id}


@router.get(
    "/teams/teams",
    response_model=TeamsTeamListResponse,
    summary="List Teams teams for the current user",
)
async def teams_list_teams(
    db: Session = Depends(get_db),
    user_id: str = Depends(_current_user_id),
    current_user: Any = Depends(get_current_user_optional),
) -> TeamsTeamListResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="teams",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Teams connector not configured")

    token = await _refresh_teams_token_if_needed(
        connector=connector,
        db=db,
        user_id=str(user_id),
        org_id=getattr(current_user, "org_id", None),
    )
    if not token:
        raise HTTPException(status_code=404, detail="Teams token missing")

    client = TeamsClient(access_token=token, tenant_id=(connector.get("config") or {}).get("tenant_id"))
    teams = client.list_teams()
    items = [
        {"id": t.get("id"), "display_name": t.get("displayName")}
        for t in teams
        if t.get("id")
    ]
    return TeamsTeamListResponse(items=items)


@router.get(
    "/teams/channels",
    response_model=TeamsChannelListResponse,
    summary="List Teams channels for a team",
)
async def teams_list_channels(
    team_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(_current_user_id),
    current_user: Any = Depends(get_current_user_optional),
) -> TeamsChannelListResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="teams",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Teams connector not configured")

    token = await _refresh_teams_token_if_needed(
        connector=connector,
        db=db,
        user_id=str(user_id),
        org_id=getattr(current_user, "org_id", None),
    )
    if not token:
        raise HTTPException(status_code=404, detail="Teams token missing")

    client = TeamsClient(access_token=token, tenant_id=(connector.get("config") or {}).get("tenant_id"))
    channels = client.list_channels(team_id)
    items = [
        {"id": c.get("id"), "display_name": c.get("displayName")}
        for c in channels
        if c.get("id")
    ]
    return TeamsChannelListResponse(items=items)


@router.post(
    "/teams/subscribe",
    response_model=TeamsSubscribeResponse,
    summary="Create a Teams Graph subscription for channel messages",
)
async def teams_subscribe(
    payload: TeamsSubscribeRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(_current_user_id),
    current_user: Any = Depends(get_current_user_optional),
) -> TeamsSubscribeResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="teams",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Teams connector not configured")

    secrets = connector.get("secrets") or {}
    token = await _refresh_teams_token_if_needed(
        connector=connector,
        db=db,
        user_id=str(user_id),
        org_id=getattr(current_user, "org_id", None),
    )
    if not token:
        raise HTTPException(status_code=404, detail="Teams token missing")

    webhook_url = _oauth_redirect("/api/webhooks/teams")
    expiration = datetime.now(timezone.utc) + timedelta(minutes=55)
    payload_resource = f"/teams/{payload.team_id}/channels/{payload.channel_id}/messages"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "changeType": "created,updated",
                "notificationUrl": webhook_url,
                "resource": payload_resource,
                "expirationDateTime": expiration.isoformat(),
                "clientState": settings.teams_webhook_secret or "aep-teams",
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Teams subscription failed: {resp.text}")

    data = resp.json()
    subscription_id = data.get("id")
    if not subscription_id:
        raise HTTPException(status_code=400, detail="Teams subscription response missing id")

    connectors_service.save_teams_connection(
        user_id=str(user_id),
        org_id=(connector.get("config") or {}).get("org_id") or getattr(current_user, "org_id", None),
        tenant_id=(connector.get("config") or {}).get("tenant_id"),
        scopes=(connector.get("config") or {}).get("scopes"),
        access_token=token,
        refresh_token=secrets.get("refresh_token"),
        expires_at=(connector.get("config") or {}).get("expires_at"),
        subscription_id=subscription_id,
        db=db,
    )

    return TeamsSubscribeResponse(ok=True, subscription_id=subscription_id, expires_at=expiration.isoformat())


@router.get(
    "/github/oauth/start",
    summary="Start GitHub OAuth flow",
)
def github_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="github",
        fallback_client_id=settings.github_client_id,
        fallback_client_secret=settings.github_client_secret,
        fallback_scopes=settings.github_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured. Set org app config or GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET.",
        )

    scopes = oauth_cfg["scopes"] or "repo read:org"
    state = create_state(
        {
            "provider": "github",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "client_id": oauth_cfg["client_id"],
        "redirect_uri": _oauth_redirect("/api/connectors/github/oauth/callback"),
        "scope": scopes,
        "state": state,
        "allow_signup": "true",
    }
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get(
    "/github/oauth/callback",
    summary="GitHub OAuth callback",
)
async def github_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "github":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id") or getattr(current_user, "org_id", None),
        provider="github",
        fallback_client_id=settings.github_client_id,
        fallback_client_secret=settings.github_client_secret,
        fallback_scopes=settings.github_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth not configured. Set org app config or GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET.",
        )

    redirect_uri = _oauth_redirect("/api/connectors/github/oauth/callback")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail=f"GitHub OAuth failed: {data.get('error_description') or data.get('error') or 'unknown_error'}",
        )

    token_type = data.get("token_type") or "bearer"
    scope = data.get("scope") or ""
    scopes = [s.strip() for s in scope.split(",") if s.strip()] or None

    expires_in = data.get("expires_in")
    refresh_token = data.get("refresh_token")
    expires_at_dt = None
    if expires_in:
        try:
            expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except Exception:
            expires_at_dt = None

    # Validate token with /user
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": _github_auth_header(access_token, token_type),
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "AutonomousEngineeringPlatform/1.0",
                },
            )
            user_resp.raise_for_status()
            user_payload = user_resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub credential validation failed: {exc}",
        ) from exc

    conn = GitHubService.save_connection(
        db,
        access_token,
        org_id=payload.get("org_id"),
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        token_type=token_type,
        scopes=scopes,
        refresh_token=refresh_token,
        expires_at=expires_at_dt,
    )

    connectors_service.save_github_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        access_token=access_token,
        db=db,
        base_url="https://api.github.com",
        token_type=token_type,
        scopes=scopes,
        refresh_token=refresh_token,
        expires_at=expires_at_dt.isoformat() if expires_at_dt else None,
        connection_id=conn.id,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="github",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True, "login": user_payload.get("login"), "connection_id": conn.id}


@router.get(
    "/github/repos",
    response_model=GitHubRepoListResponse,
    summary="List GitHub repos for the current user",
)
async def github_list_repos(
    db: Session = Depends(get_db),
    user_id: str = Depends(_current_user_id),
    current_user: Any = Depends(get_current_user_optional),
) -> GitHubRepoListResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="github",
    )
    token = None
    token_type = None
    base_url = "https://api.github.com"
    if connector:
        token = (connector.get("secrets") or {}).get("token") or (connector.get("secrets") or {}).get("access_token")
        token_type = (connector.get("config") or {}).get("token_type")
        base_url = (connector.get("config") or {}).get("base_url") or base_url
    if not token:
        raise HTTPException(status_code=404, detail="GitHub connector not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/user/repos",
            headers={
                "Authorization": _github_auth_header(token, token_type),
                "Accept": "application/vnd.github+json",
                "User-Agent": "AutonomousEngineeringPlatform/1.0",
            },
            params={
                "per_page": 100,
                "sort": "updated",
                "affiliation": "owner,collaborator,organization_member",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    items = [
        {
            "full_name": repo.get("full_name"),
            "private": bool(repo.get("private")),
            "html_url": repo.get("html_url"),
            "default_branch": repo.get("default_branch"),
        }
        for repo in data or []
        if repo.get("full_name")
    ]
    return GitHubRepoListResponse(items=items)


async def _ensure_github_webhook(
    *,
    token: str,
    token_type: str | None,
    repo_full_name: str,
    webhook_url: str,
    base_url: str = "https://api.github.com",
) -> bool:
    """Ensure a GitHub webhook exists for the repo."""
    if not settings.github_webhook_secret:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_WEBHOOK_SECRET is required to register GitHub webhooks.",
        )
    api_base = base_url.rstrip("/")
    headers = {
        "Authorization": _github_auth_header(token, token_type),
        "Accept": "application/vnd.github+json",
        "User-Agent": "AutonomousEngineeringPlatform/1.0",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        hooks = await client.get(
            f"{api_base}/repos/{repo_full_name}/hooks",
            headers=headers,
        )
        if hooks.status_code == 200:
            for hook in hooks.json() or []:
                cfg = hook.get("config") or {}
                if cfg.get("url") == webhook_url:
                    return False
        payload = {
            "name": "web",
            "active": True,
            "events": ["issues", "issue_comment", "pull_request", "pull_request_review", "status"],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": settings.github_webhook_secret,
            },
        }
        create_resp = await client.post(
            f"{api_base}/repos/{repo_full_name}/hooks",
            headers=headers,
            json=payload,
        )
        if create_resp.status_code in (200, 201):
            return True
        if create_resp.status_code == 422:
            return False
        create_resp.raise_for_status()
        return False


@router.post(
    "/github/index",
    response_model=GitHubIndexResponse,
    summary="Index a GitHub repo and register webhook",
)
async def github_index_repo(
    payload: GitHubIndexRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(_current_user_id),
    current_user: Any = Depends(get_current_user_optional),
) -> GitHubIndexResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="github",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="GitHub connector not configured")

    token = (connector.get("secrets") or {}).get("token") or (connector.get("secrets") or {}).get("access_token")
    token_type = (connector.get("config") or {}).get("token_type")
    connection_id = (connector.get("config") or {}).get("connection_id")
    base_url = (connector.get("config") or {}).get("base_url") or "https://api.github.com"

    if not connection_id:
        conn_q = db.query(GhConnection)
        if getattr(current_user, "org_id", None):
            conn_q = conn_q.filter(GhConnection.org_id == getattr(current_user, "org_id", None))
        elif user_id:
            conn_q = conn_q.filter(GhConnection.user_id == user_id)
        conn = conn_q.order_by(GhConnection.id.desc()).first()
        if conn:
            connection_id = conn.id

    if not connection_id:
        raise HTTPException(status_code=404, detail="GitHub connection id not found")
    if not token:
        raise HTTPException(status_code=404, detail="GitHub token not found")

    # Ensure repo row exists for webhook lookups
    async with httpx.AsyncClient(timeout=30.0) as client:
        repo_resp = await client.get(
            f"{base_url}/repos/{payload.repo_full_name}",
            headers={
                "Authorization": _github_auth_header(token, token_type),
                "Accept": "application/vnd.github+json",
                "User-Agent": "AutonomousEngineeringPlatform/1.0",
            },
        )
        repo_resp.raise_for_status()
        GitHubService.upsert_repo(db, connection_id, repo_resp.json())

    webhook_url = _oauth_redirect("/api/webhooks/github")
    webhook_registered = await _ensure_github_webhook(
        token=token,
        token_type=token_type,
        repo_full_name=payload.repo_full_name,
        webhook_url=webhook_url,
        base_url=base_url,
    )

    github_index.send(connection_id, payload.repo_full_name)

    return GitHubIndexResponse(
        ok=True,
        repo_full_name=payload.repo_full_name,
        webhook_registered=webhook_registered,
    )


@router.get(
    "/zoom/oauth/start",
    summary="Start Zoom OAuth flow",
)
def zoom_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="zoom",
        fallback_client_id=settings.zoom_client_id,
        fallback_client_secret=settings.zoom_client_secret,
        fallback_scopes=None,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zoom OAuth not configured. Set org app config or ZOOM_CLIENT_ID/ZOOM_CLIENT_SECRET.",
        )

    state = create_state(
        {
            "provider": "zoom",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "client_id": oauth_cfg["client_id"],
        "response_type": "code",
        "redirect_uri": _oauth_redirect("/api/connectors/zoom/oauth/callback"),
        "state": state,
    }
    auth_url = f"https://zoom.us/oauth/authorize?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get(
    "/zoom/oauth/callback",
    summary="Zoom OAuth callback",
)
async def zoom_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "zoom":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id") or getattr(current_user, "org_id", None),
        provider="zoom",
        fallback_client_id=settings.zoom_client_id,
        fallback_client_secret=settings.zoom_client_secret,
        fallback_scopes=None,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zoom OAuth not configured. Set org app config or ZOOM_CLIENT_ID/ZOOM_CLIENT_SECRET.",
        )

    redirect_uri = _oauth_redirect("/api/connectors/zoom/oauth/callback")
    auth_bytes = f"{oauth_cfg['client_id']}:{oauth_cfg['client_secret']}".encode("utf-8")
    basic_auth = base64.b64encode(auth_bytes).decode("utf-8")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://zoom.us/oauth/token",
            params={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Authorization": f"Basic {basic_auth}"},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Zoom OAuth failed: {resp.text}")

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Zoom OAuth missing access_token")

    refresh_token = data.get("refresh_token")
    expires_at = _expires_at_iso(data.get("expires_in"))
    scopes = _parse_scopes(data.get("scope"), delimiter=" ")
    token_type = data.get("token_type")

    account_id = data.get("account_id")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            me_resp = await client.get(
                "https://api.zoom.us/v2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if me_resp.status_code < 300:
                me = me_resp.json()
                account_id = account_id or me.get("account_id")
    except Exception:
        pass

    connectors_service.save_zoom_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        account_id=account_id,
        scopes=scopes,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        expires_at=expires_at,
        db=db,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="zoom",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True, "account_id": account_id}


@router.post(
    "/zoom/sync",
    response_model=ZoomSyncResponse,
    summary="Sync Zoom recordings into NAVI memory",
)
async def zoom_sync(
    payload: ZoomSyncRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
) -> ZoomSyncResponse:
    meeting_ids = await ingest_zoom_meetings(
        db=db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        zoom_user=payload.zoom_user,
        from_date=payload.from_date,
        to_date=payload.to_date,
        max_meetings=payload.max_meetings,
    )
    return ZoomSyncResponse(processed_meeting_ids=meeting_ids, total=len(meeting_ids))


@router.get(
    "/meet/oauth/start",
    summary="Start Google Meet OAuth flow",
)
def meet_oauth_start(
    install: str = "org",
    ui_origin: str | None = None,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=getattr(current_user, "org_id", None),
        provider="meet",
        fallback_client_id=settings.google_client_id,
        fallback_client_secret=settings.google_client_secret,
        fallback_scopes=settings.google_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured. Set org app config or GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.",
        )

    scopes = oauth_cfg["scopes"] or (
        "openid email profile offline_access "
        "https://www.googleapis.com/auth/calendar.readonly "
        "https://www.googleapis.com/auth/calendar.events.readonly "
        "https://www.googleapis.com/auth/drive.readonly"
    )

    state = create_state(
        {
            "provider": "meet",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "id", None),
            "org_id": getattr(current_user, "org_id", None),
            "install": install,
            "ui_origin": ui_origin or None,
        },
        secret=settings.secret_key,
        ttl_seconds=settings.oauth_state_ttl_seconds,
    )

    params = {
        "client_id": oauth_cfg["client_id"],
        "redirect_uri": _oauth_redirect("/api/connectors/meet/oauth/callback"),
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get(
    "/meet/oauth/callback",
    summary="Google Meet OAuth callback",
)
async def meet_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = parse_state(state, secret=settings.secret_key)
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.get("provider") != "meet":
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=payload.get("org_id") or getattr(current_user, "org_id", None),
        provider="meet",
        fallback_client_id=settings.google_client_id,
        fallback_client_secret=settings.google_client_secret,
        fallback_scopes=settings.google_oauth_scopes,
    )
    if not oauth_cfg["client_id"] or not oauth_cfg["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured. Set org app config or GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.",
        )

    redirect_uri = _oauth_redirect("/api/connectors/meet/oauth/callback")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg["client_secret"],
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Google OAuth failed: {resp.text}")

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google OAuth missing access_token")

    refresh_token = data.get("refresh_token")
    expires_at = _expires_at_iso(data.get("expires_in"))
    scopes = _parse_scopes(data.get("scope"), delimiter=" ")

    connectors_service.save_meet_connection(
        user_id=str(payload.get("user_id") or getattr(current_user, "user_id", "unknown")),
        org_id=payload.get("org_id"),
        scopes=scopes,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        calendar_id="primary",
        db=db,
    )

    redirect_url = _build_ui_redirect(
        db=db,
        org_id=payload.get("org_id"),
        provider="meet",
        status_value="success",
        ui_origin=payload.get("ui_origin"),
    )
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=303)

    return {"ok": True}


@router.post(
    "/meet/subscribe",
    response_model=MeetSubscribeResponse,
    summary="Create a Google Calendar watch for Meet events",
)
async def meet_subscribe(
    payload: MeetSubscribeRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
) -> MeetSubscribeResponse:
    connector = connectors_service.get_connector_for_context(
        db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        provider="meet",
    )
    if not connector:
        raise HTTPException(status_code=404, detail="Meet connector not configured")

    secrets = connector.get("secrets") or {}
    cfg = connector.get("config") or {}
    token = secrets.get("access_token") or secrets.get("token")
    refresh_token = secrets.get("refresh_token")
    expires_at = cfg.get("expires_at")

    resolved_org_id = cfg.get("org_id") or getattr(current_user, "org_id", None)
    oauth_cfg = _resolve_oauth_app_config(
        db=db,
        org_id=resolved_org_id,
        provider="meet",
        fallback_client_id=settings.google_client_id,
        fallback_client_secret=settings.google_client_secret,
        fallback_scopes=settings.google_oauth_scopes,
    )

    channel_id = str(uuid4())
    watch = await create_meet_watch(
        access_token=token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        calendar_id=payload.calendar_id,
        channel_id=channel_id,
        notification_url=_oauth_redirect("/api/webhooks/meet"),
        channel_token=settings.meet_webhook_secret,
        client_id=oauth_cfg["client_id"],
        client_secret=oauth_cfg["client_secret"],
    )

    connectors_service.save_meet_connection(
        user_id=str(user_id),
        org_id=cfg.get("org_id") or getattr(current_user, "org_id", None),
        calendar_id=payload.calendar_id,
        scopes=cfg.get("scopes"),
        access_token=token,
        refresh_token=refresh_token,
        expires_at=watch.get("expires_at") or expires_at,
        channel_id=watch.get("channel_id") or channel_id,
        resource_id=watch.get("resource_id"),
        channel_token=watch.get("channel_token"),
        db=db,
    )

    return MeetSubscribeResponse(
        ok=True,
        channel_id=watch.get("channel_id") or channel_id,
        resource_id=watch.get("resource_id"),
        expires_at=watch.get("expires_at"),
    )


@router.post(
    "/meet/sync",
    response_model=MeetSyncResponse,
    summary="Sync recent Google Meet events into NAVI memory",
)
async def meet_sync(
    payload: MeetSyncRequest,
    user_id: str = Depends(_current_user_id),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
) -> MeetSyncResponse:
    events = await list_meet_events(
        db=db,
        user_id=user_id,
        org_id=getattr(current_user, "org_id", None),
        calendar_id=payload.calendar_id,
        days_back=payload.days_back,
    )
    event_ids = await store_meet_events(db=db, user_id=user_id, events=events)
    if payload.include_transcripts:
        try:
            await store_meet_transcripts(
                db=db,
                user_id=user_id,
                org_id=getattr(current_user, "org_id", None),
                events=events,
            )
        except Exception as exc:
            logger.warning("Meet transcript ingestion failed", error=str(exc))
    return MeetSyncResponse(processed_event_ids=event_ids, total=len(event_ids))


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
