import re
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ..core.config import settings
from ..core.db import SessionLocal
from ..services.meetings import get_meeting_by_session, finalize_meeting

# Constants for AI processing
MAX_BULLETS = 8
MAX_DECISIONS = 4
MAX_RISKS = 4
MAX_ACTIONS = 5
MAX_TITLE_LENGTH = 80
MAX_SENTENCE_LENGTH = 200
DEFAULT_CONFIDENCE = 0.6

# Keywords for classification
DECISION_KEYWORDS = ["decide", "decision", "agree", "approve"]
RISK_KEYWORDS = ["risk", "blocker", "concern"]
ACTION_KEYWORDS = ["todo", "action", "follow up", "fix", "implement", "add"]

# Broker
broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _normalize(text: str) -> str:
    """Normalize text by cleaning up whitespace and punctuation spacing.

    Args:
        text: Raw text input to normalize

    Returns:
        Cleaned text with normalized whitespace

    Raises:
        ValueError: If text is None or empty
    """
    if not text or not text.strip():
        raise ValueError("Text input cannot be None or empty")

    # simple cleanup: spaces, fix punctuation spacing
    t = re.sub(r"\s+", " ", text).strip()
    return t


def _mock_summarize(chunks: list[str]) -> dict[str, list[str]]:
    """Generate mock summary from text chunks.

    Args:
        chunks: List of normalized text segments

    Returns:
        Dictionary with bullets, decisions, and risks lists

    Raises:
        ValueError: If chunks list is empty
    """
    if not chunks:
        raise ValueError("Cannot summarize empty chunks list")

    # Deterministic, simple heuristic (replace with real LLM later)
    all_text = " ".join(chunks)
    bullets = []
    for sent in re.split(r"(?<=[.!?])\s+", all_text):
        s = sent.strip()
        if s and len(bullets) < MAX_BULLETS:
            bullets.append(s[:MAX_SENTENCE_LENGTH])

    decisions = [b for b in bullets if any(k in b.lower() for k in DECISION_KEYWORDS)]
    risks = [b for b in bullets if any(k in b.lower() for k in RISK_KEYWORDS)]

    return {
        "bullets": bullets[:MAX_BULLETS],
        "decisions": decisions[:MAX_DECISIONS],
        "risks": risks[:MAX_RISKS],
    }


def _mock_actions(chunks: list[str]) -> list[dict[str, str | float | None]]:
    """Extract mock action items from text chunks.

    Args:
        chunks: List of normalized text segments

    Returns:
        List of action item dictionaries with title, assignee, due_hint, confidence, source_segment

    Raises:
        ValueError: If chunks list is empty
    """
    if not chunks:
        raise ValueError("Cannot extract actions from empty chunks list")

    actions = []
    for i, chunk in enumerate(chunks):
        if any(k in chunk.lower() for k in ACTION_KEYWORDS):
            actions.append(
                {
                    "title": chunk[:MAX_TITLE_LENGTH].strip(". "),
                    "assignee": "",
                    "due_hint": "",
                    "confidence": DEFAULT_CONFIDENCE,
                    "source_segment": None,
                }
            )
        if len(actions) >= MAX_ACTIONS:
            break
    return actions


@dramatiq.actor(max_retries=0)
def process_meeting(session_id: str) -> None:
    """Process meeting transcript to generate summary and action items.

    Args:
        session_id: Meeting session identifier

    Raises:
        ValueError: If session_id is invalid
        SQLAlchemyError: If database operation fails
        Exception: For any other processing errors
    """
    if not session_id or not session_id.strip():
        raise ValueError("session_id cannot be None or empty")

    db: Session = SessionLocal()
    try:
        m = get_meeting_by_session(db, session_id)
        if not m:
            print(f"Warning: Meeting not found for session {session_id}")
            return

        # Pull segments with proper error handling
        try:
            rows = db.execute(
                "SELECT text FROM transcript_segment WHERE meeting_id=:mid ORDER BY ts_start_ms NULLS LAST, id",
                {"mid": m.id},
            ).fetchall()
        except SQLAlchemyError as e:
            print(f"Database error retrieving segments for meeting {m.id}: {e}")
            raise

        if not rows:
            print(f"Warning: No transcript segments found for meeting {m.id}")
            return

        try:
            chunks = [
                _normalize(r[0]) for r in rows if r[0]
            ]  # Filter out None/empty text
            if not chunks:
                print(f"Warning: No valid text segments found for meeting {m.id}")
                return

            summary = _mock_summarize(chunks)
            actions = _mock_actions(chunks)

            finalize_meeting(
                db,
                m,
                summary["bullets"],
                summary["decisions"],
                summary["risks"],
                actions,
            )
            print(f"Successfully processed meeting {m.id} with {len(chunks)} segments")

        except ValueError as e:
            print(f"Validation error processing meeting {session_id}: {e}")
            raise
        except Exception as e:
            print(
                f"Unexpected error during AI processing for meeting {session_id}: {e}"
            )
            raise

    except SQLAlchemyError as e:
        print(f"Database error processing meeting {session_id}: {e}")
        # Re-raise to let Dramatiq handle the error
        raise
    except Exception as e:
        print(f"Error processing meeting {session_id}: {e}")
        # Re-raise to let Dramatiq handle the error
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            print(f"Error closing database session: {e}")


if __name__ == "__main__":
    # This allows running the worker directly: python -m backend.workers.queue
    dramatiq.main()
