"""
MCP (Model Context Protocol) Server for NAVI

This module provides MCP server implementation that exposes NAVI's
advanced operations as standardized tools for AI assistants like Claude.

MCP Protocol: https://modelcontextprotocol.io/
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPTransport(Enum):
    """Supported MCP transport protocols."""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


@dataclass
class MCPToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


@dataclass
class MCPTool:
    """Definition of an MCP tool."""
    name: str
    description: str
    parameters: List[MCPToolParameter]
    handler: Callable
    category: str = "general"
    requires_approval: bool = False


@dataclass
class MCPToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPServer:
    """
    MCP Server that exposes NAVI tools to AI assistants.

    Supports multiple transport protocols:
    - stdio: Standard input/output (for local integration)
    - http: HTTP REST API (for remote integration)
    - websocket: WebSocket (for real-time bidirectional communication)
    """

    def __init__(
        self,
        name: str = "navi-tools",
        version: str = "1.0.0",
        transport: MCPTransport = MCPTransport.STDIO,
    ):
        self.name = name
        self.version = version
        self.transport = transport
        self.tools: Dict[str, MCPTool] = {}
        self._running = False

        # Register built-in NAVI tools
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register all built-in NAVI tools."""
        # Git Operations
        self._register_git_tools()
        # Database Operations
        self._register_database_tools()
        # Code Debugging
        self._register_debugging_tools()
        # File Operations
        self._register_file_tools()
        # Test Execution
        self._register_test_tools()
        # Code Analysis
        self._register_analysis_tools()

    def _register_git_tools(self):
        """Register advanced git operation tools."""
        # Cherry-pick
        self.register_tool(MCPTool(
            name="git_cherry_pick",
            description="Cherry-pick one or more commits to the current branch",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="commit_hashes",
                    type="array",
                    description="List of commit hashes to cherry-pick",
                ),
                MCPToolParameter(
                    name="no_commit",
                    type="boolean",
                    description="Stage changes without committing",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_git_cherry_pick,
            requires_approval=True,
        ))

        # Interactive Rebase
        self.register_tool(MCPTool(
            name="git_rebase",
            description="Rebase current branch onto another branch or commit",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="onto",
                    type="string",
                    description="Branch or commit to rebase onto",
                ),
                MCPToolParameter(
                    name="interactive",
                    type="boolean",
                    description="Use interactive rebase",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_git_rebase,
            requires_approval=True,
        ))

        # Squash Commits
        self.register_tool(MCPTool(
            name="git_squash",
            description="Squash multiple commits into one",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="num_commits",
                    type="number",
                    description="Number of recent commits to squash",
                ),
                MCPToolParameter(
                    name="message",
                    type="string",
                    description="New commit message for squashed commit",
                ),
            ],
            handler=self._handle_git_squash,
            requires_approval=True,
        ))

        # Stash Operations
        self.register_tool(MCPTool(
            name="git_stash",
            description="Manage git stash (save, pop, list, apply, drop)",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="operation",
                    type="string",
                    description="Stash operation to perform",
                    enum=["save", "pop", "list", "apply", "drop", "clear"],
                ),
                MCPToolParameter(
                    name="message",
                    type="string",
                    description="Message for stash save operation",
                    required=False,
                ),
                MCPToolParameter(
                    name="stash_id",
                    type="string",
                    description="Stash ID for apply/drop operations (e.g., 'stash@{0}')",
                    required=False,
                ),
            ],
            handler=self._handle_git_stash,
        ))

        # Git Bisect
        self.register_tool(MCPTool(
            name="git_bisect",
            description="Use binary search to find commit that introduced a bug",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="operation",
                    type="string",
                    description="Bisect operation",
                    enum=["start", "good", "bad", "reset", "skip", "run"],
                ),
                MCPToolParameter(
                    name="commit",
                    type="string",
                    description="Commit hash for good/bad marking",
                    required=False,
                ),
                MCPToolParameter(
                    name="script",
                    type="string",
                    description="Script to run for automated bisect",
                    required=False,
                ),
            ],
            handler=self._handle_git_bisect,
        ))

        # Reflog Recovery
        self.register_tool(MCPTool(
            name="git_reflog",
            description="Access reference logs to recover lost commits",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="operation",
                    type="string",
                    description="Reflog operation",
                    enum=["show", "recover"],
                ),
                MCPToolParameter(
                    name="ref",
                    type="string",
                    description="Reference to show/recover (e.g., 'HEAD@{5}')",
                    required=False,
                ),
                MCPToolParameter(
                    name="limit",
                    type="number",
                    description="Number of reflog entries to show",
                    required=False,
                    default=20,
                ),
            ],
            handler=self._handle_git_reflog,
        ))

        # Branch Cleanup
        self.register_tool(MCPTool(
            name="git_cleanup_branches",
            description="Clean up merged or stale branches",
            category="git_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the git repository",
                ),
                MCPToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="List branches to delete without actually deleting",
                    required=False,
                    default=True,
                ),
                MCPToolParameter(
                    name="include_remote",
                    type="boolean",
                    description="Also prune remote tracking branches",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_git_cleanup_branches,
            requires_approval=True,
        ))

    def _register_database_tools(self):
        """Register database operation tools."""
        # Schema Diff
        self.register_tool(MCPTool(
            name="db_schema_diff",
            description="Compare database schema between environments or models",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project with database models",
                ),
                MCPToolParameter(
                    name="source",
                    type="string",
                    description="Source to compare (models, database, migration)",
                    enum=["models", "database", "migration"],
                ),
                MCPToolParameter(
                    name="target",
                    type="string",
                    description="Target to compare against",
                    enum=["models", "database", "migration"],
                ),
            ],
            handler=self._handle_db_schema_diff,
        ))

        # Generate Migration
        self.register_tool(MCPTool(
            name="db_generate_migration",
            description="Generate database migration from model changes",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="message",
                    type="string",
                    description="Migration message/description",
                ),
                MCPToolParameter(
                    name="autogenerate",
                    type="boolean",
                    description="Auto-detect changes from models",
                    required=False,
                    default=True,
                ),
            ],
            handler=self._handle_db_generate_migration,
            requires_approval=True,
        ))

        # Apply Migration
        self.register_tool(MCPTool(
            name="db_apply_migration",
            description="Apply pending database migrations",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="revision",
                    type="string",
                    description="Specific revision to migrate to (default: head)",
                    required=False,
                    default="head",
                ),
                MCPToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="Show SQL without executing",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_db_apply_migration,
            requires_approval=True,
        ))

        # Rollback Migration
        self.register_tool(MCPTool(
            name="db_rollback_migration",
            description="Rollback database migrations",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="steps",
                    type="number",
                    description="Number of migrations to rollback",
                    required=False,
                    default=1,
                ),
                MCPToolParameter(
                    name="revision",
                    type="string",
                    description="Specific revision to rollback to",
                    required=False,
                ),
            ],
            handler=self._handle_db_rollback_migration,
            requires_approval=True,
        ))

        # Migration History
        self.register_tool(MCPTool(
            name="db_migration_history",
            description="Show database migration history",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="verbose",
                    type="boolean",
                    description="Show detailed information",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_db_migration_history,
        ))

        # Seed Database
        self.register_tool(MCPTool(
            name="db_seed",
            description="Seed database with test/initial data",
            category="database_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="seed_file",
                    type="string",
                    description="Path to seed data file",
                    required=False,
                ),
                MCPToolParameter(
                    name="environment",
                    type="string",
                    description="Environment to seed (dev, test, staging)",
                    enum=["dev", "test", "staging"],
                    required=False,
                    default="dev",
                ),
            ],
            handler=self._handle_db_seed,
            requires_approval=True,
        ))

    def _register_debugging_tools(self):
        """Register code debugging tools."""
        # Comprehensive Error Analysis
        self.register_tool(MCPTool(
            name="debug_analyze_error",
            description="Analyze error output from any language (15+ supported)",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="error_output",
                    type="string",
                    description="The error output/traceback to analyze",
                ),
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the workspace for context",
                    required=False,
                ),
                MCPToolParameter(
                    name="language",
                    type="string",
                    description="Programming language hint",
                    required=False,
                    enum=[
                        "python", "javascript", "typescript", "go", "rust",
                        "java", "kotlin", "swift", "c", "cpp", "csharp",
                        "ruby", "php", "scala", "elixir", "haskell", "dart"
                    ],
                ),
            ],
            handler=self._handle_debug_analyze_error,
        ))

        # Performance Analysis
        self.register_tool(MCPTool(
            name="debug_performance",
            description="Detect performance issues in code",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the codebase",
                ),
                MCPToolParameter(
                    name="file_path",
                    type="string",
                    description="Specific file to analyze",
                    required=False,
                ),
                MCPToolParameter(
                    name="include_patterns",
                    type="array",
                    description="Patterns to include (e.g., ['**/*.py'])",
                    required=False,
                ),
            ],
            handler=self._handle_debug_performance,
        ))

        # Dead Code Detection
        self.register_tool(MCPTool(
            name="debug_dead_code",
            description="Find unused/dead code in the codebase",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the codebase",
                ),
                MCPToolParameter(
                    name="language",
                    type="string",
                    description="Language to analyze",
                    required=False,
                ),
            ],
            handler=self._handle_debug_dead_code,
        ))

        # Circular Dependencies
        self.register_tool(MCPTool(
            name="debug_circular_deps",
            description="Detect circular dependencies in imports",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the codebase",
                ),
            ],
            handler=self._handle_debug_circular_deps,
        ))

        # Code Smells
        self.register_tool(MCPTool(
            name="debug_code_smells",
            description="Detect code smells and anti-patterns",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the codebase",
                ),
                MCPToolParameter(
                    name="severity",
                    type="string",
                    description="Minimum severity to report",
                    enum=["info", "warning", "error"],
                    required=False,
                    default="warning",
                ),
            ],
            handler=self._handle_debug_code_smells,
        ))

        # Auto-fix Suggestions
        self.register_tool(MCPTool(
            name="debug_auto_fix",
            description="Generate auto-fix suggestions for detected issues",
            category="code_debugging",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the codebase",
                ),
                MCPToolParameter(
                    name="issue_type",
                    type="string",
                    description="Type of issue to fix",
                    required=False,
                ),
                MCPToolParameter(
                    name="apply",
                    type="boolean",
                    description="Apply fixes automatically",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_debug_auto_fix,
            requires_approval=True,
        ))

    def _register_file_tools(self):
        """Register file operation tools."""
        self.register_tool(MCPTool(
            name="file_search",
            description="Search for files by pattern or content",
            category="file_operations",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to search in",
                ),
                MCPToolParameter(
                    name="pattern",
                    type="string",
                    description="Glob pattern or search query",
                ),
                MCPToolParameter(
                    name="content_search",
                    type="boolean",
                    description="Search file contents instead of names",
                    required=False,
                    default=False,
                ),
                MCPToolParameter(
                    name="regex",
                    type="boolean",
                    description="Use regex for content search",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_file_search,
        ))

        self.register_tool(MCPTool(
            name="file_read",
            description="Read file contents",
            category="file_operations",
            parameters=[
                MCPToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to the file",
                ),
                MCPToolParameter(
                    name="start_line",
                    type="number",
                    description="Starting line number",
                    required=False,
                ),
                MCPToolParameter(
                    name="end_line",
                    type="number",
                    description="Ending line number",
                    required=False,
                ),
            ],
            handler=self._handle_file_read,
        ))

        self.register_tool(MCPTool(
            name="file_write",
            description="Write or update file contents",
            category="file_operations",
            parameters=[
                MCPToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to the file",
                ),
                MCPToolParameter(
                    name="content",
                    type="string",
                    description="Content to write",
                ),
                MCPToolParameter(
                    name="create_dirs",
                    type="boolean",
                    description="Create parent directories if needed",
                    required=False,
                    default=True,
                ),
            ],
            handler=self._handle_file_write,
            requires_approval=True,
        ))

    def _register_test_tools(self):
        """Register test execution tools."""
        self.register_tool(MCPTool(
            name="test_run",
            description="Run tests in the project",
            category="test_execution",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="test_path",
                    type="string",
                    description="Specific test file or directory",
                    required=False,
                ),
                MCPToolParameter(
                    name="pattern",
                    type="string",
                    description="Test name pattern to match",
                    required=False,
                ),
                MCPToolParameter(
                    name="verbose",
                    type="boolean",
                    description="Verbose output",
                    required=False,
                    default=True,
                ),
                MCPToolParameter(
                    name="coverage",
                    type="boolean",
                    description="Run with coverage",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_test_run,
        ))

        self.register_tool(MCPTool(
            name="test_discover",
            description="Discover available tests",
            category="test_execution",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
            ],
            handler=self._handle_test_discover,
        ))

    def _register_analysis_tools(self):
        """Register code analysis tools."""
        self.register_tool(MCPTool(
            name="analyze_project",
            description="Analyze project structure and detect type",
            category="code_analysis",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
            ],
            handler=self._handle_analyze_project,
        ))

        self.register_tool(MCPTool(
            name="analyze_dependencies",
            description="Analyze project dependencies",
            category="code_analysis",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to the project",
                ),
                MCPToolParameter(
                    name="include_dev",
                    type="boolean",
                    description="Include dev dependencies",
                    required=False,
                    default=True,
                ),
                MCPToolParameter(
                    name="check_outdated",
                    type="boolean",
                    description="Check for outdated packages",
                    required=False,
                    default=False,
                ),
            ],
            handler=self._handle_analyze_dependencies,
        ))

        self.register_tool(MCPTool(
            name="analyze_complexity",
            description="Analyze code complexity metrics",
            category="code_analysis",
            parameters=[
                MCPToolParameter(
                    name="workspace_path",
                    type="string",
                    description="Path to analyze",
                ),
                MCPToolParameter(
                    name="threshold",
                    type="number",
                    description="Complexity threshold to report",
                    required=False,
                    default=10,
                ),
            ],
            handler=self._handle_analyze_complexity,
        ))

    def register_tool(self, tool: MCPTool):
        """Register a tool with the MCP server."""
        self.tools[tool.name] = tool
        logger.info(f"Registered MCP tool: {tool.name}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get MCP-formatted tool definitions for all registered tools."""
        definitions = []
        for tool in self.tools.values():
            properties = {}
            required = []

            for param in tool.parameters:
                param_def: Dict[str, Any] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.enum:
                    param_def["enum"] = param.enum
                if param.default is not None:
                    param_def["default"] = param.default

                properties[param.name] = param_def

                if param.required:
                    required.append(param.name)

            definitions.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
                "metadata": {
                    "category": tool.category,
                    "requires_approval": tool.requires_approval,
                },
            })

        return definitions

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: Optional[str] = None,
        approved: bool = False,
    ) -> MCPToolResult:
        """Execute a tool by name with given arguments."""
        if tool_name not in self.tools:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}",
            )

        tool = self.tools[tool_name]

        # Check approval for sensitive operations
        if tool.requires_approval and not approved:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' requires user approval",
                metadata={"requires_approval": True},
            )

        try:
            # Validate required parameters
            for param in tool.parameters:
                if param.required and param.name not in arguments:
                    return MCPToolResult(
                        success=False,
                        data=None,
                        error=f"Missing required parameter: {param.name}",
                    )

            # Execute the tool handler
            result = await tool.handler(arguments)

            return MCPToolResult(
                success=True,
                data=result,
                metadata={
                    "tool": tool_name,
                    "category": tool.category,
                    "executed_at": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}: {e}")
            return MCPToolResult(
                success=False,
                data=None,
                error=str(e),
            )

    # Tool Handlers
    async def _handle_git_cherry_pick(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git cherry-pick operation."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.cherry_pick(
            workspace_path=args["workspace_path"],
            commit_hashes=args["commit_hashes"],
            no_commit=args.get("no_commit", False),
        )

    async def _handle_git_rebase(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git rebase operation."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.rebase(
            workspace_path=args["workspace_path"],
            onto=args["onto"],
            interactive=args.get("interactive", False),
        )

    async def _handle_git_squash(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git squash operation."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.squash_commits(
            workspace_path=args["workspace_path"],
            num_commits=args["num_commits"],
            message=args["message"],
        )

    async def _handle_git_stash(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git stash operations."""
        from backend.services.deep_analysis import AdvancedGitOperations
        operation = args["operation"]
        workspace = args["workspace_path"]

        if operation == "save":
            return await AdvancedGitOperations.stash_save(
                workspace_path=workspace,
                message=args.get("message"),
            )
        elif operation == "pop":
            return await AdvancedGitOperations.stash_pop(workspace_path=workspace)
        elif operation == "list":
            return await AdvancedGitOperations.stash_list(workspace_path=workspace)
        elif operation == "apply":
            return await AdvancedGitOperations.stash_apply(
                workspace_path=workspace,
                stash_id=args.get("stash_id"),
            )
        elif operation == "drop":
            return await AdvancedGitOperations.stash_drop(
                workspace_path=workspace,
                stash_id=args.get("stash_id"),
            )
        elif operation == "clear":
            return await AdvancedGitOperations.stash_clear(workspace_path=workspace)
        else:
            return {"success": False, "error": f"Unknown stash operation: {operation}"}

    async def _handle_git_bisect(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git bisect operations."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.bisect(
            workspace_path=args["workspace_path"],
            operation=args["operation"],
            commit=args.get("commit"),
            script=args.get("script"),
        )

    async def _handle_git_reflog(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle git reflog operations."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.reflog(
            workspace_path=args["workspace_path"],
            operation=args["operation"],
            ref=args.get("ref"),
            limit=args.get("limit", 20),
        )

    async def _handle_git_cleanup_branches(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle branch cleanup."""
        from backend.services.deep_analysis import AdvancedGitOperations
        return await AdvancedGitOperations.cleanup_merged_branches(
            workspace_path=args["workspace_path"],
            dry_run=args.get("dry_run", True),
            include_remote=args.get("include_remote", False),
        )

    async def _handle_db_schema_diff(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle database schema diff."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.schema_diff(
            workspace_path=args["workspace_path"],
            source=args["source"],
            target=args["target"],
        )

    async def _handle_db_generate_migration(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle migration generation."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.generate_migration(
            workspace_path=args["workspace_path"],
            message=args["message"],
            autogenerate=args.get("autogenerate", True),
        )

    async def _handle_db_apply_migration(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle migration application."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.apply_migration(
            workspace_path=args["workspace_path"],
            revision=args.get("revision", "head"),
            dry_run=args.get("dry_run", False),
        )

    async def _handle_db_rollback_migration(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle migration rollback."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.rollback_migration(
            workspace_path=args["workspace_path"],
            steps=args.get("steps", 1),
            revision=args.get("revision"),
        )

    async def _handle_db_migration_history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle migration history query."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.migration_history(
            workspace_path=args["workspace_path"],
            verbose=args.get("verbose", False),
        )

    async def _handle_db_seed(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle database seeding."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations
        return await AdvancedDatabaseOperations.seed_database(
            workspace_path=args["workspace_path"],
            seed_file=args.get("seed_file"),
            environment=args.get("environment", "dev"),
        )

    async def _handle_debug_analyze_error(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle comprehensive error analysis."""
        from backend.services.comprehensive_debugger import ComprehensiveDebugger
        return await ComprehensiveDebugger.analyze(
            error_output=args["error_output"],
            workspace_path=args.get("workspace_path", "."),
            context={"language_hint": args.get("language")},
        )

    async def _handle_debug_performance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle performance issue detection."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.detect_performance_issues(
            workspace_path=args["workspace_path"],
            file_path=args.get("file_path"),
        )

    async def _handle_debug_dead_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dead code detection."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.detect_dead_code(
            workspace_path=args["workspace_path"],
        )

    async def _handle_debug_circular_deps(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle circular dependency detection."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.detect_circular_dependencies(
            workspace_path=args["workspace_path"],
        )

    async def _handle_debug_code_smells(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle code smell detection."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.detect_code_smells(
            workspace_path=args["workspace_path"],
        )

    async def _handle_debug_auto_fix(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle auto-fix generation."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.auto_fix(
            workspace_path=args["workspace_path"],
            dry_run=not args.get("apply", False),
        )

    async def _handle_file_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file search."""
        import glob
        import os
        import re

        workspace = args["workspace_path"]
        pattern = args["pattern"]
        content_search = args.get("content_search", False)
        use_regex = args.get("regex", False)

        results = []

        if content_search:
            # Search file contents
            for root, dirs, files in os.walk(workspace):
                # Skip hidden and common ignore dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]

                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if use_regex:
                                matches = re.findall(pattern, content)
                                if matches:
                                    results.append({
                                        "file": file_path,
                                        "matches": len(matches),
                                    })
                            elif pattern in content:
                                results.append({"file": file_path})
                    except Exception:
                        continue
        else:
            # Search file names
            matches = glob.glob(os.path.join(workspace, pattern), recursive=True)
            results = [{"file": m} for m in matches]

        return {"success": True, "results": results, "count": len(results)}

    async def _handle_file_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file read."""
        file_path = args["file_path"]
        start_line = args.get("start_line")
        end_line = args.get("end_line")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if start_line is not None or end_line is not None:
                start = (start_line or 1) - 1
                end = end_line or len(lines)
                lines = lines[start:end]

            return {
                "success": True,
                "content": "".join(lines),
                "total_lines": len(lines),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_file_write(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file write."""
        import os

        file_path = args["file_path"]
        content = args["content"]
        create_dirs = args.get("create_dirs", True)

        try:
            if create_dirs:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return {"success": True, "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_test_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test execution."""
        from backend.services.test_executor import TestExecutor

        executor = TestExecutor(workspace_path=args["workspace_path"])
        return await executor.run_tests(
            test_path=args.get("test_path"),
            pattern=args.get("pattern"),
            verbose=args.get("verbose", True),
            coverage=args.get("coverage", False),
        )

    async def _handle_test_discover(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle test discovery."""
        from backend.services.test_executor import TestExecutor

        executor = TestExecutor(workspace_path=args["workspace_path"])
        return await executor.discover_tests()

    async def _handle_analyze_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project analysis."""
        from backend.services.navi_brain import ProjectAnalyzer
        return await ProjectAnalyzer.detect_project_type(args["workspace_path"])

    async def _handle_analyze_dependencies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dependency analysis."""
        from backend.services.navi_brain import ProjectAnalyzer
        return await ProjectAnalyzer.analyze_dependencies(
            workspace_path=args["workspace_path"],
            include_dev=args.get("include_dev", True),
            check_outdated=args.get("check_outdated", False),
        )

    async def _handle_analyze_complexity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle complexity analysis."""
        from backend.services.deep_analysis import CodeDebugger
        return await CodeDebugger.analyze_complexity(
            workspace_path=args["workspace_path"],
            threshold=args.get("threshold", 10),
        )

    # Server lifecycle methods
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information in MCP format."""
        return {
            "name": self.name,
            "version": self.version,
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": True,
                },
            },
        }

    async def start(self):
        """Start the MCP server."""
        self._running = True
        logger.info(f"Starting MCP server '{self.name}' v{self.version} with {self.transport.value} transport")

        if self.transport == MCPTransport.STDIO:
            await self._run_stdio()
        elif self.transport == MCPTransport.HTTP:
            await self._run_http()
        elif self.transport == MCPTransport.WEBSOCKET:
            await self._run_websocket()

    async def stop(self):
        """Stop the MCP server."""
        self._running = False
        logger.info(f"Stopping MCP server '{self.name}'")

    async def _run_stdio(self):
        """Run server with stdio transport."""
        import sys

        while self._running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break

                request = json.loads(line)
                response = await self._handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.exception(f"Error in stdio handler: {e}")

    async def _run_http(self):
        """Run server with HTTP transport."""
        # HTTP transport would use FastAPI router
        # This is handled by the API router instead
        pass

    async def _run_websocket(self):
        """Run server with WebSocket transport."""
        # WebSocket transport for real-time communication
        pass

    async def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming MCP request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = self.get_server_info()
            elif method == "tools/list":
                result = {"tools": self.get_tool_definitions()}
            elif method == "tools/call":
                tool_result = await self.execute_tool(
                    tool_name=params.get("name"),
                    arguments=params.get("arguments", {}),
                )
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_result.data) if tool_result.success else tool_result.error,
                        }
                    ],
                    "isError": not tool_result.success,
                }
            else:
                result = {"error": f"Unknown method: {method}"}

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e),
                },
            }


# Global MCP server instance
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create the global MCP server instance."""
    global _mcp_server
    if _mcp_server is None:
        from backend.core.config import settings
        _mcp_server = MCPServer(
            name=settings.mcp_server_name,
            version=settings.mcp_server_version,
            transport=MCPTransport(settings.mcp_transport),
        )
    return _mcp_server
