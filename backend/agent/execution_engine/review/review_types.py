"""
Review Types - Phase 4.6

Type definitions for PR comment auto-fix system.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class CommentType(str, Enum):
    """Types of PR comments that can be classified"""
    NULL_SAFETY = "null_safety"          # Null/undefined safety issues
    STYLE = "style"                      # Code style and formatting
    NAMING = "naming"                    # Variable/function naming
    LOGIC_ERROR = "logic_error"          # Logical errors in code
    PERFORMANCE = "performance"          # Performance concerns
    SECURITY = "security"                # Security issues
    TESTING = "testing"                  # Testing related comments
    DOCUMENTATION = "documentation"      # Documentation requests
    DISCUSSION = "discussion"            # General discussion/questions
    APPROVAL = "approval"                # Approval or positive feedback
    UNKNOWN = "unknown"                  # Cannot classify
    

class FixAction(str, Enum):
    """Actions that can be taken for PR comments"""
    CODE_FIX = "code_fix"                # Apply code changes
    REPLY_ONLY = "reply_only"            # Just reply to comment
    REQUEST_CLARIFICATION = "request_clarification"  # Ask for more info
    ESCALATE = "escalate"                # Escalate to human
    IGNORE = "ignore"                    # No action needed
    

class CommentClassification(BaseModel):
    """Result of classifying a PR comment"""
    comment_id: str = Field(description="ID of the comment")
    comment_type: CommentType = Field(description="Classified type of comment")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in classification")
    suggested_action: FixAction = Field(description="Suggested action to take")
    fixable: bool = Field(description="Whether this can be auto-fixed")
    priority: Literal["low", "medium", "high", "critical"] = Field(description="Priority level")
    reasoning: str = Field(description="Explanation of classification")
    keywords: List[str] = Field(default_factory=list, description="Keywords that influenced classification")
    

class ReviewContext(BaseModel):
    """Context for PR review and comment processing"""
    repository: str = Field(description="Repository name (owner/repo)")
    pr_number: int = Field(description="Pull request number")
    pr_title: str = Field(description="PR title")
    pr_body: str = Field(description="PR description")
    author: str = Field(description="PR author")
    files_changed: List[str] = Field(description="List of changed files")
    base_branch: str = Field(description="Base branch")
    head_branch: str = Field(description="Head branch")
    

class PrComment(BaseModel):
    """Representation of a PR comment"""
    id: str = Field(description="Comment ID")
    author: str = Field(description="Comment author")
    body: str = Field(description="Comment text")
    created_at: datetime = Field(description="When comment was created")
    updated_at: Optional[datetime] = Field(default=None, description="When comment was updated")
    file_path: Optional[str] = Field(default=None, description="File the comment is on")
    line_number: Optional[int] = Field(default=None, description="Line number for inline comments")
    is_resolved: bool = Field(default=False, description="Whether comment is resolved")
    reply_to: Optional[str] = Field(default=None, description="ID of parent comment if reply")
    

class FixResult(BaseModel):
    """Result of attempting to fix a PR comment"""
    comment_id: str = Field(description="ID of the comment being fixed")
    action_taken: FixAction = Field(description="Action that was taken")
    success: bool = Field(description="Whether the fix was successful")
    files_modified: List[str] = Field(default_factory=list, description="Files that were modified")
    changes_description: str = Field(description="Description of changes made")
    reply_message: Optional[str] = Field(default=None, description="Reply message posted")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the fix")
    requires_approval: bool = Field(default=True, description="Whether fix needs approval")
    

class AutoFixSummary(BaseModel):
    """Summary of auto-fix operations on a PR"""
    pr_number: int = Field(description="Pull request number")
    total_comments: int = Field(description="Total comments processed")
    comments_fixed: int = Field(description="Number of comments auto-fixed")
    comments_replied: int = Field(description="Number of comments replied to")
    comments_escalated: int = Field(description="Number of comments escalated")
    files_modified: List[str] = Field(description="Files modified by auto-fixes")
    success_rate: float = Field(ge=0.0, le=1.0, description="Success rate of fixes")
    processing_time_ms: int = Field(description="Total processing time")
    fixes_requiring_approval: int = Field(description="Number of fixes awaiting approval")