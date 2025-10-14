import asyncio
import json
from datetime import datetime, timezone

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
from ..core.db import get_db
from ..services import meetings as svc
from ..services import answers as asvc
from ..workers.answers import generate_answer

# Constants for answer generation triggering
ANSWER_GENERATION_INTERVAL = 3  # Generate answer every N captions

logger = setup_logging()

# Create Redis connection pool for reuse across requests
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url, decode_responses=True, max_connections=10
)

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
    RateLimitMiddleware, service_name="realtime", rpm=120
)  # a bit higher
app.add_middleware(AuditMiddleware, service_name="realtime")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "realtime",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


app.include_router(metrics_router)

# ---- Feature 1 endpoints (Realtime capture) ----


class CreateSessionReq(BaseModel):
    title: str | None = None
    provider: str | None = "manual"


class CreateSessionResp(BaseModel):
    session_id: str
    meeting_id: str


@app.post("/api/sessions", response_model=CreateSessionResp)
def create_session(body: CreateSessionReq, db: Session = Depends(get_db)):
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
    text: str
    speaker: str | None = None
    ts_start_ms: int | None = None
    ts_end_ms: int | None = None


@app.post("/api/sessions/{session_id}/captions")
def post_caption(session_id: str, body: CaptionReq, db: Session = Depends(get_db)):
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
        n = r.incr(key)
        if "?" in (body.text or "") or n % ANSWER_GENERATION_INTERVAL == 0:
            generate_answer.send(session_id)
        r.expire(key, 60)
    except (redis.RedisError, ConnectionError) as e:
        logger.warning("Failed to enqueue answer generation: %s", e)
        # Continue even if answer generation fails

    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def close_session(session_id: str, db: Session = Depends(get_db)):
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
):
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
def stream_answers(session_id: str):
    """Server-Sent Events stream of real-time answers.

    Args:
        session_id: Session identifier

    Returns:
        SSE stream that emits new answers as they're generated

    Note:
        Stream will continue until client disconnects or max duration is reached.
        Creates fresh database sessions for each query to avoid stale connections.
    """
    last_ts = None
    max_duration_seconds = 3600  # 1 hour max streaming

    async def event_stream():
        nonlocal last_ts
        start_time = datetime.now(timezone.utc)
        try:
            while True:
                # Check if max duration exceeded
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > max_duration_seconds:
                    yield f"data: {json.dumps({'event': 'timeout'})}\n\n"
                    break

                # Create fresh database session for each query to avoid stale connections
                # Using generator protocol properly to ensure cleanup
                db_gen = get_db()
                db = next(db_gen)
                try:
                    rows = asvc.recent_answers(db, session_id, since_ts=last_ts)
                    if rows:
                        # Set last_ts to the latest timestamp before emitting
                        last_ts = rows[0]["created_at"]
                        # emit each new row as SSE
                        for r in rows[::-1]:
                            yield f"data: {json.dumps(r, default=str)}\n\n"
                finally:
                    # Properly close the generator to trigger cleanup
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass

                await asyncio.sleep(1)
        except Exception:
            logger.exception("Error in SSE stream for session %s", session_id)
            yield f"data: {json.dumps({'event': 'error', 'message': 'An internal server error occurred.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.realtime_port)
