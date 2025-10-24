"""Search API endpoints - semantic search and reindexing"""

import asyncio
import json
import logging
import re
from importlib.util import find_spec

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, Body, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.db import get_db
from .constants import (
    MAX_CHANNELS_PER_SYNC,
    SLACK_HISTORY_LIMIT,
    CONFLUENCE_PAGE_LIMIT,
    MAX_CONTENT_LENGTH,
    MAX_MEETINGS_PER_SYNC,
    HTML_OVERHEAD_MULTIPLIER,
)
from .indexer import upsert_memory_object
from .retriever import search as do_search
from .schemas import SearchRequest, SearchResponse

router = APIRouter(prefix="/api/search", tags=["search"])

# Logger for this module
logger = logging.getLogger(__name__)

# Check if lxml parser is available (faster and more robust for malformed HTML)
LXML_AVAILABLE = find_spec("lxml") is not None
if not LXML_AVAILABLE:
    logger.info("lxml parser not available, will use html.parser as fallback")


def validate_slack_timestamp(ts: str | None) -> str | None:
    """Validate a Slack timestamp string.

    Slack timestamps are numeric strings like '1698765432.123'.

    Args:
        ts: Timestamp string to validate, or None

    Returns:
        The validated timestamp string if valid, None if invalid or None input.
    """
    if ts is None:
        return None
    try:
        ts_float = float(ts)
        # Accept timestamps from 0 (1970-01-01) up to 4102444800 (2100-01-01)
        if 0 <= ts_float <= 4102444800:
            return ts
        else:
            logger.debug("Slack timestamp out of bounds: %r", ts)
            return None
    except (TypeError, ValueError):
        logger.debug("Invalid Slack timestamp: %r", ts)
        return None


def safe_update_newest(newest: str | None, ts: str) -> str | None:
    """Safely update and return the newest Slack timestamp string.

    Slack timestamps are numeric strings like '1698765432.123'. This helper
    compares timestamps and returns the most recent one.

    Args:
        newest: Current newest timestamp, or None if no timestamp yet
        ts: New timestamp to compare

    Returns:
        - The most recent valid timestamp (string)
        - newest if ts is invalid
        - ts if newest is invalid or None
        - None if both newest is None and ts is invalid (no valid timestamp yet)
    """
    try:
        ts_float = float(ts)
    except (TypeError, ValueError):
        logger.debug("Invalid Slack timestamp received: %r", ts)
        return newest

    if newest is None:
        return ts

    try:
        newest_float = float(newest)
    except (TypeError, ValueError):
        logger.debug("Existing newest timestamp invalid: %r", newest)
        return ts

    return ts if ts_float > newest_float else newest


@router.post("/", response_model=SearchResponse)
def semantic_search(
    req: SearchRequest = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Semantic search across memory: JIRA, meetings, code"""
    org = request.headers.get("X-Org-Id")
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    return {"hits": do_search(db, org, req.q, k=req.k)}


@router.post("/reindex/jira")
def reindex_jira(request: Request = None, db: Session = Depends(get_db)):
    """Reindex JIRA issues into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    # Note: Query performance relies on index on (org_id, updated) for jira_issue table
    rows = (
        db.execute(
            text(
                "SELECT issue_key, summary, url, status FROM jira_issue WHERE org_id=:org_id ORDER BY updated DESC LIMIT 2000"
            ),
            {"org_id": org},
        )
        .mappings()
        .all()
    )

    for r in rows:
        upsert_memory_object(
            db,
            org,
            "jira",
            r["issue_key"],
            r["summary"] or r["issue_key"],
            r["url"],
            "en",
            {"status": r["status"]},
            r["summary"] or r["issue_key"],
        )

    return {"ok": True, "count": len(rows)}


@router.post("/reindex/meetings")
def reindex_meetings(request: Request = None, db: Session = Depends(get_db)):
    """Reindex meetings and summaries into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    # Note: Query performance relies on index on (org_id, created_at) for meeting table
    rows = (
        db.execute(
            text(
                """
      SELECT m.id mid, coalesce(ms.summary_json,'{}') s
      FROM meeting m
      LEFT JOIN meeting_summary ms ON ms.meeting_id=m.id
      WHERE m.org_id=:org_id
      ORDER BY m.created_at DESC LIMIT :limit
    """
            ),
            # Use MAX_MEETINGS_PER_SYNC constant for consistency across all sync operations
            {"org_id": org, "limit": MAX_MEETINGS_PER_SYNC},
        )
        .mappings()
        .all()
    )

    for r in rows:
        txt = r["s"] if isinstance(r["s"], str) else json.dumps(r["s"])
        upsert_memory_object(
            db,
            org,
            "meeting",
            str(r["mid"]),
            f"Meeting {r['mid']}",
            None,
            "en",
            {},
            txt,
        )

    return {"ok": True, "count": len(rows)}


@router.post("/reindex/code")
def reindex_code(request: Request = None, db: Session = Depends(get_db)):
    """Reindex GitHub code files into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    # Note: Query performance relies on indexes on (org_id) for gh_repo and (repo_id, updated) for gh_file
    rows = (
        db.execute(
            text(
                """
      SELECT r.repo_full_name repo, f.path, f.blob_text
      FROM gh_file f JOIN gh_repo r ON r.id=f.repo_id
      WHERE r.org_id=:org_id
      ORDER BY f.updated DESC LIMIT 5000
    """
            ),
            {"org_id": org},
        )
        .mappings()
        .all()
    )

    for r in rows:
        url = f"https://github.com/{r['repo']}/blob/HEAD/{r['path']}"
        upsert_memory_object(
            db,
            org,
            "code",
            f"{r['repo']}::{r['path']}",
            r["path"],
            url,
            "code",
            {"repo": r["repo"], "path": r["path"]},
            r["blob_text"] or "",
        )

    return {"ok": True, "count": len(rows)}


@router.post("/reindex/slack")
def reindex_slack(request: Request = None, db: Session = Depends(get_db)):
    """Reindex Slack messages into memory (incremental sync)"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")

    row = (
        db.execute(
            text(
                "SELECT bot_token FROM slack_connection WHERE org_id=:o ORDER BY id DESC LIMIT 1"
            ),
            {"o": org},
        )
        .mappings()
        .first()
    )
    if not row:
        return {"ok": False, "reason": "no slack connection"}

    async def run():
        from ..integrations_ext.slack_read import SlackReader

        async with httpx.AsyncClient(timeout=30) as client:
            sr = SlackReader(row["bot_token"])
            chans = await sr.list_channels(client)
            # incremental cursor
            cur = db.execute(
                text(
                    "SELECT cursor FROM sync_cursor WHERE org_id=:o AND source='slack'"
                ),
                {"o": org},
            ).scalar()
            # Log warning and proceed with full sync if cursor is invalid (recoverable from manual edits).
            newest = None
            newest = validate_slack_timestamp(cur)
            if newest is None and cur is not None:
                logger.warning(
                    "Invalid cursor value for org_id=%s: %r, ignoring invalid cursor and re-syncing from scratch",
                    org,
                    cur,
                )
            # Log if channels are being truncated to help operators understand sync limits
            if len(chans) > MAX_CHANNELS_PER_SYNC:
                logger.info(
                    "Truncating %d channels to limit of %d for org_id=%s",
                    len(chans),
                    MAX_CHANNELS_PER_SYNC,
                    org,
                )
            # Count of successfully indexed messages (reset per sync run)
            count = 0
            for c in chans[:MAX_CHANNELS_PER_SYNC]:
                msgs = await sr.history(
                    client, c["id"], oldest=newest, limit=SLACK_HISTORY_LIMIT
                )
                for m in msgs:
                    try:
                        ts = m.get("ts")
                        text_content = m.get("text", "")
                        if not ts:
                            raise ValueError("missing timestamp in Slack message")
                        title = f"#{c['name']} {ts}"
                        upsert_memory_object(
                            db,
                            org,
                            "slack",
                            f"{c['id']}::{ts}",
                            title,
                            None,
                            "en",
                            {"channel": c["name"]},
                            text_content,
                        )
                        # Update newest timestamp INSIDE try block to track successful upserts.
                        # This ensures cursor advances only for successfully indexed messages,
                        # preventing re-processing of already-indexed messages on next sync.
                        newest = safe_update_newest(newest, ts)
                        count += 1
                    except Exception as e:
                        logger.error(
                            "Failed to upsert Slack message (channel_id=%r, ts=%r, org_id=%r): %s",
                            c.get("id"),
                            m.get("ts"),
                            org,
                            e,
                        )
                        continue
            # Only update cursor if we have a valid timestamp.
            # Note: newest will be None only if no messages with valid timestamps were processed.
            if newest:
                # Use ON CONFLICT to handle race conditions in concurrent environments
                db.execute(
                    text(
                        """
                        INSERT INTO sync_cursor (org_id, source, cursor) 
                        VALUES (:o, 'slack', :c)
                        ON CONFLICT (org_id, source) 
                        DO UPDATE SET cursor = EXCLUDED.cursor, updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    {"o": org, "c": newest},
                )
                db.commit()
            return count

    count = asyncio.run(run())
    return {"ok": True, "count": count}


@router.post("/reindex/confluence")
def reindex_confluence(
    space_key: str = Body(..., embed=True),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Reindex Confluence pages into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")

    row = (
        db.execute(
            text(
                "SELECT base_url, access_token, email FROM confluence_connection WHERE org_id=:o ORDER BY id DESC LIMIT 1"
            ),
            {"o": org},
        )
        .mappings()
        .first()
    )
    if not row:
        return {"ok": False, "reason": "no confluence connection"}

    async def run():
        from ..integrations_ext.confluence_read import ConfluenceReader

        async with httpx.AsyncClient(timeout=30) as client:
            cr = ConfluenceReader(row["base_url"], row["access_token"], row["email"])
            pages = await cr.pages(
                client, space_key=space_key, start=0, limit=CONFLUENCE_PAGE_LIMIT
            )
            count = 0
            for p in pages:
                text_html = p["html"]
                # Truncate raw HTML before parsing for performance (avoid memory/CPU issues with large pages).
                # Apply overhead multiplier to ensure enough HTML is captured to extract target text length.
                # See HTML_OVERHEAD_MULTIPLIER in constants.py for detailed rationale.
                max_html_length = MAX_CONTENT_LENGTH * HTML_OVERHEAD_MULTIPLIER
                # Use 'lxml' parser if available (faster and more robust with malformed HTML),
                # otherwise use 'html.parser' built-in. This is especially important when truncating
                # mid-tag, as lxml handles incomplete markup more gracefully.
                parser = "lxml" if LXML_AVAILABLE else "html.parser"
                soup = BeautifulSoup(
                    text_html[:max_html_length],
                    parser,
                )
                # Remove script and style tags completely (including malformed ones)
                for tag in soup(["script", "style"]):
                    tag.decompose()
                # Extract text and normalize whitespace, then truncate to max length
                text_clean = soup.get_text(separator=" ")
                text_clean = re.sub(r"\s+", " ", text_clean).strip()[
                    :MAX_CONTENT_LENGTH
                ]
                try:
                    upsert_memory_object(
                        db,
                        org,
                        "confluence",
                        p["id"],
                        p["title"],
                        p["url"],
                        "en",
                        {"version": p["version"]},
                        text_clean,
                    )
                    count += 1
                except Exception as e:
                    logger.error(
                        "Failed to index Confluence page id=%r title=%r: %s",
                        p.get("id"),
                        p.get("title"),
                        e,
                    )
            return count

    count = asyncio.run(run())
    return {"ok": True, "count": count}


@router.post("/reindex/wiki")
def reindex_wiki(request: Request = None, db: Session = Depends(get_db)):
    """Reindex local wiki/docs markdown files into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")

    from ..integrations_ext.wiki_read import scan_docs

    docs = scan_docs("docs")
    failed = []
    for d in docs:
        try:
            upsert_memory_object(
                db,
                org,
                "wiki",
                d["title"],
                d["title"],
                d["url"],
                "en",
                {},
                d["content"],
            )
        except Exception as e:
            logger.error("Failed to index wiki document '%s': %s", d["title"], e)
            failed.append(d["title"])
    return {"ok": True, "count": len(docs), "failed": failed}


@router.post("/reindex/zoom_teams")
def reindex_zoom_teams(request: Request = None, db: Session = Depends(get_db)):
    """Reindex Zoom/Teams meeting transcripts into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")

    # Note: Query performance relies on index on (provider, created_at) for meeting table
    rows = (
        db.execute(
            text(
                """
      SELECT m.id mid, coalesce(ms.summary_json,'{}') s
      FROM meeting m LEFT JOIN meeting_summary ms ON ms.meeting_id=m.id
      WHERE m.provider IN ('zoom','teams') AND m.org_id=:org_id
      ORDER BY m.created_at DESC LIMIT :limit
    """
            ),
            # Use MAX_MEETINGS_PER_SYNC constant for consistency across all sync operations
            {"org_id": org, "limit": MAX_MEETINGS_PER_SYNC},
        )
        .mappings()
        .all()
    )
    for r in rows:
        txt = r["s"] if isinstance(r["s"], str) else json.dumps(r["s"])
        try:
            upsert_memory_object(
                db,
                org,
                "meeting",
                str(r["mid"]),
                f"Meeting {r['mid']}",
                None,
                "en",
                {"provider": "zoom/teams"},
                txt,
            )
        except Exception as e:
            logger.error("Failed to index meeting ID %s: %s", r["mid"], e)
    return {"ok": True, "count": len(rows)}
