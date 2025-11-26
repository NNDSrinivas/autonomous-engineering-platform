# backend/services/slack_service.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

try:
    # Core Slack integration client (reads from DB or Slack API depending on implementation)
    from backend.core.integrations.slack_client import SlackClient  # type: ignore
except Exception:  # pragma: no cover
    SlackClient = None  # type: ignore[misc]


def _get_client(db: Optional[Session] = None) -> Optional["SlackClient"]:
    """
    Helper to construct a SlackClient instance if the integration is available.
    This is defensive so that NAVI does not crash if Slack is not configured yet.
    """
    if SlackClient is None:
        return None

    try:
        # Adapt this to however your SlackClient is actually constructed.
        # Many projects don't need `db` here; it's passed just in case.
        return SlackClient()
    except Exception:
        return None


def search_messages_for_user(
    db: Session,
    user_id: str,
    limit: int = 20,
    include_threads: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return recent Slack messages that are relevant for the given user.

    This is intentionally generic: it can be backed either by
    - direct Slack API calls, or
    - a DB-backed index populated by slack_ingestor.py.

    The contract for each returned item:

        {
            "id": str,               # internal ID or Slack ts
            "channel": str,          # channel name or ID
            "text": str,             # message text
            "user": str | None,      # author username
            "ts": str | None,        # timestamp (Slack ts)
            "permalink": str | None, # deep link to Slack
        }
    """
    client = _get_client(db)
    if client is None:
        return []

    try:
        # You will need to adapt this to your actual SlackClient API.
        # For example, maybe you already have:
        #   client.search_messages_for_user(user_id=user_id, limit=limit)
        raw_messages = client.search_messages_for_user(
            user_id=user_id,
            limit=limit,
            include_threads=include_threads,
        )
    except AttributeError:
        # Fallback: if your client has a different API, adapt here.
        # This keeps NAVI from crashing while we wire it up.
        return []
    except Exception:
        return []

    normalized: List[Dict[str, Any]] = []
    for msg in raw_messages or []:
        normalized.append(
            {
                "id": str(msg.get("id") or msg.get("ts") or ""),
                "channel": msg.get("channel") or msg.get("channel_id"),
                "text": msg.get("text") or "",
                "user": msg.get("user"),
                "ts": msg.get("ts"),
                "permalink": msg.get("permalink") or msg.get("url"),
            }
        )

    return normalized


def search_messages(
    db: Session,
    user_id: str,
    query: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search Slack messages by query text (for unified memory retriever).
    This is the function expected by unified_memory_retriever._fetch_slack_memories.
    """
    client = _get_client(db)
    if client is None:
        return []

    try:
        # Try to search by query if client supports it
        if hasattr(client, 'search_messages'):
            raw_messages = client.search_messages(
                query=query,
                user_id=user_id,
                limit=limit,
            )
        else:
            # Fallback to user messages if no query search
            raw_messages = client.search_messages_for_user(
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
                "id": str(msg.get("id") or msg.get("ts") or ""),
                "channel": msg.get("channel") or msg.get("channel_id"),
                "text": msg.get("text") or "",
                "user": msg.get("user"),
                "ts": msg.get("ts"),
                "permalink": msg.get("permalink") or msg.get("url"),
            }
        )

    return normalized