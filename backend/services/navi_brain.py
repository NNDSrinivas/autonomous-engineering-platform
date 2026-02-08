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
from typing import Dict, Any, List, Optional, AsyncGenerator, Sequence, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
import logging
import sys

logger = logging.getLogger(__name__)

DEFAULT_SUPPORT_URL = os.getenv(
    "NAVI_ISSUE_URL",
    os.getenv(
        "NAVI_SUPPORT_URL",
        "https://github.com/navra-labs/autonomous-engineering-platform/issues/new",
    ),
)


class ModelNotAvailableError(RuntimeError):
    """Raised when a requested model is unavailable for the provider."""

    def __init__(self, provider: str, model: str, detail: str = ""):
        super().__init__(f"Model '{model}' is not available for provider '{provider}'.")
        self.provider = provider
        self.model = model
        self.detail = detail


# ==================== MEMORY INTEGRATION ====================
# Lazy-loaded to avoid circular imports
_memory_integration = None


def _get_memory_integration():
    """Lazy-load memory integration to avoid circular imports."""
    global _memory_integration
    if _memory_integration is None:
        try:
            from backend.database.session import get_db
            from backend.services.navi_memory_integration import (
                get_navi_memory_integration,
            )

            # Get database session
            db = next(get_db())
            _memory_integration = get_navi_memory_integration(db)
            logger.info("[NAVI] Memory integration initialized successfully")
        except Exception as e:
            logger.warning(f"[NAVI] Memory integration not available: {e}")
            _memory_integration = None
    return _memory_integration


async def _get_memory_context_async(
    query: str,
    user_id: Optional[int],
    org_id: Optional[int],
    workspace_path: Optional[str],
    current_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get memory context for a NAVI request.
    Returns empty dict if memory system is not available.
    """
    memory = _get_memory_integration()
    if not memory:
        return {}

    if not user_id:
        return {}

    try:
        context = await memory.get_memory_context(
            query=query,
            user_id=user_id,
            org_id=org_id,
            workspace_path=workspace_path,
            current_file=current_file,
        )
        return context
    except Exception as e:
        logger.warning(f"[NAVI] Failed to get memory context: {e}")
        return {}


def _enhance_system_prompt_with_memory(
    base_prompt: str,
    user_id: Optional[int],
    org_id: Optional[int],
) -> str:
    """
    Enhance the system prompt with user personalization.
    Returns base prompt if memory system is not available.
    """
    memory = _get_memory_integration()
    if not memory:
        return base_prompt

    if not user_id:
        return base_prompt

    try:
        return memory.enhance_system_prompt(base_prompt, user_id, org_id)
    except Exception as e:
        logger.warning(f"[NAVI] Failed to enhance system prompt: {e}")
        return base_prompt


def _detect_language(file_path: Optional[str]) -> Optional[str]:
    """Detect programming language from file extension."""
    if not file_path:
        return None

    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".vue": "vue",
        ".svelte": "svelte",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
    }

    ext = Path(file_path).suffix.lower()
    return ext_to_lang.get(ext)


async def _store_interaction_async(
    user_id: Optional[int],
    conversation_id: Optional[str],
    user_message: str,
    assistant_response: str,
    org_id: Optional[int] = None,
    workspace_path: Optional[str] = None,
    current_file: Optional[str] = None,
) -> None:
    """
    Store an interaction for future learning.
    Silently fails if memory system is not available.
    """
    memory = _get_memory_integration()
    if not memory:
        return

    if not user_id:
        return

    try:
        # Create a conversation_id if not provided
        from uuid import UUID

        conv_id = UUID(conversation_id) if conversation_id else None

        if not conv_id:
            # Create a new conversation
            conv_id = await memory.create_conversation(
                user_id=user_id,
                org_id=org_id,
                workspace_path=workspace_path,
            )

        await memory.store_interaction(
            user_id=user_id,
            conversation_id=conv_id,
            user_message=user_message,
            assistant_response=assistant_response,
            org_id=org_id,
            workspace_path=workspace_path,
            file_path=current_file,
        )
        logger.debug(f"[NAVI] Stored interaction for user {user_id}")
    except Exception as e:
        logger.warning(f"[NAVI] Failed to store interaction: {e}")


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


# ==================== DYNAMIC CONFIGURATION ====================


class NaviConfig:
    """
    Centralized configuration for NAVI - NO HARDCODED VALUES.
    All configurable values should be read from environment or detected dynamically.
    """

    # Port Configuration - can be overridden by environment
    DEFAULT_PORT_RANGE_START = int(os.getenv("NAVI_PORT_RANGE_START", "3000"))
    DEFAULT_PORT_RANGE_END = int(os.getenv("NAVI_PORT_RANGE_END", "3100"))
    COMMON_DEV_PORTS = [
        int(p)
        for p in os.getenv(
            "NAVI_COMMON_PORTS",
            "3000,3001,3002,3003,3004,3005,4000,5000,5173,5174,8000,8080,8081",
        ).split(",")
    ]

    # Timeouts - can be overridden by environment (in milliseconds)
    COMMAND_TIMEOUT = int(os.getenv("NAVI_COMMAND_TIMEOUT", "120000"))  # 2 minutes
    INSTALL_TIMEOUT = int(os.getenv("NAVI_INSTALL_TIMEOUT", "300000"))  # 5 minutes
    LLM_TIMEOUT = int(os.getenv("NAVI_LLM_TIMEOUT", "120000"))  # 2 minutes

    # Content limits - can be overridden by environment
    MAX_CONTENT_DISPLAY = int(os.getenv("NAVI_MAX_CONTENT_DISPLAY", "5000"))
    MAX_ERROR_FILE_CONTENT = int(os.getenv("NAVI_MAX_ERROR_FILE_CONTENT", "3000"))

    # Backend URLs - should come from environment
    DEFAULT_BACKEND_URL = os.getenv("NAVI_BACKEND_URL", "http://localhost:8002")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # LLM Model defaults - can be overridden by environment
    DEFAULT_MODELS = {
        "anthropic": os.getenv("NAVI_ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        "openai": os.getenv("NAVI_OPENAI_MODEL", "gpt-4o"),
        "google": os.getenv("NAVI_GOOGLE_MODEL", "gemini-1.5-pro"),
        "groq": os.getenv("NAVI_GROQ_MODEL", "llama-3.3-70b-versatile"),
        "mistral": os.getenv("NAVI_MISTRAL_MODEL", "mistral-large-latest"),
        "openrouter": os.getenv(
            "NAVI_OPENROUTER_MODEL", "anthropic/claude-3-5-sonnet-20241022"
        ),
        "ollama": os.getenv("NAVI_OLLAMA_MODEL", "llama3"),
    }

    @classmethod
    def get_preferred_port(cls, project_info: Optional["ProjectInfo"] = None) -> int:
        """
        Dynamically determine preferred port based on project type.
        Instead of hardcoding 3000, detect from project configuration.
        """
        if project_info:
            # Check project scripts for port hints
            scripts = project_info.scripts or {}
            for script_name, script_cmd in scripts.items():
                if script_name in ("dev", "start", "serve"):
                    # Look for port in script
                    port_match = re.search(
                        r"-p\s*(\d+)|--port\s*(\d+)|PORT=(\d+)|:(\d+)", script_cmd
                    )
                    if port_match:
                        for group in port_match.groups():
                            if group:
                                return int(group)

            # Framework-specific defaults
            framework = (project_info.framework or "").lower()
            project_type = (project_info.project_type or "").lower()

            if "next" in framework or "next" in project_type:
                return 3000
            elif "vite" in framework or "vite" in str(project_info.dependencies):
                return 5173
            elif "vue" in framework and "vite" not in str(project_info.dependencies):
                return 8080
            elif "angular" in framework:
                return 4200
            elif "django" in framework or "django" in project_type:
                return 8000
            elif "flask" in framework or "flask" in project_type:
                return 5000
            elif "fastapi" in framework or "fastapi" in project_type:
                return 8000
            elif "express" in framework or "express" in project_type:
                return 3000
            elif "rails" in framework or "rails" in project_type:
                return 3000

        # Fall back to environment or default
        return cls.DEFAULT_PORT_RANGE_START

    @classmethod
    def get_package_manager_command(
        cls, action: str, project_info: Optional["ProjectInfo"] = None
    ) -> str:
        """
        Get the correct package manager command based on project detection.
        Instead of assuming npm, detect from lockfiles and config.
        """
        pm = "npm"  # Default fallback

        if project_info:
            pm = project_info.package_manager or "npm"

        commands = {
            "npm": {
                "install": "npm install",
                "install_dev": "npm install --save-dev",
                "add": "npm install",
                "run": "npm run",
                "exec": "npx",
            },
            "yarn": {
                "install": "yarn install",
                "install_dev": "yarn add --dev",
                "add": "yarn add",
                "run": "yarn",
                "exec": "yarn",
            },
            "pnpm": {
                "install": "pnpm install",
                "install_dev": "pnpm add -D",
                "add": "pnpm add",
                "run": "pnpm",
                "exec": "pnpm exec",
            },
            "bun": {
                "install": "bun install",
                "install_dev": "bun add -d",
                "add": "bun add",
                "run": "bun run",
                "exec": "bunx",
            },
        }

        return commands.get(pm, commands["npm"]).get(action, f"{pm} {action}")

    @classmethod
    def get_python_package_manager(cls, workspace_path: str) -> str:
        """
        Detect Python package manager from project files.
        Instead of assuming pip, detect from pyproject.toml, Pipfile, etc.
        """
        workspace = Path(workspace_path) if workspace_path else Path.cwd()

        # Check for Poetry
        if (workspace / "poetry.lock").exists() or (
            (workspace / "pyproject.toml").exists()
            and "[tool.poetry]" in (workspace / "pyproject.toml").read_text()
        ):
            return "poetry"

        # Check for Pipenv
        if (workspace / "Pipfile").exists() or (workspace / "Pipfile.lock").exists():
            return "pipenv"

        # Check for Conda
        if (workspace / "environment.yml").exists() or (
            workspace / "environment.yaml"
        ).exists():
            return "conda"

        # Check for uv (fast Python package manager)
        if (workspace / "uv.lock").exists():
            return "uv"

        # Default to pip
        return "pip"

    @classmethod
    def get_python_install_command(cls, workspace_path: str) -> str:
        """Get the correct Python install command based on detected package manager."""
        pm = cls.get_python_package_manager(workspace_path)

        commands = {
            "poetry": "poetry install",
            "pipenv": "pipenv install",
            "conda": "conda env create -f environment.yml",
            "uv": "uv pip install -r requirements.txt",
            "pip": "pip install -r requirements.txt",
        }

        return commands.get(pm, "pip install -r requirements.txt")


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

    # Source files content (for detailed responses like Copilot)
    source_files: Dict[str, str] = field(default_factory=dict)

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

        parts.append(f"FILES ANALYZED: {', '.join(self.files_read[:15])}")

        # Include actual source file contents for detailed responses
        if self.source_files:
            parts.append("\n=== SOURCE FILES (for detailed analysis) ===")
            for file_path, content in list(self.source_files.items())[:10]:
                parts.append(f"\n--- {file_path} ---")
                # Include first ~100 lines or 3000 chars
                truncated = content[:3000]
                if len(content) > 3000:
                    truncated += "\n... (truncated)"
                parts.append(truncated)

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
    def get_important_files_count(cls, workspace_path: str) -> int:
        """
        Dynamically determine how many files to read based on workspace size.
        Smaller projects get deeper analysis, larger projects get focused analysis.

        Like Copilot, we aim to read enough files to give comprehensive context.
        """
        workspace = Path(workspace_path)

        # Count total source files in key directories
        total_files = 0
        SOURCE_DIRS = [
            "pages",
            "app",
            "src/pages",
            "src/app",
            "components",
            "src/components",
            "utils",
            "lib",
            "hooks",
            "styles",
        ]
        SOURCE_EXTENSIONS = {
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".py",
            ".go",
            ".rs",
            ".java",
            ".css",
        }

        for dir_name in SOURCE_DIRS:
            dir_path = workspace / dir_name
            if dir_path.exists() and dir_path.is_dir():
                try:
                    for file_path in dir_path.iterdir():
                        if (
                            file_path.is_file()
                            and file_path.suffix in SOURCE_EXTENSIONS
                        ):
                            total_files += 1
                except Exception:
                    pass

        # Scale file count: aim for comprehensive coverage like Copilot
        # Config files (package.json, etc.) are read separately, so add ~3 for those
        config_files = 3

        if total_files <= 10:
            return total_files + config_files  # Read all files if small project
        elif total_files <= 25:
            return 12 + config_files  # Medium project - read most files
        elif total_files <= 50:
            return 10 + config_files  # Larger project
        else:
            return 8 + config_files  # Very large project, focus on key files

    @classmethod
    def analyze_source_files(
        cls, workspace_path: str, max_files: int = 10, max_file_size: int = 5000
    ) -> Dict[str, str]:
        """
        Read actual source files from key directories to provide detailed context.
        This is what makes responses like GitHub Copilot - we READ the actual code.

        Returns a dict of {relative_path: file_content (truncated)}
        """
        workspace = Path(workspace_path)
        source_files: Dict[str, str] = {}

        # Key directories to scan for source files
        SOURCE_DIRS = [
            "pages",  # Next.js pages
            "app",  # Next.js 13+ app router
            "src/pages",  # Alternative pages location
            "src/app",  # Alternative app location
            "components",  # React components
            "src/components",  # Alternative components
            "utils",  # Utility functions
            "src/utils",  # Alternative utils
            "lib",  # Library code
            "src/lib",  # Alternative lib
            "hooks",  # React hooks
            "src/hooks",  # Alternative hooks
            "services",  # Service layer
            "src/services",  # Alternative services
            "api",  # API routes
            "src/api",  # Alternative API
        ]

        # File extensions to read
        SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".py", ".go", ".rs", ".java"}

        files_found = 0

        for dir_name in SOURCE_DIRS:
            dir_path = workspace / dir_name
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            # Get all source files in this directory (non-recursive for now)
            try:
                for file_path in sorted(dir_path.iterdir()):
                    if files_found >= max_files:
                        break

                    if not file_path.is_file():
                        continue

                    if file_path.suffix not in SOURCE_EXTENSIONS:
                        continue

                    # Skip test files and config files
                    if ".test." in file_path.name or ".spec." in file_path.name:
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        # Truncate large files
                        if len(content) > max_file_size:
                            content = content[:max_file_size] + "\n\n... (truncated)"

                        relative_path = str(file_path.relative_to(workspace))
                        source_files[relative_path] = content
                        files_found += 1
                        logger.debug(
                            f"[ProjectAnalyzer] Read source file: {relative_path}"
                        )
                    except Exception as e:
                        logger.debug(f"Could not read {file_path}: {e}")

            except Exception as e:
                logger.debug(f"Could not scan {dir_name}: {e}")

        logger.info(
            f"[ProjectAnalyzer] Read {len(source_files)} source files for context"
        )
        return source_files

    @classmethod
    async def analyze_source_files_streaming(
        cls,
        workspace_path: str,
        max_files: int = 15,
        max_file_size: int = 5000,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async version that yields events as each file is read.

        This enables real-time activity display like GitHub Copilot:
        - Shows each file being read as it happens
        - Yields {activity: {...}} events for frontend display
        - Finally yields {files: {...}} with all file contents

        Usage:
            async for event in ProjectAnalyzer.analyze_source_files_streaming(workspace):
                if "activity" in event:
                    yield event  # Forward to SSE
                elif "files" in event:
                    source_files = event["files"]
        """
        workspace = Path(workspace_path)
        source_files: Dict[str, str] = {}
        files_found = 0

        # PHASE 1: Read important config files first (like Copilot does)
        # README.md is critical for understanding project purpose and name
        CONFIG_FILES = [
            "package.json",
            "README.md",  # CRITICAL: Contains project name and description
            "readme.md",  # Alternative casing
            "next.config.js",
            "next.config.mjs",
            "tsconfig.json",
            "vite.config.js",
            "vite.config.ts",
            ".env.example",
        ]

        for config_file in CONFIG_FILES:
            if files_found >= max_files:
                break
            config_path = workspace / config_file
            if config_path.exists() and config_path.is_file():
                try:
                    relative_path = config_file

                    # Emit activity BEFORE reading
                    yield {
                        "activity": {
                            "kind": "read",
                            "label": "Reading",
                            "detail": relative_path,
                            "filePath": relative_path,
                            "status": "running",
                        }
                    }
                    await asyncio.sleep(0.01)

                    content = config_path.read_text(encoding="utf-8", errors="ignore")
                    if len(content) > max_file_size:
                        content = content[:max_file_size] + "\n\n... (truncated)"
                    source_files[relative_path] = content
                    files_found += 1

                    # Emit activity AFTER reading
                    yield {
                        "activity": {
                            "kind": "read",
                            "label": "Read",
                            "detail": relative_path,
                            "filePath": relative_path,
                            "status": "done",
                        }
                    }
                    logger.debug(f"[ProjectAnalyzer] Read config file: {relative_path}")
                except Exception as e:
                    logger.debug(f"Could not read config {config_file}: {e}")

        # PHASE 2: Key directories to scan for source files
        SOURCE_DIRS = [
            "pages",  # Next.js pages
            "app",  # Next.js 13+ app router
            "src/pages",  # Alternative pages location
            "src/app",  # Alternative app location
            "components",  # React components
            "src/components",  # Alternative components
            "utils",  # Utility functions
            "src/utils",  # Alternative utils
            "lib",  # Library code
            "src/lib",  # Alternative lib
            "hooks",  # React hooks
            "src/hooks",  # Alternative hooks
            "services",  # Service layer
            "src/services",  # Alternative services
            "api",  # API routes
            "src/api",  # Alternative API
            "styles",  # CSS/styles directory
            "src/styles",  # Alternative styles
        ]

        # File extensions to read (including CSS for styling context)
        SOURCE_EXTENSIONS = {
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".py",
            ".go",
            ".rs",
            ".java",
            ".css",
        }

        for dir_name in SOURCE_DIRS:
            dir_path = workspace / dir_name
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            try:
                for file_path in sorted(dir_path.iterdir()):
                    if files_found >= max_files:
                        break

                    if not file_path.is_file():
                        continue

                    if file_path.suffix not in SOURCE_EXTENSIONS:
                        continue

                    # Skip test files and config files
                    if ".test." in file_path.name or ".spec." in file_path.name:
                        continue

                    try:
                        relative_path = str(file_path.relative_to(workspace))

                        # Emit activity BEFORE reading (shows "Reading...")
                        yield {
                            "activity": {
                                "kind": "read",
                                "label": "Reading",
                                "detail": relative_path,
                                "filePath": relative_path,
                                "status": "running",
                            }
                        }

                        # Small delay to ensure UI updates
                        await asyncio.sleep(0.01)

                        # Actually read the file
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if len(content) > max_file_size:
                            content = content[:max_file_size] + "\n\n... (truncated)"

                        source_files[relative_path] = content
                        files_found += 1

                        # Emit activity AFTER reading (shows "Read" with checkmark)
                        yield {
                            "activity": {
                                "kind": "read",
                                "label": "Read",
                                "detail": relative_path,
                                "filePath": relative_path,
                                "status": "done",
                            }
                        }

                        logger.debug(
                            f"[ProjectAnalyzer] Read source file: {relative_path}"
                        )

                    except Exception as e:
                        logger.debug(f"Could not read {file_path}: {e}")

            except Exception as e:
                logger.debug(f"Could not scan {dir_name}: {e}")

        logger.info(
            f"[ProjectAnalyzer] Streamed {len(source_files)} source files for context"
        )

        # Yield the final files dict
        yield {"files": source_files}

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

    @classmethod
    async def analyze_deep(cls, workspace_path: str) -> Dict[str, Any]:
        """
        Perform DEEP analysis of the entire codebase.
        This reads ALL source files, extracts functions/classes,
        analyzes database schemas, and checks git status.
        """
        try:
            from backend.services.deep_analysis import DeepAnalysisService

            return await DeepAnalysisService.analyze_workspace_deep(workspace_path)
        except ImportError:
            logger.warning("[ProjectAnalyzer] Deep analysis service not available")
            return {"error": "Deep analysis service not available"}
        except Exception as e:
            logger.error(f"[ProjectAnalyzer] Deep analysis failed: {e}")
            return {"error": str(e)}

    @classmethod
    async def find_symbol_in_codebase(
        cls, workspace_path: str, symbol_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find all occurrences of a symbol (function, class, variable) in the codebase.
        """
        try:
            from backend.services.deep_analysis import DeepCodeAnalyzer

            return await DeepCodeAnalyzer.find_symbol(workspace_path, symbol_name)
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"[ProjectAnalyzer] Symbol search failed: {e}")
            return []

    @classmethod
    async def analyze_and_fix_git(
        cls, workspace_path: str, auto_fix: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze git repository for issues and optionally fix them.
        """
        try:
            from backend.services.deep_analysis import GitDebugger

            analysis = await GitDebugger.analyze_repository(workspace_path)

            result = {
                "status": {
                    "branch": analysis.status.branch,
                    "is_detached": analysis.status.is_detached,
                    "conflicts": analysis.status.conflicts,
                    "is_rebasing": analysis.status.is_rebasing,
                    "is_merging": analysis.status.is_merging,
                    "staged": len(analysis.status.staged_files),
                    "unstaged": len(analysis.status.unstaged_files),
                },
                "issues": [],
                "fixes_applied": [],
            }

            for issue in analysis.issues:
                issue_data = {
                    "type": issue.type,
                    "severity": issue.severity,
                    "message": issue.message,
                    "fix_steps": issue.fix_steps,
                }
                result["issues"].append(issue_data)

                # Auto-fix safe issues if requested
                if auto_fix and issue.severity == "error":
                    if issue.type in ["rebase_in_progress", "merge_conflict"]:
                        # Don't auto-fix conflicts - need user input
                        continue
                    fix_result = await GitDebugger.fix_issue(workspace_path, issue.type)
                    if fix_result.get("success"):
                        result["fixes_applied"].append(
                            {
                                "issue": issue.type,
                                "result": fix_result,
                            }
                        )

            return result
        except ImportError:
            return {"error": "Git debugger not available"}
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    async def analyze_and_fix_database(
        cls, workspace_path: str, auto_fix: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze database configuration and issues, optionally fix them.
        """
        try:
            from backend.services.deep_analysis import DatabaseDebugger

            analysis = await DatabaseDebugger.analyze_database(workspace_path)

            result = {
                "type": analysis.database_type,
                "connection": analysis.connection_status,
                "tables": list(analysis.tables.keys()),
                "migrations_count": len(analysis.migrations),
                "issues": analysis.issues,
                "suggestions": analysis.suggestions,
                "fixes_applied": [],
            }

            # Auto-fix safe issues if requested
            if auto_fix:
                for issue in analysis.issues:
                    if issue.get("type") in ["migration", "generate_migration"]:
                        fix_result = await DatabaseDebugger.fix_migration_issues(
                            workspace_path, "generate_migration"
                        )
                        if fix_result.get("success"):
                            result["fixes_applied"].append(
                                {
                                    "issue": issue.get("type"),
                                    "result": fix_result,
                                }
                            )

            return result
        except ImportError:
            return {"error": "Database debugger not available"}
        except Exception as e:
            return {"error": str(e)}

    # ==================== ADVANCED GIT OPERATIONS ====================

    @classmethod
    async def cherry_pick_commit(
        cls,
        workspace_path: str,
        commit_hash: str,
        no_commit: bool = False,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cherry-pick a specific commit into the current branch.

        Args:
            workspace_path: Path to git repository
            commit_hash: Commit hash to cherry-pick
            no_commit: If True, apply changes without committing
            strategy: Merge strategy ("ours" or "theirs")
        """
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.cherry_pick(
                workspace_path, commit_hash, no_commit=no_commit, strategy=strategy
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def cherry_pick_range(
        cls,
        workspace_path: str,
        from_commit: str,
        to_commit: str,
    ) -> Dict[str, Any]:
        """Cherry-pick a range of commits."""
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.cherry_pick_range(
                workspace_path, from_commit, to_commit
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def squash_commits(
        cls,
        workspace_path: str,
        num_commits: int,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Squash the last N commits into one.

        Args:
            workspace_path: Path to git repository
            num_commits: Number of commits to squash
            commit_message: Optional custom commit message
        """
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.squash_commits(
                workspace_path, num_commits, commit_message
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def rebase_branch(
        cls,
        workspace_path: str,
        target_branch: str,
        preserve_merges: bool = False,
    ) -> Dict[str, Any]:
        """Rebase current branch onto target branch."""
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.rebase_onto(
                workspace_path, target_branch, preserve_merges
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def git_bisect(
        cls,
        workspace_path: str,
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Git bisect operations for finding bug-introducing commits.

        Args:
            workspace_path: Path to git repository
            operation: One of "start", "good", "bad", "skip", "reset", "run"
            **kwargs: Additional args (bad_commit, good_commit, test_command)
        """
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            ops = {
                "start": lambda: AdvancedGitOperations.bisect_start(
                    workspace_path,
                    kwargs.get("bad_commit", "HEAD"),
                    kwargs.get("good_commit"),
                ),
                "good": lambda: AdvancedGitOperations.bisect_good(
                    workspace_path, kwargs.get("commit", "")
                ),
                "bad": lambda: AdvancedGitOperations.bisect_bad(
                    workspace_path, kwargs.get("commit", "")
                ),
                "skip": lambda: AdvancedGitOperations.bisect_skip(workspace_path),
                "reset": lambda: AdvancedGitOperations.bisect_reset(workspace_path),
                "log": lambda: AdvancedGitOperations.bisect_log(workspace_path),
                "run": lambda: AdvancedGitOperations.bisect_run(
                    workspace_path, kwargs.get("test_command", "")
                ),
            }

            if operation not in ops:
                return {
                    "success": False,
                    "message": f"Unknown bisect operation: {operation}",
                }

            return await ops[operation]()
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def git_stash(
        cls,
        workspace_path: str,
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Git stash operations.

        Args:
            workspace_path: Path to git repository
            operation: One of "save", "pop", "apply", "list", "drop", "clear", "show", "branch"
            **kwargs: Additional args (message, stash_ref, include_untracked, branch_name)
        """
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            ops = {
                "save": lambda: AdvancedGitOperations.stash_save(
                    workspace_path,
                    message=kwargs.get("message"),
                    include_untracked=kwargs.get("include_untracked", False),
                    keep_index=kwargs.get("keep_index", False),
                ),
                "pop": lambda: AdvancedGitOperations.stash_pop(
                    workspace_path,
                    stash_ref=kwargs.get("stash_ref", "stash@{0}"),
                ),
                "apply": lambda: AdvancedGitOperations.stash_apply(
                    workspace_path,
                    stash_ref=kwargs.get("stash_ref", "stash@{0}"),
                ),
                "list": lambda: AdvancedGitOperations.stash_list(workspace_path),
                "drop": lambda: AdvancedGitOperations.stash_drop(
                    workspace_path,
                    stash_ref=kwargs.get("stash_ref", "stash@{0}"),
                ),
                "clear": lambda: AdvancedGitOperations.stash_clear(workspace_path),
                "show": lambda: AdvancedGitOperations.stash_show(
                    workspace_path,
                    stash_ref=kwargs.get("stash_ref", "stash@{0}"),
                    include_patch=kwargs.get("include_patch", False),
                ),
                "branch": lambda: AdvancedGitOperations.stash_branch(
                    workspace_path,
                    branch_name=kwargs.get("branch_name", "stash-branch"),
                    stash_ref=kwargs.get("stash_ref", "stash@{0}"),
                ),
            }

            if operation not in ops:
                return {
                    "success": False,
                    "message": f"Unknown stash operation: {operation}",
                }

            return await ops[operation]()
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def git_reflog(cls, workspace_path: str, limit: int = 20) -> Dict[str, Any]:
        """Get reflog entries for recovering lost commits."""
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.reflog(workspace_path, limit)
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def git_recover_commit(
        cls,
        workspace_path: str,
        commit_hash: str,
        branch_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recover a lost commit by creating a branch pointing to it."""
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.recover_commit(
                workspace_path, commit_hash, branch_name
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def git_cleanup_merged_branches(
        cls,
        workspace_path: str,
        base_branch: str = "main",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Find and optionally delete branches that have been merged."""
        try:
            from backend.services.deep_analysis import AdvancedGitOperations

            return await AdvancedGitOperations.cleanup_merged_branches(
                workspace_path, base_branch, dry_run
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced git operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ==================== ADVANCED DATABASE OPERATIONS ====================

    @classmethod
    async def database_schema_diff(
        cls,
        workspace_path: str,
        database_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare ORM models with actual database schema."""
        try:
            from backend.services.deep_analysis import AdvancedDatabaseOperations

            return await AdvancedDatabaseOperations.schema_diff(
                workspace_path, database_url
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced database operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def database_migration(
        cls,
        workspace_path: str,
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Database migration operations.

        Args:
            workspace_path: Path to workspace
            operation: One of "generate", "apply", "rollback", "history"
            **kwargs: Additional args (migration_name, target, steps)
        """
        try:
            from backend.services.deep_analysis import AdvancedDatabaseOperations

            ops = {
                "generate": lambda: AdvancedDatabaseOperations.generate_migration(
                    workspace_path,
                    migration_name=kwargs.get("migration_name", "auto_migration"),
                    auto_detect=kwargs.get("auto_detect", True),
                ),
                "apply": lambda: AdvancedDatabaseOperations.apply_migrations(
                    workspace_path,
                    target=kwargs.get("target", "head"),
                ),
                "rollback": lambda: AdvancedDatabaseOperations.rollback_migration(
                    workspace_path,
                    steps=kwargs.get("steps", 1),
                    target_revision=kwargs.get("target_revision"),
                ),
                "history": lambda: AdvancedDatabaseOperations.get_migration_history(
                    workspace_path
                ),
            }

            if operation not in ops:
                return {
                    "success": False,
                    "message": f"Unknown migration operation: {operation}",
                }

            return await ops[operation]()
        except ImportError:
            return {
                "success": False,
                "message": "Advanced database operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def database_seed(
        cls,
        workspace_path: str,
        seed_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run database seeding."""
        try:
            from backend.services.deep_analysis import AdvancedDatabaseOperations

            return await AdvancedDatabaseOperations.seed_database(
                workspace_path, seed_file
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced database operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def database_reset(
        cls,
        workspace_path: str,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """Reset database (drop and recreate). Requires explicit confirmation."""
        try:
            from backend.services.deep_analysis import AdvancedDatabaseOperations

            return await AdvancedDatabaseOperations.reset_database(
                workspace_path, confirm
            )
        except ImportError:
            return {
                "success": False,
                "message": "Advanced database operations not available",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ==================== CODE DEBUGGING OPERATIONS ====================

    @classmethod
    async def analyze_error(
        cls,
        workspace_path: str,
        traceback: Optional[str] = None,
        error_log: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error tracebacks or logs to find root cause and suggestions.

        Args:
            workspace_path: Path to workspace
            traceback: Python or JavaScript traceback string
            error_log: Error log file content
        """
        try:
            from backend.services.deep_analysis import CodeDebugger

            return await CodeDebugger.analyze_errors(
                workspace_path, error_log, traceback
            )
        except ImportError:
            return {"success": False, "message": "Code debugger not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def analyze_error_comprehensive(
        cls,
        workspace_path: str,
        error_output: str,
    ) -> Dict[str, Any]:
        """
        Comprehensive error analysis supporting 15+ languages.

        Supports:
        - Runtime errors (Python, JS/TS, Go, Rust, Java, Kotlin, Swift, C/C++, C#, Ruby, PHP, Scala, Elixir, Haskell, Dart)
        - Compiler errors (GCC, Clang, rustc, javac, tsc, swiftc, dotnet)
        - Linter outputs (ESLint, pylint, mypy, golint, clippy, RuboCop, PHPStan, SwiftLint)
        - Test failures (pytest, Jest, go test, cargo test, JUnit, RSpec, PHPUnit)
        - Build errors (npm, yarn, pip, Cargo, Maven, Gradle, CMake, Make)
        - Memory issues (Valgrind, AddressSanitizer, UBSan)

        Args:
            workspace_path: Path to workspace
            error_output: Any error message, traceback, or compiler output

        Returns:
            Comprehensive analysis with:
            - errors: List of parsed errors with details
            - warnings: List of parsed warnings
            - summary: Statistics by language, category, and file
            - auto_fixes: Suggested automatic fixes
            - suggested_commands: Debugging commands to run
        """
        try:
            from backend.services.comprehensive_debugger import analyze_errors

            return await analyze_errors(error_output, workspace_path)
        except ImportError:
            return {"success": False, "message": "Comprehensive debugger not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def detect_code_issues(
        cls,
        workspace_path: str,
        issue_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Detect code issues including performance, dead code, circular deps, code smells.

        Args:
            workspace_path: Path to workspace
            issue_types: List of issue types to detect.
                        Options: "performance", "dead_code", "circular_deps", "code_smells", "all"
        """
        try:
            from backend.services.deep_analysis import CodeDebugger

            results = {}
            types = issue_types or ["all"]

            if "all" in types or "performance" in types:
                results["performance"] = await CodeDebugger.detect_performance_issues(
                    workspace_path
                )

            if "all" in types or "dead_code" in types:
                results["dead_code"] = await CodeDebugger.detect_dead_code(
                    workspace_path
                )

            if "all" in types or "circular_deps" in types:
                results["circular_deps"] = (
                    await CodeDebugger.detect_circular_dependencies(workspace_path)
                )

            if "all" in types or "code_smells" in types:
                results["code_smells"] = await CodeDebugger.detect_code_smells(
                    workspace_path
                )

            return {"success": True, "results": results}
        except ImportError:
            return {"success": False, "message": "Code debugger not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    async def auto_fix_code_issue(
        cls,
        workspace_path: str,
        file_path: str,
        issue_type: str,
        line_number: int,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Attempt to automatically fix a detected code issue.

        Args:
            workspace_path: Path to workspace
            file_path: Relative path to file with issue
            issue_type: Type of issue (e.g., "empty_catch", "print_statement")
            line_number: Line number of the issue
            dry_run: If True, show fix but don't apply
        """
        try:
            from backend.services.deep_analysis import CodeDebugger

            return await CodeDebugger.auto_fix(
                workspace_path, file_path, issue_type, line_number, dry_run
            )
        except ImportError:
            return {"success": False, "message": "Code debugger not available"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# ==================== PORT MANAGEMENT ====================


@dataclass
class PortStatus:
    """Information about a port's status"""

    port: int
    is_available: bool
    process_name: Optional[str] = None
    process_pid: Optional[int] = None
    process_command: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "is_available": self.is_available,
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "process_command": self.process_command,
        }


class PortManager:
    """
    Intelligent port management for NAVI.
    - Checks port availability before starting servers
    - Detects what process is using a busy port
    - Finds alternative available ports
    - Can kill processes on ports (with user approval)

    All port values come from NaviConfig - NO HARDCODING.
    """

    # Use NaviConfig instead of hardcoded values
    COMMON_DEV_PORTS = NaviConfig.COMMON_DEV_PORTS

    @classmethod
    async def check_port(cls, port: int) -> PortStatus:
        """Check if a port is available and what's using it if not"""
        import socket

        # First, quick socket check
        is_available = True
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", port))
                is_available = result != 0
        except Exception:
            is_available = True

        if is_available:
            return PortStatus(port=port, is_available=True)

        # Port is in use - try to find what's using it
        process_info = await cls._get_process_on_port(port)
        return PortStatus(
            port=port,
            is_available=False,
            process_name=process_info.get("name"),
            process_pid=process_info.get("pid"),
            process_command=process_info.get("command"),
        )

    @classmethod
    async def _get_process_on_port(cls, port: int) -> Dict[str, Any]:
        """Get information about the process using a port"""
        import platform
        import subprocess

        system = platform.system()

        try:
            if system == "Darwin" or system == "Linux":
                # Use lsof to find process on port
                result = subprocess.run(
                    ["lsof", "-i", f":{port}", "-t"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    pid = int(result.stdout.strip().split("\n")[0])

                    # Get process name and command
                    ps_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "comm=,args="],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if ps_result.returncode == 0:
                        output = ps_result.stdout.strip()
                        parts = output.split(None, 1)
                        name = parts[0] if parts else "unknown"
                        command = parts[1] if len(parts) > 1 else name
                        return {"pid": pid, "name": name, "command": command[:100]}

                    return {"pid": pid, "name": "unknown", "command": None}

            elif system == "Windows":
                # Use netstat on Windows
                result = subprocess.run(
                    ["netstat", "-ano"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if f":{port}" in line and "LISTENING" in line:
                            parts = line.split()
                            if parts:
                                pid = int(parts[-1])
                                return {"pid": pid, "name": "unknown", "command": None}
        except Exception as e:
            logger.debug(f"Could not get process info for port {port}: {e}")

        return {"pid": None, "name": None, "command": None}

    @classmethod
    async def find_available_port(
        cls,
        preferred_port: Optional[int] = None,
        exclude_ports: Optional[List[int]] = None,
        project_info: Optional["ProjectInfo"] = None,
    ) -> int:
        """
        Find an available port, starting with preferred port.
        Uses NaviConfig for all port values - NO HARDCODING.
        """
        exclude = set(exclude_ports or [])

        # Get preferred port dynamically if not specified
        if preferred_port is None:
            preferred_port = NaviConfig.get_preferred_port(project_info)

        # First try the preferred port
        if preferred_port not in exclude:
            status = await cls.check_port(preferred_port)
            if status.is_available:
                return preferred_port

        # Try common dev ports from config
        for port in cls.COMMON_DEV_PORTS:
            if port in exclude or port == preferred_port:
                continue
            status = await cls.check_port(port)
            if status.is_available:
                return port

        # Try a range of ports from config
        port_start = NaviConfig.DEFAULT_PORT_RANGE_START
        port_end = NaviConfig.DEFAULT_PORT_RANGE_END
        for port in range(port_start, port_end):
            if port in exclude:
                continue
            status = await cls.check_port(port)
            if status.is_available:
                return port

        raise RuntimeError(f"No available ports found in range {port_start}-{port_end}")

    @classmethod
    async def kill_process_on_port(cls, port: int) -> bool:
        """Kill the process using a port. Returns True if successful."""
        import platform
        import subprocess
        import signal

        status = await cls.check_port(port)
        if status.is_available:
            return True  # Port already free

        if not status.process_pid:
            return False  # Can't kill what we can't find

        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(status.process_pid)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                os.kill(status.process_pid, signal.SIGTERM)
                # Give it a moment to terminate
                await asyncio.sleep(0.5)
                # Check if still running
                try:
                    os.kill(status.process_pid, 0)
                    # Still running, force kill
                    os.kill(status.process_pid, signal.SIGKILL)
                except OSError:
                    pass  # Process already dead

            # Verify port is now free
            await asyncio.sleep(0.5)
            new_status = await cls.check_port(port)
            return new_status.is_available

        except Exception as e:
            logger.error(f"Failed to kill process on port {port}: {e}")
            return False

    @classmethod
    def modify_command_for_port(cls, command: str, new_port: int) -> str:
        """Modify a dev server command to use a specific port"""
        # Common patterns for port flags
        port_patterns = [
            (r"--port[=\s]+\d+", f"--port {new_port}"),
            (r"-p[=\s]+\d+", f"-p {new_port}"),
            (r"PORT=\d+", f"PORT={new_port}"),
        ]

        modified = command
        has_port_flag = False

        for pattern, replacement in port_patterns:
            if re.search(pattern, modified):
                modified = re.sub(pattern, replacement, modified)
                has_port_flag = True
                break

        # If no existing port flag, add one based on the command
        if not has_port_flag:
            if "next" in command.lower() or "npm run dev" in command.lower():
                modified = f"{command} -- -p {new_port}"
            elif "vite" in command.lower():
                modified = f"{command} --port {new_port}"
            elif "react-scripts" in command.lower():
                modified = f"PORT={new_port} {command}"
            elif "vue" in command.lower():
                modified = f"{command} --port {new_port}"
            elif "uvicorn" in command.lower():
                modified = f"{command} --port {new_port}"
            elif "flask" in command.lower():
                modified = f"{command} --port {new_port}"

        return modified

    @classmethod
    async def get_port_context_for_llm(
        cls,
        preferred_port: Optional[int] = None,
        project_info: Optional["ProjectInfo"] = None,
    ) -> Dict[str, Any]:
        """
        Generate port context information for LLM to make intelligent decisions.
        Uses NaviConfig.get_preferred_port() for dynamic port detection - NO HARDCODING.
        """
        # Dynamically determine preferred port if not specified
        if preferred_port is None:
            preferred_port = NaviConfig.get_preferred_port(project_info)

        status = await cls.check_port(preferred_port)

        if status.is_available:
            return {
                "preferred_port": preferred_port,
                "is_available": True,
                "message": None,
                "alternatives": [],
                "process_info": None,
            }

        # Port is busy - find alternatives and process info
        alternative = await cls.find_available_port(
            preferred_port, exclude_ports=[preferred_port], project_info=project_info
        )

        return {
            "preferred_port": preferred_port,
            "is_available": False,
            "message": DynamicMessages.port_conflict_message(
                preferred_port,
                status.process_name,
                status.process_command,
                alternative,
            ),
            "process_info": (
                {
                    "name": status.process_name,
                    "pid": status.process_pid,
                    "command": status.process_command,
                }
                if status.process_pid
                else None
            ),
            "alternative_port": alternative,
            "alternatives": [alternative],
        }


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

        # Show what we found with project name if available
        framework = project_info.framework or project_info.project_type
        if project_info.name:
            parts.append(f"This is **{project_info.name}**, a **{framework}** project.")
        else:
            parts.append(f"This is a **{framework}** project.")
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
        """Get the correct dev command and URL.

        IMPORTANT: Don't hardcode ports! The actual port depends on:
        1. Port configuration in the script (--port flag)
        2. Environment variables (PORT, VITE_PORT, etc.)
        3. Config files (vite.config.js, next.config.js, etc.)
        4. Port availability (many frameworks auto-increment if port is busy)

        Instead of guessing, we return None for URL and let the LLM explain
        that the URL will be shown in the terminal output.
        """
        pm = info.package_manager
        run = "run" if pm != "yarn" else ""

        # Check for specific scripts in order of preference
        dev_scripts = ["dev", "start", "serve", "develop"]

        for script in dev_scripts:
            if script in info.scripts:
                cmd = f"{pm} {run} {script}".replace("  ", " ")
                script_content = info.scripts.get(script, "")

                # Try to extract port from script content if explicitly set
                url = cls._extract_port_from_script(script_content, info.project_type)

                return cmd, url

        # Python projects
        if info.project_type == "python":
            if "uvicorn" in str(info.dependencies):
                # Don't assume port - uvicorn can be configured differently
                return "uvicorn main:app --reload", None
            elif "flask" in str(info.dependencies):
                return "flask run", None
            elif "django" in str(info.dependencies):
                return "python manage.py runserver", None

        return None, None

    @classmethod
    def _extract_port_from_script(
        cls, script_content: str, project_type: str
    ) -> Optional[str]:
        """Try to extract port from script content. Returns None if not explicitly set.

        We only return a URL if the port is EXPLICITLY configured in the script.
        This avoids hardcoding default ports that may not be accurate.
        """
        import re

        if not script_content:
            return None

        # Look for explicit port flags in the script
        # Common patterns: --port 3001, -p 8080, PORT=3001
        port_patterns = [
            r"--port[=\s]+(\d+)",
            r"-p[=\s]+(\d+)",
            r"PORT[=:]\s*(\d+)",
            r":(\d{4,5})",  # e.g., localhost:3001 in script
        ]

        for pattern in port_patterns:
            match = re.search(pattern, script_content)
            if match:
                port = match.group(1)
                return f"http://localhost:{port}"

        # No explicit port found - don't guess
        # The actual URL will be shown in terminal output when the server starts
        return None

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

    # SaaS Multi-tenant context
    org_id: Optional[str] = None  # Organization ID
    team_id: Optional[str] = None  # Team ID
    user_id: Optional[str] = None  # User ID
    conversation_id: Optional[str] = None  # Conversation ID for memory

    # Memory context (populated by memory system)
    memory_context: Dict[str, Any] = field(default_factory=dict)


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
    next_steps: List[str] = field(default_factory=list)  # Suggested follow-up actions

    # NAVI V2: Approval flow fields
    plan_id: Optional[str] = None  # Unique ID for this plan
    requires_approval: bool = False  # If true, show approval UI
    actions_with_risk: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Actions with risk assessment
    estimated_changes: Dict[str, Any] = field(
        default_factory=dict
    )  # Files affected, lines changed

    # NAVI V3: Rich actions with descriptions for streaming UI
    # Each action has: type, filePath/command, description (for conversational streaming)
    actions: List[Dict[str, Any]] = field(default_factory=list)

    # NAVI V3: Port management context
    # Contains: preferred_port, is_available, process_info, alternative_port
    port_context: Optional[Dict[str, Any]] = None

    # SaaS: Token usage and cost tracking
    # Contains: input_tokens, output_tokens, total_tokens, latency_ms, model, provider, cost
    usage_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
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
            "next_steps": self.next_steps,
            # NAVI V2 fields
            "plan_id": self.plan_id,
            "requires_approval": self.requires_approval,
            "actions_with_risk": self.actions_with_risk,
            "estimated_changes": self.estimated_changes,
            # NAVI V3: Rich actions with descriptions for streaming UI
            "actions": self.actions,
            # NAVI V3: Port management context
            "port_context": self.port_context,
        }

        # Add usage info with cost calculation for SaaS billing
        if self.usage_info:
            from backend.services.token_tracking import CostCalculator, TokenUsage

            model = self.usage_info.get("model", "default")
            input_tokens = self.usage_info.get("input_tokens", 0)
            output_tokens = self.usage_info.get("output_tokens", 0)

            usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
            costs = CostCalculator.calculate(model, usage)

            result["usage"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "latency_ms": round(self.usage_info.get("latency_ms", 0), 2),
                "model": model,
                "provider": self.usage_info.get("provider", "unknown"),
                "cost": {
                    "input": f"${costs['input_cost']:.6f}",
                    "output": f"${costs['output_cost']:.6f}",
                    "total": f"${costs['total_cost']:.6f}",
                },
            }

        return result


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


# ==================== DYNAMIC MESSAGE GENERATOR ====================


class DynamicMessages:
    """
    Generates dynamic, context-aware messages for NAVI responses.
    Replaces hardcoded strings with professional, contextual messages.
    """

    @staticmethod
    def error_message(error: Exception, context: Optional[str] = None) -> str:
        """Generate a user-friendly error message based on the exception type"""
        error_str = str(error)
        type(error).__name__
        error_lower = error_str.lower()

        # PRIORITY 1: LLM/API errors - check these FIRST before generic patterns
        # These errors often contain words like "access" which would be misclassified
        if (
            "api error" in error_lower
            or "anthropic" in error_lower
            or "openai" in error_lower
        ):
            # Rate limit errors
            if "rate" in error_lower or "429" in error_str or "too many" in error_lower:
                return "NAVI is experiencing high demand. Please wait a moment and try again."
            # Authentication errors
            if (
                "401" in error_str
                or "unauthorized" in error_lower
                or "invalid.*key" in error_lower
            ):
                return "There's an issue with NAVI's configuration. Please contact support."
            # Quota/billing errors
            if "quota" in error_lower or "billing" in error_lower or "402" in error_str:
                return "NAVI's service quota has been reached. Please try again later or contact support."
            # Overloaded
            if "overloaded" in error_lower or "503" in error_str or "529" in error_str:
                return (
                    "NAVI is temporarily overloaded. Please try again in a few seconds."
                )
            # Generic API error
            return "NAVI encountered a temporary issue. Please try again in a moment."

        # PRIORITY 2: Connection/network errors
        if "timeout" in error_lower or "timed out" in error_lower:
            return "The operation took longer than expected. This might be due to a slow network or busy server. Would you like me to try again?"

        if "connection" in error_lower or "network" in error_lower:
            return "I couldn't establish a connection. Please check your network and try again."

        # PRIORITY 3: File system permission errors (only if NOT an API error)
        if "permission" in error_lower or "access denied" in error_lower:
            # Make sure this is actually a file permission error, not an API error
            if (
                "file" in error_lower
                or "directory" in error_lower
                or "path" in error_lower
            ):
                return "I don't have permission to access that file or directory. You may need to adjust file permissions."
            # Otherwise, be more generic
            return (
                "Access was denied. This might be a temporary issue - please try again."
            )

        if "not found" in error_lower or "does not exist" in error_lower:
            file_match = re.search(r"['\"]([^'\"]+)['\"]", error_str)
            if file_match:
                return f"I couldn't find `{file_match.group(1)}`. Would you like me to create it or search for alternatives?"
            return (
                "The requested resource wasn't found. Can you verify the path or name?"
            )

        if "syntax" in error_lower or "parse" in error_lower:
            return "There seems to be a syntax issue. Let me analyze and help fix it."

        if "json" in error_lower:
            return "I had trouble processing the response format. Let me try a different approach."

        # Generic but still helpful
        if context:
            return f"I ran into an issue while {context}. Would you like me to try a different approach?"

        return "Something unexpected happened. Would you like me to try again or take a different approach?"

    @staticmethod
    def safety_warning(warnings: List[str]) -> str:
        """Generate a clear safety warning message"""
        if not warnings:
            return "The operation was flagged for safety review."

        warning_count = len(warnings)
        if warning_count == 1:
            return f"⚠️ **Safety Notice**: {warnings[0]}\n\nThis action requires your explicit approval. Would you like to proceed with modifications?"

        formatted_warnings = "\n".join([f"  • {w}" for w in warnings[:5]])
        if warning_count > 5:
            formatted_warnings += f"\n  • ...and {warning_count - 5} more"

        return f"⚠️ **Safety Notice**: {warning_count} potential issues detected:\n{formatted_warnings}\n\nPlease review and confirm if you'd like to proceed."

    @staticmethod
    def port_conflict_message(
        port: int,
        process_name: Optional[str] = None,
        process_cmd: Optional[str] = None,
        alt_port: Optional[int] = None,
    ) -> str:
        """Generate a helpful port conflict message"""
        process_desc = f"`{process_name}`" if process_name else "another process"
        if process_cmd:
            process_desc += f"\n   Running: `{process_cmd[:60]}{'...' if len(process_cmd) > 60 else ''}`"

        msg = f"Port {port} is currently in use by {process_desc}.\n\n"

        if alt_port:
            msg += "**Options:**\n"
            msg += f"1. Start on port **{alt_port}** instead (recommended)\n"
            msg += f"2. Stop the existing process and use port {port}\n\n"
            msg += "Which would you prefer?"
        else:
            msg += "Would you like me to find an available port, or stop the existing process?"

        return msg

    @staticmethod
    def action_description(
        action_type: str, details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a natural description for an action"""
        details = details or {}

        descriptions = {
            "createFile": lambda d: f"Creating `{d.get('filePath', 'new file')}`",
            "editFile": lambda d: f"Updating `{d.get('filePath', 'file')}`",
            "deleteFile": lambda d: f"Removing `{d.get('filePath', 'file')}`",
            "runCommand": lambda d: f"Running `{d.get('command', 'command')[:50]}{'...' if len(d.get('command', '')) > 50 else ''}`",
            "checkPort": lambda d: f"Checking if port {d.get('port', '?')} is available",
            "killPort": lambda d: f"Stopping process on port {d.get('port', '?')}",
            "installDependencies": lambda d: "Installing project dependencies",
            "startServer": lambda d: "Starting development server",
        }

        generator = descriptions.get(action_type)
        if generator:
            return generator(details)

        # Fallback for unknown action types
        return f"Performing {action_type.replace('_', ' ')}"

    @staticmethod
    def success_message(
        action_type: str, details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a success message for completed actions"""
        details = details or {}

        if action_type == "createFile":
            return f"Created `{details.get('filePath', 'file')}`"
        elif action_type == "editFile":
            stats = details.get("stats", {})
            added = stats.get("added", 0)
            removed = stats.get("removed", 0)
            if added or removed:
                return f"Updated `{details.get('filePath', 'file')}` (+{added}/-{removed} lines)"
            return f"Updated `{details.get('filePath', 'file')}`"
        elif action_type == "runCommand":
            return "Command completed successfully"
        elif action_type == "installDependencies":
            return "Dependencies installed"

        return "Action completed"


# ==================== WEB SEARCH CAPABILITY ====================


class WebSearchProvider:
    """
    Provides web search capability for NAVI when local knowledge is insufficient.

    This allows NAVI to:
    - Search for documentation on unknown technologies
    - Find solutions to specific errors
    - Get up-to-date information on libraries and frameworks
    - Research best practices for unfamiliar domains
    """

    # Search providers configuration
    SEARCH_PROVIDERS = {
        "duckduckgo": {
            "url": "https://api.duckduckgo.com/",
            "params": lambda q: {"q": q, "format": "json", "no_html": 1},
        },
        "serper": {
            "url": "https://google.serper.dev/search",
            "api_key_env": "SERPER_API_KEY",
        },
        "tavily": {
            "url": "https://api.tavily.com/search",
            "api_key_env": "TAVILY_API_KEY",
        },
    }

    # Patterns that suggest web search would help
    SEARCH_TRIGGERS = [
        # Unknown technology/library
        r"what is (\w+)",
        r"how to use (\w+)",
        r"(\w+) documentation",
        r"(\w+) tutorial",
        r"(\w+) example",
        # Error resolution
        r"error:?\s*(.+)",
        r"fix\s+(.+)\s+error",
        r"resolve\s+(.+)",
        # Best practices
        r"best practice.+(\w+)",
        r"recommended.+(\w+)",
        r"how to properly",
        # Version/update queries
        r"latest version of (\w+)",
        r"(\w+) changelog",
        r"upgrade.+(\w+)",
    ]

    @classmethod
    def should_search(
        cls, message: str, project_info: Optional[ProjectInfo] = None
    ) -> bool:
        """Determine if web search would be beneficial for this request"""
        message_lower = message.lower()

        # Check for explicit search requests
        if any(
            phrase in message_lower
            for phrase in [
                "search for",
                "look up",
                "find documentation",
                "search the web",
                "google",
                "look online",
                "find examples of",
            ]
        ):
            return True

        # Check if it's asking about something not in our domain knowledge
        known_terms = set()
        for keywords in DynamicContextProvider.DOMAIN_HINTS.values():
            known_terms.update(keywords)

        # Extract potential technology names from the message
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]+\b", message_lower)
        unknown_terms = [w for w in words if len(w) > 3 and w not in known_terms]

        # If there are many unknown terms, might benefit from search
        if len(unknown_terms) > 2:
            return True

        # Check for error messages (often benefit from web search)
        if re.search(r"error|exception|failed|cannot|unable", message_lower):
            return True

        return False

    @classmethod
    async def search(cls, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Perform a web search and return relevant results.
        Tries multiple providers in order of preference.
        """
        # Try DuckDuckGo first (no API key required)
        try:
            result = await cls._search_duckduckgo(query, max_results)
            if result.get("results"):
                return result
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")

        # Try Serper if API key is available
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            try:
                result = await cls._search_serper(query, serper_key, max_results)
                if result.get("results"):
                    return result
            except Exception as e:
                logger.warning(f"Serper search failed: {e}")

        # Try Tavily if API key is available
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                result = await cls._search_tavily(query, tavily_key, max_results)
                if result.get("results"):
                    return result
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        return {"results": [], "source": None, "error": "No search results found"}

    @classmethod
    async def _search_duckduckgo(cls, query: str, max_results: int) -> Dict[str, Any]:
        """Search using DuckDuckGo Instant Answer API"""
        import urllib.parse

        encoded_query = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    results = []

                    # Abstract (main answer)
                    if data.get("Abstract"):
                        results.append(
                            {
                                "title": data.get("Heading", "Result"),
                                "snippet": data["Abstract"],
                                "url": data.get("AbstractURL", ""),
                                "source": data.get("AbstractSource", ""),
                            }
                        )

                    # Related topics
                    for topic in data.get("RelatedTopics", [])[: max_results - 1]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            results.append(
                                {
                                    "title": topic.get("Text", "")[:100],
                                    "snippet": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", ""),
                                }
                            )

                    return {"results": results, "source": "duckduckgo"}

        return {"results": [], "source": "duckduckgo"}

    @classmethod
    async def _search_serper(
        cls, query: str, api_key: str, max_results: int
    ) -> Dict[str, Any]:
        """Search using Serper.dev (Google Search API)"""
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    results = []
                    for item in data.get("organic", [])[:max_results]:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                                "url": item.get("link", ""),
                            }
                        )

                    return {"results": results, "source": "serper"}

        return {"results": [], "source": "serper"}

    @classmethod
    async def _search_tavily(
        cls, query: str, api_key: str, max_results: int
    ) -> Dict[str, Any]:
        """Search using Tavily AI Search"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    results = []
                    for item in data.get("results", [])[:max_results]:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "snippet": item.get("content", ""),
                                "url": item.get("url", ""),
                            }
                        )

                    return {"results": results, "source": "tavily"}

        return {"results": [], "source": "tavily"}

    @classmethod
    def format_search_results_for_llm(cls, search_results: Dict[str, Any]) -> str:
        """Format search results as context for the LLM"""
        results = search_results.get("results", [])
        if not results:
            return ""

        source = search_results.get("source", "web")
        parts = [f"=== WEB SEARCH RESULTS (from {source}) ==="]

        for i, result in enumerate(results[:5], 1):
            parts.append(f"\n[{i}] {result.get('title', 'No title')}")
            if result.get("snippet"):
                parts.append(f"    {result['snippet'][:300]}")
            if result.get("url"):
                parts.append(f"    Source: {result['url']}")

        parts.append("\n" + "=" * 50)
        return "\n".join(parts)


# ==================== TOOL INSTALLATION CAPABILITY ====================


class ToolInstaller:
    """
    Provides capability to install missing tools automatically.

    NAVI can detect missing tools and offer to install them,
    making the development environment self-sufficient.
    """

    # Tool installation commands by platform
    TOOL_INSTALLERS = {
        "node": {
            "Darwin": [
                "brew install node",
                "curl -fsSL https://fnm.vercel.app/install | bash && fnm install --lts",
            ],
            "Linux": [
                "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs",
                "curl -fsSL https://fnm.vercel.app/install | bash && fnm install --lts",
            ],
            "Windows": ["winget install OpenJS.NodeJS.LTS", "choco install nodejs-lts"],
        },
        "python": {
            "Darwin": ["brew install python@3.11", "brew install python"],
            "Linux": [
                "sudo apt-get install python3 python3-pip",
                "sudo dnf install python3 python3-pip",
            ],
            "Windows": ["winget install Python.Python.3.11", "choco install python"],
        },
        "docker": {
            "Darwin": ["brew install --cask docker"],
            "Linux": ["curl -fsSL https://get.docker.com | sh"],
            "Windows": ["winget install Docker.DockerDesktop"],
        },
        "git": {
            "Darwin": ["xcode-select --install", "brew install git"],
            "Linux": ["sudo apt-get install git", "sudo dnf install git"],
            "Windows": ["winget install Git.Git", "choco install git"],
        },
        "yarn": {
            "all": [
                "npm install -g yarn",
                "corepack enable && corepack prepare yarn@stable --activate",
            ]
        },
        "pnpm": {
            "all": [
                "npm install -g pnpm",
                "corepack enable && corepack prepare pnpm@latest --activate",
            ]
        },
        "bun": {
            "Darwin": ["curl -fsSL https://bun.sh/install | bash"],
            "Linux": ["curl -fsSL https://bun.sh/install | bash"],
            "Windows": ['powershell -c "irm bun.sh/install.ps1 | iex"'],
        },
        "go": {
            "Darwin": ["brew install go"],
            "Linux": [
                "sudo apt-get install golang-go",
                "sudo snap install go --classic",
            ],
            "Windows": ["winget install GoLang.Go", "choco install golang"],
        },
        "rust": {
            "all": ["curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"]
        },
        "cargo": {
            "all": ["curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"]
        },
    }

    @classmethod
    def get_missing_tools(cls, required_tools: List[str]) -> List[str]:
        """Check which tools are missing from the system"""
        import shutil

        missing = []
        for tool in required_tools:
            if not shutil.which(tool):
                missing.append(tool)
        return missing

    @classmethod
    def get_install_commands(cls, tool: str) -> List[str]:
        """Get installation commands for a tool on the current platform"""
        import platform

        system = platform.system()

        tool_lower = tool.lower()
        if tool_lower not in cls.TOOL_INSTALLERS:
            return []

        installers = cls.TOOL_INSTALLERS[tool_lower]

        # Check for platform-agnostic installers first
        if "all" in installers:
            return installers["all"]

        # Return platform-specific installers
        return installers.get(system, [])

    @classmethod
    def detect_required_tools(
        cls, project_info: Optional[ProjectInfo], message: str
    ) -> List[str]:
        """Detect which tools are required based on project and request"""
        required = set()

        # From project type
        if project_info:
            if project_info.project_type in [
                "nextjs",
                "react",
                "vue",
                "angular",
                "node",
            ]:
                required.add("node")
                required.add(project_info.package_manager or "npm")
            elif project_info.project_type == "python":
                required.add("python")
                required.add("pip")
            elif project_info.project_type == "rust":
                required.add("cargo")
            elif project_info.project_type == "go":
                required.add("go")

        # From message content
        message_lower = message.lower()
        tool_mentions = {
            "docker": ["docker", "container", "dockerfile"],
            "git": ["git", "commit", "push", "pull", "branch"],
            "node": ["node", "npm", "package.json"],
            "yarn": ["yarn"],
            "pnpm": ["pnpm"],
            "bun": ["bun"],
            "python": ["python", "pip", "requirements.txt", "pyproject"],
            "go": ["go mod", "golang"],
            "cargo": ["cargo", "rust"],
        }

        for tool, keywords in tool_mentions.items():
            if any(kw in message_lower for kw in keywords):
                required.add(tool)

        return list(required)

    @classmethod
    def generate_install_actions(cls, missing_tools: List[str]) -> List[Dict[str, Any]]:
        """Generate actions to install missing tools"""
        actions = []

        for tool in missing_tools:
            commands = cls.get_install_commands(tool)
            if commands:
                # Prefer the first (usually most common) installation method
                actions.append(
                    {
                        "type": "installTool",
                        "tool": tool,
                        "command": commands[0],
                        "alternatives": commands[1:] if len(commands) > 1 else [],
                        "description": f"Install {tool}",
                        "requires_approval": True,
                    }
                )

        return actions

    @classmethod
    def format_missing_tools_message(cls, missing_tools: List[str]) -> str:
        """Generate a user-friendly message about missing tools"""
        if not missing_tools:
            return ""

        import platform

        platform.system()

        parts = [f"⚠️ **Missing Tools Detected**: {', '.join(missing_tools)}\n"]
        parts.append("I can install these for you. Here are the recommended methods:\n")

        for tool in missing_tools:
            commands = cls.get_install_commands(tool)
            if commands:
                parts.append(f"\n**{tool}**:")
                parts.append(f"```bash\n{commands[0]}\n```")
                if len(commands) > 1:
                    parts.append(f"_Alternative: `{commands[1]}`_")

        parts.append("\n\nWould you like me to install these tools for you?")
        return "\n".join(parts)


# ==================== DYNAMIC CONTEXT PROVIDER ====================


class DynamicContextProvider:
    """
    Provides dynamic, request-aware context enrichment for the LLM.

    This is what makes NAVI handle "millions of requests" intelligently:
    - Detects the DOMAIN of the request (web, data, DevOps, mobile, etc.)
    - Gathers relevant context based on the domain
    - Provides domain-specific knowledge and patterns
    - Ensures the LLM has everything it needs to respond accurately

    The LLM does the actual understanding - this class just ensures
    it has the right context to work with.
    """

    # Domain detection patterns - the LLM uses these as hints, not hard rules
    # Comprehensive coverage for 100+ technologies, languages, and platforms
    DOMAIN_HINTS = {
        # ==================== FRONTEND ====================
        "web_frontend": [
            "react",
            "vue",
            "angular",
            "svelte",
            "nextjs",
            "nuxt",
            "gatsby",
            "component",
            "css",
            "tailwind",
            "styled",
            "scss",
            "sass",
            "less",
            "responsive",
            "mobile-first",
            "accessibility",
            "a11y",
            "seo",
            "webpack",
            "vite",
            "parcel",
            "bundler",
            "transpile",
            "esbuild",
            "redux",
            "zustand",
            "pinia",
            "mobx",
            "recoil",
            "jotai",
            "remix",
            "astro",
            "solid",
            "qwik",
            "htmx",
            "alpine.js",
        ],
        # ==================== BACKEND ====================
        "web_backend": [
            "api",
            "endpoint",
            "rest",
            "graphql",
            "server",
            "express",
            "fastapi",
            "django",
            "flask",
            "rails",
            "spring",
            "nestjs",
            "middleware",
            "authentication",
            "authorization",
            "jwt",
            "oauth",
            "database",
            "query",
            "orm",
            "prisma",
            "sequelize",
            "sqlalchemy",
            "grpc",
            "websocket",
            "sse",
            "microservice",
            "monolith",
        ],
        # ==================== JAVA ECOSYSTEM ====================
        "java": [
            "java",
            "jvm",
            "spring boot",
            "spring",
            "maven",
            "gradle",
            "hibernate",
            "jpa",
            "jdbc",
            "tomcat",
            "jetty",
            "wildfly",
            "quarkus",
            "micronaut",
            "vert.x",
            "dropwizard",
            "jax-rs",
            "lombok",
            "jackson",
            "gson",
            "junit",
            "mockito",
            "testng",
            "java 17",
            "java 21",
            "records",
            "sealed",
            "virtual threads",
        ],
        # ==================== .NET / C# ECOSYSTEM ====================
        "dotnet": [
            ".net",
            "c#",
            "csharp",
            "dotnet",
            "asp.net",
            "blazor",
            "entity framework",
            "ef core",
            "linq",
            "nuget",
            "msbuild",
            ".net core",
            ".net 6",
            ".net 7",
            ".net 8",
            "maui",
            "xamarin",
            "signalr",
            "minimal api",
            "razor",
            "winforms",
            "wpf",
            "uwp",
            "xunit",
            "nunit",
            "moq",
            "autofac",
            "mediatr",
            "fluentvalidation",
        ],
        # ==================== C / C++ ====================
        "cpp": [
            "c++",
            "cpp",
            "c language",
            "clang",
            "gcc",
            "msvc",
            "cmake",
            "make",
            "makefile",
            "ninja",
            "conan",
            "vcpkg",
            "stl",
            "boost",
            "qt",
            "opencv",
            "eigen",
            "poco",
            "memory management",
            "pointer",
            "smart pointer",
            "raii",
            "c++11",
            "c++14",
            "c++17",
            "c++20",
            "c++23",
            "modern c++",
            "header",
            "template",
            "constexpr",
            "coroutine",
        ],
        # ==================== SCALA ====================
        "scala": [
            "scala",
            "sbt",
            "akka",
            "play framework",
            "cats",
            "zio",
            "spark scala",
            "flink",
            "scalaz",
            "circe",
            "http4s",
            "functional programming",
            "implicits",
            "case class",
            "trait",
            "scala 2",
            "scala 3",
            "dotty",
            "scalatest",
            "specs2",
        ],
        # ==================== GO ====================
        "golang": [
            "go",
            "golang",
            "goroutine",
            "channel",
            "go mod",
            "gin",
            "echo",
            "fiber",
            "chi",
            "buffalo",
            "beego",
            "gorm",
            "sqlx",
            "go-kit",
            "cobra",
            "viper",
            "concurrency",
            "interface",
            "struct",
            "defer",
        ],
        # ==================== RUST ====================
        "rust": [
            "rust",
            "cargo",
            "rustup",
            "crate",
            "rustc",
            "actix",
            "axum",
            "rocket",
            "warp",
            "tokio",
            "async-std",
            "serde",
            "diesel",
            "sqlx",
            "ownership",
            "borrowing",
            "lifetime",
            "trait",
            "macro",
            "unsafe",
            "wasm",
            "webassembly",
        ],
        # ==================== PYTHON ====================
        "python": [
            "python",
            "pip",
            "poetry",
            "pipenv",
            "conda",
            "virtualenv",
            "fastapi",
            "django",
            "flask",
            "starlette",
            "aiohttp",
            "pydantic",
            "sqlalchemy",
            "asyncio",
            "celery",
            "dramatiq",
            "numpy",
            "scipy",
            "matplotlib",
            "jupyter",
            "notebook",
        ],
        # ==================== JAVASCRIPT/TYPESCRIPT ====================
        "javascript": [
            "javascript",
            "typescript",
            "node",
            "nodejs",
            "npm",
            "yarn",
            "pnpm",
            "bun",
            "express",
            "nestjs",
            "fastify",
            "koa",
            "hapi",
            "deno",
            "es6",
            "esm",
            "commonjs",
            "async await",
            "promise",
        ],
        # ==================== RUBY ====================
        "ruby": [
            "ruby",
            "rails",
            "ruby on rails",
            "gem",
            "bundler",
            "sinatra",
            "hanami",
            "rspec",
            "minitest",
            "capybara",
            "activerecord",
            "sidekiq",
            "puma",
            "unicorn",
            "rake",
        ],
        # ==================== PHP ====================
        "php": [
            "php",
            "laravel",
            "symfony",
            "composer",
            "wordpress",
            "drupal",
            "magento",
            "codeigniter",
            "yii",
            "cakephp",
            "artisan",
            "eloquent",
            "doctrine",
            "phpunit",
            "pest",
        ],
        # ==================== ELIXIR / ERLANG ====================
        "elixir": [
            "elixir",
            "phoenix",
            "erlang",
            "otp",
            "beam",
            "mix",
            "ecto",
            "liveview",
            "genserver",
            "supervisor",
            "mnesia",
            "absinthe",
            "nerves",
            "broadway",
            "flow",
        ],
        # ==================== KOTLIN ====================
        "kotlin": [
            "kotlin",
            "ktor",
            "spring kotlin",
            "coroutines",
            "flow",
            "jetpack compose",
            "multiplatform",
            "kmp",
            "kmm",
            "arrow",
            "exposed",
            "kotest",
            "mockk",
        ],
        # ==================== SWIFT ====================
        "swift": [
            "swift",
            "swiftui",
            "uikit",
            "cocoa",
            "xcode",
            "ios development",
            "macos",
            "watchos",
            "tvos",
            "combine",
            "async/await",
            "actor",
            "spm",
            "swift package",
        ],
        # ==================== AWS ====================
        "aws": [
            "aws",
            "amazon web services",
            "ec2",
            "s3",
            "lambda",
            "rds",
            "dynamodb",
            "sqs",
            "sns",
            "ecs",
            "eks",
            "fargate",
            "cloudformation",
            "cdk",
            "sam",
            "amplify",
            "cognito",
            "api gateway",
            "cloudwatch",
            "iam",
            "vpc",
            "route53",
            "elasticache",
            "aurora",
            "kinesis",
            "step functions",
            "eventbridge",
            "secrets manager",
            "ssm",
            "cloudfront",
            "elb",
            "alb",
            "nlb",
            "auto scaling",
            "beanstalk",
        ],
        # ==================== GCP ====================
        "gcp": [
            "gcp",
            "google cloud",
            "compute engine",
            "gke",
            "cloud run",
            "cloud functions",
            "bigquery",
            "cloud storage",
            "gcs",
            "pubsub",
            "cloud sql",
            "spanner",
            "firestore",
            "bigtable",
            "dataflow",
            "dataproc",
            "composer",
            "cloud build",
            "artifact registry",
            "container registry",
            "cloud cdn",
            "load balancer",
            "vpc network",
            "iam",
            "secret manager",
            "cloud logging",
            "cloud monitoring",
            "cloud armor",
            "vertex ai",
            "automl",
            "vision api",
            "speech api",
        ],
        # ==================== AZURE ====================
        "azure": [
            "azure",
            "microsoft azure",
            "azure functions",
            "app service",
            "aks",
            "azure kubernetes",
            "cosmos db",
            "azure sql",
            "blob storage",
            "azure storage",
            "service bus",
            "event hub",
            "azure devops",
            "pipelines",
            "azure ad",
            "entra",
            "arm templates",
            "bicep",
            "azure cli",
            "key vault",
            "application insights",
            "azure monitor",
            "front door",
            "traffic manager",
            "virtual network",
            "azure cdn",
            "logic apps",
            "power automate",
            "azure openai",
        ],
        # ==================== KUBERNETES ====================
        "kubernetes": [
            "kubernetes",
            "k8s",
            "kubectl",
            "helm",
            "kustomize",
            "pod",
            "deployment",
            "service",
            "ingress",
            "configmap",
            "secret",
            "namespace",
            "pvc",
            "statefulset",
            "daemonset",
            "operator",
            "crd",
            "istio",
            "linkerd",
            "envoy",
            "argocd",
            "fluxcd",
            "crossplane",
            "keda",
            "knative",
        ],
        # ==================== DOCKER / CONTAINERS ====================
        "docker": [
            "docker",
            "dockerfile",
            "docker-compose",
            "container",
            "podman",
            "buildah",
            "containerd",
            "cri-o",
            "image",
            "registry",
            "ecr",
            "gcr",
            "acr",
            "dockerhub",
            "multi-stage",
            "layer",
            "volume",
            "network",
        ],
        # ==================== TERRAFORM / IAC ====================
        "terraform": [
            "terraform",
            "hcl",
            "tfstate",
            "terraform cloud",
            "pulumi",
            "crossplane",
            "cdktf",
            "terragrunt",
            "provider",
            "module",
            "resource",
            "data source",
            "plan",
            "apply",
            "destroy",
            "state",
            "backend",
        ],
        # ==================== CI/CD ====================
        "cicd": [
            "ci/cd",
            "github actions",
            "gitlab ci",
            "jenkins",
            "circleci",
            "travis",
            "buildkite",
            "teamcity",
            "azure pipelines",
            "bitbucket pipelines",
            "drone",
            "argocd",
            "fluxcd",
            "spinnaker",
            "harness",
            "workflow",
            "pipeline",
            "build",
            "deploy",
            "release",
        ],
        # ==================== DATA ENGINEERING ====================
        "data_engineering": [
            "etl",
            "elt",
            "pipeline",
            "spark",
            "pyspark",
            "pandas",
            "polars",
            "dataframe",
            "parquet",
            "avro",
            "orc",
            "delta lake",
            "iceberg",
            "airflow",
            "dagster",
            "prefect",
            "luigi",
            "dbt",
            "mage",
            "warehouse",
            "data lake",
            "lakehouse",
            "medallion",
            "bigquery",
            "snowflake",
            "redshift",
            "databricks",
            "synapse",
            "kafka",
            "flink",
            "beam",
            "kinesis",
            "pulsar",
            "streaming",
            "batch",
            "transform",
            "schema",
            "data quality",
        ],
        # ==================== MACHINE LEARNING / AI ====================
        "machine_learning": [
            "model",
            "training",
            "inference",
            "tensorflow",
            "pytorch",
            "jax",
            "sklearn",
            "scikit-learn",
            "huggingface",
            "transformers",
            "neural network",
            "deep learning",
            "cnn",
            "rnn",
            "lstm",
            "gpt",
            "feature engineering",
            "embedding",
            "vector",
            "rag",
            "classification",
            "regression",
            "clustering",
            "nlp",
            "computer vision",
            "reinforcement learning",
            "rl",
            "fine-tuning",
            "llm",
            "langchain",
            "llamaindex",
            "openai api",
            "mlflow",
            "wandb",
            "dvc",
            "mlops",
            "kubeflow",
            "sagemaker",
        ],
        # ==================== DATABASES ====================
        "database": [
            "postgresql",
            "postgres",
            "mysql",
            "mariadb",
            "sql server",
            "oracle",
            "sqlite",
            "mongodb",
            "redis",
            "elasticsearch",
            "cassandra",
            "couchdb",
            "neo4j",
            "graph database",
            "timescaledb",
            "influxdb",
            "clickhouse",
            "druid",
            "sql",
            "nosql",
            "index",
            "query optimization",
            "sharding",
            "replication",
            "backup",
            "migration",
            "schema design",
        ],
        # ==================== MESSAGE QUEUES ====================
        "messaging": [
            "kafka",
            "rabbitmq",
            "redis pubsub",
            "nats",
            "pulsar",
            "sqs",
            "sns",
            "pubsub",
            "service bus",
            "event hub",
            "zeromq",
            "activemq",
            "mqtt",
            "amqp",
            "message queue",
            "event driven",
            "async messaging",
        ],
        # ==================== MOBILE ====================
        "mobile": [
            "ios",
            "android",
            "react native",
            "flutter",
            "swift",
            "kotlin",
            "mobile app",
            "native",
            "expo",
            "capacitor",
            "cordova",
            "ionic",
            "push notification",
            "deep link",
            "app store",
            "play store",
            "jetpack compose",
            "swiftui",
            "uikit",
            "xml layout",
        ],
        # ==================== TESTING ====================
        "testing_quality": [
            "test",
            "spec",
            "jest",
            "pytest",
            "mocha",
            "vitest",
            "cypress",
            "playwright",
            "selenium",
            "puppeteer",
            "unit test",
            "integration test",
            "e2e",
            "coverage",
            "mock",
            "stub",
            "spy",
            "fixture",
            "snapshot",
            "tdd",
            "bdd",
            "cucumber",
            "gherkin",
            "junit",
            "testng",
            "xunit",
            "nunit",
            "rspec",
        ],
        # ==================== SECURITY ====================
        "security": [
            "security",
            "vulnerability",
            "auth",
            "authentication",
            "authorization",
            "encrypt",
            "hash",
            "ssl",
            "tls",
            "cors",
            "csrf",
            "xss",
            "injection",
            "sanitize",
            "validate",
            "penetration",
            "pentest",
            "audit",
            "compliance",
            "gdpr",
            "hipaa",
            "soc2",
            "pci",
            "iso27001",
            "oauth",
            "oidc",
            "saml",
            "mfa",
            "2fa",
            "rbac",
            "abac",
            "vault",
            "secrets",
            "key management",
            "hsm",
        ],
        # ==================== PERFORMANCE ====================
        "performance": [
            "performance",
            "optimize",
            "optimization",
            "cache",
            "caching",
            "redis",
            "memcached",
            "varnish",
            "cdn",
            "profiling",
            "profiler",
            "bottleneck",
            "latency",
            "throughput",
            "scaling",
            "horizontal",
            "vertical",
            "auto-scaling",
            "load balancing",
            "connection pooling",
            "async",
            "lazy loading",
            "code splitting",
            "tree shaking",
        ],
        # ==================== BLOCKCHAIN / WEB3 ====================
        "blockchain": [
            "blockchain",
            "web3",
            "ethereum",
            "solidity",
            "smart contract",
            "nft",
            "defi",
            "dao",
            "token",
            "erc20",
            "erc721",
            "hardhat",
            "truffle",
            "foundry",
            "remix",
            "ganache",
            "metamask",
            "wagmi",
            "ethers.js",
            "web3.js",
            "viem",
            "solana",
            "rust solana",
            "anchor",
            "polygon",
            "arbitrum",
            "ipfs",
            "the graph",
            "chainlink",
            "alchemy",
            "infura",
        ],
        # ==================== OBSERVABILITY ====================
        "observability": [
            "monitoring",
            "logging",
            "tracing",
            "metrics",
            "apm",
            "prometheus",
            "grafana",
            "elk",
            "elasticsearch",
            "kibana",
            "datadog",
            "newrelic",
            "splunk",
            "dynatrace",
            "jaeger",
            "zipkin",
            "opentelemetry",
            "otel",
            "alerting",
            "pagerduty",
            "opsgenie",
            "dashboard",
        ],
        # ==================== API DESIGN ====================
        "api_design": [
            "rest api",
            "graphql",
            "grpc",
            "openapi",
            "swagger",
            "api gateway",
            "rate limiting",
            "throttling",
            "versioning",
            "api design",
            "endpoint",
            "resource",
            "http methods",
            "postman",
            "insomnia",
            "hoppscotch",
            "api testing",
        ],
        # ==================== GAME DEVELOPMENT ====================
        "gamedev": [
            "unity",
            "unreal",
            "godot",
            "game engine",
            "gamedev",
            "c# unity",
            "blueprint",
            "gdscript",
            "shader",
            "hlsl",
            "glsl",
            "3d",
            "2d",
            "sprite",
            "animation",
            "physics",
            "multiplayer",
            "netcode",
            "photon",
            "mirror",
        ],
        # ==================== EMBEDDED / IOT ====================
        "embedded": [
            "embedded",
            "iot",
            "arduino",
            "raspberry pi",
            "esp32",
            "firmware",
            "rtos",
            "freertos",
            "zephyr",
            "c embedded",
            "microcontroller",
            "mcu",
            "gpio",
            "i2c",
            "spi",
            "uart",
            "can bus",
            "mqtt iot",
        ],
        # ==================== FUNCTIONAL PROGRAMMING ====================
        "functional": [
            "functional programming",
            "fp",
            "haskell",
            "ocaml",
            "f#",
            "clojure",
            "lisp",
            "scheme",
            "racket",
            "monad",
            "functor",
            "immutable",
            "pure function",
            "pattern matching",
            "algebraic data type",
            "lambda",
        ],
    }

    @classmethod
    def detect_domains(
        cls, message: str, project_info: Optional[ProjectInfo] = None
    ) -> List[str]:
        """
        Detect which domains are relevant to this request.
        Returns a list of domains, not just one - requests often span multiple domains.
        """
        message_lower = message.lower()
        detected = []
        scores = {}

        # Score each domain based on keyword matches
        for domain, keywords in cls.DOMAIN_HINTS.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                scores[domain] = score

        # Also consider project type
        if project_info:
            if project_info.project_type in ["nextjs", "react", "vue", "angular"]:
                scores["web_frontend"] = scores.get("web_frontend", 0) + 2
            if project_info.project_type in ["express", "fastapi", "django", "flask"]:
                scores["web_backend"] = scores.get("web_backend", 0) + 2
            if project_info.project_type == "python":
                # Python could be anything - check dependencies
                deps = str(project_info.dependencies).lower()
                if any(lib in deps for lib in ["pandas", "spark", "airflow", "dbt"]):
                    scores["data_engineering"] = scores.get("data_engineering", 0) + 2
                if any(
                    lib in deps
                    for lib in ["torch", "tensorflow", "sklearn", "transformers"]
                ):
                    scores["machine_learning"] = scores.get("machine_learning", 0) + 2

        # Return top domains (those with scores > 0)
        detected = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return detected[:3] if detected else ["general"]

    @classmethod
    def get_domain_context(
        cls, domains: List[str], project_info: Optional[ProjectInfo] = None
    ) -> str:
        """
        Generate domain-specific context to help the LLM respond accurately.
        This is NOT hardcoded responses - it's context for the LLM to use.
        """
        context_parts = []

        domain_knowledge = {
            # ==================== FRONTEND ====================
            "web_frontend": """
FRONTEND CONTEXT:
- Check for UI framework: React (hooks, components), Vue (composition API), Angular (modules), Svelte, Solid
- Check for meta-frameworks: Next.js (App Router/Pages), Nuxt, Remix, Astro, Qwik
- Check for styling: Tailwind, CSS Modules, Styled Components, SCSS, CSS-in-JS
- Check for state management: Redux Toolkit, Zustand, Pinia, MobX, Jotai, Recoil
- Check build tool: Vite, Webpack, Turbopack, esbuild, Parcel
- Consider: accessibility (ARIA, WCAG), responsive design, Core Web Vitals, SEO
""",
            # ==================== BACKEND ====================
            "web_backend": """
BACKEND CONTEXT:
- Check for framework: Express, FastAPI, Django, NestJS, Spring Boot, Rails
- Check for database: PostgreSQL, MongoDB, MySQL, Redis, SQLite
- Check for ORM: Prisma, Sequelize, SQLAlchemy, TypeORM, Drizzle
- Consider: API design (REST/GraphQL/gRPC), authentication (JWT/OAuth2/OIDC)
- Check for middleware patterns, request validation, error handling, logging
""",
            # ==================== JAVA ====================
            "java": """
JAVA/JVM CONTEXT:
- Check for framework: Spring Boot (3.x), Quarkus, Micronaut, Vert.x
- Check for build tool: Maven, Gradle (Kotlin DSL preferred)
- Check for ORM: Hibernate, JPA, Spring Data, jOOQ
- Check Java version: prefer modern features (records, sealed classes, pattern matching, virtual threads)
- Consider: dependency injection, reactive (WebFlux, Project Reactor), testing (JUnit 5, Mockito)
- Follow: SOLID principles, clean architecture, 12-factor app methodology
""",
            # ==================== .NET / C# ====================
            "dotnet": """
.NET/C# CONTEXT:
- Check for framework: ASP.NET Core (Minimal APIs or Controllers), Blazor, MAUI
- Check .NET version: prefer .NET 8+ features (primary constructors, collection expressions)
- Check for ORM: Entity Framework Core, Dapper
- Check for patterns: Dependency Injection (built-in), MediatR, FluentValidation
- Consider: async/await patterns, LINQ, nullable reference types, source generators
- Testing: xUnit, NUnit, Moq, FluentAssertions
""",
            # ==================== C/C++ ====================
            "cpp": """
C/C++ CONTEXT:
- Check for build system: CMake (modern 3.x), Make, Ninja, Meson
- Check for package manager: Conan, vcpkg, CPM
- Check C++ standard: prefer modern C++ (17/20/23) features
- Consider: RAII, smart pointers, move semantics, constexpr, concepts, coroutines
- Memory safety: avoid raw pointers, use std::unique_ptr/shared_ptr
- Libraries: STL, Boost, Qt, OpenCV, Eigen
- Testing: Google Test, Catch2, doctest
""",
            # ==================== SCALA ====================
            "scala": """
SCALA CONTEXT:
- Check for version: Scala 2.13 vs Scala 3 (Dotty) - different syntax
- Check for framework: Play Framework, Akka (now Apache Pekko), ZIO, Cats Effect
- Check for build tool: sbt (most common), Mill
- Consider: functional programming patterns, implicits/givens, type classes
- Big data: Spark, Flink integration
- Testing: ScalaTest, Specs2, MUnit
""",
            # ==================== GO ====================
            "golang": """
GO CONTEXT:
- Check for framework: Gin, Echo, Fiber, Chi, standard net/http
- Check for database: GORM, sqlx, pgx, ent
- Consider: goroutines, channels, context propagation, error handling
- Follow: Go idioms, effective Go, accept interfaces return structs
- Modules: go mod, proper versioning
- Testing: table-driven tests, testify, gomock
""",
            # ==================== RUST ====================
            "rust": """
RUST CONTEXT:
- Check for framework: Axum, Actix-web, Rocket, Warp
- Check for async runtime: Tokio, async-std
- Consider: ownership, borrowing, lifetimes, trait bounds
- Serialization: serde (JSON, TOML, etc.)
- Database: sqlx, diesel, SeaORM
- Error handling: thiserror, anyhow, Result patterns
- Testing: built-in test framework, cargo test
""",
            # ==================== PYTHON ====================
            "python": """
PYTHON CONTEXT:
- Check for framework: FastAPI, Django, Flask, Starlette
- Check for package manager: pip, Poetry, PDM, uv
- Consider: type hints (typing module), async/await, pydantic validation
- Database: SQLAlchemy (2.0 style), Tortoise ORM, Django ORM
- Task queues: Celery, RQ, Dramatiq
- Testing: pytest, unittest, hypothesis
""",
            # ==================== JAVASCRIPT/TYPESCRIPT ====================
            "javascript": """
JAVASCRIPT/TYPESCRIPT CONTEXT:
- Check for runtime: Node.js, Deno, Bun
- Check for framework: Express, Fastify, NestJS, Hono, Elysia
- Check for package manager: npm, yarn, pnpm, bun
- Consider: TypeScript (strict mode), ESM vs CommonJS, async patterns
- Database: Prisma, Drizzle, Sequelize, TypeORM
- Testing: Jest, Vitest, Mocha, Node test runner
""",
            # ==================== AWS ====================
            "aws": """
AWS CONTEXT:
- Compute: EC2, Lambda, ECS/Fargate, EKS, App Runner, Batch
- Storage: S3, EBS, EFS, FSx
- Database: RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune
- Messaging: SQS, SNS, EventBridge, Kinesis, MSK (Kafka)
- Networking: VPC, ALB/NLB, API Gateway, CloudFront, Route53
- IaC: CloudFormation, CDK (preferred), SAM for serverless
- Security: IAM (least privilege), Secrets Manager, KMS, WAF
- Observability: CloudWatch (Logs, Metrics, Alarms), X-Ray
- Best practices: Well-Architected Framework, multi-AZ, auto-scaling
""",
            # ==================== GCP ====================
            "gcp": """
GCP CONTEXT:
- Compute: Compute Engine, Cloud Run (preferred for containers), GKE, Cloud Functions, App Engine
- Storage: Cloud Storage (GCS), Persistent Disk, Filestore
- Database: Cloud SQL, Spanner, Firestore, Bigtable, AlloyDB, Memorystore
- Messaging: Pub/Sub, Eventarc, Cloud Tasks
- Data: BigQuery (analytics), Dataflow (Apache Beam), Dataproc (Spark), Composer (Airflow)
- Networking: VPC, Cloud Load Balancing, Cloud CDN, Cloud DNS, Cloud Armor
- IaC: Terraform (preferred), Deployment Manager, Pulumi
- Security: IAM, Secret Manager, KMS, VPC Service Controls
- AI/ML: Vertex AI, AutoML, Vision/Speech/Translation APIs
- Observability: Cloud Logging, Cloud Monitoring, Cloud Trace
""",
            # ==================== AZURE ====================
            "azure": """
AZURE CONTEXT:
- Compute: VMs, App Service, Azure Functions, AKS, Container Apps, Batch
- Storage: Blob Storage, Files, Disk Storage, Data Lake
- Database: Azure SQL, Cosmos DB, PostgreSQL/MySQL Flexible Server, Redis Cache
- Messaging: Service Bus, Event Hub, Event Grid, Queue Storage
- Networking: Virtual Network, Application Gateway, Front Door, Traffic Manager
- IaC: Bicep (preferred), ARM templates, Terraform, Pulumi
- Security: Azure AD/Entra ID, Key Vault, Managed Identity, Defender
- DevOps: Azure DevOps, GitHub Actions integration
- AI: Azure OpenAI Service, Cognitive Services, Machine Learning
- Observability: Application Insights, Azure Monitor, Log Analytics
""",
            # ==================== KUBERNETES ====================
            "kubernetes": """
KUBERNETES CONTEXT:
- Core resources: Pod, Deployment, Service, Ingress, ConfigMap, Secret
- Workloads: StatefulSet, DaemonSet, Job, CronJob
- Storage: PersistentVolume, PersistentVolumeClaim, StorageClass
- Networking: NetworkPolicy, Ingress controllers (nginx, traefik, istio)
- Configuration: Helm charts, Kustomize, kubectl
- GitOps: ArgoCD, Flux
- Service mesh: Istio, Linkerd, Cilium
- Security: RBAC, PodSecurityPolicy/Standards, OPA/Gatekeeper
- Scaling: HPA, VPA, KEDA, Cluster Autoscaler
- Best practices: resource limits, health probes, pod disruption budgets
""",
            # ==================== DOCKER ====================
            "docker": """
DOCKER CONTEXT:
- Dockerfile: multi-stage builds, minimal base images (distroless, alpine)
- Best practices: non-root user, .dockerignore, layer caching, security scanning
- Compose: docker-compose.yml for local dev, networking, volumes
- Registry: Docker Hub, ECR, GCR, ACR, GitHub Container Registry
- Alternatives: Podman, Buildah, containerd
- Optimization: minimize layers, copy only needed files, use COPY over ADD
""",
            # ==================== TERRAFORM ====================
            "terraform": """
TERRAFORM CONTEXT:
- Structure: providers, resources, data sources, modules, outputs, variables
- State: remote backend (S3, GCS, Azure Blob), state locking
- Best practices: version constraints, module composition, workspaces
- Workflow: terraform init/plan/apply, CI/CD integration
- Tools: Terragrunt (DRY), tflint, checkov, infracost
- Alternatives: Pulumi (programming languages), CDKTF, OpenTofu
""",
            # ==================== CI/CD ====================
            "cicd": """
CI/CD CONTEXT:
- GitHub Actions: workflows, jobs, steps, reusable workflows, OIDC
- GitLab CI: .gitlab-ci.yml, stages, jobs, artifacts, environments
- Jenkins: Jenkinsfile, declarative pipeline, shared libraries
- General: build, test, lint, security scan, deploy stages
- Best practices: caching, parallelization, environment promotion, rollback
- GitOps: ArgoCD, Flux for Kubernetes deployments
""",
            # ==================== DATA ENGINEERING ====================
            "data_engineering": """
DATA ENGINEERING CONTEXT:
- Orchestration: Airflow, Dagster, Prefect, Mage, Luigi
- Processing: Spark (PySpark/Scala), Pandas, Polars, Dask, DuckDB
- Storage formats: Parquet, Delta Lake, Iceberg, Avro, ORC
- Warehouses: BigQuery, Snowflake, Redshift, Databricks, Synapse
- Streaming: Kafka, Flink, Spark Streaming, Kinesis, Pulsar
- Quality: Great Expectations, dbt tests, Soda, Monte Carlo
- Architecture: Medallion (bronze/silver/gold), Lambda, Kappa
""",
            # ==================== MACHINE LEARNING ====================
            "machine_learning": """
ML/AI CONTEXT:
- Frameworks: PyTorch (preferred), TensorFlow, JAX, scikit-learn
- LLM/GenAI: OpenAI API, Anthropic Claude, LangChain, LlamaIndex, Hugging Face
- MLOps: MLflow, Weights & Biases, DVC, Kubeflow, SageMaker
- Vector DBs: Pinecone, Weaviate, Qdrant, Chroma, pgvector
- Training: distributed training, hyperparameter tuning, experiment tracking
- Inference: model serving, batching, quantization, TensorRT, ONNX
- Best practices: reproducibility, versioning, monitoring, drift detection
""",
            # ==================== DATABASE ====================
            "database": """
DATABASE CONTEXT:
- SQL: PostgreSQL (preferred), MySQL, SQL Server, SQLite
- NoSQL: MongoDB, Redis, Elasticsearch, Cassandra, DynamoDB
- Graph: Neo4j, Neptune, TigerGraph
- Time-series: TimescaleDB, InfluxDB, Prometheus
- Design: normalization, indexing strategy, query optimization
- Operations: migrations, backups, replication, sharding
- Tools: pgAdmin, DBeaver, DataGrip
""",
            # ==================== MESSAGING ====================
            "messaging": """
MESSAGING CONTEXT:
- Queues: Kafka, RabbitMQ, SQS, Redis Streams, NATS
- Pub/Sub: Google Pub/Sub, SNS/SQS, Azure Service Bus
- Patterns: event-driven, CQRS, event sourcing, saga
- Best practices: idempotency, dead letter queues, ordering, partitioning
- Schema: Avro, Protobuf, JSON Schema, schema registry
""",
            # ==================== MOBILE ====================
            "mobile": """
MOBILE CONTEXT:
- Cross-platform: React Native, Flutter, Capacitor, Ionic
- iOS native: Swift, SwiftUI, UIKit, Combine
- Android native: Kotlin, Jetpack Compose, XML layouts
- State: Redux, MobX, Provider, Riverpod, Bloc
- Navigation: React Navigation, GoRouter, Navigator
- Build: Fastlane, Gradle, Xcode, EAS Build
- Testing: Detox, Maestro, XCTest, Espresso
""",
            # ==================== TESTING ====================
            "testing_quality": """
TESTING CONTEXT:
- Unit: Jest, Vitest, pytest, JUnit 5, xUnit, Go test
- Integration: Supertest, TestContainers, pytest-docker
- E2E: Playwright (preferred), Cypress, Selenium
- API: Postman/Newman, REST Assured, Karate
- Performance: k6, JMeter, Locust, Artillery
- Best practices: AAA pattern, fixtures, mocking, test isolation
- Coverage: aim for meaningful coverage, not 100%
""",
            # ==================== SECURITY ====================
            "security": """
SECURITY CONTEXT:
- Auth: OAuth 2.0/OIDC, JWT, session-based, SAML
- Encryption: TLS 1.3, bcrypt/argon2 for passwords, AES for data
- Secrets: HashiCorp Vault, AWS Secrets Manager, Azure Key Vault
- Web: CORS, CSP, HSTS, XSS prevention, SQL injection prevention
- API: rate limiting, input validation, output encoding
- Compliance: OWASP Top 10, SOC2, GDPR, HIPAA, PCI-DSS
- Tools: Snyk, SonarQube, SAST/DAST, dependency scanning
""",
            # ==================== PERFORMANCE ====================
            "performance": """
PERFORMANCE CONTEXT:
- Caching: Redis, Memcached, CDN, browser cache, application cache
- Database: indexing, query optimization, connection pooling, read replicas
- Profiling: flame graphs, APM tools, Chrome DevTools
- Frontend: Core Web Vitals, lazy loading, code splitting, tree shaking
- Backend: async I/O, connection pooling, batching, pagination
- Load testing: k6, JMeter, Locust, Gatling
""",
            # ==================== BLOCKCHAIN ====================
            "blockchain": """
BLOCKCHAIN/WEB3 CONTEXT:
- Ethereum: Solidity, Hardhat, Foundry, ethers.js, viem, wagmi
- Other chains: Solana (Rust/Anchor), Polygon, Arbitrum, Base
- Concepts: smart contracts, ERC standards, gas optimization
- Testing: Hardhat tests, Foundry tests, mainnet forking
- Security: reentrancy, overflow, access control, audits
- Infrastructure: Alchemy, Infura, The Graph, IPFS
""",
            # ==================== OBSERVABILITY ====================
            "observability": """
OBSERVABILITY CONTEXT:
- Metrics: Prometheus, Grafana, DataDog, CloudWatch, Azure Monitor
- Logging: ELK Stack, Loki, Splunk, structured logging (JSON)
- Tracing: Jaeger, Zipkin, OpenTelemetry, X-Ray, Application Insights
- APM: New Relic, Dynatrace, DataDog APM
- Alerting: PagerDuty, Opsgenie, AlertManager
- Best practices: golden signals (latency, traffic, errors, saturation)
""",
            # ==================== API DESIGN ====================
            "api_design": """
API DESIGN CONTEXT:
- REST: resource-based URLs, proper HTTP methods, status codes, HATEOAS
- GraphQL: schema-first, resolvers, N+1 prevention, DataLoader
- gRPC: protobuf, streaming, service definitions
- OpenAPI/Swagger: spec-first design, code generation
- Versioning: URL path, header, query param strategies
- Best practices: pagination, filtering, rate limiting, caching headers
""",
            # ==================== RUBY ====================
            "ruby": """
RUBY CONTEXT:
- Framework: Ruby on Rails (7.x), Sinatra, Hanami
- ORM: ActiveRecord, Sequel
- Background jobs: Sidekiq, Resque, Good Job
- Testing: RSpec, Minitest, Capybara, FactoryBot
- Best practices: Convention over Configuration, RESTful design, concerns
""",
            # ==================== PHP ====================
            "php": """
PHP CONTEXT:
- Framework: Laravel (10.x/11.x), Symfony, CodeIgniter
- ORM: Eloquent, Doctrine
- Package manager: Composer
- Testing: PHPUnit, Pest, Mockery
- Best practices: PSR standards, dependency injection, modern PHP 8.x features
""",
            # ==================== ELIXIR ====================
            "elixir": """
ELIXIR CONTEXT:
- Framework: Phoenix (LiveView for real-time), Plug
- ORM: Ecto
- Concepts: OTP, GenServer, Supervisor, processes, message passing
- Testing: ExUnit
- Best practices: functional programming, immutability, pattern matching
""",
            # ==================== KOTLIN ====================
            "kotlin": """
KOTLIN CONTEXT:
- Frameworks: Ktor, Spring Boot with Kotlin, Exposed
- Concepts: coroutines, Flow, null safety, data classes
- Multiplatform: KMP/KMM for shared code
- Android: Jetpack Compose, ViewModel, Hilt
- Testing: Kotest, MockK
""",
            # ==================== SWIFT ====================
            "swift": """
SWIFT CONTEXT:
- UI: SwiftUI (preferred), UIKit
- Concepts: async/await, actors, Combine, property wrappers
- Architecture: MVVM, TCA (Composable Architecture)
- Networking: URLSession, Alamofire
- Testing: XCTest, Swift Testing (new)
- Package manager: Swift Package Manager (SPM)
""",
            # ==================== GAME DEV ====================
            "gamedev": """
GAME DEVELOPMENT CONTEXT:
- Engines: Unity (C#), Unreal (C++/Blueprints), Godot (GDScript/C#)
- Concepts: game loop, ECS, physics, rendering, shaders
- Multiplayer: Netcode, Photon, Mirror, dedicated servers
- Performance: object pooling, LOD, batching, profiling
""",
            # ==================== EMBEDDED ====================
            "embedded": """
EMBEDDED/IOT CONTEXT:
- Platforms: Arduino, ESP32, Raspberry Pi, STM32
- RTOS: FreeRTOS, Zephyr, RIOT
- Protocols: I2C, SPI, UART, CAN, MQTT
- Languages: C (primary), C++, Rust (growing), MicroPython
- Tools: PlatformIO, Arduino IDE, STM32CubeIDE
""",
            # ==================== FUNCTIONAL ====================
            "functional": """
FUNCTIONAL PROGRAMMING CONTEXT:
- Languages: Haskell, OCaml, F#, Clojure, Elm
- Concepts: immutability, pure functions, higher-order functions
- Patterns: monads, functors, applicatives, algebraic data types
- Benefits: predictability, testability, parallelism
""",
        }

        for domain in domains:
            if domain in domain_knowledge:
                context_parts.append(domain_knowledge[domain])

        # Add project-specific context
        if project_info and project_info.dependencies:
            dep_list = list(project_info.dependencies.keys())[:20]
            context_parts.append(f"\nPROJECT DEPENDENCIES: {', '.join(dep_list)}")

        # Enhanced domain knowledge for code generation
        try:
            from backend.services.domain_knowledge import (
                get_domain_context as get_enhanced_context,
                DomainType,
            )

            # Map our domains to the enhanced domain types
            domain_mapping = {
                "web_backend": [DomainType.BACKEND_PYTHON, DomainType.BACKEND_NODE],
                "web_frontend": [DomainType.FRONTEND_REACT, DomainType.FRONTEND_VUE],
                "devops_infrastructure": [
                    DomainType.DEVOPS_DOCKER,
                    DomainType.DEVOPS_CICD,
                ],
                "data_engineering": [DomainType.DATA_PANDAS, DomainType.DATA_SQL],
            }

            for domain in domains:
                if domain in domain_mapping:
                    for enhanced_domain in domain_mapping[domain]:
                        enhanced_ctx = get_enhanced_context(enhanced_domain)
                        if enhanced_ctx:
                            context_parts.append(enhanced_ctx)
                            break  # Only add one enhanced context per domain
        except ImportError:
            pass  # Domain knowledge module not available

        return "\n".join(context_parts)

    @classmethod
    def get_runtime_context(cls, workspace_path: str) -> Dict[str, Any]:
        """
        Gather runtime context that helps the LLM understand the current environment.
        """
        import platform
        import shutil

        context: Dict[str, Any] = {
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }

        # Check for common tools
        tools_available: Dict[str, bool] = {}
        for tool in [
            "node",
            "npm",
            "yarn",
            "pnpm",
            "python",
            "pip",
            "docker",
            "git",
            "go",
            "cargo",
        ]:
            tools_available[tool] = shutil.which(tool) is not None
        context["tools_available"] = tools_available

        # Check for environment hints
        env_hints: Dict[str, str] = {}
        for var in ["NODE_ENV", "PYTHON_ENV", "ENVIRONMENT", "CI", "DOCKER"]:
            value = os.getenv(var)
            if value is not None:
                env_hints[var] = value
        context["environment"] = env_hints

        return context

    @classmethod
    async def enrich_context(
        cls,
        message: str,
        project_info: Optional[ProjectInfo],
        workspace_path: str,
        enable_web_search: bool = True,
    ) -> Dict[str, Any]:
        """
        Main method: Enrich the context for the LLM based on the request.

        This is the key to handling "millions of requests":
        1. Detect what domains the request touches
        2. Gather relevant domain-specific context
        3. Check runtime environment
        4. Check for missing tools and offer installation
        5. Perform web search if needed for unknown topics
        6. Return enriched context for the LLM

        The LLM then uses this context to generate an appropriate response.
        """
        domains = cls.detect_domains(message, project_info)
        domain_context = cls.get_domain_context(domains, project_info)
        runtime_context = cls.get_runtime_context(workspace_path)

        # Check for port-related requests - use dynamic port detection
        port_context = None
        if any(
            word in message.lower()
            for word in ["run", "start", "server", "dev", "localhost", "port"]
        ):
            try:
                # Pass project_info for intelligent port detection (not hardcoded 3000)
                port_context = await PortManager.get_port_context_for_llm(
                    preferred_port=None,  # Let NaviConfig determine from project
                    project_info=project_info,
                )
            except Exception:
                pass

        # Check for missing tools and generate installation suggestions
        missing_tools = []
        tool_install_actions = []
        try:
            required_tools = ToolInstaller.detect_required_tools(project_info, message)
            missing_tools = ToolInstaller.get_missing_tools(required_tools)
            if missing_tools:
                tool_install_actions = ToolInstaller.generate_install_actions(
                    missing_tools
                )
        except Exception as e:
            logger.warning(f"Tool detection failed: {e}")

        # Perform web search if beneficial
        web_search_results = None
        web_search_context = ""
        if enable_web_search and WebSearchProvider.should_search(message, project_info):
            try:
                # Create a search query from the message
                search_query = message[:200]  # Limit query length
                web_search_results = await WebSearchProvider.search(
                    search_query, max_results=5
                )
                if web_search_results.get("results"):
                    web_search_context = (
                        WebSearchProvider.format_search_results_for_llm(
                            web_search_results
                        )
                    )
            except Exception as e:
                logger.warning(f"Web search failed (non-fatal): {e}")

        # Detect project coding standards for consistent code generation
        project_standards_context = ""
        try:
            # Import here to avoid circular dependency (class defined below)
            standards = await ProjectStandardsDetector.detect(workspace_path)
            project_standards_context = standards.to_prompt_context()
        except Exception as e:
            logger.warning(f"Standards detection failed (non-fatal): {e}")

        # Check if task needs decomposition for complex end-to-end work
        task_plan_context = ""
        if TaskDecomposer.needs_decomposition(message):
            try:
                plan = TaskDecomposer.decompose(message, project_info)
                task_plan_context = plan.to_summary()
            except Exception as e:
                logger.warning(f"Task decomposition failed (non-fatal): {e}")

        return {
            "detected_domains": domains,
            "domain_context": domain_context,
            "runtime": runtime_context,
            "port_context": port_context,
            "project_analysis": (
                project_info.to_context_string() if project_info else None
            ),
            # Tool installation support
            "missing_tools": missing_tools,
            "tool_install_actions": tool_install_actions,
            "missing_tools_message": (
                ToolInstaller.format_missing_tools_message(missing_tools)
                if missing_tools
                else None
            ),
            # Web search results
            "web_search_results": web_search_results,
            "web_search_context": web_search_context,
            "web_search_performed": bool(
                web_search_results and web_search_results.get("results")
            ),
            # Project coding standards for consistent code generation
            "project_standards": project_standards_context,
            # Task plan for complex multi-step tasks
            "task_plan": task_plan_context,
            "is_complex_task": bool(task_plan_context),
        }


# ==================== PROJECT STANDARDS DETECTION ====================


@dataclass
class ProjectStandards:
    """
    Detected coding standards and conventions from project configuration.
    This enables NAVI to generate code that matches project style.
    """

    # Code style
    indent_style: str = "spaces"  # "spaces" or "tabs"
    indent_size: int = 2
    quote_style: str = "single"  # "single" or "double"
    semicolons: bool = True
    trailing_comma: str = "es5"  # "none", "es5", "all"

    # TypeScript/JavaScript
    strict_mode: bool = True
    use_typescript: bool = False
    ts_strict: bool = False
    module_system: str = "esm"  # "esm", "commonjs"

    # Naming conventions (detected from existing code)
    component_naming: str = "PascalCase"
    file_naming: str = "kebab-case"  # or "camelCase", "PascalCase"
    variable_naming: str = "camelCase"
    constant_naming: str = "SCREAMING_SNAKE_CASE"

    # Project patterns
    import_order: List[str] = field(
        default_factory=lambda: ["builtin", "external", "internal", "relative"]
    )
    export_style: str = "named"  # "named", "default", "mixed"

    # Testing conventions
    test_framework: Optional[str] = None
    test_file_pattern: str = "*.test.ts"
    test_location: str = "__tests__"  # or "same-directory", "test/"

    # Documentation
    doc_style: str = "jsdoc"  # "jsdoc", "tsdoc", "none"
    require_docs: bool = False

    # Linting rules (key patterns detected)
    eslint_rules: Dict[str, Any] = field(default_factory=dict)

    # Detected from existing code analysis
    avg_function_length: int = 30
    max_file_length: int = 500
    prefer_arrow_functions: bool = True
    prefer_const: bool = True

    def to_prompt_context(self) -> str:
        """Convert to LLM prompt context"""
        parts = ["PROJECT CODE STANDARDS (follow these conventions):"]

        parts.append(f"- Indentation: {self.indent_size} {self.indent_style}")
        parts.append(f"- Quotes: {self.quote_style}")
        parts.append(f"- Semicolons: {'yes' if self.semicolons else 'no'}")
        parts.append(f"- Module system: {self.module_system}")

        if self.use_typescript:
            parts.append(f"- TypeScript: yes (strict: {self.ts_strict})")

        parts.append(f"- Component naming: {self.component_naming}")
        parts.append(f"- File naming: {self.file_naming}")
        parts.append(f"- Prefer const: {self.prefer_const}")
        parts.append(f"- Arrow functions: {self.prefer_arrow_functions}")

        if self.test_framework:
            parts.append(f"- Test framework: {self.test_framework}")
            parts.append(f"- Test files: {self.test_file_pattern}")

        return "\n".join(parts)


class ProjectStandardsDetector:
    """
    Detects project coding standards from configuration files and existing code.
    This is critical for end-to-end development - generated code must match project style.
    """

    @classmethod
    async def detect(cls, workspace_path: str) -> ProjectStandards:
        """Analyze project to detect coding standards"""
        standards = ProjectStandards()
        workspace = Path(workspace_path)

        # Read configuration files in parallel
        config_results = await asyncio.gather(
            cls._read_eslint_config(workspace),
            cls._read_prettier_config(workspace),
            cls._read_tsconfig(workspace),
            cls._read_editorconfig(workspace),
            cls._read_package_json(workspace),
            return_exceptions=True,
        )

        (
            eslint_config,
            prettier_config,
            tsconfig,
            editorconfig,
            package_json,
        ) = config_results

        # Apply detected settings (priority: editorconfig > prettier > eslint)
        if isinstance(editorconfig, dict):
            if "indent_style" in editorconfig:
                standards.indent_style = editorconfig["indent_style"]
            if "indent_size" in editorconfig:
                standards.indent_size = int(editorconfig.get("indent_size", 2))

        if isinstance(prettier_config, dict):
            standards.indent_size = prettier_config.get(
                "tabWidth", standards.indent_size
            )
            standards.indent_style = (
                "tabs" if prettier_config.get("useTabs") else "spaces"
            )
            standards.quote_style = (
                "single" if prettier_config.get("singleQuote") else "double"
            )
            standards.semicolons = prettier_config.get("semi", True)
            standards.trailing_comma = prettier_config.get("trailingComma", "es5")

        if isinstance(tsconfig, dict):
            standards.use_typescript = True
            compiler_options = tsconfig.get("compilerOptions", {})
            standards.ts_strict = compiler_options.get("strict", False)
            standards.module_system = (
                "esm" if "ESNext" in compiler_options.get("module", "") else "commonjs"
            )

        if isinstance(eslint_config, dict):
            rules = eslint_config.get("rules", {})
            standards.eslint_rules = rules
            # Detect specific rules
            if "prefer-const" in rules:
                standards.prefer_const = rules["prefer-const"] != "off"
            if "prefer-arrow-callback" in rules:
                standards.prefer_arrow_functions = (
                    rules["prefer-arrow-callback"] != "off"
                )

        if isinstance(package_json, dict):
            # Detect test framework
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }
            if "jest" in deps:
                standards.test_framework = "jest"
                standards.test_file_pattern = "*.test.{ts,tsx,js,jsx}"
            elif "vitest" in deps:
                standards.test_framework = "vitest"
                standards.test_file_pattern = "*.test.{ts,tsx}"
            elif "mocha" in deps:
                standards.test_framework = "mocha"
                standards.test_file_pattern = "*.spec.{ts,js}"
            elif "pytest" in str(deps) or (workspace / "pytest.ini").exists():
                standards.test_framework = "pytest"
                standards.test_file_pattern = "test_*.py"

        # Analyze existing code to detect patterns
        await cls._analyze_existing_code(workspace, standards)

        return standards

    @classmethod
    async def _read_eslint_config(cls, workspace: Path) -> Optional[Dict]:
        """Read ESLint configuration"""
        eslint_files = [
            ".eslintrc.json",
            ".eslintrc.js",
            ".eslintrc.yml",
            ".eslintrc.yaml",
            ".eslintrc",
            "eslint.config.js",
        ]
        for filename in eslint_files:
            config_path = workspace / filename
            if config_path.exists():
                try:
                    content = config_path.read_text()
                    if filename.endswith(".json") or filename == ".eslintrc":
                        return json.loads(content)
                    elif filename.endswith((".yml", ".yaml")):
                        # Simple YAML parsing for common cases
                        return cls._simple_yaml_parse(content)
                except Exception:
                    pass
        return None

    @classmethod
    async def _read_prettier_config(cls, workspace: Path) -> Optional[Dict]:
        """Read Prettier configuration"""
        prettier_files = [
            ".prettierrc",
            ".prettierrc.json",
            ".prettierrc.js",
            ".prettierrc.yml",
            ".prettierrc.yaml",
            "prettier.config.js",
        ]
        for filename in prettier_files:
            config_path = workspace / filename
            if config_path.exists():
                try:
                    content = config_path.read_text()
                    if filename.endswith(".json") or filename == ".prettierrc":
                        return json.loads(content)
                    elif filename.endswith((".yml", ".yaml")):
                        return cls._simple_yaml_parse(content)
                except Exception:
                    pass

        # Check package.json for prettier config
        pkg_path = workspace / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                if "prettier" in pkg:
                    return pkg["prettier"]
            except Exception:
                pass
        return None

    @classmethod
    async def _read_tsconfig(cls, workspace: Path) -> Optional[Dict]:
        """Read TypeScript configuration"""
        tsconfig_path = workspace / "tsconfig.json"
        if tsconfig_path.exists():
            try:
                content = tsconfig_path.read_text()
                # Remove comments (TypeScript config allows them)
                content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
                content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
                return json.loads(content)
            except Exception:
                pass
        return None

    @classmethod
    async def _read_editorconfig(cls, workspace: Path) -> Optional[Dict]:
        """Read EditorConfig"""
        editorconfig_path = workspace / ".editorconfig"
        if editorconfig_path.exists():
            try:
                content = editorconfig_path.read_text()
                config = {}
                for line in content.split("\n"):
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
                return config
            except Exception:
                pass
        return None

    @classmethod
    async def _read_package_json(cls, workspace: Path) -> Optional[Dict]:
        """Read package.json"""
        pkg_path = workspace / "package.json"
        if pkg_path.exists():
            try:
                return json.loads(pkg_path.read_text())
            except Exception:
                pass
        return None

    @classmethod
    def _simple_yaml_parse(cls, content: str) -> Dict:
        """Simple YAML parsing for basic configs"""
        result = {}
        for line in content.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                # Handle basic types
                if value.lower() == "true":
                    result[key] = True
                elif value.lower() == "false":
                    result[key] = False
                elif value.isdigit():
                    result[key] = int(value)
                elif value.startswith('"') and value.endswith('"'):
                    result[key] = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    result[key] = value[1:-1]
                else:
                    result[key] = value
        return result

    @classmethod
    async def _analyze_existing_code(cls, workspace: Path, standards: ProjectStandards):
        """Analyze existing code files to detect patterns"""
        # Find source files
        source_patterns = ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py"]
        sample_files = []

        for pattern in source_patterns:
            files = list(workspace.glob(pattern))
            # Exclude node_modules, dist, etc.
            files = [
                f
                for f in files
                if not any(
                    exc in str(f)
                    for exc in ["node_modules", "dist", "build", ".next", "__pycache__"]
                )
            ]
            sample_files.extend(files[:5])  # Sample up to 5 files per pattern

        if not sample_files:
            return

        # Analyze file naming convention
        file_names = [f.stem for f in sample_files]
        if any("-" in name for name in file_names):
            standards.file_naming = "kebab-case"
        elif any(name[0].isupper() for name in file_names):
            standards.file_naming = "PascalCase"
        else:
            standards.file_naming = "camelCase"

        # Sample content analysis
        for sample_file in sample_files[:3]:
            try:
                content = sample_file.read_text()

                # Detect quote style from imports
                single_quotes = content.count("'")
                double_quotes = content.count('"')
                if single_quotes > double_quotes * 1.5:
                    standards.quote_style = "single"
                elif double_quotes > single_quotes * 1.5:
                    standards.quote_style = "double"

                # Detect arrow function preference
                arrow_count = content.count("=>")
                function_count = content.count("function ")
                if arrow_count > function_count:
                    standards.prefer_arrow_functions = True

                # Detect const preference
                const_count = content.count("const ")
                let_count = content.count("let ")
                var_count = content.count("var ")
                if const_count > (let_count + var_count):
                    standards.prefer_const = True

            except Exception:
                pass


# ==================== TASK DECOMPOSITION ====================


@dataclass
class TaskStep:
    """A single step in a decomposed task"""

    id: str
    description: str
    action_type: (
        str  # "create_file", "modify_file", "run_command", "verify", "research"
    )
    target: Optional[str] = None  # file path or command
    dependencies: List[str] = field(
        default_factory=list
    )  # IDs of steps this depends on
    status: str = (
        "pending"  # "pending", "in_progress", "completed", "failed", "skipped"
    )
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class TaskPlan:
    """A complete plan for executing a complex task"""

    id: str
    original_request: str
    steps: List[TaskStep] = field(default_factory=list)
    status: str = "planning"  # "planning", "executing", "completed", "failed", "paused"
    current_step_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)

    def to_summary(self) -> str:
        """Generate a human-readable summary of the plan"""
        completed = sum(1 for s in self.steps if s.status == "completed")
        total = len(self.steps)

        lines = [
            f"**Task Plan** ({completed}/{total} steps completed)",
            f"Request: {self.original_request[:100]}...",
            "",
            "**Steps:**",
        ]

        for i, step in enumerate(self.steps, 1):
            status_icon = {
                "pending": "⬜",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌",
                "skipped": "⏭️",
            }.get(step.status, "⬜")
            lines.append(f"{status_icon} {i}. {step.description}")

        return "\n".join(lines)


class TaskDecomposer:
    """
    Decomposes complex tasks into manageable steps.
    This enables NAVI to handle end-to-end development without breaking.
    """

    # Patterns that indicate complex tasks needing decomposition
    COMPLEX_TASK_INDICATORS = [
        "end to end",
        "e2e",
        "full stack",
        "complete",
        "entire",
        "from scratch",
        "build",
        "implement",
        "create application",
        "add feature",
        "refactor",
        "migrate",
        "upgrade",
        "setup",
        "configure",
        "integrate",
    ]

    @classmethod
    def needs_decomposition(cls, message: str, estimated_files: int = 0) -> bool:
        """Determine if a task needs to be broken down into steps"""
        message_lower = message.lower()

        # Check for complexity indicators
        has_complex_indicator = any(
            indicator in message_lower for indicator in cls.COMPLEX_TASK_INDICATORS
        )

        # Multiple actions in one request
        action_words = [
            "create",
            "add",
            "modify",
            "update",
            "fix",
            "install",
            "configure",
            "test",
        ]
        action_count = sum(1 for word in action_words if word in message_lower)

        # Estimated scope
        is_large_scope = estimated_files > 5 or action_count >= 3

        return has_complex_indicator or is_large_scope

    @classmethod
    def decompose(
        cls, message: str, project_info: Optional[ProjectInfo] = None
    ) -> TaskPlan:
        """
        Create a task plan by decomposing the request into steps.

        The actual step generation is done by the LLM, but this provides
        the structure and common patterns.
        """
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        plan = TaskPlan(id=plan_id, original_request=message)

        # Add common initial steps based on patterns
        message_lower = message.lower()

        # Research/analysis step (always first for complex tasks)
        plan.steps.append(
            TaskStep(
                id=f"{plan_id}-research",
                description="Analyze existing code and project structure",
                action_type="research",
                dependencies=[],
            )
        )

        # Detect common patterns and add appropriate steps
        if any(word in message_lower for word in ["create", "build", "new"]):
            plan.steps.extend(
                [
                    TaskStep(
                        id=f"{plan_id}-structure",
                        description="Create file/folder structure",
                        action_type="create_file",
                        dependencies=[f"{plan_id}-research"],
                    ),
                    TaskStep(
                        id=f"{plan_id}-implement",
                        description="Implement core functionality",
                        action_type="create_file",
                        dependencies=[f"{plan_id}-structure"],
                    ),
                ]
            )

        if (
            any(word in message_lower for word in ["test", "spec", "verify"])
            or "with tests" in message_lower
        ):
            plan.steps.append(
                TaskStep(
                    id=f"{plan_id}-test",
                    description="Create and run tests",
                    action_type="run_command",
                    target="test",
                    dependencies=(
                        [f"{plan_id}-implement"]
                        if f"{plan_id}-implement" in [s.id for s in plan.steps]
                        else []
                    ),
                )
            )

        # Always add verification step
        plan.steps.append(
            TaskStep(
                id=f"{plan_id}-verify",
                description="Verify implementation works correctly",
                action_type="verify",
                dependencies=[s.id for s in plan.steps if s.id != f"{plan_id}-verify"],
            )
        )

        return plan


# ==================== SELF-HEALING & ERROR RECOVERY ====================


@dataclass
class ErrorDiagnosis:
    """Diagnosis of an error with recovery suggestions"""

    error_type: str  # "syntax", "type", "runtime", "dependency", "permission", "network", "unknown"
    error_message: str
    likely_cause: str
    suggested_fixes: List[str]
    auto_fixable: bool
    recovery_actions: List[Dict[str, Any]]


class SelfHealingEngine:
    """
    Provides self-healing capabilities for NAVI.
    When errors occur, this engine:
    1. Diagnoses the root cause
    2. Suggests or applies fixes
    3. Retries operations with adjustments
    4. Learns from failures to prevent recurrence
    """

    # Port memory: workspace_path -> last_used_port
    _port_memory: Dict[str, int] = {}

    # Common error patterns and their fixes
    ERROR_PATTERNS = {
        # Dependency errors
        r"Cannot find module '([^']+)'": {
            "type": "dependency",
            "cause": "Missing npm/node module",
            "fix_template": "npm install {0}",
            "auto_fixable": True,
        },
        r"ModuleNotFoundError: No module named '([^']+)'": {
            "type": "dependency",
            "cause": "Missing Python package",
            "fix_template": "pip install {0}",
            "auto_fixable": True,
        },
        r"ImportError: cannot import name '([^']+)'": {
            "type": "dependency",
            "cause": "Import error - package may need update",
            "fix_template": "pip install --upgrade {0}",
            "auto_fixable": True,
        },
        # Type errors
        r"TypeError: .* is not a function": {
            "type": "type",
            "cause": "Calling non-function as function",
            "fix_template": "Check import and ensure correct usage",
            "auto_fixable": False,
        },
        r"Type '([^']+)' is not assignable to type '([^']+)'": {
            "type": "type",
            "cause": "TypeScript type mismatch",
            "fix_template": "Fix type annotation or add type assertion",
            "auto_fixable": False,
        },
        # Syntax errors
        r"SyntaxError: Unexpected token": {
            "type": "syntax",
            "cause": "Invalid syntax in code",
            "fix_template": "Review and fix syntax",
            "auto_fixable": False,
        },
        r"SyntaxError: invalid syntax": {
            "type": "syntax",
            "cause": "Invalid Python syntax",
            "fix_template": "Review and fix syntax",
            "auto_fixable": False,
        },
        # Permission errors
        r"EACCES: permission denied": {
            "type": "permission",
            "cause": "Insufficient file system permissions",
            "fix_template": "Check file permissions or run with appropriate privileges",
            "auto_fixable": False,
        },
        r"PermissionError: \[Errno 13\]": {
            "type": "permission",
            "cause": "Python permission denied",
            "fix_template": "Check file/directory permissions",
            "auto_fixable": False,
        },
        # Network errors
        r"ECONNREFUSED": {
            "type": "network",
            "cause": "Connection refused - service may not be running",
            "fix_template": "Start the required service or check the port",
            "auto_fixable": False,
        },
        r"ETIMEDOUT|ENOTFOUND": {
            "type": "network",
            "cause": "Network timeout or DNS resolution failed",
            "fix_template": "Check network connection and URL",
            "auto_fixable": False,
        },
        # Port errors
        r"EADDRINUSE.*:(\d+)": {
            "type": "port",
            "cause": "Port already in use",
            "fix_template": "Kill process on port or use different port",
            "auto_fixable": True,
        },
        # Build errors
        r"error TS\d+:": {
            "type": "typescript",
            "cause": "TypeScript compilation error",
            "fix_template": "Fix TypeScript errors",
            "auto_fixable": False,
        },
        r"ESLint:.*error": {
            "type": "lint",
            "cause": "ESLint rule violation",
            "fix_template": "Fix linting errors or disable rule",
            "auto_fixable": True,
        },
    }

    @classmethod
    def diagnose(
        cls, error: str, context: Optional[Dict[str, Any]] = None
    ) -> ErrorDiagnosis:
        """Diagnose an error and suggest fixes"""
        error_str = str(error)

        for pattern, info in cls.ERROR_PATTERNS.items():
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                # Extract captured groups for fix template
                groups = match.groups() if match.groups() else []
                fix = info["fix_template"]
                if groups:
                    try:
                        fix = fix.format(*groups)
                    except (IndexError, KeyError):
                        pass

                recovery_actions = cls._generate_recovery_actions(
                    info["type"], fix, groups, context
                )

                return ErrorDiagnosis(
                    error_type=info["type"],
                    error_message=error_str,
                    likely_cause=info["cause"],
                    suggested_fixes=[fix],
                    auto_fixable=info["auto_fixable"],
                    recovery_actions=recovery_actions,
                )

        # Unknown error - provide generic diagnosis
        return ErrorDiagnosis(
            error_type="unknown",
            error_message=error_str,
            likely_cause="Unknown error occurred",
            suggested_fixes=[
                "Review the error message",
                "Check logs for details",
                "Try a different approach",
            ],
            auto_fixable=False,
            recovery_actions=[],
        )

    @classmethod
    def _get_configured_port(cls, workspace_path: str) -> Optional[int]:
        """
        Read project config files to find the configured port.
        Checks: vite.config.ts, vite.config.js, next.config.js, package.json, .env
        """
        import json
        import re

        workspace = Path(workspace_path)

        # Check Vite config (TypeScript)
        vite_config_ts = workspace / "vite.config.ts"
        if vite_config_ts.exists():
            try:
                content = vite_config_ts.read_text()
                match = re.search(r"port:\s*(\d+)", content)
                if match:
                    return int(match.group(1))
            except Exception:
                pass

        # Check Vite config (JavaScript)
        vite_config_js = workspace / "vite.config.js"
        if vite_config_js.exists():
            try:
                content = vite_config_js.read_text()
                match = re.search(r"port:\s*(\d+)", content)
                if match:
                    return int(match.group(1))
            except Exception:
                pass

        # Check Next.js config
        next_config = workspace / "next.config.js"
        if next_config.exists():
            try:
                content = next_config.read_text()
                match = re.search(r"port:\s*(\d+)", content)
                if match:
                    return int(match.group(1))
            except Exception:
                pass

        # Check package.json scripts
        package_json = workspace / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                scripts = data.get("scripts", {})
                # Join scripts with space to prevent token merging (e.g., "3000npm" → "3000 npm")
                dev_script = " ".join(
                    [scripts.get("dev", ""), scripts.get("start", "")]
                )
                # Look for port flags in scripts
                match = re.search(r"--port[=\s]+(\d+)|PORT=(\d+)", dev_script)
                if match:
                    return int(match.group(1) or match.group(2))
            except Exception:
                pass

        # Check .env files
        for env_file in [".env.local", ".env.development", ".env"]:
            env_path = workspace / env_file
            if env_path.exists():
                try:
                    content = env_path.read_text()
                    match = re.search(r"PORT=(\d+)", content)
                    if match:
                        return int(match.group(1))
                except Exception:
                    pass

        return None

    @classmethod
    async def _identify_process_owner(
        cls, port: int, workspace_path: str
    ) -> Dict[str, Any]:
        """
        Identify if the process on a port belongs to this workspace or another project.
        Returns: {
            "is_same_project": bool,
            "is_related": bool,  # e.g., different port of same server
            "workspace": str,  # path to the owning workspace
            "reason": str
        }
        """
        import subprocess

        # Get process info
        port_status = await PortManager.check_port(port)
        if port_status.is_available or not port_status.process_pid:
            return {
                "is_same_project": False,
                "is_related": False,
                "workspace": "",
                "reason": "No process found",
            }

        try:
            # Get process command and working directory
            if sys.platform == "darwin":
                # macOS: use lsof to get process cwd
                # Run in thread pool to avoid blocking event loop
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["lsof", "-a", "-p", str(port_status.process_pid), "-d", "cwd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                cwd_line = [
                    line for line in result.stdout.split("\n") if "cwd" in line.lower()
                ]
                if cwd_line:
                    # Extract directory path from lsof output
                    parts = cwd_line[0].split()
                    if len(parts) >= 9:
                        process_cwd = parts[-1]
                        workspace_path_resolved = str(Path(workspace_path).resolve())
                        process_cwd_resolved = str(Path(process_cwd).resolve())

                        if process_cwd_resolved == workspace_path_resolved:
                            return {
                                "is_same_project": True,
                                "is_related": True,
                                "workspace": process_cwd,
                                "reason": "Same workspace - server already running",
                            }
                        elif (
                            workspace_path_resolved in process_cwd_resolved
                            or process_cwd_resolved in workspace_path_resolved
                        ):
                            return {
                                "is_same_project": False,
                                "is_related": True,
                                "workspace": process_cwd,
                                "reason": "Related workspace (parent/child directory)",
                            }
                        else:
                            return {
                                "is_same_project": False,
                                "is_related": False,
                                "workspace": process_cwd,
                                "reason": "Different project entirely",
                            }

            # Fallback: just check command
            cmd = port_status.process_command or ""
            if workspace_path in cmd:
                return {
                    "is_same_project": True,
                    "is_related": True,
                    "workspace": workspace_path,
                    "reason": "Workspace path in command",
                }

        except Exception as e:
            logger.debug(f"Could not identify process owner: {e}")

        return {
            "is_same_project": False,
            "is_related": False,
            "workspace": "",
            "reason": "Unknown - could not determine",
        }

    @classmethod
    def _generate_recovery_actions(
        cls,
        error_type: str,
        fix: str,
        captured_groups: Sequence[Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate specific recovery actions based on error type"""
        actions = []

        if error_type == "dependency":
            # Add package installation action
            actions.append(
                {
                    "type": "runCommand",
                    "command": fix,
                    "description": "Installing missing dependency",
                    "auto_execute": True,
                }
            )

        elif error_type == "port":
            # Port conflict handling - using backward-compatible action types
            # Use existing action types (checkPort/killPort/findPort) that executor supports
            port = 3000
            if captured_groups:
                first_group = captured_groups[0]
                try:
                    port = int(first_group)
                except (TypeError, ValueError):
                    logger.warning(
                        "Invalid port value in captured_groups[0]: %r; falling back to default port %d",
                        first_group,
                        port,
                    )

            # Provide sequence of actions for intelligent port recovery
            # These actions are recognized by the existing recovery executor
            actions.extend(
                [
                    {
                        "type": "checkPort",
                        "port": port,
                        "description": f"Check what's using port {port}",
                        "auto_execute": False,
                    },
                    {
                        "type": "killPort",
                        "port": port,
                        "description": f"Kill process on port {port}",
                        "auto_execute": False,  # Requires user confirmation
                    },
                    {
                        "type": "findPort",
                        "port": port,
                        "description": f"Find alternative port near {port}",
                        "auto_execute": True,
                    },
                ]
            )

        elif error_type == "lint":
            actions.append(
                {
                    "type": "runCommand",
                    "command": "npm run lint -- --fix",
                    "description": "Auto-fix linting errors",
                    "auto_execute": True,
                }
            )

        return actions

    @classmethod
    async def attempt_recovery(
        cls,
        error: str,
        failed_action: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Attempt to recover from an error.

        Returns a recovery plan with actions to take.
        """
        diagnosis = cls.diagnose(error, context)

        result = {
            "diagnosis": diagnosis,
            "can_recover": diagnosis.auto_fixable and retry_count < 3,
            "recovery_plan": [],
            "message": "",
        }

        if diagnosis.auto_fixable and retry_count < 3:
            result["recovery_plan"] = diagnosis.recovery_actions
            result["message"] = (
                f"Attempting automatic recovery: {diagnosis.likely_cause}"
            )
        else:
            result["message"] = (
                f"Manual intervention needed: {diagnosis.likely_cause}\n\nSuggested fixes:\n"
                + "\n".join(f"- {fix}" for fix in diagnosis.suggested_fixes)
            )

        return result


# ==================== CHECKPOINT & ROLLBACK ====================


@dataclass
class Checkpoint:
    """A snapshot of project state at a point in time"""

    id: str
    timestamp: datetime
    description: str
    task_plan_id: Optional[str]
    step_index: int
    files_state: Dict[str, str]  # file_path -> content hash
    git_commit: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """
    Manages checkpoints for rollback capability.
    Enables NAVI to recover from failures by rolling back to known good states.
    """

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.checkpoints: List[Checkpoint] = []
        self.checkpoint_dir = self.workspace_path / ".navi" / "checkpoints"

    async def create_checkpoint(
        self,
        description: str,
        task_plan_id: Optional[str] = None,
        step_index: int = 0,
        files_to_track: Optional[List[str]] = None,
    ) -> Checkpoint:
        """Create a checkpoint of current state"""
        import hashlib

        checkpoint_id = f"cp-{uuid.uuid4().hex[:8]}"

        # Hash tracked files
        files_state = {}
        if files_to_track:
            for file_path in files_to_track:
                full_path = self.workspace_path / file_path
                if full_path.exists():
                    content = full_path.read_bytes()
                    files_state[file_path] = hashlib.sha256(content).hexdigest()

        # Get current git commit if in a git repo
        git_commit = None
        git_dir = self.workspace_path / ".git"
        if git_dir.exists():
            try:
                head_file = git_dir / "HEAD"
                if head_file.exists():
                    ref = head_file.read_text().strip()
                    if ref.startswith("ref: "):
                        ref_path = git_dir / ref[5:]
                        if ref_path.exists():
                            git_commit = ref_path.read_text().strip()[:8]
            except Exception:
                pass

        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=datetime.now(),
            description=description,
            task_plan_id=task_plan_id,
            step_index=step_index,
            files_state=files_state,
            git_commit=git_commit,
        )

        self.checkpoints.append(checkpoint)

        # Persist checkpoint
        await self._save_checkpoint(checkpoint)

        return checkpoint

    async def _save_checkpoint(self, checkpoint: Checkpoint):
        """Save checkpoint to disk"""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_file = self.checkpoint_dir / f"{checkpoint.id}.json"
        checkpoint_data = {
            "id": checkpoint.id,
            "timestamp": checkpoint.timestamp.isoformat(),
            "description": checkpoint.description,
            "task_plan_id": checkpoint.task_plan_id,
            "step_index": checkpoint.step_index,
            "files_state": checkpoint.files_state,
            "git_commit": checkpoint.git_commit,
            "metadata": checkpoint.metadata,
        }

        checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))

    def get_latest_checkpoint(
        self, task_plan_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Get the most recent checkpoint, optionally for a specific task"""
        relevant = self.checkpoints
        if task_plan_id:
            relevant = [
                cp for cp in self.checkpoints if cp.task_plan_id == task_plan_id
            ]

        if not relevant:
            return None

        return max(relevant, key=lambda cp: cp.timestamp)

    async def rollback_to(self, checkpoint_id: str) -> bool:
        """
        Rollback to a specific checkpoint.

        Note: This only provides metadata about the state - actual file
        restoration should be handled by git or backup mechanisms.
        """
        checkpoint = next(
            (cp for cp in self.checkpoints if cp.id == checkpoint_id), None
        )
        if not checkpoint:
            return False

        # If git commit is available, suggest git reset
        if checkpoint.git_commit:
            logger.info(
                f"Rollback available via: git reset --hard {checkpoint.git_commit}"
            )
            return True

        return False


# ==================== VERIFICATION LOOPS ====================


class VerificationEngine:
    """
    Verifies that completed work actually works.
    This is critical for end-to-end development - every step must be verified.
    """

    VERIFICATION_COMMANDS = {
        # JavaScript/TypeScript
        "typescript": ["npx tsc --noEmit", "npm run type-check"],
        "eslint": ["npm run lint", "npx eslint ."],
        "jest": ["npm test", "npm run test"],
        "vitest": ["npm test", "npx vitest run"],
        # Python
        "python": ["python -m py_compile {file}"],
        "pytest": ["pytest", "python -m pytest"],
        "mypy": ["mypy .", "python -m mypy ."],
        "flake8": ["flake8", "python -m flake8"],
        # Build verification
        "npm_build": ["npm run build"],
        "next_build": ["npm run build", "npx next build"],
        "vite_build": ["npm run build", "npx vite build"],
        # General
        "syntax_check": [],
        "import_check": [],
        "runtime_check": [],
    }

    @classmethod
    def get_verification_steps(
        cls,
        action_type: str,
        file_path: Optional[str] = None,
        project_info: Optional[ProjectInfo] = None,
    ) -> List[Dict[str, Any]]:
        """Get appropriate verification steps for an action"""
        steps = []

        if not project_info:
            return steps

        # Determine verification based on file type
        if file_path:
            ext = Path(file_path).suffix.lower()

            if ext in [".ts", ".tsx"]:
                steps.append(
                    {
                        "type": "runCommand",
                        "command": "npx tsc --noEmit",
                        "description": "Verify TypeScript compilation",
                        "required": True,
                    }
                )

            if ext in [".js", ".jsx", ".ts", ".tsx"]:
                if project_info.has_eslint:
                    steps.append(
                        {
                            "type": "runCommand",
                            "command": f"npx eslint {file_path}",
                            "description": "Check linting",
                            "required": False,
                        }
                    )

            if ext == ".py":
                steps.append(
                    {
                        "type": "runCommand",
                        "command": f"python -m py_compile {file_path}",
                        "description": "Verify Python syntax",
                        "required": True,
                    }
                )

        # Add test verification if tests exist
        if "test" in project_info.scripts:
            steps.append(
                {
                    "type": "runCommand",
                    "command": "npm test -- --passWithNoTests",
                    "description": "Run tests",
                    "required": False,
                }
            )

        return steps

    @classmethod
    async def verify_step(
        cls,
        step: TaskStep,
        workspace_path: str,
        project_info: Optional[ProjectInfo] = None,
    ) -> Dict[str, Any]:
        """
        Verify that a completed step actually worked.

        Returns verification result with success status and any issues found.
        """
        result = {"success": True, "verified": True, "issues": [], "warnings": []}

        if step.action_type == "create_file":
            # Verify file was created
            if step.target:
                file_path = Path(workspace_path) / step.target
                if not file_path.exists():
                    result["success"] = False
                    result["issues"].append(f"File was not created: {step.target}")
                else:
                    # Run syntax verification
                    verification_steps = cls.get_verification_steps(
                        "create_file", step.target, project_info
                    )
                    for v_step in verification_steps:
                        if v_step.get("required"):
                            result["warnings"].append(
                                f"Pending verification: {v_step['description']}"
                            )

        elif step.action_type == "run_command":
            # Command verification is based on exit code (handled elsewhere)
            if step.result and step.result.get("exit_code", 0) != 0:
                result["success"] = False
                result["issues"].append(
                    f"Command failed with exit code {step.result.get('exit_code')}"
                )

        return result


# ==================== END-TO-END ORCHESTRATOR ====================


class EndToEndOrchestrator:
    """
    Orchestrates complex end-to-end tasks.

    This is the main coordinator that brings together:
    - Task decomposition
    - Project standards
    - Self-healing
    - Checkpoints
    - Verification

    It ensures NAVI can complete full features and applications
    without failing midway.
    """

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.checkpoint_manager = CheckpointManager(workspace_path)
        self.current_plan: Optional[TaskPlan] = None
        self.project_standards: Optional[ProjectStandards] = None

    async def initialize(self):
        """Initialize the orchestrator with project analysis"""
        self.project_standards = await ProjectStandardsDetector.detect(
            self.workspace_path
        )

    async def plan_task(
        self,
        message: str,
        project_info: Optional[ProjectInfo] = None,
    ) -> TaskPlan:
        """
        Create an execution plan for a complex task.
        """
        # Determine if decomposition is needed
        needs_plan = TaskDecomposer.needs_decomposition(message)

        if needs_plan:
            plan = TaskDecomposer.decompose(message, project_info)
        else:
            # Simple task - single step
            plan = TaskPlan(
                id=f"plan-{uuid.uuid4().hex[:8]}",
                original_request=message,
                steps=[
                    TaskStep(
                        id="single-step", description=message, action_type="execute"
                    )
                ],
            )

        self.current_plan = plan
        return plan

    async def execute_with_recovery(
        self,
        action: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an action with automatic error recovery.
        """
        max_retries = 3
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                # Create checkpoint before risky operations
                if action.get("type") in ["create_file", "modify_file", "run_command"]:
                    await self.checkpoint_manager.create_checkpoint(
                        description=f"Before: {action.get('description', action.get('type'))}",
                        task_plan_id=(
                            self.current_plan.id if self.current_plan else None
                        ),
                        step_index=(
                            self.current_plan.current_step_index
                            if self.current_plan
                            else 0
                        ),
                    )

                # Execute the action (actual execution happens in NaviBrain)
                return {"success": True, "action": action, "retry_count": retry_count}

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                # Attempt recovery
                recovery = await SelfHealingEngine.attempt_recovery(
                    error=last_error,
                    failed_action=action,
                    context=context,
                    retry_count=retry_count,
                )

                if not recovery["can_recover"]:
                    break

                # Execute recovery actions
                for recovery_action in recovery["recovery_plan"]:
                    if recovery_action.get("auto_execute"):
                        logger.info(
                            f"Auto-executing recovery: {recovery_action.get('command')}"
                        )
                        # Recovery action execution would go here

        return {
            "success": False,
            "error": last_error,
            "retry_count": retry_count,
            "diagnosis": (
                SelfHealingEngine.diagnose(last_error, context) if last_error else None
            ),
        }

    def get_standards_context(self) -> str:
        """Get project standards as LLM context"""
        if self.project_standards:
            return self.project_standards.to_prompt_context()
        return ""


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

    SYSTEM_PROMPT = """You are NAVI, a UNIVERSAL, INTELLIGENT, and AUTONOMOUS AI coding assistant.

🌍 **UNIVERSAL CAPABILITY**: You work with ANY programming language, framework, or technology.
- Python, JavaScript, TypeScript, Go, Rust, Java, C#, Ruby, PHP, Swift, Kotlin, C, C++
- React, Vue, Angular, Svelte, Next.js, Django, FastAPI, Spring Boot, Rails, Laravel
- Docker, Kubernetes, Terraform, AWS, GCP, Azure, GitHub Actions, Jenkins
- SQL, NoSQL, Redis, Elasticsearch, GraphQL, REST APIs
- iOS, Android, React Native, Flutter, Electron
- Machine Learning, Data Engineering, DevOps, Systems Programming

⭐ INTELLIGENCE UPGRADE: You now have PROJECT ANALYSIS from reading actual project files.
When you see "=== PROJECT ANALYSIS (from reading files) ===" in the context:
- USE that information to give accurate, project-specific responses
- Reference actual scripts, build files, or configuration found
- Use the correct package manager or build tool for the project type
- Mention actual dependencies and framework versions
- DO NOT give generic answers when you have project-specific context

🏢 **ORGANIZATION CONTEXT**: When you see "=== ORGANIZATION CONTEXT:" in the prompt:
- Follow the organization's coding standards EXACTLY
- Use their preferred patterns and conventions
- Avoid patterns they've marked as antipatterns
- Apply insights from their past code reviews

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

🔄 **FOLLOW-UP AND CONFIRMATION HANDLING** (CRITICAL):
When the user responds with short confirmations like "yes", "yes please", "sure", "go ahead", "okay", "do it":
1. LOOK AT THE CONVERSATION HISTORY to understand what they're confirming
2. If your previous message offered multiple options (like "Would you like more details on a specific component?"):
   - Provide ALL the details you offered, not just a summary
   - If they said "yes please" to "more details", give comprehensive details on ALL components
3. NEVER respond with just a summary like "Here's a detailed explanation..." without the actual explanation
4. The follow-up response should be LONGER and MORE DETAILED than the original, not shorter

**Example:**
Previous NAVI: "Would you like more details on a specific component or feature?"
User: "yes please"
✅ CORRECT: Provide detailed breakdown of EVERY component with code examples
❌ WRONG: "Here's a detailed explanation of the project's architecture..." (without actual content)

**EXAMPLES**:

❓ "how to run this project?"
✅ Correct: Use PROJECT ANALYSIS to find actual scripts, then explain:
   "This is a Next.js 14 project. To run it:
    1. npm install (using npm as package manager)
    2. npm run dev (the URL will be shown in the terminal when it starts)
    Available scripts: build, lint, test"
❌ Wrong: Generic answer "npm install && npm run dev" without checking if those scripts exist
❌ Wrong: Hardcoding ports like "localhost:3000" - always let the terminal show the actual URL

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
- THOROUGH: For ALL responses, provide comprehensive, well-structured analysis
- HELPFUL: Give exactly what the user needs - info OR action
- PROACTIVE: Always offer to help with the next logical step
- PERSONAL: Make the user feel like they have a capable assistant on their side

🎯 **RESPONSE QUALITY STANDARD** (applies to ALL responses):
Your responses should match or exceed GitHub Copilot's quality. Every response must be:

1. **COMPREHENSIVE**: Cover all aspects of the question, not just the surface
2. **WELL-STRUCTURED**: Use markdown headers, bullet points, code blocks
3. **SPECIFIC**: Reference actual file paths, function names, line numbers
4. **ACTIONABLE**: Provide concrete next steps or offer to take action
5. **CONTEXTUAL**: Use project-specific information from the analysis

**Response Structure Template:**
- Start with a direct answer to the question
- Provide supporting details with structure (headers, bullets)
- Include relevant code snippets or file references
- End with proactive next steps or offers to help

**BAD response**: "This file handles routing."
**GOOD response**:
"## llmRouter.ts - Intelligent Model Selection

### Purpose
This file implements smart LLM routing that automatically selects the optimal model based on task type detection...

### Key Features
- **Task Detection**: Uses regex patterns and keywords to classify 13 task types
- **Model Recommendations**: Maps each task type to the best-suited model
- **Progress Messages**: Provides task-specific progress indicators

### How It Works
1. `detectTaskType()` analyzes the user message...
2. `getRecommendedModel()` returns the optimal model...

Would you like me to explain any specific function in more detail?"

PROACTIVE ASSISTANCE:
After answering ANY question, ALWAYS end with a proactive offer to help further:
- "Would you like me to run this for you?"
- "I can fix this right now - just say 'go ahead'"
- "Want me to set this up? I'll handle everything."
- "Should I create a test for this? Just let me know."

The user should feel like you're eager to help and ready to act, not just provide information.

FOCUS PRINCIPLE:
The user's explicit request is your primary objective. Use your judgment to determine if any
issues in the codebase are prerequisites to completing that request. If an issue blocks the
user's task, address it as part of completing their request. If an issue is unrelated, stay
focused on what they asked for.

RESILIENCE AND FALLBACKS:
- If a command or check returns empty output unexpectedly (example: git diff is empty), run 1-2 alternative checks (git status -sb, git diff --stat, git log -1) and report the results.
- If you still cannot proceed, provide a short summary of what you tried, what failed, and what you need next.
- When a task is done or blocked, offer 1-3 concrete next steps.

🚀 **END-TO-END TASK EXECUTION** (CRITICAL):
You MUST handle complete tasks from start to finish WITHOUT stopping halfway or asking unnecessary questions.

**SEAMLESS EXECUTION PRINCIPLES:**
1. **DO THE WHOLE THING**: If asked to "create a component", create ALL files needed (component, styles, tests, exports)
2. **CHAIN ACTIONS**: Don't stop after one file - continue until the feature is complete
3. **AUTO-RESOLVE ISSUES**: If something fails, fix it and continue - don't stop to ask
4. **VERIFY AND PROCEED**: After each action, verify it worked, then move to the next step
5. **COMPLETE THE LOOP**: Create → Verify → Fix if needed → Continue → Report success

**EXAMPLE - "Create a login form":**
✅ CORRECT (seamless end-to-end):
1. Create LoginForm.tsx with full implementation
2. Create LoginForm.css with styles
3. Create LoginForm.test.tsx with tests
4. Update index.ts to export the component
5. Run `npm run build` to verify compilation
6. Run `npm test -- LoginForm` to verify tests pass
7. Report: "Created LoginForm with styles and tests. All tests pass. ✅"

❌ WRONG (stopping halfway):
1. Create LoginForm.tsx
2. "I've created the component. Would you like me to add tests?"
   ← NO! Complete the task without asking

**When you see "=== CODE STYLE REQUIREMENTS ===" in context:**
- STRICTLY follow the detected coding conventions
- Match indent style, quote style, semicolons exactly
- Use the detected naming conventions (camelCase, PascalCase, etc.)
- Follow the project's import/export patterns

**When you see "=== CURRENT TASK PLAN ===" in context:**
- The task has been decomposed into steps for reliability
- Execute each step methodically
- Verify each step before proceeding to the next
- If a step fails, attempt automatic recovery before asking for help

**SELF-HEALING BEHAVIOR:**
When errors occur during execution, FIX THEM AUTOMATICALLY:
1. **Dependency errors** (Cannot find module): Run `npm install <package>` or `pip install <package>`
2. **Port conflicts** (EADDRINUSE): Find and kill the process, or use alternative port
3. **Type errors**: Read the file, fix the types, save, verify
4. **Lint errors**: Run `eslint --fix` or `prettier --write`
5. **Build failures**: Diagnose, fix the issue, rebuild
6. **Import errors**: Add missing imports, fix paths
7. **Permission errors**: Suggest chmod or run with appropriate permissions

**VERIFICATION AFTER ACTIONS:**
After creating or modifying files, ALWAYS verify:
- TypeScript: Run `npx tsc --noEmit` - if errors, FIX THEM
- Python: Run `python -m py_compile <file>` - if errors, FIX THEM
- Tests: Run relevant tests - if failures, FIX THEM
- Build: Run build command - if failures, FIX THEM

**COMPLEX TASK HANDLING:**
For requests like "build a complete feature" or "create an application":
1. Analyze the project structure and standards
2. Plan ALL the files and changes needed
3. Execute EVERYTHING in one go:
   - Create all files
   - Install dependencies
   - Run build/compile
   - Run tests
   - Fix any issues
4. Report complete success with summary

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
- "what does this file do?" → Comprehensive file analysis (see FILE EXPLANATION below)
Response format: {"message": "Detailed explanation", "files_to_create": {}, ...}

**FILE EXPLANATION FORMAT** (for "what does this file do?" / "explain this file"):
When explaining a file, provide a COMPREHENSIVE analysis with these sections:

## [Filename] - Brief one-line purpose

### Purpose
1-2 sentences explaining WHAT the file does and WHY it exists in the codebase.

### Key Features
Bullet list of the main capabilities/features implemented:
- Feature 1: Brief description
- Feature 2: Brief description
- etc.

### How It Works
Step-by-step explanation of the main logic flow:
1. First, it does X...
2. Then it processes Y...
3. Finally, it returns Z...

### Key Functions/Components
Brief description of important exports:
- `functionName()`: What it does
- `ComponentName`: What it renders
- `TypeName`: What it represents

### Dependencies & Integrations
- What this file imports/uses
- What other parts of the codebase use this file

### Example Usage (if applicable)
```
Brief code example showing typical usage
```

This format ensures the user gets a complete understanding, not just a brief summary.

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
    "message": "Natural, conversational explanation ending with a PROACTIVE OFFER to help",
    "files_to_create": {
        "path/to/file.tsx": "COMPLETE file content (no TODOs)",
        "another/file.ts": "COMPLETE file content"
    },
    "files_to_modify": {
        "existing/file.ts": "COMPLETE new content (full file replacement)"
    },
    "commands_to_run": ["npm install package", "npm test"],
    "actions": [
        {
            "type": "createFile",
            "filePath": "path/to/file.tsx",
            "description": "Creating the main component with state management",
            "content": "COMPLETE file content"
        },
        {
            "type": "runCommand",
            "command": "npm install",
            "description": "Installing the required dependencies"
        }
    ],
    "vscode_commands": [],
    "needs_user_input": false,
    "next_steps": ["REQUIRED: 2-4 CONTEXTUAL follow-ups based on what user asked - NOT generic suggestions"]
}

⭐ ACTIONS ARRAY (REQUIRED for streaming UI):
When you have files to create/modify or commands to run, ALWAYS include an "actions" array with:
- "type": "createFile" | "editFile" | "runCommand"
- "description": CONTEXTUAL, CONVERSATIONAL description explaining WHY this action matters (NOT generic like "Creating file" or "Running command")
  ✅ GOOD: "Adding the AuthContext provider with JWT token management"
  ✅ GOOD: "Setting up React Router with protected routes"
  ✅ GOOD: "Installing axios for API communication"
  ❌ BAD: "Creating file" or "Editing file" or "Running command"
- For files: "filePath" and "content"
- For commands: "command"
The "description" field is shown to the user during execution - make it helpful and specific to what this action accomplishes in the current task context.

NEXT_STEPS RULES (CRITICAL):
- MUST be related to what the user just asked about
- MUST be actionable (things NAVI can do, not generic advice)
- Examples for "how to run this project?":
  ✅ ["Run the project for me", "Fix the test errors", "Show me the main components"]
  ❌ ["Tell me more", "Any alternatives?", "What else?"]
- Examples for "fix this error":
  ✅ ["Run the tests to verify", "Check for similar errors", "Add error handling"]
  ❌ ["Explain further", "What are the next steps?"]

MESSAGE WRITING GUIDELINES:
🚨 BE CONCISE AND TAKE ACTION 🚨
- Keep messages SHORT (2-4 sentences max for most responses)
- DON'T explain what you COULD do - just DO IT
- DON'T list multiple options asking user to choose - pick the best one and implement it
- DON'T write long explanations before taking action
- Use markdown formatting: headers, bullet points, code blocks for readability

For ACTION requests (add, create, fix, implement):
- DO the task immediately, don't explain what it would involve
- Keep explanation brief: "I've added logging to the key functions. Click Apply to update."
- Include actual code changes in files_to_create or files_to_modify

For INFORMATION requests (explain, what is, how does):
- Give a focused answer, not an essay
- Use bullet points for clarity
- Reference specific files/lines when relevant

Example good messages:
- "I've added debug logging to your main components. The logs will show component lifecycle and props."
- "Here's a Navbar component that matches your React/Tailwind setup."
- "The mock format was wrong. I've fixed the test file."

Example BAD messages (too verbose):
- "You already have logging infrastructure... There are several ways we could expand... If you tell me which parts..." (DON'T ask - just do it!)
- Long paragraphs explaining what EXISTS before taking action
- Listing "options A, B, C, D" and asking user to choose

🚨 CRITICAL: FILE MODIFICATION RULES 🚨
When fixing errors or modifying existing files:
1. ✅ USE files_to_modify with the COMPLETE corrected file content
2. ❌ DO NOT use vscode_commands to just "open" files - that doesn't fix anything!
3. ✅ Include the ENTIRE file content in files_to_modify (not just the changed lines)
4. ✅ Use FUTURE tense in message (e.g., "This will fix..." NOT "Fixed...")

Example for "fix the syntax error in pages/index.js":
✅ CORRECT (natural, conversational, future tense):
{
  "message": "I found a missing closing parenthesis on line 12 of index.js that's causing the syntax error. Click Apply to fix it.",
  "files_to_modify": {
    "pages/index.js": "import React from 'react';\n\nexport default function Home() {\n  return <div>Hello</div>;\n}\n"
  },
  "vscode_commands": [],
  "next_steps": ["Run the dev server to verify the fix", "Check for any other syntax issues"]
}
❌ WRONG (robotic template):
{
  "message": "This will fix the syntax error by adding the missing closing parenthesis.",
  ...
}
❌ WRONG (past tense implies already done):
{
  "message": "Fixed the syntax error.",
  "vscode_commands": [{"command": "vscode.open", "args": ["pages/index.js"]}]
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

🔌 PORT MANAGEMENT (INTELLIGENT SERVER STARTUP):
When starting a dev server (npm run dev, yarn dev, etc.), NAVI performs intelligent port management:

**PORT_CONTEXT** in your context tells you:
- "port_available": true/false - Whether the preferred port is free
- "port_in_use_by": process name and command using the port
- "alternative_port": A free port to use instead
- "preferred_port": The port the project would normally use

**HOW TO RESPOND based on PORT_CONTEXT:**

1. **Port is available** (port_available: true):
   - Just run the command normally
   - Example: "I'll start the dev server. The URL will be shown in the terminal when it's ready."

2. **Port is busy** (port_available: false):
   - ALWAYS inform the user what's using the port
   - Offer TWO options dynamically:
     a) Use alternative port (modify command)
     b) Kill the existing process and use original port
   - Let the USER choose - don't decide for them

   Example response:
   "Port 3000 is currently in use by `node /path/to/server.js` (PID 12345).

   I can:
   1. **Use port 3001 instead** - Start the server on the next available port
   2. **Stop the existing process** - Kill the process on port 3000 and start fresh

   Which would you prefer?"

3. **For "run this project" requests with busy ports:**
   - Include port check action BEFORE the dev server command
   - Actions array should include: checkPort action → then runCommand action

**ACTION TYPES for port management:**
- "type": "checkPort" - Check if a port is available
- "type": "killPort" - Kill process on a port (requires user approval)
- "type": "runCommand" with modified command for alternative port

NEVER hardcode port numbers in your responses. Use the PORT_CONTEXT information.

🎯 KEY PRINCIPLE: Match your response to user intent - INFORMATION or ACTION. Both are equally valid."""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key_from_env()
        self.model = self._normalize_model(model or self._get_default_model())
        self.base_url = base_url or self._get_base_url()
        self.session: Optional[aiohttp.ClientSession] = None
        self.validator = SafetyValidator()

        # NAVI V2: Plan storage for approval flow
        self.active_plans: Dict[str, NaviPlan] = {}

        # Memory: cached personalized prompt per user
        self._personalized_prompts: Dict[str, str] = {}

    def _get_personalized_system_prompt(
        self, context: Optional[NaviContext] = None
    ) -> str:
        """
        Get personalized system prompt based on user preferences.
        Uses memory system to enhance the base prompt with user-specific instructions.
        """
        if not context or not context.user_id:
            return self.SYSTEM_PROMPT

        # Check cache first
        cache_key = f"{context.user_id}:{context.org_id or 'none'}"
        if cache_key in self._personalized_prompts:
            return self._personalized_prompts[cache_key]

        try:
            user_id_int = int(context.user_id) if context.user_id else None
            org_id_int = int(context.org_id) if context.org_id else None

            personalized = _enhance_system_prompt_with_memory(
                self.SYSTEM_PROMPT,
                user_id_int,
                org_id_int,
            )

            # Cache the personalized prompt
            self._personalized_prompts[cache_key] = personalized
            return personalized
        except Exception as e:
            logger.warning(f"[NAVI] Failed to personalize system prompt: {e}")
            return self.SYSTEM_PROMPT

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

    def _normalize_model(self, model: str) -> str:
        """Normalize known model aliases to stable provider model IDs."""
        if self.provider == "anthropic":
            alias_map = {
                "claude-sonnet-4-20250514": "claude-sonnet-4-20241022",
                "claude-opus-4-20250514": "claude-3-opus-20240229",
            }
            return alias_map.get(model, model)
        return model

    def _fallback_model_on_error(self, model: str, error_text: str) -> Optional[str]:
        """Return a fallback model if the provider reports an invalid model."""
        if self.provider != "anthropic":
            return None
        lowered = error_text.lower()
        if "model_not_found" in lowered or "not found" in lowered:
            normalized = self._normalize_model(model)
            if normalized != model:
                return normalized
            return "claude-3-5-sonnet-20241022"
        return None

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

    async def _get_saas_context(
        self,
        context: NaviContext,
        message: str,
        project_info: Optional[ProjectInfo] = None,
    ) -> str:
        """
        Get SaaS multi-tenant context for the current request.

        Combines:
        1. Organization context (coding standards, architecture patterns)
        2. Team context (team-specific overrides)
        3. User preferences
        4. RAG context (retrieved from knowledge base)
        5. Learning context (insights from past feedback)

        This enables NAVI to adapt to different organizations, teams, and users
        while leveraging company-specific knowledge from RAG.
        """
        context_parts = []

        # Only proceed if we have multi-tenant context
        if not (context.org_id or context.team_id or context.user_id):
            return ""

        try:
            # Import SaaS services
            from backend.services.organization_context import resolve_context
            from backend.services.knowledge_rag import get_rag_context
            from backend.services.feedback_learning import get_learning_context

            # Detect language from project or context
            language = None
            framework = None
            if project_info:
                if project_info.framework:
                    framework = project_info.framework
                if project_info.has_typescript:
                    language = "typescript"
                elif any(
                    d in str(project_info.dependencies)
                    for d in ["react", "vue", "angular"]
                ):
                    language = "javascript"
                elif project_info.project_type in [
                    "python",
                    "django",
                    "flask",
                    "fastapi",
                ]:
                    language = "python"

            # 1. Get hierarchical organization/team/user context
            org_team_context = resolve_context(
                org_id=context.org_id,
                team_id=context.team_id,
                user_id=context.user_id,
            )
            if org_team_context:
                context_parts.append(org_team_context)

            # 2. Get RAG context for this specific task
            if context.org_id:
                rag_context = await get_rag_context(
                    task=message,
                    org_id=context.org_id,
                    team_id=context.team_id,
                    language=language,
                    framework=framework,
                )
                if rag_context:
                    context_parts.append(rag_context)

            # 3. Get learning context (insights from past feedback)
            learning_ctx = get_learning_context(
                org_id=context.org_id,
                team_id=context.team_id,
                user_id=context.user_id,
                language=language,
            )
            if learning_ctx:
                context_parts.append(learning_ctx)

            return "\n\n".join(context_parts)

        except ImportError as e:
            logger.debug(f"SaaS services not available: {e}")
            return ""
        except Exception as e:
            logger.warning(f"Error getting SaaS context: {e}")
            return ""

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

        # STEP 1.5: FETCH MEMORY CONTEXT (user preferences, past conversations, patterns)
        try:
            user_id_int = int(context.user_id) if context.user_id else None
            org_id_int = int(context.org_id) if context.org_id else None

            if user_id_int:
                memory_context = await _get_memory_context_async(
                    query=message,
                    user_id=user_id_int,
                    org_id=org_id_int,
                    workspace_path=context.workspace_path,
                    current_file=context.current_file,
                )
                if memory_context:
                    context.memory_context = memory_context
                    thinking_steps.append("Applied user memory and preferences")
        except Exception as e:
            logger.warning(f"[NAVI] Memory context fetch failed (non-fatal): {e}")

        # STEP 2: Check if this is a "how to run" question vs "run it for me" action request
        message_lower = message.lower()

        # ACTION request: User wants NAVI to actually execute commands
        # Expanded list to capture more natural phrasings like "run the project"
        is_run_action = any(
            phrase in message_lower
            for phrase in [
                "run this for me",
                "run it for me",
                "run the project for me",
                "run this project for me",
                "run the project",  # Simple "run the project" request
                "run project",  # Shortened version
                "run this project",  # This project variant
                "start the project",  # Start variant
                "start project",  # Shortened start
                "start the app",  # App variant
                "start the server",  # Server variant
                "run the app",  # App variant
                "run app",  # Shortened
                "launch the project",  # Launch variant
                "launch project",  # Shortened launch
                "can you run",
                "please run",
                "just run",
                "go ahead and run",
                "execute",
                "start it for me",
                "start the project for me",
                "launch it for me",
            ]
        )

        # INFORMATION request: User wants to know how to run
        is_run_question = not is_run_action and any(
            phrase in message_lower
            for phrase in [
                "how to run",
                "how do i run",
                "how can i run",
                "get started",
                "set up",
                "setup",
            ]
        )

        # For ACTION requests, generate commands with actions (not just explanation)
        if is_run_action and project_info.project_type != "unknown":
            logger.info(
                "[NAVI] Detected 'run for me' ACTION request - generating executable actions"
            )
            thinking_steps.append("Preparing to run the project")

            # Generate commands to run
            install_cmd = IntelligentResponder._get_install_command(project_info)
            dev_cmd, dev_url = IntelligentResponder._get_dev_command(project_info)
            if not dev_cmd:
                response_text = (
                    f"I couldn't find a dev/start script for this **{project_info.project_type}** project. "
                    "If you can share the preferred command, I can run it for you."
                )
                return NaviResponse(
                    message=response_text,
                    thinking_steps=thinking_steps,
                    files_read=project_info.files_read,
                    project_type=project_info.project_type,
                    framework=project_info.framework,
                )

            # INTELLIGENT PORT MANAGEMENT: Check port availability before starting
            # Use NaviConfig for dynamic port detection - NO HARDCODED 3000
            preferred_port = NaviConfig.get_preferred_port(project_info)
            port_context = None
            if dev_cmd:
                # Try to extract port from dev command first
                port_match = re.search(
                    r"--port[=\s]+(\d+)|-p[=\s]+(\d+)|PORT=(\d+)", dev_cmd
                )
                if port_match:
                    preferred_port = int(
                        port_match.group(1)
                        or port_match.group(2)
                        or port_match.group(3)
                    )

                # Check port availability asynchronously
                try:
                    port_context = await PortManager.get_port_context_for_llm(
                        preferred_port=preferred_port, project_info=project_info
                    )
                    thinking_steps.append(f"Checked port {preferred_port} availability")
                except Exception as e:
                    logger.warning(f"Port check failed: {e}")

            # Build actions for the commands
            actions = []
            actions.append(
                {
                    "type": "runCommand",
                    "command": install_cmd,
                    "description": "Installing project dependencies",
                    "cwd": context.workspace_path,
                }
            )

            # Handle port conflict intelligently
            framework = project_info.framework or project_info.project_type
            if port_context and not port_context.get("is_available", True):
                # Port is busy - inform user and offer options
                process_info = port_context.get("process_info", {})
                process_name = (
                    process_info.get("name", "another process")
                    if process_info
                    else "another process"
                )
                process_cmd = process_info.get("command", "") if process_info else ""
                alt_port = port_context.get("alternative_port", preferred_port + 1)

                thinking_steps.append(
                    f"Port {preferred_port} is in use by {process_name}"
                )
                thinking_steps.append(f"Found alternative port: {alt_port}")

                # Modify command to use alternative port
                modified_cmd = PortManager.modify_command_for_port(dev_cmd, alt_port)

                response_text = f"I'll run this **{framework}** project for you.\n\n"
                response_text += f"⚠️ **Port {preferred_port} is currently in use** by `{process_name}`"
                if process_cmd:
                    response_text += (
                        f"\n   Command: `{process_cmd[:60]}...`"
                        if len(process_cmd) > 60
                        else f"\n   Command: `{process_cmd}`"
                    )
                response_text += (
                    f"\n\nI'll start the server on **port {alt_port}** instead. "
                )
                response_text += (
                    "The URL will be shown in the terminal when it's ready."
                )
                response_text += (
                    "\n\nReview the commands below and click **Allow** to proceed."
                )

                actions.append(
                    {
                        "type": "runCommand",
                        "command": modified_cmd,
                        "description": f"Starting development server on port {alt_port}",
                        "cwd": context.workspace_path,
                        "meta": {
                            "port": alt_port,
                            "original_port": preferred_port,
                            "port_conflict": True,
                        },
                    }
                )

                # Also offer to kill the process as an alternative
                if process_info and process_info.get("pid"):
                    return NaviResponse(
                        message=response_text,
                        actions=actions,
                        thinking_steps=thinking_steps,
                        files_read=project_info.files_read,
                        project_type=project_info.project_type,
                        framework=project_info.framework,
                        next_steps=[
                            f"Stop the process on port {preferred_port} and use that port instead",
                            "Continue with the alternative port",
                            "Check what's running on other ports",
                        ],
                        port_context=port_context,
                    )
            else:
                # Port is available - proceed normally
                if dev_cmd:
                    actions.append(
                        {
                            "type": "runCommand",
                            "command": dev_cmd,
                            "description": "Starting development server",
                            "cwd": context.workspace_path,
                        }
                    )

            # Generate a natural, action-oriented response
            response_text = f"I'll run this **{framework}** project for you."
            response_text += " The URL will be shown in the terminal when it's ready."
            response_text += (
                "\n\nReview the commands below and click **Allow** to proceed."
            )

            return NaviResponse(
                message=response_text,
                actions=actions,
                thinking_steps=thinking_steps,
                files_read=project_info.files_read,
                project_type=project_info.project_type,
                framework=project_info.framework,
                port_context=port_context,
            )

        # For INFORMATION requests (how to run), generate smart explanation
        if is_run_question and project_info.project_type != "unknown":
            logger.info(
                "[NAVI] Detected 'how to run' INFORMATION question - generating smart response without LLM"
            )
            thinking_steps.append("Generating project-specific run instructions")

            # Generate intelligent response based on what we read
            response_text = IntelligentResponder.generate_run_instructions(project_info)

            return NaviResponse(
                message=response_text,
                thinking_steps=thinking_steps,
                files_read=project_info.files_read,
                project_type=project_info.project_type,
                framework=project_info.framework,
                # Suggest next steps instead of asking again
                next_steps=[
                    "Run the project for me",
                    "Show me the main components",
                    "Check for any issues",
                ],
            )

        # STEP 3: Enrich context with domain-specific knowledge
        # This is what makes NAVI handle diverse requests intelligently
        enriched_context = None
        try:
            enriched_context = await DynamicContextProvider.enrich_context(
                message, project_info, context.workspace_path
            )
            if enriched_context.get("detected_domains"):
                thinking_steps.append(
                    f"Detected domains: {', '.join(enriched_context['detected_domains'])}"
                )
        except Exception as e:
            logger.warning(f"Context enrichment failed (non-fatal): {e}")

        # STEP 3.5: Add SaaS multi-tenant context (organization, RAG, learning)
        if enriched_context is None:
            enriched_context = {}
        try:
            saas_context = await self._get_saas_context(context, message, project_info)
            if saas_context:
                enriched_context["saas_context"] = saas_context
                thinking_steps.append("Applied organization-specific context")
        except Exception as e:
            logger.warning(f"SaaS context enrichment failed (non-fatal): {e}")

        # STEP 4: Build prompt with PROJECT INTELLIGENCE + DOMAIN CONTEXT for LLM
        prompt = self._build_prompt(message, context, project_info, enriched_context)

        # STEP 5: Call LLM with informed context
        try:
            llm_result = await self._call_llm(
                prompt, context.recent_conversation, context
            )

            # Handle tuple return (response_text, usage_info)
            if isinstance(llm_result, tuple):
                llm_response, usage_info = llm_result
            else:
                llm_response = llm_result
                usage_info = {}

            response = self._parse_response(llm_response)

            # Add usage info to response for SaaS billing
            if usage_info:
                response.usage_info = usage_info

            # Validate response for safety
            is_safe, warnings = self.validator.validate_response(
                response, context.workspace_path
            )

            if not is_safe:
                # Return dynamic safety warning response
                return NaviResponse(
                    message=DynamicMessages.safety_warning(warnings),
                    needs_user_input=True,
                    user_input_prompt="Would you like to proceed with a modified approach, or should I suggest alternatives?",
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

            # Store interaction for memory/learning (SYNCHRONOUS for reliable persistence)
            # Changed from fire-and-forget to await to ensure memory is actually stored
            try:
                user_id_int = int(context.user_id) if context.user_id else None
                org_id_int = int(context.org_id) if context.org_id else None
                if user_id_int:
                    # Await storage to ensure it completes before returning
                    await _store_interaction_async(
                        user_id=user_id_int,
                        conversation_id=context.conversation_id,
                        user_message=message,
                        assistant_response=response.message,
                        org_id=org_id_int,
                        workspace_path=context.workspace_path,
                        current_file=context.current_file,
                    )
                    logger.info(
                        f"[NAVI] Stored interaction for user {user_id_int} in conversation {context.conversation_id}"
                    )
            except Exception as store_error:
                logger.warning(f"[NAVI] Failed to store interaction: {store_error}")

            return response

        except Exception as e:
            logger.error(f"NAVI processing error: {e}", exc_info=True)
            # Graceful fallback - never crash, use dynamic error messages
            return NaviResponse(
                message=DynamicMessages.error_message(
                    e, context="processing your request"
                ),
                needs_user_input=True,
                user_input_prompt="Would you like to try a different approach?",
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
        enriched_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the full prompt with context + PROJECT INTELLIGENCE + DOMAIN CONTEXT + SAAS CONTEXT"""

        context_parts = []

        # SAAS MULTI-TENANT CONTEXT (organization, team, user, RAG, learning)
        saas_context = (
            enriched_context.get("saas_context", "") if enriched_context else ""
        )
        if saas_context:
            context_parts.append(saas_context)
            context_parts.append("")

        # MEMORY CONTEXT (user preferences, past conversations, code patterns)
        memory_context = (
            context.memory_context if hasattr(context, "memory_context") else {}
        )
        if memory_context:
            memory = _get_memory_integration()
            if memory:
                try:
                    memory_str = memory.format_context_for_prompt(
                        memory_context, max_tokens=1500
                    )
                    if memory_str.strip():
                        context_parts.append("=== MEMORY CONTEXT ===")
                        context_parts.append(memory_str)
                        context_parts.append("")
                except Exception as e:
                    logger.warning(f"[NAVI] Failed to format memory context: {e}")

        # CONNECTOR CONTEXT (which services the user has connected)
        if context.user_id:
            try:
                from backend.database.session import get_db
                from backend.services.connector_base import (
                    build_connector_context_for_navi,
                )

                db = next(get_db())
                connector_ctx = build_connector_context_for_navi(
                    db=db,
                    user_id=str(context.user_id),
                    org_id=str(context.org_id) if context.org_id else None,
                )
                if connector_ctx:
                    context_parts.append("=== CONNECTED SERVICES ===")
                    context_parts.append(connector_ctx)
                    context_parts.append("")
            except Exception as e:
                logger.warning(f"[NAVI] Failed to build connector context: {e}")

        # DOMAIN-SPECIFIC CONTEXT (dynamic based on request type)
        if enriched_context:
            domains = enriched_context.get("detected_domains", [])
            if domains and domains != ["general"]:
                context_parts.append(f"=== DETECTED DOMAINS: {', '.join(domains)} ===")

            domain_context = enriched_context.get("domain_context", "")
            if domain_context:
                context_parts.append(domain_context)
                context_parts.append("")

            # Port context for server-related requests
            port_ctx = enriched_context.get("port_context")
            if port_ctx:
                context_parts.append("=== PORT STATUS ===")
                if port_ctx.get("is_available"):
                    context_parts.append(
                        f"Port {port_ctx.get('preferred_port', 3000)} is available."
                    )
                else:
                    proc = port_ctx.get("process_info", {})
                    context_parts.append(
                        f"Port {port_ctx.get('preferred_port', 3000)} is IN USE by: {proc.get('name', 'unknown')}"
                    )
                    if port_ctx.get("alternative_port"):
                        context_parts.append(
                            f"Alternative available: port {port_ctx.get('alternative_port')}"
                        )
                context_parts.append("")

            # Runtime environment
            runtime = enriched_context.get("runtime", {})
            if runtime.get("tools_available"):
                available_tools = [
                    t for t, v in runtime["tools_available"].items() if v
                ]
                if available_tools:
                    context_parts.append(
                        f"AVAILABLE TOOLS: {', '.join(available_tools)}"
                    )

            # Missing tools detection
            missing_tools = enriched_context.get("missing_tools", [])
            if missing_tools:
                context_parts.append("\n=== MISSING TOOLS DETECTED ===")
                context_parts.append(f"Missing: {', '.join(missing_tools)}")
                context_parts.append("You can offer to install these for the user.")
                context_parts.append(
                    "Use 'installTool' action type with the appropriate command."
                )
                context_parts.append("")

            # Web search results (if search was performed)
            web_search_context = enriched_context.get("web_search_context", "")
            if web_search_context:
                context_parts.append(web_search_context)
                context_parts.append("")

        # PROJECT INTELLIGENCE (from reading files - like Codex/Claude Code)
        if project_info and project_info.project_type != "unknown":
            context_parts.append("=== PROJECT ANALYSIS (from reading files) ===")
            context_parts.append(project_info.to_context_string())
            context_parts.append("=" * 50)
            context_parts.append("")

        # PROJECT CODING STANDARDS (for generating consistent code)
        if enriched_context and enriched_context.get("project_standards"):
            standards_ctx = enriched_context.get("project_standards")
            if isinstance(standards_ctx, str) and standards_ctx:
                context_parts.append("=== CODE STYLE REQUIREMENTS ===")
                context_parts.append(standards_ctx)
                context_parts.append(
                    "When generating code, FOLLOW these conventions exactly."
                )
                context_parts.append("")

        # TASK PLAN (if executing a complex multi-step task)
        if enriched_context and enriched_context.get("task_plan"):
            task_plan = enriched_context.get("task_plan")
            context_parts.append("=== CURRENT TASK PLAN ===")
            context_parts.append(task_plan)
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

        # Errors - include file content for files with errors so LLM can fix them
        if context.errors:
            errors_str = "\n".join(
                [
                    f"- {e.get('file', 'unknown')}: {e.get('message', 'error')}"
                    for e in context.errors[:5]
                ]
            )
            context_parts.append(f"CURRENT ERRORS:\n{errors_str}")

            # Read content of files with errors so LLM can generate fixes
            error_files_seen = set()
            for error in context.errors[:5]:
                error_file = error.get("file")
                logger.info(f"[NaviBrain] Processing error file: {error_file}")
                if error_file and error_file not in error_files_seen:
                    error_files_seen.add(error_file)
                    try:
                        # Try to read the file content - handle both relative and absolute paths
                        if Path(error_file).is_absolute():
                            file_path = Path(error_file)
                        else:
                            file_path = Path(context.workspace_path) / error_file

                        logger.info(
                            f"[NaviBrain] Trying to read file: {file_path}, exists: {file_path.exists()}"
                        )

                        if file_path.exists() and file_path.is_file():
                            content = file_path.read_text(
                                encoding="utf-8", errors="ignore"
                            )
                            # Truncate if too long
                            if len(content) > 3000:
                                content = content[:3000] + "\n... (truncated)"
                            context_parts.append(
                                f"\nFILE WITH ERROR ({error_file}):\n```\n{content}\n```"
                            )
                            logger.info(
                                f"[NaviBrain] Successfully read error file content ({len(content)} chars)"
                            )
                        else:
                            logger.warning(
                                f"[NaviBrain] Error file not found: {file_path}"
                            )
                    except Exception as e:
                        logger.error(
                            f"[NaviBrain] Could not read error file {error_file}: {e}"
                        )

        # Open files
        if context.open_files:
            context_parts.append(f"OPEN FILES: {', '.join(context.open_files[:10])}")

        context_block = "\n".join(context_parts)

        # No hardcoded keyword detection - let the LLM use its intelligence
        # to understand user intent from the system prompt guidelines
        message_lower = message.lower()
        aggressive_block = ""

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
                    "explain",
                    "describe",
                    "tell me",
                    "show me",
                    "list",
                    "summarize",
                    "overview",
                )
            )
            or message_lower.endswith("?")
            or any(
                phrase in message_lower
                for phrase in [
                    "what is",
                    "what are",
                    "how does",
                    "why is",
                    "where is",
                    "can you explain",
                    "tell me about",
                    "walk me through",
                ]
            )
        )

        response_contract = (
            """RESPONSE FORMAT (INFORMATION MODE):
Return JSON ONLY with these fields:
{
  "message": "Comprehensive, well-structured response with markdown formatting.",
  "files_to_create": {},
  "files_to_modify": {},
  "commands_to_run": [],
  "vscode_commands": [],
  "needs_user_input": false,
  "next_steps": ["2-3 helpful follow-up options"]
}

🎯 **RESPONSE QUALITY STANDARD:**
Your responses should match or exceed GitHub Copilot's quality. EVERY response must be:
- **COMPREHENSIVE**: Cover all aspects, not just the surface
- **WELL-STRUCTURED**: Use markdown headers (##, ###), bullet points, code blocks
- **SPECIFIC**: Reference actual file paths, function names, line numbers when relevant
- **ACTIONABLE**: End with concrete next steps or offers to help

**Response Structure (apply to ALL questions):**
1. **Direct Answer**: Start with a clear answer to the question
2. **Details**: Provide supporting information with structure
3. **Examples**: Include code snippets or file references where helpful
4. **Next Steps**: End with proactive offers ("Would you like me to...")

**BAD** (too short):
"This file handles routing based on task type."

**GOOD** (comprehensive):
"## llmRouter.ts - Intelligent Model Selection

### Purpose
This file implements smart LLM routing that automatically selects the optimal model...

### Key Features
- **Task Detection**: Uses regex patterns to classify 13 task types
- **Model Recommendations**: Maps each task to the best-suited model
...

Would you like me to explain any specific function?"

Rules:
- Do NOT create/modify files unless explicitly asked.
- Use concrete file paths and project-specific details.
- Be THOROUGH - users expect quality on par with GitHub Copilot."""
            if is_question_or_chat
            else """RESPONSE FORMAT (ACTION MODE):
Return JSON ONLY with these fields:
{
  "message": "Summary of ALL actions taken and their results.",
  "files_to_create": { "path": "full file content" },
  "files_to_modify": { "path": "full file content" },
  "commands_to_run": ["command1", "command2", "..."],
  "vscode_commands": [{"command": "vscode.open", "args": ["path"]}],
  "needs_user_input": false,
  "next_steps": ["2-3 helpful follow-up options"]
}

🚀 **END-TO-END EXECUTION RULES:**
- COMPLETE THE ENTIRE TASK - don't stop halfway
- Create ALL related files (component + styles + tests + exports)
- Include ALL necessary commands (install deps, build, test)
- If creating a feature, include EVERYTHING it needs to work
- Verify compilation/tests and include fix commands if needed

**Example - "create a button component":**
files_to_create: {
  "src/components/Button/Button.tsx": "...",
  "src/components/Button/Button.css": "...",
  "src/components/Button/Button.test.tsx": "...",
  "src/components/Button/index.ts": "export { Button } from './Button';"
}
commands_to_run: ["npm run build", "npm test -- Button"]

Rules:
- At least one of files_to_create / files_to_modify / commands_to_run must be non-empty.
- Include complete file contents (not diffs).
- Be proactive and decisive - DO EVERYTHING needed.
- Keep code clean but complete (no TODOs, no "implement here" comments).
- Focus on working code that compiles and runs."""
        )

        critical_reminder = ""
        if not is_question_or_chat:
            critical_reminder = """
🚨 CRITICAL REMINDER 🚨
Your response MUST include AT LEAST ONE of:
- files_to_create (with actual file content)
- files_to_modify (with complete new file content)
- commands_to_run (with actual commands)

If your response is just text explanation, IT IS WRONG."""

        # FOLLOW-UP DETECTION: Check if this is a short confirmation
        is_followup = message_lower.strip() in (
            "yes",
            "yes please",
            "sure",
            "go ahead",
            "okay",
            "ok",
            "do it",
            "proceed",
            "continue",
            "please",
            "yeah",
            "yep",
            "sounds good",
            "that works",
            "perfect",
            "great",
        ) or (
            len(message.strip()) < 20
            and any(
                word in message_lower
                for word in ["yes", "sure", "okay", "ok", "please", "proceed"]
            )
        )

        # Include recent conversation summary for follow-ups
        conversation_context = ""
        if is_followup and context.recent_conversation:
            # Get the last assistant message to understand what they're confirming
            last_assistant_msgs = [
                msg
                for msg in context.recent_conversation
                if msg.get("role") == "assistant"
            ]
            if last_assistant_msgs:
                last_response = last_assistant_msgs[-1].get("content", "")[:2000]
                conversation_context = f"""
=== IMPORTANT: FOLLOW-UP CONTEXT ===
The user said "{message}" in response to your previous message.
Your previous message was:
---
{last_response}
---

🚨 CRITICAL: The user is confirming/requesting what you offered above!
- If you offered to explain details → Provide COMPLETE, COMPREHENSIVE details
- If you offered multiple options → Cover ALL options in depth
- If you offered to help with something → DO IT fully
- Your response MUST be LONGER and MORE DETAILED than the original
- Do NOT just say "Here's a detailed breakdown..." - actually PROVIDE the breakdown!
=== END FOLLOW-UP CONTEXT ===
"""

        return f"""CONTEXT:
{context_block}
{conversation_context}
USER REQUEST: {message}

{aggressive_block}
{critical_reminder}
{response_contract}
Respond with JSON only."""

    async def _call_llm(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[NaviContext] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Call the LLM provider with automatic retry on transient errors.
        Returns: (response_text, usage_info) tuple for token tracking.
        """
        max_retries = 3
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                if self.provider == "anthropic":
                    return await self._call_anthropic(
                        prompt, conversation_history, context
                    )
                elif (
                    self.provider == "openai"
                    or self.provider == "groq"
                    or self.provider == "openrouter"
                ):
                    result = await self._call_openai_compatible(
                        prompt, conversation_history, context
                    )
                    # Wrap in tuple for consistency (OpenAI doesn't return usage yet)
                    if isinstance(result, tuple):
                        return result
                    return result, {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }
                elif self.provider == "ollama":
                    result = await self._call_ollama(
                        prompt, conversation_history, context
                    )
                    if isinstance(result, tuple):
                        return result
                    return result, {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }
                else:
                    result = await self._call_openai_compatible(
                        prompt, conversation_history, context
                    )
                    if isinstance(result, tuple):
                        return result
                    return result, {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    }

            except Exception as e:
                error_str = str(e).lower()

                # Check if this is a retryable error
                is_retryable = any(
                    x in error_str
                    for x in [
                        "overloaded",
                        "529",
                        "503",
                        "rate",
                        "429",
                        "timeout",
                        "connection",
                        "temporarily",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"LLM call failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Not retryable or out of retries
                raise

        raise RuntimeError("LLM call failed after retries")

    async def _call_anthropic(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[NaviContext] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Call Anthropic Claude API.
        Returns: (response_text, usage_info) tuple for token tracking.
        """
        import time

        start_time = time.time()
        session = await self._get_session()

        messages = []
        if history:
            # Convert history to dicts if needed (handle ChatMessage objects)
            for msg in history:
                if isinstance(msg, dict):
                    # Handle both 'role' and 'type' field names (frontend sends 'type')
                    role = msg.get("role") or msg.get("type", "user")
                    # Map 'assistant' to 'assistant', 'user' to 'user'
                    if role not in ("user", "assistant"):
                        role = "user"  # Default unknown roles to user
                    messages.append({"role": role, "content": msg.get("content", "")})
                elif hasattr(msg, "__dict__"):
                    # Convert object to dict - check both role and type attributes
                    role = getattr(msg, "role", None) or getattr(msg, "type", "user")
                    if role not in ("user", "assistant"):
                        role = "user"
                    messages.append(
                        {
                            "role": role,
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )
                else:
                    # Fallback: convert to string
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        # Use personalized system prompt based on user context
        system_prompt = (
            self._get_personalized_system_prompt(context)
            if context
            else self.SYSTEM_PROMPT
        )

        model = self._normalize_model(self.model)
        payload = {
            "model": model,
            "max_tokens": 16384,
            "system": system_prompt,
            "messages": messages,
        }

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        for attempt in range(2):
            payload["model"] = model
            async with session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    fallback_model = self._fallback_model_on_error(model, error)
                    if fallback_model and fallback_model != model and attempt == 0:
                        logger.warning(
                            "[NAVI] Anthropic model %s not available, falling back to %s",
                            model,
                            fallback_model,
                        )
                        model = fallback_model
                        continue
                    raise Exception(f"Anthropic API error: {error}")

                data = await response.json()

                # Extract usage information for billing
                usage_info = data.get("usage", {})
                latency_ms = (time.time() - start_time) * 1000

                # Track token usage
                try:
                    from backend.services.token_tracking import track_usage

                    track_usage(
                        model=model,
                        provider="anthropic",
                        input_tokens=usage_info.get("input_tokens", 0),
                        output_tokens=usage_info.get("output_tokens", 0),
                        org_id=context.org_id if context else None,
                        team_id=context.team_id if context else None,
                        user_id=context.user_id if context else None,
                        latency_ms=latency_ms,
                    )
                except Exception as e:
                    logger.warning(f"Token tracking failed (non-fatal): {e}")

                # Safe extraction with fallback
                content = data.get("content", [])
                response_text = ""
                if isinstance(content, list) and content:
                    first_block = content[0]
                    if isinstance(first_block, dict):
                        response_text = first_block.get("text", "")
                    elif isinstance(first_block, str):
                        response_text = first_block
                elif isinstance(content, str):
                    response_text = content

                # Return both response and usage info
                return response_text, {
                    "input_tokens": usage_info.get("input_tokens", 0),
                    "output_tokens": usage_info.get("output_tokens", 0),
                    "total_tokens": usage_info.get("input_tokens", 0)
                    + usage_info.get("output_tokens", 0),
                    "latency_ms": latency_ms,
                    "model": model,
                    "provider": "anthropic",
                }

        raise Exception("Anthropic API error: failed to resolve a valid model")

    async def _call_openai_compatible(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[NaviContext] = None,
    ) -> str:
        """Call OpenAI-compatible API (OpenAI, Groq, OpenRouter, etc.)"""
        session = await self._get_session()

        # Use personalized system prompt based on user context
        system_prompt = (
            self._get_personalized_system_prompt(context)
            if context
            else self.SYSTEM_PROMPT
        )
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            # Convert history to dicts if needed (handle ChatMessage objects)
            for msg in history:
                if isinstance(msg, dict):
                    # Handle both 'role' and 'type' field names (frontend sends 'type')
                    role = msg.get("role") or msg.get("type", "user")
                    # Map to valid OpenAI roles
                    if role not in ("user", "assistant", "system"):
                        role = "user"  # Default unknown roles to user
                    messages.append({"role": role, "content": msg.get("content", "")})
                elif hasattr(msg, "__dict__"):
                    # Convert object to dict - check both role and type attributes
                    role = getattr(msg, "role", None) or getattr(msg, "type", "user")
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    messages.append(
                        {
                            "role": role,
                            "content": getattr(msg, "content", str(msg)),
                        }
                    )
                else:
                    # Fallback: convert to string
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        tokens_key = "max_tokens"
        if self.provider == "openai" and self._requires_max_completion_tokens():
            tokens_key = "max_completion_tokens"

        payload = {
            "model": self.model,
            tokens_key: 8192,
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
            # Safe extraction with fallback
            choices = data.get("choices", [])
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get("message", {})
                    if isinstance(message, dict):
                        return message.get("content", "")
            return ""

    def _requires_max_completion_tokens(self) -> bool:
        model = (self.model or "").lower()
        return any(
            token in model
            for token in (
                "gpt-5",
                "gpt-4.2",
                "gpt-4.1",
                "gpt-4o",
                "o1",
                "o3",
                "o4",
            )
        )

    async def _call_ollama(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[NaviContext] = None,
    ) -> str:
        """Call local Ollama"""
        session = await self._get_session()

        # Use personalized system prompt based on user context
        system_prompt = (
            self._get_personalized_system_prompt(context)
            if context
            else self.SYSTEM_PROMPT
        )
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            # Safely extend history - validate it's a list
            if isinstance(history, list):
                for msg in history:
                    if isinstance(msg, dict):
                        messages.append(msg)
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
            # Safe extraction with fallback
            message = data.get("message", {})
            if isinstance(message, dict):
                return message.get("content", "")
            elif isinstance(message, str):
                return message
            # Fallback for alternative response format
            return data.get("response", "")

    # ==================== STREAMING LLM METHODS ====================

    async def _call_llm_streaming(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version of LLM call that yields thinking tokens and final response.

        Yields:
        - {"thinking": "partial text..."} - As tokens stream in
        - {"complete": "full response"} - When complete
        """
        if self.provider == "anthropic":
            async for chunk in self._call_anthropic_streaming(
                prompt, conversation_history
            ):
                yield chunk
        elif self.provider in ("openai", "groq", "openrouter"):
            async for chunk in self._call_openai_streaming(
                prompt, conversation_history
            ):
                yield chunk
        else:
            # Fallback to non-streaming
            result_text, _ = await self._call_llm(prompt, conversation_history)
            yield {"complete": result_text}

    async def _call_anthropic_streaming(
        self, prompt: str, history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming call to Anthropic Claude API"""
        session = await self._get_session()

        messages = []
        if history:
            for msg in history:
                if isinstance(msg, dict):
                    role = msg.get("role") or msg.get("type", "user")
                    if role not in ("user", "assistant"):
                        role = "user"
                    messages.append({"role": role, "content": msg.get("content", "")})
                elif hasattr(msg, "__dict__"):
                    role = getattr(msg, "role", None) or getattr(msg, "type", "user")
                    if role not in ("user", "assistant"):
                        role = "user"
                    messages.append(
                        {"role": role, "content": getattr(msg, "content", str(msg))}
                    )
                else:
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        model = self._normalize_model(self.model)
        payload = {
            "model": model,
            "max_tokens": 16384,
            "system": self.SYSTEM_PROMPT,
            "messages": messages,
            "stream": True,  # Enable streaming
        }

        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        full_response = ""
        thinking_buffer = ""

        for attempt in range(2):
            payload["model"] = model
            async with session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    fallback_model = self._fallback_model_on_error(model, error)
                    if fallback_model and fallback_model != model and attempt == 0:
                        logger.warning(
                            "[NAVI] Anthropic model %s not available, falling back to %s",
                            model,
                            fallback_model,
                        )
                        model = fallback_model
                        continue
                    raise Exception(f"Anthropic API error: {error}")

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type", "")

                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                full_response += text
                                thinking_buffer += text

                                # Yield thinking chunks (every ~50 chars for smooth streaming)
                                if len(thinking_buffer) >= 50:
                                    yield {"thinking": thinking_buffer}
                                    thinking_buffer = ""

                        elif event_type == "message_stop":
                            break

                    except json.JSONDecodeError:
                        continue

                # Yield any remaining buffer
                if thinking_buffer:
                    yield {"thinking": thinking_buffer}

                # Yield complete response
                yield {"complete": full_response}
                return

        raise Exception("Anthropic API error: failed to resolve a valid model")

    async def _call_openai_streaming(
        self, prompt: str, history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming call to OpenAI-compatible API"""
        session = await self._get_session()

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if history:
            for msg in history:
                if isinstance(msg, dict):
                    role = msg.get("role") or msg.get("type", "user")
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    messages.append({"role": role, "content": msg.get("content", "")})
                elif hasattr(msg, "__dict__"):
                    role = getattr(msg, "role", None) or getattr(msg, "type", "user")
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    messages.append(
                        {"role": role, "content": getattr(msg, "content", str(msg))}
                    )
                else:
                    messages.append({"role": "user", "content": str(msg)})
        messages.append({"role": "user", "content": prompt})

        tokens_key = "max_tokens"
        if self.provider == "openai" and self._requires_max_completion_tokens():
            tokens_key = "max_completion_tokens"

        payload = {
            "model": self.model,
            tokens_key: 8192,
            "temperature": 0.7,
            "messages": messages,
            "stream": True,  # Enable streaming
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://navi.dev"
            headers["X-Title"] = "NAVI"

        full_response = ""
        thinking_buffer = ""

        async with session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"API error: {error}")

            async for line in response.content:
                line = line.decode("utf-8").strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                            thinking_buffer += content

                            # Yield thinking chunks (every ~50 chars for smooth streaming)
                            if len(thinking_buffer) >= 50:
                                yield {"thinking": thinking_buffer}
                                thinking_buffer = ""

                except json.JSONDecodeError:
                    continue

            # Yield any remaining buffer
            if thinking_buffer:
                yield {"thinking": thinking_buffer}

            # Yield complete response
            yield {"complete": full_response}

    def _parse_response(self, llm_response: str) -> NaviResponse:
        """Parse LLM response into NaviResponse"""
        logger.info(
            f"[NaviBrain] Raw LLM response (first 1000 chars): {llm_response[:1000]}"
        )
        try:
            # Clean up response - extract JSON
            content = llm_response.strip()

            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            def try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None

            data = try_parse_json(content)
            if data is None:
                # Try to locate a JSON object inside the response
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    data = try_parse_json(content[start : end + 1])

            if data is None:
                # As a last resort, extract message field from JSON-like text
                # Use a more robust pattern that handles multi-line and escaped content
                match = re.search(
                    r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL
                )
                if match:
                    message = match.group(1).encode("utf-8").decode("unicode_escape")
                    return NaviResponse(message=message, needs_user_input=False)
                # Final fallback - if content looks like plain text (not JSON), use it directly
                if not content.strip().startswith("{"):
                    return NaviResponse(message=content.strip(), needs_user_input=False)
                raise json.JSONDecodeError("No JSON object found", content, 0)

            files_to_modify = data.get("files_to_modify", {})
            files_to_create = data.get("files_to_create", {})
            vscode_commands = data.get("vscode_commands", [])
            commands_to_run = data.get("commands_to_run", [])
            actions = data.get("actions", [])

            # If LLM provided an actions array, use it. Otherwise, build from files/commands.
            if not actions:
                # Build actions from files_to_create, files_to_modify, commands_to_run
                # Try to create contextual descriptions based on file paths and commands
                for path, content in files_to_create.items():
                    filename = path.split("/")[-1]
                    # Infer context from filename
                    if (
                        "component" in path.lower()
                        or filename.endswith(".tsx")
                        or filename.endswith(".jsx")
                    ):
                        desc = f"Creating {filename} component"
                    elif "hook" in path.lower() or filename.startswith("use"):
                        desc = f"Creating {filename} hook"
                    elif "context" in path.lower():
                        desc = f"Setting up {filename} context provider"
                    elif "service" in path.lower() or "api" in path.lower():
                        desc = f"Creating {filename} for API integration"
                    elif (
                        "test" in path.lower()
                        or filename.endswith(".test.ts")
                        or filename.endswith(".spec.ts")
                    ):
                        desc = f"Adding tests in {filename}"
                    elif filename.endswith(".css") or filename.endswith(".scss"):
                        desc = f"Adding styles in {filename}"
                    else:
                        desc = f"Creating {filename}"
                    actions.append(
                        {
                            "type": "createFile",
                            "filePath": path,
                            "content": content,
                            "description": desc,
                        }
                    )
                for path, content in files_to_modify.items():
                    filename = path.split("/")[-1]
                    actions.append(
                        {
                            "type": "editFile",
                            "filePath": path,
                            "content": content,
                            "description": f"Updating {filename}",
                        }
                    )
                for cmd in commands_to_run:
                    # Infer context from command
                    if "install" in cmd.lower():
                        pkg = (
                            cmd.split()[-1] if len(cmd.split()) > 2 else "dependencies"
                        )
                        desc = f"Installing {pkg}"
                    elif "test" in cmd.lower():
                        desc = "Running tests"
                    elif "build" in cmd.lower():
                        desc = "Building the project"
                    elif "lint" in cmd.lower():
                        desc = "Checking code quality"
                    elif "dev" in cmd.lower() or "start" in cmd.lower():
                        desc = "Starting development server"
                    else:
                        desc = f"Running: {cmd[:50]}{'...' if len(cmd) > 50 else ''}"
                    actions.append(
                        {"type": "runCommand", "command": cmd, "description": desc}
                    )

            logger.info(
                f"[NaviBrain] Parsed response - files_to_modify: {list(files_to_modify.keys())}, files_to_create: {list(files_to_create.keys())}, vscode_commands: {len(vscode_commands)}, commands_to_run: {commands_to_run}, actions: {len(actions)}"
            )

            return NaviResponse(
                message=data.get("message", "Done!"),
                files_to_create=files_to_create,
                files_to_modify=files_to_modify,
                commands_to_run=commands_to_run,
                vscode_commands=vscode_commands,
                needs_user_input=data.get("needs_user_input", False),
                user_input_prompt=data.get("user_input_prompt"),
                next_steps=data.get("next_steps", []),
                actions=actions,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # LLM didn't return valid JSON - try to extract message if it looks like JSON
            raw = llm_response.strip()
            if raw.startswith("{") and '"message"' in raw:
                # Try regex extraction as final fallback
                match = re.search(
                    r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL
                )
                if match:
                    message = match.group(1).encode("utf-8").decode("unicode_escape")
                    return NaviResponse(message=message, needs_user_input=False)
            # Return plain text (first 2000 chars)
            return NaviResponse(
                message=(
                    raw[:2000]
                    if not raw.startswith("{")
                    else "I processed your request but couldn't parse the response. Please try again."
                ),
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
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None,
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
        current_file: Optional[str] = None,
        current_file_content: Optional[str] = None,
        selection: Optional[str] = None,
        open_files: Optional[List[str]] = None,
        errors: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
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
                # NAVI V3: Intelligence fields
                "thinking_steps": response.thinking_steps,
                "files_read": response.files_read,
                "project_type": response.project_type,
                "framework": response.framework,
            }

        # DON'T auto-execute file changes - let VS Code handle them
        # This allows user approval before changes are applied
        # execution_results = await self._execute_actions(response)

        # Build file edit actions for VS Code to apply
        file_edits = []
        for file_path, content in response.files_to_modify.items():
            file_edits.append(
                {
                    "type": "editFile",
                    "filePath": file_path,
                    "content": content,
                    "operation": "modify",
                }
            )
        for file_path, content in response.files_to_create.items():
            file_edits.append(
                {
                    "type": "editFile",
                    "filePath": file_path,
                    "content": content,
                    "operation": "create",
                }
            )

        # Return combined result with file edits for VS Code
        return {
            "success": True,
            "message": response.message,
            "files_created": list(response.files_to_create.keys()),
            "files_modified": list(response.files_to_modify.keys()),
            "file_edits": file_edits,  # NEW: actual file content for VS Code to apply
            "commands_run": response.commands_to_run,
            "vscode_commands": response.vscode_commands,
            "needs_user_input": response.needs_user_input,
            "user_input_prompt": response.user_input_prompt,
            "warnings": response.warnings,
            # NAVI V3: Intelligence fields
            "thinking_steps": response.thinking_steps,
            "files_read": response.files_read,
            "project_type": response.project_type,
            "framework": response.framework,
            "next_steps": response.next_steps,  # Suggested follow-up actions
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
    llm_provider: str = "openai",
    llm_model: Optional[str] = None,
    api_key: Optional[str] = None,
    current_file: Optional[str] = None,
    current_file_content: Optional[str] = None,
    selection: Optional[str] = None,
    open_files: Optional[List[str]] = None,
    errors: Optional[List[Dict]] = None,
    conversation_history: Optional[List[Dict]] = None,
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


async def process_navi_request_streaming(
    message: str,
    workspace_path: str,
    llm_provider: str = "openai",
    llm_model: Optional[str] = None,
    api_key: Optional[str] = None,
    current_file: Optional[str] = None,
    current_file_content: Optional[str] = None,
    selection: Optional[str] = None,
    open_files: Optional[List[str]] = None,
    errors: Optional[List[Dict]] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streaming version of process_navi_request that yields real-time progress events.

    Yields activity events as the processing progresses:
    - {"activity": {"kind": "...", "label": "...", "detail": "...", "status": "running/done"}}
    - {"result": {...}} - Final result when done

    Usage:
        async for event in process_navi_request_streaming(...):
            if "activity" in event:
                # Handle activity update
            elif "result" in event:
                # Handle final result
    """
    # Create engine
    engine = NaviEngine(
        workspace_path=workspace_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key=api_key,
    )

    try:
        # STEP 0: Intent Classification (NEW - wired up existing classifier)
        detected_intent = None
        try:
            from backend.agent.intent_classifier import classify_intent

            yield {
                "activity": {
                    "kind": "intent",
                    "label": "Understanding request",
                    "detail": "Classifying intent...",
                    "status": "running",
                }
            }

            # Classify intent with context
            detected_intent = classify_intent(
                message,
                metadata={
                    "files": [current_file] if current_file else [],
                    "language": (
                        _detect_language(current_file) if current_file else None
                    ),
                },
            )

            # Emit intent detection result
            confidence_pct = int(detected_intent.confidence * 100)
            yield {
                "intent": {
                    "family": (
                        detected_intent.family.value
                        if hasattr(detected_intent.family, "value")
                        else str(detected_intent.family)
                    ),
                    "kind": (
                        detected_intent.kind.value
                        if hasattr(detected_intent.kind, "value")
                        else str(detected_intent.kind)
                    ),
                    "confidence": detected_intent.confidence,
                }
            }

            yield {
                "activity": {
                    "kind": "intent",
                    "label": "Understanding request",
                    "detail": f"Detected: {detected_intent.kind.value if hasattr(detected_intent.kind, 'value') else detected_intent.kind} ({confidence_pct}%)",
                    "status": "done",
                }
            }

            # Emit narrative about what we understand
            from backend.services.narrative_generator import NarrativeGenerator

            intent_narrative = NarrativeGenerator.for_intent(
                (
                    detected_intent.kind.value
                    if hasattr(detected_intent.kind, "value")
                    else str(detected_intent.kind)
                ),
                detected_intent.confidence,
                message,
            )
            yield {"narrative": intent_narrative}

        except ImportError:
            logger.debug("Intent classifier not available, skipping classification")
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")

        # STEP 1: Project detection (happens in engine init)
        yield {
            "activity": {
                "kind": "detection",
                "label": "Detected",
                "detail": engine.project_type,
                "status": "done",
            }
        }

        # STEP 2: Build context
        yield {
            "activity": {
                "kind": "context",
                "label": "Building context",
                "detail": "Gathering workspace information",
                "status": "running",
            }
        }

        context = NaviContext(
            workspace_path=workspace_path,
            project_type=engine.project_type,
            technologies=engine.technologies,
            current_file=current_file,
            current_file_content=current_file_content,
            selection=selection,
            open_files=open_files or [],
            errors=errors or [],
            git_branch=engine._get_git_branch(),
            git_status=engine._get_git_status(),
            recent_conversation=conversation_history or [],
        )

        yield {
            "activity": {
                "kind": "context",
                "label": "Building context",
                "detail": "Complete",
                "status": "done",
            }
        }

        # STEP 3: Try to use persisted RAG index for faster context if available
        try:
            from backend.services.workspace_rag import (
                load_workspace_index,
                get_context_for_task,
            )

            persisted_index = await load_workspace_index(workspace_path)
            if persisted_index and persisted_index.total_chunks > 0:
                await get_context_for_task(workspace_path, message)
                yield {
                    "activity": {
                        "kind": "rag",
                        "label": "Searching code index",
                        "detail": f"{persisted_index.total_chunks} symbols indexed",
                        "status": "done",
                    }
                }
        except Exception as e:
            logger.debug(f"RAG index not available: {e}")

        project_info = ProjectAnalyzer.analyze(workspace_path)

        # STEP 3.5: Read actual source files with REAL-TIME streaming
        # This shows file read activities as they happen (like GitHub Copilot)
        file_count = ProjectAnalyzer.get_important_files_count(workspace_path)
        source_files: Dict[str, str] = {}

        # Stream file reads with real-time activity events
        async for event in ProjectAnalyzer.analyze_source_files_streaming(
            workspace_path, max_files=file_count
        ):
            if "activity" in event:
                # Forward activity events to the frontend in real-time
                yield event
            elif "files" in event:
                # Capture the final files dict
                source_files = event["files"]

        # Add source files to project info for context
        project_info.source_files = source_files
        project_info.files_read.extend(list(source_files.keys()))

        # Emit narrative about what we found (Copilot-style conversational update)
        if source_files:
            framework = project_info.framework or project_info.project_type
            yield {
                "narrative": f"I've analyzed {len(source_files)} files from this **{framework}** project.",
            }

        # STEP 4: Check for smart response - distinguish ACTION vs INFORMATION requests
        message_lower = message.lower()

        # ACTION request: User wants NAVI to actually execute commands
        # Expanded list to capture more natural phrasings like "run the project"
        is_run_action = any(
            phrase in message_lower
            for phrase in [
                "run this for me",
                "run it for me",
                "run the project for me",
                "run this project for me",
                "run the project",  # Simple "run the project" request
                "run project",  # Shortened version
                "run this project",  # This project variant
                "start the project",  # Start variant
                "start project",  # Shortened start
                "start the app",  # App variant
                "start the server",  # Server variant
                "run the app",  # App variant
                "run app",  # Shortened
                "launch the project",  # Launch variant
                "launch project",  # Shortened launch
                "can you run",
                "please run",
                "just run",
                "go ahead and run",
                "execute",
                "start it for me",
                "start the project for me",
                "launch it for me",
            ]
        )

        # INFORMATION request: User wants to know how to run
        is_run_question = not is_run_action and any(
            phrase in message_lower
            for phrase in [
                "how to run",
                "how do i run",
                "how can i run",
                "get started",
                "set up",
                "setup",
            ]
        )

        # For ACTION requests, generate executable actions
        if is_run_action and project_info.project_type != "unknown":
            yield {
                "activity": {
                    "kind": "response",
                    "label": "Preparing actions",
                    "detail": "Setting up commands to run",
                    "status": "running",
                }
            }

            # Get commands for actions
            install_cmd = IntelligentResponder._get_install_command(project_info)
            dev_cmd, dev_url = IntelligentResponder._get_dev_command(project_info)

            # Build actions for immediate execution with dependency tracking
            actions = []
            if install_cmd:
                actions.append(
                    {
                        "type": "runCommand",
                        "command": install_cmd,
                        "title": "Install dependencies",
                        "description": f"Run {install_cmd} to install project dependencies",
                        "cwd": workspace_path,
                        "requiresPreviousSuccess": False,  # First command, no dependency
                    }
                )
            if dev_cmd:
                actions.append(
                    {
                        "type": "runCommand",
                        "command": dev_cmd,
                        "title": "Start development server",
                        "description": f"Run {dev_cmd} to start the dev server"
                        + (f" at {dev_url}" if dev_url else ""),
                        "cwd": workspace_path,
                        "requiresPreviousSuccess": bool(
                            install_cmd
                        ),  # Only run if install succeeds
                    }
                )

            # Generate a natural, action-oriented response
            framework = project_info.framework or project_info.project_type
            response_text = f"I'll run this **{framework}** project for you."
            if dev_url:
                response_text += f" Once it's started, you can access it at {dev_url}."
            response_text += (
                "\n\nReview the commands below and click **Allow** to proceed."
            )

            yield {
                "activity": {
                    "kind": "response",
                    "label": "Preparing actions",
                    "detail": "Complete",
                    "status": "done",
                }
            }

            result = {
                "success": True,
                "message": response_text,
                "files_created": [],
                "files_modified": [],
                "file_edits": [],
                "commands_run": [],
                "vscode_commands": [],
                "needs_user_input": False,
                "user_input_prompt": None,
                "warnings": [],
                "thinking_steps": [
                    "Detected run action request",
                    "Prepared executable actions",
                ],
                "files_read": project_info.files_read,
                "project_type": project_info.project_type,
                "framework": project_info.framework,
                "next_steps": [],
                "actions": actions,
            }
            yield {"result": result}
            return

        # For INFORMATION requests (how to run), generate explanation without the "Would you like me to run" prompt
        if is_run_question and project_info.project_type != "unknown":
            yield {
                "activity": {
                    "kind": "response",
                    "label": "Generating response",
                    "detail": "Using project knowledge",
                    "status": "running",
                }
            }

            response_text = IntelligentResponder.generate_run_instructions(project_info)

            yield {
                "activity": {
                    "kind": "response",
                    "label": "Generating response",
                    "detail": "Complete",
                    "status": "done",
                }
            }

            # Generate contextual next_steps
            contextual_next_steps = [
                "Run the project for me",
                "What does this project do?",
            ]
            if project_info.has_env_example:
                contextual_next_steps.append("Help me set up the environment variables")
            if "test" in project_info.scripts:
                contextual_next_steps.append("Run the tests")
            if project_info.framework in ["nextjs", "react", "vue"]:
                contextual_next_steps.append("Show me the main components")

            result = {
                "success": True,
                "message": response_text,
                "files_created": [],
                "files_modified": [],
                "file_edits": [],
                "commands_run": [],
                "vscode_commands": [],
                "needs_user_input": False,
                "user_input_prompt": None,
                "warnings": [],
                "thinking_steps": [
                    "Detected run question",
                    "Generated project-specific instructions",
                ],
                "files_read": project_info.files_read,
                "project_type": project_info.project_type,
                "framework": project_info.framework,
                "next_steps": contextual_next_steps,
                "actions": [],  # No actions for information requests
            }
            yield {"result": result}
            return

        # STEP 5: Build prompt
        yield {
            "activity": {
                "kind": "prompt",
                "label": "Building prompt",
                "detail": "Preparing context for LLM",
                "status": "running",
            }
        }

        prompt = engine.brain._build_prompt(message, context, project_info)

        yield {
            "activity": {
                "kind": "prompt",
                "label": "Building prompt",
                "detail": "Complete",
                "status": "done",
            }
        }

        # STEP 6: Call LLM with STREAMING to show real-time thinking
        model_display = llm_model or engine.brain.model

        # Detect actual provider from model name if not explicitly set
        actual_provider = llm_provider
        if model_display:
            model_lower = model_display.lower()
            if "claude" in model_lower or "anthropic" in model_lower:
                actual_provider = "anthropic"
            elif "gpt" in model_lower or "o1" in model_lower or "o3" in model_lower:
                actual_provider = "openai"
            elif "gemini" in model_lower:
                actual_provider = "google"

        provider_display = actual_provider.capitalize()

        # Log for debugging
        logger.info(
            "[LLM Activity] provider=%s -> actual_provider=%s, model=%s",
            llm_provider,
            actual_provider,
            model_display,
        )

        yield {
            "activity": {
                "kind": "llm_call",
                "label": f"Calling {provider_display}",
                "detail": model_display,
                "status": "running",
            }
        }

        try:
            # Use streaming LLM call to show thinking in real-time
            llm_response = ""
            thinking_shown = False

            async for chunk in engine.brain._call_llm_streaming(
                prompt, context.recent_conversation
            ):
                if "thinking" in chunk:
                    # Stream thinking text to frontend
                    thinking_text = chunk["thinking"]

                    # Show first thinking activity
                    if not thinking_shown:
                        yield {
                            "activity": {
                                "kind": "thinking",
                                "label": "Thinking",
                                "detail": "",
                                "status": "running",
                            }
                        }
                        thinking_shown = True

                    # Yield thinking content for real-time display
                    yield {"thinking": thinking_text}

                elif "complete" in chunk:
                    llm_response = chunk["complete"]

            # Mark thinking as done
            if thinking_shown:
                yield {
                    "activity": {
                        "kind": "thinking",
                        "label": "Thinking",
                        "detail": "Complete",
                        "status": "done",
                    }
                }

            yield {
                "activity": {
                    "kind": "llm_call",
                    "label": f"Calling {provider_display}",
                    "detail": "Response received",
                    "status": "done",
                }
            }

            # STEP 7: Parse response
            yield {
                "activity": {
                    "kind": "parsing",
                    "label": "Processing response",
                    "detail": "Parsing JSON structure...",
                    "status": "running",
                }
            }

            response = engine.brain._parse_response(llm_response)

            yield {
                "activity": {
                    "kind": "parsing",
                    "label": "Processing response",
                    "detail": "Complete",
                    "status": "done",
                }
            }

            # STEP 8: Safety validation
            yield {
                "activity": {
                    "kind": "validation",
                    "label": "Safety check",
                    "detail": "Validating actions...",
                    "status": "running",
                }
            }

            is_safe, warnings = engine.brain.validator.validate_response(
                response, context.workspace_path
            )

            if not is_safe:
                yield {
                    "activity": {
                        "kind": "validation",
                        "label": "Safety check",
                        "detail": f"{len(warnings)} issue(s) require review",
                        "status": "done",
                    }
                }

                # Build result in same format as NaviEngine.process returns
                result = {
                    "success": False,
                    "message": DynamicMessages.safety_warning(warnings),
                    "files_created": [],
                    "files_modified": [],
                    "file_edits": [],
                    "commands_run": [],
                    "vscode_commands": [],
                    "needs_user_input": True,
                    "user_input_prompt": "Would you like to proceed with a safer approach?",
                    "warnings": warnings,
                    "thinking_steps": [],
                    "files_read": project_info.files_read,
                    "project_type": project_info.project_type,
                    "framework": project_info.framework,
                    "next_steps": [
                        "Suggest a safer alternative",
                        "Explain why this was flagged",
                    ],
                }
                yield {"result": result}
                return

            yield {
                "activity": {
                    "kind": "validation",
                    "label": "Safety check",
                    "detail": "Passed",
                    "status": "done",
                }
            }

            # Add intelligence fields
            response.warnings = warnings
            response.files_read = project_info.files_read
            response.project_type = project_info.project_type
            response.framework = project_info.framework

            # Build file_edits array for VS Code (same format as NaviEngine.process)
            file_edits: List[Dict[str, Any]] = []
            validation_results: Dict[str, Any] = {}

            # Validate generated code before presenting to user
            try:
                from backend.services.code_validator import (
                    validate_navi_output,
                    format_validation_summary,
                )

                all_files = {**response.files_to_create, **response.files_to_modify}
                if all_files:
                    is_valid, validation_results = validate_navi_output(all_files)
                    if not is_valid:
                        validation_summary = format_validation_summary(
                            validation_results
                        )
                        logger.warning(
                            f"Code validation found issues:\n{validation_summary}"
                        )
                        # Add validation info to response message
                        response.message += (
                            f"\n\n⚠️ **Code Validation:**\n{validation_summary}"
                        )
            except ImportError:
                logger.debug("Code validator not available")
            except Exception as e:
                logger.warning(f"Code validation failed: {e}")

            for file_path, content in response.files_to_modify.items():
                edit: Dict[str, Any] = {
                    "type": "editFile",
                    "filePath": file_path,
                    "content": content,
                    "operation": "modify",
                }
                # Add validation result if available
                if file_path in validation_results:
                    edit["validation"] = validation_results[file_path].to_dict()
                file_edits.append(edit)

            for file_path, content in response.files_to_create.items():
                edit: Dict[str, Any] = {
                    "type": "editFile",
                    "filePath": file_path,
                    "content": content,
                    "operation": "create",
                }
                if file_path in validation_results:
                    edit["validation"] = validation_results[file_path].to_dict()
                file_edits.append(edit)

            # Build proposed actions from commands_to_run for human-in-the-loop approval
            proposed_actions = []
            for cmd in response.commands_to_run:
                if isinstance(cmd, str) and cmd.strip():
                    # Try to generate a descriptive title based on the command
                    cmd_lower = cmd.lower()
                    if "install" in cmd_lower or cmd_lower.startswith(
                        ("npm i", "yarn add", "pnpm add")
                    ):
                        title = "Install dependencies"
                    elif "dev" in cmd_lower or "start" in cmd_lower:
                        title = "Start development server"
                    elif "build" in cmd_lower:
                        title = "Build the project"
                    elif "test" in cmd_lower:
                        title = "Run tests"
                    elif "lint" in cmd_lower:
                        title = "Run linter"
                    elif "git" in cmd_lower:
                        title = "Git operation"
                    else:
                        title = (
                            f"Run: {cmd[:30]}..." if len(cmd) > 30 else f"Run: {cmd}"
                        )

                    proposed_actions.append(
                        {
                            "type": "runCommand",
                            "command": cmd,
                            "title": title,
                            "description": f"Execute: {cmd}",
                        }
                    )

            # Build result in same format as NaviEngine.process returns
            result = {
                "success": True,
                "message": response.message,
                "files_created": list(response.files_to_create.keys()),
                "files_modified": list(response.files_to_modify.keys()),
                "file_edits": file_edits,
                "commands_run": [],  # Don't auto-run - use actions for approval instead
                "vscode_commands": response.vscode_commands,
                "needs_user_input": response.needs_user_input,
                "user_input_prompt": response.user_input_prompt,
                "warnings": response.warnings,
                "thinking_steps": response.thinking_steps,
                "files_read": response.files_read,
                "project_type": response.project_type,
                "framework": response.framework,
                "next_steps": response.next_steps,
                "actions": proposed_actions,  # Include proposed actions for approval UI
            }

            yield {"result": result}

        except Exception as e:
            logger.error(f"NAVI processing error: {e}", exc_info=True)
            # Show more error detail (increased from 50 to 500 characters)
            error_summary = str(e)[:500]
            yield {
                "activity": {
                    "kind": "error",
                    "label": "Processing Error",
                    "detail": error_summary,
                    "status": "done",
                }
            }

            # Build result in same format as NaviEngine.process returns
            result = {
                "success": False,
                "message": DynamicMessages.error_message(
                    e, context="processing your request"
                ),
                "files_created": [],
                "files_modified": [],
                "file_edits": [],
                "commands_run": [],
                "vscode_commands": [],
                "needs_user_input": True,
                "user_input_prompt": "Would you like to try a different approach?",
                "warnings": [],
                "thinking_steps": [],
                "files_read": project_info.files_read if project_info else [],
                "project_type": project_info.project_type if project_info else None,
                "framework": project_info.framework if project_info else None,
                "next_steps": [
                    "Try with more specific details",
                    "Check if resources are accessible",
                ],
            }
            yield {"result": result}

    finally:
        await engine.close()
