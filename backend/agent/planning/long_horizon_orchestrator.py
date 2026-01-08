"""
Long-Horizon Orchestrator — Initiative-Level Autonomy

The main coordinator for Phase 4.9, integrating all planning components to enable
true autonomous execution of long-horizon engineering initiatives.

This transforms NAVI from a "smart executor" to a complete engineering OS.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid

from backend.agent.planning.initiative_store import (
    InitiativeStore,
    Initiative,
    InitiativeStatus,
)
from backend.agent.planning.task_decomposer import TaskDecomposer
from backend.agent.planning.plan_graph import PlanGraph
from backend.agent.planning.execution_scheduler import (
    ExecutionScheduler,
    ExecutionContext,
    ExecutionMode,
)
from backend.agent.planning.checkpoint_engine import CheckpointEngine, CheckpointType
from backend.agent.planning.adaptive_replanner import AdaptiveReplanner
from backend.database.models.live_plan import LivePlan


logger = logging.getLogger(__name__)


class OrchestrationMode(Enum):
    """Modes of orchestration"""

    DEVELOPMENT = "DEVELOPMENT"  # Safe mode with extensive approval gates
    PRODUCTION = "PRODUCTION"  # Balanced autonomy with key checkpoints
    AUTONOMOUS = "AUTONOMOUS"  # Maximum autonomy for trusted environments


@dataclass
class InitiativeConfig:
    """Configuration for initiative execution"""

    orchestration_mode: OrchestrationMode
    auto_checkpoint_interval_minutes: int = 30
    max_execution_hours: int = 168  # 1 week default
    auto_approve_low_risk: bool = True
    require_milestone_approval: bool = True
    max_replan_attempts: int = 3
    enable_adaptive_replanning: bool = True
    notification_webhooks: List[str] = field(default_factory=list)


class LongHorizonOrchestrator:
    """
    The main orchestrator for autonomous engineering initiatives.

    Coordinates all Phase 4.9 components to enable weeks-long autonomous execution
    with proper human oversight and adaptive replanning.
    """

    def __init__(self, db_session):
        self.db = db_session

        # Initialize all components
        self.initiative_store = InitiativeStore(db_session)
        self.task_decomposer = TaskDecomposer()
        self.execution_scheduler = ExecutionScheduler()
        self.checkpoint_engine = CheckpointEngine(db_session)
        self.adaptive_replanner = AdaptiveReplanner()

        # Active orchestrations
        self.active_orchestrations: Dict[str, Dict[str, Any]] = {}

        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = {
            "initiative_started": [],
            "initiative_completed": [],
            "initiative_failed": [],
            "milestone_reached": [],
            "replan_triggered": [],
            "approval_needed": [],
            "checkpoint_created": [],
        }

    def register_event_callback(self, event_type: str, callback: Callable) -> None:
        """Register callback for orchestration events"""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)

    async def start_initiative(
        self,
        goal: str,
        context: Dict[str, Any],
        org_id: str,
        owner: str,
        config: Optional[InitiativeConfig] = None,
        jira_key: Optional[str] = None,
    ) -> str:
        """
        Start a new long-horizon initiative

        Returns: Initiative ID
        """

        config = config or InitiativeConfig(OrchestrationMode.DEVELOPMENT)

        logger.info(f"Starting new initiative: {goal[:100]}...")

        try:
            # Step 1: Create initiative record
            initiative_id = f"initiative_{uuid.uuid4().hex[:12]}"

            # Step 2: Decompose goal into tasks
            decomposition = await self.task_decomposer.decompose_goal(
                goal=goal, context=context, org_id=org_id, owner=owner
            )

            # Step 3: Create plan graph
            plan_graph = PlanGraph(decomposition.tasks)

            # Step 4: Create live plan for collaboration
            live_plan_data = self.task_decomposer.create_live_plan(
                Initiative(
                    id=initiative_id,
                    title=f"Initiative: {goal[:50]}...",
                    goal=goal,
                    status=InitiativeStatus.PLANNED,
                    plan_id="",  # Will be set after creation
                    checkpoints=[],
                    owner=owner,
                    org_id=org_id,
                    jira_key=jira_key,
                ),
                decomposition,
            )

            # Create LivePlan in database
            live_plan = LivePlan(
                title=live_plan_data["title"],
                description=live_plan_data["description"],
                steps=live_plan_data["steps"],
                participants=live_plan_data["participants"],
                org_id=org_id,
                metadata=live_plan_data["metadata"],
            )

            self.db.add(live_plan)
            self.db.flush()  # Get the ID

            # Step 5: Create initiative with plan reference
            initiative = Initiative(
                id=initiative_id,
                title=str(live_plan.title),
                goal=goal,
                status=InitiativeStatus.PLANNED,
                plan_id=str(live_plan.id),
                checkpoints=[],
                owner=owner,
                org_id=org_id,
                jira_key=jira_key,
                metadata={
                    "config": config.__dict__,
                    "context": context,
                    "decomposition_summary": {
                        "total_tasks": len(decomposition.tasks),
                        "estimated_hours": decomposition.total_estimated_hours,
                        "suggested_timeline_weeks": decomposition.suggested_timeline_weeks,
                        "risks": decomposition.risks,
                        "assumptions": decomposition.assumptions,
                    },
                },
            )

            self.initiative_store.save_initiative(initiative)
            self.db.commit()

            # Step 6: Create initial checkpoint
            checkpoint_id = self.checkpoint_engine.create_checkpoint(
                initiative_id=initiative_id,
                plan_graph=plan_graph,
                execution_context=ExecutionContext(
                    initiative_id=initiative_id,
                    plan_id=str(live_plan.id),
                    org_id=org_id,
                    owner=owner,
                    execution_mode=self._get_execution_mode(config.orchestration_mode),
                    auto_approve_low_risk=config.auto_approve_low_risk,
                    execution_timeout_hours=config.max_execution_hours,
                ),
                checkpoint_type=CheckpointType.MILESTONE,
                description="Initiative planning completed",
                created_by=owner,
            )

            # Step 7: Update initiative with checkpoint
            self.initiative_store.add_checkpoint(initiative_id, checkpoint_id)

            # Step 8: Initialize orchestration state
            self.active_orchestrations[initiative_id] = {
                "initiative": initiative,
                "plan_graph": plan_graph,
                "config": config,
                "live_plan_id": live_plan.id,
                "current_checkpoint": checkpoint_id,
                "start_time": datetime.now(timezone.utc),
                "status": "planned",
                "replan_count": 0,
            }

            # Step 9: Fire events
            await self._fire_event(
                "initiative_started",
                {
                    "initiative_id": initiative_id,
                    "goal": goal,
                    "estimated_timeline_weeks": decomposition.suggested_timeline_weeks,
                    "total_tasks": len(decomposition.tasks),
                },
            )

            logger.info(f"Initiative {initiative_id} created successfully")

            return initiative_id

        except Exception as e:
            logger.error(f"Failed to start initiative: {e}")
            self.db.rollback()
            raise

    async def execute_initiative(
        self,
        initiative_id: str,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an initiative with full autonomous orchestration

        This is the main method that enables long-horizon execution
        """

        if initiative_id not in self.active_orchestrations:
            raise ValueError(f"Initiative {initiative_id} not found or not active")

        orchestration = self.active_orchestrations[initiative_id]
        initiative = orchestration["initiative"]
        plan_graph = orchestration["plan_graph"]
        config = orchestration["config"]

        logger.info(f"Starting execution of initiative {initiative_id}")

        # Update initiative status
        self.initiative_store.update_initiative_status(
            initiative_id, InitiativeStatus.IN_PROGRESS
        )
        orchestration["status"] = "executing"

        try:
            # Create execution context
            execution_context = ExecutionContext(
                initiative_id=initiative_id,
                plan_id=orchestration["live_plan_id"],
                org_id=initiative.org_id,
                owner=initiative.owner,
                execution_mode=self._get_execution_mode(config.orchestration_mode),
                auto_approve_low_risk=config.auto_approve_low_risk,
                max_parallel_tasks=3,
                execution_timeout_hours=config.max_execution_hours,
                retry_failed_tasks=True,
            )

            # Create enhanced progress callback
            enhanced_callback = self._create_enhanced_callback(
                initiative_id, progress_callback
            )

            # Main execution loop with monitoring
            execution_result = await self._execute_with_monitoring(
                initiative_id, plan_graph, execution_context, config, enhanced_callback
            )

            # Final status update
            if execution_result.get("success", False):
                self.initiative_store.update_initiative_status(
                    initiative_id,
                    InitiativeStatus.DONE,
                    completed_at=datetime.now(timezone.utc),
                )

                await self._fire_event(
                    "initiative_completed",
                    {
                        "initiative_id": initiative_id,
                        "execution_result": execution_result,
                    },
                )

                logger.info(f"Initiative {initiative_id} completed successfully")
            else:
                self.initiative_store.update_initiative_status(
                    initiative_id, InitiativeStatus.BLOCKED
                )

                await self._fire_event(
                    "initiative_failed",
                    {
                        "initiative_id": initiative_id,
                        "failure_reason": execution_result.get(
                            "error", "Unknown error"
                        ),
                    },
                )

                logger.error(f"Initiative {initiative_id} execution failed")

            return execution_result

        except Exception as e:
            logger.error(f"Initiative {initiative_id} execution failed: {e}")

            # Update status to failed
            self.initiative_store.update_initiative_status(
                initiative_id, InitiativeStatus.BLOCKED
            )

            await self._fire_event(
                "initiative_failed",
                {
                    "initiative_id": initiative_id,
                    "failure_reason": str(e),
                    "exception_type": type(e).__name__,
                },
            )

            return {
                "success": False,
                "error": str(e),
                "initiative_id": initiative_id,
            }

    async def pause_initiative(
        self, initiative_id: str, reason: str = "Manual pause"
    ) -> bool:
        """Pause an active initiative"""

        if initiative_id not in self.active_orchestrations:
            return False

        orchestration = self.active_orchestrations[initiative_id]

        # Create pause checkpoint
        checkpoint_id = self.checkpoint_engine.pause_execution(
            initiative_id=initiative_id,
            plan_graph=orchestration["plan_graph"],
            execution_context=ExecutionContext(
                initiative_id=initiative_id,
                plan_id=orchestration["live_plan_id"],
                org_id=orchestration["initiative"].org_id,
                owner=orchestration["initiative"].owner,
                execution_mode=ExecutionMode.MANUAL,  # Safe mode when pausing
            ),
            reason=reason,
        )

        # Update status
        self.initiative_store.update_initiative_status(
            initiative_id, InitiativeStatus.PAUSED
        )

        orchestration["status"] = "paused"
        orchestration["current_checkpoint"] = checkpoint_id

        logger.info(f"Initiative {initiative_id} paused: {reason}")
        return True

    async def resume_initiative(
        self, initiative_id: str, checkpoint_id: Optional[str] = None
    ) -> bool:
        """Resume a paused initiative"""

        if initiative_id not in self.active_orchestrations:
            return False

        orchestration = self.active_orchestrations[initiative_id]

        # Restore from checkpoint if specified
        if checkpoint_id:
            try:
                (
                    plan_graph,
                    execution_context,
                    checkpoint_metadata,
                ) = self.checkpoint_engine.restore_checkpoint(checkpoint_id)

                orchestration["plan_graph"] = plan_graph
                orchestration["current_checkpoint"] = checkpoint_id

                logger.info(
                    f"Restored initiative {initiative_id} from checkpoint {checkpoint_id}"
                )

            except Exception as e:
                logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}")
                return False

        # Update status
        self.initiative_store.update_initiative_status(
            initiative_id, InitiativeStatus.IN_PROGRESS
        )

        orchestration["status"] = "executing"

        logger.info(f"Initiative {initiative_id} resumed")
        return True

    async def _execute_with_monitoring(
        self,
        initiative_id: str,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        config: InitiativeConfig,
        progress_callback: Callable,
    ) -> Dict[str, Any]:
        """Execute with continuous monitoring and adaptive replanning"""

        orchestration = self.active_orchestrations[initiative_id]
        last_checkpoint_time = datetime.now(timezone.utc)

        while True:
            # Check if execution is complete
            if self._is_execution_complete(plan_graph):
                return {
                    "success": True,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "final_progress": plan_graph.get_progress_summary(),
                }

            # Check for replanning needs
            if config.enable_adaptive_replanning:
                (
                    needs_replan,
                    replan_context,
                ) = self.adaptive_replanner.evaluate_replan_need(
                    plan_graph, execution_context
                )

                if needs_replan:
                    trigger_info = (
                        replan_context.trigger.value
                        if replan_context
                        and hasattr(replan_context, "trigger")
                        and replan_context.trigger
                        else "unknown"
                    )
                    logger.info(
                        f"Replanning triggered for {initiative_id}: {trigger_info}"
                    )

                    # Attempt replanning
                    replan_result = await self._handle_replanning(
                        initiative_id,
                        plan_graph,
                        execution_context,
                        replan_context,
                        config,
                    )

                    if replan_result.success and replan_result.new_plan_graph:
                        plan_graph = replan_result.new_plan_graph
                        orchestration["plan_graph"] = plan_graph
                        orchestration["replan_count"] += 1
                    elif orchestration["replan_count"] >= config.max_replan_attempts:
                        return {
                            "success": False,
                            "error": f"Max replan attempts ({config.max_replan_attempts}) exceeded",
                            "final_progress": plan_graph.get_progress_summary(),
                        }

            # Execute next batch of tasks
            try:
                # Run execution scheduler step
                await self._execute_scheduler_step(
                    plan_graph, execution_context, progress_callback
                )

                # Auto-checkpoint if needed
                if self.checkpoint_engine.auto_checkpoint_needed(
                    plan_graph,
                    last_checkpoint_time,
                    config.auto_checkpoint_interval_minutes,
                ):
                    checkpoint_id = self.checkpoint_engine.create_checkpoint(
                        initiative_id=initiative_id,
                        plan_graph=plan_graph,
                        execution_context=execution_context,
                        checkpoint_type=CheckpointType.AUTO,
                        description="Automatic checkpoint during execution",
                    )

                    last_checkpoint_time = datetime.now(timezone.utc)
                    orchestration["current_checkpoint"] = checkpoint_id

                # Small delay to prevent tight loops
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Execution step failed for {initiative_id}: {e}")

                # Create error checkpoint
                error_checkpoint = self.checkpoint_engine.create_checkpoint(
                    initiative_id=initiative_id,
                    plan_graph=plan_graph,
                    execution_context=execution_context,
                    checkpoint_type=CheckpointType.ERROR,
                    description=f"Error checkpoint: {str(e)}",
                )

                return {
                    "success": False,
                    "error": str(e),
                    "error_checkpoint": error_checkpoint,
                    "final_progress": plan_graph.get_progress_summary(),
                }

    async def _execute_scheduler_step(
        self,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        progress_callback: Callable,
    ) -> None:
        """Execute one step of the scheduler"""

        ready_tasks = plan_graph.get_ready_tasks()

        if ready_tasks:
            # Limit parallel execution
            tasks_to_run = ready_tasks[: execution_context.max_parallel_tasks]

            # Execute tasks in parallel
            await asyncio.gather(
                *[
                    self.execution_scheduler._execute_single_task(
                        task, plan_graph, execution_context, progress_callback
                    )
                    for task in tasks_to_run
                ]
            )

    async def _handle_replanning(
        self,
        initiative_id: str,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        replan_context: Any,
        config: InitiativeConfig,
    ) -> Any:
        """Handle replanning with proper approval workflow"""

        orchestration = self.active_orchestrations[initiative_id]
        initiative = orchestration["initiative"]

        # Create checkpoint before replanning
        self.checkpoint_engine.create_checkpoint(
            initiative_id=initiative_id,
            plan_graph=plan_graph,
            execution_context=execution_context,
            checkpoint_type=CheckpointType.MILESTONE,
            description=f"Pre-replan checkpoint: {replan_context.trigger.value}",
        )

        # Perform replanning
        replan_result = await self.adaptive_replanner.replan(
            initiative, plan_graph, execution_context, replan_context
        )

        # Record the replan attempt
        self.adaptive_replanner.record_replan(replan_result, initiative_id)

        # Fire replan event
        await self._fire_event(
            "replan_triggered",
            {
                "initiative_id": initiative_id,
                "trigger": replan_context.trigger.value,
                "replan_result": {
                    "success": replan_result.success,
                    "approval_required": replan_result.approval_required,
                    "changes_summary": replan_result.changes_summary,
                },
            },
        )

        # Handle approval if required
        if replan_result.approval_required:
            await self._fire_event(
                "approval_needed",
                {
                    "initiative_id": initiative_id,
                    "type": "replan_approval",
                    "replan_result": replan_result.__dict__,
                },
            )

            # In a full implementation, this would wait for human approval
            # For now, auto-approve in development mode
            if config.orchestration_mode == OrchestrationMode.DEVELOPMENT:
                logger.info(
                    f"Auto-approving replan for {initiative_id} (development mode)"
                )
                # Replan is approved by default in development
            else:
                logger.info(
                    f"Replan for {initiative_id} requires approval - pausing execution"
                )
                await self.pause_initiative(
                    initiative_id, "Waiting for replan approval"
                )

        return replan_result

    def _create_enhanced_callback(
        self, initiative_id: str, original_callback: Optional[Callable]
    ) -> Callable:
        """Create enhanced progress callback with orchestration awareness"""

        async def enhanced_callback(event_type: str, event_data: Dict[str, Any]):
            # Add orchestration context
            event_data["initiative_id"] = initiative_id
            event_data["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Log progress
            logger.info(f"Initiative {initiative_id} - {event_type}: {event_data}")

            # Call original callback if provided
            if original_callback:
                try:
                    if asyncio.iscoroutinefunction(original_callback):
                        await original_callback(event_type, event_data)
                    else:
                        original_callback(event_type, event_data)
                except Exception as e:
                    logger.error(f"Progress callback failed: {e}")

            # Handle milestone events
            if event_type == "task_completed":
                progress = self.active_orchestrations[initiative_id][
                    "plan_graph"
                ].get_progress_summary()
                if (
                    progress["progress_percent"] >= 25
                    and progress["progress_percent"] % 25 == 0
                ):
                    await self._fire_event(
                        "milestone_reached",
                        {
                            "initiative_id": initiative_id,
                            "milestone": f"{progress['progress_percent']}% complete",
                            "progress": progress,
                        },
                    )

        return enhanced_callback

    def _get_execution_mode(
        self, orchestration_mode: OrchestrationMode
    ) -> ExecutionMode:
        """Convert orchestration mode to execution mode"""

        if orchestration_mode == OrchestrationMode.DEVELOPMENT:
            return ExecutionMode.MANUAL
        elif orchestration_mode == OrchestrationMode.PRODUCTION:
            return ExecutionMode.SEMI_AUTO
        else:  # AUTONOMOUS
            return ExecutionMode.AUTONOMOUS

    def _is_execution_complete(self, plan_graph: PlanGraph) -> bool:
        """Check if execution is complete"""

        progress = plan_graph.get_progress_summary()
        terminal_states = ["COMPLETED", "SKIPPED"]

        total_tasks = progress["total_tasks"]
        terminal_tasks = sum(
            progress["status_counts"].get(state, 0) for state in terminal_states
        )

        return terminal_tasks == total_tasks

    async def _fire_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Fire orchestration event to registered callbacks"""

        callbacks = self.event_callbacks.get(event_type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)
            except Exception as e:
                logger.error(f"Event callback failed for {event_type}: {e}")

    def get_initiative_status(self, initiative_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive status of an initiative"""

        initiative = self.initiative_store.get_initiative(initiative_id)
        if not initiative:
            return None

        status_data = {
            "initiative": initiative.to_dict(),
            "is_active": initiative_id in self.active_orchestrations,
        }

        if initiative_id in self.active_orchestrations:
            orchestration = self.active_orchestrations[initiative_id]
            plan_graph = orchestration["plan_graph"]

            status_data.update(
                {
                    "progress": plan_graph.get_progress_summary(),
                    "execution_status": self.execution_scheduler.get_execution_status(
                        plan_graph
                    ),
                    "current_checkpoint": orchestration["current_checkpoint"],
                    "replan_count": orchestration["replan_count"],
                    "runtime_hours": (
                        datetime.now(timezone.utc) - orchestration["start_time"]
                    ).total_seconds()
                    / 3600,
                }
            )

        return status_data

    def list_active_initiatives(self, org_id: str) -> List[Dict[str, Any]]:
        """List all active initiatives for an organization"""

        active_initiatives = self.initiative_store.list_active_initiatives(org_id)

        return [
            {
                **initiative.to_dict(),
                "is_orchestrated": initiative.id in self.active_orchestrations,
                "orchestration_status": self.active_orchestrations.get(
                    initiative.id, {}
                ).get("status"),
            }
            for initiative in active_initiatives
        ]
