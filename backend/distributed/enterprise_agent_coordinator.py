"""
Enterprise Agent Coordinator

Bridges EnterpriseProject with DistributedAgentFleet to enable parallel task execution
for enterprise-scale application development spanning weeks/months.

Key capabilities:
- Spawn parallel sub-agents for independent tasks from ProjectTaskQueue
- Aggregate results from parallel execution with conflict detection
- Handle agent failures with retry, reassignment, or escalation
- Integrate with human checkpoint gates for approval workflows
- Maintain task state synchronization across distributed agents
- Support for enterprise iteration modes (unlimited iterations)

Usage:
    from backend.distributed.enterprise_agent_coordinator import EnterpriseAgentCoordinator

    coordinator = EnterpriseAgentCoordinator(db_session)
    await coordinator.start_project_execution(project_id)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import uuid

from backend.distributed.agent_fleet import (
    DistributedAgentFleet,
    AgentRole,
    TaskPriority as FleetTaskPriority,
    TaskStatus as FleetTaskStatus,
    Task as FleetTask,
    ConflictResolutionStrategy,
)
from backend.database.models.enterprise_project import (
    EnterpriseProject,
    HumanCheckpointGate,
    ProjectTaskQueue,
)
from backend.services.enterprise_project_service import EnterpriseProjectService
from backend.services.checkpoint_gate_detector import CheckpointGateDetector, GateTrigger


logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Enterprise execution modes"""
    SEQUENTIAL = "sequential"  # Tasks run one at a time
    PARALLEL = "parallel"  # Independent tasks run in parallel
    HYBRID = "hybrid"  # Mix of parallel and sequential based on dependencies


class AgentFailureStrategy(Enum):
    """Strategies for handling agent failures"""
    RETRY = "retry"  # Retry the same task
    REASSIGN = "reassign"  # Assign to different agent
    ESCALATE = "escalate"  # Escalate to human
    SKIP = "skip"  # Skip and continue (for non-blocking tasks)


@dataclass
class ParallelExecutionResult:
    """Result of parallel task execution"""
    task_results: Dict[str, Dict[str, Any]]  # task_id -> result
    successful_tasks: List[str]
    failed_tasks: List[str]
    conflicts: List[Dict[str, Any]]
    total_duration_seconds: float
    agent_utilization: Dict[str, float]  # agent_id -> utilization


@dataclass
class TaskExecutionContext:
    """Context for task execution"""
    project_id: str
    task_id: str
    workspace_path: str
    dependencies_completed: List[str]
    parent_context: Dict[str, Any]
    timeout_seconds: int = 3600  # 1 hour default
    max_retries: int = 3
    current_retry: int = 0


@dataclass
class CoordinatorState:
    """Current state of the coordinator"""
    project_id: str
    status: str  # idle, running, paused, completed, failed
    active_agents: Dict[str, str]  # agent_id -> task_id
    pending_tasks: List[str]
    completed_tasks: List[str]
    failed_tasks: List[str]
    pending_gates: List[str]  # gate IDs waiting for human decision
    start_time: Optional[datetime] = None
    checkpoint_interval_minutes: int = 30
    last_checkpoint: Optional[datetime] = None
    iteration_count: int = 0


class EnterpriseAgentCoordinator:
    """
    Coordinates distributed agent execution for enterprise projects.

    Bridges EnterpriseProject/ProjectTaskQueue with DistributedAgentFleet
    to enable parallel task execution with proper orchestration.

    Supports all LLM providers with BYOK (Bring Your Own Key).
    """

    def __init__(
        self,
        db_session,
        max_parallel_agents: int = 5,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ):
        """
        Initialize the Enterprise Agent Coordinator.

        Args:
            db_session: Database session for persistence
            max_parallel_agents: Maximum agents to run in parallel
            llm_provider: LLM provider (openai, anthropic, google, groq, etc.)
            llm_model: Model to use (provider-specific)
            llm_api_key: Optional BYOK API key
            workspace_path: Workspace path for agent execution
        """
        self.db = db_session
        self.max_parallel_agents = max_parallel_agents

        # LLM configuration for agents and task decomposition
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.workspace_path = workspace_path or os.getcwd()

        # Core components
        self.fleet = DistributedAgentFleet()
        self.project_service = EnterpriseProjectService(db_session)
        self.gate_detector = CheckpointGateDetector()

        # Coordinator state per project
        self.project_states: Dict[str, CoordinatorState] = {}

        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = {
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "gate_triggered": [],
            "gate_resolved": [],
            "checkpoint_created": [],
            "project_paused": [],
            "project_resumed": [],
            "project_completed": [],
        }

        # Agent pool management
        self.agent_pool: Dict[str, Dict[str, Any]] = {}
        self.agent_assignments: Dict[str, str] = {}  # agent_id -> task_id

        # Active agent instances (for cleanup)
        self.active_agents: Dict[str, Any] = {}

    def register_event_callback(self, event_type: str, callback: Callable) -> None:
        """Register callback for coordinator events."""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)

    async def decompose_project_goal(
        self,
        project_id: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Decompose a project goal into executable tasks using LLM.

        Args:
            project_id: The enterprise project ID
            goal: The high-level project goal
            context: Optional context (tech preferences, constraints)

        Yields:
            Progress events during decomposition
        """
        from backend.services.task_decomposer import TaskDecomposer

        logger.info(f"Decomposing goal for project {project_id}: {goal[:100]}...")

        yield {
            "type": "decomposition_started",
            "project_id": project_id,
            "goal": goal[:200],
        }

        try:
            # Create decomposer with coordinator's LLM config
            decomposer = TaskDecomposer(
                provider=self.llm_provider,
                model=self.llm_model,
                api_key=self.llm_api_key,
            )

            yield {
                "type": "status",
                "status": "analyzing",
                "message": "Analyzing project requirements...",
            }

            # Decompose the goal
            result = await decomposer.decompose_goal(
                goal=goal,
                context=context,
                min_tasks=50,
                max_tasks=200,
            )

            yield {
                "type": "decomposition_analysis",
                "project_name": result.project_name,
                "project_type": result.project_type,
                "phases": result.phases,
                "task_count": len(result.tasks),
                "tech_stack": result.tech_stack,
            }

            # Save tasks to database
            yield {
                "type": "status",
                "status": "saving_tasks",
                "message": f"Saving {len(result.tasks)} tasks...",
            }

            task_ids = []
            for task in result.tasks:
                saved_task = await self.project_service.add_task(
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

            # Update project with milestones and ADRs
            project = await self.project_service.get_project(project_id)
            if project:
                project.milestones = result.milestones
                project.architecture_decisions = result.architecture_decisions
                self.db.commit()

            yield {
                "type": "decomposition_completed",
                "project_id": project_id,
                "task_count": len(task_ids),
                "phases": result.phases,
                "milestones": result.milestones,
                "architecture_decisions_count": len(result.architecture_decisions),
                "estimated_hours": result.estimated_total_hours,
            }

            # Trigger gates for architecture decisions that need approval
            for adr in result.architecture_decisions:
                if adr.get("requires_approval", False):
                    gate = await self.project_service.create_human_gate(
                        project_id=project_id,
                        gate_type="architecture_review",
                        title=f"ADR: {adr.get('title', 'Architecture Decision')}",
                        description=adr.get("decision", ""),
                        options=[
                            {"id": "approve", "label": "Approve", "trade_offs": "Proceed with decision"},
                            {"id": "modify", "label": "Request Modification", "trade_offs": "May delay project"},
                            {"id": "reject", "label": "Reject", "trade_offs": "Need alternative approach"},
                        ],
                    )
                    yield {
                        "type": "gate_triggered",
                        "project_id": project_id,
                        "gate": {
                            "id": str(gate.id),
                            "gate_type": "architecture_review",
                            "title": gate.title,
                            "description": gate.description,
                        },
                    }

        except Exception as e:
            logger.exception(f"Failed to decompose goal: {e}")
            yield {
                "type": "decomposition_failed",
                "project_id": project_id,
                "error": str(e),
            }

    async def start_project_execution(
        self,
        project_id: str,
        execution_mode: ExecutionMode = ExecutionMode.HYBRID,
        checkpoint_interval_minutes: int = 30,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start executing an enterprise project with distributed agents.

        Args:
            project_id: EnterpriseProject ID
            execution_mode: How to execute tasks (sequential, parallel, hybrid)
            checkpoint_interval_minutes: How often to create checkpoints

        Yields:
            Progress events during execution
        """
        logger.info(f"Starting enterprise project execution: {project_id}")

        # Initialize coordinator state
        state = CoordinatorState(
            project_id=project_id,
            status="running",
            active_agents={},
            pending_tasks=[],
            completed_tasks=[],
            failed_tasks=[],
            pending_gates=[],
            start_time=datetime.now(timezone.utc),
            checkpoint_interval_minutes=checkpoint_interval_minutes,
            last_checkpoint=datetime.now(timezone.utc),
        )
        self.project_states[project_id] = state

        # Get project and tasks
        project = await self.project_service.get_project(project_id)
        if not project:
            yield {"type": "error", "message": f"Project {project_id} not found"}
            return

        # Update project status
        await self.project_service.update_project(
            project_id, status="active", started_at=datetime.now(timezone.utc)
        )

        yield {
            "type": "project_started",
            "project_id": project_id,
            "execution_mode": execution_mode.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Main execution loop
            async for event in self._execute_project_loop(
                project_id, state, execution_mode
            ):
                yield event

                # Check for completion
                if event.get("type") == "project_completed":
                    break

                # Check for fatal errors
                if event.get("type") == "fatal_error":
                    break

        except Exception as e:
            logger.error(f"Project execution failed: {e}")
            state.status = "failed"
            yield {
                "type": "project_failed",
                "project_id": project_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            # Cleanup
            await self._cleanup_agents(project_id)

    async def _execute_project_loop(
        self,
        project_id: str,
        state: CoordinatorState,
        execution_mode: ExecutionMode,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main execution loop for project tasks."""

        while state.status == "running":
            state.iteration_count += 1

            # Get ready tasks (dependencies satisfied)
            ready_tasks = await self.project_service.get_ready_tasks(project_id)

            if not ready_tasks and not state.active_agents:
                # Check if all tasks are done
                remaining = await self._get_remaining_tasks(project_id)
                if not remaining:
                    state.status = "completed"
                    yield {
                        "type": "project_completed",
                        "project_id": project_id,
                        "completed_tasks": len(state.completed_tasks),
                        "failed_tasks": len(state.failed_tasks),
                        "total_iterations": state.iteration_count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    break
                else:
                    # Tasks are blocked - check for pending gates
                    if state.pending_gates:
                        yield {
                            "type": "awaiting_human_decision",
                            "project_id": project_id,
                            "pending_gates": state.pending_gates,
                            "blocked_tasks": remaining,
                        }
                        # Wait for gate resolution
                        await asyncio.sleep(5)
                        continue
                    else:
                        # Possible deadlock - all remaining tasks have unmet deps
                        yield {
                            "type": "warning",
                            "message": "No ready tasks but project not complete",
                            "remaining_tasks": remaining,
                        }
                        await asyncio.sleep(5)
                        continue

            # Execute tasks based on mode
            if execution_mode == ExecutionMode.PARALLEL:
                async for event in self._execute_parallel(project_id, state, ready_tasks):
                    yield event
            elif execution_mode == ExecutionMode.SEQUENTIAL:
                async for event in self._execute_sequential(project_id, state, ready_tasks):
                    yield event
            else:  # HYBRID
                async for event in self._execute_hybrid(project_id, state, ready_tasks):
                    yield event

            # Check for human gates
            async for event in self._check_human_gates(project_id, state):
                yield event

            # Auto-checkpoint if needed
            if self._needs_checkpoint(state):
                async for event in self._create_checkpoint(project_id, state):
                    yield event

            # Yield progress update
            yield {
                "type": "iteration_complete",
                "project_id": project_id,
                "iteration": state.iteration_count,
                "active_agents": len(state.active_agents),
                "completed_tasks": len(state.completed_tasks),
                "pending_tasks": len(state.pending_tasks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Small delay to prevent tight loops
            await asyncio.sleep(1)

    async def _execute_parallel(
        self,
        project_id: str,
        state: CoordinatorState,
        ready_tasks: List[ProjectTaskQueue],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute ready tasks in parallel using distributed agents."""

        # Limit to max parallel agents
        tasks_to_execute = ready_tasks[: self.max_parallel_agents]

        if not tasks_to_execute:
            return

        yield {
            "type": "parallel_execution_start",
            "project_id": project_id,
            "task_count": len(tasks_to_execute),
            "task_ids": [str(t.id) for t in tasks_to_execute],
        }

        # Spawn agents for each task
        agent_futures = []
        for task in tasks_to_execute:
            task_id = str(task.id)

            # Mark task as in progress
            await self.project_service.update_task_status(
                task_id, "in_progress", started_at=datetime.now(timezone.utc)
            )

            # Create execution context
            context = TaskExecutionContext(
                project_id=project_id,
                task_id=task_id,
                workspace_path=task.outputs.get("workspace_path", ".") if task.outputs else ".",
                dependencies_completed=task.dependencies or [],
                parent_context={"project_id": project_id},
            )

            # Spawn agent
            agent_future = asyncio.create_task(
                self._spawn_task_agent(task, context)
            )
            agent_futures.append((task_id, agent_future))
            state.active_agents[task_id] = f"agent_{task_id}"

            yield {
                "type": "task_started",
                "project_id": project_id,
                "task_id": task_id,
                "task_title": task.title,
            }

        # Wait for all agents to complete
        results = {}
        for task_id, future in agent_futures:
            try:
                result = await asyncio.wait_for(future, timeout=3600)  # 1 hour timeout
                results[task_id] = result

                if result.get("success"):
                    state.completed_tasks.append(task_id)
                    await self.project_service.update_task_status(
                        task_id, "completed",
                        completed_at=datetime.now(timezone.utc),
                        outputs=result.get("outputs", {})
                    )
                    yield {
                        "type": "task_completed",
                        "project_id": project_id,
                        "task_id": task_id,
                        "result": result,
                    }
                else:
                    # Handle failure
                    async for event in self._handle_task_failure(
                        project_id, state, task_id, result
                    ):
                        yield event

            except asyncio.TimeoutError:
                async for event in self._handle_task_failure(
                    project_id, state, task_id, {"error": "Task timeout"}
                ):
                    yield event

            except Exception as e:
                async for event in self._handle_task_failure(
                    project_id, state, task_id, {"error": str(e)}
                ):
                    yield event

            finally:
                state.active_agents.pop(task_id, None)

        # Check for conflicts in results
        conflicts = await self._detect_conflicts(results)
        if conflicts:
            yield {
                "type": "conflicts_detected",
                "project_id": project_id,
                "conflicts": conflicts,
            }

            # Resolve conflicts
            resolved = await self._resolve_conflicts(conflicts, results)
            yield {
                "type": "conflicts_resolved",
                "project_id": project_id,
                "resolutions": resolved,
            }

    async def _execute_sequential(
        self,
        project_id: str,
        state: CoordinatorState,
        ready_tasks: List[ProjectTaskQueue],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute tasks one at a time in priority order."""

        for task in ready_tasks[:1]:  # Only take first task
            task_id = str(task.id)

            yield {
                "type": "task_started",
                "project_id": project_id,
                "task_id": task_id,
                "task_title": task.title,
                "mode": "sequential",
            }

            await self.project_service.update_task_status(
                task_id, "in_progress", started_at=datetime.now(timezone.utc)
            )

            context = TaskExecutionContext(
                project_id=project_id,
                task_id=task_id,
                workspace_path=".",
                dependencies_completed=task.dependencies or [],
                parent_context={"project_id": project_id},
            )

            try:
                result = await self._spawn_task_agent(task, context)

                if result.get("success"):
                    state.completed_tasks.append(task_id)
                    await self.project_service.update_task_status(
                        task_id, "completed",
                        completed_at=datetime.now(timezone.utc),
                        outputs=result.get("outputs", {})
                    )
                    yield {
                        "type": "task_completed",
                        "project_id": project_id,
                        "task_id": task_id,
                        "result": result,
                    }
                else:
                    async for event in self._handle_task_failure(
                        project_id, state, task_id, result
                    ):
                        yield event

            except Exception as e:
                async for event in self._handle_task_failure(
                    project_id, state, task_id, {"error": str(e)}
                ):
                    yield event

    async def _execute_hybrid(
        self,
        project_id: str,
        state: CoordinatorState,
        ready_tasks: List[ProjectTaskQueue],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute tasks with hybrid strategy:
        - Parallelize independent tasks
        - Serialize tasks with shared dependencies
        """

        # Group tasks by dependency clusters
        independent_tasks = []
        dependent_clusters = []

        for task in ready_tasks:
            has_active_dep = False
            for dep_id in (task.dependencies or []):
                if dep_id in state.active_agents:
                    has_active_dep = True
                    break

            if not has_active_dep:
                independent_tasks.append(task)
            else:
                dependent_clusters.append(task)

        # Execute independent tasks in parallel
        if independent_tasks:
            parallel_tasks = independent_tasks[: self.max_parallel_agents]
            async for event in self._execute_parallel(
                project_id, state, parallel_tasks
            ):
                yield event

        # Queue dependent tasks for next iteration
        state.pending_tasks = [str(t.id) for t in dependent_clusters]

    async def _spawn_task_agent(
        self,
        task: ProjectTaskQueue,
        context: TaskExecutionContext,
    ) -> Dict[str, Any]:
        """
        Spawn a sub-agent to execute a specific task.

        This creates a real AutonomousAgent instance configured with:
        1. Task-specific context and instructions
        2. LLM provider/model from coordinator config
        3. Workspace path for file operations
        4. Verification criteria for success validation

        Supports all LLM providers with BYOK (Bring Your Own Key).
        """
        from backend.services.autonomous_agent import AutonomousAgent

        logger.info(f"Spawning agent for task: {task.title}")

        start_time = datetime.now(timezone.utc)

        # Build task prompt with context
        task_prompt = self._build_task_prompt(task, context)

        # Get API key based on provider
        api_key = self.llm_api_key
        if not api_key:
            # Fall back to environment variables
            env_vars = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
                "groq": "GROQ_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "together": "TOGETHER_API_KEY",
                "mistral": "MISTRAL_API_KEY",
            }
            api_key = os.environ.get(env_vars.get(self.llm_provider, "OPENAI_API_KEY"), "")

        try:
            # Create the autonomous agent
            agent = AutonomousAgent(
                workspace_path=self.workspace_path,
                api_key=api_key,
                provider=self.llm_provider,
                model=self.llm_model,
            )

            # Track the agent for cleanup
            agent_id = f"agent_{task.id}_{uuid.uuid4().hex[:8]}"
            self.active_agents[agent_id] = {
                "agent": agent,
                "task_id": str(task.id),
                "started_at": start_time,
            }

            # Execute the task
            result_text = ""
            tool_calls = []
            iterations = 0
            verification_passed = False
            error_message = None

            async for event in agent.execute_task(
                request=task_prompt,
                run_verification=bool(task.verification_criteria),
            ):
                event_type = event.get("type", "")

                if event_type == "text":
                    result_text += event.get("text", "")
                elif event_type == "tool_call":
                    tool_calls.append(event.get("tool_call", {}))
                elif event_type == "iteration":
                    iterations = event.get("iteration", {}).get("current", 0)
                elif event_type == "verification":
                    results = event.get("results", [])
                    verification_passed = all(r.get("passed", False) for r in results)
                elif event_type == "complete":
                    break
                elif event_type == "error":
                    error_message = event.get("error", "Unknown error")
                    break

            # Clean up agent tracking
            self.active_agents.pop(agent_id, None)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # If no explicit verification, check based on error presence
            if not task.verification_criteria:
                verification_passed = error_message is None

            if error_message:
                return {
                    "success": False,
                    "task_id": str(task.id),
                    "error": error_message,
                    "outputs": {
                        "completed_at": end_time.isoformat(),
                        "verification_passed": False,
                        "result_text": result_text,
                    },
                    "metrics": {
                        "duration_seconds": duration,
                        "iterations": iterations,
                        "tool_calls": len(tool_calls),
                    },
                }

            return {
                "success": verification_passed,
                "task_id": str(task.id),
                "outputs": {
                    "completed_at": end_time.isoformat(),
                    "verification_passed": verification_passed,
                    "result_text": result_text,
                    "tool_calls": tool_calls,
                },
                "metrics": {
                    "duration_seconds": duration,
                    "iterations": iterations,
                    "tool_calls": len(tool_calls),
                },
            }

        except Exception as e:
            logger.exception(f"Agent execution failed for task {task.id}: {e}")
            return {
                "success": False,
                "task_id": str(task.id),
                "error": str(e),
                "outputs": {
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "verification_passed": False,
                },
                "metrics": {
                    "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                    "iterations": 0,
                },
            }

    def _build_task_prompt(
        self,
        task: ProjectTaskQueue,
        context: TaskExecutionContext,
    ) -> str:
        """Build a detailed prompt for the agent to execute the task."""

        prompt = f"""# Task: {task.title}

## Description
{task.description}

## Priority
{task.priority}/100 (higher is more important)

## Context
- Project ID: {context.project_id}
- Workspace: {context.workspace_path}
- Dependencies completed: {', '.join(context.dependencies_completed) if context.dependencies_completed else 'None'}

"""

        if task.verification_criteria:
            prompt += "## Verification Criteria\n"
            for i, criterion in enumerate(task.verification_criteria, 1):
                prompt += f"{i}. {criterion}\n"
            prompt += "\n"

        if task.outputs:
            prompt += "## Expected Outputs\n"
            if task.outputs.get("files_created"):
                prompt += f"Files to create: {', '.join(task.outputs['files_created'])}\n"
            if task.outputs.get("files_modified"):
                prompt += f"Files to modify: {', '.join(task.outputs['files_modified'])}\n"
            if task.outputs.get("commands_to_verify"):
                prompt += f"Commands to verify: {', '.join(task.outputs['commands_to_verify'])}\n"
            prompt += "\n"

        prompt += """## Instructions
1. Complete the task as described above
2. Ensure all verification criteria are met
3. Create or modify the expected files
4. Run verification commands if specified
5. Report any issues or blockers

Begin executing the task now.
"""

        return prompt

    async def _handle_task_failure(
        self,
        project_id: str,
        state: CoordinatorState,
        task_id: str,
        failure_result: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handle a failed task with retry or escalation."""

        error_msg = failure_result.get("error", "Unknown error")
        logger.warning(f"Task {task_id} failed: {error_msg}")

        # Check retry policy
        task = self.db.query(ProjectTaskQueue).filter(
            ProjectTaskQueue.id == task_id
        ).first()

        retry_count = (task.outputs or {}).get("retry_count", 0) if task else 0
        max_retries = 3

        if retry_count < max_retries:
            # Retry the task
            yield {
                "type": "task_retry",
                "project_id": project_id,
                "task_id": task_id,
                "retry_count": retry_count + 1,
                "max_retries": max_retries,
                "error": error_msg,
            }

            await self.project_service.update_task_status(
                task_id, "pending",
                outputs={"retry_count": retry_count + 1, "last_error": error_msg}
            )
        else:
            # Max retries exceeded - escalate
            state.failed_tasks.append(task_id)

            yield {
                "type": "task_failed",
                "project_id": project_id,
                "task_id": task_id,
                "error": error_msg,
                "action": "escalated",
            }

            await self.project_service.update_task_status(
                task_id, "failed",
                completed_at=datetime.now(timezone.utc),
                outputs={"error": error_msg, "retry_count": retry_count}
            )

            # Create human gate for escalation
            gate = await self.project_service.create_human_gate(
                project_id=project_id,
                gate_type="task_failure_escalation",
                title=f"Task Failed: {task.title if task else task_id}",
                description=f"Task failed after {max_retries} retries. Error: {error_msg}",
                options=[
                    {"id": "retry", "label": "Retry Task", "trade_offs": "May fail again"},
                    {"id": "skip", "label": "Skip Task", "trade_offs": "May affect dependent tasks"},
                    {"id": "abort", "label": "Abort Project", "trade_offs": "Stops all execution"},
                ],
            )

            state.pending_gates.append(str(gate.id))

            yield {
                "type": "gate_triggered",
                "project_id": project_id,
                "gate_id": str(gate.id),
                "gate_type": "task_failure_escalation",
                "blocking": True,
            }

    async def _check_human_gates(
        self,
        project_id: str,
        state: CoordinatorState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Check for and process any pending human checkpoint gates."""

        # Get pending gates from service
        pending_gates = await self.project_service.get_pending_gates(project_id)

        for gate in pending_gates:
            gate_id = str(gate.id)

            if gate.status == "approved":
                # Gate was resolved
                state.pending_gates = [g for g in state.pending_gates if g != gate_id]

                yield {
                    "type": "gate_resolved",
                    "project_id": project_id,
                    "gate_id": gate_id,
                    "decision": gate.chosen_option_id,
                    "reason": gate.decision_reason,
                }

                # Handle the decision
                if gate.gate_type == "task_failure_escalation":
                    if gate.chosen_option_id == "retry":
                        # Reset the failed task for retry
                        # (would need to track which task triggered the gate)
                        pass
                    elif gate.chosen_option_id == "abort":
                        state.status = "failed"
                        yield {
                            "type": "project_aborted",
                            "project_id": project_id,
                            "reason": "User requested abort",
                        }

    async def _detect_conflicts(
        self,
        results: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between parallel task results."""

        conflicts = []

        # Check for file modification conflicts
        modified_files = {}
        for task_id, result in results.items():
            if not result.get("success"):
                continue

            files = result.get("outputs", {}).get("modified_files", [])
            for file_path in files:
                if file_path in modified_files:
                    conflicts.append({
                        "type": "file_conflict",
                        "file": file_path,
                        "tasks": [modified_files[file_path], task_id],
                    })
                else:
                    modified_files[file_path] = task_id

        return conflicts

    async def _resolve_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        results: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Resolve conflicts between task results."""

        resolutions = []

        for conflict in conflicts:
            if conflict["type"] == "file_conflict":
                # Use the fleet's conflict resolution
                resolution = await self.fleet.resolve_agent_conflict(
                    conflicting_agents=conflict["tasks"],
                    conflict_type="resource",
                    description=f"Both tasks modified {conflict['file']}",
                    proposed_solutions=[
                        {"id": "merge", "label": "Merge changes"},
                        {"id": "first_wins", "label": "Keep first task's changes"},
                        {"id": "last_wins", "label": "Keep last task's changes"},
                    ],
                    strategy=ConflictResolutionStrategy.PERFORMANCE_BASED,
                )

                resolutions.append({
                    "conflict": conflict,
                    "resolution": resolution,
                })

        return resolutions

    def _needs_checkpoint(self, state: CoordinatorState) -> bool:
        """Check if a checkpoint is needed based on time interval."""

        if not state.last_checkpoint:
            return True

        elapsed = datetime.now(timezone.utc) - state.last_checkpoint
        return elapsed.total_seconds() >= state.checkpoint_interval_minutes * 60

    async def _create_checkpoint(
        self,
        project_id: str,
        state: CoordinatorState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Create a checkpoint of current execution state."""

        checkpoint_data = {
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": state.iteration_count,
            "completed_tasks": state.completed_tasks.copy(),
            "failed_tasks": state.failed_tasks.copy(),
            "pending_tasks": state.pending_tasks.copy(),
            "pending_gates": state.pending_gates.copy(),
        }

        # Would persist checkpoint to database
        state.last_checkpoint = datetime.now(timezone.utc)

        yield {
            "type": "checkpoint_created",
            "project_id": project_id,
            "checkpoint": checkpoint_data,
        }

        await self._fire_event("checkpoint_created", checkpoint_data)

    async def _get_remaining_tasks(self, project_id: str) -> List[str]:
        """Get IDs of tasks that are not yet completed."""

        tasks = self.db.query(ProjectTaskQueue).filter(
            ProjectTaskQueue.project_id == project_id,
            ProjectTaskQueue.status.notin_(["completed", "skipped"])
        ).all()

        return [str(t.id) for t in tasks]

    async def _cleanup_agents(self, project_id: str) -> None:
        """Clean up agents when project execution ends."""

        state = self.project_states.get(project_id)
        if state:
            # Cancel any active agents
            for task_id, agent_id in list(state.active_agents.items()):
                logger.info(f"Cleaning up agent {agent_id} for task {task_id}")
                # Would actually terminate agent processes here

            state.active_agents.clear()

    async def pause_project(self, project_id: str, reason: str = "Manual pause") -> bool:
        """Pause project execution."""

        state = self.project_states.get(project_id)
        if not state:
            return False

        state.status = "paused"

        await self.project_service.update_project(
            project_id, status="paused"
        )

        await self._fire_event("project_paused", {
            "project_id": project_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"Project {project_id} paused: {reason}")
        return True

    async def resume_project(self, project_id: str) -> bool:
        """Resume paused project execution."""

        state = self.project_states.get(project_id)
        if not state or state.status != "paused":
            return False

        state.status = "running"

        await self.project_service.update_project(
            project_id, status="active"
        )

        await self._fire_event("project_resumed", {
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"Project {project_id} resumed")
        return True

    async def get_project_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of project execution."""

        state = self.project_states.get(project_id)
        if not state:
            return None

        # Get fleet status
        fleet_status = await self.fleet.get_fleet_status()

        # Calculate progress
        total_tasks = len(state.completed_tasks) + len(state.failed_tasks) + len(state.pending_tasks)
        if total_tasks > 0:
            progress = len(state.completed_tasks) / total_tasks * 100
        else:
            progress = 0

        runtime_seconds = 0
        if state.start_time:
            runtime_seconds = (datetime.now(timezone.utc) - state.start_time).total_seconds()

        return {
            "project_id": project_id,
            "status": state.status,
            "progress_percent": round(progress, 1),
            "completed_tasks": len(state.completed_tasks),
            "failed_tasks": len(state.failed_tasks),
            "pending_tasks": len(state.pending_tasks),
            "active_agents": len(state.active_agents),
            "pending_gates": len(state.pending_gates),
            "iteration_count": state.iteration_count,
            "runtime_seconds": runtime_seconds,
            "runtime_hours": round(runtime_seconds / 3600, 2),
            "last_checkpoint": state.last_checkpoint.isoformat() if state.last_checkpoint else None,
            "fleet_status": {
                "total_agents": fleet_status.get("fleet_metrics", {}).get("total_agents", 0),
                "active_agents": fleet_status.get("fleet_metrics", {}).get("active_agents", 0),
            },
        }

    async def _fire_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Fire event to registered callbacks."""

        callbacks = self.event_callbacks.get(event_type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)
            except Exception as e:
                logger.error(f"Event callback failed for {event_type}: {e}")


# Convenience functions for API integration

async def create_coordinator(db_session, max_agents: int = 5) -> EnterpriseAgentCoordinator:
    """Factory function to create a coordinator instance."""
    return EnterpriseAgentCoordinator(db_session, max_parallel_agents=max_agents)


async def execute_enterprise_project(
    db_session,
    project_id: str,
    execution_mode: str = "hybrid",
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    High-level function to execute an enterprise project.

    Args:
        db_session: Database session
        project_id: EnterpriseProject ID
        execution_mode: "sequential", "parallel", or "hybrid"
        progress_callback: Optional callback for progress updates

    Returns:
        Execution result summary
    """
    coordinator = EnterpriseAgentCoordinator(db_session)

    if progress_callback:
        coordinator.register_event_callback("task_completed", progress_callback)
        coordinator.register_event_callback("task_failed", progress_callback)
        coordinator.register_event_callback("gate_triggered", progress_callback)

    mode = ExecutionMode(execution_mode)
    final_result = {}

    async for event in coordinator.start_project_execution(project_id, mode):
        if progress_callback:
            progress_callback(event)

        if event.get("type") in ["project_completed", "project_failed", "project_aborted"]:
            final_result = event

    return final_result
