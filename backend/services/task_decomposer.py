"""
Task Decomposer Service

Uses LLM to break down enterprise project goals into executable tasks.
Supports all LLM providers with BYOK (Bring Your Own Key).

Example:
    Goal: "Build an e-commerce platform with auth, payments, admin dashboard"

    Generates 120+ tasks organized into phases:
    1. Project Setup (10 tasks)
    2. Database Design (15 tasks)
    3. Authentication (20 tasks)
    4. Product Catalog (25 tasks)
    5. Shopping Cart (15 tasks)
    6. Payment Integration (20 tasks)
    7. Admin Dashboard (25 tasks)
    8. Testing (20 tasks)
    9. Deployment (15 tasks)
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from backend.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


@dataclass
class DecomposedTask:
    """A task generated from goal decomposition"""
    id: str
    title: str
    description: str
    phase: str
    priority: int  # 1-100, higher is more important
    dependencies: List[str]  # List of task IDs this depends on
    can_parallelize: bool
    estimated_complexity: str  # simple, medium, complex
    verification_criteria: List[str]
    tags: List[str]
    outputs: Dict[str, Any]  # Expected outputs


@dataclass
class DecompositionResult:
    """Result of goal decomposition"""
    project_name: str
    project_type: str
    phases: List[str]
    tasks: List[DecomposedTask]
    milestones: List[Dict[str, Any]]
    architecture_decisions: List[Dict[str, Any]]
    estimated_total_hours: int
    tech_stack: Dict[str, str]


DECOMPOSITION_SYSTEM_PROMPT = """You are an expert software architect and project manager. Your job is to decompose high-level project goals into detailed, executable tasks.

When decomposing a project:
1. Break down into logical phases (Setup, Database, Auth, Features, Testing, Deployment)
2. Create specific, actionable tasks with clear verification criteria
3. Identify task dependencies - which tasks must complete before others
4. Mark tasks that can run in parallel
5. Estimate complexity (simple: <30min, medium: 30min-2hr, complex: >2hr)
6. Include architecture decisions that need human review
7. Create milestones for phase completions

IMPORTANT: Generate tasks that an AI coding agent can execute. Each task should:
- Have a single, clear objective
- Include specific files/components to create or modify
- Have testable verification criteria
- Include expected outputs

Output Format (JSON):
{
    "project_name": "E-Commerce Platform",
    "project_type": "e-commerce",
    "tech_stack": {
        "frontend": "React/Next.js",
        "backend": "Python/FastAPI",
        "database": "PostgreSQL",
        "auth": "JWT + OAuth2",
        "payments": "Stripe",
        "deployment": "Docker + Kubernetes"
    },
    "phases": ["setup", "database", "auth", "catalog", "cart", "payments", "admin", "testing", "deployment"],
    "milestones": [
        {"id": "m1", "title": "Project Foundation", "phase": "setup", "tasks": ["t001", "t002", ...]},
        ...
    ],
    "architecture_decisions": [
        {
            "id": "adr001",
            "title": "Database Choice",
            "decision": "PostgreSQL for relational data, Redis for caching",
            "rationale": "Strong ACID compliance, scalability",
            "requires_approval": true
        }
    ],
    "tasks": [
        {
            "id": "t001",
            "title": "Initialize Next.js project with TypeScript",
            "description": "Create new Next.js 14 project with TypeScript, ESLint, Tailwind CSS",
            "phase": "setup",
            "priority": 100,
            "dependencies": [],
            "can_parallelize": false,
            "estimated_complexity": "simple",
            "verification_criteria": [
                "package.json exists with next, react, typescript dependencies",
                "tsconfig.json configured correctly",
                "npm run dev starts without errors"
            ],
            "tags": ["frontend", "setup"],
            "outputs": {
                "files_created": ["package.json", "tsconfig.json", "next.config.js"],
                "commands_to_verify": ["npm run dev"]
            }
        },
        ...
    ],
    "estimated_total_hours": 120
}"""


class TaskDecomposer:
    """
    Decomposes project goals into executable tasks using LLM.

    Supports all LLM providers (OpenAI, Anthropic, Google, Groq, etc.)
    with BYOK (Bring Your Own Key) support.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.3,  # Lower for more consistent output
    ):
        self.client = LLMClient(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=8192,  # Need large output for task list
            system_prompt=DECOMPOSITION_SYSTEM_PROMPT,
        )
        self.provider = provider
        self.model = model

    async def decompose_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        min_tasks: int = 50,
        max_tasks: int = 200,
    ) -> DecompositionResult:
        """
        Decompose a project goal into executable tasks.

        Args:
            goal: The high-level project goal
            context: Optional context (existing files, tech preferences)
            min_tasks: Minimum number of tasks to generate
            max_tasks: Maximum number of tasks to generate

        Returns:
            DecompositionResult with all tasks and metadata
        """
        logger.info(f"Decomposing goal: {goal[:100]}...")

        # Build the prompt
        prompt = self._build_decomposition_prompt(goal, context, min_tasks, max_tasks)

        # Call LLM
        response = await self.client.complete(prompt)

        # Parse the JSON response
        result = self._parse_decomposition_response(response.content)

        logger.info(f"Decomposed into {len(result.tasks)} tasks across {len(result.phases)} phases")

        return result

    def _build_decomposition_prompt(
        self,
        goal: str,
        context: Optional[Dict[str, Any]],
        min_tasks: int,
        max_tasks: int,
    ) -> str:
        """Build the prompt for task decomposition"""

        prompt = f"""Decompose the following project into detailed, executable tasks.

PROJECT GOAL:
{goal}

REQUIREMENTS:
- Generate between {min_tasks} and {max_tasks} tasks
- Organize tasks into logical phases
- Include all necessary infrastructure, testing, and deployment tasks
- Each task should be completable by an AI coding agent in 1-4 hours
- Include verification criteria that can be automatically checked
- Mark architecture decisions that need human approval
"""

        if context:
            if context.get("tech_stack"):
                prompt += f"\nPREFERRED TECH STACK: {json.dumps(context['tech_stack'])}"
            if context.get("existing_files"):
                prompt += f"\nEXISTING FILES: {context['existing_files']}"
            if context.get("constraints"):
                prompt += f"\nCONSTRAINTS: {context['constraints']}"

        prompt += """

Respond with a valid JSON object matching the schema described in the system prompt.
Include realistic task IDs (t001, t002, etc.) and proper dependencies between tasks.
"""

        return prompt

    def _parse_decomposition_response(self, response: str) -> DecompositionResult:
        """Parse the LLM response into a DecompositionResult"""

        # Extract JSON from response (may be wrapped in markdown)
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
            else:
                raise ValueError("Could not find JSON in LLM response")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response: {response[:500]}...")
            raise ValueError(f"Invalid JSON in LLM response: {e}")

        # Convert to DecomposedTask objects
        tasks = []
        for task_data in data.get("tasks", []):
            task = DecomposedTask(
                id=task_data.get("id", f"t{len(tasks):03d}"),
                title=task_data.get("title", "Untitled Task"),
                description=task_data.get("description", ""),
                phase=task_data.get("phase", "general"),
                priority=task_data.get("priority", 50),
                dependencies=task_data.get("dependencies", []),
                can_parallelize=task_data.get("can_parallelize", False),
                estimated_complexity=task_data.get("estimated_complexity", "medium"),
                verification_criteria=task_data.get("verification_criteria", []),
                tags=task_data.get("tags", []),
                outputs=task_data.get("outputs", {}),
            )
            tasks.append(task)

        return DecompositionResult(
            project_name=data.get("project_name", "Enterprise Project"),
            project_type=data.get("project_type", "custom"),
            phases=data.get("phases", ["general"]),
            tasks=tasks,
            milestones=data.get("milestones", []),
            architecture_decisions=data.get("architecture_decisions", []),
            estimated_total_hours=data.get("estimated_total_hours", len(tasks) * 2),
            tech_stack=data.get("tech_stack", {}),
        )

    async def decompose_for_enterprise_project(
        self,
        project_id: str,
        goal: str,
        db_session,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, List[str]]:
        """
        Decompose a goal and save tasks to EnterpriseProject.

        Args:
            project_id: The EnterpriseProject ID
            goal: The project goal to decompose
            db_session: Database session
            context: Optional context

        Returns:
            Tuple of (task_count, task_ids)
        """
        from backend.services.enterprise_project_service import EnterpriseProjectService

        # Decompose the goal
        result = await self.decompose_goal(goal, context)

        # Save tasks to database
        service = EnterpriseProjectService(db_session)

        task_ids = []
        for task in result.tasks:
            saved_task = await service.add_task(
                project_id=project_id,
                task_id=task.id,
                title=task.title,
                description=task.description,
                priority=task.priority,
                dependencies=task.dependencies,
                can_parallelize=task.can_parallelize,
                verification_criteria=task.verification_criteria,
                outputs=task.outputs,
            )
            task_ids.append(str(saved_task.id))

        # Save milestones to project
        project = await service.get_project(project_id)
        if project:
            project.milestones = result.milestones
            project.architecture_decisions = result.architecture_decisions
            db_session.commit()

        logger.info(f"Saved {len(task_ids)} tasks to project {project_id}")

        return len(task_ids), task_ids


# E-commerce specific decomposition template
ECOMMERCE_TEMPLATE = {
    "phases": [
        {
            "name": "setup",
            "title": "Project Setup",
            "tasks_template": [
                "Initialize frontend project (Next.js/React)",
                "Initialize backend project (FastAPI/Django)",
                "Set up database (PostgreSQL)",
                "Configure development environment",
                "Set up version control and CI/CD",
            ],
        },
        {
            "name": "database",
            "title": "Database Design",
            "tasks_template": [
                "Design user schema",
                "Design product schema",
                "Design order schema",
                "Design cart schema",
                "Design payment schema",
                "Create database migrations",
                "Set up database indexes",
                "Configure connection pooling",
            ],
        },
        {
            "name": "auth",
            "title": "Authentication & Authorization",
            "tasks_template": [
                "Implement user registration",
                "Implement email verification",
                "Implement login/logout",
                "Implement password reset",
                "Implement JWT token handling",
                "Implement OAuth2 (Google, GitHub)",
                "Implement role-based access control",
                "Implement session management",
            ],
        },
        {
            "name": "catalog",
            "title": "Product Catalog",
            "tasks_template": [
                "Create product listing API",
                "Create product detail API",
                "Implement product search",
                "Implement category management",
                "Implement product filtering",
                "Implement product sorting",
                "Create product image upload",
                "Implement inventory tracking",
                "Create product listing UI",
                "Create product detail UI",
            ],
        },
        {
            "name": "cart",
            "title": "Shopping Cart",
            "tasks_template": [
                "Implement cart API (add, remove, update)",
                "Implement cart persistence",
                "Create cart UI component",
                "Implement quantity validation",
                "Implement price calculation",
                "Implement discount codes",
            ],
        },
        {
            "name": "checkout",
            "title": "Checkout & Payments",
            "tasks_template": [
                "Create checkout flow UI",
                "Implement address management",
                "Integrate Stripe payment",
                "Implement order creation",
                "Implement payment webhooks",
                "Implement order confirmation emails",
                "Implement refund handling",
            ],
        },
        {
            "name": "admin",
            "title": "Admin Dashboard",
            "tasks_template": [
                "Create admin authentication",
                "Create product management UI",
                "Create order management UI",
                "Create user management UI",
                "Create analytics dashboard",
                "Create inventory management",
                "Create discount code management",
            ],
        },
        {
            "name": "testing",
            "title": "Testing",
            "tasks_template": [
                "Set up testing framework",
                "Write unit tests for auth",
                "Write unit tests for products",
                "Write unit tests for cart",
                "Write unit tests for checkout",
                "Write integration tests",
                "Write E2E tests",
                "Set up test coverage reporting",
            ],
        },
        {
            "name": "deployment",
            "title": "Deployment",
            "tasks_template": [
                "Create Docker configuration",
                "Set up Kubernetes manifests",
                "Configure load balancer",
                "Set up CDN for static assets",
                "Configure auto-scaling",
                "Set up monitoring (Prometheus/Grafana)",
                "Set up logging (ELK stack)",
                "Configure SSL/TLS",
                "Set up backup strategy",
            ],
        },
    ],
}


async def quick_decompose(
    goal: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
) -> DecompositionResult:
    """
    Quick function to decompose a goal.

    Args:
        goal: The project goal
        provider: LLM provider
        api_key: Optional BYOK key

    Returns:
        DecompositionResult
    """
    decomposer = TaskDecomposer(provider=provider, api_key=api_key)
    return await decomposer.decompose_goal(goal)
