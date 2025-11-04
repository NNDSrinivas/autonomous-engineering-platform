"""API router for AI feedback and learning endpoints."""

from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.deps import get_current_user, require_role
from backend.core.database import get_db_session
from backend.schemas.ai_feedback import (
    FeedbackSubmission,
    FeedbackResponse, 
    FeedbackStats,
    RecentFeedbackResponse,
    LearningStats,
)
from backend.services.feedback_service import FeedbackService
from backend.services.learning_service import LearningService


router = APIRouter(prefix="/feedback", tags=["AI Feedback"])


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackSubmission,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    """Submit feedback for an AI generation."""
    service = FeedbackService(session)
    
    success = await service.submit_feedback(
        gen_id=feedback.gen_id,
        org_key=current_user["org_key"],
        user_sub=current_user["sub"],
        rating=feedback.rating,
        reason=feedback.reason,
        comment=feedback.comment,
    )
    
    if not success:
        return FeedbackResponse(
            success=False,
            message="Feedback could not be submitted. Generation not found or feedback already exists."
        )
    
    # Update bandit learning if we have bandit metadata
    if feedback.rating != 0:  # Only learn from explicit feedback
        learning_service = LearningService()
        bandit = learning_service.get_bandit(current_user["org_key"])
        
        # Try to get bandit context from a related generation (would need to be stored)
        # For now, we'll record feedback without full context
        
    await session.commit()
    
    return FeedbackResponse(
        success=True,
        message="Feedback submitted successfully"
    )


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    days: int = 30,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackStats:
    """Get feedback statistics for the organization."""
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365"
        )
    
    service = FeedbackService(session)
    stats = await service.get_feedback_stats(
        org_key=current_user["org_key"],
        days=days,
    )
    
    return FeedbackStats(**stats)


@router.get("/recent", response_model=RecentFeedbackResponse)
async def get_recent_feedback(
    limit: int = 50,
    current_user: Dict = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> RecentFeedbackResponse:
    """Get recent feedback entries (admin only)."""
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 200"
        )
    
    service = FeedbackService(session)
    feedback_list = await service.get_recent_feedback(
        org_key=current_user["org_key"],
        limit=limit,
    )
    
    return RecentFeedbackResponse(
        feedback=feedback_list,
        total_count=len(feedback_list)
    )


@router.get("/learning", response_model=LearningStats)
async def get_learning_stats(
    current_user: Dict = Depends(require_role("admin")),
) -> LearningStats:
    """Get contextual bandit learning statistics (admin only)."""
    learning_service = LearningService()
    stats = await learning_service.get_learning_stats(current_user["org_key"])
    
    return LearningStats(**stats)