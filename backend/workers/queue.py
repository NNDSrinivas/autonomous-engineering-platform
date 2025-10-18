import re
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import SessionLocal
from ..services.meetings import get_meeting_by_session, finalize_meeting

# Broker
broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _normalize(text: str) -> str:
    """Normalize text by cleaning up whitespace and punctuation spacing."""
    # simple cleanup: spaces, fix punctuation spacing
    t = re.sub(r"\s+", " ", text).strip()
    return t


def _mock_summarize(chunks: list[str]) -> dict:
    """Generate mock summary from text chunks.

    Args:
        chunks: List of normalized text segments

    Returns:
        Dictionary with bullets, decisions, and risks
    """
    # Deterministic, simple heuristic (replace with real LLM later)
    all_text = " ".join(chunks)
    bullets = []
    for sent in re.split(r"(?<=[.!?])\s+", all_text):
        s = sent.strip()
        if s and len(bullets) < 8:
            bullets.append(s[:200])
    decisions = [
        b
        for b in bullets
        if any(k in b.lower() for k in ["decide", "decision", "agree", "approve"])
    ]
    risks = [b for b in bullets if any(k in b.lower() for k in ["risk", "blocker", "concern"])]
    return {"bullets": bullets[:8], "decisions": decisions[:4], "risks": risks[:4]}


def _mock_actions(chunks: list[str]) -> list[dict]:
    """Extract mock action items from text chunks.

    Args:
        chunks: List of normalized text segments

    Returns:
        List of action item dictionaries
    """
    actions = []
    for i, chunk in enumerate(chunks):
        if any(
            k in chunk.lower() for k in ["todo", "action", "follow up", "fix", "implement", "add"]
        ):
            actions.append(
                {
                    "title": chunk[:80].strip(". "),
                    "assignee": "",
                    "due_hint": "",
                    "confidence": 0.6,
                    "source_segment": None,
                }
            )
        if len(actions) >= 5:
            break
    return actions


@dramatiq.actor(max_retries=0)
def process_meeting(session_id: str):
    """Process meeting transcript to generate summary and action items.

    Args:
        session_id: Meeting session identifier
    """
    db: Session = SessionLocal()
    try:
        m = get_meeting_by_session(db, session_id)
        if not m:
            print(f"Warning: Meeting not found for session {session_id}")
            return

        # Pull segments
        rows = db.execute(
            "SELECT text FROM transcript_segment WHERE meeting_id=:mid ORDER BY ts_start_ms NULLS LAST, id",
            {"mid": m.id},
        ).fetchall()

        if not rows:
            print(f"Warning: No transcript segments found for meeting {m.id}")
            return

        chunks = [_normalize(r[0]) for r in rows]
        summary = _mock_summarize(chunks)
        actions = _mock_actions(chunks)
        finalize_meeting(db, m, summary["bullets"], summary["decisions"], summary["risks"], actions)
        print(f"Successfully processed meeting {m.id} with {len(chunks)} segments")
    except Exception as e:
        print(f"Error processing meeting {session_id}: {e}")
        # Re-raise to let Dramatiq handle the error
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # This allows running the worker directly: python -m backend.workers.queue
    dramatiq.main()
