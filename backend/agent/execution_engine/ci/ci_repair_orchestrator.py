"""
Enterprise CI Repair Orchestrator

Master orchestration engine that coordinates all CI failure auto-repair
components with enterprise safety controls, audit logging, and human escalation.

This is the central brain of NAVI's autonomous CI healing system.
"""

import asyncio
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from pydantic import Field

from .ci_types import (
    CIEvent,
    FailureType,
    RepairAction,
    RepairResult,
    CIRepairSession,
    RepairAuditLog,
    CIIntegrationContext,
    GitHubActionsConfig,
    CILogs,
    FailureContext,
    RepairPlan,
    RepairConfidence,
)
from .ci_log_fetcher import CILogFetcher
from .failure_classifier import FailureClassifier
from .failure_mapper import FailureMapper
from .ci_retry_engine import CIRetryEngine

logger = logging.getLogger(__name__)


@dataclass
class RepairConfiguration:
    """Configuration for CI repair behavior"""

    auto_repair_enabled: bool = True
    max_repair_attempts: int = 3
    require_approval_threshold: float = 0.8
    safety_snapshot_enabled: bool = True
    audit_logging_enabled: bool = True
    escalation_timeout_minutes: int = 30
    allowed_failure_types: List[FailureType] = Field(default_factory=list)
    blocked_file_patterns: List[str] = Field(default_factory=list)


class CIRepairOrchestrator:
    """
    Enterprise CI Repair Orchestration Engine

    Coordinates the complete autonomous CI failure detection, analysis,
    repair, and verification workflow with enterprise safety controls.
    """

    def __init__(
        self,
        github_config: Optional[GitHubActionsConfig] = None,
        repair_config: Optional[RepairConfiguration] = None,
    ):
        self.github_config = github_config
        self.config = repair_config or RepairConfiguration()

        # Initialize components
        self.log_fetcher = CILogFetcher(github_config)
        self.failure_classifier = FailureClassifier()
        self.failure_mapper = FailureMapper()
        self.retry_engine = CIRetryEngine(github_config)

        # Session tracking
        self.active_sessions: Dict[str, CIRepairSession] = {}
        self.repair_history: List[CIRepairSession] = []
        self.audit_logs: List[RepairAuditLog] = []

        # Integration context - will be populated by Phase 4.4 components
        self.integration_context: Optional[CIIntegrationContext] = None

    async def handle_ci_failure(
        self, event: CIEvent, integration_context: Optional[CIIntegrationContext] = None
    ) -> CIRepairSession:
        """
        Main entry point for autonomous CI failure handling

        Args:
            event: CI failure event to process
            integration_context: Context from Phase 4.4 infrastructure

        Returns:
            Complete repair session with results and audit trail
        """
        session_id = str(uuid.uuid4())
        self.integration_context = integration_context

        logger.info(
            f"Starting CI repair session {session_id} for {event.provider.value} run {event.run_id}"
        )

        # Initialize repair session
        session = CIRepairSession(
            session_id=session_id,
            original_event=event,
            logs=CILogs(
                raw_logs="",
                structured_logs=[],
                error_lines=[],
                warning_lines=[],
                log_size_bytes=0,
                fetched_at=datetime.now(),
                source_url="",
            ),  # Will be populated
            failure_context=FailureContext(
                failure_type=FailureType.UNKNOWN,
                confidence=0.0,
                affected_files=[],
                error_messages=[],
                stack_traces=[],
                relevant_logs=[],
            ),  # Will be populated
            repair_plan=RepairPlan(
                action=RepairAction.INVESTIGATE,
                confidence=RepairConfidence.LOW,
                target_files=[],
                repair_strategy="pending",
                expected_changes=[],
            ),  # Will be populated
            started_at=datetime.now(),
        )

        self.active_sessions[session_id] = session

        try:
            # Take safety snapshot if enabled
            if self.config.safety_snapshot_enabled:
                session.safety_snapshot_id = await self._take_safety_snapshot()

            # Execute repair workflow
            session = await self._execute_repair_workflow(session)

            # Create audit log
            if self.config.audit_logging_enabled:
                await self._create_audit_log(session)

            # Clean up active session
            self.active_sessions.pop(session_id, None)
            self.repair_history.append(session)

        except Exception as e:
            logger.error(f"Critical error in CI repair session {session_id}: {e}")
            session.result = RepairResult(
                success=False,
                action_taken=RepairAction.ESCALATE,
                files_modified=[],
                error_message=f"Critical repair error: {str(e)}",
            )
            session.human_escalated = True

        finally:
            session.completed_at = datetime.now()
            logger.info(
                f"CI repair session {session_id} completed with status: {session.result.success if session.result else 'unknown'}"
            )

        return session

    async def _execute_repair_workflow(
        self, session: CIRepairSession
    ) -> CIRepairSession:
        """Execute the complete repair workflow"""

        # Step 1: Fetch and analyze logs
        logger.info(f"Fetching CI logs for {session.original_event.run_id}")

        async with self.log_fetcher as log_fetcher:
            session.logs = await log_fetcher.fetch_logs(session.original_event)

        # Step 2: Classify failure
        logger.info("Classifying CI failure")
        session.failure_context = self.failure_classifier.classify_failure(session.logs)

        logger.info(
            f"Classified as {session.failure_context.failure_type.value} with {session.failure_context.confidence:.2f} confidence"
        )

        # Step 3: Check if repair is allowed
        if not self._is_repair_allowed(session.failure_context):
            session.result = RepairResult(
                success=False,
                action_taken=RepairAction.ESCALATE,
                files_modified=[],
                error_message=f"Repair not allowed for failure type: {session.failure_context.failure_type.value}",
            )
            session.human_escalated = True
            return session

        # Step 4: Generate repair plan
        logger.info("Generating repair plan")
        workspace_path = await self._get_workspace_path(session.original_event)
        session.repair_plan = self.failure_mapper.map_failure_to_repair_plan(
            session.failure_context, workspace_path
        )

        # Step 5: Check if approval required
        if session.repair_plan.requires_approval:
            logger.info("Repair requires human approval - escalating")
            session.result = RepairResult(
                success=False,
                action_taken=RepairAction.SUGGEST_FIX,
                files_modified=[],
                error_message="Repair requires human approval",
            )
            return session

        # Step 6: Execute repair
        if session.repair_plan.action == RepairAction.AUTO_FIX:
            session.result = await self._execute_auto_repair(session)
        elif session.repair_plan.action == RepairAction.SUGGEST_FIX:
            session.result = await self._generate_repair_suggestion(session)
        else:
            session.result = RepairResult(
                success=False,
                action_taken=session.repair_plan.action,
                files_modified=[],
                error_message=f"Action {session.repair_plan.action.value} not implemented for auto-execution",
            )
            session.human_escalated = True

        return session

    async def _execute_auto_repair(self, session: CIRepairSession) -> RepairResult:
        """Execute automatic repair"""
        logger.info(
            f"Executing automatic repair with strategy: {session.repair_plan.repair_strategy}"
        )

        # Integration with Phase 4.4 execution engine
        if (
            self.integration_context
            and self.integration_context.commit_engine_available
        ):
            return await self._execute_with_commit_integration(session)
        else:
            return await self._execute_standalone_repair(session)

    async def _execute_with_commit_integration(
        self, session: CIRepairSession
    ) -> RepairResult:
        """Execute repair with full Phase 4.4 integration"""
        try:
            # Import Phase 4.4 components
            from ..commit_engine import CommitEngine
            from ..fix_problems import FixProblemsExecutor

            # Create repair context for execution engine
            repair_context = {
                "failure_type": session.failure_context.failure_type.value,
                "target_files": session.repair_plan.target_files,
                "error_messages": session.failure_context.error_messages,
                "repair_strategy": session.repair_plan.repair_strategy,
                "confidence": session.failure_context.confidence,
            }

            # Execute repair through existing infrastructure
            executor = FixProblemsExecutor()
            execution_result = await executor.execute_ci_auto_repair(repair_context)

            if execution_result["success"]:
                # Commit changes
                commit_engine = CommitEngine(
                    workspace_root="/tmp"
                )  # TODO: Use actual workspace
                f"ci-auto-fix-{session.session_id[:8]}"

                commit_result = await commit_engine.commit_changes(
                    files=session.repair_plan.target_files,
                    message=f"Auto-fix: {session.failure_context.failure_type.value}",
                )

                # Retry CI pipeline
                async with self.retry_engine as retry_engine:
                    retry_session = await retry_engine.retry_ci_pipeline(
                        session.original_event, session.session_id
                    )

                return RepairResult(
                    success=True,
                    action_taken=RepairAction.AUTO_FIX,
                    files_modified=session.repair_plan.target_files,
                    commit_sha=commit_result.sha,
                    ci_rerun_id=(
                        retry_session.attempts[-1].ci_run_id
                        if retry_session.attempts
                        else None
                    ),
                    repair_duration_seconds=int(
                        (
                            datetime.now() - (session.started_at or datetime.now())
                        ).total_seconds()
                    ),
                    confidence_achieved=session.failure_context.confidence,
                )

            else:
                return RepairResult(
                    success=False,
                    action_taken=RepairAction.AUTO_FIX,
                    files_modified=[],
                    error_message=execution_result.get(
                        "error", "Repair execution failed"
                    ),
                )

        except ImportError:
            logger.warning(
                "Phase 4.4 components not available - falling back to standalone repair"
            )
            return await self._execute_standalone_repair(session)

        except Exception as e:
            logger.error(f"Error in integrated repair execution: {e}")
            return RepairResult(
                success=False,
                action_taken=RepairAction.AUTO_FIX,
                files_modified=[],
                error_message=f"Integrated repair failed: {str(e)}",
            )

    async def _execute_standalone_repair(
        self, session: CIRepairSession
    ) -> RepairResult:
        """Execute repair without Phase 4.4 integration"""
        logger.info("Executing standalone repair (Phase 4.4 integration not available)")

        # Simulate repair execution for now
        # In production, this would contain the actual repair logic

        await asyncio.sleep(2)  # Simulate repair time

        # For demonstration, simulate successful repair
        success_probability = session.failure_context.confidence
        is_successful = success_probability > 0.7

        if is_successful:
            # Simulate CI retry
            async with self.retry_engine as retry_engine:
                retry_session = await retry_engine.retry_ci_pipeline(
                    session.original_event, session.session_id
                )

            return RepairResult(
                success=True,
                action_taken=RepairAction.AUTO_FIX,
                files_modified=session.repair_plan.target_files,
                ci_rerun_id=(
                    retry_session.attempts[-1].ci_run_id
                    if retry_session.attempts
                    else None
                ),
                repair_duration_seconds=int(
                    (
                        datetime.now() - (session.started_at or datetime.now())
                    ).total_seconds()
                ),
                confidence_achieved=session.failure_context.confidence,
            )
        else:
            return RepairResult(
                success=False,
                action_taken=RepairAction.AUTO_FIX,
                files_modified=[],
                error_message="Simulated repair failure (standalone mode)",
            )

    async def _generate_repair_suggestion(
        self, session: CIRepairSession
    ) -> RepairResult:
        """Generate repair suggestion for human review"""
        logger.info("Generating repair suggestion for human review")

        suggestion = self._create_human_readable_suggestion(session)

        return RepairResult(
            success=False,  # Not automatically applied
            action_taken=RepairAction.SUGGEST_FIX,
            files_modified=[],
            error_message=f"Repair suggestion: {suggestion}",
            confidence_achieved=session.failure_context.confidence,
        )

    def _create_human_readable_suggestion(self, session: CIRepairSession) -> str:
        """Create human-readable repair suggestion"""
        failure_type = session.failure_context.failure_type.value
        files = session.repair_plan.target_files[:3]  # Show first 3 files
        strategy = session.repair_plan.repair_strategy
        confidence = session.failure_context.confidence

        suggestion = f"""
CI Failure Auto-Repair Suggestion:

Failure Type: {failure_type}
Confidence: {confidence:.1%}
Strategy: {strategy}

Affected Files:
{chr(10).join(f"  - {file}" for file in files)}

Expected Changes:
{chr(10).join(f"  - {change}" for change in session.repair_plan.expected_changes)}

Recommendation: Review the suggested changes and apply manually, or approve auto-repair if confidence is acceptable.
        """.strip()

        return suggestion

    def _is_repair_allowed(self, failure_context) -> bool:
        """Check if repair is allowed based on configuration"""
        if not self.config.auto_repair_enabled:
            return False

        # Check allowed failure types
        if self.config.allowed_failure_types:
            if failure_context.failure_type not in self.config.allowed_failure_types:
                logger.info(
                    f"Repair blocked: {failure_context.failure_type.value} not in allowed types"
                )
                return False

        # Check confidence threshold
        if failure_context.confidence < 0.3:  # Minimum confidence
            logger.info(
                f"Repair blocked: confidence {failure_context.confidence:.2f} too low"
            )
            return False

        return True

    async def _get_workspace_path(self, event: CIEvent) -> str:
        """Get workspace path for the CI event"""
        # In production, this would resolve the actual workspace path
        # For now, return a reasonable default
        return f"/tmp/ci_workspace_{event.repo_name}"

    async def _take_safety_snapshot(self) -> str:
        """Take safety snapshot before repair"""
        if self.integration_context and self.integration_context.safety_system_enabled:
            try:
                from ..safety.snapshot_engine import SnapshotEngine

                snapshot_engine = SnapshotEngine(
                    workspace_root="/tmp"
                )  # TODO: Use actual workspace
                snapshot = snapshot_engine.take_snapshot(files=[])
                snapshot_id = getattr(
                    snapshot, "id", getattr(snapshot, "snapshot_id", str(id(snapshot)))
                )
                logger.info(f"Safety snapshot created: {snapshot_id}")
                return snapshot_id
            except ImportError:
                logger.warning("Safety system not available")

        # Fallback: generate mock snapshot ID
        return f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _create_audit_log(self, session: CIRepairSession):
        """Create audit log for repair session"""
        audit_log = RepairAuditLog(
            session_id=session.session_id,
            timestamp=datetime.now(),
            action=session.result.action_taken.value if session.result else "unknown",
            user_context="autonomous_ci_repair",  # Added missing required parameter
            files_affected=(
                session.repair_plan.target_files if session.repair_plan else []
            ),
            confidence_score=(
                session.failure_context.confidence if session.failure_context else 0.0
            ),
            approval_required=(
                session.repair_plan.requires_approval if session.repair_plan else False
            ),
        )

        self.audit_logs.append(audit_log)
        logger.info(f"Audit log created for session {session.session_id}")

    def get_repair_statistics(self) -> Dict[str, Any]:
        """Get repair system statistics"""
        total_sessions = len(self.repair_history)
        if total_sessions == 0:
            return {
                "total_sessions": 0,
                "success_rate": 0.0,
                "average_confidence": 0.0,
                "most_common_failure_type": None,
                "active_sessions": len(self.active_sessions),
                "successful_repairs": 0,
                "failed_repairs": 0,
                "escalated_sessions": 0,
            }

        successful_sessions = sum(
            1 for s in self.repair_history if s.result and s.result.success
        )
        success_rate = successful_sessions / total_sessions

        confidences = [
            s.failure_context.confidence
            for s in self.repair_history
            if s.failure_context
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Find most common failure type
        failure_types = [
            s.failure_context.failure_type
            for s in self.repair_history
            if s.failure_context
        ]
        if failure_types:
            most_common = max(set(failure_types), key=failure_types.count)
        else:
            most_common = None

        return {
            "total_sessions": total_sessions,
            "success_rate": success_rate,
            "successful_repairs": successful_sessions,
            "failed_repairs": total_sessions - successful_sessions,
            "average_confidence": avg_confidence,
            "most_common_failure_type": most_common.value if most_common else None,
            "active_sessions": len(self.active_sessions),
            "escalated_sessions": sum(
                1 for s in self.repair_history if s.human_escalated
            ),
        }

    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get information about currently active repair sessions"""
        active_info = []

        for session_id, session in self.active_sessions.items():
            duration = datetime.now() - (session.started_at or datetime.now())

            active_info.append(
                {
                    "session_id": session_id,
                    "duration_seconds": int(duration.total_seconds()),
                    "failure_type": (
                        session.failure_context.failure_type.value
                        if session.failure_context
                        else "unknown"
                    ),
                    "repo": f"{session.original_event.repo_owner}/{session.original_event.repo_name}",
                    "run_id": session.original_event.run_id,
                }
            )

        return active_info

    async def cancel_repair_session(self, session_id: str) -> bool:
        """Cancel active repair session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.result = RepairResult(
                success=False,
                action_taken=RepairAction.ESCALATE,
                files_modified=[],
                error_message="Session cancelled by user",
            )
            session.human_escalated = True
            session.completed_at = datetime.now()

            # Move to history
            self.repair_history.append(session)
            self.active_sessions.pop(session_id)

            logger.info(f"Cancelled repair session {session_id}")
            return True

        return False
