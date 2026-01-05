"""
Execution Scheduler — Orchestrates Task Execution

Manages the execution of tasks in the plan graph, coordinating with human collaborators
and ensuring safe, step-by-step progress with proper approval gates.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from backend.agent.planning.plan_graph import PlanGraph, TaskNode
from backend.agent.planning.task_decomposer import DecomposedTask, TaskType


logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for the scheduler"""

    MANUAL = "MANUAL"  # Human approval for each task
    SEMI_AUTO = "SEMI_AUTO"  # Auto execution with approval gates
    AUTONOMOUS = "AUTONOMOUS"  # Full autonomous execution


@dataclass
class ExecutionContext:
    """Context for task execution"""

    initiative_id: str
    plan_id: str
    org_id: str
    owner: str
    execution_mode: ExecutionMode
    auto_approve_low_risk: bool = True
    max_parallel_tasks: int = 3
    execution_timeout_hours: int = 24
    retry_failed_tasks: bool = True
    max_retries: int = 2


class TaskExecutor:
    """Base class for task executors"""

    async def can_execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, str]:
        """Check if this executor can handle the task"""
        raise NotImplementedError

    async def execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute the task and return success status and results"""
        raise NotImplementedError


class AnalysisTaskExecutor(TaskExecutor):
    """Executes analysis and research tasks"""

    async def can_execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, str]:
        return task.task_type == TaskType.ANALYSIS, "Analysis task executor"

    async def execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute analysis task"""

        # Simulate analysis execution
        # In practice, this would:
        # 1. Gather relevant information
        # 2. Use AI agents to perform analysis
        # 3. Generate reports and findings

        logger.info(f"Executing analysis task: {task.title}")

        # Simulate work
        await asyncio.sleep(1)

        result = {
            "task_type": "analysis",
            "findings": f"Analysis completed for: {task.title}",
            "artifacts": ["analysis_report.md", "data_summary.json"],
            "recommendations": ["Continue with implementation based on findings"],
            "execution_time_seconds": 1,
        }

        return True, result


class CoordinationTaskExecutor(TaskExecutor):
    """Executes coordination tasks like approvals and meetings"""

    async def can_execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, str]:
        return task.task_type == TaskType.COORDINATION, "Coordination task executor"

    async def execute(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute coordination task"""

        logger.info(f"Executing coordination task: {task.title}")

        # For coordination tasks, we typically:
        # 1. Send notifications to relevant people
        # 2. Schedule meetings or create approval requests
        # 3. Wait for human input
        # 4. Record outcomes

        if task.approval_required:
            # This task requires human approval - mark as pending
            result = {
                "task_type": "coordination",
                "status": "pending_approval",
                "approvers": task.approvers,
                "message": f"Approval requested for: {task.title}",
            }
            return False, result  # Not completed yet, waiting for approval
        else:
            # Auto-complete simple coordination tasks
            result = {
                "task_type": "coordination",
                "status": "completed",
                "message": f"Coordination completed for: {task.title}",
                "execution_time_seconds": 0.1,
            }
            return True, result


class ExecutionScheduler:
    """Orchestrates task execution with proper coordination and approval gates"""

    def __init__(self):
        self.executors: List[TaskExecutor] = [
            AnalysisTaskExecutor(),
            CoordinationTaskExecutor(),
        ]
        self.active_executions: Dict[str, Dict[str, Any]] = {}

    def register_executor(self, executor: TaskExecutor) -> None:
        """Register a task executor"""
        self.executors.append(executor)

    async def execute_plan(
        self,
        plan_graph: PlanGraph,
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute the entire plan with proper orchestration"""

        logger.info(f"Starting plan execution for initiative {context.initiative_id}")

        execution_start = datetime.now(timezone.utc)
        execution_results = {
            "execution_id": f"exec_{execution_start.strftime('%Y%m%d_%H%M%S')}",
            "started_at": execution_start.isoformat(),
            "context": context.__dict__,
            "completed_tasks": [],
            "failed_tasks": [],
            "skipped_tasks": [],
            "total_tasks": len(plan_graph.nodes),
        }

        try:
            while not self._is_plan_complete(plan_graph):
                # Get tasks ready for execution
                ready_tasks = plan_graph.get_ready_tasks()

                if not ready_tasks:
                    # Check for blocked or failed tasks
                    blocked_tasks = plan_graph.get_blocked_tasks()
                    failed_tasks = plan_graph.get_failed_tasks()

                    if blocked_tasks or failed_tasks:
                        logger.warning(
                            f"Plan execution stalled. Blocked: {len(blocked_tasks)}, Failed: {len(failed_tasks)}"
                        )
                        break
                    else:
                        # No ready tasks but plan not complete - wait for ongoing executions
                        await asyncio.sleep(5)
                        continue

                # Execute tasks based on mode and constraints
                await self._execute_ready_tasks(
                    ready_tasks, plan_graph, context, progress_callback
                )

                # Small delay to prevent tight loops
                await asyncio.sleep(1)

            # Final summary
            execution_results["completed_at"] = datetime.now(timezone.utc).isoformat()
            execution_results["duration_seconds"] = (
                datetime.now(timezone.utc) - execution_start
            ).total_seconds()
            execution_results["progress_summary"] = plan_graph.get_progress_summary()

            logger.info(
                f"Plan execution completed for initiative {context.initiative_id}"
            )

        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            execution_results["error"] = str(e)
            execution_results["failed_at"] = datetime.now(timezone.utc).isoformat()

        return execution_results

    async def _execute_ready_tasks(
        self,
        ready_tasks: List[TaskNode],
        plan_graph: PlanGraph,
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]],
    ) -> None:
        """Execute ready tasks based on execution mode and constraints"""

        # Limit parallel execution
        max_parallel = min(context.max_parallel_tasks, len(ready_tasks))
        tasks_to_execute = ready_tasks[:max_parallel]

        # Filter tasks based on execution mode
        if context.execution_mode == ExecutionMode.MANUAL:
            # In manual mode, only execute tasks with explicit approval
            tasks_to_execute = [
                task
                for task in tasks_to_execute
                if not task.task.approval_required or task.approval_status == "approved"
            ]
        elif context.execution_mode == ExecutionMode.SEMI_AUTO:
            # In semi-auto mode, auto-approve low-risk tasks if enabled
            if context.auto_approve_low_risk:
                for task in tasks_to_execute:
                    if self._is_low_risk_task(task) and task.approval_status is None:
                        plan_graph.set_task_approval(
                            task.task.id, True, "system_auto_approval"
                        )

        # Execute tasks in parallel
        if tasks_to_execute:
            await asyncio.gather(
                *[
                    self._execute_single_task(
                        task, plan_graph, context, progress_callback
                    )
                    for task in tasks_to_execute
                ]
            )

    async def _execute_single_task(
        self,
        task_node: TaskNode,
        plan_graph: PlanGraph,
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]],
    ) -> None:
        """Execute a single task"""

        task_id = task_node.task.id

        try:
            # Check if task can be executed
            can_execute, reason = plan_graph.can_execute_task(task_id)
            if not can_execute:
                logger.info(f"Task {task_id} cannot be executed: {reason}")

                # If it's an approval issue, mark as blocked
                if "approval" in reason.lower():
                    plan_graph.block_task(task_id, reason)

                return

            # Start task execution
            plan_graph.start_task(task_id, assignee="autonomous_scheduler")

            if progress_callback:
                progress_callback(
                    "task_started", {"task_id": task_id, "task": task_node.to_dict()}
                )

            # Find appropriate executor
            executor = await self._find_executor(task_node.task, context)
            if not executor:
                error_msg = (
                    f"No executor found for task type {task_node.task.task_type.value}"
                )
                plan_graph.fail_task(task_id, error_msg)
                logger.error(f"Task {task_id} failed: {error_msg}")

                if progress_callback:
                    progress_callback(
                        "task_failed", {"task_id": task_id, "reason": error_msg}
                    )

                return

            # Execute the task with timeout
            try:
                success, result = await asyncio.wait_for(
                    executor.execute(task_node.task, context),
                    timeout=context.execution_timeout_hours * 3600,
                )

                if success:
                    plan_graph.complete_task(task_id, result)
                    logger.info(f"Task {task_id} completed successfully")

                    if progress_callback:
                        progress_callback(
                            "task_completed", {"task_id": task_id, "result": result}
                        )
                else:
                    # Task didn't complete (e.g., waiting for approval)
                    if result.get("status") == "pending_approval":
                        plan_graph.block_task(task_id, "Waiting for approval")

                        if progress_callback:
                            progress_callback(
                                "task_pending_approval",
                                {
                                    "task_id": task_id,
                                    "approvers": result.get("approvers", []),
                                },
                            )
                    else:
                        plan_graph.fail_task(
                            task_id, result.get("error", "Execution failed")
                        )

                        if progress_callback:
                            progress_callback(
                                "task_failed",
                                {
                                    "task_id": task_id,
                                    "reason": result.get("error", "Execution failed"),
                                },
                            )

            except asyncio.TimeoutError:
                error_msg = f"Task execution timed out after {context.execution_timeout_hours} hours"
                plan_graph.fail_task(task_id, error_msg)
                logger.error(f"Task {task_id} failed: {error_msg}")

                if progress_callback:
                    progress_callback("task_timeout", {"task_id": task_id})

        except Exception as e:
            error_msg = f"Unexpected error during task execution: {str(e)}"
            plan_graph.fail_task(task_id, error_msg)
            logger.error(f"Task {task_id} failed: {error_msg}")

            if progress_callback:
                progress_callback(
                    "task_error", {"task_id": task_id, "error": error_msg}
                )

    async def _find_executor(
        self, task: DecomposedTask, context: ExecutionContext
    ) -> Optional[TaskExecutor]:
        """Find an appropriate executor for the task"""

        for executor in self.executors:
            can_execute, _ = await executor.can_execute(task, context)
            if can_execute:
                return executor

        return None

    def _is_low_risk_task(self, task_node: TaskNode) -> bool:
        """Determine if a task is low risk and can be auto-approved"""

        task = task_node.task

        # Low risk criteria:
        # - Not critical priority
        # - Analysis or documentation tasks
        # - Short estimated duration
        # - No deployment or coordination

        if task.priority.value == "CRITICAL":
            return False

        if task.task_type in [TaskType.DEPLOYMENT, TaskType.COORDINATION]:
            return False

        if task.estimated_hours > 8:  # More than 1 day
            return False

        return True

    def _is_plan_complete(self, plan_graph: PlanGraph) -> bool:
        """Check if plan execution is complete"""

        progress = plan_graph.get_progress_summary()

        # Plan is complete if all tasks are in a terminal state
        terminal_states = ["COMPLETED", "SKIPPED", "FAILED"]
        non_terminal_count = sum(
            count
            for status, count in progress["status_counts"].items()
            if status not in terminal_states
        )

        return non_terminal_count == 0

    def get_execution_status(self, plan_graph: PlanGraph) -> Dict[str, Any]:
        """Get current execution status"""

        progress = plan_graph.get_progress_summary()

        return {
            "progress": progress,
            "ready_tasks": [node.to_dict() for node in plan_graph.get_ready_tasks()],
            "blocked_tasks": [
                node.to_dict() for node in plan_graph.get_blocked_tasks()
            ],
            "failed_tasks": [node.to_dict() for node in plan_graph.get_failed_tasks()],
            "tasks_needing_approval": [
                node.to_dict() for node in plan_graph.get_tasks_needing_approval()
            ],
            "active_executions": len(self.active_executions),
        }

    async def pause_execution(self, execution_id: str) -> bool:
        """Pause an ongoing execution"""

        if execution_id in self.active_executions:
            self.active_executions[execution_id]["paused"] = True
            logger.info(f"Execution {execution_id} paused")
            return True

        return False

    async def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused execution"""

        if execution_id in self.active_executions:
            self.active_executions[execution_id]["paused"] = False
            logger.info(f"Execution {execution_id} resumed")
            return True

        return False
