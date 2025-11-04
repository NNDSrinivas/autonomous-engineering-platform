"""Service layer for AI feedback operations."""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ai_feedback import AiFeedback, AiGenerationLog


class FeedbackService:
    """Service for managing AI feedback operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_generation(
        self,
        org_key: str,
        user_sub: str,
        task_type: str,
        model: str,
        temperature: float,
        params: Dict,
        prompt: str,
        input_fingerprint: Optional[str] = None,
        result_ref: Optional[str] = None,
    ) -> int:
        """Log an AI generation request and return the log ID."""
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:64]

        log_entry = AiGenerationLog(
            org_key=org_key,
            user_sub=user_sub,
            task_type=task_type,
            input_fingerprint=input_fingerprint,
            model=model,
            temperature=temperature,
            params=params,
            prompt_hash=prompt_hash,
            result_ref=result_ref,
        )

        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry.id  # type: ignore[return-value]

    async def submit_feedback(
        self,
        gen_id: int,
        org_key: str,
        user_sub: str,
        rating: int,
        reason: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """Submit feedback for a generation. Returns True if successful."""
        # Verify the generation exists and belongs to the user/org
        gen_result = await self.session.execute(
            select(AiGenerationLog).where(AiGenerationLog.id == gen_id)
        )
        gen_log = gen_result.scalar_one_or_none()

        if gen_log is None:
            return False
        if str(gen_log.org_key) != str(org_key):
            return False

        # Check if feedback already exists for this user/generation
        existing_result = await self.session.execute(
            select(AiFeedback).where(
                and_(
                    AiFeedback.gen_id == gen_id,
                    AiFeedback.user_sub == user_sub,
                )
            )
        )
        if existing_result.scalar_one_or_none():
            return False  # Already submitted feedback

        feedback = AiFeedback(
            gen_id=gen_id,
            org_key=org_key,
            user_sub=user_sub,
            rating=rating,
            reason=reason,
            comment=comment,
        )

        self.session.add(feedback)
        await self.session.commit()
        return True

    async def get_feedback_stats(
        self,
        org_key: str,
        days: int = 30,
    ) -> Dict:
        """Get aggregated feedback statistics for an organization."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get basic stats
        total_gen_result = await self.session.execute(
            select(func.count(AiGenerationLog.id)).where(
                and_(
                    AiGenerationLog.org_key == org_key,
                    AiGenerationLog.created_at >= cutoff_date,
                )
            )
        )
        total_generations = total_gen_result.scalar() or 0

        total_feedback_result = await self.session.execute(
            select(func.count(AiFeedback.id)).where(
                and_(
                    AiFeedback.org_key == org_key,
                    AiFeedback.created_at >= cutoff_date,
                )
            )
        )
        total_feedback = total_feedback_result.scalar() or 0

        # Get rating distribution
        rating_result = await self.session.execute(
            select(AiFeedback.rating, func.count(AiFeedback.id))
            .where(
                and_(
                    AiFeedback.org_key == org_key,
                    AiFeedback.created_at >= cutoff_date,
                )
            )
            .group_by(AiFeedback.rating)
        )

        ratings = {rating: count for rating, count in rating_result}

        # Get reason distribution
        reason_result = await self.session.execute(
            select(AiFeedback.reason, func.count(AiFeedback.id))
            .where(
                and_(
                    AiFeedback.org_key == org_key,
                    AiFeedback.created_at >= cutoff_date,
                    AiFeedback.reason.isnot(None),
                )
            )
            .group_by(AiFeedback.reason)
        )

        reasons = {reason: count for reason, count in reason_result}

        return {
            "total_generations": total_generations,
            "total_feedback": total_feedback,
            "feedback_rate": (
                round(total_feedback / total_generations * 100, 1)
                if total_generations > 0
                else 0.0
            ),
            "rating_distribution": ratings,
            "reason_distribution": reasons,
            "period_days": days,
        }

    async def get_recent_feedback(
        self,
        org_key: str,
        limit: int = 50,
    ) -> List[Dict]:
        """Get recent feedback entries with generation context."""
        results = await self.session.execute(
            select(
                AiFeedback.id,
                AiFeedback.rating,
                AiFeedback.reason,
                AiFeedback.comment,
                AiFeedback.created_at,
                AiGenerationLog.task_type,
                AiGenerationLog.model,
                AiGenerationLog.temperature,
            )
            .join(AiGenerationLog, AiFeedback.gen_id == AiGenerationLog.id)
            .where(AiFeedback.org_key == org_key)
            .order_by(AiFeedback.created_at.desc())
            .limit(limit)
        )

        return [
            {
                "id": row[0],
                "rating": row[1],
                "reason": row[2],
                "comment": row[3],
                "created_at": row[4].isoformat(),
                "task_type": row[5],
                "model": row[6],
                "temperature": row[7],
            }
            for row in results
        ]
