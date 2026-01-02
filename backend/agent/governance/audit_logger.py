"""
AuditLogger — Immutable Audit Trail

Provides comprehensive audit logging for all governance decisions and actions.
Ensures compliance with enterprise audit requirements and regulatory standards.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import uuid
import logging

from . import AuditEntry, ActionContext

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Logs all governance decisions and actions for audit purposes.
    Creates immutable records that satisfy enterprise compliance requirements.
    """
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.buffer = []  # Buffer for batch writes
        self.buffer_size = 100
    
    def log_decision(
        self,
        user_id: str,
        org_id: str,
        action_type: str,
        decision: str,
        risk_score: float,
        context: ActionContext,
        approval_id: Optional[str] = None,
        execution_result: Optional[str] = None
    ) -> str:
        """
        Log a governance decision.
        
        Args:
            user_id: User who requested the action
            org_id: Organization ID
            action_type: Type of action
            decision: AUTO, APPROVAL_REQUIRED, BLOCKED, etc.
            risk_score: Calculated risk score
            context: Action context
            approval_id: Approval request ID if applicable
            execution_result: Result if action was executed
            
        Returns:
            Audit entry ID
        """
        entry_id = str(uuid.uuid4())
        
        # Create audit entry
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now(),
            user_id=user_id,
            org_id=org_id,
            action_type=action_type,
            decision=decision,
            risk_score=risk_score,
            artifacts={
                "context": context.__dict__ if context else {},
                "approval_id": approval_id,
                "execution_result": execution_result,
                "decision_factors": self._extract_decision_factors(context, risk_score)
            },
            rollback_available=self._is_rollback_available(action_type, context)
        )
        
        # Store audit entry
        self._store_audit_entry(entry)
        
        logger.info(f"Audit log: {decision} for {action_type} by {user_id} (risk: {risk_score:.2f})")
        
        return entry_id
    
    def log_approval(
        self,
        approval_id: str,
        approver_id: str,
        decision: str,  # APPROVED, REJECTED
        comment: str,
        org_id: str
    ) -> str:
        """Log an approval decision"""
        entry_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now(),
            user_id=approver_id,
            org_id=org_id,
            action_type="approval_decision",
            decision=decision,
            risk_score=0.0,  # Approval decisions don't have risk scores
            artifacts={
                "approval_id": approval_id,
                "comment": comment,
                "approver_role": self._get_user_role(approver_id, org_id)
            }
        )
        
        self._store_audit_entry(entry)
        
        logger.info(f"Approval audit: {decision} by {approver_id} for {approval_id}")
        
        return entry_id
    
    def log_execution(
        self,
        user_id: str,
        org_id: str,
        action_type: str,
        execution_result: str,
        artifacts: Optional[Dict[str, Any]] = None,
        rollback_id: Optional[str] = None
    ) -> str:
        """Log action execution"""
        entry_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now(),
            user_id=user_id,
            org_id=org_id,
            action_type=action_type,
            decision="EXECUTED",
            risk_score=0.0,
            execution_result=execution_result,
            artifacts=artifacts or {},
            rollback_available=rollback_id is not None
        )
        
        if rollback_id:
            entry.artifacts["rollback_id"] = rollback_id
        
        self._store_audit_entry(entry)
        
        logger.info(f"Execution audit: {action_type} by {user_id} -> {execution_result}")
        
        return entry_id
    
    def log_rollback(
        self,
        user_id: str,
        org_id: str,
        original_action_id: str,
        rollback_result: str,
        artifacts: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log a rollback operation"""
        entry_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now(),
            user_id=user_id,
            org_id=org_id,
            action_type="rollback",
            decision="EXECUTED",
            risk_score=0.0,
            execution_result=rollback_result,
            artifacts={
                "original_action_id": original_action_id,
                **(artifacts or {})
            }
        )
        
        self._store_audit_entry(entry)
        
        logger.info(f"Rollback audit: {original_action_id} by {user_id} -> {rollback_result}")
        
        return entry_id
    
    def log_policy_change(
        self,
        user_id: str,
        org_id: str,
        policy_type: str,
        changes: Dict[str, Any],
        target_user_id: Optional[str] = None
    ) -> str:
        """Log policy configuration changes"""
        entry_id = str(uuid.uuid4())
        
        entry = AuditEntry(
            id=entry_id,
            timestamp=datetime.now(),
            user_id=user_id,
            org_id=org_id,
            action_type="policy_change",
            decision="EXECUTED",
            risk_score=0.5,  # Policy changes are moderately risky
            artifacts={
                "policy_type": policy_type,
                "changes": changes,
                "target_user_id": target_user_id,
                "admin_role": self._get_user_role(user_id, org_id)
            }
        )
        
        self._store_audit_entry(entry)
        
        logger.info(f"Policy change audit: {policy_type} by {user_id}")
        
        return entry_id
    
    def get_audit_trail(
        self,
        org_id: str,
        user_id: Optional[str] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Retrieve audit trail with filters"""
        if not self.db:
            return []
        
        try:
            # Build query
            conditions = ["org_id = :org_id"]
            params: Dict[str, Any] = {"org_id": org_id}
            
            if user_id:
                conditions.append("user_id = :user_id")
                params["user_id"] = user_id
            
            if action_type:
                conditions.append("action_type = :action_type")
                params["action_type"] = action_type
            
            if start_date:
                conditions.append("timestamp >= :start_date")
                params["start_date"] = start_date
            
            if end_date:
                conditions.append("timestamp <= :end_date")
                params["end_date"] = end_date
            
            where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT * FROM governance_audit_log 
                {where_clause}
                ORDER BY timestamp DESC 
                LIMIT :limit
            """
            
            params["limit"] = limit
            
            results = self.db.execute(query, params).fetchall()
            
            return [self._audit_entry_from_db_row(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error retrieving audit trail: {e}")
            return []
    
    def get_risk_insights(
        self,
        org_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get risk insights for dashboard"""
        if not self.db:
            return {}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # High-risk actions
            high_risk_actions = self.db.execute(
                """
                SELECT action_type, COUNT(*) as count, AVG(risk_score) as avg_risk
                FROM governance_audit_log 
                WHERE org_id = :org_id AND timestamp >= :cutoff_date 
                  AND risk_score > 0.7
                GROUP BY action_type
                ORDER BY count DESC
                LIMIT 10
                """,
                {"org_id": org_id, "cutoff_date": cutoff_date}
            ).fetchall()
            
            # Approval patterns
            approval_stats = self.db.execute(
                """
                SELECT decision, COUNT(*) as count
                FROM governance_audit_log 
                WHERE org_id = :org_id AND timestamp >= :cutoff_date 
                  AND action_type = 'approval_decision'
                GROUP BY decision
                """,
                {"org_id": org_id, "cutoff_date": cutoff_date}
            ).fetchall()
            
            # User activity
            user_activity = self.db.execute(
                """
                SELECT user_id, COUNT(*) as actions, AVG(risk_score) as avg_risk
                FROM governance_audit_log 
                WHERE org_id = :org_id AND timestamp >= :cutoff_date 
                GROUP BY user_id
                ORDER BY actions DESC
                LIMIT 10
                """,
                {"org_id": org_id, "cutoff_date": cutoff_date}
            ).fetchall()
            
            return {
                "high_risk_actions": [dict(row) for row in high_risk_actions],
                "approval_stats": [dict(row) for row in approval_stats],
                "user_activity": [dict(row) for row in user_activity],
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Error getting risk insights: {e}")
            return {}
    
    def _store_audit_entry(self, entry: AuditEntry):
        """Store audit entry to database"""
        if not self.db:
            # Add to buffer for later storage
            self.buffer.append(entry)
            if len(self.buffer) >= self.buffer_size:
                self._flush_buffer()
            return
        
        try:
            self.db.execute(
                """
                INSERT INTO governance_audit_log (
                    id, timestamp, user_id, org_id, action_type, decision,
                    risk_score, execution_result, artifacts, rollback_available
                ) VALUES (
                    :id, :timestamp, :user_id, :org_id, :action_type, :decision,
                    :risk_score, :execution_result, :artifacts, :rollback_available
                )
                """,
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "user_id": entry.user_id,
                    "org_id": entry.org_id,
                    "action_type": entry.action_type,
                    "decision": entry.decision,
                    "risk_score": entry.risk_score,
                    "execution_result": entry.execution_result,
                    "artifacts": json.dumps(entry.artifacts),
                    "rollback_available": entry.rollback_available
                }
            )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error storing audit entry: {e}")
    
    def _extract_decision_factors(self, context: ActionContext, risk_score: float) -> Dict[str, Any]:
        """Extract key decision factors for audit trail"""
        factors = {
            "risk_score": risk_score,
            "action_scope": len(context.target_files) if context and context.target_files else 0,
        }
        
        if context:
            factors.update({
                "touches_auth": context.touches_auth,
                "touches_prod": context.touches_prod,
                "is_multi_repo": context.is_multi_repo,
                "has_recent_incidents": context.has_recent_incidents,
                "estimated_impact": context.estimated_impact,
                "repo": context.repo,
                "branch": context.branch
            })
        
        return factors
    
    def _is_rollback_available(self, action_type: str, context: ActionContext) -> bool:
        """Check if action supports rollback"""
        rollback_supported_actions = [
            'code_edit', 'config_change', 'feature_flag', 'deploy_staging'
        ]
        
        rollback_not_supported = [
            'data_deletion', 'schema_migration', 'user_account_deletion'
        ]
        
        if action_type in rollback_not_supported:
            return False
        
        if action_type in rollback_supported_actions:
            return True
        
        # Default: assume rollback is available unless proven otherwise
        return True
    
    def _get_user_role(self, user_id: str, org_id: str) -> str:
        """Get user's role for audit context"""
        if not self.db:
            return "unknown"
        
        try:
            result = self.db.execute(
                "SELECT role FROM org_user WHERE user_id = :user_id AND org_id = :org_id",
                {"user_id": user_id, "org_id": org_id}
            ).fetchone()
            
            return result[0] if result else "unknown"
            
        except Exception:
            return "unknown"
    
    def _audit_entry_from_db_row(self, row) -> AuditEntry:
        """Convert database row to AuditEntry"""
        return AuditEntry(
            id=row['id'],
            timestamp=row['timestamp'],
            user_id=row['user_id'],
            org_id=row['org_id'],
            action_type=row['action_type'],
            decision=row['decision'],
            risk_score=row['risk_score'],
            artifacts=json.loads(row['artifacts']) if row['artifacts'] else {},
            execution_result=row['execution_result'],
            rollback_available=row['rollback_available']
        )
    
    def _flush_buffer(self):
        """Flush buffered entries to storage"""
        if not self.buffer:
            return
        
        logger.info(f"Flushing {len(self.buffer)} audit entries to storage")
        
        for entry in self.buffer:
            self._store_audit_entry(entry)
        
        self.buffer.clear()
    
    def flush(self):
        """Manually flush buffer"""
        self._flush_buffer()
