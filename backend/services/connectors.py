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
    email: str,
    api_token: str,
    db: Optional[Session] = None,
) -> None:
    """
    Save Jira connection details for a user (dev-mode, in-memory).

    Later we can:
    - persist to DB,
    - validate credentials by doing a test Jira call,
    - encrypt the token with KMS / secrets manager.
    """
    upsert_connector(
        db=db,
        user_id=user_id,
        provider="jira",
        name="default",
        config={"base_url": base_url, "email": email},
        secrets={"api_token": api_token},
    )


def save_slack_connection(user_id: str, bot_token: str, db: Optional[Session] = None) -> None:
    """
    Save Slack connection (bot token) for a user.
    """
    upsert_connector(
        db=db,
        user_id=user_id,
        provider="slack",
        name="default",
        config={},
        secrets={"bot_token": bot_token},
    )


def save_github_connection(user_id: str, access_token: str) -> None:
    """
    Save GitHub connection for a user.
    """
    upsert_connector(
        db=None,
        user_id=user_id,
        provider="github",
        name="default",
        config={},
        secrets={"access_token": access_token},
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


def connectors_available(db: Optional[Session]) -> bool:
    """Return True if the connectors table is reachable."""
    return bool(db) and _table_exists(db, "connectors")
