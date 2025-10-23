"""Search API endpoints - semantic search and reindexing"""

from fastapi import APIRouter, Depends, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db
from .schemas import SearchRequest, SearchResponse
from .retriever import search as do_search
from .indexer import upsert_memory_object
import json

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
            r["summary"] or "",
        )

    return {"ok": True, "count": len(rows)}


@router.post("/reindex/meetings")
def reindex_meetings(request: Request = None, db: Session = Depends(get_db)):
    """Reindex meetings and summaries into memory"""
    org = request.headers.get("X-Org-Id")
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="X-Org-Id header required")
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
