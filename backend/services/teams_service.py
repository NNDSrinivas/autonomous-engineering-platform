# backend/services/teams_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

try:
    from backend.core.integrations.teams_client import TeamsClient  # type: ignore
except Exception:  # pragma: no cover
    TeamsClient = None  # type: ignore[misc]


def _get_client(db: Optional[Session] = None) -> Optional["TeamsClient"]:
    """
    Helper to construct a TeamsClient instance if the integration is available.
    """
    if TeamsClient is None:
        return None

    try:
        return TeamsClient()
    except Exception:
        return None


def search_messages(
    db: Session,
    user_id: str,
    query: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search Teams messages by query text (for unified memory retriever).

    Returns normalized message format:
    {
        "id": str,
        "channel": str,
        "text": str,
        "user": str | None,
        "ts": str | None,
        "permalink": str | None,
    }
    """
    client = _get_client(db)
    if client is None:
        return []

    try:
        raw_messages = client.search_messages(
            query=query,
            user_id=user_id,
            limit=limit,
        )
    except AttributeError:
        return []
    except Exception:
        return []

    normalized: List[Dict[str, Any]] = []
    for msg in raw_messages or []:
        normalized.append(
            {
                "id": str(msg.get("id") or msg.get("messageId") or ""),
                "channel": msg.get("channel") or msg.get("channelName"),
                "text": msg.get("text") or msg.get("body") or "",
                "user": msg.get("user") or msg.get("from"),
                "ts": msg.get("timestamp") or msg.get("createdDateTime"),
                "permalink": msg.get("permalink") or msg.get("webUrl"),
            }
        )

    return normalized
