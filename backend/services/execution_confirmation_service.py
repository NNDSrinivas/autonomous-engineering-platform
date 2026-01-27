"""
Execution Confirmation Service for NAVI
Handles risk classification, user warnings, and approval flows for critical operations.

This service ensures that dangerous operations (deployments, migrations, infrastructure changes)
require explicit user confirmation before execution.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for operations."""
    LOW = "low"           # Read-only, no side effects
    MEDIUM = "medium"     # Local file changes, reversible
    HIGH = "high"         # External system changes, partially reversible
    CRITICAL = "critical" # Production changes, potentially irreversible


class OperationCategory(Enum):
    """Categories of operations."""
    DEPLOYMENT = "deployment"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    SECRETS = "secrets"
    CODE_EXECUTION = "code_execution"
    FILE_SYSTEM = "file_system"
    EXTERNAL_API = "external_api"


@dataclass
class ExecutionWarning:
    """Warning message for user review."""
    level: RiskLevel
    title: str
    message: str
    details: List[str] = field(default_factory=list)
    mitigation: Optional[str] = None
    rollback_available: bool = False
    rollback_instructions: Optional[str] = None


@dataclass
class ExecutionRequest:
    """Request for execution approval."""
    id: str
    operation_name: str
    operation_category: OperationCategory
    risk_level: RiskLevel
    description: str
    warnings: List[ExecutionWarning]
    parameters: Dict[str, Any]
    estimated_duration: Optional[str] = None
    affected_resources: List[str] = field(default_factory=list)
    rollback_plan: Optional[str] = None
    requires_confirmation: bool = True
    confirmation_phrase: Optional[str] = None  # User must type this to confirm critical ops
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    approved: bool = False
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    executed: bool = False
    execution_result: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionResult:
    """Result of an executed operation."""
    success: bool
    output: str
    error: Optional[str] = None
    duration_seconds: float = 0.0
    resources_affected: List[str] = field(default_factory=list)
    rollback_id: Optional[str] = None  # ID for rolling back this operation
    logs: List[str] = field(default_factory=list)


# Risk classification rules for different operations
OPERATION_RISK_MATRIX: Dict[str, Dict[str, Any]] = {
    # Deployment operations
    "deploy.execute": {
        "category": OperationCategory.DEPLOYMENT,
        "base_risk": RiskLevel.HIGH,
        "production_risk": RiskLevel.CRITICAL,
        "warnings": [
            "This will deploy code to a live environment",
            "Users may experience downtime during deployment",
            "Ensure all tests have passed before deploying",
        ],
        "confirmation_required": True,
        "production_confirmation_phrase": "DEPLOY TO PRODUCTION",
    },
    "deploy.rollback": {
        "category": OperationCategory.DEPLOYMENT,
        "base_risk": RiskLevel.HIGH,
        "warnings": [
            "This will rollback to a previous deployment",
            "Recent changes will be reverted",
        ],
        "confirmation_required": True,
    },

    # Infrastructure operations
    "infra.terraform_apply": {
        "category": OperationCategory.INFRASTRUCTURE,
        "base_risk": RiskLevel.CRITICAL,
        "warnings": [
            "This will modify cloud infrastructure",
            "Resources may be created, modified, or DESTROYED",
            "Costs may increase based on resources created",
            "This operation may take several minutes",
        ],
        "confirmation_required": True,
        "confirmation_phrase": "APPLY INFRASTRUCTURE CHANGES",
    },
    "infra.terraform_destroy": {
        "category": OperationCategory.INFRASTRUCTURE,
        "base_risk": RiskLevel.CRITICAL,
        "warnings": [
            "⚠️ DESTRUCTIVE OPERATION ⚠️",
            "This will PERMANENTLY DELETE cloud resources",
            "All data in destroyed resources will be LOST",
            "This action CANNOT be undone",
        ],
        "confirmation_required": True,
        "confirmation_phrase": "DESTROY ALL INFRASTRUCTURE",
    },
    "infra.kubectl_apply": {
        "category": OperationCategory.INFRASTRUCTURE,
        "base_risk": RiskLevel.HIGH,
        "production_risk": RiskLevel.CRITICAL,
        "warnings": [
            "This will modify Kubernetes resources",
            "Pods may be restarted or replaced",
            "Service disruption may occur",
        ],
        "confirmation_required": True,
    },

    # Database operations
    "db.run_migration": {
        "category": OperationCategory.DATABASE,
        "base_risk": RiskLevel.HIGH,
        "production_risk": RiskLevel.CRITICAL,
        "warnings": [
            "This will modify the database schema",
            "Data may be transformed or migrated",
            "Ensure you have a recent backup",
            "Large tables may take time to migrate",
        ],
        "confirmation_required": True,
        "production_confirmation_phrase": "RUN PRODUCTION MIGRATION",
    },
    "db.run_migration_down": {
        "category": OperationCategory.DATABASE,
        "base_risk": RiskLevel.CRITICAL,
        "warnings": [
            "⚠️ DESTRUCTIVE OPERATION ⚠️",
            "This will ROLLBACK database migrations",
            "Data added after migration may be LOST",
            "Foreign key constraints may cause failures",
        ],
        "confirmation_required": True,
        "confirmation_phrase": "ROLLBACK DATABASE MIGRATION",
    },
    "db.seed_production": {
        "category": OperationCategory.DATABASE,
        "base_risk": RiskLevel.CRITICAL,
        "warnings": [
            "⚠️ PRODUCTION DATA MODIFICATION ⚠️",
            "This will insert/modify data in production",
            "Existing data may be affected",
        ],
        "confirmation_required": True,
        "confirmation_phrase": "MODIFY PRODUCTION DATA",
    },

    # Secrets operations
    "secrets.rotate": {
        "category": OperationCategory.SECRETS,
        "base_risk": RiskLevel.HIGH,
        "warnings": [
            "This will rotate secrets/credentials",
            "Applications using old secrets will fail",
            "Ensure all services can reload secrets",
        ],
        "confirmation_required": True,
    },
    "secrets.sync_to_platform": {
        "category": OperationCategory.SECRETS,
        "base_risk": RiskLevel.MEDIUM,
        "production_risk": RiskLevel.HIGH,
        "warnings": [
            "This will update environment variables on the platform",
            "Services may need to be restarted",
        ],
        "confirmation_required": True,
    },

    # Code execution
    "code.run_command": {
        "category": OperationCategory.CODE_EXECUTION,
        "base_risk": RiskLevel.MEDIUM,
        "warnings": [
            "This will execute a shell command",
            "Command output will be captured",
        ],
        "confirmation_required": False,  # Depends on the command
    },
}


class ExecutionConfirmationService:
    """
    Service for managing execution confirmations and approvals.

    This service:
    1. Classifies operations by risk level
    2. Generates appropriate warnings
    3. Manages approval workflow
    4. Tracks execution history
    5. Provides rollback capabilities
    """

    def __init__(self):
        self._pending_requests: Dict[str, ExecutionRequest] = {}
        self._execution_history: List[ExecutionRequest] = []
        self._approval_callbacks: Dict[str, Callable] = {}
        self._expiry_minutes = 30  # Approvals expire after 30 minutes

    def classify_risk(
        self,
        operation_name: str,
        parameters: Dict[str, Any],
        environment: str = "development"
    ) -> RiskLevel:
        """
        Classify the risk level of an operation.

        Args:
            operation_name: Name of the operation (e.g., "deploy.execute")
            parameters: Operation parameters
            environment: Target environment (development, staging, production)

        Returns:
            RiskLevel for the operation
        """
        matrix = OPERATION_RISK_MATRIX.get(operation_name, {})
        base_risk = matrix.get("base_risk", RiskLevel.MEDIUM)

        # Elevate risk for production environments
        if environment.lower() in ["production", "prod", "live"]:
            production_risk = matrix.get("production_risk")
            if production_risk:
                return production_risk
            # Auto-elevate to at least HIGH for production
            if base_risk in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                return RiskLevel.HIGH

        return base_risk

    def generate_warnings(
        self,
        operation_name: str,
        parameters: Dict[str, Any],
        environment: str = "development"
    ) -> List[ExecutionWarning]:
        """Generate warnings for an operation."""
        warnings = []
        matrix = OPERATION_RISK_MATRIX.get(operation_name, {})
        risk_level = self.classify_risk(operation_name, parameters, environment)

        # Add operation-specific warnings
        for warning_msg in matrix.get("warnings", []):
            warnings.append(ExecutionWarning(
                level=risk_level,
                title=f"{operation_name} Warning",
                message=warning_msg,
            ))

        # Add environment-specific warnings
        if environment.lower() in ["production", "prod", "live"]:
            warnings.insert(0, ExecutionWarning(
                level=RiskLevel.CRITICAL,
                title="⚠️ PRODUCTION ENVIRONMENT ⚠️",
                message="You are about to modify a PRODUCTION environment. This may affect live users.",
                details=[
                    "All changes will be immediately visible to users",
                    "Ensure you have tested in staging first",
                    "Have a rollback plan ready",
                    "Consider notifying the team before proceeding",
                ],
                mitigation="Consider deploying during low-traffic hours",
            ))

        # Add rollback information if available
        if self._has_rollback_capability(operation_name):
            for warning in warnings:
                warning.rollback_available = True
                warning.rollback_instructions = self._get_rollback_instructions(operation_name)

        return warnings

    def create_execution_request(
        self,
        operation_name: str,
        description: str,
        parameters: Dict[str, Any],
        environment: str = "development",
        affected_resources: Optional[List[str]] = None,
        estimated_duration: Optional[str] = None,
    ) -> ExecutionRequest:
        """
        Create an execution request that requires user approval.

        Returns an ExecutionRequest with all necessary information for the user
        to make an informed decision.
        """
        request_id = str(uuid.uuid4())
        matrix = OPERATION_RISK_MATRIX.get(operation_name, {})
        risk_level = self.classify_risk(operation_name, parameters, environment)
        warnings = self.generate_warnings(operation_name, parameters, environment)

        # Determine confirmation phrase
        confirmation_phrase = None
        if risk_level == RiskLevel.CRITICAL:
            if environment.lower() in ["production", "prod", "live"]:
                confirmation_phrase = matrix.get(
                    "production_confirmation_phrase",
                    matrix.get("confirmation_phrase", f"CONFIRM {operation_name.upper()}")
                )
            else:
                confirmation_phrase = matrix.get("confirmation_phrase")

        request = ExecutionRequest(
            id=request_id,
            operation_name=operation_name,
            operation_category=matrix.get("category", OperationCategory.CODE_EXECUTION),
            risk_level=risk_level,
            description=description,
            warnings=warnings,
            parameters=parameters,
            estimated_duration=estimated_duration,
            affected_resources=affected_resources or [],
            rollback_plan=self._get_rollback_instructions(operation_name) if self._has_rollback_capability(operation_name) else None,
            requires_confirmation=matrix.get("confirmation_required", True),
            confirmation_phrase=confirmation_phrase,
            expires_at=datetime.utcnow() + timedelta(minutes=self._expiry_minutes),
        )

        self._pending_requests[request_id] = request
        return request

    async def approve_execution(
        self,
        request_id: str,
        user_id: str,
        confirmation_input: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Approve an execution request.

        Args:
            request_id: The execution request ID
            user_id: The user approving the request
            confirmation_input: The confirmation phrase (required for critical ops)

        Returns:
            Tuple of (success, message)
        """
        request = self._pending_requests.get(request_id)

        if not request:
            return False, "Execution request not found or expired"

        if request.expires_at and datetime.utcnow() > request.expires_at:
            del self._pending_requests[request_id]
            return False, "Execution request has expired. Please create a new request."

        if request.approved:
            return False, "Request has already been approved"

        # Verify confirmation phrase for critical operations
        if request.confirmation_phrase:
            if not confirmation_input:
                return False, f"Please type '{request.confirmation_phrase}' to confirm"
            if confirmation_input.strip().upper() != request.confirmation_phrase.upper():
                return False, f"Confirmation phrase does not match. Expected: '{request.confirmation_phrase}'"

        # Mark as approved
        request.approved = True
        request.approved_at = datetime.utcnow()
        request.approved_by = user_id

        logger.info(
            "Execution approved: %s by %s at %s",
            request.operation_name,
            user_id,
            request.approved_at
        )

        return True, "Execution approved successfully"

    async def execute_approved_request(
        self,
        request_id: str,
        executor: Callable[[Dict[str, Any]], Awaitable[ExecutionResult]],
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> ExecutionResult:
        """
        Execute an approved request.

        Args:
            request_id: The approved execution request ID
            executor: Async function that performs the actual execution
            progress_callback: Optional callback for progress updates

        Returns:
            ExecutionResult with the outcome
        """
        request = self._pending_requests.get(request_id)

        if not request:
            return ExecutionResult(
                success=False,
                output="",
                error="Execution request not found",
            )

        if not request.approved:
            return ExecutionResult(
                success=False,
                output="",
                error="Execution request has not been approved",
            )

        if request.executed:
            return ExecutionResult(
                success=False,
                output="",
                error="Request has already been executed",
            )

        # Mark as executed
        request.executed = True
        start_time = datetime.utcnow()

        try:
            if progress_callback:
                await progress_callback(f"Starting execution of {request.operation_name}...")

            # Execute the operation
            result = await executor(request.parameters)

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            result.duration_seconds = duration

            # Store result
            request.execution_result = {
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "duration_seconds": duration,
            }

            # Move to history
            self._execution_history.append(request)
            del self._pending_requests[request_id]

            logger.info(
                "Execution completed: %s - Success: %s - Duration: %.2fs",
                request.operation_name,
                result.success,
                duration
            )

            return result

        except Exception as e:
            logger.error("Execution failed: %s - Error: %s", request.operation_name, str(e))
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )

    def reject_execution(self, request_id: str, user_id: str, reason: str = "") -> bool:
        """Reject an execution request."""
        request = self._pending_requests.get(request_id)
        if request:
            logger.info(
                "Execution rejected: %s by %s - Reason: %s",
                request.operation_name,
                user_id,
                reason
            )
            del self._pending_requests[request_id]
            return True
        return False

    def get_pending_requests(self, user_id: Optional[str] = None) -> List[ExecutionRequest]:
        """Get all pending execution requests."""
        # Clean up expired requests
        now = datetime.utcnow()
        expired = [
            rid for rid, req in self._pending_requests.items()
            if req.expires_at and now > req.expires_at
        ]
        for rid in expired:
            del self._pending_requests[rid]

        return list(self._pending_requests.values())

    def get_execution_history(
        self,
        limit: int = 50,
        operation_name: Optional[str] = None,
    ) -> List[ExecutionRequest]:
        """Get execution history."""
        history = self._execution_history
        if operation_name:
            history = [h for h in history if h.operation_name == operation_name]
        return history[-limit:]

    def _has_rollback_capability(self, operation_name: str) -> bool:
        """Check if an operation supports rollback."""
        rollback_supported = {
            "deploy.execute",
            "infra.terraform_apply",
            "infra.kubectl_apply",
            "db.run_migration",
        }
        return operation_name in rollback_supported

    def _get_rollback_instructions(self, operation_name: str) -> str:
        """Get rollback instructions for an operation."""
        instructions = {
            "deploy.execute": "Use 'deploy.rollback' to revert to the previous deployment",
            "infra.terraform_apply": "Run 'terraform destroy' or apply previous state",
            "infra.kubectl_apply": "Use 'kubectl rollout undo' to revert changes",
            "db.run_migration": "Run migration with --down flag to reverse",
        }
        return instructions.get(operation_name, "Manual rollback may be required")

    def format_request_for_ui(self, request: ExecutionRequest) -> Dict[str, Any]:
        """Format an execution request for UI display."""
        return {
            "id": request.id,
            "operation": request.operation_name,
            "category": request.operation_category.value,
            "risk_level": request.risk_level.value,
            "description": request.description,
            "warnings": [
                {
                    "level": w.level.value,
                    "title": w.title,
                    "message": w.message,
                    "details": w.details,
                    "mitigation": w.mitigation,
                    "rollback_available": w.rollback_available,
                    "rollback_instructions": w.rollback_instructions,
                }
                for w in request.warnings
            ],
            "parameters": request.parameters,
            "estimated_duration": request.estimated_duration,
            "affected_resources": request.affected_resources,
            "rollback_plan": request.rollback_plan,
            "requires_confirmation": request.requires_confirmation,
            "confirmation_phrase": request.confirmation_phrase,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "ui_config": self._get_ui_config(request.risk_level),
        }

    def _get_ui_config(self, risk_level: RiskLevel) -> Dict[str, Any]:
        """Get UI configuration based on risk level."""
        configs = {
            RiskLevel.LOW: {
                "color": "green",
                "icon": "info",
                "banner_style": "subtle",
                "require_scroll": False,
                "button_style": "primary",
            },
            RiskLevel.MEDIUM: {
                "color": "yellow",
                "icon": "warning",
                "banner_style": "warning",
                "require_scroll": False,
                "button_style": "warning",
            },
            RiskLevel.HIGH: {
                "color": "orange",
                "icon": "alert-triangle",
                "banner_style": "danger",
                "require_scroll": True,
                "button_style": "danger",
                "confirm_delay_seconds": 3,
            },
            RiskLevel.CRITICAL: {
                "color": "red",
                "icon": "alert-octagon",
                "banner_style": "critical",
                "require_scroll": True,
                "button_style": "critical",
                "confirm_delay_seconds": 5,
                "require_checkbox": True,
                "checkbox_text": "I understand this action may be irreversible",
                "pulsing_border": True,
            },
        }
        return configs.get(risk_level, configs[RiskLevel.MEDIUM])


# Global instance
execution_confirmation_service = ExecutionConfirmationService()
