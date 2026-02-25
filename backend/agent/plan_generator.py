"""
Plan Generator - Creates architectural implementation plans by analyzing codebase.

This module:
1. Analyzes the codebase to understand patterns, structure, and conventions
2. Breaks down feature requests into concrete implementation steps
3. Identifies affected files and potential risks
4. Generates a comprehensive plan for NAVI to execute
"""

import logging
import uuid
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend.agent.plan_mode_controller import (
    ImplementationPlan,
    PlanStep,
    PlanStepType,
)

logger = logging.getLogger(__name__)


class PlanGenerator:
    """
    Generates implementation plans by analyzing codebase and user requests.

    The generator:
    1. Reads project structure and key files
    2. Identifies patterns and conventions
    3. Breaks down the feature into steps
    4. Estimates risks for each step
    """

    def __init__(self, llm_router=None):
        """Initialize the plan generator."""
        self.llm_router = llm_router
        if not self.llm_router:
            try:
                from backend.ai.llm_router import LLMRouter

                self.llm_router = LLMRouter()
            except ImportError:
                logger.warning("LLM router not available for plan generator")

    async def generate_plan(
        self,
        user_request: str,
        workspace_path: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ImplementationPlan:
        """
        Generate an implementation plan for the user's request.

        Args:
            user_request: The feature/task the user wants implemented
            workspace_path: Path to the workspace
            context: Additional context (codebase analysis, etc.)

        Returns:
            ImplementationPlan with steps to implement the feature
        """
        logger.info("[PLAN_GEN] Generating plan for: %s", user_request[:100])

        # Step 1: Analyze codebase structure
        codebase_analysis = await self._analyze_codebase(workspace_path)

        # Step 2: Identify what needs to be done
        task_breakdown = await self._break_down_task(
            user_request, codebase_analysis, context or {}
        )

        # Step 3: Generate implementation steps
        steps = self._generate_steps(task_breakdown, codebase_analysis)

        # Step 4: Identify affected files
        affected_files = self._identify_affected_files(steps, codebase_analysis)

        # Step 5: Create the plan
        plan = ImplementationPlan(
            id=f"plan_{uuid.uuid4().hex[:8]}",
            title=self._generate_plan_title(user_request),
            description=task_breakdown.get("description", user_request),
            steps=steps,
            architecture_summary=task_breakdown.get("architecture", ""),
            affected_files=affected_files,
            estimated_steps=len(steps),
            created_at=time.time(),
            status="draft",
        )

        logger.info(
            "[PLAN_GEN] Plan generated: %s with %d steps", plan.title, len(plan.steps)
        )

        return plan

    async def _analyze_codebase(self, workspace_path: str) -> Dict[str, Any]:
        """
        Analyze the codebase to understand structure and patterns.

        Returns analysis including:
        - Project type (frontend, backend, fullstack)
        - Language and framework
        - Directory structure
        - Key files and their purposes
        - Coding patterns/conventions
        """
        analysis = {
            "project_type": "unknown",
            "languages": [],
            "frameworks": [],
            "structure": {},
            "patterns": [],
            "key_files": [],
        }

        workspace = Path(workspace_path)
        if not workspace.exists():
            return analysis

        # Detect project type from key files
        key_files_to_check = [
            ("package.json", "javascript", "node"),
            ("pyproject.toml", "python", "python"),
            ("requirements.txt", "python", "python"),
            ("Cargo.toml", "rust", "rust"),
            ("go.mod", "go", "go"),
            ("pom.xml", "java", "maven"),
            ("build.gradle", "java", "gradle"),
            ("composer.json", "php", "php"),
            ("Gemfile", "ruby", "ruby"),
        ]

        for filename, language, framework in key_files_to_check:
            if (workspace / filename).exists():
                if language not in analysis["languages"]:
                    analysis["languages"].append(language)
                if framework not in analysis["frameworks"]:
                    analysis["frameworks"].append(framework)
                analysis["key_files"].append(filename)

        # Detect frontend frameworks
        if (workspace / "package.json").exists():
            try:
                import json

                with open(workspace / "package.json") as f:
                    pkg = json.load(f)
                    deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }

                    if "react" in deps:
                        analysis["frameworks"].append("react")
                    if "vue" in deps:
                        analysis["frameworks"].append("vue")
                    if "next" in deps:
                        analysis["frameworks"].append("nextjs")
                    if "@angular/core" in deps:
                        analysis["frameworks"].append("angular")
                    if "express" in deps:
                        analysis["frameworks"].append("express")
                    if "fastapi" in str(deps) or "fastapi" in str(pkg):
                        analysis["frameworks"].append("fastapi")
            except Exception:
                pass

        # Detect Python frameworks
        if (workspace / "pyproject.toml").exists():
            try:
                content = (workspace / "pyproject.toml").read_text()
                if "fastapi" in content.lower():
                    analysis["frameworks"].append("fastapi")
                if "django" in content.lower():
                    analysis["frameworks"].append("django")
                if "flask" in content.lower():
                    analysis["frameworks"].append("flask")
            except Exception:
                pass

        # Analyze directory structure
        analysis["structure"] = self._get_directory_structure(workspace)

        # Determine project type
        if "react" in analysis["frameworks"] or "vue" in analysis["frameworks"]:
            if (
                "fastapi" in analysis["frameworks"]
                or "express" in analysis["frameworks"]
            ):
                analysis["project_type"] = "fullstack"
            else:
                analysis["project_type"] = "frontend"
        elif "fastapi" in analysis["frameworks"] or "django" in analysis["frameworks"]:
            analysis["project_type"] = "backend"
        elif analysis["languages"]:
            analysis["project_type"] = "backend"

        return analysis

    def _get_directory_structure(
        self, workspace: Path, max_depth: int = 3
    ) -> Dict[str, Any]:
        """Get directory structure up to max_depth."""
        structure = {"directories": [], "files": []}

        try:
            for item in workspace.iterdir():
                if item.name.startswith("."):
                    continue
                if item.name in (
                    "node_modules",
                    "__pycache__",
                    "venv",
                    ".venv",
                    "dist",
                    "build",
                ):
                    continue

                if item.is_dir():
                    structure["directories"].append(item.name)
                elif item.is_file():
                    structure["files"].append(item.name)
        except Exception:
            pass

        return structure

    async def _break_down_task(
        self,
        user_request: str,
        codebase_analysis: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Break down the user's request into a structured task description.

        Uses LLM to analyze the request and create:
        - Clear description of what needs to be done
        - Architecture decisions
        - Components to create/modify
        - Potential challenges
        """
        # Build prompt for LLM
        frameworks_str = ", ".join(codebase_analysis.get("frameworks", ["unknown"]))
        languages_str = ", ".join(codebase_analysis.get("languages", ["unknown"]))

        prompt = f"""Analyze this feature request and create an implementation plan.

**User Request:** {user_request}

**Project Info:**
- Type: {codebase_analysis.get("project_type", "unknown")}
- Languages: {languages_str}
- Frameworks: {frameworks_str}
- Key Files: {", ".join(codebase_analysis.get("key_files", []))}

**Instructions:**
Create a structured breakdown including:
1. A clear description of what needs to be implemented
2. Architecture decisions (what components, where they go)
3. List of specific implementation tasks
4. Potential risks or challenges

Respond in JSON format:
{{
    "description": "Clear description of the feature",
    "architecture": "High-level architecture decisions",
    "tasks": [
        {{"task": "description", "type": "create|modify|test|deploy", "files": ["file1.py"], "risk": "low|medium|high"}}
    ],
    "challenges": ["potential challenge 1", "potential challenge 2"]
}}
"""

        try:
            if self.llm_router:
                response = await self.llm_router.generate(
                    prompt=prompt,
                    model="gpt-4",
                    temperature=0.3,
                    max_tokens=2000,
                )

                # Parse JSON response
                import json
                import re

                # Extract JSON from response
                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning("[PLAN_GEN] LLM task breakdown failed: %s", e)

        # Fallback: basic breakdown without LLM
        return self._basic_task_breakdown(user_request, codebase_analysis)

    def _basic_task_breakdown(
        self, user_request: str, codebase_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a basic task breakdown without LLM."""
        # Detect common patterns in request
        request_lower = user_request.lower()

        tasks = []
        description = user_request
        architecture = "Standard implementation following existing patterns"

        # Detect what kind of feature this is
        if any(word in request_lower for word in ["api", "endpoint", "route"]):
            tasks.extend(
                [
                    {
                        "task": "Create API endpoint",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                    {
                        "task": "Add request/response models",
                        "type": "create",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Implement business logic",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                    {"task": "Add tests", "type": "create", "files": [], "risk": "low"},
                ]
            )
            architecture = "REST API endpoint with service layer"

        elif any(word in request_lower for word in ["component", "ui", "page", "form"]):
            tasks.extend(
                [
                    {
                        "task": "Create UI component",
                        "type": "create",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Add styling",
                        "type": "create",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Connect to state/API",
                        "type": "modify",
                        "files": [],
                        "risk": "medium",
                    },
                    {"task": "Add tests", "type": "create", "files": [], "risk": "low"},
                ]
            )
            architecture = "React/Vue component with state management"

        elif any(
            word in request_lower
            for word in ["database", "model", "table", "migration"]
        ):
            tasks.extend(
                [
                    {
                        "task": "Create database model",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                    {
                        "task": "Create migration",
                        "type": "create",
                        "files": [],
                        "risk": "high",
                    },
                    {
                        "task": "Add repository/service layer",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                    {"task": "Add tests", "type": "create", "files": [], "risk": "low"},
                ]
            )
            architecture = "Database model with migration and service layer"

        elif any(word in request_lower for word in ["test", "testing"]):
            tasks.extend(
                [
                    {
                        "task": "Create test file",
                        "type": "create",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Add unit tests",
                        "type": "create",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Add integration tests",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                ]
            )
            architecture = "Test suite with unit and integration tests"

        else:
            # Generic feature
            tasks.extend(
                [
                    {
                        "task": "Analyze existing code",
                        "type": "analyze",
                        "files": [],
                        "risk": "low",
                    },
                    {
                        "task": "Create new files/components",
                        "type": "create",
                        "files": [],
                        "risk": "medium",
                    },
                    {
                        "task": "Integrate with existing code",
                        "type": "modify",
                        "files": [],
                        "risk": "medium",
                    },
                    {"task": "Add tests", "type": "create", "files": [], "risk": "low"},
                ]
            )

        return {
            "description": description,
            "architecture": architecture,
            "tasks": tasks,
            "challenges": ["Ensure compatibility with existing code patterns"],
        }

    def _generate_steps(
        self, task_breakdown: Dict[str, Any], codebase_analysis: Dict[str, Any]
    ) -> List[PlanStep]:
        """Generate concrete implementation steps from task breakdown."""
        steps = []
        step_num = 0

        # Always start with analysis
        steps.append(
            PlanStep(
                id=f"step_{step_num}",
                description="Analyze codebase structure and patterns",
                step_type=PlanStepType.ANALYZE,
                tool="repo.inspect",
                arguments={"max_depth": 3, "max_files": 100},
                estimated_risk="low",
            )
        )
        step_num += 1

        steps.append(
            PlanStep(
                id=f"step_{step_num}",
                description="Read relevant existing files",
                step_type=PlanStepType.ANALYZE,
                tool="code.read_files",
                arguments={"paths": codebase_analysis.get("key_files", [])[:5]},
                estimated_risk="low",
            )
        )
        step_num += 1

        # Convert tasks to steps
        for task in task_breakdown.get("tasks", []):
            task_type = task.get("type", "create")
            task_desc = task.get("task", "Unknown task")
            task_risk = task.get("risk", "medium")
            task_files = task.get("files", [])

            if task_type == "analyze":
                steps.append(
                    PlanStep(
                        id=f"step_{step_num}",
                        description=task_desc,
                        step_type=PlanStepType.ANALYZE,
                        tool="code.search",
                        arguments={"query": task_desc},
                        estimated_risk=task_risk,
                    )
                )

            elif task_type == "create":
                steps.append(
                    PlanStep(
                        id=f"step_{step_num}",
                        description=task_desc,
                        step_type=PlanStepType.CREATE_FILE,
                        tool="code.create_file",
                        arguments={"files": task_files, "task": task_desc},
                        estimated_risk=task_risk,
                    )
                )

            elif task_type == "modify":
                steps.append(
                    PlanStep(
                        id=f"step_{step_num}",
                        description=task_desc,
                        step_type=PlanStepType.MODIFY_FILE,
                        tool="code.apply_patch",
                        arguments={"files": task_files, "task": task_desc},
                        estimated_risk=task_risk,
                    )
                )

            elif task_type == "test":
                steps.append(
                    PlanStep(
                        id=f"step_{step_num}",
                        description=task_desc,
                        step_type=PlanStepType.RUN_TESTS,
                        tool="test.run",
                        arguments={"scope": "related"},
                        estimated_risk=task_risk,
                    )
                )

            elif task_type == "deploy":
                steps.append(
                    PlanStep(
                        id=f"step_{step_num}",
                        description=task_desc,
                        step_type=PlanStepType.DEPLOY,
                        tool="deploy.run",
                        arguments={"environment": "staging"},
                        estimated_risk="high",
                    )
                )

            step_num += 1

        # Always end with test verification
        steps.append(
            PlanStep(
                id=f"step_{step_num}",
                description="Run tests to verify implementation",
                step_type=PlanStepType.RUN_TESTS,
                tool="test.run",
                arguments={"scope": "all", "with_coverage": True},
                estimated_risk="low",
            )
        )

        return steps

    def _identify_affected_files(
        self, steps: List[PlanStep], codebase_analysis: Dict[str, Any]
    ) -> List[str]:
        """Identify files that will be affected by the plan."""
        affected = set()

        for step in steps:
            if step.step_type in (PlanStepType.CREATE_FILE, PlanStepType.MODIFY_FILE):
                files = step.arguments.get("files", [])
                affected.update(files)

        # Add likely affected files based on codebase analysis
        # This is a heuristic - in practice the LLM would identify these
        affected.update(codebase_analysis.get("key_files", []))

        return list(affected)

    def _generate_plan_title(self, user_request: str) -> str:
        """Generate a concise title for the plan."""
        # Take first 50 chars and clean up
        title = user_request[:50]
        if len(user_request) > 50:
            title = title.rsplit(" ", 1)[0] + "..."
        return f"Implement: {title}"


async def generate_implementation_plan(
    user_request: str,
    workspace_path: str,
    context: Optional[Dict[str, Any]] = None,
) -> ImplementationPlan:
    """
    Public API to generate an implementation plan.

    Args:
        user_request: What the user wants implemented
        workspace_path: Path to the workspace
        context: Additional context

    Returns:
        ImplementationPlan ready for execution
    """
    generator = PlanGenerator()
    return await generator.generate_plan(user_request, workspace_path, context)
