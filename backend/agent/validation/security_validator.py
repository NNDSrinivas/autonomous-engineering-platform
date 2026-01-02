"""
Security Validator for NAVI Phase 3.4.

Responsibility:
- Detect high-risk code patterns before apply/PR
- Block obvious vulnerabilities deterministically
- Provide clear, actionable diagnostics

This validator:
- Operates on POST-PATCH content
- Is heuristic-based (fast, predictable)
- Complements deeper SAST later in CI

Order:
- Runs AFTER SyntaxValidator
- Runs BEFORE PolicyValidator
"""

from __future__ import annotations

import os
import re
from typing import Iterable, List

from backend.agent.codegen.types import CodeChange
from backend.agent.validation.result import (
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)


class SecurityValidator:
    """
    Scans patched content for high-risk security patterns.
    """

    # ---- Dangerous APIs / patterns (language-agnostic) ----
    DANGEROUS_PATTERNS = [
        # Code execution
        (re.compile(r"\beval\s*\("), "Use of eval() is unsafe"),
        (re.compile(r"\bexec\s*\("), "Use of exec() is unsafe"),
        (re.compile(r"\bcompile\s*\("), "Dynamic compile() is unsafe"),

        # Python-specific
        (re.compile(r"\bpickle\.loads?\s*\("), "pickle deserialization is unsafe"),
        (re.compile(r"\bos\.system\s*\("), "os.system() is unsafe"),
        (re.compile(r"\bsubprocess\.Popen\s*\("), "subprocess.Popen may allow injection"),

        # JS / TS
        (re.compile(r"\bnew Function\s*\("), "new Function() is unsafe"),
        (re.compile(r"\bchild_process\.exec\s*\("), "child_process.exec is unsafe"),

        # Shell injection
        (re.compile(r"\$\{.*\}"), "Possible shell interpolation"),
    ]

    # ---- Hardcoded secret heuristics ----
    SECRET_PATTERNS = [
        (re.compile(r"AKIA[0-9A-Z]{16}"), "Possible AWS Access Key"),
        (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Possible Google API Key"),
        (re.compile(r"sk-[0-9a-zA-Z]{32,}"), "Possible OpenAI API Key"),
        (re.compile(r"-----BEGIN (RSA|EC|DSA) PRIVATE KEY-----"),
         "Embedded private key detected"),
    ]

    def __init__(self, *, repo_root: str) -> None:
        self._repo_root = os.path.abspath(repo_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, changes: Iterable[CodeChange]) -> ValidationResult:
        issues: List[ValidationIssue] = []

        for change in changes:
            content = self._materialize_content(change)
            if not content:
                continue

            self._scan_dangerous_patterns(change, content, issues)
            if issues:
                return ValidationResult(
                    status=ValidationStatus.FAILED,
                    issues=issues,
                )

            self._scan_secrets(change, content, issues)
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
    # Scanners
    # ------------------------------------------------------------------

    def _scan_dangerous_patterns(
        self,
        change: CodeChange,
        content: str,
        issues: List[ValidationIssue],
    ) -> None:
        for pattern, message in self.DANGEROUS_PATTERNS:
            if pattern.search(content):
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message=message,
                    )
                )
                return

    def _scan_secrets(
        self,
        change: CodeChange,
        content: str,
        issues: List[ValidationIssue],
    ) -> None:
        for pattern, message in self.SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(
                    ValidationIssue(
                        validator=self.__class__.__name__,
                        file_path=change.file_path,
                        message=message,
                    )
                )
                return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _materialize_content(self, change: CodeChange) -> str:
        """
        Extract post-patch content safely.

        NOTE:
        - We rely on SyntaxValidator's patch application logic
        - Here we only do lightweight scanning
        """
        # SecurityValidator intentionally reuses the same materialization logic
        # to avoid duplicating git operations.
        #
        # We assume SyntaxValidator has already validated the patch.
        #
        # For now, operate directly on the diff as a fallback.
        #
        # Future enhancement: share a PatchMaterializer service.
        return change.diff