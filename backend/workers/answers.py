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
# Constants for Dramatiq actor configuration
NO_RETRIES = 0  # No retries for one-shot operations

# Constants for path detection
PROTOCOL_INDICATORS = ["http", "ftp", "://", "www."]  # Strings that indicate URLs rather than file paths

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _recent_meeting_text(db: Session, meeting_id: str) -> list[str]:
    """Get last N transcript segments of a meeting.

    Args:
        db: Database session
        meeting_id: Meeting identifier

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
    # Choose a path-like term if present (avoid URLs and version numbers)
    path_term = None
    if terms:
        for t in terms:
            # Look for file paths: contains '/' but not protocol indicators
            if "/" in t and not any(proto in t.lower() for proto in PROTOCOL_INDICATORS):
                # Additional check: if it contains a file extension
                if "." in t.split("/")[-1]:  # Last segment has extension
                    path_term = t
                    break
                # Or if it looks like a directory path
                elif len(t.split("/")) > 1:
                    path_term = t
                    break
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


@dramatiq.actor(max_retries=NO_RETRIES)
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

        # Calculate latency and save result
        latency_ms = int((time.perf_counter() - t0) * 1000)
        payload["latency_ms"] = latency_ms
        asvc.save_answer(db, session_id, payload)
    except Exception as e:
        # Log error - no retries configured (max_retries=NO_RETRIES)
        logger.exception("Error generating answer for session %s: %s", session_id, e)
    finally:
        db.close()
