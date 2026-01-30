# backend/models/review.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class ReviewIssue(BaseModel):
    """A specific issue found during code review"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: str = Field(..., description="error, warning, info, style")
    title: str = Field(..., description="Brief issue title")
    message: str = Field(..., description="Detailed issue description")
    suggestion: Optional[str] = Field(None, description="Suggested fix")
    line_number: Optional[int] = Field(None, description="Line number if applicable")
    fix_patch: Optional[str] = Field(
        None, description="Auto-fix patch in unified diff format"
    )
    can_auto_fix: bool = Field(
        default=False, description="Whether this issue can be auto-fixed"
    )

    @property
    def type(self) -> str:
        """Compatibility alias for legacy tests."""
        return self.title

    @property
    def description(self) -> str:
        """Compatibility alias for legacy tests."""
        return self.message


class ReviewEntry(BaseModel):
    """Review result for a single file"""

    file: str = Field(..., description="File path")
    diff: str = Field(..., description="Git diff for this file")
    content: Optional[str] = Field(None, description="Current file content")
    issues: List[ReviewIssue] = Field(default_factory=list)
    file_type: Optional[str] = Field(None, description="File extension/type")
    status: Optional[str] = Field(None, description="Git status (M, A, D, etc.)")

    class Config:
        json_encoders = {
            # Ensure proper JSON serialization
        }

    @property
    def path(self) -> str:
        """Compatibility alias for legacy tests."""
        return self.file


class ReviewSummary(BaseModel):
    """Overall review summary"""

    total_files: int
    total_issues: int
    issues_by_severity: Dict[str, int] = Field(default_factory=dict)
    files_with_issues: int = 0
    auto_fixable_issues: int = 0


class StreamingReviewEvent(BaseModel):
    """Event sent via SSE during streaming review"""

    event_type: str = Field(..., description="progress, review_entry, error, done")
    data: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = Field(None, description="Human readable message")
    progress: Optional[float] = Field(None, description="Progress percentage 0-100")


class ReviewProgress(BaseModel):
    """Progress tracking for review operations"""

    current_file: Optional[str] = None
    files_processed: int = 0
    total_files: int = 0
    current_step: str = "Starting..."

    @property
    def progress_percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return min(100.0, (self.files_processed / self.total_files) * 100)
