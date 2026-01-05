"""
Extension Verification Service - Phase 7.2
Runtime verification with hard security stops

This is the critical security gateway - no unsigned or tampered extension can pass.
Implements zero-trust verification with cryptographic guarantees.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, Any

from .signing_service import (
    ExtensionBundle,
    ExtensionManifest,
    get_verification_service as get_signing_verification_service,
)
from .policy import PolicyResult, PolicyAction, get_policy_engine, get_audit_logger

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when extension verification fails"""

    pass


class ExtensionVerifier:
    """Main extension verification service with security enforcement"""

    def __init__(self):
        self.verification_service = get_signing_verification_service()
        self.policy_engine = get_policy_engine()
        self.audit_logger = get_audit_logger()

    def verify_and_validate_extension(
        self, bundle_bytes: bytes, user_id: str, org_id: str
    ) -> ExtensionBundle:
        """
        Complete extension verification and policy validation

        This is the main entry point for extension installation.
        HARD STOPS on any failure - no silent bypasses allowed.
        """

        try:
            # Step 1: Cryptographic verification (CRITICAL)
            bundle = self._verify_cryptographic_integrity(bundle_bytes)
            logger.info(
                f"Extension {bundle.manifest.id} passed cryptographic verification"
            )

            # Step 2: Policy validation (ENFORCEMENT)
            policy_result = self._validate_against_policy(
                bundle.manifest, user_id, org_id
            )

            # Step 3: Security checks (ADDITIONAL PROTECTION)
            self._perform_security_checks(bundle)

            # Step 4: Audit logging (COMPLIANCE)
            self._log_verification_success(bundle, policy_result, user_id, org_id)

            return bundle

        except Exception as e:
            # Log verification failure
            self._log_verification_failure(e, user_id, org_id)
            raise VerificationError(f"Extension verification failed: {e}")

    def _verify_cryptographic_integrity(self, bundle_bytes: bytes) -> ExtensionBundle:
        """Verify cryptographic signature and integrity - HARD STOP on failure"""

        try:
            # This will raise an exception if signature is invalid
            bundle = self.verification_service.verify_extension_bundle(bundle_bytes)

            # Additional hash validation
            self._validate_content_hash(bundle)

            return bundle

        except ValueError as e:
            raise VerificationError(f"Cryptographic verification failed: {e}")

    def _validate_content_hash(self, bundle: ExtensionBundle) -> None:
        """Validate that bundle content matches manifest hash"""

        # Recalculate hash of bundle contents
        calculated_hash = hashlib.sha256()

        # Hash all files in deterministic order
        for filename in sorted(bundle.files.keys()):
            calculated_hash.update(filename.encode("utf-8"))
            calculated_hash.update(bundle.files[filename])

        calculated_hex = calculated_hash.hexdigest()

        if calculated_hex != bundle.manifest.hash:
            raise VerificationError(
                f"Content hash mismatch: expected {bundle.manifest.hash}, got {calculated_hex}"
            )

        if calculated_hex != bundle.bundle_hash:
            raise VerificationError(
                f"Bundle hash inconsistency: manifest={bundle.manifest.hash}, bundle={bundle.bundle_hash}"
            )

    def _validate_against_policy(
        self, manifest: ExtensionManifest, user_id: str, org_id: str
    ) -> PolicyResult:
        """Validate extension against organization policy - HARD STOP on denial"""

        policy_result = self.policy_engine.evaluate_installation(manifest)

        # Log policy evaluation
        self.audit_logger.log_installation_attempt(
            manifest, policy_result, user_id, org_id
        )

        # HARD STOP: Block denied extensions
        if policy_result.action == PolicyAction.DENY:
            raise VerificationError(f"Policy violation: {policy_result.reason}")

        # APPROVAL REQUIRED: Block until approved
        if policy_result.action == PolicyAction.REQUIRE_APPROVAL:
            raise VerificationError(
                f"Administrator approval required: {policy_result.reason}. "
                f"Extension blocked until approved."
            )

        # Warn but allow
        if policy_result.action == PolicyAction.WARN:
            logger.warning(f"Extension policy warning: {policy_result.reason}")

        return policy_result

    def _perform_security_checks(self, bundle: ExtensionBundle) -> None:
        """Additional security checks beyond signature verification"""

        manifest = bundle.manifest

        # Check for suspicious file types
        suspicious_extensions = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so"}
        for filename in bundle.files.keys():
            if any(filename.lower().endswith(ext) for ext in suspicious_extensions):
                raise VerificationError(f"Suspicious file type detected: {filename}")

        # Check for excessive permissions
        if len(manifest.permissions) > 5:
            logger.warning(
                f"Extension {manifest.id} requests {len(manifest.permissions)} permissions"
            )

        # Validate manifest fields
        if not manifest.id or not manifest.name or not manifest.version:
            raise VerificationError("Invalid manifest: missing required fields")

        # Check entry point exists
        if manifest.entry not in bundle.files:
            raise VerificationError(f"Entry point {manifest.entry} not found in bundle")

        # Basic code scanning for dangerous patterns
        self._scan_for_dangerous_code(bundle)

    def _scan_for_dangerous_code(self, bundle: ExtensionBundle) -> None:
        """Basic code scanning for dangerous patterns"""

        dangerous_patterns = [
            b"eval(",
            b"exec(",
            b"__import__(",
            b"os.system(",
            b"subprocess.",
            b"socket.",
            b"urllib.",
            b"requests.",
            b'open("/etc/',
            b'open("/usr/',
            b"rm -rf",
            b"del /s",
        ]

        for filename, content in bundle.files.items():
            if filename.endswith((".py", ".js", ".ts")):
                content_lower = content.lower()

                for pattern in dangerous_patterns:
                    if pattern in content_lower:
                        logger.warning(
                            f"Potentially dangerous pattern found in {filename}: {pattern.decode()}"
                        )
                        # Don't block, but log for review

    def _log_verification_success(
        self,
        bundle: ExtensionBundle,
        policy_result: PolicyResult,
        user_id: str,
        org_id: str,
    ) -> None:
        """Log successful extension verification"""

        logger.info(
            f"Extension verification SUCCESS: {bundle.manifest.id} v{bundle.manifest.version} "
            f"by {bundle.manifest.author} with trust level {bundle.manifest.trust}"
        )

        # Additional audit logging happens in policy engine

    def _log_verification_failure(
        self, error: Exception, user_id: str, org_id: str
    ) -> None:
        """Log verification failure"""

        logger.error(f"Extension verification FAILED: {error}")

        self.audit_logger.audit_logger.error(
            "EXTENSION_VERIFICATION_FAILED",
            extra={
                "event_type": "extension_verification_failed",
                "error": str(error),
                "error_type": type(error).__name__,
                "user_id": user_id,
                "org_id": org_id,
            },
        )


class RuntimePermissionChecker:
    """Runtime permission validation for active extensions"""

    def __init__(self):
        self.policy_engine = get_policy_engine()
        self.audit_logger = get_audit_logger()
        # In production, this would load from database
        self.installed_extensions: Dict[str, ExtensionManifest] = {}

    def register_extension(self, bundle: ExtensionBundle) -> None:
        """Register successfully installed extension"""
        self.installed_extensions[bundle.manifest.id] = bundle.manifest
        logger.info(f"Extension {bundle.manifest.id} registered for runtime checks")

    def check_runtime_permission(
        self,
        extension_id: str,
        permission: str,
        operation_context: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Check if extension can perform operation at runtime"""

        # Verify extension is installed
        if extension_id not in self.installed_extensions:
            logger.error(
                f"Runtime permission check for unknown extension: {extension_id}"
            )
            return False

        manifest = self.installed_extensions[extension_id]

        # Check if extension was granted this permission during installation
        if permission not in [p.value for p in manifest.permissions]:
            self.audit_logger.log_security_violation(
                extension_id,
                "permission_escalation_attempt",
                {
                    "requested_permission": permission,
                    "granted_permissions": [p.value for p in manifest.permissions],
                    "operation_context": operation_context,
                },
                user_id,
            )
            return False

        # Additional runtime policy check
        from .signing_service import ExtensionPermission

        try:
            perm_enum = ExtensionPermission(permission)
        except ValueError:
            logger.error(f"Invalid permission requested: {permission}")
            return False

        policy_result = self.policy_engine.evaluate_runtime_permission(
            extension_id, perm_enum, operation_context
        )

        # Log the permission check
        self.audit_logger.log_runtime_permission_check(
            extension_id, perm_enum, policy_result, user_id, operation_context
        )

        # Only allow if policy permits
        return policy_result.action == PolicyAction.ALLOW


# Quick verification function for API endpoints
def verify_extension_bundle(
    bundle_bytes: bytes, user_id: str, org_id: str
) -> ExtensionBundle:
    """
    Main verification entry point for API

    Returns verified extension bundle or raises VerificationError
    """
    verifier = ExtensionVerifier()
    return verifier.verify_and_validate_extension(bundle_bytes, user_id, org_id)


# Runtime permission check for extension execution
def check_extension_permission(
    extension_id: str, permission: str, operation_context: Dict[str, Any], user_id: str
) -> bool:
    """
    Runtime permission check entry point

    Returns True if operation is allowed, False otherwise
    """
    checker = RuntimePermissionChecker()
    return checker.check_runtime_permission(
        extension_id, permission, operation_context, user_id
    )
