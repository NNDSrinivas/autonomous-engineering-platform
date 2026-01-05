# backend/schemas/review_schemas.py
"""
Pydantic schemas for auto-fix and code review operations.
Part of Batch 6 — Real Auto-Fix Engine.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity levels for code issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NONE = "none"


class FixRequest(BaseModel):
    """Request to register a code fix."""

    file_path: str = Field(..., description="Path to the file containing the issue")
    hunk: str = Field(..., description="Git diff hunk containing the problematic code")
    issue: str = Field(..., description="Description of the issue to fix")
    line_number: Optional[int] = Field(
        None, description="Line number where the issue occurs"
    )
    severity: SeverityLevel = Field(
        SeverityLevel.INFO, description="Severity of the issue"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "src/components/Button.tsx",
                "hunk": "@@ -15,7 +15,7 @@\n function Button() {\n-  const [count, setCount] = useState();\n+  const [count, setCount] = useState(0);\n   return <button>{count}</button>;\n }",
                "issue": "useState hook should have initial value",
                "line_number": 16,
                "severity": "warning",
            }
        }


class FixResponse(BaseModel):
    """Response from auto-fix operation."""

    status: Literal["success", "failed"] = Field(
        ..., description="Status of the fix operation"
    )
    patch: str = Field(..., description="Generated unified diff patch")
    file_path: str = Field(..., description="Path to the file being fixed")
    fix_id: str = Field(..., description="Unique identifier for this fix")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the fix"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "patch": "--- a/src/components/Button.tsx\n+++ b/src/components/Button.tsx\n@@ -15,7 +15,7 @@\n function Button() {\n-  const [count, setCount] = useState();\n+  const [count, setCount] = useState(0);\n   return <button>{count}</button>;\n }",
                "file_path": "src/components/Button.tsx",
                "fix_id": "fix_12345",
                "metadata": {
                    "confidence": 0.95,
                    "fix_type": "type_annotation",
                    "estimated_safety": "high",
                },
            }
        }


class ReviewEntry(BaseModel):
    """Individual review entry for a code change."""

    file: str = Field(..., description="File path relative to repository root")
    issues: List[str] = Field(
        default_factory=list, description="List of issues found in this file"
    )
    severity: SeverityLevel = Field(
        SeverityLevel.INFO, description="Overall severity for this file"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    fix_id: Optional[str] = Field(None, description="ID for auto-fix if available")
    line_numbers: List[int] = Field(
        default_factory=list, description="Line numbers with issues"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "file": "src/components/Button.tsx",
                "issues": ["useState hook missing initial value", "Missing prop types"],
                "severity": "warning",
                "suggestions": [
                    "Add initial value to useState",
                    "Define prop interface",
                ],
                "fix_id": "fix_12345",
                "line_numbers": [16, 25],
            }
        }


class ReviewResponse(BaseModel):
    """Complete code review response."""

    summary: str = Field(..., description="Overall review summary")
    entries: List[ReviewEntry] = Field(
        ..., description="Individual file review entries"
    )
    overall_severity: SeverityLevel = Field(
        SeverityLevel.INFO, description="Highest severity across all files"
    )
    total_issues: int = Field(0, description="Total number of issues found")
    fixable_issues: int = Field(
        0, description="Number of issues that can be auto-fixed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Found 3 issues across 2 files with 2 auto-fixable problems",
                "entries": [
                    {
                        "file": "src/components/Button.tsx",
                        "issues": ["useState hook missing initial value"],
                        "severity": "warning",
                        "fix_id": "fix_12345",
                    }
                ],
                "overall_severity": "warning",
                "total_issues": 3,
                "fixable_issues": 2,
            }
        }
