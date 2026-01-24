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
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


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
    file_path: str   # The file causing the error
    error_pattern: str  # Normalized error message pattern
    iteration: int

    def matches(self, other: 'ErrorSignature') -> bool:
        """Check if this error signature matches another (same file and pattern)."""
        return (self.error_type == other.error_type and
                self.file_path == other.file_path and
                self.error_pattern == other.error_pattern)


@dataclass
class FailedApproach:
    """Record of a failed approach for the LLM to avoid repeating."""
    iteration: int
    description: str
    files_touched: List[str]
    error_summary: str


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
    max_iterations: int = 10  # Increased to allow more alternative attempts
    status: TaskStatus = TaskStatus.PLANNING
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    project_type: Optional[str] = None
    framework: Optional[str] = None
    tool_calls_per_iteration: Dict[int, List[str]] = field(default_factory=dict)  # Track tool calls per iteration
    files_per_iteration: Dict[int, List[str]] = field(default_factory=dict)  # Track files created per iteration
    error_signatures: List[ErrorSignature] = field(default_factory=list)  # Track specific error patterns
    failed_approaches: List[FailedApproach] = field(default_factory=list)  # Track what approaches failed
    consecutive_same_error_count: int = 0  # Count of consecutive identical errors


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
        if os.path.exists(os.path.join(workspace_path, "pyproject.toml")) or \
           os.path.exists(os.path.join(workspace_path, "setup.py")) or \
           os.path.exists(os.path.join(workspace_path, "requirements.txt")):

            framework = "python"
            if os.path.exists(os.path.join(workspace_path, "manage.py")):
                framework = "django"
            elif os.path.exists(os.path.join(workspace_path, "app.py")):
                framework = "flask"

            commands["typecheck"] = "python -m mypy . --ignore-missing-imports" if \
                os.path.exists(os.path.join(workspace_path, "mypy.ini")) else None
            commands["test"] = "python -m pytest" if \
                os.path.exists(os.path.join(workspace_path, "pytest.ini")) or \
                os.path.exists(os.path.join(workspace_path, "tests")) else None
            commands["lint"] = "python -m ruff check ." if \
                os.path.exists(os.path.join(workspace_path, "ruff.toml")) else None

            return "python", framework, commands

        # Check for Go project
        if os.path.exists(os.path.join(workspace_path, "go.mod")):
            commands["build"] = "go build ./..."
            commands["test"] = "go test ./..."
            commands["lint"] = "golangci-lint run" if \
                os.path.exists(os.path.join(workspace_path, ".golangci.yml")) else None
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
        self,
        command: str,
        timeout: int = 120
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
                    process.communicate(),
                    timeout=timeout
                )
                output = stdout.decode("utf-8", errors="replace")
                return process.returncode == 0, output, process.returncode
            except asyncio.TimeoutError:
                process.kill()
                return False, f"Command timed out after {timeout}s", -1

        except Exception as e:
            return False, str(e), -1

    async def run_verification(
        self,
        verification_type: VerificationType,
        command: str
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
            errors=errors[:20],    # Limit error count
            warnings=warnings[:20]
        )

    async def verify_changes(
        self,
        commands: Dict[str, Optional[str]],
        run_tests: bool = True
    ) -> List[VerificationResult]:
        """Run all applicable verification commands."""
        results = []

        # Always run typecheck if available
        if commands.get("typecheck"):
            result = await self.run_verification(
                VerificationType.TYPESCRIPT,
                commands["typecheck"]
            )
            results.append(result)
            # If typecheck fails, don't continue
            if not result.success:
                return results

        # Run lint if available
        if commands.get("lint"):
            result = await self.run_verification(
                VerificationType.LINT,
                commands["lint"]
            )
            results.append(result)

        # Run tests if requested and available
        if run_tests and commands.get("test"):
            result = await self.run_verification(
                VerificationType.TESTS,
                commands["test"]
            )
            results.append(result)

        # Run build if available
        if commands.get("build"):
            result = await self.run_verification(
                VerificationType.BUILD,
                commands["build"]
            )
            results.append(result)

        return results


# Enhanced system prompt for autonomous operation
AUTONOMOUS_SYSTEM_PROMPT = """You are NAVI, an autonomous AI software engineer that solves ANY problem END-TO-END.

## Your Mission
You are not just a coding assistant - you are a FULL SOFTWARE ENGINEER.
You handle EVERYTHING: code, infrastructure, databases, DevOps, architecture, debugging, deployment - ANY software engineering challenge.
Execute until the task is DONE. NEVER stop to ask permission or explain what the user should do.

## TROUBLESHOOTING - ACT FAST, DON'T OVER-ANALYZE
When a user reports something isn't working (e.g., "site not loading", "server not starting"):
1. **DON'T read every file in the project** - only read what's needed
2. **DO check the obvious first**: Is the server running? Check with `lsof -i :PORT` or `ps aux | grep node`
3. **DO run diagnostic commands immediately**: `curl localhost:3000`, `docker ps`, `npm run dev`
4. **DO check logs**: Look at terminal output, error messages, log files
5. **FIX IT, don't explain** - Start the server, kill blocking processes, install dependencies

Example of GOOD troubleshooting:
```
User: "Site not loading"
You: Check if server is running... `lsof -i :3000` → No process found
You: Starting server... `npm run dev &` → Server started
You: Verifying... `curl localhost:3000` → Success!
Done!
```

Example of BAD troubleshooting:
```
User: "Site not loading"
You: Let me read package.json... reading README... reading tsconfig...
You: "This is a Next.js project. To fix this, you should: 1. Check Node version..."
```
WRONG! Don't read unnecessary files. Just check if the server is running and start it!

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

**REMEMBER:** Your narrative text is displayed to the user in real-time. Without it, they see only cryptic tool labels and wonder what's happening. BE VERBOSE about your actions!

## OUTPUT RESTRICTIONS - DO NOT ASK USER TO DO THINGS
- ❌ "Next steps:" followed by instructions for the user
- ❌ "You need to..." or "You should..."
- ❌ Numbered lists of things the USER should do
- ❌ ANY sentence asking the user to do something

INSTEAD: Narrate briefly what you're doing, then DO IT yourself.

You are a SOFTWARE ENGINEER who explains their work. Brief narration + immediate action.
"""


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
    ):
        self.workspace_path = workspace_path
        self.api_key = api_key
        self.provider = provider
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
        self.project_type, self.framework, self.verification_commands = \
            ProjectAnalyzer.detect_project_type(workspace_path)

        logger.info(f"[AutonomousAgent] Project: {self.project_type}/{self.framework}")
        logger.info(f"[AutonomousAgent] Verification commands: {self.verification_commands}")

    def _extract_error_signatures(
        self,
        results: List[VerificationResult],
        iteration: int
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
                    r'(?:ERROR in |error in |at |)(?:\.\/)?([^\s:()]+\.[tj]sx?)',
                    error_line,
                    re.IGNORECASE
                )
                file_path = file_match.group(1) if file_match else "unknown"

                # Normalize error pattern - remove line numbers, specific values
                # Keep the core error type/message
                error_pattern = error_line.lower()
                # Remove line/column numbers
                error_pattern = re.sub(r'\(\d+,\d+\)', '', error_pattern)
                error_pattern = re.sub(r':\d+:\d+', '', error_pattern)
                error_pattern = re.sub(r'line \d+', '', error_pattern)
                # Extract key error indicators
                if 'cannot find module' in error_pattern:
                    error_pattern = 'cannot_find_module'
                elif 'syntax error' in error_pattern or 'unexpected token' in error_pattern:
                    error_pattern = 'syntax_error'
                elif 'type' in error_pattern and 'error' in error_pattern:
                    error_pattern = 'type_error'
                elif 'jsx' in error_pattern:
                    error_pattern = 'jsx_error'
                elif 'import' in error_pattern:
                    error_pattern = 'import_error'
                elif 'unterminated' in error_pattern or 'string literal' in error_pattern:
                    error_pattern = 'unterminated_string'
                else:
                    # Keep first 50 chars as pattern
                    error_pattern = error_pattern[:50].strip()

                signatures.append(ErrorSignature(
                    error_type=result.type.value,
                    file_path=file_path,
                    error_pattern=error_pattern,
                    iteration=iteration
                ))

        return signatures

    def _detect_iteration_loop(self, context: TaskContext) -> Tuple[bool, str, List[str]]:
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
        last_iteration_errors = [s for s in context.error_signatures if s.iteration == context.iteration - 1]
        current_iteration_errors = [s for s in context.error_signatures if s.iteration == context.iteration]

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
                "Check if dependencies are missing or incorrectly installed"
            ]
        elif context.consecutive_same_error_count >= 2:
            severity = "warning"
            suggestions = [
                "Your previous fix did not resolve the issue",
                f"Re-read {', '.join(problem_files)} to see the actual current content",
                "The error might be in a different location than you think",
                "Check the import paths and file structure carefully",
                "Consider if you're fixing the symptom rather than the root cause"
            ]

        # Add specific suggestions based on error patterns
        for pattern_key in recurring.keys():
            if 'syntax_error' in pattern_key or 'jsx_error' in pattern_key:
                suggestions.append("For JSX/syntax errors: check for unescaped characters, missing closing tags, or incorrect attribute syntax")
            elif 'cannot_find_module' in pattern_key:
                suggestions.append("For module errors: verify the exact path, check if file exists, ensure correct relative path")
            elif 'type_error' in pattern_key:
                suggestions.append("For type errors: check the actual type definitions, don't assume types")

        return True, severity, suggestions

    def _record_failed_approach(self, context: TaskContext, error_summary: str) -> None:
        """Record a failed approach so the LLM knows not to repeat it."""
        # Get files touched in this iteration
        files_touched = list(set(
            context.files_modified[-5:] +
            context.files_created[-5:]
        ))

        # Build description of what was attempted
        tool_calls = context.tool_calls_per_iteration.get(context.iteration, [])
        description_parts = []

        for tc in tool_calls[-5:]:  # Last 5 tool calls
            if ':' in tc:
                tool, target = tc.split(':', 1)
                if tool == 'write_file':
                    description_parts.append(f"Created/wrote {target}")
                elif tool == 'edit_file':
                    description_parts.append(f"Edited {target}")
                elif tool == 'run_command':
                    description_parts.append(f"Ran command: {target[:50]}")

        description = "; ".join(description_parts) if description_parts else "Unknown approach"

        context.failed_approaches.append(FailedApproach(
            iteration=context.iteration,
            description=description,
            files_touched=files_touched,
            error_summary=error_summary[:200]
        ))

    def _build_system_prompt(self, context: TaskContext) -> str:
        """Build system prompt with current context."""
        # No longer including iteration/error info in prompt to keep responses clean
        return AUTONOMOUS_SYSTEM_PROMPT

    async def _diagnose_environment(self) -> str:
        """
        Diagnose the development environment ONCE at the start.
        This prevents the agent from blindly guessing what tools are available.
        """
        diagnostics = []

        checks = [
            # Node.js ecosystem
            ("Node.js", "node --version 2>/dev/null || echo 'not found'"),
            ("npm", "npm --version 2>/dev/null || echo 'not found'"),
            ("nvm", "bash -c 'source ~/.nvm/nvm.sh 2>/dev/null && nvm --version' 2>/dev/null || echo 'not found'"),
            ("Available Node versions", "ls ~/.nvm/versions/node/ 2>/dev/null | tr '\\n' ' ' || echo 'none'"),
            # Python ecosystem
            ("Python", "python3 --version 2>/dev/null || python --version 2>/dev/null || echo 'not found'"),
            ("pip", "pip3 --version 2>/dev/null || pip --version 2>/dev/null || echo 'not found'"),
            # Docker
            ("Docker", "docker --version 2>/dev/null || echo 'not found'"),
            ("Docker running", "docker ps >/dev/null 2>&1 && echo 'yes' || echo 'no'"),
            # Package managers
            ("Homebrew", "brew --version 2>/dev/null | head -1 || echo 'not found'"),
            # OS info
            ("OS", "uname -s 2>/dev/null"),
            # Current directory info
            ("Working dir", f"echo '{self.workspace_path}'"),
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
                    cwd=self.workspace_path
                )
                value = result.stdout.strip() or result.stderr.strip() or "unknown"
                diagnostics.append(f"{name}: {value}")
            except Exception as e:
                diagnostics.append(f"{name}: error checking ({e})")

        return "\n".join(diagnostics)

    async def _generate_plan(
        self,
        request: str,
        env_info: str,
        context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate a high-level plan for complex tasks before execution.
        This helps users understand what the agent will do.
        """
        # Determine if this is a complex task that needs planning
        # Simple tasks: single file edits, quick questions, simple commands
        # Complex tasks: multi-file changes, new feature implementation, debugging
        is_complex = (
            len(request) > 200 or
            any(kw in request.lower() for kw in [
                'implement', 'create', 'build', 'develop', 'fix all', 'refactor',
                'add feature', 'new feature', 'multiple files', 'complete',
                'full', 'entire', 'whole', 'application', 'project'
            ])
        )

        if not is_complex:
            # For simple tasks, generate a meaningful step label based on the request
            request_lower = request.lower()

            # Generate a task-specific label based on request content
            if 'fix' in request_lower or 'error' in request_lower or 'bug' in request_lower:
                label = "Fix the issue"
                desc = "Analyzing and fixing the reported problem"
            elif 'add' in request_lower:
                label = "Add requested feature"
                desc = "Implementing the requested addition"
            elif 'create' in request_lower:
                label = "Create component"
                desc = "Creating the requested file or component"
            elif 'update' in request_lower or 'change' in request_lower:
                label = "Apply changes"
                desc = "Updating the code as requested"
            elif 'delete' in request_lower or 'remove' in request_lower:
                label = "Remove items"
                desc = "Removing the specified code or files"
            elif 'refactor' in request_lower:
                label = "Refactor code"
                desc = "Restructuring code for better quality"
            elif 'test' in request_lower:
                label = "Run tests"
                desc = "Executing and verifying tests"
            elif 'read' in request_lower or 'show' in request_lower or 'what' in request_lower:
                label = "Analyze code"
                desc = "Reading and understanding the code"
            elif 'explain' in request_lower:
                label = "Explain code"
                desc = "Providing explanation of the code"
            else:
                # Extract first meaningful verb/noun phrase from request
                words = request.split()[:6]
                label = " ".join(words)[:30].strip()
                if not label:
                    label = "Process request"
                desc = request[:100] if len(request) > 100 else request

            yield {
                "type": "plan",
                "steps": [
                    {"id": 1, "label": label, "description": desc, "status": "pending"}
                ],
                "estimated_files": [],
                "is_complex": False
            }
            return

        # For complex tasks, use LLM to generate a proper plan
        plan_prompt = f"""Analyze this task and create a SPECIFIC execution plan (3-5 steps).

TASK: {request}

ENVIRONMENT:
{env_info}

Create steps that are SPECIFIC to this task, not generic.

Examples of GOOD task-specific steps:
- For "create a login page": "Create LoginForm component", "Add authentication logic", "Style login page"
- For "fix CSS errors": "Identify missing CSS modules", "Create CTASection.module.css", "Update component imports"
- For "implement API": "Create API route handlers", "Add database queries", "Test endpoints"

Examples of BAD generic steps (don't use these):
- "Analyze codebase" (too vague)
- "Implement changes" (not specific)
- "Run verification" (always implied)

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
                    messages=[{"role": "user", "content": plan_prompt}]
                )
                plan_text = response.content[0].text
            else:
                import openai
                client = openai.AsyncOpenAI(api_key=self.api_key)
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=500,
                    messages=[{"role": "user", "content": plan_prompt}]
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
                formatted_steps.append({
                    "id": step.get("id", i + 1),
                    "label": str(step.get("label", f"Step {i + 1}"))[:30],
                    "description": str(step.get("description", "")),
                    "status": "pending"
                })

            yield {
                "type": "plan",
                "steps": formatted_steps,
                "estimated_files": estimated_files[:10],  # Max 10 files
                "is_complex": True
            }

        except Exception as e:
            logger.warning(f"[AutonomousAgent] Plan generation failed: {e}")
            # Fall back to a task-specific default plan based on keywords
            request_lower = request.lower()

            if 'fix' in request_lower or 'error' in request_lower or 'bug' in request_lower:
                fallback_steps = [
                    {"id": 1, "label": "Identify issues", "description": "Find the root cause of errors", "status": "pending"},
                    {"id": 2, "label": "Apply fixes", "description": "Make corrections to resolve issues", "status": "pending"},
                    {"id": 3, "label": "Test changes", "description": "Verify fixes work correctly", "status": "pending"}
                ]
            elif 'create' in request_lower or 'add' in request_lower or 'new' in request_lower:
                fallback_steps = [
                    {"id": 1, "label": "Check dependencies", "description": "Review existing files and imports", "status": "pending"},
                    {"id": 2, "label": "Create new files", "description": "Generate required components", "status": "pending"},
                    {"id": 3, "label": "Update imports", "description": "Connect new files to project", "status": "pending"}
                ]
            elif 'implement' in request_lower or 'build' in request_lower:
                fallback_steps = [
                    {"id": 1, "label": "Review requirements", "description": "Understand what needs to be built", "status": "pending"},
                    {"id": 2, "label": "Build components", "description": "Create the implementation", "status": "pending"},
                    {"id": 3, "label": "Integrate & test", "description": "Connect and verify functionality", "status": "pending"}
                ]
            else:
                fallback_steps = [
                    {"id": 1, "label": "Analyze request", "description": "Understand the task requirements", "status": "pending"},
                    {"id": 2, "label": "Execute changes", "description": "Perform the necessary actions", "status": "pending"},
                    {"id": 3, "label": "Verify results", "description": "Ensure task completed successfully", "status": "pending"}
                ]

            yield {
                "type": "plan",
                "steps": fallback_steps,
                "estimated_files": [],
                "is_complex": True
            }

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: TaskContext
    ) -> Dict[str, Any]:
        """Execute a tool and track the action in context."""
        try:
            if tool_name == "read_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {"success": False, "error": f"File not found: {arguments['path']}"}

                with open(path, "r") as f:
                    lines = f.readlines()

                start = arguments.get("start_line", 1) - 1
                end = arguments.get("end_line", len(lines))
                content = "".join(lines[max(0, start):end])

                context.files_read.append(arguments["path"])
                return {
                    "success": True,
                    "content": content,
                    "total_lines": len(lines),
                    "path": arguments["path"]
                }

            elif tool_name == "write_file":
                file_path = arguments.get("path", "")
                content = arguments.get("content", "")

                if not file_path:
                    return {"success": False, "error": "No file path provided"}

                if not content:
                    logger.warning(f"write_file called with empty content for {file_path}")

                path = os.path.join(self.workspace_path, file_path)

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
                    return {"success": False, "error": f"Failed to write file: {write_error}"}

                # Verify the file was actually created/written
                if not os.path.exists(path):
                    logger.error(f"File {file_path} was not created despite no errors")
                    return {"success": False, "error": f"File {file_path} was not created"}

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
                    "size": len(content)
                }

            elif tool_name == "edit_file":
                path = os.path.join(self.workspace_path, arguments["path"])
                if not os.path.exists(path):
                    return {"success": False, "error": f"File not found: {arguments['path']}"}

                with open(path, "r") as f:
                    content = f.read()

                if arguments["old_text"] not in content:
                    return {
                        "success": False,
                        "error": "Could not find the text to replace. The file may have changed.",
                        "hint": "Try reading the file again to see current content."
                    }

                new_content = content.replace(arguments["old_text"], arguments["new_text"], 1)
                with open(path, "w") as f:
                    f.write(new_content)

                if arguments["path"] not in context.files_modified:
                    context.files_modified.append(arguments["path"])

                return {"success": True, "path": arguments["path"]}

            elif tool_name == "run_command":
                cwd = self.workspace_path
                if arguments.get("cwd"):
                    cwd = os.path.join(self.workspace_path, arguments["cwd"])

                # Use bash explicitly to support 'source' command for nvm/pyenv
                result = subprocess.run(
                    arguments["command"],
                    shell=True,
                    executable="/bin/bash",
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                context.commands_run.append({
                    "command": arguments["command"],
                    "exit_code": result.returncode,
                    "success": result.returncode == 0
                })

                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:3000] if result.stdout else "",
                    "stderr": result.stderr[:3000] if result.stderr else ""
                }

            elif tool_name == "search_files":
                import glob as glob_module
                pattern = arguments["pattern"]
                search_type = arguments["search_type"]
                results = []

                if search_type == "filename":
                    matches = glob_module.glob(
                        os.path.join(self.workspace_path, pattern),
                        recursive=True
                    )
                    results = [os.path.relpath(m, self.workspace_path) for m in matches[:30]]
                else:
                    try:
                        result = subprocess.run(
                            ["grep", "-r", "-l", pattern, "."],
                            cwd=self.workspace_path,
                            capture_output=True,
                            text=True,
                            timeout=30
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
                    entries.append({
                        "name": entry,
                        "type": "directory" if os.path.isdir(full_path) else "file"
                    })

                return {"success": True, "entries": entries}

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {tool_name} - {e}")
            return {"success": False, "error": str(e)}

    def _generate_next_steps(self, context: TaskContext) -> List[str]:
        """Generate helpful next steps based on what was accomplished."""
        steps = []

        # If we modified files, suggest testing
        if context.files_modified:
            if any('test' in f.lower() for f in context.files_modified):
                steps.append("Run tests to verify the changes")
            else:
                steps.append("Run tests to verify the changes work correctly")

        # If we created new files, suggest reviewing
        if context.files_created:
            steps.append("Review the newly created files")

        # If we ran commands that built something
        if context.commands_run:
            has_build = any('build' in cmd.get('command', '').lower() for cmd in context.commands_run)
            has_start = any('start' in cmd.get('command', '').lower() or 'dev' in cmd.get('command', '').lower() for cmd in context.commands_run)

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

    async def _call_llm_with_tools(
        self,
        messages: List[Dict[str, Any]],
        context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call LLM with tools and stream the response."""

        system_prompt = self._build_system_prompt(context)

        if self.provider == "anthropic":
            async for event in self._call_anthropic(messages, system_prompt, context):
                yield event
        else:
            async for event in self._call_openai(messages, system_prompt, context):
                yield event

    async def _call_anthropic(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call Anthropic Claude with tools."""
        import aiohttp
        from backend.services.streaming_agent import NAVI_TOOLS

        async with aiohttp.ClientSession() as session:
            while True:
                payload = {
                    "model": self.model,
                    "max_tokens": 4096,
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

                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=600),  # 10 minutes for complex operations
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        yield {"type": "error", "error": error}
                        return

                    text_buffer = ""
                    tool_calls = []
                    current_tool = None
                    stop_reason = None

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

                            if event_type == "content_block_start":
                                block = data.get("content_block", {})
                                if block.get("type") == "tool_use":
                                    current_tool = {
                                        "id": block.get("id"),
                                        "name": block.get("name"),
                                        "input": ""
                                    }
                                    if text_buffer:
                                        yield {"type": "text", "text": text_buffer}
                                        text_buffer = ""

                            elif event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    text_buffer += text
                                    if len(text_buffer) >= 30 or text.endswith((".", "!", "?", "\n")):
                                        yield {"type": "text", "text": text_buffer}
                                        text_buffer = ""
                                elif delta.get("type") == "input_json_delta" and current_tool:
                                    current_tool["input"] += delta.get("partial_json", "")

                            elif event_type == "content_block_stop":
                                if current_tool:
                                    try:
                                        args = json.loads(current_tool["input"]) if current_tool["input"] else {}
                                    except json.JSONDecodeError:
                                        args = {}

                                    yield {
                                        "type": "tool_call",
                                        "tool_call": {
                                            "id": current_tool["id"],
                                            "name": current_tool["name"],
                                            "arguments": args
                                        }
                                    }

                                    # Execute the tool
                                    result = await self._execute_tool(current_tool["name"], args, context)
                                    yield {
                                        "type": "tool_result",
                                        "tool_result": {
                                            "id": current_tool["id"],
                                            "result": result
                                        }
                                    }

                                    tool_calls.append({
                                        "id": current_tool["id"],
                                        "name": current_tool["name"],
                                        "input": args,
                                        "result": result
                                    })

                                    # Track tool calls per iteration for loop detection
                                    if context.iteration not in context.tool_calls_per_iteration:
                                        context.tool_calls_per_iteration[context.iteration] = []
                                    context.tool_calls_per_iteration[context.iteration].append(
                                        f"{current_tool['name']}:{args.get('path', args.get('command', ''))}"
                                    )
                                    current_tool = None

                            elif event_type == "message_delta":
                                stop_reason = data.get("delta", {}).get("stop_reason")

                        except json.JSONDecodeError:
                            continue

                    if text_buffer:
                        yield {"type": "text", "text": text_buffer}

                    # Continue if tool use
                    if stop_reason == "tool_use" and tool_calls:
                        assistant_content = []
                        for tc in tool_calls:
                            assistant_content.append({
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["name"],
                                "input": tc["input"]
                            })
                        messages.append({"role": "assistant", "content": assistant_content})

                        tool_results = []
                        for tc in tool_calls:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tc["id"],
                                "content": json.dumps(tc["result"])
                            })
                        messages.append({"role": "user", "content": tool_results})

                        tool_calls = []
                        continue
                    else:
                        return

    async def _call_openai(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        context: TaskContext
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Call OpenAI with function calling."""
        import aiohttp
        from backend.services.streaming_agent import NAVI_FUNCTIONS_OPENAI

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        async with aiohttp.ClientSession() as session:
            while True:
                payload = {
                    "model": self.model,
                    "messages": full_messages,
                    "tools": NAVI_FUNCTIONS_OPENAI,
                    "stream": True,
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                base_url = "https://api.openai.com/v1"
                if self.provider == "openrouter":
                    base_url = "https://openrouter.ai/api/v1"
                    headers["Authorization"] = f"Bearer {os.environ.get('OPENROUTER_API_KEY', self.api_key)}"
                elif self.provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                    headers["Authorization"] = f"Bearer {os.environ.get('GROQ_API_KEY', self.api_key)}"

                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=600),  # 10 minutes for complex operations
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        yield {"type": "error", "error": error}
                        return

                    text_buffer = ""
                    tool_calls: Dict[int, Dict[str, Any]] = {}
                    finish_reason = None

                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choice = data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            finish_reason = choice.get("finish_reason")

                            if delta.get("content"):
                                text = delta["content"]
                                text_buffer += text
                                if len(text_buffer) >= 30 or text.endswith((".", "!", "?", "\n")):
                                    yield {"type": "text", "text": text_buffer}
                                    text_buffer = ""

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls:
                                        tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                    if tc.get("id"):
                                        tool_calls[idx]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        tool_calls[idx]["name"] = tc["function"]["name"]
                                    if tc.get("function", {}).get("arguments"):
                                        tool_calls[idx]["arguments"] += tc["function"]["arguments"]

                        except json.JSONDecodeError:
                            continue

                    if text_buffer:
                        yield {"type": "text", "text": text_buffer}

                    if finish_reason == "tool_calls" and tool_calls:
                        assistant_tool_calls = []
                        for idx in sorted(tool_calls.keys()):
                            tc = tool_calls[idx]
                            assistant_tool_calls.append({
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"]
                                }
                            })

                        full_messages.append({
                            "role": "assistant",
                            "tool_calls": assistant_tool_calls
                        })

                        for idx in sorted(tool_calls.keys()):
                            tc = tool_calls[idx]
                            try:
                                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                            except json.JSONDecodeError:
                                args = {}

                            yield {
                                "type": "tool_call",
                                "tool_call": {
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "arguments": args
                                }
                            }

                            result = await self._execute_tool(tc["name"], args, context)

                            yield {
                                "type": "tool_result",
                                "tool_result": {
                                    "id": tc["id"],
                                    "result": result
                                }
                            }

                            full_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(result)
                            })

                        tool_calls = {}
                        continue
                    else:
                        return

    async def execute_task(
        self,
        request: str,
        run_verification: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a task autonomously with verification and self-healing.

        Yields events:
        - {"type": "status", "status": "planning|executing|verifying|fixing|completed|failed"}
        - {"type": "text", "text": "..."}
        - {"type": "tool_call", "tool_call": {...}}
        - {"type": "tool_result", "tool_result": {...}}
        - {"type": "verification", "results": [...]}
        - {"type": "iteration", "iteration": N, "reason": "..."}
        - {"type": "complete", "summary": {...}}
        """
        context = TaskContext(
            task_id=str(uuid.uuid4()),
            original_request=request,
            workspace_path=self.workspace_path,
            project_type=self.project_type,
            framework=self.framework,
        )

        yield {"type": "status", "status": "planning", "task_id": context.task_id}

        # Gather environment info ONCE at the start to avoid blind guessing
        env_info = await self._diagnose_environment()

        # Generate and emit execution plan for complex tasks
        plan_steps = []
        async for plan_event in self._generate_plan(request, env_info, context):
            yield plan_event
            if plan_event.get("type") == "plan":
                plan_steps = plan_event.get("steps", [])

        # Update first step to in_progress
        if plan_steps:
            yield {"type": "step_update", "step_id": 1, "status": "in_progress"}

        # Include environment info in the initial request
        enhanced_request = f"""{request}

--- ENVIRONMENT INFO (gathered automatically) ---
{env_info}
--- END ENVIRONMENT INFO ---

Use the tools and versions listed above. Don't guess - use what's actually available."""

        messages = [{"role": "user", "content": enhanced_request}]

        while context.iteration < context.max_iterations:
            context.iteration += 1
            context.status = TaskStatus.EXECUTING

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
                           f"3. Checking if there are missing dependencies or configuration\n"
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
                        "remaining_errors": [e["message"][:200] for e in context.error_history[-3:]]
                    }
                }
                return

            # Only emit iteration event for subsequent iterations (not the first one)
            # This avoids showing "Iteration 1/10" debug info to users
            if context.iteration > 1:
                # Provide context-aware iteration reason
                if context.consecutive_same_error_count >= 3:
                    reason = f"Loop detected ({context.consecutive_same_error_count}x same error) - forcing different strategy"
                elif context.consecutive_same_error_count >= 2:
                    reason = "Same error persists - trying alternative fix"
                elif context.failed_approaches:
                    reason = f"Previous approach failed - trying alternative ({len(context.failed_approaches)} attempts so far)"
                else:
                    reason = "Fixing verification errors..."

                yield {
                    "type": "iteration",
                    "iteration": context.iteration,
                    "max": context.max_iterations,
                    "reason": reason,
                    "loop_count": context.consecutive_same_error_count
                }

            # Call LLM with tools
            async for event in self._call_llm_with_tools(messages, context):
                yield event

                # Track assistant text for conversation history
                if event.get("type") == "text":
                    if not context.conversation_history or \
                       context.conversation_history[-1]["role"] != "assistant":
                        context.conversation_history.append({"role": "assistant", "content": ""})
                    context.conversation_history[-1]["content"] += event["text"]

            # Check if any files were modified
            if not context.files_modified and not context.files_created:
                # No changes made - task might be info-only or failed
                yield {"type": "status", "status": "completed"}

                # For info-only tasks, suggest follow-up questions
                next_steps = ["Ask me to implement changes if needed", "Explore related files", "Ask follow-up questions"]
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
                        "next_steps": next_steps
                    }
                }
                return

            # Run verification if enabled
            if run_verification and self.verification_commands:
                context.status = TaskStatus.VERIFYING
                yield {"type": "status", "status": "verifying"}

                # Update step progress - mark previous steps completed, verification in progress
                if plan_steps:
                    # Mark all previous steps as completed
                    for i, step in enumerate(plan_steps[:-1], 1):
                        yield {"type": "step_update", "step_id": i, "status": "completed"}
                    # Mark last step (usually verification) as in progress
                    yield {"type": "step_update", "step_id": len(plan_steps), "status": "in_progress"}

                yield {"type": "text", "text": "\n\n**Running verification...**\n"}

                results = await self.verifier.verify_changes(
                    self.verification_commands,
                    run_tests=True
                )
                context.verification_results = results

                yield {"type": "verification", "results": [
                    {
                        "type": r.type.value,
                        "success": r.success,
                        "errors": r.errors[:5],
                        "warnings": r.warnings[:5]
                    }
                    for r in results
                ]}

                # Check if all passed
                all_passed = all(r.success for r in results)

                if all_passed:
                    yield {"type": "text", "text": "\n✅ **All verifications passed!**\n"}
                    yield {"type": "status", "status": "completed"}

                    # Mark all plan steps as completed
                    if plan_steps:
                        for step in plan_steps:
                            yield {"type": "step_update", "step_id": step.get("id", 1), "status": "completed"}

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
                            "next_steps": next_steps
                        }
                    }
                    return

                # Verification failed - prepare for retry
                context.status = TaskStatus.FIXING
                yield {"type": "status", "status": "fixing"}

                # Build error context for retry
                error_details = []
                for r in results:
                    if not r.success:
                        context.error_history.append({
                            "type": r.type.value,
                            "message": "\n".join(r.errors[:10]),
                            "iteration": context.iteration
                        })
                        error_details.append(f"**{r.type.value}** failed:\n```\n{r.output[:1500]}\n```")

                error_message = "\n\n".join(error_details)

                # Extract error signatures for loop detection
                new_signatures = self._extract_error_signatures(results, context.iteration)
                context.error_signatures.extend(new_signatures)

                # Detect iteration loops
                is_looping, loop_severity, loop_suggestions = self._detect_iteration_loop(context)

                # Record this as a failed approach
                error_summary = "; ".join(r.errors[0] if r.errors else "Unknown error" for r in results if not r.success)
                self._record_failed_approach(context, error_summary)

                # Emit appropriate message based on loop detection
                if is_looping and loop_severity == "critical":
                    yield {
                        "type": "text",
                        "text": f"\n🔄 **Loop detected - same error {context.consecutive_same_error_count} times.** Forcing different strategy...\n"
                    }
                    yield {"type": "loop_detected", "severity": loop_severity, "count": context.consecutive_same_error_count}
                else:
                    yield {
                        "type": "text",
                        "text": f"\n❌ **Verification failed.** Analyzing errors and fixing...\n\n{error_message}\n"
                    }

                # Add error context to messages for retry
                messages.append({
                    "role": "assistant",
                    "content": context.conversation_history[-1]["content"] if context.conversation_history else ""
                })

                # Build context of what was already tried to prevent repeating the same approach
                actions_taken = []
                if context.files_created:
                    actions_taken.append(f"Files already created: {', '.join(context.files_created)}")
                if context.files_modified:
                    actions_taken.append(f"Files already modified: {', '.join(context.files_modified)}")
                if context.files_read:
                    actions_taken.append(f"Files already read: {', '.join(context.files_read[-10:])}")  # Last 10

                actions_context = "\n".join(actions_taken) if actions_taken else "No files created or modified yet."

                # Build failed approaches summary with detailed guidance
                failed_approaches_text = ""
                if context.failed_approaches:
                    approach_list = []
                    for fa in context.failed_approaches[-5:]:  # Last 5 failed approaches
                        approach_list.append(f"  ❌ Iteration {fa.iteration}: {fa.description}")
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

                messages.append({
                    "role": "user",
                    "content": f"""Verification failed. Here are the errors:

{error_message}

**Actions taken so far (iteration {context.iteration} of {context.max_iterations}):**
{actions_context}
{failed_approaches_text}
{approach_hint}

After fixing, I'll run verification again."""
                })

            else:
                # No verification or no commands available
                yield {"type": "status", "status": "completed"}

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
                        "next_steps": next_steps
                    }
                }
                return

        # Max iterations reached
        yield {"type": "status", "status": "failed"}
        yield {
            "type": "text",
            "text": f"\n⚠️ **Max iterations ({context.max_iterations}) reached.** Some issues may remain.\n"
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
                "remaining_errors": [e["message"][:200] for e in context.error_history[-3:]]
            }
        }
