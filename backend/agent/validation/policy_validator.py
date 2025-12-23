"""
Policy Validator for NAVI Phase 3.4.

Responsibility:
- Enforce repository and organizational policies
- Apply governance rules BEFORE patches are applied
- Integrate with .aepolicy.json and future RBAC layers

Order:
- Runs AFTER SecurityValidator
- Runs BEFORE RollbackCheckpoint
"""

from __future__ import annotations

import json
import os
from typing import Iterable, List

from backend.agent.codegen.types import CodeChange, ChangeType
from backend.agent.validation.result import (
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)


class PolicyValidator:
    """
    Enforces repository-level and organization-level policies.
    """

    DEFAULT_POLICY_FILE = ".aepolicy.json"

    def __init__(self, *, repo_root: str) -> None:
        self._repo_root = os.path.abspath(repo_root)
        self._policy = self._load_policy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, changes: Iterable[CodeChange]) -> ValidationResult:
        issues: List[ValidationIssue] = []

        for change in changes:
            self._validate_change(change, issues)
            if issues:
                return ValidationResult(
                    status=ValidationStatus.FAILED,
                    issues=issues,
                )

        return ValidationResult(
            status=ValidationStatus.PASSED,
            issues=[],
        )

    # ------------------------------------------------------------------
    # Policy Enforcement
    # ------------------------------------------------------------------

    def _validate_change(
        self,
        change: CodeChange,
        issues: List[ValidationIssue],
    ) -> None:
        # Rule: DELETE restrictions
        if change.change_type.value == "delete_file":
            if not self._policy.get("allow_delete", False):
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message="DELETE operations are disallowed by policy",
                    )
                )
                return

        # Rule: Protected paths
        protected_paths = self._policy.get("protected_paths", [])
        for prefix in protected_paths:
            if change.file_path.startswith(prefix):
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message=f"Modification of protected path blocked: {prefix}",
                    )
                )
                return

        # Rule: Test enforcement for risky changes
        if self._policy.get("require_tests_for_risky_changes", True):
            if self._is_risky_change(change):
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message="Risky change requires associated tests",
                    )
                )
                return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_risky_change(self, change: CodeChange) -> bool:
        """
        Determine whether a change is considered risky by policy.
        """
        risky_keywords = self._policy.get(
            "risky_keywords",
            ["auth", "security", "payment", "crypto", "permission"],
        )

        path = change.file_path.lower()
        return any(keyword in path for keyword in risky_keywords)

    def _load_policy(self) -> dict:
        """
        Load policy from .aepolicy.json if present.
        """
        policy_path = os.path.join(self._repo_root, self.DEFAULT_POLICY_FILE)

        if not os.path.exists(policy_path):
            # Default permissive policy
            return {
                "allow_delete": False,
                "protected_paths": [],
                "require_tests_for_risky_changes": False,
                "risky_keywords": [],
            }

        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # Fail closed on malformed policy
            raise RuntimeError(
                f"Failed to load policy file {self.DEFAULT_POLICY_FILE}: {e}"
            )