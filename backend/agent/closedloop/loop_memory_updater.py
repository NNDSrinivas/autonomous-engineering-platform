"""
Phase 5.0 — Loop Memory Updater (Learning & Adaptation)

Updates system memory based on execution outcomes, verification results, and user feedback
to continuously improve autonomous operations. Integrates with existing learning infrastructure
and contextual bandit systems for adaptive parameter selection.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

# Phase 5.0 Components
from backend.agent.closedloop.execution_controller import (
    ExecutionResult,
    ExecutionStatus,
)
from backend.agent.closedloop.verification_engine import VerificationResult
from backend.agent.closedloop.auto_planner import (
    PlannedAction,
    ActionType,
    ExecutionPlan,
)
from backend.agent.closedloop.context_resolver import ResolvedContext
from backend.agent.closedloop.report_dispatcher import GeneratedReport

# Existing Memory & Learning Infrastructure
from backend.agent.memory.learning_engine import (
    LearningEngine,
    learn_from_approval,
    learn_from_rejection,
)
from backend.agent.memory.memory_manager import MemoryManager
from backend.agent.memory.memory_capture import MemoryCapture
from backend.agent.memory.memory_types import TaskMemory, ConversationalMemory
from backend.services.learning_service import LearningService, ThompsonSamplingBandit


logger = logging.getLogger(__name__)


class LearningTrigger(Enum):
    """Types of events that trigger learning"""

    EXECUTION_SUCCESS = "execution_success"
    EXECUTION_FAILURE = "execution_failure"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    USER_APPROVAL = "user_approval"
    USER_REJECTION = "user_rejection"
    PLAN_APPROVED = "plan_approved"
    PLAN_CANCELLED = "plan_cancelled"
    SAFETY_VIOLATION = "safety_violation"
    PERFORMANCE_METRIC = "performance_metric"
    CONTEXTUAL_FEEDBACK = "contextual_feedback"


class MemoryUpdateType(Enum):
    """Types of memory updates"""

    PATTERN_LEARNING = "pattern_learning"
    PREFERENCE_UPDATE = "preference_update"
    EXECUTION_HISTORY = "execution_history"
    CONTEXT_ASSOCIATION = "context_association"
    PARAMETER_OPTIMIZATION = "parameter_optimization"
    QUALITY_METRICS = "quality_metrics"
    SAFETY_RULES = "safety_rules"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"


@dataclass
class LearningOutcome:
    """Result of a learning operation"""

    trigger: LearningTrigger
    update_type: MemoryUpdateType
    success: bool

    # What was learned
    learned_patterns: List[str] = field(default_factory=list)
    updated_preferences: Dict[str, Any] = field(default_factory=dict)
    parameter_adjustments: Dict[str, float] = field(default_factory=dict)

    # Context and metadata
    user_id: Optional[str] = None
    context_key: Optional[str] = None
    confidence_delta: float = 0.0
    importance_score: float = 0.5

    # Tracking
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    memory_ids: List[str] = field(default_factory=list)

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class MemoryUpdateRequest:
    """Request to update system memory"""

    trigger: LearningTrigger

    # Source data
    execution_result: Optional[ExecutionResult] = None
    verification_result: Optional[VerificationResult] = None
    plan: Optional[ExecutionPlan] = None
    context: Optional[ResolvedContext] = None
    report: Optional[GeneratedReport] = None

    # User feedback
    user_feedback: Optional[Dict[str, Any]] = None
    approval_status: Optional[bool] = None
    feedback_rating: Optional[int] = None  # -1, 0, +1

    # Metadata
    user_id: Optional[str] = None
    workspace_path: Optional[str] = None
    task_id: Optional[str] = None

    # Learning parameters
    learning_rate: float = 1.0
    importance_multiplier: float = 1.0
    immediate_update: bool = True


class LoopMemoryUpdater:
    """
    Closed-loop memory and learning system for continuous improvement

    Key responsibilities:
    1. Process execution outcomes and learn from successes/failures
    2. Update user preferences based on approvals/rejections
    3. Optimize AI parameters using contextual bandits
    4. Store execution patterns for future reference
    5. Maintain and prune memory efficiently
    6. Adapt planning and execution strategies over time
    """

    def __init__(
        self, db_session, workspace_path: Optional[str] = None, org_key: str = "default"
    ):
        self.db = db_session
        self.workspace_path = workspace_path
        self.org_key = org_key

        # Existing learning infrastructure
        self.learning_engine = LearningEngine(db_session) if db_session else None
        self.memory_manager = MemoryManager(db_session) if db_session else None
        self.memory_capture = MemoryCapture(db_session) if db_session else None
        self.learning_service = LearningService()
        self.bandit = ThompsonSamplingBandit(org_key)

        # Learning configuration
        self.learning_enabled = True
        self.batch_learning = True
        self.learning_buffer: List[MemoryUpdateRequest] = []
        self.buffer_size = 50
        self.flush_interval_minutes = 15

        # Pattern detection
        self.pattern_thresholds = {
            "execution_success_rate": 0.8,  # Learn patterns with >80% success
            "verification_pass_rate": 0.9,  # Learn quality patterns with >90% pass
            "user_approval_rate": 0.85,  # Learn preferences with >85% approval
            "minimum_occurrences": 3,  # Need at least 3 occurrences to learn
        }

        # Memory optimization settings
        self.auto_maintenance = True
        self.maintenance_interval_hours = 24
        self.last_maintenance = datetime.now(timezone.utc)

        # Tracking and metrics
        self.learning_stats: Dict[LearningTrigger, Dict[str, int]] = {
            trigger: {"attempted": 0, "successful": 0, "failed": 0}
            for trigger in LearningTrigger
        }
        self.recent_outcomes: List[LearningOutcome] = []
        self.max_recent_outcomes = 100

    async def process_execution_outcome(
        self,
        execution_result: ExecutionResult,
        verification_result: Optional[VerificationResult] = None,
        plan: Optional[ExecutionPlan] = None,
        context: Optional[ResolvedContext] = None,
    ) -> List[LearningOutcome]:
        """Process execution outcome and update memory"""

        outcomes = []

        try:
            # Determine learning trigger based on execution status
            if execution_result.status == ExecutionStatus.COMPLETED:
                trigger = LearningTrigger.EXECUTION_SUCCESS

                # Also check verification status
                if verification_result:
                    if verification_result.verification_passed:
                        outcomes.append(
                            await self._learn_from_success(
                                execution_result, verification_result, plan, context
                            )
                        )
                    else:
                        outcomes.append(
                            await self._learn_from_verification_failure(
                                execution_result, verification_result, plan, context
                            )
                        )

            elif execution_result.status == ExecutionStatus.FAILED:
                trigger = LearningTrigger.EXECUTION_FAILURE
                outcomes.append(
                    await self._learn_from_failure(execution_result, plan, context)
                )

            # Update contextual bandit for parameter optimization
            if context and execution_result.action:
                bandit_outcome = await self._update_parameter_learning(
                    execution_result, verification_result, context
                )
                if bandit_outcome:
                    outcomes.append(bandit_outcome)

            # Store execution history
            history_outcome = await self._capture_execution_history(
                execution_result, verification_result, plan, context
            )
            if history_outcome:
                outcomes.append(history_outcome)

            # Update statistics
            self.learning_stats[trigger]["attempted"] += 1
            successful_outcomes = [o for o in outcomes if o.success]
            self.learning_stats[trigger]["successful"] += len(successful_outcomes)
            self.learning_stats[trigger]["failed"] += len(outcomes) - len(
                successful_outcomes
            )

            # Track recent outcomes
            self.recent_outcomes.extend(outcomes)
            self.recent_outcomes = self.recent_outcomes[-self.max_recent_outcomes :]

            logger.info(
                f"Processed execution outcome: {len(outcomes)} learning outcomes"
            )

        except Exception as e:
            logger.error(f"Failed to process execution outcome: {e}", exc_info=True)
            error_outcome = LearningOutcome(
                trigger=LearningTrigger.EXECUTION_SUCCESS,
                update_type=MemoryUpdateType.EXECUTION_HISTORY,
                success=False,
                error_message=str(e),
            )
            outcomes.append(error_outcome)

        return outcomes

    async def process_user_feedback(
        self,
        user_feedback: Dict[str, Any],
        execution_result: Optional[ExecutionResult] = None,
        plan: Optional[ExecutionPlan] = None,
        context: Optional[ResolvedContext] = None,
    ) -> List[LearningOutcome]:
        """Process user feedback and update preferences"""

        outcomes = []

        try:
            approval_status = user_feedback.get("approved")
            rating = user_feedback.get("rating", 0)  # -1, 0, +1
            feedback_text = user_feedback.get("comment", "")
            user_feedback.get("user_id")

            if approval_status is not None:
                if approval_status:
                    # User approved - learn positive patterns
                    outcomes.append(
                        await self._learn_from_user_approval(
                            user_feedback, execution_result, plan, context
                        )
                    )
                else:
                    # User rejected - learn what to avoid
                    outcomes.append(
                        await self._learn_from_user_rejection(
                            user_feedback, execution_result, plan, context
                        )
                    )

            # Process contextual feedback (ratings, comments)
            if rating != 0 or feedback_text:
                outcomes.append(
                    await self._process_contextual_feedback(
                        user_feedback, execution_result, context
                    )
                )

            # Update bandit learning with explicit feedback
            if rating != 0 and execution_result and context:
                bandit_outcome = await self._record_bandit_feedback(
                    rating, execution_result, context
                )
                if bandit_outcome:
                    outcomes.append(bandit_outcome)

            logger.info(f"Processed user feedback: {len(outcomes)} learning outcomes")

        except Exception as e:
            logger.error(f"Failed to process user feedback: {e}", exc_info=True)
            error_outcome = LearningOutcome(
                trigger=LearningTrigger.USER_APPROVAL,
                update_type=MemoryUpdateType.PREFERENCE_UPDATE,
                success=False,
                error_message=str(e),
            )
            outcomes.append(error_outcome)

        return outcomes

    async def process_plan_lifecycle(
        self,
        plan: ExecutionPlan,
        lifecycle_event: str,  # "created", "approved", "cancelled", "completed"
        context: Optional[ResolvedContext] = None,
        user_feedback: Optional[Dict[str, Any]] = None,
    ) -> List[LearningOutcome]:
        """Process plan lifecycle events for learning"""

        outcomes = []

        try:
            if lifecycle_event == "approved":
                outcomes.append(
                    await self._learn_from_plan_approval(plan, context, user_feedback)
                )

            elif lifecycle_event == "cancelled":
                outcomes.append(
                    await self._learn_from_plan_cancellation(
                        plan, context, user_feedback
                    )
                )

            elif lifecycle_event == "completed":
                # This is handled by process_execution_outcome
                pass

            logger.info(
                f"Processed plan {lifecycle_event}: {len(outcomes)} learning outcomes"
            )

        except Exception as e:
            logger.error(f"Failed to process plan lifecycle: {e}", exc_info=True)
            error_outcome = LearningOutcome(
                trigger=LearningTrigger.PLAN_APPROVED,
                update_type=MemoryUpdateType.PATTERN_LEARNING,
                success=False,
                error_message=str(e),
            )
            outcomes.append(error_outcome)

        return outcomes

    async def run_memory_maintenance(self, force: bool = False) -> Dict[str, Any]:
        """Run memory maintenance and optimization"""

        # Check if maintenance is needed
        time_since_maintenance = datetime.now(timezone.utc) - self.last_maintenance
        if (
            not force
            and time_since_maintenance.total_seconds()
            < self.maintenance_interval_hours * 3600
        ):
            return {"skipped": True, "reason": "Too soon since last maintenance"}

        maintenance_stats = {}

        try:
            # Run memory manager maintenance
            if self.memory_manager:
                stats = await self.memory_manager.run_maintenance()
                maintenance_stats.update(stats)

            # Flush learning buffer if batch learning is enabled
            if self.batch_learning and self.learning_buffer:
                flushed = await self._flush_learning_buffer()
                maintenance_stats["learning_buffer_flushed"] = flushed

            # Update learning statistics
            maintenance_stats["learning_stats"] = dict(self.learning_stats)

            # Clean up recent outcomes
            self.recent_outcomes = self.recent_outcomes[-self.max_recent_outcomes :]
            maintenance_stats["recent_outcomes_count"] = len(self.recent_outcomes)

            self.last_maintenance = datetime.now(timezone.utc)
            maintenance_stats["last_maintenance"] = self.last_maintenance.isoformat()

            logger.info(f"Memory maintenance completed: {maintenance_stats}")

        except Exception as e:
            logger.error(f"Memory maintenance failed: {e}", exc_info=True)
            maintenance_stats["error"] = str(e)

        return maintenance_stats

    async def get_learning_insights(
        self, user_id: Optional[str] = None, days_back: int = 30
    ) -> Dict[str, Any]:
        """Get insights about learning performance and patterns"""

        insights = {
            "learning_stats": dict(self.learning_stats),
            "recent_outcomes": len(self.recent_outcomes),
            "patterns_learned": {},
            "parameter_optimization": {},
            "memory_health": {},
            "recommendations": [],
        }

        try:
            # Analyze recent outcomes
            successful_outcomes = [o for o in self.recent_outcomes if o.success]
            if self.recent_outcomes:
                success_rate = len(successful_outcomes) / len(self.recent_outcomes)
                insights["overall_success_rate"] = success_rate

            # Analyze patterns by update type
            for outcome in successful_outcomes:
                update_type = outcome.update_type.value
                if update_type not in insights["patterns_learned"]:
                    insights["patterns_learned"][update_type] = {
                        "count": 0,
                        "patterns": set(),
                        "avg_confidence": 0.0,
                    }

                pattern_info = insights["patterns_learned"][update_type]
                pattern_info["count"] += 1
                pattern_info["patterns"].update(outcome.learned_patterns)
                pattern_info["avg_confidence"] += outcome.confidence_delta

            # Convert sets to lists for JSON serialization
            for pattern_type in insights["patterns_learned"]:
                pattern_info = insights["patterns_learned"][pattern_type]
                pattern_info["patterns"] = list(pattern_info["patterns"])
                if pattern_info["count"] > 0:
                    pattern_info["avg_confidence"] /= pattern_info["count"]

            # Get bandit performance from learning service
            if hasattr(self.learning_service, "get_learning_stats"):
                bandit_stats = await self.learning_service.get_learning_stats(
                    self.org_key
                )
                insights["parameter_optimization"] = bandit_stats

            # Memory health metrics
            if self.memory_manager:
                insights["memory_health"] = {
                    "last_maintenance": self.last_maintenance.isoformat(),
                    "auto_maintenance_enabled": self.auto_maintenance,
                }

            # Generate recommendations
            insights["recommendations"] = self._generate_learning_recommendations(
                insights
            )

        except Exception as e:
            logger.error(f"Failed to generate learning insights: {e}", exc_info=True)
            insights["error"] = str(e)

        return insights

    # Private helper methods for specific learning scenarios

    async def _learn_from_success(
        self,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Learn patterns from successful executions"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.EXECUTION_SUCCESS,
            update_type=MemoryUpdateType.PATTERN_LEARNING,
            success=True,
        )

        try:
            action = execution_result.action
            learned_patterns = []

            # Extract successful patterns
            if execution_result.result_data:
                if execution_result.result_data.get("pr_created"):
                    learned_patterns.append("successful_pr_creation")

                if execution_result.result_data.get("tests_passed"):
                    learned_patterns.append("test_passing_implementation")

                if execution_result.result_data.get("comment_added"):
                    learned_patterns.append("effective_communication")

            # Learn from verification results
            if verification_result and verification_result.verification_passed:
                if verification_result.overall_score > 0.9:
                    learned_patterns.append("high_quality_execution")

                if not verification_result.critical_issues:
                    learned_patterns.append("safe_implementation")

            # Use existing learning engine to capture patterns
            if self.learning_engine and context and context.primary_object:
                user_id = context.primary_object.get(
                    "assignee"
                ) or context.primary_object.get("reporter")
                if user_id:
                    approval_data = {
                        "task_id": action.target,
                        "action_type": action.action_type.value,
                        "confidence": action.confidence_score,
                        "patterns": learned_patterns,
                        "execution_time": execution_result.duration_seconds,
                        "quality_score": (
                            verification_result.overall_score
                            if verification_result
                            else None
                        ),
                    }

                    success = await learn_from_approval(user_id, approval_data, self.db)
                    outcome.success = success
                    outcome.user_id = user_id

            outcome.learned_patterns = learned_patterns
            outcome.confidence_delta = (
                0.1  # Increase confidence for successful patterns
            )

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from success: {e}", exc_info=True)

        return outcome

    async def _learn_from_failure(
        self,
        execution_result: ExecutionResult,
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Learn from execution failures"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.EXECUTION_FAILURE,
            update_type=MemoryUpdateType.PATTERN_LEARNING,
            success=False,
        )

        try:
            action = execution_result.action
            failure_patterns = []

            # Extract failure patterns
            error_msg = execution_result.error_message or ""
            error_lower = error_msg.lower()

            if "permission" in error_lower or "unauthorized" in error_lower:
                failure_patterns.append("permission_error_pattern")

            if "timeout" in error_lower:
                failure_patterns.append("timeout_pattern")

            if "network" in error_lower or "connection" in error_lower:
                failure_patterns.append("network_error_pattern")

            if "syntax" in error_lower or "parse" in error_lower:
                failure_patterns.append("syntax_error_pattern")

            # Use existing learning engine for rejection learning
            if self.learning_engine and context and context.primary_object:
                user_id = context.primary_object.get(
                    "assignee"
                ) or context.primary_object.get("reporter")
                if user_id:
                    rejection_data = {
                        "task_id": action.target,
                        "action_type": action.action_type.value,
                        "reason": execution_result.error_message,
                        "patterns": failure_patterns,
                        "retry_count": execution_result.retry_count,
                    }

                    success = await learn_from_rejection(
                        user_id, rejection_data, self.db
                    )
                    outcome.success = success
                    outcome.user_id = user_id

            outcome.learned_patterns = failure_patterns
            outcome.confidence_delta = (
                -0.05
            )  # Slightly decrease confidence for failed patterns

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from failure: {e}", exc_info=True)

        return outcome

    async def _learn_from_verification_failure(
        self,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Learn from verification failures"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.VERIFICATION_FAILED,
            update_type=MemoryUpdateType.QUALITY_METRICS,
            success=False,
        )

        try:
            quality_patterns = []

            # Extract quality issues
            if verification_result.critical_issues:
                for issue in verification_result.critical_issues:
                    issue_text = str(issue).lower() if issue else ""
                    if "security" in issue_text:
                        quality_patterns.append("security_issue_pattern")
                    if "performance" in issue_text:
                        quality_patterns.append("performance_issue_pattern")
                    if "style" in issue_text:
                        quality_patterns.append("style_issue_pattern")

            # Learn quality preferences
            if self.memory_capture and context:
                memory_entry = TaskMemory(
                    content=f"Quality issue in {execution_result.action.action_type.value}: {verification_result.critical_issues}",
                    task_id=execution_result.action.target,
                    action_taken=execution_result.action.action_type.value,
                    result="verification_failed",
                    user_approved=False,
                    user_feedback=f"Quality score: {verification_result.overall_score}",
                    importance=0.7,  # High importance for quality issues
                )

                success = await self.memory_capture.capture_memory(memory_entry)
                outcome.success = success

            outcome.learned_patterns = quality_patterns
            outcome.confidence_delta = -0.1  # Decrease confidence for quality issues

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(
                f"Failed to learn from verification failure: {e}", exc_info=True
            )

        return outcome

    async def _learn_from_user_approval(
        self,
        user_feedback: Dict[str, Any],
        execution_result: Optional[ExecutionResult],
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Learn from explicit user approval"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.USER_APPROVAL,
            update_type=MemoryUpdateType.PREFERENCE_UPDATE,
            success=True,
        )

        try:
            user_id = user_feedback.get("user_id")

            if self.learning_engine and user_id and execution_result:
                approval_data = {
                    "task_id": execution_result.action.target,
                    "action_type": execution_result.action.action_type.value,
                    "approved": True,
                    "comment": user_feedback.get("comment", ""),
                    "files_changed": (
                        execution_result.result_data.get("files_modified", [])
                        if execution_result.result_data
                        else []
                    ),
                    "execution_time": execution_result.duration_seconds,
                }

                success = await learn_from_approval(user_id, approval_data, self.db)
                outcome.success = success
                outcome.user_id = user_id
                outcome.learned_patterns = ["user_approved_pattern"]
                outcome.confidence_delta = 0.15  # Strong positive signal

                # Update preferences
                outcome.updated_preferences = {
                    "action_type": execution_result.action.action_type.value,
                    "approved": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from user approval: {e}", exc_info=True)

        return outcome

    async def _learn_from_user_rejection(
        self,
        user_feedback: Dict[str, Any],
        execution_result: Optional[ExecutionResult],
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Learn from explicit user rejection"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.USER_REJECTION,
            update_type=MemoryUpdateType.PREFERENCE_UPDATE,
            success=False,
        )

        try:
            user_id = user_feedback.get("user_id")
            rejection_reason = user_feedback.get("comment", "No reason provided")

            if self.learning_engine and user_id and execution_result:
                rejection_data = {
                    "task_id": execution_result.action.target,
                    "action_type": execution_result.action.action_type.value,
                    "reason": rejection_reason,
                    "approved": False,
                    "files_changed": (
                        execution_result.result_data.get("files_modified", [])
                        if execution_result.result_data
                        else []
                    ),
                }

                success = await learn_from_rejection(user_id, rejection_data, self.db)
                outcome.success = success
                outcome.user_id = user_id
                outcome.learned_patterns = ["user_rejected_pattern"]
                outcome.confidence_delta = -0.15  # Strong negative signal

                # Update preferences
                outcome.updated_preferences = {
                    "action_type": execution_result.action.action_type.value,
                    "approved": False,
                    "reason": rejection_reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from user rejection: {e}", exc_info=True)

        return outcome

    async def _process_contextual_feedback(
        self,
        user_feedback: Dict[str, Any],
        execution_result: Optional[ExecutionResult],
        context: Optional[ResolvedContext],
    ) -> LearningOutcome:
        """Process contextual feedback (ratings, comments)"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.CONTEXTUAL_FEEDBACK,
            update_type=MemoryUpdateType.PREFERENCE_UPDATE,
            success=True,
        )

        try:
            rating = user_feedback.get("rating", 0)
            comment = user_feedback.get("comment", "")
            user_id = user_feedback.get("user_id")

            # Capture contextual memory
            if self.memory_capture and user_id:
                memory_content = f"User feedback: Rating {rating}/5"
                if comment:
                    memory_content += f", Comment: {comment}"

                memory_entry = ConversationalMemory(
                    content=memory_content,
                    user_id=user_id,
                    learned_from="explicit",
                    preference_key="feedback_rating",
                    preference_value=str(rating),
                    confidence=min(
                        abs(rating) / 5.0, 1.0
                    ),  # Convert rating to confidence
                )

                success = await self.memory_capture.capture_memory(memory_entry)
                outcome.success = success
                outcome.user_id = user_id

                # Learn patterns from feedback text
                if comment:
                    feedback_patterns = self._extract_feedback_patterns(comment)
                    outcome.learned_patterns = feedback_patterns
                    outcome.confidence_delta = (
                        rating - 3
                    ) * 0.05  # Neutral is 3, so adjust accordingly

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to process contextual feedback: {e}", exc_info=True)

        return outcome

    async def _update_parameter_learning(
        self,
        execution_result: ExecutionResult,
        verification_result: Optional[VerificationResult],
        context: ResolvedContext,
    ) -> Optional[LearningOutcome]:
        """Update contextual bandit for parameter optimization"""

        try:
            # Create context for bandit learning
            bandit_context = self._create_bandit_context(execution_result, context)

            # Determine success based on execution and verification
            success = execution_result.status == ExecutionStatus.COMPLETED
            if verification_result:
                success = success and verification_result.verification_passed

            # Record feedback for the bandit
            context_key = self.bandit._get_context_key(bandit_context)
            arm_name = self._get_arm_name(execution_result.action)

            # Convert success to rating (-1, 0, +1)
            rating = 1 if success else -1

            await self.bandit.record_feedback(context_key, arm_name, rating)

            outcome = LearningOutcome(
                trigger=LearningTrigger.PERFORMANCE_METRIC,
                update_type=MemoryUpdateType.PARAMETER_OPTIMIZATION,
                success=True,
                context_key=context_key,
                parameter_adjustments={arm_name: rating},
            )

            return outcome

        except Exception as e:
            logger.error(f"Failed to update parameter learning: {e}", exc_info=True)
            return None

    async def _record_bandit_feedback(
        self, rating: int, execution_result: ExecutionResult, context: ResolvedContext
    ) -> Optional[LearningOutcome]:
        """Record explicit user feedback for bandit learning"""

        try:
            bandit_context = self._create_bandit_context(execution_result, context)
            context_key = self.bandit._get_context_key(bandit_context)
            arm_name = self._get_arm_name(execution_result.action)

            await self.bandit.record_feedback(context_key, arm_name, rating)

            outcome = LearningOutcome(
                trigger=LearningTrigger.CONTEXTUAL_FEEDBACK,
                update_type=MemoryUpdateType.PARAMETER_OPTIMIZATION,
                success=True,
                context_key=context_key,
                parameter_adjustments={arm_name: rating},
            )

            return outcome

        except Exception as e:
            logger.error(f"Failed to record bandit feedback: {e}", exc_info=True)
            return None

    async def _capture_execution_history(
        self,
        execution_result: ExecutionResult,
        verification_result: Optional[VerificationResult],
        plan: Optional[ExecutionPlan],
        context: Optional[ResolvedContext],
    ) -> Optional[LearningOutcome]:
        """Capture execution history for future reference"""

        try:
            if not self.memory_capture:
                return None

            # Create task memory entry
            task_memory = TaskMemory(
                content=f"Executed {execution_result.action.action_type.value} on {execution_result.action.target}",
                task_id=execution_result.action.target,
                step="execution",
                action_taken=execution_result.action.action_type.value,
                result=(
                    "success"
                    if execution_result.status == ExecutionStatus.COMPLETED
                    else "failed"
                ),
                error=execution_result.error_message,
                files_changed=(
                    execution_result.result_data.get("files_modified", [])
                    if execution_result.result_data
                    else []
                ),
                user_approved=None,  # Will be updated if user provides feedback
                confidence=execution_result.action.confidence_score,
                importance=(
                    0.7 if execution_result.status == ExecutionStatus.COMPLETED else 0.5
                ),
            )

            # Add verification results if available
            if verification_result:
                task_memory.user_feedback = f"Quality score: {verification_result.overall_score}, Passed: {verification_result.verification_passed}"
                if verification_result.critical_issues:
                    task_memory.error = f"Quality issues: {', '.join(str(issue) for issue in verification_result.critical_issues)}"

            success = await self.memory_capture.capture_memory(task_memory)

            outcome = LearningOutcome(
                trigger=(
                    LearningTrigger.EXECUTION_SUCCESS
                    if execution_result.status == ExecutionStatus.COMPLETED
                    else LearningTrigger.EXECUTION_FAILURE
                ),
                update_type=MemoryUpdateType.EXECUTION_HISTORY,
                success=success,
            )

            return outcome

        except Exception as e:
            logger.error(f"Failed to capture execution history: {e}", exc_info=True)
            return None

    async def _learn_from_plan_approval(
        self,
        plan: ExecutionPlan,
        context: Optional[ResolvedContext],
        user_feedback: Optional[Dict[str, Any]],
    ) -> LearningOutcome:
        """Learn from plan approval patterns"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.PLAN_APPROVED,
            update_type=MemoryUpdateType.WORKFLOW_OPTIMIZATION,
            success=True,
        )

        try:
            plan_patterns = []

            # Extract plan characteristics that led to approval
            if plan.overall_confidence > 0.8:
                plan_patterns.append("high_confidence_plan")

            if len(plan.primary_actions) <= 3:
                plan_patterns.append("concise_plan")

            if plan.overall_safety.value == "safe":
                plan_patterns.append("safe_plan")

            # Learn plan approval preferences
            if user_feedback and user_feedback.get("user_id"):
                user_id = user_feedback["user_id"]
                approval_data = {
                    "plan_id": f"plan_{int(datetime.now().timestamp())}",
                    "action_count": len(plan.primary_actions),
                    "confidence": plan.overall_confidence,
                    "safety_level": plan.overall_safety.value,
                    "patterns": plan_patterns,
                    "approved": True,
                }

                if self.learning_engine:
                    success = await learn_from_approval(user_id, approval_data, self.db)
                    outcome.success = success
                    outcome.user_id = user_id

            outcome.learned_patterns = plan_patterns
            outcome.confidence_delta = 0.1

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from plan approval: {e}", exc_info=True)

        return outcome

    async def _learn_from_plan_cancellation(
        self,
        plan: ExecutionPlan,
        context: Optional[ResolvedContext],
        user_feedback: Optional[Dict[str, Any]],
    ) -> LearningOutcome:
        """Learn from plan cancellation patterns"""

        outcome = LearningOutcome(
            trigger=LearningTrigger.PLAN_CANCELLED,
            update_type=MemoryUpdateType.WORKFLOW_OPTIMIZATION,
            success=False,
        )

        try:
            cancellation_patterns = []

            # Extract patterns that led to cancellation
            if plan.overall_confidence < 0.6:
                cancellation_patterns.append("low_confidence_plan")

            if len(plan.primary_actions) > 5:
                cancellation_patterns.append("overly_complex_plan")

            if plan.overall_safety.value in ["risky", "dangerous"]:
                cancellation_patterns.append("unsafe_plan")

            # Learn cancellation preferences
            if user_feedback and user_feedback.get("user_id"):
                user_id = user_feedback["user_id"]
                cancellation_reason = user_feedback.get("reason", "No reason provided")

                rejection_data = {
                    "plan_id": f"plan_{int(datetime.now().timestamp())}",
                    "reason": cancellation_reason,
                    "action_count": len(plan.primary_actions),
                    "confidence": plan.overall_confidence,
                    "patterns": cancellation_patterns,
                }

                if self.learning_engine:
                    success = await learn_from_rejection(
                        user_id, rejection_data, self.db
                    )
                    outcome.success = success
                    outcome.user_id = user_id

            outcome.learned_patterns = cancellation_patterns
            outcome.confidence_delta = -0.1

        except Exception as e:
            outcome.success = False
            outcome.error_message = str(e)
            logger.error(f"Failed to learn from plan cancellation: {e}", exc_info=True)

        return outcome

    async def _flush_learning_buffer(self) -> int:
        """Flush batched learning requests"""

        if not self.learning_buffer:
            return 0

        flushed_count = 0

        try:
            # Process all buffered requests
            for request in self.learning_buffer:
                try:
                    if (
                        request.trigger == LearningTrigger.EXECUTION_SUCCESS
                        and request.execution_result
                    ):
                        await self.process_execution_outcome(
                            request.execution_result,
                            request.verification_result,
                            request.plan,
                            request.context,
                        )
                    elif (
                        request.trigger
                        in [
                            LearningTrigger.USER_APPROVAL,
                            LearningTrigger.USER_REJECTION,
                        ]
                        and request.user_feedback
                    ):
                        await self.process_user_feedback(
                            request.user_feedback,
                            request.execution_result,
                            request.plan,
                            request.context,
                        )

                    flushed_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to flush learning request: {e}", exc_info=True
                    )

            # Clear the buffer
            self.learning_buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush learning buffer: {e}", exc_info=True)

        return flushed_count

    # Utility methods

    def _create_bandit_context(
        self, execution_result: ExecutionResult, context: ResolvedContext
    ) -> Dict[str, Any]:
        """Create context for bandit learning"""

        # Determine task type
        task_type = "unknown"
        if execution_result.action.action_type == ActionType.IMPLEMENT_FEATURE:
            task_type = "implementation"
        elif execution_result.action.action_type == ActionType.FIX_BUG:
            task_type = "bug_fix"
        elif execution_result.action.action_type == ActionType.ADD_COMMENT:
            task_type = "communication"

        # Determine input size bucket
        input_size_bucket = "small"
        if context.primary_object and context.primary_object.get("description"):
            desc_length = len(context.primary_object["description"].split())
            if desc_length > 200:
                input_size_bucket = "large"
            elif desc_length > 50:
                input_size_bucket = "medium"

        # Determine user experience level (placeholder - would need user profile)
        user_experience = "standard"

        return {
            "task_type": task_type,
            "input_size_bucket": input_size_bucket,
            "user_experience": user_experience,
        }

    def _get_arm_name(self, action: PlannedAction) -> str:
        """Get bandit arm name based on action characteristics"""

        # Map action to temperature/style
        if action.confidence_score > 0.9:
            return "precise"
        elif action.confidence_score > 0.7:
            return "balanced"
        else:
            return "creative"

    def _extract_feedback_patterns(self, feedback_text: str) -> List[str]:
        """Extract patterns from user feedback text"""

        patterns = []
        feedback_lower = feedback_text.lower()

        # Positive patterns
        if any(
            word in feedback_lower
            for word in ["good", "great", "excellent", "perfect", "awesome"]
        ):
            patterns.append("positive_feedback")

        if any(word in feedback_lower for word in ["fast", "quick", "efficient"]):
            patterns.append("speed_appreciation")

        if any(word in feedback_lower for word in ["clean", "clear", "readable"]):
            patterns.append("code_quality_appreciation")

        # Negative patterns
        if any(
            word in feedback_lower for word in ["slow", "confusing", "unclear", "wrong"]
        ):
            patterns.append("negative_feedback")

        if any(word in feedback_lower for word in ["bug", "error", "issue", "problem"]):
            patterns.append("quality_concern")

        return patterns

    def _generate_learning_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on learning insights"""

        recommendations = []

        success_rate = insights.get("overall_success_rate", 0.0)

        if success_rate < 0.7:
            recommendations.append(
                "Consider reducing action complexity or improving context resolution"
            )

        if success_rate > 0.9:
            recommendations.append(
                "Excellent learning performance - consider increasing automation confidence"
            )

        # Analyze pattern learning
        patterns_learned = insights.get("patterns_learned", {})

        if "pattern_learning" in patterns_learned:
            pattern_count = patterns_learned["pattern_learning"]["count"]
            if pattern_count < 5:
                recommendations.append(
                    "Increase pattern detection by encouraging more user feedback"
                )

        if "preference_update" in patterns_learned:
            pref_count = patterns_learned["preference_update"]["count"]
            if pref_count > 20:
                recommendations.append(
                    "Rich user preference data available - consider personalizing recommendations"
                )

        # Memory health
        memory_health = insights.get("memory_health", {})
        if memory_health and "last_maintenance" in memory_health:
            last_maintenance = datetime.fromisoformat(
                memory_health["last_maintenance"].replace("Z", "+00:00")
            )
            hours_since_maintenance = (
                datetime.now(timezone.utc) - last_maintenance
            ).total_seconds() / 3600

            if hours_since_maintenance > 48:
                recommendations.append("Run memory maintenance to optimize performance")

        return recommendations or [
            "System performing well - continue current learning patterns"
        ]
