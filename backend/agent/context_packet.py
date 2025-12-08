"""
Context Packet builder

Produces a normalized, source-linked packet of everything NAVI needs for a task/PR:
- Jira issue facts
- Conversations, meetings, docs
- PRs/builds/tests
- Code references and owners
- Decisions, risks, actions, approvals

This is intentionally light on implementation for now; connectors will hydrate the
packet incrementally (Jira webhook ingest, Slack/Teams, GitHub, CI, docs).
"""

from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.core.cache.service import cache_service

logger = logging.getLogger(__name__)


@dataclass
class SourceRef:
    """Clickable source reference for IDE/agent responses."""

    name: str
    type: str  # e.g., "jira", "slack", "github", "doc", "ci"
    url: Optional[str] = None
    connector: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPacket:
    """Structured context for a single task/PR."""

    task_key: str
    summary: Optional[str] = None
    status: Optional[str] = None
    acceptance: List[str] = field(default_factory=list)
    jira: Dict[str, Any] = field(default_factory=dict)
    prs: List[Dict[str, Any]] = field(default_factory=list)
    builds: List[Dict[str, Any]] = field(default_factory=list)
    tests: List[Dict[str, Any]] = field(default_factory=list)
    conversations: List[Dict[str, Any]] = field(default_factory=list)
    meetings: List[Dict[str, Any]] = field(default_factory=list)
    docs: List[Dict[str, Any]] = field(default_factory=list)
    code_refs: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    owners: List[Dict[str, Any]] = field(default_factory=list)
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[SourceRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass (including nested SourceRef) into a JSON-friendly dict."""
        data = asdict(self)
        data["sources"] = [asdict(src) for src in self.sources]
        return data


async def build_context_packet(
    task_key: str,
    db: Session,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
    include_related: bool = True,
    related_limit: int = 5,
    use_cache: bool = True,
) -> ContextPacket:
    """
    Assemble a ContextPacket using persisted connector data.

    Current scope (v0.1):
    - Pull Jira issue from local DB cache (ingested via JiraService)
    - Shape packet + initial sources list

    Upcoming:
    - Hydrate conversations (Slack/Teams), docs (Confluence/Notion), PRs/builds/tests (GitHub/CI)
    - Enforce org_id scoping once auth plumbing is in place
    - Add webhook-driven cache invalidation + on-demand refresh
    """


    cache_key = f"context_packet:{org_id}:{task_key}" if use_cache and org_id else None

    async def _build() -> Dict[str, Any]:
        packet = ContextPacket(task_key=task_key)
        try:
            jira_row = (
                db.execute(
                    text(
                        """
                        SELECT ji.issue_key, ji.summary, ji.status, ji.project_key, ji.assignee, ji.reporter,
                               ji.priority, ji.updated, ji.url, ji.description
                        FROM jira_issue ji
                        JOIN jira_connection jc ON jc.id = ji.connection_id
                        WHERE ji.issue_key = :k
                          AND (:org_id IS NULL OR jc.org_id = :org_id)
                        LIMIT 1
                        """
                    ),
                    {"k": task_key, "org_id": org_id},
                )
                .mappings()
                .first()
            )
        except Exception as exc:  # defensive: avoid breaking the agent on query errors
            logger.warning("context_packet.jira_lookup_failed", extra={"task_key": task_key, "error": str(exc)})
            jira_row = None

        if jira_row:
            packet.summary = jira_row.get("summary")
            packet.status = jira_row.get("status")
            packet.jira = dict(jira_row)
            packet.owners.append(
                {
                    "role": "assignee",
                    "name": jira_row.get("assignee"),
                }
            )
            packet.owners.append(
                {
                    "role": "reporter",
                    "name": jira_row.get("reporter"),
                }
            )
            if jira_row.get("url"):
                packet.sources.append(
                    SourceRef(
                        name=f"{jira_row['issue_key']}: {jira_row.get('summary', '')[:60]}",
                        type="jira",
                        connector="jira",
                        url=jira_row["url"],
                        meta={
                            "status": jira_row.get("status"),
                            "project": jira_row.get("project_key"),
                        },
                    )
                )

        if include_related:
            _hydrate_slack_messages(db, packet, org_id, task_key, related_limit)
            _hydrate_github_signals(db, packet, org_id, task_key, related_limit)
            _hydrate_docs(db, packet, org_id, task_key, related_limit)
            _hydrate_ci_signals(db, packet, org_id, task_key, related_limit)

        return packet.to_dict()

    if cache_key:
        cached = await cache_service.cached_fetch(cache_key, _build)
        return _packet_from_dict(cached.value)

    raw = await _build()
    return _packet_from_dict(raw)


def invalidate_context_packet_cache(task_key: str, org_id: Optional[str]) -> None:
    """
    Evict cached context packet for this task/org.
    """
    if not org_id:
        return
    key = f"context_packet:{org_id}:{task_key}"
    logger.info("context_packet.invalidate", extra={"task_key": task_key, "org_id": org_id})
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(cache_service.del_key(key))
    except RuntimeError:
        try:
            asyncio.run(cache_service.del_key(key))
        except Exception:
            logger.warning("context_packet.invalidate_failed", extra={"task_key": task_key, "org_id": org_id})


def _packet_from_dict(data: Dict[str, Any]) -> ContextPacket:
    """Rehydrate ContextPacket from dict (handles SourceRef conversion)."""
    sources_data = data.get("sources") or []
    base = {k: v for k, v in data.items() if k != "sources"}
    packet = ContextPacket(**base)
    packet.sources = [
        SourceRef(
            name=s.get("name"),
            type=s.get("type"),
            url=s.get("url"),
            connector=s.get("connector"),
            meta=s.get("meta") or {},
        )
        for s in sources_data
    ]
    return packet


def _hydrate_slack_messages(
    db: Session,
    packet: ContextPacket,
    org_id: Optional[str],
    task_key: str,
    limit: int,
) -> None:
    """
    Pull recent Slack messages mentioning the task key for this org.
    """
    if not org_id:
        return

    # Pull from dedicated conversation tables for threading
    rows = (
        db.execute(
            text(
                """
                SELECT cm.id, cm.channel, cm.user, cm.message_ts, cm.text
                FROM conversation_message cm
                WHERE cm.org_id = :org_id
                  AND cm.text ILIKE :pattern
                ORDER BY cm.created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "pattern": f"%{task_key}%", "limit": limit},
        )
        .mappings()
        .all()
    )
    for r in rows:
        packet.conversations.append(
            {
                "channel": r["channel"],
                "user": r["user"],
                "ts": r["message_ts"],
                "text": r["text"],
            }
        )
        if r["channel"] and r["message_ts"]:
            packet.sources.append(
                SourceRef(
                    name=f"Slack:{r['channel']}#{r['message_ts']}",
                    type="slack",
                    connector="slack",
                    url=None,
                    meta={"channel": r["channel"], "ts": r["message_ts"]},
            )
            )


def _hydrate_github_signals(
    db: Session,
    packet: ContextPacket,
    org_id: Optional[str],
    task_key: str,
    limit: int,
) -> None:
    """
    Pull recent GitHub statuses/reviews mentioning the task key for this org.
    """
    if not org_id:
        return

    rows = (
        db.execute(
            text(
                """
                SELECT title, text, meta_json, node_type
                FROM memory_node
                WHERE org_id = :org_id
                  AND node_type IN ('github_status', 'github_pr_review')
                  AND text ILIKE :pattern
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "pattern": f"%{task_key}%", "limit": limit},
        )
        .mappings()
        .all()
    )

    for r in rows:
        meta = r["meta_json"] or {}
        entry = {
            "state": meta.get("state") or meta.get("context"),
            "repo": meta.get("repo"),
            "target_url": meta.get("target_url"),
            "text": r["text"],
            "type": r.get("node_type"),
        }
        packet.builds.append(entry)
        packet.sources.append(
            SourceRef(
                name=r.get("title") or (meta.get("repo") or "github"),
                type="github",
                connector="github",
                url=meta.get("target_url") or meta.get("html_url"),
                meta=meta,
            )
        )


def _hydrate_docs(
    db: Session,
    packet: ContextPacket,
    org_id: Optional[str],
    task_key: str,
    limit: int,
) -> None:
    """Pull recent docs/ADRs mentioning the task key for this org."""
    if not org_id:
        return

    rows = (
        db.execute(
            text(
                """
                SELECT title, text, meta_json, node_type
                FROM memory_node
                WHERE org_id = :org_id
                  AND node_type IN ('doc', 'confluence', 'notion', 'adr')
                  AND (text ILIKE :pattern OR title ILIKE :pattern)
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "pattern": f"%{task_key}%", "limit": limit},
        )
        .mappings()
        .all()
    )
    for r in rows:
        meta = r["meta_json"] or {}
        packet.docs.append(
            {
                "title": r.get("title"),
                "excerpt": (r.get("text") or "")[:300],
                "url": meta.get("url"),
                "source": meta.get("source") or r.get("node_type"),
            }
        )
        packet.sources.append(
            SourceRef(
                name=r.get("title") or meta.get("url") or "doc",
                type="doc",
                connector=meta.get("source") or r.get("node_type"),
                url=meta.get("url"),
                meta=meta,
            )
        )


def _hydrate_ci_signals(
    db: Session,
    packet: ContextPacket,
    org_id: Optional[str],
    task_key: str,
    limit: int,
) -> None:
    """Pull recent CI statuses mentioning the task key for this org."""
    if not org_id:
        return

    rows = (
        db.execute(
            text(
                """
                SELECT title, text, meta_json
                FROM memory_node
                WHERE org_id = :org_id
                  AND node_type = 'ci_status'
                  AND text ILIKE :pattern
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "pattern": f"%{task_key}%", "limit": limit},
        )
        .mappings()
        .all()
    )
    for r in rows:
        meta = r["meta_json"] or {}
        packet.builds.append(
            {
                "state": meta.get("status"),
                "job": meta.get("job"),
                "repo": meta.get("repo"),
                "url": meta.get("url"),
                "text": r["text"],
            }
        )
        packet.sources.append(
            SourceRef(
                name=r.get("title") or meta.get("job") or "ci",
                type="ci",
                connector="ci",
                url=meta.get("url"),
                meta=meta,
            )
        )
