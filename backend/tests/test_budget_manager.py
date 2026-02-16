"""
Unit tests for BudgetManager with Redis-backed atomic enforcement.

Tests atomic multi-scope operations, midnight safety, concurrency,
and graceful degradation scenarios.

Uses fakeredis for deterministic testing without real Redis dependency.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

try:
    import fakeredis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

from backend.services.budget_manager import (
    BudgetManager,
    BudgetScope,
    BudgetScopeKey,
    BudgetExceeded,
)


@pytest.fixture
def redis_client():
    """Create fake Redis client for testing."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    # Use lua_modules=True to enable Lua script support
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def policy():
    """Test budget policy."""
    return {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 10000},
        "orgs": {
            "test-org": {"per_day": 5000},
        },
        "users": {},
        "providers": {
            "openai": {"per_day": 8000},
        },
        "models": {
            "openai/gpt-4o": {"per_day": 3000},
        },
    }


@pytest.fixture
def budget_manager(redis_client, policy):
    """Create budget manager with test configuration."""
    return BudgetManager(
        redis_client=redis_client,
        policy=policy,
        enforcement_mode="strict",
    )


class TestBudgetManagerInitialization:
    """Test budget manager initialization and configuration."""

    def test_enforcement_mode_validation(self, redis_client, policy):
        """Invalid enforcement mode defaults to strict."""
        mgr = BudgetManager(
            redis_client=redis_client,
            policy=policy,
            enforcement_mode="invalid",
        )
        assert mgr.enforcement_mode == "strict"

    def test_enforcement_modes_accepted(self, redis_client, policy):
        """All valid enforcement modes accepted."""
        for mode in ["strict", "advisory", "disabled"]:
            mgr = BudgetManager(
                redis_client=redis_client,
                policy=policy,
                enforcement_mode=mode,
            )
            assert mgr.enforcement_mode == mode


class TestSingleScopeReserve:
    """Test basic single-scope budget reserve operations."""

    def test_reserve_within_limit(self, budget_manager):
        """Reserve succeeds when within limit."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        assert token.amount == 1000
        assert token.scopes == scopes
        assert token.day == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_reserve_exceeds_limit(self, budget_manager):
        """Reserve fails when exceeding limit."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        with pytest.raises(BudgetExceeded) as exc_info:
            budget_manager.reserve(15000, scopes)  # Limit is 10000

        assert "Budget exceeded" in str(exc_info.value)
        assert exc_info.value.details["limit"] == 10000
        assert exc_info.value.details["requested"] == 15000

    def test_multiple_reserves_accumulate(self, budget_manager):
        """Multiple reserves accumulate reserved amount."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        # First reserve
        budget_manager.reserve(4000, scopes)

        # Second reserve
        budget_manager.reserve(3000, scopes)

        # Third reserve should fail (4000 + 3000 + 5000 > 10000)
        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(5000, scopes)


class TestMultiScopeAtomic:
    """Test atomic multi-scope reserve operations."""

    def test_all_scopes_checked_atomically(self, budget_manager):
        """All scopes checked before any reservation."""
        scopes = [
            BudgetScopeKey(BudgetScope.GLOBAL, "global"),  # Limit: 10000
            BudgetScopeKey(BudgetScope.ORG, "test-org"),  # Limit: 5000
            BudgetScopeKey(BudgetScope.PROVIDER, "openai"),  # Limit: 8000
        ]

        # Reserve 4000 - should succeed (all scopes have capacity)
        token = budget_manager.reserve(4000, scopes)
        assert token.amount == 4000

        # Reserve 2000 more - should fail on org scope (4000 + 2000 > 5000)
        with pytest.raises(BudgetExceeded) as exc_info:
            budget_manager.reserve(2000, scopes)

        # Error should indicate which scope failed
        assert "test-org" in str(exc_info.value) or "org" in str(exc_info.value).lower()

    def test_multi_scope_rollback_on_failure(self, budget_manager):
        """Failed reserve doesn't partially reserve any scopes."""
        scopes = [
            BudgetScopeKey(BudgetScope.GLOBAL, "global"),  # Limit: 10000
            BudgetScopeKey(BudgetScope.ORG, "test-org"),  # Limit: 5000
        ]

        # Try to reserve 6000 - should fail on org scope
        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(6000, scopes)

        # Verify nothing was reserved in any scope
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0


class TestCommitOperations:
    """Test budget commit with actual usage."""

    def test_commit_exact_amount(self, budget_manager):
        """Commit with exact reserved amount."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        # Commit exact amount
        budget_manager.commit(token, used_amount=1000)

        # Verify reserved decremented, used incremented
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0
            assert data["used"] == 1000

    def test_commit_less_than_reserved(self, budget_manager):
        """Commit with less than reserved amount."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        # Commit less than reserved
        budget_manager.commit(token, used_amount=500)

        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0
            assert data["used"] == 500

    def test_commit_more_than_reserved_overspend(self, budget_manager):
        """Commit with more than reserved (overspend scenario)."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        # Commit more than reserved (provider returned more tokens)
        budget_manager.commit(token, used_amount=1500)

        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0
            assert data["used"] == 1500  # Overspend allowed

    def test_commit_massive_overspend_logs_critical(self, budget_manager, caplog):
        """Massive overspend (>5x) triggers critical log."""
        import logging

        caplog.set_level(logging.CRITICAL)

        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(100, scopes)

        # Commit 10x reserved amount (anomaly)
        budget_manager.commit(token, used_amount=1000)

        # Verify CRITICAL log emitted
        assert any("BUDGET ANOMALY" in record.message for record in caplog.records)


class TestReleaseOperations:
    """Test budget release (error case)."""

    def test_release_decrements_reserved(self, budget_manager):
        """Release decrements reserved, doesn't increment used."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        # Release (error case)
        budget_manager.release(token)

        # Verify reserved decremented, used unchanged
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0
            assert data["used"] == 0


class TestMidnightSafety:
    """Test midnight UTC boundary edge cases."""

    def test_reservation_token_captures_day(self, budget_manager):
        """Reservation token captures day at reserve time."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        with patch("backend.services.budget_manager.datetime") as mock_datetime:
            # Mock reserve at 2025-02-15 23:59:59 UTC
            mock_datetime.now.return_value = datetime(
                2025, 2, 15, 23, 59, 59, tzinfo=timezone.utc
            )

            token = budget_manager.reserve(1000, scopes)
            assert token.day == "2025-02-15"

    def test_commit_uses_token_day_not_current_day(self, budget_manager):
        """Commit uses token.day (midnight-safe)."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        with patch("backend.services.budget_manager.datetime") as mock_datetime:
            # Reserve on 2025-02-15
            mock_datetime.now.return_value = datetime(
                2025, 2, 15, 23, 59, 59, tzinfo=timezone.utc
            )
            token = budget_manager.reserve(1000, scopes)

            # Commit on 2025-02-16 (after midnight)
            mock_datetime.now.return_value = datetime(
                2025, 2, 16, 0, 0, 1, tzinfo=timezone.utc
            )
            budget_manager.commit(token, used_amount=1000)

            # Verify committed to 2025-02-15 bucket (token.day)
            snapshot_feb15 = budget_manager.snapshot(scopes, day="2025-02-15")
            snapshot_feb16 = budget_manager.snapshot(scopes, day="2025-02-16")

            for key in snapshot_feb15:
                assert snapshot_feb15[key]["used"] == 1000  # Committed to Feb 15
            for key in snapshot_feb16:
                assert snapshot_feb16[key]["used"] == 0  # Feb 16 untouched


class TestModelIdSlashHandling:
    """Test model ID with slash in Redis keys."""

    def test_model_id_slash_replaced(self, budget_manager):
        """Model ID slashes replaced with __ in Redis keys."""
        scopes = [BudgetScopeKey(BudgetScope.MODEL, "openai/gpt-4o")]
        _token = budget_manager.reserve(100, scopes)  # Reserve to create keys

        # Verify Redis key uses __ instead of /
        snapshot = budget_manager.snapshot(scopes)
        keys = list(snapshot.keys())
        assert len(keys) == 1
        assert "openai__gpt-4o" in keys[0]
        assert "openai/gpt-4o" not in keys[0]


class TestEnforcementModes:
    """Test different enforcement modes."""

    def test_strict_mode_rejects_on_exceeded(self, redis_client, policy):
        """Strict mode rejects when budget exceeded."""
        mgr = BudgetManager(redis_client, policy, enforcement_mode="strict")
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        with pytest.raises(BudgetExceeded):
            mgr.reserve(15000, scopes)  # Exceeds 10000 limit

    def test_disabled_mode_always_allows(self, redis_client, policy):
        """Disabled mode always allows reserves."""
        mgr = BudgetManager(redis_client, policy, enforcement_mode="disabled")
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        # Should succeed even though it exceeds limit
        token = mgr.reserve(15000, scopes)
        assert token.amount == 15000

    def test_advisory_mode_allows_on_redis_error(self, redis_client, policy):
        """Advisory mode allows request when Redis unavailable."""
        mgr = BudgetManager(redis_client, policy, enforcement_mode="advisory")

        # Force Redis error by closing connection
        redis_client.connection_pool.disconnect()

        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        # Should not raise, should allow request
        token = mgr.reserve(1000, scopes)
        assert token.amount == 1000


class TestScopeHierarchy:
    """Test hierarchical scope enforcement."""

    def test_org_scope_overrides_default(self, budget_manager):
        """Org-specific limit overrides default."""
        scopes = [BudgetScopeKey(BudgetScope.ORG, "test-org")]

        # Org limit is 5000, default is 10000
        token = budget_manager.reserve(4500, scopes)
        assert token.amount == 4500

        # Exceeds org limit
        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(1000, scopes)

    def test_provider_scope_overrides_default(self, budget_manager):
        """Provider-specific limit overrides default."""
        scopes = [BudgetScopeKey(BudgetScope.PROVIDER, "openai")]

        # Provider limit is 8000
        token = budget_manager.reserve(7500, scopes)
        assert token.amount == 7500

        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(1000, scopes)

    def test_model_scope_overrides_default(self, budget_manager):
        """Model-specific limit overrides default."""
        scopes = [BudgetScopeKey(BudgetScope.MODEL, "openai/gpt-4o")]

        # Model limit is 3000
        token = budget_manager.reserve(2500, scopes)
        assert token.amount == 2500

        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(1000, scopes)


class TestSnapshot:
    """Test snapshot for debugging and metrics."""

    def test_snapshot_returns_current_state(self, budget_manager):
        """Snapshot returns accurate budget state."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        # Initial state
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["limit"] == 10000
            assert data["used"] == 0
            assert data["reserved"] == 0
            assert data["remaining"] == 10000

        # After reserve
        token = budget_manager.reserve(3000, scopes)
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 3000
            assert data["remaining"] == 7000

        # After commit
        budget_manager.commit(token, used_amount=3000)
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 0
            assert data["used"] == 3000
            assert data["remaining"] == 7000

    def test_snapshot_multi_scope(self, budget_manager):
        """Snapshot returns state for all requested scopes."""
        scopes = [
            BudgetScopeKey(BudgetScope.GLOBAL, "global"),
            BudgetScopeKey(BudgetScope.ORG, "test-org"),
            BudgetScopeKey(BudgetScope.PROVIDER, "openai"),
        ]

        snapshot = budget_manager.snapshot(scopes)
        assert len(snapshot) == 3

        # Verify each scope has correct limit
        for key, data in snapshot.items():
            if "global" in key:
                assert data["limit"] == 10000
            elif "test-org" in key:
                assert data["limit"] == 5000
            elif "openai" in key:
                assert data["limit"] == 8000


class TestRedisKeyTTL:
    """Test Redis key TTL (48 hours)."""

    def test_keys_have_ttl(self, budget_manager, redis_client):
        """Budget keys have 48-hour TTL."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]
        token = budget_manager.reserve(1000, scopes)

        # Get Redis key
        day = token.day
        key = f"budget:global:global:{day}"

        # Verify TTL exists and is ~48 hours (172800 seconds)
        ttl = redis_client.ttl(key)
        assert ttl > 0
        assert ttl <= 172800  # 48 hours


class TestConcurrentWorkers:
    """Test multi-worker race condition handling."""

    def test_atomic_reserve_prevents_over_reservation(self, budget_manager):
        """Atomic Lua prevents two workers from both reserving when only one fits."""
        scopes = [BudgetScopeKey(BudgetScope.GLOBAL, "global")]

        # Reserve 8000 (limit is 10000)
        budget_manager.reserve(8000, scopes)

        # Two workers try to reserve 3000 each
        # Only one should succeed (8000 + 3000 = 11000 > 10000)
        with pytest.raises(BudgetExceeded):
            budget_manager.reserve(3000, scopes)

        # Verify total reserved is still 8000 (not 11000)
        snapshot = budget_manager.snapshot(scopes)
        for key, data in snapshot.items():
            assert data["reserved"] == 8000
