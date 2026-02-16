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
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
import pytest

from backend.services.model_router import ModelRouter, ModelRoutingError


class TestPhase2FactsLoading:
    """Test Phase 1 facts loading and merging into model_index."""

    def test_load_model_facts_dev_env(self, tmp_path: Path):
        """Test facts loaded from model-registry-dev.json in dev environment."""
        # Create minimal registry structure
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        # Create Phase 1 facts file
        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": ["chat", "json"],
                    "pricing": {
                        "currency": "USD",
                        "inputPer1KTokens": 0.001,
                        "outputPer1KTokens": 0.002,
                    },
                    "limits": {"maxInputTokens": 8192, "maxOutputTokens": 2048},
                    "governance": {
                        "tier": "budget",
                        "allowedEnvironments": ["dev", "staging", "prod"],
                    },
                }
            ],
        }

        (shared_dir / "model-registry-dev.json").write_text(json.dumps(facts_registry))

        # Create legacy registry
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
                    "id": "test",
                    "type": "saas",
                    "models": [
                        {
                            "id": "test/model-1",
                            "displayName": "Test Model 1",
                            "streaming": True,
                        }
                    ],
                }
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        # Set environment to dev
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            mp.setenv("MODEL_REGISTRY_PATH", str(shared_dir / "model-registry-dev.json"))
            mp.setenv("TEST_API_KEY", "test-key")  # Configure provider
            mp.chdir(tmp_path)  # Change to tmp directory
            router = ModelRouter(registry_path=legacy_path)

            # Verify facts were loaded
            assert "test/model-1" in router.model_facts
            facts = router.model_facts["test/model-1"]
            assert facts["pricing"]["inputPer1KTokens"] == 0.001
            assert facts["governance"]["tier"] == "budget"

    def test_merge_facts_into_model_index(self, tmp_path: Path):
        """Test pricing, tier, capabilities_array, factsEnabled merged into model_index."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        # Create Phase 1 facts
        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": ["chat", "tool-use", "json"],
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

        # Create legacy registry
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
                    "id": "test",
                    "type": "saas",
                    "models": [{"id": "test/model-1", "streaming": True, "tools": True}],
                }
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            router = ModelRouter(registry_path=legacy_path)

            # Verify merge
            model = router.model_index["test/model-1"]
            assert model["pricing"]["inputPer1KTokens"] == 0.001
            assert model["tier"] == "budget"
            assert model["capabilities_array"] == ["chat", "tool-use", "json"]
            assert model["factsEnabled"] is True

    def test_provider_mismatch_sanity_check(self, tmp_path: Path):
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

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            # Should raise ValueError on provider mismatch
            with pytest.raises(ValueError, match="Provider mismatch"):
                ModelRouter(registry_path=legacy_path)


class TestPhase2CostEstimation:
    """Test cost estimation from Phase 1 pricing metadata."""

    def test_estimate_cost_basic(self, tmp_path: Path):
        """Test cost calculation from pricing metadata."""
        router = self._create_router_with_pricing(tmp_path)

        # Estimate cost: 2000 input tokens, 500 output tokens
        cost = router.estimate_cost("test/model-1", 2000, 500)

        assert cost is not None
        # (2000/1000 * 0.001) + (500/1000 * 0.002) = 0.002 + 0.001 = 0.003
        assert cost["estimatedCostUSD"] == 0.003
        assert cost["tier"] == "budget"
        assert cost["breakdown"]["inputCostUSD"] == 0.002
        assert cost["breakdown"]["outputCostUSD"] == 0.001

    def test_estimate_cost_no_pricing(self, tmp_path: Path):
        """Test cost estimation returns None when pricing unavailable."""
        router = self._create_router_without_pricing(tmp_path)
        cost = router.estimate_cost("test/model-1", 2000, 500)
        assert cost is None

    def test_estimate_cost_model_not_found(self, tmp_path: Path):
        """Test cost estimation returns None for unknown model."""
        router = self._create_router_with_pricing(tmp_path)
        cost = router.estimate_cost("nonexistent/model", 2000, 500)
        assert cost is None

    def _create_router_with_pricing(self, tmp_path: Path) -> ModelRouter:
        """Helper: Create router with pricing metadata."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_without_pricing(self, tmp_path: Path) -> ModelRouter:
        """Helper: Create router without pricing metadata."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        # No Phase 1 facts file
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)


class TestPhase2PolicyEvaluation:
    """Test policy constraint checking."""

    def test_policy_missing_capability(self, tmp_path: Path):
        """Test policy rejects model missing required capability."""
        router = self._create_router_with_capabilities(tmp_path, ["chat", "json"])

        result = router.evaluate_policy(
            "test/model-1", {"requiredCapabilities": ["vision"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "missing_capability:vision"
        assert "vision" in result["evaluation"]["capabilities"]["missing"]

    def test_policy_tier_blocked(self, tmp_path: Path):
        """Test policy rejects model with blocked tier."""
        router = self._create_router_with_tier(tmp_path, "budget")

        result = router.evaluate_policy(
            "test/model-1", {"allowedTiers": ["premium", "standard"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "tier_blocked"
        assert result["evaluation"]["tier"]["blocked"] is True

    def test_policy_provider_blocked(self, tmp_path: Path):
        """Test policy rejects model with blocked provider."""
        router = self._create_router_with_provider(tmp_path, "test")

        result = router.evaluate_policy(
            "test/model-1", {"allowedProviders": ["openai", "anthropic"]}
        )

        assert result["allowed"] is False
        assert result["reason"] == "provider_blocked"
        assert result["evaluation"]["provider"]["blocked"] is True

    def test_policy_cost_exceeded(self, tmp_path: Path):
        """Test policy rejects model exceeding cost limit."""
        router = self._create_router_with_pricing(
            tmp_path, input_per_1k=0.01, output_per_1k=0.02
        )

        # Max cost: $0.005, but model costs: (2000/1000 * 0.01) + (500/1000 * 0.02) = 0.03
        result = router.evaluate_policy("test/model-1", {"maxCostUSD": 0.005})

        assert result["allowed"] is False
        assert result["reason"] == "cost_exceeded"
        assert result["evaluation"]["cost"]["exceeded"] is True

    def test_policy_all_checks_pass(self, tmp_path: Path):
        """Test policy allows model meeting all constraints."""
        router = self._create_router_full(tmp_path)

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

    def _create_router_with_capabilities(
        self, tmp_path: Path, capabilities: list[str]
    ) -> ModelRouter:
        """Helper: Create router with specific capabilities."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": capabilities,
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_with_tier(self, tmp_path: Path, tier: str) -> ModelRouter:
        """Helper: Create router with specific tier."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
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
                        "tier": tier,
                        "allowedEnvironments": ["dev"],
                    },
                }
            ],
        }

        (shared_dir / "model-registry-dev.json").write_text(json.dumps(facts_registry))

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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_with_provider(self, tmp_path: Path, provider: str) -> ModelRouter:
        """Helper: Create router with specific provider."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": provider,
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
                {"id": provider, "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_with_pricing(
        self, tmp_path: Path, input_per_1k: float, output_per_1k: float
    ) -> ModelRouter:
        """Helper: Create router with specific pricing."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": ["chat"],
                    "pricing": {
                        "currency": "USD",
                        "inputPer1KTokens": input_per_1k,
                        "outputPer1KTokens": output_per_1k,
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_full(self, tmp_path: Path) -> ModelRouter:
        """Helper: Create router with all metadata."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": True,
                    "productionApproved": True,
                    "capabilities": ["chat", "json"],
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            return ModelRouter(registry_path=legacy_path)


class TestPhase2RoutabilityEvaluation:
    """Test enhanced routability evaluation with reason codes."""

    def test_routability_with_facts_disabled(self, tmp_path: Path):
        """Test factsEnabled=false triggers facts_disabled reason."""
        router = self._create_router_with_facts_enabled(tmp_path, enabled=False)

        routable, reason = router._is_model_routable_with_reason(
            "test/model-1",
            "stream",
            {"test"},
            strict_private=False,
        )

        assert routable is False
        assert reason == "facts_disabled"

    def test_routability_model_not_found(self, tmp_path: Path):
        """Test unknown model triggers model_not_found reason."""
        router = self._create_basic_router(tmp_path)

        routable, reason = router._is_model_routable_with_reason(
            "nonexistent/model",
            "stream",
            {"test"},
            strict_private=False,
        )

        assert routable is False
        assert reason == "model_not_found"

    def test_routability_provider_not_supported(self, tmp_path: Path):
        """Test provider not in supported set triggers provider_not_supported."""
        router = self._create_basic_router(tmp_path)

        routable, reason = router._is_model_routable_with_reason(
            "test/model-1",
            "stream",
            {"other_provider"},  # test not in this set
            strict_private=False,
        )

        assert routable is False
        assert reason == "provider_not_supported"

    def test_pick_first_routable_returns_evaluation(self, tmp_path: Path):
        """Test _pick_first_routable returns dict with evaluation list."""
        router = self._create_router_with_multiple_models(tmp_path)

        result = router._pick_first_routable(
            ["test/model-disabled", "test/model-enabled"],
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
        assert result["selected"] == "test/model-enabled"

    def _create_router_with_facts_enabled(
        self, tmp_path: Path, enabled: bool
    ) -> ModelRouter:
        """Helper: Create router with factsEnabled flag."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
                    "displayName": "Test Model 1",
                    "enabled": enabled,
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            mp.setenv("TEST_API_KEY", "test-key")  # Configure provider
            return ModelRouter(registry_path=legacy_path)

    def _create_basic_router(self, tmp_path: Path) -> ModelRouter:
        """Helper: Create basic router."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-1",
                    "provider": "test",
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
                {"id": "test", "type": "saas", "models": [{"id": "test/model-1"}]}
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            mp.setenv("TEST_API_KEY", "test-key")
            return ModelRouter(registry_path=legacy_path)

    def _create_router_with_multiple_models(self, tmp_path: Path) -> ModelRouter:
        """Helper: Create router with multiple models."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()

        facts_registry = {
            "schemaVersion": 1,
            "environment": "dev",
            "models": [
                {
                    "id": "test/model-disabled",
                    "provider": "test",
                    "displayName": "Test Model Disabled",
                    "enabled": False,  # Disabled
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
                },
                {
                    "id": "test/model-enabled",
                    "provider": "test",
                    "displayName": "Test Model Enabled",
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
                },
            ],
        }

        (shared_dir / "model-registry-dev.json").write_text(json.dumps(facts_registry))

        legacy_registry = {
            "version": "1.0.0",
            "defaults": {"defaultModeId": "navi/fast"},
            "naviModes": [
                {
                    "id": "navi/fast",
                    "displayName": "Fast",
                    "candidateModelIds": ["test/model-disabled", "test/model-enabled"],
                }
            ],
            "providers": [
                {
                    "id": "test",
                    "type": "saas",
                    "models": [
                        {"id": "test/model-disabled"},
                        {"id": "test/model-enabled"},
                    ],
                }
            ],
        }

        legacy_path = shared_dir / "model-registry.json"
        legacy_path.write_text(json.dumps(legacy_registry))

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("APP_ENV", "dev")
            mp.setenv("TEST_API_KEY", "test-key")
            return ModelRouter(registry_path=legacy_path)
