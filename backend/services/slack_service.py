# backend/services/slack_service.py

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.integrations.slack_client import SlackClient
from backend.services import connectors as connectors_service

logger = logging.getLogger(__name__)


def _get_client(
    db: Optional[Session] = None,
    *,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> Optional[SlackClient]:
    """
    Safe helper to construct a SlackClient instance.

    Returns None if Slack is not configured so that NAVI keeps working
    even when AEP_SLACK_BOT_TOKEN is missing.
    """
    try:
        token = None
        if db and (user_id or org_id):
            connector = connectors_service.get_connector_for_context(
                db, user_id=user_id, org_id=org_id, provider="slack"
            )
            if connector:
                token = (connector.get("secrets") or {}).get("bot_token")
        return SlackClient(bot_token=token) if token else SlackClient()
    except Exception as e:
        # Most common case: AEP_SLACK_BOT_TOKEN not set
        logger.info("SlackClient not available: %s", e)
        return None


def search_messages_for_user(
    db: Session,
    user_id: str,
    limit: int = 30,
    include_threads: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return recent Slack messages that are relevant for the given user.

    For now this is intentionally simple and safe:

    - Lists all channels the bot can see
    - Pulls recent messages from each channel
    - Optionally expands threads
    - Later we can filter more strictly by user_id or mentions

    Each returned item has the shape:

        {
            "id": str,
            "channel": str,      # channel id
            "channel_name": str, # human readable name
            "text": str,
            "user": str | None,
            "ts": str | None,
            "permalink": str | None,
        }
    """
    client = _get_client(db, user_id=user_id)
    if client is None:
        return []

    messages: List[Dict[str, Any]] = []

    try:
        channels = client.list_channels()
    except Exception as e:
        logger.warning("Slack: failed to list channels: %s", e, exc_info=True)
        return []

    # Simple strategy for now:
    # - Walk channels in order
    # - Collect messages until we hit the limit
    for ch in channels:
        if len(messages) >= limit:
            break

        ch_id = ch.get("id")
        ch_name = ch.get("name") or ch_id
        if not ch_id:
            continue

        try:
            raw_msgs = client.fetch_channel_messages(
                channel_id=ch_id,
                limit=min(limit - len(messages), 200),
            )
        except Exception as e:
            logger.warning(
                "Slack: failed to fetch messages for channel %s: %s",
                ch_id,
                e,
                exc_info=True,
            )
            continue

        for m in raw_msgs or []:
            if len(messages) >= limit:
                break

            ts = m.get("ts")
            text = m.get("text") or ""
            user = m.get("user")

            # Optional: expand threads (we keep it off by default if include_threads is False)
            if include_threads and m.get("thread_ts") and m.get("thread_ts") == ts:
                try:
                    replies = client.fetch_thread_replies(ch_id, m["thread_ts"])
                except Exception as e:
                    logger.debug(
                        "Slack: failed to fetch thread replies for %s in %s: %s",
                        ts,
                        ch_id,
                        e,
                    )
                else:
                    for r in replies[1:]:  # skip parent (already handled)
                        if len(messages) >= limit:
                            break
                        r_ts = r.get("ts")
                        r_text = r.get("text") or ""
                        r_user = r.get("user")
                        messages.append(
                            {
                                "id": f"{ch_id}:{r_ts}",
                                "channel": ch_id,
                                "channel_name": ch_name,
                                "text": r_text,
                                "user": r_user,
                                "ts": r_ts,
                                "permalink": _build_permalink(ch_id, r_ts),
                            }
                        )

            messages.append(
                {
                    "id": f"{ch_id}:{ts}",
                    "channel": ch_id,
                    "channel_name": ch_name,
                    "text": text,
                    "user": user,
                    "ts": ts,
                    "permalink": _build_permalink(ch_id, ts),
                }
            )

    logger.info("Slack: collected %d messages for org memory", len(messages))
    return messages


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
    # For now, just delegate to search_messages_for_user since we don't have query-based search
    # Later we can implement actual query matching
    return search_messages_for_user(db, user_id, limit, include_threads=True)


def _build_permalink(channel_id: str, ts: Optional[str]) -> Optional[str]:
    """
    Best-effort permalink builder.

    This mirrors what your SlackIngestor already uses:
    https://slack.com/archives/{channel_id}/p{ts_without_dot}
    """
    if not channel_id or not ts:
        return None
    return f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
