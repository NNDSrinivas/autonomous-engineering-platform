import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.answers import SessionAnswer

# Constants for answer generation
MAX_CONTEXT_LENGTH = 600  # Maximum characters of meeting context to use
MAX_FALLBACK_LENGTH = 140  # Maximum characters for fallback answer from meeting
MAX_ANSWER_LENGTH = 280  # Maximum length of generated answer
MIN_SENTENCE_LENGTH = 2  # Minimum character length for meaningful sentences

# Constants for answer retrieval
MAX_RECENT_ANSWERS = 20  # Maximum number of recent answers to retrieve


def _id() -> str:
    """Generate a unique identifier for an answer.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def extract_terms(latest_text: str) -> list[str]:
    """Ultra-light keyword extractor: split, dedupe, keep useful tokens.

    Args:
        latest_text: Text to extract keywords from

    Returns:
        List of up to 8 unique keywords, excluding common stopwords
    """
    words = re.findall(r"[A-Za-z0-9_-]{3,}", latest_text or "")
    uniq = []
    stopwords = {
        "the",
        "and",
        "this",
        "that",
        "with",
        "have",
        "what",
        "when",
        "where",
        "how",
    }
    for w in words:
        wl = w.lower()
        if wl not in uniq and wl not in stopwords:
            uniq.append(wl)
    return uniq[:8]


def _pick_best(items: list[dict], n: int) -> list[dict]:
    """Select top N items from a list.

    Args:
        items: List of items to select from
        n: Number of items to select

    Returns:
        First N items or empty list if items is None
    """
    return items[:n] if items else []


def generate_grounded_answer(
    jira_hits: list[dict],
    code_hits: list[dict],
    pr_hits: list[dict],
    meeting_snippets: list[str],
) -> dict:
    """Generate a grounded answer with citations from JIRA, GitHub, and meeting context.

    Priority order: JIRA issues → GitHub code → Pull requests → Meeting context → Fallback

    Args:
        jira_hits: List of matching JIRA issues
        code_hits: List of matching GitHub code files
        pr_hits: List of matching GitHub pull requests
        meeting_snippets: Recent transcript text segments

    Returns:
        Dictionary with answer text, citations, confidence score, token count, and latency_ms placeholder
    """
    text_context = " ".join(meeting_snippets)[-MAX_CONTEXT_LENGTH:]
    answer = ""
    citations = []

    if jira_hits:
        j = jira_hits[0]
        answer = f"Latest on {j.get('issue_key')}: {j.get('summary') or 'see ticket'} (status: {j.get('status')})."
        citations.append(
            {"type": "jira", "key": j.get("issue_key"), "url": j.get("url")}
        )
    elif code_hits:
        c = code_hits[0]
        answer = f"Relevant code is at {c.get('repo')}/{c.get('path')}."
        citations.append({"type": "code", "repo": c.get("repo"), "path": c.get("path")})
    elif pr_hits:
        p = pr_hits[0]
        answer = f"Related PR: {p.get('title')} (#{p.get('number')}, {p.get('state')})."
        citations.append({"type": "pr", "number": p.get("number"), "url": p.get("url")})
    elif text_context:
        # fallback from meeting context only
        if "." in text_context:
            # Extract last two sentences, filter out empty/trivial ones
            sentences = [
                stripped
                for sent in text_context.split(".")
                if (stripped := sent.strip()) and len(stripped) > MIN_SENTENCE_LENGTH
            ]
            s = sentences[-2:] if sentences else []
        else:
            s = []
        if not s:
            s = [text_context[:MAX_FALLBACK_LENGTH]]
        answer = " ".join(s).strip()
        citations.append({"type": "meeting"})
    else:
        answer = "I don't have enough context yet."

    return {
        "answer": answer[:MAX_ANSWER_LENGTH],
        "citations": citations,
        "confidence": 0.6,
        "token_count": len(answer.split()),
        "latency_ms": 0,
    }


def save_answer(db: Session, session_id: str, payload: dict) -> SessionAnswer:
    """Save a generated answer to the database.

    Args:
        db: Database session
        session_id: Session identifier
        payload: Answer data including text, citations, and metrics

    Returns:
        Created SessionAnswer instance
    """
    row = SessionAnswer(
        id=_id(),
        session_id=session_id,
        created_at=datetime.now(timezone.utc),
        answer=payload["answer"],
        citations=payload.get("citations", []),
        confidence=payload.get("confidence"),
        token_count=payload.get("token_count"),
        latency_ms=payload.get("latency_ms"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recent_answers(
    db: Session, session_id: str, since_ts: str | None = None
) -> list[dict]:
    """Retrieve recent answers for a session.

    Args:
        db: Database session
        session_id: Session identifier
        since_ts: Optional ISO timestamp to filter answers after this time

    Returns:
        List of answer dictionaries with id, created_at, answer, citations, confidence
    """
    query = db.query(
        SessionAnswer.id,
        SessionAnswer.created_at,
        SessionAnswer.answer,
        SessionAnswer.citations,
        SessionAnswer.confidence,
    ).filter(SessionAnswer.session_id == session_id)
    if since_ts:
        # Parse since_ts string to a timezone-aware datetime object
        if isinstance(since_ts, str):
            try:
                dt = datetime.fromisoformat(since_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                since_ts_dt = dt
            except ValueError:
                raise ValueError(f"Invalid ISO timestamp for since_ts: {since_ts}")
        else:
            since_ts_dt = since_ts
        query = query.filter(SessionAnswer.created_at > since_ts_dt)
    query = query.order_by(SessionAnswer.created_at.desc()).limit(MAX_RECENT_ANSWERS)
    rows = query.all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "answer": r.answer,
            "citations": r.citations,
            "confidence": r.confidence,
        }
        for r in rows
    ]
