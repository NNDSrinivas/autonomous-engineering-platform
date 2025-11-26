"""
LLM Model Registry

Loads and validates llm_providers.yaml and exposes a simple API for:
- listing providers and models
- retrieving model metadata
- picking SMART-AUTO candidates

Validation policy (medium strict, per user choice):
- Require top-level "providers"
- For each provider:
    - require "models" dict (non-empty)
- For each model:
    - ensure it's a dict
    - ensure "provider" is set (fallback to parent provider key)
- All other fields are treated as optional / pass-through

This module is deliberately dependency-light. It uses PyYAML if
available; if not, it will raise a clear error at import/load time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Iterable

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - environment-specific
    raise RuntimeError(
        "PyYAML is required to use the LLM model registry. "
        "Install it with: pip install pyyaml"
    ) from exc


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ModelInfo:
    """Metadata for a single LLM model."""

    provider_id: str
    model_id: str
    max_context: Optional[int] = None
    speed_index: Optional[int] = None
    cost_index: Optional[int] = None
    coding_accuracy: Optional[int] = None
    smart_auto_rank: Optional[int] = None
    recommended: bool = False
    type: Optional[str] = None  # text / text+vision / legacy / etc.
    base_url: Optional[str] = None  # inherited from provider
    display_name: Optional[str] = None  # optional UI label
    # Raw / extra fields from YAML for future use
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderInfo:
    """Metadata for a provider and its models."""

    provider_id: str
    display_name: str
    base_url: str
    models: Dict[str, ModelInfo] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMRegistry:
    """In-memory registry of all providers and models."""

    version: Optional[str]
    updated: Optional[str]
    providers: Dict[str, ProviderInfo]

    # ------------------------ lookup helpers ------------------------ #

    def list_providers(self) -> List[ProviderInfo]:
        return list(self.providers.values())

    def get_provider(self, provider_id: str) -> Optional[ProviderInfo]:
        return self.providers.get(provider_id)

    def list_models(self, provider_id: Optional[str] = None) -> List[ModelInfo]:
        if provider_id is None:
            models: List[ModelInfo] = []
            for p in self.providers.values():
                models.extend(p.models.values())
            return models
        provider = self.providers.get(provider_id)
        if not provider:
            return []
        return list(provider.models.values())

    def get_model(
        self,
        model_id: str,
        provider_id: Optional[str] = None,
    ) -> Optional[ModelInfo]:
        if provider_id:
            provider = self.providers.get(provider_id)
            if not provider:
                return None
            return provider.models.get(model_id)

        # Try to find by model_id across all providers
        for provider in self.providers.values():
            if model_id in provider.models:
                return provider.models[model_id]
        return None

    def smart_auto_candidates(
        self,
        *,
        limit: int = 5,
        allowed_providers: Optional[Iterable[str]] = None,
    ) -> List[ModelInfo]:
        """
        Return SMART-AUTO candidates sorted by:
            1) smart_auto_rank (ascending, non-null)
            2) recommended flag (True first)
            3) cost_index (ascending)
            4) speed_index (descending)
        """
        allowed = set(allowed_providers) if allowed_providers else None

        models: List[ModelInfo] = []
        for provider in self.providers.values():
            if allowed and provider.provider_id not in allowed:
                continue
            for m in provider.models.values():
                if m.smart_auto_rank is None:
                    continue
                models.append(m)

        def _key(m: ModelInfo) -> Tuple[int, int, int, int]:
            # Lower rank is better; treat None as large
            rank = m.smart_auto_rank if m.smart_auto_rank is not None else 999
            # recommended True should come before False
            recommended_score = 0 if m.recommended else 1
            cost = m.cost_index if m.cost_index is not None else 5
            # higher speed_index is better, so negate for ascending sort
            speed = -(m.speed_index if m.speed_index is not None else 0)
            return (rank, recommended_score, cost, speed)

        models.sort(key=_key)
        if limit > 0:
            models = models[:limit]
        return models


# ---------------------------------------------------------------------------
# Registry loading / caching
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY_PATH = Path(__file__).with_name("llm_providers.yaml")
_registry_cache: Optional[LLMRegistry] = None


def _ensure_dict(value: Any, context: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping for {context}, got {type(value)}")
    return value


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"LLM providers YAML not found at: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Top-level YAML is not a mapping")
    return data


def _validate_and_build_registry(raw: Dict[str, Any]) -> LLMRegistry:
    version = raw.get("version")
    updated = raw.get("updated")

    providers_raw = _ensure_dict(raw.get("providers", {}), "providers")

    providers: Dict[str, ProviderInfo] = {}

    for provider_id, provider_obj in providers_raw.items():
        provider_map = _ensure_dict(provider_obj, f"provider '{provider_id}'")

        display_name = provider_map.get("display_name") or provider_id
        base_url = provider_map.get("base_url") or ""

        models_raw = _ensure_dict(
            provider_map.get("models", {}),
            f"provider '{provider_id}'.models",
        )
        if not models_raw:
            # Medium strict: provider must define at least one model
            raise ValueError(
                f"Provider '{provider_id}' has no models defined in llm_providers.yaml"
            )

        models: Dict[str, ModelInfo] = {}

        for model_id, model_obj in models_raw.items():
            model_map = _ensure_dict(
                model_obj, f"provider '{provider_id}', model '{model_id}'"
            )

            # Medium strict core fields
            model_provider = model_map.get("provider") or provider_id

            # Optional numeric fields
            max_context = model_map.get("max_context")
            speed_index = model_map.get("speed_index")
            cost_index = model_map.get("cost_index")
            coding_accuracy = model_map.get("coding_accuracy")
            smart_auto_rank = model_map.get("smart_auto_rank")

            recommended = bool(model_map.get("recommended", False))
            model_type = model_map.get("type")
            display_model_name = model_map.get("display_name")

            # Everything else stays in raw metadata
            extra_raw = dict(model_map)
            # Remove the fields we already surfaced
            for k in [
                "provider",
                "max_context",
                "speed_index",
                "cost_index",
                "coding_accuracy",
                "smart_auto_rank",
                "recommended",
                "type",
                "display_name",
            ]:
                extra_raw.pop(k, None)

            models[model_id] = ModelInfo(
                provider_id=model_provider,
                model_id=model_id,
                max_context=max_context,
                speed_index=speed_index,
                cost_index=cost_index,
                coding_accuracy=coding_accuracy,
                smart_auto_rank=smart_auto_rank,
                recommended=recommended,
                type=model_type,
                base_url=base_url,
                display_name=display_model_name or model_id,
                raw=extra_raw,
            )

        extra_provider_raw = dict(provider_map)
        for k in ["display_name", "base_url", "models"]:
            extra_provider_raw.pop(k, None)

        providers[provider_id] = ProviderInfo(
            provider_id=provider_id,
            display_name=display_name,
            base_url=base_url,
            models=models,
            raw=extra_provider_raw,
        )

    return LLMRegistry(version=version, updated=updated, providers=providers)


def load_registry(path: Optional[Path] = None, *, force_reload: bool = False) -> LLMRegistry:
    """
    Load the LLM registry from YAML.

    - If `force_reload` is False, uses an in-memory cache.
    - If `path` is None, uses llm_providers.yaml next to this file.
    """
    global _registry_cache

    registry_path = path or _DEFAULT_REGISTRY_PATH

    if _registry_cache is not None and not force_reload:
        return _registry_cache

    raw = _load_yaml(registry_path)
    registry = _validate_and_build_registry(raw)
    _registry_cache = registry
    return registry


# ---------------------------------------------------------------------------
# Convenience top-level helpers
# ---------------------------------------------------------------------------


def get_registry() -> LLMRegistry:
    """Return the cached registry, loading it on first use."""
    return load_registry()


def list_providers() -> List[ProviderInfo]:
    return get_registry().list_providers()


def list_models(provider_id: Optional[str] = None) -> List[ModelInfo]:
    return get_registry().list_models(provider_id)


def get_provider(provider_id: str) -> Optional[ProviderInfo]:
    return get_registry().get_provider(provider_id)


def get_model(model_id: str, provider_id: Optional[str] = None) -> Optional[ModelInfo]:
    return get_registry().get_model(model_id, provider_id)


def smart_auto_candidates(
    *,
    limit: int = 5,
    allowed_providers: Optional[Iterable[str]] = None,
) -> List[ModelInfo]:
    """
    Helper that proxies to registry.smart_auto_candidates.

    This is what your SMART-AUTO LLM router will typically call.
    """
    return get_registry().smart_auto_candidates(
        limit=limit,
        allowed_providers=allowed_providers,
    )