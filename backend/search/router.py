"""Search API endpoints - semantic search and reindexing"""

from fastapi import APIRouter, Depends, Body, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db
from .schemas import SearchRequest, SearchResponse
from .retriever import search as do_search
from .indexer import upsert_memory_object
import json
import httpx
import asyncio
import re

router = APIRouter(prefix="/api/search", tags=["search"])


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
      ORDER BY m.created_at DESC LIMIT 1000
    """
            ),
            {"org_id": org},
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
            newest = cur
            count = 0
            for c in chans[:20]:  # throttle MVP to 20 channels
                msgs = await sr.history(client, c["id"], oldest=cur, limit=300)
                for m in msgs:
                    ts = m.get("ts")
                    text_content = m.get("text", "")
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
                    newest = max(newest or ts, ts)
                    count += 1
            if newest:
                if cur is None:
                    db.execute(
                        text(
                            "INSERT INTO sync_cursor (org_id, source, cursor) VALUES (:o,'slack',:c)"
                        ),
                        {"o": org, "c": newest},
                    )
                else:
                    db.execute(
                        text(
                            "UPDATE sync_cursor SET cursor=:c, updated_at=CURRENT_TIMESTAMP WHERE org_id=:o AND source='slack'"
                        ),
                        {"o": org, "c": newest},
                    )
                db.commit()
            return count

    count = asyncio.get_event_loop().run_until_complete(run())
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
            pages = await cr.pages(client, space_key=space_key, start=0, limit=200)
            count = 0
            for p in pages:
                text_html = p["html"]
                text_clean = re.sub(r"<[^>]+>", " ", text_html)[:200000]
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
            return count

    count = asyncio.get_event_loop().run_until_complete(run())
    return {"ok": True, "count": count}


@router.post("/reindex/wiki")
def reindex_wiki(request: Request = None, db: Session = Depends(get_db)):
    """Reindex local wiki/docs markdown files into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")

    from ..integrations_ext.wiki_read import scan_docs

    docs = scan_docs("docs")
    for d in docs:
        upsert_memory_object(
            db, org, "wiki", d["title"], d["title"], d["url"], "en", {}, d["content"]
        )
    return {"ok": True, "count": len(docs)}


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
      ORDER BY m.created_at DESC LIMIT 1000
    """
            ),
            {"org_id": org},
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
            {"provider": "zoom/teams"},
            txt,
        )
    return {"ok": True, "count": len(rows)}
