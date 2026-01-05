"""
Extension Policy Enforcement Engine - Phase 7.2
Runtime policy enforcement with organizational controls

Enforces security policies at installation and runtime:
- Blocks untrusted extensions
- Validates permissions against org policy
- Prevents privilege escalation
- Maintains audit logs
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any
from enum import Enum
from datetime import datetime, timezone

from .signing_service import (
    ExtensionManifest,
    TrustLevel,
    ExtensionPermission,
    get_org_policy,
)

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    """Policy enforcement actions"""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    WARN = "warn"


class PolicyResult:
    """Result of policy enforcement check"""

    def __init__(
        self, action: PolicyAction, reason: str, details: Optional[Dict] = None
    ):
        self.action = action
        self.reason = reason
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def is_allowed(self) -> bool:
        return self.action == PolicyAction.ALLOW

    def requires_approval(self) -> bool:
        return self.action == PolicyAction.REQUIRE_APPROVAL


class PolicyEngine:
    """Core policy enforcement engine"""

    def __init__(self):
        self.org_policy = get_org_policy()

        # Built-in security rules that cannot be overridden
        self.immutable_rules = {
            # Untrusted extensions are always blocked
            TrustLevel.UNTRUSTED: PolicyAction.DENY,
            # Critical permissions always require approval
            "critical_permissions": {
                ExtensionPermission.DEPLOY,
                ExtensionPermission.EXECUTE_COMMANDS,
            },
        }

    def evaluate_installation(self, manifest: ExtensionManifest) -> PolicyResult:
        """Evaluate if extension installation should be allowed"""

        # Check immutable rules first
        if manifest.trust == TrustLevel.UNTRUSTED:
            return PolicyResult(
                PolicyAction.DENY,
                "Untrusted extensions are blocked",
                {"trust_level": manifest.trust},
            )

        # Check organization trust level policy
        if manifest.trust not in self.org_policy.allowed_trust_levels:
            return PolicyResult(
                PolicyAction.DENY,
                f"Trust level {manifest.trust} not allowed by organization policy",
                {"allowed_levels": list(self.org_policy.allowed_trust_levels)},
            )

        # Check blocked authors
        if manifest.author in self.org_policy.blocked_authors:
            return PolicyResult(
                PolicyAction.DENY,
                f"Author '{manifest.author}' is blocked by organization policy",
                {"blocked_author": manifest.author},
            )

        # Check forbidden permissions
        forbidden_perms = (
            set(manifest.permissions) & self.org_policy.forbidden_permissions
        )
        if forbidden_perms:
            return PolicyResult(
                PolicyAction.DENY,
                "Extension requests forbidden permissions",
                {"forbidden_permissions": list(forbidden_perms)},
            )

        # Check if approval is required
        requires_approval = (
            set(manifest.permissions) & self.org_policy.requires_approval
            or set(manifest.permissions) & self.immutable_rules["critical_permissions"]
        )

        if requires_approval:
            return PolicyResult(
                PolicyAction.REQUIRE_APPROVAL,
                "Extension requires administrator approval",
                {
                    "approval_required_for": list(requires_approval),
                    "extension_id": manifest.id,
                    "trust_level": manifest.trust,
                },
            )

        # Warn for potentially risky extensions
        if (
            manifest.trust == TrustLevel.ORG_APPROVED
            and ExtensionPermission.NETWORK_ACCESS in manifest.permissions
        ):
            return PolicyResult(
                PolicyAction.WARN,
                "Organization-approved extension with network access",
                {"warning": "Monitor network activity"},
            )

        # Default allow
        return PolicyResult(
            PolicyAction.ALLOW,
            "Extension meets all policy requirements",
            {"trust_level": manifest.trust, "permissions": list(manifest.permissions)},
        )

    def evaluate_runtime_permission(
        self,
        extension_id: str,
        permission: ExtensionPermission,
        runtime_context: Optional[Dict[str, Any]] = None,
    ) -> PolicyResult:
        """Evaluate if extension can use permission at runtime"""

        # This would check against installed extension manifest
        # For now, implement basic permission validation

        context = runtime_context or {}

        # Block dangerous operations in production mode
        if context.get("environment") == "production":
            if permission in {
                ExtensionPermission.DEPLOY,
                ExtensionPermission.EXECUTE_COMMANDS,
            }:
                return PolicyResult(
                    PolicyAction.DENY,
                    f"Permission {permission} blocked in production environment",
                    {"environment": "production", "permission": permission},
                )

        # Block file writes to sensitive paths
        if permission == ExtensionPermission.WRITE_FILES:
            file_path = context.get("file_path", "")
            sensitive_paths = ["/etc/", "/usr/", "/var/", "/bin/", "/sbin/"]

            if any(file_path.startswith(path) for path in sensitive_paths):
                return PolicyResult(
                    PolicyAction.DENY,
                    "Write access to sensitive system paths denied",
                    {"file_path": file_path, "sensitive_paths": sensitive_paths},
                )

        return PolicyResult(
            PolicyAction.ALLOW,
            f"Runtime permission {permission} allowed",
            {"permission": permission, "extension_id": extension_id},
        )


class AuditLogger:
    """Security audit logging for extension operations"""

    def __init__(self):
        self.audit_logger = logging.getLogger("navi.extension.audit")
        # Configure audit logger to write to separate audit log file
        if not self.audit_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [AUDIT] %(levelname)s: %(message)s"
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)

    def log_installation_attempt(
        self,
        manifest: ExtensionManifest,
        result: PolicyResult,
        user_id: str,
        org_id: str,
    ) -> None:
        """Log extension installation attempt"""

        self.audit_logger.info(
            "EXTENSION_INSTALL_ATTEMPT",
            extra={
                "event_type": "extension_install_attempt",
                "extension_id": manifest.id,
                "extension_name": manifest.name,
                "extension_version": manifest.version,
                "extension_author": manifest.author,
                "trust_level": manifest.trust,
                "permissions": list(manifest.permissions),
                "policy_result": result.action,
                "policy_reason": result.reason,
                "user_id": user_id,
                "org_id": org_id,
                "timestamp": result.timestamp.isoformat(),
            },
        )

    def log_runtime_permission_check(
        self,
        extension_id: str,
        permission: ExtensionPermission,
        result: PolicyResult,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log runtime permission check"""

        self.audit_logger.info(
            "EXTENSION_PERMISSION_CHECK",
            extra={
                "event_type": "extension_permission_check",
                "extension_id": extension_id,
                "permission": permission,
                "policy_result": result.action,
                "policy_reason": result.reason,
                "user_id": user_id,
                "context": context or {},
                "timestamp": result.timestamp.isoformat(),
            },
        )

    def log_security_violation(
        self,
        extension_id: str,
        violation_type: str,
        details: Dict[str, Any],
        user_id: str,
    ) -> None:
        """Log security policy violation"""

        self.audit_logger.error(
            "EXTENSION_SECURITY_VIOLATION",
            extra={
                "event_type": "extension_security_violation",
                "extension_id": extension_id,
                "violation_type": violation_type,
                "details": details,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


class SecuritySandbox:
    """Runtime security sandbox for extension execution"""

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.audit_logger = AuditLogger()

    def validate_operation(
        self,
        extension_id: str,
        operation_type: str,
        operation_data: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Validate extension operation against security policy"""

        # Map operations to permissions
        permission_mapping = {
            "file_read": ExtensionPermission.ANALYZE_PROJECT,
            "file_write": ExtensionPermission.WRITE_FILES,
            "network_request": ExtensionPermission.NETWORK_ACCESS,
            "command_execute": ExtensionPermission.EXECUTE_COMMANDS,
            "ci_action": ExtensionPermission.CI_ACCESS,
            "deployment": ExtensionPermission.DEPLOY,
        }

        permission = permission_mapping.get(operation_type)
        if not permission:
            self.audit_logger.log_security_violation(
                extension_id,
                "unknown_operation",
                {"operation_type": operation_type, "operation_data": operation_data},
                user_id,
            )
            return False

        # Check runtime permission
        result = self.policy_engine.evaluate_runtime_permission(
            extension_id, permission, operation_data
        )

        # Log the check
        self.audit_logger.log_runtime_permission_check(
            extension_id, permission, result, user_id, operation_data
        )

        # Block if denied
        if result.action == PolicyAction.DENY:
            self.audit_logger.log_security_violation(
                extension_id,
                "permission_denied",
                {
                    "permission": permission,
                    "reason": result.reason,
                    "operation_data": operation_data,
                },
                user_id,
            )
            return False

        return True

    def isolate_extension_environment(self, extension_id: str) -> Dict[str, Any]:
        """Create isolated environment for extension execution"""

        # Return environment restrictions
        return {
            "allowed_modules": [
                "json",
                "re",
                "datetime",
                "typing",
                "dataclasses",
                "pathlib",
                "tempfile",
                "logging",
            ],
            "blocked_modules": [
                "os",
                "sys",
                "subprocess",
                "socket",
                "urllib",
                "requests",
                "httplib",
                "eval",
                "exec",
                "__import__",
            ],
            "max_memory_mb": 256,
            "max_cpu_time_seconds": 30,
            "max_network_requests": 10,
            "allowed_file_extensions": [".txt", ".json", ".yaml", ".md"],
            "blocked_file_paths": ["/etc/", "/usr/", "/var/", "/bin/"],
            "extension_id": extension_id,
        }


# Global instances
_policy_engine: Optional[PolicyEngine] = None
_audit_logger: Optional[AuditLogger] = None
_security_sandbox: Optional[SecuritySandbox] = None


def get_policy_engine() -> PolicyEngine:
    """Get global policy engine instance"""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_security_sandbox() -> SecuritySandbox:
    """Get global security sandbox instance"""
    global _security_sandbox
    if _security_sandbox is None:
        _security_sandbox = SecuritySandbox()
    return _security_sandbox
