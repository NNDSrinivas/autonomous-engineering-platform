import datetime as dt

from fastapi import FastAPI, Depends, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..core.config import settings
from ..core.logging import setup_logging
from ..core.metrics import router as metrics_router
from ..core.middleware import AuditMiddleware
from ..core.middleware import RateLimitMiddleware
from ..core.middleware import RequestIDMiddleware
from ..core.db import get_db
from ..services import meetings as svc
from ..services import jira as jsvc, github as ghsvc
from ..workers.queue import process_meeting
from ..workers.integrations import jira_sync, github_index
from ..workers.answers import generate_answer
from .tasks import router as tasks_router
from .plan import router as plan_router

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
    return {
        "status": "ok",
        "service": "core",
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


# Prometheus
app.include_router(metrics_router)
app.include_router(tasks_router)

# Context Pack endpoint for IDE Bridge
ctx_router = APIRouter(prefix="/api/context", tags=["context"])


@ctx_router.get("/task/{key}")
def context_for_task(key: str, db: Session = Depends(get_db)):
    """Compose context pack from JIRA, meetings, tasks, code refs for IDE Bridge MVP"""
    # Get JIRA ticket info
    jira = (
        db.execute(
            text(
                "SELECT issue_key as key, summary, status, url FROM jira_issue WHERE issue_key=:k LIMIT 1"
            ),
            {"k": key},
        )
        .mappings()
        .first()
    )

    # Get recent meetings with summaries
    meets = (
        db.execute(
            text(
                """
        SELECT m.id, ms.id as summary_id, ms.summary_json
        FROM meeting m
        LEFT JOIN meeting_summary ms ON ms.meeting_id = m.id
        ORDER BY m.created_at DESC NULLS LAST LIMIT 5
    """
            )
        )
        .mappings()
        .all()
    )

    # Get recent action items
    actions = (
        db.execute(
            text(
                """
        SELECT a.id, a.title, a.assignee, a.meeting_id FROM action_item a
        ORDER BY a.created_at DESC NULLS LAST LIMIT 10
    """
            )
        )
        .mappings()
        .all()
    )

    # Get recent code files (if GitHub integration is available)
    code = (
        db.execute(
            text(
                """
        SELECT r.repo_full_name as repo, f.path FROM gh_file f 
        JOIN gh_repo r ON r.id=f.repo_id
        ORDER BY f.updated DESC NULLS LAST LIMIT 20
    """
            )
        )
        .mappings()
        .all()
    )

    # Build explanation
    explain = {
        "what": jira["summary"] if jira else f"Work item {key}",
        "why": "Aligns with team objectives.",
        "how": ["Open branch", "Edit auth module", "Add tests", "Run CI", "Open PR"],
    }

    return {
        "ticket": dict(jira) if jira else {"key": key},
        "explain": explain,
        "sources": {
            "meetings": [{"id": m["id"], "summary_id": m["summary_id"]} for m in meets],
            "actions": [dict(a) for a in actions],
            "code": [dict(c) for c in code],
        },
    }


app.include_router(ctx_router)
app.include_router(plan_router)

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


# ---- Feature 4: Integration endpoints (JIRA + GitHub) ----


# --- JIRA ---
class JiraConnectReq(BaseModel):
    cloud_base_url: str
    access_token: str  # for MVP; replace with real OAuth exchange later


@app.post("/api/integrations/jira/connect")
def jira_connect(body: JiraConnectReq, db: Session = Depends(get_db)):
    """Connect to JIRA instance with access token.

    Args:
        body: JIRA connection details including base URL and access token
        db: Database session dependency

    Returns:
        Connection ID for subsequent operations

    Raises:
        HTTPException: If connection creation fails
    """
    try:
        conn = jsvc.save_connection(db, body.cloud_base_url, body.access_token)
        return {"connection_id": conn.id}
    except Exception as e:
        logger.error(f"Failed to create JIRA connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to create JIRA connection")


class JiraConfigReq(BaseModel):
    connection_id: str
    project_keys: list[str]
    default_jql: str | None = None


@app.post("/api/integrations/jira/config")
def jira_config(body: JiraConfigReq, db: Session = Depends(get_db)):
    """Configure JIRA project sync settings.

    Args:
        body: Configuration including connection ID, project keys, and default JQL
        db: Database session dependency

    Returns:
        Configuration ID

    Raises:
        HTTPException: If configuration creation fails
    """
    try:
        cfg = jsvc.set_project_config(db, body.connection_id, body.project_keys, body.default_jql)
        return {"config_id": cfg.id}
    except Exception as e:
        logger.error(f"Failed to create JIRA configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to create JIRA configuration")


@app.post("/api/integrations/jira/sync")
def jira_trigger_sync(connection_id: str):
    """Trigger background sync of JIRA issues.

    Args:
        connection_id: JIRA connection identifier

    Returns:
        Sync job enqueue confirmation

    Raises:
        HTTPException: If sync job enqueue fails
    """
    try:
        jira_sync.send(connection_id)
        return {"enqueued": True}
    except Exception as e:
        logger.error(f"Failed to enqueue JIRA sync job: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue sync job")


@app.get("/api/jira/tasks")
def jira_tasks(
    q: str | None = None,
    project: str | None = None,
    assignee: str | None = None,
    updated_since: str | None = None,
    db: Session = Depends(get_db),
):
    """Search JIRA issues with optional filters.

    Args:
        q: Text search query for summary/description
        project: Filter by project key
        assignee: Filter by assignee name
        updated_since: Filter by update timestamp
        db: Database session dependency

    Returns:
        List of matching JIRA issues
    """
    return {
        "items": jsvc.search_issues(
            db, q=q, project=project, assignee=assignee, updated_since=updated_since
        )
    }


# --- GitHub ---
class GhConnectReq(BaseModel):
    access_token: str  # for MVP; replace with real OAuth exchange later


@app.post("/api/integrations/github/connect")
def gh_connect(body: GhConnectReq, db: Session = Depends(get_db)):
    """Connect to GitHub with access token.

    Args:
        body: GitHub connection details with access token
        db: Database session dependency

    Returns:
        Connection ID for subsequent operations

    Raises:
        HTTPException: If connection creation fails
    """
    try:
        conn = ghsvc.save_connection(db, body.access_token)
        return {"connection_id": conn.id}
    except Exception as e:
        logger.error(f"Failed to create GitHub connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to create GitHub connection")


class GhIndexReq(BaseModel):
    connection_id: str
    repo_full_name: str


@app.post("/api/github/index")
def gh_index_repo(body: GhIndexReq):
    """Trigger background indexing of GitHub repository.

    Args:
        body: Repository indexing request with connection ID and repo name

    Returns:
        Index job enqueue confirmation

    Raises:
        HTTPException: If index job enqueue fails
    """
    try:
        github_index.send(body.connection_id, body.repo_full_name)
        return {"enqueued": True}
    except Exception as e:
        logger.error(f"Failed to enqueue GitHub index job: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue index job")


@app.get("/api/github/search/code")
def gh_search_code(
    repo: str | None = None,
    q: str | None = None,
    path: str | None = None,
    db: Session = Depends(get_db),
):
    """Search GitHub code files with optional filters.

    Args:
        repo: Filter by repository full name (org/repo)
        q: Text search query (placeholder for future semantic search)
        path: Filter by file path prefix
        db: Database session dependency

    Returns:
        List of matching code files
    """
    return {"hits": ghsvc.search_code(db, repo=repo, q=q, path_prefix=path)}


@app.get("/api/github/search/issues")
def gh_search_issues(
    repo: str | None = None,
    q: str | None = None,
    updated_since: str | None = None,
    db: Session = Depends(get_db),
):
    """Search GitHub issues and pull requests with optional filters.

    Args:
        repo: Filter by repository full name (org/repo)
        q: Text search query for title/body
        updated_since: Filter by update timestamp
        db: Database session dependency

    Returns:
        List of matching issues and pull requests
    """
    return {"hits": ghsvc.search_issues(db, repo=repo, q=q, updated_since=updated_since)}


# TODO: Write actions (comment, transition, PR create) will ship in a later PR.


# ---- PR-5: Answer Coach manual trigger ----


class GenerateReq(BaseModel):
    session_id: str


class GenerateResp(BaseModel):
    enqueued: bool


@app.post("/api/answers/generate", response_model=GenerateResp)
def manual_generate(body: GenerateReq):
    """Manually trigger answer generation for a session.

    Args:
        body: Request containing session_id

    Returns:
        Confirmation that job was enqueued
    """
    generate_answer.send(body.session_id)
    return GenerateResp(enqueued=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
