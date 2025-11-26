"""
Unified memory retrieval for NAVI.

This module gives the agent a single place to ask:
    "Given this user + query, what do we already know?"

It pulls from multiple backends *if available*:

- Jira / tasks             (backend.services.jira / tasks)
- Slack / Teams / Zoom     (backend.core.integrations_ext.* or services.ingestors.*)
- Confluence / Wiki docs   (backend.core.integrations_ext.*)
- Meetings & answers       (backend.services.meetings / answers)
- Code / repo context      (backend.core.repo_context or search)
- Prior NAVI interactions  (backend.core.memory_system / navi_memory_service)

All calls are defensive: if a service or function is missing, it just logs and
returns an empty list instead of breaking the agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical memory item
# ---------------------------------------------------------------------------

@dataclass
class MemoryItem:
    id: str
    source: str  # e.g. "jira", "slack", "meeting", "wiki", "code", "build", "navi"
    title: str
    body: str
    url: Optional[str] = None
    when: Optional[datetime] = None
    score: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper: safe import & call so we never crash if a service is missing
# ---------------------------------------------------------------------------

def _try_import(path: str):
    """
    Import a module by dotted path, returning None if it does not exist.
    """
    try:
        parts = path.split(".")
        module = __import__(parts[0])
        for p in parts[1:]:
            module = getattr(module, p)
        return module
    except Exception:
        logger.debug("Memory retriever: module %s not available", path)
        return None


def _safe_call(module, func_name: str, *args, **kwargs):
    """
    Call module.func_name(*args, **kwargs) if it exists, else return [].

    This lets us declare our ideal API surface without tightly coupling
    to any one implementation. If a function hasn't been implemented yet,
    NAVI will just skip that source instead of crashing.
    """
    if module is None:
        return []

    func = getattr(module, func_name, None)
    if func is None:
        logger.debug("Memory retriever: %s.%s not found", getattr(module, "__name__", module), func_name)
        return []

    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory retriever: error calling %s.%s: %s", module.__name__, func_name, exc)
        return []


# ---------------------------------------------------------------------------
# Source-specific fetchers
#   NOTE: these are written against a *logical* API. If you already have
#   different function names, you can either:
#       - add small adapter functions in the services, OR
#       - update the func_name strings below.
# ---------------------------------------------------------------------------

def _fetch_jira_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Jira issues & tasks relevant to this user or query.
    """
    jira_mod = _try_import("backend.services.jira")

    # Try a few likely function names until one exists.
    raw_items = (
        _safe_call(jira_mod, "search_issues_for_user", db=db, user_id=user_id, query=query)
        or _safe_call(jira_mod, "search_issues", db=db, query=query)
        or _safe_call(jira_mod, "get_user_issues", db=db, user_id=user_id)
    )

    memories: List[MemoryItem] = []
    for item in raw_items or []:
        try:
            issue_id = str(item.get("id") or item.get("key") or "")
            if not issue_id:
                continue

            memories.append(
                MemoryItem(
                    id=f"jira:{issue_id}",
                    source="jira",
                    title=item.get("summary") or item.get("title") or issue_id,
                    body=item.get("description") or "",
                    url=item.get("url"),
                    when=item.get("updated_at") or item.get("created_at"),
                    metadata={
                        "key": item.get("key"),
                        "status": item.get("status"),
                        "assignee": item.get("assignee"),
                        "project": item.get("project"),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


def _fetch_slack_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Slack messages mentioning the user or matching the query.
    """
    # Try the new slack_service first, then fallback to other integrations
    slack_service = _try_import("backend.services.slack_service")
    slack_read = _try_import("backend.core.integrations_ext.slack_read") 
    slack_ingestor = _try_import("backend.services.ingestors.slack_ingestor")

    raw_msgs = (
        _safe_call(slack_service, "search_messages", db=db, user_id=user_id, query=query)
        or _safe_call(slack_read, "search_messages", user_id=user_id, query=query, db=db)
        or _safe_call(slack_ingestor, "search_messages", user_id=user_id, query=query, db=db)
    )

    memories: List[MemoryItem] = []
    for msg in raw_msgs or []:
        try:
            mid = str(msg.get("id") or "")
            if not mid:
                continue

            memories.append(
                MemoryItem(
                    id=f"slack:{mid}",
                    source="slack",
                    title=msg.get("channel") or "Slack message",
                    body=msg.get("text") or "",
                    url=msg.get("permalink"),
                    when=msg.get("ts"),
                    metadata={
                        "channel": msg.get("channel"),
                        "user": msg.get("user"),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


def _fetch_meeting_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Meeting summaries / action items that may be relevant.
    """
    meetings_mod = _try_import("backend.services.meetings")
    answers_mod = _try_import("backend.services.answers")

    # Try different function signatures for meetings service
    raw_meetings = (
        _safe_call(meetings_mod, "search_meetings", db=db, query=query, user_id=user_id)
        or _safe_call(meetings_mod, "search_meetings", db=db, q=query, people=user_id)
        or _safe_call(meetings_mod, "list_recent_for_user", db=db, user_id=user_id, limit=10)
    )
    
    raw_answers = _safe_call(answers_mod, "search_answers", db=db, query=query, user_id=user_id)

    memories: List[MemoryItem] = []

    for m in raw_meetings or []:
        try:
            mid = str(m.get("id") or "")
            if not mid:
                continue

            memories.append(
                MemoryItem(
                    id=f"meeting:{mid}",
                    source="meeting",
                    title=m.get("title") or "Meeting",
                    body=m.get("summary") or "",
                    url=m.get("url"),
                    when=m.get("start_time"),
                    metadata={"participants": m.get("participants"), "actions": m.get("actions")},
                )
            )
        except Exception:  # noqa: BLE001
            continue

    for a in raw_answers or []:
        try:
            aid = str(a.get("id") or "")
            if not aid:
                continue

            memories.append(
                MemoryItem(
                    id=f"answer:{aid}",
                    source="answer",
                    title=a.get("question") or "Answer",
                    body=a.get("answer") or "",
                    url=None,
                    when=a.get("created_at"),
                    metadata={"session_id": a.get("session_id")},
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


def _fetch_wiki_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Confluence / wiki docs.
    """
    # Try the new confluence_service first, then fallback to other integrations
    confluence_service = _try_import("backend.services.confluence_service")
    conf_read = _try_import("backend.core.integrations_ext.confluence_read")
    wiki_read = _try_import("backend.core.integrations_ext.wiki_read")

    raw_docs = (
        _safe_call(confluence_service, "search_pages", db=db, query=query, user_id=user_id)
        or _safe_call(conf_read, "search_pages", query=query, user_id=user_id, db=db)
        or _safe_call(wiki_read, "search_docs", query=query, user_id=user_id, db=db)
    )

    memories: List[MemoryItem] = []
    for d in raw_docs or []:
        try:
            did = str(d.get("id") or "")
            if not did:
                continue

            memories.append(
                MemoryItem(
                    id=f"wiki:{did}",
                    source="wiki",
                    title=d.get("title") or "Wiki page",
                    body=d.get("excerpt") or d.get("body", ""),
                    url=d.get("url"),
                    when=d.get("updated_at"),
                    metadata={"space": d.get("space"), "labels": d.get("labels")},
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


def _fetch_code_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Code search hits (repo-aware memory).
    """
    repo_context_mod = _try_import("backend.core.repo_context")
    search_mod = _try_import("backend.search.retriever")

    raw_hits = (
        _safe_call(repo_context_mod, "search_code", query=query, user_id=user_id, db=db)
        or _safe_call(search_mod, "search_code", query=query, user_id=user_id, db=db)
    )

    memories: List[MemoryItem] = []
    for h in raw_hits or []:
        try:
            hid = str(h.get("id") or h.get("path") or "")
            if not hid:
                continue

            memories.append(
                MemoryItem(
                    id=f"code:{hid}",
                    source="code",
                    title=h.get("path") or "Code hit",
                    body=h.get("snippet") or h.get("content", ""),
                    url=h.get("url"),
                    when=h.get("updated_at"),
                    metadata={
                        "repo": h.get("repo"),
                        "language": h.get("language"),
                        "score": h.get("score"),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


def _fetch_build_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    CI / build statuses.
    """
    builds_mod = _try_import("backend.services.telemetry") or _try_import("backend.services.ci")

    raw_builds = _safe_call(builds_mod, "search_builds", user_id=user_id, query=query, db=db)

    memories: List[MemoryItem] = []
    for b in raw_builds or []:
        try:
            bid = str(b.get("id") or "")
            if not bid:
                continue

            memories.append(
                MemoryItem(
                    id=f"build:{bid}",
                    source="build",
                    title=b.get("name") or "Build",
                    body=b.get("summary") or "",
                    url=b.get("url"),
                    when=b.get("started_at"),
                    metadata={
                        "status": b.get("status"),
                        "branch": b.get("branch"),
                        "commit": b.get("commit"),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


async def _fetch_long_term_navi_memories(user_id: str, query: str, db=None) -> List[MemoryItem]:
    """
    Prior NAVI conversations / long-term memory via vector store.

    This expects either:
      - backend.core.memory_system.vector_store.search_memories, or
      - backend.services.navi_memory_service.search_memory
    """
    vs_mod = _try_import("backend.core.memory_system.vector_store")
    navi_mem_mod = _try_import("backend.services.navi_memory_service")

    # Try the existing navi_memory_service.search_memory function first
    raw = []
    if navi_mem_mod and db is not None:
        try:
            # Use the existing search_memory function (note: different name than spec)
            from backend.services.navi_memory_service import search_memory
            raw = await search_memory(
                db=db, user_id=user_id, query=query, 
                categories=["profile", "workspace", "task", "interaction"],
                min_importance=3, limit=10
            )
        except Exception as e:
            logger.debug("Memory retriever: navi memory search failed: %s", e)
            raw = []
    
    # Fallback to vector store if available
    if not raw:
        raw = _safe_call(vs_mod, "search_memories", user_id=user_id, query=query, db=db)

    memories: List[MemoryItem] = []
    for m in raw or []:
        try:
            # Handle both dict and object formats
            if hasattr(m, 'id') and not isinstance(m, dict):
                # SQLAlchemy model
                mid = str(getattr(m, 'id', ''))
                title = getattr(m, 'title', None) or "Previous NAVI context"
                body = getattr(m, 'content', '') or ''
                created_at = getattr(m, 'created_at', None)
                score = getattr(m, 'similarity', 1.0) or 1.0
                metadata = getattr(m, 'metadata', {}) or {}
            else:
                # Dict format
                mid = str(m.get("id") or "") if isinstance(m, dict) else str(m)
                title = m.get("title", "Previous NAVI context") if isinstance(m, dict) else "Previous NAVI context"
                body = m.get("content", "") if isinstance(m, dict) else ""
                created_at = m.get("created_at") if isinstance(m, dict) else None
                score = (m.get("score") or m.get("similarity") or 1.0) if isinstance(m, dict) else 1.0
                metadata = m.get("metadata", {}) if isinstance(m, dict) else {}
                
            if not mid:
                continue

            memories.append(
                MemoryItem(
                    id=f"navi:{mid}",
                    source="navi",
                    title=title,
                    body=body,
                    url=None,
                    when=created_at,
                    score=score,
                    metadata=metadata,
                )
            )
        except Exception:  # noqa: BLE001
            continue

    return memories


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_unified_memories(
    user_id: str,
    query: str,
    db=None,
) -> Dict[str, Any]:
    """
    Main entry point used by the agent loop.

    Returns a dict shaped for build_context(), with:
        {
          "items": [MemoryItem, ...],
          "by_source": {
              "jira": [...],
              "slack": [...],
              ...
          }
        }
    """
    logger.info("[MEMORY] Retrieving unified memories for user=%s query='%s...'", user_id, query[:60])

    # NOTE: this is intentionally sync-style even though the outer function is async.
    # Most downstream services are sync today; if you add async services later you
    # can wrap them in asyncio.to_thread or similar.
    jira_items = _fetch_jira_memories(user_id, query, db=db)
    slack_items = _fetch_slack_memories(user_id, query, db=db)
    meeting_items = _fetch_meeting_memories(user_id, query, db=db)
    wiki_items = _fetch_wiki_memories(user_id, query, db=db)
    code_items = _fetch_code_memories(user_id, query, db=db)
    build_items = _fetch_build_memories(user_id, query, db=db)
    navi_items = await _fetch_long_term_navi_memories(user_id, query, db=db)

    all_items: List[MemoryItem] = (
        jira_items
        + slack_items
        + meeting_items
        + wiki_items
        + code_items
        + build_items
        + navi_items
    )

    logger.info(
        "[MEMORY] Retrieved %d unified items (jira=%d slack=%d meetings=%d wiki=%d code=%d builds=%d navi=%d)",
        len(all_items),
        len(jira_items),
        len(slack_items),
        len(meeting_items),
        len(wiki_items),
        len(code_items),
        len(build_items),
        len(navi_items),
    )

    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for item in all_items:
        by_source.setdefault(item.source, []).append(_memory_to_dict(item))

    return {
        "items": [_memory_to_dict(m) for m in all_items],
        "by_source": by_source,
    }


def _memory_to_dict(m: MemoryItem) -> Dict[str, Any]:
    return {
        "id": m.id,
        "source": m.source,
        "title": m.title,
        "body": m.body,
        "url": m.url,
        "when": m.when.isoformat() if isinstance(m.when, datetime) else m.when,
        "score": m.score,
        "metadata": m.metadata,
    }