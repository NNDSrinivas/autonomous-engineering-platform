"""
NAVI Project Analyzer - Read-First Intelligence

This module makes NAVI intelligent by reading project files BEFORE responding.
This is how Codex and Claude Code work - they read your project first.

Usage in navi.py:
    from backend.navi.project_analyzer import (
        ProjectAnalyzer,
        generate_run_instructions,
        is_run_question,
    )

    # In navi_chat endpoint, before agent_loop:
    if workspace_root and is_run_question(request.message):
        project_info = await ProjectAnalyzer.analyze(workspace_root)
        if project_info.project_type != "unknown":
            return ChatResponse(
                content=generate_run_instructions(project_info),
                ...
            )
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ThinkingStep:
    """A step shown to the user during analysis"""

    id: str
    label: str
    status: str = "completed"  # pending, running, completed, failed


@dataclass
class ProjectInfo:
    """Information gathered from reading project files"""

    project_type: str = "unknown"  # nextjs, react, vue, express, python, etc.
    framework: Optional[str] = None  # "Next.js", "React", "Vue.js"
    framework_version: Optional[str] = None  # "14.0.0"
    package_manager: str = "npm"  # npm, yarn, pnpm, bun

    # From package.json
    name: Optional[str] = None
    scripts: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)

    # From config files
    has_typescript: bool = False
    has_eslint: bool = False
    has_docker: bool = False
    has_env_example: bool = False
    env_vars: List[str] = field(default_factory=list)

    # Analysis metadata
    files_read: List[str] = field(default_factory=list)
    thinking_steps: List[ThinkingStep] = field(default_factory=list)


class ProjectAnalyzer:
    """
    Analyzes a project by reading its files.
    This is what makes NAVI intelligent - reading before responding.
    """

    KEY_FILES = [
        "package.json",
        "README.md",
        "readme.md",
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
        ".env.example",
        ".env.local.example",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "docker-compose.yml",
        "Dockerfile",
        ".eslintrc.js",
        ".eslintrc.json",
        "pom.xml",
        "build.gradle",
        "Gemfile",
    ]

    @classmethod
    async def analyze(cls, workspace_path: str) -> ProjectInfo:
        """
        Analyze a project by reading its key files.
        Returns structured information about the project.
        """
        info = ProjectInfo()
        workspace = Path(workspace_path)

        if not workspace.exists():
            logger.warning(
                f"[ProjectAnalyzer] Workspace does not exist: {workspace_path}"
            )
            return info

        # Add initial thinking step
        info.thinking_steps.append(
            ThinkingStep(id="start", label="Analyzing project...", status="completed")
        )

        # Read each key file
        for filename in cls.KEY_FILES:
            file_path = workspace / filename
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    cls._process_file(filename, content, info)
                    info.files_read.append(filename)

                    # Add thinking step for important files
                    if filename == "package.json":
                        info.thinking_steps.append(
                            ThinkingStep(
                                id=f"read-{filename}",
                                label=f"Read {filename}",
                                status="completed",
                            )
                        )
                except Exception as e:
                    logger.debug(f"[ProjectAnalyzer] Could not read {filename}: {e}")

        # Detect package manager from lock files
        lock_files = [
            ("yarn.lock", "yarn"),
            ("pnpm-lock.yaml", "pnpm"),
            ("bun.lockb", "bun"),
            ("package-lock.json", "npm"),
        ]
        for lock_file, pm in lock_files:
            if (workspace / lock_file).exists():
                info.package_manager = pm
                break

        # Add framework detection step
        if info.framework:
            version_str = f" {info.framework_version}" if info.framework_version else ""
            info.thinking_steps.append(
                ThinkingStep(
                    id="detect-framework",
                    label=f"Detected {info.framework}{version_str}",
                    status="completed",
                )
            )

        # Add package manager step
        info.thinking_steps.append(
            ThinkingStep(
                id="detect-pm",
                label=f"Using {info.package_manager}",
                status="completed",
            )
        )

        logger.info(
            f"[ProjectAnalyzer] Analysis complete: type={info.project_type}, "
            f"framework={info.framework}, files_read={len(info.files_read)}"
        )

        return info

    @classmethod
    def _process_file(cls, filename: str, content: str, info: ProjectInfo) -> None:
        """Process a file and extract information"""

        if filename == "package.json":
            cls._process_package_json(content, info)

        elif filename == "tsconfig.json":
            info.has_typescript = True

        elif filename.startswith(".eslint"):
            info.has_eslint = True

        elif filename in ["Dockerfile", "docker-compose.yml"]:
            info.has_docker = True

        elif filename in [".env.example", ".env.local.example"]:
            info.has_env_example = True
            # Extract env var names
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    var_name = line.split("=")[0].strip()
                    if var_name:
                        info.env_vars.append(var_name)

        # Detect framework from config files
        elif filename.startswith("next.config"):
            info.project_type = "nextjs"
            info.framework = "Next.js"

        elif filename.startswith("vite.config"):
            if info.project_type == "unknown":
                info.project_type = "vite"

        elif filename.startswith("vue.config") or filename.startswith("nuxt.config"):
            info.project_type = "vue" if "vue" in filename else "nuxt"
            info.framework = "Vue.js" if "vue" in filename else "Nuxt"

        elif filename == "angular.json":
            info.project_type = "angular"
            info.framework = "Angular"

        elif filename == "requirements.txt":
            info.project_type = "python"
            info.framework = "Python"
            # Check for common frameworks
            content_lower = content.lower()
            if "fastapi" in content_lower:
                info.framework = "FastAPI"
            elif "django" in content_lower:
                info.framework = "Django"
            elif "flask" in content_lower:
                info.framework = "Flask"

        elif filename == "pyproject.toml":
            info.project_type = "python"
            if "fastapi" in content.lower():
                info.framework = "FastAPI"
            elif "django" in content.lower():
                info.framework = "Django"

        elif filename == "Cargo.toml":
            info.project_type = "rust"
            info.framework = "Rust"

        elif filename == "go.mod":
            info.project_type = "go"
            info.framework = "Go"

        elif filename == "pom.xml":
            info.project_type = "java"
            info.framework = "Java (Maven)"

        elif filename == "build.gradle":
            info.project_type = "java"
            info.framework = "Java (Gradle)"

        elif filename == "Gemfile":
            info.project_type = "ruby"
            if "rails" in content.lower():
                info.framework = "Ruby on Rails"
            else:
                info.framework = "Ruby"

    @classmethod
    def _process_package_json(cls, content: str, info: ProjectInfo) -> None:
        """Extract information from package.json"""
        try:
            pkg = json.loads(content)

            info.name = pkg.get("name")
            info.scripts = pkg.get("scripts", {})

            deps = pkg.get("dependencies", {})
            dev_deps = pkg.get("devDependencies", {})

            info.dependencies = list(deps.keys())
            info.dev_dependencies = list(dev_deps.keys())

            all_deps = {**deps, **dev_deps}

            # Detect framework from dependencies
            if "next" in all_deps:
                info.project_type = "nextjs"
                info.framework = "Next.js"
                version = deps.get("next", dev_deps.get("next", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "nuxt" in all_deps:
                info.project_type = "nuxt"
                info.framework = "Nuxt"
                version = deps.get("nuxt", dev_deps.get("nuxt", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "@angular/core" in all_deps:
                info.project_type = "angular"
                info.framework = "Angular"
                version = deps.get("@angular/core", dev_deps.get("@angular/core", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "vue" in all_deps:
                info.project_type = "vue"
                info.framework = "Vue.js"
                version = deps.get("vue", dev_deps.get("vue", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "svelte" in all_deps:
                info.project_type = "svelte"
                info.framework = "Svelte"
                version = deps.get("svelte", dev_deps.get("svelte", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "react" in all_deps:
                if "vite" in all_deps:
                    info.project_type = "react-vite"
                    info.framework = "React + Vite"
                else:
                    info.project_type = "react"
                    info.framework = "React"
                version = deps.get("react", dev_deps.get("react", ""))
                info.framework_version = version.lstrip("^~") if version else None

            elif "express" in all_deps:
                info.project_type = "express"
                info.framework = "Express.js"

            elif "fastify" in all_deps:
                info.project_type = "fastify"
                info.framework = "Fastify"

            elif "hono" in all_deps:
                info.project_type = "hono"
                info.framework = "Hono"

            # Check for TypeScript
            if "typescript" in all_deps:
                info.has_typescript = True

        except json.JSONDecodeError:
            logger.warning("[ProjectAnalyzer] Could not parse package.json")


# Default ports for different frameworks
DEFAULT_PORTS = {
    "nextjs": 3000,
    "nuxt": 3000,
    "react": 3000,
    "react-vite": 5173,
    "vite": 5173,
    "vue": 8080,
    "angular": 4200,
    "svelte": 5173,
    "express": 3000,
    "fastify": 3000,
    "hono": 3000,
    "fastapi": 8000,
    "django": 8000,
    "flask": 5000,
    "python": 8000,
    "rust": 8080,
    "go": 8080,
    "java": 8080,
    "ruby": 3000,
}


def generate_run_instructions(info: ProjectInfo) -> str:
    """
    Generate intelligent run instructions based on project analysis.
    This replaces the generic "npm install, npm run dev" response.
    """
    parts = []
    pm = info.package_manager

    # Project identification
    if info.framework:
        version = f" {info.framework_version}" if info.framework_version else ""
        name_part = f" ({info.name})" if info.name else ""
        parts.append(f"This is a **{info.framework}{version}** project{name_part}.\n")

    # Environment setup (if needed)
    if info.has_env_example:
        parts.append("**Environment Setup:**")
        parts.append("1. Copy `.env.example` to `.env.local`")
        if info.env_vars:
            vars_preview = ", ".join(info.env_vars[:5])
            if len(info.env_vars) > 5:
                vars_preview += f" (+{len(info.env_vars) - 5} more)"
            parts.append(f"2. Fill in required variables: `{vars_preview}`")
        parts.append("")

    # Run commands based on project type
    parts.append("**To run this project:**")

    port = DEFAULT_PORTS.get(info.project_type, 3000)

    # JavaScript/TypeScript projects
    if info.project_type in [
        "nextjs",
        "react",
        "react-vite",
        "vue",
        "angular",
        "svelte",
        "nuxt",
        "express",
        "fastify",
        "hono",
        "vite",
    ]:
        parts.append(f"1. `{pm} install` - Install dependencies")

        if "dev" in info.scripts:
            parts.append(f"2. `{pm} run dev` - Start development server")
        elif "start" in info.scripts:
            parts.append(f"2. `{pm} start` - Start the server")
        elif "serve" in info.scripts:
            parts.append(f"2. `{pm} run serve` - Start the server")

        parts.append(f"3. Open **http://localhost:{port}**")

    # Python projects
    elif info.project_type == "python":
        parts.append("1. `python -m venv venv` - Create virtual environment")
        parts.append(
            "2. `source venv/bin/activate` - Activate it "
            "(or `venv\\Scripts\\activate` on Windows)"
        )
        parts.append("3. `pip install -r requirements.txt` - Install dependencies")

        if info.framework == "FastAPI":
            parts.append("4. `uvicorn main:app --reload` - Start FastAPI server")
        elif info.framework == "Django":
            parts.append("4. `python manage.py runserver` - Start Django server")
        elif info.framework == "Flask":
            parts.append("4. `flask run` - Start Flask server")
        else:
            parts.append("4. `python main.py` - Run the application")

        parts.append(f"5. Open **http://localhost:{port}**")

    # Rust projects
    elif info.project_type == "rust":
        parts.append("1. `cargo build` - Build the project")
        parts.append("2. `cargo run` - Run the application")

    # Go projects
    elif info.project_type == "go":
        parts.append("1. `go mod download` - Download dependencies")
        parts.append("2. `go run .` - Run the application")

    # Java projects
    elif info.project_type == "java":
        if "Maven" in (info.framework or ""):
            parts.append("1. `mvn install` - Install dependencies")
            parts.append("2. `mvn spring-boot:run` - Run the application")
        else:
            parts.append("1. `gradle build` - Build the project")
            parts.append("2. `gradle bootRun` - Run the application")

    # Ruby projects
    elif info.project_type == "ruby":
        parts.append("1. `bundle install` - Install dependencies")
        if "Rails" in (info.framework or ""):
            parts.append("2. `rails server` - Start Rails server")
        else:
            parts.append("2. `ruby main.rb` - Run the application")

    # Other available scripts (for JS projects)
    if info.scripts:
        useful_scripts = _get_useful_scripts(info)
        if useful_scripts:
            parts.append("\n**Other available commands:**")
            for script, desc in useful_scripts:
                parts.append(f"- `{pm} run {script}` - {desc}")

    return "\n".join(parts)


def _get_useful_scripts(info: ProjectInfo) -> List[tuple]:
    """Get useful scripts with descriptions"""
    script_descriptions = {
        "build": "Create production build",
        "test": "Run tests",
        "lint": "Run linter",
        "format": "Format code",
        "typecheck": "Check TypeScript types",
        "type-check": "Check TypeScript types",
        "preview": "Preview production build",
        "storybook": "Start Storybook",
        "e2e": "Run end-to-end tests",
        "cypress": "Run Cypress tests",
        "jest": "Run Jest tests",
        "vitest": "Run Vitest tests",
    }

    result = []
    for script in info.scripts:
        if script in script_descriptions and script not in ["dev", "start", "serve"]:
            result.append((script, script_descriptions[script]))

    return result[:5]  # Max 5


def is_run_question(message: str) -> bool:
    """Check if the message is asking how to run the project"""
    lower = message.lower().strip()

    # Direct patterns
    patterns = [
        "how to run",
        "how do i run",
        "how can i run",
        "run this project",
        "run the project",
        "start the project",
        "start this project",
        "launch the project",
        "launch this",
        "get started",
        "getting started",
        "set up",
        "setup",
        "run this",
        "start this",
        "how to start",
        "how do i start",
        "run it",
        "start it",
        "execute this",
        "boot up",
        "spin up",
        "fire up",
    ]

    if any(pattern in lower for pattern in patterns):
        return True

    # Check for short questions about running
    if len(lower) < 50:
        short_patterns = [
            "run?",
            "start?",
            "launch?",
            "execute?",
            "how to run",
            "run this",
        ]
        if any(pattern in lower for pattern in short_patterns):
            return True

    return False


def is_scripts_question(message: str) -> bool:
    """Check if asking about available scripts"""
    lower = message.lower()
    patterns = [
        "what scripts",
        "available scripts",
        "npm scripts",
        "yarn scripts",
        "package scripts",
        "what commands",
        "available commands",
    ]
    return any(pattern in lower for pattern in patterns)


def is_dependencies_question(message: str) -> bool:
    """Check if asking about dependencies"""
    lower = message.lower()
    patterns = [
        "what dependencies",
        "what packages",
        "using what",
        "tech stack",
        "technologies",
        "frameworks used",
    ]
    return any(pattern in lower for pattern in patterns)
