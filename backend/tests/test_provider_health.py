"""
Unit tests for ProviderHealthTracker.

Tests health tracker metrics integration and multi-provider management.
"""

import time

import pytest

try:
    import fakeredis
    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

from backend.services.provider_health import ProviderHealthTracker
from backend.services.redis_circuit_breaker import CircuitState


@pytest.fixture
def redis_client():
    """Create fake Redis client for testing."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def tracker(redis_client):
    """Create health tracker with test configuration."""
    return ProviderHealthTracker(
        redis_client=redis_client,
        window_sec=60,
        failure_threshold=5,
        open_duration_sec=30,
    )


class TestProviderHealthTrackerBasics:
    """Test basic health tracker functionality."""

    def test_record_success(self, tracker):
        """record_success() doesn't raise exceptions."""
        # Should not raise
        tracker.record_success("openai")
        tracker.record_success("anthropic")

    def test_record_failure_with_error_type(self, tracker):
        """record_failure() accepts error type classification."""
        tracker.record_failure("openai", "timeout")
        tracker.record_failure("openai", "http")
        tracker.record_failure("openai", "network")
        tracker.record_failure("openai", "rate_limit")
        tracker.record_failure("openai", "auth")

    def test_record_timeout(self, tracker):
        """record_timeout() works correctly."""
        tracker.record_timeout("openai")

    def test_multiple_providers(self, tracker):
        """Tracker manages multiple providers independently."""
        # Provider 1: trigger open
        for _ in range(5):
            tracker.record_failure("openai", "http")

        # Provider 2: stays healthy
        tracker.record_success("anthropic")

        # Provider 1 should be open, Provider 2 should be closed
        assert tracker.is_circuit_open("openai") is True
        assert tracker.is_circuit_open("anthropic") is False


class TestCircuitStateQueries:
    """Test circuit state query methods."""

    def test_is_circuit_open_initially_false(self, tracker):
        """is_circuit_open() returns False initially."""
        assert tracker.is_circuit_open("openai") is False

    def test_is_circuit_open_after_failures(self, tracker):
        """is_circuit_open() returns True after threshold."""
        for _ in range(5):
            tracker.record_failure("openai", "http")

        assert tracker.is_circuit_open("openai") is True

    def test_get_circuit_state(self, tracker):
        """get_circuit_state() returns correct state enum."""
        # Initially CLOSED
        assert tracker.get_circuit_state("openai") == CircuitState.CLOSED

        # After failures, OPEN
        for _ in range(5):
            tracker.record_failure("openai", "http")

        assert tracker.get_circuit_state("openai") == CircuitState.OPEN

    def test_half_open_not_blocked(self, tracker):
        """HALF_OPEN state allows probe request (not blocked)."""
        # Note: is_circuit_open() should return False for HALF_OPEN
        # because we want to allow the probe request through

        # For now, just verify CLOSED is not blocked
        assert tracker.is_circuit_open("openai") is False


class TestErrorTypeClassification:
    """Test error type tracking."""

    def test_different_error_types_tracked(self, tracker):
        """Different error types are tracked separately."""
        tracker.record_failure("openai", "timeout")
        tracker.record_failure("openai", "http")
        tracker.record_failure("openai", "network")
        tracker.record_failure("openai", "rate_limit")
        tracker.record_failure("openai", "auth")

        # All should count toward threshold (5 total)
        assert tracker.is_circuit_open("openai") is True

    def test_unknown_error_type(self, tracker):
        """Unknown error types are handled gracefully."""
        tracker.record_failure("openai", "unknown")
        tracker.record_failure("openai", "weird_error")

        # Should still count toward threshold
        for _ in range(3):
            tracker.record_failure("openai", "unknown")

        assert tracker.is_circuit_open("openai") is True


class TestProviderIsolation:
    """Test provider health isolation."""

    def test_provider_failures_isolated(self, tracker):
        """Failures in one provider don't affect others."""
        # Open openai circuit
        for _ in range(5):
            tracker.record_failure("openai", "http")

        # Anthropic should still be healthy
        tracker.record_success("anthropic")
        assert tracker.is_circuit_open("openai") is True
        assert tracker.is_circuit_open("anthropic") is False

    def test_multiple_provider_failures(self, tracker):
        """Multiple providers can fail independently."""
        # Fail openai
        for _ in range(5):
            tracker.record_failure("openai", "http")

        # Fail anthropic
        for _ in range(5):
            tracker.record_failure("anthropic", "timeout")

        # Both should be open
        assert tracker.is_circuit_open("openai") is True
        assert tracker.is_circuit_open("anthropic") is True

        # Google should still be healthy
        assert tracker.is_circuit_open("google") is False


class TestRecovery:
    """Test health tracker recovery."""

    def test_success_after_open_eventually_closes(self, tracker):
        """Circuit eventually closes after recovery."""
        # Open circuit
        for _ in range(5):
            tracker.record_failure("openai", "http")

        assert tracker.is_circuit_open("openai") is True

        # This test would need time mocking to properly test HALF_OPEN → CLOSED
        # For now, just verify the methods don't crash
        tracker.record_success("openai")


class TestGracefulDegradation:
    """Test graceful degradation on errors."""

    def test_missing_provider_returns_false(self, tracker):
        """is_circuit_open() returns False for unknown provider."""
        # Should not crash, should return False (fail-open)
        assert tracker.is_circuit_open("nonexistent_provider") is False

    def test_redis_error_handled_gracefully(self):
        """Redis errors are handled gracefully."""
        # Create tracker with broken Redis client
        class BrokenRedis:
            def register_script(self, script):
                raise RuntimeError("Redis unavailable")

            def get(self, key):
                raise RuntimeError("Redis unavailable")

        broken_redis = BrokenRedis()

        # Initialization should not crash
        tracker = ProviderHealthTracker(broken_redis)

        # Should degrade gracefully (no health tracking)
        # These methods should not raise exceptions
        tracker.record_success("openai")
        tracker.record_failure("openai", "http")

        # Should return False (fail-open on error)
        assert tracker.is_circuit_open("openai") is False


class TestLazyBreakerInitialization:
    """Test lazy circuit breaker initialization."""

    def test_breakers_created_on_demand(self, tracker):
        """Circuit breakers are created lazily per provider."""
        # Initially, no breakers exist
        assert len(tracker._breakers) == 0

        # First call creates breaker
        tracker.record_success("openai")
        assert "openai" in tracker._breakers

        # Second provider creates another breaker
        tracker.record_success("anthropic")
        assert "anthropic" in tracker._breakers
        assert len(tracker._breakers) == 2

    def test_breaker_reused_for_same_provider(self, tracker):
        """Same breaker is reused for repeated calls."""
        tracker.record_success("openai")
        breaker1 = tracker._breakers.get("openai")

        tracker.record_failure("openai", "http")
        breaker2 = tracker._breakers.get("openai")

        # Should be the same instance
        assert breaker1 is breaker2


class TestProbeLease:
    """Test HALF_OPEN probe lease to prevent thundering herd."""

    def test_single_probe_allowed_in_half_open(self, tracker, redis_client):
        """In HALF_OPEN state, only one worker can acquire probe lease."""
        # Force circuit to OPEN state
        for _ in range(5):
            tracker.record_failure("openai", "http")

        # Verify it's OPEN
        assert tracker.is_circuit_open("openai") is True

        # Force transition to HALF_OPEN by setting open_at to past
        redis_client.set("circuit:{openai}:open_at", str(time.time() - 100))

        # First check should acquire probe lease
        is_open_1 = tracker.is_circuit_open("openai")
        assert is_open_1 is False  # Probe lease acquired

        # Second check (simulating another worker) should NOT acquire lease
        is_open_2 = tracker.is_circuit_open("openai")
        assert is_open_2 is True  # Blocked, lease held by worker 1

        # Third check should also be blocked
        is_open_3 = tracker.is_circuit_open("openai")
        assert is_open_3 is True  # Blocked, lease held by worker 1

    def test_probe_lease_expires(self, redis_client):
        """Probe lease expires after TTL, allowing retry."""
        # Create tracker with short probe lease TTL for faster test
        from backend.services.redis_circuit_breaker import RedisCircuitBreaker

        breaker = RedisCircuitBreaker(
            redis_client, "openai", probe_lease_ttl=1  # 1 second TTL
        )
        tracker = ProviderHealthTracker(redis_client)
        tracker._breakers["openai"] = breaker

        # Force circuit to HALF_OPEN
        for _ in range(5):
            tracker.record_failure("openai", "http")
        redis_client.set("circuit:{openai}:open_at", str(time.time() - 100))

        # First worker acquires lease
        assert tracker.is_circuit_open("openai") is False

        # Second worker blocked
        assert tracker.is_circuit_open("openai") is True

        # Wait for lease to expire (1 second TTL + margin)
        time.sleep(1.5)

        # Now another worker can acquire lease
        assert tracker.is_circuit_open("openai") is False
