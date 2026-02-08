"""Service layer for AI feedback operations."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import logging

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.utils.hashing import sha256_hash
from backend.models.ai_feedback import AiFeedback, AiGenerationLog, TaskType

# Learning system integration
from backend.services.feedback_learning import (
    get_feedback_manager,
    FeedbackType,
    SuggestionCategory,
)

# Cache valid task type values for performance
VALID_TASK_TYPES = frozenset(t.value for t in TaskType)

logger = logging.getLogger(__name__)


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
        # Validate task type
        if task_type not in VALID_TASK_TYPES:
            raise ValueError(
                f"Invalid task_type: {task_type}. Must be one of: {list(VALID_TASK_TYPES)}"
            )

        prompt_hash = sha256_hash(prompt)

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

    def _validate_user_match(self, field_value: Any, expected_value: str) -> bool:
        """Helper method to validate user field matches with consistent string conversion."""
        return field_value is not None and str(field_value) == str(expected_value)

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
        if not self._validate_user_match(gen_log.org_key, org_key):
            return False
        if not self._validate_user_match(gen_log.user_sub, user_sub):
            return False  # Only the original requester can provide feedback

        # Check if feedback already exists for this user/generation
        existing_result = await self.session.execute(
            select(AiFeedback).where(
                and_(
                    AiFeedback.gen_id == gen_id,
                    AiFeedback.user_sub == user_sub,
                    AiFeedback.org_key == org_key,  # Add org_key filter for efficiency
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

        # Bridge to learning system: Convert rating to feedback type
        try:
            await self._bridge_to_learning_system(
                gen_id, gen_log, rating, reason, comment
            )
        except Exception as e:
            logger.warning("Failed to bridge feedback to learning system: %s", e)

        return True

    async def _bridge_to_learning_system(
        self,
        gen_id: int,
        gen_log: AiGenerationLog,
        rating: int,
        reason: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        """
        Bridge rating-based feedback to the learning system.
        Converts 1-5 star ratings into accept/reject feedback.
        """
        # Convert rating to feedback type
        if rating >= 4:
            feedback_type = FeedbackType.ACCEPTED
        elif rating == 3:
            feedback_type = FeedbackType.ACCEPTED_MODIFIED
        else:  # rating <= 2
            feedback_type = FeedbackType.REJECTED

        # Map task type to suggestion category
        category_map = {
            "chat": SuggestionCategory.EXPLANATION,
            "code_generation": SuggestionCategory.FILE_CREATE,
            "code_edit": SuggestionCategory.FILE_EDIT,
            "code_review": SuggestionCategory.REFACTOR,
            "debug": SuggestionCategory.FIX,
            "test": SuggestionCategory.TEST,
            "documentation": SuggestionCategory.DOCUMENTATION,
        }
        category = category_map.get(gen_log.task_type, SuggestionCategory.EXPLANATION)

        # Get the learning manager
        learning_manager = get_feedback_manager()

        # Record the feedback to the learning system
        learning_manager.record_user_feedback(
            suggestion_id=str(gen_id),
            feedback_type=feedback_type,
            original_content="",  # Not tracked in current system
            reason=reason or comment,
            org_id=gen_log.org_key,
            user_id=gen_log.user_sub,
        )

        logger.info(
            f"[FeedbackService] Bridged feedback to learning system: "
            f"gen_id={gen_id}, rating={rating} → {feedback_type.value}"
        )

        # Also persist to database for v1 analytics and history
        try:
            from backend.models.learning_data import LearningSuggestion

            # Persist raw org/user identifiers so non-numeric IDs (OIDC sub, UUIDs, etc.)
            # are not dropped for learning analytics
            suggestion = LearningSuggestion(
                org_id=gen_log.org_key,
                user_id=gen_log.user_sub,
                category=category.value,
                suggestion_text=f"AI generation (task_type: {gen_log.task_type})",
                context=gen_log.params if gen_log.params else {},
                feedback_type=feedback_type.value,
                rating=rating,
                reason=reason,
                comment=comment,
                model_used=gen_log.model,
                gen_id=gen_id,
            )

            self.session.add(suggestion)
            await self.session.commit()
            logger.debug(
                "[FeedbackService] 💾 Persisted learning suggestion to database"
            )
        except Exception as e:
            logger.warning(f"Failed to persist learning suggestion to database: {e}")
            # Rollback to keep session usable after failed commit
            try:
                await self.session.rollback()
            except Exception as rollback_error:
                logger.error(
                    f"Failed to rollback after persist error: {rollback_error}"
                )
            # Don't fail the feedback submission if DB persistence fails

    async def get_feedback_stats(
        self,
        org_key: str,
        days: int = 30,
    ) -> Dict:
        """Get aggregated feedback statistics for an organization."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

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
