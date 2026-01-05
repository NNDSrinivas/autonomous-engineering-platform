"""
Task Decomposer — Smart Goal → Executable Steps

Converts high-level goals into executable, measurable tasks with dependencies and approval gates.
Leverages the existing planner infrastructure and extends it with long-horizon capabilities.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from backend.agent.planner_v3 import PlannerV3
from backend.orchestrator import PlannedStep, PlanResult
from backend.agent.intent_schema import NaviIntent, IntentKind, IntentFamily
from backend.agent.planning.initiative_store import Initiative


class TaskPriority(Enum):
    """Task priority levels"""

    CRITICAL = "CRITICAL"  # Blocking
    HIGH = "HIGH"  # Important
    MEDIUM = "MEDIUM"  # Standard
    LOW = "LOW"  # Nice to have


class TaskType(Enum):
    """Types of tasks"""

    ANALYSIS = "ANALYSIS"  # Research, investigation
    DEVELOPMENT = "DEVELOPMENT"  # Code, implementation
    TESTING = "TESTING"  # QA, validation
    DEPLOYMENT = "DEPLOYMENT"  # Release, rollout
    DOCUMENTATION = "DOCUMENTATION"  # Docs, specs
    COORDINATION = "COORDINATION"  # Meetings, approvals


@dataclass
class DecomposedTask:
    """A task decomposed from a high-level goal"""

    id: str
    title: str
    description: str
    task_type: TaskType
    priority: TaskPriority
    estimated_hours: float
    dependencies: List[str]  # Task IDs this depends on
    approval_required: bool
    approvers: List[str]
    success_criteria: List[str]
    jira_issue_type: str = "Task"
    metadata: Optional[Dict[str, Any]] = None

    def to_plan_step(self) -> Dict[str, Any]:
        """Convert to LivePlan step format"""
        return {
            "id": self.id,
            "type": "task",
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "estimated_hours": self.estimated_hours,
            "dependencies": self.dependencies,
            "approval_required": self.approval_required,
            "approvers": self.approvers,
            "success_criteria": self.success_criteria,
            "jira_issue_type": self.jira_issue_type,
            "status": "planned",
            "metadata": self.metadata or {},
        }


@dataclass
class DecompositionResult:
    """Result of goal decomposition"""

    tasks: List[DecomposedTask]
    execution_phases: List[List[str]]  # Task IDs grouped by execution phase
    critical_path: List[str]  # Task IDs in critical path
    total_estimated_hours: float
    suggested_timeline_weeks: int
    risks: List[str]
    assumptions: List[str]


class TaskDecomposer:
    """Decomposes high-level goals into executable tasks"""

    def __init__(self, planner: Optional[PlannerV3] = None):
        self.planner = planner or PlannerV3()
        self.task_counter = 0

    async def decompose_goal(
        self,
        goal: str,
        context: Dict[str, Any],
        org_id: str,
        owner: str,
        approval_policy: Optional[Dict[str, Any]] = None,
    ) -> DecompositionResult:
        """
        Decompose a high-level goal into executable tasks

        Args:
            goal: The high-level goal to achieve
            context: Additional context (codebase, team, constraints)
            org_id: Organization ID
            owner: Goal owner
            approval_policy: Policy for when approvals are required
        """

        # Use the existing planner to get initial task breakdown
        plan_prompt = self._build_decomposition_prompt(goal, context, approval_policy)

        # Create NaviIntent for the planner
        intent = NaviIntent(
            family=IntentFamily.PROJECT_MANAGEMENT,
            kind=IntentKind.GENERIC,
            raw_text=plan_prompt,
            slots={"org_id": org_id, "owner": owner},
        )

        initial_plan = await self.planner.plan(intent, context)

        # Extract tasks from the plan
        tasks = self._extract_tasks_from_plan(
            initial_plan, org_id, owner, approval_policy
        )

        # Analyze dependencies and create execution phases
        execution_phases = self._create_execution_phases(tasks)

        # Identify critical path
        critical_path = self._identify_critical_path(tasks, execution_phases)

        # Calculate estimates
        total_hours = sum(task.estimated_hours for task in tasks)
        timeline_weeks = max(1, int(total_hours / 40))  # Assuming 40 hours/week

        # Identify risks and assumptions
        risks = self._identify_risks(tasks, context)
        assumptions = self._identify_assumptions(tasks, context)

        return DecompositionResult(
            tasks=tasks,
            execution_phases=execution_phases,
            critical_path=critical_path,
            total_estimated_hours=total_hours,
            suggested_timeline_weeks=timeline_weeks,
            risks=risks,
            assumptions=assumptions,
        )

    def create_live_plan(
        self, initiative: Initiative, decomposition: DecompositionResult
    ) -> Dict[str, Any]:
        """Create a LivePlan from decomposition results"""

        # Convert tasks to plan steps
        steps = [task.to_plan_step() for task in decomposition.tasks]

        # Add phases as organizational steps
        for i, phase_tasks in enumerate(decomposition.execution_phases):
            phase_step = {
                "id": f"phase_{i+1}",
                "type": "phase",
                "title": f"Phase {i+1}",
                "description": f"Execution phase {i+1}",
                "task_ids": phase_tasks,
                "status": "planned",
            }
            steps.append(phase_step)

        # Create the live plan data
        plan_data = {
            "title": f"Initiative: {initiative.title}",
            "description": initiative.goal,
            "steps": steps,
            "participants": [initiative.owner],
            "org_id": initiative.org_id,
            "metadata": {
                "initiative_id": initiative.id,
                "type": "long_horizon_plan",
                "total_estimated_hours": decomposition.total_estimated_hours,
                "suggested_timeline_weeks": decomposition.suggested_timeline_weeks,
                "critical_path": decomposition.critical_path,
                "risks": decomposition.risks,
                "assumptions": decomposition.assumptions,
                "execution_phases": decomposition.execution_phases,
            },
        }

        return plan_data

    def _build_decomposition_prompt(
        self,
        goal: str,
        context: Dict[str, Any],
        approval_policy: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt for goal decomposition"""

        prompt = f"""
GOAL DECOMPOSITION REQUEST

Goal: {goal}

Context:
- Repository: {context.get('repository', 'Unknown')}
- Team Size: {context.get('team_size', 'Unknown')}
- Timeline: {context.get('timeline', 'Flexible')}
- Constraints: {context.get('constraints', 'None specified')}

Please decompose this goal into specific, executable tasks. For each task, provide:
1. Clear title and description
2. Task type (analysis, development, testing, deployment, documentation, coordination)
3. Priority level (critical, high, medium, low)
4. Estimated effort in hours
5. Dependencies on other tasks
6. Success criteria
7. Whether approval is required

Consider:
- Break down large tasks into smaller, manageable pieces
- Identify dependencies and ordering constraints
- Include testing and validation steps
- Add coordination points for stakeholder involvement
- Consider rollback and risk mitigation steps
"""

        if approval_policy:
            prompt += f"\nApproval Policy: {json.dumps(approval_policy, indent=2)}"

        return prompt

    def _extract_tasks_from_plan(
        self,
        plan_result: PlanResult,
        org_id: str,
        owner: str,
        approval_policy: Optional[Dict[str, Any]],
    ) -> List[DecomposedTask]:
        """Extract structured tasks from planner result"""

        tasks = []
        steps = plan_result.steps

        for i, step in enumerate(steps):
            task_id = f"task_{i+1:03d}"

            # Parse task details from step
            title = step.description or f"Task {i+1}"
            description = step.description or ""

            # Infer task type from content
            task_type = self._infer_task_type(title, description)

            # Estimate effort and priority
            estimated_hours = self._estimate_effort(title, description, task_type)
            urgency = step.arguments.get("urgency", "medium")
            priority = self._infer_priority(title, description, urgency)

            # Extract dependencies
            dependencies = self._extract_dependencies(step, tasks)

            # Determine if approval is required
            approval_required = self._needs_approval(step, task_type, approval_policy)
            approvers = (
                self._get_approvers(step, approval_policy) if approval_required else []
            )

            # Extract success criteria
            success_criteria = self._extract_success_criteria(step)

            task = DecomposedTask(
                id=task_id,
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
                estimated_hours=estimated_hours,
                dependencies=dependencies,
                approval_required=approval_required,
                approvers=approvers,
                success_criteria=success_criteria,
                metadata={"original_step": step},
            )

            tasks.append(task)

        return tasks

    def _create_execution_phases(self, tasks: List[DecomposedTask]) -> List[List[str]]:
        """Group tasks into execution phases based on dependencies"""

        # Build dependency graph
        task_deps = {task.id: set(task.dependencies) for task in tasks}

        phases = []
        remaining_tasks = set(task.id for task in tasks)

        while remaining_tasks:
            # Find tasks with no unresolved dependencies
            ready_tasks = []
            for task_id in remaining_tasks:
                deps = task_deps[task_id]
                if not deps or all(dep not in remaining_tasks for dep in deps):
                    ready_tasks.append(task_id)

            if not ready_tasks:
                # Circular dependency - break it by taking highest priority task
                priority_order = {
                    TaskPriority.CRITICAL: 0,
                    TaskPriority.HIGH: 1,
                    TaskPriority.MEDIUM: 2,
                    TaskPriority.LOW: 3,
                }
                task_priorities = {
                    t.id: priority_order[t.priority]
                    for t in tasks
                    if t.id in remaining_tasks
                }
                ready_tasks = [
                    min(task_priorities.keys(), key=lambda k: task_priorities[k])
                ]

            phases.append(ready_tasks)
            remaining_tasks -= set(ready_tasks)

        return phases

    def _identify_critical_path(
        self, tasks: List[DecomposedTask], phases: List[List[str]]
    ) -> List[str]:
        """Identify the critical path through the task graph"""

        # Simple critical path: longest path through dependencies
        task_map = {task.id: task for task in tasks}

        def get_longest_path(task_id: str, visited: set) -> Tuple[float, List[str]]:
            if task_id in visited:
                return 0, []

            visited.add(task_id)
            task = task_map[task_id]

            if not task.dependencies:
                return task.estimated_hours, [task_id]

            best_time, best_path = 0, []
            for dep in task.dependencies:
                if dep in task_map:
                    dep_time, dep_path = get_longest_path(dep, visited.copy())
                    if dep_time > best_time:
                        best_time, best_path = dep_time, dep_path

            return best_time + task.estimated_hours, best_path + [task_id]

        # Find the longest path from any starting task
        longest_path = []
        longest_time = 0

        for task in tasks:
            if not task.dependencies:  # Starting tasks
                time, path = get_longest_path(task.id, set())
                if time > longest_time:
                    longest_time, longest_path = time, path

        return longest_path

    def _identify_risks(
        self, tasks: List[DecomposedTask], context: Dict[str, Any]
    ) -> List[str]:
        """Identify potential risks in the task plan"""

        risks = []

        # Check for long critical path
        total_hours = sum(task.estimated_hours for task in tasks)
        if total_hours > 200:  # 5+ weeks
            risks.append("Long execution timeline increases delivery risk")

        # Check for many dependencies
        high_dep_tasks = [t for t in tasks if len(t.dependencies) > 3]
        if high_dep_tasks:
            risks.append(f"{len(high_dep_tasks)} tasks have complex dependencies")

        # Check for approval bottlenecks
        approval_tasks = [t for t in tasks if t.approval_required]
        if len(approval_tasks) > len(tasks) * 0.3:  # > 30% need approval
            risks.append("High number of approval gates may slow progress")

        return risks

    def _identify_assumptions(
        self, tasks: List[DecomposedTask], context: Dict[str, Any]
    ) -> List[str]:
        """Identify assumptions made during decomposition"""

        assumptions = [
            "Team has necessary skills and access permissions",
            "External dependencies will be available when needed",
            "No major scope changes during execution",
            "Standard development environment and tools available",
        ]

        # Add context-specific assumptions
        if context.get("team_size"):
            assumptions.append(f"Team size of {context['team_size']} is maintained")

        if context.get("timeline"):
            assumptions.append(
                f"Timeline constraint of {context['timeline']} is flexible"
            )

        return assumptions

    def _infer_task_type(self, title: str, description: str) -> TaskType:
        """Infer task type from title and description"""

        content = f"{title} {description}".lower()

        if any(
            keyword in content
            for keyword in ["analyze", "research", "investigate", "study"]
        ):
            return TaskType.ANALYSIS
        elif any(
            keyword in content for keyword in ["implement", "code", "develop", "build"]
        ):
            return TaskType.DEVELOPMENT
        elif any(
            keyword in content for keyword in ["test", "verify", "validate", "qa"]
        ):
            return TaskType.TESTING
        elif any(
            keyword in content for keyword in ["deploy", "release", "rollout", "launch"]
        ):
            return TaskType.DEPLOYMENT
        elif any(
            keyword in content for keyword in ["document", "spec", "readme", "wiki"]
        ):
            return TaskType.DOCUMENTATION
        elif any(
            keyword in content for keyword in ["meet", "approve", "coordinate", "sync"]
        ):
            return TaskType.COORDINATION
        else:
            return TaskType.DEVELOPMENT  # Default

    def _estimate_effort(
        self, title: str, description: str, task_type: TaskType
    ) -> float:
        """Estimate effort in hours for a task"""

        # Base estimates by task type
        base_estimates = {
            TaskType.ANALYSIS: 8,
            TaskType.DEVELOPMENT: 16,
            TaskType.TESTING: 12,
            TaskType.DEPLOYMENT: 6,
            TaskType.DOCUMENTATION: 4,
            TaskType.COORDINATION: 2,
        }

        base = base_estimates[task_type]

        # Adjust based on complexity indicators
        content = f"{title} {description}".lower()

        if any(
            keyword in content
            for keyword in ["complex", "advanced", "integration", "migration"]
        ):
            base *= 2
        elif any(
            keyword in content
            for keyword in ["simple", "basic", "straightforward", "quick"]
        ):
            base *= 0.5

        return max(1, base)  # At least 1 hour

    def _infer_priority(
        self, title: str, description: str, urgency: str
    ) -> TaskPriority:
        """Infer priority from task details"""

        content = f"{title} {description}".lower()

        if urgency.lower() in ["critical", "urgent", "high"]:
            return TaskPriority.CRITICAL
        elif any(
            keyword in content
            for keyword in ["critical", "blocker", "urgent", "security"]
        ):
            return TaskPriority.CRITICAL
        elif any(keyword in content for keyword in ["important", "core", "essential"]):
            return TaskPriority.HIGH
        elif any(keyword in content for keyword in ["nice", "optional", "enhancement"]):
            return TaskPriority.LOW
        else:
            return TaskPriority.MEDIUM

    def _extract_dependencies(
        self, step: PlannedStep, existing_tasks: List[DecomposedTask]
    ) -> List[str]:
        """Extract dependencies from step data"""

        # Look for explicit dependencies in step
        explicit_deps = step.arguments.get("depends_on", [])
        if explicit_deps:
            return explicit_deps

        # Infer dependencies based on task content and order
        dependencies = []

        # Simple rule: testing depends on development, deployment depends on testing
        step.arguments.get("type", "").lower()
        title = (step.description or "").lower()

        if "test" in title or "validate" in title:
            # Find related development tasks
            for task in existing_tasks:
                if task.task_type == TaskType.DEVELOPMENT and any(
                    keyword in task.title.lower()
                    for keyword in ["implement", "build", "create"]
                ):
                    dependencies.append(task.id)

        elif "deploy" in title or "release" in title:
            # Depend on testing tasks
            for task in existing_tasks:
                if task.task_type == TaskType.TESTING:
                    dependencies.append(task.id)

        return dependencies

    def _needs_approval(
        self,
        step: PlannedStep,
        task_type: TaskType,
        approval_policy: Optional[Dict[str, Any]],
    ) -> bool:
        """Determine if a task needs approval"""

        if not approval_policy:
            # Default policy: deployment and high-impact changes need approval
            return (
                task_type in [TaskType.DEPLOYMENT]
                or "critical" in (step.description or "").lower()
            )

        # Check policy rules
        rules = approval_policy.get("rules", [])
        for rule in rules:
            if self._matches_approval_rule(step, task_type, rule):
                return True

        return False

    def _get_approvers(
        self, step: PlannedStep, approval_policy: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Get list of approvers for a task"""

        if not approval_policy:
            return ["tech_lead", "product_manager"]  # Default approvers

        return approval_policy.get("default_approvers", ["tech_lead"])

    def _extract_success_criteria(self, step: PlannedStep) -> List[str]:
        """Extract success criteria from step"""

        criteria = step.arguments.get("success_criteria", [])
        if criteria:
            return criteria

        # Generate default criteria based on step type
        title = step.description or ""

        if "implement" in title.lower():
            return [
                "Code is implemented and passes unit tests",
                "Code review is completed",
            ]
        elif "test" in title.lower():
            return ["All tests pass", "Test coverage meets requirements"]
        elif "deploy" in title.lower():
            return ["Deployment is successful", "Health checks pass"]
        else:
            return ["Task objectives are met", "Deliverables are completed"]

    def _matches_approval_rule(
        self, step: PlannedStep, task_type: TaskType, rule: Dict[str, Any]
    ) -> bool:
        """Check if a step matches an approval rule"""

        # Simple rule matching - can be extended
        if rule.get("task_type") == task_type.value:
            return True

        if (
            rule.get("keyword")
            and rule["keyword"].lower() in (step.description or "").lower()
        ):
            return True

        return False
