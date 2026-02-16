"""
Phase 2 unit tests: Policy evaluation, cost estimation, and routability with Phase 1 facts.

Tests the Phase 2 enhancements to ModelRouter:
- Facts loading and merging (pricing, tier, capabilities, factsEnabled)
- Provider mismatch sanity check
- Cost estimation from Phase 1 pricing metadata
- Policy evaluation (capability/tier/provider/cost constraints)
- Enhanced routability evaluation with reason codes
- Dual-layer evaluation (policy → routability → selection)
"""

import json
from pathlib import Path
import pytest

from backend.services.model_router import ModelRouter, ModelRoutingError


class TestPhase2FactsLoading:
    """Test Phase 1 facts loading and merging into model_index."""

    def test_load_model_facts_dev_env(self, router_fixture):
        """Test facts loaded from model-registry-dev.json in dev environment."""
        router, _, _ = router_fixture

        # Verify facts were loaded
        assert "test/model-1" in router.model_facts
        facts = router.model_facts["test/model-1"]
        assert facts["pricing"]["inputPer1KTokens"] == 0.001
        assert facts["governance"]["tier"] == "budget"

    def test_merge_facts_into_model_index(self, router_fixture):
        """Test pricing, tier, capabilities_array, factsEnabled merged into model_index."""
        router, _, _ = router_fixture

        # Verify merge
        model = router.model_index["test/model-1"]
        assert model["pricing"]["inputPer1KTokens"] == 0.001
        assert model["tier"] == "budget"
        assert model["capabilities_array"] == ["chat", "tool-use", "json", "streaming"]
        assert model["factsEnabled"] is True

    def test_provider_mismatch_sanity_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test provider mismatch between facts and legacy triggers error."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        # Create Phase 1 facts with DIFFERENT provider
        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "wrong_provider",  # Mismatch!
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": ["chat"],
                    "pricing": {
                        "currency": "USD",
                        "inputPer1KTokens": 0.001,
                        "outputPer1KTokens": 0.002,
                    },
                    "limits": {"maxInputTokens": 8192, "maxOutputTokens": 2048},
                    "governance": {
                        "tier": "budget",
                        "allowedEnvironments": ["dev"],
                    },
                }
            ],
        }

        (shared_dir / "model-registry-dev.json").write_text(json.dumps(facts_registry))

        # Create legacy registry with different provider
        legacy_registry = {
            "version": "1.0.0",
            "defaults": {"defaultModeId": "navi/fast"},
            "naviModes": [
                {
                    "id": "navi/fast",
                    "displayName": "Fast",
                    "candidateModelIds": ["test/model-1"],
                }
            ],
            "providers": [
                {
                    "id": "test",  # Different from "wrong_provider"
                    "type": "saas",
                    "models": [{"id": "test/model-1"}],
                }
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("MODEL_REGISTRY_PATH", str(shared_dir / "model-registry-dev.json"))

        # Should raise ValueError on provider mismatch
        with pytest.raises(ValueError, match="Provider mismatch"):
            ModelRouter(registry_path=legacy_path)


class TestPhase2CostEstimation:
    """Test cost estimation from Phase 1 pricing metadata."""

    def test_estimate_cost_basic(self, router_fixture):
        """Test cost calculation from pricing metadata."""
        router, _, _ = router_fixture

        # Estimate cost: 2000 input tokens, 500 output tokens
        cost = router.estimate_cost("test/model-1", 2000, 500)

        assert cost is not None
        # (2000/1000 * 0.001) + (500/1000 * 0.002) = 0.002 + 0.001 = 0.003
        assert cost["estimatedCostUSD"] == 0.003
        assert cost["tier"] == "budget"
        assert cost["breakdown"]["inputCostUSD"] == 0.002
        assert cost["breakdown"]["outputCostUSD"] == 0.001

    def test_estimate_cost_expensive_model(self, router_fixture):
        """Test cost calculation for expensive model."""
        router, _, _ = router_fixture

        # test/expensive-model: input=0.05, output=0.1
        cost = router.estimate_cost("test/expensive-model", 2000, 500)

        assert cost is not None
        # (2000/1000 * 0.05) + (500/1000 * 0.1) = 0.1 + 0.05 = 0.15
        assert cost["estimatedCostUSD"] == 0.15
        assert cost["tier"] == "premium"

    def test_estimate_cost_model_not_found(self, router_fixture):
        """Test cost estimation returns None for unknown model."""
        router, _, _ = router_fixture
        cost = router.estimate_cost("nonexistent/model", 2000, 500)
        assert cost is None


class TestPhase2PolicyEvaluation:
    """Test policy constraint checking."""

    def test_policy_missing_capability(self, router_fixture):
        """Test policy rejects model missing required capability."""
        router, _, _ = router_fixture

        # test/model-1 has ["chat", "tool-use", "json", "streaming"] but NOT "vision"
        result = router.evaluate_policy(
            "test/model-1", {"requiredCapabilities": ["vision"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "missing_capability:vision"
        assert "vision" in result["evaluation"]["capabilities"]["missing"]

    def test_policy_tier_blocked(self, router_fixture):
        """Test policy rejects model with blocked tier."""
        router, _, _ = router_fixture

        # test/model-1 has tier "budget", not in ["premium", "standard"]
        result = router.evaluate_policy(
            "test/model-1", {"allowedTiers": ["premium", "standard"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "tier_blocked"
        assert result["evaluation"]["tier"]["blocked"] is True

    def test_policy_provider_blocked(self, router_fixture):
        """Test policy rejects model with blocked provider."""
        router, _, _ = router_fixture

        # test/model-1 has provider "test", not in ["openai", "anthropic"]
        result = router.evaluate_policy(
            "test/model-1", {"allowedProviders": ["openai", "anthropic"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "provider_blocked"
        assert result["evaluation"]["provider"]["blocked"] is True

    def test_policy_cost_exceeded(self, router_fixture):
        """Test policy rejects model exceeding cost limit."""
        router, _, _ = router_fixture

        # test/expensive-model costs 0.15 for default 2000/500 tokens, exceeds $0.01
        result = router.evaluate_policy("test/expensive-model", {"maxCostUSD": 0.01})

        assert result["allowed"] is False
        assert result["reason"] == "cost_exceeded"
        assert result["evaluation"]["cost"]["exceeded"] is True

    def test_policy_all_checks_pass(self, router_fixture):
        """Test policy allows model meeting all constraints."""
        router, _, _ = router_fixture

        result = router.evaluate_policy(
            "test/model-1",
            {
                "requiredCapabilities": ["chat", "json"],
                "allowedTiers": ["budget", "standard"],
                "allowedProviders": ["test"],
                "maxCostUSD": 1.0,
            },
        )

        assert result["allowed"] is True
        assert result["reason"] is None


class TestPhase2RoutabilityEvaluation:
    """Test enhanced routability evaluation with reason codes."""

    def test_routability_with_facts_disabled(self, router_fixture):
        """Test factsEnabled=false triggers facts_disabled reason."""
        router, _, _ = router_fixture

        # test/disabled-model has enabled=False
        routable, reason = router._is_model_routable_with_reason(
            "test/disabled-model",
            "stream",
            {"test"},
            strict_private=False,
        )

        assert routable is False
        assert reason == "facts_disabled"

    def test_routability_model_not_found(self, router_fixture):
        """Test unknown model triggers model_not_found reason."""
        router, _, _ = router_fixture

        routable, reason = router._is_model_routable_with_reason(
            "nonexistent/model",
            "stream",
            {"test"},
            strict_private=False,
        )

        assert routable is False
        assert reason == "model_not_found"

    def test_routability_provider_not_supported(self, router_fixture):
        """Test provider not in supported set triggers provider_not_supported."""
        router, _, _ = router_fixture

        routable, reason = router._is_model_routable_with_reason(
            "test/model-1",
            "stream",
            {"other_provider"},  # test not in this set
            strict_private=False,
        )

        assert routable is False
        assert reason == "provider_not_supported"

    def test_pick_first_routable_returns_evaluation(self, router_fixture):
        """Test _pick_first_routable returns dict with evaluation list."""
        router, _, _ = router_fixture

        result = router._pick_first_routable(
            ["test/disabled-model", "test/model-1"],
            "stream",
            {"test"},
            strict_private=False,
        )

        assert "selected" in result
        assert "routability_evaluation" in result
        assert len(result["routability_evaluation"]) == 2

        # First model should be not routable (facts_disabled)
        assert result["routability_evaluation"][0]["routable"] is False
        assert result["routability_evaluation"][0]["reason"] == "facts_disabled"

        # Second model should be routable
        assert result["routability_evaluation"][1]["routable"] is True
        assert result["routability_evaluation"][1]["reason"] is None

        # Selected should be the second model
        assert result["selected"] == "test/model-1"


class TestPhase2DualLayerEvaluation:
    """Test dual-layer evaluation (policy → routability → selection)."""

    def test_route_includes_cost_estimate(self, router_fixture):
        """Test route() includes cost estimate in decision."""
        router, _, _ = router_fixture

        decision = router.route("navi/intelligence", "stream")

        # Should have cost estimate
        assert decision.cost_estimate is not None
        assert "estimatedCostUSD" in decision.cost_estimate
        assert "tier" in decision.cost_estimate

    def test_route_includes_routability_evaluation(self, router_fixture):
        """Test route() includes routability evaluation."""
        router, _, _ = router_fixture

        decision = router.route("navi/intelligence", "stream")

        # Should have routability evaluation
        assert decision.routability_evaluation is not None
        assert len(decision.routability_evaluation) > 0
        assert all("model_id" in eval for eval in decision.routability_evaluation)
        assert all("routable" in eval for eval in decision.routability_evaluation)
