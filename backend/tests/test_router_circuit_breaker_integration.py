"""
Integration tests for circuit breaker + ModelRouter.

Tests that router correctly blocks routing when circuit breakers are open.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

try:
    import fakeredis
    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

from backend.services.model_router import ModelRouter
from backend.services.provider_health import ProviderHealthTracker
from backend.services.redis_circuit_breaker import CircuitState


@pytest.fixture
def mock_redis():
    """Create fake Redis client."""
    if not FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def mock_health_tracker(mock_redis):
    """Create health tracker with fake Redis."""
    return ProviderHealthTracker(
        redis_client=mock_redis,
        window_sec=60,
        failure_threshold=5,
        open_duration_sec=30,
    )


def _write_json(path: Path, obj: dict) -> None:
    """Helper to write JSON files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


@pytest.fixture
def minimal_router_with_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_health_tracker
):
    """Create minimal router with health tracker injected."""
    # Set up environment
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    # Create minimal registry
    legacy_path = tmp_path / "shared" / "model-registry.json"
    _write_json(
        legacy_path,
        {
            "version": "1.0.0",
            "defaults": {"defaultModeId": "navi/test"},
            "providers": [
                {
                    "id": "openai",
                    "type": "saas",
                    "models": [{"id": "openai/gpt-4o", "streaming": True}],
                },
                {
                    "id": "anthropic",
                    "type": "saas",
                    "models": [{"id": "anthropic/claude-sonnet-4", "streaming": True}],
                },
            ],
            "naviModes": [
                {
                    "id": "navi/test",
                    "candidateModelIds": ["openai/gpt-4o", "anthropic/claude-sonnet-4"],
                }
            ],
        },
    )

    # Create minimal facts registry
    facts_path = tmp_path / "shared" / "model-registry-dev.json"
    _write_json(
        facts_path,
        {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "openai/gpt-4o",
                    "provider": "openai",
                    "enabled": True,
                    "capabilities": ["chat", "streaming"],
                    "pricing": {"currency": "USD", "inputPer1KTokens": 0.0025, "outputPer1KTokens": 0.01},
                    "governance": {"tier": "standard", "allowedEnvironments": ["dev"]},
                    "limits": {"maxInputTokens": 128000, "maxOutputTokens": 16384},
                    "displayName": "GPT-4o",
                    "productionApproved": True,
                },
                {
                    "id": "anthropic/claude-sonnet-4",
                    "provider": "anthropic",
                    "enabled": True,
                    "capabilities": ["chat", "streaming"],
                    "pricing": {"currency": "USD", "inputPer1KTokens": 0.003, "outputPer1KTokens": 0.015},
                    "governance": {"tier": "standard", "allowedEnvironments": ["dev"]},
                    "limits": {"maxInputTokens": 200000, "maxOutputTokens": 8192},
                    "displayName": "Claude Sonnet 4",
                    "productionApproved": True,
                },
            ],
        },
    )

    monkeypatch.setenv("MODEL_REGISTRY_PATH", str(facts_path))

    # Create router
    router = ModelRouter(registry_path=legacy_path)

    # Inject health tracker (replace the one created in __init__)
    router.health_tracker = mock_health_tracker

    return router, mock_health_tracker


class TestCircuitBreakerRouting:
    """Test circuit breaker integration with routing decisions."""

    def test_closed_circuit_allows_routing(self, minimal_router_with_health):
        """CLOSED circuit allows normal routing."""
        router, health_tracker = minimal_router_with_health

        # Verify circuit is closed
        assert health_tracker.is_circuit_open("openai") is False

        # Routing should work
        routable, reason = router._is_model_routable_with_reason(
            "openai/gpt-4o",
            "stream",
            {"openai", "anthropic"},
            strict_private=False,
        )

        assert routable is True
        assert reason is None

    def test_open_circuit_blocks_routing(self, minimal_router_with_health):
        """OPEN circuit blocks routing with circuit_open reason."""
        router, health_tracker = minimal_router_with_health

        # Open openai circuit
        for _ in range(5):
            health_tracker.record_failure("openai", "http")

        assert health_tracker.is_circuit_open("openai") is True

        # Routing should be blocked
        routable, reason = router._is_model_routable_with_reason(
            "openai/gpt-4o",
            "stream",
            {"openai", "anthropic"},
            strict_private=False,
        )

        assert routable is False
        assert reason == "circuit_open"

    def test_other_providers_unaffected(self, minimal_router_with_health):
        """Opening one provider's circuit doesn't affect others."""
        router, health_tracker = minimal_router_with_health

        # Open openai circuit
        for _ in range(5):
            health_tracker.record_failure("openai", "http")

        # OpenAI should be blocked
        routable_openai, reason_openai = router._is_model_routable_with_reason(
            "openai/gpt-4o",
            "stream",
            {"openai", "anthropic"},
            strict_private=False,
        )
        assert routable_openai is False
        assert reason_openai == "circuit_open"

        # Anthropic should still work
        routable_anthropic, reason_anthropic = router._is_model_routable_with_reason(
            "anthropic/claude-sonnet-4",
            "stream",
            {"openai", "anthropic"},
            strict_private=False,
        )
        assert routable_anthropic is True
        assert reason_anthropic is None


class TestFallbackRouting:
    """Test fallback routing when primary provider circuit is open."""

    def test_routes_to_fallback_when_primary_open(self, minimal_router_with_health):
        """Router falls back to secondary provider when primary is open."""
        router, health_tracker = minimal_router_with_health

        # Open openai circuit (primary candidate)
        for _ in range(5):
            health_tracker.record_failure("openai", "http")

        # Route should fall back to anthropic
        decision = router.route("navi/test", "stream")

        assert decision.status == "ok"
        assert decision.selected_model == "anthropic/claude-sonnet-4"

        # Routability evaluation should show openai blocked
        openai_eval = next(
            (e for e in decision.routability_evaluation if e["model_id"] == "openai/gpt-4o"),
            None
        )
        assert openai_eval is not None
        assert openai_eval["routable"] is False
        assert openai_eval["reason"] == "circuit_open"


class TestHealthTrackerInitialization:
    """Test health tracker initialization in router."""

    def test_router_initializes_health_tracker(self, tmp_path, monkeypatch):
        """Router initializes health tracker on startup."""
        monkeypatch.setenv("APP_ENV", "dev")

        # Create minimal registry
        legacy_path = tmp_path / "shared" / "model-registry.json"
        _write_json(
            legacy_path,
            {
                "version": "1.0.0",
                "defaults": {"defaultModeId": "navi/test"},
                "providers": [{"id": "openai", "type": "saas", "models": [{"id": "openai/gpt-4o"}]}],
                "naviModes": [{"id": "navi/test", "candidateModelIds": ["openai/gpt-4o"]}],
            },
        )

        facts_path = tmp_path / "shared" / "model-registry-dev.json"
        _write_json(
            facts_path,
            {
                "schemaVersion": 1,
                "environment": "dev",
                "models": [
                    {
                        "id": "openai/gpt-4o",
                        "provider": "openai",
                        "enabled": True,
                        "capabilities": ["chat"],
                        "pricing": {"currency": "USD", "inputPer1KTokens": 0.0025, "outputPer1KTokens": 0.01},
                        "governance": {"tier": "standard", "allowedEnvironments": ["dev"]},
                        "limits": {"maxInputTokens": 128000, "maxOutputTokens": 16384},
                        "displayName": "GPT-4o",
                        "productionApproved": True,
                    }
                ],
            },
        )

        monkeypatch.setenv("MODEL_REGISTRY_PATH", str(facts_path))

        # Mock Redis to avoid real connection
        with patch("backend.services.model_router.redis.from_url") as mock_redis_from_url:
            mock_redis_from_url.return_value = Mock()

            router = ModelRouter(registry_path=legacy_path)

            # Health tracker should be initialized (might be None if Redis unavailable)
            # But should not crash
            assert hasattr(router, "health_tracker")


class TestGracefulDegradation:
    """Test graceful degradation when health tracking unavailable."""

    def test_router_works_without_health_tracker(self, tmp_path, monkeypatch):
        """Router works even if health tracker initialization fails."""
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("OPENAI_API_KEY", "test")

        # Create minimal registry
        legacy_path = tmp_path / "shared" / "model-registry.json"
        _write_json(
            legacy_path,
            {
                "version": "1.0.0",
                "defaults": {"defaultModeId": "navi/test"},
                "providers": [{"id": "openai", "type": "saas", "models": [{"id": "openai/gpt-4o", "streaming": True}]}],
                "naviModes": [{"id": "navi/test", "candidateModelIds": ["openai/gpt-4o"]}],
            },
        )

        facts_path = tmp_path / "shared" / "model-registry-dev.json"
        _write_json(
            facts_path,
            {
                "schemaVersion": 1,
                "environment": "dev",
                "models": [
                    {
                        "id": "openai/gpt-4o",
                        "provider": "openai",
                        "enabled": True,
                        "capabilities": ["chat", "streaming"],
                        "pricing": {"currency": "USD", "inputPer1KTokens": 0.0025, "outputPer1KTokens": 0.01},
                        "governance": {"tier": "standard", "allowedEnvironments": ["dev"]},
                        "limits": {"maxInputTokens": 128000, "maxOutputTokens": 16384},
                        "displayName": "GPT-4o",
                        "productionApproved": True,
                    }
                ],
            },
        )

        monkeypatch.setenv("MODEL_REGISTRY_PATH", str(facts_path))

        # Force health tracker to fail
        with patch("backend.services.model_router.redis.from_url") as mock_redis:
            mock_redis.side_effect = RuntimeError("Redis unavailable")

            router = ModelRouter(registry_path=legacy_path)

            # Health tracker should be None (graceful degradation)
            assert router.health_tracker is None

            # Routing should still work
            routable, reason = router._is_model_routable_with_reason(
                "openai/gpt-4o",
                "stream",
                {"openai"},
                strict_private=False,
            )

            assert routable is True
            assert reason is None

    def test_circuit_check_skipped_when_tracker_none(self, minimal_router_with_health):
        """Circuit check is skipped when health_tracker is None."""
        router, _ = minimal_router_with_health

        # Force health tracker to None
        router.health_tracker = None

        # Should still be routable (circuit check skipped)
        routable, reason = router._is_model_routable_with_reason(
            "openai/gpt-4o",
            "stream",
            {"openai"},
            strict_private=False,
        )

        assert routable is True
        assert reason is None
