import asyncio
import json
import redis
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from typing import Generator, AsyncGenerator, Dict, Any

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logging import setup_logging
from ..core.metrics import router as metrics_router
from ..core.middleware import AuditMiddleware
from ..core.middleware import RateLimitMiddleware
from ..core.middleware import RequestIDMiddleware
from ..core.db import get_db, SessionLocal
from ..services import meetings as svc
from ..services import answers as asvc
from ..workers.answers import generate_answer

# Constants for answer generation triggering
ANSWER_GENERATION_INTERVAL = 3  # Generate answer every N captions

# Constants for SSE streaming
SSE_MAX_DURATION_SECONDS = 3600  # Maximum duration for SSE streams (1 hour)
SSE_POLL_INTERVAL_SECONDS = 1  # Polling interval for new answers in SSE streams

# Constants for rate limiting
REALTIME_API_RPM = 120  # Requests per minute for realtime API

# Constants for HTTP status codes
HTTP_404_NOT_FOUND = 404  # Resource not found
HTTP_503_SERVICE_UNAVAILABLE = 503  # Service unavailable


def _datetime_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# Constants for Redis operations
REDIS_KEY_EXPIRY_SECONDS = 60  # TTL for Redis keys

# Constants for fallback question detection
FALLBACK_QUESTION_INDICATORS = {
    "what",
    "when",
    "where",
    "how",
    "who",
    "why",
    "which",
    "can",
    "should",
    "would",
    "could",
    "will",  # Modal verbs indicate questions or uncertainty
}

# Additional modal verbs not covered by FALLBACK_QUESTION_INDICATORS
ADDITIONAL_MODAL_VERBS = ["might", "may"]

REDIS_MAX_CONNECTIONS = 10  # Maximum connections in Redis pool

logger = setup_logging()

# Redis client instance for dependency injection
_redis_client_instance = None
_redis_client_lock = threading.Lock()


def get_redis_client() -> redis.Redis:
    """Get or create Redis client for dependency injection.

    Thread-safe lazy initialization using double-checked locking pattern.
    Ensures only one Redis client instance is created even in multi-threaded
    FastAPI environments.
    """
    global _redis_client_instance
    if _redis_client_instance is None:
        with _redis_client_lock:
            # Double-check pattern to prevent race conditions
            if _redis_client_instance is None:
                try:
                    # Redis client handles connection pooling internally
                    _redis_client_instance = redis.Redis.from_url(
                        settings.redis_url,
                        decode_responses=True,
                        max_connections=REDIS_MAX_CONNECTIONS,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to initialize Redis client: %s", e, exc_info=True
                    )
                    raise HTTPException(
                        status_code=HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Redis unavailable",
                    ) from e
    return _redis_client_instance


# Context manager for database sessions in streaming contexts
@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup.

    Used specifically for SSE streaming where we need shorter-lived sessions
    per poll cycle rather than dependency injection. This is complementary
    to get_db() which is used for FastAPI dependency injection.

    Yields:
        Database session that will be automatically closed
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _format_sse_data(data: Dict[str, Any] | str) -> str:
    """Format data for Server-Sent Events transmission.

    Args:
        data: Dictionary or string to send as SSE data

    Returns:
        Formatted SSE data string
    """
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, default=_datetime_serializer)}\n\n"


def _extract_timestamp_from_row(row: Dict[str, Any]) -> str | None:
    """Extract and convert timestamp from a row to ISO format string.

    Args:
        row: Dictionary containing row data with potential 'created_at' field

    Returns:
        ISO formatted timestamp string or None if not available
    """
    if "created_at" in row and row["created_at"] is not None:
        if isinstance(row["created_at"], datetime):
            return row["created_at"].isoformat()
        # If it's already a string, return as-is
        return str(row["created_at"])
    return None


def _convert_timestamp_to_iso(timestamp: datetime | str | None) -> str | None:
    """Convert datetime or string timestamp to ISO format string.

    Args:
        timestamp: Datetime object, ISO string, or None

    Returns:
        ISO formatted timestamp string or input if already string/None
    """
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return timestamp


app = FastAPI(title=f"{settings.app_name} - Realtime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware, service_name="realtime")
app.add_middleware(
    RateLimitMiddleware, service_name="realtime", rpm=REALTIME_API_RPM
)  # a bit higher
app.add_middleware(AuditMiddleware, service_name="realtime")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint for service monitoring.

    Returns:
        Status information with service name and timestamp
    """
    return {
        "status": "ok",
        "service": "realtime",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/version")
def version() -> dict[str, str]:
    """Version information endpoint.

    Returns:
        Application name, environment, and version details
    """
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


app.include_router(metrics_router)

# ---- Feature 1 endpoints (Realtime capture) ----


class CreateSessionReq(BaseModel):
    """Request model for creating a new answer session."""

    title: str | None = None
    provider: str | None = "manual"


class CreateSessionResp(BaseModel):
    """Response model for answer session creation."""

    session_id: str
    meeting_id: str


@app.post("/api/sessions", response_model=CreateSessionResp)
def create_session(
    body: CreateSessionReq, db: Session = Depends(get_db)
) -> CreateSessionResp:
    """Create a new meeting session for real-time caption capture.

    Args:
        body: Session creation request with title and provider
        db: Database session dependency

    Returns:
        Session and meeting IDs for subsequent API calls
    """
    m = svc.create_meeting(db, title=body.title, provider=body.provider, org_id=None)
    return CreateSessionResp(session_id=m.session_id, meeting_id=m.id)


class CaptionReq(BaseModel):
    """Request model for caption submission."""

    text: str
    speaker: str | None = None
    ts_start_ms: int | None = None
    ts_end_ms: int | None = None


def _should_generate_answer(text: str, caption_count: int) -> bool:
    """Determine if answer generation should be triggered.

    Args:
        text: Caption text to analyze
        caption_count: Current caption count for session

    Returns:
        True if answer should be generated
    """
    has_question = _should_generate_answer_fallback(text)
    is_interval_trigger = caption_count % ANSWER_GENERATION_INTERVAL == 0
    return has_question or is_interval_trigger


def _enqueue_answer_generation(session_id: str, text: str) -> None:
    """Enqueue answer generation with Redis-based heuristics.

    Args:
        session_id: Session identifier
        text: Caption text for analysis
    """
    try:
        r = get_redis_client()
        key = f"ans:count:{session_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, REDIS_KEY_EXPIRY_SECONDS)
        results = pipe.execute()
        n = results[0]  # Get count from first result

        if _should_generate_answer(text, n):
            generate_answer.send(session_id)
    except (redis.RedisError, ConnectionError) as e:
        logger.warning(
            "Failed to enqueue answer generation for session %s: %s", session_id, e
        )
        # Fallback: Use simple heuristic without Redis state
        logger.info("Using fallback answer generation for session %s", session_id)
        if _should_generate_answer_fallback(text):
            try:
                generate_answer.send(session_id)
            except Exception as fallback_error:
                logger.error(
                    "Fallback answer generation also failed for session %s: %s",
                    session_id,
                    fallback_error,
                )


def _should_generate_answer_fallback(text: str) -> bool:
    """Fallback heuristic for answer generation when Redis is unavailable.

    Note: This fallback only uses question-based triggers since we cannot track
    caption intervals without Redis state. To compensate for the loss of
    interval-based triggers, this uses more generous question detection.

    Args:
        text: Caption text to analyze

    Returns:
        True if answer should be generated based on simple text analysis
    """
    # Enhanced fallback: more generous question detection to compensate for lost interval triggers
    text_lower = (text or "").lower()

    # Check for question indicators or any sentence ending with '?'
    has_question_word = (
        any(indicator in text_lower for indicator in FALLBACK_QUESTION_INDICATORS)
        or "?" in text_lower
    )
    has_question_punctuation = "?" in text_lower

    # Additional generous patterns for fallback mode
    # Use module-level constant for performance
    has_modal_verbs = any(modal in text_lower for modal in ADDITIONAL_MODAL_VERBS)
    has_uncertainty = any(
        word in text_lower
        for word in ["maybe", "perhaps", "possibly", "not sure", "uncertain"]
    )

    return (
        has_question_word
        or has_question_punctuation
        or has_modal_verbs
        or has_uncertainty
    )


@app.post("/api/sessions/{session_id}/captions")
def post_caption(
    session_id: str, body: CaptionReq, db: Session = Depends(get_db)
) -> dict[str, bool]:
    """Add a caption/transcript segment to an active session.

    Args:
        session_id: Session identifier from create_session
        body: Caption data with text, speaker, and timestamps
        db: Database session dependency

    Returns:
        Success confirmation

    Raises:
        HTTPException: If session not found
    """
    m = svc.get_meeting_by_session(db, session_id)
    if not m:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Session not found")

    svc.append_segment(
        db, m.id, body.text, body.speaker, body.ts_start_ms, body.ts_end_ms
    )

    # Enqueue answer generation with simple heuristic
    _enqueue_answer_generation(session_id, body.text)
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def close_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Close/end a meeting session by marking it with an end timestamp.

    Args:
        session_id: Session identifier to close
        db: Database session dependency

    Returns:
        Success confirmation

    Raises:
        HTTPException: 404 if session not found
    """
    m = svc.get_meeting_by_session(db, session_id)
    if not m:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Session not found")
    m.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ---- PR-5: Real-time Answer Coach endpoints ----


@app.get("/api/sessions/{session_id}/answers")
def get_answers(
    session_id: str, since: str | None = None, db: Session = Depends(get_db)
) -> dict[str, list[Dict[str, Any]]]:
    """Poll for new answers generated for this session.

    Args:
        session_id: Session identifier
        since: Optional ISO timestamp to get answers after this time
        db: Database session dependency

    Returns:
        List of answers with citations
    """
    return {"answers": asvc.recent_answers(db, session_id, since_ts=since)}


def _check_stream_timeout(start_time: datetime) -> bool:
    """Check if SSE stream has exceeded maximum duration.

    Args:
        start_time: When the stream started

    Returns:
        True if timeout exceeded
    """
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    return elapsed > SSE_MAX_DURATION_SECONDS


def _emit_new_answers(
    db: Session, session_id: str, last_ts: datetime | None
) -> tuple[list[Dict[str, Any]], str | None]:
    """Emit new answers and return updated timestamp.

    Args:
        db: Database session
        session_id: Session identifier
        last_ts: Last timestamp processed

    Returns:
        Tuple of (new_rows, updated_last_ts as ISO string)
    """
    # Convert datetime to string for the API call
    since_ts = _convert_timestamp_to_iso(last_ts)
    rows = asvc.recent_answers(db, session_id, since_ts=since_ts)
    if rows:
        last_row = rows[-1]
        timestamp_str = _extract_timestamp_from_row(last_row)
        if timestamp_str:
            return rows, timestamp_str
        else:
            # Log a warning when "created_at" is missing
            logger.warning(
                "Missing or null 'created_at' in answer row for session %s", session_id
            )
            return rows, _convert_timestamp_to_iso(last_ts)
    return [], _convert_timestamp_to_iso(last_ts)


@app.get("/api/sessions/{session_id}/stream")
def stream_answers(session_id: str) -> StreamingResponse:
    """Server-Sent Events stream of real-time answers.

    Args:
        session_id: Session identifier

    Returns:
        SSE stream that emits new answers as they're generated

    Note:
        Stream will continue until client disconnects or max duration is reached.
        Uses short-lived database sessions for each poll to prevent connection exhaustion.
    """
    last_ts = None

    async def event_stream() -> AsyncGenerator[str, None]:
        nonlocal last_ts
        start_time = datetime.now(timezone.utc)
        # Use connection pooling for read-only SSE streaming

        try:
            # Create fresh database session for each poll iteration to prevent connection pool exhaustion
            while True:
                # Check if max duration exceeded
                if _check_stream_timeout(start_time):
                    yield _format_sse_data({"event": "timeout"})
                    break

                # Use short-lived database session for each query to prevent resource exhaustion
                with db_session() as db:
                    # Query for new answers and emit them
                    rows, last_ts = _emit_new_answers(db, session_id, last_ts)

                    # Emit in chronological order (oldest first)
                    for r in rows:
                        yield _format_sse_data(r)

                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            # Client disconnected - clean shutdown
            logger.info(
                "SSE stream cancelled for session %s (client disconnect)", session_id
            )
            raise  # Re-raise to properly close the connection
        except Exception as e:
            logger.exception("Error in SSE stream for session %s: %s", session_id, e)
            yield _format_sse_data(
                {
                    "event": "error",
                    "message": f"SSE stream error for session {session_id}. Please try reconnecting.",
                    "session_id": session_id,
                }
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.realtime_port)
