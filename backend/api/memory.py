"""Memory API endpoints

Provides episodic memory recording and agent note consolidation
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import List, Optional
import json
from ..core.db import get_db
from ..context.schemas import AgentNoteOut
from ..context.service import parse_tags_field

router = APIRouter(prefix="/memory", tags=["memory"])


# Request/Response schemas
class SessionEventRequest(BaseModel):
    """Record episodic memory event"""

    session_id: str = Field(..., description="IDE/agent session identifier")
    event_type: str = Field(..., description="Event type: plan, decision, error, qa, exec, meeting")
    task_key: Optional[str] = Field(None, description="Associated task key")
    context: str = Field(..., description="Event context/details")
    metadata: Optional[dict] = Field(default_factory=dict)


class ConsolidateRequest(BaseModel):
    """Consolidate session events into agent notes"""

    session_id: str = Field(..., description="Session ID to consolidate")
    task_key: str = Field(..., description="Task key for note")
    summary: str = Field(..., description="Consolidated summary")
    importance: int = Field(5, ge=1, le=10, description="Importance score 1-10")
    tags: List[str] = Field(default_factory=list)


@router.post("/event")
def record_event(req: SessionEventRequest, db: Session = Depends(get_db)):
    """Record episodic memory event

    Stores short-term events like plans, decisions, errors, QA exchanges.
    Events are later consolidated into long-term agent notes.
    """
    # TODO: SECURITY - Hardcoded org_id bypasses tenant isolation
    # This is MVP code - in production, extract org_id from authenticated user context
    # to prevent unauthorized access/modification of other organizations' data
    org_id = "default_org"

    db.execute(
        text(
            """
      INSERT INTO session_event (org_id, session_id, event_type, task_key, context, metadata)
      VALUES (:o, :sid, :et, :tk, :ctx, :meta)
    """
        ),
        {
            "o": org_id,
            "sid": req.session_id,
            "et": req.event_type,
            "tk": req.task_key,
            "ctx": req.context,
            "meta": json.dumps(req.metadata),
        },
    )
    db.commit()

    return {"status": "recorded", "session_id": req.session_id}


@router.post("/consolidate", response_model=AgentNoteOut)
def consolidate_memory(req: ConsolidateRequest, db: Session = Depends(get_db)):
    """Consolidate session events into agent note

    Takes ephemeral session events and creates a persistent, searchable note.
    Used for long-term memory and context retrieval.
    """
    # TODO: SECURITY - Hardcoded org_id bypasses tenant isolation
    # This is MVP code - in production, extract org_id from authenticated user context
    # to prevent unauthorized access/modification of other organizations' data
    org_id = "default_org"

    # Fetch session events for context
    events = (
        db.execute(
            text(
                """
      SELECT event_type, context, created_at
      FROM session_event
      WHERE org_id = :o AND session_id = :sid
      ORDER BY created_at ASC
    """
            ),
            {"o": org_id, "sid": req.session_id},
        )
        .mappings()
        .all()
    )

    if not events:
        raise HTTPException(status_code=404, detail="No events found for session")

    # Build consolidated context
    ctx_parts = [f"[{e['event_type']}] {e['context']}" for e in events]
    full_context = "\n\n".join(ctx_parts)

    # Insert agent note
    result = db.execute(
        text(
            """
      INSERT INTO agent_note (org_id, task_key, context, summary, importance, tags)
      VALUES (:o, :tk, :ctx, :sum, :imp, :tags)
      RETURNING id, task_key, context, summary, importance, tags, created_at, updated_at
    """
        ),
        {
            "o": org_id,
            "tk": req.task_key,
            "ctx": full_context,
            "sum": req.summary,
            "imp": req.importance,
            "tags": json.dumps(req.tags),
        },
    )
    db.commit()

    note = result.mappings().one()
    return AgentNoteOut(
        id=note["id"],
        task_key=note["task_key"],
        context=note["context"],
        summary=note["summary"],
        importance=note["importance"],
        tags=parse_tags_field(note["tags"]),
        created_at=note["created_at"].isoformat() if note["created_at"] else None,
        updated_at=note["updated_at"].isoformat() if note["updated_at"] else None,
    )


@router.get("/notes/{task_key}", response_model=List[AgentNoteOut])
def get_notes(task_key: str, db: Session = Depends(get_db)):
    """Fetch agent notes for task"""
    # TODO: SECURITY - Hardcoded org_id bypasses tenant isolation
    # This is MVP code - in production, extract org_id from authenticated user context
    # to prevent unauthorized access to other organizations' data
    org_id = "default_org"

    rows = (
        db.execute(
            text(
                """
      SELECT id, task_key, context, summary, importance, tags, created_at, updated_at
      FROM agent_note
      WHERE org_id = :o AND task_key = :tk
      ORDER BY importance DESC, updated_at DESC
    """
            ),
            {"o": org_id, "tk": task_key},
        )
        .mappings()
        .all()
    )

    return [
        AgentNoteOut(
            id=r["id"],
            task_key=r["task_key"],
            context=r["context"],
            summary=r["summary"],
            importance=r["importance"],
            tags=parse_tags_field(r["tags"]),
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
        )
        for r in rows
    ]
