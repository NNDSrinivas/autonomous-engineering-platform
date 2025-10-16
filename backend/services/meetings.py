import uuid
import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from ..models.meetings import Meeting, TranscriptSegment, MeetingSummary, ActionItem
from . import tasks as tasksvc


def new_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def create_meeting(
    db: Session, title: str | None, provider: str | None, org_id: str | None
) -> Meeting:
    """Create a new meeting and persist it to the database.

    Args:
        db: Database session
        title: Optional meeting title
        provider: Meeting provider (zoom, teams, meet, manual)
        org_id: Optional organization ID

    Returns:
        Created Meeting instance
    """
    m = Meeting(
        id=new_uuid(),
        session_id=new_uuid(),
        title=title,
        provider=provider,
        started_at=dt.dt.datetime.now(dt.timezone.utc),
        org_id=org_id,
        participants=[],
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def get_meeting_by_session(db: Session, session_id: str) -> Meeting | None:
    """Retrieve a meeting by its session ID.

    Args:
        db: Database session
        session_id: Unique session identifier

    Returns:
        Meeting instance if found, None otherwise
    """
    return db.scalar(select(Meeting).where(Meeting.session_id == session_id))


def append_segment(
    db: Session,
    meeting_id: str,
    text_content: str,
    speaker: str | None,
    ts_start_ms: int | None,
    ts_end_ms: int | None,
) -> TranscriptSegment:
    """Add a transcript segment to a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID to add segment to
        text_content: Transcript text
        speaker: Optional speaker name
        ts_start_ms: Optional start timestamp in milliseconds
        ts_end_ms: Optional end timestamp in milliseconds

    Returns:
        Created TranscriptSegment instance
    """
    seg = TranscriptSegment(
        id=new_uuid(),
        meeting_id=meeting_id,
        text=text_content,
        speaker=speaker,
        ts_start_ms=ts_start_ms,
        ts_end_ms=ts_end_ms,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def finalize_meeting(
    db: Session,
    meeting: Meeting,
    bullets: list[str],
    decisions: list[str],
    risks: list[str],
    actions: list[dict],
) -> None:
    """Finalize a meeting by saving summary and action items.

    Args:
        db: Database session
        meeting: Meeting to finalize
        bullets: Summary bullets
        decisions: Key decisions made
        risks: Identified risks
        actions: Extracted action items
    """
    # upsert summary
    existing = db.get(MeetingSummary, meeting.id)
    if not existing:
        existing = MeetingSummary(
            meeting_id=meeting.id, bullets=bullets, decisions=decisions, risks=risks
        )
        db.add(existing)
    else:
        existing.bullets, existing.decisions, existing.risks = bullets, decisions, risks
    # clear old actions
    db.execute(
        text("DELETE FROM action_item WHERE meeting_id=:mid"), {"mid": meeting.id}
    )
    # insert new actions
    for a in actions:
        db.add(
            ActionItem(
                id=new_uuid(),
                meeting_id=meeting.id,
                title=a.get("title", "").strip(),
                assignee=a.get("assignee") or None,
                due_hint=a.get("due_hint") or None,
                confidence=float(a.get("confidence", 0.5)),
                source_segment=a.get("source_segment") or None,
            )
        )
    meeting.ended_at = dt.dt.datetime.now(dt.timezone.utc)
    db.commit()
    tasksvc.ensure_tasks_for_actions(db, meeting.id)


def get_summary(db: Session, session_id: str) -> dict | None:
    m = get_meeting_by_session(db, session_id)
    if not m:
        return None
    s = db.get(MeetingSummary, m.id)
    if not s:
        return None
    actions = (
        db.execute(select(ActionItem).where(ActionItem.meeting_id == m.id))
        .scalars()
        .all()
    )
    return {
        "meeting_id": m.id,
        "session_id": m.session_id,
        "title": m.title,
        "summary": {
            "bullets": s.bullets or [],
            "decisions": s.decisions or [],
            "risks": s.risks or [],
        },
        "actions": [
            {
                "id": a.id,
                "title": a.title,
                "assignee": a.assignee,
                "due_hint": a.due_hint,
                "confidence": a.confidence,
                "source_segment": a.source_segment,
            }
            for a in actions
        ],
    }


def list_actions(db: Session, session_id: str) -> list[dict]:
    m = get_meeting_by_session(db, session_id)
    if not m:
        return []
    actions = (
        db.execute(select(ActionItem).where(ActionItem.meeting_id == m.id))
        .scalars()
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "assignee": a.assignee,
            "due_hint": a.due_hint,
            "confidence": a.confidence,
            "source_segment": a.source_segment,
        }
        for a in actions
    ]


def search_meetings(
    db: Session, q: str | None, since: str | None, people: str | None
) -> list[dict]:
    # simple hybrid: text ILIKE on segments or title; since filter on started_at
    clauses = []
    params = {}
    if q:
        clauses.append("(m.title ILIKE :q OR ts.text ILIKE :q)")
        params["q"] = f"%{q}%"
    if since:
        clauses.append("m.started_at >= :since")
        params["since"] = since
    sql = f"""
        SELECT m.id, m.session_id, m.title, min(ts.ts_start_ms) AS first_ts, count(ts.id) AS segs
        FROM meeting m
        LEFT JOIN transcript_segment ts ON ts.meeting_id = m.id
        {"WHERE " + " AND ".join(clauses) if clauses else ""}
        GROUP BY m.id, m.session_id, m.title
        ORDER BY m.started_at DESC NULLS LAST
        LIMIT 50
    """
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
