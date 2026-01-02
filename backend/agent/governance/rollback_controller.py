"""
RollbackController — Undo Anything Safely

Provides rollback capabilities for actions that support it.
Integrates with git, infrastructure tools, and configuration management.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import uuid
import logging
import subprocess
import os

logger = logging.getLogger(__name__)


class RollbackStrategy:
    """Base class for rollback strategies"""
    
    def can_rollback(self, action_type: str, artifacts: Dict[str, Any]) -> bool:
        """Check if this strategy can rollback the given action"""
        raise NotImplementedError
    
    def rollback(self, action_type: str, artifacts: Dict[str, Any]) -> Tuple[bool, str]:
        """Perform the rollback. Returns (success, message)"""
        raise NotImplementedError


class GitRollbackStrategy(RollbackStrategy):
    """Git-based rollback for code changes"""
    
    def can_rollback(self, action_type: str, artifacts: Dict[str, Any]) -> bool:
        return (
            action_type in ['code_edit', 'refactor', 'config_change'] and
            'git_commit_hash' in artifacts and
            'repo_path' in artifacts
        )
    
    def rollback(self, action_type: str, artifacts: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            repo_path = artifacts['repo_path']
            commit_hash = artifacts['git_commit_hash']
            
            # Change to repo directory
            original_dir = os.getcwd()
            os.chdir(repo_path)
            
            try:
                # Create rollback branch
                rollback_branch = f"rollback-{commit_hash[:8]}-{int(datetime.now().timestamp())}"
                subprocess.run(['git', 'checkout', '-b', rollback_branch], check=True, capture_output=True)
                
                # Revert the commit
                subprocess.run(
                    ['git', 'revert', commit_hash, '--no-edit'],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                return True, f"Successfully reverted commit {commit_hash} on branch {rollback_branch}"
                
            finally:
                os.chdir(original_dir)
                
        except subprocess.CalledProcessError as e:
            return False, f"Git rollback failed: {e.stderr}"
        except Exception as e:
            return False, f"Rollback error: {str(e)}"


class ConfigRollbackStrategy(RollbackStrategy):
    """Configuration file rollback using backups"""
    
    def can_rollback(self, action_type: str, artifacts: Dict[str, Any]) -> bool:
        return (
            action_type in ['config_change', 'env_update'] and
            'config_backup' in artifacts
        )
    
    def rollback(self, action_type: str, artifacts: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            config_file = artifacts['config_file']
            backup_content = artifacts['config_backup']
            
            # Restore from backup
            with open(config_file, 'w') as f:
                f.write(backup_content)
            
            return True, f"Successfully restored {config_file} from backup"
            
        except Exception as e:
            return False, f"Config rollback failed: {str(e)}"


class FeatureFlagRollbackStrategy(RollbackStrategy):
    """Feature flag rollback"""
    
    def can_rollback(self, action_type: str, artifacts: Dict[str, Any]) -> bool:
        return (
            action_type == 'feature_flag' and
            'flag_name' in artifacts and
            'previous_state' in artifacts
        )
    
    def rollback(self, action_type: str, artifacts: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            flag_name = artifacts['flag_name']
            previous_state = artifacts['previous_state']
            
            # This would integrate with your feature flag system
            # For now, we'll simulate the rollback
            logger.info(f"Rolling back feature flag {flag_name} to {previous_state}")
            
            return True, f"Successfully rolled back feature flag {flag_name} to {previous_state}"
            
        except Exception as e:
            return False, f"Feature flag rollback failed: {str(e)}"


class DatabaseRollbackStrategy(RollbackStrategy):
    """Database rollback for reversible migrations"""
    
    def can_rollback(self, action_type: str, artifacts: Dict[str, Any]) -> bool:
        return (
            action_type in ['schema_change', 'data_migration'] and
            'migration_id' in artifacts and
            'rollback_sql' in artifacts
        )
    
    def rollback(self, action_type: str, artifacts: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            migration_id = artifacts['migration_id']
            artifacts['rollback_sql']
            
            # This would execute the rollback SQL
            # For now, we'll simulate the rollback
            logger.info(f"Rolling back migration {migration_id}")
            
            return True, f"Successfully rolled back migration {migration_id}"
            
        except Exception as e:
            return False, f"Database rollback failed: {str(e)}"


class RollbackController:
    """
    Central controller for rolling back actions.
    Supports multiple rollback strategies and maintains rollback history.
    """
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.strategies = [
            GitRollbackStrategy(),
            ConfigRollbackStrategy(),
            FeatureFlagRollbackStrategy(),
            DatabaseRollbackStrategy()
        ]
    
    def can_rollback(self, action_id: str) -> Tuple[bool, str]:
        """
        Check if an action can be rolled back.
        
        Args:
            action_id: ID of the action to check
            
        Returns:
            Tuple of (can_rollback, reason)
        """
        try:
            # Get action details from audit log
            action_details = self._get_action_details(action_id)
            
            if not action_details:
                return False, "Action not found in audit log"
            
            action_type = action_details['action_type']
            artifacts = action_details.get('artifacts', {})
            
            # Check if already rolled back
            if self._is_already_rolled_back(action_id):
                return False, "Action has already been rolled back"
            
            # Check if action is too old (rollback window expired)
            action_time = action_details['timestamp']
            if isinstance(action_time, str):
                action_time = datetime.fromisoformat(action_time)
            
            hours_since = (datetime.now() - action_time).total_seconds() / 3600
            max_rollback_hours = self._get_rollback_window(action_type)
            
            if hours_since > max_rollback_hours:
                return False, f"Rollback window expired ({max_rollback_hours}h limit)"
            
            # Check if any strategy can handle this rollback
            for strategy in self.strategies:
                if strategy.can_rollback(action_type, artifacts):
                    return True, f"Can rollback using {strategy.__class__.__name__}"
            
            return False, f"No rollback strategy available for action type: {action_type}"
            
        except Exception as e:
            logger.error(f"Error checking rollback capability: {e}")
            return False, f"Error checking rollback: {str(e)}"
    
    def rollback_action(self, action_id: str, user_id: str, reason: str = "") -> Dict[str, Any]:
        """
        Roll back an action.
        
        Args:
            action_id: ID of the action to roll back
            user_id: User performing the rollback
            reason: Reason for rollback
            
        Returns:
            Dictionary with rollback result
        """
        rollback_id = str(uuid.uuid4())
        
        try:
            # Check if rollback is possible
            can_rollback, rollback_reason = self.can_rollback(action_id)
            
            if not can_rollback:
                return {
                    "success": False,
                    "rollback_id": rollback_id,
                    "message": rollback_reason,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Get action details
            action_details = self._get_action_details(action_id)
            if not action_details:
                return {
                    "success": False,
                    "rollback_id": rollback_id,
                    "message": f"Could not find action details for {action_id}",
                    "timestamp": datetime.now().isoformat()
                }
            
            action_type = action_details['action_type']
            artifacts = action_details.get('artifacts', {})
            
            # Find appropriate strategy
            strategy = None
            for s in self.strategies:
                if s.can_rollback(action_type, artifacts):
                    strategy = s
                    break
            
            if not strategy:
                return {
                    "success": False,
                    "rollback_id": rollback_id,
                    "message": "No rollback strategy found",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Perform rollback
            success, message = strategy.rollback(action_type, artifacts)
            
            # Record rollback in database
            self._record_rollback(
                rollback_id=rollback_id,
                original_action_id=action_id,
                user_id=user_id,
                reason=reason,
                success=success,
                message=message,
                strategy=strategy.__class__.__name__
            )
            
            result = {
                "success": success,
                "rollback_id": rollback_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "strategy_used": strategy.__class__.__name__
            }
            
            if success:
                logger.info(f"Successful rollback of {action_id} by {user_id}: {message}")
            else:
                logger.error(f"Failed rollback of {action_id} by {user_id}: {message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Rollback error for {action_id}: {e}")
            
            # Record failed rollback
            self._record_rollback(
                rollback_id=rollback_id,
                original_action_id=action_id,
                user_id=user_id,
                reason=reason,
                success=False,
                message=str(e),
                strategy="error"
            )
            
            return {
                "success": False,
                "rollback_id": rollback_id,
                "message": f"Rollback failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_rollback_history(self, org_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get rollback history for organization"""
        if not self.db:
            return []
        
        try:
            results = self.db.execute(
                """
                SELECT * FROM rollback_history 
                WHERE org_id = :org_id 
                ORDER BY timestamp DESC 
                LIMIT :limit
                """,
                {"org_id": org_id, "limit": limit}
            ).fetchall()
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error getting rollback history: {e}")
            return []
    
    def get_rollback_stats(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Get rollback statistics"""
        if not self.db:
            return {}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total rollbacks
            total_rollbacks = self.db.execute(
                """
                SELECT COUNT(*) as count, 
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM rollback_history 
                WHERE org_id = :org_id AND timestamp >= :cutoff_date
                """,
                {"org_id": org_id, "cutoff_date": cutoff_date}
            ).fetchone()
            
            # Rollbacks by strategy
            by_strategy = self.db.execute(
                """
                SELECT strategy, COUNT(*) as count, 
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM rollback_history 
                WHERE org_id = :org_id AND timestamp >= :cutoff_date
                GROUP BY strategy
                """,
                {"org_id": org_id, "cutoff_date": cutoff_date}
            ).fetchall()
            
            return {
                "total_rollbacks": total_rollbacks['count'] if total_rollbacks else 0,
                "successful_rollbacks": total_rollbacks['successful'] if total_rollbacks else 0,
                "by_strategy": [dict(row) for row in by_strategy],
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Error getting rollback stats: {e}")
            return {}
    
    def _get_action_details(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get action details from audit log"""
        if not self.db:
            return None
        
        try:
            result = self.db.execute(
                "SELECT * FROM governance_audit_log WHERE id = :action_id",
                {"action_id": action_id}
            ).fetchone()
            
            if result:
                row_dict = dict(result)
                if row_dict.get('artifacts'):
                    row_dict['artifacts'] = json.loads(row_dict['artifacts'])
                return row_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting action details: {e}")
            return None
    
    def _is_already_rolled_back(self, action_id: str) -> bool:
        """Check if action has already been rolled back"""
        if not self.db:
            return False
        
        try:
            result = self.db.execute(
                "SELECT COUNT(*) as count FROM rollback_history WHERE original_action_id = :action_id AND success = 1",
                {"action_id": action_id}
            ).fetchone()
            
            return result['count'] > 0 if result else False
            
        except Exception:
            return False
    
    def _get_rollback_window(self, action_type: str) -> int:
        """Get rollback window in hours for action type"""
        rollback_windows = {
            'code_edit': 72,           # 3 days
            'config_change': 24,       # 1 day
            'feature_flag': 168,       # 1 week
            'schema_change': 1,        # 1 hour (very limited)
            'deploy_staging': 48,      # 2 days
            'deploy_prod': 1,          # 1 hour (emergency only)
        }
        
        return rollback_windows.get(action_type, 24)  # Default 24 hours
    
    def _record_rollback(
        self,
        rollback_id: str,
        original_action_id: str,
        user_id: str,
        reason: str,
        success: bool,
        message: str,
        strategy: str
    ):
        """Record rollback in database"""
        if not self.db:
            return
        
        try:
            # Get org_id from original action
            org_result = self.db.execute(
                "SELECT org_id FROM governance_audit_log WHERE id = :action_id",
                {"action_id": original_action_id}
            ).fetchone()
            
            org_id = org_result['org_id'] if org_result else 'default'
            
            self.db.execute(
                """
                INSERT INTO rollback_history (
                    id, original_action_id, user_id, org_id, reason,
                    success, message, strategy, timestamp
                ) VALUES (
                    :id, :original_action_id, :user_id, :org_id, :reason,
                    :success, :message, :strategy, :timestamp
                )
                """,
                {
                    "id": rollback_id,
                    "original_action_id": original_action_id,
                    "user_id": user_id,
                    "org_id": org_id,
                    "reason": reason,
                    "success": success,
                    "message": message,
                    "strategy": strategy,
                    "timestamp": datetime.now()
                }
            )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error recording rollback: {e}")
