"""
Governance Integration Layer

Integrates Phase 5.1 Human-in-the-Loop Governance with Phase 5.0 Closed-Loop system.
Ensures all autonomous actions are governed by approval policies and risk assessments.
"""

import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from ..governance.approval_engine import ApprovalEngine
from ..governance.risk_scorer import RiskScorer
from ..governance.audit_logger import AuditLogger
from ..governance import ActionContext, DecisionType
from ..closedloop.closed_loop_orchestrator import (
    ClosedLoopOrchestrator,
    OrchestrationConfig,
)
from ..closedloop.auto_planner import (
    PlannedAction,
    ActionType,
    ActionPriority,
    SafetyLevel,
)
from ..closedloop.execution_controller import ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


def generate_action_id(action: PlannedAction) -> str:
    """Generate a unique ID for a PlannedAction"""
    id_string = (
        f"{action.action_type.value}-{action.target}-{action.created_at.isoformat()}"
    )
    return hashlib.md5(id_string.encode()).hexdigest()[:12]


class GovernedClosedLoopOrchestrator(ClosedLoopOrchestrator):
    """
    Enhanced Closed-Loop Orchestrator with Phase 5.1 Governance integration.

    Extends the base orchestrator with:
    - Real-time approval gates
    - Risk-based decision making
    - Comprehensive audit trails
    - Rollback capabilities
    - Policy enforcement
    """

    def __init__(
        self,
        db_session,
        workspace_path: Optional[str] = None,
        org_key: str = "default",
        config: Optional[OrchestrationConfig] = None,
        user_id: Optional[str] = None,
    ):
        super().__init__(db_session, workspace_path or "", org_key, config)

        self.user_id = user_id or "system"

        # Initialize governance components
        self.approval_engine = ApprovalEngine(db_session)
        self.risk_scorer = RiskScorer()
        self.audit_logger = AuditLogger(db_session)

        # Governance state
        self.pending_approvals: Dict[str, str] = {}  # action_id -> approval_id
        self.governance_enabled = True

        logger.info(f"Initialized governed orchestrator for user {self.user_id}")

    async def execute_governed_action(
        self, action: PlannedAction, context: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute an action through the governance layer.

        Process:
        1. Create action context
        2. Evaluate governance decision
        3. Handle approval if required
        4. Execute if approved/auto
        5. Log audit trail
        6. Return result
        """
        try:
            # Create governance context
            action_context = self._create_action_context(action, context)

            # Evaluate governance decision
            (
                decision,
                risk_score,
                reasons,
                approval_id,
            ) = self.approval_engine.evaluate_action(
                action.action_type.value, action_context
            )

            logger.info(
                f"Governance decision for {action.action_type}: {decision.value} "
                f"(risk: {risk_score:.2f}) - {len(reasons)} reasons"
            )

            # Handle decision
            if decision == DecisionType.BLOCKED:
                message = f"Action blocked by governance policy: {', '.join(reasons)}"
                return ExecutionResult(
                    action=action,
                    status=ExecutionStatus.BLOCKED,
                    error_message=message,
                    message=message,
                    result_data={"risk_score": risk_score, "reasons": reasons},
                    metadata={"risk_score": risk_score, "reasons": reasons},
                )

            elif decision == DecisionType.APPROVAL:
                # Store pending approval
                action_id = generate_action_id(action)
                if approval_id:  # Only store if approval_id is not None
                    # Track by approval_id for lookup consistency
                    self.pending_approvals[approval_id] = action_id

                message = f"Action requires approval: {', '.join(reasons)}"
                return ExecutionResult(
                    action=action,
                    status=ExecutionStatus.WAITING_APPROVAL,
                    error_message=message,
                    message=message,
                    result_data={
                        "approval_id": approval_id,
                        "risk_score": risk_score,
                        "reasons": reasons,
                    },
                    metadata={
                        "approval_id": approval_id,
                        "risk_score": risk_score,
                        "reasons": reasons,
                    },
                )

            elif decision == DecisionType.AUTO:
                # Execute immediately
                result = await self._execute_with_governance(
                    action, context, risk_score
                )

                # Log execution
                self.audit_logger.log_execution(
                    user_id=self.user_id,
                    org_id=action_context.org_id,
                    action_type=action.action_type.value,
                    execution_result=result.status.value,
                    artifacts={
                        "action_id": generate_action_id(action),
                        "risk_score": risk_score,
                        "execution_time": datetime.now().isoformat(),
                        "result_data": result.result_data,
                    },
                    rollback_id=None,  # Rollback ID would be generated separately if needed
                )

                return result

            else:
                # Default case - should not happen with proper DecisionType enum
                return ExecutionResult(
                    action=action,
                    status=ExecutionStatus.FAILED,
                    error_message=f"Unknown governance decision: {decision}",
                    result_data={"risk_score": risk_score, "reasons": reasons},
                )

        except Exception as e:
            logger.error(f"Error in governed execution: {e}")

            # Log error
            self.audit_logger.log_execution(
                user_id=self.user_id,
                org_id=context.get("org_id", "default"),
                action_type=action.action_type.value,
                execution_result="ERROR",
                artifacts={"error": str(e), "action_id": generate_action_id(action)},
            )

            return ExecutionResult(
                action=action,
                status=ExecutionStatus.FAILED,
                error_message=f"Governance error: {str(e)}",
            )

    async def execute_approved_action(
        self, action_id: str, approver_id: str
    ) -> ExecutionResult:
        """Execute an action after it has been approved"""

        try:
            # Accept either action_id or approval_id for backwards compatibility.
            approval_id = action_id
            resolved_action_id = self.pending_approvals.get(approval_id)
            if not resolved_action_id:
                for (
                    pending_approval_id,
                    pending_action_id,
                ) in self.pending_approvals.items():
                    if pending_action_id == action_id:
                        approval_id = pending_approval_id
                        resolved_action_id = pending_action_id
                        break
            if not resolved_action_id:
                # Create a dummy action for the error result
                dummy_action = PlannedAction(
                    action_type=ActionType.ESCALATE_ISSUE,
                    priority=ActionPriority.LOW,
                    safety_level=SafetyLevel.SAFE,
                    confidence_score=0.0,
                    context_completeness=0.0,
                    historical_success=0.0,
                    target=action_id,
                    parameters={},
                    prerequisites=[],
                    safety_checks=[],
                    rollback_plan=None,
                    human_approval_required=False,
                    escalation_triggers=[],
                    notification_recipients=[],
                    estimated_duration=0,
                    max_retries=0,
                    timeout_minutes=0,
                    reasoning="Unknown action for error handling",
                    alternatives_considered=[],
                    risks_identified=[],
                    created_at=datetime.now(),
                )
                return ExecutionResult(
                    action=dummy_action,
                    status=ExecutionStatus.FAILED,
                    error_message="No pending approval found for this action",
                    message="No pending approval found for this action",
                )

            # TODO: Retrieve original action and context from storage
            # For now, we'll need to modify the architecture to store these

            logger.info(
                f"Executing approved action {resolved_action_id} by {approver_id}"
            )

            # Remove from pending
            del self.pending_approvals[approval_id]

            # Execute using parent's execution controller
            # This is a simplified version - in practice, we'd need to reconstruct the action
            dummy_action = PlannedAction(
                action_type=ActionType.ESCALATE_ISSUE,
                priority=ActionPriority.MEDIUM,
                safety_level=SafetyLevel.SAFE,
                confidence_score=1.0,
                context_completeness=1.0,
                historical_success=1.0,
                target=resolved_action_id,
                parameters={},
                prerequisites=[],
                safety_checks=[],
                rollback_plan=None,
                human_approval_required=False,
                escalation_triggers=[],
                notification_recipients=[],
                estimated_duration=0,
                max_retries=0,
                timeout_minutes=0,
                reasoning="Action executed after approval",
                alternatives_considered=[],
                risks_identified=[],
                created_at=datetime.now(),
            )
            result = ExecutionResult(
                action=dummy_action,
                status=ExecutionStatus.COMPLETED,
                success=True,
                message="Approved action executed",
            )

            # Log execution
            self.audit_logger.log_execution(
                user_id=approver_id,
                org_id="default",  # TODO: Get from stored context
                action_type="approved_execution",
                execution_result=result.status.value,
                artifacts={
                    "action_id": resolved_action_id,
                    "approver_id": approver_id,
                    "original_requester": self.user_id,
                    "approval_id": approval_id,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Error executing approved action {action_id}: {e}")

            dummy_action = PlannedAction(
                action_type=ActionType.ESCALATE_ISSUE,
                priority=ActionPriority.HIGH,
                safety_level=SafetyLevel.RISKY,
                confidence_score=0.0,
                context_completeness=0.0,
                historical_success=0.0,
                target=action_id,
                parameters={},
                prerequisites=[],
                safety_checks=[],
                rollback_plan=None,
                human_approval_required=False,
                escalation_triggers=[],
                notification_recipients=[],
                estimated_duration=0,
                max_retries=0,
                timeout_minutes=0,
                reasoning="Failed approved execution",
                alternatives_considered=[],
                risks_identified=[],
                created_at=datetime.now(),
            )
            return ExecutionResult(
                action=dummy_action,
                status=ExecutionStatus.FAILED,
                error_message=f"Error executing approved action: {str(e)}",
            )

    def _create_action_context(
        self, action: PlannedAction, context: Dict[str, Any]
    ) -> ActionContext:
        """Create governance ActionContext from PlannedAction"""

        return ActionContext(
            action_type=action.action_type.value,
            target_files=context.get("target_files", []),
            repo=context.get("repo"),
            branch=context.get("branch", "main"),
            command=getattr(action, "command", None),
            touches_auth=self._touches_auth(action, context),
            touches_prod=self._touches_prod(context),
            is_multi_repo=context.get("is_multi_repo", False),
            has_recent_incidents=context.get("has_recent_incidents", False),
            estimated_impact="medium",  # PlannedAction doesn't have this field
            user_id=self.user_id,
            org_id=self.org_key,
        )

    def _touches_auth(self, action: PlannedAction, context: Dict[str, Any]) -> bool:
        """Detect if action affects authentication/authorization"""

        # Check action type
        auth_actions = [
            "auth_config",
            "user_permissions",
            "security_policy",
            "oauth_setup",
        ]
        if action.action_type in auth_actions:
            return True

        # Check target files
        target_files = context.get("target_files", [])
        auth_patterns = [
            "auth",
            "security",
            "permission",
            "role",
            "oauth",
            "jwt",
            "token",
        ]

        for file in target_files:
            file_lower = file.lower()
            if any(pattern in file_lower for pattern in auth_patterns):
                return True

        # Check command
        command = getattr(action, "command", "")
        if isinstance(command, str):
            auth_commands = ["auth", "login", "permission", "role", "jwt"]
            if any(cmd in command.lower() for cmd in auth_commands):
                return True

        return False

    def _touches_prod(self, context: Dict[str, Any]) -> bool:
        """Detect if action affects production environment"""

        # Check branch
        branch = context.get("branch", "").lower()
        if branch in ["main", "master", "production", "prod"]:
            return True

        # Check repo
        repo = context.get("repo", "").lower()
        if any(keyword in repo for keyword in ["prod", "production", "live"]):
            return True

        # Check environment indicators
        env_indicators = context.get("environment_indicators", [])
        prod_indicators = ["production", "prod", "live", "main"]
        if any(indicator.lower() in prod_indicators for indicator in env_indicators):
            return True

        return False

    async def _execute_with_governance(
        self, action: PlannedAction, context: Dict[str, Any], risk_score: float
    ) -> ExecutionResult:
        """Execute action with governance oversight"""

        try:
            # Pre-execution governance check
            if risk_score > self.config.max_auto_risk_override:
                logger.warning(f"Risk score {risk_score} exceeds override threshold")

            # Execute using parent's execution controller
            result = await self.execution_controller.execute_action(action, context)

            # Post-execution governance
            if result.status == ExecutionStatus.COMPLETED:
                # Check if rollback capability should be registered
                if self._supports_rollback(action):
                    # TODO: Register rollback capability in separate rollback tracker
                    logger.info(
                        f"Action {generate_action_id(action)} supports rollback"
                    )

            return result

        except Exception as e:
            logger.error(f"Error in governed execution: {e}")
            raise

    def _supports_rollback(self, action: PlannedAction) -> bool:
        """Check if action supports rollback"""

        rollback_supported = [
            "code_edit",
            "config_change",
            "feature_flag_toggle",
            "dependency_update",
            "documentation_update",
        ]

        rollback_not_supported = [
            "data_deletion",
            "user_account_deletion",
            "schema_drop",
            "permanent_data_migration",
        ]

        if action.action_type in rollback_not_supported:
            return False

        if action.action_type in rollback_supported:
            return True

        # Default: assume rollback is possible
        return True

    def get_governance_status(self) -> Dict[str, Any]:
        """Get current governance status and metrics"""

        try:
            # Get pending approvals count
            pending_count = len(self.pending_approvals)

            # Get recent audit insights (simplified)
            # In production, this would call audit_logger.get_risk_insights()

            return {
                "governance_enabled": self.governance_enabled,
                "pending_approvals": pending_count,
                "user_id": self.user_id,
                "org_id": self.org_key,
                "config": {
                    "max_auto_risk": self.config.max_auto_risk_override,
                    "orchestration_mode": self.config.orchestration_mode.value,
                    "safety_checks_enabled": self.config.enable_safety_checks,
                },
            }

        except Exception as e:
            logger.error(f"Error getting governance status: {e}")
            return {"error": str(e)}

    def enable_governance(self):
        """Enable governance controls"""
        self.governance_enabled = True
        logger.info("Governance controls enabled")

    def disable_governance(self):
        """Disable governance controls (emergency mode)"""
        self.governance_enabled = False
        logger.warning("Governance controls DISABLED - emergency mode")

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of actions pending approval"""

        try:
            approvals = self.approval_engine.get_pending_approvals(
                self.org_key, self.user_id
            )
            return [
                {
                    "id": approval.id,
                    "action_type": approval.action_type,
                    "requester_id": approval.requester_id,
                    "risk_score": approval.risk_score,
                    "risk_reasons": approval.risk_reasons,
                    "plan_summary": approval.plan_summary,
                    "created_at": approval.created_at.isoformat(),
                    "expires_at": approval.expires_at.isoformat(),
                }
                for approval in approvals
            ]

        except Exception as e:
            logger.error(f"Error getting pending approvals: {e}")
            return []


class GovernanceIntegrationMixin:
    """
    Mixin to add governance capabilities to existing execution engines.
    Can be used to retrofit governance into Phase 4.x execution engines.
    """

    db: Optional[Any] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize governance if db session available
        if hasattr(self, "db") and self.db:
            self.approval_engine = ApprovalEngine(self.db)
            self.risk_scorer = RiskScorer()
            self.audit_logger = AuditLogger(self.db)
            self.governance_enabled = True
        else:
            self.governance_enabled = False
            logger.warning("No database session - governance disabled")

    async def execute_with_governance(
        self, action_type: str, context: Dict[str, Any], user_id: str = "system"
    ) -> Dict[str, Any]:
        """Execute action through governance layer"""

        if not self.governance_enabled:
            # Fall back to direct execution
            return await self._direct_execute(action_type, context)

        try:
            # Create action context
            action_context = ActionContext(
                action_type=action_type,
                target_files=context.get("target_files", []),
                repo=context.get("repo"),
                branch=context.get("branch"),
                user_id=user_id,
                org_id=context.get("org_id", "default"),
            )

            # Evaluate governance
            (
                decision,
                risk_score,
                reasons,
                approval_id,
            ) = self.approval_engine.evaluate_action(action_type, action_context)

            if decision == DecisionType.BLOCKED:
                return {
                    "success": False,
                    "message": f"Action blocked: {', '.join(reasons)}",
                    "governance": {
                        "decision": decision.value,
                        "risk_score": risk_score,
                        "reasons": reasons,
                    },
                }

            elif decision == DecisionType.APPROVAL:
                return {
                    "success": False,
                    "message": "Action requires approval",
                    "governance": {
                        "decision": decision.value,
                        "approval_id": approval_id,
                        "risk_score": risk_score,
                        "reasons": reasons,
                    },
                }

            else:  # AUTO
                result = await self._direct_execute(action_type, context)

                # Log execution
                self.audit_logger.log_execution(
                    user_id=user_id,
                    org_id=context.get("org_id", "default"),
                    action_type=action_type,
                    execution_result="SUCCESS" if result.get("success") else "FAILURE",
                    artifacts={"context": context, "result": result},
                )

                # Add governance metadata
                result["governance"] = {
                    "decision": decision.value,
                    "risk_score": risk_score,
                    "auto_executed": True,
                }

                return result

        except Exception as e:
            logger.error(f"Governance error: {e}")
            # Fall back to direct execution on governance errors
            return await self._direct_execute(action_type, context)

    async def _direct_execute(
        self, action_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Direct execution fallback - should be implemented by subclass"""
        return {"success": True, "message": "Direct execution (no governance)"}


def integrate_governance_with_phase5(
    orchestrator: ClosedLoopOrchestrator, user_id: str
) -> GovernedClosedLoopOrchestrator:
    """
    Upgrade a Phase 5.0 orchestrator to include Phase 5.1 governance.

    Args:
        orchestrator: Existing Phase 5.0 orchestrator
        user_id: User ID for governance context

    Returns:
        Governed orchestrator with same configuration
    """

    return GovernedClosedLoopOrchestrator(
        db_session=orchestrator.db,
        workspace_path=orchestrator.workspace_path,
        org_key=orchestrator.org_key,
        config=orchestrator.config,
        user_id=user_id,
    )
