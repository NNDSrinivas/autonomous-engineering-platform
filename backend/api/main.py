from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logging import setup_logging
from ..core.metrics import router as metrics_router
from ..core.middleware import AuditMiddleware
from ..core.middleware import RateLimitMiddleware
from ..core.middleware import RequestIDMiddleware
from ..core.db import get_db
from ..services import meetings as svc
from ..workers.queue import process_meeting

logger = setup_logging()
app = FastAPI(title=f"{settings.app_name} - Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware, service_name="core")
app.add_middleware(RateLimitMiddleware, service_name="core", rpm=60)
app.add_middleware(AuditMiddleware, service_name="core")


@app.get("/health")
def health():
    return {"status": "ok", "service": "core", "time": datetime.utcnow().isoformat()}


@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


# Prometheus
app.include_router(metrics_router)

# ---- Feature 1 endpoints (Finalize + Query) ----


class FinalizeResp(BaseModel):
    enqueued: bool


@app.post("/api/meetings/{session_id}/finalize", response_model=FinalizeResp)
def finalize(session_id: str):
    """Enqueue background processing to generate meeting summary and actions.

    Args:
        session_id: Session identifier from realtime API

    Returns:
        Confirmation that processing was enqueued
    """
    # enqueue background processing
    process_meeting.send(session_id)
    return FinalizeResp(enqueued=True)


@app.get("/api/meetings/{session_id}/summary")
def get_summary(session_id: str, db: Session = Depends(get_db)):
    """Retrieve the AI-generated summary for a processed meeting.

    Args:
        session_id: Session identifier
        db: Database session dependency

    Returns:
        Meeting summary with bullets, decisions, risks, and actions

    Raises:
        HTTPException: If meeting not found or not yet processed
    """
    res = svc.get_summary(db, session_id)
    if not res:
        raise HTTPException(status_code=404, detail="Not ready or session not found")
    return res


@app.get("/api/meetings/{session_id}/actions")
def get_actions(session_id: str, db: Session = Depends(get_db)):
    return {"actions": svc.list_actions(db, session_id)}


@app.get("/api/meetings/search")
def search_meetings(
    q: str | None = None,
    since: str | None = Query(None),
    people: str | None = None,
    db: Session = Depends(get_db),
):
    return {"results": svc.search_meetings(db, q=q, since=since, people=people)}


# TODO: JIRA/GitHub endpoints coming in Features 2-3.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
