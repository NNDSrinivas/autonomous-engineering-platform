"""
Governance API Endpoints

REST API for Phase 5.1 Human-in-the-Loop Governance.
Provides endpoints for approval management, policy configuration, audit trails, and rollbacks.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from ..core.db import get_db
from ..agent.governance.approval_engine import ApprovalEngine
from ..agent.governance.risk_scorer import RiskScorer
from ..agent.governance.policy_store import AutonomyPolicyStore
from ..agent.governance.audit_logger import AuditLogger
from ..agent.governance.rollback_controller import RollbackController
from ..agent.governance import ActionContext, AutonomyPolicy, AutonomyLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])


# Initialize governance components
def get_approval_engine(db: Session = Depends(get_db)) -> ApprovalEngine:
    return ApprovalEngine(db)

def get_policy_store(db: Session = Depends(get_db)) -> AutonomyPolicyStore:
    return AutonomyPolicyStore(db)

def get_audit_logger(db: Session = Depends(get_db)) -> AuditLogger:
    return AuditLogger(db)

def get_rollback_controller(db: Session = Depends(get_db)) -> RollbackController:
    return RollbackController(db)


# Approval Management Endpoints

@router.post("/evaluate", summary="Evaluate action for approval requirement")
def evaluate_action(
    request: Request,
    payload: dict = Body(...),
    approval_engine: ApprovalEngine = Depends(get_approval_engine)
) -> Dict[str, Any]:
    """
    Evaluate whether an action should be auto-executed, require approval, or be blocked.
    
    Body:
        - action_type: str - Type of action (e.g., "code_edit", "deploy")
        - context: dict - Action context details
        
    Returns:
        - decision: str - "AUTO", "APPROVAL", or "BLOCKED"
        - risk_score: float - Risk score (0.0 - 1.0)
        - reasons: list - Explanation of decision
        - approval_id: str (optional) - ID if approval required
    """
    org_id = request.headers.get("X-Org-Id", "default")
    user_id = request.headers.get("X-User-Id", "unknown")
    
    try:
        action_type = str(payload.get("action_type") or "unknown")
        context_data = payload.get("context", {})
        
        # Create ActionContext
        context = ActionContext(
            action_type=action_type,
            target_files=context_data.get("target_files", []),
            repo=context_data.get("repo"),
            branch=context_data.get("branch"),
            command=context_data.get("command"),
            touches_auth=context_data.get("touches_auth", False),
            touches_prod=context_data.get("touches_prod", False),
            is_multi_repo=context_data.get("is_multi_repo", False),
            has_recent_incidents=context_data.get("has_recent_incidents", False),
            estimated_impact=context_data.get("estimated_impact", "low"),
            user_id=user_id,
            org_id=org_id
        )
        
        # Evaluate action
        decision, risk_score, reasons, approval_id = approval_engine.evaluate_action(
            action_type, context
        )
        
        return {
            "decision": decision.value,
            "risk_score": risk_score,
            "reasons": reasons,
            "approval_id": approval_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error evaluating action: {e}")
        raise HTTPException(500, f"Error evaluating action: {str(e)}")


@router.get("/approvals", summary="Get pending approval requests")
def get_pending_approvals(
    request: Request,
    user_id: Optional[str] = None,
    limit: int = 50,
    approval_engine: ApprovalEngine = Depends(get_approval_engine)
) -> Dict[str, Any]:
    """Get pending approval requests for organization or specific user"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        approvals = approval_engine.get_pending_approvals(org_id, user_id)
        
        # Convert to serializable format
        approval_list = []
        for approval in approvals[:limit]:
            approval_list.append({
                "id": approval.id,
                "action_type": approval.action_type,
                "requester_id": approval.requester_id,
                "risk_score": approval.risk_score,
                "risk_reasons": approval.risk_reasons,
                "plan_summary": approval.plan_summary,
                "created_at": approval.created_at.isoformat(),
                "expires_at": approval.expires_at.isoformat(),
                "context": {
                    "repo": approval.context.repo,
                    "branch": approval.context.branch,
                    "estimated_impact": approval.context.estimated_impact,
                    "touches_auth": approval.context.touches_auth,
                    "touches_prod": approval.context.touches_prod,
                    "is_multi_repo": approval.context.is_multi_repo
                }
            })
        
        return {
            "approvals": approval_list,
            "total": len(approval_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        raise HTTPException(500, f"Error getting approvals: {str(e)}")


@router.post("/approvals/{approval_id}/approve", summary="Approve a pending request")
def approve_request(
    approval_id: str,
    request: Request,
    payload: dict = Body({}),
    approval_engine: ApprovalEngine = Depends(get_approval_engine)
) -> Dict[str, Any]:
    """Approve a pending approval request"""
    approver_id = request.headers.get("X-User-Id", "unknown")
    comment = payload.get("comment", "")
    
    try:
        success = approval_engine.approve_request(approval_id, approver_id, comment)
        
        if not success:
            raise HTTPException(404, "Approval request not found or expired")
        
        return {
            "success": True,
            "message": "Approval request approved",
            "approver_id": approver_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving request: {e}")
        raise HTTPException(500, f"Error approving request: {str(e)}")


@router.post("/approvals/{approval_id}/reject", summary="Reject a pending request")
def reject_request(
    approval_id: str,
    request: Request,
    payload: dict = Body({}),
    approval_engine: ApprovalEngine = Depends(get_approval_engine)
) -> Dict[str, Any]:
    """Reject a pending approval request"""
    approver_id = request.headers.get("X-User-Id", "unknown")
    comment = payload.get("comment", "")
    
    try:
        success = approval_engine.reject_request(approval_id, approver_id, comment)
        
        if not success:
            raise HTTPException(404, "Approval request not found or expired")
        
        return {
            "success": True,
            "message": "Approval request rejected",
            "approver_id": approver_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        raise HTTPException(500, f"Error rejecting request: {str(e)}")


# Policy Management Endpoints

@router.get("/policy", summary="Get user's autonomy policy")
def get_autonomy_policy(
    request: Request,
    user_id: Optional[str] = None,
    repo: Optional[str] = None,
    policy_store: AutonomyPolicyStore = Depends(get_policy_store)
) -> Dict[str, Any]:
    """Get autonomy policy for a user"""
    org_id = request.headers.get("X-Org-Id", "default")
    target_user_id = user_id or request.headers.get("X-User-Id", "unknown")
    
    try:
        policy = policy_store.get_policy(target_user_id, org_id, repo)
        
        if not policy:
            raise HTTPException(404, "Policy not found")
        
        return {
            "user_id": policy.user_id,
            "org_id": policy.org_id,
            "repo": policy.repo,
            "autonomy_level": policy.autonomy_level.value,
            "max_auto_risk": policy.max_auto_risk,
            "blocked_actions": policy.blocked_actions or [],
            "auto_allowed_actions": policy.auto_allowed_actions or [],
            "require_approval_for": policy.require_approval_for or [],
            "created_at": policy.created_at.isoformat() if policy.created_at else None,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting policy: {e}")
        raise HTTPException(500, f"Error getting policy: {str(e)}")


@router.post("/policy", summary="Update user's autonomy policy")
def update_autonomy_policy(
    request: Request,
    payload: dict = Body(...),
    policy_store: AutonomyPolicyStore = Depends(get_policy_store)
) -> Dict[str, Any]:
    """Update autonomy policy for a user (requires admin/maintainer role)"""
    org_id = request.headers.get("X-Org-Id", "default")
    admin_user_id = request.headers.get("X-User-Id", "unknown")
    
    try:
        # TODO: Verify admin/maintainer role
        
        target_user_id = payload.get("user_id")
        if not target_user_id:
            raise HTTPException(400, "user_id is required")
        
        # Create policy object
        policy = AutonomyPolicy(
            user_id=target_user_id,
            org_id=org_id,
            repo=payload.get("repo"),
            autonomy_level=AutonomyLevel(payload.get("autonomy_level", "standard")),
            max_auto_risk=payload.get("max_auto_risk", 0.3),
            blocked_actions=payload.get("blocked_actions", []),
            auto_allowed_actions=payload.get("auto_allowed_actions", []),
            require_approval_for=payload.get("require_approval_for", []),
            updated_at=datetime.now()
        )
        
        success = policy_store.save_policy(policy)
        
        if not success:
            raise HTTPException(500, "Failed to save policy")
        
        return {
            "success": True,
            "message": "Policy updated successfully",
            "updated_by": admin_user_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating policy: {e}")
        raise HTTPException(500, f"Error updating policy: {str(e)}")


@router.get("/policies", summary="Get all policies for organization")
def get_organization_policies(
    request: Request,
    policy_store: AutonomyPolicyStore = Depends(get_policy_store)
) -> Dict[str, Any]:
    """Get all autonomy policies for organization"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        policies = policy_store.get_all_policies_for_org(org_id)
        
        policy_list = []
        for policy in policies:
            policy_list.append({
                "user_id": policy.user_id,
                "repo": policy.repo,
                "autonomy_level": policy.autonomy_level.value,
                "max_auto_risk": policy.max_auto_risk,
                "blocked_actions": policy.blocked_actions or [],
                "auto_allowed_actions": policy.auto_allowed_actions or [],
                "require_approval_for": policy.require_approval_for or [],
                "updated_at": policy.updated_at.isoformat() if policy.updated_at else None
            })
        
        return {
            "policies": policy_list,
            "total": len(policy_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting organization policies: {e}")
        raise HTTPException(500, f"Error getting policies: {str(e)}")


# Audit and Insights Endpoints

@router.get("/audit", summary="Get audit trail")
def get_audit_trail(
    request: Request,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    audit_logger: AuditLogger = Depends(get_audit_logger)
) -> Dict[str, Any]:
    """Get audit trail with optional filters"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        # Parse dates
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        
        entries = audit_logger.get_audit_trail(
            org_id=org_id,
            user_id=user_id,
            action_type=action_type,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit
        )
        
        audit_list = []
        for entry in entries:
            audit_list.append({
                "id": entry.id,
                "timestamp": entry.timestamp.isoformat(),
                "user_id": entry.user_id,
                "action_type": entry.action_type,
                "decision": entry.decision,
                "risk_score": entry.risk_score,
                "execution_result": entry.execution_result,
                "rollback_available": entry.rollback_available,
                "artifacts": entry.artifacts
            })
        
        return {
            "audit_entries": audit_list,
            "total": len(audit_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        raise HTTPException(500, f"Error getting audit trail: {str(e)}")


@router.get("/insights", summary="Get risk insights for dashboard")
def get_risk_insights(
    request: Request,
    days: int = 30,
    audit_logger: AuditLogger = Depends(get_audit_logger)
) -> Dict[str, Any]:
    """Get risk insights and statistics for governance dashboard"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        insights = audit_logger.get_risk_insights(org_id, days)
        return insights
        
    except Exception as e:
        logger.error(f"Error getting risk insights: {e}")
        raise HTTPException(500, f"Error getting insights: {str(e)}")


# Rollback Endpoints

@router.get("/rollback/{action_id}/check", summary="Check if action can be rolled back")
def check_rollback(
    action_id: str,
    rollback_controller: RollbackController = Depends(get_rollback_controller)
) -> Dict[str, Any]:
    """Check if an action can be rolled back"""
    try:
        can_rollback, reason = rollback_controller.can_rollback(action_id)
        
        return {
            "can_rollback": can_rollback,
            "reason": reason,
            "action_id": action_id
        }
        
    except Exception as e:
        logger.error(f"Error checking rollback: {e}")
        raise HTTPException(500, f"Error checking rollback: {str(e)}")


@router.post("/rollback/{action_id}", summary="Rollback an action")
def rollback_action(
    action_id: str,
    request: Request,
    payload: dict = Body({}),
    rollback_controller: RollbackController = Depends(get_rollback_controller)
) -> Dict[str, Any]:
    """Rollback a previously executed action"""
    user_id = request.headers.get("X-User-Id", "unknown")
    reason = payload.get("reason", "")
    
    try:
        result = rollback_controller.rollback_action(action_id, user_id, reason)
        return result
        
    except Exception as e:
        logger.error(f"Error rolling back action: {e}")
        raise HTTPException(500, f"Error rolling back action: {str(e)}")


@router.get("/rollback/history", summary="Get rollback history")
def get_rollback_history(
    request: Request,
    limit: int = 50,
    rollback_controller: RollbackController = Depends(get_rollback_controller)
) -> Dict[str, Any]:
    """Get rollback history for organization"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        history = rollback_controller.get_rollback_history(org_id, limit)
        return {"rollback_history": history, "total": len(history)}
        
    except Exception as e:
        logger.error(f"Error getting rollback history: {e}")
        raise HTTPException(500, f"Error getting rollback history: {str(e)}")


@router.get("/rollback/stats", summary="Get rollback statistics")
def get_rollback_stats(
    request: Request,
    days: int = 30,
    rollback_controller: RollbackController = Depends(get_rollback_controller)
) -> Dict[str, Any]:
    """Get rollback statistics"""
    org_id = request.headers.get("X-Org-Id", "default")
    
    try:
        stats = rollback_controller.get_rollback_stats(org_id, days)
        return stats
        
    except Exception as e:
        logger.error(f"Error getting rollback stats: {e}")
        raise HTTPException(500, f"Error getting rollback stats: {str(e)}")


# Utility Endpoints

@router.post("/risk/calculate", summary="Calculate risk score for context")
def calculate_risk(
    request: Request,
    payload: dict = Body(...),
) -> Dict[str, Any]:
    """Calculate risk score for given action and context"""
    try:
        action_type = str(payload.get("action_type") or "unknown")
        context_data = payload.get("context", {})
        
        # Create ActionContext
        context = ActionContext(
            action_type=action_type,
            target_files=context_data.get("target_files", []),
            repo=context_data.get("repo"),
            branch=context_data.get("branch"),
            command=context_data.get("command"),
            touches_auth=context_data.get("touches_auth", False),
            touches_prod=context_data.get("touches_prod", False),
            is_multi_repo=context_data.get("is_multi_repo", False),
            has_recent_incidents=context_data.get("has_recent_incidents", False),
            estimated_impact=context_data.get("estimated_impact", "low")
        )
        
        risk_scorer = RiskScorer()
        risk_score, reasons = risk_scorer.calculate_risk(action_type, context)
        
        return {
            "risk_score": risk_score,
            "reasons": reasons,
            "risk_level": risk_scorer.get_risk_level(risk_score).value
        }
        
    except Exception as e:
        logger.error(f"Error calculating risk: {e}")
        raise HTTPException(500, f"Error calculating risk: {str(e)}")


@router.post("/cleanup", summary="Cleanup expired approvals")
def cleanup_expired_approvals(
    approval_engine: ApprovalEngine = Depends(get_approval_engine)
) -> Dict[str, Any]:
    """Cleanup expired approval requests"""
    try:
        expired_count = approval_engine.cleanup_expired_approvals()
        
        return {
            "expired_approvals_removed": expired_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up expired approvals: {e}")
        raise HTTPException(500, f"Error cleaning up: {str(e)}")
