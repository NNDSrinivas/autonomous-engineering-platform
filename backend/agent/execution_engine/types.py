"""
Execution Engine Types - Phase 4.3

Type definitions for the autonomous execution system.
These types define the canonical execution loop interface.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


class ExecutionStatus(str, Enum):
    """Status of execution phases"""

    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    PROPOSING = "proposing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLYING = "applying"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DiagnosticIssue(BaseModel):
    """Single diagnostic issue analysis"""

    file: str = Field(description="File path relative to workspace")
    line: int = Field(description="Line number (1-indexed)")
    character: int = Field(description="Character position")
    message: str = Field(description="Diagnostic message")
    severity: Literal["error", "warning", "info", "hint"] = Field(
        description="Issue severity"
    )
    source: Optional[str] = Field(
        default=None, description="Diagnostic source (e.g., 'eslint', 'typescript')"
    )
    code: Optional[str] = Field(
        default=None, description="Diagnostic code if available"
    )
    category: str = Field(
        description="Issue category (e.g., 'ReferenceError', 'SyntaxError')"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in analysis")
    fixable: bool = Field(
        default=True, description="Whether this issue can be automatically fixed"
    )


class AnalysisResult(BaseModel):
    """Result of analyzing a GroundedTask"""

    issues: List[DiagnosticIssue] = Field(description="Analyzed diagnostic issues")
    total_issues: int = Field(description="Total number of issues found")
    error_count: int = Field(description="Number of errors")
    warning_count: int = Field(description="Number of warnings")
    fixable_count: int = Field(description="Number of issues that can be auto-fixed")
    affected_files: List[str] = Field(description="List of files with issues")
    analysis_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in analysis"
    )
    estimated_complexity: Literal["low", "medium", "high"] = Field(
        description="Estimated fix complexity"
    )


class FixStep(BaseModel):
    """Single step in a fix plan"""

    step_id: str = Field(description="Unique step identifier")
    title: str = Field(description="Human-readable step title")
    description: str = Field(description="Detailed step description")
    file_target: str = Field(description="Primary file this step affects")
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Risk level of this step"
    )


class FixPlan(BaseModel):
    """Plan for fixing analyzed issues"""

    summary: str = Field(description="High-level summary of the fix approach")
    reasoning: str = Field(description="Detailed reasoning behind the fix plan")
    steps: List[FixStep] = Field(description="Ordered list of fix steps")
    files_to_modify: List[str] = Field(
        description="List of files that will be modified"
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Overall risk level"
    )
    estimated_time: str = Field(description="Estimated time to apply fixes")
    requires_tests: bool = Field(
        default=False, description="Whether tests should be run after fixes"
    )


class FileDiff(BaseModel):
    """Diff for a single file"""

    file: str = Field(description="File path relative to workspace")
    original_content: Optional[str] = Field(
        default=None, description="Original file content"
    )
    modified_content: str = Field(description="Modified file content")
    unified_diff: str = Field(description="Unified diff format")
    lines_added: int = Field(ge=0, description="Number of lines added")
    lines_removed: int = Field(ge=0, description="Number of lines removed")
    change_summary: str = Field(description="Summary of changes made")


class DiffProposal(BaseModel):
    """Proposed changes before application"""

    proposal_id: str = Field(description="Unique proposal identifier")
    summary: str = Field(description="High-level summary of all changes")
    explanation: str = Field(
        description="Detailed explanation of why these changes fix the issues"
    )
    files_changed: List[FileDiff] = Field(description="List of file diffs")
    total_files: int = Field(description="Total number of files to be changed")
    total_additions: int = Field(description="Total lines added across all files")
    total_deletions: int = Field(description="Total lines removed across all files")
    risk_assessment: Literal["low", "medium", "high"] = Field(
        description="Risk assessment"
    )
    safety_checks: List[str] = Field(
        description="Safety checks performed before proposing"
    )


class ApplyResult(BaseModel):
    """Result of applying changes"""

    files_updated: List[str] = Field(description="List of successfully updated files")
    files_failed: List[str] = Field(description="List of files that failed to update")
    success: bool = Field(description="Whether all changes were applied successfully")
    error_messages: List[str] = Field(
        default_factory=list, description="Error messages if any"
    )
    backup_created: bool = Field(
        default=False, description="Whether backups were created"
    )
    # Phase 4.3 additions
    session_id: Optional[str] = Field(
        default=None, description="Session ID for tracking changes"
    )
    backup_location: Optional[str] = Field(
        default=None, description="Location of backup files"
    )
    change_summary: str = Field(default="", description="Summary of changes applied")


class VerificationResult(BaseModel):
    """Result of verifying applied fixes"""

    remaining_issues: int = Field(description="Number of issues remaining after fix")
    resolved_issues: int = Field(description="Number of issues successfully resolved")
    new_issues: int = Field(default=0, description="Number of new issues introduced")
    status: Literal[
        "resolved", "partially_resolved", "failed", "introduced_new_issues"
    ] = Field(description="Overall verification status")
    verification_details: str = Field(description="Detailed verification report")
    next_steps: List[str] = Field(
        default_factory=list, description="Suggested next steps if needed"
    )
    # Phase 4.3 additions
    success: bool = Field(description="Whether verification passed")
    message: str = Field(description="Verification message")
    remaining_issues_list: List[Any] = Field(
        default_factory=list,
        alias="remaining_issues_data",
        description="Detailed remaining issues",
    )
    new_issues_detected: List[Any] = Field(
        default_factory=list, description="List of new issues detected"
    )
    files_verified: List[str] = Field(
        default_factory=list, description="List of files that were verified"
    )


class ExecutionResult(BaseModel):
    """Final result of task execution"""

    task_id: str = Field(description="ID of the executed task")
    status: ExecutionStatus = Field(description="Final execution status")
    analysis: Optional[AnalysisResult] = Field(
        default=None, description="Analysis results"
    )
    plan: Optional[FixPlan] = Field(default=None, description="Fix plan generated")
    proposal: Optional[DiffProposal] = Field(
        default=None, description="Diff proposal created"
    )
    apply_result: Optional[ApplyResult] = Field(
        default=None, description="Application results"
    )
    verification: Optional[VerificationResult] = Field(
        default=None, description="Verification results"
    )
    workflow_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Phase 4.4 workflow results"
    )
    execution_time_ms: int = Field(description="Total execution time in milliseconds")
    user_approved: bool = Field(
        default=False, description="Whether user approved the changes"
    )
    final_report: str = Field(description="Final human-readable report")
    success: bool = Field(description="Overall success status")
