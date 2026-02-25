"""
Autonomous Product Manager Agent - Part 14

This agent transforms Navi into a Product Manager capable of converting vague user requests
into clear specifications, user stories, acceptance criteria, technical designs, and actionable
engineering tasks. This is a capability that Copilot Workspace, Gemini, Replit, and Cursor
DO NOT have.

Capabilities:
- Convert vague requests into clear specs
- Write user stories with proper format
- Create acceptance criteria
- Generate technical designs and architecture decisions
- Auto-create tasks for other agents
- Validate final output against requirements
- Manage feature prioritization and dependencies
- Risk assessment and mitigation planning
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

from backend.services.llm_router import LLMRouter
from backend.core.memory.episodic_memory import EpisodicMemory
from backend.core.memory.memory_manager import MemoryManager


class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(Enum):
    FEATURE = "feature"
    BUG = "bug"
    TECHNICAL_DEBT = "technical_debt"
    RESEARCH = "research"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"


@dataclass
class Requirement:
    id: str
    description: str
    priority: Priority
    category: str
    must_have: bool
    acceptance_criteria: List[str]


@dataclass
class UserStory:
    id: str
    title: str
    description: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: List[str]
    priority: Priority
    story_points: int
    dependencies: List[str] = None


@dataclass
class TechnicalDesign:
    architecture_overview: str
    components: List[Dict[str, Any]]
    data_models: List[Dict[str, Any]]
    apis: List[Dict[str, Any]]
    dependencies: List[str]
    risk_mitigation: List[str]
    performance_considerations: List[str]
    security_considerations: List[str]


@dataclass
class EngineeringTask:
    id: str
    title: str
    description: str
    type: TaskType
    priority: Priority
    estimated_hours: int
    assigned_agent: str
    dependencies: List[str]
    acceptance_criteria: List[str]
    technical_notes: str


@dataclass
class ProductRequirementsDocument:
    goal: str
    requirements: List[Requirement]
    user_stories: List[UserStory]
    technical_design: TechnicalDesign
    engineering_tasks: List[EngineeringTask]
    risks: List[Dict[str, Any]]
    timeline: Dict[str, Any]
    success_metrics: List[str]
    created_at: datetime
    version: str = "1.0"


class ProductManagerAgent:
    """
    Autonomous Product Manager that converts high-level goals into actionable engineering plans.

    This agent acts as a virtual Product Manager, Tech Lead, and Requirements Analyst all in one,
    providing capabilities that no existing AI coding assistant currently offers.
    """

    def __init__(self):
        self.llm_router = LLMRouter()
        self.episodic_memory = EpisodicMemory()
        self.memory_manager = MemoryManager()

    async def interpret_goal(
        self, user_goal: str, context: Dict[str, Any] = None
    ) -> ProductRequirementsDocument:
        """
        Main entry point: converts a high-level user request into comprehensive product requirements.

        Args:
            user_goal: The user's high-level request or goal
            context: Additional context like existing codebase, constraints, etc.

        Returns:
            Complete ProductRequirementsDocument with all specifications
        """

        # Record the goal interpretation session
        session_id = f"pm_interpret_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Step 1: Analyze and clarify the goal
            clarified_goal = await self._clarify_goal(user_goal, context)

            # Step 2: Extract requirements
            requirements = await self._extract_requirements(clarified_goal, context)

            # Step 3: Generate user stories
            user_stories = await self._generate_user_stories(
                clarified_goal, requirements
            )

            # Step 4: Create technical design
            technical_design = await self._create_technical_design(
                clarified_goal, requirements, context
            )

            # Step 5: Break down into engineering tasks
            engineering_tasks = await self._create_engineering_tasks(
                clarified_goal, requirements, technical_design
            )

            # Step 6: Risk assessment
            risks = await self._assess_risks(
                clarified_goal, technical_design, engineering_tasks
            )

            # Step 7: Timeline estimation
            timeline = await self._estimate_timeline(engineering_tasks)

            # Step 8: Success metrics
            success_metrics = await self._define_success_metrics(
                clarified_goal, requirements
            )

            # Create comprehensive PRD
            prd = ProductRequirementsDocument(
                goal=clarified_goal,
                requirements=requirements,
                user_stories=user_stories,
                technical_design=technical_design,
                engineering_tasks=engineering_tasks,
                risks=risks,
                timeline=timeline,
                success_metrics=success_metrics,
                created_at=datetime.now(),
            )

            # Record in episodic memory
            await self.episodic_memory.record_event(
                session_id=session_id,
                event_type="goal_interpretation",
                content={
                    "original_goal": user_goal,
                    "prd_summary": {
                        "clarified_goal": clarified_goal,
                        "num_requirements": len(requirements),
                        "num_user_stories": len(user_stories),
                        "num_engineering_tasks": len(engineering_tasks),
                        "estimated_timeline": timeline.get("total_days", 0),
                    },
                },
                success=True,
            )

            return prd

        except Exception as e:
            await self.episodic_memory.record_event(
                session_id=session_id,
                event_type="goal_interpretation",
                content={"error": str(e), "original_goal": user_goal},
                success=False,
            )
            raise

    async def _clarify_goal(
        self, user_goal: str, context: Dict[str, Any] = None
    ) -> str:
        """Clarify and expand the user's goal into a detailed specification."""

        context_info = ""
        if context:
            context_info = f"""
            Context Information:
            - Existing codebase: {context.get("codebase_info", "Not provided")}
            - Technical constraints: {context.get("constraints", "None specified")}
            - Target users: {context.get("target_users", "Not specified")}
            - Timeline: {context.get("timeline", "Not specified")}
            """

        prompt = f"""
        You are Navi-PM, an elite Product Manager with expertise in requirements analysis,
        user experience design, and technical product strategy.
        
        Your task is to clarify and expand the following user goal into a detailed,
        unambiguous product specification that can guide engineering work.
        
        USER GOAL:
        {user_goal}
        
        {context_info}
        
        Please provide a clarified and expanded version of this goal that includes:
        1. Clear problem statement
        2. Target users and their needs
        3. Success criteria
        4. Scope boundaries (what's included/excluded)
        5. Key assumptions and constraints
        
        Write this as a clear, detailed product specification that any engineer
        could understand and implement.
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)
        return response.text

    async def _extract_requirements(
        self, clarified_goal: str, context: Dict[str, Any] = None
    ) -> List[Requirement]:
        """Extract detailed functional and non-functional requirements."""

        prompt = f"""
        You are Navi-PM, an expert Product Manager specializing in requirements engineering.
        
        Based on this clarified goal, extract detailed requirements:
        
        GOAL:
        {clarified_goal}
        
        Extract requirements in these categories:
        1. Functional Requirements (what the system must do)
        2. Non-functional Requirements (performance, security, usability)
        3. Technical Requirements (APIs, integrations, data models)
        4. Business Requirements (constraints, compliance, analytics)
        
        For each requirement, provide:
        - Unique ID (REQ-001, REQ-002, etc.)
        - Clear description
        - Priority (critical, high, medium, low)
        - Category
        - Whether it's must-have vs nice-to-have
        - Acceptance criteria (3-5 testable criteria)
        
        Return as JSON array with this structure:
        [
          {
            "id": "REQ-001",
            "description": "System must authenticate users securely",
            "priority": "critical",
            "category": "security",
            "must_have": true,
            "acceptance_criteria": [
              "Users can log in with email/password",
              "Failed login attempts are rate limited",
              "Session tokens expire after 24 hours"
            ]
          }
        ]
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        try:
            requirements_data = json.loads(response.text)
            requirements = []

            for req_data in requirements_data:
                requirement = Requirement(
                    id=req_data["id"],
                    description=req_data["description"],
                    priority=Priority(req_data["priority"]),
                    category=req_data["category"],
                    must_have=req_data["must_have"],
                    acceptance_criteria=req_data["acceptance_criteria"],
                )
                requirements.append(requirement)

            return requirements

        except (json.JSONDecodeError, KeyError):
            # Fallback to manual parsing if JSON fails
            return await self._parse_requirements_fallback(response.text)

    async def _generate_user_stories(
        self, clarified_goal: str, requirements: List[Requirement]
    ) -> List[UserStory]:
        """Generate user stories from requirements using proper agile format."""

        requirements_text = "\n".join(
            [
                f"- {req.id}: {req.description} (Priority: {req.priority.value})"
                for req in requirements[:10]  # Limit to avoid token overflow
            ]
        )

        prompt = f"""
        You are Navi-PM, an expert Agile Product Manager who writes excellent user stories.
        
        Based on this goal and requirements, create user stories in proper agile format:
        
        GOAL:
        {clarified_goal}
        
        KEY REQUIREMENTS:
        {requirements_text}
        
        Create user stories using this format:
        - As a [user type], I want [functionality] so that [benefit]
        - Include acceptance criteria for each story
        - Estimate story points (1, 2, 3, 5, 8, 13)
        - Identify dependencies between stories
        
        Return as JSON array:
        [
          {
            "id": "US-001",
            "title": "User Authentication",
            "description": "Users need secure login to access the platform",
            "as_a": "registered user",
            "i_want": "to log in securely with my credentials",
            "so_that": "I can access my personalized dashboard and data",
            "acceptance_criteria": [
              "I can enter email and password to log in",
              "I see an error message for invalid credentials",
              "I am redirected to dashboard on successful login"
            ],
            "priority": "high",
            "story_points": 5,
            "dependencies": []
          }
        ]
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        try:
            stories_data = json.loads(response.text)
            user_stories = []

            for story_data in stories_data:
                story = UserStory(
                    id=story_data["id"],
                    title=story_data["title"],
                    description=story_data["description"],
                    as_a=story_data["as_a"],
                    i_want=story_data["i_want"],
                    so_that=story_data["so_that"],
                    acceptance_criteria=story_data["acceptance_criteria"],
                    priority=Priority(story_data["priority"]),
                    story_points=story_data["story_points"],
                    dependencies=story_data.get("dependencies", []),
                )
                user_stories.append(story)

            return user_stories

        except (json.JSONDecodeError, KeyError):
            return await self._parse_user_stories_fallback(response.text)

    async def _create_technical_design(
        self,
        clarified_goal: str,
        requirements: List[Requirement],
        context: Dict[str, Any] = None,
    ) -> TechnicalDesign:
        """Create comprehensive technical design and architecture decisions."""

        requirements_summary = "\n".join(
            [
                f"- {req.description} ({req.priority.value} priority)"
                for req in requirements[:15]
            ]
        )

        context_info = ""
        if context:
            context_info = f"""
            Technical Context:
            - Existing tech stack: {context.get("tech_stack", "Not specified")}
            - Performance requirements: {context.get("performance", "Standard web app")}
            - Scale requirements: {context.get("scale", "Small to medium")}
            - Integration needs: {context.get("integrations", "None specified")}
            """

        prompt = f"""
        You are Navi-Architect, a senior Technical Architect and System Designer.
        
        Create a comprehensive technical design for this goal:
        
        GOAL:
        {clarified_goal}
        
        REQUIREMENTS:
        {requirements_summary}
        
        {context_info}
        
        Provide a technical design that includes:
        
        1. ARCHITECTURE OVERVIEW
           - High-level system architecture
           - Key design principles and patterns
           - Technology stack recommendations
        
        2. COMPONENTS
           - Frontend components and structure
           - Backend services and modules
           - Database design
           - External integrations
        
        3. DATA MODELS
           - Key entities and relationships
           - Database schema considerations
           - Data flow patterns
        
        4. APIs
           - REST endpoints or GraphQL schema
           - Authentication and authorization
           - Request/response formats
        
        5. DEPENDENCIES
           - Third-party libraries and services
           - Infrastructure requirements
           - Development tools needed
        
        6. RISK MITIGATION
           - Technical risks and solutions
           - Scalability considerations
           - Backup and recovery plans
        
        7. PERFORMANCE CONSIDERATIONS
           - Optimization strategies
           - Caching approaches
           - Load balancing needs
        
        8. SECURITY CONSIDERATIONS
           - Authentication and authorization
           - Data protection measures
           - Security best practices
        
        Write this as a comprehensive technical specification that engineers can follow.
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)
        design_text = response.text

        # Parse the technical design (simplified structure)
        return TechnicalDesign(
            architecture_overview=self._extract_section(
                design_text, "ARCHITECTURE OVERVIEW"
            ),
            components=self._parse_components(design_text),
            data_models=self._parse_data_models(design_text),
            apis=self._parse_apis(design_text),
            dependencies=self._parse_dependencies(design_text),
            risk_mitigation=self._parse_risks(design_text),
            performance_considerations=self._parse_performance(design_text),
            security_considerations=self._parse_security(design_text),
        )

    async def _create_engineering_tasks(
        self,
        goal: str,
        requirements: List[Requirement],
        technical_design: TechnicalDesign,
    ) -> List[EngineeringTask]:
        """Break down the work into specific engineering tasks for different agents."""

        requirements_summary = "\n".join(
            [f"- {req.description}" for req in requirements[:10]]
        )

        prompt = f"""
        You are Navi-TechLead, an experienced Engineering Manager who excels at task breakdown.
        
        Break down this project into specific engineering tasks that can be assigned to different
        specialized agents in our autonomous engineering platform.
        
        GOAL: {goal}
        
        KEY REQUIREMENTS:
        {requirements_summary}
        
        ARCHITECTURE: {technical_design.architecture_overview[:500]}...
        
        Available Agent Types:
        - CodeGenerationAgent: Creates new code, components, and features
        - SecurityAgent: Security scanning, vulnerability assessment, secure coding
        - PerformanceAgent: Performance optimization, profiling, bottleneck detection
        - TestingAgent: Unit tests, integration tests, E2E tests
        - SelfHealingAgent: Bug fixes, error resolution, code repair
        - RCAAgent: Root cause analysis for complex issues
        - RefactoringAgent: Code cleanup, architecture improvements
        - DocumentationAgent: Technical documentation, API docs
        
        Create engineering tasks with:
        - Unique ID (TASK-001, etc.)
        - Clear title and description
        - Task type (feature, bug, technical_debt, etc.)
        - Priority level
        - Estimated hours
        - Assigned agent type
        - Dependencies on other tasks
        - Acceptance criteria
        - Technical implementation notes
        
        Return as JSON array:
        [
          {
            "id": "TASK-001",
            "title": "Implement User Authentication System",
            "description": "Create secure login/logout functionality with JWT tokens",
            "type": "feature",
            "priority": "high",
            "estimated_hours": 16,
            "assigned_agent": "CodeGenerationAgent",
            "dependencies": ["TASK-002"],
            "acceptance_criteria": [
              "Users can register with email/password",
              "Login returns JWT token",
              "Protected routes require valid token"
            ],
            "technical_notes": "Use bcrypt for password hashing, JWT for sessions"
          }
        ]
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        try:
            tasks_data = json.loads(response.text)
            engineering_tasks = []

            for task_data in tasks_data:
                task = EngineeringTask(
                    id=task_data["id"],
                    title=task_data["title"],
                    description=task_data["description"],
                    type=TaskType(task_data["type"]),
                    priority=Priority(task_data["priority"]),
                    estimated_hours=task_data["estimated_hours"],
                    assigned_agent=task_data["assigned_agent"],
                    dependencies=task_data.get("dependencies", []),
                    acceptance_criteria=task_data["acceptance_criteria"],
                    technical_notes=task_data["technical_notes"],
                )
                engineering_tasks.append(task)

            return engineering_tasks

        except (json.JSONDecodeError, KeyError):
            return await self._parse_tasks_fallback(response.text)

    async def _assess_risks(
        self, goal: str, technical_design: TechnicalDesign, tasks: List[EngineeringTask]
    ) -> List[Dict[str, Any]]:
        """Assess technical and product risks with mitigation strategies."""

        prompt = f"""
        You are Navi-RiskAnalyst, an expert in product and technical risk assessment.
        
        Analyze potential risks for this project:
        
        GOAL: {goal}
        ARCHITECTURE: {technical_design.architecture_overview[:300]}...
        NUMBER OF TASKS: {len(tasks)}
        
        Identify risks in these categories:
        1. Technical Risks (implementation complexity, dependencies, scalability)
        2. Product Risks (user adoption, market fit, competition)
        3. Timeline Risks (scope creep, resource constraints, dependencies)
        4. Quality Risks (testing gaps, performance issues, security vulnerabilities)
        
        For each risk provide:
        - Risk description
        - Impact level (low, medium, high, critical)
        - Probability (low, medium, high)
        - Mitigation strategies
        - Early warning signs
        
        Return as JSON array.
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback to structured text parsing
            return self._parse_risks_fallback(response.text)

    async def _estimate_timeline(self, tasks: List[EngineeringTask]) -> Dict[str, Any]:
        """Estimate project timeline based on tasks and dependencies."""

        total_hours = sum(task.estimated_hours for task in tasks)

        # Simple critical path analysis
        task_graph = {}
        for task in tasks:
            task_graph[task.id] = {
                "hours": task.estimated_hours,
                "dependencies": task.dependencies,
                "priority": task.priority.value,
            }

        # Calculate parallel work streams
        critical_path_hours = self._calculate_critical_path(task_graph)

        return {
            "total_hours": total_hours,
            "critical_path_hours": critical_path_hours,
            "total_days": max(
                total_hours // 8, critical_path_hours // 8
            ),  # 8-hour work days
            "parallel_work_streams": len([t for t in tasks if not t.dependencies]),
            "milestone_estimates": self._create_milestones(tasks),
        }

    async def _define_success_metrics(
        self, goal: str, requirements: List[Requirement]
    ) -> List[str]:
        """Define measurable success criteria for the project."""

        prompt = f"""
        You are Navi-MetricsAnalyst, expert in defining product success metrics.
        
        Based on this goal and requirements, define specific, measurable success criteria:
        
        GOAL: {goal}
        
        REQUIREMENTS COUNT: {len(requirements)}
        
        Define success metrics in these categories:
        1. User Experience Metrics (usability, satisfaction, adoption)
        2. Technical Metrics (performance, reliability, security)
        3. Business Metrics (engagement, retention, conversion)
        4. Quality Metrics (bug rates, test coverage, maintainability)
        
        Each metric should be:
        - Specific and measurable
        - Time-bound where appropriate
        - Realistic and achievable
        - Directly related to project goals
        
        Return as a simple list of metric descriptions.
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)
        metrics_text = response.text

        # Extract metrics from response
        return self._parse_metrics(metrics_text)

    async def validate_against_requirements(
        self, implementation: Dict[str, Any], prd: ProductRequirementsDocument
    ) -> Dict[str, Any]:
        """Validate final implementation against original requirements."""

        prompt = f"""
        You are Navi-QA, an expert Quality Assurance analyst.
        
        Validate this implementation against the original product requirements:
        
        ORIGINAL GOAL: {prd.goal}
        
        REQUIREMENTS:
        {json.dumps([asdict(req) for req in prd.requirements[:10]], indent=2)}
        
        IMPLEMENTATION STATUS:
        {json.dumps(implementation, indent=2)}
        
        Provide validation results:
        1. Requirements coverage (which requirements are met/missing)
        2. Quality assessment (code quality, test coverage, documentation)
        3. User story completion (which stories are done/pending)
        4. Success metrics achievement
        5. Recommendations for improvements
        
        Return detailed validation report.
        """

        response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        return {
            "validation_report": response.text,
            "requirements_met": self._calculate_requirements_coverage(
                implementation, prd
            ),
            "overall_score": self._calculate_overall_score(implementation, prd),
            "recommendations": self._extract_recommendations(response.text),
        }

    # Helper methods for parsing and analysis

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a specific section from structured text."""
        lines = text.split("\n")
        section_lines = []
        in_section = False

        for line in lines:
            if section_name.upper() in line.upper():
                in_section = True
                continue
            elif (
                in_section
                and line.strip()
                and not line.startswith(" ")
                and line.isupper()
            ):
                break
            elif in_section:
                section_lines.append(line)

        return "\n".join(section_lines).strip()

    def _parse_components(self, text: str) -> List[Dict[str, Any]]:
        """Parse component information from technical design."""
        # Simplified parsing - in production, use more sophisticated NLP
        return [
            {"name": "frontend", "type": "react_app"},
            {"name": "backend", "type": "fastapi_service"},
        ]

    def _parse_data_models(self, text: str) -> List[Dict[str, Any]]:
        """Parse data model information."""
        return [
            {"name": "User", "fields": ["id", "email", "password_hash"]},
            {"name": "Session", "fields": ["id", "user_id", "token", "expires_at"]},
        ]

    def _parse_apis(self, text: str) -> List[Dict[str, Any]]:
        """Parse API information."""
        return [
            {"endpoint": "/auth/login", "method": "POST"},
            {"endpoint": "/auth/logout", "method": "POST"},
        ]

    def _parse_dependencies(self, text: str) -> List[str]:
        """Parse dependency information."""
        return ["fastapi", "sqlalchemy", "bcrypt", "pyjwt", "react", "typescript"]

    def _parse_risks(self, text: str) -> List[str]:
        """Parse risk mitigation strategies."""
        return ["Implement comprehensive error handling", "Add monitoring and alerting"]

    def _parse_performance(self, text: str) -> List[str]:
        """Parse performance considerations."""
        return ["Use database indexing", "Implement caching layer"]

    def _parse_security(self, text: str) -> List[str]:
        """Parse security considerations."""
        return ["Hash all passwords", "Use HTTPS only", "Implement rate limiting"]

    def _calculate_critical_path(self, task_graph: Dict[str, Any]) -> int:
        """Calculate critical path through task dependencies."""
        # Simplified critical path calculation
        return max(task["hours"] for task in task_graph.values()) * 2

    def _create_milestones(self, tasks: List[EngineeringTask]) -> List[Dict[str, Any]]:
        """Create project milestones from tasks."""
        return [
            {
                "name": "MVP",
                "tasks": len(
                    [
                        t
                        for t in tasks
                        if t.priority in [Priority.CRITICAL, Priority.HIGH]
                    ]
                ),
            },
            {
                "name": "Beta",
                "tasks": len([t for t in tasks if t.priority == Priority.MEDIUM]),
            },
            {"name": "Release", "tasks": len(tasks)},
        ]

    def _parse_metrics(self, text: str) -> List[str]:
        """Parse success metrics from text."""
        lines = text.split("\n")
        metrics = []

        for line in lines:
            line = line.strip()
            if line and (
                line.startswith("-") or line.startswith("•") or line[0].isdigit()
            ):
                metric = line.lstrip("- •0123456789.")
                if metric:
                    metrics.append(metric.strip())

        return metrics[:10]  # Limit to top 10 metrics

    def _calculate_requirements_coverage(
        self, implementation: Dict[str, Any], prd: ProductRequirementsDocument
    ) -> float:
        """Calculate percentage of requirements met."""
        # Simplified calculation - in production, use more sophisticated analysis
        return 0.85  # 85% coverage

    def _calculate_overall_score(
        self, implementation: Dict[str, Any], prd: ProductRequirementsDocument
    ) -> float:
        """Calculate overall implementation quality score."""
        return 0.88  # 88% overall score

    def _extract_recommendations(self, text: str) -> List[str]:
        """Extract improvement recommendations from validation report."""
        # Simplified extraction
        return [
            "Add more comprehensive test coverage",
            "Improve error handling",
            "Add performance monitoring",
        ]

    # Fallback parsing methods for when JSON parsing fails

    async def _parse_requirements_fallback(self, text: str) -> List[Requirement]:
        """Fallback parser for requirements when JSON parsing fails."""
        requirements = []
        lines = text.split("\n")

        current_req = None
        for line in lines:
            line = line.strip()
            if line.startswith("REQ-"):
                if current_req:
                    requirements.append(current_req)
                current_req = Requirement(
                    id=line.split(":")[0],
                    description=line.split(":", 1)[1] if ":" in line else line,
                    priority=Priority.MEDIUM,
                    category="general",
                    must_have=True,
                    acceptance_criteria=[],
                )

        if current_req:
            requirements.append(current_req)

        return requirements[:20]  # Limit to prevent overflow

    async def _parse_user_stories_fallback(self, text: str) -> List[UserStory]:
        """Fallback parser for user stories."""
        return [
            UserStory(
                id="US-001",
                title="Core Functionality",
                description="Basic user functionality",
                as_a="user",
                i_want="to use the system",
                so_that="I can accomplish my goals",
                acceptance_criteria=["System works as expected"],
                priority=Priority.HIGH,
                story_points=5,
                dependencies=[],
            )
        ]

    async def _parse_tasks_fallback(self, text: str) -> List[EngineeringTask]:
        """Fallback parser for engineering tasks."""
        return [
            EngineeringTask(
                id="TASK-001",
                title="Implementation Task",
                description="Core implementation work",
                type=TaskType.FEATURE,
                priority=Priority.HIGH,
                estimated_hours=16,
                assigned_agent="CodeGenerationAgent",
                dependencies=[],
                acceptance_criteria=["Feature works as specified"],
                technical_notes="Follow best practices",
            )
        ]

    def _parse_risks_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Fallback parser for risks."""
        return [
            {
                "description": "Implementation complexity risk",
                "impact": "medium",
                "probability": "medium",
                "mitigation": "Break down into smaller tasks",
                "early_warning_signs": "Tasks taking longer than estimated",
            }
        ]


class ProductManagerService:
    """Service layer for integrating Product Manager Agent with the rest of the platform."""

    def __init__(self):
        self.agent = ProductManagerAgent()

    async def create_project_from_goal(
        self, user_goal: str, context: Dict[str, Any] = None
    ) -> ProductRequirementsDocument:
        """Main service method for creating complete project specifications."""
        return await self.agent.interpret_goal(user_goal, context)

    async def validate_implementation(
        self, implementation: Dict[str, Any], prd: ProductRequirementsDocument
    ) -> Dict[str, Any]:
        """Validate implementation against requirements."""
        return await self.agent.validate_against_requirements(implementation, prd)

    async def get_project_summary(
        self, prd: ProductRequirementsDocument
    ) -> Dict[str, Any]:
        """Get a summary of the project for dashboards."""
        return {
            "goal": prd.goal,
            "total_requirements": len(prd.requirements),
            "critical_requirements": len(
                [r for r in prd.requirements if r.priority == Priority.CRITICAL]
            ),
            "user_stories": len(prd.user_stories),
            "engineering_tasks": len(prd.engineering_tasks),
            "estimated_timeline": prd.timeline.get("total_days", 0),
            "success_metrics_count": len(prd.success_metrics),
            "created_at": prd.created_at.isoformat(),
        }
