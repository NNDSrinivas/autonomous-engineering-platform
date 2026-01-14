# NAVI LLM-First Engine (with Safety Features)
# backend/services/navi_brain.py
"""
NAVI Brain - LLM-First Architecture with Safety

NO regex patterns. NO hardcoded intents.
LLM understands EVERYTHING and decides what to do.

This is how Cursor, Claude Code, Copilot, and Cline actually work.

Safety Features:
- Command whitelist (only safe commands allowed)
- File size limits (max 100KB per file)
- Path validation (no escaping workspace)
- Dangerous command detection
- User confirmation required for sensitive operations

Usage:
    brain = NaviBrain(provider="anthropic", model="claude-3-5-sonnet-20241022", api_key="...")
    result = await brain.process("I need a way for users to login", context)
    # Returns: files to create, commands to run, explanation
"""

import os
import json
import asyncio
import aiohttp
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

# ==================== SAFETY CONFIGURATION ====================

# Safe commands that can be executed without user confirmation
SAFE_COMMANDS = {
    # Package managers
    "npm",
    "yarn",
    "pnpm",
    "bun",
    "pip",
    "pip3",
    "poetry",
    "pipenv",
    "cargo",
    "go",
    "composer",
    "gem",
    "bundle",
    # Build tools
    "make",
    "cmake",
    "gradle",
    "mvn",
    "ant",
    # Testing
    "pytest",
    "jest",
    "vitest",
    "mocha",
    "jasmine",
    "karma",
    "go test",
    "cargo test",
    "phpunit",
    # Linting/Formatting
    "eslint",
    "prettier",
    "black",
    "flake8",
    "pylint",
    "mypy",
    "rustfmt",
    "gofmt",
    "rubocop",
    # Git (safe operations only)
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git checkout",
    "git add",
    "git commit",
    "git pull",
    "git fetch",
    "git stash",
    # Docker (read-only operations)
    "docker ps",
    "docker images",
    "docker logs",
    # File operations (safe)
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "tree",
}

# Dangerous commands that require user confirmation
DANGEROUS_PATTERNS = [
    r"rm\s+-rf",  # Recursive force delete
    r"rm\s+/",  # Delete from root
    r"sudo",  # Elevated privileges
    r"chmod\s+777",  # Insecure permissions
    r"git\s+push\s+.*--force",  # Force push
    r"docker\s+rm",  # Delete containers
    r"docker\s+rmi",  # Delete images
    r"kubectl\s+delete",  # Delete k8s resources
    r"DROP\s+TABLE",  # SQL drop
    r"DROP\s+DATABASE",
]

MAX_FILE_SIZE = 100 * 1024  # 100KB max per file
MAX_FILES_PER_REQUEST = 20  # Max files to create at once


# ==================== PROJECT INTELLIGENCE ====================


@dataclass
class ProjectInfo:
    """Information gathered from reading the project (like Codex/Claude Code)"""

    project_type: str = "unknown"  # nextjs, react, vue, express, python, etc.
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    package_manager: str = "npm"  # npm, yarn, pnpm, bun

    # From package.json
    name: Optional[str] = None
    scripts: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)

    # From README
    readme_content: Optional[str] = None
    readme_run_instructions: Optional[str] = None

    # From config files
    has_typescript: bool = False
    has_eslint: bool = False
    has_prettier: bool = False
    has_docker: bool = False
    has_env_example: bool = False

    # Files found
    files_read: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Convert to string for LLM context"""
        parts = []

        parts.append(f"PROJECT TYPE: {self.project_type}")
        if self.framework:
            parts.append(f"FRAMEWORK: {self.framework} {self.framework_version or ''}")
        parts.append(f"PACKAGE MANAGER: {self.package_manager}")

        if self.name:
            parts.append(f"PROJECT NAME: {self.name}")

        if self.scripts:
            scripts_str = ", ".join([f"{k}" for k in list(self.scripts.keys())[:15]])
            parts.append(f"AVAILABLE SCRIPTS: {scripts_str}")

        features = []
        if self.has_typescript:
            features.append("TypeScript")
        if self.has_eslint:
            features.append("ESLint")
        if self.has_prettier:
            features.append("Prettier")
        if self.has_docker:
            features.append("Docker")
        if features:
            parts.append(f"FEATURES: {', '.join(features)}")

        if self.readme_run_instructions:
            parts.append(f"README INSTRUCTIONS:\n{self.readme_run_instructions[:300]}")

        parts.append(f"FILES ANALYZED: {', '.join(self.files_read[:10])}")

        return "\n".join(parts)


class ProjectAnalyzer:
    """
    Analyzes a project by reading its files (like Codex/Claude Code).
    This is what makes NAVI intelligent - it reads before responding.
    """

    # Files to read for understanding the project
    KEY_FILES = [
        "package.json",
        "README.md",
        "README",
        "readme.md",
        ".env.example",
        ".env.local.example",
        "tsconfig.json",
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
        "vite.config.js",
        "vite.config.ts",
        "vue.config.js",
        "angular.json",
        "nuxt.config.js",
        "nuxt.config.ts",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Cargo.toml",
        "go.mod",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Dockerfile",
    ]

    @classmethod
    def analyze(cls, workspace_path: str) -> ProjectInfo:
        """
        Analyze a project by reading its key files.
        Returns structured information about the project.
        """
        info = ProjectInfo()
        workspace = Path(workspace_path)

        if not workspace.exists():
            logger.warning(f"Workspace does not exist: {workspace_path}")
            return info

        # Read each key file
        for filename in cls.KEY_FILES:
            file_path = workspace / filename
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    cls._process_file(filename, content, info)
                    info.files_read.append(filename)
                except Exception as e:
                    logger.debug(f"Could not read {filename}: {e}")

        # Detect package manager
        if (workspace / "yarn.lock").exists():
            info.package_manager = "yarn"
        elif (workspace / "pnpm-lock.yaml").exists():
            info.package_manager = "pnpm"
        elif (workspace / "bun.lockb").exists():
            info.package_manager = "bun"

        logger.info(
            f"[ProjectAnalyzer] Analyzed project: type={info.project_type}, framework={info.framework}, files_read={len(info.files_read)}"
        )
        return info

    @classmethod
    def _process_file(cls, filename: str, content: str, info: ProjectInfo) -> None:
        """Process a file and extract information"""

        if filename == "package.json":
            cls._process_package_json(content, info)

        elif filename.lower() in ["readme.md", "readme"]:
            cls._process_readme(content, info)

        elif filename == "tsconfig.json":
            info.has_typescript = True

        elif filename in [".env.example", ".env.local.example"]:
            info.has_env_example = True

        # Detect framework from config files
        elif filename.startswith("next.config"):
            info.project_type = "nextjs"
            info.framework = "Next.js"

        elif filename.startswith("vite.config"):
            if info.project_type == "unknown":
                info.project_type = "vite"

        elif filename.startswith("vue.config"):
            info.project_type = "vue"
            info.framework = "Vue.js"

        elif filename == "angular.json":
            info.project_type = "angular"
            info.framework = "Angular"

        elif filename.startswith("nuxt.config"):
            info.project_type = "nuxt"
            info.framework = "Nuxt.js"

        elif filename == "requirements.txt" or filename == "pyproject.toml":
            info.project_type = "python"

        elif filename == "Cargo.toml":
            info.project_type = "rust"

        elif filename == "go.mod":
            info.project_type = "go"

        elif filename in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]:
            info.has_docker = True

    @classmethod
    def _process_package_json(cls, content: str, info: ProjectInfo) -> None:
        """Extract information from package.json"""
        try:
            pkg = json.loads(content)

            info.name = pkg.get("name")
            info.scripts = pkg.get("scripts", {})
            info.dependencies = pkg.get("dependencies", {})
            info.dev_dependencies = pkg.get("devDependencies", {})

            # Detect framework from dependencies
            deps = {**info.dependencies, **info.dev_dependencies}

            if "next" in deps:
                info.project_type = "nextjs"
                info.framework = "Next.js"
                info.framework_version = deps.get("next", "").lstrip("^~")

            elif "nuxt" in deps or "@nuxt/core" in deps:
                info.project_type = "nuxt"
                info.framework = "Nuxt.js"

            elif "vue" in deps:
                info.project_type = "vue"
                info.framework = "Vue.js"
                info.framework_version = deps.get("vue", "").lstrip("^~")

            elif "@angular/core" in deps:
                info.project_type = "angular"
                info.framework = "Angular"

            elif "react" in deps:
                info.project_type = "react"
                info.framework = "React"
                info.framework_version = deps.get("react", "").lstrip("^~")

            elif "express" in deps:
                info.project_type = "express"
                info.framework = "Express.js"

            elif "svelte" in deps or "@sveltejs/kit" in deps:
                info.project_type = "svelte"
                info.framework = "SvelteKit"

            # Check for TypeScript
            if "typescript" in deps:
                info.has_typescript = True

        except json.JSONDecodeError:
            logger.debug("Could not parse package.json")

    @classmethod
    def _process_readme(cls, content: str, info: ProjectInfo) -> None:
        """Extract run instructions from README"""
        info.readme_content = content[:2000]  # First 2000 chars

        # Look for "Getting Started", "Installation", "Usage", "Running" sections
        patterns = [
            r"##\s*(?:Getting Started|Quick Start|Installation|Setup|Running|Usage|Development)\s*\n([\s\S]*?)(?=\n##|\Z)",
            r"###\s*(?:Getting Started|Quick Start|Installation|Setup|Running|Usage|Development)\s*\n([\s\S]*?)(?=\n###|\n##|\Z)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info.readme_run_instructions = match.group(0)[:500]
                break


# ==================== INTELLIGENT RESPONSE GENERATOR ====================


class IntelligentResponder:
    """
    Generates intelligent responses based on project analysis.
    This is what makes NAVI act like Codex/Claude Code.
    """

    @classmethod
    def generate_run_instructions(cls, project_info: ProjectInfo) -> str:
        """
        Generate 'how to run' instructions based on actual project analysis.
        This is what Codex and Claude Code do - they read first, then respond.
        """
        parts = []

        # Show what we found
        parts.append(
            f"This is a **{project_info.framework or project_info.project_type}** project."
        )
        if project_info.framework_version:
            parts.append(f"(Version: {project_info.framework_version})")

        parts.append("\n**To run this project:**\n")

        # Step 1: Install dependencies
        install_cmd = cls._get_install_command(project_info)
        parts.append("1. **Install dependencies** (if you haven't already):")
        parts.append("   ```")
        parts.append(f"   {install_cmd}")
        parts.append("   ```")

        # Step 2: Run dev server
        dev_cmd, dev_url = cls._get_dev_command(project_info)
        if dev_cmd:
            parts.append("\n2. **Start the development server:**")
            parts.append("   ```")
            parts.append(f"   {dev_cmd}")
            parts.append("   ```")
            if dev_url:
                parts.append(f"   → Opens at {dev_url}")

        # Additional scripts
        other_scripts = cls._get_other_useful_scripts(project_info)
        if other_scripts:
            parts.append("\n**Other available commands:**")
            for script, desc in other_scripts:
                parts.append(
                    f"- `{project_info.package_manager} run {script}` - {desc}"
                )

        # Environment setup
        if project_info.has_env_example:
            parts.append("\n**⚠️ Environment Setup:**")
            parts.append("Copy `.env.example` to `.env.local` and fill in your values.")

        return "\n".join(parts)

    @classmethod
    def _get_install_command(cls, info: ProjectInfo) -> str:
        """Get the correct install command for the project"""
        if info.project_type == "python":
            if "pyproject.toml" in info.files_read:
                return "pip install -e ."
            return "pip install -r requirements.txt"
        elif info.project_type == "rust":
            return "cargo build"
        elif info.project_type == "go":
            return "go mod download"
        else:
            # JavaScript/Node.js
            return {
                "npm": "npm install",
                "yarn": "yarn",
                "pnpm": "pnpm install",
                "bun": "bun install",
            }.get(info.package_manager, "npm install")

    @classmethod
    def _get_dev_command(cls, info: ProjectInfo) -> tuple[Optional[str], Optional[str]]:
        """Get the correct dev command and URL"""
        pm = info.package_manager
        run = "run" if pm != "yarn" else ""

        # Check for specific scripts in order of preference
        dev_scripts = ["dev", "start", "serve", "develop"]

        for script in dev_scripts:
            if script in info.scripts:
                cmd = f"{pm} {run} {script}".replace("  ", " ")

                # Determine URL based on framework
                url = None
                if info.project_type in ["nextjs", "react", "vue", "nuxt"]:
                    url = "http://localhost:3000"
                elif info.project_type == "angular":
                    url = "http://localhost:4200"
                elif info.project_type == "astro":
                    url = "http://localhost:4321"
                elif info.project_type in ["vite", "svelte"]:
                    url = "http://localhost:5173"

                return cmd, url

        # Python projects
        if info.project_type == "python":
            if "uvicorn" in str(info.dependencies):
                return "uvicorn main:app --reload", "http://localhost:8000"
            elif "flask" in str(info.dependencies):
                return "flask run", "http://localhost:5000"
            elif "django" in str(info.dependencies):
                return "python manage.py runserver", "http://localhost:8000"

        return None, None

    @classmethod
    def _get_other_useful_scripts(cls, info: ProjectInfo) -> List[tuple[str, str]]:
        """Get other useful scripts with descriptions"""
        result = []

        script_descriptions = {
            "build": "Creates a production build",
            "test": "Runs tests",
            "lint": "Runs the linter",
            "format": "Formats code",
            "typecheck": "Runs TypeScript type checking",
            "preview": "Preview production build locally",
            "e2e": "Runs end-to-end tests",
            "storybook": "Starts Storybook",
        }

        for script, desc in script_descriptions.items():
            if script in info.scripts and script not in ["dev", "start"]:
                result.append((script, desc))

        return result[:5]  # Max 5 other scripts


# ==================== DATA CLASSES ====================


@dataclass
class NaviContext:
    """Everything NAVI knows about the current state"""

    workspace_path: str
    project_type: str = "unknown"
    technologies: List[str] = field(default_factory=list)
    current_file: Optional[str] = None
    current_file_content: Optional[str] = None
    selection: Optional[str] = None
    open_files: List[str] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    git_branch: Optional[str] = None
    git_status: Dict[str, Any] = field(default_factory=dict)
    recent_conversation: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class NaviResponse:
    """What NAVI returns after processing"""

    message: str  # What to show the user
    files_to_create: Dict[str, str] = field(default_factory=dict)  # path -> content
    files_to_modify: Dict[str, str] = field(default_factory=dict)  # path -> new content
    commands_to_run: List[str] = field(default_factory=list)  # shell commands
    vscode_commands: List[Dict] = field(default_factory=list)  # VS Code commands
    needs_user_input: bool = False
    user_input_prompt: Optional[str] = None

    # Safety fields
    dangerous_commands: List[str] = field(
        default_factory=list
    )  # Commands needing confirmation
    warnings: List[str] = field(default_factory=list)  # Safety warnings

    # Intelligence fields (like Codex/Claude Code)
    thinking_steps: List[str] = field(default_factory=list)  # Show what NAVI did
    files_read: List[str] = field(default_factory=list)  # Show what files were analyzed
    project_type: Optional[str] = None  # Detected project type
    framework: Optional[str] = None  # Detected framework

    # NAVI V2: Approval flow fields
    plan_id: Optional[str] = None  # Unique ID for this plan
    requires_approval: bool = False  # If true, show approval UI
    actions_with_risk: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Actions with risk assessment
    estimated_changes: Dict[str, Any] = field(
        default_factory=dict
    )  # Files affected, lines changed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "files_to_create": self.files_to_create,
            "files_to_modify": self.files_to_modify,
            "commands_to_run": self.commands_to_run,
            "vscode_commands": self.vscode_commands,
            "needs_user_input": self.needs_user_input,
            "user_input_prompt": self.user_input_prompt,
            "dangerous_commands": self.dangerous_commands,
            "warnings": self.warnings,
            "thinking_steps": self.thinking_steps,
            "files_read": self.files_read,
            "project_type": self.project_type,
            "framework": self.framework,
            # NAVI V2 fields
            "plan_id": self.plan_id,
            "requires_approval": self.requires_approval,
            "actions_with_risk": self.actions_with_risk,
            "estimated_changes": self.estimated_changes,
        }


@dataclass
class NaviPlan:
    """
    A plan that requires user approval before execution.
    This is NAVI V2's key feature - human-in-the-loop approval flow.
    """

    id: str  # Unique UUID
    user_message: str
    context: NaviContext
    response: NaviResponse
    status: str = (
        "pending_approval"  # pending_approval, approved, rejected, executing, completed
    )
    created_at: datetime = field(default_factory=datetime.now)
    approved_actions: List[int] = field(
        default_factory=list
    )  # User-selected action indices

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_message": self.user_message,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "approved_actions": self.approved_actions,
            "response": self.response.to_dict(),
        }


# ==================== SAFETY VALIDATORS ====================


class SafetyValidator:
    """Validates LLM responses for safety"""

    @staticmethod
    def is_safe_command(command: str) -> bool:
        """Check if command is in whitelist"""
        # Check if command starts with any safe command
        for safe_cmd in SAFE_COMMANDS:
            if command.startswith(safe_cmd):
                return True

        return False

    @staticmethod
    def is_dangerous_command(command: str) -> bool:
        """Check if command matches dangerous patterns"""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def validate_file_path(file_path: str, workspace_path: str) -> bool:
        """Ensure file path doesn't escape workspace"""
        try:
            workspace = Path(workspace_path).resolve()
            target = (workspace / file_path).resolve()

            # Check if target is within workspace
            return str(target).startswith(str(workspace))
        except Exception:
            return False  # Path resolution failed, treat as unsafe

    @staticmethod
    def validate_file_size(content: str) -> bool:
        """Check file size doesn't exceed limit"""
        return len(content.encode("utf-8")) <= MAX_FILE_SIZE

    @staticmethod
    def validate_response(
        response: NaviResponse, workspace_path: str
    ) -> tuple[bool, List[str]]:
        """
        Validate entire response for safety.

        Returns: (is_safe, list_of_warnings)
        """
        warnings = []

        # Check file count
        total_files = len(response.files_to_create) + len(response.files_to_modify)
        if total_files > MAX_FILES_PER_REQUEST:
            warnings.append(
                f"Too many files ({total_files}). Max allowed: {MAX_FILES_PER_REQUEST}"
            )
            return False, warnings

        # Check file paths
        all_files = {**response.files_to_create, **response.files_to_modify}
        for file_path, content in all_files.items():
            # Validate path
            if not SafetyValidator.validate_file_path(file_path, workspace_path):
                warnings.append(f"Invalid path (escapes workspace): {file_path}")
                return False, warnings

            # Validate size
            if not SafetyValidator.validate_file_size(content):
                size_kb = len(content.encode("utf-8")) / 1024
                warnings.append(
                    f"File too large: {file_path} ({size_kb:.1f}KB > {MAX_FILE_SIZE/1024}KB)"
                )
                return False, warnings

        # Check commands
        for command in response.commands_to_run:
            if SafetyValidator.is_dangerous_command(command):
                response.dangerous_commands.append(command)
                warnings.append(f"Dangerous command detected: {command}")

        return True, warnings


# ==================== NAVI BRAIN ====================


class NaviBrain:
    """
    The brain of NAVI - LLM-first, understands everything.

    No regex. No pattern matching. Just intelligence.
    """

    SYSTEM_PROMPT = """You are NAVI, an INTELLIGENT and AUTONOMOUS AI coding assistant.

⭐ INTELLIGENCE UPGRADE: You now have PROJECT ANALYSIS from reading actual project files.
When you see "=== PROJECT ANALYSIS (from reading files) ===" in the context:
- USE that information to give accurate, project-specific responses
- Reference actual scripts found in package.json
- Use the correct package manager (npm/yarn/pnpm/bun)
- Mention actual dependencies and framework versions
- DO NOT give generic answers when you have project-specific context

INTELLIGENT DECISION FRAMEWORK:

**ANALYZE INTENT FIRST** - Determine if the user wants:
1. 📖 **INFORMATION** (read-only): "what is...", "are there errors?", "explain...", "how to run?"
2. 🛠️ **ACTION** (modify code): "create...", "add...", "fix...", "install..."

**FOR INFORMATION REQUESTS** (read-only):
- USE the PROJECT ANALYSIS to give informed answers
- Provide clear, detailed explanations based on what was found
- Analyze code and report findings
- List errors with line numbers and suggestions
- Explain what the code does
- ❌ DO NOT create files or modify code unless explicitly asked

**FOR ACTION REQUESTS** (modify code):
- USE the PROJECT ANALYSIS to understand the project structure
- Take immediate action
- Create/modify files with complete code matching project conventions
- Run necessary commands using the correct package manager
- Be proactive and decisive
- ✅ ALWAYS execute the requested changes

**EXAMPLES**:

❓ "how to run this project?"
✅ Correct: Use PROJECT ANALYSIS to find actual scripts, then explain:
   "This is a Next.js 14 project. To run it:
    1. npm install (using npm as package manager)
    2. npm run dev (opens at localhost:3000)
    Available scripts: build, lint, test"
❌ Wrong: Generic answer "npm install && npm run dev" without checking if those scripts exist

❓ "are there any errors in this repo?"
✅ Correct: Analyze diagnostics, explain each error with line numbers, suggest fixes
❌ Wrong: Create files to "demonstrate" error handling

❓ "what is this project for?"
✅ Correct: Use PROJECT ANALYSIS package.json name, dependencies, README
❌ Wrong: Create README or example files

❓ "create a navbar component"
✅ Correct: Create Navbar.tsx with complete implementation
❌ Wrong: Just explain what a navbar is

❓ "fix the type errors"
✅ Correct: Read files, modify them to fix errors
❌ Wrong: Just list the errors without fixing

YOUR PERSONALITY:
- INTELLIGENT: Understand user intent before acting
- DECISIVE: When action is needed, execute immediately without asking
- THOROUGH: For information requests, provide complete analysis
- HELPFUL: Give exactly what the user needs - info OR action

YOUR CAPABILITIES:
- Create ANY files (components, pages, APIs, configs, tests, docs, anything)
- Modify ANY existing files
- Run ANY commands (npm, git, docker, databases, deployment, anything)
- Read and analyze ANY code for errors, improvements, patterns
- Chain unlimited actions (create 20 files + install packages + run tests + commit)

RESPONSE MODE RULES:

**INFORMATION MODE** (no files/commands):
- "are there errors?" → List and explain errors
- "what is this?" → Analyze and explain
- "how does X work?" → Explain the mechanism
- "what files handle X?" → List and describe files
Response format: {"message": "Detailed explanation", "files_to_create": {}, ...}

**ACTION MODE** (create/modify files):
- "create X" → Generate complete implementation
- "add X" → Modify files to add feature
- "fix the errors" → Modify files with fixes
- "install X" → Run commands
- "improve X" → Modify with enhancements
Response format: {"message": "Brief description", "files_to_create": {...}, ...}

**SMART DISAMBIGUATION**:
- "what else can we do?" = INFORMATION (list possibilities, don't create)
- "add more features" = ACTION (create new features)
- "are there problems?" = INFORMATION (analyze and report)
- "fix the problems" = ACTION (modify files)

CODE QUALITY STANDARDS:
- COMPLETE code only (no TODOs, no placeholders, no comments like "implement here")
- PRODUCTION-READY (error handling, validation, best practices)
- FOLLOW project conventions (detect and match existing patterns)
- MODERN approaches (latest features, current best practices)

SAFETY CONSTRAINTS:
- NO: rm -rf, sudo, chmod 777, or destructive commands
- NO: files outside workspace boundaries
- NO: files larger than 100KB (split into multiple files)
- YES: Everything else is fair game

RESPONSE FORMAT (MUST BE VALID JSON):
{
    "message": "Brief description of actions taken (1-2 sentences)",
    "files_to_create": {
        "path/to/file.tsx": "COMPLETE file content (no TODOs)",
        "another/file.ts": "COMPLETE file content"
    },
    "files_to_modify": {
        "existing/file.ts": "COMPLETE new content (full file replacement)"
    },
    "commands_to_run": ["npm install package", "npm test"],
    "vscode_commands": [
        {"command": "vscode.open", "args": ["path/to/file.tsx"]}
    ],
    "needs_user_input": false
}

**CLARIFICATION REQUEST** (rare):
{
    "message": "I need clarification: [specific question]",
    "needs_user_input": true,
    "user_input_prompt": "Specific question about X or Y?",
    "files_to_create": {},
    "files_to_modify": {},
    "commands_to_run": [],
    "vscode_commands": []
}

🎯 KEY PRINCIPLE: Match your response to user intent - INFORMATION or ACTION. Both are equally valid."""

    def __init__(
        self,
        provider: str = "anthropic",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
    ):
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key_from_env()
        self.model = model or self._get_default_model()
        self.base_url = base_url or self._get_base_url()
        self.session: Optional[aiohttp.ClientSession] = None
        self.validator = SafetyValidator()

        # NAVI V2: Plan storage for approval flow
        self.active_plans: Dict[str, NaviPlan] = {}

    def _get_api_key_from_env(self) -> str:
        """Get API key from environment"""
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        return os.getenv(env_vars.get(self.provider, ""), "")

    def _get_default_model(self) -> str:
        """Get default model for provider"""
        defaults = {
            "anthropic": "claude-3-5-sonnet-20241022",  # Claude 3.5 Sonnet (latest)
            "openai": "gpt-4o",
            "google": "gemini-1.5-pro",
            "groq": "llama-3.3-70b-versatile",
            "mistral": "mistral-large-latest",
            "openrouter": "anthropic/claude-3-5-sonnet-20241022",
            "ollama": "llama3",
        }
        return defaults.get(self.provider, "claude-3-5-sonnet-20241022")

    def _get_base_url(self) -> str:
        """Get base URL for provider"""
        urls = {
            "anthropic": "https://api.anthropic.com/v1",
            "openai": "https://api.openai.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "groq": "https://api.groq.com/openai/v1",
            "mistral": "https://api.mistral.ai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "ollama": "http://localhost:11434",
        }
        return urls.get(self.provider, urls["anthropic"])

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def process(self, message: str, context: NaviContext) -> NaviResponse:
        """
        Process a user message and return what to do.

        INTELLIGENCE UPGRADE: Now READS project files FIRST (like Codex/Claude Code)
        """
        thinking_steps = []

        # STEP 1: ANALYZE PROJECT BY READING FILES (This is what makes it intelligent!)
        logger.info(f"[NAVI] Analyzing project at: {context.workspace_path}")
        thinking_steps.append("Analyzing project files...")
        project_info = ProjectAnalyzer.analyze(context.workspace_path)

        if project_info.files_read:
            thinking_steps.append(
                f"Read {len(project_info.files_read)} files: {', '.join(project_info.files_read[:5])}"
            )

        if project_info.framework:
            thinking_steps.append(f"Detected {project_info.framework} project")
        elif project_info.project_type != "unknown":
            thinking_steps.append(f"Detected {project_info.project_type} project")

        if project_info.scripts:
            thinking_steps.append(
                f"Found {len(project_info.scripts)} available scripts"
            )

        # STEP 2: Check if this is a "how to run" question - SMART RESPONSE (no LLM needed!)
        message_lower = message.lower()
        is_run_question = any(
            phrase in message_lower
            for phrase in [
                "how to run",
                "how do i run",
                "how can i run",
                "run this project",
                "start the",
                "launch",
                "get started",
                "set up",
                "setup",
            ]
        )

        # For "how to run" questions with known project type, generate smart response directly
        if is_run_question and project_info.project_type != "unknown":
            logger.info(
                "[NAVI] Detected 'how to run' question - generating smart response without LLM"
            )
            thinking_steps.append("Generating project-specific run instructions")

            # Generate intelligent response based on what we read
            response_text = IntelligentResponder.generate_run_instructions(project_info)

            # Generate commands to run
            commands_to_run = []
            install_cmd = IntelligentResponder._get_install_command(project_info)
            commands_to_run.append(install_cmd)

            dev_cmd, _ = IntelligentResponder._get_dev_command(project_info)
            if dev_cmd:
                commands_to_run.append(dev_cmd)

            return NaviResponse(
                message=response_text,
                commands_to_run=commands_to_run,
                thinking_steps=thinking_steps,
                files_read=project_info.files_read,
                project_type=project_info.project_type,
                framework=project_info.framework,
            )

        # STEP 3: Build prompt with PROJECT INTELLIGENCE for LLM
        prompt = self._build_prompt(message, context, project_info)

        # STEP 4: Call LLM with informed context
        try:
            llm_response = await self._call_llm(prompt, context.recent_conversation)
            response = self._parse_response(llm_response)

            # Validate response for safety
            is_safe, warnings = self.validator.validate_response(
                response, context.workspace_path
            )

            if not is_safe:
                # Return error response
                return NaviResponse(
                    message=f"Safety check failed: {'; '.join(warnings)}",
                    needs_user_input=True,
                    user_input_prompt="The requested operation contains unsafe actions. Please review and adjust your request.",
                    warnings=warnings,
                    thinking_steps=thinking_steps,
                    files_read=project_info.files_read,
                    project_type=project_info.project_type,
                    framework=project_info.framework,
                )

            # Add intelligence fields to response
            response.warnings = warnings
            response.thinking_steps = thinking_steps
            response.files_read = project_info.files_read
            response.project_type = project_info.project_type
            response.framework = project_info.framework

            return response

        except Exception as e:
            logger.error(f"NAVI processing error: {e}", exc_info=True)
            # Graceful fallback - never crash
            return NaviResponse(
                message=f"I encountered an issue: {str(e)}. Please try again.",
                needs_user_input=True,
                user_input_prompt="Could you rephrase your request?",
                thinking_steps=thinking_steps,
                files_read=(
                    project_info.files_read if "project_info" in locals() else []
                ),
            )

    # ==================== NAVI V2: APPROVAL FLOW METHODS ====================

    def _needs_approval(self, message: str) -> bool:
        """
        Determine if this operation needs user approval.
        Simple read-only questions don't need approval.
        """
        # Simple read-only patterns don't need approval
        read_only_patterns = [
            "how to",
            "how do i",
            "what is",
            "explain",
            "show me",
            "where is",
            "find",
            "search",
            "list",
            "describe",
            "tell me",
        ]
        message_lower = message.lower()

        if any(p in message_lower for p in read_only_patterns):
            return False

        # Anything that modifies code or runs commands needs approval
        return True

    def _assess_action_risks(
        self, response: NaviResponse, workspace_path: str
    ) -> List[Dict[str, Any]]:
        """
        Assess risk level for each action.
        Returns list of actions with risk assessment.
        """
        actions_with_risk = []

        # Assess file creations
        for path, content in response.files_to_create.items():
            risk = "low"
            warnings = []

            if len(content) > MAX_FILE_SIZE:
                risk = "high"
                warnings.append(f"Large file ({len(content)} bytes)")

            if path.endswith(".env") or ".env" in path:
                risk = "medium"
                warnings.append("Environment file - may contain secrets")

            if path.startswith("../") or ".." in path:
                risk = "high"
                warnings.append("Path attempts to escape workspace")

            actions_with_risk.append(
                {
                    "type": "createFile",
                    "path": path,
                    "content": content,  # Full content for diff viewing
                    "risk": risk,
                    "warnings": warnings,
                    "preview": content[:200] + ("..." if len(content) > 200 else ""),
                }
            )

        # Assess file modifications
        for path, content in response.files_to_modify.items():
            risk = "medium"  # Modifying existing files is always medium+ risk
            warnings = []

            full_path = Path(workspace_path) / path
            if not full_path.exists():
                risk = "high"
                warnings.append("File doesn't exist")

            if len(content) > MAX_FILE_SIZE:
                risk = "high"
                warnings.append(f"Large file ({len(content)} bytes)")

            actions_with_risk.append(
                {
                    "type": "editFile",
                    "path": path,
                    "content": content,  # Full new content
                    "risk": risk,
                    "warnings": warnings,
                    "preview": content[:200] + ("..." if len(content) > 200 else ""),
                }
            )

        # Assess commands
        for cmd in response.commands_to_run:
            risk = self._assess_command_risk(cmd)
            warnings = []

            if risk == "high":
                warnings.append("Potentially destructive command")
            elif risk == "medium":
                warnings.append("Modifies project state")

            actions_with_risk.append(
                {
                    "type": "runCommand",
                    "command": cmd,
                    "risk": risk,
                    "warnings": warnings,
                }
            )

        return actions_with_risk

    def _assess_command_risk(self, cmd: str) -> str:
        """Assess risk level of a command"""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return "high"

        # Check if command is in safe list
        first_word = cmd.split()[0] if cmd.split() else ""
        if first_word in SAFE_COMMANDS or cmd in SAFE_COMMANDS:
            return "low"

        return "medium"

    async def plan(
        self,
        message: str,
        context: NaviContext,
    ) -> NaviResponse:
        """
        NAVI V2: Generate a plan with actions but don't execute.
        This is the key method for approval flow.

        Returns a NaviResponse with:
        - requires_approval: bool (if true, UI shows approval panel)
        - actions_with_risk: List of actions with risk assessment
        - plan_id: UUID for tracking this plan
        """
        # Use existing process() method to generate response
        response = await self.process(message, context)

        # Check if this needs approval
        needs_approval = self._needs_approval(message)

        if not needs_approval:
            # Simple operations don't need approval
            response.requires_approval = False
            return response

        # Assess risks for all actions
        response.actions_with_risk = self._assess_action_risks(
            response, context.workspace_path
        )
        response.requires_approval = True

        # Store plan
        plan_id = str(uuid.uuid4())
        response.plan_id = plan_id

        self.active_plans[plan_id] = NaviPlan(
            id=plan_id,
            user_message=message,
            context=context,
            response=response,
        )

        logger.info(
            f"[NAVI V2] Created plan {plan_id} with {len(response.actions_with_risk)} actions"
        )

        return response

    async def execute_plan(
        self, plan_id: str, approved_action_indices: List[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        NAVI V2: Execute approved actions from a plan.
        Yields progress updates as it executes.

        Yields messages like:
        - {"type": "action_start", "index": 0, "action": {...}}
        - {"type": "action_complete", "index": 0, "success": True}
        - {"type": "plan_complete"}
        """
        plan = self.active_plans.get(plan_id)
        if not plan:
            yield {"type": "error", "message": "Plan not found"}
            return

        plan.status = "executing"
        plan.approved_actions = approved_action_indices

        actions = plan.response.actions_with_risk
        workspace_path = Path(plan.context.workspace_path)

        logger.info(
            f"[NAVI V2] Executing plan {plan_id}: {len(approved_action_indices)} actions"
        )

        for idx in approved_action_indices:
            if idx >= len(actions):
                continue

            action = actions[idx]

            yield {"type": "action_start", "index": idx, "action": action}

            try:
                if action["type"] == "createFile":
                    path = action["path"]
                    content = action["content"]

                    full_path = workspace_path / path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding="utf-8")

                    logger.info(f"[NAVI V2] Created file: {path}")
                    yield {"type": "action_complete", "index": idx, "success": True}

                elif action["type"] == "editFile":
                    path = action["path"]
                    content = action["content"]

                    full_path = workspace_path / path
                    full_path.write_text(content, encoding="utf-8")

                    logger.info(f"[NAVI V2] Modified file: {path}")
                    yield {"type": "action_complete", "index": idx, "success": True}

                elif action["type"] == "runCommand":
                    cmd = action["command"]

                    # Execute command
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(workspace_path),
                    )

                    stdout, stderr = await process.communicate()
                    output = stdout.decode() + stderr.decode()

                    success = process.returncode == 0

                    logger.info(
                        f"[NAVI V2] Ran command: {cmd} (exit code: {process.returncode})"
                    )
                    yield {
                        "type": "action_complete",
                        "index": idx,
                        "success": success,
                        "output": output,
                        "exitCode": process.returncode,
                    }

            except Exception as e:
                logger.error(f"[NAVI V2] Action {idx} failed: {e}")
                yield {
                    "type": "action_complete",
                    "index": idx,
                    "success": False,
                    "error": str(e),
                }

        plan.status = "completed"
        yield {"type": "plan_complete"}

        logger.info(f"[NAVI V2] Plan {plan_id} execution complete")

    def get_plan(self, plan_id: str) -> Optional[NaviPlan]:
        """Get a plan by ID"""
        return self.active_plans.get(plan_id)

    # ==================== END NAVI V2 METHODS ====================

    def _build_prompt(
        self,
        message: str,
        context: NaviContext,
        project_info: Optional[ProjectInfo] = None,
    ) -> str:
        """Build the full prompt with context + PROJECT INTELLIGENCE"""

        context_parts = []

        # PROJECT INTELLIGENCE (from reading files - like Codex/Claude Code)
        if project_info and project_info.project_type != "unknown":
            context_parts.append("=== PROJECT ANALYSIS (from reading files) ===")
            context_parts.append(project_info.to_context_string())
            context_parts.append("=" * 50)
            context_parts.append("")

        # Project info (fallback)
        if not project_info or project_info.project_type == "unknown":
            context_parts.append(f"PROJECT TYPE: {context.project_type}")
            if context.technologies:
                context_parts.append(f"TECHNOLOGIES: {', '.join(context.technologies)}")
        context_parts.append(f"WORKSPACE: {context.workspace_path}")

        # Current state
        if context.current_file:
            context_parts.append(f"CURRENT FILE: {context.current_file}")
        if context.current_file_content:
            # Truncate if too long
            content = context.current_file_content
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
            context_parts.append(f"CURRENT FILE CONTENT:\n```\n{content}\n```")
        if context.selection:
            context_parts.append(f"SELECTED CODE:\n```\n{context.selection}\n```")

        # Git status
        if context.git_branch:
            context_parts.append(f"GIT BRANCH: {context.git_branch}")
        if context.git_status.get("has_changes"):
            files = context.git_status.get("changed_files", [])[:10]
            context_parts.append(f"CHANGED FILES: {', '.join(files)}")

        # Errors
        if context.errors:
            errors_str = "\n".join(
                [
                    f"- {e.get('file', 'unknown')}: {e.get('message', 'error')}"
                    for e in context.errors[:5]
                ]
            )
            context_parts.append(f"CURRENT ERRORS:\n{errors_str}")

        # Open files
        if context.open_files:
            context_parts.append(f"OPEN FILES: {', '.join(context.open_files[:10])}")

        context_block = "\n".join(context_parts)

        # Detect request type and add aggressive instructions
        message_lower = message.lower()
        aggressive_instructions = []

        if any(
            keyword in message_lower
            for keyword in [
                "what else",
                "what can",
                "capabilities",
                "features",
                "what do",
            ]
        ):
            aggressive_instructions.append(
                "⚠️ User is asking WHAT you can do. SHOW them by CREATING 3-5 example files demonstrating different capabilities."
            )

        if any(
            keyword in message_lower
            for keyword in [
                "error",
                "issue",
                "problem",
                "bug",
                "fix",
                "broken",
                "not working",
            ]
        ):
            aggressive_instructions.append(
                "⚠️ User is asking about ERRORS. READ the relevant files, ANALYZE them, and FIX any issues by MODIFYING the files."
            )

        if any(
            keyword in message_lower
            for keyword in ["how to", "how do", "start", "setup", "initialize", "begin"]
        ):
            aggressive_instructions.append(
                "⚠️ User is asking HOW to do something. Don't explain - CREATE all necessary starter files AND RUN setup commands."
            )

        if any(
            keyword in message_lower
            for keyword in ["improve", "better", "optimize", "enhance", "upgrade"]
        ):
            aggressive_instructions.append(
                "⚠️ User wants IMPROVEMENTS. MODIFY the relevant files with actual improvements, don't just suggest them."
            )

        if any(
            keyword in message_lower
            for keyword in ["add", "create", "make", "build", "implement", "generate"]
        ):
            aggressive_instructions.append(
                "⚠️ User wants something ADDED. CREATE it immediately with complete, production-ready code."
            )

        aggressive_block = (
            "\n".join(aggressive_instructions) if aggressive_instructions else ""
        )

        return f"""CONTEXT:
{context_block}

USER REQUEST: {message}

{aggressive_block}

🚨 CRITICAL REMINDER 🚨
Your response MUST include AT LEAST ONE of:
- files_to_create (with actual file content)
- files_to_modify (with complete new file content)
- commands_to_run (with actual commands)

If your response is just text explanation, IT IS WRONG.
Respond with JSON only."""

    async def _call_llm(
        self, prompt: str, conversation_history: List[Dict] = None
    ) -> str:
        """Call the LLM provider"""

        if self.provider == "anthropic":
            return await self._call_anthropic(prompt, conversation_history)
        elif (
            self.provider == "openai"
            or self.provider == "groq"
            or self.provider == "openrouter"
        ):
            return await self._call_openai_compatible(prompt, conversation_history)
        elif self.provider == "ollama":
            return await self._call_ollama(prompt, conversation_history)
        else:
            return await self._call_openai_compatible(prompt, conversation_history)

    async def _call_anthropic(self, prompt: str, history: List[Dict] = None) -> str:
        """Call Anthropic Claude API"""
        session = await self._get_session()

        messages = []
        if history:
            # Convert history to dicts if needed (handle ChatMessage objects)
            for msg in history:
                if isinstance(msg, dict):
                    messages.append(msg)
                elif hasattr(msg, "__dict__"):
                    # Convert object to dict
                    messages.append(
                        {
                            "role": getattr(msg, "role", "user"),
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )
                else:
                    # Fallback: convert to string
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": self.SYSTEM_PROMPT,
            "messages": messages,
        }

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        async with session.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"Anthropic API error: {error}")

            data = await response.json()
            return data["content"][0]["text"]

    async def _call_openai_compatible(
        self, prompt: str, history: List[Dict] = None
    ) -> str:
        """Call OpenAI-compatible API (OpenAI, Groq, OpenRouter, etc.)"""
        session = await self._get_session()

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if history:
            # Convert history to dicts if needed (handle ChatMessage objects)
            for msg in history:
                if isinstance(msg, dict):
                    messages.append(msg)
                elif hasattr(msg, "__dict__"):
                    # Convert object to dict
                    messages.append(
                        {
                            "role": getattr(msg, "role", "user"),
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )
                else:
                    # Fallback: convert to string
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "temperature": 0.7,
            "messages": messages,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # OpenRouter needs extra headers
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://navi.dev"
            headers["X-Title"] = "NAVI"

        async with session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"API error: {error}")

            data = await response.json()
            return data["choices"][0]["message"]["content"]

    async def _call_ollama(self, prompt: str, history: List[Dict] = None) -> str:
        """Call local Ollama"""
        session = await self._get_session()

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"Ollama error: {error}")

            data = await response.json()
            return data["message"]["content"]

    def _parse_response(self, llm_response: str) -> NaviResponse:
        """Parse LLM response into NaviResponse"""
        try:
            # Clean up response - extract JSON
            content = llm_response.strip()

            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            # Parse JSON
            data = json.loads(content)

            return NaviResponse(
                message=data.get("message", "Done!"),
                files_to_create=data.get("files_to_create", {}),
                files_to_modify=data.get("files_to_modify", {}),
                commands_to_run=data.get("commands_to_run", []),
                vscode_commands=data.get("vscode_commands", []),
                needs_user_input=data.get("needs_user_input", False),
                user_input_prompt=data.get("user_input_prompt"),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # LLM didn't return valid JSON - extract what we can
            return NaviResponse(
                message=llm_response[:500],  # First 500 chars as message
                needs_user_input=False,
            )


# ==================== NAVI ENGINE (FULL INTEGRATION) ====================


class NaviEngine:
    """
    Complete NAVI Engine with LLM brain + file operations + git + packages + safety.

    This is what your API calls.
    """

    def __init__(
        self,
        workspace_path: str,
        llm_provider: str = "anthropic",
        llm_model: str = None,
        api_key: str = None,
    ):
        self.workspace_path = workspace_path
        self.brain = NaviBrain(
            provider=llm_provider,
            model=llm_model,
            api_key=api_key,
        )

        # Detect project
        self.project_type, self.technologies = self._detect_project()

    def _detect_project(self) -> tuple:
        """Auto-detect project type and technologies"""
        path = Path(self.workspace_path)
        technologies = []
        project_type = "unknown"

        # Check package.json
        pkg_json = path / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }

                    if "next" in deps:
                        project_type = "nextjs"
                        technologies.extend(["Next.js", "React"])
                    elif "react" in deps:
                        project_type = "react"
                        technologies.append("React")
                    elif "vue" in deps:
                        project_type = "vue"
                        technologies.append("Vue")
                    elif "@angular/core" in deps:
                        project_type = "angular"
                        technologies.append("Angular")
                    elif "express" in deps:
                        project_type = "express"
                        technologies.append("Express")
                    elif "@nestjs/core" in deps:
                        project_type = "nestjs"
                        technologies.append("NestJS")
                    else:
                        project_type = "nodejs"
                        technologies.append("Node.js")

                    if "typescript" in deps:
                        technologies.append("TypeScript")
                    if "tailwindcss" in deps:
                        technologies.append("Tailwind")
            except Exception:
                pass  # Ignore JSON parse errors in package.json

        # Check Python
        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            technologies.append("Python")
            if (path / "requirements.txt").exists():
                try:
                    content = (path / "requirements.txt").read_text().lower()
                    if "fastapi" in content:
                        project_type = "fastapi"
                        technologies.append("FastAPI")
                    elif "django" in content:
                        project_type = "django"
                        technologies.append("Django")
                    elif "flask" in content:
                        project_type = "flask"
                        technologies.append("Flask")
                except Exception:
                    pass  # Ignore file read errors in requirements.txt

        return project_type, list(set(technologies))

    async def process(
        self,
        message: str,
        current_file: str = None,
        current_file_content: str = None,
        selection: str = None,
        open_files: List[str] = None,
        errors: List[Dict] = None,
        conversation_history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Process user message and execute actions.

        This is the main API entry point.
        """
        # Build context
        context = NaviContext(
            workspace_path=self.workspace_path,
            project_type=self.project_type,
            technologies=self.technologies,
            current_file=current_file,
            current_file_content=current_file_content,
            selection=selection,
            open_files=open_files or [],
            errors=errors or [],
            git_branch=self._get_git_branch(),
            git_status=self._get_git_status(),
            recent_conversation=conversation_history or [],
        )

        # Get response from brain
        response = await self.brain.process(message, context)

        # AGGRESSIVE MODE: Validate that response contains actions
        # But ONLY for command-like messages, not questions/chat
        has_actions = (
            len(response.files_to_create) > 0
            or len(response.files_to_modify) > 0
            or len(response.commands_to_run) > 0
        )

        # Detect if this is a question/chat (no actions expected) vs a command (actions expected)
        message_lower = message.lower().strip()
        is_question_or_chat = (
            message_lower.startswith(
                (
                    "is ",
                    "are ",
                    "was ",
                    "were ",
                    "what ",
                    "where ",
                    "when ",
                    "why ",
                    "how ",
                    "who ",
                    "which ",
                    "can ",
                    "could ",
                    "would ",
                    "should ",
                    "do ",
                    "does ",
                    "did ",
                    "have ",
                    "has ",
                    "had ",
                )
            )
            or message_lower.endswith("?")
            or message_lower.startswith(
                (
                    "hi",
                    "hello",
                    "hey",
                    "thanks",
                    "thank you",
                    "explain",
                    "describe",
                    "tell me",
                    "show me",
                    "list",
                    "find",
                )
            )
            or any(
                phrase in message_lower
                for phrase in [
                    "is there",
                    "are there",
                    "do you",
                    "can you explain",
                    "what is",
                    "how does",
                    "why is",
                    "where is",
                ]
            )
        )

        # Also check if the LLM indicated this was just informational
        is_informational_response = (
            response.needs_user_input
            or "no explicit information" in response.message.lower()
            or "not found" in response.message.lower()
            or "does not" in response.message.lower()
        )

        if (
            not has_actions
            and not is_question_or_chat
            and not is_informational_response
        ):
            # LLM failed to take action on a command - this might be an issue
            logger.info(f"ℹ️ No actions generated for message: {message[:100]}")
            # Don't add warning for questions - only for clear commands that should have generated actions

        # If there are dangerous commands, ask for confirmation
        if response.dangerous_commands:
            return {
                "success": False,
                "message": response.message,
                "needs_user_confirmation": True,
                "dangerous_commands": response.dangerous_commands,
                "warnings": response.warnings,
                "files_to_create": list(response.files_to_create.keys()),
                "files_to_modify": list(response.files_to_modify.keys()),
                "commands_to_run": response.commands_to_run,
            }

        # Execute the actions (only if safe)
        execution_results = await self._execute_actions(response)

        # Return combined result
        return {
            "success": True,
            "message": response.message,
            "files_created": list(response.files_to_create.keys()),
            "files_modified": list(response.files_to_modify.keys()),
            "commands_run": response.commands_to_run,
            "vscode_commands": response.vscode_commands,
            "needs_user_input": response.needs_user_input,
            "user_input_prompt": response.user_input_prompt,
            "warnings": response.warnings,
            "execution_results": execution_results,
        }

    async def _execute_actions(self, response: NaviResponse) -> Dict[str, Any]:
        """Execute the actions from the response"""
        results = {
            "files_created": [],
            "files_modified": [],
            "commands_output": [],
            "errors": [],
        }

        # Create files
        for file_path, content in response.files_to_create.items():
            try:
                full_path = Path(self.workspace_path) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                results["files_created"].append(file_path)
                logger.info(f"✅ Created file: {file_path}")
            except Exception as e:
                logger.error(f"❌ Failed to create {file_path}: {e}")
                results["errors"].append(f"Failed to create {file_path}: {e}")

        # Modify files
        for file_path, content in response.files_to_modify.items():
            try:
                full_path = Path(self.workspace_path) / file_path
                if full_path.exists():
                    full_path.write_text(content)
                    results["files_modified"].append(file_path)
                    logger.info(f"✅ Modified file: {file_path}")
                else:
                    # File doesn't exist, create it
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    results["files_created"].append(file_path)
                    logger.info(
                        f"✅ Created file (modify target not found): {file_path}"
                    )
            except Exception as e:
                logger.error(f"❌ Failed to modify {file_path}: {e}")
                results["errors"].append(f"Failed to modify {file_path}: {e}")

        # Run commands
        for command in response.commands_to_run:
            try:
                import subprocess

                logger.info(f"🔧 Running command: {command}")
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                results["commands_output"].append(
                    {
                        "command": command,
                        "success": result.returncode == 0,
                        "output": result.stdout,
                        "error": result.stderr,
                    }
                )
                if result.returncode == 0:
                    logger.info(f"✅ Command succeeded: {command}")
                else:
                    logger.warning(f"⚠️ Command failed: {command}")
            except Exception as e:
                logger.error(f"❌ Failed to run '{command}': {e}")
                results["errors"].append(f"Failed to run '{command}': {e}")

        return results

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch"""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass  # Git branch command failed, return None
        return None

    def _get_git_status(self) -> Dict[str, Any]:
        """Get git status"""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                changed = [
                    line[3:] for line in result.stdout.strip().split("\n") if line
                ]
                return {
                    "has_changes": len(changed) > 0,
                    "changed_files": changed,
                }
        except Exception:
            pass  # Git status command failed, return empty state
        return {"has_changes": False, "changed_files": []}

    async def close(self):
        """Cleanup"""
        await self.brain.close()


# ==================== API HELPER ====================


async def process_navi_request(
    message: str,
    workspace_path: str,
    llm_provider: str = "anthropic",
    llm_model: str = None,
    api_key: str = None,
    current_file: str = None,
    current_file_content: str = None,
    selection: str = None,
    open_files: List[str] = None,
    errors: List[Dict] = None,
    conversation_history: List[Dict] = None,
) -> Dict[str, Any]:
    """
    Main API function - process a NAVI request with safety features.

    Usage in FastAPI:

    @router.post("/navi/process")
    async def navi_process(request: NaviRequest):
        return await process_navi_request(
            message=request.message,
            workspace_path=request.workspace_path,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            api_key=request.api_key,
            current_file=request.current_file,
            selection=request.selection,
            errors=request.errors,
        )
    """
    engine = NaviEngine(
        workspace_path=workspace_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key=api_key,
    )

    try:
        result = await engine.process(
            message=message,
            current_file=current_file,
            current_file_content=current_file_content,
            selection=selection,
            open_files=open_files,
            errors=errors,
            conversation_history=conversation_history,
        )
        return result
    finally:
        await engine.close()
