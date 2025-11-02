import asyncio
import functools
import json
import redis
import time
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
REDIS_TRANSACTION_MAX_RETRIES = 5  # Maximum retries for Redis transactions
REDIS_RETRY_BASE_DELAY = 0.001  # Base delay for exponential backoff (1ms)

# Constants for fallback question detection
QUESTION_WORDS = {
    "what",
    "when",
    "where",
    "how",
    "who",
    "why",
    "which",
}

# Modal verbs that indicate questions or uncertainty
MODAL_VERBS = {
    "can",
    "should",
    "would",
    "could",
    "will",
    "might",
    "may",
}

# Combined question indicators for fallback detection
FALLBACK_QUESTION_INDICATORS = QUESTION_WORDS | MODAL_VERBS

logger = setup_logging()


# Redis client instance for dependency injection
@functools.lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Get or create Redis client for dependency injection.

    Thread-safe lazy initialization using functools.lru_cache.
    Ensures only one Redis client instance is created and cached.

    IMPORTANT: This creates a singleton Redis client shared across all FastAPI workers
    in the same process. The connection pool (settings.redis_max_connections) is shared
    by all concurrent requests.

    Multi-process deployment note: Each process (e.g., uvicorn --workers=4) gets its own
    singleton Redis client. Total Redis connections = workers × redis_max_connections.
    Plan Redis server capacity accordingly.

    Redis connection pool is configured via settings.redis_max_connections.
    For high-traffic scenarios with many concurrent SSE streams, consider:
    - Increasing redis_max_connections (default: 20, may need 50+ for 100+ concurrent streams)
    - Monitoring Redis memory usage and connection counts per process
    - Implementing connection health checks
    - Using FastAPI lifespan events for per-worker Redis instances if needed

    Expected concurrency: Up to 100+ concurrent SSE streams per instance
    with proper Redis pool sizing (recommend 0.5-1 connection per concurrent stream).

    Singleton limitation: All concurrent requests within the same worker process share the same
    connection pool, which may become a bottleneck under extreme load. Consider per-worker instances for 500+ concurrent streams.
    """
    try:
        # Use configured Redis connection pool size directly
        # Redis client handles connection pooling internally
        return redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_max_connections,
        )
    except Exception as e:
        logger.error("Failed to initialize Redis client: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable",
        ) from e


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


def _redis_result_to_int(result: Any) -> int:
    """Safely convert Redis result to integer.

    Redis operations can return various types depending on configuration.
    This helper ensures we get a consistent integer result.

    Args:
        result: The value returned from a Redis operation.

    Returns:
        The integer value of the result if conversion succeeds.
        Returns 0 if the result is None or cannot be converted to an integer.
    """
    if result is None:
        return 0
    if isinstance(result, int):
        return result
    if isinstance(result, (str, bytes)):
        try:
            return int(result)
        except (ValueError, TypeError):
            return 0
    # For other types, attempt conversion or default to 0
    try:
        return int(result)
    except (ValueError, TypeError):
        return 0


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

        # Use Redis transactions to prevent race conditions in concurrent requests
        retry_count = 0
        with r.pipeline(transaction=True) as pipe:
            while retry_count < REDIS_TRANSACTION_MAX_RETRIES:
                try:
                    # Watch the key for changes during transaction
                    pipe.watch(key)

                    # Start transaction
                    pipe.multi()
                    pipe.incr(key)
                    pipe.expire(key, REDIS_KEY_EXPIRY_SECONDS)
                    results = pipe.execute()
                    result = results[0] if results else 0
                    n = _redis_result_to_int(result)
                    break
                except redis.WatchError:
                    # Key was modified during transaction, retry with exponential backoff
                    retry_count += 1
                    if retry_count < REDIS_TRANSACTION_MAX_RETRIES:
                        time.sleep(REDIS_RETRY_BASE_DELAY * (2**retry_count))
                        continue
                    else:
                        # Max retries reached, fall back to non-atomic increment
                        result = r.incr(key)
                        n = _redis_result_to_int(result)
                        r.expire(key, REDIS_KEY_EXPIRY_SECONDS)
                        break

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

    # Check for question indicators with word boundaries to avoid partial matches
    # Strip punctuation to handle cases like 'what?' -> 'what'
    words = set(word.strip(".,!?;:") for word in text_lower.split())
    has_question_word = (
        any(indicator in words for indicator in FALLBACK_QUESTION_INDICATORS)
        or "?" in text_lower
    )

    # Additional generous patterns for fallback mode
    has_uncertainty = any(
        word in text_lower
        for word in ["maybe", "perhaps", "possibly", "not sure", "uncertain"]
    )

    return has_question_word or has_uncertainty


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
    db: Session, session_id: str, last_ts: datetime | str | None
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

    # Filter out rows with missing or null 'created_at' to prevent infinite loops
    if rows:
        # Filter and extract timestamps in one pass to avoid redundant calls
        filtered_rows_with_timestamps = []
        for row in rows:
            ts = _extract_timestamp_from_row(row)
            if ts:
                filtered_rows_with_timestamps.append((row, ts))
        if filtered_rows_with_timestamps:
            filtered_rows, timestamps = zip(*filtered_rows_with_timestamps)
            last_timestamp = timestamps[-1]  # Get timestamp of last row
            return list(filtered_rows), last_timestamp
        else:
            # All rows have missing timestamps - log warning for data integrity issue
            logger.warning(
                "All recent answer rows for session %s are missing or have null 'created_at'. "
                "Skipping rows and not updating last_ts. This may indicate a data integrity issue "
                "in the session_answer table. Preventing infinite polling by not updating last_ts.",
                session_id,
            )
            # Do not update last_ts; return previous last_ts to avoid infinite polling
            return [], _convert_timestamp_to_iso(last_ts)

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
            # Short-lived sessions are preferred for SSE streams to prevent resource leaks
            # and connection pool exhaustion with 100+ concurrent streams. Session overhead
            # is minimal compared to long-held connections in streaming contexts.
            # Poll continuously until timeout or client disconnect
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
