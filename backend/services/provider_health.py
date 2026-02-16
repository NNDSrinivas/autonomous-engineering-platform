"""
Provider health tracking with circuit breakers and Prometheus metrics.

Integrates:
- RedisCircuitBreaker for multi-worker state sharing
- Prometheus metrics for observability
- Error type classification
"""

import logging

import redis

from backend.services.redis_circuit_breaker import CircuitState, RedisCircuitBreaker
from backend.telemetry.metrics import (
    PROVIDER_CALLS,
    PROVIDER_ERRORS,
    CIRCUIT_BREAKER_STATE,
)

logger = logging.getLogger(__name__)

# Allowlist for error_type to prevent unbounded Prometheus label cardinality
_ALLOWED_ERROR_TYPES = {"http", "timeout", "network", "rate_limit", "auth", "unknown"}


def _normalize_error_type(error_type: str) -> str:
    """Normalize error type to allowlist to prevent metric cardinality explosion."""
    return error_type if error_type in _ALLOWED_ERROR_TYPES else "unknown"


class ProviderHealthTracker:
    """
    Tracks provider health across all workers using Redis-backed circuit breakers.

    Usage:
        tracker = ProviderHealthTracker(redis_client)
        tracker.record_success("openai")
        tracker.record_failure("anthropic", "timeout")
        if tracker.is_circuit_open("openai"):
            # Block request
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        window_sec: int = 60,
        failure_threshold: int = 5,
        open_duration_sec: int = 30,
    ):
        """
        Initialize provider health tracker.

        Args:
            redis_client: Shared Redis client
            window_sec: Sliding window for failure tracking (default 60s)
            failure_threshold: Failures to trigger circuit open (default 5)
            open_duration_sec: How long to stay open before half-open probe (default 30s)
        """
        self.redis = redis_client
        self.window_sec = window_sec
        self.failure_threshold = failure_threshold
        self.open_duration_sec = open_duration_sec

        # Lazy-initialized circuit breakers per provider
        self._breakers: dict[str, RedisCircuitBreaker] = {}

    def _get_breaker(self, provider_id: str) -> RedisCircuitBreaker:
        """Get or create circuit breaker for provider"""
        if provider_id not in self._breakers:
            self._breakers[provider_id] = RedisCircuitBreaker(
                redis_client=self.redis,
                provider_id=provider_id,
                window_sec=self.window_sec,
                failure_threshold=self.failure_threshold,
                open_duration_sec=self.open_duration_sec,
            )
        return self._breakers[provider_id]

    def record_success(self, provider_id: str) -> None:
        """Record successful provider call"""
        try:
            breaker = self._get_breaker(provider_id)
            new_state = breaker.record_success()

            # Update Prometheus metrics
            PROVIDER_CALLS.labels(provider=provider_id, status="success").inc()
            self._update_circuit_state_metric(provider_id, new_state)

            logger.debug(f"Provider {provider_id} success, circuit={new_state.name}")

        except Exception as e:
            logger.error(
                f"Error recording success for {provider_id}: {e}", exc_info=True
            )

    def record_failure(self, provider_id: str, error_type: str = "unknown") -> None:
        """
        Record provider failure.

        Args:
            provider_id: Provider identifier
            error_type: Error classification (http|timeout|network|rate_limit|auth|unknown)
        """
        try:
            breaker = self._get_breaker(provider_id)
            # Get previous state to detect transitions
            prev_state = breaker.get_state()
            new_state = breaker.record_failure()

            # Normalize error_type to prevent unbounded label cardinality
            normalized_error = _normalize_error_type(error_type)

            # Update Prometheus metrics
            PROVIDER_CALLS.labels(provider=provider_id, status="error").inc()
            PROVIDER_ERRORS.labels(
                provider=provider_id, error_type=normalized_error
            ).inc()
            self._update_circuit_state_metric(provider_id, new_state)

            # Log only on state transitions to reduce noise
            if prev_state != new_state:
                logger.warning(
                    f"Provider {provider_id} circuit transition: "
                    f"{prev_state.name} → {new_state.name} (error_type={normalized_error})"
                )
            else:
                logger.debug(
                    f"Provider {provider_id} failure (type={normalized_error}), "
                    f"circuit={new_state.name}"
                )

        except Exception as e:
            logger.error(
                f"Error recording failure for {provider_id}: {e}", exc_info=True
            )

    def record_timeout(self, provider_id: str) -> None:
        """Record provider timeout (treated as failure)"""
        try:
            breaker = self._get_breaker(provider_id)
            # Get previous state to detect transitions
            prev_state = breaker.get_state()
            new_state = breaker.record_timeout()

            # Update Prometheus metrics
            PROVIDER_CALLS.labels(provider=provider_id, status="timeout").inc()
            PROVIDER_ERRORS.labels(provider=provider_id, error_type="timeout").inc()
            self._update_circuit_state_metric(provider_id, new_state)

            # Log only on state transitions to reduce noise
            if prev_state != new_state:
                logger.warning(
                    f"Provider {provider_id} circuit transition: "
                    f"{prev_state.name} → {new_state.name} (timeout)"
                )
            else:
                logger.debug(
                    f"Provider {provider_id} timeout, circuit={new_state.name}"
                )

        except Exception as e:
            logger.error(
                f"Error recording timeout for {provider_id}: {e}", exc_info=True
            )

    def is_circuit_open(self, provider_id: str) -> bool:
        """
        Check if circuit breaker is OPEN (blocking requests).

        Returns:
            True if circuit is OPEN, False otherwise (CLOSED or HALF_OPEN)
        """
        try:
            breaker = self._get_breaker(provider_id)
            state = breaker.get_state()

            # Update gauge to reflect time-based transitions (OPEN → HALF_OPEN)
            self._update_circuit_state_metric(provider_id, state)

            # HALF_OPEN allows single probe request, so return False
            return state == CircuitState.OPEN

        except Exception as e:
            logger.error(
                f"Error checking circuit state for {provider_id}: {e}", exc_info=True
            )
            # Fail-open on error: allow requests
            return False

    def get_circuit_state(self, provider_id: str) -> CircuitState:
        """Get current circuit state for provider"""
        try:
            breaker = self._get_breaker(provider_id)
            return breaker.get_state()
        except Exception as e:
            logger.error(
                f"Error getting circuit state for {provider_id}: {e}", exc_info=True
            )
            return CircuitState.CLOSED

    def _update_circuit_state_metric(
        self, provider_id: str, state: CircuitState
    ) -> None:
        """Update Prometheus gauge for circuit breaker state"""
        try:
            CIRCUIT_BREAKER_STATE.labels(provider=provider_id).set(state.value)
        except Exception as e:
            logger.error(f"Error updating circuit state metric: {e}", exc_info=True)
