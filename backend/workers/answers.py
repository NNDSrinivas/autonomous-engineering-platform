import logging
import time
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.db import SessionLocal
from ..models.meetings import TranscriptSegment
from ..services import answers as asvc
from ..services import meetings as msvc
from ..services.jira import JiraService
from ..services.github import GitHubService

logger = logging.getLogger(__name__)

# Constants for search term extraction
MAX_SEARCH_TERMS = 4  # Maximum number of terms to use in searches

# Constants for transcript retrieval
MAX_TRANSCRIPT_SEGMENTS = 20  # Maximum number of recent transcript segments to fetch
DEFAULT_MEETING_WINDOW_SECONDS = 180  # Default time window for meeting transcripts

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _recent_meeting_text(
    db: Session, meeting_id: str, window_seconds: int = DEFAULT_MEETING_WINDOW_SECONDS
) -> list[str]:
    """Get last N seconds of meeting transcript text.

    Args:
        db: Database session
        meeting_id: Meeting identifier
        window_seconds: Time window in seconds (currently unused, fallback to last N segments)

    Returns:
        List of transcript text segments in chronological order
    """
    # Use SQLAlchemy ORM for better type safety and maintainability
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(
            TranscriptSegment.ts_end_ms.desc().nulls_last(), TranscriptSegment.id.desc()
        )
        .limit(MAX_TRANSCRIPT_SEGMENTS)
        .all()
    )
    return [
        seg.text for seg in reversed(segments)
    ]  # reverse to chronological order (oldest first)


def _terms_from_latest(db: Session, meeting_id: str) -> list[str]:
    """Extract search terms from the most recent transcript segment.

    Args:
        db: Database session
        meeting_id: Meeting identifier

    Returns:
        List of extracted keyword terms
    """
    # Use SQLAlchemy ORM for better type safety and maintainability
    segment = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id)
        .order_by(
            TranscriptSegment.ts_end_ms.desc().nulls_last(), TranscriptSegment.id.desc()
        )
        .first()
    )
    latest = segment.text if segment else ""
    return asvc.extract_terms(latest)


def _build_search_query(terms: list[str]) -> str | None:
    """Build search query string from terms.

    Args:
        terms: List of search terms

    Returns:
        Space-joined string of up to MAX_SEARCH_TERMS, or None if no terms
    """
    return " ".join(terms[:MAX_SEARCH_TERMS]) if terms else None


def _search_jira(db: Session, terms: list[str]) -> list[dict]:
    """Search JIRA issues using extracted terms.

    Args:
        db: Database session
        terms: List of search terms

    Returns:
        List of matching JIRA issues
    """
    q = _build_search_query(terms)
    return JiraService.search_issues(db, project=None, q=q, updated_since=None)


def _search_code(db: Session, terms: list[str]) -> list[dict]:
    """Search GitHub code using extracted terms.

    Args:
        db: Database session
        terms: List of search terms

    Returns:
        List of matching code files
    """
    q = _build_search_query(terms)
    # choose a path-like term if present
    path_term = (
        next((t for t in terms if "/" in t or "." in t), None) if terms else None
    )
    return GitHubService.search_code(db, repo=None, q=q, path_prefix=path_term)


def _search_prs(db: Session, terms: list[str]) -> list[dict]:
    """Search GitHub pull requests using extracted terms.

    Args:
        db: Database session
        terms: List of search terms

    Returns:
        List of matching pull requests
    """
    q = _build_search_query(terms)
    return GitHubService.search_issues(db, repo=None, q=q, updated_since=None)


@dramatiq.actor(max_retries=0)
def generate_answer(session_id: str) -> None:
    """Generate grounded answer for a session using JIRA and GitHub context.

    Args:
        session_id: Session identifier to generate answer for
    """
    t0 = time.perf_counter()
    db: Session = SessionLocal()
    try:
        m = msvc.get_meeting_by_session(db, session_id)
        if not m:
            return

        meeting_snips = _recent_meeting_text(db, m.id)
        terms = _terms_from_latest(db, m.id)

        jira_hits = _search_jira(db, terms)
        code_hits = _search_code(db, terms)
        pr_hits = _search_prs(db, terms)

        payload = asvc.generate_grounded_answer(
            jira_hits, code_hits, pr_hits, meeting_snips
        )
        payload["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        asvc.save_answer(db, session_id, payload)
    except Exception as e:
        # Log but don't raise - Dramatiq will handle retries
        logger.error(
            "Error generating answer for session %s: %s", session_id, e, exc_info=True
        )
    finally:
        db.close()
