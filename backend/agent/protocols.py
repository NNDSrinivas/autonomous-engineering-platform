"""
Agent Protocol Types
===================

Protocol definitions for type safety in agent modules.
"""

from __future__ import annotations

from typing import Protocol, List, Dict, Any, Optional


class SupportsLLMModelRegistry(Protocol):
    """Protocol for LLM model registry dependencies."""

    def get_available_models(self) -> List[str]:
        """Get list of available model names."""
        ...

    def get_default_model(self) -> str:
        """Get the default model name."""
        ...

    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available."""
        ...

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific model."""
        ...
