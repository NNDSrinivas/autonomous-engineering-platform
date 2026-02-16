from __future__ import annotations

import pytest

from backend.api.navi import _get_vision_provider_for_model
from backend.services.vision_service import VisionProvider


def test_openrouter_vision_defaults_to_anthropic() -> None:
    provider = _get_vision_provider_for_model("openrouter/claude-3.5-sonnet")
    assert provider == VisionProvider.ANTHROPIC


def test_openrouter_gpt_vision_uses_openai() -> None:
    provider = _get_vision_provider_for_model("openrouter/gpt-4o")
    assert provider == VisionProvider.OPENAI


def test_groq_vision_falls_back_to_anthropic() -> None:
    provider = _get_vision_provider_for_model("groq/llama-3.3-70b-versatile")
    assert provider == VisionProvider.ANTHROPIC


@pytest.mark.parametrize(
    "model_id",
    ["ollama/llama3.2", "self_hosted/qwen2.5-coder"],
)
def test_private_local_models_reject_vision(model_id: str) -> None:
    with pytest.raises(ValueError):
        _get_vision_provider_for_model(model_id)
