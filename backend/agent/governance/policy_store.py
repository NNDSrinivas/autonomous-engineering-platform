"""
AutonomyPolicyStore — Granular Policy Management

Manages per-user, per-repo autonomy policies and approval requests.
Integrates with existing org_policy system while adding user-level granularity.
"""

from typing import List, Optional
from datetime import datetime
import json
import logging

from . import AutonomyPolicy, ApprovalRequest, AutonomyLevel

logger = logging.getLogger(__name__)


class AutonomyPolicyStore:
    """
    Stores and manages autonomy policies for users and repositories.
    Provides granular control over what each user can do autonomously.
    """
    
    def __init__(self, db_session=None):
        self.db = db_session
        self._policy_cache = {}
        
        # Default policies by role (integrate with existing RBAC)
        self.default_policies = {
            'developer': AutonomyPolicy(
                user_id='',
                autonomy_level=AutonomyLevel.MINIMAL,
                max_auto_risk=0.2,
                blocked_actions=['deploy_prod', 'schema_change', 'infrastructure_change'],
                auto_allowed_actions=['lint_fix', 'test_fix', 'doc_update'],
                require_approval_for=['code_review', 'merge_pr', 'config_change']
            ),
            'senior_developer': AutonomyPolicy(
                user_id='',
                autonomy_level=AutonomyLevel.STANDARD,
                max_auto_risk=0.4,
                blocked_actions=['deploy_prod', 'schema_change'],
                auto_allowed_actions=['lint_fix', 'test_fix', 'doc_update', 'refactor', 'feature_flag'],
                require_approval_for=['infrastructure_change', 'security_config']
            ),
            'tech_lead': AutonomyPolicy(
                user_id='',
                autonomy_level=AutonomyLevel.ELEVATED,
                max_auto_risk=0.6,
                blocked_actions=['deploy_prod'],
                auto_allowed_actions=['lint_fix', 'test_fix', 'doc_update', 'refactor', 'feature_flag', 'config_change'],
                require_approval_for=['schema_change', 'infrastructure_change']
            ),
            'platform_team': AutonomyPolicy(
                user_id='',
                autonomy_level=AutonomyLevel.FULL,
                max_auto_risk=0.8,
                blocked_actions=[],
                auto_allowed_actions=['*'],  # All actions allowed
                require_approval_for=['deploy_prod']  # Only prod deployments need approval
            )
        }
    
    def get_policy(
        self,
        user_id: Optional[str],
        org_id: str = "default",
        repo: Optional[str] = None,
    ) -> Optional[AutonomyPolicy]:
        """
        Get autonomy policy for a user, with repo-specific overrides.
        
        Priority:
        1. User-specific repo policy
        2. User-specific global policy
        3. Role-based default policy
        4. System default (minimal autonomy)
        """
        user_id = user_id or "system"
        cache_key = f"{user_id}:{org_id}:{repo or 'global'}"
        
        # Check cache first
        if cache_key in self._policy_cache:
            return self._policy_cache[cache_key]
        
        policy = None
        
        try:
            # Try to get from database first
            if self.db:
                policy = self._get_policy_from_db(user_id, org_id, repo)
            
            if not policy:
                # Fall back to role-based default
                policy = self._get_default_policy_for_user(user_id, org_id)
            
            if not policy:
                # System default - minimal autonomy
                policy = AutonomyPolicy(
                    user_id=user_id,
                    org_id=org_id,
                    repo=repo,
                    autonomy_level=AutonomyLevel.MINIMAL,
                    max_auto_risk=0.1,
                    blocked_actions=['deploy_prod', 'schema_change', 'infrastructure_change', 'security_config'],
                    auto_allowed_actions=['lint_fix'],
                    require_approval_for=['code_edit', 'config_change']
                )
            
            # Cache the result
            self._policy_cache[cache_key] = policy
            return policy
            
        except Exception as e:
            logger.error(f"Error getting policy for user {user_id}: {e}")
            # Return restrictive default on error
            return AutonomyPolicy(
                user_id=user_id,
                org_id=org_id,
                autonomy_level=AutonomyLevel.MINIMAL,
                max_auto_risk=0.1,
                require_approval_for=['*']
            )
    
    def _get_policy_from_db(
        self, 
        user_id: str, 
        org_id: str, 
        repo: Optional[str] = None
    ) -> Optional[AutonomyPolicy]:
        """Get policy from database"""
        if not self.db:
            return None
        
        try:
            # First try repo-specific policy
            if repo:
                result = self.db.execute(
                    """
                    SELECT * FROM autonomy_policy 
                    WHERE user_id = :user_id AND org_id = :org_id AND repo = :repo
                    """,
                    {"user_id": user_id, "org_id": org_id, "repo": repo}
                ).fetchone()
                
                if result:
                    return self._policy_from_db_row(result)
            
            # Try global user policy
            result = self.db.execute(
                """
                SELECT * FROM autonomy_policy 
                WHERE user_id = :user_id AND org_id = :org_id AND repo IS NULL
                """,
                {"user_id": user_id, "org_id": org_id}
            ).fetchone()
            
            if result:
                return self._policy_from_db_row(result)
            
            return None
            
        except Exception as e:
            logger.error(f"Database error getting policy: {e}")
            return None
    
    def _get_default_policy_for_user(self, user_id: str, org_id: str) -> Optional[AutonomyPolicy]:
        """Get default policy based on user's role"""
        try:
            if not self.db:
                return None
            
            # Get user role from org_user table
            result = self.db.execute(
                """
                SELECT role FROM org_user 
                WHERE user_id = :user_id AND org_id = :org_id
                """,
                {"user_id": user_id, "org_id": org_id}
            ).fetchone()
            
            if not result:
                return None
            
            role = result[0]
            
            # Map roles to default policies
            role_mapping = {
                'developer': 'developer',
                'senior_developer': 'senior_developer',
                'tech_lead': 'tech_lead',
                'maintainer': 'tech_lead',
                'admin': 'platform_team'
            }
            
            policy_key = role_mapping.get(role, 'developer')
            default_policy = self.default_policies.get(policy_key)
            
            if default_policy:
                # Create a copy with the correct user_id
                return AutonomyPolicy(
                    user_id=user_id,
                    org_id=org_id,
                    autonomy_level=default_policy.autonomy_level,
                    max_auto_risk=default_policy.max_auto_risk,
                    blocked_actions=default_policy.blocked_actions.copy() if default_policy.blocked_actions else [],
                    auto_allowed_actions=default_policy.auto_allowed_actions.copy() if default_policy.auto_allowed_actions else [],
                    require_approval_for=default_policy.require_approval_for.copy() if default_policy.require_approval_for else []
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting default policy for user {user_id}: {e}")
            return None
    
    def save_policy(self, policy: AutonomyPolicy) -> bool:
        """Save or update a user's autonomy policy"""
        try:
            if not self.db:
                logger.warning("No database connection - cannot save policy")
                return False
            
            # Insert or update policy
            self.db.execute(
                """
                INSERT OR REPLACE INTO autonomy_policy (
                    user_id, org_id, repo, autonomy_level, max_auto_risk,
                    blocked_actions, auto_allowed_actions, require_approval_for,
                    created_at, updated_at
                ) VALUES (
                    :user_id, :org_id, :repo, :autonomy_level, :max_auto_risk,
                    :blocked_actions, :auto_allowed_actions, :require_approval_for,
                    :created_at, :updated_at
                )
                """,
                {
                    "user_id": policy.user_id,
                    "org_id": policy.org_id,
                    "repo": policy.repo,
                    "autonomy_level": policy.autonomy_level.value,
                    "max_auto_risk": policy.max_auto_risk,
                    "blocked_actions": json.dumps(policy.blocked_actions or []),
                    "auto_allowed_actions": json.dumps(policy.auto_allowed_actions or []),
                    "require_approval_for": json.dumps(policy.require_approval_for or []),
                    "created_at": policy.created_at or datetime.now(),
                    "updated_at": datetime.now()
                }
            )
            
            self.db.commit()
            
            # Clear cache for this policy
            cache_keys_to_remove = [
                key for key in self._policy_cache.keys()
                if key.startswith(f"{policy.user_id}:{policy.org_id}")
            ]
            
            for key in cache_keys_to_remove:
                del self._policy_cache[key]
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving policy: {e}")
            return False
    
    def store_approval_request(self, request: ApprovalRequest) -> bool:
        """Store a new approval request"""
        try:
            if not self.db:
                return False
            
            self.db.execute(
                """
                INSERT INTO approval_request (
                    id, action_type, requester_id, org_id, repo, risk_score,
                    risk_reasons, plan_summary, context_data, status,
                    created_at, expires_at
                ) VALUES (
                    :id, :action_type, :requester_id, :org_id, :repo, :risk_score,
                    :risk_reasons, :plan_summary, :context_data, :status,
                    :created_at, :expires_at
                )
                """,
                {
                    "id": request.id,
                    "action_type": request.action_type,
                    "requester_id": request.requester_id,
                    "org_id": request.org_id,
                    "repo": request.context.repo,
                    "risk_score": request.risk_score,
                    "risk_reasons": json.dumps(request.risk_reasons),
                    "plan_summary": request.plan_summary,
                    "context_data": json.dumps(request.context.__dict__),
                    "status": "pending",
                    "created_at": request.created_at,
                    "expires_at": request.expires_at
                }
            )
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing approval request: {e}")
            return False
    
    def update_approval_status(
        self, 
        approval_id: str, 
        status: str, 
        approver_id: Optional[str] = None, 
        comment: str = ""
    ) -> bool:
        """Update approval request status"""
        try:
            if not self.db:
                return False
            
            self.db.execute(
                """
                UPDATE approval_request 
                SET status = :status, approver_id = :approver_id, 
                    approver_comment = :comment, updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    "id": approval_id,
                    "status": status,
                    "approver_id": approver_id,
                    "comment": comment,
                    "updated_at": datetime.now()
                }
            )
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating approval status: {e}")
            return False
    
    def _policy_from_db_row(self, row) -> AutonomyPolicy:
        """Convert database row to AutonomyPolicy"""
        return AutonomyPolicy(
            user_id=row['user_id'],
            org_id=row['org_id'],
            repo=row['repo'],
            autonomy_level=AutonomyLevel(row['autonomy_level']),
            max_auto_risk=row['max_auto_risk'],
            blocked_actions=json.loads(row['blocked_actions']) if row['blocked_actions'] else [],
            auto_allowed_actions=json.loads(row['auto_allowed_actions']) if row['auto_allowed_actions'] else [],
            require_approval_for=json.loads(row['require_approval_for']) if row['require_approval_for'] else [],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def clear_cache(self):
        """Clear policy cache"""
        self._policy_cache.clear()
    
    def get_all_policies_for_org(self, org_id: str) -> List[AutonomyPolicy]:
        """Get all policies for an organization"""
        if not self.db:
            return []
        
        try:
            results = self.db.execute(
                """
                SELECT * FROM autonomy_policy 
                WHERE org_id = :org_id
                ORDER BY user_id, repo
                """,
                {"org_id": org_id}
            ).fetchall()
            
            return [self._policy_from_db_row(row) for row in results]
            
        except Exception as e:
            logger.error(f"Error getting all policies for org {org_id}: {e}")
            return []
