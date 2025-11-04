"""Contextual bandit learning system for AI parameter optimization."""

import random
from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np

from backend.infra.cache.redis_cache import cache


class ThompsonSamplingBandit:
    """Contextual bandit using Thompson Sampling for AI parameter selection."""

    CACHE_PREFIX = "bandit"
    CONTEXT_EXPIRY = 3600 * 24 * 7  # 7 days

    def __init__(self, org_key: str):
        self.org_key = org_key
        self.cache = cache

    def _get_context_key(self, context: Dict) -> str:
        """Generate a consistent cache key for a context."""
        # Create a simplified context fingerprint
        fingerprint_parts = [
            context.get("task_type", "unknown"),
            str(context.get("input_size_bucket", "small")),  # small/medium/large
            context.get("user_experience", "standard"),  # novice/standard/expert
        ]
        fingerprint = "_".join(fingerprint_parts)
        return f"{self.CACHE_PREFIX}:{self.org_key}:{fingerprint}"

    async def _get_arm_stats(self, context_key: str, arm: str) -> Tuple[float, float]:
        """Get success/failure counts for an arm in a context."""
        key = f"{context_key}:arm:{arm}"
        data = await self.cache.get_json(key)

        if data:
            return data.get("successes", 0.0), data.get("failures", 0.0)
        return 1.0, 1.0  # Start with uniform prior

    async def _update_arm_stats(
        self, context_key: str, arm: str, success: bool
    ) -> None:
        """Update success/failure counts for an arm."""
        key = f"{context_key}:arm:{arm}"
        successes, failures = await self._get_arm_stats(context_key, arm)

        if success:
            successes += 1
        else:
            failures += 1

        stats = {"successes": successes, "failures": failures}
        await self.cache.set_json(key, stats, ttl_sec=self.CONTEXT_EXPIRY)

    async def select_parameters(self, context: Dict) -> Dict:
        """Select AI parameters using Thompson Sampling."""
        context_key = self._get_context_key(context)

        # Define arms (parameter combinations)
        arms = [
            {"model": "gpt-4o-mini", "temperature": 0.1, "name": "precise"},
            {"model": "gpt-4o-mini", "temperature": 0.3, "name": "balanced"},
            {"model": "gpt-4o-mini", "temperature": 0.7, "name": "creative"},
        ]

        # Sample from beta distributions for each arm
        arm_scores = []
        for arm in arms:
            successes, failures = await self._get_arm_stats(context_key, arm["name"])

            # Thompson Sampling: sample from Beta(successes, failures)
            if successes + failures >= 2:  # Have some data (including prior)
                score = np.random.beta(successes, failures)
            else:
                score = random.random()  # Fallback for very sparse data

            arm_scores.append((score, arm))

        # Select arm with highest sampled score
        selected_arm = max(arm_scores, key=lambda x: x[0])[1]

        # Add selection metadata
        return {
            **selected_arm,
            "_bandit_context": context_key,
            "_bandit_arm": selected_arm["name"],
        }

    async def record_feedback(self, context_key: str, arm: str, rating: int) -> None:
        """Record feedback for bandit learning."""
        # Convert rating to success/failure
        # +1 (thumbs up) = success, 0 or -1 = failure
        success = rating > 0
        await self._update_arm_stats(context_key, arm, success)

    async def get_arm_performance(self, context: Dict) -> Dict[str, Dict]:
        """Get performance statistics for all arms in a context."""
        context_key = self._get_context_key(context)

        arms = ["precise", "balanced", "creative"]
        performance = {}

        for arm in arms:
            successes, failures = await self._get_arm_stats(context_key, arm)
            total = successes + failures

            performance[arm] = {
                "successes": successes,
                "failures": failures,
                "total_trials": total,
                "success_rate": successes / total if total > 0 else 0.0,
                "confidence": min(total / 20.0, 1.0),  # Confidence in estimate
            }

        return performance


class LearningService:
    """Service for managing contextual bandit learning."""

    def __init__(self):
        self.cache = cache

    def get_bandit(self, org_key: str) -> ThompsonSamplingBandit:
        """Get a bandit instance for an organization."""
        return ThompsonSamplingBandit(org_key)

    def extract_context(
        self, task_type: str, input_text: str, user_role: Optional[str] = None
    ) -> Dict:
        """Extract relevant context features for bandit selection."""
        # Categorize input size
        input_length = len(input_text.split())
        if input_length < 50:
            size_bucket = "small"
        elif input_length < 200:
            size_bucket = "medium"
        else:
            size_bucket = "large"

        # Map user role to experience level
        experience_map = {
            "admin": "expert",
            "developer": "expert",
            "user": "standard",
            None: "standard",
        }

        return {
            "task_type": task_type,
            "input_size_bucket": size_bucket,
            "user_experience": experience_map.get(user_role, "standard"),
        }

    async def get_learning_stats(self, org_key: str) -> Dict:
        """Get overall learning statistics for an organization."""
        bandit = self.get_bandit(org_key)

        # Get stats for common contexts
        contexts = [
            {
                "task_type": "codegen",
                "input_size_bucket": "small",
                "user_experience": "standard",
            },
            {
                "task_type": "codegen",
                "input_size_bucket": "medium",
                "user_experience": "standard",
            },
            {
                "task_type": "codegen",
                "input_size_bucket": "large",
                "user_experience": "standard",
            },
        ]

        context_stats = {}
        for context in contexts:
            context_name = f"{context['task_type']}_{context['input_size_bucket']}"
            context_stats[context_name] = await bandit.get_arm_performance(context)

        return {
            "org_key": org_key,
            "contexts": context_stats,
            "last_updated": datetime.utcnow().isoformat(),
        }
