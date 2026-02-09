"""
Unified Agentic Agent for NAVI
==============================

This is the core agentic loop that makes NAVI competitive with:
- Claude Code (Anthropic's CLI)
- Cline (VS Code extension)
- GitHub Copilot (chat mode)
- OpenAI Codex

Key features:
1. Native tool-use API (not text parsing)
2. Continuous loop until task complete or max iterations
3. Streaming throughout (thinking, tool calls, results)
4. Context management with token tracking
5. Self-healing on errors
6. **VERIFICATION LOOP** - Automatically runs typecheck/tests/build after changes
7. **ERROR RECOVERY** - Feeds errors back to LLM for automatic fixes

The agent continuously:
1. Sends prompt + tools to LLM
2. Receives response with potential tool calls
3. Executes tool calls
4. Feeds results back to LLM
5. **If files modified**: Run verification (typecheck, tests, build)
6. **If verification fails**: Feed errors to LLM and loop
7. Repeats until LLM says "done" and verification passes, or max iterations
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from backend.ai.llm_router import LLMRouter, LLMResponse, ToolCall
from backend.services.command_utils import format_command_message

logger = logging.getLogger(__name__)


# ======================================================================
# Project Analyzer - Detect project type and verification commands
# ======================================================================


class ProjectAnalyzer:
    """Analyzes project to determine verification commands."""

    @staticmethod
    def detect_project_type(
        workspace_path: str,
    ) -> Tuple[str, str, Dict[str, Optional[str]]]:
        """
        Detect project type and return (project_type, framework, verification_commands).
        """
        commands: Dict[str, Optional[str]] = {
            "typecheck": None,
            "test": None,
            "build": None,
            "lint": None,
        }

        # Check for package.json (Node.js/TypeScript)
        pkg_json_path = os.path.join(workspace_path, "package.json")
        if os.path.exists(pkg_json_path):
            try:
                with open(pkg_json_path) as f:
                    pkg = json.load(f)

                scripts = pkg.get("scripts", {})
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                # Detect framework
                framework = "node"
                if "next" in deps:
                    framework = "nextjs"
                elif "react" in deps:
                    framework = "react"
                elif "vue" in deps:
                    framework = "vue"
                elif "angular" in deps or "@angular/core" in deps:
                    framework = "angular"
                elif "express" in deps:
                    framework = "express"

                # Detect package manager
                pkg_manager = "npm"
                if os.path.exists(os.path.join(workspace_path, "pnpm-lock.yaml")):
                    pkg_manager = "pnpm"
                elif os.path.exists(os.path.join(workspace_path, "yarn.lock")):
                    pkg_manager = "yarn"
                elif os.path.exists(os.path.join(workspace_path, "bun.lockb")):
                    pkg_manager = "bun"

                run_cmd = f"{pkg_manager} run" if pkg_manager != "npm" else "npm run"

                # Set verification commands based on scripts
                if "typecheck" in scripts:
                    commands["typecheck"] = f"{run_cmd} typecheck"
                elif "type-check" in scripts:
                    commands["typecheck"] = f"{run_cmd} type-check"
                elif "typescript" in deps or "ts-node" in deps:
                    commands["typecheck"] = "npx tsc --noEmit"

                if "test" in scripts:
                    commands["test"] = (
                        f"{run_cmd} test -- --passWithNoTests --watchAll=false"
                    )
                elif "jest" in deps:
                    commands["test"] = "npx jest --passWithNoTests"
                elif "vitest" in deps:
                    commands["test"] = "npx vitest run"

                if "build" in scripts:
                    commands["build"] = f"{run_cmd} build"

                if "lint" in scripts:
                    commands["lint"] = f"{run_cmd} lint"
                elif "eslint" in deps:
                    commands["lint"] = "npx eslint . --max-warnings=0"

                return "nodejs", framework, commands

            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")

        # Check for Python project
        if (
            os.path.exists(os.path.join(workspace_path, "pyproject.toml"))
            or os.path.exists(os.path.join(workspace_path, "setup.py"))
            or os.path.exists(os.path.join(workspace_path, "requirements.txt"))
        ):
            framework = "python"
            if os.path.exists(os.path.join(workspace_path, "manage.py")):
                framework = "django"
            elif os.path.exists(os.path.join(workspace_path, "app.py")):
                framework = "flask"

            commands["typecheck"] = (
                "python -m mypy . --ignore-missing-imports"
                if os.path.exists(os.path.join(workspace_path, "mypy.ini"))
                else None
            )
            commands["test"] = (
                "python -m pytest -x"
                if os.path.exists(os.path.join(workspace_path, "pytest.ini"))
                or os.path.exists(os.path.join(workspace_path, "tests"))
                else None
            )
            commands["lint"] = (
                "python -m ruff check ."
                if os.path.exists(os.path.join(workspace_path, "ruff.toml"))
                else None
            )

            return "python", framework, commands

        # Check for Go project
        if os.path.exists(os.path.join(workspace_path, "go.mod")):
            commands["build"] = "go build ./..."
            commands["test"] = "go test ./..."
            commands["lint"] = (
                "golangci-lint run"
                if os.path.exists(os.path.join(workspace_path, ".golangci.yml"))
                else None
            )
            return "go", "go", commands

        # Check for Rust project
        if os.path.exists(os.path.join(workspace_path, "Cargo.toml")):
            commands["build"] = "cargo build"
            commands["test"] = "cargo test"
            commands["lint"] = "cargo clippy"
            return "rust", "rust", commands

        return "unknown", "unknown", commands


# ======================================================================
# Verification Runner - Execute verification commands
# ======================================================================


@dataclass
class VerificationResult:
    """Result of a verification step."""

    verification_type: str
    success: bool
    output: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class VerificationRunner:
    """Runs verification commands and parses results."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def run_command(
        self, command: str, timeout: int = 120
    ) -> Tuple[bool, str, int]:
        """Run a command and return (success, output, exit_code)."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                output = stdout.decode("utf-8", errors="replace")
                return process.returncode == 0, output, process.returncode or 0
            except asyncio.TimeoutError:
                process.kill()
                return False, f"Command timed out after {timeout}s", -1

        except Exception as e:
            return False, str(e), -1

    async def run_verification(
        self, verification_type: str, command: str
    ) -> VerificationResult:
        """Run a verification command and parse the results."""
        success, output, _ = await self.run_command(command)

        errors = []
        warnings = []

        # Parse output for errors/warnings
        for line in output.split("\n"):
            line_lower = line.lower()
            if "error" in line_lower or "failed" in line_lower:
                errors.append(line.strip())
            elif "warning" in line_lower or "warn" in line_lower:
                warnings.append(line.strip())

        return VerificationResult(
            verification_type=verification_type,
            success=success,
            output=output[:5000],  # Limit output size
            errors=errors[:20],  # Limit error count
            warnings=warnings[:20],
        )

    async def verify_changes(
        self,
        commands: Dict[str, Optional[str]],
        run_tests: bool = False,  # Only run tests on explicit request
    ) -> List[VerificationResult]:
        """Run all applicable verification commands."""
        results = []

        # Always run typecheck if available (fast, catches most issues)
        if commands.get("typecheck"):
            result = await self.run_verification("typecheck", commands["typecheck"])
            results.append(result)
            # If typecheck fails badly, don't continue
            if not result.success and len(result.errors) > 10:
                return results

        # Run lint if available (fast)
        if commands.get("lint"):
            result = await self.run_verification("lint", commands["lint"])
            results.append(result)

        # Run tests if explicitly requested (can be slow)
        if run_tests and commands.get("test"):
            result = await self.run_verification("tests", commands["test"])
            results.append(result)

        # Run build if available and other checks passed
        if commands.get("build") and all(r.success for r in results):
            result = await self.run_verification("build", commands["build"])
            results.append(result)

        return results


# ======================================================================
# Tool Definitions (Anthropic format - converted for other providers)
# ======================================================================

NAVI_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace. Use this to understand code before making changes. Always read files before editing them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file from the workspace root",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: start line number (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional: end line number (1-indexed)",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create a new file or completely replace an existing file's contents. Use for creating new files or when you need to rewrite most of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path where to write the file",
                },
                "content": {
                    "type": "string",
                    "description": "The complete content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Make targeted edits to a file by replacing specific text. Use for small, precise changes to existing files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace (must match exactly)",
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace it with",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "run_command",
        "description": "Execute a shell command in the workspace. Use for running builds, tests, installs, git commands, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run (e.g., 'npm install', 'python test.py', 'git status')",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional: working directory relative to workspace root",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files matching a pattern or containing specific text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern for file names (e.g., '**/*.ts') or text to search for",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["filename", "content"],
                    "description": "Whether to search file names or file contents",
                },
            },
            "required": ["pattern", "search_type"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories in a path to understand project structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (relative to workspace root, use '.' for root)",
                }
            },
            "required": ["path"],
        },
    },
    # === PROCESS MANAGEMENT TOOLS ===
    # These enable handling ANY long-running process (servers, watchers, etc.)
    {
        "name": "run_background",
        "description": "Start a long-running command in background (dev servers, watchers, docker, etc.). Returns immediately with process_id. ALWAYS use this instead of run_command for: 'npm run dev', 'python app.py', 'docker-compose up', 'npm run watch', or ANY command that runs indefinitely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"},
                "env": {
                    "type": "object",
                    "description": "Optional environment variables (e.g., {'PORT': '3001'})",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "check_process",
        "description": "Check status of a background process. Returns running status, exit code, recent output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "The process ID returned by run_background",
                }
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "get_process_output",
        "description": "Get recent output/logs from a background process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string", "description": "The process ID"},
                "lines": {
                    "type": "integer",
                    "description": "Number of recent lines (default: 50)",
                },
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "kill_process",
        "description": "Kill/stop a background process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "The process ID to kill",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force kill with SIGKILL (default: false, uses SIGTERM)",
                },
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "verify_condition",
        "description": "Check if a condition is true. COMPREHENSIVE verification for ANY scenario: network, files, databases, containers, cloud, registries, services, resources. Use to VERIFY your work before reporting success.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_type": {
                    "type": "string",
                    "enum": [
                        "http",
                        "port",
                        "tcp",
                        "websocket",
                        "ssl",
                        "dns",
                        "ssh",
                        "ftp",
                        "smtp",
                        "ldap",
                        "file_exists",
                        "file_contains",
                        "process_running",
                        "command_succeeds",
                        "disk_space",
                        "memory_available",
                        "cpu_usage",
                        "env_var",
                        "database",
                        "elasticsearch",
                        "docker",
                        "docker_compose",
                        "kubernetes",
                        "queue",
                        "graphql",
                        "grpc",
                        "sse",
                        "api_response",
                        "json_schema",
                        "url_accessible",
                        "s3",
                        "npm_registry",
                        "docker_registry",
                        "git_remote",
                        "systemd_service",
                        "launchd_service",
                        "cron_job",
                        "network_interface",
                        "health_aggregate",
                    ],
                    "description": "Type of condition to check",
                },
                "url": {
                    "type": "string",
                    "description": "For http/websocket/graphql/sse: URL to check",
                },
                "port": {
                    "type": "integer",
                    "description": "For port/tcp/ssl/grpc: port number",
                },
                "host": {
                    "type": "string",
                    "description": "Hostname (default: localhost)",
                },
                "path": {
                    "type": "string",
                    "description": "For file_exists/file_contains/disk_space: path",
                },
                "pattern": {
                    "type": "string",
                    "description": "For file_contains/tcp/cron_job: regex pattern",
                },
                "name": {
                    "type": "string",
                    "description": "For process_running/env_var/kubernetes: name",
                },
                "command": {
                    "type": "string",
                    "description": "For command_succeeds: command to run",
                },
                "db_type": {
                    "type": "string",
                    "description": "For database: postgres, mysql, mongodb, redis",
                },
                "database": {
                    "type": "string",
                    "description": "For database: database name",
                },
                "user": {"type": "string", "description": "For database/ssh: username"},
                "password": {"type": "string", "description": "For database: password"},
                "container": {
                    "type": "string",
                    "description": "For docker: container name/id",
                },
                "service": {
                    "type": "string",
                    "description": "For docker_compose/systemd/launchd: service name",
                },
                "queue_type": {
                    "type": "string",
                    "description": "For queue: rabbitmq, kafka, redis, nats",
                },
                "hostname": {
                    "type": "string",
                    "description": "For dns: hostname to resolve",
                },
                "bucket": {"type": "string", "description": "For s3: bucket name"},
                "registry": {
                    "type": "string",
                    "description": "For npm/docker_registry: registry URL",
                },
                "resource_type": {
                    "type": "string",
                    "description": "For kubernetes: pod, deployment, service",
                },
                "namespace": {
                    "type": "string",
                    "description": "For kubernetes: namespace",
                },
                "min_free_gb": {
                    "type": "number",
                    "description": "For disk_space/memory: minimum free GB",
                },
                "max_used_percent": {
                    "type": "number",
                    "description": "For disk_space/memory/cpu: max used %",
                },
                "interface": {
                    "type": "string",
                    "description": "For network_interface: interface name",
                },
                "expected_status": {
                    "type": "integer",
                    "description": "For http/api_response: expected HTTP status",
                },
                "response_contains": {
                    "type": "string",
                    "description": "For api_response: expected text in response",
                },
                "checks": {
                    "type": "array",
                    "description": "For health_aggregate: list of checks to run",
                    "items": {
                        "type": "object",
                        "description": "Individual health check configuration",
                    },
                },
            },
            "required": ["condition_type"],
        },
    },
    {
        "name": "wait_for_condition",
        "description": "Wait for a condition to become true with configurable retry/backoff. Use after run_background to wait for server to start.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_type": {
                    "type": "string",
                    "enum": [
                        "http",
                        "port",
                        "tcp",
                        "websocket",
                        "file_exists",
                        "file_contains",
                        "process_running",
                        "command_succeeds",
                        "database",
                        "docker",
                        "docker_compose",
                        "kubernetes",
                        "elasticsearch",
                        "queue",
                    ],
                    "description": "Type of condition to wait for",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait (default: 30)",
                },
                "interval": {
                    "type": "number",
                    "description": "Seconds between checks (default: 1.0)",
                },
                "backoff": {
                    "type": "string",
                    "enum": ["none", "linear", "exponential"],
                    "description": "Retry backoff strategy (default: linear)",
                },
                "url": {"type": "string", "description": "For http: URL to wait for"},
                "port": {
                    "type": "integer",
                    "description": "For port: port to wait for",
                },
                "host": {
                    "type": "string",
                    "description": "Hostname (default: localhost)",
                },
                "path": {
                    "type": "string",
                    "description": "For file_exists: path to wait for",
                },
                "name": {
                    "type": "string",
                    "description": "For process_running/kubernetes: name",
                },
                "container": {
                    "type": "string",
                    "description": "For docker: container name",
                },
                "service": {
                    "type": "string",
                    "description": "For docker_compose: service name",
                },
            },
            "required": ["condition_type"],
        },
    },
    # === ADVANCED PROCESS MANAGEMENT ===
    {
        "name": "run_interactive",
        "description": "Run a command that requires stdin input (npm init, git rebase, npx create-*, etc). Automates expect/send pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"},
                "inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "expect": {
                                "type": "string",
                                "description": "Pattern to wait for in output",
                            },
                            "send": {
                                "type": "string",
                                "description": "Response to send",
                            },
                        },
                    },
                    "description": "Expect/send pairs for automation",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds (default: 60)",
                },
            },
            "required": ["command", "inputs"],
        },
    },
    {
        "name": "run_parallel",
        "description": "Run multiple commands in parallel, wait for all to complete. Use for concurrent lint, test, build, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "name": {
                                "type": "string",
                                "description": "Label for this command",
                            },
                        },
                        "required": ["command"],
                    },
                    "description": "Commands to run in parallel",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds for all (default: 300)",
                },
                "fail_fast": {
                    "type": "boolean",
                    "description": "Stop all on first failure (default: false)",
                },
            },
            "required": ["commands"],
        },
    },
    {
        "name": "wait_for_log_pattern",
        "description": "Wait for a specific pattern in process output. Use when HTTP check isn't the right signal (e.g., 'Database connected', 'Ready to accept connections').",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "Process ID to monitor",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to match in output",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait (default: 60)",
                },
            },
            "required": ["process_id", "pattern"],
        },
    },
    {
        "name": "cleanup_session",
        "description": "Kill all managed processes and clean up. Use when done with task or on error to ensure no orphan processes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only clean processes with these tags",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force kill with SIGKILL (default: false)",
                },
            },
        },
    },
    {
        "name": "list_processes",
        "description": "List all managed background processes with their status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "start_service_chain",
        "description": "Start multiple dependent services in order with health checks. Handles dependencies (e.g., db before backend before frontend).",
        "input_schema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Service name"},
                            "command": {
                                "type": "string",
                                "description": "Start command",
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Services this depends on",
                            },
                            "health_check": {
                                "type": "object",
                                "description": "Health check config (type, url, port, etc)",
                            },
                            "startup_timeout": {
                                "type": "integer",
                                "description": "Seconds to wait for health (default: 30)",
                            },
                        },
                        "required": ["name", "command"],
                    },
                }
            },
            "required": ["services"],
        },
    },
    {
        "name": "check_resources",
        "description": "Check CPU, memory, disk usage. For a specific process or system-wide.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "Check specific managed process",
                },
                "pid": {"type": "integer", "description": "Check specific PID"},
            },
        },
    },
    {
        "name": "run_with_environment",
        "description": "Run command with specific Node/Python/Ruby/Java version. Handles version managers (nvm, pyenv, rbenv, sdkman).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"},
                "env_type": {
                    "type": "string",
                    "enum": ["node", "python", "ruby", "java"],
                    "description": "Environment type",
                },
                "version": {
                    "type": "string",
                    "description": "Version (e.g., '18', '3.11')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds (default: 120)",
                },
            },
            "required": ["command", "env_type"],
        },
    },
    {
        "name": "run_oauth_flow",
        "description": "Run command that triggers browser OAuth (vercel login, gh auth login, firebase login). Monitors for success patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "CLI auth command"},
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds for auth (default: 300)",
                },
            },
            "required": ["command"],
        },
    },
]


# ======================================================================
# Event Types
# ======================================================================


class AgentEventType(Enum):
    """Types of events emitted by the agent."""

    THINKING = "thinking"  # Agent iteration started
    TEXT = "text"  # Text chunk from LLM
    TOOL_CALL = "tool_call"  # Tool being called
    TOOL_RESULT = "tool_result"  # Tool execution result
    ERROR = "error"  # Error occurred
    DONE = "done"  # Execution complete
    VERIFICATION = "verification"  # Verification started/completed
    FIXING = "fixing"  # Agent is fixing verification errors
    PHASE_CHANGE = "phase_change"  # Agent phase changed


@dataclass
class AgentEvent:
    """Event emitted during agent execution."""

    type: AgentEventType
    data: Any
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "sequence": self.sequence,
        }


# ======================================================================
# Agent Context
# ======================================================================


class AgentPhase(Enum):
    """Current phase of the agent."""

    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    FIXING = "fixing"
    COMPLETE = "complete"


@dataclass
class AgentContext:
    """Maintains context across the agentic loop."""

    task_id: str
    user_id: str
    workspace_path: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 25
    total_tokens: int = 0
    # Verification tracking
    phase: AgentPhase = AgentPhase.EXECUTING
    verification_results: List[VerificationResult] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    verification_attempts: int = 0
    max_verification_attempts: int = (
        3  # How many times to try fixing verification errors
    )
    # Project info
    project_type: str = "unknown"
    framework: str = "unknown"
    verification_commands: Dict[str, Optional[str]] = field(default_factory=dict)


# ======================================================================
# Tool Executor
# ======================================================================


class ToolExecutor:
    """Executes tools in the workspace."""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path).resolve()

    async def execute(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        name = tool_call.name
        args = tool_call.arguments

        try:
            if name == "read_file":
                return await self._read_file(args)
            elif name == "write_file":
                return await self._write_file(args)
            elif name == "edit_file":
                return await self._edit_file(args)
            elif name == "run_command":
                return await self._run_command(args)
            elif name == "search_files":
                return await self._search_files(args)
            elif name == "list_directory":
                return await self._list_directory(args)
            # Process management tools
            elif name == "run_background":
                return await self._run_background(args)
            elif name == "check_process":
                return await self._check_process(args)
            elif name == "get_process_output":
                return await self._get_process_output(args)
            elif name == "kill_process":
                return await self._kill_process(args)
            elif name == "verify_condition":
                return await self._verify_condition(args)
            elif name == "wait_for_condition":
                return await self._wait_for_condition(args)
            # Advanced process management tools
            elif name == "run_interactive":
                return await self._run_interactive(args)
            elif name == "run_parallel":
                return await self._run_parallel(args)
            elif name == "wait_for_log_pattern":
                return await self._wait_for_log_pattern(args)
            elif name == "cleanup_session":
                return await self._cleanup_session(args)
            elif name == "list_processes":
                return await self._list_processes(args)
            elif name == "start_service_chain":
                return await self._start_service_chain(args)
            elif name == "check_resources":
                return await self._check_resources(args)
            elif name == "run_with_environment":
                return await self._run_with_environment(args)
            elif name == "run_oauth_flow":
                return await self._run_oauth_flow(args)
            else:
                return {"error": f"Unknown tool: {name}", "success": False}
        except Exception as e:
            logger.error(f"Tool execution error ({name}): {e}")
            return {"error": str(e), "success": False}

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path to absolute, ensuring it's within workspace."""
        # Handle absolute paths by making them relative
        if relative_path.startswith("/"):
            relative_path = relative_path.lstrip("/")

        full_path = (self.workspace_path / relative_path).resolve()

        # Security check: ensure path is within workspace
        try:
            full_path.relative_to(self.workspace_path)
        except ValueError:
            raise ValueError(f"Path '{relative_path}' is outside workspace")

        return full_path

    async def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read file contents."""
        path = self._resolve_path(args["path"])

        if not path.exists():
            return {"error": f"File not found: {args['path']}", "success": False}

        if not path.is_file():
            return {"error": f"Not a file: {args['path']}", "success": False}

        try:
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Handle line ranges
            start_line = args.get("start_line", 1)
            end_line = args.get("end_line", len(lines))

            # Convert to 0-indexed
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            selected_lines = lines[start_idx:end_idx]

            # Add line numbers
            numbered_content = "\n".join(
                f"{i + start_line}: {line}" for i, line in enumerate(selected_lines)
            )

            return {
                "content": numbered_content,
                "path": args["path"],
                "lines": len(selected_lines),
                "total_lines": len(lines),
                "success": True,
            }
        except Exception as e:
            return {"error": f"Error reading file: {e}", "success": False}

    async def _write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write content to a file."""
        path = self._resolve_path(args["path"])
        content = args["content"]

        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            path.write_text(content, encoding="utf-8")

            return {
                "message": f"Successfully wrote {len(content)} characters to {args['path']}",
                "path": args["path"],
                "size": len(content),
                "success": True,
            }
        except Exception as e:
            return {"error": f"Error writing file: {e}", "success": False}

    async def _edit_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit a file by replacing text."""
        path = self._resolve_path(args["path"])
        old_text = args["old_text"]
        new_text = args["new_text"]

        if not path.exists():
            return {"error": f"File not found: {args['path']}", "success": False}

        try:
            content = path.read_text(encoding="utf-8")

            if old_text not in content:
                return {
                    "error": "Text to replace not found in file. Make sure old_text matches exactly.",
                    "success": False,
                }

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return {
                    "error": f"Found {count} occurrences of old_text. Please provide more context to make it unique.",
                    "success": False,
                }

            # Replace
            new_content = content.replace(old_text, new_text)
            path.write_text(new_content, encoding="utf-8")

            return {
                "message": f"Successfully edited {args['path']}",
                "path": args["path"],
                "success": True,
            }
        except Exception as e:
            return {"error": f"Error editing file: {e}", "success": False}

    async def _run_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run a shell command."""
        command = args["command"]
        cwd = args.get("cwd", ".")

        work_dir = self._resolve_path(cwd) if cwd else self.workspace_path

        # Security: Block dangerous commands
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf ~",
            ":(){ :|:& };:",  # Fork bomb
            "mkfs",
            "dd if=",
            "> /dev/sd",
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                return {
                    "error": f"Blocked dangerous command pattern: {pattern}",
                    "success": False,
                }

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Timeout after 120 seconds
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=120.0
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "error": "Command timed out after 120 seconds",
                    "success": False,
                }

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # Truncate long output
            max_output = 10000
            if len(stdout_text) > max_output:
                stdout_text = (
                    stdout_text[:max_output]
                    + f"\n... (truncated, {len(stdout_text)} total chars)"
                )
            if len(stderr_text) > max_output:
                stderr_text = (
                    stderr_text[:max_output]
                    + f"\n... (truncated, {len(stderr_text)} total chars)"
                )

            success = process.returncode == 0
            message = format_command_message(command, success, stdout_text, stderr_text)

            return {
                "command": command,
                "exit_code": process.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "success": success,
                "message": message,
            }
        except Exception as e:
            return {"error": f"Error running command: {e}", "success": False}

    async def _search_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for files."""
        pattern = args["pattern"]
        search_type = args.get("search_type", "filename")

        try:
            if search_type == "filename":
                # Glob search
                matches = list(self.workspace_path.glob(pattern))
                # Convert to relative paths
                results = [
                    str(m.relative_to(self.workspace_path)) for m in matches[:100]
                ]
                return {
                    "matches": results,
                    "count": len(matches),
                    "truncated": len(matches) > 100,
                    "success": True,
                }
            else:
                # Content search using grep
                process = await asyncio.create_subprocess_exec(
                    "grep",
                    "-r",
                    "-l",
                    "--include=*",
                    pattern,
                    ".",
                    cwd=str(self.workspace_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)
                files = [
                    f.strip() for f in stdout.decode().strip().split("\n") if f.strip()
                ]
                return {
                    "matches": files[:100],
                    "count": len(files),
                    "truncated": len(files) > 100,
                    "success": True,
                }
        except Exception as e:
            return {"error": f"Error searching: {e}", "success": False}

    async def _list_directory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents."""
        dir_path = self._resolve_path(args.get("path", "."))

        if not dir_path.exists():
            return {
                "error": f"Directory not found: {args.get('path', '.')}",
                "success": False,
            }

        if not dir_path.is_dir():
            return {
                "error": f"Not a directory: {args.get('path', '.')}",
                "success": False,
            }

        try:
            items = []
            for item in sorted(dir_path.iterdir()):
                # Skip hidden files and common ignore patterns
                if item.name.startswith(".") or item.name in (
                    "node_modules",
                    "__pycache__",
                    "venv",
                    ".git",
                ):
                    continue

                rel_path = str(item.relative_to(self.workspace_path))
                if item.is_dir():
                    items.append(f"{rel_path}/")
                else:
                    size = item.stat().st_size
                    items.append(f"{rel_path} ({size} bytes)")

            return {
                "path": args.get("path", "."),
                "items": items[:100],
                "count": len(items),
                "success": True,
            }
        except Exception as e:
            return {"error": f"Error listing directory: {e}", "success": False}

    # ====== PROCESS MANAGEMENT TOOLS ======
    # These enable handling ANY long-running process generically

    async def _run_background(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Start a command in background and return immediately."""
        from backend.services.process_manager import ProcessManager

        command = args["command"]
        env = args.get("env")

        # Get or create process manager
        pm = ProcessManager()

        result = await pm.start_background(
            command=command, working_dir=str(self.workspace_path), env=env
        )

        return result

    async def _check_process(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of a background process."""
        from backend.services.process_manager import ProcessManager

        process_id = args["process_id"]
        pm = ProcessManager()

        return await pm.check_process(process_id)

    async def _get_process_output(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent output from a background process."""
        from backend.services.process_manager import ProcessManager

        process_id = args["process_id"]
        lines = args.get("lines", 50)
        pm = ProcessManager()

        return await pm.get_output(process_id, lines)

    async def _kill_process(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Kill a background process."""
        from backend.services.process_manager import ProcessManager

        process_id = args["process_id"]
        force = args.get("force", False)
        pm = ProcessManager()

        signal_type = "KILL" if force else "TERM"
        return await pm.kill_process(process_id, signal_type)

    async def _verify_condition(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if a condition is true - extensible verification.

        Uses the condition registry which supports:
        - 100+ built-in conditions
        - Custom patterns from YAML/JSON config
        - Dynamic service detection
        - Plugin-based extensibility
        """
        try:
            from backend.services.condition_registry import verify_condition
        except ImportError:
            # Fallback to legacy implementation
            from backend.services.process_manager import verify_condition

        condition_type = args["condition_type"]

        # Build kwargs from args
        kwargs = {
            k: v for k, v in args.items() if k != "condition_type" and v is not None
        }

        # For file operations, resolve paths relative to workspace
        if "path" in kwargs and not kwargs["path"].startswith("/"):
            kwargs["path"] = str(self.workspace_path / kwargs["path"])
        if "working_dir" in kwargs and not kwargs["working_dir"].startswith("/"):
            kwargs["working_dir"] = str(self.workspace_path / kwargs["working_dir"])
        elif "working_dir" not in kwargs and condition_type == "command_succeeds":
            kwargs["working_dir"] = str(self.workspace_path)

        return await verify_condition(condition_type, **kwargs)

    async def _wait_for_condition(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wait for a condition to become true with retry.

        Uses the extensible condition registry for maximum flexibility.
        """
        try:
            from backend.services.condition_registry import wait_for_condition
        except ImportError:
            from backend.services.process_manager import wait_for_condition

        condition_type = args["condition_type"]
        timeout = args.get("timeout", 30)
        interval = args.get("interval", 1.0)

        # Build kwargs from args
        kwargs = {
            k: v
            for k, v in args.items()
            if k not in ["condition_type", "timeout", "interval"] and v is not None
        }

        # For file operations, resolve paths relative to workspace
        if "path" in kwargs and not kwargs["path"].startswith("/"):
            kwargs["path"] = str(self.workspace_path / kwargs["path"])

        return await wait_for_condition(
            condition_type, timeout=timeout, interval=interval, **kwargs
        )

    async def _run_interactive(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run interactive command with expect/send automation."""
        from backend.services.process_manager import ProcessManager

        pm = ProcessManager()
        return await pm.run_interactive(
            command=args["command"],
            working_dir=str(self.workspace_path),
            inputs=args["inputs"],
            timeout=args.get("timeout", 60),
        )

    async def _run_parallel(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run multiple commands in parallel."""
        from backend.services.process_manager import ProcessManager

        pm = ProcessManager()
        return await pm.run_parallel(
            commands=args["commands"],
            working_dir=str(self.workspace_path),
            timeout=args.get("timeout", 300),
            fail_fast=args.get("fail_fast", False),
        )

    async def _wait_for_log_pattern(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for pattern in process output."""
        from backend.services.process_manager import ProcessManager

        pm = ProcessManager()
        return await pm.wait_for_log_pattern(
            process_id=args["process_id"],
            pattern=args["pattern"],
            timeout=args.get("timeout", 60),
        )

    async def _cleanup_session(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up all managed processes."""
        from backend.services.process_manager import ProcessManager

        pm = ProcessManager()
        return await pm.cleanup_session(
            tags=args.get("tags"), force=args.get("force", False)
        )

    async def _list_processes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all managed processes."""
        from backend.services.process_manager import ProcessManager

        pm = ProcessManager()
        return await pm.list_processes()

    async def _start_service_chain(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Start multiple dependent services."""
        from backend.services.process_manager import start_service_chain

        return await start_service_chain(
            services=args["services"], working_dir=str(self.workspace_path)
        )

    async def _check_resources(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check CPU, memory, disk usage."""
        from backend.services.process_manager import check_resources

        return await check_resources(
            process_id=args.get("process_id"), pid=args.get("pid")
        )

    async def _run_with_environment(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run command with specific environment."""
        from backend.services.process_manager import run_with_environment

        return await run_with_environment(
            command=args["command"],
            working_dir=str(self.workspace_path),
            env_type=args["env_type"],
            version=args.get("version"),
            timeout=args.get("timeout", 120),
        )

    async def _run_oauth_flow(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OAuth/browser authentication flow."""
        from backend.services.process_manager import run_oauth_flow

        return await run_oauth_flow(
            command=args["command"],
            working_dir=str(self.workspace_path),
            timeout=args.get("timeout", 300),
        )


# ======================================================================
# Unified Agent
# ======================================================================


class UnifiedAgent:
    """
    The main agentic loop that powers NAVI.

    Flow:
    1. User message -> Build context
    2. Send to LLM with tools
    3. If LLM returns tool_calls:
       a. Execute each tool
       b. Append results to context
       c. Send back to LLM
       d. Repeat until LLM says "done" or max iterations
    4. Stream events throughout
    """

    def __init__(
        self,
        provider: str = "anthropic",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        max_iterations: int = 25,
    ):
        self.provider = provider
        self.model = model or self._get_default_model(provider)
        self.api_key = api_key
        self.max_iterations = max_iterations
        self.router = LLMRouter(timeout_sec=120, max_retries=2)

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            "openai": os.environ.get("OPENAI_MODEL", "gpt-4o"),
            "groq": "llama-3.3-70b-versatile",
            "google": "gemini-1.5-pro",
        }
        return defaults.get(provider, "gpt-4o")

    async def run(
        self,
        message: str,
        workspace_path: str,
        user_id: str = "anonymous",
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        project_context: Optional[Dict] = None,
        run_verification: bool = True,
        run_tests: bool = False,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        Main entry point - runs the agentic loop with verification and self-healing.

        Args:
            message: User's request
            workspace_path: Path to the workspace
            user_id: User identifier
            system_prompt: Optional custom system prompt
            conversation_history: Previous conversation messages
            project_context: Project metadata
            run_verification: Whether to run verification after changes
            run_tests: Whether to include tests in verification

        Yields:
            AgentEvent objects for thinking, tool_call, tool_result, text,
            verification, fixing, done, error
        """
        # Detect project type and verification commands
        (
            project_type,
            framework,
            verification_commands,
        ) = ProjectAnalyzer.detect_project_type(workspace_path)

        ctx = AgentContext(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_path=workspace_path,
            max_iterations=self.max_iterations,
            project_type=project_type,
            framework=framework,
            verification_commands=verification_commands,
        )

        logger.info(
            f"[Agent] Project: {project_type}/{framework}, Verification: {verification_commands}"
        )

        # Build system prompt with project awareness
        if project_context is None:
            project_context = {}
        project_context["project_type"] = project_type
        project_context["framework"] = framework

        full_system = self._build_system_prompt(system_prompt, project_context)

        # Build initial messages
        if conversation_history:
            for msg in conversation_history[-10:]:  # Keep last 10 messages
                ctx.messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )

        # Add user message
        ctx.messages.append({"role": "user", "content": message})

        # Tool executor and verification runner
        executor = ToolExecutor(workspace_path)
        verifier = VerificationRunner(workspace_path) if run_verification else None

        sequence = 0
        files_modified_this_iteration = []

        # Main agentic loop
        while ctx.iteration < ctx.max_iterations:
            ctx.iteration += 1
            ctx.phase = AgentPhase.EXECUTING
            files_modified_this_iteration = []

            yield AgentEvent(
                AgentEventType.THINKING,
                {
                    "iteration": ctx.iteration,
                    "phase": ctx.phase.value,
                    "message": f"Thinking... (iteration {ctx.iteration}/{ctx.max_iterations})",
                },
                sequence,
            )
            sequence += 1

            try:
                # Call LLM with tools
                response = await self.router.run(
                    prompt=message,  # Original message for context
                    model=self.model,
                    provider=self.provider,
                    system_prompt=full_system,
                    api_key=self.api_key,
                    tools=NAVI_TOOLS,
                    messages=ctx.messages,
                    max_tokens=4096,
                    temperature=0.1,
                )

                # Track token usage
                if response.tokens_used:
                    ctx.total_tokens += response.tokens_used

                # Yield any text content
                if response.text:
                    yield AgentEvent(AgentEventType.TEXT, response.text, sequence)
                    sequence += 1

                # Check if LLM wants to call tools
                if response.tool_calls:
                    # Add assistant message with tool calls to context
                    ctx.messages.append(self._format_assistant_message(response))

                    tool_results = []

                    # Execute each tool
                    for tool_call in response.tool_calls:
                        yield AgentEvent(
                            AgentEventType.TOOL_CALL,
                            {
                                "id": tool_call.id,
                                "name": tool_call.name,
                                "arguments": tool_call.arguments,
                            },
                            sequence,
                        )
                        sequence += 1

                        # Execute the tool
                        result = await executor.execute(tool_call)

                        yield AgentEvent(
                            AgentEventType.TOOL_RESULT,
                            {
                                "id": tool_call.id,
                                "name": tool_call.name,
                                "result": result,
                            },
                            sequence,
                        )
                        sequence += 1

                        # Track what was done
                        self._track_tool_usage(tool_call, result, ctx)

                        # Track files modified this iteration for verification
                        if tool_call.name in ("write_file", "edit_file") and result.get(
                            "success"
                        ):
                            files_modified_this_iteration.append(
                                tool_call.arguments.get("path", "")
                            )

                        tool_results.append(
                            {
                                "tool_use_id": tool_call.id,
                                "result": result,
                            }
                        )

                    # Add tool results to messages
                    ctx.messages.append(
                        self._format_tool_results(response.tool_calls, tool_results)
                    )

                    # Continue loop - LLM will process results
                    continue

                # No tool calls - LLM thinks it's done
                # But we need to verify if files were modified
                if response.text:
                    ctx.messages.append({"role": "assistant", "content": response.text})

                # ============================================================
                # VERIFICATION PHASE - The key to end-to-end reliability
                # ============================================================
                if (
                    run_verification
                    and (ctx.files_modified or ctx.files_created)
                    and verifier
                ):
                    ctx.phase = AgentPhase.VERIFYING

                    yield AgentEvent(
                        AgentEventType.PHASE_CHANGE,
                        {"phase": "verifying", "message": "Running verification..."},
                        sequence,
                    )
                    sequence += 1

                    yield AgentEvent(
                        AgentEventType.VERIFICATION,
                        {
                            "status": "running",
                            "commands": {
                                k: v for k, v in ctx.verification_commands.items() if v
                            },
                        },
                        sequence,
                    )
                    sequence += 1

                    # Run verification
                    verification_results = await verifier.verify_changes(
                        ctx.verification_commands, run_tests=run_tests
                    )
                    ctx.verification_results = verification_results

                    # Check if all passed
                    all_passed = all(r.success for r in verification_results)

                    yield AgentEvent(
                        AgentEventType.VERIFICATION,
                        {
                            "status": "complete",
                            "success": all_passed,
                            "results": [
                                {
                                    "type": r.verification_type,
                                    "success": r.success,
                                    "errors": r.errors[:5],
                                    "output": r.output[:1000] if not r.success else "",
                                }
                                for r in verification_results
                            ],
                        },
                        sequence,
                    )
                    sequence += 1

                    if not all_passed:
                        # Verification failed - enter self-healing loop
                        ctx.verification_attempts += 1

                        if ctx.verification_attempts < ctx.max_verification_attempts:
                            ctx.phase = AgentPhase.FIXING

                            yield AgentEvent(
                                AgentEventType.FIXING,
                                {
                                    "attempt": ctx.verification_attempts,
                                    "max_attempts": ctx.max_verification_attempts,
                                    "message": "Verification failed. Analyzing errors and fixing...",
                                },
                                sequence,
                            )
                            sequence += 1

                            # Build error context for LLM
                            error_details = []
                            for r in verification_results:
                                if not r.success:
                                    ctx.error_history.append(
                                        {
                                            "type": r.verification_type,
                                            "errors": r.errors[:5],
                                            "iteration": ctx.iteration,
                                        }
                                    )
                                    error_details.append(
                                        f"**{r.verification_type}** failed:\n```\n{r.output[:2000]}\n```"
                                    )

                            error_message = "\n\n".join(error_details)

                            # Add error context to messages for LLM to fix
                            ctx.messages.append(
                                {
                                    "role": "user",
                                    "content": f"""Verification failed. Here are the errors:

{error_message}

Please analyze these errors and fix them. This is verification attempt {ctx.verification_attempts} of {ctx.max_verification_attempts}.

Fix the issues in the code. After you fix them, I'll run verification again.""",
                                }
                            )

                            # Continue loop - LLM will try to fix
                            continue
                        else:
                            # Max verification attempts reached
                            yield AgentEvent(
                                AgentEventType.TEXT,
                                f"\n\n⚠️ **Max verification attempts ({ctx.max_verification_attempts}) reached.** Some issues may remain.\n",
                                sequence,
                            )
                            sequence += 1
                    else:
                        # All verification passed!
                        yield AgentEvent(
                            AgentEventType.TEXT,
                            "\n\n✅ **All verifications passed!**\n",
                            sequence,
                        )
                        sequence += 1

                # Done!
                ctx.phase = AgentPhase.COMPLETE

                yield AgentEvent(
                    AgentEventType.DONE,
                    {
                        "task_id": ctx.task_id,
                        "iterations": ctx.iteration,
                        "files_read": ctx.files_read,
                        "files_modified": ctx.files_modified,
                        "files_created": ctx.files_created,
                        "commands_run": ctx.commands_run,
                        "total_tokens": ctx.total_tokens,
                        "verification_passed": (
                            all(r.success for r in ctx.verification_results)
                            if ctx.verification_results
                            else None
                        ),
                        "verification_attempts": ctx.verification_attempts,
                    },
                    sequence,
                )
                return

            except Exception as e:
                logger.error(f"[Agent] Error in iteration {ctx.iteration}: {e}")
                yield AgentEvent(
                    AgentEventType.ERROR,
                    {
                        "error": str(e),
                        "iteration": ctx.iteration,
                    },
                    sequence,
                )
                sequence += 1

                # Try to recover by continuing
                if ctx.iteration < ctx.max_iterations:
                    ctx.error_history.append(
                        {
                            "type": "execution_error",
                            "errors": [str(e)],
                            "iteration": ctx.iteration,
                        }
                    )
                    ctx.messages.append(
                        {
                            "role": "user",
                            "content": f"An error occurred: {e}. Please try a different approach.",
                        }
                    )
                    continue
                return

        # Max iterations reached
        yield AgentEvent(
            AgentEventType.DONE,
            {
                "task_id": ctx.task_id,
                "iterations": ctx.iteration,
                "max_iterations_reached": True,
                "files_read": ctx.files_read,
                "files_modified": ctx.files_modified,
                "files_created": ctx.files_created,
                "commands_run": ctx.commands_run,
                "verification_passed": (
                    all(r.success for r in ctx.verification_results)
                    if ctx.verification_results
                    else None
                ),
            },
            sequence,
        )

    def _track_tool_usage(self, tool_call: ToolCall, result: Dict, ctx: AgentContext):
        """Track what tools were used for summary."""
        name = tool_call.name
        args = tool_call.arguments

        if name == "read_file":
            path = args.get("path", "")
            if path and path not in ctx.files_read:
                ctx.files_read.append(path)
        elif name == "write_file":
            path = args.get("path", "")
            if path and result.get("success"):
                # Check if it was a creation or modification
                if (
                    "created" in result.get("message", "").lower()
                    or path not in ctx.files_read
                ):
                    if path not in ctx.files_created:
                        ctx.files_created.append(path)
                else:
                    if path not in ctx.files_modified:
                        ctx.files_modified.append(path)
        elif name == "edit_file":
            path = args.get("path", "")
            if path and path not in ctx.files_modified and result.get("success"):
                ctx.files_modified.append(path)
        elif name == "run_command":
            cmd = args.get("command", "")
            if cmd:
                ctx.commands_run.append(cmd)

    def _format_assistant_message(self, response: LLMResponse) -> Dict[str, Any]:
        """Format assistant message with tool calls for context."""
        if self.provider == "anthropic":
            content = []
            if response.text:
                content.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            return {"role": "assistant", "content": content}
        else:
            # OpenAI format
            msg = {
                "role": "assistant",
                "content": response.text or None,
            }
            if response.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
            return msg

    def _format_tool_results(
        self, tool_calls: List[ToolCall], results: List[Dict]
    ) -> Dict[str, Any]:
        """Format tool results for next LLM call."""
        if self.provider == "anthropic":
            content = []
            for tc, res in zip(tool_calls, results):
                content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(res.get("result", {})),
                    }
                )
            return {"role": "user", "content": content}
        else:
            # OpenAI format - return list of tool messages
            # Note: For OpenAI, tool results are separate messages
            # We return a single dict but the router should handle this
            return {
                "role": "tool",
                "tool_call_id": tool_calls[0].id if tool_calls else "",
                "content": json.dumps(results[0].get("result", {}) if results else {}),
            }

    def _build_system_prompt(
        self,
        custom_prompt: Optional[str],
        project_context: Optional[Dict],
    ) -> str:
        """Build the system prompt with context."""

        base_prompt = """You are NAVI, an autonomous AI SOFTWARE ENGINEER that solves ANY problem.

## Your Mission
You are not just a coding assistant - you are a FULL SOFTWARE ENGINEER.
You handle EVERYTHING: code, git, databases, servers, DevOps, architecture, debugging, deployment.
When users ask you to do something, you DO IT. When something fails, you FIX IT.
NEVER stop to ask permission. NEVER just explain. ALWAYS take action.

## Your Scope - UNLIMITED
You solve ANY software engineering problem:

**Code**: Any language, any framework, any build system, any package manager
**Git**: Merge conflicts, rebases, branches, remotes, submodules, history
**Servers**: Startup, ports, processes, configs, logs, health checks
**Databases**: Connections, migrations, queries, schemas, backups, any DB
**DevOps**: Docker, Kubernetes, CI/CD, cloud CLIs, Terraform, secrets
**Architecture**: APIs, performance, security, scaling, refactoring
**Environment**: Version managers, PATH, permissions, shell config, OS specifics

## Tools Available

### File Operations
- **read_file**: Read any file (code, config, logs)
- **write_file**: Create or replace files
- **edit_file**: Make targeted edits
- **search_files**: Find files by pattern or content
- **list_directory**: Explore structure

### Command Execution
- **run_command**: Short-lived commands that finish quickly (build, test, install, git)
- **run_background**: Long-running processes that run indefinitely (dev servers, watchers, docker)

### Process Management (CRITICAL FOR SERVERS!)
- **run_background**: Start server/watcher in background → returns process_id
- **check_process**: Check if process is running, get recent output
- **get_process_output**: Get logs from background process
- **kill_process**: Stop a background process
- **verify_condition**: Check if something is working (HTTP responds, port open, file exists)
- **wait_for_condition**: Wait for something to become true (server to start, file to appear)

## CRITICAL: How to Start Servers

**NEVER use run_command for: npm run dev, python app.py, docker-compose up, npm run watch**
These run FOREVER and will timeout!

**CORRECT pattern for starting any server:**
1. `run_background` command="npm run dev" → get process_id
2. `wait_for_condition` condition_type="http" url="http://localhost:3000" timeout=30
3. If wait succeeds → "Server running and verified!"
4. If wait fails → `get_process_output` to see error logs → fix the issue → retry

**Example:**
```
User: "Start the dev server"
You: Starting server in background...
     run_background: npm run dev → process_id: proc_abc123
     Waiting for server to respond...
     wait_for_condition: http, url=http://localhost:3000
     ✓ Server running and responding at localhost:3000!
```

## How You Work

1. **DO IT**: When asked to do something, USE YOUR TOOLS
   - "Run the project" → run_background + wait_for_condition (NOT run_command!)
   - "Fix the bug" → read_file, then edit_file
   - "Resolve merge conflict" → git commands
   - "Fix database" → check connection, run migrations
   - "Check if server is running" → verify_condition

2. **READ BEFORE WRITE**: Always understand before changing

3. **HANDLE ANY FAILURE**:
   When ANYTHING fails:
   - ANALYZE the error output
   - DIAGNOSE with more commands if needed
   - FIX IT immediately

   **YOUR MINDSET:**
   - Error = Problem to solve NOW
   - Failure = Try different approach
   - Unknown = Investigate then fix

   **NEVER SAY:**
   - "Would you like me to..."
   - "You need to..."
   - "You should try..."
   - "Here's what went wrong..."

   **ALWAYS SAY:**
   - "Failed. Fixing..." [then fix]
   - "Error. Trying alternative..." [then try]
   - "Found issue. Fixing now..." [then fix]

4. **ITERATE**: Try multiple approaches until success

5. **ALWAYS VERIFY YOUR WORK**:
   - After starting server: verify_condition http to confirm it responds
   - After editing file: run tests/build to confirm it works
   - After fixing bug: run the failing test to confirm it passes
   - NEVER say "done" or ask user to check - VERIFY IT YOURSELF

## Response Style
Brief, action-oriented:
- "Reading config..."
- "Found issue - missing dep. Installing..."
- "Port blocked. Killing process..."
- "Migration failed. Rolling back..."
- "Done! Summary: [what you did]"
"""

        if custom_prompt:
            base_prompt = custom_prompt + "\n\n" + base_prompt

        if project_context:
            context_str = self._format_project_context(project_context)
            base_prompt += f"\n\n## Project Context\n{context_str}"

        return base_prompt

    def _format_project_context(self, ctx: Dict) -> str:
        """Format project context for system prompt."""
        parts = []
        if ctx.get("project_name"):
            parts.append(f"Project: {ctx['project_name']}")
        if ctx.get("project_type"):
            parts.append(f"Type: {ctx['project_type']}")
        if ctx.get("framework"):
            parts.append(f"Framework: {ctx['framework']}")
        if ctx.get("language"):
            parts.append(f"Language: {ctx['language']}")
        return "\n".join(parts)


# ======================================================================
# Convenience Function
# ======================================================================


async def run_agent(
    message: str,
    workspace_path: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    Convenience function to run the unified agent.

    Usage:
        async for event in run_agent("Create a hello world", "/path/to/workspace"):
            print(event.type, event.data)
    """
    agent = UnifiedAgent(provider=provider, model=model, api_key=api_key)

    async for event in agent.run(
        message=message,
        workspace_path=workspace_path,
        conversation_history=conversation_history,
    ):
        yield event
