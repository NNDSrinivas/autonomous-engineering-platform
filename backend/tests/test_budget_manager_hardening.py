"""
Unit tests for budget manager edge cases and hardening scenarios.

These tests verify critical budget enforcement invariants:
- Midnight boundary safety (token.day consistency)
- Overspend anomaly detection and logging
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.budget_manager import (
    BudgetManager,
    BudgetReservationToken,
    BudgetScope,
)


@pytest.mark.asyncio
async def test_midnight_boundary_commit_uses_token_day():
    """
    Test that commit uses token.day, not current day.

    This prevents midnight boundary issues where:
    - Reserve at 23:59:59 on 2025-02-15
    - Commit at 00:00:01 on 2025-02-16
    - Without token.day, commit would increment wrong day's bucket
    """
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=[1])  # Success

    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(mock_redis, enforcement_mode="strict", policy=policy)

    # Create token with explicit day (simulating reserve from yesterday)
    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]
    token = BudgetReservationToken(
        day="2025-02-15",  # Yesterday
        amount=5000,
        scopes=tuple(scopes),
    )

    # Current day is different (midnight has passed)
    with patch(
        "backend.services.budget_manager._utc_day_bucket", return_value="2025-02-16"
    ):
        await mgr.commit(token, 3000)

    # Verify commit used token.day (2025-02-15), not current day (2025-02-16)
    mock_redis.eval.assert_called_once()
    call_args = mock_redis.eval.call_args
    keys = call_args[0][2:]  # Skip script and num_keys

    # Key should contain token.day (2025-02-15)
    assert "2025-02-15" in keys[0]
    assert "2025-02-16" not in keys[0]


@pytest.mark.asyncio
async def test_midnight_boundary_release_uses_token_day():
    """
    Test that release uses token.day, not current day.

    Similar to commit test - ensures reserved tokens are decremented
    from the correct day's bucket even if midnight passes.
    """
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=[1])  # Success

    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(mock_redis, enforcement_mode="strict", policy=policy)

    # Create token with explicit day
    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]
    token = BudgetReservationToken(
        day="2025-02-15",
        amount=5000,
        scopes=tuple(scopes),
    )

    # Current day is different (midnight has passed)
    with patch(
        "backend.services.budget_manager._utc_day_bucket", return_value="2025-02-16"
    ):
        await mgr.release(token)

    # Verify release used token.day (2025-02-15)
    mock_redis.eval.assert_called_once()
    call_args = mock_redis.eval.call_args
    keys = call_args[0][2:]

    assert "2025-02-15" in keys[0]
    assert "2025-02-16" not in keys[0]


@pytest.mark.asyncio
async def test_overspend_anomaly_critical_log(caplog):
    """
    Test that massive overspend (>5x estimate) triggers CRITICAL log.

    Scenario:
    - Reserve 2500 tokens (estimate)
    - Provider returns 15000 tokens (6x overspend)
    - Should log CRITICAL anomaly
    - Should still commit actual usage (realistic: can't undo provider call)
    """
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=[1])

    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(mock_redis, enforcement_mode="strict", policy=policy)

    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]
    token = BudgetReservationToken(
        day="2025-02-15",
        amount=2500,  # Reserved 2500
        scopes=tuple(scopes),
    )

    with caplog.at_level(logging.CRITICAL):
        await mgr.commit(token, 15000)  # Actual 15000 (6x overspend)

    # Verify CRITICAL log was emitted
    critical_logs = [
        record for record in caplog.records if record.levelno == logging.CRITICAL
    ]
    assert len(critical_logs) > 0

    # Verify log contains overspend details
    log_message = critical_logs[0].message.lower()
    assert "overspend" in log_message or "anomaly" in log_message
    assert "15000" in log_message or "15,000" in log_message

    # Verify commit still proceeded (can't undo provider call)
    mock_redis.eval.assert_called_once()


@pytest.mark.asyncio
async def test_overspend_within_threshold_no_critical_log(caplog):
    """
    Test that moderate overspend (<5x) does NOT trigger CRITICAL log.

    Scenario:
    - Reserve 2500 tokens
    - Provider returns 8000 tokens (3.2x overspend)
    - Should log WARNING, not CRITICAL
    """
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=[1])

    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(mock_redis, enforcement_mode="strict", policy=policy)

    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]
    token = BudgetReservationToken(
        day="2025-02-15",
        amount=2500,
        scopes=tuple(scopes),
    )

    with caplog.at_level(logging.WARNING):
        await mgr.commit(token, 8000)  # 3.2x overspend (below 5x threshold)

    # Verify NO CRITICAL logs
    critical_logs = [
        record for record in caplog.records if record.levelno == logging.CRITICAL
    ]
    assert len(critical_logs) == 0

    # May have WARNING logs (acceptable, but not verified in this test)
    # Implementation may choose to log or not log warnings for moderate overspend


@pytest.mark.asyncio
async def test_reserve_captures_current_utc_day():
    """
    Test that reserve() captures current UTC day in token.

    This ensures token.day is always set at reserve time,
    which is then reused in commit/release for midnight safety.
    """
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=[1])

    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(mock_redis, enforcement_mode="strict", policy=policy)

    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]

    # Mock specific day
    fixed_day = "2025-02-15"
    with patch(
        "backend.services.budget_manager._utc_day_bucket", return_value=fixed_day
    ):
        token = await mgr.reserve(2500, scopes)

    # Verify token captured the mocked day
    assert token.day == fixed_day
    assert token.amount == 2500


@pytest.mark.asyncio
async def test_disabled_mode_with_none_redis():
    """
    Test that disabled mode works with None Redis client.

    Verifies the fix from Copilot review - BudgetManager should
    accept None redis_client in disabled/advisory modes.
    """
    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    # Create manager with None Redis (simulating Redis unavailable)
    mgr = BudgetManager(None, enforcement_mode="disabled", policy=policy)

    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]

    # All operations should succeed without touching Redis
    token = await mgr.reserve(2500, scopes)
    assert token.amount == 2500

    await mgr.commit(token, 2000)  # Should not raise
    await mgr.release(token)  # Should not raise


@pytest.mark.asyncio
async def test_advisory_mode_with_none_redis():
    """
    Test that advisory mode works with None Redis client.
    """
    policy = {
        "version": 1,
        "day_boundary": "UTC",
        "units": "tokens",
        "defaults": {"per_day": 1000000},
        "orgs": {},
        "providers": {},
        "models": {},
        "users": {},
    }

    mgr = BudgetManager(None, enforcement_mode="advisory", policy=policy)

    scopes = [BudgetScope(scope="global", scope_id="global", per_day_limit=1000000)]

    # Reserve should succeed in advisory mode even without Redis
    token = await mgr.reserve(2500, scopes)
    assert token.amount == 2500
