"""
Phase 5.0 — Closed-Loop Autonomy Integration

This module integrates all Phase 5.0 components into a cohesive autonomous engineering system.
It provides the main entry points and API integration for the closed-loop orchestration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Phase 5.0 Components
from backend.agent.closedloop.event_ingestor import (
    EventPriority,
    AutonomiTrigger,
    EventSource,
    EventType,
)
from backend.agent.closedloop.closed_loop_orchestrator import (
    ClosedLoopOrchestrator,
    OrchestrationMode,
    OrchestrationConfig,
    LoopExecution,
)

# Integration points with existing system
from backend.core.db import get_db
from backend.services.jira import JiraService
from backend.integrations.slack_client import SlackClient

# Explicit re-exports for external usage
__all__ = [
    "EventPriority",
    "AutonomiTrigger",
    "EventSource",
    "EventType",
    "ClosedLoopOrchestrator",
    "OrchestrationMode",
    "OrchestrationConfig",
    "LoopExecution",
    "JiraService",
    "SlackClient",
]


logger = logging.getLogger(__name__)


class Phase5System:
    """
    Phase 5.0 Closed-Loop Autonomy System

    The main interface for the autonomous engineering platform that enables:
    - Event-driven autonomous operation
    - Jira-triggered coding workflows
    - PR auto-fix loops
    - CI self-healing
    - Slack-native reporting
    """

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        org_key: str = "default",
        config: Optional[OrchestrationConfig] = None,
    ):
        self.workspace_path = workspace_path
        self.org_key = org_key
        self.config = config or OrchestrationConfig()

        # Core orchestrator
        self.orchestrator: Optional[ClosedLoopOrchestrator] = None

        # System state
        self.is_running = False
        self.startup_time: Optional[datetime] = None

    async def initialize(self, db_session=None) -> None:
        """Initialize the Phase 5.0 system"""

        try:
            logger.info("🚀 Initializing Phase 5.0 Closed-Loop Autonomy System")

            # Get database session
            if not db_session:
                db_session = next(get_db())

            # Initialize orchestrator
            self.orchestrator = ClosedLoopOrchestrator(
                db_session=db_session,
                workspace_path=self.workspace_path,
                org_key=self.org_key,
                config=self.config,
            )

            # Start orchestration
            await self.orchestrator.start_orchestration()

            self.is_running = True
            self.startup_time = datetime.now(timezone.utc)

            logger.info("✅ Phase 5.0 System initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Phase 5.0 system: {e}", exc_info=True)
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown the Phase 5.0 system"""

        try:
            logger.info("🛑 Shutting down Phase 5.0 System")

            if self.orchestrator:
                await self.orchestrator.stop_orchestration()

            self.is_running = False
            logger.info("✅ Phase 5.0 System shutdown complete")

        except Exception as e:
            logger.error(f"Error during Phase 5.0 shutdown: {e}", exc_info=True)

    # Main entry points for external event integration

    async def handle_jira_event(
        self,
        event_type: str,
        issue_data: Dict[str, Any],
        webhook_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Handle Jira webhook events for autonomous coding workflows

        Supported event types:
        - issue_assigned: Start autonomous work on assigned issues
        - issue_updated: React to issue updates and comments
        - issue_transitioned: Handle status changes
        """

        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return None

        try:
            # Map Jira event types to our internal event types
            event_mapping = {
                "issue_assigned": EventType.ISSUE_ASSIGNED,
                "issue_updated": EventType.ISSUE_UPDATED,
                "issue_commented": EventType.ISSUE_COMMENTED,
                "issue_transitioned": EventType.ISSUE_STATUS_CHANGED,
            }

            internal_event_type = event_mapping.get(event_type, EventType.UNKNOWN)
            if internal_event_type == EventType.UNKNOWN:
                logger.warning(f"Unsupported Jira event type: {event_type}")
                return None

            # Enrich event data
            event_data = {
                "issue": issue_data,
                "webhook": webhook_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Ingest the event
            loop_id = await self.orchestrator.ingest_external_event(
                source=EventSource.JIRA,
                event_type=internal_event_type,
                event_data=event_data,
                metadata={"workspace_path": self.workspace_path},
            )

            logger.info(f"Processed Jira {event_type} event, started loop {loop_id}")
            return loop_id

        except Exception as e:
            logger.error(
                f"Failed to handle Jira event {event_type}: {e}", exc_info=True
            )
            return None

    async def handle_github_event(
        self,
        event_type: str,
        pr_data: Optional[Dict[str, Any]] = None,
        comment_data: Optional[Dict[str, Any]] = None,
        ci_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Handle GitHub webhook events for PR auto-fix loops

        Supported event types:
        - pr_comment: React to PR review comments
        - pr_review: Handle PR review submissions
        - ci_failure: Auto-fix CI failures
        - push: React to new commits
        """

        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return None

        try:
            # Map GitHub event types
            event_mapping = {
                "pr_comment": EventType.PR_COMMENT_ADDED,
                "pr_review": EventType.PR_REVIEW_SUBMITTED,
                "ci_failure": EventType.CI_FAILURE,
                "ci_success": EventType.CI_SUCCESS,
                "push": EventType.PUSH,
            }

            internal_event_type = event_mapping.get(event_type, EventType.UNKNOWN)
            if internal_event_type == EventType.UNKNOWN:
                logger.warning(f"Unsupported GitHub event type: {event_type}")
                return None

            # Build event data
            event_data = {
                "pr": pr_data,
                "comment": comment_data,
                "ci": ci_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Ingest the event
            loop_id = await self.orchestrator.ingest_external_event(
                source=EventSource.GITHUB,
                event_type=internal_event_type,
                event_data=event_data,
                metadata={"workspace_path": self.workspace_path},
            )

            logger.info(f"Processed GitHub {event_type} event, started loop {loop_id}")
            return loop_id

        except Exception as e:
            logger.error(
                f"Failed to handle GitHub event {event_type}: {e}", exc_info=True
            )
            return None

    async def handle_slack_mention(
        self, message_data: Dict[str, Any], user_id: str, channel_id: str
    ) -> Optional[str]:
        """
        Handle Slack mentions for contextual autonomous actions

        When NAVI is mentioned in Slack, analyze the context and take appropriate action:
        - Answer questions
        - Start tasks
        - Provide status updates
        - Escalate issues
        """

        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return None

        try:
            event_data = {
                "message": message_data,
                "user_id": user_id,
                "channel_id": channel_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Ingest the event
            loop_id = await self.orchestrator.ingest_external_event(
                source=EventSource.SLACK,
                event_type=EventType.MENTION,
                event_data=event_data,
                metadata={
                    "workspace_path": self.workspace_path,
                    "user_id": user_id,
                    "channel_id": channel_id,
                },
            )

            logger.info(
                f"Processed Slack mention from {user_id}, started loop {loop_id}"
            )
            return loop_id

        except Exception as e:
            logger.error(f"Failed to handle Slack mention: {e}", exc_info=True)
            return None

    async def handle_ci_event(
        self, event_type: str, build_data: Dict[str, Any], repository: str, branch: str
    ) -> Optional[str]:
        """
        Handle CI/CD events for self-healing workflows

        Supported event types:
        - build_failed: Diagnose and fix build failures
        - deployment_failed: Handle deployment issues
        - test_failed: Fix failing tests
        """

        if not self.orchestrator:
            logger.error("Orchestrator not initialized")
            return None

        try:
            # Map CI event types
            event_mapping = {
                "build_failed": EventType.CI_FAILURE,
                "build_succeeded": EventType.CI_SUCCESS,
                "deployment_failed": EventType.DEPLOYMENT_FAILURE,
                "deployment_succeeded": EventType.DEPLOYMENT_SUCCESS,
                "test_failed": EventType.TEST_FAILURE,
            }

            internal_event_type = event_mapping.get(event_type, EventType.UNKNOWN)
            if internal_event_type == EventType.UNKNOWN:
                logger.warning(f"Unsupported CI event type: {event_type}")
                return None

            event_data = {
                "build": build_data,
                "repository": repository,
                "branch": branch,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Ingest the event
            loop_id = await self.orchestrator.ingest_external_event(
                source=EventSource.CI_CD,
                event_type=internal_event_type,
                event_data=event_data,
                metadata={
                    "workspace_path": self.workspace_path,
                    "repository": repository,
                    "branch": branch,
                },
            )

            logger.info(
                f"Processed CI {event_type} event for {repository}/{branch}, started loop {loop_id}"
            )
            return loop_id

        except Exception as e:
            logger.error(f"Failed to handle CI event {event_type}: {e}", exc_info=True)
            return None

    # Management and monitoring methods

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""

        try:
            status = {
                "system_running": self.is_running,
                "startup_time": (
                    self.startup_time.isoformat() if self.startup_time else None
                ),
                "workspace_path": self.workspace_path,
                "org_key": self.org_key,
                "configuration": {
                    "default_mode": self.config.default_mode.value,
                    "safety_threshold": self.config.safety_threshold,
                    "confidence_threshold": self.config.confidence_threshold,
                    "learning_enabled": self.config.enable_learning,
                },
            }

            # Get orchestrator metrics if available
            if self.orchestrator:
                orchestrator_metrics = (
                    await self.orchestrator.get_orchestration_metrics()
                )
                status["orchestration"] = orchestrator_metrics

            return status

        except Exception as e:
            logger.error(f"Failed to get system status: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_active_loops(self) -> List[Dict[str, Any]]:
        """Get information about currently active loops"""

        if not self.orchestrator:
            return []

        try:
            active_loops = []

            for loop_id, loop_execution in self.orchestrator.active_loops.items():
                loop_info = {
                    "loop_id": loop_id,
                    "started_at": loop_execution.started_at.isoformat(),
                    "current_state": loop_execution.current_state.value,
                    "progress": loop_execution.progress,
                    "confidence_score": loop_execution.confidence_score,
                    "orchestration_mode": loop_execution.orchestration_mode.value,
                    "safety_level": (
                        loop_execution.safety_level.value
                        if loop_execution.safety_level
                        else None
                    ),
                    "user_id": loop_execution.user_id,
                    "error_count": loop_execution.error_count,
                    "retry_count": loop_execution.retry_count,
                }

                # Add event information if available
                if loop_execution.triggering_event:
                    loop_info["triggering_event"] = {
                        "source": loop_execution.triggering_event.source.value,
                        "type": loop_execution.triggering_event.event_type.value,
                        "received_at": loop_execution.triggering_event.received_at.isoformat(),
                    }

                # Add execution plan summary if available
                if loop_execution.execution_plan:
                    loop_info["execution_plan"] = {
                        "action_count": len(
                            loop_execution.execution_plan.primary_actions
                        ),
                        "overall_confidence": loop_execution.execution_plan.overall_confidence,
                        "human_approval_needed": loop_execution.execution_plan.human_approval_needed,
                    }

                active_loops.append(loop_info)

            return active_loops

        except Exception as e:
            logger.error(f"Failed to get active loops: {e}", exc_info=True)
            return []

    async def get_loop_details(self, loop_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific loop"""

        if not self.orchestrator:
            return None

        try:
            loop_execution = await self.orchestrator.get_loop_status(loop_id)
            if not loop_execution:
                return None

            # Build detailed response
            details = {
                "loop_id": loop_execution.loop_id,
                "started_at": loop_execution.started_at.isoformat(),
                "completed_at": (
                    loop_execution.completed_at.isoformat()
                    if loop_execution.completed_at
                    else None
                ),
                "current_state": loop_execution.current_state.value,
                "final_status": loop_execution.final_status,
                "progress": loop_execution.progress,
                "confidence_score": loop_execution.confidence_score,
                "orchestration_mode": loop_execution.orchestration_mode.value,
                "safety_level": (
                    loop_execution.safety_level.value
                    if loop_execution.safety_level
                    else None
                ),
                "total_duration_seconds": loop_execution.total_duration_seconds,
                "error_count": loop_execution.error_count,
                "retry_count": loop_execution.retry_count,
                "last_error": loop_execution.last_error,
                "escalation_reason": loop_execution.escalation_reason,
                "user_id": loop_execution.user_id,
                "workspace_path": loop_execution.workspace_path,
                "org_id": loop_execution.org_id,
            }

            # Add event details
            if loop_execution.triggering_event:
                details["triggering_event"] = {
                    "event_id": loop_execution.triggering_event.event_id,
                    "source": loop_execution.triggering_event.source.value,
                    "type": loop_execution.triggering_event.event_type.value,
                    "received_at": loop_execution.triggering_event.received_at.isoformat(),
                    "priority": loop_execution.triggering_event.priority.value,
                    "confidence": loop_execution.triggering_event.confidence_score,
                    "filtered": loop_execution.triggering_event.should_be_filtered,
                    "summary": loop_execution.triggering_event.event_summary,
                }

            # Add context details
            if loop_execution.resolved_context:
                details["resolved_context"] = {
                    "context_type": loop_execution.resolved_context.context_type.value,
                    "confidence": loop_execution.resolved_context.context_completeness,
                    "team_members_count": len(
                        loop_execution.resolved_context.team_members
                    ),
                    "related_issues_count": len(
                        loop_execution.resolved_context.related_issues
                    ),
                    "urgency_indicators": loop_execution.resolved_context.urgency_indicators,
                }

                if loop_execution.resolved_context.primary_object:
                    details["resolved_context"]["primary_object"] = {
                        "type": loop_execution.resolved_context.primary_object.get(
                            "type", "unknown"
                        ),
                        "key": loop_execution.resolved_context.primary_object.get(
                            "key", ""
                        ),
                        "title": loop_execution.resolved_context.primary_object.get(
                            "title", ""
                        )[
                            :100
                        ],  # Truncate
                    }

            # Add execution plan details
            if loop_execution.execution_plan:
                details["execution_plan"] = {
                    "primary_actions_count": len(
                        loop_execution.execution_plan.primary_actions
                    ),
                    "backup_actions_count": len(
                        loop_execution.execution_plan.backup_actions
                    ),
                    "overall_confidence": loop_execution.execution_plan.overall_confidence,
                    "overall_safety": loop_execution.execution_plan.overall_safety.value,
                    "estimated_duration": loop_execution.execution_plan.estimated_duration_minutes,
                    "human_approval_needed": loop_execution.execution_plan.human_approval_needed,
                    "automation_mode": loop_execution.execution_plan.automation_mode.value,
                }

                # Add action summaries
                details["execution_plan"]["primary_actions"] = [
                    {
                        "action_type": action.action_type.value,
                        "target": action.target,
                        "confidence": action.confidence_score,
                        "estimated_duration": action.estimated_duration,
                        "is_destructive": action.is_destructive,
                        "safety_level": action.safety_level.value,
                    }
                    for action in loop_execution.execution_plan.primary_actions
                ]

            # Add execution results summary
            if loop_execution.execution_results:
                details["execution_results"] = [
                    {
                        "action_type": result.action.action_type.value,
                        "target": result.action.target,
                        "status": result.status.value,
                        "duration_seconds": result.duration_seconds,
                        "retry_count": result.retry_count,
                        "error_message": result.error_message,
                        "has_result_data": bool(result.result_data),
                    }
                    for result in loop_execution.execution_results
                ]

            # Add verification results summary
            if loop_execution.verification_results:
                details["verification_results"] = [
                    {
                        "verification_passed": result.verification_passed,
                        "overall_score": result.overall_score,
                        "status": result.verification_status.value,
                        "passed_checks": result.passed_checks,
                        "total_checks": result.total_checks,
                        "critical_issues_count": len(result.critical_issues),
                        "recommendations_count": len(result.recommendations),
                    }
                    for result in loop_execution.verification_results
                ]

            # Add generated reports summary
            if loop_execution.generated_reports:
                details["generated_reports"] = [
                    {
                        "report_id": report.report_id,
                        "report_type": report.report_type.value,
                        "priority": report.priority.value,
                        "title": report.title,
                        "target_channels": [
                            channel.value for channel in report.target_channels
                        ],
                        "successful_deliveries": [
                            channel.value for channel in report.successful_deliveries
                        ],
                        "failed_deliveries": list(report.failed_deliveries.keys()),
                        "generated_at": report.generated_at.isoformat(),
                    }
                    for report in loop_execution.generated_reports
                ]

            # Add learning outcomes summary
            if loop_execution.learning_outcomes:
                details["learning_outcomes"] = [
                    {
                        "trigger": outcome.trigger.value,
                        "update_type": outcome.update_type.value,
                        "success": outcome.success,
                        "learned_patterns_count": len(outcome.learned_patterns),
                        "confidence_delta": outcome.confidence_delta,
                        "importance_score": outcome.importance_score,
                        "user_id": outcome.user_id,
                        "error_message": outcome.error_message,
                    }
                    for outcome in loop_execution.learning_outcomes
                ]

            return details

        except Exception as e:
            logger.error(
                f"Failed to get loop details for {loop_id}: {e}", exc_info=True
            )
            return {"error": str(e)}

    async def approve_loop(
        self, loop_id: str, approved: bool, user_id: str, reason: str = ""
    ) -> bool:
        """Approve or reject a pending loop execution"""

        if not self.orchestrator:
            return False

        return await self.orchestrator.approve_pending_loop(
            loop_id, approved, user_id, reason
        )

    async def escalate_loop(
        self, loop_id: str, reason: str, escalation_level: str = "management"
    ) -> bool:
        """Escalate a loop execution to human intervention"""

        if not self.orchestrator:
            return False

        return await self.orchestrator.escalate_loop(loop_id, reason, escalation_level)

    async def update_configuration(self, new_config: OrchestrationConfig) -> bool:
        """Update the orchestration configuration"""

        try:
            self.config = new_config

            if self.orchestrator:
                self.orchestrator.config = new_config
                logger.info("Orchestration configuration updated")

            return True

        except Exception as e:
            logger.error(f"Failed to update configuration: {e}", exc_info=True)
            return False


# Global system instance
_phase5_system: Optional[Phase5System] = None


async def initialize_phase5_system(
    workspace_path: Optional[str] = None,
    org_key: str = "default",
    config: Optional[OrchestrationConfig] = None,
) -> Phase5System:
    """Initialize the global Phase 5.0 system instance"""

    global _phase5_system

    if _phase5_system and _phase5_system.is_running:
        logger.warning("Phase 5.0 system already initialized and running")
        return _phase5_system

    _phase5_system = Phase5System(workspace_path, org_key, config)
    await _phase5_system.initialize()

    return _phase5_system


async def get_phase5_system() -> Optional[Phase5System]:
    """Get the global Phase 5.0 system instance"""

    return _phase5_system


async def shutdown_phase5_system() -> None:
    """Shutdown the global Phase 5.0 system instance"""

    global _phase5_system

    if _phase5_system:
        await _phase5_system.shutdown()
        _phase5_system = None


# Convenience functions for common use cases


async def start_autonomous_jira_workflow(
    issue_key: str,
    workspace_path: Optional[str] = None,
    mode: OrchestrationMode = OrchestrationMode.SEMI_AUTONOMOUS,
) -> Optional[str]:
    """
    Start an autonomous workflow for a Jira issue

    This is a high-level function that:
    1. Fetches the issue details from Jira
    2. Creates a synthetic event
    3. Starts the closed-loop execution
    """

    try:
        system = await get_phase5_system()
        if not system:
            logger.error("Phase 5.0 system not initialized")
            return None

        # Simulate a Jira assignment event
        issue_data = {
            "key": issue_key,
            "synthetic_event": True,
            "triggered_manually": True,
        }

        return await system.handle_jira_event("issue_assigned", issue_data)

    except Exception as e:
        logger.error(
            f"Failed to start autonomous Jira workflow for {issue_key}: {e}",
            exc_info=True,
        )
        return None


async def trigger_pr_autofix(
    pr_number: int,
    repository: str,
    comment_text: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> Optional[str]:
    """
    Trigger autonomous PR fixing workflow

    This analyzes PR comments and automatically fixes issues
    """

    try:
        system = await get_phase5_system()
        if not system:
            logger.error("Phase 5.0 system not initialized")
            return None

        pr_data = {
            "number": pr_number,
            "repository": repository,
            "synthetic_event": True,
            "triggered_manually": True,
        }

        comment_data = {"body": comment_text or "Auto-fix requested", "synthetic": True}

        return await system.handle_github_event("pr_comment", pr_data, comment_data)

    except Exception as e:
        logger.error(
            f"Failed to trigger PR autofix for {repository}#{pr_number}: {e}",
            exc_info=True,
        )
        return None


async def handle_ci_failure_autonomously(
    repository: str,
    branch: str,
    build_id: str,
    error_details: Optional[Dict[str, Any]] = None,
    workspace_path: Optional[str] = None,
) -> Optional[str]:
    """
    Handle CI failures autonomously

    This diagnoses CI failures and attempts to fix them automatically
    """

    try:
        system = await get_phase5_system()
        if not system:
            logger.error("Phase 5.0 system not initialized")
            return None

        build_data = {
            "build_id": build_id,
            "status": "failed",
            "error_details": error_details or {},
            "synthetic_event": True,
            "triggered_manually": True,
        }

        return await system.handle_ci_event(
            "build_failed", build_data, repository, branch
        )

    except Exception as e:
        logger.error(
            f"Failed to handle CI failure for {repository}/{branch}: {e}", exc_info=True
        )
        return None
