"""
Phase 5.0 — Closed-Loop Orchestrator (Master Autonomous Coordinator)

The brain of the autonomous engineering system that coordinates all Phase 5.0 components
into a cohesive closed-loop: Signal → Reason → Plan → Execute → Verify → Report → Learn → Repeat.

This is what makes NAVI a true autonomous engineering OS rather than just a chat bot.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback

# Phase 5.0 Components
from backend.agent.closedloop.event_ingestor import (
    EventIngestor,
    ProcessedEvent,
    EventSource,
    EventType,
)
from backend.agent.closedloop.context_resolver import ContextResolver, ResolvedContext
from backend.agent.closedloop.auto_planner import (
    AutoPlanner,
    ExecutionPlan,
    PlannedAction,
    ActionType,
)
from backend.agent.closedloop.execution_controller import (
    ExecutionController,
    ExecutionResult,
    ExecutionStatus,
)
from backend.agent.closedloop.verification_engine import (
    VerificationEngine,
    VerificationResult,
)
from backend.agent.closedloop.report_dispatcher import ReportDispatcher, GeneratedReport
from backend.agent.closedloop.loop_memory_updater import (
    LoopMemoryUpdater,
    LearningOutcome,
)

# Existing Infrastructure Integration
from backend.agent.execution_engine.core import ExecutionEngine
from backend.agent.planner_v3 import SimplePlanner
from backend.agent.tool_executor_real import RealToolExecutor
from backend.services.jira import JiraService


logger = logging.getLogger(__name__)


class OrchestrationMode(Enum):
    """Operating modes for the closed-loop orchestrator"""

    AUTONOMOUS = "autonomous"  # Fully autonomous operation
    SEMI_AUTONOMOUS = "semi_autonomous"  # Requires approval for risky actions
    SUPERVISED = "supervised"  # Human oversight for all actions
    MANUAL = "manual"  # Human-driven with AI assistance
    MONITORING = "monitoring"  # Event monitoring only, no actions


class LoopState(Enum):
    """States in the closed-loop lifecycle"""

    IDLE = "idle"  # Waiting for events
    INGESTING = "ingesting"  # Processing incoming events
    RESOLVING = "resolving"  # Building context
    PLANNING = "planning"  # Creating execution plan
    APPROVING = "approving"  # Waiting for human approval
    EXECUTING = "executing"  # Executing actions
    VERIFYING = "verifying"  # Quality verification
    REPORTING = "reporting"  # Communication and updates
    LEARNING = "learning"  # Memory updates and learning
    ERROR = "error"  # Error state requiring intervention
    ESCALATED = "escalated"  # Escalated to human


class SafetyLevel(Enum):
    """Safety assessment levels for autonomous actions"""

    SAFE = "safe"  # Can execute autonomously
    MODERATE_RISK = "moderate_risk"  # Requires approval
    HIGH_RISK = "high_risk"  # Requires supervisor approval
    DANGEROUS = "dangerous"  # Block autonomous execution


@dataclass
class LoopExecution:
    """Represents a single closed-loop execution cycle"""

    loop_id: str
    started_at: datetime

    # Pipeline stages
    triggering_event: Optional[ProcessedEvent] = None
    resolved_context: Optional[ResolvedContext] = None
    execution_plan: Optional[ExecutionPlan] = None
    execution_results: List[ExecutionResult] = field(default_factory=list)
    verification_results: List[VerificationResult] = field(default_factory=list)
    generated_reports: List[GeneratedReport] = field(default_factory=list)
    learning_outcomes: List[LearningOutcome] = field(default_factory=list)

    # State tracking
    current_state: LoopState = LoopState.IDLE
    orchestration_mode: OrchestrationMode = OrchestrationMode.SEMI_AUTONOMOUS
    safety_level: SafetyLevel = SafetyLevel.MODERATE_RISK

    # Progress and metrics
    progress: float = 0.0
    confidence_score: float = 0.0
    error_count: int = 0
    retry_count: int = 0

    # Completion tracking
    completed_at: Optional[datetime] = None
    final_status: Optional[str] = None
    total_duration_seconds: Optional[float] = None

    # Metadata
    user_id: Optional[str] = None
    workspace_path: Optional[str] = None
    org_id: Optional[str] = None
    session_id: Optional[str] = None

    # Error handling
    last_error: Optional[str] = None
    error_traceback: Optional[str] = None
    escalation_reason: Optional[str] = None


@dataclass
class OrchestrationConfig:
    """Configuration for closed-loop orchestration"""

    # Operating mode
    default_mode: OrchestrationMode = OrchestrationMode.SEMI_AUTONOMOUS
    orchestration_mode: OrchestrationMode = OrchestrationMode.SEMI_AUTONOMOUS
    safety_threshold: float = 0.7  # Minimum safety score for autonomous execution
    confidence_threshold: float = 0.8  # Minimum confidence for autonomous execution
    max_auto_risk_override: float = 0.7  # Max risk score for auto-execution

    # Event processing
    event_batch_size: int = 10
    event_processing_interval_seconds: int = 30
    max_concurrent_loops: int = 5

    # Timeouts and retries
    context_resolution_timeout_seconds: int = 120
    planning_timeout_seconds: int = 180
    execution_timeout_seconds: int = 600
    verification_timeout_seconds: int = 120
    max_retry_attempts: int = 3

    # Approval and escalation
    approval_timeout_minutes: int = 60
    escalation_after_failures: int = 2
    require_approval_for_destructive: bool = True
    require_approval_for_external_apis: bool = True

    # Learning and memory
    enable_learning: bool = True
    learning_batch_size: int = 20
    memory_maintenance_interval_hours: int = 24

    # Reporting
    report_all_executions: bool = True
    report_only_failures: bool = False
    notification_channels: List[str] = field(default_factory=lambda: ["slack", "jira"])

    # Safety and compliance
    enable_safety_checks: bool = True
    block_high_risk_actions: bool = True
    audit_trail_enabled: bool = True
    compliance_mode: bool = False


class ClosedLoopOrchestrator:
    """
    Master coordinator for Phase 5.0 Closed-Loop Autonomy

    This is the brain that orchestrates the complete autonomous engineering pipeline:
    Signal → Reason → Plan → Execute → Verify → Report → Learn → Repeat

    Key responsibilities:
    1. Coordinate all Phase 5.0 components in proper sequence
    2. Manage multiple concurrent loop executions
    3. Handle approval gates and safety checks
    4. Provide real-time progress tracking and reporting
    5. Integrate with existing NAVI infrastructure
    6. Maintain audit trails and compliance
    7. Learn and adapt from outcomes
    8. Escalate when human intervention is needed
    """

    def __init__(
        self,
        db_session,
        workspace_path: Optional[str] = None,
        org_key: str = "default",
        config: Optional[OrchestrationConfig] = None,
    ):
        self.db = db_session
        self.workspace_path = workspace_path
        self.org_key = org_key
        self.config = config or OrchestrationConfig()

        # Initialize Phase 5.0 components
        self.event_ingestor = EventIngestor(
            db_session=db_session,
            workspace_path=workspace_path,
        )
        self.context_resolver = ContextResolver(
            db_session,
            org_id=org_key,
            user_id="system",
        )
        self.auto_planner = AutoPlanner(db_session)
        self.execution_controller = ExecutionController(db_session, workspace_path)
        self.verification_engine = VerificationEngine(db_session, workspace_path)
        self.report_dispatcher = ReportDispatcher(db_session, workspace_path)
        self.loop_memory_updater = LoopMemoryUpdater(
            db_session, workspace_path, org_key
        )

        # Existing infrastructure integration
        self.execution_engine = ExecutionEngine() if db_session else None
        self.planner = SimplePlanner() if db_session else None
        self.tool_executor = RealToolExecutor(db_session) if db_session else None
        self.jira_service = JiraService if db_session else None
        self.slack_client = None

        # Loop management
        self.active_loops: Dict[str, LoopExecution] = {}
        self.completed_loops: Dict[str, LoopExecution] = {}
        self.max_history = 1000

        # Event queue and processing
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processing_loop_active = False
        self.shutdown_requested = False

        # Approval and escalation tracking
        self.pending_approvals: Dict[str, LoopExecution] = {}
        self.escalated_loops: Dict[str, LoopExecution] = {}

        # Performance metrics
        self.total_loops_processed = 0
        self.successful_loops = 0
        self.failed_loops = 0
        self.autonomous_success_rate = 0.0

        # Safety and compliance
        self.safety_violations: List[Dict[str, Any]] = []
        self.audit_log: List[Dict[str, Any]] = []

        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()

    async def start_orchestration(self) -> None:
        """Start the closed-loop orchestration system"""

        logger.info("🚀 Starting Phase 5.0 Closed-Loop Orchestration")

        try:
            # Start event processing loop
            if not self.processing_loop_active:
                task = asyncio.create_task(self._event_processing_loop())
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

            # Start periodic maintenance
            maintenance_task = asyncio.create_task(self._periodic_maintenance())
            self.background_tasks.add(maintenance_task)
            maintenance_task.add_done_callback(self.background_tasks.discard)

            # Initialize components
            await self._initialize_components()

            logger.info("✅ Closed-Loop Orchestration started successfully")

        except Exception as e:
            logger.error(f"Failed to start orchestration: {e}", exc_info=True)
            raise

    async def stop_orchestration(self) -> None:
        """Gracefully stop the orchestration system"""

        logger.info("🛑 Stopping Closed-Loop Orchestration")

        try:
            self.shutdown_requested = True

            # Complete active loops gracefully
            for loop_id in list(self.active_loops.keys()):
                await self._handle_loop_interruption(loop_id, "System shutdown")

            # Cancel background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)

            logger.info("✅ Closed-Loop Orchestration stopped gracefully")

        except Exception as e:
            logger.error(f"Error during orchestration shutdown: {e}", exc_info=True)

    async def ingest_external_event(
        self,
        source: EventSource,
        event_type: EventType,
        event_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Ingest an external event into the closed-loop system

        This is the main entry point for external triggers (Jira, Slack, GitHub, CI, etc.)
        """

        try:
            # Process event through EventIngestor
            processed_event = await self.event_ingestor.process_event(
                source, event_type, event_data, metadata
            )

            if processed_event:
                # Queue for processing
                await self.event_queue.put(processed_event)

                logger.info(
                    f"Queued event {processed_event.event_id} from {source.value}"
                )
                return processed_event.event_id
            else:
                logger.warning(f"Event from {source.value} was filtered out")
                return ""

        except Exception as e:
            logger.error(
                f"Failed to ingest event from {source.value}: {e}", exc_info=True
            )
            raise

    async def execute_closed_loop(
        self,
        triggering_event: ProcessedEvent,
        orchestration_mode: Optional[OrchestrationMode] = None,
        user_id: Optional[str] = None,
    ) -> LoopExecution:
        """
        Execute a complete closed-loop cycle for a processed event

        This is the core orchestration method that runs the full pipeline:
        Signal → Reason → Plan → Execute → Verify → Report → Learn
        """

        # Create loop execution tracking
        loop_id = f"loop_{int(datetime.now().timestamp())}_{triggering_event.event_id}"
        mode = orchestration_mode or self.config.default_mode

        loop_execution = LoopExecution(
            loop_id=loop_id,
            started_at=datetime.now(timezone.utc),
            triggering_event=triggering_event,
            orchestration_mode=mode,
            user_id=user_id,
            workspace_path=self.workspace_path,
            org_id=self.org_key,
        )

        # Track active loop
        self.active_loops[loop_id] = loop_execution
        self.total_loops_processed += 1

        try:
            # Phase 1: Context Resolution (Reason)
            loop_execution.current_state = LoopState.RESOLVING
            loop_execution.progress = 0.1

            logger.info(f"🔍 [{loop_id}] Starting context resolution")

            resolved_context = await asyncio.wait_for(
                self.context_resolver.resolve_context(triggering_event.original_event),
                timeout=self.config.context_resolution_timeout_seconds,
            )

            loop_execution.resolved_context = resolved_context
            loop_execution.progress = 0.2

            # Phase 2: Autonomous Planning (Plan)
            loop_execution.current_state = LoopState.PLANNING
            logger.info(f"📋 [{loop_id}] Creating execution plan")

            execution_plan = await asyncio.wait_for(
                self.auto_planner.create_execution_plan(
                    triggering_event, resolved_context
                ),
                timeout=self.config.planning_timeout_seconds,
            )

            loop_execution.execution_plan = execution_plan
            loop_execution.confidence_score = execution_plan.overall_confidence
            loop_execution.progress = 0.3

            # Safety Assessment
            safety_level = self._assess_safety_level(execution_plan, resolved_context)
            loop_execution.safety_level = safety_level

            # Phase 3: Approval Gate (if needed)
            if await self._requires_approval(execution_plan, safety_level, mode):
                loop_execution.current_state = LoopState.APPROVING
                logger.info(f"⏳ [{loop_id}] Requesting human approval")

                # Report plan for approval
                await self.report_dispatcher.dispatch_plan_created(
                    execution_plan, resolved_context
                )

                # Wait for approval or timeout
                approved = await self._wait_for_approval(loop_execution)

                if not approved:
                    return await self._handle_loop_cancellation(
                        loop_execution, "Approval denied or timeout"
                    )

            # Phase 4: Execution (Execute)
            loop_execution.current_state = LoopState.EXECUTING
            loop_execution.progress = 0.4

            logger.info(f"⚡ [{loop_id}] Starting execution")

            # Report execution start
            if execution_plan.primary_actions:
                await self.report_dispatcher.dispatch_execution_start(
                    execution_plan, execution_plan.primary_actions[0], resolved_context
                )

            # Execute all planned actions
            for i, action in enumerate(execution_plan.primary_actions):
                logger.info(
                    f"🔧 [{loop_id}] Executing action {i+1}/{len(execution_plan.primary_actions)}: {action.action_type.value}"
                )

                execution_result = await asyncio.wait_for(
                    self.execution_controller.execute_action(
                        action, resolved_context, execution_plan
                    ),
                    timeout=self.config.execution_timeout_seconds,
                )

                loop_execution.execution_results.append(execution_result)

                # Check for execution failure
                if execution_result.status == ExecutionStatus.FAILED:
                    if execution_result.retry_count < self.config.max_retry_attempts:
                        logger.info(f"🔄 [{loop_id}] Retrying failed action")
                        # Implement retry logic here if needed
                    else:
                        logger.error(f"💥 [{loop_id}] Action failed after max retries")
                        break

                # Update progress
                loop_execution.progress = 0.4 + (
                    0.3 * (i + 1) / len(execution_plan.primary_actions)
                )

            # Phase 5: Verification (Verify)
            loop_execution.current_state = LoopState.VERIFYING
            loop_execution.progress = 0.8

            logger.info(f"✅ [{loop_id}] Starting verification")

            # Verify each execution result
            for execution_result in loop_execution.execution_results:
                verification_result = await asyncio.wait_for(
                    self.verification_engine.verify_execution(
                        execution_result, resolved_context
                    ),
                    timeout=self.config.verification_timeout_seconds,
                )

                loop_execution.verification_results.append(verification_result)

            # Phase 6: Reporting (Report)
            loop_execution.current_state = LoopState.REPORTING
            loop_execution.progress = 0.9

            logger.info(f"📢 [{loop_id}] Dispatching reports")

            # Report execution results
            for execution_result, verification_result in zip(
                loop_execution.execution_results, loop_execution.verification_results
            ):
                if execution_result.status == ExecutionStatus.COMPLETED:
                    report = await self.report_dispatcher.dispatch_execution_complete(
                        execution_result, verification_result, resolved_context
                    )
                else:
                    report = await self.report_dispatcher.dispatch_execution_failed(
                        execution_result, resolved_context
                    )

                loop_execution.generated_reports.append(report)

                # Report verification results if enabled
                if verification_result and self.config.report_all_executions:
                    verification_report = (
                        await self.report_dispatcher.dispatch_verification_results(
                            verification_result, execution_result, resolved_context
                        )
                    )
                    loop_execution.generated_reports.append(verification_report)

            # Phase 7: Learning (Learn)
            if self.config.enable_learning:
                loop_execution.current_state = LoopState.LEARNING
                logger.info(f"🧠 [{loop_id}] Processing learning outcomes")

                # Learn from execution outcomes
                for execution_result, verification_result in zip(
                    loop_execution.execution_results,
                    loop_execution.verification_results,
                ):
                    learning_outcomes = (
                        await self.loop_memory_updater.process_execution_outcome(
                            execution_result,
                            verification_result,
                            execution_plan,
                            resolved_context,
                        )
                    )
                    loop_execution.learning_outcomes.extend(learning_outcomes)

            # Complete the loop
            loop_execution = await self._complete_loop_execution(loop_execution)

            logger.info(f"🎉 [{loop_id}] Closed-loop execution completed successfully")

            return loop_execution

        except asyncio.TimeoutError as e:
            logger.error(f"⏰ [{loop_id}] Loop execution timed out: {e}")
            return await self._handle_loop_timeout(loop_execution, str(e))

        except Exception as e:
            logger.error(f"💥 [{loop_id}] Loop execution failed: {e}", exc_info=True)
            return await self._handle_loop_error(loop_execution, e)

        finally:
            # Move from active to completed
            self.active_loops.pop(loop_id, None)
            self.completed_loops[loop_id] = loop_execution

            # Maintain history size
            if len(self.completed_loops) > self.max_history:
                oldest_key = min(self.completed_loops.keys())
                self.completed_loops.pop(oldest_key)

    async def get_loop_status(self, loop_id: str) -> Optional[LoopExecution]:
        """Get the current status of a loop execution"""

        # Check active loops first
        if loop_id in self.active_loops:
            return self.active_loops[loop_id]

        # Check completed loops
        if loop_id in self.completed_loops:
            return self.completed_loops[loop_id]

        return None

    async def approve_pending_loop(
        self, loop_id: str, approved: bool, user_id: str, reason: str = ""
    ) -> bool:
        """Approve or reject a pending loop execution"""

        if loop_id not in self.pending_approvals:
            logger.warning(f"Loop {loop_id} not found in pending approvals")
            return False

        try:
            loop_execution = self.pending_approvals[loop_id]

            # Record approval decision
            approval_data = {
                "approved": approved,
                "user_id": user_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Process approval through learning system
            if self.config.enable_learning:
                if loop_execution.execution_plan:
                    await self.loop_memory_updater.process_plan_lifecycle(
                        loop_execution.execution_plan,
                        "approved" if approved else "cancelled",
                        loop_execution.resolved_context,
                        approval_data,
                    )

            # Remove from pending
            self.pending_approvals.pop(loop_id)

            # Continue or cancel the loop
            if approved:
                logger.info(f"✅ Loop {loop_id} approved by {user_id}")
                # The loop will continue from where it left off
                return True
            else:
                logger.info(f"❌ Loop {loop_id} rejected by {user_id}: {reason}")
                await self._handle_loop_cancellation(
                    loop_execution, f"Rejected by {user_id}: {reason}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to process approval for loop {loop_id}: {e}", exc_info=True
            )
            return False

    async def escalate_loop(
        self, loop_id: str, escalation_reason: str, escalation_level: str = "management"
    ) -> bool:
        """Escalate a loop execution to human intervention"""

        loop_execution = await self.get_loop_status(loop_id)
        if not loop_execution:
            return False

        try:
            loop_execution.current_state = LoopState.ESCALATED
            loop_execution.escalation_reason = escalation_reason

            # Move to escalated tracking
            self.escalated_loops[loop_id] = loop_execution

            # Send escalation alert
            action_type = ActionType.NO_ACTION_NEEDED
            if (
                loop_execution.execution_plan
                and loop_execution.execution_plan.primary_actions
            ):
                action_type = loop_execution.execution_plan.primary_actions[
                    0
                ].action_type

            await self.report_dispatcher.dispatch_safety_alert(
                "Loop Escalation",
                action_type,
                escalation_level,
                f"Loop {loop_id} escalated: {escalation_reason}",
                [
                    "Review loop execution details",
                    "Determine appropriate intervention",
                    "Provide guidance or take manual control",
                ],
                loop_execution.resolved_context,
            )

            logger.info(
                f"🚨 Loop {loop_id} escalated to {escalation_level}: {escalation_reason}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to escalate loop {loop_id}: {e}", exc_info=True)
            return False

    async def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get comprehensive orchestration metrics and insights"""

        try:
            # Basic metrics
            total_loops = self.total_loops_processed
            success_rate = (
                self.successful_loops / total_loops if total_loops > 0 else 0.0
            )

            metrics = {
                "orchestration_status": (
                    "active" if self.processing_loop_active else "stopped"
                ),
                "total_loops_processed": total_loops,
                "successful_loops": self.successful_loops,
                "failed_loops": self.failed_loops,
                "success_rate": success_rate,
                "autonomous_success_rate": self.autonomous_success_rate,
                "active_loops": len(self.active_loops),
                "pending_approvals": len(self.pending_approvals),
                "escalated_loops": len(self.escalated_loops),
                "event_queue_size": self.event_queue.qsize(),
                "background_tasks": len(self.background_tasks),
                "configuration": {
                    "default_mode": self.config.default_mode.value,
                    "safety_threshold": self.config.safety_threshold,
                    "confidence_threshold": self.config.confidence_threshold,
                    "max_concurrent_loops": self.config.max_concurrent_loops,
                    "learning_enabled": self.config.enable_learning,
                },
            }

            # Recent performance
            recent_loops = list(self.completed_loops.values())[-10:]  # Last 10 loops
            if recent_loops:
                recent_success_rate = len(
                    [loop for loop in recent_loops if loop.final_status == "completed"]
                ) / len(recent_loops)
                avg_duration = sum(
                    loop.total_duration_seconds or 0 for loop in recent_loops
                ) / len(recent_loops)

                metrics["recent_performance"] = {
                    "recent_success_rate": recent_success_rate,
                    "avg_loop_duration_seconds": avg_duration,
                    "sample_size": len(recent_loops),
                }

            # Component health
            component_health = {}
            for component_name in [
                "event_ingestor",
                "context_resolver",
                "auto_planner",
                "execution_controller",
                "verification_engine",
                "report_dispatcher",
                "loop_memory_updater",
            ]:
                component = getattr(self, component_name, None)
                if component and hasattr(component, "get_health_status"):
                    component_health[component_name] = (
                        await component.get_health_status()
                    )
                else:
                    component_health[component_name] = "available"

            metrics["component_health"] = component_health

            # Safety and compliance
            metrics["safety_compliance"] = {
                "safety_violations_count": len(self.safety_violations),
                "audit_log_entries": len(self.audit_log),
                "compliance_mode": self.config.compliance_mode,
                "safety_checks_enabled": self.config.enable_safety_checks,
            }

            return metrics

        except Exception as e:
            logger.error(
                f"Failed to generate orchestration metrics: {e}", exc_info=True
            )
            return {"error": str(e)}

    # Private helper methods for orchestration logic

    async def _initialize_components(self) -> None:
        """Initialize all Phase 5.0 components"""

        try:
            # Initialize each component if it has an init method
            components = [
                self.event_ingestor,
                self.context_resolver,
                self.auto_planner,
                self.execution_controller,
                self.verification_engine,
                self.report_dispatcher,
                self.loop_memory_updater,
            ]

            for component in components:
                if hasattr(component, "initialize"):
                    await component.initialize()

            logger.info("✅ All Phase 5.0 components initialized")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}", exc_info=True)
            raise

    async def _event_processing_loop(self) -> None:
        """Background event processing loop"""

        self.processing_loop_active = True
        logger.info("🔄 Event processing loop started")

        try:
            while not self.shutdown_requested:
                try:
                    # Check for concurrent loop limit
                    if len(self.active_loops) >= self.config.max_concurrent_loops:
                        await asyncio.sleep(5)  # Wait for capacity
                        continue

                    # Get next event from queue with timeout
                    try:
                        event = await asyncio.wait_for(
                            self.event_queue.get(),
                            timeout=self.config.event_processing_interval_seconds,
                        )

                        # Process event in background
                        loop_task = asyncio.create_task(self.execute_closed_loop(event))
                        self.background_tasks.add(loop_task)
                        loop_task.add_done_callback(self.background_tasks.discard)

                    except asyncio.TimeoutError:
                        # No events to process, continue
                        continue

                except Exception as e:
                    logger.error(f"Error in event processing loop: {e}", exc_info=True)
                    await asyncio.sleep(1)  # Brief pause on error

        except Exception as e:
            logger.error(f"Event processing loop crashed: {e}", exc_info=True)
        finally:
            self.processing_loop_active = False
            logger.info("🛑 Event processing loop stopped")

    async def _periodic_maintenance(self) -> None:
        """Periodic maintenance tasks"""

        logger.info("🔧 Starting periodic maintenance")

        try:
            while not self.shutdown_requested:
                await asyncio.sleep(
                    self.config.memory_maintenance_interval_hours * 3600
                )

                if self.shutdown_requested:
                    break

                try:
                    # Run memory maintenance
                    if self.config.enable_learning:
                        maintenance_stats = (
                            await self.loop_memory_updater.run_memory_maintenance()
                        )
                        logger.info(
                            f"Memory maintenance completed: {maintenance_stats}"
                        )

                    # Clean up old completed loops
                    self._cleanup_old_loops()

                    # Update performance metrics
                    self._update_performance_metrics()

                    logger.info("✅ Periodic maintenance completed")

                except Exception as e:
                    logger.error(f"Periodic maintenance failed: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Periodic maintenance loop crashed: {e}", exc_info=True)

    def _assess_safety_level(
        self, execution_plan: ExecutionPlan, context: ResolvedContext
    ) -> SafetyLevel:
        """Assess the safety level of an execution plan"""

        try:
            # Start with plan's overall safety
            if execution_plan.overall_safety.value == "dangerous":
                return SafetyLevel.DANGEROUS
            elif execution_plan.overall_safety.value == "risky":
                return SafetyLevel.HIGH_RISK
            elif execution_plan.overall_safety.value == "moderate":
                return SafetyLevel.MODERATE_RISK
            else:
                return SafetyLevel.SAFE

        except Exception as e:
            logger.error(f"Failed to assess safety level: {e}")
            return SafetyLevel.HIGH_RISK  # Default to conservative

    async def _requires_approval(
        self,
        execution_plan: ExecutionPlan,
        safety_level: SafetyLevel,
        mode: OrchestrationMode,
    ) -> bool:
        """Determine if human approval is required"""

        # Always require approval in supervised mode
        if mode == OrchestrationMode.SUPERVISED:
            return True

        if execution_plan.human_approval_needed:
            return True

        # Never require approval in autonomous mode (unless dangerous)
        if (
            mode == OrchestrationMode.AUTONOMOUS
            and safety_level != SafetyLevel.DANGEROUS
        ):
            return False

        # Block dangerous actions entirely if configured
        if (
            safety_level == SafetyLevel.DANGEROUS
            and self.config.block_high_risk_actions
        ):
            return True

        # Check safety threshold
        if safety_level in [SafetyLevel.HIGH_RISK, SafetyLevel.DANGEROUS]:
            return True

        # Check confidence threshold
        if execution_plan.overall_confidence < self.config.confidence_threshold:
            return True

        # Check for destructive actions
        if self.config.require_approval_for_destructive:
            for action in execution_plan.primary_actions:
                if action.is_destructive:
                    return True

        # Check for external API write actions
        if self.config.require_approval_for_external_apis:
            for action in execution_plan.primary_actions:
                if self._requires_external_approval(action):
                    return True

        return False

    def _requires_external_approval(self, action: PlannedAction) -> bool:
        """Return True if the action should be gated as an external write."""
        external_write_actions = {
            ActionType.NOTIFY_TEAM,
            ActionType.ADD_COMMENT,
            ActionType.ASSIGN_ISSUE,
            ActionType.UPDATE_STATUS,
            ActionType.CREATE_SUBTASK,
            ActionType.LINK_ISSUES,
            ActionType.CREATE_PR,
            ActionType.REVIEW_PR,
            ActionType.MERGE_PR,
            ActionType.CREATE_ISSUE,
        }
        if action.action_type in external_write_actions:
            return True

        target = (action.target or "").lower()
        if target.startswith(("slack:", "teams:", "confluence:", "github:", "jira:")):
            return True

        return False

    async def _wait_for_approval(self, loop_execution: LoopExecution) -> bool:
        """Wait for human approval with timeout"""

        loop_id = loop_execution.loop_id

        try:
            # Add to pending approvals
            self.pending_approvals[loop_id] = loop_execution

            # Wait for approval with timeout
            timeout_seconds = self.config.approval_timeout_minutes * 60
            start_time = datetime.now(timezone.utc)

            while (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() < timeout_seconds:
                if loop_id not in self.pending_approvals:
                    # Approval was processed
                    return loop_execution.current_state != LoopState.ESCALATED

                await asyncio.sleep(5)  # Check every 5 seconds

            # Timeout reached
            logger.warning(f"Approval timeout for loop {loop_id}")
            self.pending_approvals.pop(loop_id, None)
            return False

        except Exception as e:
            logger.error(f"Error waiting for approval: {e}", exc_info=True)
            self.pending_approvals.pop(loop_id, None)
            return False

    async def _complete_loop_execution(
        self, loop_execution: LoopExecution
    ) -> LoopExecution:
        """Complete a loop execution and update metrics"""

        try:
            loop_execution.current_state = LoopState.IDLE
            loop_execution.progress = 1.0
            loop_execution.completed_at = datetime.now(timezone.utc)
            loop_execution.total_duration_seconds = (
                loop_execution.completed_at - loop_execution.started_at
            ).total_seconds()

            # Determine final status
            all_successful = all(
                result.status == ExecutionStatus.COMPLETED
                for result in loop_execution.execution_results
            )

            if all_successful:
                loop_execution.final_status = "completed"
                self.successful_loops += 1
            else:
                loop_execution.final_status = "failed"
                self.failed_loops += 1

            # Update autonomous success rate
            if loop_execution.orchestration_mode == OrchestrationMode.AUTONOMOUS:
                self._update_autonomous_success_rate(all_successful)

            # Add to audit log
            if self.config.audit_trail_enabled:
                self._add_audit_entry(
                    "loop_completed",
                    {
                        "loop_id": loop_execution.loop_id,
                        "final_status": loop_execution.final_status,
                        "duration_seconds": loop_execution.total_duration_seconds,
                        "mode": loop_execution.orchestration_mode.value,
                    },
                )

            return loop_execution

        except Exception as e:
            logger.error(f"Failed to complete loop execution: {e}", exc_info=True)
            loop_execution.final_status = "error"
            loop_execution.last_error = str(e)
            return loop_execution

    async def _handle_loop_error(
        self, loop_execution: LoopExecution, error: Exception
    ) -> LoopExecution:
        """Handle loop execution error"""

        try:
            loop_execution.current_state = LoopState.ERROR
            loop_execution.error_count += 1
            loop_execution.last_error = str(error)
            loop_execution.error_traceback = traceback.format_exc()
            loop_execution.final_status = "error"
            loop_execution.completed_at = datetime.now(timezone.utc)

            # Log error
            logger.error(
                f"Loop {loop_execution.loop_id} failed: {error}", exc_info=True
            )

            # Send error report
            if self.config.report_all_executions or self.config.report_only_failures:
                try:
                    await self.report_dispatcher.dispatch_safety_alert(
                        "Loop Execution Error",
                        ActionType.NO_ACTION_NEEDED,
                        "HIGH",
                        f"Loop {loop_execution.loop_id} encountered an error: {error}",
                        [
                            "Review error logs",
                            "Check system health",
                            "Consider manual intervention",
                        ],
                        loop_execution.resolved_context,
                    )
                except Exception as report_error:
                    logger.error(f"Failed to send error report: {report_error}")

            # Escalate if too many failures
            if loop_execution.error_count >= self.config.escalation_after_failures:
                await self.escalate_loop(
                    loop_execution.loop_id,
                    f"Multiple failures ({loop_execution.error_count})",
                    "technical",
                )

            return loop_execution

        except Exception as e:
            logger.error(f"Failed to handle loop error: {e}", exc_info=True)
            return loop_execution

    async def _handle_loop_timeout(
        self, loop_execution: LoopExecution, timeout_reason: str
    ) -> LoopExecution:
        """Handle loop execution timeout"""

        loop_execution.current_state = LoopState.ERROR
        loop_execution.final_status = "timeout"
        loop_execution.last_error = f"Timeout: {timeout_reason}"
        loop_execution.completed_at = datetime.now(timezone.utc)

        logger.warning(f"Loop {loop_execution.loop_id} timed out: {timeout_reason}")

        return loop_execution

    async def _handle_loop_cancellation(
        self, loop_execution: LoopExecution, reason: str
    ) -> LoopExecution:
        """Handle loop execution cancellation"""

        loop_execution.current_state = LoopState.IDLE
        loop_execution.final_status = "cancelled"
        loop_execution.last_error = f"Cancelled: {reason}"
        loop_execution.completed_at = datetime.now(timezone.utc)

        logger.info(f"Loop {loop_execution.loop_id} cancelled: {reason}")

        return loop_execution

    async def _handle_loop_interruption(self, loop_id: str, reason: str) -> None:
        """Handle graceful loop interruption"""

        if loop_id in self.active_loops:
            loop_execution = self.active_loops[loop_id]
            await self._handle_loop_cancellation(loop_execution, reason)

    def _cleanup_old_loops(self) -> None:
        """Clean up old completed loops to manage memory"""

        try:
            # Keep only the most recent loops
            if len(self.completed_loops) > self.max_history:
                # Sort by completion time and keep the newest
                sorted_loops = sorted(
                    self.completed_loops.items(),
                    key=lambda x: x[1].completed_at
                    or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )

                # Keep only the most recent
                self.completed_loops = dict(sorted_loops[: self.max_history])

                logger.info(
                    f"Cleaned up old loops, keeping {self.max_history} most recent"
                )

        except Exception as e:
            logger.error(f"Failed to clean up old loops: {e}")

    def _update_performance_metrics(self) -> None:
        """Update performance metrics"""

        try:
            # Update overall success rate
            if self.total_loops_processed > 0:
                self.autonomous_success_rate = (
                    self.successful_loops / self.total_loops_processed
                )

        except Exception as e:
            logger.error(f"Failed to update performance metrics: {e}")

    def _update_autonomous_success_rate(self, success: bool) -> None:
        """Update autonomous-specific success rate"""

        # This would maintain a rolling average for autonomous mode specifically
        # Implementation depends on desired tracking granularity
        pass

    def _add_audit_entry(self, event_type: str, data: Dict[str, Any]) -> None:
        """Add entry to audit log"""

        if self.config.audit_trail_enabled:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "data": data,
            }

            self.audit_log.append(entry)

            # Maintain audit log size
            if len(self.audit_log) > 10000:  # Keep last 10k entries
                self.audit_log = self.audit_log[-5000:]  # Trim to 5k
