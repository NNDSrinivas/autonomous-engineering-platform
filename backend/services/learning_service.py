"""Contextual bandit learning system for AI parameter optimization."""

from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np

from backend.infra.cache.redis_cache import cache

# Configuration constants
# MIN_TRIALS_FOR_FULL_CONFIDENCE determines the number of trials required before the
# system considers its success rate estimates to be fully reliable for a given arm/context.
# The value 20 is chosen as a practical heuristic: it provides a reasonable balance between
# exploration (trying less-tested arms) and exploitation (favoring arms with higher observed success rates).
# With fewer than 20 trials, the confidence in the estimated success rate is scaled down,
# encouraging continued exploration. This threshold can be tuned based on application needs:
# increasing it makes the system more conservative (more exploration), while decreasing it
# leads to faster exploitation. See: Sutton & Barto, "Reinforcement Learning: An Introduction" (Section 2.4).
MIN_TRIALS_FOR_FULL_CONFIDENCE = (
    20  # Minimum trials to reach full confidence in estimates
)

# Input size thresholds for contextual bucketing
SMALL_INPUT_THRESHOLD = 50  # Words for small input classification
MEDIUM_INPUT_THRESHOLD = 200  # Words for medium input classification

# Beta distribution prior constants for Thompson Sampling
PRIOR_SUCCESSES = 1.0  # Beta distribution alpha parameter (successes prior)
PRIOR_FAILURES = 1.0   # Beta distribution beta parameter (failures prior)


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
        """Get success/failure counts for an arm in a context using Redis hash."""
        key = f"{context_key}:arm:{arm}"
        
        # Try Redis first for atomic operations
        if hasattr(self.cache, '_r') and self.cache._r:
            r = await self.cache._ensure()
            if r:
                # Use Redis hash for atomic counters
                data = await r.hgetall(key)
                if data:
                    # Redis returns strings, convert to float
                    successes = float(data.get("successes", PRIOR_SUCCESSES))
                    failures = float(data.get("failures", PRIOR_FAILURES))
                    return successes, failures
                # Use Beta(1,1) as the starting values for the Beta distribution.
                return PRIOR_SUCCESSES, PRIOR_FAILURES
        
        # Fallback to JSON cache (backwards compatibility)
        data = await self.cache.get_json(key)
        if data:
            return data.get("successes", PRIOR_SUCCESSES), data.get("failures", PRIOR_FAILURES)
        
        # Use Beta(1,1) as the starting values for the Beta distribution.
        # This represents a uniform prior, meaning we assume no initial preference
        # for success or failure. This is standard in Thompson Sampling to ensure
        # unbiased initial sampling and equal exploration of all arms.
        return PRIOR_SUCCESSES, PRIOR_FAILURES

    async def _update_arm_stats(
        self, context_key: str, arm: str, success: bool
    ) -> None:
        """Atomically update success/failure counts for an arm using Redis hash."""
        key = f"{context_key}:arm:{arm}"
        field = "successes" if success else "failures"
        
        # Try Redis atomic operations first
        if hasattr(self.cache, '_r') and self.cache._r:
            r = await self.cache._ensure()
            if r:
                # Atomically increment the appropriate field
                await r.hincrby(key, field, 1)
                # Set TTL if this is a new key (only if TTL not set)
                ttl = await r.ttl(key)
                if ttl == -1:
                    await r.expire(key, self.CONTEXT_EXPIRY)
                return
        
        # Fallback to non-atomic JSON operations (backwards compatibility)
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

            # Thompson Sampling: sample from Beta(successes, failures), where
            # successes and failures include the prior (initially 1.0 each).
            score = np.random.beta(successes, failures)

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
        # Only learn from explicit positive (+1) or negative (-1) feedback; ignore neutral (0)
        if rating == 0:
            return

        # Convert rating to success/failure: +1 = success, -1 = failure
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

            # Adjust for Beta(1,1) prior - subtract the initial counts for reporting
            actual_trials = max(0, int(total) - (PRIOR_SUCCESSES + PRIOR_FAILURES))
            actual_successes = max(0, int(successes) - PRIOR_SUCCESSES)

            performance[arm] = {
                "successes": int(actual_successes),
                "failures": int(max(0, failures - PRIOR_FAILURES)),
                "total_trials": actual_trials,
                "success_rate": (
                    actual_successes / actual_trials if actual_trials > 0 else None
                ),
                "confidence": min(
                    actual_trials / MIN_TRIALS_FOR_FULL_CONFIDENCE, 1.0
                ),  # Confidence in estimate
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
        if input_length < SMALL_INPUT_THRESHOLD:
            size_bucket = "small"
        elif input_length < MEDIUM_INPUT_THRESHOLD:
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

        # Generate common contexts dynamically to cover key usage patterns
        from backend.models.ai_feedback import TaskType

        contexts = []
        task_types = [t.value for t in TaskType]
        size_buckets = ["small", "medium", "large"]
        experience_levels = ["standard", "expert"]  # Support mapped experience levels

        # Generate contexts for all task types and sizes (starting with standard experience)
        for task_type in task_types:
            for size_bucket in size_buckets:
                for experience in experience_levels:
                    contexts.append(
                        {
                            "task_type": task_type,
                            "input_size_bucket": size_bucket,
                            "user_experience": experience,
                        }
                    )

        context_stats = {}
        for context in contexts:
            context_name = f"{context['task_type']}_{context['input_size_bucket']}"
            context_stats[context_name] = await bandit.get_arm_performance(context)

        return {
            "org_key": org_key,
            "contexts": context_stats,
            "last_updated": datetime.utcnow().isoformat(),
        }
