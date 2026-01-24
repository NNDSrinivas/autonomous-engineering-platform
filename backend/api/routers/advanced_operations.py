"""
Advanced Operations API Router

Exposes advanced git, database, and debugging operations via REST API
for frontend integration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced", tags=["advanced-operations"])


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

    approved: bool = Field(False, description="User approval for operation")
    request: Dict[str, Any]


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
async def list_mcp_tools():
    """List all available MCP tools."""
    from backend.services.mcp_server import get_mcp_server

    server = get_mcp_server()
    return {
        "server_info": server.get_server_info(),
        "tools": server.get_tool_definitions(),
    }


@router.post("/mcp/execute")
async def execute_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    approved: bool = False,
):
    """Execute an MCP tool."""
    from backend.services.mcp_server import get_mcp_server

    server = get_mcp_server()
    result = await server.execute_tool(
        tool_name=tool_name,
        arguments=arguments,
        approved=approved,
    )
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "metadata": result.metadata,
    }


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
