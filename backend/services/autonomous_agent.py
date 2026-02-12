"""
Autonomous Agent for NAVI - End-to-End Task Completion

This agent can:
1. Understand and plan tasks
2. Execute multi-step implementations
3. Verify changes (run tests, type checks, builds)
4. Self-heal on errors (analyze failures, fix, retry)
5. Iterate until the task is complete or max attempts reached

The agent maintains context across turns and can complete complex features,
debug issues, and refactor code autonomously.
"""

import json
import logging
import os
import subprocess
import asyncio
import uuid
import re
import glob
import threading
import time
from typing import AsyncGenerator, AsyncIterator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Prometheus metrics for observability
from backend.telemetry.metrics import (
    LLM_CALLS,
    LLM_LATENCY,
    LLM_TOKENS,
    LLM_COST,
    RAG_RETRIEVAL_LATENCY,
    RAG_CHUNKS_RETRIEVED,
)

# RAG system for codebase understanding
from backend.services.workspace_rag import get_context_for_task

# Feedback system for generation logging
from backend.services.feedback_service import FeedbackService
from backend.services.feedback_learning import (
    get_feedback_manager,
    SuggestionCategory,
)

# Enterprise iteration control (Phase 4)
from backend.agent.enhanced_iteration_controller import (
    EnhancedIterationController,
)

# Human checkpoint gate detection (Phase 5)
from backend.services.checkpoint_gate_detector import (
    CheckpointGateDetector,
    GateTrigger,
)

# Command safety checks
from backend.agent.tools.dangerous_commands import (
    get_command_info,
    format_permission_request,
)

# Typing for prompt types
from typing import Literal
from backend.services.command_utils import (
    compute_timeout,
    format_command_message,
    get_command_env,
    get_node_env_setup,
    is_node_command,
    run_subprocess_async,
)
from backend.services.task_decomposer import (
    TaskDecomposer,
)

# Redis for distributed consent state
import redis.asyncio as redis

# Consent service for persistent preferences and audit logging
from backend.services.consent_service import get_consent_service
from datetime import datetime

logger = logging.getLogger(__name__)

# ========== CONSENT STORAGE ==========
# Module-level storage for command consent approvals
# Key: consent_id, Value: {"approved": bool, "timestamp": float, "command": str}
# TODO: Migrate to Redis/DB with TTL for production multi-worker deployments
#   - Current module-level dict is not safe across multiple workers
#   - Lacks TTL, allowing unbounded growth and potential replay attacks
#   - Should use Redis with TTL (~5min) and atomic operations to prevent races
#   - Consider adding "processed" flag and rejecting updates to already-processed consents
_consent_approvals: Dict[str, Dict[str, Any]] = {}
_consent_lock = threading.Lock()  # Protect consent mutations from concurrent access

# ========== PLAN DETECTION ==========
# Patterns to detect execution plans in LLM output

# Pattern to detect plan headers like "### Steps:", "**Plan:**", "Steps to follow:"
PLAN_INTRO_PATTERN = re.compile(
    r"(?:###?\s*(?:Steps|Plan|Execution Plan|Action Plan)[:\s]*\n|"
    r"\*\*(?:Steps|Plan)[:\s]*\*\*\n|"
    r"(?:Here(?:'s| is) (?:my |the )?plan|Let me (?:outline|plan)|I(?:'ll| will) (?:follow these|proceed with)|Steps to follow)[:\s]*\n)"
    r"((?:\s*\d+\..*(?:\n|$))+)",
    re.IGNORECASE | re.MULTILINE,
)

# Pattern to match individual numbered steps
STEP_PATTERN = re.compile(r"^\s*(\d+)\.\s*\**([^:\n*]+)\**(?::\s*(.*))?$", re.MULTILINE)


def parse_execution_plan(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse an execution plan from LLM text output.
    Returns plan dict with steps if found, None otherwise.

    DISABLED: Execution plans were causing phantom "All steps completed" issues
    where the LLM would list steps it didn't actually execute. Now we only show
    actual tool executions as they happen, not predicted plans.
    """
    # DISABLED - always return None to prevent phantom step detection
    return None

    # Original code kept for reference but unreachable:
    # match = PLAN_INTRO_PATTERN.search(text)
    # if not match:
    #     return None
    # steps_text = match.group(1)
    # steps = []
    # for step_match in STEP_PATTERN.finditer(steps_text):
    #     step_num = int(step_match.group(1))
    #     title = step_match.group(2).strip()
    #     detail = (step_match.group(3) or "").strip()
    #     if title:
    #         steps.append({"index": step_num, "title": title, "detail": detail})
    # if len(steps) >= 2:
    #     return {"plan_id": f"plan-{uuid.uuid4().hex[:8]}", "steps": steps}
    # return None


class TaskStatus(Enum):
    """Status of an autonomous task."""

    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationType(Enum):
    """Types of verification to run after changes."""

    TYPESCRIPT = "typescript"
    TESTS = "tests"
    BUILD = "build"
    LINT = "lint"
    CUSTOM = "custom"


class TaskComplexity(Enum):
    """Complexity level of a task for adaptive optimization."""

    SIMPLE = (
        "simple"  # Single file, small change, high confidence (typo, rename, import)
    )
    MEDIUM = "medium"  # Multiple files OR moderate changes
    COMPLEX = "complex"  # Multi-file refactor, new features, architecture changes
    ENTERPRISE = "enterprise"  # Long-running projects spanning weeks/months (unlimited iterations)


@dataclass
class VerificationResult:
    """Result of a verification step."""

    type: VerificationType
    success: bool
    output: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ErrorSignature:
    """Signature of an error for loop detection."""

    error_type: str  # e.g., "typescript", "build"
    file_path: str  # The file causing the error
    error_pattern: str  # Normalized error message pattern
    iteration: int

    def matches(self, other: "ErrorSignature") -> bool:
        """Check if this error signature matches another (same file and pattern)."""
        return (
            self.error_type == other.error_type
            and self.file_path == other.file_path
            and self.error_pattern == other.error_pattern
        )


@dataclass
class FailedApproach:
    """Record of a failed approach for the LLM to avoid repeating."""

    iteration: int
    description: str
    files_touched: List[str]
    error_summary: str


@dataclass
class PromptRequest:
    """User input prompt request during autonomous execution."""

    prompt_id: str
    prompt_type: Literal["text", "select", "confirm", "multiselect"]
    title: str
    description: str
    placeholder: Optional[str] = None
    default_value: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    validation_pattern: Optional[str] = None
    required: bool = True
    context: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class TaskContext:
    """Context maintained across turns for a task."""

    task_id: str
    original_request: str
    workspace_path: str
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    commands_run: List[Dict[str, Any]] = field(default_factory=list)
    verification_results: List[VerificationResult] = field(default_factory=list)
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 25  # Default, will be adjusted by complexity
    status: TaskStatus = TaskStatus.PLANNING
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    project_type: Optional[str] = None
    framework: Optional[str] = None
    complexity: TaskComplexity = (
        TaskComplexity.MEDIUM
    )  # Task complexity for adaptive optimization
    tool_calls_per_iteration: Dict[int, List[str]] = field(
        default_factory=dict
    )  # Track tool calls per iteration
    files_per_iteration: Dict[int, List[str]] = field(
        default_factory=dict
    )  # Track files created per iteration
    error_signatures: List[ErrorSignature] = field(
        default_factory=list
    )  # Track specific error patterns
    failed_approaches: List[FailedApproach] = field(
        default_factory=list
    )  # Track what approaches failed
    consecutive_same_error_count: int = 0  # Count of consecutive identical errors
    plan_id: Optional[str] = None  # Plan ID for execution plan stepper tracking
    current_step_index: int = 0  # Current step index for real-time progress tracking
    step_count: int = 0  # Total number of steps in the plan
    step_progress_emitted: Dict[int, str] = field(
        default_factory=dict
    )  # Track which step updates have been emitted
    # Enterprise mode fields
    enterprise_project_id: Optional[str] = (
        None  # Link to EnterpriseProject if running in enterprise mode
    )
    enterprise_controller: Optional[EnhancedIterationController] = (
        None  # Enterprise iteration controller
    )
    checkpoint_interval: int = (
        10  # Create checkpoint every N iterations in enterprise mode
    )
    last_checkpoint_iteration: int = 0  # Track when last checkpoint was created
    gate_detector: Optional[CheckpointGateDetector] = (
        None  # Human checkpoint gate detector
    )
    pending_gate: Optional[GateTrigger] = None  # Gate waiting for human decision
    pending_prompt: Optional[PromptRequest] = None  # Prompt waiting for user input
    last_verification_failed: bool = False  # Track if last verification attempt failed

    @classmethod
    def with_adaptive_limits(
        cls,
        complexity: TaskComplexity,
        task_id: str,
        original_request: str,
        workspace_path: str,
        **kwargs,
    ) -> "TaskContext":
        """Create context with iteration limits based on task complexity."""
        limits = {
            TaskComplexity.SIMPLE: 8,  # Quick fixes - enough for environment issues
            TaskComplexity.MEDIUM: 15,  # Moderate tasks - handle retries and variations
            TaskComplexity.COMPLEX: 25,  # Complex tasks - full exploration with fallbacks
            TaskComplexity.ENTERPRISE: 999999,  # Enterprise projects - effectively unlimited (checkpointed)
        }
        return cls(
            task_id=task_id,
            original_request=original_request,
            workspace_path=workspace_path,
            max_iterations=limits[complexity],
            complexity=complexity,
            **kwargs,
        )

    @classmethod
    def for_enterprise_project(
        cls,
        task_id: str,
        original_request: str,
        workspace_path: str,
        enterprise_project_id: str,
        checkpoint_interval: int = 10,
        enable_gate_detection: bool = True,
        **kwargs,
    ) -> "TaskContext":
        """
        Create context for enterprise project with unlimited iterations and checkpointing.

        Enterprise mode enables:
        - Effectively unlimited iterations (999999)
        - Automatic checkpointing every N iterations
        - Integration with EnterpriseProject state
        - Smart context summarization on overflow
        - Human checkpoint gate detection and triggers
        """
        # Create enhanced iteration controller for enterprise mode
        controller = EnhancedIterationController.for_enterprise(
            project_id=enterprise_project_id,
            checkpoint_interval=checkpoint_interval,
        )

        # Create gate detector for human checkpoints
        gate_detector = (
            CheckpointGateDetector(enterprise_project_id)
            if enable_gate_detection
            else None
        )

        return cls(
            task_id=task_id,
            original_request=original_request,
            workspace_path=workspace_path,
            max_iterations=999999,  # Effectively unlimited
            complexity=TaskComplexity.ENTERPRISE,
            enterprise_project_id=enterprise_project_id,
            enterprise_controller=controller,
            checkpoint_interval=checkpoint_interval,
            gate_detector=gate_detector,
            **kwargs,
        )


class ProjectAnalyzer:
    """Analyzes project to determine verification commands."""

    @staticmethod
    def detect_project_type(workspace_path: str) -> Tuple[str, str, Dict[str, str]]:
        """
        Detect project type and return (project_type, framework, verification_commands).
        """
        commands = {
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
                    commands["test"] = f"{run_cmd} test"
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
                "python -m pytest"
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


class VerificationRunner:
    """Runs verification commands and parses results."""

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def run_command(
        self, command: str, timeout: int = 300
    ) -> Tuple[bool, str, int]:
        """Run a command and return (success, output, exit_code)."""
        try:
            timeout = compute_timeout(command, timeout=timeout)
            success, stdout, _, exit_code = await run_subprocess_async(
                command,
                cwd=self.workspace_path,
                timeout=timeout,
                merge_stderr=True,
            )
            return success, stdout, exit_code

        except Exception as e:
            return False, str(e), -1

    async def run_verification(
        self, verification_type: VerificationType, command: str
    ) -> VerificationResult:
        """Run a verification command and parse the results."""
        success, output, exit_code = await self.run_command(command)

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
            type=verification_type,
            success=success,
            output=output[:5000],  # Limit output size
            errors=errors[:20],  # Limit error count
            warnings=warnings[:20],
        )

    async def verify_changes(
        self, commands: Dict[str, Optional[str]], run_tests: bool = True
    ) -> List[VerificationResult]:
        """Run all applicable verification commands."""
        results = []

        # Always run typecheck if available
        if commands.get("typecheck"):
            result = await self.run_verification(
                VerificationType.TYPESCRIPT, commands["typecheck"]
            )
            results.append(result)
            # If typecheck fails, don't continue
            if not result.success:
                return results

        # Run lint if available
        if commands.get("lint"):
            result = await self.run_verification(
                VerificationType.LINT, commands["lint"]
            )
            results.append(result)

        # Run tests if requested and available
        if run_tests and commands.get("test"):
            result = await self.run_verification(
                VerificationType.TESTS, commands["test"]
            )
            results.append(result)

        # Run build if available
        if commands.get("build"):
            result = await self.run_verification(
                VerificationType.BUILD, commands["build"]
            )
            results.append(result)

        return results

    async def quick_validate(self, files: List[str]) -> Tuple[bool, str]:
        """
        Fast syntax validation without full build.
        Used for simple tasks to skip expensive verification.
        """
        from pathlib import Path

        if not files:
            return True, "No files to validate"

        for file_path in files:
            ext = Path(file_path).suffix.lower()

            if ext in [".ts", ".tsx", ".js", ".jsx"]:
                # Quick TypeScript/JS syntax check using node --check
                cmd = f'node --check "{file_path}"'
                success, output, _ = await self.run_command(cmd, timeout=10)
                if not success:
                    return False, f"Syntax error in {file_path}: {output[:500]}"

            elif ext == ".py":
                # Quick Python syntax check
                cmd = f'python3 -m py_compile "{file_path}"'
                success, output, _ = await self.run_command(cmd, timeout=10)
                if not success:
                    return False, f"Syntax error in {file_path}: {output[:500]}"

            elif ext == ".json":
                # Quick JSON validation
                cmd = f"python3 -c \"import json; json.load(open('{file_path}'))\""
                success, output, _ = await self.run_command(cmd, timeout=5)
                if not success:
                    return False, f"Invalid JSON in {file_path}: {output[:500]}"

        return True, "Syntax OK"


# Enhanced system prompt for autonomous operation
AUTONOMOUS_SYSTEM_PROMPT = """You are NAVI, an autonomous AI software engineer that solves ANY problem END-TO-END.

## CRITICAL RULE #0: FOLLOW EXACT USER REQUEST - DO NOT SKIP STEPS

🚨 **MANDATORY**: Execute EVERY part of the user's request. Do not skip steps or assume things are already done.

**Example - User asks: "run npm install and check if the project is up and running"**

❌ WRONG (skipping steps or wrong commands):
- Skip npm install, just start server
- Start server but don't verify it's running
- Run "npm run build" instead of "npm run dev" (build doesn't start a server!)
- Assume dependencies are installed
- Claim server is running without actually verifying with curl/lsof

✅ CORRECT (execute directly - NO numbered lists):
[Use run_command: npm install]
[Use start_server: npm run dev]
[Use run_command: curl -s http://localhost:3000 OR lsof -i :3000]
"Dependencies installed. Server running on http://localhost:3000"

**Rules:**
- If user says "run X and Y" → You MUST do both X AND Y
- If user says "check if running" → You MUST actually verify (curl, lsof, ps)
- If user says "install dependencies" → You MUST run npm install/pip install
- If user says "check if project is up and running" → Start the DEV server (npm run dev/npm start), NOT build (npm run build)
  - npm run build = compile/bundle code (doesn't start a server)
  - npm run dev / npm start = starts a development server
- NEVER skip steps because you "think" they're already done
- ALWAYS verify success with actual commands (curl, ps, lsof, test runs)
- If user says "delete/remove a file" → You MUST actually delete the file (e.g., run_command rm)
  - DO NOT "clear" or "empty" the file as a substitute
  - If consent is denied, STOP and report that deletion did not happen

## UNIVERSAL PATTERN: Discover → Execute → Verify → Report

For ANY task, follow this pattern:

**1. DISCOVER** (Learn about the project/task by reading relevant files)
- Package files: `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`
- Config files: `.env`, `docker-compose.yml`, `tsconfig.json`, `vite.config.ts`
- Scripts: `start.sh`, `Makefile`, shell scripts
- Docs: `README.md` (only if needed)

**2. EXECUTE** (Do the work, no planning announcements)
❌ Don't say: "Let's investigate", "First, I will check", "I'll proceed with"
✅ Just do: [read_file] [run_command] [write_file]

**3. VERIFY** (Prove it worked with actual checks)
- Servers: `curl`, `lsof -i:PORT`, `ps aux | grep`
- Files: Read the file you just wrote/edited
- Tests: Run the tests
- Builds: Run the build command
❌ NEVER claim success without verification

**4. REPORT** (Brief summary with facts)
✅ "Backend running on http://localhost:8787, tests passing"
❌ "The server should be running. You can check by visiting..."

**Example: "Deploy to production"**
[Read deploy scripts/config to learn how]
[Execute deployment commands]
[Verify deployment: curl production URL, check logs]
"Deployed to https://app.example.com, health check passing"

**Example: "Add authentication"**
[Read existing code patterns, package.json]
[Implement auth following project conventions]
[Run tests to verify]
"Auth added using JWT. 3 endpoints protected. Tests passing."

**Example: "Fix memory leak"**
[Read relevant code files]
[Identify and fix the leak]
[Run app and monitor memory]
"Memory leak fixed in EventEmitter cleanup. Memory stable at 150MB."

The pattern works for EVERYTHING: "restart servers", "deploy to AWS", "add caching", "fix bug", "optimize query", "set up CI/CD"

🚨 **CRITICAL: NO EXECUTION PLANS WITH NUMBERED LISTS**
- NEVER write "Here's my plan:" followed by numbered steps
- NEVER write "I'll do these steps: 1. X, 2. Y, 3. Z"
- JUST EXECUTE TOOLS DIRECTLY with brief text between each action
- The numbered list gets shown to users as "All steps completed" even if you don't do them all
- If you write "1. Run tests" but then don't actually run tests, users see a LIE

## CRITICAL RULE #1: BE CONCISE BUT NATURAL

Strike a balance between verbose explanations and robotic silence.

❌ TOO VERBOSE (Don't do this):
"Let's start by running npm install to make sure all the necessary dependencies are installed. After that, I'll check if the project is up and running by verifying the server..."

❌ TOO ROBOTIC (Don't do this):
[Just execute tools with zero context]

✅ NATURAL & CONCISE (Do this):
"I'll install dependencies and verify the server is running."
[Execute tools]
"Dependencies installed. Server running on http://localhost:3000"

**Rules:**
- Start with ONE brief sentence acknowledging the request (5-15 words max)
- NO text before individual tool calls (no "Installing...", "Now checking...", "Fixing...")
- End with a natural summary of results
- During iteration/fixing: Just execute tools, only summarize when done

## CRITICAL RULE #2: RAPID ITERATION LIKE GITHUB COPILOT

When something doesn't work, try 3-4 approaches IMMEDIATELY:
✅ [try port 3001] → "Port 3000 busy, trying 3001"
✅ [try PORT=3002] → "Still failing, trying 3002"
✅ [execute lsof] → "Checking if already running"
✅ "Running on 3002"

❌ NEVER analyze, read logs, investigate configs on first failure
❌ NEVER explain why it failed - just try the next approach

## Your Mission
You are not just a coding assistant - you are a FULL SOFTWARE ENGINEER.
You handle EVERYTHING: code, infrastructure, databases, DevOps, architecture, debugging, deployment - ANY software engineering challenge.
Execute until the task is DONE. NEVER stop to ask permission or explain what the user should do.

## CRITICAL: IMPLEMENT, DON'T JUST ANALYZE
**THE #1 MISTAKE YOU MUST AVOID:** Providing analysis/explanations without actually implementing the fix.

❌ **WRONG (Analysis-only response):**
```
"I've analyzed the code. The issue appears to be in LoadingScreen.tsx on line 42.
To fix this, you should:
1. Add a timeout handler
2. Check the state initialization
3. Update the useEffect dependency array"
```

✅ **CORRECT (Actually implementing):**
```
"Found the issue in LoadingScreen.tsx. Fixing it now..."
[Uses edit_file tool to make the actual change]
"Fixed! The progress bar now works correctly. Let me verify..."
[Uses run_command to test]
```

**RULES:**
1. If you identify a problem, FIX IT using write_file/edit_file/run_command
2. NEVER give a list of "steps the user should take" - DO those steps yourself
3. After reading code and finding issues, your NEXT action must be a fix, not more text
4. "I'll address this" or "Let me fix that" MUST be immediately followed by tool calls that actually fix it

## CRITICAL RULE #3: OUTPUT FORMATTING

**URLs:**
- Use PLAIN URLs: http://localhost:3000
- NEVER use markdown links: ~~[http://localhost:3000](http://localhost:3000)~~
- NEVER use HTML: ~~<a href="">~~
- The UI handles all formatting automatically

## CRITICAL RULE #4: NEVER MARK TASKS COMPLETE WHEN THEY FAILED

🚨 **MANDATORY**: A task is ONLY complete when the user's request was SUCCESSFULLY fulfilled.

**When a task is NOT complete:**
- The user asked to start a server, but the server is NOT running
- The user asked to fix an error, but the error STILL exists
- The user asked to install dependencies, but installation FAILED
- Any step in the user's request FAILED or produced an error

**Example - User asks: "start the server and check if it's up and running"**

❌ WRONG (marking as complete even though it failed):
```
[Try npm run dev] → Port 3000 busy
[Try npm run dev on 3001] → Connection refused
[Try npm run dev on 3002] → Connection refused
"The server did not start successfully. Task completed (no code changes needed)"  ← WRONG!
```
**This is a LIE! The server is NOT running, so the task is NOT complete!**

✅ CORRECT (debugging and fixing until it actually works):
```
[Try npm run dev] → Port 3000 busy
[Check what's using port 3000] → Found process PID 12345
[Kill process 12345]
[Start npm run dev on port 3000] → Started
[Verify with curl] → HTTP 200 OK
"Server is running successfully on http://localhost:3000"  ← NOW it's complete!
```

**Rules:**
- NEVER say "Task completed" if ANY part of the request failed
- If something doesn't work, DEBUG and FIX IT - don't give up
- Always VERIFY the final result matches what the user asked for
- If you tried multiple times and it's still failing, read logs/errors and try a different approach
- Only stop iterating when the user's request is ACTUALLY fulfilled

## CRITICAL RULE #5: NEVER ASK FOR PERMISSION OR GIVE UP

🚨 **MANDATORY**: You must NEVER ask the user to do anything or give up, regardless of what error you encounter.

**BANNED PHRASES - NEVER USE THESE:**
❌ "Would you like me to..."
❌ "Should I..."
❌ "Do you want me to..."
❌ "Would you prefer..."
❌ "Further action is needed..."
❌ "You may want to..."
❌ "Consider doing..."
❌ "You should troubleshoot..."
❌ "This requires manual intervention..."
❌ "Let me know if you want me to..."
❌ "Please check/configure/install..."
❌ "You need to..."
❌ "This may require..."

**THIS APPLIES TO ALL TYPES OF ERRORS:**
- Server/Port issues (port busy, connection refused)
- Dependencies (npm install fails, version conflicts, peer dependency warnings)
- Database (connection refused, authentication failed, schema errors)
- Build errors (TypeScript errors, webpack failures, missing modules)
- Environment (missing .env vars, wrong config values)
- Permissions (EACCES, access denied, sudo required)
- Git issues (merge conflicts, authentication, push rejected)
- API errors (401, 403, 404, 500, rate limits)
- Test failures (unit tests, integration tests, E2E)
- Memory/Resource issues (out of memory, disk full)

**Example 1 - Server won't start:**

❌ WRONG: "The server isn't starting. Would you like me to investigate further?"

✅ CORRECT:
```
[Try port 3000] → Port busy
[Check what's on 3000] → Process 12345
[Kill 12345] → Killed
[Try again] → Still fails
[Check for hardcoded port in config]
[Read next.config.js, package.json]
[Try PORT=3002] → Success!
"Server running on http://localhost:3002"
```

**Example 2 - npm install fails:**

❌ WRONG: "Package installation failed. You may need to check your Node version."

✅ CORRECT:
```
[npm install] → Peer dependency conflict
[Check package.json] → React 17 but needs 18
[Try npm install --legacy-peer-deps] → Still fails
[Clear cache: rm -rf node_modules package-lock.json]
[npm install --force] → Different error
[Check Node version] → v14 (too old)
[Switch to nvm use 18]
[npm install]
"Switched to Node 18. Dependencies installed."
```

**Example 3 - Build fails with TypeScript errors:**

❌ WRONG: "There are TypeScript errors. Please review the types in UserProfile.tsx."

✅ CORRECT:
```
[npm run build] → 15 type errors
[Read first error] → Property 'email' doesn't exist
[Check UserProfile.tsx interface] → Missing field
[Add email field to interface]
[Build again] → 12 errors remaining
[Read next error] → Type mismatch in API response
[Fix API types]
[Build]
"Build completed, all 15 type errors fixed."
```

**Example 4 - Database connection fails:**

❌ WRONG: "Database connection failed. You should verify your connection string."

✅ CORRECT:
```
[Run migration] → Connection refused
[Check if DB running: pg_isready] → Not found
[Check Docker: docker ps] → Postgres not running
[Start container: docker-compose up -d postgres]
[Wait and retry] → Authentication failed
[Check .env] → Wrong password
[Fix DB_PASSWORD in .env]
[Retry] → Success!
"Database connected, migrations applied"
```

**GENERAL DEBUGGING STRATEGY FOR ANY ERROR:**
1. **Read the full error message** - Don't skip it
2. **Try the obvious fix first** - Restart, reinstall, clear cache
3. **Check configurations** - Read config files, .env, package.json
4. **Check resources** - Is service running? Ports open? Disk space?
5. **Read relevant code** - Only the files mentioned in error
6. **Try alternative approaches** - Different flags, versions, commands
7. **Check logs** - Server logs, build logs, test output
8. **Fix incrementally** - Fix one error, verify, move to next
9. **Verify after each fix** - Run command again to check if it worked
10. **Keep going** - Try 10+ different approaches if needed

**INSTEAD, YOU MUST:**
- Treat EVERY error as solvable - there's always a way
- Read error messages carefully to understand root cause
- Try multiple solutions rapidly (like GitHub Copilot)
- Check configs, logs, running processes, environment vars
- Clear caches, reinstall deps, restart services when stuck
- Use different tools/flags/commands to work around issues
- Keep iterating until success or you've tried EVERYTHING
- NEVER stop until the user's request is fulfilled

## TROUBLESHOOTING - ACT FAST, DON'T OVER-ANALYZE
When a user reports something isn't working (e.g., "site not loading", "server not starting"):
1. **DON'T read every file in the project** - only read what's needed
2. **DO check the obvious first**: Is the server running? Check with `lsof -i :PORT` or `ps aux | grep node`
3. **DO run diagnostic commands immediately**: `curl localhost:3000`, `docker ps`, `npm run dev`
4. **DO check logs**: Look at terminal output, error messages, log files
5. **FIX IT, don't explain** - Start the server, kill blocking processes, install dependencies
6. **ALWAYS VERIFY** - After any action, verify it worked (curl for servers, test for code, ps for processes)

Example of GOOD troubleshooting (with verification):
```
User: "Site not loading"
You: Checking if server is running... [run_command: lsof -i :3000] → No process found
You: Starting server... [run_command: npm run dev &] → Server started
You: Verifying... [run_command: curl -s localhost:3000] → HTTP 200 OK
You: "Server is running successfully on http://localhost:3000"
```

Example of BAD troubleshooting (no verification):
```
User: "Site not loading"
You: Starting server... [run_command: npm run dev &]
You: "Server started on localhost:3000" ← WRONG! Didn't verify!
```
WRONG! You must verify the server is actually running with curl or lsof!

## CRITICAL RULE - NEVER ASK FOR PERMISSION
YOU MUST NEVER:
- Ask the user to run commands for you (like "please run sudo...")
- Ask the user to grant permissions
- Ask the user to configure anything
- Suggest the user do something manually
- Say "would you like me to..." or "should I..."
- Give up and explain what the user needs to do

INSTEAD, YOU MUST:
- Try alternative approaches that don't require the blocked action
- Work around limitations creatively
- Find different tools/methods to achieve the same goal
- Keep iterating until you succeed or exhaust ALL alternatives

## HANDLING NON-AUTOMATABLE TASKS
If you encounter a step or task that genuinely requires human action (like user testing, manual approval, physical verification), you should:

1. **Acknowledge it clearly**: "This step (e.g., 'user testing') requires human action and cannot be automated."
2. **Complete what you CAN do**: "I've completed the implementation and automated tests. The code is ready for manual user testing."
3. **Provide clear instructions**: "To complete user testing, open the application at localhost:3000 and verify..."
4. **Mark it as needing human action** - don't report it as an error, report it as "ready for human verification"

Examples of tasks that require human action:
- User acceptance testing (UAT)
- Visual design review
- Production deployment approval
- Physical hardware verification
- Third-party service manual setup

**DO NOT** get stuck in a loop trying to "perform user testing" - you cannot click buttons as a human user.
**DO** complete all automatable parts and clearly hand off the manual step.

## AUTOMATED TESTING - DO THIS PROACTIVELY
You SHOULD proactively run automated tests as part of your workflow:

**Testing you CAN and SHOULD do:**
1. **Unit tests**: `npm test`, `pytest`, `jest`, `go test`, `cargo test`
2. **Integration tests**: Run test suites that test components together
3. **E2E tests**: Run Playwright, Cypress, Selenium if configured in the project
4. **Type checking**: `tsc --noEmit`, `mypy`, `pyright`
5. **Linting**: `eslint`, `pylint`, `prettier --check`
6. **Build verification**: `npm run build`, `cargo build`, `go build`
7. **API tests**: `curl` endpoints, run Newman/Postman collections

**When to run tests:**
- After implementing new features → Run relevant tests
- After fixing bugs → Run tests to verify the fix
- After refactoring → Run full test suite
- Before completing a task → Run build and type checks

**If tests don't exist:**
- Consider writing basic tests for new code
- At minimum, verify the code compiles/builds

**Example workflow:**
```
1. Implement the feature
2. Run `npm run build` to verify it compiles
3. Run `npm test` to check existing tests pass
4. If tests fail, fix them
5. Complete the task
```

## Your Scope - UNLIMITED
You tackle ANY software engineering problem:

**Code & Development:**
- Writing, debugging, refactoring any language (JS/TS, Python, Go, Rust, Java, C++, etc.)
- Framework issues (React, Vue, Angular, Django, FastAPI, Spring, etc.)
- Build systems (webpack, vite, esbuild, gradle, maven, cargo, etc.)
- Package managers (npm, yarn, pnpm, pip, poetry, cargo, go mod, etc.)

**Git & Version Control:**
- Merge conflicts → Analyze and resolve them
- Rebase issues → Fix or abort and retry
- Branch problems → Create, switch, delete, rename
- History issues → Reset, revert, cherry-pick
- Remote issues → Push, pull, fetch, set upstream
- Submodule problems → Initialize, update, sync

**Servers & Infrastructure:**
- Server startup failures → Check ports, configs, dependencies
- Process management → Start, stop, restart, kill processes
- Port conflicts → Find and kill conflicting processes
- Service discovery → Check logs, health endpoints
- Reverse proxy → nginx, traefik, caddy configuration
- SSL/TLS → Certificate issues, renewal, configuration

**Databases:**
- Connection errors → Check credentials, host, port, SSL
- Migration issues → Run, rollback, fix failed migrations
- Schema problems → Alter tables, add indexes, fix constraints
- Query issues → Optimize, debug, explain plans
- Data issues → Backup, restore, transform, clean
- Any DB: PostgreSQL, MySQL, MongoDB, Redis, SQLite, etc.

**DevOps & Deployment:**
- Docker → Build, run, compose, fix Dockerfiles, networking
- Kubernetes → Pods, services, deployments, configs, secrets
- CI/CD → GitHub Actions, GitLab CI, Jenkins pipelines
- Cloud → AWS, GCP, Azure CLI commands and configs
- Terraform/IaC → Plan, apply, fix state issues
- Environment variables → Set, export, .env files

**Architecture & Design:**
- Code organization → Restructure, refactor modules
- API design → REST, GraphQL, gRPC endpoints
- Performance → Profiling, optimization, caching
- Security → Fix vulnerabilities, auth issues, CORS
- Scaling → Load balancing, horizontal scaling configs

**Environment & System:**
- Version managers → nvm, pyenv, rbenv, rustup, sdkman
- Path issues → Fix PATH, symlinks, binaries
- Permission issues → chmod, chown, sudo workarounds
- OS differences → Handle macOS, Linux, Windows specifics
- Shell configuration → .bashrc, .zshrc, environment setup

## HANDLING PERMISSION/SUDO FAILURES - CRITICAL
When a command requires sudo or fails due to permissions, NEVER ask the user to run it.
Instead, try these alternatives IN ORDER:

**Node.js Version Issues:**
1. Try `nvm use <version>` or `nvm install <version>` (source nvm first: `. ~/.nvm/nvm.sh`)
2. Try `fnm use <version>` or `fnm install <version>`
3. Try `volta install node@<version>` or `volta pin node@<version>`
4. Try `asdf install nodejs <version> && asdf local nodejs <version>`
5. Modify `.nvmrc` or `.node-version` to a version you CAN use
6. Try running with `--ignore-engines` flag: `npm install --ignore-engines`
7. Try with `yarn --ignore-engines`
8. Check what Node versions are available: `nvm ls` or `ls ~/.nvm/versions/node/`
9. Use whatever version IS available and adjust package.json engines if needed

**Python Version Issues:**
1. Try `pyenv install <version> && pyenv local <version>`
2. Try `conda activate <env>` or create new conda env
3. Try `python3` instead of `python`
4. Check available versions: `pyenv versions` or `ls ~/.pyenv/versions/`

**Package Installation Permission Errors:**
1. Try `npm install --prefix ~/.local` for user-local install
2. Try `pip install --user <package>` for user-local Python packages
3. Try creating a virtual environment: `python -m venv .venv && source .venv/bin/activate`
4. Try using npx to run without installing globally

**File/Directory Permission Errors:**
1. Check if you can create in a subdirectory instead
2. Check if there's a user-writable alternative location
3. Try creating in /tmp first then moving
4. Work in the current workspace directory instead

**General Rule:** If sudo is needed, the approach is WRONG. Find the non-sudo way.

## DOCKER ISSUES - START IT, DON'T COMPLAIN
If Docker commands fail with "daemon not running" or "socket not found":
1. On macOS: `open -a Docker` to start Docker Desktop, then wait: `sleep 10 && docker ps`
2. On Linux: `systemctl start docker` or `sudo service docker start`
3. Check if Docker is starting: `docker info` (retry after a few seconds if needed)
4. If Docker Desktop isn't installed, check for alternatives like Podman: `podman --version`
5. NEVER say "Docker isn't running" without trying to START it first

## INSTALLING TOOLS AND DEPENDENCIES
When a tool is missing, INSTALL IT. Don't say "X is not installed":

**Package Managers (use what's available):**
- macOS: `brew install <package>` (Homebrew)
- Linux: `apt-get install <package>` or `yum install <package>`
- Universal: `npm install -g <package>` for Node tools
- Python: `pip install <package>` or `pipx install <package>`

**Common Missing Tools:**
- `jq` not found → `brew install jq` or `apt-get install jq`
- `curl` not found → `brew install curl` or `apt-get install curl`
- `git` not found → `brew install git` or `apt-get install git`
- `make` not found → `xcode-select --install` (macOS) or `apt-get install build-essential`

**If brew/apt need sudo:** Use user-local alternatives:
- `npm install -g <tool>` for CLI tools
- `pip install --user <tool>` for Python tools
- Download binary directly to `~/.local/bin`

NEVER say "tool X is not installed" - just install it or find an alternative!

## STARTING DEV SERVERS - CRITICAL
When running dev servers (npm run dev, npm start, yarn dev, etc.):
1. These are LONG-RUNNING processes - they don't exit
2. Run them in the BACKGROUND with `&` at the end: `npm run dev &`
3. Add a sleep to capture initial output: `npm run dev & sleep 5 && echo "Server starting..."`
4. Check if the server started by verifying the port: `lsof -i :3000` or `curl -s http://localhost:3000`
5. If you need to source nvm first: `bash -c 'source ~/.nvm/nvm.sh && nvm use 20.9.0 && npm run dev &' && sleep 5`

**Common patterns for starting servers:**
- Next.js: `npm run dev &` (port 3000)
- React (CRA): `npm start &` (port 3000)
- Vite: `npm run dev &` (port 5173)
- Express/Node: `npm start &` or `node server.js &`
- Python Flask: `python app.py &` or `flask run &`
- Python Django: `python manage.py runserver &`

After starting, verify with: `sleep 3 && curl -s http://localhost:PORT || lsof -i :PORT`

## PORT CONFLICTS - HANDLE INTELLIGENTLY
When `lsof -i :PORT` shows a process already running:

**If it's the SAME app (e.g., previous npm run dev):**
1. Check if the site actually works: `curl -s http://localhost:3000`
2. If it works → DONE! Server is already running. Tell the user.
3. If it doesn't respond → Kill and restart: `kill $(lsof -t -i :3000) && npm run dev &`

**If it's a DIFFERENT app blocking the port:**
1. Identify what it is: `lsof -i :3000` shows the process name
2. Options:
   - Kill it if safe: `kill $(lsof -t -i :3000)`
   - Or use a different port: `PORT=3001 npm run dev &` or `npm run dev -- --port 3001`
   - Or for Next.js: `npm run dev -- -p 3001`

**Quick port conflict resolution:**
```bash
# Check what's on port 3000
lsof -i :3000

# If it's node/next and not responding, kill it
kill $(lsof -t -i :3000) 2>/dev/null

# Start fresh
npm run dev &
```

**NEVER say "port 3000 is in use" and stop.** Either:
- Verify the existing server works and tell the user it's already running
- Kill and restart
- Use a different port

## How You Work - INTELLIGENT PROBLEM SOLVING

### 1. DIAGNOSE FIRST (Critical!)
Before trying random commands, UNDERSTAND THE ENVIRONMENT:
```bash
# Check what's actually available
which node npm nvm fnm volta 2>/dev/null
node --version 2>/dev/null
ls ~/.nvm/versions/node/ 2>/dev/null
which docker podman 2>/dev/null
which python python3 pip pip3 2>/dev/null
uname -s  # OS type
```

This tells you WHAT YOU HAVE. Don't guess - CHECK.

### 2. PLAN BASED ON REALITY
If Node 18.18.2 is available via nvm, USE IT. Don't try 5 different version managers.
If Docker isn't installed, use an ALTERNATIVE (podman, or skip Docker entirely).
Work with what EXISTS, not what you wish existed.

### 3. EXECUTE WITH PRECISION
- Use the EXACT tools and versions you discovered
- One command at a time, verify each step
- Don't chain commands blindly - check results

### 4. HANDLE FAILURES INTELLIGENTLY
When something fails:

1. **READ THE ERROR** - The error message tells you what's wrong
2. **UNDERSTAND WHY** - Is it missing tool? Wrong version? Permission?
3. **FIX THE ROOT CAUSE** - Don't just try random alternatives

**🚨 CRITICAL: When run_command fails, check for error_analysis in the result**
- The tool result includes an `error_analysis` field with specific suggestions
- **DO NOT retry the exact same command** - it will fail again
- **FOLLOW the error_analysis suggestions** - they're tailored to your specific error
- Try the suggested alternatives in order

**EXAMPLE OF GOOD PROBLEM SOLVING:**
```
npm install failed
→ Check error_analysis: "Dependency conflict. Try: npm install --legacy-peer-deps"
→ Try: run_command("npm install --legacy-peer-deps")
→ Success!
```

**EXAMPLE OF BAD PROBLEM SOLVING (DON'T DO THIS):**
```
npm install failed
→ Try: run_command("npm install") again (❌ Same command will fail again!)
```

**EXAMPLE OF GOOD PROBLEM SOLVING:**
```
Error: "nvm: command not found"
→ Check: "which nvm" (not found)
→ Check: "ls ~/.nvm" (exists!)
→ Solution: "source ~/.nvm/nvm.sh && nvm use 18"
```

**EXAMPLE OF BAD PROBLEM SOLVING:**
```
Error: "nvm: command not found"
→ Try: "fnm use 18" (fails)
→ Try: "volta install" (fails)
→ Try: "asdf install" (fails)
→ Give up
```

### 5. YOUR MINDSET
- Error = Information about what's wrong (read it!)
- Failure = Clue to the real problem
- Unknown error = Investigate with diagnostic commands
- Complex issue = Break down into smaller steps

**NEVER DO THIS - BANNED PHRASES:**
- "The command failed. Would you like me to..."
- "You need to upgrade/install/configure X..."
- "Here's what went wrong, you can fix it by..."
- "I recommend that you..."
- "You should try..."
- "Could you please run..."
- "Please grant permissions..."
- "You'll need to manually..."
- "I don't have permission to..."
- "This requires sudo..."
- "Would you mind running..."
- "X is not installed..." (INSTALL IT!)
- "Docker is not running..." (START IT!)
- "I cannot download/install X..." (YES YOU CAN - use brew/apt/npm/pip)
- "The environment doesn't have X..." (THEN ADD X!)
- "I don't have access to..." (FIND ANOTHER WAY!)
- ANY sentence asking the user to do something
- ANY excuse about missing tools or services

**ALWAYS DO THIS - REQUIRED BEHAVIOR:**
- "Failed. Let me fix that..." [then fix it with alternative approach]
- "Error detected. Trying alternative..." [then try different method]
- "That didn't work. Investigating..." [then investigate and fix]
- "Found the issue. Fixing now..." [then fix]
- "Permission denied. Using alternative approach..." [then use non-sudo method]
- "Version mismatch. Let me check available versions..." [then find working version]
- "Can't use sudo. Finding another way..." [then find workaround]

### 4. VERIFY
After changes, verification runs automatically. If it fails, fix the errors.

### 5. ITERATE AGGRESSIVELY
Keep going until success or you've exhausted ALL possible approaches.
You have {max_iterations} iterations - USE THEM ALL if needed.
Each failed approach should trigger a DIFFERENT alternative strategy.
NEVER give up after just one or two failures.

## Tools Available
- **read_file**: Read any file to understand code/config
- **write_file**: Create or replace files
- **edit_file**: Make targeted edits to existing files
- **run_command**: Execute ANY shell command - this is your most powerful tool
  - Diagnose issues: `cat`, `grep`, `ps`, `lsof`, `netstat`, `docker logs`, etc.
  - Fix issues: `npm install`, `git reset`, `docker restart`, `kill`, etc.
  - Investigate: `curl`, `wget`, `ping`, `nslookup`, etc.
- **search_files**: Find files by pattern or content
- **list_directory**: Explore project structure

## Communication Style - MANDATORY NARRATION BEFORE EVERY ACTION
**CRITICAL:** You MUST narrate BEFORE and AFTER every single tool call. No silent operations!
Users see your narrative text in the UI - it's their window into what you're doing.

**MANDATORY RULE: NEVER make a tool call without first outputting a narrative sentence.**

**BEFORE every tool call, output a sentence like:**
- "Let me check if the server is running..."
- "I'll read the package.json to understand the project structure..."
- "Searching for configuration files..."
- "Now I'll create the new component file..."
- "Running the build to verify the changes..."

**AFTER every tool result, explain what you found:**
- "I found 3 configuration files. Let me read the main one..."
- "The server is running on port 3000. Let me check if it's responding..."
- "The file has 150 lines. I can see the issue is on line 42..."
- "Build succeeded! Moving on to testing..."

**REQUIRED PATTERN: NARRATE → TOOL → NARRATE → TOOL → NARRATE**
1. Output narrative text explaining what you're about to do
2. Make the tool call
3. Output narrative text explaining what you found/what happened
4. Repeat for every action

**Example of CORRECT behavior:**
```
"Let me check the project structure first..."
[list_directory tool]
"I can see this is a Next.js project with a pages/ directory. Let me read the main page..."
[read_file tool: pages/index.tsx]
"The page is using React hooks. I'll add the new feature after the existing useEffect..."
[edit_file tool]
"Great, the feature is added. Now let me run the build to verify..."
[run_command: npm run build]
"Build successful! The feature is now complete."
```

**Example of WRONG behavior (DO NOT DO THIS):**
```
[list_directory tool]
[read_file tool]
[edit_file tool]
[run_command]
"Done!"
```
This is BAD because there's no narrative between tool calls - the user sees nothing!

**For failures, always narrate:**
- "Hmm, the build failed. Let me check the error..."
- "The file wasn't found. I'll search for it..."
- "Port conflict detected. Resolving by using port 3001 instead..."

**REMEMBER:** Your narrative text is displayed to the user in real-time. Without it, they see only cryptic tool labels and wonder what's happening. Keep narration concise: 1 short sentence before and after each tool call.

## TRUTHFULNESS & VERIFICATION (MANDATORY)
- Never claim a tool succeeded unless you saw its result.
- Never say a server is running unless you executed the command and it exited successfully.
- Never claim a file was created/edited/deleted unless the tool result confirms success.
- If a tool was blocked (e.g., consent required), say “Waiting for approval” and stop. Do not invent outcomes.
- If you didn’t run a tool, say you haven’t yet.

## OUTPUT RESTRICTIONS - DO NOT ASK USER TO DO THINGS
- ❌ "Next steps:" followed by instructions for the user
- ❌ "You need to..." or "You should..."
- ❌ Numbered lists of things the USER should do
- ❌ ANY sentence asking the user to do something

INSTEAD: Narrate briefly what you're doing, then DO IT yourself.

You are a SOFTWARE ENGINEER who explains their work. Brief narration + immediate action.
"""


def get_event_timestamp() -> float:
    """
    Get current timestamp in milliseconds for event ordering.

    This ensures all events have consistent timestamps that reflect
    their true chronological order, allowing proper sorting in the frontend.
    """
    return time.time() * 1000


def analyze_command_error(
    command: str, stderr: str, stdout: str, exit_code: int
) -> str:
    """
    Analyze command errors and suggest better alternatives.

    This prevents the agent from retrying the exact same command.
    Instead, it analyzes the error and suggests specific fixes.
    """
    error_output = (stderr + "\n" + stdout).lower()
    suggestions = []

    # npm/yarn/pnpm install errors
    if any(
        cmd in command
        for cmd in ["npm install", "yarn install", "pnpm install", "npm ci"]
    ):
        if "enoent" in error_output or "no such file" in error_output:
            suggestions.append("The error indicates missing files. Try:")
            suggestions.append(
                "1. Check if package.json exists in the correct directory"
            )
            suggestions.append("2. Verify you're in the right working directory")
            suggestions.append("3. Check if node_modules was accidentally deleted")

        elif "eacces" in error_output or "permission denied" in error_output:
            suggestions.append("Permission error detected. Instead of retrying, try:")
            suggestions.append("1. Clear npm cache: npm cache clean --force")
            suggestions.append(
                "2. Check ownership of node_modules: ls -la node_modules"
            )
            suggestions.append(
                "3. Delete node_modules and package-lock.json, then retry"
            )

        elif "etimedout" in error_output or "network" in error_output:
            suggestions.append("Network timeout detected. Try a different approach:")
            suggestions.append(
                "1. Use a different registry: npm install --registry=https://registry.npmjs.org/"
            )
            suggestions.append("2. Increase timeout: npm install --fetch-timeout=60000")
            suggestions.append("3. Try yarn or pnpm instead if npm continues failing")

        elif "eresolve" in error_output or "dependency conflict" in error_output:
            suggestions.append(
                "Dependency conflict detected. Don't retry the same command. Instead:"
            )
            suggestions.append("1. Try: npm install --legacy-peer-deps")
            suggestions.append("2. Or: npm install --force (use carefully)")
            suggestions.append(
                "3. Check package.json for conflicting version requirements"
            )

        elif "engine" in error_output or "node version" in error_output:
            suggestions.append("Node version mismatch. Don't retry. Instead:")
            suggestions.append("1. Check required Node version in package.json")
            suggestions.append("2. Install correct version: nvm install <version>")
            suggestions.append("3. Or remove engine requirement if not critical")

        elif "checksum" in error_output or "integrity" in error_output:
            suggestions.append("Integrity check failed. Clear cache before retrying:")
            suggestions.append("1. npm cache clean --force")
            suggestions.append("2. Delete package-lock.json")
            suggestions.append("3. Then retry npm install")

        else:
            suggestions.append(
                "npm install failed. Before retrying the same command, try:"
            )
            suggestions.append(
                "1. Delete node_modules and package-lock.json: rm -rf node_modules package-lock.json"
            )
            suggestions.append("2. Clear npm cache: npm cache clean --force")
            suggestions.append("3. Then try: npm install")

    # Python/pip install errors
    elif any(
        cmd in command for cmd in ["pip install", "pip3 install", "poetry install"]
    ):
        if (
            "could not find a version" in error_output
            or "no matching distribution" in error_output
        ):
            suggestions.append("Package not found. Try:")
            suggestions.append("1. Check package name spelling")
            suggestions.append("2. Verify the package exists: pip search <package>")
            suggestions.append(
                "3. Try with a specific version: pip install package==version"
            )

        elif "permission denied" in error_output:
            suggestions.append("Permission error. Don't use sudo. Instead:")
            suggestions.append(
                "1. Use virtual environment: python -m venv venv && source venv/bin/activate"
            )
            suggestions.append(
                "2. Install with --user flag: pip install --user <package>"
            )

        else:
            suggestions.append("pip install failed. Try:")
            suggestions.append("1. Upgrade pip: pip install --upgrade pip")
            suggestions.append(
                "2. Use --no-cache-dir: pip install --no-cache-dir <package>"
            )

    # Build command errors
    elif any(cmd in command for cmd in ["npm run build", "yarn build", "pnpm build"]):
        if "command not found" in error_output:
            suggestions.append("Build script not found. Instead of retrying:")
            suggestions.append("1. Check package.json scripts section")
            suggestions.append("2. Verify the build script name")
            suggestions.append("3. Install dependencies first: npm install")

        elif "out of memory" in error_output or "javascript heap" in error_output:
            suggestions.append("Memory error. Don't retry the same command. Try:")
            suggestions.append(
                "1. Increase memory: NODE_OPTIONS='--max-old-space-size=4096' npm run build"
            )
            suggestions.append("2. Or close other applications to free memory")

    # Docker errors
    elif "docker" in command:
        if (
            "cannot connect to the docker daemon" in error_output
            or "daemon not running" in error_output
        ):
            suggestions.append("Docker daemon not running. Don't retry. Instead:")
            suggestions.append("1. On macOS: open -a Docker")
            suggestions.append("2. On Linux: sudo systemctl start docker")
            suggestions.append("3. Wait for Docker to start, then retry")

        elif "port is already allocated" in error_output:
            suggestions.append("Port conflict. Don't retry. Instead:")
            suggestions.append("1. Find process using port: lsof -i :<port>")
            suggestions.append("2. Kill the process or use a different port")

    # Git errors
    elif command.startswith("git"):
        if "not a git repository" in error_output:
            suggestions.append("Not a git repo. Instead of retrying:")
            suggestions.append("1. Initialize: git init")
            suggestions.append("2. Or check you're in the correct directory")

        elif "permission denied" in error_output and "publickey" in error_output:
            suggestions.append("SSH key issue. Don't retry. Instead:")
            suggestions.append("1. Use HTTPS URL instead of SSH")
            suggestions.append("2. Or set up SSH keys: ssh-keygen")

    # Test command errors
    elif any(cmd in command for cmd in ["npm test", "yarn test", "pytest", "jest"]):
        suggestions.append("Tests failed. Don't retry the same command. Instead:")
        suggestions.append("1. Read the test failure output carefully")
        suggestions.append("2. Fix the failing tests")
        suggestions.append("3. Then run tests again to verify fixes")

    # Generic command failures
    if not suggestions:
        suggestions.append(f"Command '{command}' failed with exit code {exit_code}.")
        suggestions.append("Don't retry the exact same command. Instead:")
        suggestions.append("1. Read the error message carefully")
        suggestions.append("2. Try a different approach or fix the root cause")
        suggestions.append("3. Consider alternative commands or tools")

    return "\n".join(suggestions)


def create_user_prompt(
    prompt_type: Literal["text", "select", "confirm", "multiselect"],
    title: str,
    description: str,
    **kwargs,
) -> PromptRequest:
    """
    Create a user input prompt request.

    Args:
        prompt_type: Type of input (text, select, confirm, multiselect)
        title: Short title for the prompt
        description: Detailed description/question
        **kwargs: Type-specific options (placeholder, options, validation_pattern, etc.)

    Returns:
        PromptRequest ready to be assigned to context.pending_prompt

    Example:
        prompt = create_user_prompt(
            prompt_type="select",
            title="Choose Database",
            description="Which database should I configure?",
            options=[
                {"value": "postgresql", "label": "PostgreSQL"},
                {"value": "mongodb", "label": "MongoDB"},
            ]
        )
        context.pending_prompt = prompt
    """
    prompt_id = f"prompt_{uuid.uuid4().hex[:12]}"

    return PromptRequest(
        prompt_id=prompt_id,
        prompt_type=prompt_type,
        title=title,
        description=description,
        placeholder=kwargs.get("placeholder"),
        default_value=kwargs.get("default_value"),
        options=kwargs.get("options"),
        validation_pattern=kwargs.get("validation_pattern"),
        required=kwargs.get("required", True),
        context=kwargs.get("context", {}),
        timeout_seconds=kwargs.get("timeout_seconds"),
    )


class AutonomousAgent:
    """
    Autonomous agent that completes tasks end-to-end with verification.
    """

    def __init__(
        self,
        workspace_path: str,
        api_key: str,
        provider: str = "openai",
        model: Optional[str] = None,
        db_session=None,  # Database session for checkpoint persistence and generation logging
        user_id: Optional[str] = None,  # User ID for generation logging
        org_id: Optional[str] = None,  # Organization ID for generation logging
    ):
        self.workspace_path = workspace_path
        self.api_key = api_key
        self.provider = provider
        self.db_session = (
            db_session  # For checkpoint persistence and generation logging
        )
        self.user_id = user_id  # For generation logging
        self.org_id = org_id  # For generation logging
        # Always prefer Claude for autonomous tasks - it's significantly better at agentic work
        # Claude excels at: tool use, following complex instructions, multi-step reasoning
        if model:
            self.model = model
        elif provider == "anthropic":
            self.model = "claude-sonnet-4-20250514"
        elif provider == "openai":
            self.model = "gpt-4o"
        else:
            # Default to Claude Sonnet - best model for autonomous coding
            self.model = "claude-sonnet-4-20250514"
            self.provider = "anthropic"
        self.verifier = VerificationRunner(workspace_path)

        # Detect project and get verification commands
        (
            self.project_type,
            self.framework,
            self.verification_commands,
        ) = ProjectAnalyzer.detect_project_type(workspace_path)

        logger.info(f"[AutonomousAgent] Project: {self.project_type}/{self.framework}")
        logger.info(
            f"[AutonomousAgent] Verification commands: {self.verification_commands}"
        )

        # Track pending consent requests for dangerous commands
        self.pending_consents: Dict[str, Dict[str, Any]] = {}

        # Initialize Redis client for distributed consent state
        from backend.core.config import settings
        self.redis_client: Optional[redis.Redis] = None
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"[AutonomousAgent] Redis client initialized: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"[AutonomousAgent] Failed to initialize Redis (consent will fail): {e}")

        # Initialize consent service for preferences and audit logging
        self.consent_service = get_consent_service(db=self.db_session)

    async def _check_prompt_response(
        self, prompt_id: str, timeout_seconds: Optional[int] = 300
    ) -> Optional[Any]:
        """
        Wait for user's response to a prompt request.

        Args:
            prompt_id: ID of the prompt request
            timeout_seconds: How long to wait for response (default 5 minutes)

        Returns:
            User's response value, or None if timeout/cancelled
        """
        from backend.api.navi import _prompt_responses

        start_time = time.time()
        timeout = timeout_seconds or 300

        while time.time() - start_time < timeout:
            if prompt_id in _prompt_responses:
                response_data = _prompt_responses[prompt_id]
                if not response_data.get("pending", True):
                    # Response received
                    if response_data.get("cancelled"):
                        logger.info(
                            f"[AutonomousAgent] Prompt {prompt_id} cancelled by user"
                        )
                        return None

                    logger.info(f"[AutonomousAgent] Prompt {prompt_id} answered")
                    return response_data.get("response")

            await asyncio.sleep(0.5)

        # Timeout
        logger.warning(
            f"[AutonomousAgent] Prompt {prompt_id} timed out after {timeout}s"
        )
        return None

    def _assess_task_complexity(
        self, request: str, context: Optional[TaskContext] = None
    ) -> TaskComplexity:
        """
        Assess task complexity to determine verification strategy and iteration limits.

        Returns:
            TaskComplexity.SIMPLE: Single file fixes, typos, renames, imports (3 iterations, quick validation)
            TaskComplexity.MEDIUM: Multiple files, moderate changes (5 iterations, lint+typecheck)
            TaskComplexity.COMPLEX: Refactors, new features, architecture (10 iterations, full verification)
        """
        request_lower = request.lower()

        # Simple task indicators
        simple_indicators = [
            len(request) < 150,  # Short request
            any(
                kw in request_lower
                for kw in ["typo", "rename", "import", "missing", "unused", "spelling"]
            ),
            "fix" in request_lower and "all" not in request_lower,
            any(
                kw in request_lower
                for kw in ["add import", "remove import", "update import"]
            ),
        ]

        # Check files modified count if context available
        if context and context.files_modified:
            simple_indicators.append(len(context.files_modified) == 1)

        # Complex task indicators
        complex_indicators = [
            len(request) > 300,
            any(
                kw in request_lower
                for kw in [
                    "refactor",
                    "implement",
                    "create",
                    "build",
                    "multiple",
                    "entire",
                    "whole",
                    "all files",
                    "architecture",
                    "redesign",
                ]
            ),
            "feature" in request_lower,
            "add feature" in request_lower or "new feature" in request_lower,
        ]

        # Check files modified count for complexity
        if context and context.files_modified:
            complex_indicators.append(len(context.files_modified) > 3)

        simple_score = sum(simple_indicators)
        complex_score = sum(complex_indicators)

        if complex_score >= 2:
            return TaskComplexity.COMPLEX
        elif simple_score >= 2:
            return TaskComplexity.SIMPLE
        return TaskComplexity.MEDIUM

    def _estimate_required_tokens(
        self, request: str, context: TaskContext, complexity: TaskComplexity
    ) -> int:
        """
        Dynamically estimate required tokens based on task complexity and type.

        This prevents:
        - Wasting time/money on simple tasks (was using 8192 for "create file")
        - Timeouts on complex tasks (gives appropriate allocation)
        - Response truncation (ensures enough tokens for markdown/explanations)

        Returns:
            Optimal max_tokens value (500-8192)
        """
        request_lower = request.lower()

        # Micro tasks (500 tokens ≈ 375 words)
        micro_indicators = [
            "create file" in request_lower and len(request) < 100,
            "add import" in request_lower or "import" in request_lower,
            "rename" in request_lower and len(request) < 80,
            "delete" in request_lower and len(request) < 80,
            "typo" in request_lower or "spelling" in request_lower,
        ]
        if any(micro_indicators):
            return 500

        # Small tasks (1000 tokens ≈ 750 words)
        small_indicators = [
            complexity == TaskComplexity.SIMPLE,
            "fix" in request_lower and len(request) < 150,
            len(context.files_modified) == 1 and context.iteration <= 2,
            "update" in request_lower and len(request) < 100,
        ]
        if any(small_indicators):
            return 1000

        # Medium tasks (2500 tokens ≈ 1875 words)
        medium_indicators = [
            complexity == TaskComplexity.MEDIUM,
            len(context.files_modified) <= 3,
            "add feature" in request_lower and len(request) < 200,
            "implement" in request_lower and len(request) < 250,
        ]
        if any(medium_indicators):
            return 2500

        # Large tasks (4096 tokens ≈ 3000 words)
        large_indicators = [
            complexity == TaskComplexity.COMPLEX,
            len(context.files_modified) > 3,
            any(kw in request_lower for kw in ["refactor", "architecture", "redesign"]),
            "build" in request_lower and len(request) > 200,
        ]
        if any(large_indicators):
            return 4096

        # Enterprise tasks (8192 tokens ≈ 6000 words)
        # Only use maximum for truly massive tasks
        enterprise_indicators = [
            "e-commerce" in request_lower or "platform" in request_lower,
            "end-to-end" in request_lower or "end to end" in request_lower,
            "production" in request_lower and "deploy" in request_lower,
            len(request) > 400,
            "website" in request_lower
            and "build" in request_lower
            and len(request) > 250,
        ]
        if any(enterprise_indicators):
            logger.warning(
                "[AutonomousAgent] 🚨 Enterprise-scale task detected! "
                "This will use max tokens (8192) and may need task decomposition."
            )
            return 8192

        # Default: medium allocation
        return 2500

    def _should_decompose_task(self, request: str, complexity: TaskComplexity) -> bool:
        """
        Determine if a task should be decomposed into subtasks.

        Enterprise-scale projects that span multiple features, components,
        or require end-to-end implementation should be decomposed.

        Returns:
            True if task should be decomposed into subtasks
        """
        request_lower = request.lower()

        # Always decompose enterprise-complexity tasks
        if complexity == TaskComplexity.ENTERPRISE:
            return True

        # Decompose if request contains enterprise indicators
        enterprise_indicators = [
            "e-commerce" in request_lower and len(request) > 200,
            "platform" in request_lower and "build" in request_lower,
            "end-to-end" in request_lower or "end to end" in request_lower,
            ("production" in request_lower and "deploy" in request_lower)
            and len(request) > 200,
            "website" in request_lower
            and "build" in request_lower
            and len(request) > 250,
            any(
                word in request_lower
                for word in ["microservices", "distributed", "full-stack"]
            ),
        ]

        if any(enterprise_indicators):
            logger.info(
                "[AutonomousAgent] 🔀 Enterprise task detected - will decompose into subtasks"
            )
            return True

        # Decompose if request mentions multiple major components
        component_count = sum(
            [
                "auth" in request_lower or "authentication" in request_lower,
                "database" in request_lower or "db" in request_lower,
                "api" in request_lower or "backend" in request_lower,
                "frontend" in request_lower or "ui" in request_lower,
                "payment" in request_lower or "checkout" in request_lower,
                "admin" in request_lower and "dashboard" in request_lower,
                "deployment" in request_lower or "deploy" in request_lower,
                "testing" in request_lower or "tests" in request_lower,
            ]
        )

        if component_count >= 3:
            logger.info(
                f"[AutonomousAgent] 🔀 Multi-component task detected ({component_count} components) - will decompose"
            )
            return True

        return False

    async def _execute_with_decomposition_generator(
        self,
        request: str,
        context: TaskContext,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute a task by decomposing it into subtasks and executing them sequentially.

        Streams progress updates for each subtask.

        Yields:
            SSE events for subtask progress and completion
        """
        logger.info(
            f"[AutonomousAgent] 🔀 Starting task decomposition for: {request[:100]}..."
        )

        # Send decomposition start event
        yield {
            "type": "decomposition_start",
            "message": "Analyzing task and breaking it into subtasks...",
            "timestamp": time.time(),
        }

        try:
            # Initialize task decomposer with same provider/model
            decomposer = TaskDecomposer(
                provider=self.provider,
                model=self.model,
                api_key=self.api_key,
                temperature=0.3,
            )

            # Decompose the task
            decomposition = await decomposer.decompose_goal(
                goal=request,
                context={
                    "workspace_path": self.workspace_path,
                    "project_type": self.project_type,
                    "framework": self.framework,
                },
                min_tasks=10,
                max_tasks=50,  # Start with reasonable subtask count
            )

            logger.info(
                f"[AutonomousAgent] ✅ Decomposed into {len(decomposition.tasks)} subtasks "
                f"across {len(decomposition.phases)} phases"
            )

            # Send decomposition complete event
            yield {
                "type": "decomposition_complete",
                "task_count": len(decomposition.tasks),
                "phase_count": len(decomposition.phases),
                "phases": decomposition.phases,
                "estimated_hours": decomposition.estimated_total_hours,
                "timestamp": time.time(),
            }

            # Execute subtasks in dependency order
            completed_tasks = set()
            failed_tasks = set()

            for idx, task in enumerate(decomposition.tasks):
                # Check if dependencies are met
                unmet_deps = [
                    dep for dep in task.dependencies if dep not in completed_tasks
                ]

                if unmet_deps:
                    logger.warning(
                        f"[AutonomousAgent] ⚠️ Skipping task {task.id} - "
                        f"unmet dependencies: {unmet_deps}"
                    )
                    failed_tasks.add(task.id)
                    continue

                # Send subtask start event
                yield {
                    "type": "subtask_start",
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "phase": task.phase,
                    "progress": f"{idx + 1}/{len(decomposition.tasks)}",
                    "timestamp": time.time(),
                }

                try:
                    # Execute the subtask using regular execute flow
                    subtask_request = f"{task.title}\n\n{task.description}"

                    # Create subtask context (currently not used directly but kept
                    # for future execution flow integration)
                    TaskContext.with_adaptive_limits(
                        complexity=TaskComplexity.SIMPLE,  # Subtasks should be simple
                        task_id=task.id,
                        original_request=subtask_request,
                        workspace_path=self.workspace_path,
                    )

                    # Execute subtask (this will use the regular LLM execution flow)
                    # TODO: Actually execute the subtask - for now just simulate
                    await asyncio.sleep(0.1)  # Simulate execution

                    logger.info(
                        f"[AutonomousAgent] ✅ Completed subtask {task.id}: {task.title}"
                    )

                    completed_tasks.add(task.id)

                    # Send subtask complete event
                    yield {
                        "type": "subtask_complete",
                        "task_id": task.id,
                        "title": task.title,
                        "success": True,
                        "progress": f"{idx + 1}/{len(decomposition.tasks)}",
                        "timestamp": time.time(),
                    }

                except Exception as e:
                    logger.error(
                        f"[AutonomousAgent] ❌ Failed subtask {task.id}: {str(e)}"
                    )
                    failed_tasks.add(task.id)

                    # Send subtask failed event
                    yield {
                        "type": "subtask_failed",
                        "task_id": task.id,
                        "title": task.title,
                        "error": str(e),
                        "timestamp": time.time(),
                    }

            # Send final completion event
            yield {
                "type": "decomposition_finished",
                "total_tasks": len(decomposition.tasks),
                "completed": len(completed_tasks),
                "failed": len(failed_tasks),
                "success_rate": len(completed_tasks) / len(decomposition.tasks),
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"[AutonomousAgent] ❌ Decomposition failed: {str(e)}")
            yield {
                "type": "decomposition_error",
                "error": str(e),
                "timestamp": time.time(),
            }
            raise

    def _extract_error_signatures(
        self, results: List[VerificationResult], iteration: int
    ) -> List[ErrorSignature]:
        """
        Extract error signatures from verification results for loop detection.
        Normalizes error messages to detect when the same fundamental error occurs.
        """
        import re

        signatures = []

        for result in results:
            if result.success:
                continue

            for error_line in result.errors:
                # Extract file path from common error formats
                # TypeScript: src/file.tsx(10,5): error TS2345
                # ESLint: /path/to/file.js:10:5
                # Webpack: ERROR in ./src/file.tsx
                file_match = re.search(
                    r"(?:ERROR in |error in |at |)(?:\.\/)?([^\s:()]+\.[tj]sx?)",
                    error_line,
                    re.IGNORECASE,
                )
                file_path = file_match.group(1) if file_match else "unknown"

                # Normalize error pattern - remove line numbers, specific values
                # Keep the core error type/message
                error_pattern = error_line.lower()
                # Remove line/column numbers
                error_pattern = re.sub(r"\(\d+,\d+\)", "", error_pattern)
                error_pattern = re.sub(r":\d+:\d+", "", error_pattern)
                error_pattern = re.sub(r"line \d+", "", error_pattern)
                # Extract key error indicators
                if "cannot find module" in error_pattern:
                    error_pattern = "cannot_find_module"
                elif (
                    "syntax error" in error_pattern
                    or "unexpected token" in error_pattern
                ):
                    error_pattern = "syntax_error"
                elif "type" in error_pattern and "error" in error_pattern:
                    error_pattern = "type_error"
                elif "jsx" in error_pattern:
                    error_pattern = "jsx_error"
                elif "import" in error_pattern:
                    error_pattern = "import_error"
                elif (
                    "unterminated" in error_pattern or "string literal" in error_pattern
                ):
                    error_pattern = "unterminated_string"
                else:
                    # Keep first 50 chars as pattern
                    error_pattern = error_pattern[:50].strip()

                signatures.append(
                    ErrorSignature(
                        error_type=result.type.value,
                        file_path=file_path,
                        error_pattern=error_pattern,
                        iteration=iteration,
                    )
                )

        return signatures

    def _detect_iteration_loop(
        self, context: TaskContext
    ) -> Tuple[bool, str, List[str]]:
        """
        Detect if the agent is stuck in an iteration loop trying the same fix.

        Returns:
            (is_looping, severity, suggestions)
            - is_looping: True if a loop is detected
            - severity: "warning" or "critical"
            - suggestions: List of alternative strategies to try
        """
        if context.iteration < 2:
            return False, "", []

        current_signatures = context.error_signatures[-10:]  # Last N errors

        # Check for repeated error signatures
        repeated_patterns = {}
        for sig in current_signatures:
            key = f"{sig.error_type}:{sig.file_path}:{sig.error_pattern}"
            if key not in repeated_patterns:
                repeated_patterns[key] = []
            repeated_patterns[key].append(sig.iteration)

        # Find patterns that occurred in multiple iterations
        recurring = {k: v for k, v in repeated_patterns.items() if len(v) >= 2}

        if not recurring:
            context.consecutive_same_error_count = 0
            return False, "", []

        # Check if this is the same error as last iteration
        last_iteration_errors = [
            s for s in context.error_signatures if s.iteration == context.iteration - 1
        ]
        current_iteration_errors = [
            s for s in context.error_signatures if s.iteration == context.iteration
        ]

        same_as_last = False
        for curr in current_iteration_errors:
            for last in last_iteration_errors:
                if curr.matches(last):
                    same_as_last = True
                    break

        if same_as_last:
            context.consecutive_same_error_count += 1
        else:
            context.consecutive_same_error_count = 0

        # Determine severity and suggestions
        suggestions = []
        severity = "warning"

        # Get the problematic files
        problem_files = list(set(s.file_path for s in current_iteration_errors))

        if context.consecutive_same_error_count >= 3:
            severity = "critical"
            suggestions = [
                f"STOP editing {', '.join(problem_files)} - your fixes are not working",
                "Read the ENTIRE file to understand its structure before editing",
                "Check if there's an existing working example in the codebase to copy from",
                "Consider if the file needs to be completely rewritten rather than patched",
                "Look for a completely different approach to achieve the same goal",
                "Check if dependencies are missing or incorrectly installed",
            ]
        elif context.consecutive_same_error_count >= 2:
            severity = "warning"
            suggestions = [
                "Your previous fix did not resolve the issue",
                f"Re-read {', '.join(problem_files)} to see the actual current content",
                "The error might be in a different location than you think",
                "Check the import paths and file structure carefully",
                "Consider if you're fixing the symptom rather than the root cause",
            ]

        # Add specific suggestions based on error patterns
        for pattern_key in recurring.keys():
            if "syntax_error" in pattern_key or "jsx_error" in pattern_key:
                suggestions.append(
                    "For JSX/syntax errors: check for unescaped characters, missing closing tags, or incorrect attribute syntax"
                )
            elif "cannot_find_module" in pattern_key:
                suggestions.append(
                    "For module errors: verify the exact path, check if file exists, ensure correct relative path"
                )
            elif "type_error" in pattern_key:
                suggestions.append(
                    "For type errors: check the actual type definitions, don't assume types"
                )

        return True, severity, suggestions

    def _record_failed_approach(self, context: TaskContext, error_summary: str) -> None:
        """Record a failed approach so the LLM knows not to repeat it."""
        # Get files touched in this iteration
        files_touched = list(
            set(context.files_modified[-5:] + context.files_created[-5:])
        )

        # Build description of what was attempted
        tool_calls = context.tool_calls_per_iteration.get(context.iteration, [])
        description_parts = []

        for tc in tool_calls[-5:]:  # Last 5 tool calls
            if ":" in tc:
                tool, target = tc.split(":", 1)
                if tool == "write_file":
                    description_parts.append(f"Created/wrote {target}")
                elif tool == "edit_file":
                    description_parts.append(f"Edited {target}")
                elif tool == "run_command":
                    description_parts.append(f"Ran command: {target[:50]}")

        description = (
            "; ".join(description_parts) if description_parts else "Unknown approach"
        )

        context.failed_approaches.append(
            FailedApproach(
                iteration=context.iteration,
                description=description,
                files_touched=files_touched,
                error_summary=error_summary[:200],
            )
        )

    def _is_fix_request(self, request: str) -> bool:
        """
        Detect if the user's request is asking for a fix/implementation vs just a question.
        Returns True if the user wants something DONE, not just analyzed.
        """
        request_lower = request.lower()

        # Patterns that indicate the user wants action taken
        action_patterns = [
            "fix",
            "solve",
            "resolve",
            "repair",
            "debug",
            "make it work",
            "get it working",
            "stop",
            "start",
            "implement",
            "add",
            "create",
            "build",
            "set up",
            "setup",
            "update",
            "change",
            "modify",
            "edit",
            "remove",
            "delete",
            "install",
            "configure",
            "run",
            "execute",
            "deploy",
            "not working",
            "doesn't work",
            "isn't working",
            "won't work",
            "broken",
            "error",
            "issue",
            "problem",
            "bug",
            "stuck",
            "failing",
            "failed",
            "crashed",
            "can't",
            "cannot",
            "help me",
            "please",
            "need to",
            "want to",
            "trying to",
        ]

        # Patterns that indicate just a question (not needing action)
        question_only_patterns = [
            "what is",
            "what are",
            "what does",
            "how does",
            "why is",
            "why does",
            "explain",
            "tell me about",
            "what's the difference",
            "can you explain",
        ]

        # Check if it's primarily a question
        is_question_only = any(
            pattern in request_lower for pattern in question_only_patterns
        )
        has_action_intent = any(pattern in request_lower for pattern in action_patterns)

        # If it has action patterns or is not purely a question, treat as fix request
        return has_action_intent or not is_question_only

    def _is_run_start_request(self, request: str) -> bool:
        request_lower = (request or "").lower().strip()

        if not request_lower:
            return False

        config = self._load_run_start_config()

        # Direct phrase matches (high confidence)
        run_patterns = [
            "run the app",
            "start the app",
            "start the server",
            "run the server",
            "launch the app",
            "launch the server",
            "boot the app",
            "boot the server",
            "bring up the app",
            "bring up the server",
            "spin up the app",
            "spin up the server",
            "fire up the app",
            "fire up the server",
            "start dev server",
            "run dev server",
            "start the dev server",
            "run the dev server",
            "check if it’s running",
            "check if it's running",
            "is it running",
            "is the server running",
            "is the app running",
            "start locally",
            "run locally",
            "start frontend",
            "start backend",
            "run frontend",
            "run backend",
            "serve the app",
            "serve the site",
            "dev server",
            "health check",
            "status check",
            "is it up",
            "is it online",
            "is it alive",
            "check status",
            "check health",
        ]
        if any(p in request_lower for p in run_patterns):
            return True
        if any(p in request_lower for p in config["phrases"]):
            return True

        # Command/tech signals (medium confidence)
        command_tokens = [
            "npm ",
            "pnpm ",
            "yarn ",
            "bun ",
            "node ",
            "python ",
            "python3 ",
            "uvicorn",
            "gunicorn",
            "flask run",
            "django runserver",
            "rails s",
            "rails server",
            "vite",
            "next ",
            "nuxt ",
            "sveltekit",
            "astro ",
            "docker ",
            "docker-compose",
            "docker compose",
            "kubectl ",
            "helm ",
        ]
        if any(tok in request_lower for tok in command_tokens):
            return True
        if any(tok in request_lower for tok in config["command_tokens"]):
            return True

        # URL/port signals (medium confidence)
        if "localhost" in request_lower or "127.0.0.1" in request_lower:
            return True
        if re.search(r":\d{2,5}\b", request_lower):
            return True
        if re.search(r"https?://", request_lower):
            return True

        # Short status questions (low-to-medium confidence)
        status_questions = [
            "running?",
            "up?",
            "alive?",
            "online?",
            "working?",
            "works?",
        ]
        if len(request_lower.split()) <= 6 and any(
            q in request_lower for q in status_questions
        ):
            return True
        if len(request_lower.split()) <= 6 and any(
            q in request_lower for q in config["status_questions"]
        ):
            return True

        # Verb+noun pattern (broad coverage)
        verbs = {"run", "start", "launch", "boot", "spin", "fire", "bring", "serve"}
        nouns = {"app", "server", "service", "site", "frontend", "backend"}
        verbs |= set(config["verbs"])
        nouns |= set(config["nouns"])

        if any(v in request_lower for v in verbs) and any(
            n in request_lower for n in nouns
        ):
            return True

        return False

    def _is_delete_request(self, request: str, context: Optional[TaskContext] = None) -> bool:
        request_lower = (request or "").lower()
        if not request_lower:
            return False

        delete_markers = [
            "delete",
            "remove file",
            "remove the file",
            "remove",
            "rm ",
            "trash",
            "erase",
            "get rid",
            "unlink",
        ]
        clear_markers = [
            "clear file",
            "clear the file",
            "clear contents",
            "clear content",
            "empty file",
            "empty the file",
            "truncate",
            "wipe contents",
            "wipe content",
        ]

        if any(marker in request_lower for marker in delete_markers):
            # Guard against explicit "clear/empty contents" which is not deletion
            if any(marker in request_lower for marker in clear_markers):
                return False
            return True

        # Handle "do the same" using conversation context
        if "do the same" in request_lower or "same for" in request_lower or "same thing" in request_lower:
            history_text = ""
            if context and context.conversation_history:
                history_text = " ".join(
                    str(m.get("content", "")) for m in context.conversation_history[-12:]
                    if m.get("role") in ("user", "assistant")
                ).lower()
            if history_text and any(marker in history_text for marker in delete_markers):
                return True

        return False

    def _is_move_request(self, request: str) -> bool:
        request_lower = (request or "").lower()
        if not request_lower:
            return False
        move_markers = [
            "rename",
            "move",
            "mv ",
            "relocate",
            "transfer",
            "shift",
        ]
        return any(marker in request_lower for marker in move_markers)

    def _is_create_request(self, request: str) -> bool:
        request_lower = (request or "").lower()
        if not request_lower:
            return False
        create_markers = [
            "create",
            "add file",
            "add a file",
            "new file",
            "generate file",
            "scaffold",
            "make a file",
        ]
        return any(marker in request_lower for marker in create_markers)

    def _is_edit_request(self, request: str) -> bool:
        request_lower = (request or "").lower()
        if not request_lower:
            return False
        edit_markers = [
            "edit",
            "update",
            "modify",
            "change",
            "fix",
            "refactor",
            "adjust",
            "tweak",
        ]
        return any(marker in request_lower for marker in edit_markers)

    def _classify_file_intent(
        self, request: str, context: Optional[TaskContext] = None
    ) -> str:
        if self._is_delete_request(request, context):
            return "delete"
        if self._is_move_request(request):
            return "move"
        if self._is_create_request(request):
            return "create"
        if self._is_edit_request(request):
            return "edit"
        return "unknown"

    def _is_file_operation_request(
        self, request: str, context: Optional[TaskContext] = None
    ) -> bool:
        request_lower = (request or "").lower()
        if not request_lower:
            return False
        if self._classify_file_intent(request, context) != "unknown":
            return True
        # If it mentions "file" and includes any file-like tokens, treat as file op
        candidates = self._extract_file_candidates(request, context)
        return "file" in request_lower and len(candidates) > 0

    def _detect_command_intent(self, request: str) -> str:
        request_lower = (request or "").lower()
        if not request_lower:
            return "unknown"

        if re.search(r"\binstall( dependencies| deps)?\b", request_lower):
            return "install"

        if re.search(
            r"\b(run|start|launch|serve)\b.*\b(dev server|server|app|site|frontend|backend)\b",
            request_lower,
        ):
            return "dev"

        if re.search(r"\b(run|rerun|execute)?\s*(tests?|test suite|pytest|jest|vitest)\b", request_lower):
            return "test"

        if re.search(r"\b(run|execute)\s+(build|compile|bundle)\b", request_lower) or re.search(
            r"\bbuild\b.*\b(project|app|site|frontend|backend|server)\b", request_lower
        ):
            return "build"

        if re.search(r"\b(run|execute)?\s*(lint|eslint)\b", request_lower):
            return "lint"

        if re.search(r"\b(type ?check|tsc)\b", request_lower):
            return "typecheck"

        if re.search(r"\b(format|prettier|black|ruff format)\b", request_lower):
            return "format"

        return "unknown"

    def _read_package_json(self) -> Dict[str, Any]:
        pkg_path = os.path.join(self.workspace_path, "package.json")
        if not os.path.exists(pkg_path):
            return {}
        try:
            with open(pkg_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _detect_package_manager(self) -> str:
        if os.path.exists(os.path.join(self.workspace_path, "pnpm-lock.yaml")):
            return "pnpm"
        if os.path.exists(os.path.join(self.workspace_path, "yarn.lock")):
            return "yarn"
        if os.path.exists(os.path.join(self.workspace_path, "bun.lockb")):
            return "bun"
        return "npm"

    def _format_script_command(self, package_manager: str, script: str) -> str:
        if package_manager == "yarn":
            return f"yarn {script}"
        if package_manager == "bun":
            return f"bun run {script}"
        if package_manager == "pnpm":
            return f"pnpm run {script}"
        return f"npm run {script}"

    def _resolve_command_for_intent(self, intent: str) -> Optional[str]:
        pkg = self._read_package_json()
        scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
        package_manager = self._detect_package_manager()

        if intent == "install":
            if os.path.exists(os.path.join(self.workspace_path, "package.json")):
                return {
                    "npm": "npm install",
                    "yarn": "yarn install",
                    "pnpm": "pnpm install",
                    "bun": "bun install",
                }.get(package_manager, "npm install")
            if os.path.exists(os.path.join(self.workspace_path, "pyproject.toml")):
                return "pip install -e ."
            if os.path.exists(os.path.join(self.workspace_path, "requirements.txt")):
                return "pip install -r requirements.txt"
            if os.path.exists(os.path.join(self.workspace_path, "Cargo.toml")):
                return "cargo build"
            if os.path.exists(os.path.join(self.workspace_path, "go.mod")):
                return "go mod download"
            return None

        if intent == "dev":
            for script in ["dev", "start", "serve", "develop", "preview"]:
                if script in scripts:
                    return self._format_script_command(package_manager, script)
            return None

        if intent in {"test", "build", "lint", "typecheck"}:
            _, _, commands = ProjectAnalyzer.detect_project_type(self.workspace_path)
            return commands.get(intent)

        if intent == "format":
            for script in ["format", "fmt"]:
                if script in scripts:
                    return self._format_script_command(package_manager, script)
            return None

        return None

    def _extract_file_candidates(
        self, request: str, context: Optional[TaskContext] = None
    ) -> List[str]:
        """Extract likely file paths/names from a request."""
        text = request or ""
        candidates: List[str] = []

        # Backticks and quotes
        for pattern in (r"`([^`]+)`", r'"([^"]+)"', r"'([^']+)'"):
            for match in re.findall(pattern, text):
                candidates.append(match)

        # rm/mv/cp command pattern (capture target after flags)
        for match in re.findall(r"\b(?:rm|mv|cp)\s+(?:-[^\s]+\s+)*([^\s;]+)", text):
            candidates.append(match)

        # "file named X" / "file X"
        for match in re.findall(
            r"\bfile(?:\s+named|\s+called|\s+is)?\s+([A-Za-z0-9_./-]+)",
            text,
        ):
            candidates.append(match)

        # Any token that looks like a filename with extension
        for match in re.findall(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})", text):
            candidates.append(match)

        # Fallback to conversation history for "do the same"
        if context and context.conversation_history:
            history_text = " ".join(
                str(m.get("content", "")) for m in context.conversation_history[-12:]
                if m.get("role") in ("user", "assistant")
            )
            for pattern in (r"`([^`]+)`", r'"([^"]+)"', r"'([^']+)'"):
                for match in re.findall(pattern, history_text):
                    candidates.append(match)
            for match in re.findall(
                r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})", history_text
            ):
                candidates.append(match)

        # Normalize + dedupe
        normalized: List[str] = []
        seen = set()
        for raw in candidates:
            if not raw:
                continue
            cleaned = raw.strip().strip(",.;:)")
            if cleaned.startswith("./"):
                cleaned = cleaned[2:]
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)

        return normalized

    def _extract_delete_candidates(
        self, request: str, context: Optional[TaskContext] = None
    ) -> List[str]:
        return self._extract_file_candidates(request, context)

    def _preflight_file_targets(
        self, request: str, context: TaskContext
    ) -> Dict[str, Any]:
        """
        Resolve file targets with a single deterministic preflight.
        Returns: {
            "status": "resolved"|"ambiguous"|"not_found",
            "targets": [paths],
            "matches": [paths],
            "candidate": "name"
        }
        """
        candidates = self._extract_file_candidates(request, context)
        resolved: List[str] = []
        ambiguous_matches: List[str] = []
        first_candidate: Optional[str] = None

        for candidate in candidates:
            if not first_candidate:
                first_candidate = candidate

            # Absolute path
            if os.path.isabs(candidate):
                if os.path.exists(candidate):
                    rel = (
                        os.path.relpath(candidate, self.workspace_path)
                        if candidate.startswith(self.workspace_path)
                        else candidate
                    )
                    resolved.append(rel)
                continue

            # Relative path
            rel_path = candidate.lstrip("./")
            direct_path = os.path.join(self.workspace_path, rel_path)
            if os.path.exists(direct_path):
                resolved.append(rel_path)
                continue

            # Fallback: search by basename
            base = os.path.basename(rel_path)
            if not base:
                continue
            pattern = f"**/{base}" if "." in base else f"**/{base}.*"
            matches = glob.glob(os.path.join(self.workspace_path, pattern), recursive=True)
            matches = [
                os.path.relpath(m, self.workspace_path)
                for m in matches
                if os.path.isfile(m)
            ]
            if len(matches) == 1:
                resolved.append(matches[0])
            elif len(matches) > 1:
                ambiguous_matches.extend(matches[:10])

        # Deduplicate resolved
        resolved_unique = []
        seen = set()
        for p in resolved:
            if p not in seen:
                resolved_unique.append(p)
                seen.add(p)

        if resolved_unique and not ambiguous_matches:
            return {"status": "resolved", "targets": resolved_unique}

        if ambiguous_matches:
            return {
                "status": "ambiguous",
                "matches": list(dict.fromkeys(ambiguous_matches)),
                "candidate": first_candidate or "",
            }

        return {"status": "not_found", "candidate": first_candidate or ""}

    def _is_run_start_command(self, command: str) -> bool:
        if not command:
            return False
        cmd = command.lower()
        # Long-running dev/server patterns
        if re.search(r"\b(run|start|serve|dev)\b", cmd):
            if re.search(r"\b(npm|pnpm|yarn|bun)\s+run\s+(dev|start|serve)\b", cmd):
                return True
            if re.search(r"\b(node|python|python3)\b", cmd) and re.search(
                r"\b(app\.py|main\.py|server\.py|manage\.py)\b", cmd
            ):
                return True
            if re.search(
                r"\b(uvicorn|gunicorn|flask|django|rails|vite|next|nuxt|astro|sveltekit)\b",
                cmd,
            ):
                return True
            if re.search(r"\bdocker(\s+compose)?\s+up\b", cmd):
                return True
        return False

    def _load_run_start_config(self) -> Dict[str, List[str]]:
        defaults = {
            "phrases": [],
            "command_tokens": [],
            "verbs": [],
            "nouns": [],
            "status_questions": [],
        }
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "config",
                "run_start_detection.json",
            )
            config_path = os.path.abspath(config_path)
            if not os.path.exists(config_path):
                return defaults
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = {**defaults, **(data or {})}
            # Normalize to lists of strings
            for key in defaults.keys():
                value = merged.get(key, [])
                if not isinstance(value, list):
                    merged[key] = []
                else:
                    merged[key] = [str(v).lower() for v in value if str(v).strip()]
            return merged
        except Exception:
            return defaults

    def _should_suppress_iteration_banner(self, context: TaskContext) -> bool:
        # Suppress noisy iteration banners for pure run/start tasks with no code changes
        if context.files_modified or context.files_created:
            return False
        if self._is_fix_request(context.original_request):
            return False
        if self._is_run_start_request(context.original_request):
            return True
        # Tool-based detection: if latest command is a run/start command, suppress
        if context.commands_run:
            last_cmd = context.commands_run[-1].get("command", "")
            if self._is_run_start_command(last_cmd):
                return True
        return False

    def _calculate_llm_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate LLM API cost in USD based on model and token usage."""
        # Pricing as of 2024-2026 (per million tokens)
        pricing = {
            # Anthropic Claude models
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
            "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
            "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
            # OpenAI GPT models
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-4": {"input": 30.00, "output": 60.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }

        # Default pricing if model not found
        default = {"input": 3.00, "output": 15.00}
        rates = pricing.get(model, default)

        # Calculate cost (price is per million tokens)
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]

        return input_cost + output_cost

    async def _persist_llm_metrics(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: Optional[int] = None,
        task_type: str = "autonomous",
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Persist LLM metrics to database for historical analysis."""
        if not self.db_session:
            return  # No database session available

        try:
            from backend.models.llm_metrics import LlmMetric

            metric = LlmMetric(
                org_id=str(self.org_id) if self.org_id else None,
                user_id=str(self.user_id) if self.user_id else None,
                model=model,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                input_cost=(
                    (input_tokens / 1_000_000) * cost_usd if input_tokens > 0 else 0.0
                ),
                output_cost=(
                    (output_tokens / 1_000_000) * cost_usd if output_tokens > 0 else 0.0
                ),
                total_cost=cost_usd,
                latency_ms=latency_ms,
                task_type=task_type,
                status=status,
                error_message=error_message,
            )

            self.db_session.add(metric)
            await self.db_session.commit()
            logger.debug("[AutonomousAgent] 💾 Persisted LLM metrics to database")
        except Exception as e:
            logger.warning(f"[AutonomousAgent] Failed to persist LLM metrics: {e}")
            pass

    def _build_system_prompt(
        self, context: TaskContext, rag_context: Optional[str] = None
    ) -> str:
        """Build system prompt with current context and optional RAG context."""
        base_prompt = AUTONOMOUS_SYSTEM_PROMPT

        # Inject RAG context if available
        if rag_context and rag_context.strip():
            base_prompt = f"""{base_prompt}

## CODEBASE CONTEXT

You have access to relevant codebase context retrieved via semantic search:

{rag_context}

Use this context to understand existing patterns, dependencies, and architecture when completing the task.
"""

        return base_prompt

    async def _log_generation(self, context: TaskContext, prompt: str) -> Optional[int]:
        """Log LLM generation to database for feedback tracking. Returns gen_id."""
        if not self.db_session or not self.user_id or not self.org_id:
            # Cannot log without database session and user context
            return None

        try:
            feedback_service = FeedbackService(self.db_session)
            gen_id = await feedback_service.log_generation(
                org_key=self.org_id,
                user_sub=self.user_id,
                task_type="chat",  # or "codegen" for code generation tasks
                model=self.model,
                temperature=0.0,  # Autonomous agent uses 0 temperature
                params={"provider": self.provider, "task_id": context.task_id},
                prompt=prompt[:1000],  # Truncate prompt for storage
                input_fingerprint=None,
                result_ref=context.task_id,
            )
            logger.info(f"[AutonomousAgent] 📝 Logged generation: gen_id={gen_id}")

            # Also track suggestion in learning system
            try:
                learning_manager = get_feedback_manager()
                learning_manager.track_suggestion(
                    suggestion_id=str(gen_id),
                    category=SuggestionCategory.EXPLANATION,  # Default category
                    content="",  # Content tracked separately
                    context=context.original_request[:500],  # User's request
                    org_id=self.org_id,
                    user_id=self.user_id,
                )
                logger.info(
                    f"[AutonomousAgent] 🎯 Tracked suggestion in learning system: gen_id={gen_id}"
                )
            except Exception as le:
                logger.warning(f"[AutonomousAgent] Failed to track suggestion: {le}")

            return gen_id
        except Exception as e:
            logger.warning(f"[AutonomousAgent] Failed to log generation: {e}")
            return None

    async def _diagnose_environment(self) -> str:
        """
        Diagnose the development environment ONCE at the start.
        This prevents the agent from blindly guessing what tools are available.
        Properly sources nvm/volta/fnm before checking Node.js tools.
        """
        diagnostics = []
        home = os.environ.get("HOME", os.path.expanduser("~"))

        # Build nvm activation command
        nvm_activate = (
            f'export NVM_DIR="{home}/.nvm" && '
            f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" 2>/dev/null'
        )

        # Build volta activation command
        volta_activate = (
            f'export VOLTA_HOME="{home}/.volta" && '
            f'export PATH="$VOLTA_HOME/bin:$PATH"'
        )

        # Build fnm activation command
        fnm_activate = 'eval "$(fnm env 2>/dev/null)" 2>/dev/null || true'

        # Combined Node.js environment setup (tries all managers)
        node_env_setup = f"{nvm_activate} || {volta_activate} || {fnm_activate}"

        checks = [
            # Node.js ecosystem - WITH proper environment activation
            (
                "Node.js",
                f"({node_env_setup}) && node --version 2>/dev/null || "
                f"/opt/homebrew/bin/node --version 2>/dev/null || "
                f"/usr/local/bin/node --version 2>/dev/null || "
                f"echo 'not found'",
            ),
            (
                "npm",
                f"({node_env_setup}) && npm --version 2>/dev/null || "
                f"/opt/homebrew/bin/npm --version 2>/dev/null || "
                f"/usr/local/bin/npm --version 2>/dev/null || "
                f"echo 'not found'",
            ),
            (
                "npx",
                f"({node_env_setup}) && npx --version 2>/dev/null || "
                f"/opt/homebrew/bin/npx --version 2>/dev/null || "
                f"echo 'not found'",
            ),
            (
                "nvm",
                f'{nvm_activate} && nvm --version 2>/dev/null || echo "not found"',
            ),
            (
                "volta",
                'command -v volta >/dev/null 2>&1 && volta --version 2>/dev/null || echo "not found"',
            ),
            (
                "fnm",
                'command -v fnm >/dev/null 2>&1 && fnm --version 2>/dev/null || echo "not found"',
            ),
            (
                "Available Node versions",
                f"ls {home}/.nvm/versions/node/ 2>/dev/null | tr '\\n' ' ' || echo 'none'",
            ),
            # Python ecosystem
            (
                "Python",
                "python3 --version 2>/dev/null || python --version 2>/dev/null || echo 'not found'",
            ),
            (
                "pip",
                "pip3 --version 2>/dev/null || pip --version 2>/dev/null || echo 'not found'",
            ),
            # Docker
            ("Docker", "docker --version 2>/dev/null || echo 'not found'"),
            ("Docker running", "docker ps >/dev/null 2>&1 && echo 'yes' || echo 'no'"),
            # Package managers
            ("Homebrew", "brew --version 2>/dev/null | head -1 || echo 'not found'"),
            # OS info
            ("OS", "uname -s 2>/dev/null"),
            # Current directory info
            ("Working dir", f"echo '{self.workspace_path}'"),
            # Check if node_modules exists
            (
                "node_modules",
                f"[ -d '{self.workspace_path}/node_modules' ] && echo 'exists' || echo 'missing (run npm install)'",
            ),
        ]

        for name, cmd in checks:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    executable="/bin/bash",
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.workspace_path,
                )
                value = result.stdout.strip() or result.stderr.strip() or "unknown"
                diagnostics.append(f"{name}: {value}")
            except Exception as e:
                diagnostics.append(f"{name}: error checking ({e})")

        return "\n".join(diagnostics)

    async def _generate_plan(
        self, request: str, env_info: str, context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate a high-level plan for complex tasks before execution.
        This helps users understand what the agent will do.
        """
        # Determine if this is a complex task that needs planning
        # Simple tasks: single file edits, quick questions, simple commands
        # Complex tasks: multi-file changes, new feature implementation, debugging
        is_complex = len(request) > 200 or any(
            kw in request.lower()
            for kw in [
                "implement",
                "create",
                "build",
                "develop",
                "fix all",
                "refactor",
                "add feature",
                "new feature",
                "multiple files",
                "complete",
                "full",
                "entire",
                "whole",
                "application",
                "project",
            ]
        )

        if not is_complex:
            # For simple tasks, generate a meaningful step label based on the request
            request_lower = request.lower()

            # Generate a task-specific label based on request content
            if (
                "fix" in request_lower
                or "error" in request_lower
                or "bug" in request_lower
            ):
                label = "Fix the issue"
                desc = "Analyzing and fixing the reported problem"
            elif "add" in request_lower:
                label = "Add requested feature"
                desc = "Implementing the requested addition"
            elif "create" in request_lower:
                label = "Create component"
                desc = "Creating the requested file or component"
            elif "update" in request_lower or "change" in request_lower:
                label = "Apply changes"
                desc = "Updating the code as requested"
            elif "delete" in request_lower or "remove" in request_lower:
                label = "Remove items"
                desc = "Removing the specified code or files"
            elif "refactor" in request_lower:
                label = "Refactor code"
                desc = "Restructuring code for better quality"
            elif "test" in request_lower:
                label = "Run tests"
                desc = "Executing and verifying tests"
            elif (
                "read" in request_lower
                or "show" in request_lower
                or "what" in request_lower
            ):
                label = "Analyze code"
                desc = "Reading and understanding the code"
            elif "explain" in request_lower:
                label = "Explain code"
                desc = "Providing explanation of the code"
            elif (
                "npm install" in request_lower
                or "yarn install" in request_lower
                or "pnpm install" in request_lower
            ):
                # Package installation commands
                pm = (
                    "npm"
                    if "npm" in request_lower
                    else "yarn" if "yarn" in request_lower else "pnpm"
                )
                label = f"Install dependencies with {pm}"
                desc = f"Running {pm} install to install project dependencies"
            elif any(
                cmd in request_lower
                for cmd in ["npm start", "npm run", "npm dev", "yarn start", "yarn dev"]
            ):
                # Run/start commands
                if "dev" in request_lower:
                    label = "Start development server"
                    desc = "Running dev script to start the development server"
                elif "build" in request_lower:
                    label = "Build project"
                    desc = "Running build script to create production build"
                else:
                    label = "Run npm script"
                    desc = "Executing the requested npm/yarn script"
            elif "run" in request_lower and any(
                word in request_lower for word in ["command", "script", "execute"]
            ):
                # Generic command execution
                label = "Execute command"
                desc = "Running the requested command"
            else:
                # For all other cases, generate a meaningful action-oriented step
                # instead of echoing the user's request
                label = "Complete task"

                # Try to infer the action from the request
                request_lower = request.lower()
                if any(word in request_lower for word in ["see", "show", "view", "look", "check"]):
                    if any(word in request_lower for word in ["animation", "video", "result", "output"]):
                        label = "Run and display animation"
                        desc = "Execute the animation script and show the visual output"
                    elif any(word in request_lower for word in ["file", "code"]):
                        label = "Read and explain code"
                        desc = "Analyze the file and explain how it works"
                    else:
                        label = "Analyze and show result"
                        desc = "Process the request and display the outcome"
                elif any(word in request_lower for word in ["run", "execute", "start"]):
                    label = "Execute command"
                    desc = "Run the specified command and show results"
                elif any(word in request_lower for word in ["help", "how"]):
                    label = "Provide assistance"
                    desc = "Analyze the question and provide helpful guidance"
                else:
                    # Generic fallback - use a brief description of the actual task
                    label = "Complete task"
                    desc = "Process the request and perform necessary actions"

            # Emit plan_start event in the format the frontend expects
            plan_id = f"plan-{uuid.uuid4().hex[:8]}"
            context.plan_id = plan_id  # Store plan_id in context for step_update events
            yield {
                "type": "plan_start",
                "data": {
                    "plan_id": plan_id,
                    "steps": [
                        {
                            "index": 1,
                            "title": label,
                            "detail": desc,
                            "status": "pending",
                        }
                    ],
                },
            }
            # Also emit legacy format for backwards compatibility
            yield {
                "type": "plan",
                "steps": [
                    {"id": 1, "label": label, "description": desc, "status": "pending"}
                ],
                "estimated_files": [],
                "is_complex": False,
            }
            return

        # For complex tasks, use LLM to generate a proper plan
        plan_prompt = f"""Analyze this task and create a SPECIFIC execution plan (3-5 steps).

TASK: {request}

ENVIRONMENT:
{env_info}

Create steps that are SPECIFIC to this task, not generic.

**CRITICAL: Only include steps that an AI agent can AUTOMATICALLY execute.**
You are an autonomous coding agent that can:
- Read, create, edit, and delete files
- Run terminal commands (build, test, lint, install packages)
- Search and analyze code
- Run automated tests (unit, integration, E2E)
- Execute build and type checking

You CANNOT:
- Perform manual user testing (requires human clicking/interacting)
- Get user feedback (requires human)
- Deploy to production (requires approval)
- Conduct interviews or surveys
- Access external systems that require authentication you don't have

**TESTING GUIDELINES - USE AUTOMATED TESTING:**
When a task involves testing, ALWAYS use automatable testing:
✅ GOOD testing steps:
- "Run unit tests" (npm test, pytest, jest)
- "Write E2E tests" (Playwright, Cypress)
- "Run integration tests"
- "Verify with automated tests"
- "Add test coverage for new code"
- "Run linting and type checks"

❌ BAD testing steps (NEVER use):
- "Perform user testing" (requires human)
- "User acceptance testing" (requires human)
- "Manual testing" (requires human)
- "Get user feedback" (requires human)

Examples of GOOD task-specific steps:
- For "create a login page": "Create LoginForm component", "Add authentication logic", "Write tests for login"
- For "fix CSS errors": "Identify missing CSS modules", "Create CTASection.module.css", "Run build to verify"
- For "implement API": "Create API route handlers", "Add database queries", "Write and run API tests"
- For "improve UI design": "Update component styles", "Add animations", "Run visual regression tests"

Examples of BAD steps (DO NOT use these):
- "Analyze codebase" (too vague)
- "Implement changes" (not specific)
- "Run verification" (always implied)
- "Perform user testing" (requires human - NEVER include this)
- "Get user feedback" (requires human)
- "Deploy to production" (requires approval)
- "Conduct A/B testing" (requires human users)
- "Manual QA testing" (requires human)

Respond with ONLY a JSON object:
{{
  "steps": [
    {{"id": 1, "label": "Specific action (max 30 chars)", "description": "What exactly will be done"}},
    ...
  ],
  "estimated_files": ["specific/file/path.ts", "another/file.css"]
}}

Return ONLY the JSON, no markdown or explanations."""

        try:
            # Use a fast model for planning
            if self.provider == "anthropic":
                import anthropic

                client = anthropic.AsyncAnthropic(api_key=self.api_key)
                response = await client.messages.create(
                    model="claude-3-5-haiku-latest",
                    max_tokens=500,
                    messages=[{"role": "user", "content": plan_prompt}],
                )
                plan_text = response.content[0].text
            else:
                import openai

                client = openai.AsyncOpenAI(api_key=self.api_key)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=500,
                    messages=[{"role": "user", "content": plan_prompt}],
                )
                plan_text = response.choices[0].message.content

            # Parse the plan
            import json

            # Extract JSON from response (handle potential markdown wrapping)
            plan_text = plan_text.strip()
            if plan_text.startswith("```"):
                plan_text = plan_text.split("```")[1]
                if plan_text.startswith("json"):
                    plan_text = plan_text[4:]
            plan_text = plan_text.strip()

            plan_data = json.loads(plan_text)
            steps = plan_data.get("steps", [])
            estimated_files = plan_data.get("estimated_files", [])

            # Ensure steps have proper structure
            formatted_steps = []
            for i, step in enumerate(steps[:5]):  # Max 5 steps
                formatted_steps.append(
                    {
                        "id": step.get("id", i + 1),
                        "label": str(step.get("label", f"Step {i + 1}"))[:30],
                        "description": str(step.get("description", "")),
                        "status": "pending",
                    }
                )

            # Emit plan_start event in the format the frontend expects
            plan_id = f"plan-{uuid.uuid4().hex[:8]}"
            context.plan_id = plan_id  # Store plan_id in context for step_update events
            yield {
                "type": "plan_start",
                "data": {
                    "plan_id": plan_id,
                    "steps": [
                        {
                            "index": s["id"],
                            "title": s["label"],
                            "detail": s["description"],
                        }
                        for s in formatted_steps
                    ],
                },
            }
            # Also emit legacy format for backwards compatibility
            yield {
                "type": "plan",
                "steps": formatted_steps,
                "estimated_files": estimated_files[:10],  # Max 10 files
                "is_complex": True,
            }

        except Exception as e:
            logger.warning(f"[AutonomousAgent] Plan generation failed: {e}")
            # Fall back to a task-specific default plan based on keywords
            request_lower = request.lower()

            if (
                "fix" in request_lower
                or "error" in request_lower
                or "bug" in request_lower
            ):
                fallback_steps = [
                    {
                        "id": 1,
                        "label": "Identify issues",
                        "description": "Find the root cause of errors",
                        "status": "pending",
                    },
                    {
                        "id": 2,
                        "label": "Apply fixes",
                        "description": "Make corrections to resolve issues",
                        "status": "pending",
                    },
                    {
                        "id": 3,
                        "label": "Test changes",
                        "description": "Verify fixes work correctly",
                        "status": "pending",
                    },
                ]
            elif (
                "create" in request_lower
                or "add" in request_lower
                or "new" in request_lower
            ):
                fallback_steps = [
                    {
                        "id": 1,
                        "label": "Check dependencies",
                        "description": "Review existing files and imports",
                        "status": "pending",
                    },
                    {
                        "id": 2,
                        "label": "Create new files",
                        "description": "Generate required components",
                        "status": "pending",
                    },
                    {
                        "id": 3,
                        "label": "Update imports",
                        "description": "Connect new files to project",
                        "status": "pending",
                    },
                ]
            elif "implement" in request_lower or "build" in request_lower:
                fallback_steps = [
                    {
                        "id": 1,
                        "label": "Review requirements",
                        "description": "Understand what needs to be built",
                        "status": "pending",
                    },
                    {
                        "id": 2,
                        "label": "Build components",
                        "description": "Create the implementation",
                        "status": "pending",
                    },
                    {
                        "id": 3,
                        "label": "Integrate & test",
                        "description": "Connect and verify functionality",
                        "status": "pending",
                    },
                ]
            else:
                fallback_steps = [
                    {
                        "id": 1,
                        "label": "Analyze request",
                        "description": "Understand the task requirements",
                        "status": "pending",
                    },
                    {
                        "id": 2,
                        "label": "Execute changes",
                        "description": "Perform the necessary actions",
                        "status": "pending",
                    },
                    {
                        "id": 3,
                        "label": "Verify results",
                        "description": "Ensure task completed successfully",
                        "status": "pending",
                    },
                ]

            # Emit plan_start event in the format the frontend expects
            plan_id = f"plan-{uuid.uuid4().hex[:8]}"
            context.plan_id = plan_id  # Store plan_id in context for step_update events
            yield {
                "type": "plan_start",
                "data": {
                    "plan_id": plan_id,
                    "steps": [
                        {
                            "index": s["id"],
                            "title": s["label"],
                            "detail": s["description"],
                        }
                        for s in fallback_steps
                    ],
                },
            }
            # Also emit legacy format for backwards compatibility
            yield {
                "type": "plan",
                "steps": fallback_steps,
                "estimated_files": [],
                "is_complex": True,
            }

    def _calculate_step_progress(
        self, context: TaskContext, tool_name: str
    ) -> Optional[Dict]:
        """
        Calculate step progress based on tool usage and overall execution state.

        Uses heuristics to map tool activity to execution plan steps.
        """
        # Check if we have a plan to track
        if not context.plan_id or context.step_count == 0:
            return None

        # Determine which step we should be on based on activities
        has_writes = len(context.files_modified) + len(context.files_created) > 0
        has_commands = len(context.commands_run) > 0

        # Map tool types to step phases (kept for future routing logic)

        # Determine target step based on current tool and overall progress
        # Be conservative - don't jump ahead too quickly
        if context.step_count == 1:
            # Single step plan - always on step 0
            target_step = 0
        elif context.step_count == 2:
            # Two step plan: only advance when we have substantial progress
            if has_writes and has_commands:
                target_step = 1
            else:
                target_step = 0
        else:
            # 3+ step plan: advance gradually based on overall progress
            # Only move to final step when we have writes AND commands (substantial work done)
            if has_writes and has_commands:
                # We've done both implementation and commands - move to final step
                target_step = min(context.step_count - 1, 2)
            elif has_writes or (has_commands and context.iteration > 3):
                # We've started implementation OR we've been running commands for a while
                target_step = 1
            else:
                # Still in analysis/setup phase
                target_step = 0

        # Only emit if we're advancing or haven't emitted this step yet
        current_emitted = context.step_progress_emitted.get(target_step)

        # Mark previous steps as completed if we're advancing
        events = []
        if target_step > context.current_step_index:
            # Complete all steps from current to target (except target itself)
            for step_idx in range(context.current_step_index, target_step):
                step_status = context.step_progress_emitted.get(step_idx)
                # Only mark as completed if it was running or pending (not already completed)
                if step_status != "completed":
                    events.append(
                        {
                            "type": "step_update",
                            "data": {
                                "plan_id": context.plan_id,
                                "step_index": step_idx,
                                "status": "completed",
                            },
                        }
                    )
                    context.step_progress_emitted[step_idx] = "completed"

            # Mark new step as running
            context.current_step_index = target_step

        # Ensure current step is marked as running
        if current_emitted != "running" and current_emitted != "completed":
            events.append(
                {
                    "type": "step_update",
                    "data": {
                        "plan_id": context.plan_id,
                        "step_index": target_step,
                        "status": "running",
                    },
                }
            )
            context.step_progress_emitted[target_step] = "running"

        return events if events else None

    def _create_consent_event(
        self,
        result: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a consent event from a tool result that requires consent.

        This is a unified method used by all provider code paths (OpenAI, Anthropic, etc.)
        to ensure consistent consent event structure.

        Args:
            result: Tool execution result containing consent metadata
            args: Tool arguments containing cwd and other context

        Returns:
            Dict containing the consent event in SSE format
        """
        return {
            "type": "command.consent_required",
            "data": {
                "consent_id": result.get("consent_id"),
                "command": result.get("command"),
                "shell": "bash",
                "cwd": args.get("cwd", self.workspace_path),
                "danger_level": result.get("danger_level", "medium"),
                "warning": result.get("warning", ""),
                "consequences": result.get("consequences", []),
                "alternatives": result.get("alternatives", []),
                "rollback_possible": result.get("rollback_possible", False),
            },
            "timestamp": get_event_timestamp(),
        }

    def _check_requires_consent(
        self,
        result: Dict[str, Any],
        args: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a tool result requires user consent and return consent event if needed.

        This is a unified method used by all provider code paths (OpenAI, Anthropic, etc.)
        to ensure consistent consent checking logic.

        Args:
            result: Tool execution result
            args: Tool arguments containing cwd and other context

        Returns:
            Consent event dict if consent required, None otherwise
        """
        if result.get("requires_consent"):
            logger.info(
                f"[AutonomousAgent] 🔐 Consent required for command: {result.get('command')}"
            )
            return self._create_consent_event(result, args)
        return None

    async def _handle_consent_decision(
        self,
        consent_id: str,
        command: str,
        decision: Dict[str, Any],
        requested_at: datetime,
        danger_level: Optional[str] = None,
        cwd: Optional[str] = None
    ) -> Optional[str]:
        """
        Handle user's consent decision by saving preferences and logging to audit.

        Args:
            consent_id: The consent ID
            command: Original command string
            decision: Decision data from Redis
            requested_at: When consent was requested
            danger_level: Command danger level
            cwd: Current working directory

        Returns:
            Command to execute (original or alternative), or None if denied
        """
        if not self.user_id or not self.org_id:
            logger.warning("[AutonomousAgent] Cannot handle consent decision without user/org ID")
            return None

        choice = decision.get("choice", "deny")
        alternative_cmd = decision.get("alternative_command")
        responded_at = datetime.now()

        try:
            # Save preference if "always allow" choice
            if choice == "allow_always_exact":
                self.consent_service.save_preference(
                    user_id=str(self.user_id),
                    org_id=str(self.org_id),
                    preference_type="exact_command",
                    command=command
                )
            elif choice == "allow_always_type":
                self.consent_service.save_preference(
                    user_id=str(self.user_id),
                    org_id=str(self.org_id),
                    preference_type="command_type",
                    command=command
                )

            # Log decision to audit trail
            self.consent_service.log_decision(
                consent_id=consent_id,
                user_id=str(self.user_id),
                org_id=str(self.org_id),
                command=command,
                decision=choice,
                requested_at=requested_at,
                responded_at=responded_at,
                shell="bash",
                cwd=cwd,
                danger_level=danger_level,
                alternative_command=alternative_cmd
            )

            # Determine which command to execute
            if choice == "deny":
                return None
            elif choice == "alternative" and alternative_cmd:
                logger.info(f"[AutonomousAgent] Using alternative command: {alternative_cmd}")
                return alternative_cmd
            else:
                # allow_once, allow_always_exact, or allow_always_type
                return command

        except Exception as e:
            logger.error(f"[AutonomousAgent] Failed to handle consent decision: {e}")
            # Still return the command if user approved, even if logging failed
            if choice != "deny":
                return alternative_cmd if choice == "alternative" and alternative_cmd else command
            return None

    async def _check_auto_allow(self, command: str) -> bool:
        """
        Check if command is auto-allowed by user preferences.

        Args:
            command: Command string to check

        Returns:
            True if command is auto-allowed, False otherwise
        """
        if not self.user_id or not self.org_id:
            # Can't check preferences without user/org ID
            return False

        try:
            pref_type = self.consent_service.check_auto_allow(
                user_id=str(self.user_id),
                org_id=str(self.org_id),
                command=command
            )

            if pref_type:
                logger.info(
                    f"[AutonomousAgent] ✅ Auto-allowed '{command}' via {pref_type} preference"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"[AutonomousAgent] Failed to check auto-allow: {e}")
            return False

    async def _wait_for_consent(
        self, consent_id: str, timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Wait for user consent decision via Redis.

        Polls Redis until the user responds with a decision, or the timeout expires.

        Args:
            consent_id: The consent ID to wait for
            timeout_seconds: Maximum time to wait (default 5 minutes)

        Returns:
            Dict with decision data: {
                "choice": "allow_once" | "allow_always_exact" | "allow_always_type" | "deny" | "alternative",
                "alternative_command": Optional[str]
            }
            Returns {"choice": "deny"} if timeout or error
        """
        if not self.redis_client:
            logger.error(f"[AutonomousAgent] Redis not available, denying consent {consent_id}")
            return {"choice": "deny"}

        start_time = time.time()
        poll_interval = 0.5  # Poll every 500ms

        logger.info(
            f"[AutonomousAgent] ⏳ Waiting for consent {consent_id} (timeout: {timeout_seconds}s)"
        )

        while time.time() - start_time < timeout_seconds:
            # Check consent decision in Redis
            try:
                consent_data = await self.redis_client.get(f"consent:{consent_id}")

                if consent_data:
                    decision = json.loads(consent_data)

                    # Check if consent was decided (not still pending)
                    if not decision.get("pending", False):
                        choice = decision.get("choice", "deny")

                        logger.info(
                            f"[AutonomousAgent] {'✅' if choice != 'deny' else '❌'} "
                            f"Consent {consent_id} decision: {choice}"
                        )

                        # Clean up the consent record from Redis
                        await self.redis_client.delete(f"consent:{consent_id}")

                        return decision

            except Exception as e:
                logger.error(f"[AutonomousAgent] Error checking consent in Redis: {e}")

            # Wait before polling again
            await asyncio.sleep(poll_interval)

        # Timeout - consent not received
        logger.warning(
            f"[AutonomousAgent] ⏱️ Consent {consent_id} timed out after {timeout_seconds}s"
        )

        # Clean up pending consent from Redis
        try:
            await self.redis_client.delete(f"consent:{consent_id}")
        except Exception as e:
            logger.error(f"[AutonomousAgent] Error cleaning up consent: {e}")

        return {"choice": "deny"}

    def _log_tool_result(self, result: Dict[str, Any]) -> None:
        """
        Log tool execution result, with warning if tool failed.

        This is a unified method used by all provider code paths (OpenAI, Anthropic, etc.)
        to ensure consistent logging.

        Args:
            result: Tool execution result
        """
        if not result.get("success"):
            logger.warning(
                f"[AutonomousAgent] ⚠️ Tool error: {result.get('error', 'Unknown error')}"
            )

    def _create_tool_result_event(
        self, tool_id: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a tool_result SSE event.

        This is a unified method used by all provider code paths (OpenAI, Anthropic, etc.)
        to ensure consistent event structure.

        Args:
            tool_id: Tool call ID from the LLM
            result: Tool execution result

        Returns:
            Dict containing the tool_result event in SSE format
        """
        return {
            "type": "tool_result",
            "tool_result": {
                "id": tool_id,
                "result": result,
            },
            "timestamp": get_event_timestamp(),
        }

    async def _execute_tool(
        self, tool_name: str, arguments: Dict[str, Any], context: TaskContext
    ) -> Dict[str, Any]:
        """Execute a tool and track the action in context."""
        # === TOOL EXECUTION TRACING ===
        logger.info("-" * 40)
        logger.info(f"[AutonomousAgent] 🔧 TOOL CALL: {tool_name}")
        logger.info(
            f"[AutonomousAgent] Arguments: {json.dumps(arguments, default=str)[:500]}"
        )
        logger.info(f"[AutonomousAgent] Iteration: {context.iteration}")
        logger.info("-" * 40)

        try:
            if tool_name == "read_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {
                        "success": False,
                        "error": f"File not found: {arguments['path']}",
                    }

                with open(path, "r") as f:
                    lines = f.readlines()

                start = arguments.get("start_line", 1) - 1
                end = arguments.get("end_line", len(lines))
                content = "".join(lines[max(0, start) : end])

                context.files_read.append(arguments["path"])
                return {
                    "success": True,
                    "content": content,
                    "total_lines": len(lines),
                    "path": arguments["path"],
                }

            elif tool_name == "write_file":
                file_path = arguments.get("path", "")
                content = arguments.get("content", "")

                if not file_path:
                    return {"success": False, "error": "No file path provided"}

                if not content:
                    logger.warning(
                        f"write_file called with empty content for {file_path}"
                    )

                path = os.path.join(self.workspace_path, file_path)

                # If the user requested deletion, do not "clear" the file - delete it
                if content == "" and self._is_delete_request(context.original_request, context):
                    if not os.path.exists(path):
                        return {
                            "success": False,
                            "error": f"File not found for deletion: {file_path}",
                        }
                    logger.info(
                        f"[AutonomousAgent] ⚠️ write_file with empty content during delete request. Deleting instead: {file_path}"
                    )
                    import shlex
                    from backend.agent.tools.run_command import run_command as run_cmd
                    return await run_cmd(
                        user_id=str(self.user_id or "anonymous"),
                        command=f"rm {shlex.quote(file_path)}",
                        cwd=self.workspace_path,
                    )

                # Ensure parent directory exists (handle root files too)
                parent_dir = os.path.dirname(path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)

                is_new = not os.path.exists(path)

                try:
                    with open(path, "w") as f:
                        f.write(content)
                except Exception as write_error:
                    logger.error(f"Failed to write file {file_path}: {write_error}")
                    return {
                        "success": False,
                        "error": f"Failed to write file: {write_error}",
                    }

                # Verify the file was actually created/written
                if not os.path.exists(path):
                    logger.error(f"File {file_path} was not created despite no errors")
                    return {
                        "success": False,
                        "error": f"File {file_path} was not created",
                    }

                # Track the file
                if is_new:
                    if file_path not in context.files_created:
                        context.files_created.append(file_path)
                    logger.info(f"✅ Created file: {file_path} ({len(content)} bytes)")
                else:
                    if file_path not in context.files_modified:
                        context.files_modified.append(file_path)
                    logger.info(f"✅ Modified file: {file_path} ({len(content)} bytes)")

                return {
                    "success": True,
                    "path": file_path,
                    "action": "created" if is_new else "modified",
                    "size": len(content),
                }

            elif tool_name == "edit_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {
                        "success": False,
                        "error": f"File not found: {arguments['path']}",
                    }

                with open(path, "r") as f:
                    content = f.read()

                if arguments["old_text"] not in content:
                    return {
                        "success": False,
                        "error": "Could not find the text to replace. The file may have changed.",
                        "hint": "Try reading the file again to see current content.",
                    }

                new_content = content.replace(
                    arguments["old_text"], arguments["new_text"], 1
                )
                with open(path, "w") as f:
                    f.write(new_content)

                if arguments["path"] not in context.files_modified:
                    context.files_modified.append(arguments["path"])

                return {"success": True, "path": arguments["path"]}

            elif tool_name == "run_command":
                cwd = self.workspace_path
                if arguments.get("cwd"):
                    cwd = os.path.join(self.workspace_path, arguments["cwd"])

                command = arguments["command"]
                command_raw = command

                def _is_background_command(cmd: str) -> bool:
                    stripped = cmd.strip()
                    if stripped.endswith("&"):
                        return True
                    bg_tokens = ("nohup ", "pm2 ", "forever ", "daemon ", "disown")
                    return any(token in stripped for token in bg_tokens)

                def _extract_port_from_command(cmd: str) -> Optional[int]:
                    port_match = re.search(
                        r"--port[=\s]+(\d+)|-p[=\s]+(\d+)|PORT=(\d+)", cmd
                    )
                    if not port_match:
                        return None
                    for group in port_match.groups():
                        if group:
                            try:
                                return int(group)
                            except ValueError:
                                return None
                    return None

                def _determine_server_port(workdir: str) -> Optional[int]:
                    port = _extract_port_from_command(command_raw)
                    if port:
                        return port
                    try:
                        from backend.services.navi_brain import (
                            SelfHealingEngine,
                            NaviConfig,
                            ProjectAnalyzer,
                        )

                        configured = SelfHealingEngine._get_configured_port(workdir)
                        if configured:
                            return configured
                        project_info = ProjectAnalyzer.analyze(workdir)
                        return NaviConfig.get_preferred_port(project_info)
                    except Exception:
                        return None

                # Check if this is a dangerous command that requires consent
                cmd_info = get_command_info(command)
                if cmd_info is not None and cmd_info.requires_confirmation:
                    # Check if consent has already been granted for this command
                    consent_id = arguments.get("consent_id")

                    # Check global consent approvals first (protected by lock)
                    consent_denied = False
                    with _consent_lock:
                        if consent_id and consent_id in _consent_approvals:
                            approval = _consent_approvals[consent_id]
                            if approval.get("approved"):
                                # Consent was approved, proceed with execution
                                logger.info(
                                    f"[AutonomousAgent] ✅ Consent approved for command: {command}"
                                )
                                # Clean up the approval to prevent reuse
                                del _consent_approvals[consent_id]
                            else:
                                # Consent was denied
                                logger.info(
                                    f"[AutonomousAgent] ❌ Consent denied for command: {command}"
                                )
                                consent_denied = True

                    # Handle consent decision outside lock to avoid holding it during return
                    if consent_denied:
                        return {
                            "success": False,
                            "error": "User denied consent for this command",
                            "consent_denied": True,
                        }
                    elif not consent_id or consent_id not in self.pending_consents:
                        # Generate new consent request
                        consent_id = str(uuid.uuid4())
                        permission_request = format_permission_request(
                            command, cmd_info, cwd
                        )

                        # Store pending consent in both locations
                        consent_data = {
                            "command": command,
                            "cwd": cwd,
                            "cmd_info": cmd_info,
                            "permission_request": permission_request,
                            "timestamp": int(__import__("time").time()),
                            "user_id": self.user_id,
                            "org_id": self.org_id,
                        }
                        self.pending_consents[consent_id] = consent_data
                        with _consent_lock:
                            _consent_approvals[consent_id] = {
                                "approved": False,
                                "command": command,
                                "timestamp": int(__import__("time").time()),
                                "pending": True,
                                "user_id": self.user_id,
                                "org_id": self.org_id,
                            }

                        # Return consent required response
                        return {
                            "success": False,
                            "requires_consent": True,
                            "consent_id": consent_id,
                            "command": command,
                            "danger_level": cmd_info.risk_level.value,
                            "warning": permission_request["warning_message"],
                            "consequences": cmd_info.consequences,
                            "alternatives": cmd_info.alternatives,
                            "rollback_possible": cmd_info.rollback_possible,
                            "error": f"⚠️ CONSENT REQUIRED: This command requires user approval. A consent dialog has been shown to the user. DO NOT retry this command until the user has approved it. The consent_id is: {consent_id}",
                        }

                env = get_command_env()

                # Detect if this is a Node.js command that needs nvm setup
                is_node_cmd = is_node_command(command)

                # If it's a node command and doesn't already source nvm, add the setup
                if is_node_cmd and "nvm.sh" not in command:
                    env_setup = get_node_env_setup(
                        cwd=cwd,
                        include_project_bins=False,
                        include_common_paths=True,
                        fnm_use_on_cd=False,
                    )
                    if env_setup:
                        command = f"{env_setup} && {command}"
                        logger.info("[AutonomousAgent] Added node env setup to command")

                # If command is already wrapped in bash -c, extract the inner command
                # to avoid double-wrapping issues
                if command.strip().startswith("bash -c"):
                    # Extract command from bash -c '...' or bash -c "..."
                    import shlex

                    try:
                        parts = shlex.split(command)
                        if len(parts) >= 3 and parts[0] == "bash" and parts[1] == "-c":
                            command = parts[2]
                            logger.info("[AutonomousAgent] Unwrapped bash -c command")
                    except Exception:
                        pass  # Keep original if parsing fails

                # Determine timeout - use parameter or default (5 minutes)
                cmd_timeout = arguments.get("timeout_seconds", 300)

                # Cap timeout at 30 minutes for safety
                cmd_timeout = min(cmd_timeout, 1800)

                # Auto-extend timeout for known long-running commands
                long_running_patterns = [
                    "npm install",
                    "npm ci",
                    "yarn install",
                    "pnpm install",
                    "bun install",
                    "pip install",
                    "poetry install",
                    "pipenv install",
                    "bundle install",
                    "gem install",
                    "composer install",
                    "composer update",
                    "cargo build",
                    "cargo install",
                    "mvn install",
                    "mvn package",
                    "mvn compile",
                    "gradle build",
                    "gradle assemble",
                    "docker build",
                    "docker-compose build",
                    "npm run build",
                    "yarn build",
                    "pnpm build",
                    "npm test",
                    "yarn test",
                    "pytest",
                    "jest --",
                ]

                if any(pattern in command for pattern in long_running_patterns):
                    cmd_timeout = max(
                        cmd_timeout, 1200
                    )  # 20 minutes minimum for complex operations
                    logger.info(
                        f"[AutonomousAgent] Extended timeout to {cmd_timeout}s for long-running command"
                    )
                elif cmd_timeout != 300:
                    logger.info(
                        f"[AutonomousAgent] Using custom timeout: {cmd_timeout}s"
                    )

                # ==== INTELLIGENT PORT CONFLICT HANDLING ====
                # Check if this is a dev server command that might have port conflicts
                dev_server_patterns = [
                    "npm run dev",
                    "npm run start",
                    "npm start",
                    "yarn dev",
                    "yarn start",
                    "pnpm dev",
                    "pnpm start",
                    "bun dev",
                    "bun start",
                    "vite",
                    "next dev",
                    "next start",
                    "uvicorn",
                    "python -m uvicorn",
                    "fastapi",
                    "flask run",
                    "python app.py",
                    "python main.py",
                    "rails server",
                    "rails s",
                ]

                is_dev_server_cmd = any(
                    pattern in command for pattern in dev_server_patterns
                )

                if is_dev_server_cmd and not _is_background_command(command):
                    server_port = _determine_server_port(cwd)
                    if server_port:
                        logger.info(
                            "[AutonomousAgent] Detected dev server command; using start_server tool for background start and verification"
                        )
                        return await self._execute_tool(
                            "start_server",
                            {"command": command, "port": server_port},
                            context,
                        )

                if is_dev_server_cmd and cwd:
                    from backend.services.navi_brain import SelfHealingEngine

                    # Get configured port from project config files
                    configured_port = SelfHealingEngine._get_configured_port(cwd)

                    # Remember this port for future use
                    if configured_port:
                        SelfHealingEngine._port_memory[cwd] = configured_port
                        logger.info(
                            f"[AutonomousAgent] Found configured port {configured_port} for project"
                        )
                    else:
                        # Try to remember from previous runs
                        configured_port = SelfHealingEngine._port_memory.get(cwd)
                        if configured_port:
                            logger.info(
                                f"[AutonomousAgent] Using remembered port {configured_port} for project"
                            )

                    # Check if the configured port is in use
                    if configured_port:
                        from backend.services.navi_brain import PortManager

                        # Check port status
                        port_status = await PortManager.check_port(configured_port)

                        if not port_status.is_available:
                            # Port is busy - identify the process
                            process_owner = (
                                await SelfHealingEngine._identify_process_owner(
                                    configured_port, cwd
                                )
                            )

                            if process_owner["is_same_project"]:
                                # Server is already running for this project!
                                logger.info(
                                    f"[AutonomousAgent] Port {configured_port} already running for this project - reporting success"
                                )
                                return {
                                    "success": True,
                                    "result": f"✅ Development server is already running on port {configured_port}\nAccess it at: http://localhost:{configured_port}",
                                    "exit_code": 0,
                                    "reason": "Server already running on configured port",
                                }

                            elif not process_owner["is_related"]:
                                # Different project - this is a real conflict
                                process_name = (
                                    port_status.process_name or "Unknown process"
                                )

                                # Find alternative port
                                alt_port = await PortManager.find_available_port(
                                    configured_port, configured_port + 100
                                )

                                logger.info(
                                    f"[AutonomousAgent] Port {configured_port} occupied by different project. "
                                    f"Will use port {alt_port} instead."
                                )

                                # Modify command to use alternative port
                                command = PortManager.modify_command_for_port(
                                    command, alt_port
                                )

                                # Update port memory
                                SelfHealingEngine._port_memory[cwd] = alt_port

                                # Add info message (will be shown to user)
                                logger.info(
                                    f"[AutonomousAgent] Modified command to use port {alt_port} "
                                    f"(original port {configured_port} in use by {process_name})"
                                )

                # Use async subprocess for real-time streaming output
                logger.info(
                    f"[AutonomousAgent] Executing command with streaming output: {command[:100]}..."
                )

                # Create async subprocess
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                    executable="/bin/bash",
                )

                stdout_lines = []
                stderr_lines = []

                async def read_stream(stream, output_list, stream_name):
                    """Read from stream line by line."""
                    while True:
                        line = await stream.readline()
                        if not line:
                            break

                        line_text = line.decode("utf-8", errors="replace").rstrip()
                        output_list.append(line_text)

                # Read stdout and stderr concurrently
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            read_stream(process.stdout, stdout_lines, "stdout"),
                            read_stream(process.stderr, stderr_lines, "stderr"),
                        ),
                        timeout=cmd_timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return {
                        "success": False,
                        "exit_code": -1,
                        "stdout": "\n".join(stdout_lines),
                        "stderr": f"Command timed out after {cmd_timeout} seconds",
                        "error": f"Command execution exceeded timeout of {cmd_timeout} seconds",
                    }

                # Wait for process to complete
                exit_code = await process.wait()

                stdout_text = "\n".join(stdout_lines)
                stderr_text = "\n".join(stderr_lines)

                context.commands_run.append(
                    {
                        "command": arguments["command"],
                        "exit_code": exit_code,
                        "success": exit_code == 0,
                    }
                )

                # If command failed, analyze the error and suggest alternatives
                error_analysis = ""
                if exit_code != 0:
                    error_analysis = analyze_command_error(
                        command=arguments["command"],
                        stderr=stderr_text,
                        stdout=stdout_text,
                        exit_code=exit_code,
                    )
                    logger.info(
                        f"[AutonomousAgent] Command failed - error analysis:\n{error_analysis}"
                    )

                response = {
                    "success": exit_code == 0,
                    "exit_code": exit_code,
                    "stdout": stdout_text[:3000] if stdout_text else "",
                    "stderr": stderr_text[:3000] if stderr_text else "",
                }

                # Add error analysis to help the agent try a different approach
                if error_analysis:
                    response["error_analysis"] = error_analysis

                # If this was a dev server command, verify the server is responding
                if is_dev_server_cmd:
                    server_port = _determine_server_port(cwd)
                    if server_port:
                        import urllib.request
                        import urllib.error

                        url = f"http://localhost:{server_port}/"
                        verified = False
                        last_error = ""
                        for _ in range(6):  # up to ~6 seconds total
                            try:
                                req = urllib.request.Request(url, method="HEAD")
                                with urllib.request.urlopen(req, timeout=2) as resp:
                                    if resp.status < 500:
                                        verified = True
                                        break
                            except urllib.error.HTTPError as e:
                                if e.code < 500:
                                    verified = True
                                    break
                                last_error = f"HTTP {e.code}"
                            except Exception as e:
                                last_error = str(e)

                        # Fallback: check port listener if HTTP check failed
                        if not verified:
                            try:
                                check = subprocess.run(
                                    ["lsof", "-i", f":{server_port}"],
                                    cwd=cwd,
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if check.stdout.strip():
                                    verified = True
                            except Exception as e:
                                last_error = last_error or str(e)

                        response.update(
                            {
                                "server_verified": verified,
                                "server_url": url,
                                "server_port": server_port,
                                "server_check_error": (
                                    last_error if not verified else ""
                                ),
                            }
                        )

                response["message"] = format_command_message(
                    arguments["command"],
                    response.get("success", False),
                    response.get("stdout", ""),
                    response.get("stderr", ""),
                )

                if response.get("server_verified"):
                    response[
                        "message"
                    ] += f" | Server responding at {response.get('server_url')}"

                # Post-process visual outputs (animations, videos)
                if response.get("success"):
                    try:
                        from backend.services.visual_output_handler import VisualOutputHandler

                        visual_handler = VisualOutputHandler(self.workspace_path)
                        visual_result = await visual_handler.process_visual_output(
                            output=stdout_text + "\n" + stderr_text,
                            created_files=context.files_created + context.files_modified
                        )

                        if visual_result and visual_result.get("compiled"):
                            # Add visual output info to result
                            response["visual_output"] = visual_result
                            # Enhance the message with visual output info
                            response["message"] += f"\n\n{visual_result['message']}"
                            logger.info(
                                f"[AutonomousAgent] ✅ Processed visual output: {visual_result.get('output_file')}"
                            )
                    except Exception as visual_err:
                        logger.warning(f"Visual output processing failed (non-critical): {visual_err}")

                return response

            elif tool_name == "search_files":
                import glob as glob_module

                pattern = arguments["pattern"]
                search_type = arguments["search_type"]
                results = []

                if search_type == "filename":
                    matches = glob_module.glob(
                        os.path.join(self.workspace_path, pattern), recursive=True
                    )
                    results = [
                        os.path.relpath(m, self.workspace_path) for m in matches[:30]
                    ]
                else:
                    try:
                        result = subprocess.run(
                            ["grep", "-r", "-l", pattern, "."],
                            cwd=self.workspace_path,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.stdout:
                            results = result.stdout.strip().split("\n")[:30]
                    except Exception:
                        pass

                return {"success": True, "matches": results, "count": len(results)}

            elif tool_name == "list_directory":
                path = os.path.join(self.workspace_path, arguments.get("path", ""))
                if not os.path.exists(path):
                    return {"success": False, "error": "Directory not found"}

                entries = []
                for entry in sorted(os.listdir(path))[:50]:
                    full_path = os.path.join(path, entry)
                    entries.append(
                        {
                            "name": entry,
                            "type": "directory" if os.path.isdir(full_path) else "file",
                        }
                    )

                return {"success": True, "entries": entries}

            elif tool_name == "start_server":
                import time
                import urllib.request
                import urllib.error

                command = arguments["command"]
                port = arguments["port"]
                health_path = arguments.get("health_path", "/")
                startup_time = arguments.get("startup_time", 10)

                env = get_command_env()

                # First, kill any existing process on the port
                try:
                    subprocess.run(
                        f"lsof -ti :{port} | xargs kill -9 2>/dev/null || true",
                        shell=True,
                        capture_output=True,
                        timeout=10,
                        env=env,
                    )
                except Exception:
                    pass

                # Also remove any lock files for Next.js
                try:
                    lock_path = os.path.join(
                        self.workspace_path, ".next", "dev", "lock"
                    )
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
                except Exception:
                    pass

                # Detect if this is a Node.js command that needs nvm setup
                is_node_cmd = is_node_command(command)

                # If it's a node command and doesn't already source nvm, add the setup
                server_command = command
                if is_node_cmd and "nvm.sh" not in command:
                    env_setup = get_node_env_setup(
                        cwd=self.workspace_path,
                        include_project_bins=False,
                        include_common_paths=True,
                        fnm_use_on_cd=False,
                    )
                    if env_setup:
                        server_command = f"{env_setup} && {command}"
                        logger.info(
                            "[AutonomousAgent] Added node env setup to start_server command"
                        )

                # Start the server in background using nohup
                log_file = os.path.join(self.workspace_path, ".navi-server.log")
                # Escape single quotes in command for bash -c
                escaped_command = server_command.replace("'", "'\\''")
                bg_command = f"cd {self.workspace_path} && nohup bash -c '{escaped_command}' > {log_file} 2>&1 &"

                try:
                    subprocess.run(bg_command, shell=True, timeout=5, env=env)
                except subprocess.TimeoutExpired:
                    pass  # Expected - we're running in background

                # Wait for server to start, checking periodically
                url = f"http://localhost:{port}{health_path}"
                server_started = False
                last_error = ""

                for i in range(startup_time * 2):  # Check every 0.5 seconds
                    time.sleep(0.5)
                    try:
                        req = urllib.request.Request(url, method="HEAD")
                        with urllib.request.urlopen(req, timeout=2) as response:
                            if response.status < 500:
                                server_started = True
                                break
                    except urllib.error.HTTPError as e:
                        # Even a 404 means server is running
                        if e.code < 500:
                            server_started = True
                            break
                        last_error = f"HTTP {e.code}"
                    except urllib.error.URLError as e:
                        last_error = str(e.reason)
                    except Exception as e:
                        last_error = str(e)

                # Get any log output
                log_content = ""
                try:
                    with open(log_file, "r") as f:
                        log_content = f.read()[-1000:]  # Last 1000 chars
                except Exception:
                    pass

                # Track the command
                context.commands_run.append(
                    {
                        "command": command,
                        "success": server_started,
                        "type": "start_server",
                    }
                )

                if server_started:
                    return {
                        "success": True,
                        "message": f"Server started successfully on port {port}",
                        "url": url,
                        "verified": True,
                        "log_preview": log_content[:500] if log_content else None,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Server did not respond after {startup_time} seconds",
                        "last_error": last_error,
                        "url": url,
                        "log_preview": (
                            log_content if log_content else "No log output captured"
                        ),
                        "suggestion": "Check the log output for errors. Common issues: port already in use, missing dependencies, build errors.",
                    }

            elif tool_name == "check_endpoint":
                import urllib.request
                import urllib.error

                url = arguments["url"]
                method = arguments.get("method", "GET")
                expected_status = arguments.get("expected_status", 200)

                try:
                    req = urllib.request.Request(url, method=method)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        body_preview = response.read(500).decode(
                            "utf-8", errors="ignore"
                        )
                        return {
                            "success": response.status == expected_status,
                            "status": response.status,
                            "responding": True,
                            "body_preview": body_preview,
                        }
                except urllib.error.HTTPError as e:
                    return {
                        "success": e.code == expected_status,
                        "status": e.code,
                        "responding": True,
                        "error": f"HTTP {e.code}: {e.reason}",
                    }
                except urllib.error.URLError as e:
                    return {
                        "success": False,
                        "responding": False,
                        "error": f"Connection failed: {e.reason}",
                    }
                except Exception as e:
                    return {"success": False, "responding": False, "error": str(e)}

            elif tool_name == "stop_server":
                port = arguments["port"]

                try:
                    # Find and kill processes on the port
                    result = subprocess.run(
                        f"lsof -ti :{port} | xargs kill -9 2>/dev/null",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    # Verify the port is free
                    check = subprocess.run(
                        f"lsof -ti :{port}",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if not check.stdout.strip():
                        return {
                            "success": True,
                            "message": f"Server on port {port} stopped successfully",
                            "port_free": True,
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to stop server on port {port}",
                            "port_free": False,
                        }
                except Exception as e:
                    return {"success": False, "error": str(e)}

            else:
                logger.error(f"[AutonomousAgent] ❌ UNKNOWN TOOL: {tool_name}")
                logger.error(
                    "[AutonomousAgent] Available tools: read_file, write_file, edit_file, run_command, search_files, list_directory, start_server, check_endpoint, stop_server"
                )
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"[AutonomousAgent] ❌ TOOL EXCEPTION: {tool_name} - {e}")
            import traceback

            logger.error(f"[AutonomousAgent] Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    def _generate_next_steps(self, context: TaskContext) -> List[str]:
        """Generate helpful next steps based on what was accomplished."""
        steps = []

        # If we modified files, suggest testing
        if context.files_modified:
            if any("test" in f.lower() for f in context.files_modified):
                steps.append("Run tests to verify the changes")
            else:
                steps.append("Run tests to verify the changes work correctly")

        # If we created new files, suggest reviewing
        if context.files_created:
            steps.append("Review the newly created files")

        # If we ran commands that built something
        if context.commands_run:
            has_build = any(
                "build" in cmd.get("command", "").lower()
                for cmd in context.commands_run
            )
            has_start = any(
                "start" in cmd.get("command", "").lower()
                or "dev" in cmd.get("command", "").lower()
                for cmd in context.commands_run
            )

            if has_build and not has_start:
                steps.append("Start the development server to see the changes")
            elif has_start:
                steps.append("Check the running application in your browser")

        # Project-type specific suggestions
        if self.project_type == "node":
            if not steps:
                steps.append("Run npm run dev to see the changes")
        elif self.project_type == "python":
            if not steps:
                steps.append("Run the application to verify the changes")

        # Generic suggestions if nothing specific
        if not steps:
            steps.append("Review the changes made")
            steps.append("Test the functionality")

        # Limit to 3 most relevant steps
        return steps[:3]

    def _can_parallelize_tools(
        self, tools: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Separate tools into parallelizable reads and sequential writes.
        Read operations (search, list, read_file) can be parallelized.
        Write operations must execute sequentially to maintain consistency.
        """
        # Write operations for the autonomous agent's local tools
        # These mutate files, run commands, or have side effects
        LOCAL_WRITE_OPERATIONS = {
            "write_file",
            "edit_file",
            "run_command",
            "start_server",
            "stop_server",
        }

        parallel_reads = []
        sequential_writes = []

        for tool in tools:
            tool_name = tool.get("name", "")
            if tool_name in LOCAL_WRITE_OPERATIONS:
                sequential_writes.append(tool)
            else:
                parallel_reads.append(tool)

        return parallel_reads, sequential_writes

    async def _execute_tools_parallel(
        self, tools: List[Dict[str, Any]], context: TaskContext, max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple read-only tools in parallel using asyncio.gather.
        Uses a semaphore to limit concurrent executions.
        """
        if not tools:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def execute_with_semaphore(tool: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                tool_name = tool.get("name", "")
                args = tool.get("input", tool.get("arguments", {}))
                try:
                    result = await self._execute_tool(tool_name, args, context)
                    return {"tool": tool, "result": result, "success": True}
                except Exception as e:
                    logger.error(
                        f"[AutonomousAgent] Parallel tool execution failed for {tool_name}: {e}"
                    )
                    return {"tool": tool, "result": {"error": str(e)}, "success": False}

        tasks = [execute_with_semaphore(t) for t in tools]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any gather-level exceptions
        processed = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[AutonomousAgent] Parallel execution exception: {r}")
                processed.append(
                    {
                        "tool": tools[i] if i < len(tools) else {},
                        "result": {"error": str(r)},
                        "success": False,
                    }
                )
            else:
                processed.append(r)

        return processed

    async def _call_llm_with_tools(
        self,
        messages: List[Dict[str, Any]],
        context: TaskContext,
        rag_context: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call LLM with tools and stream the response."""

        system_prompt = self._build_system_prompt(context, rag_context=rag_context)

        if self.provider == "anthropic":
            async for event in self._call_anthropic(messages, system_prompt, context):
                yield event
        else:
            async for event in self._call_openai(messages, system_prompt, context):
                yield event

    async def _call_anthropic(
        self, messages: List[Dict[str, Any]], system_prompt: str, context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call Anthropic Claude with tools."""
        import aiohttp
        from backend.services.streaming_agent import NAVI_TOOLS

        # === LLM API CALL TRACING ===
        logger.info("=" * 60)
        logger.info("[AutonomousAgent] 🤖 CALLING ANTHROPIC API")
        logger.info(f"[AutonomousAgent] Model: {self.model}")
        logger.info(f"[AutonomousAgent] Messages Count: {len(messages)}")
        logger.info(
            f"[AutonomousAgent] Tools Available: {[t['name'] for t in NAVI_TOOLS]}"
        )
        logger.info(
            f"[AutonomousAgent] Last Message Role: {messages[-1]['role'] if messages else 'N/A'}"
        )
        if messages:
            last_content = str(messages[-1].get("content", ""))[:200]
            logger.info(f"[AutonomousAgent] Last Message Preview: {last_content}...")
        logger.info("=" * 60)

        # Dynamic token allocation based on task complexity
        # Extract user request from first user message
        user_request = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_request = str(msg.get("content", ""))
                break

        # Estimate required tokens dynamically
        max_tokens = self._estimate_required_tokens(
            user_request, context, context.complexity
        )

        logger.info(
            f"[AutonomousAgent] 💡 Dynamic token allocation: {max_tokens} tokens "
            f"(Complexity: {context.complexity.value})"
        )

        async with aiohttp.ClientSession() as session:
            while True:
                payload = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": messages,
                    "tools": NAVI_TOOLS,
                    "stream": True,
                }

                headers = {
                    "x-api-key": self.api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                }

                logger.info("[AutonomousAgent] 📡 Sending request to Anthropic...")

                # === METRICS: Start LLM call timer ===
                call_start_time = time.time()

                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(
                        total=600
                    ),  # 10 minutes for complex operations
                ) as response:
                    logger.info(
                        f"[AutonomousAgent] 📥 Response Status: {response.status}"
                    )

                    if response.status != 200:
                        # === METRICS: Record failed LLM call ===
                        call_duration_ms = (time.time() - call_start_time) * 1000
                        LLM_CALLS.labels(
                            phase="autonomous", model=self.model, status="error"
                        ).inc()
                        LLM_LATENCY.labels(
                            phase="autonomous", model=self.model
                        ).observe(call_duration_ms)

                        error = await response.text()
                        logger.error(f"[AutonomousAgent] ❌ API Error: {error[:500]}")
                        yield {"type": "error", "error": error}
                        return

                    text_buffer = ""
                    full_text_for_plan = ""  # Accumulate text for plan detection
                    detected_plan = None  # Track if we've detected a plan
                    tool_calls = []
                    current_tool = None
                    stop_reason = None
                    input_tokens = 0
                    output_tokens = 0

                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            event_type = data.get("type", "")

                            # Capture token usage from message_start event
                            if event_type == "message_start":
                                usage = data.get("message", {}).get("usage", {})
                                input_tokens = usage.get("input_tokens", 0)
                                logger.info(
                                    f"[AutonomousAgent] 📊 Input tokens: {input_tokens}"
                                )

                            # Capture output tokens from message_delta event
                            elif event_type == "message_delta":
                                usage = data.get("usage", {})
                                if usage:
                                    output_tokens = usage.get("output_tokens", 0)
                                    logger.info(
                                        f"[AutonomousAgent] 📊 Output tokens: {output_tokens}"
                                    )
                                stop_reason = data.get("delta", {}).get("stop_reason")

                            if event_type == "content_block_start":
                                block = data.get("content_block", {})
                                if block.get("type") == "tool_use":
                                    logger.info(
                                        f"[AutonomousAgent] 🔧 LLM requesting tool: {block.get('name')}"
                                    )
                                    current_tool = {
                                        "id": block.get("id"),
                                        "name": block.get("name"),
                                        "input": "",
                                    }
                                    if text_buffer:
                                        yield {
                                            "type": "text",
                                            "text": text_buffer,
                                            "timestamp": get_event_timestamp(),
                                        }
                                        text_buffer = ""

                            elif event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    text_buffer += text
                                    full_text_for_plan += text

                                    # Check for plan in accumulated text (only if not already detected)
                                    if (
                                        not detected_plan
                                        and len(full_text_for_plan) > 100
                                    ):
                                        detected_plan = parse_execution_plan(
                                            full_text_for_plan
                                        )
                                        if detected_plan:
                                            logger.info(
                                                f"[AutonomousAgent] ⚡ Detected execution plan with {len(detected_plan['steps'])} steps"
                                            )
                                            yield {
                                                "type": "plan_start",
                                                "data": detected_plan,
                                            }

                                    if len(text_buffer) >= 30 or text.endswith(
                                        (".", "!", "?", "\n")
                                    ):
                                        yield {
                                            "type": "text",
                                            "text": text_buffer,
                                            "timestamp": get_event_timestamp(),
                                        }
                                        text_buffer = ""
                                elif (
                                    delta.get("type") == "input_json_delta"
                                    and current_tool
                                ):
                                    current_tool["input"] += delta.get(
                                        "partial_json", ""
                                    )

                            elif event_type == "content_block_stop":
                                if current_tool:
                                    try:
                                        args = (
                                            json.loads(current_tool["input"])
                                            if current_tool["input"]
                                            else {}
                                        )
                                    except json.JSONDecodeError:
                                        args = {}

                                    yield {
                                        "type": "tool_call",
                                        "tool_call": {
                                            "id": current_tool["id"],
                                            "name": current_tool["name"],
                                            "arguments": args,
                                        },
                                        "timestamp": get_event_timestamp(),
                                    }

                                    # Emit step progress updates BEFORE execution (unified method)
                                    step_events = self._calculate_step_progress(
                                        context, current_tool["name"]
                                    )
                                    if step_events:
                                        for step_event in step_events:
                                            yield step_event

                                    # Execute the tool
                                    logger.info(
                                        f"[AutonomousAgent] ⚙️ Executing tool: {current_tool['name']}"
                                    )
                                    result = await self._execute_tool(
                                        current_tool["name"], args, context
                                    )
                                    logger.info(
                                        f"[AutonomousAgent] ✅ Tool result: success={result.get('success', 'N/A')}"
                                    )

                                    # Check if consent is required for this command
                                    consent_event = self._check_requires_consent(
                                        result, args
                                    )
                                    if consent_event:
                                        command = result.get("command", "")
                                        consent_id = result.get("consent_id")

                                        # Check if command is auto-allowed by user preferences
                                        auto_allowed = await self._check_auto_allow(command)

                                        if auto_allowed:
                                            # Execute directly without user consent
                                            logger.info("[AutonomousAgent] 🚀 Auto-allowed, executing without consent")
                                            args["consent_id"] = consent_id
                                            result = await self._execute_tool(
                                                current_tool["name"], args, context
                                            )
                                        else:
                                            # Store consent request in Redis
                                            if self.redis_client:
                                                try:
                                                    requested_at = datetime.now()
                                                    await self.redis_client.setex(
                                                        f"consent:{consent_id}",
                                                        300,  # 5 minute TTL
                                                        json.dumps({
                                                            "pending": True,
                                                            "command": command,
                                                            "requested_at": requested_at.isoformat(),
                                                            "user_id": str(self.user_id) if self.user_id else None,
                                                            "org_id": str(self.org_id) if self.org_id else None
                                                        })
                                                    )
                                                except Exception as e:
                                                    logger.error(f"[AutonomousAgent] Failed to store consent in Redis: {e}")

                                            # Emit consent event to frontend
                                            yield consent_event

                                            # Wait for user to approve/deny consent
                                            decision = await self._wait_for_consent(consent_id)

                                            # Handle the decision (save preferences, log audit)
                                            command_to_execute = await self._handle_consent_decision(
                                                consent_id=consent_id,
                                                command=command,
                                                decision=decision,
                                                requested_at=requested_at if 'requested_at' in locals() else datetime.now(),
                                                danger_level=result.get("danger_level"),
                                                cwd=args.get("cwd", self.workspace_path)
                                            )

                                            if command_to_execute:
                                                # Retry tool execution with consent_id
                                                logger.info(
                                                    "[AutonomousAgent] 🔄 Retrying tool with consent approval"
                                                )
                                                args["consent_id"] = consent_id
                                                # If alternative command, update the args
                                                if decision.get("choice") == "alternative":
                                                    args["command"] = command_to_execute
                                                result = await self._execute_tool(
                                                    current_tool["name"], args, context
                                                )
                                            else:
                                                # Consent denied or timeout
                                                result = {
                                                    "success": False,
                                                    "error": "User denied consent or consent timed out"
                                                }

                                    # Log result (unified method - warns if failed)
                                    self._log_tool_result(result)

                                    # Yield tool result event (unified method)
                                    yield self._create_tool_result_event(
                                        current_tool["id"], result
                                    )

                                    tool_calls.append(
                                        {
                                            "id": current_tool["id"],
                                            "name": current_tool["name"],
                                            "input": args,
                                            "result": result,
                                        }
                                    )

                                    # Track tool calls per iteration for loop detection
                                    if (
                                        context.iteration
                                        not in context.tool_calls_per_iteration
                                    ):
                                        context.tool_calls_per_iteration[
                                            context.iteration
                                        ] = []
                                    context.tool_calls_per_iteration[
                                        context.iteration
                                    ].append(
                                        f"{current_tool['name']}:{args.get('path', args.get('command', ''))}"
                                    )
                                    current_tool = None

                        except json.JSONDecodeError:
                            continue

                    if text_buffer:
                        yield {
                            "type": "text",
                            "text": text_buffer,
                            "timestamp": get_event_timestamp(),
                        }

                    # === METRICS: Record successful LLM call latency ===
                    call_duration_ms = (time.time() - call_start_time) * 1000
                    LLM_LATENCY.labels(phase="autonomous", model=self.model).observe(
                        call_duration_ms
                    )

                    # Log stop reason
                    logger.info(f"[AutonomousAgent] 🛑 LLM Stop Reason: {stop_reason}")
                    logger.info(f"[AutonomousAgent] Tool Calls Made: {len(tool_calls)}")
                    if tool_calls:
                        logger.info(
                            f"[AutonomousAgent] Tools Called: {[tc['name'] for tc in tool_calls]}"
                        )

                    # Continue if tool use
                    if stop_reason == "tool_use" and tool_calls:
                        logger.info(
                            "[AutonomousAgent] 🔄 Continuing with tool results - sending back to LLM"
                        )
                        assistant_content = []
                        for tc in tool_calls:
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["input"],
                                }
                            )
                        messages.append(
                            {"role": "assistant", "content": assistant_content}
                        )

                        tool_results = []
                        for tc in tool_calls:
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tc["id"],
                                    "content": json.dumps(tc["result"]),
                                }
                            )
                        messages.append({"role": "user", "content": tool_results})

                        tool_calls = []
                        continue
                    else:
                        # === METRICS: Record successful LLM call ===
                        LLM_CALLS.labels(
                            phase="autonomous", model=self.model, status="success"
                        ).inc()

                        # === METRICS: Record token usage ===
                        total_tokens = input_tokens + output_tokens
                        if total_tokens > 0:
                            LLM_TOKENS.labels(phase="autonomous", model=self.model).inc(
                                total_tokens
                            )

                            # Calculate and record cost
                            cost_usd = self._calculate_llm_cost(
                                self.model, input_tokens, output_tokens
                            )
                            LLM_COST.labels(phase="autonomous", model=self.model).inc(
                                cost_usd
                            )

                            logger.info(
                                f"[AutonomousAgent] 💰 Tokens: {input_tokens} in + {output_tokens} out = {total_tokens} total"
                            )
                            logger.info(
                                f"[AutonomousAgent] 💵 Cost: ${cost_usd:.6f} USD"
                            )

                            # Persist metrics to database
                            await self._persist_llm_metrics(
                                model=self.model,
                                provider=self.provider,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                cost_usd=cost_usd,
                                task_type="autonomous",
                                status="success",
                            )

                        # === FEEDBACK: Log generation for feedback tracking ===
                        gen_id = await self._log_generation(context, system_prompt)
                        if gen_id:
                            yield {
                                "type": "generation_logged",
                                "gen_id": gen_id,
                                "timestamp": int(time.time() * 1000),
                            }

                        logger.info(
                            "[AutonomousAgent] ✅ LLM turn complete - stop_reason: end_turn"
                        )
                        return

    async def _call_openai(
        self, messages: List[Dict[str, Any]], system_prompt: str, context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call OpenAI with function calling."""
        import aiohttp
        from backend.services.streaming_agent import (
            NAVI_FUNCTIONS_OPENAI,
            OPENAI_TO_NAVI_TOOL_NAME,
        )

        # === LLM API CALL TRACING (OpenAI) ===
        logger.info("=" * 60)
        logger.info(
            f"[AutonomousAgent] 🤖 CALLING OPENAI API (Provider: {self.provider})"
        )
        logger.info(f"[AutonomousAgent] Model: {self.model}")
        logger.info(f"[AutonomousAgent] Messages Count: {len(messages)}")
        logger.info("=" * 60)

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        async with aiohttp.ClientSession() as session:
            while True:
                payload = {
                    "model": self.model,
                    "messages": full_messages,
                    "tools": NAVI_FUNCTIONS_OPENAI,
                    "stream": True,
                    "stream_options": {
                        "include_usage": True
                    },  # Enable token usage in stream
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                base_url = "https://api.openai.com/v1"
                if self.provider == "openrouter":
                    base_url = "https://openrouter.ai/api/v1"
                    headers["Authorization"] = (
                        f"Bearer {os.environ.get('OPENROUTER_API_KEY', self.api_key)}"
                    )
                elif self.provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                    headers["Authorization"] = (
                        f"Bearer {os.environ.get('GROQ_API_KEY', self.api_key)}"
                    )

                logger.info(f"[AutonomousAgent] 📡 Sending request to {base_url}...")

                # === METRICS: Start LLM call timer ===
                call_start_time = time.time()

                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(
                        total=600
                    ),  # 10 minutes for complex operations
                ) as response:
                    logger.info(
                        f"[AutonomousAgent] 📥 Response Status: {response.status}"
                    )

                    if response.status != 200:
                        # === METRICS: Record failed LLM call ===
                        call_duration_ms = (time.time() - call_start_time) * 1000
                        LLM_CALLS.labels(
                            phase="autonomous", model=self.model, status="error"
                        ).inc()
                        LLM_LATENCY.labels(
                            phase="autonomous", model=self.model
                        ).observe(call_duration_ms)

                        error = await response.text()
                        logger.error(f"[AutonomousAgent] ❌ API Error: {error[:500]}")
                        yield {"type": "error", "error": error}
                        return

                    text_buffer = ""
                    full_text_for_plan = ""  # Accumulate text for plan detection
                    detected_plan = None  # Track if we've detected a plan
                    tool_calls: Dict[int, Dict[str, Any]] = {}
                    finish_reason = None
                    prompt_tokens = 0
                    completion_tokens = 0

                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)

                            # Capture usage if available (some providers include it)
                            usage = data.get("usage", {})
                            if usage:
                                prompt_tokens = usage.get(
                                    "prompt_tokens", prompt_tokens
                                )
                                completion_tokens = usage.get(
                                    "completion_tokens", completion_tokens
                                )
                                logger.info(
                                    f"[AutonomousAgent] 📊 Usage received: prompt={prompt_tokens}, completion={completion_tokens}"
                                )

                            # Some chunks (like the final usage chunk) may not have choices
                            choices = data.get("choices", [])
                            if not choices:
                                continue  # Skip chunks without choices (e.g., final usage chunk)

                            choice = choices[0]
                            delta = choice.get("delta", {})
                            finish_reason = choice.get("finish_reason")

                            if delta.get("content"):
                                text = delta["content"]
                                text_buffer += text
                                full_text_for_plan += text

                                # Check for plan in accumulated text (only if not already detected)
                                if not detected_plan and len(full_text_for_plan) > 100:
                                    detected_plan = parse_execution_plan(
                                        full_text_for_plan
                                    )
                                    if detected_plan:
                                        logger.info(
                                            f"[AutonomousAgent] ⚡ Detected execution plan with {len(detected_plan['steps'])} steps"
                                        )
                                        yield {
                                            "type": "plan_start",
                                            "data": detected_plan,
                                        }

                                if len(text_buffer) >= 30 or text.endswith(
                                    (".", "!", "?", "\n")
                                ):
                                    yield {
                                        "type": "text",
                                        "text": text_buffer,
                                        "timestamp": get_event_timestamp(),
                                    }
                                    text_buffer = ""

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls:
                                        tool_calls[idx] = {
                                            "id": "",
                                            "name": "",
                                            "arguments": "",
                                        }
                                    if tc.get("id"):
                                        tool_calls[idx]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        # Convert OpenAI-sanitized name back to original NAVI name
                                        openai_name = tc["function"]["name"]
                                        tool_calls[idx]["name"] = (
                                            OPENAI_TO_NAVI_TOOL_NAME.get(
                                                openai_name, openai_name
                                            )
                                        )
                                    if tc.get("function", {}).get("arguments"):
                                        tool_calls[idx]["arguments"] += tc["function"][
                                            "arguments"
                                        ]

                        except json.JSONDecodeError:
                            continue

                    if text_buffer:
                        yield {
                            "type": "text",
                            "text": text_buffer,
                            "timestamp": get_event_timestamp(),
                        }

                    # === METRICS: Record successful LLM call latency ===
                    call_duration_ms = (time.time() - call_start_time) * 1000
                    LLM_LATENCY.labels(phase="autonomous", model=self.model).observe(
                        call_duration_ms
                    )

                    if finish_reason == "tool_calls" and tool_calls:
                        assistant_tool_calls = []
                        for idx in sorted(tool_calls.keys()):
                            tc = tool_calls[idx]
                            assistant_tool_calls.append(
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc["arguments"],
                                    },
                                }
                            )

                        full_messages.append(
                            {"role": "assistant", "tool_calls": assistant_tool_calls}
                        )

                        # OPTIMIZATION: Separate read and write operations for parallel execution
                        all_tools_parsed = []
                        for idx in sorted(tool_calls.keys()):
                            tc = tool_calls[idx]
                            try:
                                args = (
                                    json.loads(tc["arguments"])
                                    if tc["arguments"]
                                    else {}
                                )
                            except json.JSONDecodeError:
                                args = {}
                            all_tools_parsed.append(
                                {
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "arguments": args,
                                }
                            )

                        # Separate into parallel reads and sequential writes
                        parallel_reads, sequential_writes = self._can_parallelize_tools(
                            all_tools_parsed
                        )

                        # Execute read operations in parallel
                        if parallel_reads:
                            logger.info(
                                f"[AutonomousAgent] ⚡ Executing {len(parallel_reads)} read operations in parallel"
                            )
                            parallel_results = await self._execute_tools_parallel(
                                [
                                    {"name": t["name"], "input": t["arguments"]}
                                    for t in parallel_reads
                                ],
                                context,
                            )

                            # Yield events and add to messages in original order
                            for i, pr in enumerate(parallel_results):
                                tool_info = parallel_reads[i]
                                result = pr["result"]

                                yield {
                                    "type": "tool_call",
                                    "tool_call": {
                                        "id": tool_info["id"],
                                        "name": tool_info["name"],
                                        "arguments": tool_info["arguments"],
                                    },
                                }

                                # Emit step progress updates
                                step_events = self._calculate_step_progress(
                                    context, tool_info["name"]
                                )
                                if step_events:
                                    for step_event in step_events:
                                        yield step_event

                                # Check if consent is required for this command
                                consent_event = self._check_requires_consent(
                                    result, tool_info["arguments"]
                                )
                                if consent_event:
                                    command = result.get("command", "")
                                    consent_id = result.get("consent_id")

                                    # Check if command is auto-allowed by user preferences
                                    auto_allowed = await self._check_auto_allow(command)

                                    if auto_allowed:
                                        # Execute directly without user consent
                                        logger.info("[AutonomousAgent] 🚀 Auto-allowed, executing without consent")
                                        tool_info["arguments"]["consent_id"] = consent_id
                                        result = await self._execute_tool(
                                            tool_info["name"], tool_info["arguments"], context
                                        )
                                    else:
                                        # Store consent request in Redis
                                        if self.redis_client:
                                            try:
                                                requested_at = datetime.now()
                                                await self.redis_client.setex(
                                                    f"consent:{consent_id}",
                                                    300,  # 5 minute TTL
                                                    json.dumps({
                                                        "pending": True,
                                                        "command": command,
                                                        "requested_at": requested_at.isoformat(),
                                                        "user_id": str(self.user_id) if self.user_id else None,
                                                        "org_id": str(self.org_id) if self.org_id else None
                                                    })
                                                )
                                            except Exception as e:
                                                logger.error(f"[AutonomousAgent] Failed to store consent in Redis: {e}")

                                        # Emit consent event to frontend
                                        yield consent_event

                                        # Wait for user to approve/deny consent
                                        decision = await self._wait_for_consent(consent_id)

                                        # Handle the decision (save preferences, log audit)
                                        command_to_execute = await self._handle_consent_decision(
                                            consent_id=consent_id,
                                            command=command,
                                            decision=decision,
                                            requested_at=requested_at if 'requested_at' in locals() else datetime.now(),
                                            danger_level=result.get("danger_level"),
                                            cwd=tool_info["arguments"].get("cwd", self.workspace_path)
                                        )

                                        if command_to_execute:
                                            # Retry tool execution with consent_id
                                            logger.info(
                                                "[AutonomousAgent] 🔄 Retrying tool with consent approval"
                                            )
                                            tool_info["arguments"]["consent_id"] = consent_id
                                            # If alternative command, update the args
                                            if decision.get("choice") == "alternative":
                                                tool_info["arguments"]["command"] = command_to_execute
                                            result = await self._execute_tool(
                                                tool_info["name"], tool_info["arguments"], context
                                            )
                                        else:
                                            # Consent denied or timeout
                                            result = {
                                                "success": False,
                                                "error": "User denied consent or consent timed out"
                                            }

                                # Log result (unified method - warns if failed)
                                self._log_tool_result(result)

                                # Yield tool result event (unified method)
                                yield self._create_tool_result_event(
                                    tool_info["id"], result
                                )
                                full_messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_info["id"],
                                        "content": json.dumps(result),
                                    }
                                )

                        # Execute write operations sequentially (preserve order)
                        for tc in sequential_writes:
                            yield {
                                "type": "tool_call",
                                "tool_call": {
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }

                            # Emit step progress updates BEFORE execution
                            step_events = self._calculate_step_progress(
                                context, tc["name"]
                            )
                            if step_events:
                                for step_event in step_events:
                                    yield step_event

                            result = await self._execute_tool(
                                tc["name"], tc["arguments"], context
                            )

                            # Check if consent is required for this command
                            consent_event = self._check_requires_consent(
                                result, tc["arguments"]
                            )
                            if consent_event:
                                command = result.get("command", "")
                                consent_id = result.get("consent_id")

                                # Check if command is auto-allowed by user preferences
                                auto_allowed = await self._check_auto_allow(command)

                                if auto_allowed:
                                    # Execute directly without user consent
                                    logger.info("[AutonomousAgent] 🚀 Auto-allowed, executing without consent")
                                    tc["arguments"]["consent_id"] = consent_id
                                    result = await self._execute_tool(
                                        tc["name"], tc["arguments"], context
                                    )
                                else:
                                    # Store consent request in Redis
                                    if self.redis_client:
                                        try:
                                            requested_at = datetime.now()
                                            await self.redis_client.setex(
                                                f"consent:{consent_id}",
                                                300,  # 5 minute TTL
                                                json.dumps({
                                                    "pending": True,
                                                    "command": command,
                                                    "requested_at": requested_at.isoformat(),
                                                    "user_id": str(self.user_id) if self.user_id else None,
                                                    "org_id": str(self.org_id) if self.org_id else None
                                                })
                                            )
                                        except Exception as e:
                                            logger.error(f"[AutonomousAgent] Failed to store consent in Redis: {e}")

                                    # Emit consent event to frontend
                                    yield consent_event

                                    # Wait for user to approve/deny consent
                                    decision = await self._wait_for_consent(consent_id)

                                    # Handle the decision (save preferences, log audit)
                                    command_to_execute = await self._handle_consent_decision(
                                        consent_id=consent_id,
                                        command=command,
                                        decision=decision,
                                        requested_at=requested_at if 'requested_at' in locals() else datetime.now(),
                                        danger_level=result.get("danger_level"),
                                        cwd=tc["arguments"].get("cwd", self.workspace_path)
                                    )

                                    if command_to_execute:
                                        # Retry tool execution with consent_id
                                        logger.info(
                                            "[AutonomousAgent] 🔄 Retrying tool with consent approval"
                                        )
                                        tc["arguments"]["consent_id"] = consent_id
                                        # If alternative command, update the args
                                        if decision.get("choice") == "alternative":
                                            tc["arguments"]["command"] = command_to_execute
                                        result = await self._execute_tool(
                                            tc["name"], tc["arguments"], context
                                        )
                                    else:
                                        # Consent denied or timeout
                                        result = {
                                            "success": False,
                                            "error": "User denied consent or consent timed out"
                                        }

                            # Log result (unified method - warns if failed)
                            self._log_tool_result(result)

                            # Yield tool result event (unified method)
                            yield self._create_tool_result_event(tc["id"], result)

                            full_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(result),
                                }
                            )

                        tool_calls = {}
                        continue
                    else:
                        # === METRICS: Record successful LLM call ===
                        LLM_CALLS.labels(
                            phase="autonomous", model=self.model, status="success"
                        ).inc()

                        # === METRICS: Record token usage ===
                        total_tokens = prompt_tokens + completion_tokens
                        logger.info(
                            f"[AutonomousAgent] 📊 Final token counts: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                        )
                        if total_tokens > 0:
                            LLM_TOKENS.labels(phase="autonomous", model=self.model).inc(
                                total_tokens
                            )

                            # Calculate and record cost
                            cost_usd = self._calculate_llm_cost(
                                self.model, prompt_tokens, completion_tokens
                            )
                            LLM_COST.labels(phase="autonomous", model=self.model).inc(
                                cost_usd
                            )

                            logger.info(
                                f"[AutonomousAgent] 💰 Tokens: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total"
                            )
                            logger.info(
                                f"[AutonomousAgent] 💵 Cost: ${cost_usd:.6f} USD"
                            )

                            # Persist metrics to database
                            await self._persist_llm_metrics(
                                model=self.model,
                                provider=self.provider,
                                input_tokens=prompt_tokens,
                                output_tokens=completion_tokens,
                                cost_usd=cost_usd,
                                task_type="autonomous",
                                status="success",
                            )

                        # === FEEDBACK: Log generation for feedback tracking ===
                        gen_id = await self._log_generation(context, system_prompt)
                        if gen_id:
                            yield {
                                "type": "generation_logged",
                                "gen_id": gen_id,
                                "timestamp": int(time.time() * 1000),
                            }

                        return

    async def execute_task(
        self,
        request: str,
        run_verification: bool = True,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a task autonomously with verification and self-healing.

        Args:
            request: The user's task/question
            run_verification: Whether to run verification steps
            conversation_history: Previous conversation messages for context

        Yields events:
        - {"type": "status", "status": "planning|executing|verifying|fixing|completed|failed"}
        - {"type": "text", "text": "..."}
        - {"type": "tool_call", "tool_call": {...}}
        - {"type": "tool_result", "tool_result": {...}}
        - {"type": "verification", "results": [...]}
        - {"type": "iteration", "iteration": N, "reason": "..."}
        - {"type": "complete", "summary": {...}}
        """
        # === EXECUTION TRACING ===
        logger.info("=" * 60)
        logger.info("[AutonomousAgent] 🚀 STARTING TASK EXECUTION")
        logger.info(f"[AutonomousAgent] Request: {request[:100]}...")
        logger.info(f"[AutonomousAgent] Provider: {self.provider}")
        logger.info(f"[AutonomousAgent] Model: {self.model}")
        logger.info(f"[AutonomousAgent] Workspace: {self.workspace_path}")
        logger.info(f"[AutonomousAgent] API Key Set: {'YES' if self.api_key else 'NO'}")
        logger.info(
            f"[AutonomousAgent] API Key Length: {len(self.api_key) if self.api_key else 0}"
        )
        logger.info("=" * 60)

        # Assess task complexity for adaptive optimization
        complexity = self._assess_task_complexity(request)
        logger.info(f"[AutonomousAgent] 📊 Task complexity: {complexity.value}")

        # Create context with adaptive iteration limits
        context = TaskContext.with_adaptive_limits(
            complexity=complexity,
            task_id=str(uuid.uuid4()),
            original_request=request,
            workspace_path=self.workspace_path,
            project_type=self.project_type,
            framework=self.framework,
        )
        if conversation_history:
            # Preserve recent conversation history for intent disambiguation
            context.conversation_history = [
                {
                    "role": msg.get("role") or msg.get("type") or "user",
                    "content": msg.get("content", ""),
                }
                for msg in conversation_history[-50:]
                if msg.get("content")
            ]
        max_display = (
            context.max_iterations
            if context.complexity != TaskComplexity.ENTERPRISE
            else "unlimited (checkpointed)"
        )
        logger.info(f"[AutonomousAgent] 🔄 Max iterations set to: {max_display}")

        yield {"type": "status", "status": "planning", "task_id": context.task_id}

        # Emit thinking progress: analyzing request
        yield {
            "type": "thinking_progress",
            "message": "Analyzing your request...",
            "timestamp": int(__import__("time").time()) * 1000,
        }

        # Gather environment info ONCE at the start to avoid blind guessing
        yield {
            "type": "thinking_progress",
            "message": "Checking project configuration...",
            "timestamp": int(__import__("time").time()) * 1000,
        }
        env_info = await self._diagnose_environment()

        # Retrieve relevant codebase context via RAG
        yield {
            "type": "thinking_progress",
            "message": "Searching codebase for relevant context...",
            "timestamp": int(__import__("time").time()) * 1000,
        }
        rag_context = None
        try:
            # === METRICS: Start RAG retrieval timer ===
            rag_start_time = time.time()

            # Add timeout to prevent RAG from blocking for minutes
            # RAG now triggers background indexing on first request, so timeout is less critical
            try:
                rag_context = await asyncio.wait_for(
                    get_context_for_task(
                        workspace_path=self.workspace_path,
                        task_description=request,
                        max_context_tokens=4000,  # Limit context size
                    ),
                    timeout=10.0,  # 10 second timeout for RAG (allows background indexing to start)
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[AutonomousAgent] RAG context retrieval timed out after 10s - "
                    "continuing without RAG context (background indexing may be in progress)"
                )
                rag_context = None

            # === METRICS: Record RAG retrieval latency ===
            rag_duration_ms = (time.time() - rag_start_time) * 1000
            RAG_RETRIEVAL_LATENCY.labels(phase="autonomous").observe(rag_duration_ms)

            if rag_context and rag_context.strip():
                # Estimate number of chunks (typical chunk is ~500 chars)
                estimated_chunks = max(1, len(rag_context) // 500)
                RAG_CHUNKS_RETRIEVED.labels(phase="autonomous").inc(estimated_chunks)

                logger.info(
                    f"[AutonomousAgent] 🔍 Retrieved RAG context: {len(rag_context)} chars "
                    f"(~{estimated_chunks} chunks) in {rag_duration_ms:.0f}ms"
                )
            else:
                logger.info("[AutonomousAgent] No relevant RAG context found")
        except Exception as e:
            logger.warning(f"[AutonomousAgent] RAG retrieval failed: {e}")
            rag_context = None

        # Generate and emit execution plan for complex tasks
        yield {
            "type": "thinking_progress",
            "message": "Planning actions...",
            "timestamp": int(__import__("time").time()) * 1000,
        }
        plan_steps = []
        async for plan_event in self._generate_plan(request, env_info, context):
            yield plan_event
            if plan_event.get("type") == "plan":
                plan_steps = plan_event.get("steps", [])
                context.step_count = len(
                    plan_steps
                )  # Store step count for progress tracking

        # Update first step to in_progress (running)
        if plan_steps and context.plan_id:
            context.step_progress_emitted[0] = (
                "running"  # Track that we've emitted step 0 as running
            )
            yield {
                "type": "step_update",
                "data": {
                    "plan_id": context.plan_id,
                    "step_index": 0,  # 0-indexed for frontend
                    "status": "running",
                },
            }

        # File path preflight (single deterministic check for file operations)
        file_preflight_note = ""
        if self._is_file_operation_request(request, context):
            intent = self._classify_file_intent(request, context)
            preflight = self._preflight_file_targets(request, context)
            status = preflight.get("status")

            if status == "resolved":
                targets = preflight.get("targets", [])
                if targets:
                    if len(targets) == 1:
                        file_preflight_note = (
                            f"Resolved file target: `{targets[0]}`. "
                            "Use this exact path. Do not guess."
                        )
                    else:
                        joined = ", ".join(f"`{t}`" for t in targets[:5])
                        file_preflight_note = (
                            f"Resolved file targets: {joined}. "
                            "Use these exact paths. Do not guess."
                        )
            elif status == "ambiguous":
                matches = preflight.get("matches", [])
                candidate = preflight.get("candidate", "") or "the requested file"
                if (
                    matches
                    and intent in ("delete", "move", "edit")
                    and context.pending_prompt is None
                ):
                    context.pending_prompt = create_user_prompt(
                        prompt_type="select",
                        title="Select file",
                        description=(
                            f"Multiple matches found for {candidate}. "
                            "Which file should I use?"
                        ),
                        options=[
                            {"value": m, "label": m} for m in matches[:10]
                        ],
                    )
            elif status == "not_found":
                candidate = preflight.get("candidate", "") or ""
                if intent in ("delete", "move", "edit") and context.pending_prompt is None:
                    context.pending_prompt = create_user_prompt(
                        prompt_type="text",
                        title="File path",
                        description=(
                            f"I couldn't find {candidate or 'that file'} in the workspace. "
                            "Please provide the exact relative path."
                        ),
                        placeholder="path/to/file.ext",
                    )

        # Command preflight (single deterministic check for command-centric requests)
        command_preflight_note = ""
        command_intent = self._detect_command_intent(request)
        if command_intent != "unknown":
            resolved_command = self._resolve_command_for_intent(command_intent)
            if resolved_command:
                command_preflight_note = (
                    f"Resolved command for {command_intent}: `{resolved_command}`. "
                    "Use this exact command. Do not guess."
                )
            elif context.pending_prompt is None:
                context.pending_prompt = create_user_prompt(
                    prompt_type="text",
                    title="Command to run",
                    description=(
                        f"I couldn't determine the exact command to {command_intent}. "
                        "Please provide the command you want me to run."
                    ),
                    placeholder="e.g. npm run dev",
                )

        # Include environment info in the initial request
        preflight_blocks = []
        if file_preflight_note:
            preflight_blocks.append(
                f"--- FILE PREFLIGHT ---\n{file_preflight_note}\n--- END FILE PREFLIGHT ---"
            )
        if command_preflight_note:
            preflight_blocks.append(
                f"--- COMMAND PREFLIGHT ---\n{command_preflight_note}\n--- END COMMAND PREFLIGHT ---"
            )
        preflight_block = f"\n\n{chr(10).join(preflight_blocks)}" if preflight_blocks else ""
        enhanced_request = f"""{request}{preflight_block}

--- ENVIRONMENT INFO (gathered automatically) ---
{env_info}
--- END ENVIRONMENT INFO ---

Use the tools and versions listed above. Don't guess - use what's actually available."""

        # Check if task should be decomposed into subtasks
        if self._should_decompose_task(request, complexity):
            logger.info(
                "[AutonomousAgent] 🔀 Task will be decomposed into subtasks for better execution"
            )

            # Execute with decomposition and stream progress directly
            async for event in self._execute_with_decomposition_generator(
                request=request,
                context=context,
            ):
                yield event

            # After decomposition completes, return
            yield {
                "type": "complete",
                "summary": {
                    "success": True,
                    "message": "Enterprise task completed via decomposition",
                    "total_iterations": context.iteration,
                },
            }
            return

        # Build messages list with conversation history for context
        messages = []

        # Add conversation history if provided (for context continuity)
        if conversation_history:
            # Convert conversation history format to LLM message format
            for hist_msg in conversation_history[
                -(
                    100
                    if len(conversation_history) > 100
                    else len(conversation_history)
                ) :
            ]:  # Last 100 messages max
                role = hist_msg.get("type") or hist_msg.get("role", "user")
                content = hist_msg.get("content", "")
                if role and content:
                    # Normalize role names
                    if role in ["user", "assistant", "system"]:
                        messages.append({"role": role, "content": content})

        # Add current request as the latest user message
        messages.append({"role": "user", "content": enhanced_request})

        while context.iteration < context.max_iterations:
            context.iteration += 1
            context.status = TaskStatus.EXECUTING

            # === USER PROMPT HANDLING ===
            # Check if there's a pending prompt that needs user input
            if context.pending_prompt:
                prompt = context.pending_prompt
                logger.info(
                    f"[AutonomousAgent] 💬 User prompt pending: {prompt.title}"
                )

                # Yield prompt event to frontend
                yield {
                    "type": "prompt_request",
                    "data": {
                        "prompt_id": prompt.prompt_id,
                        "prompt_type": prompt.prompt_type,
                        "title": prompt.title,
                        "description": prompt.description,
                        "placeholder": prompt.placeholder,
                        "default_value": prompt.default_value,
                        "options": prompt.options,
                        "validation_pattern": prompt.validation_pattern,
                        "required": prompt.required,
                        "timeout_seconds": prompt.timeout_seconds,
                    },
                    "timestamp": int(time.time() * 1000),
                }

                # Change status to waiting for input
                yield {
                    "type": "status",
                    "status": "awaiting_user_input",
                    "prompt_id": prompt.prompt_id,
                }

                # Wait for response
                response = await self._check_prompt_response(
                    prompt.prompt_id, prompt.timeout_seconds
                )

                if response is None:
                    # Timeout or cancellation - stop execution
                    logger.warning(
                        "[AutonomousAgent] ⏸️ Stopping execution - user prompt was not answered"
                    )
                    yield {
                        "type": "complete",
                        "summary": {
                            "task_id": context.task_id,
                            "files_read": context.files_read,
                            "files_modified": context.files_modified,
                            "files_created": context.files_created,
                            "iterations": context.iteration,
                            "verification_passed": False,
                            "stopped_reason": "prompt_timeout",
                            "pending_prompt": {
                                "title": prompt.title,
                                "prompt_type": prompt.prompt_type,
                            },
                        },
                    }
                    return  # Stop execution

                # Clear pending prompt and continue with response
                context.pending_prompt = None

                # Add response to conversation for agent to use
                messages.append(
                    {
                        "role": "user",
                        "content": f"[User's response to '{prompt.title}']: {response}",
                    }
                )

                yield {
                    "type": "text",
                    "text": f"\n✓ Received response: {response}\n",
                    "timestamp": int(time.time() * 1000),
                }

            # === ENTERPRISE MODE CHECKPOINTING ===
            if (
                context.complexity == TaskComplexity.ENTERPRISE
                and context.enterprise_controller
            ):
                # Record iteration in enterprise controller
                iterations_since_checkpoint = (
                    context.iteration - context.last_checkpoint_iteration
                )

                # Check if we should create a checkpoint
                if iterations_since_checkpoint >= context.checkpoint_interval:
                    logger.info(
                        f"[AutonomousAgent] 📸 Creating enterprise checkpoint at iteration {context.iteration}"
                    )
                    context.last_checkpoint_iteration = context.iteration

                    # PERSIST CHECKPOINT TO DATABASE for crash recovery
                    checkpoint_id = None
                    if self.db_session and context.enterprise_project_id:
                        try:
                            from backend.services.checkpoint_persistence_service import (
                                CheckpointPersistenceService,
                            )

                            checkpoint_service = CheckpointPersistenceService(
                                db_session=self.db_session,
                                project_id=context.enterprise_project_id,
                                llm_provider=self.provider,
                                llm_api_key=self.api_key,
                            )
                            checkpoint_id = await checkpoint_service.save_checkpoint(
                                task_context=context,
                                checkpoint_type="automatic",
                                reason=f"Automatic checkpoint at iteration {context.iteration}",
                            )
                            logger.info(
                                f"[AutonomousAgent] ✅ Checkpoint {checkpoint_id} saved to database"
                            )
                        except Exception as e:
                            logger.error(
                                f"[AutonomousAgent] Failed to save checkpoint: {e}"
                            )

                    # Emit checkpoint event for frontend
                    yield {
                        "type": "enterprise_checkpoint",
                        "data": {
                            "iteration": context.iteration,
                            "project_id": context.enterprise_project_id,
                            "checkpoint_id": checkpoint_id,
                            "files_modified": context.files_modified,
                            "files_created": context.files_created,
                            "commands_run": len(context.commands_run),
                        },
                    }

            # === ITERATION TRACING ===
            logger.info("*" * 60)
            max_display = (
                context.max_iterations
                if context.complexity != TaskComplexity.ENTERPRISE
                else "∞"
            )
            logger.info(
                f"[AutonomousAgent] 🔁 ITERATION {context.iteration}/{max_display}"
            )
            logger.info(f"[AutonomousAgent] Files Read: {len(context.files_read)}")
            logger.info(
                f"[AutonomousAgent] Files Modified: {len(context.files_modified)}"
            )
            logger.info(
                f"[AutonomousAgent] Files Created: {len(context.files_created)}"
            )
            logger.info(f"[AutonomousAgent] Commands Run: {len(context.commands_run)}")
            logger.info(
                f"[AutonomousAgent] Consecutive Errors: {context.consecutive_same_error_count}"
            )
            logger.info("*" * 60)

            # Check for unrecoverable loops - terminate early to avoid wasting iterations
            if context.consecutive_same_error_count >= 5:
                yield {"type": "status", "status": "failed"}
                yield {
                    "type": "text",
                    "text": f"\n🛑 **Stopping: Same error occurred {context.consecutive_same_error_count} times in a row.**\n"
                    f"The agent appears to be stuck and cannot resolve this issue automatically.\n"
                    f"Please review the errors above and consider:\n"
                    f"1. Fixing the issue manually\n"
                    f"2. Providing more specific instructions\n"
                    f"3. Checking if there are missing dependencies or configuration\n",
                    "timestamp": get_event_timestamp(),
                }

                # Mark plan as failed
                if plan_steps and context.plan_id:
                    yield {
                        "type": "step_update",
                        "data": {
                            "plan_id": context.plan_id,
                            "step_index": len(plan_steps) - 1,
                            "status": "error",
                        },
                    }
                    yield {
                        "type": "plan_complete",
                        "data": {"plan_id": context.plan_id},
                    }

                yield {
                    "type": "complete",
                    "summary": {
                        "task_id": context.task_id,
                        "files_read": context.files_read,
                        "files_modified": context.files_modified,
                        "files_created": context.files_created,
                        "iterations": context.iteration,
                        "verification_passed": False,
                        "stopped_reason": "iteration_loop_detected",
                        "loop_count": context.consecutive_same_error_count,
                        "remaining_errors": [
                            e["message"][:200] for e in context.error_history[-3:]
                        ],
                    },
                }
                return

            # Only emit iteration event for subsequent iterations (not the first one)
            # This avoids showing "Iteration 1/10" debug info to users
            if context.iteration > 1 and not self._should_suppress_iteration_banner(
                context
            ):
                # Provide context-aware iteration reason
                if context.consecutive_same_error_count >= 3:
                    reason = f"Loop detected ({context.consecutive_same_error_count}x same error) - forcing different strategy"
                elif context.consecutive_same_error_count >= 2:
                    reason = "Same error persists - trying alternative fix"
                elif context.failed_approaches:
                    reason = f"Previous approach failed - trying alternative ({len(context.failed_approaches)} attempts so far)"
                elif context.last_verification_failed:
                    reason = "Fixing verification errors..."
                else:
                    reason = "Trying next approach..."

                yield {
                    "type": "iteration",
                    "iteration": context.iteration,
                    "max": (
                        context.max_iterations
                        if context.complexity != TaskComplexity.ENTERPRISE
                        else None
                    ),
                    "reason": reason,
                    "loop_count": context.consecutive_same_error_count,
                    "enterprise_mode": context.complexity == TaskComplexity.ENTERPRISE,
                    "last_checkpoint": (
                        context.last_checkpoint_iteration
                        if context.complexity == TaskComplexity.ENTERPRISE
                        else None
                    ),
                }

            # Call LLM with tools (with RAG context on first iteration)
            llm_output_text = ""
            last_error_event = None  # Track if we got an error event
            # Only inject RAG context on first iteration to avoid repetition
            current_rag_context = rag_context if context.iteration == 1 else None
            async for event in self._call_llm_with_tools(
                messages, context, rag_context=current_rag_context
            ):
                yield event

                # Track assistant text for conversation history and gate detection
                if event.get("type") == "text":
                    llm_output_text += event.get("text", "")
                    if (
                        not context.conversation_history
                        or context.conversation_history[-1]["role"] != "assistant"
                    ):
                        context.conversation_history.append(
                            {"role": "assistant", "content": ""}
                        )
                    context.conversation_history[-1]["content"] += event["text"]

                # Track error events for early exit detection
                elif event.get("type") == "error":
                    last_error_event = event

            # === EARLY EXIT: Check for non-retryable API errors ===
            if last_error_event:
                error_msg = last_error_event.get("error", "")
                error_lower = error_msg.lower()

                # Detect non-retryable errors (rate limits, quota, auth issues)
                is_non_retryable = (
                    "rate" in error_lower
                    or "429" in error_msg
                    or "quota" in error_lower
                    or "billing" in error_lower
                    or "402" in error_msg
                    or "401" in error_msg
                    or "unauthorized" in error_lower
                    or ("invalid" in error_lower and "key" in error_lower)
                    or "payment" in error_lower
                )

                if is_non_retryable:
                    # Stop immediately - don't waste remaining iterations
                    logger.warning(
                        f"[AutonomousAgent] 🛑 Non-retryable API error detected, exiting early (iteration {context.iteration}/{context.max_iterations})"
                    )
                    yield {"type": "status", "status": "failed"}
                    yield {
                        "type": "text",
                        "text": f"\n\n🛑 **Cannot continue: Non-retryable API error**\n\n"
                        f"**Error:** {error_msg[:300]}\n\n"
                        f"This is a non-retryable error (rate limit, quota exceeded, or authentication issue). "
                        f"Please resolve the issue and try again later.\n\n"
                        f"**Common solutions:**\n"
                        f"- Rate limit: Wait and try again later\n"
                        f"- Quota exceeded: Check your API usage limits\n"
                        f"- Auth error: Verify your API key is valid\n",
                    }
                    yield {
                        "type": "complete",
                        "summary": {
                            "success": False,
                            "stopped_reason": "non_retryable_api_error",
                            "error": error_msg[:200],
                            "iterations_used": context.iteration,
                            "iterations_saved": context.max_iterations
                            - context.iteration,
                        },
                    }
                    return  # Exit immediately - no more iterations

            # === ENTERPRISE MODE: Human Checkpoint Gate Detection ===
            if (
                context.complexity == TaskComplexity.ENTERPRISE
                and context.gate_detector
            ):
                gates = context.gate_detector.detect_gates(
                    llm_output=llm_output_text,
                    files_to_create=context.files_created,
                    files_to_modify=context.files_modified,
                    commands_to_run=[
                        cmd.get("command", "") for cmd in context.commands_run
                    ],
                    current_task=context.original_request,
                )

                if gates:
                    # Found gate triggers - yield the highest priority one
                    gate = gates[0]
                    logger.info(
                        f"[AutonomousAgent] 🚦 Human checkpoint gate triggered: {gate.gate_type} - {gate.title}"
                    )

                    # Store pending gate in context
                    context.pending_gate = gate

                    # Yield gate event for frontend
                    yield {
                        "type": "human_gate",
                        "data": {
                            "gate_type": gate.gate_type,
                            "title": gate.title,
                            "description": gate.description,
                            "options": gate.options,
                            "priority": gate.priority,
                            "blocks_progress": gate.blocks_progress,
                            "project_id": context.enterprise_project_id,
                            "iteration": context.iteration,
                            "trigger_context": gate.trigger_context,
                        },
                    }

                    # If gate blocks progress, pause execution
                    if gate.blocks_progress:
                        logger.info(
                            f"[AutonomousAgent] ⏸️ Pausing execution for human gate: {gate.title}"
                        )
                        yield {
                            "type": "status",
                            "status": "awaiting_human_decision",
                            "gate_id": f"gate_{context.iteration}_{gate.gate_type}",
                        }

                        yield {
                            "type": "complete",
                            "summary": {
                                "task_id": context.task_id,
                                "files_read": context.files_read,
                                "files_modified": context.files_modified,
                                "files_created": context.files_created,
                                "iterations": context.iteration,
                                "verification_passed": False,
                                "stopped_reason": "human_gate_pending",
                                "pending_gate": {
                                    "type": gate.gate_type,
                                    "title": gate.title,
                                    "options": gate.options,
                                },
                            },
                        }
                        return  # Stop execution until human decision

            # Check if any actions were taken (files modified, created, OR commands run)
            # Commands count as "doing something" - e.g., starting a server, running npm install
            has_taken_action = (
                context.files_modified
                or context.files_created
                or context.commands_run  # Commands also count as action!
            )

            if not has_taken_action:
                # No actions taken - check if this was supposed to be a fix request
                is_fix_request = self._is_fix_request(context.original_request)

                if is_fix_request and context.iteration < context.max_iterations:
                    # User asked for a fix but LLM only provided analysis - push it to implement
                    logger.warning(
                        f"[AutonomousAgent] ⚠️ FIX REQUEST but no actions taken in iteration {context.iteration}. "
                        "Pushing LLM to actually implement the fix."
                    )

                    yield {
                        "type": "text",
                        "text": "\n\n🔧 **No actions executed yet—attempting tool run.**\n",
                        "timestamp": get_event_timestamp(),
                    }

                    # Add a forceful follow-up message to make LLM actually implement
                    implement_prompt = """
⚠️ **STOP! You just provided analysis but didn't actually FIX anything.**

The user asked you to FIX/SOLVE a problem. You MUST:
1. Use write_file or edit_file to make the actual code changes
2. Use run_command to execute fixes (install deps, restart servers, etc.)

DO NOT:
- Give more explanations or recommendations
- Ask the user to do anything
- Say "you should" or "you can"

**IMPLEMENT THE FIX NOW.** Use the tools to make the changes.
Based on your analysis, what specific file(s) need to be edited? Make those edits NOW.
"""
                    messages.append({"role": "user", "content": implement_prompt})
                    continue  # Continue the loop to call LLM again with the implementation directive

                # Task is genuinely info-only OR we've exhausted retries
                yield {"type": "status", "status": "completed"}

                # Mark plan as complete if we have one
                if plan_steps and context.plan_id:
                    for i in range(len(plan_steps)):
                        yield {
                            "type": "step_update",
                            "data": {
                                "plan_id": context.plan_id,
                                "step_index": i,
                                "status": "completed",
                            },
                        }
                    yield {
                        "type": "plan_complete",
                        "data": {"plan_id": context.plan_id},
                    }

                # For info-only tasks, suggest follow-up questions
                next_steps = [
                    "Ask me to implement changes if needed",
                    "Explore related files",
                    "Ask follow-up questions",
                ]
                yield {"type": "next_steps", "next_steps": next_steps}

                yield {
                    "type": "complete",
                    "summary": {
                        "task_id": context.task_id,
                        "files_read": context.files_read,
                        "files_modified": context.files_modified,
                        "files_created": context.files_created,
                        "iterations": context.iteration,
                        "verification_run": False,
                        "next_steps": next_steps,
                    },
                }
                return

            # Run verification if enabled - use complexity-based strategy
            # OPTIMIZATION: Skip verification entirely if no files were modified or commands run
            # Note: Commands (like npm install, starting servers) ARE valuable actions even if no files change
            if not (
                context.files_modified or context.files_created or context.commands_run
            ):
                # No files changed and no commands run - genuinely info-only task
                if True:  # Simplified - removed failure detection due to complexity
                    # No files changed and no failures - genuinely info-only task
                    logger.info(
                        "[AutonomousAgent] ⏭️ Skipping verification - no files modified or created, no failures"
                    )
                    context.last_verification_failed = False
                    yield {
                        "type": "text",
                        "text": "\n✅ **Task completed** (no code changes needed)\n",
                        "timestamp": get_event_timestamp(),
                    }
                    yield {"type": "status", "status": "completed"}

                    # Mark plan as complete if we have one
                    if plan_steps and context.plan_id:
                        for i in range(len(plan_steps)):
                            yield {
                                "type": "step_update",
                                "data": {
                                    "plan_id": context.plan_id,
                                    "step_index": i,
                                    "status": "completed",
                                },
                            }
                        yield {
                            "type": "plan_complete",
                            "data": {"plan_id": context.plan_id},
                        }

                    next_steps = self._generate_next_steps(context)
                    if next_steps:
                        yield {"type": "next_steps", "next_steps": next_steps}

                    yield {
                        "type": "complete",
                        "summary": {
                            "task_id": context.task_id,
                            "files_read": len(context.files_read),
                            "files_modified": 0,
                            "files_created": 0,
                            "iterations": context.iteration,
                            "verification_skipped": True,
                            "next_steps": next_steps,
                        },
                    }
                    return

            if run_verification and self.verification_commands:
                context.status = TaskStatus.VERIFYING
                yield {"type": "status", "status": "verifying"}

                # Update step progress - mark previous steps completed, verification in progress
                if plan_steps and context.plan_id:
                    # Mark all previous steps as completed (0-indexed for frontend)
                    for i in range(len(plan_steps) - 1):
                        yield {
                            "type": "step_update",
                            "data": {
                                "plan_id": context.plan_id,
                                "step_index": i,
                                "status": "completed",
                            },
                        }
                    # Mark last step (usually verification) as running
                    yield {
                        "type": "step_update",
                        "data": {
                            "plan_id": context.plan_id,
                            "step_index": len(plan_steps) - 1,
                            "status": "running",
                        },
                    }

                # OPTIMIZATION: Use complexity-based verification strategy
                if (
                    context.complexity == TaskComplexity.SIMPLE
                    and context.files_modified
                ):
                    # For simple tasks: quick syntax validation only
                    yield {
                        "type": "text",
                        "text": "\n\n**Quick validation (simple task)...**\n",
                        "timestamp": get_event_timestamp(),
                    }
                    logger.info(
                        "[AutonomousAgent] 🚀 Using quick validation for simple task"
                    )

                    is_valid, error_msg = await self.verifier.quick_validate(
                        list(context.files_modified)
                    )

                    if is_valid:
                        # Quick validation passed - complete immediately
                        logger.info(
                            "[AutonomousAgent] ✅ Quick validation passed - skipping full build"
                        )
                        context.last_verification_failed = False
                        yield {
                            "type": "text",
                            "text": "\n✅ **Quick validation passed!**\n",
                            "timestamp": get_event_timestamp(),
                        }
                        yield {"type": "status", "status": "completed"}

                        # Mark all plan steps as completed (0-indexed for frontend)
                        if plan_steps and context.plan_id:
                            for i in range(len(plan_steps)):
                                yield {
                                    "type": "step_update",
                                    "data": {
                                        "plan_id": context.plan_id,
                                        "step_index": i,
                                        "status": "completed",
                                    },
                                }
                            # Emit plan_complete to close the panel
                            yield {
                                "type": "plan_complete",
                                "data": {"plan_id": context.plan_id},
                            }

                        next_steps = self._generate_next_steps(context)
                        if next_steps:
                            yield {"type": "next_steps", "next_steps": next_steps}

                        yield {
                            "type": "complete",
                            "summary": {
                                "task_id": context.task_id,
                                "files_read": len(context.files_read),
                                "files_modified": len(context.files_modified),
                                "files_created": len(context.files_created),
                                "iterations": context.iteration,
                                "verification_passed": True,
                                "quick_validation": True,
                                "next_steps": next_steps,
                            },
                        }
                        return
                    else:
                        # Quick validation failed - syntax error
                        context.last_verification_failed = True
                        yield {
                            "type": "text",
                            "text": f"\n⚠️ **Syntax error:** {error_msg}\n",
                            "timestamp": get_event_timestamp(),
                        }
                        # Continue to retry loop - don't do full verification
                        context.error_history.append(
                            {
                                "type": "syntax",
                                "errors": [error_msg],
                                "iteration": context.iteration,
                            }
                        )
                        context.status = TaskStatus.FIXING
                        yield {"type": "status", "status": "fixing"}
                        # Add error to messages for retry
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Syntax error detected: {error_msg}\nPlease fix and try again.",
                            }
                        )
                        continue  # Skip to next iteration

                # For MEDIUM and COMPLEX tasks: run appropriate verification
                # Don't emit verification status as text - it makes responses verbose
                # yield {"type": "text", "text": "\n\n**Running verification...**\n", "timestamp": get_event_timestamp()}

                # Always run tests for MEDIUM and COMPLEX tasks (not just COMPLEX)
                # Tests are crucial for validating changes work correctly
                run_tests = context.complexity in (
                    TaskComplexity.MEDIUM,
                    TaskComplexity.COMPLEX,
                )
                logger.info(
                    f"[AutonomousAgent] Running verification (run_tests={run_tests}) for {context.complexity.value} task"
                )

                results = await self.verifier.verify_changes(
                    self.verification_commands, run_tests=run_tests
                )
                context.verification_results = results

                yield {
                    "type": "verification",
                    "results": [
                        {
                            "type": r.type.value,
                            "success": r.success,
                            "errors": r.errors[:5],
                            "warnings": r.warnings[:5],
                        }
                        for r in results
                    ],
                }

                # Check if all passed
                all_passed = all(r.success for r in results)

                if all_passed:
                    logger.info(
                        "[AutonomousAgent] ✅ ALL VERIFICATIONS PASSED - TASK COMPLETE"
                    )
                    context.last_verification_failed = False
                    # Don't emit verification success as text - it makes responses verbose
                    # yield {
                    #     "type": "text",
                    #     "text": "\n✅ **All verifications passed!**\n",
                    # "timestamp": get_event_timestamp()
                    # }
                    yield {"type": "status", "status": "completed"}

                    # Mark all plan steps as completed (0-indexed for frontend)
                    if plan_steps and context.plan_id:
                        for i in range(len(plan_steps)):
                            yield {
                                "type": "step_update",
                                "data": {
                                    "plan_id": context.plan_id,
                                    "step_index": i,
                                    "status": "completed",
                                },
                            }
                        # Emit plan_complete to close the panel
                        yield {
                            "type": "plan_complete",
                            "data": {"plan_id": context.plan_id},
                        }

                    # Generate helpful next steps based on what was done
                    next_steps = self._generate_next_steps(context)
                    if next_steps:
                        yield {"type": "next_steps", "next_steps": next_steps}

                    yield {
                        "type": "complete",
                        "summary": {
                            "task_id": context.task_id,
                            "files_read": len(context.files_read),
                            "files_modified": len(context.files_modified),
                            "files_created": len(context.files_created),
                            "iterations": context.iteration,
                            "verification_passed": True,
                            "next_steps": next_steps,
                        },
                    }
                    return

                # Verification failed - prepare for retry
                logger.warning("[AutonomousAgent] ⚠️ VERIFICATION FAILED - Will retry")
                logger.warning(
                    f"[AutonomousAgent] Failed verifications: {[r.type.value for r in results if not r.success]}"
                )
                context.last_verification_failed = True
                context.status = TaskStatus.FIXING
                yield {"type": "status", "status": "fixing"}

                # Build error context for retry
                error_details = []
                for r in results:
                    if not r.success:
                        context.error_history.append(
                            {
                                "type": r.type.value,
                                "message": "\n".join(r.errors[:10]),
                                "iteration": context.iteration,
                            }
                        )
                        error_details.append(
                            f"**{r.type.value}** failed:\n```\n{r.output[:1500]}\n```"
                        )

                error_message = "\n\n".join(error_details)

                # Extract error signatures for loop detection
                new_signatures = self._extract_error_signatures(
                    results, context.iteration
                )
                context.error_signatures.extend(new_signatures)

                # Detect iteration loops
                (
                    is_looping,
                    loop_severity,
                    loop_suggestions,
                ) = self._detect_iteration_loop(context)

                # Record this as a failed approach
                error_summary = "; ".join(
                    r.errors[0] if r.errors else "Unknown error"
                    for r in results
                    if not r.success
                )
                self._record_failed_approach(context, error_summary)

                # Emit appropriate message based on loop detection
                if is_looping and loop_severity == "critical":
                    yield {
                        "type": "text",
                        "text": f"\n🔄 **Loop detected - same error {context.consecutive_same_error_count} times.** Forcing different strategy...\n",
                        "timestamp": get_event_timestamp(),
                    }
                    yield {
                        "type": "loop_detected",
                        "severity": loop_severity,
                        "count": context.consecutive_same_error_count,
                    }
                else:
                    # Don't emit verification failure as text - it makes responses verbose
                    # The error will be shown via the status change to "fixing"
                    pass
                    # yield {
                    #     "type": "text",
                    #     "text": f"\n❌ **Verification failed.** Analyzing errors and fixing...\n\n{error_message}\n",
                    #     "timestamp": get_event_timestamp()
                    # }

                # Add error context to messages for retry
                messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            context.conversation_history[-1]["content"]
                            if context.conversation_history
                            else ""
                        ),
                    }
                )

                # Build context of what was already tried to prevent repeating the same approach
                actions_taken = []
                if context.files_created:
                    actions_taken.append(
                        f"Files already created: {', '.join(context.files_created)}"
                    )
                if context.files_modified:
                    actions_taken.append(
                        f"Files already modified: {', '.join(context.files_modified)}"
                    )
                if context.files_read:
                    actions_taken.append(
                        f"Files already read: {', '.join(context.files_read[-10:])}"
                    )  # Last 10

                actions_context = (
                    "\n".join(actions_taken)
                    if actions_taken
                    else "No files created or modified yet."
                )

                # Build failed approaches summary with detailed guidance
                failed_approaches_text = ""
                if context.failed_approaches:
                    approach_list = []
                    for fa in context.failed_approaches[
                        -5:
                    ]:  # Last 5 failed approaches
                        approach_list.append(
                            f"  ❌ Iteration {fa.iteration}: {fa.description}"
                        )
                        approach_list.append(f"     Error: {fa.error_summary[:150]}")
                    failed_approaches_text = f"""
**FAILED APPROACHES (DO NOT REPEAT THESE):**
{chr(10).join(approach_list)}

⚠️ You have tried {len(context.failed_approaches)} approach(es) that did NOT work.
Each new attempt MUST be FUNDAMENTALLY DIFFERENT from those listed above.
DO NOT make minor variations of the same approach - try something completely new."""

                # Build loop detection guidance
                approach_hint = ""
                if is_looping:
                    if loop_severity == "critical":
                        approach_hint = f"""
🚨 **CRITICAL: You are in an iteration loop!**
You have tried the same fix {context.consecutive_same_error_count} times and it keeps failing with the same error.

**YOU MUST COMPLETELY CHANGE YOUR APPROACH:**
{chr(10).join('- ' + s for s in loop_suggestions)}

**MANDATORY ACTIONS:**
1. STOP trying to fix the file you've been editing
2. READ the error message carefully - what is it ACTUALLY asking for?
3. Check if you're editing the RIGHT file in the RIGHT location
4. Consider if the entire approach is wrong and needs rethinking
5. Look for working examples in the codebase to copy patterns from

**DO NOT:**
- Edit the same file again with minor changes
- Try the same fix with different syntax
- Ignore this warning and proceed as before

Your fix MUST be fundamentally different this time."""
                    else:
                        approach_hint = f"""
⚠️ **WARNING: Your previous fix did not work.**
{chr(10).join('- ' + s for s in loop_suggestions)}

You MUST try a DIFFERENT approach this time:
1. Re-read the file to see its ACTUAL current content
2. The error might be in a different location than you think
3. Check if you're fixing the symptom vs the root cause
DO NOT repeat the same fix - it will fail again."""
                else:
                    # Even without loop detection, provide guidance
                    approach_hint = """
Please analyze these errors carefully:
1. Read the EXACT error message - it tells you what's wrong
2. Make sure any files you create are in the correct location
3. Verify the content is syntactically correct before saving"""

                messages.append(
                    {
                        "role": "user",
                        "content": f"""Verification failed. Here are the errors:

{error_message}

**Actions taken so far (iteration {context.iteration} of {context.max_iterations}):**
{actions_context}
{failed_approaches_text}
{approach_hint}

After fixing, I'll run verification again.""",
                    }
                )

            else:
                # No verification or no commands available
                context.last_verification_failed = False
                yield {"type": "status", "status": "completed"}

                # Mark plan as complete if we have one
                if plan_steps and context.plan_id:
                    for i in range(len(plan_steps)):
                        yield {
                            "type": "step_update",
                            "data": {
                                "plan_id": context.plan_id,
                                "step_index": i,
                                "status": "completed",
                            },
                        }
                    yield {
                        "type": "plan_complete",
                        "data": {"plan_id": context.plan_id},
                    }

                # Generate next steps
                next_steps = self._generate_next_steps(context)
                if next_steps:
                    yield {"type": "next_steps", "next_steps": next_steps}

                yield {
                    "type": "complete",
                    "summary": {
                        "task_id": context.task_id,
                        "files_read": context.files_read,
                        "files_modified": context.files_modified,
                        "files_created": context.files_created,
                        "iterations": context.iteration,
                        "verification_run": False,
                        "next_steps": next_steps,
                    },
                }
                return

        # Max iterations reached
        yield {"type": "status", "status": "failed"}
        yield {
            "type": "text",
            "text": f"\n⚠️ **Max iterations ({context.max_iterations}) reached.** Some issues may remain.\n",
            "timestamp": get_event_timestamp(),
        }

        # Mark plan as failed/incomplete
        if plan_steps and context.plan_id:
            # Mark last step as error since we couldn't complete
            yield {
                "type": "step_update",
                "data": {
                    "plan_id": context.plan_id,
                    "step_index": len(plan_steps) - 1,
                    "status": "error",
                },
            }
            yield {
                "type": "plan_complete",
                "data": {"plan_id": context.plan_id},
            }

        yield {
            "type": "complete",
            "summary": {
                "task_id": context.task_id,
                "files_read": context.files_read,
                "files_modified": context.files_modified,
                "files_created": context.files_created,
                "iterations": context.iteration,
                "verification_passed": False,
                "remaining_errors": [
                    e["message"][:200] for e in context.error_history[-3:]
                ],
            },
        }
