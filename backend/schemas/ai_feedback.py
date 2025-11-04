"""Pydantic schemas for AI feedback endpoints."""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FeedbackSubmission(BaseModel):
    """Schema for submitting feedback on AI generations."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )

    gen_id: int = Field(..., description="Generation log ID")
    rating: int = Field(
        ...,
        ge=-1,
        le=1,
        description="Feedback rating: -1 (negative/thumbs down), 0 (neutral), 1 (positive/thumbs up)",
    )
    reason: Optional[str] = Field(
        None, max_length=64, description="Feedback reason category"
    )
    comment: Optional[str] = Field(
        None, max_length=1000, description="Optional feedback comment"
    )


class FeedbackResponse(BaseModel):
    """Response schema for feedback submission."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(
        ..., description="Whether feedback was submitted successfully"
    )
    message: str = Field(..., description="Response message")


class FeedbackStats(BaseModel):
    """Schema for feedback statistics."""

    model_config = ConfigDict(frozen=True)

    total_generations: int = Field(..., description="Total generations in period")
    total_feedback: int = Field(..., description="Total feedback received")
    feedback_rate: float = Field(..., description="Feedback rate percentage")
    rating_distribution: Dict[int, int] = Field(
        ..., description="Rating counts by value"
    )
    reason_distribution: Dict[str, int] = Field(
        ..., description="Reason counts by category"
    )
    period_days: int = Field(..., description="Period in days")


class FeedbackEntry(BaseModel):
    """Schema for individual feedback entry."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Feedback ID")
    rating: int = Field(..., description="Feedback rating")
    reason: Optional[str] = Field(None, description="Feedback reason")
    comment: Optional[str] = Field(None, description="Feedback comment")
    created_at: str = Field(..., description="Creation timestamp")
    task_type: str = Field(..., description="AI task type")
    model: str = Field(..., description="AI model used")
    temperature: float = Field(..., description="Temperature used")


class RecentFeedbackResponse(BaseModel):
    """Response schema for recent feedback list."""

    model_config = ConfigDict(frozen=True)

    feedback: List[FeedbackEntry] = Field(..., description="List of recent feedback")
    total_count: int = Field(..., description="Total feedback count")


class LearningStats(BaseModel):
    """Schema for contextual bandit learning statistics."""

    model_config = ConfigDict(frozen=True)

    org_key: str = Field(..., description="Organization key")
    contexts: Dict[str, Dict] = Field(..., description="Context performance data")
    last_updated: str = Field(..., description="Last update timestamp")


class ArmPerformance(BaseModel):
    """Schema for individual arm performance."""

    model_config = ConfigDict(frozen=True)

    successes: float = Field(..., description="Success count")
    failures: float = Field(..., description="Failure count")
    total_trials: float = Field(..., description="Total trials")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level")


class ContextPerformance(BaseModel):
    """Schema for context-level performance data."""

    model_config = ConfigDict(frozen=True)

    precise: ArmPerformance = Field(..., description="Precise arm performance")
    balanced: ArmPerformance = Field(..., description="Balanced arm performance")
    creative: ArmPerformance = Field(..., description="Creative arm performance")
