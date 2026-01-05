"""
Phase 5.0 — Autonomous Planner with Safety (Never Acts Blindly)

Intelligent decision-making engine that plans autonomous actions based on resolved context.
Includes confidence scoring, safety thresholds, and escalation protocols.
Core principle: Never take action without sufficient context and confidence.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from backend.agent.closedloop.context_resolver import ResolvedContext, ContextType
from backend.agent.closedloop.event_ingestor import ProcessedEvent

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of autonomous actions the system can take"""

    # Jira actions
    ASSIGN_ISSUE = "assign_issue"
    UPDATE_STATUS = "update_status"
    ADD_COMMENT = "add_comment"
    CREATE_SUBTASK = "create_subtask"
    LINK_ISSUES = "link_issues"

    # GitHub actions
    CREATE_PR = "create_pr"
    REVIEW_PR = "review_pr"
    MERGE_PR = "merge_pr"
    CREATE_ISSUE = "create_issue"

    # Code actions
    FIX_BUG = "fix_bug"
    IMPLEMENT_FEATURE = "implement_feature"
    REFACTOR_CODE = "refactor_code"
    UPDATE_DOCUMENTATION = "update_documentation"
    WRITE_TESTS = "write_tests"

    # Compatibility actions for governance demos/tests
    CODE_EDIT = "code_edit"
    DOCUMENTATION_UPDATE = "documentation_update"
    AUTH_CONFIG = "auth_config"
    DATA_DELETION = "data_deletion"
    SECURITY_PATCH = "security_patch"
    ROLLBACK = "rollback"

    # Communication actions
    NOTIFY_TEAM = "notify_team"
    ESCALATE_ISSUE = "escalate_issue"
    REQUEST_CLARIFICATION = "request_clarification"

    # System actions
    RESTART_SERVICE = "restart_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    SCALE_RESOURCES = "scale_resources"

    # Meta actions
    GATHER_MORE_CONTEXT = "gather_more_context"
    WAIT_FOR_HUMAN = "wait_for_human"
    NO_ACTION_NEEDED = "no_action_needed"


class ActionPriority(Enum):
    """Priority levels for autonomous actions"""

    CRITICAL = "critical"  # Immediate action required (security, outages)
    HIGH = "high"  # Action needed within hours
    MEDIUM = "medium"  # Action needed within days
    LOW = "low"  # Action can wait
    DEFERRED = "deferred"  # Action should be reviewed by human


class SafetyLevel(Enum):
    """Safety levels for autonomous actions"""

    SAFE = "safe"  # Action is safe to execute autonomously
    CAUTIOUS = "cautious"  # Action needs additional checks
    RISKY = "risky"  # Action requires human approval
    DANGEROUS = "dangerous"  # Action should not be executed autonomously


class AutomationMode(Enum):
    """Automation modes for execution plans"""

    AUTONOMOUS = "autonomous"
    SEMI_AUTONOMOUS = "semi_autonomous"
    SUPERVISED = "supervised"
    MANUAL = "manual"


@dataclass
class PlannedAction:
    """A planned autonomous action with safety and confidence scoring"""

    action_type: ActionType
    priority: ActionPriority = ActionPriority.MEDIUM
    safety_level: SafetyLevel = SafetyLevel.CAUTIOUS

    # Confidence metrics
    confidence_score: float = 0.5  # 0.0 to 1.0
    context_completeness: float = 0.5  # 0.0 to 1.0
    historical_success: float = 0.5  # 0.0 to 1.0 (similar actions in past)

    # Action details
    target: str = ""  # What the action targets (issue key, PR number, etc.)
    parameters: Dict[str, Any] = field(
        default_factory=dict
    )  # Action-specific parameters

    # Safety and execution
    prerequisites: List[str] = field(
        default_factory=list
    )  # What must be true before execution
    safety_checks: List[str] = field(default_factory=list)  # Safety checks to perform
    rollback_plan: Optional[str] = None  # How to rollback if needed

    # Human oversight
    human_approval_required: bool = False
    escalation_triggers: List[str] = field(default_factory=list)
    notification_recipients: List[str] = field(default_factory=list)

    # Execution planning
    estimated_duration: int = 0  # Expected execution time in minutes
    max_retries: int = 0  # Maximum retry attempts
    timeout_minutes: int = 0  # Maximum time to wait

    # Context and reasoning
    reasoning: str = ""  # Why this action was chosen
    alternatives_considered: List[str] = field(default_factory=list)
    risks_identified: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "autonomous_planner"
    plan_id: str = ""

    # Compatibility fields for older call sites
    action_id: Optional[str] = None
    description: Optional[str] = None
    estimated_impact: Optional[str] = None

    def __post_init__(self) -> None:
        self.action_type = self._coerce_action_type(self.action_type)
        self.priority = self._coerce_priority(self.priority)
        self.safety_level = self._coerce_safety_level(self.safety_level)

    @property
    def is_destructive(self) -> bool:
        destructive_actions = {
            ActionType.RESTART_SERVICE,
            ActionType.ROLLBACK_DEPLOYMENT,
            ActionType.SCALE_RESOURCES,
            ActionType.MERGE_PR,
        }
        return self.action_type in destructive_actions

    @staticmethod
    def _coerce_action_type(value: Any) -> ActionType:
        if isinstance(value, ActionType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            try:
                return ActionType(normalized)
            except ValueError:
                for candidate in ActionType:
                    if (
                        candidate.value == normalized
                        or candidate.name.lower() == normalized
                    ):
                        return candidate
        logger.warning(
            "Unknown action_type '%s'; defaulting to REQUEST_CLARIFICATION", value
        )
        return ActionType.REQUEST_CLARIFICATION

    @staticmethod
    def _coerce_priority(value: Any) -> ActionPriority:
        if isinstance(value, ActionPriority):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            try:
                return ActionPriority(normalized)
            except ValueError:
                for candidate in ActionPriority:
                    if (
                        candidate.value == normalized
                        or candidate.name.lower() == normalized
                    ):
                        return candidate
        if isinstance(value, int):
            if value >= 8:
                return ActionPriority.CRITICAL
            if value >= 5:
                return ActionPriority.HIGH
            if value >= 3:
                return ActionPriority.MEDIUM
            if value >= 1:
                return ActionPriority.LOW
            return ActionPriority.DEFERRED
        return ActionPriority.MEDIUM

    @staticmethod
    def _coerce_safety_level(value: Any) -> SafetyLevel:
        if isinstance(value, SafetyLevel):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            mapping = {
                "safe": SafetyLevel.SAFE,
                "low": SafetyLevel.SAFE,
                "cautious": SafetyLevel.CAUTIOUS,
                "moderate": SafetyLevel.CAUTIOUS,
                "moderate_risk": SafetyLevel.CAUTIOUS,
                "risky": SafetyLevel.RISKY,
                "high": SafetyLevel.RISKY,
                "high_risk": SafetyLevel.RISKY,
                "dangerous": SafetyLevel.DANGEROUS,
                "critical": SafetyLevel.DANGEROUS,
            }
            if normalized in mapping:
                return mapping[normalized]
        return SafetyLevel.CAUTIOUS


@dataclass
class ExecutionPlan:
    """Complete execution plan for handling an event"""

    event_id: str
    context: ResolvedContext

    # Actions to take
    primary_actions: List[PlannedAction]  # Main actions to execute
    contingency_actions: List[PlannedAction]  # Backup actions if primary fails
    monitoring_actions: List[PlannedAction]  # Actions to monitor progress

    # Overall assessment
    overall_confidence: float  # Combined confidence across all actions
    overall_safety: SafetyLevel  # Most restrictive safety level
    overall_priority: ActionPriority

    # Execution constraints
    execution_window: Optional[Tuple[datetime, datetime]]  # When to execute
    prerequisites_met: bool  # Are all prerequisites satisfied
    human_approval_needed: bool  # Does any action need human approval

    # Monitoring and feedback
    success_criteria: List[str]  # How to measure success
    failure_indicators: List[str]  # Signs that plan is failing
    monitoring_frequency: int  # How often to check progress (minutes)

    # Metadata
    created_at: datetime
    expires_at: datetime
    plan_id: str
    automation_mode: AutomationMode = AutomationMode.SEMI_AUTONOMOUS

    @property
    def backup_actions(self) -> List[PlannedAction]:
        return self.contingency_actions

    @property
    def estimated_duration_minutes(self) -> int:
        return sum(action.estimated_duration for action in self.primary_actions)


class AutoPlanner:
    """
    Autonomous planning engine with built-in safety and confidence scoring

    Core responsibilities:
    1. Analyze resolved context to determine appropriate actions
    2. Score actions by confidence, safety, and priority
    3. Create execution plans with safety checks and rollback procedures
    4. Ensure human approval for risky actions
    5. Learn from historical patterns to improve planning
    """

    def __init__(self, db_session):
        self.db = db_session

        # Configuration
        self.min_confidence_threshold = 0.7  # Minimum confidence to act
        self.min_context_completeness = 0.6  # Minimum context needed
        self.max_simultaneous_actions = 3  # Max actions to plan at once

        # Safety thresholds by action type
        self.action_safety_requirements = {
            ActionType.FIX_BUG: 0.8,
            ActionType.MERGE_PR: 0.9,
            ActionType.RESTART_SERVICE: 0.95,
            ActionType.ROLLBACK_DEPLOYMENT: 0.9,
            ActionType.ADD_COMMENT: 0.5,
            ActionType.NOTIFY_TEAM: 0.3,
        }

        # Historical success tracking (would be loaded from database)
        self.historical_success_rates: Dict[ActionType, float] = {}

        # Planning strategies by context type
        self.planning_strategies = {
            ContextType.JIRA_ISSUE: self._plan_jira_actions,
            ContextType.GITHUB_PR: self._plan_github_actions,
            ContextType.SLACK_THREAD: self._plan_slack_actions,
            ContextType.CI_BUILD: self._plan_ci_actions,
            ContextType.DEPLOYMENT: self._plan_deployment_actions,
        }

    async def create_execution_plan(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> ExecutionPlan:
        """
        Create comprehensive execution plan for an event

        This is the main entry point for autonomous planning
        """

        logger.info(f"Creating execution plan for {event.event_id}")

        # Check if we have enough context to plan
        if context.context_completeness < self.min_context_completeness:
            logger.warning(
                f"Insufficient context completeness: {context.context_completeness}"
            )
            return await self._create_context_gathering_plan(event, context)

        # Get planning strategy for this context type
        strategy = self.planning_strategies.get(
            context.context_type, self._plan_generic_actions
        )

        try:
            # Execute planning strategy
            primary_actions = await strategy(event, context)

            # Filter actions by confidence and safety
            viable_actions = self._filter_viable_actions(primary_actions)

            # Sort by priority and confidence
            prioritized_actions = self._prioritize_actions(viable_actions)

            # Limit simultaneous actions
            if len(prioritized_actions) > self.max_simultaneous_actions:
                prioritized_actions = prioritized_actions[
                    : self.max_simultaneous_actions
                ]

            # Create contingency actions
            contingency_actions = await self._create_contingency_actions(
                event, context, prioritized_actions
            )

            # Create monitoring actions
            monitoring_actions = await self._create_monitoring_actions(
                event, context, prioritized_actions
            )

            # Calculate overall metrics
            overall_confidence = self._calculate_overall_confidence(prioritized_actions)
            overall_safety = self._determine_overall_safety(prioritized_actions)
            overall_priority = self._determine_overall_priority(prioritized_actions)

            # Determine execution constraints
            execution_window = self._determine_execution_window(
                context, prioritized_actions
            )
            prerequisites_met = await self._check_prerequisites(prioritized_actions)
            human_approval_needed = any(
                action.human_approval_required for action in prioritized_actions
            )

            # Create execution plan
            plan = ExecutionPlan(
                event_id=event.event_id,
                context=context,
                primary_actions=prioritized_actions,
                contingency_actions=contingency_actions,
                monitoring_actions=monitoring_actions,
                overall_confidence=overall_confidence,
                overall_safety=overall_safety,
                overall_priority=overall_priority,
                execution_window=execution_window,
                prerequisites_met=prerequisites_met,
                human_approval_needed=human_approval_needed,
                success_criteria=self._define_success_criteria(
                    context, prioritized_actions
                ),
                failure_indicators=self._define_failure_indicators(
                    context, prioritized_actions
                ),
                monitoring_frequency=self._determine_monitoring_frequency(
                    overall_priority
                ),
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=24),  # Plans expire after 24 hours
                plan_id=f"plan_{event.event_id}_{int(datetime.now().timestamp())}",
            )

            logger.info(
                f"Created execution plan {plan.plan_id} with {len(prioritized_actions)} actions"
            )
            return plan

        except Exception as e:
            logger.error(f"Failed to create execution plan for {event.event_id}: {e}")

            # Return safe fallback plan
            return await self._create_safe_fallback_plan(event, context)

    async def _plan_jira_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for Jira events"""

        actions = []

        # Determine action based on event type and issue state
        if event.trigger_type == "issue_assigned":
            actions.extend(await self._plan_issue_assignment_actions(event, context))

        elif event.trigger_type == "issue_created":
            actions.extend(await self._plan_new_issue_actions(event, context))

        elif event.trigger_type == "issue_commented":
            actions.extend(await self._plan_comment_response_actions(event, context))

        elif event.trigger_type == "status_changed":
            actions.extend(await self._plan_status_change_actions(event, context))

        # Always consider general issue improvement actions
        actions.extend(await self._plan_general_issue_actions(event, context))

        return actions

    async def _plan_issue_assignment_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions when an issue is assigned"""

        actions = []
        issue = context.primary_object
        assignee = issue.get("assignee")

        # If assigned to NAVI/bot, create autonomous work plan
        if assignee and assignee.lower() in ["navi", "bot", "autonomous"]:

            # Analyze issue complexity and create implementation plan
            complexity = context.complexity_score

            if complexity < 0.3:  # Simple issue
                actions.append(
                    PlannedAction(
                        action_type=ActionType.IMPLEMENT_FEATURE,
                        priority=ActionPriority.MEDIUM,
                        safety_level=SafetyLevel.SAFE,
                        confidence_score=0.8,
                        context_completeness=context.context_completeness,
                        historical_success=self._get_historical_success(
                            ActionType.IMPLEMENT_FEATURE
                        ),
                        target=issue.get("key", ""),
                        parameters={
                            "issue_key": issue.get("key"),
                            "approach": "autonomous_implementation",
                            "create_pr": True,
                            "request_review": True,
                        },
                        prerequisites=[
                            "issue_has_clear_requirements",
                            "repository_accessible",
                        ],
                        safety_checks=[
                            "validate_requirements",
                            "run_tests",
                            "check_for_conflicts",
                        ],
                        rollback_plan="Close PR if implementation fails validation",
                        human_approval_required=False,
                        escalation_triggers=[
                            "implementation_fails",
                            "tests_fail",
                            "conflicts_detected",
                        ],
                        notification_recipients=[issue.get("reporter", "")],
                        estimated_duration=120,  # 2 hours
                        max_retries=2,
                        timeout_minutes=240,  # 4 hours
                        reasoning=f"Issue {issue.get('key')} assigned to autonomous agent with low complexity ({complexity:.2f})",
                        alternatives_considered=[
                            "request_human_review",
                            "gather_more_context",
                        ],
                        risks_identified=["unclear_requirements", "missing_tests"],
                        created_at=datetime.now(timezone.utc),
                    )
                )

            elif complexity < 0.7:  # Medium complexity
                actions.append(
                    PlannedAction(
                        action_type=ActionType.GATHER_MORE_CONTEXT,
                        priority=ActionPriority.HIGH,
                        safety_level=SafetyLevel.SAFE,
                        confidence_score=0.9,
                        context_completeness=context.context_completeness,
                        historical_success=0.95,
                        target=issue.get("key", ""),
                        parameters={
                            "gather_types": [
                                "related_issues",
                                "code_examples",
                                "test_cases",
                            ],
                            "analysis_depth": "detailed",
                        },
                        prerequisites=[],
                        safety_checks=[],
                        rollback_plan=None,
                        human_approval_required=False,
                        escalation_triggers=[],
                        notification_recipients=[],
                        estimated_duration=30,
                        max_retries=1,
                        timeout_minutes=60,
                        reasoning=f"Issue {issue.get('key')} has medium complexity ({complexity:.2f}), need more context",
                        alternatives_considered=[
                            "immediate_implementation",
                            "request_human_help",
                        ],
                        risks_identified=["insufficient_context"],
                        created_at=datetime.now(timezone.utc),
                    )
                )

            else:  # High complexity
                actions.append(
                    PlannedAction(
                        action_type=ActionType.REQUEST_CLARIFICATION,
                        priority=ActionPriority.HIGH,
                        safety_level=SafetyLevel.SAFE,
                        confidence_score=0.8,
                        context_completeness=context.context_completeness,
                        historical_success=0.9,
                        target=issue.get("key", ""),
                        parameters={
                            "clarification_type": "implementation_approach",
                            "questions": [
                                "What is the preferred implementation approach?",
                                "Are there specific architectural constraints?",
                                "Should this be broken down into smaller tasks?",
                            ],
                            "notify_assignee": True,
                        },
                        prerequisites=[],
                        safety_checks=[],
                        rollback_plan=None,
                        human_approval_required=False,
                        escalation_triggers=["no_response_24h"],
                        notification_recipients=[issue.get("reporter", "")],
                        estimated_duration=15,
                        max_retries=0,
                        timeout_minutes=30,
                        reasoning=f"Issue {issue.get('key')} has high complexity ({complexity:.2f}), need clarification",
                        alternatives_considered=[
                            "attempt_implementation",
                            "escalate_immediately",
                        ],
                        risks_identified=[
                            "incorrect_implementation",
                            "missed_requirements",
                        ],
                        created_at=datetime.now(timezone.utc),
                    )
                )

        else:
            # Issue assigned to human - offer assistance
            actions.append(
                PlannedAction(
                    action_type=ActionType.ADD_COMMENT,
                    priority=ActionPriority.LOW,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.7,
                    context_completeness=context.context_completeness,
                    historical_success=0.85,
                    target=issue.get("key", ""),
                    parameters={
                        "comment": f"Hi {assignee}, I've analyzed this issue and can provide context or assist with implementation. Let me know if you need help!",
                        "offer_assistance": True,
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=[],
                    estimated_duration=2,
                    max_retries=1,
                    timeout_minutes=10,
                    reasoning="Offering assistance to human assignee",
                    alternatives_considered=["no_action", "wait_for_request"],
                    risks_identified=["unwanted_interference"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_new_issue_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for newly created issues"""

        actions = []
        issue = context.primary_object

        # Auto-triage new issues
        priority = issue.get("priority", "").lower()
        issue_type = issue.get("issuetype", {}).get("name", "").lower()

        # Critical issues need immediate attention
        if (
            priority in ["critical", "blocker"]
            or "critical" in context.urgency_indicators
        ):
            actions.append(
                PlannedAction(
                    action_type=ActionType.ESCALATE_ISSUE,
                    priority=ActionPriority.CRITICAL,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.9,
                    context_completeness=context.context_completeness,
                    historical_success=0.95,
                    target=issue.get("key", ""),
                    parameters={
                        "escalation_type": "critical_issue",
                        "notify_oncall": True,
                        "notify_management": True,
                        "create_incident": issue_type == "incident",
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=[
                        "oncall@company.com",
                        "management@company.com",
                    ],
                    estimated_duration=5,
                    max_retries=0,
                    timeout_minutes=10,
                    reasoning=f"Critical issue {issue.get('key')} needs immediate escalation",
                    alternatives_considered=["standard_triage", "wait_for_assignment"],
                    risks_identified=["delayed_response"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        # Auto-categorize and suggest labels
        if not issue.get("labels") or len(issue.get("labels", [])) == 0:
            suggested_labels = self._suggest_issue_labels(issue, context)
            if suggested_labels:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.ADD_COMMENT,
                        priority=ActionPriority.LOW,
                        safety_level=SafetyLevel.SAFE,
                        confidence_score=0.6,
                        context_completeness=context.context_completeness,
                        historical_success=0.8,
                        target=issue.get("key", ""),
                        parameters={
                            "comment": f"I've analyzed this issue and suggest adding these labels: {', '.join(suggested_labels)}",
                            "suggested_labels": suggested_labels,
                        },
                        prerequisites=[],
                        safety_checks=[],
                        rollback_plan=None,
                        human_approval_required=False,
                        escalation_triggers=[],
                        notification_recipients=[],
                        estimated_duration=3,
                        max_retries=1,
                        timeout_minutes=10,
                        reasoning="New issue needs proper categorization",
                        alternatives_considered=["auto_apply_labels", "no_action"],
                        risks_identified=["incorrect_categorization"],
                        created_at=datetime.now(timezone.utc),
                    )
                )

        # Link to related issues
        if context.related_issues:
            actions.append(
                PlannedAction(
                    action_type=ActionType.LINK_ISSUES,
                    priority=ActionPriority.MEDIUM,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.7,
                    context_completeness=context.context_completeness,
                    historical_success=0.8,
                    target=issue.get("key", ""),
                    parameters={
                        "link_type": "relates to",
                        "target_issues": [
                            ri.get("key") for ri in context.related_issues[:3]
                        ],  # Max 3 links
                    },
                    prerequisites=["related_issues_exist"],
                    safety_checks=["validate_relationship"],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=["invalid_relationship"],
                    notification_recipients=[],
                    estimated_duration=10,
                    max_retries=1,
                    timeout_minutes=20,
                    reasoning="New issue appears related to existing issues",
                    alternatives_considered=["manual_review", "no_linking"],
                    risks_identified=["incorrect_relationships"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_comment_response_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for issue comments"""

        actions = []
        comment_text = event.event_data.get("comment", {}).get("body", "")

        # Check if NAVI is mentioned or asked a question
        if self._is_navi_mentioned(comment_text):
            actions.append(
                PlannedAction(
                    action_type=ActionType.ADD_COMMENT,
                    priority=ActionPriority.HIGH,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.8,
                    context_completeness=context.context_completeness,
                    historical_success=0.9,
                    target=context.primary_object.get("key", ""),
                    parameters={
                        "comment": await self._generate_intelligent_response(
                            comment_text, context
                        ),
                        "parent_comment": event.event_data.get("comment", {}).get("id"),
                    },
                    prerequisites=[],
                    safety_checks=["validate_response_appropriateness"],
                    rollback_plan="Delete comment if inappropriate",
                    human_approval_required=False,
                    escalation_triggers=["response_flagged_inappropriate"],
                    notification_recipients=[],
                    estimated_duration=5,
                    max_retries=1,
                    timeout_minutes=15,
                    reasoning="NAVI was directly mentioned and should respond",
                    alternatives_considered=["ignore_mention", "escalate_to_human"],
                    risks_identified=["inappropriate_response"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_status_change_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for issue status changes"""

        actions = []
        event.event_data.get("from_status", "")
        to_status = event.event_data.get("to_status", "")

        # When issue moves to "In Progress", offer assistance
        if to_status.lower() == "in progress":
            actions.append(
                PlannedAction(
                    action_type=ActionType.ADD_COMMENT,
                    priority=ActionPriority.LOW,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.6,
                    context_completeness=context.context_completeness,
                    historical_success=0.7,
                    target=context.primary_object.get("key", ""),
                    parameters={
                        "comment": "I see you're starting work on this issue. I can help with code analysis, testing, or creating related PRs. Just mention me if you need assistance!",
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=[],
                    estimated_duration=2,
                    max_retries=1,
                    timeout_minutes=10,
                    reasoning="Issue moved to In Progress, offering assistance",
                    alternatives_considered=["no_action", "wait_for_request"],
                    risks_identified=["unwanted_interference"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        # When issue is resolved, verify completion
        elif to_status.lower() in ["resolved", "done", "closed"]:
            actions.append(
                PlannedAction(
                    action_type=ActionType.GATHER_MORE_CONTEXT,
                    priority=ActionPriority.LOW,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.9,
                    context_completeness=context.context_completeness,
                    historical_success=0.9,
                    target=context.primary_object.get("key", ""),
                    parameters={
                        "verification_type": "completion_check",
                        "check_prs": True,
                        "check_tests": True,
                        "check_documentation": True,
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=[],
                    estimated_duration=15,
                    max_retries=1,
                    timeout_minutes=30,
                    reasoning="Issue resolved, verifying completion",
                    alternatives_considered=["no_verification", "manual_review"],
                    risks_identified=["incomplete_work"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_general_issue_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan general actions that could apply to any issue"""

        actions = []
        issue = context.primary_object

        # If issue is old and stale, suggest review
        created_date = issue.get("created")
        if created_date:  # Would parse and check age
            # Placeholder logic
            if issue.get("status", "").lower() not in ["resolved", "done", "closed"]:
                actions.append(
                    PlannedAction(
                        action_type=ActionType.ADD_COMMENT,
                        priority=ActionPriority.LOW,
                        safety_level=SafetyLevel.SAFE,
                        confidence_score=0.5,
                        context_completeness=context.context_completeness,
                        historical_success=0.6,
                        target=issue.get("key", ""),
                        parameters={
                            "comment": "This issue has been open for a while. Should it be reviewed for current relevance or priority?",
                        },
                        prerequisites=["issue_age_over_30_days"],
                        safety_checks=[],
                        rollback_plan=None,
                        human_approval_required=True,  # Stale issue comments should be reviewed
                        escalation_triggers=[],
                        notification_recipients=[issue.get("assignee", "")],
                        estimated_duration=2,
                        max_retries=0,
                        timeout_minutes=10,
                        reasoning="Old issue may need review",
                        alternatives_considered=["auto_close", "no_action"],
                        risks_identified=["inappropriate_timing"],
                        created_at=datetime.now(timezone.utc),
                    )
                )

        return actions

    async def _plan_github_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for GitHub events"""

        actions = []
        pr = context.primary_object

        # Handle PR reviews
        if event.trigger_type == "pr_review_requested":
            actions.append(
                PlannedAction(
                    action_type=ActionType.REVIEW_PR,
                    priority=ActionPriority.HIGH,
                    safety_level=SafetyLevel.CAUTIOUS,
                    confidence_score=0.7,
                    context_completeness=context.context_completeness,
                    historical_success=self._get_historical_success(
                        ActionType.REVIEW_PR
                    ),
                    target=f"{pr.get('repository')}#{pr.get('number')}",
                    parameters={
                        "review_type": "automated_analysis",
                        "check_code_quality": True,
                        "check_tests": True,
                        "check_security": True,
                        "provide_suggestions": True,
                    },
                    prerequisites=["pr_has_changes", "repository_accessible"],
                    safety_checks=[
                        "validate_changes_scope",
                        "check_for_breaking_changes",
                    ],
                    rollback_plan="Delete review if inappropriate",
                    human_approval_required=False,
                    escalation_triggers=[
                        "security_issues_found",
                        "breaking_changes_detected",
                    ],
                    notification_recipients=[pr.get("author", "")],
                    estimated_duration=30,
                    max_retries=1,
                    timeout_minutes=60,
                    reasoning="PR review requested and code analysis can provide value",
                    alternatives_considered=["defer_to_human", "skip_review"],
                    risks_identified=["incorrect_analysis", "false_positives"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_slack_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for Slack events"""

        actions = []
        message = context.primary_object

        # Respond to direct mentions
        if self._is_navi_mentioned(message.get("text", "")):
            actions.append(
                PlannedAction(
                    action_type=ActionType.NOTIFY_TEAM,
                    priority=ActionPriority.MEDIUM,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.8,
                    context_completeness=context.context_completeness,
                    historical_success=0.9,
                    target=message.get("channel", ""),
                    parameters={
                        "response": await self._generate_slack_response(
                            message, context
                        ),
                        "thread_ts": message.get("timestamp"),
                    },
                    prerequisites=[],
                    safety_checks=["validate_response_appropriateness"],
                    rollback_plan=None,
                    human_approval_required=True,
                    escalation_triggers=["response_flagged_inappropriate"],
                    notification_recipients=[],
                    estimated_duration=3,
                    max_retries=1,
                    timeout_minutes=10,
                    reasoning="Direct mention in Slack requires response",
                    alternatives_considered=["ignore", "escalate_to_human"],
                    risks_identified=["inappropriate_response"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return actions

    async def _plan_ci_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for CI events"""

        actions = []
        build = context.primary_object

        # Handle CI failures
        if build.get("status") == "failed":
            failure_type = build.get("failure_type", "")

            if failure_type == "test_failure":
                actions.append(
                    PlannedAction(
                        action_type=ActionType.FIX_BUG,
                        priority=ActionPriority.HIGH,
                        safety_level=SafetyLevel.CAUTIOUS,
                        confidence_score=0.6,
                        context_completeness=context.context_completeness,
                        historical_success=self._get_historical_success(
                            ActionType.FIX_BUG
                        ),
                        target=build.get("build_id", ""),
                        parameters={
                            "fix_type": "test_failure",
                            "analyze_logs": True,
                            "create_pr": True,
                            "run_tests": True,
                        },
                        prerequisites=["build_logs_accessible", "repository_writable"],
                        safety_checks=["validate_fix_scope", "run_full_test_suite"],
                        rollback_plan="Revert PR if fix causes more failures",
                        human_approval_required=True,  # CI fixes are risky
                        escalation_triggers=[
                            "fix_causes_more_failures",
                            "tests_still_fail",
                        ],
                        notification_recipients=[build.get("author", "")],
                        estimated_duration=60,
                        max_retries=1,
                        timeout_minutes=120,
                        reasoning="CI test failure detected, attempting automated fix",
                        alternatives_considered=["notify_only", "wait_for_human"],
                        risks_identified=["incorrect_fix", "breaking_more_tests"],
                        created_at=datetime.now(timezone.utc),
                    )
                )

        return actions

    async def _plan_deployment_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Plan actions for deployment events"""

        actions = []
        deployment = context.primary_object

        # Handle deployment failures
        if deployment.get("status") == "failed":
            environment = deployment.get("environment", "")

            # Production failures are critical
            if environment == "production":
                actions.append(
                    PlannedAction(
                        action_type=ActionType.ROLLBACK_DEPLOYMENT,
                        priority=ActionPriority.CRITICAL,
                        safety_level=SafetyLevel.RISKY,
                        confidence_score=0.9,
                        context_completeness=context.context_completeness,
                        historical_success=self._get_historical_success(
                            ActionType.ROLLBACK_DEPLOYMENT
                        ),
                        target=deployment.get("deployment_id", ""),
                        parameters={
                            "rollback_type": "immediate",
                            "notify_oncall": True,
                            "create_incident": True,
                        },
                        prerequisites=["rollback_target_available", "oncall_notified"],
                        safety_checks=[
                            "validate_rollback_safety",
                            "check_rollback_impact",
                        ],
                        rollback_plan="Manual intervention required if rollback fails",
                        human_approval_required=True,  # Production rollbacks always need approval
                        escalation_triggers=["rollback_fails", "service_still_down"],
                        notification_recipients=[
                            "oncall@company.com",
                            "management@company.com",
                        ],
                        estimated_duration=15,
                        max_retries=0,  # Don't retry rollbacks
                        timeout_minutes=30,
                        reasoning="Production deployment failed, immediate rollback needed",
                        alternatives_considered=["attempt_fix", "wait_for_analysis"],
                        risks_identified=[
                            "rollback_causes_data_loss",
                            "service_downtime",
                        ],
                        created_at=datetime.now(timezone.utc),
                    )
                )

        return actions

    async def _plan_generic_actions(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> List[PlannedAction]:
        """Fallback planning for unknown event types"""

        # For unknown events, the safest action is to gather more context
        return [
            PlannedAction(
                action_type=ActionType.GATHER_MORE_CONTEXT,
                priority=ActionPriority.LOW,
                safety_level=SafetyLevel.SAFE,
                confidence_score=0.9,
                context_completeness=context.context_completeness,
                historical_success=0.95,
                target=event.event_id,
                parameters={
                    "context_type": "unknown_event",
                    "analyze_content": True,
                },
                prerequisites=[],
                safety_checks=[],
                rollback_plan=None,
                human_approval_required=False,
                escalation_triggers=["context_gathering_fails"],
                notification_recipients=[],
                estimated_duration=10,
                max_retries=1,
                timeout_minutes=20,
                reasoning="Unknown event type, need more context before planning",
                alternatives_considered=["no_action", "escalate_immediately"],
                risks_identified=["missing_important_signal"],
                created_at=datetime.now(timezone.utc),
            )
        ]

    # Helper methods for action planning

    def _filter_viable_actions(
        self, actions: List[PlannedAction]
    ) -> List[PlannedAction]:
        """Filter actions that meet minimum viability thresholds"""

        viable_actions = []

        for action in actions:
            # Check minimum confidence
            if action.confidence_score < self.min_confidence_threshold:
                logger.debug(
                    f"Filtering out {action.action_type} due to low confidence: {action.confidence_score}"
                )
                continue

            # Check context completeness
            if action.context_completeness < self.min_context_completeness:
                logger.debug(
                    f"Filtering out {action.action_type} due to incomplete context: {action.context_completeness}"
                )
                continue

            # Check action-specific safety requirements
            min_required = self.action_safety_requirements.get(action.action_type, 0.5)
            if action.confidence_score < min_required:
                logger.debug(
                    f"Filtering out {action.action_type} due to safety requirement: {action.confidence_score} < {min_required}"
                )
                continue

            viable_actions.append(action)

        return viable_actions

    def _prioritize_actions(self, actions: List[PlannedAction]) -> List[PlannedAction]:
        """Sort actions by priority and confidence"""

        priority_order = {
            ActionPriority.CRITICAL: 4,
            ActionPriority.HIGH: 3,
            ActionPriority.MEDIUM: 2,
            ActionPriority.LOW: 1,
            ActionPriority.DEFERRED: 0,
        }

        return sorted(
            actions,
            key=lambda a: (
                priority_order.get(a.priority, 0),  # Priority first
                a.confidence_score,  # Then confidence
                -a.estimated_duration,  # Then speed (prefer faster actions)
            ),
            reverse=True,
        )

    async def _create_contingency_actions(
        self,
        event: ProcessedEvent,
        context: ResolvedContext,
        primary_actions: List[PlannedAction],
    ) -> List[PlannedAction]:
        """Create backup actions in case primary actions fail"""

        contingency_actions = []

        for action in primary_actions:
            # Create human escalation as contingency
            contingency_actions.append(
                PlannedAction(
                    action_type=ActionType.ESCALATE_ISSUE,
                    priority=action.priority,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=1.0,
                    context_completeness=context.context_completeness,
                    historical_success=0.95,
                    target=action.target,
                    parameters={
                        "escalation_reason": f"Primary action {action.action_type} failed",
                        "include_context": True,
                        "original_action": action.action_type.value,
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=["team@company.com"],
                    estimated_duration=5,
                    max_retries=0,
                    timeout_minutes=10,
                    reasoning=f"Contingency for failed {action.action_type}",
                    alternatives_considered=["retry_original", "no_action"],
                    risks_identified=["escalation_noise"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return contingency_actions

    async def _create_monitoring_actions(
        self,
        event: ProcessedEvent,
        context: ResolvedContext,
        primary_actions: List[PlannedAction],
    ) -> List[PlannedAction]:
        """Create actions to monitor progress of primary actions"""

        monitoring_actions = []

        # Create general progress monitoring
        if primary_actions:
            monitoring_actions.append(
                PlannedAction(
                    action_type=ActionType.GATHER_MORE_CONTEXT,
                    priority=ActionPriority.LOW,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.9,
                    context_completeness=1.0,
                    historical_success=0.95,
                    target=event.event_id,
                    parameters={
                        "monitoring_type": "action_progress",
                        "check_frequency": "every_30_minutes",
                        "report_progress": True,
                    },
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=["actions_stalled"],
                    notification_recipients=[],
                    estimated_duration=5,
                    max_retries=10,  # Keep monitoring
                    timeout_minutes=1440,  # 24 hours
                    reasoning="Monitor progress of autonomous actions",
                    alternatives_considered=["no_monitoring", "human_oversight"],
                    risks_identified=["monitoring_overhead"],
                    created_at=datetime.now(timezone.utc),
                )
            )

        return monitoring_actions

    # Helper methods for plan creation

    async def _create_context_gathering_plan(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> ExecutionPlan:
        """Create plan focused on gathering more context"""

        action = PlannedAction(
            action_type=ActionType.GATHER_MORE_CONTEXT,
            priority=ActionPriority.HIGH,
            safety_level=SafetyLevel.SAFE,
            confidence_score=0.9,
            context_completeness=context.context_completeness,
            historical_success=0.95,
            target=event.event_id,
            parameters={
                "context_types": [
                    "related_issues",
                    "team_members",
                    "historical_patterns",
                ],
                "depth": "comprehensive",
            },
            prerequisites=[],
            safety_checks=[],
            rollback_plan=None,
            human_approval_required=False,
            escalation_triggers=["context_gathering_fails"],
            notification_recipients=[],
            estimated_duration=20,
            max_retries=2,
            timeout_minutes=40,
            reasoning="Insufficient context to plan autonomous actions",
            alternatives_considered=["wait_for_human", "act_with_limited_context"],
            risks_identified=["delayed_response"],
            created_at=datetime.now(timezone.utc),
            plan_id=f"context_plan_{event.event_id}",
        )

        return ExecutionPlan(
            event_id=event.event_id,
            context=context,
            primary_actions=[action],
            contingency_actions=[],
            monitoring_actions=[],
            overall_confidence=0.9,
            overall_safety=SafetyLevel.SAFE,
            overall_priority=ActionPriority.HIGH,
            execution_window=None,
            prerequisites_met=True,
            human_approval_needed=False,
            success_criteria=["context_completeness > 0.6"],
            failure_indicators=["context_gathering_timeout"],
            monitoring_frequency=10,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            plan_id=f"context_plan_{event.event_id}_{int(datetime.now().timestamp())}",
        )

    async def _create_safe_fallback_plan(
        self, event: ProcessedEvent, context: ResolvedContext
    ) -> ExecutionPlan:
        """Create safe fallback plan when planning fails"""

        action = PlannedAction(
            action_type=ActionType.WAIT_FOR_HUMAN,
            priority=ActionPriority.MEDIUM,
            safety_level=SafetyLevel.SAFE,
            confidence_score=1.0,
            context_completeness=context.context_completeness,
            historical_success=1.0,
            target=event.event_id,
            parameters={
                "wait_reason": "planning_failed",
                "notify_team": True,
                "include_error": True,
            },
            prerequisites=[],
            safety_checks=[],
            rollback_plan=None,
            human_approval_required=False,
            escalation_triggers=[],
            notification_recipients=["team@company.com"],
            estimated_duration=0,
            max_retries=0,
            timeout_minutes=0,
            reasoning="Planning failed, escalating to humans",
            alternatives_considered=["retry_planning", "ignore_event"],
            risks_identified=["missed_important_signal"],
            created_at=datetime.now(timezone.utc),
        )

        return ExecutionPlan(
            event_id=event.event_id,
            context=context,
            primary_actions=[action],
            contingency_actions=[],
            monitoring_actions=[],
            overall_confidence=1.0,  # High confidence in doing nothing
            overall_safety=SafetyLevel.SAFE,
            overall_priority=ActionPriority.MEDIUM,
            execution_window=None,
            prerequisites_met=True,
            human_approval_needed=False,
            success_criteria=["human_notified"],
            failure_indicators=["notification_failed"],
            monitoring_frequency=60,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            plan_id=f"fallback_plan_{event.event_id}_{int(datetime.now().timestamp())}",
        )

    # Utility and helper methods

    def _calculate_overall_confidence(self, actions: List[PlannedAction]) -> float:
        """Calculate overall confidence across all actions"""
        if not actions:
            return 0.0

        # Weighted average by action duration (shorter actions weighted more)
        total_weighted_confidence = 0.0
        total_weight = 0.0

        for action in actions:
            weight = 1.0 / max(
                action.estimated_duration, 1
            )  # Inverse duration weighting
            total_weighted_confidence += action.confidence_score * weight
            total_weight += weight

        return total_weighted_confidence / total_weight if total_weight > 0 else 0.0

    def _determine_overall_safety(self, actions: List[PlannedAction]) -> SafetyLevel:
        """Determine overall safety level (most restrictive wins)"""
        if not actions:
            return SafetyLevel.SAFE

        safety_priority = {
            SafetyLevel.DANGEROUS: 4,
            SafetyLevel.RISKY: 3,
            SafetyLevel.CAUTIOUS: 2,
            SafetyLevel.SAFE: 1,
        }

        most_restrictive = max(
            actions, key=lambda a: safety_priority.get(a.safety_level, 1)
        )
        return most_restrictive.safety_level

    def _determine_overall_priority(
        self, actions: List[PlannedAction]
    ) -> ActionPriority:
        """Determine overall priority (highest priority wins)"""
        if not actions:
            return ActionPriority.LOW

        priority_values = {
            ActionPriority.CRITICAL: 4,
            ActionPriority.HIGH: 3,
            ActionPriority.MEDIUM: 2,
            ActionPriority.LOW: 1,
            ActionPriority.DEFERRED: 0,
        }

        highest_priority = max(
            actions, key=lambda a: priority_values.get(a.priority, 1)
        )
        return highest_priority.priority

    def _determine_execution_window(
        self, context: ResolvedContext, actions: List[PlannedAction]
    ) -> Optional[Tuple[datetime, datetime]]:
        """Determine when actions should be executed"""

        # For now, execute immediately for most actions
        # Could be enhanced with business hours, maintenance windows, etc.

        has_critical = any(a.priority == ActionPriority.CRITICAL for a in actions)
        if has_critical:
            return None  # Execute immediately

        has_risky = any(a.safety_level == SafetyLevel.RISKY for a in actions)
        if has_risky:
            # Execute during business hours
            now = datetime.now(timezone.utc)
            start = now.replace(hour=9, minute=0, second=0, microsecond=0)  # 9 AM UTC
            end = now.replace(hour=17, minute=0, second=0, microsecond=0)  # 5 PM UTC

            if now > end:
                # Move to next day
                start += timedelta(days=1)
                end += timedelta(days=1)

            return (start, end)

        return None  # No execution window restrictions

    async def _check_prerequisites(self, actions: List[PlannedAction]) -> bool:
        """Check if prerequisites are met for all actions"""

        for action in actions:
            for prerequisite in action.prerequisites:
                if not await self._check_prerequisite(prerequisite, action):
                    logger.warning(
                        f"Prerequisite '{prerequisite}' not met for {action.action_type}"
                    )
                    return False

        return True

    async def _check_prerequisite(
        self, prerequisite: str, action: PlannedAction
    ) -> bool:
        """Check a specific prerequisite"""

        # Simple prerequisite checking - would be enhanced with actual checks
        prerequisite_checks = {
            "issue_has_clear_requirements": lambda: True,  # Would check issue description
            "repository_accessible": lambda: True,  # Would check repo access
            "build_logs_accessible": lambda: True,  # Would check CI access
            "repository_writable": lambda: True,  # Would check write permissions
            "rollback_target_available": lambda: True,  # Would check rollback viability
            "oncall_notified": lambda: True,  # Would check notification status
            "related_issues_exist": lambda: len(
                action.parameters.get("target_issues", [])
            )
            > 0,
            "pr_has_changes": lambda: True,  # Would check PR diff
            "issue_age_over_30_days": lambda: False,  # Would check issue age
        }

        checker = prerequisite_checks.get(prerequisite, lambda: True)
        try:
            return checker()
        except Exception as e:
            logger.error(f"Failed to check prerequisite '{prerequisite}': {e}")
            return False

    def _define_success_criteria(
        self, context: ResolvedContext, actions: List[PlannedAction]
    ) -> List[str]:
        """Define success criteria for the execution plan"""

        criteria = []

        for action in actions:
            if action.action_type == ActionType.IMPLEMENT_FEATURE:
                criteria.extend(
                    [
                        "PR created successfully",
                        "All tests pass",
                        "Code review requested",
                    ]
                )
            elif action.action_type == ActionType.FIX_BUG:
                criteria.extend(
                    [
                        "Bug fix implemented",
                        "Tests pass",
                        "Issue status updated",
                    ]
                )
            elif action.action_type == ActionType.ADD_COMMENT:
                criteria.append("Comment added successfully")
            elif action.action_type == ActionType.ESCALATE_ISSUE:
                criteria.extend(
                    [
                        "Team notified",
                        "Escalation documented",
                    ]
                )
            else:
                criteria.append(f"{action.action_type.value} completed")

        return criteria

    def _define_failure_indicators(
        self, context: ResolvedContext, actions: List[PlannedAction]
    ) -> List[str]:
        """Define failure indicators for the execution plan"""

        indicators = [
            "Action timeout exceeded",
            "Prerequisites not met",
            "Safety checks failed",
            "Human approval denied",
        ]

        # Action-specific indicators
        for action in actions:
            if action.action_type in [ActionType.IMPLEMENT_FEATURE, ActionType.FIX_BUG]:
                indicators.extend(
                    [
                        "Code compilation failed",
                        "Tests failed",
                        "PR creation failed",
                    ]
                )
            elif action.action_type == ActionType.ROLLBACK_DEPLOYMENT:
                indicators.extend(
                    [
                        "Rollback failed",
                        "Service still down",
                    ]
                )

        return indicators

    def _determine_monitoring_frequency(self, priority: ActionPriority) -> int:
        """Determine how often to monitor plan progress (in minutes)"""

        frequency_map = {
            ActionPriority.CRITICAL: 5,  # Every 5 minutes
            ActionPriority.HIGH: 15,  # Every 15 minutes
            ActionPriority.MEDIUM: 30,  # Every 30 minutes
            ActionPriority.LOW: 60,  # Every hour
            ActionPriority.DEFERRED: 240,  # Every 4 hours
        }

        return frequency_map.get(priority, 30)

    def _get_historical_success(self, action_type: ActionType) -> float:
        """Get historical success rate for an action type"""

        # Default success rates - would be calculated from historical data
        default_rates = {
            ActionType.ADD_COMMENT: 0.95,
            ActionType.IMPLEMENT_FEATURE: 0.75,
            ActionType.FIX_BUG: 0.70,
            ActionType.REVIEW_PR: 0.85,
            ActionType.MERGE_PR: 0.90,
            ActionType.NOTIFY_TEAM: 0.98,
            ActionType.ESCALATE_ISSUE: 0.95,
            ActionType.GATHER_MORE_CONTEXT: 0.90,
            ActionType.REQUEST_CLARIFICATION: 0.85,
            ActionType.ROLLBACK_DEPLOYMENT: 0.80,
        }

        return self.historical_success_rates.get(
            action_type, default_rates.get(action_type, 0.5)
        )

    def _is_navi_mentioned(self, text: str) -> bool:
        """Check if NAVI is mentioned in text"""

        text_lower = text.lower()
        navi_mentions = ["navi", "@navi", "autonomous", "bot", "assistant"]

        return any(mention in text_lower for mention in navi_mentions)

    def _suggest_issue_labels(
        self, issue: Dict[str, Any], context: ResolvedContext
    ) -> List[str]:
        """Suggest appropriate labels for an issue"""

        suggested = []

        title = issue.get("title", "").lower()
        description = issue.get("description", "").lower()
        text = f"{title} {description}"

        # Technical labels
        if any(word in text for word in ["bug", "error", "broken", "fail"]):
            suggested.append("bug")
        if any(word in text for word in ["feature", "enhancement", "new"]):
            suggested.append("enhancement")
        if any(word in text for word in ["performance", "slow", "optimization"]):
            suggested.append("performance")
        if any(word in text for word in ["security", "vulnerability", "auth"]):
            suggested.append("security")
        if any(word in text for word in ["documentation", "docs", "readme"]):
            suggested.append("documentation")

        # Priority labels
        if any(word in text for word in ["critical", "urgent", "emergency"]):
            suggested.append("priority-high")
        elif any(word in text for word in ["minor", "nice-to-have", "low"]):
            suggested.append("priority-low")

        return suggested[:3]  # Limit to 3 suggestions

    async def _generate_intelligent_response(
        self, comment_text: str, context: ResolvedContext
    ) -> str:
        """Generate intelligent response to a comment"""

        # This would integrate with LLM for intelligent responses
        # For now, provide helpful template responses

        text_lower = comment_text.lower()

        if "help" in text_lower or "assist" in text_lower:
            return "I'm here to help! I can analyze code, create PRs, run tests, or provide context about related issues. What specifically would you like me to help with?"

        elif "status" in text_lower or "progress" in text_lower:
            return (
                "Let me check the current status and provide an update on progress..."
            )

        elif "review" in text_lower:
            return "I can perform an automated code review. Would you like me to analyze the current PR or specific files?"

        elif "test" in text_lower:
            return "I can help with testing. I can run existing tests, write new test cases, or analyze test coverage."

        else:
            return "I understand you've mentioned me. How can I assist with this issue? I can help with code analysis, testing, documentation, or project management tasks."

    async def _generate_slack_response(
        self, message: Dict[str, Any], context: ResolvedContext
    ) -> str:
        """Generate appropriate Slack response"""

        text = message.get("text", "").lower()

        if "status" in text:
            return "Current status update: I'm monitoring several active issues and PRs. I can provide detailed status on any specific items you're interested in."

        elif "help" in text:
            return "I'm here to help! I can assist with Jira issues, PR reviews, code analysis, testing, and more. What do you need help with?"

        else:
            return "Hi! I'm NAVI, the autonomous engineering assistant. I can help with development tasks, issue management, code reviews, and more. What can I help you with?"
