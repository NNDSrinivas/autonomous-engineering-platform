import logging
import re
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

# Pattern for matching version numbers like "v1.2.3" or "1.2.3"
VERSION_PATTERN = re.compile(r"^v?\d+(\.\d+)*$")


def _is_version_number(segment: str) -> bool:
    """Check if a string matches a version number pattern.
    
    Args:
        segment: String segment to check
        
    Returns:
        True if segment matches version pattern like 'v1.2.3' or '1.2.3'
    """
    return bool(VERSION_PATTERN.match(segment))

# Constants for path detection
PROTOCOL_INDICATORS = [
    "http",
    "ftp",
    "://",
    "www.",
]  # Strings that indicate URLs rather than file paths

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _recent_meeting_text(db: Session, meeting_id_param: str) -> list[str]:
    """Get last N transcript segments of a meeting.

    Args:
        db: Database session
        meeting_id_param: Meeting identifier

    Returns:
        List of transcript text segments in chronological order
    """
    # Use SQLAlchemy ORM for better type safety and maintainability
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id_param)
        .order_by(
            TranscriptSegment.ts_end_ms.desc().nulls_last(), TranscriptSegment.id.desc()
        )
        .limit(MAX_TRANSCRIPT_SEGMENTS)
        .all()
    )
    return [
        seg.text for seg in reversed(segments)
    ]  # reverse to chronological order (oldest first)


def _terms_from_latest(db: Session, meeting_id_param: str) -> list[str]:
    """Extract search terms from the most recent transcript segment.

    Args:
        db: Database session
        meeting_id_param: Meeting identifier

    Returns:
        List of extracted keyword terms
    """
    # Use SQLAlchemy ORM for better type safety and maintainability
    segment = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.meeting_id == meeting_id_param)
        .order_by(
            TranscriptSegment.ts_end_ms.desc().nulls_last(), TranscriptSegment.id.desc()
        )
        .first()
    )
    if not segment or not segment.text:
        return []
    return asvc.extract_terms(segment.text)


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


def _extract_path_term(terms: list[str]) -> str | None:
    """Extract a path-like term from the list, avoiding URLs and version numbers.

    Args:
        terms: List of search terms

    Returns:
        First valid path-like term found, or None if no valid paths
    """
    if not terms:
        return None

    # Common file extensions to validate against
    VALID_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".html",
        ".css",
        ".scss",
        ".sass",
        ".vue",
        ".svelte",
        ".md",
        ".txt",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".sh",
        ".bat",
        ".ps1",
        ".sql",
        ".dockerfile",
        ".tf",
    }

    for t in terms:
        # Look for file paths: contains '/' but not protocol indicators
        if "/" in t and not any(proto in t.lower() for proto in PROTOCOL_INDICATORS):
            last_segment = t.split("/")[-1]

            # Check if last segment has a valid file extension
            if "." in last_segment:
                extension = "." + last_segment.split(".")[-1].lower()
                if extension in VALID_EXTENSIONS:
                    return t
                # Avoid version numbers like "1.2.3" or "v1.2.3"
                if _is_version_number(last_segment):
                    continue

            # Or if it looks like a directory path (multiple segments, no obvious version pattern)
            elif len(t.split("/")) > 1 and not any(
                _is_version_number(segment) for segment in t.split("/")
            ):
                return t
    return None


def _search_code(db: Session, terms: list[str]) -> list[dict]:
    """Search code repositories for relevant information."""

    if not terms:
        return []

    # Try to find a path-like term
    path_term = _extract_path_term(terms)

    # Use path if found, otherwise use first term
    search_term = path_term if path_term else terms[0]

    try:
        results = GitHubService.search_code(db, repo=None, q=search_term, path_prefix=None)
        return results
    except Exception:
        logger.exception("Error searching code in GitHubService")
        return []


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
