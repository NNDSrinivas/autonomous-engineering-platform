"""Unified model routing for NAVI endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


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
    ),
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

    def to_public_dict(self) -> Dict[str, Any]:
        # Keep legacy keys for current webview/extension while adding new metadata keys.
        return {
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


class ModelRouter:
    def __init__(self, registry_path: Optional[Path] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.registry_path = registry_path or (
            repo_root / "shared" / "model-registry.json"
        )
        self.registry = self._load_registry()
        self.defaults = self.registry.get("defaults", {})
        self.providers = self.registry.get("providers", [])
        self.modes = self.registry.get("naviModes", [])

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
                    self.model_index[model_id] = {
                        **model,
                        "provider": provider_id,
                        "providerType": provider.get("type", "saas"),
                    }

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

    def _load_registry(self) -> Dict[str, Any]:
        with self.registry_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

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

        selected = self._pick_first_routable(
            candidates,
            endpoint_key=endpoint_key,
            supported_providers=supported_providers,
            strict_private=strict_private,
        )

        if selected:
            selected_model_id, reason = selected
            model_cfg = self.model_index[selected_model_id]
            is_first_choice = selected_model_id == candidates[0]
            was_fallback = not is_first_choice or mode_fallback_reason is not None
            fallback_reason_code = mode_fallback_code
            fallback_reason = mode_fallback_reason

            if not is_first_choice:
                # Model candidate fallback within the mode
                fallback_reason_code = fallback_reason_code or "MODE_CANDIDATE_UNAVAILABLE"
                fallback_reason = reason or (
                    f"Primary mode candidate '{candidates[0]}' unavailable; used '{selected_model_id}'."
                )
                # If we also had a mode fallback, combine the reasons
                if mode_fallback_reason:
                    fallback_reason = f"{mode_fallback_reason} {fallback_reason}"

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

            return RoutingDecision(
                requested_model_id=None,
                requested_mode_id=requested_mode_id_original,  # Use original, not effective
                effective_model_id=default_model,
                provider=model_cfg["provider"],
                model=model_cfg.get("providerModel") or default_model.split("/", 1)[1],
                was_fallback=True,
                fallback_reason_code=mode_fallback_code or "MODE_NO_AVAILABLE_MODELS",
                fallback_reason=combined_reason,
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
    ) -> Optional[tuple[str, Optional[str]]]:
        first_failure_reason: Optional[str] = None
        for candidate in candidates:
            if self._is_model_routable(
                candidate,
                endpoint_key,
                supported_providers,
                strict_private=strict_private,
            ):
                return candidate, first_failure_reason
            if first_failure_reason is None:
                first_failure_reason = f"Candidate '{candidate}' unavailable, unsupported, or not configured."
        return None

    def _is_model_routable(
        self,
        model_id: str,
        endpoint_key: str,
        supported_providers: set[str],
        strict_private: bool,
    ) -> bool:
        model_cfg = self.model_index.get(model_id)
        if not model_cfg:
            return False

        provider = model_cfg["provider"]
        provider_cfg = self.provider_index.get(provider, {})
        provider_type = provider_cfg.get("type", "saas")

        if strict_private and provider_type not in {"local", "self_hosted"}:
            return False

        if provider not in supported_providers:
            return False

        if not self._is_provider_configured(provider):
            return False

        # TODO(navi-model-router-v2): gate by model capabilities from registry
        # (streaming/tools/json/vision/search). V1 routability is provider-level.
        return True

    def _is_provider_configured(self, provider_id: str) -> bool:
        # Ollama defaults to localhost:11434, so it's always available
        # even without OLLAMA_BASE_URL being set.
        if provider_id == "ollama":
            return True

        keys = _PROVIDER_CREDENTIAL_KEYS.get(provider_id, ())
        if not keys:
            # Unknown providers are treated as unavailable.
            return False
        return any(bool(os.getenv(key)) for key in keys)

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
        # Match GPT models and o-series models (o1, o3, o4, etc.) but not "ollama" or "openrouter"
        if lowered.startswith("gpt") or (lowered.startswith("o") and len(lowered) > 1 and lowered[1].isdigit()):
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
