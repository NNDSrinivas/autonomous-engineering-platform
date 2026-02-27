"""
Streaming Agent for NAVI - Claude Code Style

This implements a tool-use based streaming model where the LLM:
1. Explains what it's doing in natural language
2. Calls tools inline (read_file, edit_file, run_command)
3. Continues explaining based on tool results

The stream interleaves:
- Text chunks (narrative explanation)
- Tool calls (actions being taken)
- Tool results (outcomes)

This matches Claude Code's conversational style where the AI talks through
what it's doing while actually doing it.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional

# Session memory for conversation context

logger = logging.getLogger(__name__)


# Give-up detection patterns - LLM responses that indicate premature termination
GIVE_UP_PATTERNS = [
    r"I was unable to",
    r"I couldn'?t",
    r"I encountered several issues",
    r"Here'?s a summary",
    r"manual intervention",
    r"you can try",
    r"you might want to",
    r"I suggest",
    r"please check",
    r"you may need to",
    r"unfortunately",
    r"I'?m unable to",
    r"could not complete",
    r"failed to complete",
    # Patterns for giving manual instructions instead of executing
    r"try running",
    r"you should run",
    r"run the following",
    r"you need to run",
    r"execute the following",
    r"you can run",
    r"you'll need to",
    r"you would need to",
    r"here's how",
    r"here is how",
    r"steps to follow",
    r"follow these steps",
    r"Then,.*:",  # "Then, start the development server:" pattern
]


def is_giving_up(text: str, max_retries: int = 3, retry_count: int = 0) -> bool:
    """
    Detect if the LLM is giving up instead of persisting.
    Returns True if give-up patterns are detected and we haven't exceeded max retries.
    """
    if retry_count >= max_retries:
        return False  # Don't force retry indefinitely

    text_lower = text.lower()
    for pattern in GIVE_UP_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.info(f"[StreamingAgent] Give-up pattern detected: {pattern}")
            return True
    return False


FORCE_CONTINUE_MESSAGE = """DO NOT GIVE UP. You have more tool calls available.

You said you would try 5-10 DIFFERENT alternatives before stopping. Try a COMPLETELY DIFFERENT approach now.

What else can you try? Use a different tool, different command, different strategy.
DO NOT output a summary or suggest manual steps. TAKE ACTION with your tools."""


# ========== EXECUTION PLAN DETECTION ==========
# Regex patterns to detect when LLM outputs a numbered execution plan
# This enables the visual step-by-step progress UI in the frontend

# Matches phrases that introduce a plan followed by numbered steps
PLAN_INTRO_PATTERN = re.compile(
    r"(?:let'?s|I'?ll|I will|here'?s|proceed|steps?|following steps)[^:]*:\s*\n?"
    r"((?:\s*\d+[\.\)]\s*\*{0,2}[^\n]+\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)

# Extracts individual steps: number, title, and optional detail after colon
STEP_PATTERN = re.compile(
    r"(\d+)[\.\)]\s*\*{0,2}([^:\*\n]+?)\*{0,2}(?:[:\s]+([^\n]*))?$", re.MULTILINE
)


def parse_execution_plan(text: str) -> Optional[Dict[str, Any]]:
    """
    Execution plan parsing is disabled.

    Always returns None. Execution plans caused phantom "All steps completed" issues
    where the LLM would list steps it didn't actually execute. We now only show
    actual tool executions as they happen, not predicted plans.

    Note: PLAN_INTRO_PATTERN and STEP_PATTERN regex patterns are preserved above
    for potential future re-enablement via feature flag.
    """
    return None


# ========== BUILD VERIFICATION ==========
# Automatically verify builds after task completion to ensure code quality


def _get_command_env() -> dict:
    """
    Get environment for command execution with nvm compatibility fixes.
    Removes npm_config_prefix which conflicts with nvm.
    """
    env = os.environ.copy()
    env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
    env["SHELL"] = env.get("SHELL", "/bin/bash")
    return env


def _get_node_env_setup(workspace_path: str) -> str:
    """Get Node.js environment setup commands for nvm."""
    home = os.environ.get("HOME", os.path.expanduser("~"))
    nvm_dir = os.environ.get("NVM_DIR", os.path.join(home, ".nvm"))

    if os.path.exists(os.path.join(nvm_dir, "nvm.sh")):
        # Check for .nvmrc in workspace
        nvmrc_path = os.path.join(workspace_path, ".nvmrc")
        node_version_path = os.path.join(workspace_path, ".node-version")
        if os.path.exists(nvmrc_path) or os.path.exists(node_version_path):
            nvm_use = "nvm use 2>/dev/null || nvm install 2>/dev/null"
        else:
            nvm_use = "nvm use default 2>/dev/null || true"

        return (
            f"unset npm_config_prefix 2>/dev/null; "
            f'export NVM_DIR="{nvm_dir}" && '
            f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use 2>/dev/null && '
            f"{nvm_use}"
        )
    return ""


async def stream_with_tools_openai(
    message: str,
    workspace_path: str,
    api_key: str,
    model: str,
    base_url: str = "https://api.openai.com/v1",
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    provider: str = "openai",
) -> AsyncGenerator["StreamEvent", None]:
    """
    Minimal streaming implementation for OpenAI-compatible providers.
    Emits text chunks as StreamEventType.TEXT to keep the V2 endpoint functional.
    """
    from backend.services.llm_client import LLMClient, LLMMessage
    from backend.services.model_router import get_model_router

    if not api_key:
        yield StreamEvent(
            StreamEventType.DONE, {"summary": {}, "error": "Missing API key"}
        )
        return

    system_prompt = "You are NAVI, an autonomous engineering assistant."
    if context:
        system_prompt += "\n\nContext:\n" + json.dumps(context, ensure_ascii=False)

    messages: List[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role") or msg.get("type") or "user"
            content = str(msg.get("content") or "")
            messages.append(LLMMessage(role=role, content=content))
    messages.append(LLMMessage(role="user", content=message))

    # For health tracking, use actual provider
    # For adapter compatibility, normalize self_hosted to openai
    health_provider = provider
    adapter_provider = "openai" if provider == "self_hosted" else provider

    router = get_model_router()

    client = LLMClient(
        provider=adapter_provider,
        model=model,
        api_key=api_key,
        api_base=base_url,
        health_tracker=router.health_tracker,
        health_provider_id=health_provider,
    )

    async for chunk in client.stream(messages):
        if chunk:
            yield StreamEvent(StreamEventType.TEXT, chunk)

    yield StreamEvent(StreamEventType.DONE, {"summary": {}})


async def stream_with_tools_anthropic(
    message: str,
    workspace_path: str,
    api_key: str,
    model: str,
    context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    conversation_id: Optional[str] = None,
) -> AsyncGenerator["StreamEvent", None]:
    """
    Minimal streaming implementation for Anthropic.
    Emits text chunks as StreamEventType.TEXT to keep the V2 endpoint functional.
    """
    from backend.services.llm_client import LLMClient, LLMMessage
    from backend.services.model_router import get_model_router

    if not api_key:
        yield StreamEvent(
            StreamEventType.DONE, {"summary": {}, "error": "Missing API key"}
        )
        return

    system_prompt = "You are NAVI, an autonomous engineering assistant."
    if context:
        system_prompt += "\n\nContext:\n" + json.dumps(context, ensure_ascii=False)

    messages: List[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role") or msg.get("type") or "user"
            content = str(msg.get("content") or "")
            messages.append(LLMMessage(role=role, content=content))
    messages.append(LLMMessage(role="user", content=message))

    router = get_model_router()

    client = LLMClient(
        provider="anthropic",
        model=model,
        api_key=api_key,
        health_tracker=router.health_tracker,
        health_provider_id="anthropic",
    )

    async for chunk in client.stream(messages):
        if chunk:
            yield StreamEvent(StreamEventType.TEXT, chunk)

    yield StreamEvent(StreamEventType.DONE, {"summary": {}})


async def detect_project_type_and_build_command(
    workspace_path: str,
) -> Optional[Dict[str, Any]]:
    """
    Detect the project type and return the appropriate build command.
    Returns None if no buildable project is detected.
    """
    workspace = Path(workspace_path)

    # Check for Node.js/JavaScript projects
    package_json = workspace / "package.json"
    if package_json.exists():
        try:
            import json

            with open(package_json) as f:
                pkg = json.load(f)
                scripts = pkg.get("scripts", {})

                # Detect package manager
                pkg_manager = "npm"
                if (workspace / "pnpm-lock.yaml").exists():
                    pkg_manager = "pnpm"
                elif (workspace / "yarn.lock").exists():
                    pkg_manager = "yarn"
                elif (workspace / "bun.lockb").exists():
                    pkg_manager = "bun"

                # Priority: typecheck > build > tsc
                if "typecheck" in scripts:
                    return {
                        "type": "node",
                        "command": f"{pkg_manager} run typecheck",
                        "name": "TypeScript type check",
                    }
                elif "build" in scripts:
                    return {
                        "type": "node",
                        "command": f"{pkg_manager} run build",
                        "name": "Build",
                    }
                elif "tsc" in scripts:
                    return {
                        "type": "node",
                        "command": f"{pkg_manager} run tsc",
                        "name": "TypeScript compile",
                    }
                # Check if TypeScript is installed - run tsc directly
                elif (workspace / "tsconfig.json").exists():
                    return {
                        "type": "node",
                        "command": f"{pkg_manager} exec tsc --noEmit",
                        "name": "TypeScript check",
                    }
        except Exception as e:
            logger.warning(f"Error reading package.json: {e}")

    # Check for Python projects
    pyproject = workspace / "pyproject.toml"
    setup_py = workspace / "setup.py"
    if pyproject.exists() or setup_py.exists():
        # Check for mypy config
        if (workspace / "mypy.ini").exists() or (workspace / ".mypy.ini").exists():
            return {
                "type": "python",
                "command": "python -m mypy .",
                "name": "MyPy type check",
            }
        elif pyproject.exists():
            try:
                with open(pyproject) as f:
                    content = f.read()
                    if "[tool.mypy]" in content:
                        return {
                            "type": "python",
                            "command": "python -m mypy .",
                            "name": "MyPy type check",
                        }
                    if "ruff" in content:
                        return {
                            "type": "python",
                            "command": "python -m ruff check .",
                            "name": "Ruff lint",
                        }
            except Exception:
                pass
        return {
            "type": "python",
            "command": "python -m py_compile",
            "name": "Python syntax check",
        }

    # Check for Go projects
    go_mod = workspace / "go.mod"
    if go_mod.exists():
        return {"type": "go", "command": "go build ./...", "name": "Go build"}

    # Check for Rust projects
    cargo_toml = workspace / "Cargo.toml"
    if cargo_toml.exists():
        return {"type": "rust", "command": "cargo check", "name": "Cargo check"}

    return None


async def run_build_verification(workspace_path: str) -> Dict[str, Any]:
    """
    Run build verification for the workspace.
    Returns a dict with:
    - success: bool
    - project_type: str (node, python, go, rust, etc.)
    - command: str (the command that was run)
    - output: str (stdout/stderr from the build)
    - errors: list of error messages if any
    """
    project_info = await detect_project_type_and_build_command(workspace_path)

    if not project_info:
        return {
            "success": True,
            "skipped": True,
            "message": "No buildable project detected",
        }

    command = project_info["command"]
    project_type = project_info["type"]
    command_name = project_info["name"]

    logger.info(f"[BuildVerification] Running {command_name}: {command}")

    # Get environment with npm_config_prefix removed for nvm compatibility
    env = _get_command_env()

    # For Node.js projects, prepend nvm setup
    full_command = command
    if project_type == "node":
        nvm_setup = _get_node_env_setup(workspace_path)
        if nvm_setup:
            full_command = f"{nvm_setup} && {command}"
            logger.info("[BuildVerification] Added nvm setup to command")

    try:
        # Run the build command asynchronously
        process = await asyncio.create_subprocess_shell(
            full_command,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            executable="/bin/bash",
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=120.0,  # 2 minute timeout
        )

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        success = process.returncode == 0

        # Parse errors from output
        errors = []
        if not success:
            # Extract error lines (usually start with "error:" or contain "Error:")
            combined = stdout_text + "\n" + stderr_text
            for line in combined.split("\n"):
                line = line.strip()
                if line and any(
                    marker in line.lower()
                    for marker in ["error:", "error[", "failed", "cannot find"]
                ):
                    errors.append(line)

        return {
            "success": success,
            "skipped": False,
            "project_type": project_type,
            "command": command,
            "command_name": command_name,
            "output": (stdout_text + stderr_text)[:2000],  # Limit output size
            "errors": errors[:10],  # Limit to 10 errors
            "return_code": process.returncode,
        }

    except asyncio.TimeoutError:
        return {
            "success": False,
            "skipped": False,
            "project_type": project_type,
            "command": command,
            "command_name": command_name,
            "output": "",
            "errors": ["Build timed out after 2 minutes"],
            "return_code": -1,
        }
    except Exception as e:
        logger.error(f"[BuildVerification] Error running build: {e}")
        return {
            "success": False,
            "skipped": False,
            "project_type": project_type,
            "command": command,
            "command_name": command_name,
            "output": "",
            "errors": [str(e)],
            "return_code": -1,
        }


class TaskState(Enum):
    """Task lifecycle states for proper completion tracking."""

    IDLE = "idle"  # No active task
    PLANNING = "planning"  # LLM is creating a plan
    EXECUTING = "executing"  # Executing tool calls
    VERIFYING = "verifying"  # Running verification (tests, build, etc.)
    COMPLETE = "complete"  # Task successfully completed
    FAILED = "failed"  # Task failed
    WAITING_INPUT = "waiting_input"  # Waiting for user input/approval


@dataclass
class TaskContext:
    """
    Tracks task state for proper completion detection.

    This replaces heuristic-based completion detection (regex on response text)
    with semantic state tracking based on actual execution.
    """

    state: TaskState = TaskState.IDLE
    plan_id: Optional[str] = None
    planned_steps: List[Dict[str, Any]] = None
    completed_steps: List[int] = None
    current_step: int = 0
    pending_tool_calls: int = 0
    files_modified: List[str] = None
    files_created: List[str] = None
    commands_executed: List[Dict[str, Any]] = None
    verification_required: bool = False
    verification_passed: Optional[bool] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.planned_steps is None:
            self.planned_steps = []
        if self.completed_steps is None:
            self.completed_steps = []
        if self.files_modified is None:
            self.files_modified = []
        if self.files_created is None:
            self.files_created = []
        if self.commands_executed is None:
            self.commands_executed = []

    def start_planning(self):
        """Transition to planning state."""
        self.state = TaskState.PLANNING

    def set_plan(self, plan_id: str, steps: List[Dict[str, Any]]):
        """Set the execution plan."""
        self.plan_id = plan_id
        self.planned_steps = steps
        self.state = TaskState.EXECUTING

    def start_tool_call(self):
        """Track that a tool call is starting."""
        self.pending_tool_calls += 1
        if self.state == TaskState.IDLE:
            self.state = TaskState.EXECUTING

    def complete_tool_call(self, tool_name: str, result: Dict[str, Any]):
        """Track tool call completion."""
        self.pending_tool_calls = max(0, self.pending_tool_calls - 1)

        # Track file operations
        if tool_name in ("write_file", "create_file"):
            path = result.get("path", "")
            if path and path not in self.files_created:
                self.files_created.append(path)
        elif tool_name == "edit_file":
            path = result.get("path", "")
            if path and path not in self.files_modified:
                self.files_modified.append(path)
        elif tool_name == "run_command":
            self.commands_executed.append(
                {
                    "command": result.get("command", ""),
                    "success": result.get("success", False),
                    "exit_code": result.get("exit_code", -1),
                }
            )

    def complete_step(self, step_index: int):
        """Mark a step as completed."""
        if step_index not in self.completed_steps:
            self.completed_steps.append(step_index)
        self.current_step = step_index + 1

    def start_verification(self):
        """Transition to verification state."""
        self.state = TaskState.VERIFYING
        self.verification_required = True

    def complete_verification(self, passed: bool):
        """Record verification result."""
        self.verification_passed = passed
        if passed:
            self.state = TaskState.COMPLETE
        else:
            self.state = TaskState.FAILED

    def is_complete(self) -> bool:
        """
        Determine if task is truly complete.

        A task is complete when:
        1. No pending tool calls
        2. All planned steps executed (if there's a plan)
        3. Verification passed (if verification was required)
        4. State is explicitly COMPLETE
        """
        if self.state != TaskState.COMPLETE:
            return False
        if self.pending_tool_calls > 0:
            return False
        if self.planned_steps and len(self.completed_steps) < len(self.planned_steps):
            return False
        if self.verification_required and not self.verification_passed:
            return False
        return True

    def mark_complete(self, success: bool = True, error: Optional[str] = None):
        """Explicitly mark task as complete or failed."""
        if success:
            self.state = TaskState.COMPLETE
        else:
            self.state = TaskState.FAILED
            self.error_message = error

    def get_summary(self) -> Dict[str, Any]:
        """Get task completion summary."""
        return {
            "state": self.state.value,
            "is_complete": self.is_complete(),
            "files_modified": len(self.files_modified),
            "files_created": len(self.files_created),
            "commands_executed": len(self.commands_executed),
            "steps_completed": len(self.completed_steps),
            "steps_total": len(self.planned_steps),
            "verification_passed": self.verification_passed,
            "error": self.error_message,
        }


class StreamEventType(Enum):
    """Types of events in the streaming response."""

    TEXT = "text"  # Narrative text from LLM
    THINKING = "thinking"  # Extended thinking/reasoning from LLM
    TOOL_CALL = "tool_call"  # LLM wants to call a tool
    TOOL_RESULT = "tool_result"  # Result of tool execution
    DONE = "done"  # Stream complete
    # Execution Plan Events - for visual step-by-step progress UI
    PLAN_START = "plan_start"  # Detected execution plan with steps
    STEP_UPDATE = "step_update"  # Step status changed (running/completed/error)
    PLAN_COMPLETE = "plan_complete"  # All steps completed
    # Task State Events - for proper completion tracking
    TASK_STATE = (
        "task_state"  # Task state changed (planning, executing, complete, failed)
    )
    TASK_COMPLETE = "task_complete"  # Explicit task completion signal
    # Build Verification Events
    BUILD_VERIFICATION = "build_verification"  # Build/type-check verification results


@dataclass
class StreamEvent:
    """A single event in the streaming response."""

    type: StreamEventType
    content: Any
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type.value}
        if self.type == StreamEventType.TEXT:
            result["text"] = self.content
        elif self.type == StreamEventType.THINKING:
            result["thinking"] = self.content
        elif self.type == StreamEventType.TOOL_CALL:
            result["tool_call"] = {
                "id": self.tool_id,
                "name": self.tool_name,
                "arguments": self.content,
            }
        elif self.type == StreamEventType.TOOL_RESULT:
            result["tool_result"] = {
                "id": self.tool_id,
                "result": self.content,
            }
        elif self.type == StreamEventType.DONE:
            # Include summary if content is a dict with summary
            if isinstance(self.content, dict):
                result["type"] = "complete"
                result["summary"] = self.content.get("summary", {})
            else:
                result["final_message"] = self.content
        # Execution Plan Events
        elif self.type == StreamEventType.PLAN_START:
            result["data"] = self.content  # {plan_id, steps: [{index, title, detail}]}
        elif self.type == StreamEventType.STEP_UPDATE:
            result["data"] = self.content  # {plan_id, step_index, status}
        elif self.type == StreamEventType.PLAN_COMPLETE:
            result["data"] = self.content  # {plan_id}
        # Task State Events - for proper completion tracking
        elif self.type == StreamEventType.TASK_STATE:
            result["task_state"] = self.content  # {state, context}
        elif self.type == StreamEventType.TASK_COMPLETE:
            # Explicit task completion signal with full summary
            result[
                "task_complete"
            ] = self.content  # {success, summary, files_modified, etc.}
        elif self.type == StreamEventType.BUILD_VERIFICATION:
            # Build/type-check verification results
            result[
                "build_verification"
            ] = self.content  # {success, command, output, errors}
        return result


# Define the tools that NAVI can use
NAVI_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace. Use this to understand code before making changes.",
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
        "description": "Create a new file or completely replace an existing file's contents.",
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
        "description": "Make targeted edits to a file by replacing specific text. Use for small, precise changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The relative path to the file",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace",
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
        "description": "Execute a shell command in the workspace. Use for running builds, tests, installs, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"},
                "cwd": {
                    "type": "string",
                    "description": "Optional: working directory relative to workspace root",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Optional: timeout in seconds (default 300, max 1800). Use longer timeouts for builds, tests, or package installs.",
                    "default": 300,
                    "minimum": 1,
                    "maximum": 1800,
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
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (relative to workspace root)",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "start_server",
        "description": "Start a dev server or long-running process in background. Returns immediately after starting, then verifies the server is responding. Use this instead of run_command for 'npm run dev', 'python app.py', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to start the server (e.g., 'npm run dev', 'python app.py')",
                },
                "port": {
                    "type": "integer",
                    "description": "The port the server will listen on (for verification)",
                },
                "health_path": {
                    "type": "string",
                    "description": "Optional: path to check for health (default: '/')",
                },
                "startup_time": {
                    "type": "integer",
                    "description": "Optional: seconds to wait for server to start (default: 10)",
                },
            },
            "required": ["command", "port"],
        },
    },
    {
        "name": "check_endpoint",
        "description": "Check if an HTTP endpoint is responding. Use to verify servers, APIs, or services are running.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to check (e.g., 'http://localhost:3000')",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "HEAD"],
                    "description": "HTTP method (default: GET)",
                },
                "expected_status": {
                    "type": "integer",
                    "description": "Expected HTTP status code (default: 200)",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "stop_server",
        "description": "Stop a running server by killing processes on a specific port.",
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "The port the server is running on",
                }
            },
            "required": ["port"],
        },
    },
    {
        "name": "ask_user",
        "description": "Request user input when you genuinely need clarification and CANNOT proceed without it. Use sparingly - only when truly necessary. Examples: multiple files match and you can't determine which one, user's request is ambiguous with no context, need to choose between mutually exclusive approaches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The specific question to ask the user. Be clear and concise.",
                },
                "title": {
                    "type": "string",
                    "description": "Short title for the prompt (e.g., 'Select file', 'Confirm action')",
                },
                "prompt_type": {
                    "type": "string",
                    "enum": ["text", "select", "confirm"],
                    "description": "Type of input: 'text' (free text), 'select' (choose one option), 'confirm' (yes/no)",
                },
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["value", "label"],
                    },
                    "description": "List of options (required for 'select' type, ignored for others)",
                },
                "placeholder": {
                    "type": "string",
                    "description": "Placeholder text (for 'text' type only)",
                },
            },
            "required": ["question", "prompt_type"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch and read the content of a web page. Use this when the user provides a URL or wants you to analyze a website. Returns the page title and text content extracted from HTML.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch (e.g., 'https://example.com')",
                },
                "extract_text": {
                    "type": "boolean",
                    "description": "If true, extract readable text from HTML. If false, return raw content. Default: true",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for information. Use when you need to find current information or research a topic. Requires TAVILY_API_KEY to be configured.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 5, max: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_backups",
        "description": "List all NAVI backups created before dangerous operations. Use to show user what can be restored.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "restore_backup",
        "description": "Restore a backup that was created before a dangerous operation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_name": {
                    "type": "string",
                    "description": "Name of the backup to restore (from list_backups)",
                },
                "target_path": {
                    "type": "string",
                    "description": "Where to restore to (optional, will try to detect from backup name)",
                },
            },
            "required": ["backup_name"],
        },
    },
    {
        "name": "run_interactive_command",
        "description": "Execute a command that might require interactive input (yes/no prompts). Automatically answers common prompts like 'Continue? [y/n]'. Use for npm install, apt-get, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"},
                "auto_yes": {
                    "type": "boolean",
                    "description": "Auto-answer yes to prompts (default: true)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "run_parallel_commands",
        "description": "Execute multiple commands in parallel. Use for running independent tasks concurrently like building while testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of commands to run in parallel",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Max parallel workers (default: 4)",
                },
                "stop_on_failure": {
                    "type": "boolean",
                    "description": "Stop all if one fails (default: false)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            "required": ["commands"],
        },
    },
    {
        "name": "run_command_with_retry",
        "description": "Execute a command with automatic retry on failure. Use for flaky commands or network operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"},
                "max_retries": {
                    "type": "integer",
                    "description": "Max retry attempts (default: 3)",
                },
                "retry_delay": {
                    "type": "number",
                    "description": "Seconds between retries (default: 1.0)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "create_jira_issue",
        "description": "Create a new Jira issue. Requires user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {
                    "type": "string",
                    "description": "Jira project key (e.g., 'PROJ')",
                },
                "summary": {"type": "string", "description": "Issue title"},
                "description": {"type": "string", "description": "Issue description"},
                "issue_type": {
                    "type": "string",
                    "description": "Type (Task, Bug, Story, etc.)",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority (Highest, High, Medium, Low)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["project_key", "summary", "approve"],
        },
    },
    {
        "name": "search_jira_issues",
        "description": "Search Jira issues using JQL or filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jql": {"type": "string", "description": "Raw JQL query (optional)"},
                "project": {"type": "string", "description": "Filter by project key"},
                "status": {"type": "string", "description": "Filter by status"},
                "text": {"type": "string", "description": "Full-text search"},
                "max_results": {
                    "type": "integer",
                    "description": "Max results (default: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "add_jira_comment",
        "description": "Add a comment to a Jira issue. Requires user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "Jira issue key (e.g., 'PROJ-123')",
                },
                "comment": {"type": "string", "description": "Comment text"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["issue_key", "comment", "approve"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a new GitHub issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "title": {"type": "string", "description": "Issue title"},
                "body": {
                    "type": "string",
                    "description": "Issue description (markdown)",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to add",
                },
            },
            "required": ["repo", "title"],
        },
    },
    {
        "name": "github_list_issues",
        "description": "List GitHub issues in a repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Issue state",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max issues to return (default: 20)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_add_issue_comment",
        "description": "Add a comment to a GitHub issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "issue_number": {"type": "integer", "description": "Issue number"},
                "body": {"type": "string", "description": "Comment text (markdown)"},
            },
            "required": ["repo", "issue_number", "body"],
        },
    },
    {
        "name": "github_add_pr_review",
        "description": "Add a review to a GitHub pull request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "pr_number": {"type": "integer", "description": "PR number"},
                "body": {"type": "string", "description": "Review comment (markdown)"},
                "event": {
                    "type": "string",
                    "enum": ["COMMENT", "APPROVE", "REQUEST_CHANGES"],
                    "description": "Review type",
                },
            },
            "required": ["repo", "pr_number", "body"],
        },
    },
    {
        "name": "github_list_prs",
        "description": "List GitHub pull requests in a repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "PR state",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max PRs to return (default: 20)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_merge_pr",
        "description": "Merge a GitHub pull request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "pr_number": {"type": "integer", "description": "PR number"},
                "merge_method": {
                    "type": "string",
                    "enum": ["merge", "squash", "rebase"],
                    "description": "Merge method",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    # ============================================
    # INFRASTRUCTURE TOOLS (Terraform, K8s, Docker)
    # ============================================
    {
        "name": "infra_generate_terraform",
        "description": "Generate Terraform configuration for infrastructure. Analyzes project needs and creates appropriate IaC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure", "digitalocean"],
                    "description": "Cloud provider",
                },
                "resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Resources to provision (e.g., 'ec2', 'rds', 's3')",
                },
                "environment": {
                    "type": "string",
                    "description": "Environment name (dev, staging, prod)",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "infra_generate_k8s",
        "description": "Generate Kubernetes YAML manifests for deploying the application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Application name"},
                "replicas": {
                    "type": "integer",
                    "description": "Number of replicas (default: 2)",
                },
                "port": {"type": "integer", "description": "Container port"},
                "image": {
                    "type": "string",
                    "description": "Docker image (optional, will be inferred)",
                },
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "infra_generate_docker_compose",
        "description": "Generate docker-compose.yml for local development. Auto-detects services from project structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_db": {
                    "type": "boolean",
                    "description": "Include database service",
                },
                "include_redis": {
                    "type": "boolean",
                    "description": "Include Redis cache",
                },
                "include_nginx": {
                    "type": "boolean",
                    "description": "Include Nginx reverse proxy",
                },
            },
            "required": [],
        },
    },
    {
        "name": "infra_generate_helm",
        "description": "Generate a Helm chart for Kubernetes deployment with configurable values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_name": {
                    "type": "string",
                    "description": "Name for the Helm chart",
                },
                "app_version": {"type": "string", "description": "Application version"},
            },
            "required": ["chart_name"],
        },
    },
    {
        "name": "infra_terraform_plan",
        "description": "Run 'terraform plan' to preview infrastructure changes. Requires user approval for apply.",
        "input_schema": {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Directory containing Terraform files",
                },
                "var_file": {
                    "type": "string",
                    "description": "Path to tfvars file (optional)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "infra_kubectl_apply",
        "description": "Apply Kubernetes manifests to a cluster. Requires user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "manifest_path": {
                    "type": "string",
                    "description": "Path to YAML manifest or directory",
                },
                "namespace": {"type": "string", "description": "Target namespace"},
                "dry_run": {
                    "type": "boolean",
                    "description": "Dry run mode (default: true for safety)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to actually apply",
                },
            },
            "required": ["manifest_path", "approve"],
        },
    },
    {
        "name": "infra_generate_cloudformation",
        "description": "Generate AWS CloudFormation templates for infrastructure provisioning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "AWS resources to provision (ec2, rds, lambda, etc.)",
                },
                "environment": {
                    "type": "string",
                    "description": "Environment name (dev, staging, prod)",
                },
                "region": {"type": "string", "description": "AWS region"},
            },
            "required": ["resources"],
        },
    },
    {
        "name": "infra_analyze_needs",
        "description": "Analyze project requirements and recommend infrastructure setup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_scaling": {
                    "type": "boolean",
                    "description": "Include auto-scaling recommendations",
                },
                "include_security": {
                    "type": "boolean",
                    "description": "Include security recommendations",
                },
            },
            "required": [],
        },
    },
    {
        "name": "infra_terraform_apply",
        "description": "Run 'terraform apply' to provision infrastructure. Requires user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Directory containing Terraform files",
                },
                "var_file": {
                    "type": "string",
                    "description": "Path to tfvars file (optional)",
                },
                "auto_approve": {
                    "type": "boolean",
                    "description": "Skip interactive approval (not recommended)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["approve"],
        },
    },
    {
        "name": "infra_terraform_destroy",
        "description": "Run 'terraform destroy' to tear down infrastructure. DANGEROUS - requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Directory containing Terraform files",
                },
                "target": {
                    "type": "string",
                    "description": "Specific resource to destroy (optional)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["approve"],
        },
    },
    {
        "name": "infra_helm_install",
        "description": "Install or upgrade a Helm chart in Kubernetes. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "release_name": {"type": "string", "description": "Helm release name"},
                "chart": {"type": "string", "description": "Chart name or path"},
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "values_file": {
                    "type": "string",
                    "description": "Path to values.yaml file",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to install",
                },
            },
            "required": ["release_name", "chart", "approve"],
        },
    },
    # ============================================
    # DATABASE TOOLS (Schema, Migrations)
    # ============================================
    {
        "name": "db_design_schema",
        "description": "Design a database schema from natural language description. Generates ORM models or raw SQL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the data model",
                },
                "orm": {
                    "type": "string",
                    "enum": ["prisma", "sqlalchemy", "drizzle", "typeorm", "raw_sql"],
                    "description": "ORM/schema format",
                },
                "database": {
                    "type": "string",
                    "enum": ["postgresql", "mysql", "sqlite", "mongodb"],
                    "description": "Database type",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "db_generate_migration",
        "description": "Generate a database migration file for schema changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Migration name (e.g., 'add_users_table')",
                },
                "changes": {
                    "type": "string",
                    "description": "Description of changes to make",
                },
            },
            "required": ["name", "changes"],
        },
    },
    {
        "name": "db_run_migration",
        "description": "Run pending database migrations. Shows command and requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Migration direction",
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of migrations to run (for rollback)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["approve"],
        },
    },
    {
        "name": "db_generate_seed",
        "description": "Generate seed data for database tables based on schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tables to seed",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of records per table (default: 10)",
                },
                "realistic": {
                    "type": "boolean",
                    "description": "Generate realistic fake data (default: true)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "db_analyze_schema",
        "description": "Analyze existing database schema and suggest improvements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "check_indexes": {
                    "type": "boolean",
                    "description": "Check for missing indexes",
                },
                "check_relations": {
                    "type": "boolean",
                    "description": "Validate foreign key relationships",
                },
                "check_naming": {
                    "type": "boolean",
                    "description": "Check naming conventions",
                },
            },
            "required": [],
        },
    },
    {
        "name": "db_generate_erd",
        "description": "Generate an Entity Relationship Diagram from database schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["mermaid", "plantuml", "dbml"],
                    "description": "Output format",
                },
            },
            "required": [],
        },
    },
    {
        "name": "db_backup",
        "description": "Create a database backup. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "Database name"},
                "format": {
                    "type": "string",
                    "enum": ["sql", "pg_dump", "custom"],
                    "description": "Backup format",
                },
                "destination": {
                    "type": "string",
                    "description": "Backup destination path",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["approve"],
        },
    },
    {
        "name": "db_restore",
        "description": "Restore database from backup. DANGEROUS - requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_file": {"type": "string", "description": "Path to backup file"},
                "database": {"type": "string", "description": "Target database name"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to execute",
                },
            },
            "required": ["backup_file", "approve"],
        },
    },
    {
        "name": "db_migration_status",
        "description": "Get status of database migrations (pending, applied).",
        "input_schema": {
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "description": "Show detailed migration info",
                },
            },
            "required": [],
        },
    },
    {
        "name": "db_execute_query",
        "description": "Execute a raw SQL query. Requires approval for write operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute"},
                "database": {"type": "string", "description": "Database name"},
                "params": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Query parameters",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true for write operations",
                },
            },
            "required": ["query"],
        },
    },
    # ============================================
    # TEST GENERATION TOOLS
    # ============================================
    {
        "name": "test_generate_for_file",
        "description": "Generate comprehensive tests for all functions/classes in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file",
                },
                "framework": {
                    "type": "string",
                    "description": "Test framework (pytest, jest, vitest, etc.)",
                },
                "coverage_target": {
                    "type": "number",
                    "description": "Target coverage percentage (default: 80)",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "test_generate_for_function",
        "description": "Generate tests for a specific function with edge cases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file",
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function to test",
                },
                "include_edge_cases": {
                    "type": "boolean",
                    "description": "Include edge case tests (default: true)",
                },
            },
            "required": ["file_path", "function_name"],
        },
    },
    {
        "name": "test_generate_suite",
        "description": "Generate a complete test suite for a module or directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to module or directory",
                },
                "include_integration": {
                    "type": "boolean",
                    "description": "Include integration tests",
                },
                "include_e2e": {
                    "type": "boolean",
                    "description": "Include end-to-end tests",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "test_detect_framework",
        "description": "Detect the test framework used in the project.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "test_suggest_improvements",
        "description": "Analyze existing test file and suggest improvements for coverage, edge cases, and best practices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_file_path": {
                    "type": "string",
                    "description": "Path to the test file to analyze",
                },
                "workspace_path": {
                    "type": "string",
                    "description": "Project root directory (optional)",
                },
            },
            "required": ["test_file_path"],
        },
    },
    # ============================================
    # CI/CD TOOLS (GitLab CI, GitHub Actions)
    # ============================================
    {
        "name": "gitlab_ci_generate",
        "description": "Generate a .gitlab-ci.yml file with stages for lint, test, build, and deploy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_docker": {
                    "type": "boolean",
                    "description": "Include Docker build stage",
                },
                "include_security": {
                    "type": "boolean",
                    "description": "Include security scanning",
                },
                "environments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Deployment environments (staging, prod)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "github_actions_generate",
        "description": "Generate GitHub Actions workflow files for CI/CD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_name": {"type": "string", "description": "Workflow name"},
                "triggers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Trigger events (push, pull_request)",
                },
                "include_deploy": {
                    "type": "boolean",
                    "description": "Include deployment job",
                },
            },
            "required": [],
        },
    },
    {
        "name": "github_actions_list_workflows",
        "description": "List GitHub Actions workflows in a repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_actions_list_runs",
        "description": "List recent GitHub Actions workflow runs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "workflow_id": {
                    "type": "string",
                    "description": "Filter by workflow ID",
                },
                "status": {
                    "type": "string",
                    "enum": ["queued", "in_progress", "completed"],
                    "description": "Filter by status",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_actions_get_run_status",
        "description": "Get status of a specific GitHub Actions run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "run_id": {"type": "string", "description": "Run ID"},
            },
            "required": ["repo", "run_id"],
        },
    },
    {
        "name": "github_actions_trigger_workflow",
        "description": "Trigger a GitHub Actions workflow. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository (owner/repo format)",
                },
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID or filename",
                },
                "ref": {"type": "string", "description": "Branch or tag to run on"},
                "inputs": {
                    "type": "object",
                    "description": "Workflow input parameters",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to trigger",
                },
            },
            "required": ["repo", "workflow_id", "approve"],
        },
    },
    {
        "name": "gitlab_ci_list_pipelines",
        "description": "List GitLab CI pipelines for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project path (group/project)",
                },
                "status": {
                    "type": "string",
                    "enum": ["running", "pending", "success", "failed", "canceled"],
                    "description": "Filter by status",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "gitlab_ci_get_pipeline_jobs",
        "description": "Get jobs for a GitLab CI pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project path"},
                "pipeline_id": {"type": "integer", "description": "Pipeline ID"},
            },
            "required": ["project", "pipeline_id"],
        },
    },
    {
        "name": "gitlab_ci_trigger_pipeline",
        "description": "Trigger a GitLab CI pipeline. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project path"},
                "ref": {"type": "string", "description": "Branch or tag"},
                "variables": {"type": "object", "description": "Pipeline variables"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to trigger",
                },
            },
            "required": ["project", "approve"],
        },
    },
    {
        "name": "gitlab_ci_retry_job",
        "description": "Retry a failed GitLab CI job. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project path"},
                "job_id": {"type": "integer", "description": "Job ID"},
                "approve": {"type": "boolean", "description": "Must be true to retry"},
            },
            "required": ["project", "job_id", "approve"],
        },
    },
    # ============================================
    # DOCUMENTATION TOOLS
    # ============================================
    {
        "name": "docs_generate_readme",
        "description": "Generate a comprehensive README.md for the project with installation, usage, and API documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_badges": {
                    "type": "boolean",
                    "description": "Include status badges (build, coverage, etc.)",
                },
                "include_toc": {
                    "type": "boolean",
                    "description": "Include table of contents",
                },
                "style": {
                    "type": "string",
                    "enum": ["standard", "minimal", "detailed"],
                    "description": "Documentation style",
                },
            },
            "required": [],
        },
    },
    {
        "name": "docs_generate_api",
        "description": "Generate API documentation from code. Supports OpenAPI/Swagger, Markdown, or JSDoc format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["openapi", "markdown", "jsdoc"],
                    "description": "Output format",
                },
                "include_examples": {
                    "type": "boolean",
                    "description": "Include usage examples",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["endpoint", "resource", "tag"],
                    "description": "How to group endpoints",
                },
            },
            "required": [],
        },
    },
    {
        "name": "docs_generate_component",
        "description": "Generate documentation for React/Vue components including props, usage examples, and styling.",
        "input_schema": {
            "type": "object",
            "properties": {
                "component_path": {
                    "type": "string",
                    "description": "Path to the component file",
                },
                "include_props_table": {
                    "type": "boolean",
                    "description": "Include props/types table",
                },
                "include_examples": {
                    "type": "boolean",
                    "description": "Include usage examples",
                },
            },
            "required": ["component_path"],
        },
    },
    {
        "name": "docs_generate_architecture",
        "description": "Generate architecture documentation with system overview, components, data flow, and diagrams.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_diagrams": {
                    "type": "boolean",
                    "description": "Include Mermaid diagrams",
                },
                "include_tech_stack": {
                    "type": "boolean",
                    "description": "Include technology stack details",
                },
                "include_security": {
                    "type": "boolean",
                    "description": "Include security considerations",
                },
            },
            "required": [],
        },
    },
    {
        "name": "docs_generate_comments",
        "description": "Generate inline code comments and docstrings for functions/classes in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file",
                },
                "style": {
                    "type": "string",
                    "enum": ["jsdoc", "tsdoc", "google", "numpy", "sphinx"],
                    "description": "Comment style",
                },
                "include_params": {
                    "type": "boolean",
                    "description": "Include parameter descriptions",
                },
                "include_returns": {
                    "type": "boolean",
                    "description": "Include return value descriptions",
                },
            },
            "required": ["file_path"],
        },
    },
    # ============================================
    # SCAFFOLDING TOOLS (Project Templates)
    # ============================================
    {
        "name": "scaffold_project",
        "description": "Create a new project from a template. Supports React, Next.js, FastAPI, Express, and more.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "description": "Type of project (nextjs, react, fastapi, express, etc.)",
                },
                "name": {"type": "string", "description": "Project name"},
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Features to include (auth, db, docker)",
                },
            },
            "required": ["project_type", "name"],
        },
    },
    {
        "name": "scaffold_detect_requirements",
        "description": "Analyze natural language requirements and suggest project structure and technologies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the project",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "scaffold_add_feature",
        "description": "Add a feature to an existing project (API route, component, model, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_type": {
                    "type": "string",
                    "enum": [
                        "api-route",
                        "component",
                        "model",
                        "service",
                        "middleware",
                    ],
                    "description": "Type of feature",
                },
                "name": {"type": "string", "description": "Feature name"},
            },
            "required": ["feature_type", "name"],
        },
    },
    {
        "name": "scaffold_list_templates",
        "description": "List available project templates and their features.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (frontend, backend, fullstack)",
                },
            },
            "required": [],
        },
    },
    # ============================================
    # MONITORING & OBSERVABILITY TOOLS
    # ============================================
    {
        "name": "monitor_setup_errors",
        "description": "Set up error tracking with Sentry, Rollbar, or similar services.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["sentry", "rollbar", "bugsnag"],
                    "description": "Error tracking provider",
                },
                "framework": {
                    "type": "string",
                    "description": "Project framework (nextjs, fastapi, express)",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "monitor_setup_apm",
        "description": "Set up Application Performance Monitoring with Datadog, New Relic, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["datadog", "newrelic", "dynatrace"],
                    "description": "APM provider",
                },
                "enable_profiling": {
                    "type": "boolean",
                    "description": "Enable code profiling",
                },
                "enable_tracing": {
                    "type": "boolean",
                    "description": "Enable distributed tracing",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "monitor_setup_logging",
        "description": "Configure structured logging with proper formatters and transports.",
        "input_schema": {
            "type": "object",
            "properties": {
                "library": {
                    "type": "string",
                    "enum": ["pino", "winston", "structlog", "loguru"],
                    "description": "Logging library",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "pretty", "compact"],
                    "description": "Output format",
                },
                "level": {
                    "type": "string",
                    "enum": ["debug", "info", "warn", "error"],
                    "description": "Default log level",
                },
            },
            "required": [],
        },
    },
    {
        "name": "monitor_generate_health_checks",
        "description": "Generate health check endpoints for liveness and readiness probes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_db": {
                    "type": "boolean",
                    "description": "Check database connectivity",
                },
                "include_redis": {
                    "type": "boolean",
                    "description": "Check Redis connectivity",
                },
                "include_external": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "External services to check",
                },
            },
            "required": [],
        },
    },
    {
        "name": "monitor_setup_alerting",
        "description": "Configure alerting rules for monitoring services.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["pagerduty", "opsgenie", "slack", "email"],
                    "description": "Alert destination",
                },
                "thresholds": {
                    "type": "object",
                    "description": "Alert thresholds (error_rate, latency_ms, etc.)",
                },
            },
            "required": ["provider"],
        },
    },
    # ============================================
    # SECRETS MANAGEMENT TOOLS
    # ============================================
    {
        "name": "secrets_generate_env",
        "description": "Generate .env.example template by scanning code for environment variable usage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_descriptions": {
                    "type": "boolean",
                    "description": "Include descriptions for each variable",
                },
                "group_by_service": {
                    "type": "boolean",
                    "description": "Group variables by service/feature",
                },
            },
            "required": [],
        },
    },
    {
        "name": "secrets_setup_provider",
        "description": "Set up a secrets provider like HashiCorp Vault or AWS Secrets Manager.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": [
                        "vault",
                        "aws_secrets_manager",
                        "gcp_secret_manager",
                        "azure_keyvault",
                    ],
                    "description": "Secrets provider",
                },
                "generate_config": {
                    "type": "boolean",
                    "description": "Generate configuration files",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "secrets_sync_to_platform",
        "description": "Sync secrets to a deployment platform (Vercel, Railway, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["vercel", "railway", "fly", "netlify", "heroku"],
                    "description": "Target platform",
                },
                "env_file": {"type": "string", "description": "Path to .env file"},
                "environment": {
                    "type": "string",
                    "enum": ["development", "preview", "production"],
                    "description": "Target environment",
                },
            },
            "required": ["platform"],
        },
    },
    {
        "name": "secrets_audit",
        "description": "Audit codebase for exposed secrets, API keys, or credentials.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scan_git_history": {
                    "type": "boolean",
                    "description": "Scan git history for secrets",
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patterns to exclude from scan",
                },
            },
            "required": [],
        },
    },
    {
        "name": "secrets_rotate",
        "description": "Generate commands to rotate secrets for various providers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "secret_type": {
                    "type": "string",
                    "description": "Type of secret (api_key, database, jwt, etc.)",
                },
                "provider": {
                    "type": "string",
                    "description": "Service provider (aws, stripe, github, etc.)",
                },
            },
            "required": ["secret_type"],
        },
    },
    # ============================================
    # ARCHITECTURE PLANNING TOOLS
    # ============================================
    {
        "name": "arch_recommend_stack",
        "description": "Get technology stack recommendations based on project requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "description": "Type of project (web app, API, mobile, etc.)",
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key requirements (realtime, high-scale, etc.)",
                },
                "team_size": {
                    "type": "string",
                    "enum": ["solo", "small", "medium", "large"],
                    "description": "Team size",
                },
                "budget": {
                    "type": "string",
                    "enum": ["minimal", "moderate", "enterprise"],
                    "description": "Infrastructure budget",
                },
            },
            "required": ["project_type"],
        },
    },
    {
        "name": "arch_design_system",
        "description": "Design a system architecture with components, services, and data flows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "System description and requirements",
                },
                "pattern": {
                    "type": "string",
                    "enum": [
                        "monolith",
                        "microservices",
                        "serverless",
                        "event_driven",
                        "modular_monolith",
                    ],
                    "description": "Architecture pattern",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "arch_generate_diagram",
        "description": "Generate architecture diagrams in Mermaid, PlantUML, or D2 format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "enum": [
                        "system",
                        "sequence",
                        "component",
                        "deployment",
                        "data_flow",
                    ],
                    "description": "Type of diagram",
                },
                "format": {
                    "type": "string",
                    "enum": ["mermaid", "plantuml", "d2"],
                    "description": "Output format",
                },
            },
            "required": ["diagram_type"],
        },
    },
    {
        "name": "arch_decompose_microservices",
        "description": "Analyze a monolith and suggest microservices decomposition boundaries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "analyze_dependencies": {
                    "type": "boolean",
                    "description": "Analyze code dependencies",
                },
                "suggest_boundaries": {
                    "type": "boolean",
                    "description": "Suggest service boundaries",
                },
            },
            "required": [],
        },
    },
    {
        "name": "arch_generate_adr",
        "description": "Generate an Architecture Decision Record (ADR) document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Decision title"},
                "context": {
                    "type": "string",
                    "description": "Context and problem statement",
                },
                "decision": {"type": "string", "description": "The decision made"},
                "alternatives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alternatives considered",
                },
            },
            "required": ["title", "decision"],
        },
    },
    # ============================================
    # DEPLOYMENT TOOLS
    # ============================================
    {
        "name": "deploy_detect_project",
        "description": "Detect project type and suggest optimal deployment platforms.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "deploy_check_cli",
        "description": "Check if deployment CLI tools are installed and authenticated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": [
                        "vercel",
                        "railway",
                        "fly",
                        "netlify",
                        "heroku",
                        "aws",
                        "gcp",
                    ],
                    "description": "Deployment platform",
                },
            },
            "required": ["platform"],
        },
    },
    {
        "name": "deploy_get_info",
        "description": "Get current deployment status and information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Deployment platform"},
                "environment": {
                    "type": "string",
                    "description": "Environment (production, staging, preview)",
                },
            },
            "required": ["platform"],
        },
    },
    {
        "name": "deploy_list_platforms",
        "description": "List supported deployment platforms and their features.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "description": "Filter by project type (nextjs, fastapi, etc.)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "deploy_execute",
        "description": "Execute deployment to a platform. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": [
                        "vercel",
                        "railway",
                        "fly",
                        "netlify",
                        "heroku",
                        "aws",
                        "gcp",
                    ],
                    "description": "Target platform",
                },
                "environment": {
                    "type": "string",
                    "enum": ["development", "preview", "production"],
                    "description": "Target environment",
                },
                "approve": {"type": "boolean", "description": "Must be true to deploy"},
            },
            "required": ["platform", "approve"],
        },
    },
    {
        "name": "deploy_rollback",
        "description": "Rollback to a previous deployment. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Deployment platform"},
                "deployment_id": {
                    "type": "string",
                    "description": "Deployment ID to rollback to",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to rollback",
                },
            },
            "required": ["platform", "approve"],
        },
    },
    {
        "name": "deploy_status",
        "description": "Get current deployment status and health.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Deployment platform"},
                "environment": {
                    "type": "string",
                    "description": "Environment to check",
                },
            },
            "required": ["platform"],
        },
    },
    {
        "name": "deploy_logs",
        "description": "Get deployment logs from a platform.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Deployment platform"},
                "deployment_id": {"type": "string", "description": "Deployment ID"},
                "tail": {
                    "type": "integer",
                    "description": "Number of recent lines (default: 100)",
                },
            },
            "required": ["platform"],
        },
    },
    # ============================================
    # SLACK INTEGRATION TOOLS
    # ============================================
    {
        "name": "slack_search_messages",
        "description": "Search Slack messages across channels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "channel": {
                    "type": "string",
                    "description": "Filter by channel name or ID",
                },
                "from_user": {"type": "string", "description": "Filter by sender"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results (default: 20)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "slack_list_channel_messages",
        "description": "List recent messages in a Slack channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name or ID"},
                "limit": {
                    "type": "integer",
                    "description": "Number of messages (default: 50)",
                },
            },
            "required": ["channel"],
        },
    },
    {
        "name": "slack_send_message",
        "description": "Send a message to a Slack channel. Requires user approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name or ID"},
                "message": {
                    "type": "string",
                    "description": "Message text (supports Slack markdown)",
                },
                "approve": {"type": "boolean", "description": "Must be true to send"},
            },
            "required": ["channel", "message", "approve"],
        },
    },
    # ============================================
    # GITLAB INTEGRATION TOOLS
    # ============================================
    {
        "name": "gitlab_list_my_merge_requests",
        "description": "List your open merge requests across GitLab projects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["opened", "closed", "merged", "all"],
                    "description": "MR state filter",
                },
                "scope": {
                    "type": "string",
                    "enum": ["created_by_me", "assigned_to_me", "all"],
                    "description": "Scope filter",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gitlab_list_my_issues",
        "description": "List your assigned issues across GitLab projects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["opened", "closed", "all"],
                    "description": "Issue state filter",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by labels",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gitlab_get_pipeline_status",
        "description": "Get the status of a GitLab CI/CD pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project path (group/project)",
                },
                "pipeline_id": {
                    "type": "integer",
                    "description": "Pipeline ID (optional, defaults to latest)",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "gitlab_search",
        "description": "Search GitLab for projects, issues, or merge requests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "scope": {
                    "type": "string",
                    "enum": ["projects", "issues", "merge_requests", "blobs"],
                    "description": "Search scope",
                },
            },
            "required": ["query"],
        },
    },
    # ============================================
    # LINEAR INTEGRATION TOOLS
    # ============================================
    {
        "name": "linear_list_my_issues",
        "description": "List Linear issues assigned to you.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (backlog, todo, in_progress, done)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max issues to return (default: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "linear_search_issues",
        "description": "Search Linear issues by text query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "team": {"type": "string", "description": "Filter by team name"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "linear_create_issue",
        "description": "Create a new Linear issue. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Issue title"},
                "description": {
                    "type": "string",
                    "description": "Issue description (markdown)",
                },
                "team": {"type": "string", "description": "Team name or ID"},
                "priority": {
                    "type": "integer",
                    "description": "Priority (0=None, 1=Urgent, 2=High, 3=Medium, 4=Low)",
                },
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["title", "team", "approve"],
        },
    },
    {
        "name": "linear_update_status",
        "description": "Update status of a Linear issue. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string", "description": "Issue ID or identifier"},
                "status": {
                    "type": "string",
                    "description": "New status (backlog, todo, in_progress, done, canceled)",
                },
                "approve": {"type": "boolean", "description": "Must be true to update"},
            },
            "required": ["issue_id", "status", "approve"],
        },
    },
    {
        "name": "linear_list_teams",
        "description": "List all Linear teams in your workspace.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # ============================================
    # NOTION INTEGRATION TOOLS
    # ============================================
    {
        "name": "notion_search_pages",
        "description": "Search Notion pages by query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "filter_type": {
                    "type": "string",
                    "enum": ["page", "database"],
                    "description": "Filter by type",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "notion_list_recent_pages",
        "description": "List recently edited Notion pages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max pages to return (default: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "notion_get_page_content",
        "description": "Get the content of a Notion page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page ID or URL"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "notion_list_databases",
        "description": "List Notion databases in workspace.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "notion_create_page",
        "description": "Create a new Notion page. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"},
                "parent_id": {
                    "type": "string",
                    "description": "Parent page or database ID",
                },
                "content": {"type": "string", "description": "Page content (markdown)"},
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["title", "approve"],
        },
    },
    # ============================================
    # CONFLUENCE INTEGRATION TOOLS
    # ============================================
    {
        "name": "confluence_search_pages",
        "description": "Search Confluence pages by query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "space": {"type": "string", "description": "Filter by space key"},
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 20)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "confluence_get_page",
        "description": "Get a Confluence page content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Page ID"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "confluence_list_pages_in_space",
        "description": "List pages in a Confluence space.",
        "input_schema": {
            "type": "object",
            "properties": {
                "space_key": {"type": "string", "description": "Space key"},
                "limit": {"type": "integer", "description": "Max pages (default: 50)"},
            },
            "required": ["space_key"],
        },
    },
    # ============================================
    # MULTI-CLOUD TOOLS
    # ============================================
    {
        "name": "cloud_compare_services",
        "description": "Compare equivalent services across AWS, GCP, and Azure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "description": "Service type (compute, storage, database, serverless, etc.)",
                },
                "providers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Providers to compare (aws, gcp, azure)",
                },
            },
            "required": ["service_type"],
        },
    },
    {
        "name": "cloud_generate_multi_region",
        "description": "Generate multi-region infrastructure configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Cloud provider",
                },
                "regions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Regions to deploy",
                },
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Services to deploy",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["active-active", "active-passive", "pilot-light"],
                    "description": "HA strategy",
                },
            },
            "required": ["provider", "regions"],
        },
    },
    {
        "name": "cloud_migrate_provider",
        "description": "Generate migration plan between cloud providers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Source cloud",
                },
                "target_provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Target cloud",
                },
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Services to migrate",
                },
            },
            "required": ["source_provider", "target_provider"],
        },
    },
    {
        "name": "cloud_estimate_costs",
        "description": "Estimate cloud costs for a service configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Cloud provider",
                },
                "service_type": {"type": "string", "description": "Service type"},
                "requirements": {
                    "type": "object",
                    "description": "Resource requirements (cpu, memory, storage)",
                },
            },
            "required": ["provider", "service_type"],
        },
    },
    {
        "name": "cloud_generate_landing_zone",
        "description": "Generate cloud landing zone configuration with best practices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Cloud provider",
                },
                "environments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Environments (dev, staging, prod)",
                },
                "include_security": {
                    "type": "boolean",
                    "description": "Include security controls",
                },
                "include_networking": {
                    "type": "boolean",
                    "description": "Include VPC/network config",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "cloud_analyze_spend",
        "description": "Analyze cloud spending and suggest optimizations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure"],
                    "description": "Cloud provider",
                },
                "time_period": {
                    "type": "string",
                    "enum": ["7d", "30d", "90d"],
                    "description": "Analysis period",
                },
            },
            "required": ["provider"],
        },
    },
    # ============================================
    # ASANA PROJECT MANAGEMENT TOOLS
    # ============================================
    {
        "name": "asana_list_my_tasks",
        "description": "List Asana tasks assigned to you.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace ID or name"},
                "project": {"type": "string", "description": "Filter by project"},
                "completed": {
                    "type": "boolean",
                    "description": "Include completed tasks",
                },
            },
            "required": [],
        },
    },
    {
        "name": "asana_search_tasks",
        "description": "Search Asana tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "workspace": {"type": "string", "description": "Workspace to search"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "asana_list_projects",
        "description": "List Asana projects in workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace ID"},
                "archived": {
                    "type": "boolean",
                    "description": "Include archived projects",
                },
            },
            "required": [],
        },
    },
    {
        "name": "asana_create_task",
        "description": "Create a new Asana task. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Task name"},
                "project": {"type": "string", "description": "Project ID"},
                "notes": {"type": "string", "description": "Task description"},
                "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["name", "approve"],
        },
    },
    {
        "name": "asana_complete_task",
        "description": "Mark an Asana task as complete. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to complete",
                },
            },
            "required": ["task_id", "approve"],
        },
    },
    # ============================================
    # TRELLO PROJECT MANAGEMENT TOOLS
    # ============================================
    {
        "name": "trello_list_boards",
        "description": "List your Trello boards.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "trello_list_my_cards",
        "description": "List Trello cards assigned to you.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board": {"type": "string", "description": "Filter by board ID"},
            },
            "required": [],
        },
    },
    {
        "name": "trello_create_card",
        "description": "Create a new Trello card. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Card name"},
                "list_id": {"type": "string", "description": "List ID to add card to"},
                "description": {"type": "string", "description": "Card description"},
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["name", "list_id", "approve"],
        },
    },
    # ============================================
    # CLICKUP PROJECT MANAGEMENT TOOLS
    # ============================================
    {
        "name": "clickup_list_workspaces",
        "description": "List ClickUp workspaces.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "clickup_list_spaces",
        "description": "List spaces in a ClickUp workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Workspace ID"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "clickup_list_my_tasks",
        "description": "List ClickUp tasks assigned to you.",
        "input_schema": {
            "type": "object",
            "properties": {
                "list_id": {"type": "string", "description": "Filter by list"},
            },
            "required": [],
        },
    },
    {
        "name": "clickup_create_task",
        "description": "Create a new ClickUp task. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Task name"},
                "list_id": {"type": "string", "description": "List ID"},
                "description": {"type": "string", "description": "Task description"},
                "priority": {"type": "integer", "description": "Priority (1-4)"},
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["name", "list_id", "approve"],
        },
    },
    # ============================================
    # MONDAY.COM PROJECT MANAGEMENT TOOLS
    # ============================================
    {
        "name": "monday_list_boards",
        "description": "List Monday.com boards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {
                    "type": "string",
                    "description": "Filter by workspace",
                },
            },
            "required": [],
        },
    },
    {
        "name": "monday_list_items",
        "description": "List items in a Monday.com board.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Board ID"},
                "limit": {"type": "integer", "description": "Max items (default: 50)"},
            },
            "required": ["board_id"],
        },
    },
    {
        "name": "monday_get_my_items",
        "description": "Get Monday.com items assigned to you.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "monday_get_item",
        "description": "Get details of a specific Monday.com item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item ID"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "monday_create_item",
        "description": "Create a new Monday.com item. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "board_id": {"type": "string", "description": "Board ID"},
                "name": {"type": "string", "description": "Item name"},
                "column_values": {
                    "type": "object",
                    "description": "Column values to set",
                },
                "approve": {"type": "boolean", "description": "Must be true to create"},
            },
            "required": ["board_id", "name", "approve"],
        },
    },
    # ============================================
    # BITBUCKET INTEGRATION TOOLS
    # ============================================
    {
        "name": "bitbucket_list_my_prs",
        "description": "List Bitbucket pull requests you're involved in.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["OPEN", "MERGED", "DECLINED"],
                    "description": "PR state",
                },
                "role": {
                    "type": "string",
                    "enum": ["author", "reviewer"],
                    "description": "Your role",
                },
            },
            "required": [],
        },
    },
    {
        "name": "bitbucket_list_repos",
        "description": "List Bitbucket repositories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace slug"},
            },
            "required": ["workspace"],
        },
    },
    {
        "name": "bitbucket_get_pipeline_status",
        "description": "Get Bitbucket pipeline status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace slug"},
                "repo": {"type": "string", "description": "Repository slug"},
                "pipeline_uuid": {
                    "type": "string",
                    "description": "Pipeline UUID (optional, latest if not specified)",
                },
            },
            "required": ["workspace", "repo"],
        },
    },
    {
        "name": "bitbucket_add_pr_comment",
        "description": "Add comment to a Bitbucket PR. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace slug"},
                "repo": {"type": "string", "description": "Repository slug"},
                "pr_id": {"type": "integer", "description": "PR ID"},
                "content": {"type": "string", "description": "Comment content"},
                "approve": {"type": "boolean", "description": "Must be true to post"},
            },
            "required": ["workspace", "repo", "pr_id", "content", "approve"],
        },
    },
    # ============================================
    # SENTRY ERROR TRACKING TOOLS
    # ============================================
    {
        "name": "sentry_list_issues",
        "description": "List Sentry issues/errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project slug"},
                "status": {
                    "type": "string",
                    "enum": ["unresolved", "resolved", "ignored"],
                    "description": "Issue status",
                },
                "limit": {"type": "integer", "description": "Max issues (default: 25)"},
            },
            "required": ["project"],
        },
    },
    {
        "name": "sentry_get_issue",
        "description": "Get details of a Sentry issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string", "description": "Issue ID"},
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "sentry_list_projects",
        "description": "List Sentry projects in organization.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "sentry_resolve_issue",
        "description": "Resolve a Sentry issue. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string", "description": "Issue ID"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to resolve",
                },
            },
            "required": ["issue_id", "approve"],
        },
    },
    # ============================================
    # DATADOG MONITORING TOOLS
    # ============================================
    {
        "name": "datadog_list_monitors",
        "description": "List Datadog monitors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
            },
            "required": [],
        },
    },
    {
        "name": "datadog_get_alerting_monitors",
        "description": "Get Datadog monitors currently alerting.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "datadog_list_incidents",
        "description": "List Datadog incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "stable", "resolved"],
                    "description": "Filter by status",
                },
            },
            "required": [],
        },
    },
    {
        "name": "datadog_list_dashboards",
        "description": "List Datadog dashboards.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Filter by name"},
            },
            "required": [],
        },
    },
    {
        "name": "datadog_mute_monitor",
        "description": "Mute a Datadog monitor. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monitor_id": {"type": "string", "description": "Monitor ID"},
                "end_time": {
                    "type": "string",
                    "description": "Mute end time (ISO format)",
                },
                "approve": {"type": "boolean", "description": "Must be true to mute"},
            },
            "required": ["monitor_id", "approve"],
        },
    },
    # ============================================
    # PAGERDUTY INCIDENT MANAGEMENT TOOLS
    # ============================================
    {
        "name": "pagerduty_list_incidents",
        "description": "List PagerDuty incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["triggered", "acknowledged", "resolved"],
                    "description": "Filter by status",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["high", "low"],
                    "description": "Filter by urgency",
                },
            },
            "required": [],
        },
    },
    {
        "name": "pagerduty_get_oncall",
        "description": "Get current on-call schedule.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schedule_id": {
                    "type": "string",
                    "description": "Schedule ID (optional)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "pagerduty_list_services",
        "description": "List PagerDuty services.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "pagerduty_acknowledge_incident",
        "description": "Acknowledge a PagerDuty incident. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Incident ID"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to acknowledge",
                },
            },
            "required": ["incident_id", "approve"],
        },
    },
    {
        "name": "pagerduty_resolve_incident",
        "description": "Resolve a PagerDuty incident. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string", "description": "Incident ID"},
                "resolution_note": {"type": "string", "description": "Resolution note"},
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to resolve",
                },
            },
            "required": ["incident_id", "approve"],
        },
    },
    # ============================================
    # SNYK SECURITY SCANNING TOOLS
    # ============================================
    {
        "name": "snyk_list_vulnerabilities",
        "description": "List Snyk vulnerabilities in projects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Filter by severity",
                },
                "project": {"type": "string", "description": "Filter by project"},
            },
            "required": [],
        },
    },
    {
        "name": "snyk_list_projects",
        "description": "List Snyk projects.",
        "input_schema": {
            "type": "object",
            "properties": {
                "org": {"type": "string", "description": "Organization ID"},
            },
            "required": [],
        },
    },
    {
        "name": "snyk_get_security_summary",
        "description": "Get security summary across all projects.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "snyk_get_project_issues",
        "description": "Get security issues for a specific project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
            },
            "required": ["project_id"],
        },
    },
    # ============================================
    # SONARQUBE CODE QUALITY TOOLS
    # ============================================
    {
        "name": "sonarqube_list_projects",
        "description": "List SonarQube projects.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "sonarqube_list_issues",
        "description": "List SonarQube code issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project key"},
                "severity": {
                    "type": "string",
                    "enum": ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"],
                    "description": "Filter by severity",
                },
                "type": {
                    "type": "string",
                    "enum": ["BUG", "VULNERABILITY", "CODE_SMELL"],
                    "description": "Filter by type",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "sonarqube_get_quality_gate",
        "description": "Get quality gate status for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project key"},
            },
            "required": ["project"],
        },
    },
    # ============================================
    # FIGMA DESIGN TOOLS
    # ============================================
    {
        "name": "figma_list_files",
        "description": "List Figma files in a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "figma_get_file",
        "description": "Get Figma file details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "File key"},
            },
            "required": ["file_key"],
        },
    },
    {
        "name": "figma_get_comments",
        "description": "Get comments on a Figma file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "File key"},
            },
            "required": ["file_key"],
        },
    },
    {
        "name": "figma_list_projects",
        "description": "List Figma projects in a team.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Team ID"},
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "figma_add_comment",
        "description": "Add comment to a Figma file. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "File key"},
                "message": {"type": "string", "description": "Comment message"},
                "approve": {"type": "boolean", "description": "Must be true to post"},
            },
            "required": ["file_key", "message", "approve"],
        },
    },
    # ============================================
    # LOOM VIDEO TOOLS
    # ============================================
    {
        "name": "loom_list_videos",
        "description": "List Loom videos.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max videos (default: 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "loom_get_transcript",
        "description": "Get transcript of a Loom video.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "Video ID"},
            },
            "required": ["video_id"],
        },
    },
    {
        "name": "loom_search_videos",
        "description": "Search Loom videos by query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    # ============================================
    # DISCORD COMMUNICATION TOOLS
    # ============================================
    {
        "name": "discord_list_servers",
        "description": "List Discord servers the bot is in.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "discord_list_channels",
        "description": "List channels in a Discord server.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"},
            },
            "required": ["server_id"],
        },
    },
    {
        "name": "discord_get_messages",
        "description": "Get recent messages from a Discord channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Channel ID"},
                "limit": {
                    "type": "integer",
                    "description": "Max messages (default: 50)",
                },
            },
            "required": ["channel_id"],
        },
    },
    {
        "name": "discord_send_message",
        "description": "Send a message to a Discord channel. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Channel ID"},
                "content": {"type": "string", "description": "Message content"},
                "approve": {"type": "boolean", "description": "Must be true to send"},
            },
            "required": ["channel_id", "content", "approve"],
        },
    },
    # ============================================
    # ZOOM MEETING TOOLS
    # ============================================
    {
        "name": "zoom_list_recordings",
        "description": "List Zoom cloud recordings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "zoom_get_transcript",
        "description": "Get transcript of a Zoom recording.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string", "description": "Meeting ID"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "zoom_search_recordings",
        "description": "Search Zoom recordings by query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    # ============================================
    # GOOGLE CALENDAR TOOLS
    # ============================================
    {
        "name": "gcalendar_list_upcoming_events",
        "description": "List upcoming Google Calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (default: primary)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events (default: 10)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gcalendar_get_todays_events",
        "description": "Get today's Google Calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (default: primary)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gcalendar_get_event_details",
        "description": "Get details of a specific calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event ID"},
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (default: primary)",
                },
            },
            "required": ["event_id"],
        },
    },
    # ============================================
    # GOOGLE DRIVE TOOLS
    # ============================================
    {
        "name": "gdrive_list_files",
        "description": "List files in Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_id": {
                    "type": "string",
                    "description": "Folder ID (default: root)",
                },
                "limit": {"type": "integer", "description": "Max files (default: 20)"},
            },
            "required": [],
        },
    },
    {
        "name": "gdrive_search",
        "description": "Search Google Drive files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "mime_type": {"type": "string", "description": "Filter by MIME type"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "gdrive_get_file_content",
        "description": "Get content of a Google Drive file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "File ID"},
            },
            "required": ["file_id"],
        },
    },
    # ============================================
    # VERCEL DEPLOYMENT TOOLS
    # ============================================
    {
        "name": "vercel_list_projects",
        "description": "List Vercel projects.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "vercel_list_deployments",
        "description": "List Vercel deployments for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name or ID"},
                "limit": {
                    "type": "integer",
                    "description": "Max deployments (default: 20)",
                },
            },
            "required": ["project"],
        },
    },
    {
        "name": "vercel_get_deployment_status",
        "description": "Get status of a Vercel deployment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {
                    "type": "string",
                    "description": "Deployment ID or URL",
                },
            },
            "required": ["deployment_id"],
        },
    },
    {
        "name": "vercel_redeploy",
        "description": "Trigger a Vercel redeployment. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {
                    "type": "string",
                    "description": "Deployment ID to redeploy",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to redeploy",
                },
            },
            "required": ["deployment_id", "approve"],
        },
    },
    # ============================================
    # CIRCLECI CI/CD TOOLS
    # ============================================
    {
        "name": "circleci_list_pipelines",
        "description": "List CircleCI pipelines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_slug": {
                    "type": "string",
                    "description": "Project slug (gh/owner/repo or bb/owner/repo)",
                },
            },
            "required": ["project_slug"],
        },
    },
    {
        "name": "circleci_get_pipeline_status",
        "description": "Get CircleCI pipeline status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "string", "description": "Pipeline ID"},
            },
            "required": ["pipeline_id"],
        },
    },
    {
        "name": "circleci_trigger_pipeline",
        "description": "Trigger a CircleCI pipeline. Requires approval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_slug": {"type": "string", "description": "Project slug"},
                "branch": {
                    "type": "string",
                    "description": "Branch to build (default: main)",
                },
                "approve": {
                    "type": "boolean",
                    "description": "Must be true to trigger",
                },
            },
            "required": ["project_slug", "approve"],
        },
    },
    {
        "name": "circleci_get_job_status",
        "description": "Get CircleCI job status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number"},
                "project_slug": {"type": "string", "description": "Project slug"},
            },
            "required": ["job_number", "project_slug"],
        },
    },
]


# OpenAI-compatible function format for NAVI tools
# Converts Anthropic's input_schema format to OpenAI's parameters format
# Note: OpenAI has a maximum limit of 128 tools per API call
# NAVI_TOOLS has 191 tools, so we limit to the first 128 which includes all core tools
# (read_file, write_file, edit_file, run_command, search_files, etc.) and key integrations
# Also sanitizes tool names: OpenAI only allows ^[a-zA-Z0-9_-]+$ (no dots)
def _sanitize_openai_function_name(name: str) -> str:
    """Convert tool name to OpenAI-compatible format (replace dots with underscores)."""
    return name.replace(".", "_")


NAVI_FUNCTIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": _sanitize_openai_function_name(tool["name"]),
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }
    for tool in NAVI_TOOLS[:128]  # OpenAI API limit is 128 tools max
]

# Reverse mapping: OpenAI function name -> original NAVI tool name
OPENAI_TO_NAVI_TOOL_NAME = {
    _sanitize_openai_function_name(tool["name"]): tool["name"]
    for tool in NAVI_TOOLS[:128]
}
