import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from ..models.answers import SessionAnswer

# Constants for answer generation
MAX_CONTEXT_LENGTH = 600  # Maximum characters of meeting context to use
MAX_FALLBACK_LENGTH = 140  # Maximum characters for fallback answer from meeting
MAX_ANSWER_LENGTH = 280  # Maximum length of generated answer
MIN_SENTENCE_LENGTH = 2  # Minimum character length for meaningful sentences
MAX_EXTRACTED_TERMS = 8  # Maximum number of terms to extract from text

# Constants for answer retrieval
MAX_RECENT_ANSWERS = 20  # Maximum number of recent answers to retrieve

# Constants for answer metadata
DEFAULT_CONFIDENCE = 0.6  # Default confidence score for generated answers
DEFAULT_LATENCY_MS = 0  # Default latency for immediate responses

# Regex pattern for extracting words/tokens of 3+ characters (alphanumeric, underscores, hyphens)
KEYWORD_EXTRACTION_PATTERN = r"[A-Za-z0-9_-]{3,}"

# Common stopwords to exclude from keyword extraction
STOPWORDS = {
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

# Common abbreviations that shouldn't trigger sentence breaks
COMMON_ABBREVIATIONS = {
    "Dr",
    "Mr",
    "Mrs",
    "Ms",
    "Prof",
    "Inc",
    "Ltd",
    "Corp",
    "vs",
    "etc",
    "ie",  # Both with and without periods for robust matching
    "eg",
}


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime object.

    Handles various ISO 8601 formats including 'Z' suffix for UTC timezone
    which datetime.fromisoformat() doesn't support natively.

    Used for parsing timestamps from API query parameters.

    Args:
        timestamp_str: ISO 8601 timestamp string (e.g., '2023-10-14T12:30:45Z')

    Returns:
        Timezone-aware datetime object

    Raises:
        ValueError: If the timestamp string is not a valid ISO 8601 format
    """
    try:
        # Handle 'Z' suffix for UTC timezone which fromisoformat doesn't support
        ts_normalized = (
            timestamp_str.replace("Z", "+00:00")
            if timestamp_str.endswith("Z")
            else timestamp_str
        )
        dt = datetime.fromisoformat(ts_normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as e:
        raise ValueError(f"Invalid ISO timestamp '{timestamp_str}': {e}") from e


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
        List of up to MAX_EXTRACTED_TERMS unique keywords, excluding common stopwords
    """
    words = re.findall(KEYWORD_EXTRACTION_PATTERN, latest_text or "")
    uniq = []
    for w in words:
        wl = w.lower()
        if wl not in uniq and wl not in STOPWORDS:
            uniq.append(wl)
    return uniq[:MAX_EXTRACTED_TERMS]


def _pick_best(items: list[Dict[str, Any]], n: int) -> list[Dict[str, Any]]:
    """Select top N items from a list.

    Args:
        items: List of items to select from
        n: Number of items to select

    Returns:
        First N items or empty list if items is None
    """
    return items[:n] if items else []


def _generate_jira_answer(jira_hit: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Generate answer from JIRA issue.

    Args:
        jira_hit: JIRA issue data

    Returns:
        Tuple of (answer_text, citation)
    """
    status = jira_hit.get("status")
    issue_key = jira_hit.get("issue_key")
    summary = jira_hit.get("summary") or "see ticket"
    answer = f"Latest on {issue_key}: {summary} (status: {status})."
    citation = {"type": "jira", "key": issue_key, "url": jira_hit.get("url")}
    return answer, citation


def _generate_code_answer(code_hit: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Generate answer from GitHub code.

    Args:
        code_hit: GitHub code data

    Returns:
        Tuple of (answer_text, citation)
    """
    repo = code_hit.get("repo")
    path = code_hit.get("path")
    answer = f"Relevant code is at {repo}/{path}."
    citation = {"type": "code", "repo": repo, "path": path}
    return answer, citation


def _generate_pr_answer(pr_hit: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Generate answer from GitHub PR.

    Args:
        pr_hit: GitHub PR data

    Returns:
        Tuple of (answer_text, citation)
    """
    title = pr_hit.get("title")
    number = pr_hit.get("number")
    state = pr_hit.get("state")
    answer = f"Related PR: {title} (#{number}, {state})."
    citation = {"type": "pr", "number": number, "url": pr_hit.get("url")}
    return answer, citation


def _generate_meeting_answer(text_context: str) -> tuple[str, dict]:
    """Generate fallback answer from meeting context.

    Args:
        text_context: Meeting transcript text

    Returns:
        Tuple of (answer_text, citation)
    """
    if "." in text_context:
        # Extract last two sentences using improved sentence boundary detection
        # Handle common abbreviations and edge cases more robustly

        # Split on sentence boundaries (., !, ?) but reassemble when followed by known abbreviations
        # Regex matches sentence end punctuation followed by whitespace or end of string
        sentence_endings = re.compile(r"(?<=[.!?])\s+")
        potential_sentences = sentence_endings.split(text_context)
        sentences = []
        current_sentence = ""

        for i, part in enumerate(potential_sentences):
            part = part.strip()
            if not part:
                continue
            words = part.split()
            # Check if the last word is a known abbreviation (strip trailing punctuation and internal periods)
            last_word = words[-1].rstrip(".!?").replace(".", "") if words else ""
            if last_word in COMMON_ABBREVIATIONS and i < len(potential_sentences) - 1:
                # This is an abbreviation, continue building the sentence
                current_sentence += part + " "
            else:
                current_sentence += part
                if (
                    current_sentence.strip()
                    and len(current_sentence.strip()) > MIN_SENTENCE_LENGTH
                ):
                    sentences.append(current_sentence.strip())
                current_sentence = ""

        s = sentences[-2:] if sentences else []
    else:
        s = []

    if not s:
        s = [text_context[:MAX_FALLBACK_LENGTH]]

    answer = " ".join(s).strip()
    citation = {"type": "meeting"}
    return answer, citation


def generate_grounded_answer(
    jira_hits: list[Dict[str, Any]],
    code_hits: list[Dict[str, Any]],
    pr_hits: list[Dict[str, Any]],
    meeting_snippets: list[str],
) -> Dict[str, Any]:
    """Generate a grounded answer with citations from JIRA, GitHub, and meeting context.

    This function coordinates the complete answer generation pipeline.
    Priority order: JIRA issues -> GitHub code -> Pull requests ->
    Meeting context -> Fallback

    Args:
        jira_hits: List of matching JIRA issues
        code_hits: List of matching GitHub code files
        pr_hits: List of matching GitHub pull requests
        meeting_snippets: Recent transcript text segments

    Returns:
        Dictionary with answer text, citations, confidence score,
        token count, and latency_ms placeholder
    """
    # Build text_context from the end, only including as many snippets as fit within MAX_CONTEXT_LENGTH
    context_parts = []
    total_length = 0
    # Iterate from the end (most recent) backwards
    for snippet in reversed(meeting_snippets):
        snippet_length = len(snippet) + (
            0 if not context_parts else 1
        )  # +1 for space if not first
        if total_length + snippet_length > MAX_CONTEXT_LENGTH:
            break
        context_parts.insert(0, snippet)
        total_length += snippet_length
    text_context = " ".join(context_parts)
    # If still too long (e.g., one very long snippet), truncate at word boundary
    if len(text_context) > MAX_CONTEXT_LENGTH:
        # Find the last space before MAX_CONTEXT_LENGTH
        cutoff = text_context.rfind(" ", 0, MAX_CONTEXT_LENGTH)
        if cutoff == -1:
            # No space before MAX_CONTEXT_LENGTH; try to find the next space after
            next_space = text_context.find(" ", MAX_CONTEXT_LENGTH)
            if next_space != -1:
                text_context = text_context[:next_space]
            else:
                # No spaces at all; apply absolute hard limit to prevent unbounded growth
                hard_limit = int(
                    MAX_CONTEXT_LENGTH * 1.5
                )  # Allow 50% overflow for single words
                if len(text_context) > hard_limit:
                    text_context = text_context[:hard_limit]
                # else: preserve complete word if under hard limit
        else:
            text_context = text_context[:cutoff]

    # Generate answer based on priority order
    if jira_hits:
        answer, citation = _generate_jira_answer(jira_hits[0])
        citations = [citation]
    elif code_hits:
        answer, citation = _generate_code_answer(code_hits[0])
        citations = [citation]
    elif pr_hits:
        answer, citation = _generate_pr_answer(pr_hits[0])
        citations = [citation]
    elif text_context:
        answer, citation = _generate_meeting_answer(text_context)
        citations = [citation]
    else:
        answer = "I don't have enough context yet."
        citations = []

    return {
        "answer": answer[:MAX_ANSWER_LENGTH],
        "citations": citations,
        "confidence": DEFAULT_CONFIDENCE,
        "token_count": len(answer.split()),
        "latency_ms": DEFAULT_LATENCY_MS,
    }


def save_answer(db: Session, session_id: str, payload: Dict[str, Any]) -> SessionAnswer:
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


def _format_answer_row(row: SessionAnswer) -> dict[str, Any]:
    """Convert database row to API response format.

    Args:
        row: SQLAlchemy result row with answer data

    Returns:
        Dictionary formatted for API response
    """
    return {
        "id": row.id,
        "created_at": row.created_at,
        "answer": row.answer,
        "citations": row.citations or [],
        "confidence": row.confidence,
    }


def recent_answers(
    db: Session, session_id_param: str, since_ts: str | None = None
) -> list[Dict[str, Any]]:
    """Retrieve recent answers for a session.

    Args:
        db: Database session
        session_id_param: Session identifier
        since_ts: Optional ISO timestamp string to filter results after this time

    Returns:
        List of answer dictionaries with id, created_at, answer, citations, confidence
    """
    query = db.query(SessionAnswer).filter(SessionAnswer.session_id == session_id_param)
    if since_ts:
        try:
            since_datetime = parse_iso_timestamp(since_ts)
        except ValueError as e:
            raise ValueError(
                f"Invalid ISO timestamp format for 'since_ts': {since_ts}. "
                "Expected ISO 8601 format (e.g., 2023-10-14T12:30:45Z or 2023-10-14T12:30:45+00:00)."
            ) from e
        query = query.filter(SessionAnswer.created_at >= since_datetime)
    query = query.order_by(SessionAnswer.created_at.asc()).limit(MAX_RECENT_ANSWERS)
    rows = query.all()
    return [_format_answer_row(row) for row in rows]
