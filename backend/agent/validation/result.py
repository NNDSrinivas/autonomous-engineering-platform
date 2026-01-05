from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class ValidationIssue:
    validator: str
    message: str
    file_path: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    issues: List[ValidationIssue]

    @property
    def ok(self) -> bool:
        return self.status == ValidationStatus.PASSED
