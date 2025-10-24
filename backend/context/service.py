"""Context Pack service layer - policy filtering and agent notes"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Union
import json


def parse_tags_field(tags: Union[list, str, None]) -> list:
    """Parse tags field that can be either a list or JSON string.

    Handles cross-database compatibility where PostgreSQL may return
    native lists but SQLite returns JSON strings.

    Args:
        tags: Tags as list, JSON string, or None

    Returns:
        List of tag strings (empty list if None)
    """
    if isinstance(tags, list):
        return tags
    return json.loads(tags or "[]")


def filter_by_policy(
    db: Session, org_id: str, hits: List[Dict[str, Any]], policy: str
) -> List[Dict[str, Any]]:
    """Filter context hits by policy (PR-13 policy engine)

    Args:
        db: Database session
        org_id: Organization ID
        hits: List of context hits
        policy: Policy name to apply

    Returns:
        Filtered context hits
    """
    # TODO: Wire up to PR-13 policy engine when available
    # For now, apply simple filtering based on source
    if policy == "public_only":
        return [h for h in hits if h.get("source") in ("github", "docs")]
    elif policy == "internal_only":
        return [h for h in hits if h.get("source") in ("slack", "jira")]
    return hits


def fetch_relevant_notes(
    db: Session, org_id: str, task_key: str, limit: int = 5
) -> List[Dict[str, Any]]:
    """Fetch relevant agent notes for task context

    Args:
        db: Database session
        org_id: Organization ID
        task_key: Task identifier (e.g., JIRA issue key)
        limit: Maximum number of notes to return

    Returns:
        List of agent notes with metadata
    """
    rows = (
        db.execute(
            text(
                """
      SELECT id, task_key, context, summary, importance, tags,
             created_at, updated_at
      FROM agent_note
      WHERE org_id = :o
        AND (task_key = :tk OR tags ? :tk)
      ORDER BY importance DESC, updated_at DESC
      LIMIT :lim
    """
            ),
            {"o": org_id, "tk": task_key, "lim": limit},
        )
        .mappings()
        .all()
    )

    return [
        {
            "id": r["id"],
            "task_key": r["task_key"],
            "context": r["context"],
            "summary": r["summary"],
            "importance": r["importance"],
            "tags": parse_tags_field(r["tags"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
