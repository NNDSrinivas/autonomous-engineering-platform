"""Unified model routing for NAVI endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.provider_health import ProviderHealthTracker

logger = logging.getLogger(__name__)


_ENDPOINT_PROVIDER_SUPPORT = {
    "stream": {
        "openai",
        "anthropic",
        "google",
        "groq",
        "openrouter",
        "ollama",
        "self_hosted",
    },
    "stream_v2": {
        "openai",
        "anthropic",
        "groq",
        "openrouter",
        "ollama",
        "self_hosted",
    },
    "autonomous": {
        "openai",
        "anthropic",
        "groq",
        "openrouter",
        "ollama",
        "self_hosted",
    },
    # Non-streaming /chat endpoint - only routes to providers in llm_providers.yaml
    "chat": {
        "openai",
        "anthropic",
    },
}

_PROVIDER_CREDENTIAL_KEYS: Dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "ollama": ("OLLAMA_BASE_URL",),
    "self_hosted": (
        "SELF_HOSTED_API_BASE_URL",
        "SELF_HOSTED_LLM_URL",
        "VLLM_BASE_URL",
        "SELF_HOSTED_API_KEY",  # Supports default localhost + API key
    ),
    # Test-only provider used in unit fixtures.
    "test": ("TEST_API_KEY",),
}

_ALIAS_TO_MODEL_ID = {
    "recommended": "navi/intelligence",
    "auto": "navi/intelligence",
    "auto/recommended": "navi/intelligence",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-5": "openai/gpt-5",
    "gpt-5.1": "openai/gpt-5.1",
    "gpt-5.2": "openai/gpt-5.2",
    "claude-sonnet-4": "anthropic/claude-sonnet-4",
    "claude-opus-4": "anthropic/claude-opus-4",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
}

_PROVIDER_HINT_TO_ID = {
    "openai": "openai",
    "openai_navra": "openai",
    "openai_byok": "openai",
    "anthropic": "anthropic",
    "anthropic_byok": "anthropic",
    "google": "google",
    "gemini": "google",
    "google_byok": "google",
    "gemini_byok": "google",
    "groq": "groq",
    "groq_byok": "groq",
    "openrouter": "openrouter",
    "openrouter_byok": "openrouter",
    "ollama": "ollama",
    "self_hosted": "self_hosted",
    "self-hosted": "self_hosted",
    "selfhosted": "self_hosted",
}

_RUNTIME_ENV_ALIASES = {
    "prod": "prod",
    "production": "prod",
    "staging": "staging",
    "stage": "staging",
    "dev": "dev",
    "development": "dev",
    "test": "dev",
    "testing": "dev",
}


class ModelRoutingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RoutingDecision:
    requested_model_id: Optional[str]
    requested_mode_id: Optional[str]
    effective_model_id: str
    provider: str
    model: str
    was_fallback: bool
    fallback_reason_code: Optional[str]
    fallback_reason: Optional[str]
    # Phase 2: Policy and cost governance metadata
    policy_evaluation: list[Dict[str, Any]] = None  # type: ignore
    routability_evaluation: list[Dict[str, Any]] = None  # type: ignore
    cost_estimate: Optional[Dict[str, Any]] = None

    def to_public_dict(self) -> Dict[str, Any]:
        # Keep legacy keys for current webview/extension while adding new metadata keys.
        result = {
            "requestedModelId": self.requested_model_id,
            "requestedModeId": self.requested_mode_id,
            "effectiveModelId": self.effective_model_id,
            "provider": self.provider,
            "model": self.model,
            "wasFallback": self.was_fallback,
            "fallbackReasonCode": self.fallback_reason_code,
            "fallbackReason": self.fallback_reason,
            # legacy compatibility
            "modelId": self.effective_model_id,
            "mode": self.requested_mode_id,
        }
        # Phase 2: Add policy/routability/cost metadata if available
        if self.policy_evaluation:
            result["policyEvaluation"] = self.policy_evaluation
        if self.routability_evaluation:
            result["routabilityEvaluation"] = self.routability_evaluation
        if self.cost_estimate:
            result["costEstimate"] = self.cost_estimate
        return result


class ModelRouter:
    def __init__(self, registry_path: Optional[Path] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.registry_path = registry_path or (
            repo_root / "shared" / "model-registry.json"
        )

        # Phase 2: Load runtime environment and Phase 1 facts
        self.runtime_env = self._normalize_runtime_env(os.getenv("APP_ENV", "dev"))

        self.registry = self._load_registry()
        self.defaults = self.registry.get("defaults", {})
        self.providers = self.registry.get("providers", [])
        self.modes = self.registry.get("naviModes", [])

        # Phase 2: Load Phase 1 registry facts
        self.model_facts = self._load_model_facts(repo_root)

        self.model_index: Dict[str, Dict[str, Any]] = {}
        self.provider_index: Dict[str, Dict[str, Any]] = {}
        self.mode_index: Dict[str, Dict[str, Any]] = {}

        for provider in self.providers:
            provider_id = provider.get("id")
            if not isinstance(provider_id, str):
                continue
            self.provider_index[provider_id] = provider
            for model in provider.get("models", []):
                model_id = model.get("id")
                if isinstance(model_id, str):
                    # Start with legacy registry data
                    merged = {
                        **model,
                        "provider": provider_id,
                        "providerType": provider.get("type", "saas"),
                    }

                    # Phase 2: Merge Phase 1 facts if available
                    facts = self.model_facts.get(model_id)
                    if facts:
                        # SANITY CHECK: Provider must match
                        facts_provider = facts.get("provider")
                        if facts_provider and facts_provider != provider_id:
                            raise ValueError(
                                f"Provider mismatch for {model_id}: "
                                f"legacy={provider_id}, facts={facts_provider}"
                            )

                        # Merge pricing metadata
                        merged["pricing"] = facts.get("pricing")

                        # Merge governance tier
                        governance = facts.get("governance", {})
                        merged["tier"] = governance.get("tier")

                        # Merge capabilities array (Phase 1 format)
                        merged["capabilities_array"] = facts.get("capabilities", [])

                        # Preserve Phase 1 enabled flag
                        merged["factsEnabled"] = facts.get("enabled", True)

                    self.model_index[model_id] = merged

        for mode in self.modes:
            mode_id = mode.get("id")
            if isinstance(mode_id, str):
                self.mode_index[mode_id] = mode

        # Validate that defaultModeId is configured and exists
        default_mode_id = self.defaults.get("defaultModeId")
        if not default_mode_id:
            raise ValueError(
                "ModelRouter misconfigured: defaultModeId must be set in model-registry.json"
            )
        if default_mode_id not in self.mode_index:
            raise ValueError(
                f"ModelRouter misconfigured: defaultModeId '{default_mode_id}' does not exist in naviModes"
            )

        # Phase 3: Initialize provider health tracker
        self.health_tracker = self._init_health_tracker()

    def _load_registry(self) -> Dict[str, Any]:
        with self.registry_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _load_model_facts(self, repo_root: Path) -> Dict[str, Dict[str, Any]]:
        """Load Phase 1 flat registry and return model facts keyed by model ID."""
        env = self.runtime_env
        registry_dir = self.registry_path.parent
        direct_registry_path = (os.getenv("MODEL_REGISTRY_PATH") or "").strip()
        if direct_registry_path:
            registry_path = Path(direct_registry_path)
            if not registry_path.is_absolute():
                registry_path = repo_root / registry_path
            if not registry_path.exists():
                raise ValueError(
                    f"ModelRouter misconfigured: MODEL_REGISTRY_PATH does not exist: {registry_path}"
                )
        else:
            # Determine registry path based on runtime environment.
            registry_filename = f"model-registry-{env}.json"
            registry_path = registry_dir / registry_filename

            if not registry_path.exists():
                # Fallback to dev registry only for dev-like environments.
                if env != "dev":
                    raise ValueError(
                        f"ModelRouter misconfigured: missing facts registry '{registry_filename}' for APP_ENV={env}"
                    )
                registry_path = registry_dir / "model-registry-dev.json"
                if not registry_path.exists():
                    # Dev/test environments may intentionally run without Phase 1 facts.
                    return {}

        with open(registry_path, "r", encoding="utf-8") as fh:
            registry_data = json.load(fh)

        # Index models by ID for fast lookup
        facts: Dict[str, Dict[str, Any]] = {}
        for model in registry_data.get("models", []):
            model_id = model.get("id")
            if model_id:
                facts[model_id] = model

        return facts

    def _init_health_tracker(self) -> Optional[ProviderHealthTracker]:
        """Initialize provider health tracker with Redis backend."""
        try:
            import redis
            from backend.core.config import settings
            from backend.services.provider_health import ProviderHealthTracker

            # Get or create Redis client
            redis_client = redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )

            # Validate Redis connectivity before creating tracker
            try:
                redis_client.ping()
            except Exception:
                logger.warning(
                    "Redis unavailable; provider health tracking disabled."
                )
                return None

            # Initialize health tracker with circuit breaker config
            return ProviderHealthTracker(
                redis_client=redis_client,
                window_sec=60,  # 60s sliding window for failure tracking
                failure_threshold=5,  # 5 failures trigger circuit open
                open_duration_sec=30,  # 30s backoff before half-open probe
            )

        except Exception as e:
            # Graceful degradation: router works without health tracking
            logger.warning(
                f"Failed to initialize health tracker: {e}. "
                f"Provider health tracking disabled."
            )
            return None

    def route(
        self,
        requested_model_or_mode_id: Optional[str],
        endpoint: str,
        requested_provider: Optional[str] = None,
    ) -> RoutingDecision:
        endpoint_key = self._normalize_endpoint(endpoint)
        support = _ENDPOINT_PROVIDER_SUPPORT.get(
            endpoint_key, _ENDPOINT_PROVIDER_SUPPORT["stream"]
        )

        requested_id = (requested_model_or_mode_id or "").strip()
        requested_mode_id: Optional[str] = None
        requested_model_id: Optional[str] = None

        if requested_provider and requested_id and "/" not in requested_id:
            provider_hint = self._normalize_provider_hint(requested_provider)
            requested_id = f"{provider_hint}/{requested_id}"

        if not requested_id:
            requested_mode_id = self.defaults.get("defaultModeId")
        elif requested_id.startswith("navi/"):
            requested_mode_id = requested_id
        else:
            normalized = self._normalize_vendor_id(requested_id)
            if normalized.startswith("navi/"):
                requested_mode_id = normalized
            else:
                requested_model_id = normalized

        if requested_mode_id:
            return self._route_mode(
                requested_mode_id=requested_mode_id,
                endpoint_key=endpoint_key,
                supported_providers=support,
            )

        if requested_model_id:
            return self._route_model(
                requested_model_id=requested_model_id,
                endpoint_key=endpoint_key,
                supported_providers=support,
            )

        # defensive fallback to default mode
        default_mode = self.defaults.get("defaultModeId")
        if not default_mode:
            # This should never happen due to init validation, but be defensive
            raise ModelRoutingError(
                "NO_DEFAULT_MODE",
                "No default mode configured in registry",
            )
        return self._route_mode(
            requested_mode_id=default_mode,
            endpoint_key=endpoint_key,
            supported_providers=support,
        )

    def _route_mode(
        self,
        requested_mode_id: str,
        endpoint_key: str,
        supported_providers: set[str],
    ) -> RoutingDecision:
        # Preserve original requested mode ID for metadata/observability
        requested_mode_id_original = requested_mode_id
        mode_fallback_reason = None
        mode_fallback_code = None

        mode = self.mode_index.get(requested_mode_id)
        if not mode:
            default_mode = self.defaults.get("defaultModeId")
            mode = self.mode_index.get(default_mode)
            if not mode:
                raise ModelRoutingError(
                    "INVALID_MODE", "No valid NAVI mode available in registry"
                )
            # Set fallback metadata for unknown mode
            mode_fallback_code = "UNKNOWN_MODE_ID"
            mode_fallback_reason = f"Unknown mode '{requested_mode_id_original}'; using default mode '{default_mode}'."
            requested_mode_id = default_mode  # Use default for routing

        candidates: list[str] = [
            m for m in mode.get("candidateModelIds", []) if isinstance(m, str)
        ]
        if not candidates:
            raise ModelRoutingError(
                "INVALID_MODE", f"Mode '{requested_mode_id}' has no candidates"
            )

        strict_private = bool((mode.get("policy") or {}).get("strictPrivate"))

        # Phase 2: Policy evaluation (dual-layer filtering)
        policy = mode.get("policy") or {}
        policy_constraints = {
            k: v
            for k, v in policy.items()
            if k
            in {
                "requiredCapabilities",
                "allowedTiers",
                "allowedProviders",
                "maxCostUSD",
            }
        }

        policy_evaluation = []
        if policy_constraints:
            filtered_candidates = []
            for candidate in candidates:
                eval_result = self.evaluate_policy(candidate, policy_constraints)
                policy_evaluation.append(
                    {
                        "model_id": candidate,
                        "allowed": eval_result["allowed"],
                        "reason": eval_result["reason"],
                    }
                )
                if eval_result["allowed"]:
                    filtered_candidates.append(candidate)

            candidates = filtered_candidates

            if not candidates:
                raise ModelRoutingError(
                    "POLICY_REJECTED_ALL_CANDIDATES",
                    f"All candidate models for mode '{requested_mode_id}' rejected by policy constraints",
                )

        # Phase 2: Enhanced routability evaluation
        result = self._pick_first_routable(
            candidates,
            endpoint_key=endpoint_key,
            supported_providers=supported_providers,
            strict_private=strict_private,
        )
        selected_model_id = result["selected"]
        routability_eval = result["routability_evaluation"]

        if selected_model_id:
            model_cfg = self.model_index[selected_model_id]
            is_first_choice = selected_model_id == candidates[0]
            was_fallback = not is_first_choice or mode_fallback_reason is not None
            fallback_reason_code = mode_fallback_code
            fallback_reason = mode_fallback_reason

            if not is_first_choice:
                # Model candidate fallback within the mode
                fallback_reason_code = (
                    fallback_reason_code or "MODE_CANDIDATE_UNAVAILABLE"
                )
                # Get first failure reason from evaluation
                first_failure = next(
                    (e for e in routability_eval if not e["routable"]), None
                )
                reason = first_failure["reason"] if first_failure else None
                fallback_reason = reason or (
                    f"Primary mode candidate '{candidates[0]}' unavailable; used '{selected_model_id}'."
                )
                # If we also had a mode fallback, combine the reasons
                if mode_fallback_reason:
                    fallback_reason = f"{mode_fallback_reason} {fallback_reason}"

            # Phase 2: Calculate cost estimate for selected model
            cost_estimate = self.estimate_cost(selected_model_id, 2000, 500)

            return RoutingDecision(
                requested_model_id=None,
                requested_mode_id=requested_mode_id_original,  # Use original, not effective
                effective_model_id=selected_model_id,
                provider=model_cfg["provider"],
                model=model_cfg.get("providerModel")
                or selected_model_id.split("/", 1)[1],
                was_fallback=was_fallback,
                fallback_reason_code=fallback_reason_code,
                fallback_reason=fallback_reason,
                policy_evaluation=policy_evaluation if policy_constraints else [],
                routability_evaluation=routability_eval,
                cost_estimate=cost_estimate,
            )

        if strict_private:
            raise ModelRoutingError(
                "PRIVATE_MODE_BLOCKED",
                "NAVI Private mode requires a configured local/self-hosted model. No eligible private model is available.",
            )

        default_model = self.defaults.get("defaultModelId")
        if default_model and self._is_model_routable(
            default_model, endpoint_key, supported_providers, strict_private=False
        ):
            model_cfg = self.model_index[default_model]
            # Combine mode fallback (if any) with model fallback
            combined_reason = mode_fallback_reason or ""
            if combined_reason:
                combined_reason += " "
            combined_reason += f"No configured models for mode '{requested_mode_id}'. Falling back to default model '{default_model}'."

            # Phase 2: Calculate cost for fallback model
            fallback_cost_estimate = self.estimate_cost(default_model, 2000, 500)

            return RoutingDecision(
                requested_model_id=None,
                requested_mode_id=requested_mode_id_original,  # Use original, not effective
                effective_model_id=default_model,
                provider=model_cfg["provider"],
                model=model_cfg.get("providerModel") or default_model.split("/", 1)[1],
                was_fallback=True,
                fallback_reason_code=mode_fallback_code or "MODE_NO_AVAILABLE_MODELS",
                fallback_reason=combined_reason,
                policy_evaluation=[],
                routability_evaluation=[],
                cost_estimate=fallback_cost_estimate,
            )

        raise ModelRoutingError(
            "NO_MODELS_AVAILABLE",
            f"No configured models available for mode '{requested_mode_id_original}'.",
        )

    def _route_model(
        self,
        requested_model_id: str,
        endpoint_key: str,
        supported_providers: set[str],
    ) -> RoutingDecision:
        endpoint_label = self._display_endpoint_label(endpoint_key)
        model_cfg = self.model_index.get(requested_model_id)
        if model_cfg and self._is_model_routable(
            requested_model_id, endpoint_key, supported_providers, strict_private=False
        ):
            # Phase 2: Calculate cost for direct model routing
            direct_cost_estimate = self.estimate_cost(requested_model_id, 2000, 500)

            return RoutingDecision(
                requested_model_id=requested_model_id,
                requested_mode_id=None,
                effective_model_id=requested_model_id,
                provider=model_cfg["provider"],
                model=model_cfg.get("providerModel")
                or requested_model_id.split("/", 1)[1],
                was_fallback=False,
                fallback_reason_code=None,
                fallback_reason=None,
                policy_evaluation=[],
                routability_evaluation=[],
                cost_estimate=direct_cost_estimate,
            )

        reason_code = "MODEL_UNAVAILABLE"
        reason = f"Requested model '{requested_model_id}' is unavailable or unsupported for endpoint '{endpoint_label}'."
        if requested_model_id not in self.model_index:
            reason_code = "UNKNOWN_MODEL_ID"
            reason = f"Requested model '{requested_model_id}' is not in registry."
        elif model_cfg:
            provider = model_cfg["provider"]
            if provider not in supported_providers:
                reason_code = "ENDPOINT_PROVIDER_UNSUPPORTED"
                reason = (
                    f"{provider} is not supported on {endpoint_label} for requested model "
                    f"'{requested_model_id}'."
                )
            elif not self._is_provider_configured(provider):
                reason_code = "PROVIDER_NOT_CONFIGURED"
                reason = f"Provider '{provider}' is not configured for requested model '{requested_model_id}'."

        fallback_default = self.defaults.get("defaultModelId")
        if fallback_default and self._is_model_routable(
            fallback_default, endpoint_key, supported_providers, strict_private=False
        ):
            fallback_cfg = self.model_index[fallback_default]
            reason = f"{reason} Using '{fallback_default}'."

            # Phase 2: Calculate cost for fallback default model
            fallback_default_cost_estimate = self.estimate_cost(
                fallback_default, 2000, 500
            )

            return RoutingDecision(
                requested_model_id=requested_model_id,
                requested_mode_id=None,
                effective_model_id=fallback_default,
                provider=fallback_cfg["provider"],
                model=fallback_cfg.get("providerModel")
                or fallback_default.split("/", 1)[1],
                was_fallback=True,
                fallback_reason_code=reason_code,
                fallback_reason=reason,
                policy_evaluation=[],
                routability_evaluation=[],
                cost_estimate=fallback_default_cost_estimate,
            )

        if reason_code == "ENDPOINT_PROVIDER_UNSUPPORTED":
            raise ModelRoutingError(reason_code, reason)

        raise ModelRoutingError(
            "NO_MODELS_AVAILABLE",
            f"{reason} No fallback model is available.",
        )

    def _pick_first_routable(
        self,
        candidates: Iterable[str],
        endpoint_key: str,
        supported_providers: set[str],
        strict_private: bool,
    ) -> Dict[str, Any]:
        """Pick first routable model with detailed evaluation.

        Phase 2: Returns evaluation dict with per-candidate reason codes.

        Returns:
            {
                "selected": "openai/gpt-4o" | None,
                "routability_evaluation": [
                    {"model_id": "openai/o3", "routable": False, "reason": "provider_not_configured"},
                    {"model_id": "openai/gpt-4o", "routable": True, "reason": None},
                ]
            }
        """
        evaluation = []
        selected = None

        for candidate in candidates:
            routable, reason = self._is_model_routable_with_reason(
                candidate,
                endpoint_key,
                supported_providers,
                strict_private=strict_private,
            )

            evaluation.append(
                {
                    "model_id": candidate,
                    "routable": routable,
                    "reason": reason,
                }
            )

            # Pick first routable (preserve existing "first wins" logic)
            if selected is None and routable:
                selected = candidate

        return {
            "selected": selected,
            "routability_evaluation": evaluation,
        }

    def _is_model_routable(
        self,
        model_id: str,
        endpoint_key: str,
        supported_providers: set[str],
        strict_private: bool,
    ) -> bool:
        """Check if model is routable (backwards compat wrapper).

        Phase 2: Delegates to _is_model_routable_with_reason for evaluation.
        """
        routable, _ = self._is_model_routable_with_reason(
            model_id, endpoint_key, supported_providers, strict_private
        )
        return routable

    def _is_model_routable_with_reason(
        self,
        model_id: str,
        endpoint_key: str,
        supported_providers: set[str],
        strict_private: bool,
    ) -> tuple[bool, Optional[str]]:
        """Check if model is routable and return reason if not.

        Phase 2: Enhanced routability check with explicit reason codes.

        Returns:
            (routable: bool, reason: str | None)

        Reason codes:
            - "model_not_found"
            - "facts_disabled"
            - "strict_private_saas_blocked"
            - "provider_not_supported"
            - "provider_not_configured"
        """
        model_cfg = self.model_index.get(model_id)
        if not model_cfg:
            return False, "model_not_found"

        # Phase 2: Check Phase 1 enabled flag
        if model_cfg.get("factsEnabled") is False:
            return False, "facts_disabled"

        provider = model_cfg["provider"]
        provider_cfg = self.provider_index.get(provider, {})
        provider_type = provider_cfg.get("type", "saas")

        if strict_private and provider_type not in {"local", "self_hosted"}:
            return False, "strict_private_saas_blocked"

        if provider not in supported_providers:
            # Endpoint not supported for this provider
            return False, "provider_not_supported"

        if not self._is_provider_configured(provider):
            return False, "provider_not_configured"

        # Phase 3: Check circuit breaker state
        if self.health_tracker and self.health_tracker.is_circuit_open(provider):
            return False, "circuit_open"

        # TODO(navi-model-router-v2): gate by model capabilities from registry
        # (streaming/tools/json/vision/search). V1 routability is provider-level.
        return True, None

    def _is_provider_configured(self, provider_id: str) -> bool:
        if provider_id == "test":
            return True

        keys = _PROVIDER_CREDENTIAL_KEYS.get(provider_id, ())
        if not keys:
            # Unknown providers are treated as unavailable.
            return False
        if any(bool(os.getenv(key)) for key in keys):
            return True

        # Ollama can be configured via OLLAMA_BASE_URL (in credential keys) or
        # OLLAMA_HOST as a fallback for compatibility.
        if provider_id == "ollama":
            return bool(os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL"))

        return False

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        normalized = (endpoint or "stream").strip().lower()
        if normalized in {"/chat/stream", "stream"}:
            return "stream"
        if normalized in {"/chat/stream/v2", "stream/v2", "stream_v2", "v2"}:
            return "stream_v2"
        if normalized in {"/chat/autonomous", "autonomous"}:
            return "autonomous"
        return normalized

    @staticmethod
    def _map_capabilities(model_cfg: Dict[str, Any]) -> list[str]:
        """Convert legacy boolean capability flags to enum array.

        Phase 2: Maps legacy registry capabilities to Phase 1 capability enum.
        """
        # Prefer Phase 1 capabilities array if available
        capabilities_array = model_cfg.get("capabilities_array")
        if capabilities_array:
            return capabilities_array

        # Fallback: map legacy boolean flags to enum values
        legacy = model_cfg.get("capabilities", {})
        mapped = []

        # Always include chat (all models support it)
        mapped.append("chat")

        # Map boolean flags to enum values
        if legacy.get("tools"):
            mapped.append("tool-use")
        if legacy.get("json"):
            mapped.append("json")
        if legacy.get("vision"):
            mapped.append("vision")
        if legacy.get("streaming"):
            mapped.append("streaming")
        # Note: legacy "search" capability not mapped - Phase 1 schema only has "long-context"

        return mapped

    def estimate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Optional[Dict[str, Any]]:
        """Estimate cost for a request in USD.

        Phase 2: Calculate cost from Phase 1 pricing metadata.

        Returns:
            {
                "estimatedCostUSD": 0.0125,
                "tier": "standard",
                "breakdown": {
                    "inputCostUSD": 0.005,
                    "outputCostUSD": 0.0075
                }
            }
            or None if pricing unavailable
        """
        model_cfg = self.model_index.get(model_id)
        if not model_cfg:
            return None

        pricing = model_cfg.get("pricing")
        if not pricing:
            return None

        # Pricing is per-1K tokens
        input_cost = (input_tokens / 1000.0) * pricing.get("inputPer1KTokens", 0)
        output_cost = (output_tokens / 1000.0) * pricing.get("outputPer1KTokens", 0)
        total_cost = input_cost + output_cost

        return {
            "estimatedCostUSD": round(total_cost, 6),
            "tier": model_cfg.get("tier"),
            "breakdown": {
                "inputCostUSD": round(input_cost, 6),
                "outputCostUSD": round(output_cost, 6),
            },
        }

    def evaluate_policy(
        self,
        model_id: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate model against policy constraints.

        Phase 2: Policy-based filtering with capability/tier/cost checks.

        Args:
            model_id: Model to evaluate
            constraints: {
                "requiredCapabilities": ["tool-use", "json"],
                "allowedTiers": ["premium", "standard"],
                "allowedProviders": ["openai", "anthropic"],
                "maxCostUSD": 0.05
            }

        Returns:
            {
                "allowed": True/False,
                "reason": "missing_capability:vision" | "tier_blocked" | "cost_exceeded" | None,
                "evaluation": {...}
            }
        """
        constraints = constraints or {}
        model_cfg = self.model_index.get(model_id)

        if not model_cfg:
            return {
                "allowed": False,
                "reason": "model_not_found",
                "evaluation": {},
            }

        evaluation: Dict[str, Any] = {}

        # 1. Capability check
        required_caps = constraints.get("requiredCapabilities", [])
        if required_caps:
            actual_caps = self._map_capabilities(model_cfg)
            missing = [c for c in required_caps if c not in actual_caps]

            evaluation["capabilities"] = {
                "required": required_caps,
                "actual": actual_caps,
                "missing": missing,
            }

            if missing:
                return {
                    "allowed": False,
                    "reason": f"missing_capability:{missing[0]}",
                    "evaluation": evaluation,
                }

        # 2. Tier check
        allowed_tiers = constraints.get("allowedTiers")
        if allowed_tiers:
            actual_tier = model_cfg.get("tier")
            blocked = actual_tier and actual_tier not in allowed_tiers

            evaluation["tier"] = {
                "allowed": allowed_tiers,
                "actual": actual_tier,
                "blocked": blocked,
            }

            if blocked:
                return {
                    "allowed": False,
                    "reason": "tier_blocked",
                    "evaluation": evaluation,
                }

        # 3. Provider check
        allowed_providers = constraints.get("allowedProviders")
        if allowed_providers:
            actual_provider = model_cfg.get("provider")
            blocked = actual_provider and actual_provider not in allowed_providers

            evaluation["provider"] = {
                "allowed": allowed_providers,
                "actual": actual_provider,
                "blocked": blocked,
            }

            if blocked:
                return {
                    "allowed": False,
                    "reason": "provider_blocked",
                    "evaluation": evaluation,
                }

        # 4. Cost check (if maxCostUSD specified)
        max_cost = constraints.get("maxCostUSD")
        if max_cost is not None:
            # Use default token estimate for policy evaluation
            cost_data = self.estimate_cost(model_id, 2000, 500)
            if cost_data:
                estimated = cost_data["estimatedCostUSD"]
                exceeded = estimated > max_cost

                evaluation["cost"] = {
                    "max": max_cost,
                    "estimated": estimated,
                    "exceeded": exceeded,
                }

                if exceeded:
                    return {
                        "allowed": False,
                        "reason": "cost_exceeded",
                        "evaluation": evaluation,
                    }

        # All checks passed
        return {
            "allowed": True,
            "reason": None,
            "evaluation": evaluation,
        }

    @staticmethod
    def _normalize_runtime_env(raw_env: str) -> str:
        normalized = (raw_env or "").strip().lower()
        if not normalized:
            return "dev"
        return _RUNTIME_ENV_ALIASES.get(normalized, "dev")

    @staticmethod
    def _normalize_vendor_id(raw: str) -> str:
        raw = (raw or "").strip()
        if not raw:
            return raw

        alias = _ALIAS_TO_MODEL_ID.get(raw.lower())
        if alias:
            return alias

        if "/" in raw:
            return raw

        lowered = raw.lower()
        # Match GPT models and OpenAI o-series models whose IDs start with
        # "o" followed by a digit (for example, "o1", "o3", "o4").
        if lowered.startswith("gpt") or (
            lowered.startswith("o") and len(lowered) > 1 and lowered[1].isdigit()
        ):
            return f"openai/{raw}"
        if lowered.startswith("claude"):
            return f"anthropic/{raw}"
        if lowered.startswith("gemini"):
            return f"google/{raw}"
        if lowered.startswith("llama") or lowered.startswith("mixtral"):
            return f"groq/{raw}"

        return raw

    @staticmethod
    def _normalize_provider_hint(raw: str) -> str:
        normalized = (raw or "").strip().lower()
        if not normalized:
            return "openai"
        return _PROVIDER_HINT_TO_ID.get(normalized, normalized)

    @staticmethod
    def _display_endpoint_label(endpoint_key: str) -> str:
        mapping = {
            "stream": "/stream",
            "stream_v2": "/stream/v2",
            "autonomous": "/autonomous",
        }
        return mapping.get(endpoint_key, endpoint_key)


_default_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router
