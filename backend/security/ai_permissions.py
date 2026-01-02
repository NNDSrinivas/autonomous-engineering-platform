"""
Security-First AI Execution Model

This system implements a comprehensive security framework for AI operations
with read-only by default, diff preview requirements, role-based permissions,
sandbox execution, dry-run mode, canary rollout, and automatic rollback.

Key security principles:
- Read-only by default (zero trust)
- Explicit approval for all write operations
- Role-based access control with fine-grained permissions
- Sandbox execution with resource limits
- Mandatory diff preview and human approval
- Comprehensive audit logging
- Automatic rollback on security violations
- Multi-layer security validation
"""

import asyncio
import tempfile
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..memory.memory_layer import MemoryLayer
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.memory.memory_layer import MemoryLayer
    from backend.core.config import get_settings


class SecurityLevel(Enum):
    """Security levels for operations."""
    UNRESTRICTED = "unrestricted"  # Full access
    RESTRICTED = "restricted"      # Limited access with monitoring
    SANDBOXED = "sandboxed"        # Isolated execution environment
    READ_ONLY = "read_only"        # No write permissions
    BLOCKED = "blocked"            # No access allowed


class ExecutionMode(Enum):
    """Execution modes for AI operations."""
    DRY_RUN = "dry_run"           # Simulate execution without changes
    PREVIEW = "preview"           # Generate diff for review
    APPROVED = "approved"         # Execute with prior approval
    AUTONOMOUS = "autonomous"     # Execute without human intervention
    EMERGENCY = "emergency"       # Emergency execution with relaxed rules


class RiskLevel(Enum):
    """Risk levels for operations."""
    CRITICAL = "critical"         # Could cause system failure
    HIGH = "high"               # Significant impact
    MEDIUM = "medium"           # Moderate impact
    LOW = "low"                 # Minimal impact
    NEGLIGIBLE = "negligible"   # No significant impact


class ValidationResult(Enum):
    """Results of security validation."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


@dataclass
class SecurityContext:
    """Security context for an operation."""
    user_id: str
    session_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    environment: str  # dev, staging, prod
    request_source: str  # api, ui, cli, autonomous
    timestamp: datetime
    

@dataclass
class OperationRequest:
    """Request for AI operation execution."""
    operation_id: str
    operation_type: str
    description: str
    target_resources: List[str]
    proposed_changes: Dict[str, Any]
    security_context: SecurityContext
    execution_mode: ExecutionMode
    override_permissions: List[str] = field(default_factory=list)
    

@dataclass
class SecurityValidation:
    """Result of security validation."""
    validation_id: str
    operation_id: str
    result: ValidationResult
    risk_level: RiskLevel
    security_violations: List[str]
    required_permissions: List[str]
    approval_required: bool
    sandbox_required: bool
    max_execution_time: int  # seconds
    resource_limits: Dict[str, Any]
    validation_details: Dict[str, Any]
    

@dataclass
class ExecutionEnvironment:
    """Isolated execution environment."""
    env_id: str
    container_id: Optional[str]
    temp_directory: str
    resource_limits: Dict[str, Any]
    network_isolation: bool
    file_system_isolation: bool
    created_at: datetime
    cleanup_at: Optional[datetime]
    

@dataclass
class DiffPreview:
    """Preview of proposed changes."""
    preview_id: str
    operation_id: str
    file_changes: List[Dict[str, Any]]
    config_changes: List[Dict[str, Any]]
    dependency_changes: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    rollback_plan: Dict[str, Any]
    estimated_impact: Dict[str, Any]
    requires_approval: bool
    generated_at: datetime


class AIPermissionPolicy:
    """
    Comprehensive permission policy system for AI operations.
    
    Implements fine-grained permissions with role-based access control,
    environment-specific rules, and dynamic security assessment.
    """
    
    def __init__(self):
        """Initialize the AI Permission Policy system."""
        self.role_permissions = self._initialize_role_permissions()
        self.environment_restrictions = self._initialize_environment_restrictions()
        self.operation_risk_matrix = self._initialize_risk_matrix()
        
    def can_read_code(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can read code."""
        base_permission = "READ_CODE" in self.role_permissions.get(user_role, set())
        env_restriction = self.environment_restrictions.get(environment, {}).get("read_code", True)
        return base_permission and env_restriction
    
    def can_write_code(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can write code."""
        base_permission = "WRITE_CODE" in self.role_permissions.get(user_role, set())
        env_restriction = self.environment_restrictions.get(environment, {}).get("write_code", False)
        return base_permission and env_restriction
    
    def can_apply_patch(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can apply patches."""
        return user_role in ["senior_developer", "tech_lead", "architect", "admin"]
    
    def can_migrate_framework(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can perform framework migrations."""
        return user_role in ["architect", "admin"] and environment != "production"
    
    def can_run_autonomous(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can run autonomous operations."""
        return user_role in ["admin"] and environment == "dev"
    
    def can_deploy_changes(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can deploy changes."""
        deploy_roles = {
            "dev": ["developer", "senior_developer", "tech_lead", "architect", "devops_engineer", "admin"],
            "staging": ["senior_developer", "tech_lead", "architect", "devops_engineer", "admin"],
            "production": ["devops_engineer", "admin"]
        }
        return user_role in deploy_roles.get(environment, [])
    
    def can_rollback_changes(self, user_role: str, environment: str = "dev") -> bool:
        """Check if user can rollback changes."""
        # Rollback permissions are more permissive in emergency situations
        rollback_roles = {
            "dev": ["developer", "senior_developer", "tech_lead", "architect", "devops_engineer", "admin"],
            "staging": ["tech_lead", "architect", "devops_engineer", "admin"],
            "production": ["devops_engineer", "admin"]
        }
        return user_role in rollback_roles.get(environment, [])
    
    def get_required_approvers(self, operation_type: str, environment: str, risk_level: RiskLevel) -> List[str]:
        """Get required approvers for an operation."""
        if environment == "production":
            if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                return ["devops_engineer", "admin"]  # Requires both
            elif risk_level == RiskLevel.MEDIUM:
                return ["devops_engineer"]  # Either role
        
        if risk_level == RiskLevel.CRITICAL:
            return ["admin"]
        
        return []  # No approval required
    
    def _initialize_role_permissions(self) -> Dict[str, Set[str]]:
        """Initialize role-based permissions."""
        return {
            "developer": {
                "READ_CODE", "WRITE_CODE",
                "READ_DATA", "VIEW_AI_DECISIONS"
            },
            "senior_developer": {
                "READ_CODE", "WRITE_CODE", "REVIEW_CODE",
                "READ_DATA", "WRITE_DATA", "VIEW_AI_DECISIONS"
            },
            "tech_lead": {
                "READ_CODE", "WRITE_CODE", "REVIEW_CODE",
                "APPROVE_CODE", "READ_DATA", "WRITE_DATA",
                "VIEW_AI_DECISIONS", "CONFIGURE_AI"
            },
            "architect": {
                "READ_CODE", "WRITE_CODE", "REVIEW_CODE",
                "APPROVE_CODE", "CONFIGURE_SYSTEM",
                "EXECUTE_MIGRATIONS", "VIEW_AI_DECISIONS", "CONFIGURE_AI"
            },
            "devops_engineer": {
                "READ_CODE", "DEPLOY_CHANGES", "ROLLBACK_CHANGES",
                "CONFIGURE_SYSTEM", "VIEW_AUDIT_LOGS"
            },
            "admin": {
                "READ_CODE", "WRITE_CODE", "DELETE_CODE", "REVIEW_CODE", "APPROVE_CODE",
                "EXECUTE_MIGRATIONS", "DEPLOY_CHANGES", "ROLLBACK_CHANGES", "CONFIGURE_SYSTEM",
                "READ_DATA", "WRITE_DATA", "EXPORT_DATA", "DELETE_DATA",
                "MANAGE_USERS", "MANAGE_ROLES", "MANAGE_POLICIES", "VIEW_AUDIT_LOGS",
                "CONFIGURE_GOVERNANCE", "CONFIGURE_AI", "VIEW_AI_DECISIONS", "OVERRIDE_AI", "TRAIN_MODELS"
            }
        }
    
    def _initialize_environment_restrictions(self) -> Dict[str, Dict[str, bool]]:
        """Initialize environment-specific restrictions."""
        return {
            "dev": {
                "read_code": True,
                "write_code": True,
                "deploy": True,
                "autonomous": True
            },
            "staging": {
                "read_code": True,
                "write_code": False,  # Only approved changes
                "deploy": True,
                "autonomous": False
            },
            "production": {
                "read_code": True,
                "write_code": False,  # Only approved changes
                "deploy": True,  # With strict approval
                "autonomous": False
            }
        }
    
    def _initialize_risk_matrix(self) -> Dict[str, RiskLevel]:
        """Initialize operation risk matrix."""
        return {
            "code_change": RiskLevel.MEDIUM,
            "config_update": RiskLevel.HIGH,
            "deployment": RiskLevel.HIGH,
            "rollback": RiskLevel.MEDIUM,
            "migration": RiskLevel.CRITICAL,
            "framework_upgrade": RiskLevel.CRITICAL,
            "security_fix": RiskLevel.HIGH,
            "data_operation": RiskLevel.HIGH,
            "user_management": RiskLevel.HIGH
        }


class SecureExecutionEngine:
    """
    Secure execution engine for AI operations with comprehensive safety measures.
    
    Provides sandboxed execution, resource limiting, network isolation,
    and comprehensive monitoring for all AI-driven operations.
    """
    
    def __init__(self):
        """Initialize the Secure Execution Engine."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.memory = MemoryLayer()
        self.settings = get_settings()
        
        # Security components
        self.permission_policy = AIPermissionPolicy()
        
        # Active environments and validations
        self.active_environments: Dict[str, ExecutionEnvironment] = {}
        self.validation_cache: Dict[str, SecurityValidation] = {}
        self.diff_previews: Dict[str, DiffPreview] = {}
        
        # Security configuration
        self.security_config = {
            "default_execution_mode": ExecutionMode.PREVIEW,
            "max_execution_time": 3600,  # 1 hour
            "enable_sandbox": True,
            "require_approval_for_production": True,
            "auto_rollback_on_failure": True,
            "resource_limits": {
                "max_cpu_percent": 50,
                "max_memory_mb": 1024,
                "max_disk_mb": 2048,
                "max_network_calls": 100
            },
            "blocked_operations": [
                "rm -rf", "format", "delete_database", "drop_table"
            ],
            "high_risk_patterns": [
                "sudo", "chmod 777", "disable_firewall", "password"
            ]
        }
    
    async def validate_operation(self, request: OperationRequest, user_role: str) -> SecurityValidation:
        """
        Comprehensive security validation for an operation request.
        
        Args:
            request: Operation request to validate
            user_role: Role of the user making the request
            
        Returns:
            Security validation result
        """
        
        validation_id = str(uuid.uuid4())
        
        # Check basic permissions
        permission_check = await self._check_permissions(request, user_role)
        
        # Assess risk level
        risk_level = await self._assess_risk_level(request)
        
        # Check for security violations
        security_violations = await self._check_security_violations(request)
        
        # Determine execution requirements
        approval_required = await self._requires_approval(request, user_role, risk_level)
        sandbox_required = await self._requires_sandbox(request, risk_level)
        
        # Calculate resource limits
        resource_limits = await self._calculate_resource_limits(request, risk_level)
        
        # Determine validation result
        if security_violations:
            result = ValidationResult.BLOCKED
        elif not permission_check["granted"]:
            result = ValidationResult.REJECTED
        elif approval_required:
            result = ValidationResult.REQUIRES_APPROVAL
        elif risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            result = ValidationResult.REQUIRES_REVIEW
        else:
            result = ValidationResult.APPROVED
        
        validation = SecurityValidation(
            validation_id=validation_id,
            operation_id=request.operation_id,
            result=result,
            risk_level=risk_level,
            security_violations=security_violations,
            required_permissions=permission_check["required_permissions"],
            approval_required=approval_required,
            sandbox_required=sandbox_required,
            max_execution_time=self._calculate_execution_time_limit(risk_level),
            resource_limits=resource_limits,
            validation_details={
                "permission_check": permission_check,
                "risk_factors": await self._identify_risk_factors(request),
                "mitigation_measures": await self._suggest_mitigations(request, risk_level)
            }
        )
        
        self.validation_cache[validation_id] = validation
        
        logging.info(f"Security validation {validation_id} completed: {result.value}")
        
        return validation
    
    async def generate_diff_preview(
        self,
        request: OperationRequest,
        validation: SecurityValidation
    ) -> DiffPreview:
        """
        Generate a comprehensive diff preview for proposed changes.
        
        Args:
            request: Operation request
            validation: Security validation result
            
        Returns:
            Detailed diff preview
        """
        
        preview_id = str(uuid.uuid4())
        
        # Analyze proposed changes
        file_changes = await self._analyze_file_changes(request)
        config_changes = await self._analyze_config_changes(request)
        dependency_changes = await self._analyze_dependency_changes(request)
        
        # Assess impact
        risk_assessment = await self._assess_change_risk(request, validation)
        estimated_impact = await self._estimate_impact(request)
        
        # Generate rollback plan
        rollback_plan = await self._generate_rollback_plan(request)
        
        preview = DiffPreview(
            preview_id=preview_id,
            operation_id=request.operation_id,
            file_changes=file_changes,
            config_changes=config_changes,
            dependency_changes=dependency_changes,
            risk_assessment=risk_assessment,
            rollback_plan=rollback_plan,
            estimated_impact=estimated_impact,
            requires_approval=validation.approval_required,
            generated_at=datetime.now()
        )
        
        self.diff_previews[preview_id] = preview
        
        logging.info(f"Generated diff preview {preview_id} for operation {request.operation_id}")
        
        return preview
    
    async def create_sandbox_environment(self, validation: SecurityValidation) -> ExecutionEnvironment:
        """
        Create an isolated sandbox environment for secure execution.
        
        Args:
            validation: Security validation with requirements
            
        Returns:
            Isolated execution environment
        """
        
        env_id = str(uuid.uuid4())
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"navi_sandbox_{env_id}_")
        
        # Set up resource limits
        resource_limits = validation.resource_limits.copy()
        resource_limits.update(self.security_config["resource_limits"])
        
        # Create isolated environment
        environment = ExecutionEnvironment(
            env_id=env_id,
            container_id=None,  # Would create Docker container in real implementation
            temp_directory=temp_dir,
            resource_limits=resource_limits,
            network_isolation=validation.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            file_system_isolation=True,
            created_at=datetime.now(),
            cleanup_at=datetime.now() + timedelta(seconds=validation.max_execution_time + 300)
        )
        
        self.active_environments[env_id] = environment
        
        # Schedule cleanup
        asyncio.create_task(self._schedule_environment_cleanup(env_id))
        
        logging.info(f"Created sandbox environment {env_id}")
        
        return environment
    
    async def execute_with_safety_checks(
        self,
        request: OperationRequest,
        validation: SecurityValidation,
        environment: Optional[ExecutionEnvironment] = None
    ) -> Dict[str, Any]:
        """
        Execute operation with comprehensive safety checks and monitoring.
        
        Args:
            request: Validated operation request
            validation: Security validation result
            environment: Optional sandbox environment
            
        Returns:
            Execution result with safety information
        """
        
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Set up monitoring
        monitor_task = asyncio.create_task(
            self._monitor_execution(execution_id, validation.max_execution_time)
        )
        
        try:
            # Pre-execution safety checks
            await self._pre_execution_checks(request, validation)
            
            # Execute based on mode
            if request.execution_mode == ExecutionMode.DRY_RUN:
                result = await self._execute_dry_run(request, environment)
            else:
                result = await self._execute_operation(request, environment)
            
            # Post-execution validation
            await self._post_execution_validation(request, result)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "execution_id": execution_id,
                "success": True,
                "result": result,
                "execution_time": execution_time,
                "safety_checks_passed": True,
                "rollback_available": result.get("rollback_info") is not None
            }
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Handle execution failure
            await self._handle_execution_failure(request, validation, str(e))
            
            return {
                "execution_id": execution_id,
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "safety_checks_passed": False,
                "rollback_initiated": self.security_config["auto_rollback_on_failure"]
            }
        
        finally:
            # Cancel monitoring
            monitor_task.cancel()
            
            # Cleanup if using sandbox
            if environment:
                await self._cleanup_environment(environment.env_id)
    
    # Helper Methods (Implementation stubs)
    
    async def _check_permissions(self, request: OperationRequest, user_role: str) -> Dict[str, Any]:
        """Check user permissions for operation."""
        
        required_permissions = []
        
        # Determine required permissions based on operation
        if "write" in request.operation_type or "change" in request.operation_type:
            required_permissions.append("WRITE_CODE")
        
        if "deploy" in request.operation_type:
            required_permissions.append("DEPLOY_CHANGES")
        
        # Check if user has required permissions
        user_permissions = self.permission_policy.role_permissions.get(user_role, set())
        granted = all(perm in user_permissions for perm in required_permissions)
        
        return {
            "granted": granted,
            "required_permissions": required_permissions,
            "user_permissions": list(user_permissions),
            "missing_permissions": [p for p in required_permissions if p not in user_permissions]
        }
    
    async def _assess_risk_level(self, request: OperationRequest) -> RiskLevel:
        """Assess risk level for an operation."""
        
        base_risk = self.permission_policy.operation_risk_matrix.get(
            request.operation_type, RiskLevel.MEDIUM
        )
        
        # Increase risk for production environment
        if request.security_context.environment == "production":
            if base_risk == RiskLevel.LOW:
                base_risk = RiskLevel.MEDIUM
            elif base_risk == RiskLevel.MEDIUM:
                base_risk = RiskLevel.HIGH
        
        return base_risk
    
    async def _check_security_violations(self, request: OperationRequest) -> List[str]:
        """Check for security violations in the operation."""
        
        violations = []
        
        # Check for blocked operations
        for blocked_op in self.security_config["blocked_operations"]:
            if blocked_op in str(request.proposed_changes):
                violations.append(f"Blocked operation detected: {blocked_op}")
        
        # Check for high-risk patterns
        for risk_pattern in self.security_config["high_risk_patterns"]:
            if risk_pattern in str(request.proposed_changes):
                violations.append(f"High-risk pattern detected: {risk_pattern}")
        
        return violations
    
    async def _requires_approval(self, request: OperationRequest, user_role: str, risk_level: RiskLevel) -> bool:
        """Determine if operation requires approval."""
        
        # Always require approval for production
        if (request.security_context.environment == "production" and 
            self.security_config["require_approval_for_production"]):
            return True
        
        # Require approval for high-risk operations
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True
        
        # Require approval if user lacks sufficient permissions
        if not self.permission_policy.can_apply_patch(
            user_role, request.security_context.environment
        ):
            return True
        
        return False
    
    async def _requires_sandbox(self, request: OperationRequest, risk_level: RiskLevel) -> bool:
        """Determine if operation requires sandbox execution."""
        
        if not self.security_config["enable_sandbox"]:
            return False
        
        # Always sandbox high-risk operations
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True
        
        # Sandbox production operations
        if request.security_context.environment == "production":
            return True
        
        return False
    
    async def _calculate_resource_limits(self, request: OperationRequest, risk_level: RiskLevel) -> Dict[str, Any]:
        """Calculate resource limits for operation."""
        
        base_limits = self.security_config["resource_limits"].copy()
        
        # Reduce limits for high-risk operations
        if risk_level == RiskLevel.CRITICAL:
            base_limits["max_cpu_percent"] = min(25, base_limits["max_cpu_percent"])
            base_limits["max_memory_mb"] = min(512, base_limits["max_memory_mb"])
        
        return base_limits
    
    def _calculate_execution_time_limit(self, risk_level: RiskLevel) -> int:
        """Calculate execution time limit based on risk."""
        
        base_time = self.security_config["max_execution_time"]
        
        if risk_level == RiskLevel.CRITICAL:
            return min(300, base_time)  # 5 minutes max for critical
        elif risk_level == RiskLevel.HIGH:
            return min(900, base_time)  # 15 minutes max for high
        
        return base_time
    
    # Additional helper method stubs
    async def _identify_risk_factors(self, request: OperationRequest) -> List[str]:
        """Identify risk factors in the operation."""
        return []
    
    async def _suggest_mitigations(self, request: OperationRequest, risk_level: RiskLevel) -> List[str]:
        """Suggest risk mitigation measures."""
        return []
    
    async def _analyze_file_changes(self, request: OperationRequest) -> List[Dict[str, Any]]:
        """Analyze file changes in the operation."""
        return []
    
    async def _analyze_config_changes(self, request: OperationRequest) -> List[Dict[str, Any]]:
        """Analyze configuration changes."""
        return []
    
    async def _analyze_dependency_changes(self, request: OperationRequest) -> List[Dict[str, Any]]:
        """Analyze dependency changes."""
        return []
    
    async def _assess_change_risk(self, request: OperationRequest, validation: SecurityValidation) -> Dict[str, Any]:
        """Assess risk of proposed changes."""
        return {"overall_risk": validation.risk_level.value}
    
    async def _estimate_impact(self, request: OperationRequest) -> Dict[str, Any]:
        """Estimate impact of changes."""
        return {"estimated_downtime": 0, "affected_services": []}
    
    async def _generate_rollback_plan(self, request: OperationRequest) -> Dict[str, Any]:
        """Generate rollback plan for changes."""
        return {"rollback_available": True, "method": "git_revert"}
    
    async def _schedule_environment_cleanup(self, env_id: str) -> None:
        """Schedule cleanup of sandbox environment."""
        # Would implement actual cleanup scheduling
        pass
    
    async def _monitor_execution(self, execution_id: str, max_time: int) -> None:
        """Monitor execution for timeout and resource usage."""
        # Would implement actual monitoring
        pass
    
    async def _pre_execution_checks(self, request: OperationRequest, validation: SecurityValidation) -> None:
        """Perform pre-execution safety checks."""
        pass
    
    async def _execute_dry_run(self, request: OperationRequest, environment: Optional[ExecutionEnvironment]) -> Dict[str, Any]:
        """Execute operation in dry-run mode."""
        return {"dry_run": True, "simulated_changes": []}
    
    async def _execute_operation(self, request: OperationRequest, environment: Optional[ExecutionEnvironment]) -> Dict[str, Any]:
        """Execute the actual operation."""
        return {"executed": True, "changes": []}
    
    async def _post_execution_validation(self, request: OperationRequest, result: Dict[str, Any]) -> None:
        """Perform post-execution validation."""
        pass
    
    async def _handle_execution_failure(self, request: OperationRequest, validation: SecurityValidation, error: str) -> None:
        """Handle execution failure."""
        logging.error(f"Execution failed for {request.operation_id}: {error}")
    
    async def _cleanup_environment(self, env_id: str) -> None:
        """Cleanup sandbox environment."""
        if env_id in self.active_environments:
            env = self.active_environments[env_id]
            # Cleanup temp directory
            import shutil
            shutil.rmtree(env.temp_directory, ignore_errors=True)
            del self.active_environments[env_id]
            logging.info(f"Cleaned up sandbox environment {env_id}")
