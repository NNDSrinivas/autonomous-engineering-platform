"""
NAVI Planner - World-Class Pair Programming Experience

This module provides:
1. Plan Mode - Structured planning before execution
2. Clarifying Questions - Senior engineer level questions
3. Vision/Image Support - UI screenshot analysis
4. Full Codebase Understanding - Context-aware planning
5. End-to-End Feature Creation - Complete implementation workflow
6. Refactoring Suggestions - Code quality analysis and improvement suggestions
7. Auto-Commit - Automatic git commits after feature completion

The vision: "I always start in plan mode, I'll drag UI screenshots,
describe the main features and NAVI starts asking clarifying questions,
the kind a senior engineer would ask. Then it creates a full, structured plan."
"""

import os
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS & DATA CLASSES
# ============================================================


class PlanStatus(Enum):
    DRAFT = "draft"  # Plan being created
    QUESTIONS = "questions"  # Waiting for clarifying answers
    READY = "ready"  # Plan ready for approval
    APPROVED = "approved"  # User approved, ready to execute
    IN_PROGRESS = "in_progress"  # Executing
    COMPLETED = "completed"  # All tasks done
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # User cancelled


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QuestionCategory(Enum):
    ARCHITECTURE = "architecture"  # System design decisions
    REQUIREMENTS = "requirements"  # Feature requirements
    TECHNOLOGY = "technology"  # Tech stack choices
    SCOPE = "scope"  # What's in/out of scope
    INTEGRATION = "integration"  # External integrations
    SECURITY = "security"  # Auth, encryption, etc.
    PERFORMANCE = "performance"  # Scale, caching, etc.
    TESTING = "testing"  # Test strategy
    DEPLOYMENT = "deployment"  # Deploy target
    REFACTORING = "refactoring"  # Code quality improvements
    COMMIT = "commit"  # Git commit preferences


@dataclass
class ClarifyingQuestion:
    """A senior-engineer-level clarifying question"""

    id: str
    category: QuestionCategory
    question: str
    why_asking: str  # Explain why this matters
    options: List[str]  # Suggested answers
    default: Optional[str] = None
    answer: Optional[str] = None
    answered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "question": self.question,
            "why_asking": self.why_asking,
            "options": self.options,
            "default": self.default,
            "answer": self.answer,
            "answered": self.answered,
        }


@dataclass
class PlanTask:
    """A single task in the execution plan"""

    id: str
    title: str
    description: str
    task_type: str  # file_create, file_edit, command, test, etc.
    files: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "files": self.files,
            "commands": self.commands,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ImageAttachment:
    """UI screenshot or design image"""

    id: str
    filename: str
    mime_type: str
    base64_data: str
    description: Optional[str] = None
    analysis: Optional[str] = None  # Vision model analysis


@dataclass
class ExecutionPlan:
    """A complete structured plan for implementation"""

    id: str
    title: str
    summary: str
    status: PlanStatus = PlanStatus.DRAFT

    # User's original request
    original_request: str = ""
    images: List[ImageAttachment] = field(default_factory=list)

    # Clarifying questions
    questions: List[ClarifyingQuestion] = field(default_factory=list)

    # The plan itself
    tasks: List[PlanTask] = field(default_factory=list)

    # Codebase context
    workspace_path: Optional[str] = None
    project_type: Optional[str] = None
    detected_technologies: List[str] = field(default_factory=list)
    relevant_files: List[str] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    current_task_index: int = 0

    # Estimates
    estimated_files: int = 0
    estimated_lines: int = 0
    risk_level: str = "low"  # low, medium, high

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "status": self.status.value,
            "original_request": self.original_request,
            "images": [
                {"id": img.id, "filename": img.filename, "description": img.description}
                for img in self.images
            ],
            "questions": [q.to_dict() for q in self.questions],
            "tasks": [t.to_dict() for t in self.tasks],
            "workspace_path": self.workspace_path,
            "project_type": self.project_type,
            "detected_technologies": self.detected_technologies,
            "relevant_files": self.relevant_files,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_task_index": self.current_task_index,
            "estimated_files": self.estimated_files,
            "estimated_lines": self.estimated_lines,
            "risk_level": self.risk_level,
            "unanswered_questions": len([q for q in self.questions if not q.answered]),
            "completed_tasks": len(
                [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
            ),
            "total_tasks": len(self.tasks),
        }


# ============================================================
# PLAN STORAGE (In-memory for now, can be upgraded to DB)
# ============================================================

_plan_storage: Dict[str, ExecutionPlan] = {}


def store_plan(plan: ExecutionPlan) -> None:
    """Store a plan"""
    plan.updated_at = datetime.utcnow().isoformat()
    _plan_storage[plan.id] = plan


def get_plan(plan_id: str) -> Optional[ExecutionPlan]:
    """Retrieve a plan by ID"""
    return _plan_storage.get(plan_id)


def list_plans(workspace_path: Optional[str] = None) -> List[ExecutionPlan]:
    """List all plans, optionally filtered by workspace"""
    plans = list(_plan_storage.values())
    if workspace_path:
        plans = [p for p in plans if p.workspace_path == workspace_path]
    return sorted(plans, key=lambda p: p.created_at, reverse=True)


# ============================================================
# SENIOR ENGINEER CLARIFYING QUESTIONS
# ============================================================


class ClarifyingQuestionGenerator:
    """
    Generates senior-engineer-level clarifying questions based on
    the request context and detected intent.
    """

    # Question templates by category
    QUESTION_TEMPLATES = {
        QuestionCategory.ARCHITECTURE: [
            {
                "trigger": ["api", "endpoint", "backend", "server"],
                "question": "What's your preferred API architecture?",
                "why": "This affects code organization, middleware patterns, and how clients interact with your service.",
                "options": [
                    "REST with resource-based URLs",
                    "GraphQL for flexible queries",
                    "gRPC for high performance",
                    "Mix of REST + WebSockets for real-time",
                ],
            },
            {
                "trigger": ["database", "data", "store", "persist"],
                "question": "What database strategy works best for your use case?",
                "why": "Database choice impacts query patterns, scaling strategy, and data modeling approach.",
                "options": [
                    "PostgreSQL (relational, ACID)",
                    "MongoDB (document, flexible schema)",
                    "Redis (caching + sessions)",
                    "Keep existing database",
                ],
            },
            {
                "trigger": ["auth", "login", "user", "account"],
                "question": "How should users authenticate?",
                "why": "Auth strategy affects security, user experience, and integration complexity.",
                "options": [
                    "JWT tokens (stateless)",
                    "Session-based (server state)",
                    "OAuth2 with social login",
                    "Magic link / passwordless",
                ],
            },
        ],
        QuestionCategory.SCOPE: [
            {
                "trigger": ["feature", "build", "create", "implement", "add"],
                "question": "What's the MVP scope for this feature?",
                "why": "Starting with a focused MVP lets us ship faster and iterate based on real feedback.",
                "options": [
                    "Core functionality only (ship fast)",
                    "Include edge cases (more robust)",
                    "Full feature with tests (production-ready)",
                    "Prototype to validate approach",
                ],
            },
            {
                "trigger": ["refactor", "improve", "optimize", "clean"],
                "question": "How extensive should the refactoring be?",
                "why": "Scoping prevents scope creep and helps maintain a working codebase throughout.",
                "options": [
                    "Minimal changes (fix the immediate issue)",
                    "Moderate (improve touched files)",
                    "Comprehensive (full module refactor)",
                    "Just add tests first",
                ],
            },
        ],
        QuestionCategory.TECHNOLOGY: [
            {
                "trigger": ["ui", "frontend", "component", "page", "screen"],
                "question": "What UI framework conventions should I follow?",
                "why": "Consistent patterns make the codebase maintainable and code review easier.",
                "options": [
                    "Follow existing project patterns",
                    "Use functional components with hooks",
                    "Add TypeScript if not present",
                    "Include Storybook stories",
                ],
            },
            {
                "trigger": ["test", "testing", "spec"],
                "question": "What testing approach do you prefer?",
                "why": "Testing strategy affects confidence in deployments and refactoring safety.",
                "options": [
                    "Unit tests for business logic",
                    "Integration tests for API",
                    "E2E tests for critical paths",
                    "All of the above",
                ],
            },
        ],
        QuestionCategory.INTEGRATION: [
            {
                "trigger": ["api", "external", "third-party", "service", "webhook"],
                "question": "How should we handle external API failures?",
                "why": "Resilient integrations prevent cascading failures when third-party services have issues.",
                "options": [
                    "Retry with exponential backoff",
                    "Circuit breaker pattern",
                    "Fallback to cached data",
                    "Fail fast with clear error",
                ],
            },
        ],
        QuestionCategory.PERFORMANCE: [
            {
                "trigger": ["list", "table", "fetch", "load", "query"],
                "question": "What's the expected data volume?",
                "why": "Scale expectations inform pagination, caching, and query optimization strategies.",
                "options": [
                    "Small (< 1K records)",
                    "Medium (1K - 100K records)",
                    "Large (100K+ records, needs pagination)",
                    "Unknown (let's add pagination just in case)",
                ],
            },
        ],
        QuestionCategory.SECURITY: [
            {
                "trigger": ["admin", "role", "permission", "access"],
                "question": "What authorization model do you need?",
                "why": "Access control complexity varies significantly based on your permission requirements.",
                "options": [
                    "Simple roles (admin/user)",
                    "Role-based (RBAC)",
                    "Attribute-based (ABAC)",
                    "Resource-level permissions",
                ],
            },
        ],
        QuestionCategory.REFACTORING: [
            {
                "trigger": ["build", "create", "implement", "add", "feature", "new"],
                "question": "Should I also review and improve existing related code?",
                "why": "While implementing new features, I can identify and fix code quality issues in touched areas.",
                "options": [
                    "Yes, suggest improvements inline",
                    "Yes, but as a separate task",
                    "No, just implement the feature",
                    "Let me decide after seeing the plan",
                ],
            },
            {
                "trigger": ["refactor", "clean", "optimize", "improve", "fix"],
                "question": "What level of code quality improvements should I apply?",
                "why": "Code quality improvements range from simple cleanups to major restructuring.",
                "options": [
                    "Lint fixes and formatting only",
                    "Add types and better error handling",
                    "Extract reusable functions and improve patterns",
                    "Full refactor with tests",
                ],
            },
        ],
        QuestionCategory.COMMIT: [
            {
                "trigger": [
                    "feature",
                    "build",
                    "create",
                    "implement",
                    "add",
                    "fix",
                    "update",
                ],
                "question": "How would you like me to handle git commits?",
                "why": "Automatic commits help maintain a clean git history and make it easy to track changes.",
                "options": [
                    "Auto-commit after each task with descriptive messages",
                    "Single commit at the end with summary",
                    "Don't commit, I'll handle it manually",
                    "Suggest commit points but let me confirm",
                ],
            },
            {
                "trigger": ["commit", "git", "push"],
                "question": "What commit message style do you prefer?",
                "why": "Consistent commit messages improve project history readability.",
                "options": [
                    "Conventional commits (feat:, fix:, etc.)",
                    "Brief and descriptive",
                    "Detailed with context",
                    "Follow existing project style",
                ],
            },
        ],
    }

    @classmethod
    def generate_questions(
        cls,
        request: str,
        project_type: Optional[str] = None,
        detected_technologies: Optional[List[str]] = None,
        existing_questions: Optional[List[str]] = None,
    ) -> List[ClarifyingQuestion]:
        """
        Generate relevant clarifying questions based on the request.
        """
        questions = []
        request_lower = request.lower()
        existing = set(existing_questions or [])

        for category, templates in cls.QUESTION_TEMPLATES.items():
            for template in templates:
                # Check if any trigger words are in the request
                if any(trigger in request_lower for trigger in template["trigger"]):
                    # Don't ask duplicate questions
                    if template["question"] not in existing:
                        questions.append(
                            ClarifyingQuestion(
                                id=str(uuid.uuid4())[:8],
                                category=category,
                                question=template["question"],
                                why_asking=template["why"],
                                options=template["options"],
                                default=(
                                    template["options"][0]
                                    if template["options"]
                                    else None
                                ),
                            )
                        )

        # Limit to most relevant 3-5 questions
        return questions[:5]

    @classmethod
    def generate_ui_questions(cls, image_analysis: str) -> List[ClarifyingQuestion]:
        """Generate questions specifically for UI implementation from screenshots"""
        questions = []

        # Always ask about component structure for UI work
        questions.append(
            ClarifyingQuestion(
                id=str(uuid.uuid4())[:8],
                category=QuestionCategory.ARCHITECTURE,
                question="How should this UI be structured?",
                why_asking="Component organization affects reusability and maintainability.",
                options=[
                    "Single page component",
                    "Split into reusable components",
                    "Create a full component library",
                    "Match existing component patterns",
                ],
            )
        )

        # State management question
        questions.append(
            ClarifyingQuestion(
                id=str(uuid.uuid4())[:8],
                category=QuestionCategory.TECHNOLOGY,
                question="How should we handle state for this UI?",
                why_asking="State management approach depends on complexity and data flow needs.",
                options=[
                    "Local component state (useState)",
                    "Context for shared state",
                    "Global store (Redux/Zustand)",
                    "Server state (React Query/SWR)",
                ],
            )
        )

        # Responsiveness
        questions.append(
            ClarifyingQuestion(
                id=str(uuid.uuid4())[:8],
                category=QuestionCategory.REQUIREMENTS,
                question="What responsive behavior is needed?",
                why_asking="Mobile-first approach requires different layout strategies.",
                options=[
                    "Desktop only",
                    "Responsive (desktop + mobile)",
                    "Mobile-first design",
                    "Match existing breakpoints",
                ],
            )
        )

        return questions


# ============================================================
# VISION / IMAGE ANALYSIS
# ============================================================


class VisionAnalyzer:
    """
    Analyzes UI screenshots and design images using vision-capable LLMs.
    Supports: Claude 3.5 Sonnet, GPT-4 Vision, Gemini Pro Vision
    """

    @staticmethod
    def is_image_attachment(attachment: Dict[str, Any]) -> bool:
        """Check if an attachment is an image"""
        mime_type = attachment.get("mime_type", attachment.get("type", ""))
        return mime_type.startswith("image/") or attachment.get("kind") == "image"

    @staticmethod
    def extract_image_data(attachment: Dict[str, Any]) -> Optional[ImageAttachment]:
        """Extract image data from an attachment"""
        try:
            # Handle different attachment formats
            data = (
                attachment.get("data")
                or attachment.get("content")
                or attachment.get("base64")
            )
            if not data:
                return None

            # Remove data URL prefix if present
            if "base64," in data:
                data = data.split("base64,")[1]

            return ImageAttachment(
                id=str(uuid.uuid4())[:8],
                filename=attachment.get(
                    "filename", attachment.get("name", "image.png")
                ),
                mime_type=attachment.get(
                    "mime_type", attachment.get("type", "image/png")
                ),
                base64_data=data,
                description=attachment.get("description"),
            )
        except Exception as e:
            logger.error(f"Failed to extract image data: {e}")
            return None

    @staticmethod
    async def analyze_ui_screenshot(
        image: ImageAttachment,
        llm_client: Any,
        additional_context: str = "",
    ) -> str:
        """
        Analyze a UI screenshot and describe it for code generation.
        Returns a detailed description of the UI elements, layout, and interactions.
        """
        try:
            # Build the vision prompt
            prompt = """Analyze this UI screenshot/mockup and provide a detailed description for implementing it in code.

Please describe:
1. **Layout Structure**: Overall layout pattern (grid, flex, sidebar, etc.)
2. **Components**: List each visible component (buttons, forms, cards, tables, etc.)
3. **Styling**: Colors, typography, spacing, visual hierarchy
4. **Interactions**: Apparent interactive elements and their likely behaviors
5. **Data Requirements**: What data structures would be needed
6. **Accessibility**: Any a11y considerations visible

Be specific enough that a developer could implement this UI from your description."""

            if additional_context:
                prompt += f"\n\nAdditional context: {additional_context}"

            # Call vision model (implementation depends on provider)
            # This is a placeholder - actual implementation would use the LLM client
            analysis = """
UI Screenshot Analysis:

**Layout**: The screenshot shows a modern dashboard interface with a sidebar navigation on the left and main content area on the right.

**Components Identified**:
- Header with logo and user profile dropdown
- Sidebar with navigation items (icons + labels)
- Main content area with:
  - Page title and breadcrumbs
  - Summary cards/stats at the top
  - Data table or list below
  - Action buttons (primary CTA visible)

**Styling Notes**:
- Clean, minimal design with good whitespace
- Likely using a modern design system (Material, Tailwind, etc.)
- Primary accent color for CTAs
- Neutral grays for secondary elements

**Implementation Suggestions**:
- Use CSS Grid for main layout (sidebar + content)
- Flexbox for component alignment
- Consider component library compatibility
- Add responsive breakpoints for mobile

**Data Structures Needed**:
- User object for profile
- Navigation items array
- Summary statistics object
- Table data with pagination
"""

            image.analysis = analysis
            return analysis

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"Unable to analyze image: {str(e)}"


# ============================================================
# PLAN GENERATOR
# ============================================================


class PlanGenerator:
    """
    Generates structured execution plans from user requests.
    Incorporates clarifying questions, codebase analysis, and task breakdown.
    """

    @classmethod
    async def create_plan(
        cls,
        request: str,
        workspace_path: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        llm_client: Any = None,
    ) -> ExecutionPlan:
        """
        Create a new execution plan from a user request.

        This implements the workflow:
        1. Analyze images if present
        2. Understand codebase context
        3. Generate clarifying questions
        4. Create structured plan (once questions answered)
        """
        plan_id = str(uuid.uuid4())[:12]

        # Initialize plan
        plan = ExecutionPlan(
            id=plan_id,
            title="",  # Will be set after analysis
            summary="",
            original_request=request,
            workspace_path=workspace_path,
        )

        # Process images if present
        images = []
        if attachments:
            for att in attachments:
                if VisionAnalyzer.is_image_attachment(att):
                    img = VisionAnalyzer.extract_image_data(att)
                    if img:
                        # Analyze the image
                        if llm_client:
                            await VisionAnalyzer.analyze_ui_screenshot(img, llm_client)
                        images.append(img)

        plan.images = images

        # Analyze workspace
        plan = await cls._analyze_workspace(plan, workspace_path, context)

        # Generate clarifying questions
        image_context = "\n".join([img.analysis or "" for img in images])
        questions = ClarifyingQuestionGenerator.generate_questions(
            request=request + "\n" + image_context,
            project_type=plan.project_type,
            detected_technologies=plan.detected_technologies,
        )

        # Add UI-specific questions if images present
        if images:
            questions.extend(
                ClarifyingQuestionGenerator.generate_ui_questions(image_context)
            )

        plan.questions = questions[:5]  # Limit to 5 questions max

        # Set initial title and summary
        plan.title = cls._generate_title(request, images)
        plan.summary = cls._generate_summary(request, images, plan.project_type)

        # Set status based on whether we have questions
        if plan.questions:
            plan.status = PlanStatus.QUESTIONS
        else:
            plan.status = PlanStatus.READY
            # Generate tasks immediately if no questions needed
            plan = await cls._generate_tasks(plan, llm_client)

        # Store and return
        store_plan(plan)
        return plan

    @classmethod
    async def _analyze_workspace(
        cls,
        plan: ExecutionPlan,
        workspace_path: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Analyze the workspace to understand project context"""
        try:
            # Import project analyzer
            from backend.services.navi_brain import ProjectAnalyzer

            # Analyze the project
            project_info = ProjectAnalyzer.analyze_project(workspace_path)

            if project_info:
                plan.project_type = project_info.project_type
                plan.detected_technologies = [
                    project_info.language,
                    project_info.framework or "",
                    project_info.package_manager or "",
                ]
                plan.detected_technologies = [
                    t for t in plan.detected_technologies if t
                ]

                # Get relevant files
                plan.relevant_files = (
                    list(project_info.dependencies.keys())[:20]
                    if project_info.dependencies
                    else []
                )
        except Exception as e:
            logger.error(f"Workspace analysis failed: {e}")

        return plan

    @classmethod
    def _generate_title(cls, request: str, images: List[ImageAttachment]) -> str:
        """Generate a concise title for the plan"""
        # Simple heuristic - first 50 chars of request
        title = request[:50].strip()
        if len(request) > 50:
            title += "..."
        if images:
            title = f"[UI Implementation] {title}"
        return title

    @classmethod
    def _generate_summary(
        cls,
        request: str,
        images: List[ImageAttachment],
        project_type: Optional[str],
    ) -> str:
        """Generate a summary of what the plan will accomplish"""
        summary_parts = [f"**Request**: {request[:200]}"]

        if images:
            summary_parts.append(
                f"**UI References**: {len(images)} screenshot(s) provided"
            )

        if project_type:
            summary_parts.append(f"**Project Type**: {project_type}")

        return "\n".join(summary_parts)

    @classmethod
    async def answer_questions(
        cls,
        plan_id: str,
        answers: Dict[str, str],
        llm_client: Any = None,
    ) -> ExecutionPlan:
        """
        Process answers to clarifying questions and generate the task plan.
        """
        plan = get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Apply answers
        for question in plan.questions:
            if question.id in answers:
                question.answer = answers[question.id]
                question.answered = True

        # Check if all questions answered
        unanswered = [q for q in plan.questions if not q.answered]

        if unanswered:
            plan.status = PlanStatus.QUESTIONS
        else:
            plan.status = PlanStatus.READY
            # Generate tasks now that we have all answers
            plan = await cls._generate_tasks(plan, llm_client)

        store_plan(plan)
        return plan

    @classmethod
    async def _generate_tasks(
        cls, plan: ExecutionPlan, llm_client: Any = None
    ) -> ExecutionPlan:
        """
        Generate the detailed task breakdown for execution.
        This is where the magic happens - turning requirements into actionable tasks.
        """
        tasks = []

        # Build context from questions and answers
        context_parts = [plan.original_request]
        for q in plan.questions:
            if q.answered:
                context_parts.append(f"- {q.question}: {q.answer}")

        # Add image analysis
        for img in plan.images:
            if img.analysis:
                context_parts.append(f"UI Analysis:\n{img.analysis}")

        # Create task breakdown (this would ideally use LLM for complex cases)
        # For now, use heuristic breakdown

        # Task 1: Setup/scaffolding (if needed)
        if (
            "create" in plan.original_request.lower()
            or "new" in plan.original_request.lower()
        ):
            tasks.append(
                PlanTask(
                    id=f"task-{len(tasks) + 1}",
                    title="Set up project structure",
                    description="Create necessary directories and configuration files",
                    task_type="setup",
                    files=[],
                )
            )

        # Task 2: Core implementation
        tasks.append(
            PlanTask(
                id=f"task-{len(tasks) + 1}",
                title="Implement core functionality",
                description="Create the main implementation files",
                task_type="implementation",
                files=[],
                dependencies=[t.id for t in tasks[-1:]] if tasks else [],
            )
        )

        # Task 3: UI components (if UI work)
        if plan.images:
            tasks.append(
                PlanTask(
                    id=f"task-{len(tasks) + 1}",
                    title="Create UI components",
                    description="Implement the UI based on provided screenshots",
                    task_type="ui",
                    files=[],
                    dependencies=[tasks[-1].id] if tasks else [],
                )
            )

        # Task 4: Integration/wiring
        tasks.append(
            PlanTask(
                id=f"task-{len(tasks) + 1}",
                title="Wire up integration",
                description="Connect components and ensure proper data flow",
                task_type="integration",
                dependencies=[t.id for t in tasks],
            )
        )

        # Task 5: Tests
        tasks.append(
            PlanTask(
                id=f"task-{len(tasks) + 1}",
                title="Add tests",
                description="Write unit and integration tests",
                task_type="testing",
                dependencies=[tasks[-1].id],
            )
        )

        # Task 6: Documentation
        tasks.append(
            PlanTask(
                id=f"task-{len(tasks) + 1}",
                title="Update documentation",
                description="Add/update relevant documentation",
                task_type="documentation",
                dependencies=[tasks[-2].id],
            )
        )

        # Task 7: Code Review & Refactoring (conditional based on user answer)
        should_refactor = cls._should_add_refactoring_task(plan.questions)
        if should_refactor:
            tasks.append(
                PlanTask(
                    id=f"task-{len(tasks) + 1}",
                    title="Review and improve code quality",
                    description="Run code validation, suggest improvements, and apply refactoring",
                    task_type="refactoring",
                    dependencies=[tasks[-1].id],
                )
            )

        # Task 8: Git Commit (conditional based on user answer)
        commit_strategy = cls._get_commit_strategy(plan.questions)
        if commit_strategy and commit_strategy != "manual":
            tasks.append(
                PlanTask(
                    id=f"task-{len(tasks) + 1}",
                    title="Commit changes to git",
                    description=f"Stage and commit all changes ({commit_strategy})",
                    task_type="commit",
                    dependencies=[tasks[-1].id],
                )
            )

        plan.tasks = tasks
        plan.estimated_files = len(tasks) * 2  # Rough estimate
        plan.estimated_lines = plan.estimated_files * 100  # Rough estimate

        return plan

    @classmethod
    def _should_add_refactoring_task(cls, questions: List[ClarifyingQuestion]) -> bool:
        """Check if user wants refactoring suggestions based on their answers."""
        for q in questions:
            if q.category == QuestionCategory.REFACTORING and q.answered:
                answer = (q.answer or "").lower()
                # Add refactoring task unless user explicitly said no
                if "no" not in answer and "just implement" not in answer:
                    return True
        # Default: add refactoring for any significant feature work
        return False

    @classmethod
    def _get_commit_strategy(cls, questions: List[ClarifyingQuestion]) -> Optional[str]:
        """Get the user's preferred commit strategy from their answers."""
        for q in questions:
            if q.category == QuestionCategory.COMMIT and q.answered:
                answer = (q.answer or "").lower()
                if "auto-commit" in answer or "after each" in answer:
                    return "auto_per_task"
                elif "single commit" in answer or "at the end" in answer:
                    return "single_at_end"
                elif "suggest" in answer or "confirm" in answer:
                    return "suggest_and_confirm"
                elif "manual" in answer or "don't commit" in answer:
                    return "manual"
        # Default: suggest commit at end
        return "single_at_end"

    @classmethod
    async def approve_plan(cls, plan_id: str) -> ExecutionPlan:
        """Mark a plan as approved and ready for execution"""
        plan = get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if plan.status != PlanStatus.READY:
            raise ValueError(
                f"Plan is not ready for approval (status: {plan.status.value})"
            )

        plan.status = PlanStatus.APPROVED
        store_plan(plan)
        return plan


# ============================================================
# PLAN EXECUTOR
# ============================================================


class PlanExecutor:
    """
    Executes approved plans task by task.
    Provides streaming updates and handles failures gracefully.
    """

    @classmethod
    async def execute_plan(
        cls,
        plan_id: str,
        llm_client: Any = None,
        on_progress: Optional[callable] = None,
    ) -> ExecutionPlan:
        """
        Execute all tasks in an approved plan.
        """
        plan = get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if plan.status not in [PlanStatus.APPROVED, PlanStatus.IN_PROGRESS]:
            raise ValueError(f"Plan cannot be executed (status: {plan.status.value})")

        plan.status = PlanStatus.IN_PROGRESS
        store_plan(plan)

        try:
            # Execute each task in order
            for i, task in enumerate(plan.tasks):
                # Skip completed or skipped tasks
                if task.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                    continue

                # Check dependencies
                deps_met = all(
                    plan.tasks[j].status == TaskStatus.COMPLETED
                    for j, t in enumerate(plan.tasks)
                    if t.id in task.dependencies
                )

                if not deps_met:
                    task.status = TaskStatus.SKIPPED
                    task.error = "Dependencies not met"
                    continue

                # Execute task
                task.status = TaskStatus.IN_PROGRESS
                plan.current_task_index = i
                store_plan(plan)

                if on_progress:
                    await on_progress(
                        {
                            "type": "task_start",
                            "task_id": task.id,
                            "task_title": task.title,
                            "progress": i / len(plan.tasks),
                        }
                    )

                try:
                    result = await cls._execute_task(task, plan, llm_client)
                    task.status = TaskStatus.COMPLETED
                    task.result = result

                    if on_progress:
                        await on_progress(
                            {
                                "type": "task_complete",
                                "task_id": task.id,
                                "result": result,
                            }
                        )

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)

                    if on_progress:
                        await on_progress(
                            {
                                "type": "task_failed",
                                "task_id": task.id,
                                "error": str(e),
                            }
                        )

                    # Continue to next task on failure (resilient execution)

                store_plan(plan)

            # Check final status
            failed_tasks = [t for t in plan.tasks if t.status == TaskStatus.FAILED]
            if failed_tasks:
                plan.status = PlanStatus.FAILED
            else:
                plan.status = PlanStatus.COMPLETED

        except Exception as e:
            plan.status = PlanStatus.FAILED
            logger.error(f"Plan execution failed: {e}")

        store_plan(plan)
        return plan

    @classmethod
    async def _execute_task(
        cls,
        task: PlanTask,
        plan: ExecutionPlan,
        llm_client: Any,
    ) -> Dict[str, Any]:
        """Execute a single task and return results"""
        result = {
            "task_id": task.id,
            "task_type": task.task_type,
            "files_created": [],
            "files_modified": [],
            "commands_run": [],
        }

        # Handle different task types
        if task.task_type == "refactoring":
            result = await cls._execute_refactoring_task(task, plan)
        elif task.task_type == "commit":
            result = await cls._execute_commit_task(task, plan)
        else:
            # Default: placeholder for other task types (implementation, ui, etc.)
            # These would typically call navi_brain or other services
            await asyncio.sleep(0.1)  # Simulate work

        return result

    @classmethod
    async def _execute_refactoring_task(
        cls,
        task: PlanTask,
        plan: ExecutionPlan,
    ) -> Dict[str, Any]:
        """
        Execute code review and refactoring task.
        Uses CodeValidator to analyze code quality and suggest improvements.
        """
        result = {
            "task_id": task.id,
            "task_type": "refactoring",
            "files_analyzed": [],
            "issues_found": [],
            "improvements_applied": [],
            "suggestions": [],
        }

        try:
            from backend.services.code_validator import CodeValidator

            validator = CodeValidator()

            # Get all files created/modified in previous tasks
            files_to_analyze = []
            for t in plan.tasks:
                if t.status == TaskStatus.COMPLETED and t.result:
                    files_to_analyze.extend(t.result.get("files_created", []))
                    files_to_analyze.extend(t.result.get("files_modified", []))

            # Also check the plan's workspace for relevant files
            if plan.workspace_path and plan.relevant_files:
                for f in plan.relevant_files[:10]:  # Limit to avoid too much analysis
                    full_path = os.path.join(plan.workspace_path, f)
                    if os.path.exists(full_path) and full_path not in files_to_analyze:
                        files_to_analyze.append(full_path)

            # Analyze each file
            for file_path in files_to_analyze[:20]:  # Limit files
                if not os.path.exists(file_path):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    validation_result = validator.validate(content, file_path)
                    result["files_analyzed"].append(file_path)

                    if validation_result.issues:
                        for issue in validation_result.issues:
                            result["issues_found"].append(
                                {
                                    "file": file_path,
                                    "level": issue.level.value,
                                    "message": issue.message,
                                    "line": issue.line,
                                    "rule": issue.rule,
                                    "fix_suggestion": issue.fix_suggestion,
                                }
                            )

                            # Add to suggestions if it has a fix
                            if issue.fix_suggestion:
                                result["suggestions"].append(
                                    {
                                        "file": file_path,
                                        "issue": issue.message,
                                        "suggestion": issue.fix_suggestion,
                                    }
                                )

                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")

            # Summary
            result["summary"] = {
                "files_analyzed": len(result["files_analyzed"]),
                "total_issues": len(result["issues_found"]),
                "errors": len(
                    [i for i in result["issues_found"] if i["level"] == "error"]
                ),
                "warnings": len(
                    [i for i in result["issues_found"] if i["level"] == "warning"]
                ),
                "suggestions_count": len(result["suggestions"]),
            }

        except ImportError:
            result["error"] = "CodeValidator not available"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Refactoring task failed: {e}")

        return result

    @classmethod
    async def _execute_commit_task(
        cls,
        task: PlanTask,
        plan: ExecutionPlan,
    ) -> Dict[str, Any]:
        """
        Execute git commit task.
        Stages and commits all changes with a descriptive message.
        """
        result = {
            "task_id": task.id,
            "task_type": "commit",
            "committed": False,
            "commit_hash": None,
            "files_committed": [],
            "commit_message": None,
        }

        if not plan.workspace_path:
            result["error"] = "No workspace path specified"
            return result

        try:
            from backend.services.git_service import GitService

            git = GitService(plan.workspace_path)

            # Get list of changed files
            status_result = git.execute_safe_command(["git", "status", "--porcelain"])
            if not status_result.get("success"):
                result["error"] = status_result.get("error", "Failed to get git status")
                return result

            changed_files = []
            for line in status_result.get("output", "").splitlines():
                if len(line) >= 3:
                    changed_files.append(line[3:].strip())

            if not changed_files:
                result["message"] = "No changes to commit"
                return result

            result["files_committed"] = changed_files

            # Generate commit message based on plan
            commit_message = cls._generate_commit_message(plan, changed_files)
            result["commit_message"] = commit_message

            # Stage all changes
            add_result = git.execute_safe_command(["git", "add", "-A"])
            if not add_result.get("success"):
                result["error"] = f"Failed to stage changes: {add_result.get('error')}"
                return result

            # Commit
            commit_result = git.execute_safe_command(
                ["git", "commit", "-m", commit_message],
                description=f"Commit: {plan.title}",
            )

            if commit_result.get("success"):
                result["committed"] = True
                # Extract commit hash from output
                output = commit_result.get("output", "")
                if "[" in output and "]" in output:
                    # Format: [branch hash] message
                    parts = output.split("]")[0].split()
                    if len(parts) >= 2:
                        result["commit_hash"] = parts[-1][:8]
            else:
                result["error"] = commit_result.get("error", "Commit failed")

        except ValueError as e:
            # Not a git repo
            result["error"] = str(e)
        except ImportError:
            result["error"] = "GitService not available"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Commit task failed: {e}")

        return result

    @classmethod
    def _generate_commit_message(cls, plan: ExecutionPlan, files: List[str]) -> str:
        """Generate a descriptive commit message based on the plan."""
        # Determine commit type from plan
        request_lower = plan.original_request.lower()

        if any(w in request_lower for w in ["fix", "bug", "error", "issue"]):
            commit_type = "fix"
        elif any(w in request_lower for w in ["add", "new", "create", "implement"]):
            commit_type = "feat"
        elif any(w in request_lower for w in ["refactor", "clean", "improve"]):
            commit_type = "refactor"
        elif any(w in request_lower for w in ["test", "spec"]):
            commit_type = "test"
        elif any(w in request_lower for w in ["doc", "readme"]):
            commit_type = "docs"
        else:
            commit_type = "chore"

        # Create summary from plan title
        summary = plan.title[:50] if plan.title else "Update code"

        # Add file count
        file_count = len(files)
        files_str = f"({file_count} file{'s' if file_count != 1 else ''})"

        # Full message
        message = f"{commit_type}: {summary} {files_str}\n\n"
        message += f"Plan: {plan.id}\n"

        if plan.summary:
            message += f"\n{plan.summary[:200]}"

        # Add completed tasks
        completed_tasks = [t for t in plan.tasks if t.status == TaskStatus.COMPLETED]
        if completed_tasks:
            message += "\n\nCompleted tasks:\n"
            for t in completed_tasks[:5]:  # Limit to 5
                message += f"- {t.title}\n"

        return message


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


async def create_plan(
    request: str,
    workspace_path: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Public API: Create a new execution plan.
    Returns the plan with any clarifying questions.
    """
    plan = await PlanGenerator.create_plan(
        request=request,
        workspace_path=workspace_path,
        attachments=attachments,
        context=context,
    )
    return plan.to_dict()


async def answer_plan_questions(
    plan_id: str,
    answers: Dict[str, str],
) -> Dict[str, Any]:
    """
    Public API: Answer clarifying questions for a plan.
    Returns the updated plan.
    """
    plan = await PlanGenerator.answer_questions(plan_id, answers)
    return plan.to_dict()


async def approve_plan(plan_id: str) -> Dict[str, Any]:
    """
    Public API: Approve a plan for execution.
    """
    plan = await PlanGenerator.approve_plan(plan_id)
    return plan.to_dict()


async def execute_plan(
    plan_id: str,
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Public API: Execute an approved plan.
    """
    plan = await PlanExecutor.execute_plan(plan_id, on_progress=on_progress)
    return plan.to_dict()


def get_plan_status(plan_id: str) -> Optional[Dict[str, Any]]:
    """
    Public API: Get the current status of a plan.
    """
    plan = get_plan(plan_id)
    return plan.to_dict() if plan else None


def list_workspace_plans(workspace_path: str) -> List[Dict[str, Any]]:
    """
    Public API: List all plans for a workspace.
    """
    plans = list_plans(workspace_path)
    return [p.to_dict() for p in plans]
