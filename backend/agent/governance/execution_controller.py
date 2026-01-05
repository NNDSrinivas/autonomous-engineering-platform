"""
Governed Execution Controller

Enhanced execution controller that integrates Phase 5.1 governance controls
with Phase 5.0 autonomous execution capabilities.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
import logging
import traceback
import uuid

from ..governance.approval_engine import ApprovalEngine
from ..governance.audit_logger import AuditLogger
from ..governance.rollback_controller import RollbackController
from ..governance import ActionContext, DecisionType
from ..closedloop.execution_controller import (
    ExecutionController,
    ExecutionResult,
    ExecutionStatus,
)
from ..closedloop.auto_planner import (
    PlannedAction,
    ExecutionPlan,
    ActionType,
    ActionPriority,
    SafetyLevel,
)
from ..closedloop.context_resolver import ResolvedContext

logger = logging.getLogger(__name__)


class GovernedExecutionController(ExecutionController):
    """
    Enhanced Execution Controller with integrated governance.

    Extends the base execution controller with:
    - Pre-execution governance checks
    - Approval workflow integration
    - Real-time risk assessment
    - Comprehensive audit logging
    - Automated rollback capabilities
    """

    def __init__(
        self,
        db_session,
        workspace_path: Optional[str] = None,
        org_key: str = "default",
        user_id: Optional[str] = None,
    ):
        super().__init__(db_session, workspace_path)

        self.user_id = user_id or "system"
        self.org_key = org_key

        # Initialize governance components
        self.approval_engine = ApprovalEngine(db_session)
        self.audit_logger = AuditLogger(db_session)
        self.rollback_controller = RollbackController(db_session)

        # Execution state
        self.pending_executions: Dict[str, Dict] = (
            {}
        )  # approval_id -> execution context
        self.governance_enabled = True
        self.safety_mode = True

        logger.info(
            f"Initialized governed execution controller for user {self.user_id}"
        )

    async def execute_action(
        self,
        action: PlannedAction,
        context: ResolvedContext,
        plan: Optional[ExecutionPlan] = None,
        *,
        bypass_governance: bool = False,
    ) -> ExecutionResult:
        """
        Execute an action through the governance framework.

        Process:
        1. Create governance context
        2. Evaluate approval requirements
        3. Execute if approved/auto
        4. Log comprehensive audit trail
        5. Setup rollback capabilities
        6. Return detailed result
        """

        execution_start = datetime.now()
        action_id = self._action_identifier(action)
        context_data = self._normalize_context(context)
        action_context: Optional[ActionContext] = None

        try:
            # Create governance context
            action_context = self._create_action_context(action, context_data)

            # Check governance (unless bypassed for emergency operations)
            if self.governance_enabled and not bypass_governance:
                decision, risk_score, reasons, approval_id = (
                    self.approval_engine.evaluate_action(
                        action.action_type.value, action_context
                    )
                )

                logger.info(
                    f"Governance decision for {action.action_type.value}: {decision.value} "
                    f"(risk: {risk_score:.3f}) - {reasons}"
                )

                # Handle governance decision
                if decision == DecisionType.BLOCKED:
                    return ExecutionResult(
                        action=action,
                        status=ExecutionStatus.BLOCKED,
                        error_message="Governance policy blocked this action",
                        result_data={
                            "action_id": action_id,
                            "governance": {
                                "decision": decision.value,
                                "risk_score": risk_score,
                                "reasons": reasons,
                                "policy_enforced": True,
                            },
                        },
                    )

                if decision == DecisionType.APPROVAL:
                    approval_token = approval_id or f"approval-{uuid.uuid4()}"
                    # Store for later execution
                    self.pending_executions[approval_token] = {
                        "action": action,
                        "context": context,
                        "plan": plan,
                        "created_at": execution_start,
                        "requester_id": self.user_id,
                    }

                    return ExecutionResult(
                        action=action,
                        status=ExecutionStatus.WAITING_APPROVAL,
                        error_message="Action requires approval before execution",
                        result_data={
                            "action_id": action_id,
                            "governance": {
                                "decision": decision.value,
                                "approval_id": approval_token,
                                "risk_score": risk_score,
                                "reasons": reasons,
                                "approval_required": True,
                            },
                        },
                    )

            # Execute immediately (auto decision or governance bypassed)
            result = await self._execute_with_safety_checks(
                action, context, plan, action_context, context_data
            )

            # Setup rollback if execution succeeded
            rollback_context = None
            if result.status == ExecutionStatus.COMPLETED and self._supports_rollback(
                action
            ):
                rollback_context = self._setup_rollback(action, context_data, result)

            # Log execution
            artifacts = {
                "action_id": action_id,
                "execution_time_ms": (datetime.now() - execution_start).total_seconds()
                * 1000,
                "result_data": result.result_data,
            }
            if rollback_context:
                artifacts["rollback_context"] = rollback_context

            audit_entry_id = self.audit_logger.log_execution(
                user_id=self.user_id,
                org_id=action_context.org_id,
                action_type=action.action_type.value,
                execution_result=result.status.value,
                artifacts=artifacts,
                rollback_id=action_id if rollback_context else None,
            )

            result.result_data = result.result_data or {}
            governance_data = result.result_data.setdefault("governance", {})
            governance_data.update(
                {
                    "audit_entry_id": audit_entry_id,
                    "rollback_available": rollback_context is not None,
                }
            )
            if rollback_context:
                governance_data["rollback_action_id"] = audit_entry_id

            return result

        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")

            # Log execution error
            org_id = (
                action_context.org_id
                if action_context
                else context_data.get("org_id") or self.org_key
            )
            self.audit_logger.log_execution(
                user_id=self.user_id,
                org_id=org_id,
                action_type=action.action_type.value,
                execution_result="ERROR",
                artifacts={
                    "action_id": action_id,
                    "error": str(e),
                    "execution_time_ms": (
                        datetime.now() - execution_start
                    ).total_seconds()
                    * 1000,
                },
            )

            return ExecutionResult(
                action=action,
                status=ExecutionStatus.FAILED,
                error_message=f"Execution failed: {str(e)}",
                error_traceback=traceback.format_exc(),
                result_data={"action_id": action_id},
            )

    async def execute_approved_action(
        self, approval_id: str, approver_id: str, approval_notes: Optional[str] = None
    ) -> ExecutionResult:
        """Execute an action that has been approved"""

        try:
            # Get pending execution
            if approval_id not in self.pending_executions:
                fallback_action = self._build_placeholder_action(
                    approval_id,
                    "No pending execution found for approval",
                )
                return ExecutionResult(
                    action=fallback_action,
                    status=ExecutionStatus.FAILED,
                    error_message=f"No pending execution found for approval {approval_id}",
                )

            execution_context = self.pending_executions.pop(approval_id)
            action = execution_context["action"]
            context = execution_context["context"]
            plan = execution_context["plan"]

            logger.info(
                f"Executing approved action {self._action_identifier(action)} "
                f"(approval: {approval_id})"
            )

            approval_recorded = self.approval_engine.approve_request(
                approval_id, approver_id, comment=approval_notes or ""
            )
            if not approval_recorded:
                logger.warning(
                    f"Approval {approval_id} not found or expired; proceeding with execution"
                )

            # Execute the action (bypass governance since it's already approved)
            result = await self.execute_action(
                action, context, plan, bypass_governance=True
            )

            # Update result with approval metadata
            result.result_data = result.result_data or {}
            approval_data = result.result_data.setdefault("governance", {})
            approval_data.update(
                {
                    "approval_id": approval_id,
                    "approver_id": approver_id,
                    "approval_notes": approval_notes,
                    "approved_execution": True,
                    "approval_recorded": approval_recorded,
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error executing approved action {approval_id}: {e}")
            fallback_action = self._build_placeholder_action(
                approval_id,
                "Error executing approved action",
            )
            return ExecutionResult(
                action=fallback_action,
                status=ExecutionStatus.FAILED,
                error_message=f"Error executing approved action: {str(e)}",
                error_traceback=traceback.format_exc(),
            )

    async def rollback_action(
        self, rollback_id: str, requester_id: str, reason: Optional[str] = None
    ) -> ExecutionResult:
        """Rollback a previously executed action"""

        try:
            logger.info(
                f"Initiating rollback {rollback_id} requested by {requester_id}"
            )

            # Execute rollback
            rollback_result = self.rollback_controller.rollback_action(
                rollback_id, requester_id, reason or ""
            )

            success = bool(rollback_result.get("success"))
            message = rollback_result.get("message", "Rollback completed")

            # Log rollback
            self.audit_logger.log_rollback(
                user_id=requester_id,
                org_id=self.org_key,
                original_action_id=rollback_id,
                rollback_result="SUCCESS" if success else "FAILED",
                artifacts={
                    "rollback_id": rollback_result.get("rollback_id"),
                    "reason": reason,
                    "strategy": rollback_result.get("strategy_used"),
                    "timestamp": rollback_result.get("timestamp"),
                },
            )

            rollback_action = self._build_placeholder_action(
                rollback_id,
                "Rollback execution",
                action_type=ActionType.ROLLBACK_DEPLOYMENT,
            )
            result = ExecutionResult(
                action=rollback_action,
                status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
                success=success,
            )
            result.result_data = {
                "rollback": rollback_result,
                "message": message,
            }
            if not success:
                result.error_message = f"Rollback failed: {message}"

            return result

        except Exception as e:
            logger.error(f"Error during rollback {rollback_id}: {e}")

            # Log rollback error
            self.audit_logger.log_rollback(
                user_id=requester_id,
                org_id=self.org_key,
                original_action_id=rollback_id,
                rollback_result="ERROR",
                artifacts={"error": str(e), "reason": reason},
            )

            fallback_action = self._build_placeholder_action(
                rollback_id,
                "Rollback failed",
                action_type=ActionType.ROLLBACK_DEPLOYMENT,
            )
            return ExecutionResult(
                action=fallback_action,
                status=ExecutionStatus.FAILED,
                error_message=f"Rollback failed: {str(e)}",
                error_traceback=traceback.format_exc(),
            )

    async def _execute_with_safety_checks(
        self,
        action: PlannedAction,
        context: ResolvedContext,
        plan: Optional[ExecutionPlan],
        action_context: ActionContext,
        context_data: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute action with additional safety checks"""

        if self.safety_mode:
            # Pre-execution safety checks
            safety_issues = await self._run_safety_checks(
                action, context_data, action_context
            )
            if safety_issues:
                result = ExecutionResult(
                    action=action,
                    status=ExecutionStatus.FAILED,
                    error_message="Safety checks failed",
                )
                result.safety_checks_passed = False
                result.result_data = {"safety_failures": safety_issues}
                return result

        # Execute using parent's execution logic
        result = await super().execute_action(action, context, plan)

        if self.safety_mode and result.status == ExecutionStatus.COMPLETED:
            # Post-execution validation
            validation_issues = await self._validate_execution_result(
                action, context_data, result
            )
            if validation_issues:
                logger.warning(f"Post-execution validation issues: {validation_issues}")
                result.result_data = result.result_data or {}
                result.result_data["validation_warnings"] = validation_issues

        return result

    async def _run_safety_checks(
        self,
        action: PlannedAction,
        context_data: Dict[str, Any],
        action_context: ActionContext,
    ) -> List[str]:
        """Run pre-execution safety checks"""

        issues = []

        try:
            # Check for high-risk patterns
            if action_context.touches_auth and action_context.touches_prod:
                issues.append(
                    "Action affects both authentication and production systems"
                )

            # Check for destructive operations
            destructive_keywords = ["delete", "drop", "remove", "destroy", "truncate"]
            if any(
                keyword in action.action_type.value.lower()
                for keyword in destructive_keywords
            ):
                if not context_data.get("destructive_confirmed", False):
                    issues.append(
                        "Destructive operation requires explicit confirmation"
                    )

            # Check workspace state
            if self.workspace_path:
                # Check for uncommitted changes
                # TODO: Add git status check
                pass

            # Check resource constraints
            # TODO: Add memory/disk space checks

        except Exception as e:
            logger.error(f"Error in safety checks: {e}")
            issues.append(f"Safety check error: {str(e)}")

        return issues

    async def _validate_execution_result(
        self,
        action: PlannedAction,
        context_data: Dict[str, Any],
        result: ExecutionResult,
    ) -> List[str]:
        """Validate execution result for consistency"""

        warnings = []

        try:
            # Check if expected artifacts were created
            expected_outputs = action.parameters.get("expected_outputs")
            if expected_outputs:
                result_data = result.result_data or {}
                for expected_output in expected_outputs:
                    if expected_output not in result_data:
                        warnings.append(f"Expected output missing: {expected_output}")

            # Check for unexpected side effects
            # TODO: Add file system change detection
            # TODO: Add process monitoring

        except Exception as e:
            logger.error(f"Error in result validation: {e}")
            warnings.append(f"Validation error: {str(e)}")

        return warnings

    def _normalize_context(self, context: Any) -> Dict[str, Any]:
        """Normalize context payload to a dictionary for governance checks."""
        if isinstance(context, dict):
            return context

        repo_info = context.repository_info or {}
        deployment_info = context.deployment_info or {}
        project_context = context.project_context or {}

        return {
            "target_files": list(context.related_code_files or []),
            "repo": repo_info.get("name")
            or repo_info.get("full_name")
            or repo_info.get("repository"),
            "branch": repo_info.get("branch") or repo_info.get("default_branch"),
            "environment": deployment_info.get("environment"),
            "environment_indicators": deployment_info.get("environment_indicators", []),
            "is_multi_repo": project_context.get("is_multi_repo", False),
            "has_recent_incidents": project_context.get("has_recent_incidents", False),
            "org_id": project_context.get("org_id"),
        }

    def _action_identifier(self, action: PlannedAction) -> str:
        """Generate a stable identifier for logging and rollback references."""
        id_string = f"{action.action_type.value}-{action.target}-{action.created_at.isoformat()}"
        return hashlib.md5(id_string.encode()).hexdigest()[:12]

    def _build_placeholder_action(
        self,
        target: str,
        reason: str,
        action_type: ActionType = ActionType.ESCALATE_ISSUE,
    ) -> PlannedAction:
        """Create a minimal PlannedAction for error/rollback results."""
        return PlannedAction(
            action_type=action_type,
            priority=ActionPriority.LOW,
            safety_level=SafetyLevel.SAFE,
            confidence_score=0.0,
            context_completeness=0.0,
            historical_success=0.0,
            target=target,
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
            reasoning=reason,
            alternatives_considered=[],
            risks_identified=[],
            created_at=datetime.now(),
        )

    def _create_action_context(
        self, action: PlannedAction, context_data: Dict[str, Any]
    ) -> ActionContext:
        """Create ActionContext from execution parameters"""

        estimated_impact = getattr(action, "estimated_impact", None)
        if not estimated_impact:
            impact_map = {
                SafetyLevel.SAFE: "low",
                SafetyLevel.CAUTIOUS: "medium",
                SafetyLevel.RISKY: "high",
                SafetyLevel.DANGEROUS: "high",
            }
            estimated_impact = impact_map.get(action.safety_level, "medium")

        return ActionContext(
            action_type=action.action_type.value,
            target_files=context_data.get("target_files", []),
            repo=context_data.get("repo"),
            branch=context_data.get("branch", "main"),
            command=getattr(action, "command", None),
            touches_auth=self._detect_auth_impact(action, context_data),
            touches_prod=self._detect_prod_impact(context_data),
            is_multi_repo=context_data.get("is_multi_repo", False),
            has_recent_incidents=context_data.get("has_recent_incidents", False),
            estimated_impact=estimated_impact,
            user_id=self.user_id,
            org_id=context_data.get("org_id") or self.org_key,
        )

    def _detect_auth_impact(
        self, action: PlannedAction, context_data: Dict[str, Any]
    ) -> bool:
        """Detect if action impacts authentication/authorization"""

        # Check action type
        if "auth" in action.action_type.value.lower():
            return True

        # Check target files
        auth_patterns = [
            "auth",
            "security",
            "permission",
            "role",
            "oauth",
            "jwt",
            "session",
        ]
        target_files = context_data.get("target_files", [])

        for file_path in target_files:
            file_lower = file_path.lower()
            if any(pattern in file_lower for pattern in auth_patterns):
                return True

        return False

    def _detect_prod_impact(self, context_data: Dict[str, Any]) -> bool:
        """Detect if action impacts production environment"""

        # Check branch
        branch = context_data.get("branch", "").lower()
        if branch in ["main", "master", "production", "prod", "release"]:
            return True

        # Check environment
        env = context_data.get("environment", "").lower()
        if env in ["production", "prod", "live"]:
            return True

        # Check environment indicators
        env_indicators = context_data.get("environment_indicators", [])
        if any(
            indicator.lower() in ["production", "prod", "live"]
            for indicator in env_indicators
        ):
            return True

        return False

    def _setup_rollback(
        self,
        action: PlannedAction,
        context_data: Dict[str, Any],
        result: ExecutionResult,
    ) -> Optional[Dict[str, Any]]:
        """Prepare rollback metadata for an executed action"""

        try:
            rollback_data = {
                "action_type": action.action_type.value,
                "action_id": self._action_identifier(action),
                "execution_context": context_data,
                "execution_result": result.result_data,
                "timestamp": datetime.now().isoformat(),
                "user_id": self.user_id,
            }

            logger.info(
                f"Rollback metadata prepared for {self._action_identifier(action)}"
            )
            return rollback_data

        except Exception as e:
            logger.error(
                f"Error preparing rollback metadata for {self._action_identifier(action)}: {e}"
            )
            return None

    def _supports_rollback(self, action: PlannedAction) -> bool:
        """Check if action type supports rollback"""

        # Actions that support rollback
        rollback_supported = [
            "code_edit",
            "config_change",
            "feature_toggle",
            "dependency_update",
            "documentation_update",
            "database_migration",
            "deployment",
        ]

        # Actions that don't support rollback
        rollback_forbidden = [
            "data_deletion",
            "account_deletion",
            "permanent_migration",
            "security_breach_response",
            "audit_log_entry",
        ]

        if action.action_type.value in rollback_forbidden:
            return False

        if action.action_type.value in rollback_supported:
            return True

        # Default: assume rollback possible for safety
        return True

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get execution controller metrics and status"""

        try:
            return {
                "governance_enabled": self.governance_enabled,
                "safety_mode": self.safety_mode,
                "pending_executions": len(self.pending_executions),
                "user_id": self.user_id,
                "org_id": self.org_key,
                "workspace_path": self.workspace_path,
                "components": {
                    "approval_engine": bool(self.approval_engine),
                    "audit_logger": bool(self.audit_logger),
                    "rollback_controller": bool(self.rollback_controller),
                },
            }

        except Exception as e:
            logger.error(f"Error getting execution metrics: {e}")
            return {"error": str(e)}

    def set_safety_mode(self, enabled: bool):
        """Enable/disable safety mode"""
        self.safety_mode = enabled
        logger.info(f"Safety mode {'enabled' if enabled else 'disabled'}")

    def enable_governance(self):
        """Enable governance controls"""
        self.governance_enabled = True
        logger.info("Governance enabled")

    def disable_governance(self):
        """Disable governance controls (emergency use)"""
        self.governance_enabled = False
        logger.warning("Governance DISABLED - emergency mode active")
