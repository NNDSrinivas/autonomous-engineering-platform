# ruff: noqa: E402
# E402: Module level import not at top of file - intentional due to conditional imports
from __future__ import annotations

import importlib
import inspect
import os
import threading
from contextlib import asynccontextmanager
from typing import Any
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

# ---- Observability imports ----
from backend.core.obs.obs_logging import configure_json_logging, logger
from backend.core.obs.error_taxonomy import error_code_for_status

# Try to import tracing module, provide no-op implementations if not available
try:
    from backend.core.obs.obs_tracing import init_tracing, instrument_fastapi_app  # type: ignore[import]
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
from backend.core.rate_limit.middleware import RateLimitMiddleware
from backend.core.auth.vscode_middleware import VscodeAuthMiddleware
from backend.core.auth.deps import get_current_user

from backend.core.config import settings
from backend.core.settings import (
    settings as core_settings,
    validate_production_settings,
)

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
from backend.integrations.jira_client import JiraClient
from ..workers.queue import process_meeting
from ..workers.integrations import jira_sync, github_index
from ..workers.answers import generate_answer
from .tasks import router as tasks_router
from .routers.plan import router as plan_router
from .deliver import router as deliver_router
from .routers.policy import router as policy_router
from .routers.audit import router as audit_router
from .change import router as change_router
from .chat import router as chat_router
from .routers.chat_sessions import (
    router as chat_sessions_router,
)  # Chat session management
from .routers.autonomous_coding import (
    router as autonomous_coding_router,
)  # Project scaffolding + autonomous coding

# TEMPORARILY DISABLED FOR DEBUGGING - THESE IMPORTS ARE HANGING
from .navi import router as navi_router  # PR-5B/PR-6: NAVI extension endpoint
from .navi import agent_router as navi_agent_router  # Agent classification endpoint
from .navi import jobs_router as navi_jobs_router  # Long-running background jobs
from .routers.navi import (
    router as navi_engine_router,
)  # Aggressive NAVI engine with code generation
from .org_sync import router as org_sync_router  # Step 2: Jira/Confluence memory sync
from .navi_search import router as navi_search_router  # Step 3: Unified RAG search
from .github_actions import router as github_actions_router  # GitHub PR actions
from .github_ci import router as github_ci_router  # GitHub Actions CI
from .gitlab_ci import router as gitlab_ci_router  # GitLab CI
from .jenkins_ci import router as jenkins_ci_router  # Jenkins CI
from .routers.connectors import router as connectors_router
from .navi_brief import router as navi_brief_router  # Jira tasks + task brief endpoints
from .navi_intent import router as navi_intent_router  # NAVI intent classification
from .routes.intent import (
    router as intent_api_router,
)  # LLM-powered intent classification API
from .routes.providers import (
    router as providers_api_router,
)  # BYOK provider management API
from .routes.agent import router as agent_api_router  # Complete NAVI agent API
from .routes.tools import router as tools_api_router  # NAVI tools execution API
from ..search.router import router as search_router
from .integrations_ext import router as integrations_ext_router
from .context_pack import router as context_pack_router
from .routers.memory import router as memory_router
from .routers.memory_graph import router as memory_graph_router
from .routers.navi_memory import router as navi_memory_router
from .routers.saas import router as saas_router
from .routers.plan import router as live_plan_router
from .apply_fix import router as apply_fix_router  # Batch 6: Auto-Fix Engine
from .routers import presence as presence_router
from .routers.admin_rbac import router as admin_rbac_router
from .routers.admin_security import router as admin_security_router
from backend.marketplace import marketplace_router  # Phase 7.2: Extension Platform
from backend.extensions.api import (
    router as extensions_router,
)  # Phase 7.2: Extension Execution API
from .routers.rate_limit_admin import router as rate_limit_admin_router
from .routers.github_webhook import router as github_webhook_router
from .routers.advanced_operations import (
    router as advanced_operations_router,
)  # MCP Tools
from .routers.navi_planner import router as navi_planner_router
from .review_stream import router as review_stream_router  # SSE streaming for reviews
from .review import router as review_router
from .smart import router as smart_router
from .smart_review import router as smart_review_router
from .diff import router as diff_router
from .real_review_stream import (
    router as real_review_stream_router,
)  # Real git-based review streaming
from .comprehensive_review import (
    router as comprehensive_review_router,
)  # Advanced comprehensive analysis
from .navi_analyze import (
    router as navi_analyze_router,
)  # Phase 4.2: Task grounding for FIX_PROBLEMS
from .routes.navi_multirepo import (
    router as navi_multirepo_router,
)  # Phase 4.8: Multi-repository intelligence
from .governance import (
    router as governance_router,
)  # Phase 5.1: Human-in-the-Loop Governance
from ..ci_api import router as ci_api_router  # CI Failure Analysis API

# VS Code Extension API endpoints
from .routers.oauth_device_auth0 import router as oauth_device_auth0_router
from .routers.preview import (
    router as preview_router,
)  # Phase 1: Loveable-style live preview
from backend.core.auth0 import AUTH0_DEVICE_CLIENT_ID

# Conditionally import in-memory OAuth device router for development mode
# This router requires OAUTH_DEVICE_USE_IN_MEMORY_STORE=true to be set
oauth_device_dev_router = None
if settings.oauth_device_use_in_memory_store:
    try:
        from .routers.oauth_device import router as oauth_device_dev_router
    except RuntimeError:
        # Module throws RuntimeError if env var not set - shouldn't happen since we checked
        pass
from .routers.me import router as me_router
from .routers.jira_integration import router as jira_integration_router
from .routers.agent_planning import router as agent_planning_router
from .routers.ai_codegen import router as ai_codegen_router
from .routers.ai_feedback import router as ai_feedback_router
from .events.router import router as events_router  # Universal event ingestion
from .internal.router import router as internal_router  # System info and diagnostics
from .routers.telemetry import (
    router as telemetry_router,
)  # Telemetry & cache monitoring
from ..core.realtime_engine import presence as presence_lifecycle

from .routers.jira_webhook import router as jira_webhook_router
from .routers.slack_webhook import router as slack_webhook_router
from .routers.teams_webhook import router as teams_webhook_router
from .routers.docs_webhook import router as docs_webhook_router
from .routers.ci_webhook import router as ci_webhook_router
from .routers.zoom_webhook import router as zoom_webhook_router
from .routers.meet_webhook import router as meet_webhook_router

# Removed: navi_chat_enhanced_router - unused duplicate of chat.py navi_router
from .routers.memory_enhanced import router as memory_enhanced_router
from .routers.media import router as media_router  # Video/media processing for NAVI
from .routers.checkpoint import (
    router as checkpoint_router,
)  # Task checkpoint management
from .routers.enterprise_project import (
    router as enterprise_project_router,
)  # Enterprise project management

# from .refactor_stream_api import router as refactor_stream_router  # Batch 8 Part 4: SSE Live Refactor Streaming - TODO: Implement
# from .orchestrator import router as orchestrator_router  # Multi-Agent Orchestrator API

# Auth0 JWT validation routes
from ..auth.routes import router as auth_routes_router

# Initialize observability after imports
configure_json_logging()
init_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: manage startup/shutdown of background services."""
    # Startup: validate production settings and initialize background services
    validate_production_settings(
        core_settings
    )  # Validate production-specific settings for the active app configuration
    await on_startup()  # PR-29: Health system startup
    presence_lifecycle.start_cleanup_thread()

    # Initialize PreviewService singleton (Phase 1: Loveable-style live preview)
    # Only enable in single-worker deployments (in-memory storage doesn't support multi-worker)
    if os.getenv("PREVIEW_SERVICE_IN_MEMORY_ENABLED", "false").lower() == "true":
        from backend.services.preview.preview_service import PreviewService

        app.state.preview_service = PreviewService(
            ttl_seconds=3600,  # 1 hour TTL
            max_previews=100,  # Max 100 concurrent previews
        )
        logger.info("PreviewService initialized (TTL=3600s, max=100)")
        logger.warning(
            "PreviewService using in-memory storage. Only use with single-worker deployments "
            "(uvicorn --workers 1). For multi-worker environments, disable this feature flag "
            "and implement a shared backend (Redis/S3)."
        )
    else:
        app.state.preview_service = None
        logger.info(
            "PreviewService disabled (set PREVIEW_SERVICE_IN_MEMORY_ENABLED=true to enable)"
        )

    yield
    # Shutdown: cleanup background services
    # presence_lifecycle.stop_cleanup_thread()
    try:
        result = on_shutdown()  # PR-29: Graceful shutdown
        if inspect.iscoroutine(result):
            await result
    except Exception:
        logger.warning("Shutdown warning occurred during cleanup", exc_info=True)


app = FastAPI(title=f"{settings.app_name} - Core API", lifespan=lifespan)

# Ultra-fast health endpoints (registered before middleware for minimal latency)
from backend.api.fast_health import router as fast_health_router

app.include_router(fast_health_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_code = error_code_for_status(exc.status_code)
    logger.warning(
        "http_error",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "route": request.url.path,
            "method": request.method,
            "status": exc.status_code,
            "error_code": error_code,
        },
    )
    headers = dict(exc.headers or {})
    headers.setdefault("X-Error-Code", error_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": error_code,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_code = error_code_for_status(500)
    logger.error(
        "unhandled_error",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "trace_id": getattr(request.state, "trace_id", None),
            "route": request.url.path,
            "method": request.method,
            "status": 500,
            "error_code": error_code,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": error_code,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"X-Error-Code": error_code},
    )


# Instrument app with OpenTelemetry after creation (PR-28)
instrument_fastapi_app(app)

# Middlewares (place ObservabilityMiddleware high so all routes are observed)
app.add_middleware(
    ObservabilityMiddleware
)  # PR-28: Request IDs, metrics, structured logs
app.add_middleware(
    ResilienceMiddleware
)  # PR-29: Circuit breaker support with 503 responses

# CORS configuration - strict by default, dev override is explicit
dev_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
    "http://localhost:3006",
    "http://localhost:3007",
    "http://localhost:3008",
    "http://localhost:3009",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:3003",
    "http://127.0.0.1:3004",
    "http://127.0.0.1:3005",
    "http://127.0.0.1:3006",
    "http://127.0.0.1:3007",
    "http://127.0.0.1:3008",
    "http://127.0.0.1:3009",
]

cors_origins = settings.cors_origins_list
cors_regex = None
allow_creds = True

if settings.allow_dev_cors:
    cors_origins = sorted(set(cors_origins + dev_origins))
    if settings.allow_vscode_webview:
        cors_regex = (
            r"^(https?://(localhost|127\.0\.0\.1):\d+"
            r"|vscode-webview://.*|https://.*\.vscode-cdn\.net)$"
        )
    else:
        cors_regex = r"^(https?://(localhost|127\.0\.0\.1):\d+)$"
    allow_creds = False
elif settings.allow_vscode_webview:
    cors_regex = r"^(https://.*\.vscode-cdn\.net|vscode-webview://.*)$"

if settings.cors_origins == "*" and not settings.allow_dev_cors:
    cors_origins = []
    cors_regex = None

logger.info("🌐 CORS Configuration:")
logger.info(f"  allow_dev_cors: {settings.allow_dev_cors}")
logger.info(f"  allow_vscode_webview: {settings.allow_vscode_webview}")
logger.info(f"  allow_origins: {cors_origins}")
logger.info(f"  allow_origin_regex: {cors_regex}")
logger.info(f"  allow_credentials: {allow_creds}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# VS Code/webview auth enforcement
app.add_middleware(
    VscodeAuthMiddleware,
    enabled=settings.vscode_auth_required,
    allow_dev_bypass=settings.allow_dev_auth_bypass,
)
# RequestIDMiddleware removed - ObservabilityMiddleware provides this functionality
app.add_middleware(RateLimitMiddleware, enabled=core_settings.RATE_LIMITING_ENABLED)
app.add_middleware(CacheMiddleware)  # PR-27: Distributed caching headers

# Conditional audit logging (disabled in test/CI environments to prevent DB errors)
# Check for explicit test environment using app_env
is_test_env = settings.app_env in ["test", "ci"]
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


@app.get("/ping")
def ping():
    return {"status": "ok", "message": "pong"}


@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


_OPTIONAL_ROUTER_LOCK = threading.Lock()
_OPTIONAL_ROUTER_GROUPS: list[dict[str, Any]] = [
    {
        "key": "debug",
        "prefixes": ("/api/debug",),
        "routers": [
            ("backend.api.routers.debug_info", "router", {}),
            ("backend.api.routers.debug_context", "router", {}),
        ],
    },
    {
        "key": "org_scan",
        "prefixes": ("/api/org/scan",),
        "routers": [
            ("backend.api.routers.org_scan", "router", {}),
        ],
    },
    {
        "key": "chat_history",
        "prefixes": ("/api/chat",),
        "routers": [
            ("backend.api.routers.chat_history", "router", {}),
        ],
    },
    {
        "key": "team_collaboration",
        "prefixes": ("/api/navi/team",),
        "routers": [
            ("backend.api.routers.team_collaboration", "router", {}),
        ],
    },
    {
        "key": "code_generation",
        "prefixes": (
            "/api/navi/generate",
            "/api/navi/analyze",
            "/api/navi/refactor",
            "/api/navi/explain",
            "/api/navi/convert",
            "/api/navi/templates",
            "/api/navi/items",
        ),
        "routers": [
            ("backend.api.routers.code_generation", "router", {}),
        ],
    },
    {
        "key": "task_management",
        "prefixes": (
            "/api/navi/tasks",
            "/api/navi/projects",
            "/api/navi/dashboard",
            "/api/navi/analytics",
        ),
        "routers": [
            ("backend.api.routers.task_management", "router", {}),
        ],
    },
]
_OPTIONAL_ROUTER_LOADED: set[str] = set()


def _load_optional_router_group(app: FastAPI, group: dict[str, Any]) -> None:
    key = group["key"]
    if key in _OPTIONAL_ROUTER_LOADED:
        return
    with _OPTIONAL_ROUTER_LOCK:
        if key in _OPTIONAL_ROUTER_LOADED:
            return
        for module_path, router_attr, include_kwargs in group["routers"]:
            module = importlib.import_module(module_path)
            router = getattr(module, router_attr)
            app.include_router(router, **include_kwargs)
        _OPTIONAL_ROUTER_LOADED.add(key)
        logger.info("Lazy-loaded optional router group: %s", key)


def _maybe_load_optional_routers(app: FastAPI, path: str) -> None:
    for group in _OPTIONAL_ROUTER_GROUPS:
        prefixes = group["prefixes"]
        if any(path.startswith(prefix) for prefix in prefixes):
            _load_optional_router_group(app, group)
            break


def _load_all_optional_routers(app: FastAPI) -> None:
    for group in _OPTIONAL_ROUTER_GROUPS:
        _load_optional_router_group(app, group)


if hasattr(settings, "defer_optional_routers") and settings.defer_optional_routers:

    @app.middleware("http")
    async def deferred_optional_router_loader(request: Request, call_next):
        _maybe_load_optional_routers(request.app, request.url.path)
        return await call_next(request)

else:
    _load_all_optional_routers(app)


# Routers
# Old metrics_router removed - using new /metrics mount (PR-28)
app.include_router(tasks_router)
app.include_router(deliver_router)
app.include_router(policy_router)
app.include_router(change_router)
app.include_router(chat_router)  # Enhanced conversational interface
app.include_router(
    chat_sessions_router
)  # Chat session management (list, create, delete)
# DISABLED: navi_chat_router was taking precedence over navi_router, preventing deep analysis
# The navi_router from navi.py uses the full agent_loop with project overview and deep analysis
# app.include_router(navi_chat_router)  # Diff-aware Navi chat - DISABLED, use navi_router instead
app.include_router(autonomous_coding_router)  # Autonomous coding + project scaffolding
# Removed: navi_chat_enhanced_router - unused duplicate
app.include_router(
    memory_enhanced_router
)  # Enhanced memory management from code-companion
app.include_router(
    navi_router  # PR-5B/PR-6: NAVI VS Code extension (already has /api/navi prefix)
)
app.include_router(navi_jobs_router)  # /api/jobs background execution endpoints
app.include_router(navi_planner_router)  # NAVI planner endpoints (/api/navi/plan/*)
app.include_router(
    navi_engine_router
)  # Aggressive NAVI engine with code generation, git ops, dependency management
app.include_router(navi_analyze_router)  # Phase 4.2: Task grounding for FIX_PROBLEMS
app.include_router(navi_multirepo_router)  # Phase 4.8: Multi-repository intelligence
app.include_router(governance_router)  # Phase 5.1: Human-in-the-Loop Governance
app.include_router(
    navi_agent_router, prefix="/api/navi/agent"
)  # Agent classification endpoint
app.include_router(org_sync_router)  # Step 2: Jira/Confluence memory integration
app.include_router(navi_search_router)  # Step 3: Unified RAG search
app.include_router(github_actions_router)  # GitHub PR actions
app.include_router(github_ci_router)  # GitHub CI trigger/status
app.include_router(gitlab_ci_router)  # GitLab CI trigger/status
app.include_router(jenkins_ci_router)  # Jenkins CI trigger/status
app.include_router(connectors_router, prefix="/api")  # Connector management
app.include_router(navi_brief_router)  # NAVI: Jira task list and task brief
app.include_router(navi_intent_router)  # NAVI: Intent classification for smart routing
app.include_router(ci_api_router)  # CI Failure Analysis API
app.include_router(marketplace_router)  # Phase 7.2: Extension Marketplace & Signing
app.include_router(extensions_router)  # Phase 7.2: Extension Execution API
app.include_router(
    intent_api_router
)  # LLM-powered intent classification API (includes /api/agent/intent prefix)
app.include_router(providers_api_router)  # BYOK provider management API
app.include_router(agent_api_router, prefix="/api")  # Complete NAVI agent API
app.include_router(tools_api_router)  # NAVI tools execution API
app.include_router(
    apply_fix_router
)  # Batch 6: Auto-Fix Engine with AI patch generation
# app.include_router(
#     autonomous_navi_router, prefix="/api"
# )  # Autonomous coding integration - DISABLED FOR DEBUG (router not imported)
app.include_router(search_router)
app.include_router(integrations_ext_router)
app.include_router(context_pack_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(memory_graph_router)  # Memory graph queries (/api/memory/*)
app.include_router(
    navi_memory_router,
    dependencies=[Depends(get_current_user)],
)  # NAVI memory endpoints (/api/navi-memory/*) - secured with authentication
app.include_router(saas_router)  # SaaS management endpoints (/saas/*)
app.include_router(events_router, prefix="/api")  # Universal event ingestion
app.include_router(internal_router, prefix="/api")  # System info and diagnostics
app.include_router(telemetry_router)  # Telemetry & cache monitoring (/api/telemetry/*)
app.include_router(review_router)
app.include_router(smart_router)
app.include_router(smart_review_router)
app.include_router(diff_router)
app.include_router(review_stream_router)  # SSE streaming for code reviews
app.include_router(
    real_review_stream_router, prefix="/api"
)  # Real git-based review streaming
app.include_router(preview_router)  # Phase 1: Loveable-style live preview (static HTML)
# Test and debug endpoints - only enabled in development
if (
    os.getenv("DEBUG", "false").lower() == "true"
    or os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"
):
    app.include_router(
        comprehensive_review_router, prefix="/api"
    )  # Advanced comprehensive analysis
    logger.info("Test and debug endpoints enabled")
# app.include_router(refactor_stream_router)  # Batch 8 Part 4: SSE Live Refactor Streaming - TODO: Implement
app.include_router(audit_router, prefix="/api")  # Audit and replay endpoints
app.include_router(jira_webhook_router)  # Jira webhook ingestion
app.include_router(github_webhook_router)  # GitHub webhook ingestion
app.include_router(slack_webhook_router)  # Slack webhook ingestion
app.include_router(teams_webhook_router)  # Teams webhook ingestion
app.include_router(docs_webhook_router)  # Docs ingestion webhook
app.include_router(ci_webhook_router)  # CI ingestion webhook
app.include_router(zoom_webhook_router)  # Zoom webhook ingestion
app.include_router(meet_webhook_router)  # Meet webhook ingestion
# app.include_router(orchestrator_router)  # Multi-Agent Orchestrator API
app.include_router(media_router)  # Video/media processing for NAVI
app.include_router(checkpoint_router)  # Task checkpoint management for recovery
app.include_router(
    enterprise_project_router
)  # Enterprise project management for long-running projects

# Register Auth0 device flow router (LEGACY - gated by feature flag)
# DEPRECATED: Device flow is replaced by PKCE for VS Code extension.
# Only enable ENABLE_LEGACY_DEVICE_FLOW=true for backward compatibility.
if settings.enable_legacy_device_flow and AUTH0_DEVICE_CLIENT_ID and not settings.oauth_device_use_in_memory_store:
    app.include_router(oauth_device_auth0_router)
    logger.warning(
        "⚠️  LEGACY MODE: Device flow endpoints enabled. "
        "This is DEPRECATED. Extension v0.3.0+ uses PKCE. "
        "Set ENABLE_LEGACY_DEVICE_FLOW=false to disable."
    )
else:
    logger.info(
        "Device flow router disabled (ENABLE_LEGACY_DEVICE_FLOW=false or missing config). "
        "Extension v0.3.0+ uses PKCE."
    )

# Register in-memory OAuth device router for development mode (LEGACY)
# This provides a simple device code flow without Auth0 for local development
if settings.enable_legacy_device_flow and oauth_device_dev_router is not None:
    app.include_router(oauth_device_dev_router)
    logger.warning(
        "🚨 DEVELOPMENT MODE: In-memory OAuth device router enabled (LEGACY). "
        "This is NOT suitable for production. Extension v0.3.0+ uses PKCE. "
        "Set ENABLE_LEGACY_DEVICE_FLOW=false and OAUTH_DEVICE_USE_IN_MEMORY_STORE=false."
    )

app.include_router(connectors_router)
app.include_router(me_router)
app.include_router(jira_integration_router)
app.include_router(agent_planning_router)

# Auth0 JWT protected routes
app.include_router(auth_routes_router)

# Admin RBAC endpoints (PR-24)
app.include_router(admin_rbac_router)
app.include_router(admin_security_router)

# Rate limiting admin endpoints (PR-26)
app.include_router(rate_limit_admin_router)

# MCP Tools - Advanced Git, Database, Debugging operations
app.include_router(advanced_operations_router)

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
app.include_router(live_plan_router)  # Live Plan Mode
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
    access_token: str | None = None  # for MVP; replace with real OAuth exchange later
    token_type: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    email: str | None = None
    api_token: str | None = None


@app.post("/api/integrations/jira/connect")
async def jira_connect(body: JiraConnectReq, db: Session = Depends(get_db)):
    """Connect to JIRA instance with access token.

    Args:
        body: JIRA connection details including base URL and access token
        db: Database session dependency

    Returns:
        Connection ID for subsequent operations

    Raises:
        HTTPException: If connection creation fails
    """
    base_url = body.cloud_base_url.rstrip("/")
    token_type = body.token_type or "Bearer"

    if body.access_token:
        try:
            async with JiraClient(
                base_url=base_url,
                access_token=body.access_token,
                token_type=token_type,
            ) as jira:
                await jira.get_myself()
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail=f"Jira credential validation failed: {exc}",
            ) from exc
        try:
            conn = JiraService.save_connection(
                db,
                base_url,
                body.access_token,
                token_type=token_type,
                refresh_token=body.refresh_token,
                expires_at=body.expires_at,
            )
            return {"connection_id": conn.id}
        except Exception as e:
            logger.error(f"Failed to create JIRA connection: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to create JIRA connection"
            )

    if body.email and body.api_token:
        raise HTTPException(
            status_code=400,
            detail="API token auth should be configured via /api/connectors/jira/connect",
        )

    raise HTTPException(
        status_code=400,
        detail="Provide access_token or email + api_token",
    )


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
    q: str | None = None,
    project: str | None = None,
    updated_since: str | None = None,
    db: Session = Depends(get_db),
):
    """Search JIRA issues with optional filters.

    Args:
        q: Text search query for summary/description
        project: Filter by project key
        updated_since: Filter by update timestamp
        db: Database session dependency

    Returns:
        List of matching JIRA issues
    """
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

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
