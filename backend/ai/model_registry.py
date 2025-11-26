"""
LLM Model Registry for AEP (Autonomous Engineering Platform)
===========================================================

This module provides a simple in-memory registry backed by `backend/ai/llm_providers.yaml`.

The registry exposes:
- list_providers() -> List[str]
- list_models(provider=None) -> List[LLMModelInfo]  
- get_model(provider, name) -> Optional[LLMModelInfo]
- best_smart_auto() -> Optional[LLMModelInfo]

Used by:
- backend/api/routes/providers.py (BYOK provider management API)
- backend/ai/llm_router.py (model selection and routing)
- backend/ai/intent_llm_classifier.py (LLM-powered intent classification)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # make sure PyYAML is in requirements.txt


@dataclass
class LLMModelInfo:
    provider: str
    name: str
    type: str
    max_context: int
    speed_index: int
    cost_index: int
    coding_accuracy: int
    recommended: bool = False
    smart_auto_rank: int = 999
    capabilities: Dict[str, Any] = field(default_factory=dict)



    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "name": self.name,
            "type": self.type,
            "max_context": self.max_context,
            "speed_index": self.speed_index,
            "cost_index": self.cost_index,
            "coding_accuracy": self.coding_accuracy,
            "recommended": self.recommended,
            "smart_auto_rank": self.smart_auto_rank,
            "capabilities": self.capabilities or {},
        }


class LLMModelRegistry:
    """
    Simple in-memory registry backed by `backend/ai/llm_providers.yaml`.

    This is read-only at runtime; if the YAML changes you restart the
    backend or add a reload hook.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            # Root of repo: backend/ai/model_registry.py -> backend/ai
            config_path = Path(__file__).with_name("llm_providers.yaml")

        self._config_path = config_path
        self._providers: Dict[str, Dict[str, LLMModelInfo]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def list_providers(self) -> List[str]:
        return sorted(self._providers.keys())

    def list_models(self, provider: Optional[str] = None) -> List[LLMModelInfo]:
        if provider:
            return list(self._providers.get(provider, {}).values())
        models: List[LLMModelInfo] = []
        for p in self._providers.values():
            models.extend(p.values())
        return models

    def get_model(self, provider: str, name: str) -> Optional[LLMModelInfo]:
        return self._providers.get(provider, {}).get(name)

    def best_smart_auto(self) -> Optional[LLMModelInfo]:
        # Pick globally best ranked model (lower = better)
        all_models = self.list_models()
        if not all_models:
            return None
        return sorted(all_models, key=lambda m: m.smart_auto_rank)[0]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        try:
            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            # No config file found, start with empty registry
            raw = {"providers": {}}
        
        providers_cfg = raw.get("providers", {})

        for provider_key, provider_data in providers_cfg.items():
            models_cfg = provider_data.get("models", {})
            self._providers[provider_key] = {}

            for model_name, model_data in models_cfg.items():
                info = LLMModelInfo(
                    provider=model_data.get("provider", provider_key),
                    name=model_name,
                    type=model_data.get("type", "text"),
                    max_context=int(model_data.get("max_context", 0)),
                    speed_index=int(model_data.get("speed_index", 3)),
                    cost_index=int(model_data.get("cost_index", 3)),
                    coding_accuracy=int(model_data.get("coding_accuracy", 3)),
                    recommended=bool(model_data.get("recommended", False)),
                    smart_auto_rank=int(model_data.get("smart_auto_rank", 999)),
                    capabilities=model_data.get("capabilities") or {},
                )
                self._providers[provider_key][model_name] = info

    # For debugging
    def dump_json(self) -> str:
        return json.dumps(
            {
                provider: {
                    name: m.to_dict()
                    for name, m in models.items()
                }
                for provider, models in self._providers.items()
            },
            indent=2,
            sort_keys=True,
        )


# ============================================================================
# Convenience functions for common use cases
# ============================================================================

# Global registry instance (lazy loaded)
_registry_instance: Optional[LLMModelRegistry] = None


def get_registry() -> LLMModelRegistry:
    """Get the global model registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = LLMModelRegistry()
    return _registry_instance


def list_providers() -> List[str]:
    """Convenience function to list all providers."""
    return get_registry().list_providers()


def list_models(provider: Optional[str] = None) -> List[LLMModelInfo]:
    """Convenience function to list models."""
    return get_registry().list_models(provider)


def smart_auto_candidates() -> List[LLMModelInfo]:
    """Get top 3 models for smart auto selection."""
    all_models = get_registry().list_models()
    return sorted(all_models, key=lambda m: m.smart_auto_rank)[:3]