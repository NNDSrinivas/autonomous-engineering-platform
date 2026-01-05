"""
ApprovalEngine — The Gatekeeper

Every sensitive action passes through this engine for real-time governance decisions.
Integrates with existing org_policy system while adding granular real-time controls.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import uuid
import logging

from . import ActionContext, ApprovalRequest, AutonomyPolicy, DecisionType
from .risk_scorer import RiskScorer
from .policy_store import AutonomyPolicyStore
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class ApprovalEngine:
    """
    The gatekeeper that decides whether actions should be:
    1. Executed automatically
    2. Queued for approval
    3. Blocked by policy
    """

    def __init__(self, db_session=None):
        self.risk_scorer = RiskScorer()
        self.policy_store = AutonomyPolicyStore(db_session)
        self.audit_logger = AuditLogger(db_session)
        self.pending_approvals: Dict[str, ApprovalRequest] = {}

    def evaluate_action(
        self, action_type: str, context: ActionContext
    ) -> Tuple[DecisionType, float, List[str], Optional[str]]:
        """
        Evaluate whether an action should be auto-executed, require approval, or be blocked.

        Args:
            action_type: Type of action (e.g., "code_edit", "deploy", "schema_change")
            context: Action context with details

        Returns:
            Tuple of (decision, risk_score, reasons, approval_request_id)
        """
        try:
            user_id = context.user_id or "system"

            # Get user's autonomy policy
            policy = self.policy_store.get_policy(
                user_id=user_id,
                org_id=context.org_id,
                repo=context.repo,
            )

            # Calculate risk score
            risk_score, risk_reasons = self.risk_scorer.calculate_risk(
                action_type, context
            )

            # Check if action is explicitly blocked
            if self._is_action_blocked(action_type, policy, context):
                decision = DecisionType.BLOCKED
                self.audit_logger.log_decision(
                    user_id=user_id,
                    org_id=context.org_id,
                    action_type=action_type,
                    decision="BLOCKED",
                    risk_score=risk_score,
                    context=context,
                )
                return (
                    decision,
                    risk_score,
                    risk_reasons + ["Action blocked by policy"],
                    None,
                )

            # Check if action requires approval
            if self._requires_approval(action_type, risk_score, policy, context):
                approval_request = self._create_approval_request(
                    action_type=action_type,
                    context=context,
                    risk_score=risk_score,
                    risk_reasons=risk_reasons,
                )
                decision = DecisionType.APPROVAL
                self.audit_logger.log_decision(
                    user_id=user_id,
                    org_id=context.org_id,
                    action_type=action_type,
                    decision="APPROVAL_REQUIRED",
                    risk_score=risk_score,
                    context=context,
                    approval_id=approval_request.id,
                )
                return decision, risk_score, risk_reasons, approval_request.id

            # Action can be auto-executed
            decision = DecisionType.AUTO
            self.audit_logger.log_decision(
                user_id=user_id,
                org_id=context.org_id,
                action_type=action_type,
                decision="AUTO",
                risk_score=risk_score,
                context=context,
            )
            return decision, risk_score, risk_reasons, None

        except Exception as e:
            logger.error(f"Error evaluating action {action_type}: {e}")
            # Fail-safe: require approval on error
            return (
                DecisionType.APPROVAL,
                1.0,
                ["Error in evaluation - requires manual review"],
                None,
            )

    def _is_action_blocked(
        self, action_type: str, policy: Optional[AutonomyPolicy], context: ActionContext
    ) -> bool:
        """Check if action is explicitly blocked by policy"""
        if not policy or not policy.blocked_actions:
            return False

        return action_type in policy.blocked_actions

    def _requires_approval(
        self,
        action_type: str,
        risk_score: float,
        policy: Optional[AutonomyPolicy],
        context: ActionContext,
    ) -> bool:
        """Determine if action requires human approval"""
        if not policy:
            # Default policy: require approval for medium+ risk
            return risk_score > 0.3

        # Risk-based approval threshold
        if risk_score > policy.max_auto_risk:
            return True

        # Explicit approval requirements
        if policy.require_approval_for and action_type in policy.require_approval_for:
            return True

        # Auto-allowed actions override risk threshold
        if policy.auto_allowed_actions and action_type in policy.auto_allowed_actions:
            return False

        return False

    def _create_approval_request(
        self,
        action_type: str,
        context: ActionContext,
        risk_score: float,
        risk_reasons: List[str],
    ) -> ApprovalRequest:
        """Create a new approval request"""
        request_id = str(uuid.uuid4())

        # Create approval request
        approval_request = ApprovalRequest(
            id=request_id,
            action_type=action_type,
            context=context,
            risk_score=risk_score,
            risk_reasons=risk_reasons,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),  # 24h expiry
            requester_id=context.user_id or "system",
            org_id=context.org_id,
            plan_summary=f"{action_type} on {context.repo or 'workspace'}",
        )

        # Store pending approval
        self.pending_approvals[request_id] = approval_request

        # Persist to database
        self.policy_store.store_approval_request(approval_request)

        return approval_request

    def get_pending_approvals(
        self, org_id: str = "default", user_id: Optional[str] = None
    ) -> List[ApprovalRequest]:
        """Get pending approval requests for organization or user"""
        approvals = []

        for approval in self.pending_approvals.values():
            if approval.org_id != org_id:
                continue

            if user_id and approval.requester_id != user_id:
                continue

            # Check if expired
            if approval.expires_at < datetime.now():
                continue

            approvals.append(approval)

        return sorted(approvals, key=lambda a: a.created_at, reverse=True)

    def approve_request(
        self, approval_id: str, approver_id: str, comment: str = ""
    ) -> bool:
        """Approve a pending request"""
        if approval_id not in self.pending_approvals:
            return False

        approval = self.pending_approvals[approval_id]

        # Check if expired
        if approval.expires_at < datetime.now():
            del self.pending_approvals[approval_id]
            return False

        # Log approval
        self.audit_logger.log_approval(
            approval_id=approval_id,
            approver_id=approver_id,
            decision="APPROVED",
            comment=comment,
            org_id=approval.org_id,
        )

        # Remove from pending
        del self.pending_approvals[approval_id]

        # Update database
        self.policy_store.update_approval_status(
            approval_id, "approved", approver_id, comment
        )

        return True

    def reject_request(
        self, approval_id: str, approver_id: str, comment: str = ""
    ) -> bool:
        """Reject a pending request"""
        if approval_id not in self.pending_approvals:
            return False

        approval = self.pending_approvals[approval_id]

        # Log rejection
        self.audit_logger.log_approval(
            approval_id=approval_id,
            approver_id=approver_id,
            decision="REJECTED",
            comment=comment,
            org_id=approval.org_id,
        )

        # Remove from pending
        del self.pending_approvals[approval_id]

        # Update database
        self.policy_store.update_approval_status(
            approval_id, "rejected", approver_id, comment
        )

        return True

    def cleanup_expired_approvals(self) -> int:
        """Remove expired approval requests"""
        expired_count = 0
        current_time = datetime.now()

        expired_ids = [
            approval_id
            for approval_id, approval in self.pending_approvals.items()
            if approval.expires_at < current_time
        ]

        for approval_id in expired_ids:
            del self.pending_approvals[approval_id]
            self.policy_store.update_approval_status(approval_id, "expired")
            expired_count += 1

        return expired_count
