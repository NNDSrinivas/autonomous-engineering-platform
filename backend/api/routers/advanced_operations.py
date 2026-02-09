"""
Advanced Operations API Router

Exposes advanced git, database, and debugging operations via REST API
for frontend integration.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.db import get_db
from backend.services import mcp_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced", tags=["advanced-operations"])


# --- Auth dependency shim -------------------------------------------------


def _viewer_user(user: User = Depends(require_role(Role.VIEWER))) -> User:
    return user


def _admin_user(user: User = Depends(require_role(Role.ADMIN))) -> User:
    return user


# ============================================================================
# Request/Response Models
# ============================================================================


# Git Operations Models
class GitCherryPickRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to git repository")
    commit_hashes: List[str] = Field(..., description="Commits to cherry-pick")
    no_commit: bool = Field(False, description="Stage without committing")


class GitRebaseRequest(BaseModel):
    workspace_path: str
    onto: str = Field(..., description="Branch/commit to rebase onto")
    interactive: bool = False


class GitSquashRequest(BaseModel):
    workspace_path: str
    num_commits: int = Field(..., gt=1, description="Number of commits to squash")
    message: str = Field(..., description="New commit message")


class GitStashRequest(BaseModel):
    workspace_path: str
    operation: str = Field(..., description="save, pop, list, apply, drop, clear")
    message: Optional[str] = None
    stash_id: Optional[str] = None


class GitBisectRequest(BaseModel):
    workspace_path: str
    operation: str = Field(..., description="start, good, bad, reset, skip, run")
    commit: Optional[str] = None
    script: Optional[str] = None


class GitReflogRequest(BaseModel):
    workspace_path: str
    operation: str = Field("show", description="show, recover")
    ref: Optional[str] = None
    limit: int = 20


class GitCleanupRequest(BaseModel):
    workspace_path: str
    dry_run: bool = True
    include_remote: bool = False


# Database Operations Models
class DbSchemaDiffRequest(BaseModel):
    workspace_path: str
    source: str = Field(..., description="models, database, or migration")
    target: str = Field(..., description="models, database, or migration")


class DbMigrationRequest(BaseModel):
    workspace_path: str
    message: str = Field(..., description="Migration message")
    autogenerate: bool = True


class DbApplyMigrationRequest(BaseModel):
    workspace_path: str
    revision: str = "head"
    dry_run: bool = False


class DbRollbackRequest(BaseModel):
    workspace_path: str
    steps: int = 1
    revision: Optional[str] = None


class DbSeedRequest(BaseModel):
    workspace_path: str
    seed_file: Optional[str] = None
    environment: str = "dev"


# Debugging Models
class DebugErrorRequest(BaseModel):
    error_output: str = Field(..., description="Error output/traceback")
    workspace_path: Optional[str] = None
    language: Optional[str] = None


class DebugPerformanceRequest(BaseModel):
    workspace_path: str
    file_path: Optional[str] = None


class DebugAutoFixRequest(BaseModel):
    workspace_path: str
    apply: bool = False


class ApprovalWrapper(BaseModel):
    """Wrapper for requests that require approval."""

    request: Dict[str, Any] = Field(
        ..., description="Wrapped operation request payload"
    )
    approved: bool = Field(False, description="User approval for operation")


# MCP Server Models
class McpServerCreateRequest(BaseModel):
    name: str = Field(..., description="Display name for the MCP server")
    url: str = Field(..., description="Streamable HTTP endpoint for MCP server")
    transport: str = Field("streamable_http", description="Transport protocol")
    auth_type: str = Field("none", description="Auth type: none, bearer, header, basic")
    auth_header_name: Optional[str] = Field(
        None, description="Header name for header auth"
    )
    headers: Optional[Dict[str, str]] = Field(
        None, description="Additional non-secret headers"
    )
    username: Optional[str] = Field(None, description="Username for basic auth")
    token: Optional[str] = Field(None, description="Bearer token or header token")
    password: Optional[str] = Field(None, description="Password for basic auth")
    enabled: bool = True


class McpServerUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    auth_header_name: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    username: Optional[str] = None
    token: Optional[str] = None
    password: Optional[str] = None
    enabled: Optional[bool] = None
    clear_secrets: Optional[bool] = None


class McpServerResponse(BaseModel):
    id: int
    name: str
    url: str
    transport: str
    auth_type: str
    enabled: bool
    status: str
    source: Optional[str] = None
    scope: Optional[str] = None
    tool_count: Optional[int] = None
    last_checked_at: Optional[str] = None
    last_error: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class McpServerListResponse(BaseModel):
    items: List[McpServerResponse]


class McpServerTestResponse(BaseModel):
    ok: bool
    tool_count: Optional[int] = None
    error: Optional[str] = None
    request: Optional[Dict[str, Any]] = None


# ============================================================================
# Git Operations Endpoints
# ============================================================================


@router.post("/git/cherry-pick")
async def git_cherry_pick(request: GitCherryPickRequest, approved: bool = False):
    """Cherry-pick commits to current branch. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Cherry-pick operation requires user approval",
            "operation": "git_cherry_pick",
            "details": {
                "commits": request.commit_hashes,
                "workspace": request.workspace_path,
            },
        }

    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.cherry_pick(
        workspace_path=request.workspace_path,
        commit_hashes=request.commit_hashes,
        no_commit=request.no_commit,
    )


@router.post("/git/rebase")
async def git_rebase(request: GitRebaseRequest, approved: bool = False):
    """Rebase current branch. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Rebase operation requires user approval",
            "operation": "git_rebase",
            "details": {
                "onto": request.onto,
                "interactive": request.interactive,
            },
        }

    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.rebase(
        workspace_path=request.workspace_path,
        onto=request.onto,
        interactive=request.interactive,
    )


@router.post("/git/squash")
async def git_squash(request: GitSquashRequest, approved: bool = False):
    """Squash commits. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Squash operation requires user approval",
            "operation": "git_squash",
            "details": {
                "num_commits": request.num_commits,
                "message": request.message,
            },
        }

    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.squash_commits(
        workspace_path=request.workspace_path,
        num_commits=request.num_commits,
        message=request.message,
    )


@router.post("/git/stash")
async def git_stash(request: GitStashRequest):
    """Manage git stash."""
    from backend.services.deep_analysis import AdvancedGitOperations

    operation = request.operation
    workspace = request.workspace_path

    if operation == "save":
        return await AdvancedGitOperations.stash_save(
            workspace_path=workspace,
            message=request.message,
        )
    elif operation == "pop":
        return await AdvancedGitOperations.stash_pop(workspace_path=workspace)
    elif operation == "list":
        return await AdvancedGitOperations.stash_list(workspace_path=workspace)
    elif operation == "apply":
        return await AdvancedGitOperations.stash_apply(
            workspace_path=workspace,
            stash_id=request.stash_id,
        )
    elif operation == "drop":
        return await AdvancedGitOperations.stash_drop(
            workspace_path=workspace,
            stash_id=request.stash_id,
        )
    elif operation == "clear":
        return await AdvancedGitOperations.stash_clear(workspace_path=workspace)
    else:
        raise HTTPException(400, f"Unknown stash operation: {operation}")


@router.post("/git/bisect")
async def git_bisect(request: GitBisectRequest):
    """Run git bisect to find bug-introducing commit."""
    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.bisect(
        workspace_path=request.workspace_path,
        operation=request.operation,
        commit=request.commit,
        script=request.script,
    )


@router.post("/git/reflog")
async def git_reflog(request: GitReflogRequest):
    """Access reflog for commit recovery."""
    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.reflog(
        workspace_path=request.workspace_path,
        operation=request.operation,
        ref=request.ref,
        limit=request.limit,
    )


@router.post("/git/cleanup-branches")
async def git_cleanup_branches(request: GitCleanupRequest, approved: bool = False):
    """Clean up merged branches. Requires approval for actual deletion."""
    if not request.dry_run and not approved:
        return {
            "requires_approval": True,
            "message": "Branch deletion requires user approval",
            "operation": "git_cleanup_branches",
        }

    from backend.services.deep_analysis import AdvancedGitOperations

    return await AdvancedGitOperations.cleanup_merged_branches(
        workspace_path=request.workspace_path,
        dry_run=request.dry_run,
        include_remote=request.include_remote,
    )


# ============================================================================
# Database Operations Endpoints
# ============================================================================


@router.post("/db/schema-diff")
async def db_schema_diff(request: DbSchemaDiffRequest):
    """Compare database schema between sources."""
    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.schema_diff(
        workspace_path=request.workspace_path,
        source=request.source,
        target=request.target,
    )


@router.post("/db/generate-migration")
async def db_generate_migration(request: DbMigrationRequest, approved: bool = False):
    """Generate database migration. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Migration generation requires user approval",
            "operation": "db_generate_migration",
            "details": {"message": request.message},
        }

    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.generate_migration(
        workspace_path=request.workspace_path,
        message=request.message,
        autogenerate=request.autogenerate,
    )


@router.post("/db/apply-migration")
async def db_apply_migration(request: DbApplyMigrationRequest, approved: bool = False):
    """Apply database migrations. Requires approval."""
    if not request.dry_run and not approved:
        return {
            "requires_approval": True,
            "message": "Migration application requires user approval",
            "operation": "db_apply_migration",
            "details": {"revision": request.revision},
        }

    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.apply_migration(
        workspace_path=request.workspace_path,
        revision=request.revision,
        dry_run=request.dry_run,
    )


@router.post("/db/rollback")
async def db_rollback(request: DbRollbackRequest, approved: bool = False):
    """Rollback database migrations. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Migration rollback requires user approval",
            "operation": "db_rollback",
            "details": {"steps": request.steps},
        }

    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.rollback_migration(
        workspace_path=request.workspace_path,
        steps=request.steps,
        revision=request.revision,
    )


@router.get("/db/migration-history")
async def db_migration_history(workspace_path: str, verbose: bool = False):
    """Get migration history."""
    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.migration_history(
        workspace_path=workspace_path,
        verbose=verbose,
    )


@router.post("/db/seed")
async def db_seed(request: DbSeedRequest, approved: bool = False):
    """Seed database with data. Requires approval."""
    if not approved:
        return {
            "requires_approval": True,
            "message": "Database seeding requires user approval",
            "operation": "db_seed",
            "details": {"environment": request.environment},
        }

    from backend.services.deep_analysis import AdvancedDatabaseOperations

    return await AdvancedDatabaseOperations.seed_database(
        workspace_path=request.workspace_path,
        seed_file=request.seed_file,
        environment=request.environment,
    )


# ============================================================================
# Debugging Endpoints
# ============================================================================


@router.post("/debug/analyze-error")
async def debug_analyze_error(request: DebugErrorRequest):
    """Comprehensive error analysis supporting 15+ languages."""
    from backend.services.comprehensive_debugger import ComprehensiveDebugger

    return await ComprehensiveDebugger.analyze(
        error_output=request.error_output,
        workspace_path=request.workspace_path or ".",
        context={"language_hint": request.language},
    )


@router.post("/debug/performance")
async def debug_performance(request: DebugPerformanceRequest):
    """Detect performance issues in code."""
    from backend.services.deep_analysis import CodeDebugger

    return await CodeDebugger.detect_performance_issues(
        workspace_path=request.workspace_path,
        file_path=request.file_path,
    )


@router.post("/debug/dead-code")
async def debug_dead_code(workspace_path: str):
    """Find unused/dead code."""
    from backend.services.deep_analysis import CodeDebugger

    return await CodeDebugger.detect_dead_code(workspace_path=workspace_path)


@router.post("/debug/circular-deps")
async def debug_circular_deps(workspace_path: str):
    """Detect circular dependencies."""
    from backend.services.deep_analysis import CodeDebugger

    return await CodeDebugger.detect_circular_dependencies(
        workspace_path=workspace_path
    )


@router.post("/debug/code-smells")
async def debug_code_smells(workspace_path: str):
    """Detect code smells and anti-patterns."""
    from backend.services.deep_analysis import CodeDebugger

    return await CodeDebugger.detect_code_smells(workspace_path=workspace_path)


@router.post("/debug/auto-fix")
async def debug_auto_fix(request: DebugAutoFixRequest, approved: bool = False):
    """Generate and optionally apply auto-fixes. Requires approval to apply."""
    if request.apply and not approved:
        return {
            "requires_approval": True,
            "message": "Applying auto-fixes requires user approval",
            "operation": "debug_auto_fix",
        }

    from backend.services.deep_analysis import CodeDebugger

    return await CodeDebugger.auto_fix(
        workspace_path=request.workspace_path,
        dry_run=not request.apply,
    )


# ============================================================================
# MCP Integration Endpoints
# ============================================================================


@router.get("/mcp/tools")
async def list_mcp_tools(
    include_external: bool = True,
    scope: Optional[str] = None,
    user: User = Depends(_viewer_user),
    db: Session = Depends(get_db),
):
    """List all available MCP tools (builtin + external)."""
    if scope and scope not in {"auto", "org", "user", "all"}:
        raise HTTPException(status_code=400, detail="Invalid scope value")
    from backend.services.mcp_server import get_mcp_server

    server = get_mcp_server()
    server_info = server.get_server_info()
    builtin_tools = server.get_tool_definitions()

    for tool in builtin_tools:
        metadata = tool.get("metadata") or {}
        tool["metadata"] = {
            **metadata,
            "server_id": "builtin",
            "server_name": server_info.get("name"),
            "source": "builtin",
            "transport": "local",
            "scope": "builtin",
            "category": metadata.get("category") or "builtin",
        }

    servers = (
        mcp_registry.list_servers(
            db,
            user_id=user.user_id,
            org_id=user.org_id,
            scope=scope or "auto",
        )
        if include_external
        else []
    )
    external_tools = (
        await mcp_registry.list_external_tools(
            db,
            user_id=user.user_id,
            org_id=user.org_id,
            servers=servers,
        )
        if include_external
        else []
    )

    server_list = [
        {
            "id": "builtin",
            "name": server_info.get("name"),
            "url": "local",
            "transport": "local",
            "auth_type": "none",
            "enabled": True,
            "status": "connected",
            "tool_count": len(builtin_tools),
            "last_checked_at": None,
            "last_error": None,
            "config": {},
            "source": "builtin",
            "scope": "builtin",
        }
    ] + servers

    return {
        "server_info": server_info,
        "servers": server_list,
        "tools": builtin_tools + external_tools,
    }


@router.post("/mcp/execute")
async def execute_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    approved: bool = False,
    server_id: Optional[str] = None,
    user: User = Depends(_viewer_user),
    db: Session = Depends(get_db),
):
    """Execute an MCP tool (builtin or external)."""
    from backend.services.mcp_server import get_mcp_server

    if server_id and server_id != "builtin":
        try:
            server_int_id = int(server_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="server_id must be 'builtin' or a valid integer",
            )
        server = mcp_registry.get_server(
            db,
            user_id=user.user_id,
            org_id=user.org_id,
            server_id=server_int_id,
        )
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")
        try:
            result = await mcp_registry.call_remote_tool(server, tool_name, arguments)
        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {
                    "tool": tool_name,
                    "server_id": server_id,
                    "server_name": server.get("name"),
                    "scope": server.get("scope"),
                    "source": "external",
                },
            }

        is_error = bool(result.get("isError")) if isinstance(result, dict) else False
        return {
            "success": not is_error,
            "data": result,
            "error": result.get("error") if isinstance(result, dict) else None,
            "metadata": {
                "tool": tool_name,
                "server_id": server_id,
                "server_name": server.get("name"),
                "source": "external",
                "scope": server.get("scope"),
                "executed_at": datetime.utcnow().isoformat(),
            },
        }

    server = get_mcp_server()
    result = await server.execute_tool(
        tool_name=tool_name,
        arguments=arguments,
        user_id=user.user_id,
        approved=approved,
    )
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "metadata": result.metadata,
    }


@router.get(
    "/mcp/servers",
    response_model=McpServerListResponse,
    summary="List MCP servers for current user",
)
def list_mcp_servers(
    scope: Optional[str] = None,
    user: User = Depends(_viewer_user),
    db: Session = Depends(get_db),
) -> McpServerListResponse:
    if scope and scope not in {"auto", "org", "user", "all"}:
        raise HTTPException(status_code=400, detail="Invalid scope value")
    items = mcp_registry.list_servers(
        db,
        user_id=user.user_id,
        org_id=user.org_id,
        scope=scope or "auto",
    )
    return McpServerListResponse(items=items)


@router.post(
    "/mcp/servers",
    response_model=McpServerResponse,
    summary="Create an MCP server",
)
def create_mcp_server(
    payload: McpServerCreateRequest,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> McpServerResponse:
    try:
        item = mcp_registry.create_server(
            db=db,
            user_id=user.user_id,
            org_id=user.org_id,
            name=payload.name,
            url=payload.url,
            transport=payload.transport,
            auth_type=payload.auth_type,
            header_name=payload.auth_header_name,
            headers=payload.headers,
            username=payload.username,
            token=payload.token,
            password=payload.password,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return McpServerResponse(**item)


@router.patch(
    "/mcp/servers/{server_id}",
    response_model=McpServerResponse,
    summary="Update an MCP server",
)
def update_mcp_server(
    server_id: int,
    payload: McpServerUpdateRequest,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> McpServerResponse:
    updates: Dict[str, Any] = payload.model_dump(exclude_unset=True)
    secrets: Dict[str, str] = {}
    if payload.token:
        secrets["token"] = payload.token
    if payload.password:
        secrets["password"] = payload.password
    if secrets:
        updates["secrets"] = secrets
    if payload.clear_secrets:
        updates["clear_secrets"] = True
    try:
        item = mcp_registry.update_server(
            db, user.user_id, user.org_id, server_id, updates
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return McpServerResponse(**item)


@router.delete(
    "/mcp/servers/{server_id}",
    summary="Delete an MCP server",
)
def delete_mcp_server(
    server_id: int,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
):
    deleted = mcp_registry.delete_server(db, user.user_id, user.org_id, server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"ok": True}


@router.post(
    "/mcp/servers/{server_id}/test",
    response_model=McpServerTestResponse,
    summary="Test an MCP server connection",
)
async def test_mcp_server(
    server_id: int,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> McpServerTestResponse:
    result = await mcp_registry.test_server(db, user.user_id, user.org_id, server_id)
    return McpServerTestResponse(**result)


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def health_check():
    """Health check for advanced operations."""
    from backend.services.mcp_server import get_mcp_server

    server = get_mcp_server()
    return {
        "status": "healthy",
        "mcp_server": server.get_server_info(),
        "tools_count": len(server.tools),
        "categories": list(set(t.category for t in server.tools.values())),
    }
