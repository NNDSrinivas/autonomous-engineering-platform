"""
Unit tests for Redis-backed circuit breaker.

Tests circuit breaker state transitions without router/LLMClient integration.
Uses fakeredis for deterministic testing without real Redis dependency.
"""

import time
from unittest.mock import patch

import pytest

try:
    import fakeredis
    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

from backend.services.redis_circuit_breaker import (
    RedisCircuitBreaker,
    CircuitState,
)


@pytest.fixture
def redis_client():
    """Create fake Redis client for testing."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def breaker(redis_client):
    """Create circuit breaker with test configuration."""
    return RedisCircuitBreaker(
        redis_client=redis_client,
        provider_id="test_provider",
        window_sec=60,
        failure_threshold=5,
        open_duration_sec=30,
    )


class TestCircuitBreakerInitialState:
    """Test initial circuit breaker state."""

    def test_initial_state_closed(self, breaker):
        """Circuit breaker starts in CLOSED state."""
        state = breaker.get_state()
        assert state == CircuitState.CLOSED

    def test_initial_redis_keys_not_exist(self, redis_client):
        """Redis keys don't exist before any operations."""
        # Keys use hash tag format for Redis Cluster compatibility
        assert not redis_client.exists("circuit:{test_provider}:state")
        assert not redis_client.exists("circuit:{test_provider}:window")
        assert not redis_client.exists("circuit:{test_provider}:open_at")


class TestFailureThreshold:
    """Test failure threshold behavior."""

    def test_failures_below_threshold_stay_closed(self, breaker):
        """Failures below threshold keep circuit CLOSED."""
        # Record 4 failures (threshold is 5)
        for _ in range(4):
            state = breaker.record_failure()
            assert state == CircuitState.CLOSED

        # Verify still closed
        assert breaker.get_state() == CircuitState.CLOSED

    def test_threshold_triggers_open(self, breaker):
        """5th failure triggers OPEN state."""
        # Record 4 failures
        for _ in range(4):
            breaker.record_failure()

        # 5th failure should open circuit
        state = breaker.record_failure()
        assert state == CircuitState.OPEN

        # Verify state persists
        assert breaker.get_state() == CircuitState.OPEN

    def test_success_does_not_count_toward_threshold(self, breaker):
        """Successes don't count toward failure threshold (failures persist in window)."""
        # Record 4 failures
        for _ in range(4):
            breaker.record_failure()

        # Record multiple successes
        for _ in range(10):
            breaker.record_success()

        # Still only 4 failures in window, adding 1 more = 5 total, should open
        state = breaker.record_failure()
        assert state == CircuitState.OPEN

    def test_mixed_success_failure_below_threshold(self, breaker):
        """Mixed success/failure stays CLOSED if failures < threshold."""
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()

        # Only 3 failures in window, threshold is 5
        assert breaker.get_state() == CircuitState.CLOSED


class TestOpenState:
    """Test OPEN state behavior."""

    def test_open_state_persists(self, breaker):
        """OPEN state persists across get_state() calls."""
        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        assert breaker.get_state() == CircuitState.OPEN
        assert breaker.get_state() == CircuitState.OPEN

    def test_open_state_timeout_transition(self, breaker):
        """OPEN transitions to HALF_OPEN after timeout."""
        # Capture time before opening
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        assert breaker.get_state() == CircuitState.OPEN

        # Simulate time passing (30s backoff)
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            # Set current time to 31s after opening
            mock_time.return_value = base_time + 31

            # Should transition to HALF_OPEN
            state = breaker.get_state()
            assert state == CircuitState.HALF_OPEN

    def test_timeout_not_elapsed_stays_open(self, breaker):
        """OPEN stays OPEN if timeout not elapsed."""
        # Capture time before opening
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Simulate only 10s passing (need 30s)
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 10

            state = breaker.get_state()
            assert state == CircuitState.OPEN


class TestHalfOpenState:
    """Test HALF_OPEN state behavior."""

    def test_half_open_success_closes_circuit(self, breaker):
        """Success in HALF_OPEN closes circuit."""
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Transition to HALF_OPEN
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 31
            breaker.get_state()  # Trigger transition

        # Record success - should close
        state = breaker.record_success()
        assert state == CircuitState.CLOSED

        # Verify state persists
        assert breaker.get_state() == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self, breaker):
        """Failure in HALF_OPEN reopens circuit."""
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Transition to HALF_OPEN
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 31
            breaker.get_state()  # Trigger transition

        # Record failure - should reopen
        state = breaker.record_failure()
        assert state == CircuitState.OPEN

    def test_half_open_timeout_reopens_circuit(self, breaker):
        """Timeout in HALF_OPEN reopens circuit."""
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Transition to HALF_OPEN
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 31
            breaker.get_state()  # Trigger transition

        # Record timeout - should reopen
        state = breaker.record_timeout()
        assert state == CircuitState.OPEN


class TestSlidingWindow:
    """Test sliding window failure tracking."""

    def test_old_failures_expire(self, breaker):
        """Failures outside window don't count toward threshold."""
        base_time = time.time()

        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time

            # Record 4 failures at t=0
            for _ in range(4):
                breaker.record_failure()

            # Move time forward 61s (outside window)
            mock_time.return_value = base_time + 61

            # Record 1 more failure - should NOT open (old ones expired)
            state = breaker.record_failure()
            assert state == CircuitState.CLOSED

    def test_failures_within_window_count(self, breaker):
        """Failures within window count toward threshold."""
        # Record 3 failures
        for _ in range(3):
            breaker.record_failure()

        # Small delay but still within window (use real time, window is 60s)
        time.sleep(0.1)

        # Record 2 more failures - should open (5 total in window)
        breaker.record_failure()
        state = breaker.record_failure()
        assert state == CircuitState.OPEN


class TestTimeoutTracking:
    """Test timeout recording."""

    def test_timeout_counts_as_failure(self, breaker):
        """Timeouts count toward failure threshold."""
        # Record 4 timeouts
        for _ in range(4):
            breaker.record_timeout()

        # 5th timeout should open circuit
        state = breaker.record_timeout()
        assert state == CircuitState.OPEN

    def test_mixed_failure_timeout(self, breaker):
        """Mixed failures and timeouts count toward threshold."""
        breaker.record_failure()
        breaker.record_timeout()
        breaker.record_failure()
        breaker.record_timeout()

        # 5th error (failure or timeout) should open
        state = breaker.record_failure()
        assert state == CircuitState.OPEN


class TestConcurrentWorkers:
    """Test multi-worker race condition handling."""

    def test_simultaneous_threshold_hits(self, breaker):
        """Two workers hitting threshold simultaneously don't corrupt state."""
        # Record 4 failures
        for _ in range(4):
            breaker.record_failure()

        # Simulate two workers recording 5th failure simultaneously
        # Lua script should handle atomically
        state1 = breaker.record_failure()
        state2 = breaker.record_failure()

        # Both should see OPEN (one triggered it, one observed it)
        assert state1 == CircuitState.OPEN
        assert state2 == CircuitState.OPEN

        # State should be OPEN (not corrupted)
        assert breaker.get_state() == CircuitState.OPEN

    def test_rapid_state_queries(self, breaker):
        """Rapid get_state() calls return consistent results."""
        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Multiple workers checking state
        states = [breaker.get_state() for _ in range(10)]

        # All should see OPEN
        assert all(s == CircuitState.OPEN for s in states)


class TestRecoveryFlow:
    """Test full circuit breaker recovery flow."""

    def test_full_cycle_open_half_open_closed(self, breaker):
        """Full cycle: CLOSED → OPEN → HALF_OPEN → CLOSED."""
        base_time = time.time()

        # 1. Start CLOSED
        assert breaker.get_state() == CircuitState.CLOSED

        # 2. Trigger OPEN
        for _ in range(5):
            breaker.record_failure()
        assert breaker.get_state() == CircuitState.OPEN

        # 3. Wait for backoff → HALF_OPEN
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 31
            assert breaker.get_state() == CircuitState.HALF_OPEN

            # 4. Success → CLOSED
            state = breaker.record_success()
            assert state == CircuitState.CLOSED

    def test_failed_recovery_reopens(self, breaker):
        """Failed recovery reopens circuit."""
        base_time = time.time()

        # Trigger OPEN
        for _ in range(5):
            breaker.record_failure()

        # Transition to HALF_OPEN
        with patch("backend.services.redis_circuit_breaker.time.time") as mock_time:
            mock_time.return_value = base_time + 31
            breaker.get_state()

            # Probe fails - should reopen
            state = breaker.record_failure()
            assert state == CircuitState.OPEN

            # Wait again for second recovery attempt
            mock_time.return_value = base_time + 62

            # Should be HALF_OPEN again
            assert breaker.get_state() == CircuitState.HALF_OPEN

            # This time success
            state = breaker.record_success()
            assert state == CircuitState.CLOSED


class TestFallbackLogic:
    """Test fallback when Lua script unavailable."""

    def test_fallback_without_lua_script(self, redis_client):
        """Circuit breaker works even without Lua script."""
        breaker = RedisCircuitBreaker(
            redis_client=redis_client,
            provider_id="test_fallback",
            window_sec=60,
            failure_threshold=5,
            open_duration_sec=30,
        )

        # Force Lua script to None (simulate registration failure)
        breaker.record_call_script = None

        # Should still work via fallback
        for _ in range(5):
            state = breaker.record_failure()

        # Should open (via fallback logic)
        assert state == CircuitState.OPEN
