"""
Safety Types - Phase 4.5

Type definitions for enterprise safety and rollback system.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class RollbackTrigger(str, Enum):
    """Triggers that can initiate a rollback"""
    USER_REQUEST = "user_request"  # User clicked Undo button
    CI_FAILURE = "ci_failure"      # CI failure worse than baseline
    TOOL_EXCEPTION = "tool_exception"  # Tool execution exception
    LOW_CONFIDENCE = "low_confidence"  # Confidence below threshold
    SAFETY_OVERRIDE = "safety_override"  # Manual safety override
    

class SafetyStatus(str, Enum):
    """Safety status of current operations"""
    SAFE = "safe"                    # All operations safe
    AT_RISK = "at_risk"              # Operations have some risk
    REQUIRES_ROLLBACK = "requires_rollback"  # Immediate rollback needed
    ROLLING_BACK = "rolling_back"    # Currently rolling back
    RESTORED = "restored"            # Successfully restored to safe state
    

class FileState(BaseModel):
    """State of a single file for rollback"""
    path: str = Field(description="File path relative to workspace")
    content: str = Field(description="File content at snapshot time")
    last_modified: datetime = Field(description="Last modification time")
    permissions: Optional[str] = Field(default=None, description="File permissions")
    checksum: str = Field(description="Content checksum for integrity")
    

class GitState(BaseModel):
    """Git repository state for rollback"""
    current_branch: str = Field(description="Current git branch")
    commit_sha: Optional[str] = Field(default=None, description="Current commit SHA")
    is_clean: bool = Field(description="Whether working directory is clean")
    remote_url: Optional[str] = Field(default=None, description="Remote repository URL")
    uncommitted_changes: List[str] = Field(default_factory=list, description="List of uncommitted files")
    

class SnapshotMetadata(BaseModel):
    """Metadata for a safety snapshot"""
    snapshot_id: str = Field(description="Unique snapshot identifier")
    created_at: datetime = Field(description="Snapshot creation time")
    operation: str = Field(description="Operation that triggered snapshot")
    trigger: str = Field(description="What triggered this snapshot")
    workspace_path: str = Field(description="Workspace root path")
    file_count: int = Field(description="Number of files in snapshot")
    total_size_bytes: int = Field(description="Total size of snapshot in bytes")
    description: str = Field(description="Human-readable snapshot description")
    

class RollbackResult(BaseModel):
    """Result of a rollback operation"""
    success: bool = Field(description="Whether rollback was successful")
    trigger: RollbackTrigger = Field(description="What triggered the rollback")
    files_restored: List[str] = Field(description="List of files successfully restored")
    files_failed: List[str] = Field(default_factory=list, description="List of files that failed to restore")
    git_restored: bool = Field(description="Whether git state was restored")
    duration_ms: int = Field(description="Rollback operation duration in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error message if rollback failed")
    final_status: SafetyStatus = Field(description="Final safety status after rollback")
    

class SafetyReport(BaseModel):
    """Comprehensive safety report for webview"""
    current_status: SafetyStatus = Field(description="Current safety status")
    snapshot_available: bool = Field(description="Whether a rollback snapshot is available")
    snapshot_age_minutes: Optional[int] = Field(default=None, description="Age of latest snapshot in minutes")
    risk_factors: List[str] = Field(default_factory=list, description="Current risk factors")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended safety actions")
    can_rollback: bool = Field(description="Whether rollback is currently possible")
    rollback_scope: List[str] = Field(default_factory=list, description="What would be rolled back")