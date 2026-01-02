# backend/services/connectors.py

from __future__ import annotations

from typing import Dict, Any, List, Optional
import json
import logging

from backend.schemas.connectors import ConnectorStatus
from backend.core.crypto import encrypt_token, decrypt_token
from backend.models.connector import Connector
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from functools import lru_cache

logger = logging.getLogger(__name__)


# In-memory storage: { user_id: { connector_id: { ...config... } } }
_USER_CONNECTORS: Dict[str, Dict[str, Dict[str, Any]]] = {}
_FALLBACK_WARNING = (
    "Connectors table is unavailable. Falling back to in-memory storage. "
    "Run Alembic migrations and ensure DATABASE_URL/sqlalchemy_url is configured."
)


@lru_cache(maxsize=1)
def _warn_once() -> None:
    logger.warning(_FALLBACK_WARNING)


# --- helpers --------------------------------------------------------------


def _ensure_user(user_id: str) -> Dict[str, Dict[str, Any]]:
    if user_id not in _USER_CONNECTORS:
        _USER_CONNECTORS[user_id] = {}
    return _USER_CONNECTORS[user_id]


def _base_catalog() -> List[ConnectorStatus]:
    """
    Full catalog of connectors NAVI knows about.

    Status will be filled per-user based on _USER_CONNECTORS.
    """
    return [
        ConnectorStatus(id="jira", name="Jira", category="work_tracking"),
        ConnectorStatus(id="slack", name="Slack", category="chat"),
        ConnectorStatus(id="github", name="GitHub", category="code"),
        ConnectorStatus(id="gitlab", name="GitLab", category="code"),
        ConnectorStatus(id="teams", name="Microsoft Teams", category="chat"),
        ConnectorStatus(id="meet", name="Google Meet", category="meetings"),
        ConnectorStatus(id="zoom", name="Zoom", category="meetings"),
        ConnectorStatus(id="confluence", name="Confluence", category="wiki"),
        ConnectorStatus(id="jenkins", name="Jenkins", category="ci_cd"),
    ]


# --- public API -----------------------------------------------------------


def get_connector_status_for_user(
    user_id: str, db: Optional[Session] = None
) -> List[ConnectorStatus]:
    """
    Return the status of all known connectors for this user.

    Prefers DB-backed connectors if table exists; falls back to in-memory.
    """
    items: List[ConnectorStatus] = []
    if db and _table_exists(db, "connectors"):
        db_items = (
            db.query(Connector)
            .filter(Connector.user_id == str(user_id))
            .all()
        )
        connected_map = {(c.provider or "").lower(): True for c in db_items}
        for base in _base_catalog():
            if connected_map.get(base.id):
                items.append(
                    ConnectorStatus(
                        id=base.id,
                        name=base.name,
                        category=base.category,
                        status="connected",
                    )
                )
            else:
                items.append(base)
        return items

    # fallback: in-memory
    _warn_once()
    user_key = str(user_id)
    user_connectors = _USER_CONNECTORS.get(user_key, {})
    for base in _base_catalog():
        if base.id in user_connectors:
            items.append(
                ConnectorStatus(
                    id=base.id,
                    name=base.name,
                    category=base.category,
                    status="connected",
                )
            )
        else:
            items.append(base)
    return items


def upsert_connector(
    db: Optional[Session],
    user_id: str,
    provider: str,
    name: str,
    config: Optional[Dict[str, Any]] = None,
    secrets: Optional[Dict[str, Any]] = None,
    workspace_root: Optional[str] = None,
) -> Optional[int]:
    """
    Persist connector to DB if available; fallback to in-memory.
    Returns connector id (or None in in-memory fallback).
    """
    provider = provider.lower()
    if db and _table_exists(db, "connectors"):
        try:
            encrypted_secrets = {}
            for k, v in (secrets or {}).items():
                if v:
                    try:
                        encrypted_secrets[k] = encrypt_token(str(v))
                    except Exception as e:
                        logger.warning("Failed to encrypt secret %s: %s", k, e)
            config_json = json.dumps(config or {})
            secret_blob = (
                json.dumps(encrypted_secrets or {}).encode("utf-8")
                if encrypted_secrets
                else None
            )
            existing = (
                db.query(Connector)
                .filter(
                    Connector.user_id == str(user_id),
                    Connector.provider == provider,
                    Connector.name == name,
                )
                .first()
            )
            if existing:
                existing.config_json = config_json
                existing.secret_json = secret_blob
                existing.workspace_root = workspace_root
                db.add(existing)
                db.commit()
                db.refresh(existing)
                return existing.id
            new = Connector(
                user_id=str(user_id),
                provider=provider,
                name=name,
                config_json=config_json,
                secret_json=secret_blob,
                workspace_root=workspace_root,
            )
            db.add(new)
            db.commit()
            db.refresh(new)
            return new.id
        except Exception as e:
            logger.error("DB upsert connector failed, falling back to memory: %s", e, exc_info=True)
            db.rollback()

    # fallback in-memory
    _warn_once()
    user_connectors = _ensure_user(str(user_id))
    user_connectors[provider] = {
        "name": name,
        "config": config or {},
        "secrets": secrets or {},
        "workspace_root": workspace_root,
    }
    return None


def list_connectors(
    db: Optional[Session],
    user_id: str,
    workspace_root: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List connectors (excluding secrets). If DB is available, use it; else fallback.
    """
    provider_filter = (lambda c: True) if not provider else (lambda c: (c or "").lower() == provider.lower())
    results: List[Dict[str, Any]] = []
    if db and _table_exists(db, "connectors"):
        try:
            q = db.query(Connector).filter(Connector.user_id == str(user_id))
            if workspace_root:
                q = q.filter(Connector.workspace_root == workspace_root)
            for c in q.all():
                if not provider_filter(c.provider):
                    continue
                cfg = {}
                try:
                    cfg = json.loads(c.config_json or "{}")
                except Exception:
                    cfg = {}
                results.append(
                    {
                        "id": c.id,
                        "provider": c.provider,
                        "name": c.name,
                        "config": cfg,
                        "workspace_root": c.workspace_root,
                    }
                )
            return results
        except Exception as e:
            logger.error("DB list connectors failed, falling back: %s", e, exc_info=True)

    # fallback in-memory
    _warn_once()
    user_connectors = _USER_CONNECTORS.get(str(user_id), {})
    for provider_name, data in user_connectors.items():
        if not provider_filter(provider_name):
            continue
        results.append(
            {
                "id": None,
                "provider": provider_name,
                "name": data.get("name", "default"),
                "config": data.get("config", {}),
                "workspace_root": data.get("workspace_root"),
            }
        )
    return results


def delete_connector(
    db: Optional[Session], user_id: str, connector_id: int
) -> bool:
    if db and _table_exists(db, "connectors"):
        try:
            deleted = (
                db.query(Connector)
                .filter(Connector.user_id == str(user_id), Connector.id == connector_id)
                .delete()
            )
            db.commit()
            return bool(deleted)
        except Exception as e:
            logger.error("DB delete connector failed: %s", e, exc_info=True)
            db.rollback()
    return False


def save_jira_connection(
    user_id: str,
    base_url: str,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    token_type: Optional[str] = None,
    expires_at: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    """
    Save Jira connection details for a user (dev-mode, in-memory).

    Later we can:
    - persist to DB,
    - validate credentials by doing a test Jira call,
    - encrypt the token with KMS / secrets manager.
    """
    config: Dict[str, Any] = {"base_url": base_url}
    if email:
        config["email"] = email
    if token_type:
        config["token_type"] = token_type
    if expires_at:
        config["expires_at"] = expires_at

    secrets: Dict[str, Any] = {}
    if api_token:
        secrets["api_token"] = api_token
    if access_token:
        secrets["access_token"] = access_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="jira",
        name="default",
        config=config,
        secrets=secrets,
    )


def save_slack_connection(
    user_id: str,
    bot_token: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    team_name: Optional[str] = None,
    bot_user_id: Optional[str] = None,
    token_type: Optional[str] = None,
    scope: Optional[str] = None,
    install_scope: Optional[str] = None,
    user_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    user_refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> None:
    """
    Save Slack connection (bot token) for a user.
    """
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if team_id:
        config["team_id"] = team_id
    if team_name:
        config["team_name"] = team_name
    if bot_user_id:
        config["bot_user_id"] = bot_user_id
    if token_type:
        config["token_type"] = token_type
    if scope:
        config["scope"] = scope
    if install_scope:
        config["install_scope"] = install_scope
    if expires_at:
        config["expires_at"] = expires_at

    secrets: Dict[str, Any] = {"bot_token": bot_token}
    if user_token:
        secrets["user_token"] = user_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token
    if user_refresh_token:
        secrets["user_refresh_token"] = user_refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="slack",
        name=team_id or "default",
        config=config,
        secrets=secrets,
    )


def save_github_connection(
    user_id: str,
    access_token: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    base_url: Optional[str] = None,
    token_type: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> None:
    """
    Save GitHub connection for a user.
    """
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if base_url:
        config["base_url"] = base_url
    if token_type:
        config["token_type"] = token_type
    if scopes:
        config["scopes"] = scopes
    if expires_at:
        config["expires_at"] = expires_at
    if connection_id:
        config["connection_id"] = connection_id

    secrets: Dict[str, Any] = {
        "access_token": access_token,
        "token": access_token,
    }
    if refresh_token:
        secrets["refresh_token"] = refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="github",
        name="default",
        config=config,
        secrets=secrets,
    )


def save_confluence_connection(
    user_id: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    base_url: Optional[str] = None,
    cloud_id: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
) -> None:
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if base_url:
        config["base_url"] = base_url
    if cloud_id:
        config["cloud_id"] = cloud_id
    if scopes:
        config["scopes"] = scopes
    if expires_at:
        config["expires_at"] = expires_at
    if email:
        config["email"] = email

    secrets: Dict[str, Any] = {}
    if access_token:
        secrets["access_token"] = access_token
        secrets["token"] = access_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token
    if api_token:
        secrets["api_token"] = api_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="confluence",
        name=cloud_id or "default",
        config=config,
        secrets=secrets,
    )


def save_teams_connection(
    user_id: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    install_scope: Optional[str] = None,
    subscription_id: Optional[str] = None,
) -> None:
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if tenant_id:
        config["tenant_id"] = tenant_id
    if scopes:
        config["scopes"] = scopes
    if expires_at:
        config["expires_at"] = expires_at
    if install_scope:
        config["install_scope"] = install_scope
    if subscription_id:
        config["subscription_id"] = subscription_id

    secrets: Dict[str, Any] = {}
    if access_token:
        secrets["access_token"] = access_token
        secrets["token"] = access_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="teams",
        name=tenant_id or "default",
        config=config,
        secrets=secrets,
    )


def save_zoom_connection(
    user_id: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    account_id: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    token_type: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> None:
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if account_id:
        config["account_id"] = account_id
    if scopes:
        config["scopes"] = scopes
    if token_type:
        config["token_type"] = token_type
    if expires_at:
        config["expires_at"] = expires_at

    secrets: Dict[str, Any] = {}
    if access_token:
        secrets["access_token"] = access_token
        secrets["token"] = access_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="zoom",
        name=account_id or "default",
        config=config,
        secrets=secrets,
    )


def save_meet_connection(
    user_id: str,
    db: Optional[Session] = None,
    *,
    org_id: Optional[str] = None,
    calendar_id: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    channel_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    channel_token: Optional[str] = None,
    last_sync: Optional[str] = None,
) -> None:
    config: Dict[str, Any] = {}
    if org_id:
        config["org_id"] = org_id
    if calendar_id:
        config["calendar_id"] = calendar_id
    if scopes:
        config["scopes"] = scopes
    if expires_at:
        config["expires_at"] = expires_at
    if channel_id:
        config["channel_id"] = channel_id
    if resource_id:
        config["resource_id"] = resource_id
    if channel_token:
        config["channel_token"] = channel_token
    if last_sync:
        config["last_sync"] = last_sync

    secrets: Dict[str, Any] = {}
    if access_token:
        secrets["access_token"] = access_token
        secrets["token"] = access_token
    if refresh_token:
        secrets["refresh_token"] = refresh_token

    upsert_connector(
        db=db,
        user_id=user_id,
        provider="meet",
        name=calendar_id or "default",
        config=config,
        secrets=secrets,
    )


def save_oauth_app_config(
    *,
    db: Optional[Session],
    org_id: str,
    provider: str,
    client_id: str,
    client_secret: str,
    scopes: Optional[str] = None,
    tenant_id: Optional[str] = None,
    account_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    updated_by: Optional[str] = None,
) -> Optional[int]:
    """
    Save per-org OAuth app credentials for a provider.
    Stored in connectors table under provider 'oauth_app'.
    """
    config: Dict[str, Any] = {"org_id": org_id, "client_id": client_id}
    if scopes:
        config["scopes"] = scopes
    if tenant_id:
        config["tenant_id"] = tenant_id
    if account_id:
        config["account_id"] = account_id
    if extra:
        config["extra"] = extra
    if updated_by:
        config["updated_by"] = updated_by

    secrets: Dict[str, Any] = {"client_secret": client_secret}

    return upsert_connector(
        db=db,
        user_id=f"org:{org_id}",
        provider="oauth_app",
        name=provider.lower(),
        config=config,
        secrets=secrets,
    )


def get_oauth_app_config(
    *,
    db: Optional[Session],
    org_id: str,
    provider: str,
) -> Optional[Dict[str, Any]]:
    """Fetch per-org OAuth app config for provider."""
    if not db or not _table_exists(db, "connectors"):
        return None
    return get_connector(
        db,
        user_id=f"org:{org_id}",
        provider="oauth_app",
        name=provider.lower(),
    )


def get_jira_connection(user_id: str) -> Dict[str, Any] | None:
    """Get Jira connection details for a user."""
    user_key = str(user_id)
    user_connectors = _USER_CONNECTORS.get(user_key, {})
    return user_connectors.get("jira")


def get_slack_connection(user_id: str) -> Dict[str, Any] | None:
    """Get Slack connection details for a user."""
    user_key = str(user_id)
    user_connectors = _USER_CONNECTORS.get(user_key, {})
    return user_connectors.get("slack")


def _table_exists(db: Session, table_name: str) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table(table_name)
    except Exception:
        return False


def get_connector(
    db: Session,
    user_id: str,
    provider: str,
    name: str = "default",
) -> Optional[Dict[str, Any]]:
    """Fetch connector config + decrypted secrets for a provider/name."""
    if not _table_exists(db, "connectors"):
        return None
    row = (
        db.query(Connector)
        .filter(
            Connector.user_id == str(user_id),
            Connector.provider == provider.lower(),
            Connector.name == name,
        )
        .first()
    )
    if not row:
        return None
    cfg = {}
    try:
        cfg = json.loads(row.config_json or "{}")
    except Exception:
        cfg = {}
    secrets = {}
    if row.secret_json:
        try:
            decoded = json.loads(row.secret_json.decode("utf-8"))
            for k, v in decoded.items():
                try:
                    secrets[k] = decrypt_token(v)
                except Exception:
                    secrets[k] = None
        except Exception:
            secrets = {}
    return {"config": cfg, "secrets": secrets, "id": row.id}


def get_connector_for_org(
    db: Session,
    org_id: str,
    provider: str,
    name: str | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Best-effort lookup for an org-scoped connector stored in config_json.
    """
    if not _table_exists(db, "connectors"):
        return None
    try:
        rows = (
            db.query(Connector)
            .filter(Connector.provider == provider.lower())
            .all()
        )
    except Exception:
        return None
    for row in rows:
        if name and row.name != name:
            continue
        cfg = {}
        try:
            cfg = json.loads(row.config_json or "{}")
        except Exception:
            cfg = {}
        if cfg.get("org_id") != org_id:
            continue
        secrets = {}
        if row.secret_json:
            try:
                decoded = json.loads(row.secret_json.decode("utf-8"))
                for k, v in decoded.items():
                    try:
                        secrets[k] = decrypt_token(v)
                    except Exception:
                        secrets[k] = None
            except Exception:
                secrets = {}
        return {
            "config": cfg,
            "secrets": secrets,
            "id": row.id,
            "user_id": row.user_id,
            "provider": row.provider,
            "name": row.name,
        }
    return None


def get_connector_for_context(
    db: Optional[Session],
    *,
    user_id: Optional[str],
    org_id: Optional[str],
    provider: str,
    name: str | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Lookup connector by user_id first, then fall back to org-scoped config.
    """
    if not db:
        return None
    if user_id:
        row = get_connector(db, user_id=str(user_id), provider=provider, name=name or "default")
        if row:
            return row
    if org_id:
        return get_connector_for_org(db, org_id=org_id, provider=provider, name=name)
    return None


def find_connector_by_config(
    db: Optional[Session],
    *,
    provider: str,
    key: str,
    value: str,
) -> Optional[Dict[str, Any]]:
    """
    Find a connector by a specific config key/value (e.g., Slack team_id).
    """
    if not db or not value or not _table_exists(db, "connectors"):
        return None
    try:
        rows = (
            db.query(Connector)
            .filter(Connector.provider == provider.lower())
            .all()
        )
    except Exception:
        return None
    for row in rows:
        cfg = {}
        try:
            cfg = json.loads(row.config_json or "{}")
        except Exception:
            cfg = {}
        if str(cfg.get(key)) != str(value):
            continue
        secrets = {}
        if row.secret_json:
            try:
                decoded = json.loads(row.secret_json.decode("utf-8"))
                for k, v in decoded.items():
                    try:
                        secrets[k] = decrypt_token(v)
                    except Exception:
                        secrets[k] = None
            except Exception:
                secrets = {}
        return {"config": cfg, "secrets": secrets, "id": row.id}
    return None


def connectors_available(db: Optional[Session]) -> bool:
    """Return True if the connectors table is reachable."""
    return bool(db) and _table_exists(db, "connectors")
