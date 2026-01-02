"""
RiskScorer — Explainable Risk Assessment

Provides transparent, explainable risk scoring for actions.
Risk factors are weighted and combined to produce a final risk score (0.0 - 1.0).
"""

from typing import List, Tuple
from . import ActionContext, ActionRisk
import logging

logger = logging.getLogger(__name__)


class RiskScorer:
    """
    Calculates risk scores for actions based on multiple factors.
    Always provides clear explanations for risk assessment.
    """
    
    # Risk factor weights (must sum to <= 1.0)
    RISK_WEIGHTS = {
        'auth_impact': 0.4,        # Touches authentication/authorization
        'prod_impact': 0.3,        # Affects production systems
        'multi_repo': 0.15,        # Spans multiple repositories
        'recent_incidents': 0.15,   # Area has recent incidents
        'file_sensitivity': 0.2,   # Modifies sensitive files
        'scope_impact': 0.1,       # Breadth of change
        'rollback_difficulty': 0.1, # How hard to undo
        'compliance_risk': 0.3,    # Regulatory/compliance impact
    }
    
    def __init__(self):
        self.sensitive_file_patterns = [
            # Authentication & Security
            '**/auth/**', '**/security/**', '**/*auth*', '**/*security*',
            '**/middleware/auth*', '**/guards/**', '**/permissions/**',
            
            # Configuration & Infrastructure
            '**/config/**', '**/.env*', '**/secrets/**', '**/credentials/**',
            '**/docker*', '**/k8s/**', '**/terraform/**', '**/cloudformation/**',
            
            # Database & Schema
            '**/migrations/**', '**/schema/**', '**/*migration*',
            '**/models/**', '**/entities/**',
            
            # CI/CD & Deployment
            '**/.github/**', '**/.gitlab-ci*', '**/jenkins*', '**/pipeline*',
            '**/deploy*', '**/build*',
            
            # Financial & Compliance
            '**/billing/**', '**/payment/**', '**/finance/**',
            '**/compliance/**', '**/audit/**'
        ]
        
        self.high_risk_actions = [
            'schema_change', 'deploy_prod', 'auth_config', 'security_policy',
            'user_permissions', 'infrastructure_change', 'database_migration'
        ]
        
        self.incident_keywords = [
            'outage', 'incident', 'failure', 'security', 'breach', 'vulnerability',
            'rollback', 'hotfix', 'emergency', 'critical'
        ]
    
    def calculate_risk(self, action_type: str, context: ActionContext) -> Tuple[float, List[str]]:
        """
        Calculate risk score and provide explanations.
        
        Args:
            action_type: Type of action being performed
            context: Detailed context about the action
            
        Returns:
            Tuple of (risk_score, list_of_reasons)
        """
        risk_factors = {}
        reasons = []
        
        # Authentication/Authorization Impact
        if context.touches_auth or self._affects_auth_system(action_type, context):
            risk_factors['auth_impact'] = 1.0
            reasons.append("Affects authentication or authorization systems")
        
        # Production Impact
        if context.touches_prod or self._affects_production(action_type, context):
            risk_factors['prod_impact'] = 1.0
            reasons.append("Affects production environment")
        
        # Multi-repository Impact
        if context.is_multi_repo:
            risk_factors['multi_repo'] = 1.0
            reasons.append("Spans multiple repositories")
        
        # Recent Incidents
        if context.has_recent_incidents:
            risk_factors['recent_incidents'] = 1.0
            reasons.append("Area has recent incidents or failures")
        
        # File Sensitivity
        sensitivity_score = self._assess_file_sensitivity(context.target_files or [])
        if sensitivity_score > 0:
            risk_factors['file_sensitivity'] = sensitivity_score
            if sensitivity_score > 0.5:
                reasons.append("Modifies sensitive files (config, auth, infrastructure)")
            else:
                reasons.append("Modifies moderately sensitive files")
        
        # Scope Impact
        scope_score = self._assess_scope_impact(action_type, context)
        if scope_score > 0.3:
            risk_factors['scope_impact'] = scope_score
            reasons.append(f"Broad scope change ({action_type})")
        
        # Rollback Difficulty
        rollback_score = self._assess_rollback_difficulty(action_type, context)
        if rollback_score > 0.4:
            risk_factors['rollback_difficulty'] = rollback_score
            reasons.append("Difficult to rollback if issues occur")
        
        # Compliance Risk
        compliance_score = self._assess_compliance_risk(action_type, context)
        if compliance_score > 0.3:
            risk_factors['compliance_risk'] = compliance_score
            reasons.append("May impact regulatory compliance")
        
        # Calculate weighted risk score
        total_risk = 0.0
        for factor, value in risk_factors.items():
            weight = self.RISK_WEIGHTS.get(factor, 0.0)
            total_risk += value * weight
        
        # Ensure risk is between 0.0 and 1.0
        final_risk = min(total_risk, 1.0)
        
        # Add risk level to reasons
        if final_risk >= 0.7:
            reasons.insert(0, f"HIGH RISK ({final_risk:.2f})")
        elif final_risk >= 0.3:
            reasons.insert(0, f"MEDIUM RISK ({final_risk:.2f})")
        else:
            reasons.insert(0, f"LOW RISK ({final_risk:.2f})")
        
        return final_risk, reasons
    
    def _affects_auth_system(self, action_type: str, context: ActionContext) -> bool:
        """Check if action affects authentication systems"""
        auth_actions = ['auth_config', 'user_permissions', 'security_policy', 'oauth_config']
        
        if action_type in auth_actions:
            return True
        
        if context.target_files:
            return any(
                any(pattern in file.lower() for pattern in ['auth', 'security', 'permission', 'role'])
                for file in context.target_files
            )
        
        return False
    
    def _affects_production(self, action_type: str, context: ActionContext) -> bool:
        """Check if action affects production environment"""
        prod_actions = ['deploy_prod', 'schema_change', 'infrastructure_change']
        
        if action_type in prod_actions:
            return True
        
        if context.branch and context.branch.lower() in ['main', 'master', 'production', 'prod']:
            return True
        
        if context.repo and any(keyword in context.repo.lower() for keyword in ['prod', 'production']):
            return True
        
        return False
    
    def _assess_file_sensitivity(self, files: List[str]) -> float:
        """Assess sensitivity of files being modified"""
        if not files:
            return 0.0
        
        sensitive_count = 0
        total_files = len(files)
        
        for file in files:
            file_lower = file.lower()
            
            # High sensitivity patterns
            high_sensitivity = [
                'config', 'secret', 'credential', 'password', 'key', 'token',
                'auth', 'security', 'permission', 'role', 'policy',
                'migration', 'schema', 'deploy', 'infrastructure'
            ]
            
            if any(pattern in file_lower for pattern in high_sensitivity):
                sensitive_count += 1
        
        return min(sensitive_count / total_files, 1.0)
    
    def _assess_scope_impact(self, action_type: str, context: ActionContext) -> float:
        """Assess the scope/breadth of the change"""
        scope_score = 0.0
        
        # Action type impact
        high_scope_actions = [
            'infrastructure_change', 'schema_change', 'global_config',
            'multi_repo_change', 'system_wide_refactor'
        ]
        
        if action_type in high_scope_actions:
            scope_score += 0.5
        
        # File count impact
        if context.target_files:
            file_count = len(context.target_files)
            if file_count > 20:
                scope_score += 0.4
            elif file_count > 10:
                scope_score += 0.3
            elif file_count > 5:
                scope_score += 0.2
        
        # Multi-repo impact
        if context.is_multi_repo:
            scope_score += 0.3
        
        return min(scope_score, 1.0)
    
    def _assess_rollback_difficulty(self, action_type: str, context: ActionContext) -> float:
        """Assess how difficult it would be to rollback the change"""
        rollback_score = 0.0
        
        # Actions that are hard to rollback
        hard_rollback_actions = [
            'database_migration', 'data_deletion', 'schema_change',
            'infrastructure_destroy', 'user_data_modification'
        ]
        
        if action_type in hard_rollback_actions:
            rollback_score += 0.6
        
        # Database changes are hard to rollback
        if context.target_files:
            db_patterns = ['migration', 'schema', 'model', 'entity']
            if any(pattern in ' '.join(context.target_files).lower() for pattern in db_patterns):
                rollback_score += 0.4
        
        # Production changes harder to rollback
        if context.touches_prod:
            rollback_score += 0.2
        
        return min(rollback_score, 1.0)
    
    def _assess_compliance_risk(self, action_type: str, context: ActionContext) -> float:
        """Assess regulatory/compliance risk"""
        compliance_score = 0.0
        
        # High compliance risk actions
        compliance_actions = [
            'user_data_access', 'data_export', 'audit_log_change',
            'security_policy', 'privacy_config', 'data_retention'
        ]
        
        if action_type in compliance_actions:
            compliance_score += 0.5
        
        # File patterns that indicate compliance risk
        if context.target_files:
            compliance_patterns = [
                'audit', 'compliance', 'privacy', 'gdpr', 'hipaa', 'pci',
                'user_data', 'personal', 'sensitive'
            ]
            
            if any(
                pattern in ' '.join(context.target_files).lower() 
                for pattern in compliance_patterns
            ):
                compliance_score += 0.3
        
        return min(compliance_score, 1.0)
    
    def get_risk_level(self, risk_score: float) -> ActionRisk:
        """Convert risk score to risk level enum"""
        if risk_score >= 0.7:
            return ActionRisk.HIGH
        elif risk_score >= 0.3:
            return ActionRisk.MEDIUM
        else:
            return ActionRisk.LOW