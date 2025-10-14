from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
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

logger = setup_logging()
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
        "time": datetime.utcnow().isoformat(),
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
    m = svc.create_meeting(db, title=body.title, provider=body.provider, org_id=None)
    return CreateSessionResp(session_id=m.session_id, meeting_id=m.id)


class CaptionReq(BaseModel):
    text: str
    speaker: str | None = None
    ts_start_ms: int | None = None
    ts_end_ms: int | None = None


@app.post("/api/sessions/{session_id}/captions")
def post_caption(session_id: str, body: CaptionReq, db: Session = Depends(get_db)):
    m = svc.get_meeting_by_session(db, session_id)
    if not m:
        raise HTTPException(status_code=404, detail="Session not found")
    svc.append_segment(
        db, m.id, body.text, body.speaker, body.ts_start_ms, body.ts_end_ms
    )
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def close_session(session_id: str, db: Session = Depends(get_db)):
    m = svc.get_meeting_by_session(db, session_id)
    if not m:
        raise HTTPException(status_code=404, detail="Session not found")
    m.ended_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# TODO: /answers/stream coming in Feature 4.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.realtime_port)
