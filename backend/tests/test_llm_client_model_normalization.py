from backend.services.llm_client import LLMConfig, LLMProvider, OpenAIAdapter


def _adapter(provider: LLMProvider, model: str) -> OpenAIAdapter:
    return OpenAIAdapter(LLMConfig(provider=provider, model=model))


def test_normalize_strips_internal_provider_prefix_for_openai() -> None:
    adapter = _adapter(LLMProvider.OPENAI, "openai/gpt-4o")
    assert adapter._normalize_openai_model_name("openai/gpt-4o") == "gpt-4o"


def test_normalize_preserves_namespaced_openrouter_model_id() -> None:
    adapter = _adapter(LLMProvider.OPENROUTER, "anthropic/claude-3.5-sonnet")
    assert (
        adapter._normalize_openai_model_name("anthropic/claude-3.5-sonnet")
        == "anthropic/claude-3.5-sonnet"
    )


def test_normalize_strips_explicit_openrouter_prefix_only() -> None:
    adapter = _adapter(
        LLMProvider.OPENROUTER,
        "openrouter/anthropic/claude-3.5-sonnet",
    )
    assert (
        adapter._normalize_openai_model_name("openrouter/anthropic/claude-3.5-sonnet")
        == "anthropic/claude-3.5-sonnet"
    )


def test_normalize_preserves_together_namespaced_model_id() -> None:
    adapter = _adapter(LLMProvider.TOGETHER, "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    assert (
        adapter._normalize_openai_model_name("meta-llama/Llama-3.3-70B-Instruct-Turbo")
        == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    )
