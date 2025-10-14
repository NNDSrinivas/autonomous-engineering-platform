import asyncio
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from typing import Generator

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import redis

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

# Constants for Redis operations
REDIS_KEY_EXPIRY_SECONDS = 60  # TTL for Redis keys
REDIS_MAX_CONNECTIONS = 10  # Maximum connections in Redis pool

logger = setup_logging()

# Create Redis connection pool for reuse across requests
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url, decode_responses=True, max_connections=REDIS_MAX_CONNECTIONS
)


# Context manager for database sessions in streaming contexts
@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup.

    Yields:
        Database session that will be automatically closed
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _format_sse_data(data: dict | str) -> str:
    """Format data for Server-Sent Events transmission.

    Args:
        data: Dictionary or string to send as SSE data

    Returns:
        Formatted SSE data string
    """
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, default=str)}\n\n"


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
    return {
        "status": "ok",
        "service": "realtime",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/version")
def version() -> dict[str, str]:
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


app.include_router(metrics_router)

# ---- Feature 1 endpoints (Realtime capture) ----


class CreateSessionReq(BaseModel):
    """Request model for creating a new answer session."""
    question: str
    user_id: str = "default_user"


class CreateSessionResp(BaseModel):
    """Response model for answer session creation."""
    session_id: str
    message: str


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


@app.post("/api/sessions/{session_id}/captions")
def post_caption(
    session_id: str, body: CaptionReq, db: Session = Depends(get_db)
) -> dict[str, str]:
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
        raise HTTPException(status_code=404, detail="Session not found")
    svc.append_segment(
        db, m.id, body.text, body.speaker, body.ts_start_ms, body.ts_end_ms
    )

    # Enqueue answer generation with simple heuristic
    try:
        r = redis.Redis(connection_pool=redis_pool)
        key = f"ans:count:{session_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, REDIS_KEY_EXPIRY_SECONDS)
        n, _ = pipe.execute()
        
        # Check for question or interval-based trigger
        has_question = "?" in (body.text or "")
        is_interval_trigger = n % ANSWER_GENERATION_INTERVAL == 0
        if has_question or is_interval_trigger:
            generate_answer.send(session_id)
    except (redis.RedisError, ConnectionError) as e:
        logger.warning("Failed to enqueue answer generation: %s", e)
        # Continue even if answer generation fails

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
        raise HTTPException(status_code=404, detail="Session not found")
    m.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ---- PR-5: Real-time Answer Coach endpoints ----


@app.get("/api/sessions/{session_id}/answers")
def get_answers(
    session_id: str, since: str | None = None, db: Session = Depends(get_db)
) -> dict[str, list[dict]]:
    """Poll for new answers generated for this session.

    Args:
        session_id: Session identifier
        since: Optional ISO timestamp to get answers after this time
        db: Database session dependency

    Returns:
        List of answers with citations
    """
    return {"answers": asvc.recent_answers(db, session_id, since_ts=since)}


@app.get("/api/sessions/{session_id}/stream")
def stream_answers(session_id: str) -> StreamingResponse:
    """Server-Sent Events stream of real-time answers.

    Args:
        session_id: Session identifier

    Returns:
        SSE stream that emits new answers as they're generated

    Note:
        Stream will continue until client disconnects or max duration is reached.
        Uses a single database session for the entire stream duration to avoid connection pool exhaustion.
    """
    last_ts = None

    async def event_stream():
        nonlocal last_ts
        start_time = datetime.now(timezone.utc)
        # Use a single database session for the entire SSE stream to avoid connection pool exhaustion
        with db_session() as db:
            try:
                while True:
                    # Check if max duration exceeded
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    if elapsed > SSE_MAX_DURATION_SECONDS:
                        yield _format_sse_data({"event": "timeout"})
                        break

                    # Query for new answers using the shared session
                    rows = asvc.recent_answers(db, session_id, since_ts=last_ts)
                    if rows:
                        # emit each new row as SSE (most recent first - already sorted by query)
                        for r in rows:
                            yield _format_sse_data(r)
                        # Set last_ts to the latest timestamp after emitting
                        last_ts = rows[0]["created_at"]

                    await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
            except Exception as e:
                logger.exception(
                    "Error in SSE stream for session %s: %s", session_id, e
                )
                yield _format_sse_data(
                    {"event": "error", "message": "An internal server error occurred."}
                )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.realtime_port)
