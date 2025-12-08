# backend/services/connectors.py

"""
Lightweight connector service for NAVI.

Phase 1 (dev mode):
- Stores connector configuration in an in-memory dict keyed by user_id.
- No database migrations required.
- API surface is stable so we can later swap to a real DB-backed model.

Connectors covered:
- jira
- slack
- github
- teams
- zoom
- confluence
- gitlab
- jenkins
"""

from __future__ import annotations

from typing import Dict, Any, List

from backend.schemas.connectors import ConnectorStatus


# In-memory storage: { user_id: { connector_id: { ...config... } } }
_USER_CONNECTORS: Dict[str, Dict[str, Dict[str, Any]]] = {}


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


def get_connector_status_for_user(user_id: str) -> List[ConnectorStatus]:
    """
    Return the status of all known connectors for this user.

    In dev mode:
    - "connected" if we have any config saved for that connector
    - "disconnected" otherwise
    """
    user_key = str(user_id)
    user_connectors = _USER_CONNECTORS.get(user_key, {})

    items: List[ConnectorStatus] = []
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


def save_jira_connection(
    user_id: str,
    base_url: str,
    email: str,
    api_token: str,
) -> None:
    """
    Save Jira connection details for a user (dev-mode, in-memory).

    Later we can:
    - persist to DB,
    - validate credentials by doing a test Jira call,
    - encrypt the token with KMS / secrets manager.
    """
    user_connectors = _ensure_user(str(user_id))

    user_connectors["jira"] = {
        "base_url": base_url,
        "email": email,
        "api_token": api_token,
    }


def save_slack_connection(user_id: str, bot_token: str) -> None:
    """
    Save Slack connection (bot token) for a user.
    """
    user_connectors = _ensure_user(str(user_id))
    user_connectors["slack"] = {
        "bot_token": bot_token,
    }


def save_github_connection(user_id: str, access_token: str) -> None:
    """
    Save GitHub connection for a user.
    """
    user_connectors = _ensure_user(str(user_id))
    user_connectors["github"] = {
        "access_token": access_token,
    }





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