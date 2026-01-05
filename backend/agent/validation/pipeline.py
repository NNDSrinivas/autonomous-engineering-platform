"""
ValidationPipeline for NAVI Phase 3.4.

This orchestrator runs all validators in sequence:
1. ScopeValidator (boundary checks)
2. SyntaxValidator (parsing validation)
3. SecurityValidator (vulnerability detection)
4. PolicyValidator (governance enforcement)

Fail-fast behavior: stops at first validation failure.
"""

from __future__ import annotations

from typing import Iterable, List

from backend.agent.codegen.types import CodeChange
from backend.agent.validation.result import ValidationResult, ValidationStatus
from backend.agent.validation.scope_validator import ScopeValidator
from backend.agent.validation.syntax_validator import SyntaxValidator
from backend.agent.validation.security_validator import SecurityValidator
from backend.agent.validation.policy_validator import PolicyValidator


class ValidationPipeline:
    """
    Orchestrates all validation layers with fail-fast behavior.
    """

    def __init__(self, *, repo_root: str) -> None:
        self._validators = [
            ScopeValidator(repo_root=repo_root),
            SyntaxValidator(),
            SecurityValidator(),
            PolicyValidator(repo_root=repo_root),
        ]

    def validate(self, changes: Iterable[CodeChange]) -> ValidationResult:
        """
        Run all validators in sequence. Stop at first failure.
        """
        changes_list = list(changes)

        if not changes_list:
            return ValidationResult(
                status=ValidationStatus.PASSED,
                issues=[],
            )

        for validator in self._validators:
            result = validator.validate(changes_list)
            if result.status == ValidationStatus.FAILED:
                return result

        return ValidationResult(
            status=ValidationStatus.PASSED,
            issues=[],
        )

    def get_validator_names(self) -> List[str]:
        """
        Get list of validator class names for debugging.
        """
        return [validator.__class__.__name__ for validator in self._validators]
