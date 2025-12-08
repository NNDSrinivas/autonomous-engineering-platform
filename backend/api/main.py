from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

# ---- Observability imports ----
from backend.core.obs.obs_logging import configure_json_logging

# Try to import tracing module, provide no-op implementations if not available
try:
    from backend.core.obs.obs_tracing import init_tracing, instrument_fastapi_app
except (ImportError, ModuleNotFoundError):
    def init_tracing() -> None:  # type: ignore[unused-ignore]
        """Fallback no-op if tracing module is absent."""
        pass

    def instrument_fastapi_app(app: FastAPI) -> None:  # type: ignore[unused-ignore]
        """Fallback no-op if tracing module is absent."""
        pass

from backend.core.obs.obs_metrics import metrics_app, PROM_ENABLED
from backend.core.obs.obs_middleware import ObservabilityMiddleware

from backend.core.health.router import router as health_router
from backend.core.health.shutdown import on_startup, on_shutdown
from backend.core.resilience.resilience_middleware import ResilienceMiddleware

from backend.core.settings import settings

# removed unused: setup_logging (using obs logging instead)
# removed unused: metrics_router (using new /metrics mount)
from ..core.middleware import AuditMiddleware

# removed unused: RequestIDMiddleware (ObservabilityMiddleware provides this)
from ..core.audit_service.middleware import EnhancedAuditMiddleware
from ..core.cache.middleware import CacheMiddleware
from ..core.db import get_db
from ..services import meetings as svc
from ..services.jira import JiraService
from ..services.github import GitHubService
from ..workers.queue import process_meeting
from ..workers.integrations import jira_sync, github_index
from ..workers.answers import generate_answer
from .tasks import router as tasks_router
from .routers.plan import router as plan_router
from .deliver import router as deliver_router
from .routers.policy import router as policy_router
from .change import router as change_router
from .chat import router as chat_router
from .navi import router as navi_router  # PR-5B/PR-6: NAVI extension endpoint
from .org_sync import router as org_sync_router  # Step 2: Jira/Confluence memory sync
from .navi_search import router as navi_search_router  # Step 3: Unified RAG search
from .navi_brief import router as navi_brief_router  # Jira tasks + task brief endpoints
from .navi_intent import router as navi_intent_router  # NAVI intent classification
from .routes.intent import router as intent_api_router  # LLM-powered intent classification API
from .routes.providers import router as providers_api_router  # BYOK provider management API
from .routes.agent import router as agent_api_router  # Complete NAVI agent API
from ..search.router import router as search_router
from .integrations_ext import router as integrations_ext_router
from .context_pack import router as context_pack_router
from .routers.memory import router as memory_router
from .routers.plan import router as live_plan_router
from .routers import presence as presence_router
from .routers.admin_rbac import router as admin_rbac_router
from .routers.rate_limit_admin import router as rate_limit_admin_router
from .routers.github_webhook import router as github_webhook_router

# VS Code Extension API endpoints
from .routers.oauth_device_auth0 import router as oauth_device_auth0_router
from .routers.connectors import router as connectors_router
from .routers.me import router as me_router
from .routers.jira_integration import router as jira_integration_router
from .routers.agent_planning import router as agent_planning_router
from .routers.ai_codegen import router as ai_codegen_router
from .routers.ai_feedback import router as ai_feedback_router
from .events.router import router as events_router  # Universal event ingestion
from .internal.router import router as internal_router  # System info and diagnostics
from ..core.realtime_engine import presence as presence_lifecycle
from ..core.obs.obs_logging import logger

from .routers.jira_webhook import router as jira_webhook_router
from .routers.slack_webhook import router as slack_webhook_router
from .routers.teams_webhook import router as teams_webhook_router
from .routers.docs_webhook import router as docs_webhook_router
from .routers.ci_webhook import router as ci_webhook_router
from .routers.debug_info import router as debug_info_router
from .routers.debug_context import router as debug_context_router
from .routers.chat_history import router as chat_history_router
# Auth0 JWT validation routes
from ..auth.routes import router as auth_routes_router

# Initialize observability after imports
configure_json_logging()
init_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: manage startup/shutdown of background services."""
    # Startup: initialize background services
    await on_startup()  # PR-29: Health system startup
    presence_lifecycle.start_cleanup_thread()
    yield
    # Shutdown: cleanup background services
    presence_lifecycle.stop_cleanup_thread()
    try:
        result = on_shutdown()  # PR-29: Graceful shutdown
        if hasattr(result, '__await__'):
            await result
    except Exception as e:
        logger.warning(f"Shutdown warning: {e}")


app = FastAPI(title=f"{settings.APP_NAME} - Core API", lifespan=lifespan)

# Instrument app with OpenTelemetry after creation (PR-28)
instrument_fastapi_app(app)

# Middlewares (place ObservabilityMiddleware high so all routes are observed)
app.add_middleware(
    ObservabilityMiddleware
)  # PR-28: Request IDs, metrics, structured logs
app.add_middleware(
    ResilienceMiddleware
)  # PR-29: Circuit breaker support with 503 responses
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# RequestIDMiddleware removed - ObservabilityMiddleware provides this functionality
# Temporarily disabled for local dev while debugging connector issues
# app.add_middleware(RateLimitMiddleware, enabled=settings.RATE_LIMITING_ENABLED)
app.add_middleware(CacheMiddleware)  # PR-27: Distributed caching headers

# Conditional audit logging (disabled in test/CI environments to prevent DB errors)
# Check for explicit test environment using app_env
is_test_env = settings.APP_ENV in ["test", "ci"]
if not is_test_env and settings.enable_audit_logging:
    app.add_middleware(AuditMiddleware, service_name="core")
    app.add_middleware(EnhancedAuditMiddleware)  # PR-25: Enhanced audit logging

# Mount /metrics when enabled (PR-28)
if PROM_ENABLED:
    app.mount("/metrics", metrics_app())

# Health endpoints (PR-29) - replaces basic /health endpoint
app.include_router(health_router)


# Basic health endpoint for backwards compatibility
@app.get("/health")
def health():
    return {"status": "ok", "service": "core"}


@app.get("/version")
def version():
    return {"name": settings.APP_SLUG, "env": settings.APP_ENV, "version": "0.1.0"}


# Routers
# Old metrics_router removed - using new /metrics mount (PR-28)
app.include_router(tasks_router)
app.include_router(deliver_router)
app.include_router(policy_router)
app.include_router(change_router)
app.include_router(chat_router)  # Enhanced conversational interface
app.include_router(navi_router)  # PR-5B/PR-6: NAVI VS Code extension
app.include_router(org_sync_router)  # Step 2: Jira/Confluence memory integration
app.include_router(navi_search_router)  # Step 3: Unified RAG search
app.include_router(navi_brief_router)  # NAVI: Jira task list and task brief
app.include_router(navi_intent_router)  # NAVI: Intent classification for smart routing  
app.include_router(intent_api_router)  # LLM-powered intent classification API (includes /api/agent/intent prefix)
app.include_router(providers_api_router)  # BYOK provider management API
app.include_router(agent_api_router, prefix="/api")  # Complete NAVI agent API
app.include_router(search_router)
app.include_router(integrations_ext_router)
app.include_router(context_pack_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(events_router, prefix="/api")  # Universal event ingestion
app.include_router(internal_router, prefix="/api")  # System info and diagnostics
app.include_router(jira_webhook_router)  # Jira webhook ingestion
app.include_router(github_webhook_router)  # GitHub webhook ingestion
app.include_router(slack_webhook_router)  # Slack webhook ingestion
app.include_router(teams_webhook_router)  # Teams webhook ingestion
app.include_router(docs_webhook_router)  # Docs ingestion webhook
app.include_router(ci_webhook_router)  # CI ingestion webhook
app.include_router(debug_info_router)  # Debug context/ingestion info
app.include_router(chat_history_router)  # Chat history endpoints
app.include_router(debug_context_router)  # Debug org/user/context info

app.include_router(oauth_device_auth0_router)
app.include_router(connectors_router)
app.include_router(me_router)
app.include_router(jira_integration_router)
app.include_router(agent_planning_router)

# Auth0 JWT protected routes
app.include_router(auth_routes_router)

# Admin RBAC endpoints (PR-24)
app.include_router(admin_rbac_router)

# Rate limiting admin endpoints (PR-26)
app.include_router(rate_limit_admin_router)

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
# Include the real-time "live plan" router first so static endpoints like
# /api/plan/start resolve before the parameterized ModelRouter endpoint
# (which uses /api/plan/{key}). This prevents accidental route shadowing.
app.include_router(live_plan_router)  # PR-19: Live Plan Mode
app.include_router(presence_router.router)  # PR-22: Presence & Cursor Sync
app.include_router(plan_router)
# Note: These routers already include /api prefix internally (ai_codegen: /api/ai, ai_feedback: /api/feedback)
app.include_router(ai_codegen_router)  # PR-31: AI Code Generation
app.include_router(ai_feedback_router)  # PR-32: AI Feedback & Learning

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
        conn = JiraService.save_connection(db, body.cloud_base_url, body.access_token)
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
        cfg = JiraService.set_project_config(
            db, body.connection_id, body.project_keys, body.default_jql
        )
        return {"config_id": cfg.id}
    except Exception as e:
        logger.error(f"Failed to create JIRA configuration: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create JIRA configuration"
        )


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
    request: Request,
    q: str | None = None,
    project: str | None = None,
    assignee: str | None = None,  # DEPRECATED: Will be removed in v2.0
    updated_since: str | None = None,
    db: Session = Depends(get_db),
):
    """Search JIRA issues with optional filters.

    Args:
        q: Text search query for summary/description
        project: Filter by project key
        assignee: DEPRECATED - This parameter is no longer functional and will be
                 removed in v2.0. The underlying JiraService no longer supports
                 assignee filtering. Use project and query filters instead.
        updated_since: Filter by update timestamp
        db: Database session dependency

    Returns:
        List of matching JIRA issues

    Deprecation Notice:
        The 'assignee' parameter is deprecated as of v1.5 and will be removed in v2.0.
        It currently has no effect on the search results. Please update your code
        to use other filtering options.
    """
    # Issue deprecation warning if assignee parameter is provided in the request
    if "assignee" in request.query_params:
        import warnings

        warnings.warn(
            "The 'assignee' parameter is deprecated and will be removed in v2.0. "
            "It has no effect on search results. Use 'project' and 'q' parameters instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    return {
        "items": JiraService.search_issues(
            db, project=project, q=q, updated_since=updated_since
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
        conn = GitHubService.save_connection(db, body.access_token)
        return {"connection_id": conn.id}
    except Exception as e:
        logger.error(f"Failed to create GitHub connection: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create GitHub connection"
        )


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
    return {"hits": GitHubService.search_code(db, repo=repo, q=q, path_prefix=path)}


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
    return {
        "hits": GitHubService.search_issues(
            db, repo=repo, q=q, updated_since=updated_since
        )
    }


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

    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
