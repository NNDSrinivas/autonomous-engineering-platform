"""
Failure Analyzer for NAVI Phase 3.6

Responsibility:
- Parse CI failure signals into structured causes
- Identify failure categories for appropriate response
- Extract actionable diagnostics from raw CI logs
- Support multiple CI systems (GitHub Actions, CircleCI, etc.)

Purpose:
This is the foundation of intelligent self-healing - instead of blindly
trying to fix everything, NAVI first understands what went wrong and
categorizes it appropriately for targeted fixes.

Flow:
1. Receive CI failure payload (logs, status, metadata)
2. Parse logs using pattern matching and heuristics
3. Extract structured failure causes with confidence scores
4. Return actionable failure information for FixPlanner
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Categories of CI failures with different fix strategies."""

    SYNTAX = "syntax"  # Syntax errors - auto-fixable
    LINT = "lint"  # Linting violations - auto-fixable
    TEST = "test"  # Test failures - human review needed
    DEPENDENCY = "dependency"  # Missing deps - conditional auto-fix
    INFRA = "infra"  # Infrastructure issues - not auto-fixable
    TIMEOUT = "timeout"  # CI timeouts - retry strategy
    UNKNOWN = "unknown"  # Unrecognized failures - human review


@dataclass(frozen=True)
class FailureCause:
    """
    Structured representation of a CI failure cause.

    Contains all information needed for fix planning and UI display.
    """

    category: FailureCategory
    message: str  # Human-readable failure description
    file_path: Optional[str] = None  # File where failure occurred
    line: Optional[int] = None  # Line number (if applicable)
    column: Optional[int] = None  # Column number (if applicable)
    raw_log_excerpt: str = ""  # Raw log segment for context
    confidence: float = 0.8  # Confidence in categorization (0-1)
    fix_hint: Optional[str] = None  # Suggested fix approach
    severity: str = "medium"  # low | medium | high | critical

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["category"] = self.category.value  # Convert enum to string
        return result

    def is_auto_fixable(self) -> bool:
        """Check if this failure type is eligible for autonomous fixing."""
        return self.category in {FailureCategory.SYNTAX, FailureCategory.LINT}


class FailureAnalysisError(Exception):
    """Raised when failure analysis encounters an error."""

    pass


class FailureAnalyzer:
    """
    Converts CI logs into structured failure causes.

    This analyzer uses pattern matching and heuristics to understand
    different types of CI failures. It's designed to be conservative -
    when in doubt, it categorizes as UNKNOWN to require human review.
    """

    # Pattern matching for different failure types
    SYNTAX_PATTERNS = [
        r"SyntaxError",
        r"IndentationError",
        r"TabError",
        r"invalid syntax",
        r"unexpected token",
        r"Syntax error",
        r"ParseError",
    ]

    LINT_PATTERNS = [
        r"lint.*failed",
        r"eslint.*error",
        r"flake8.*error",
        r"pylint.*error",
        r"prettier.*failed",
        r"black.*failed",
        r"mypy.*error",
        r"tsc.*error",
        r"Type.*error",
    ]

    TEST_PATTERNS = [
        r"FAILED.*test_",
        r"Test.*failed",
        r"AssertionError",
        r"test.*FAIL",
        r"jest.*failed",
        r"pytest.*failed",
        r"✗.*test",
    ]

    DEPENDENCY_PATTERNS = [
        r"ModuleNotFoundError",
        r"ImportError",
        r"Cannot find module",
        r"Package.*not found",
        r"dependency.*missing",
        r"npm.*ERR",
    ]

    TIMEOUT_PATTERNS = [
        r"timeout",
        r"timed out",
        r"exceeded.*time",
        r"job.*cancelled",
        r"build.*timeout",
    ]

    def __init__(self):
        """Initialize the failure analyzer."""
        self.analysis_stats = {
            "total_analyzed": 0,
            "by_category": {category: 0 for category in FailureCategory},
        }

    def analyze(self, ci_payload: Dict[str, Any]) -> List[FailureCause]:
        """
        Analyze CI failure payload and extract structured causes.

        Args:
            ci_payload: Dictionary containing CI failure information
                       Expected keys: 'logs', 'status', 'conclusion', etc.

        Returns:
            List of FailureCause objects representing detected failures
        """
        try:
            self.analysis_stats["total_analyzed"] += 1

            # Extract information from payload
            logs = ci_payload.get("logs", "")
            status = ci_payload.get("status", "")
            conclusion = ci_payload.get("conclusion", "")
            ci_payload.get("check_name", "")

            if not logs and not status:
                logger.warning("No logs or status provided for failure analysis")
                return [self._create_unknown_failure("No CI logs available", logs)]

            # Analyze logs for failure patterns
            causes = []

            # Check for syntax errors first (highest priority)
            syntax_cause = self._analyze_syntax_errors(logs)
            if syntax_cause:
                causes.append(syntax_cause)

            # Check for linting issues
            lint_cause = self._analyze_lint_failures(logs)
            if lint_cause:
                causes.append(lint_cause)

            # Check for test failures
            test_cause = self._analyze_test_failures(logs)
            if test_cause:
                causes.append(test_cause)

            # Check for dependency issues
            dep_cause = self._analyze_dependency_failures(logs)
            if dep_cause:
                causes.append(dep_cause)

            # Check for timeouts
            timeout_cause = self._analyze_timeout_failures(logs, status)
            if timeout_cause:
                causes.append(timeout_cause)

            # If no specific patterns matched, create unknown failure
            if not causes:
                causes.append(
                    self._create_unknown_failure(
                        f"Unrecognized CI failure: {conclusion}", logs
                    )
                )

            # Update statistics
            for cause in causes:
                self.analysis_stats["by_category"][cause.category] += 1

            logger.info(f"Analyzed CI failure: found {len(causes)} causes")
            return causes

        except Exception as e:
            logger.exception("Failed to analyze CI failure")
            raise FailureAnalysisError(f"Analysis failed: {e}")

    def _analyze_syntax_errors(self, logs: str) -> Optional[FailureCause]:
        """Analyze logs for syntax errors."""
        for pattern in self.SYNTAX_PATTERNS:
            match = re.search(pattern, logs, re.IGNORECASE)
            if match:
                # Try to extract file and line information
                file_info = self._extract_file_info(logs, match.start())

                return FailureCause(
                    category=FailureCategory.SYNTAX,
                    message="Syntax error detected during CI build",
                    file_path=file_info.get("file_path"),
                    line=file_info.get("line"),
                    column=file_info.get("column"),
                    raw_log_excerpt=self._extract_log_context(logs, match.start()),
                    confidence=0.9,
                    fix_hint="Review syntax around the error location",
                    severity="high",
                )
        return None

    def _analyze_lint_failures(self, logs: str) -> Optional[FailureCause]:
        """Analyze logs for linting violations."""
        for pattern in self.LINT_PATTERNS:
            match = re.search(pattern, logs, re.IGNORECASE)
            if match:
                file_info = self._extract_file_info(logs, match.start())

                return FailureCause(
                    category=FailureCategory.LINT,
                    message="Linting violations detected",
                    file_path=file_info.get("file_path"),
                    line=file_info.get("line"),
                    raw_log_excerpt=self._extract_log_context(logs, match.start()),
                    confidence=0.85,
                    fix_hint="Run linter locally and fix violations",
                    severity="medium",
                )
        return None

    def _analyze_test_failures(self, logs: str) -> Optional[FailureCause]:
        """Analyze logs for test failures."""
        for pattern in self.TEST_PATTERNS:
            match = re.search(pattern, logs, re.IGNORECASE)
            if match:
                file_info = self._extract_file_info(logs, match.start())

                return FailureCause(
                    category=FailureCategory.TEST,
                    message="Unit test failures detected",
                    file_path=file_info.get("file_path"),
                    line=file_info.get("line"),
                    raw_log_excerpt=self._extract_log_context(logs, match.start()),
                    confidence=0.9,
                    fix_hint="Review failing tests and fix implementation",
                    severity="high",
                )
        return None

    def _analyze_dependency_failures(self, logs: str) -> Optional[FailureCause]:
        """Analyze logs for dependency issues."""
        for pattern in self.DEPENDENCY_PATTERNS:
            match = re.search(pattern, logs, re.IGNORECASE)
            if match:
                return FailureCause(
                    category=FailureCategory.DEPENDENCY,
                    message="Missing or broken dependencies detected",
                    raw_log_excerpt=self._extract_log_context(logs, match.start()),
                    confidence=0.8,
                    fix_hint="Check package.json/requirements.txt and install missing dependencies",
                    severity="medium",
                )
        return None

    def _analyze_timeout_failures(
        self, logs: str, status: str
    ) -> Optional[FailureCause]:
        """Analyze for timeout/cancellation issues."""
        timeout_in_logs = any(
            re.search(pattern, logs, re.IGNORECASE) for pattern in self.TIMEOUT_PATTERNS
        )
        timeout_in_status = "timeout" in status.lower() or "cancelled" in status.lower()

        if timeout_in_logs or timeout_in_status:
            return FailureCause(
                category=FailureCategory.TIMEOUT,
                message="CI job timed out or was cancelled",
                raw_log_excerpt=logs[-300:] if logs else status,  # Last part of logs
                confidence=0.8,
                fix_hint="Consider optimizing build time or increasing timeout limits",
                severity="medium",
            )
        return None

    def _create_unknown_failure(self, message: str, logs: str) -> FailureCause:
        """Create an unknown failure cause."""
        return FailureCause(
            category=FailureCategory.UNKNOWN,
            message=message,
            raw_log_excerpt=logs[:500] if logs else "No logs available",
            confidence=0.5,
            fix_hint="Manual investigation required",
            severity="medium",
        )

    def _extract_file_info(self, logs: str, position: int) -> Dict[str, Any]:
        """
        Extract file path and line information from logs around a match position.

        This uses heuristics to find file references near error messages.
        """
        # Look for common file reference patterns around the error
        context_window = 200
        start = max(0, position - context_window)
        end = min(len(logs), position + context_window)
        context = logs[start:end]

        result = {"file_path": None, "line": None, "column": None}

        # Common patterns for file references
        file_patterns = [
            r'File "([^"]+)", line (\d+)(?:, column (\d+))?',  # Python traceback
            r"at ([^:]+):(\d+):(\d+)",  # TypeScript/JavaScript
            r"([^:\s]+):(\d+):(\d+)",  # Generic file:line:column
            r"([^:\s]+):(\d+)",  # Generic file:line
        ]

        for pattern in file_patterns:
            match = re.search(pattern, context)
            if match:
                result["file_path"] = match.group(1)
                result["line"] = (
                    int(match.group(2)) if len(match.groups()) >= 2 else None
                )
                if len(match.groups()) >= 3 and match.group(3):
                    result["column"] = int(match.group(3))
                break

        return result

    def _extract_log_context(
        self, logs: str, position: int, context_size: int = 300
    ) -> str:
        """Extract relevant log context around a match position."""
        start = max(0, position - context_size // 2)
        end = min(len(logs), position + context_size // 2)
        return logs[start:end].strip()

    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get statistics about analysis results."""
        return {
            "total_analyzed": self.analysis_stats["total_analyzed"],
            "by_category": {
                category.value: count
                for category, count in self.analysis_stats["by_category"].items()
            },
        }

    def reset_stats(self) -> None:
        """Reset analysis statistics."""
        self.analysis_stats = {
            "total_analyzed": 0,
            "by_category": {category: 0 for category in FailureCategory},
        }
