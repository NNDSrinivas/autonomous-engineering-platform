from __future__ import annotations

import pytest

from backend.services.model_router import ModelRouter, ModelRoutingError


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_BASE_URL",
        "SELF_HOSTED_API_BASE_URL",
        "SELF_HOSTED_LLM_URL",
        "VLLM_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_valid_vendor_model_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route("openai/gpt-4o", endpoint="stream")

    assert decision.requested_model_id == "openai/gpt-4o"
    assert decision.effective_model_id == "openai/gpt-4o"
    assert decision.was_fallback is False
    assert decision.provider == "openai"


def test_invalid_vendor_model_falls_back_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route("openai/unknown-model", endpoint="stream")

    assert decision.was_fallback is True
    assert decision.fallback_reason_code == "UNKNOWN_MODEL_ID"
    assert decision.effective_model_id == "openai/gpt-4o"


def test_navi_mode_picks_first_available_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    router = ModelRouter()

    mode_cfg = router.mode_index["navi/intelligence"]
    # Keep this test deterministic by pinning candidates to stable IDs.
    mode_cfg["candidateModelIds"] = [
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
    ]
    expected_first_candidate = mode_cfg["candidateModelIds"][0]
    decision = router.route("navi/intelligence", endpoint="stream")

    assert decision.requested_mode_id == "navi/intelligence"
    assert decision.effective_model_id == expected_first_candidate
    assert decision.was_fallback is False


def test_private_mode_routes_to_ollama_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    router = ModelRouter()

    decision = router.route("navi/private", endpoint="stream")

    assert decision.requested_mode_id == "navi/private"
    assert decision.effective_model_id == "ollama/llama3.2"
    assert decision.provider == "ollama"
    assert decision.was_fallback is False


def test_private_mode_blocks_when_only_saas_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    with pytest.raises(ModelRoutingError) as exc:
        router.route("navi/private", endpoint="autonomous")

    assert exc.value.code == "PRIVATE_MODE_BLOCKED"


def test_alias_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route("gpt-4o", endpoint="stream")

    assert decision.requested_model_id == "openai/gpt-4o"
    assert decision.effective_model_id == "openai/gpt-4o"


def test_frontend_provider_hint_normalizes_before_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route(
        "gpt-5.1",
        endpoint="stream",
        requested_provider="openai_navra",
    )

    assert decision.requested_model_id == "openai/gpt-5.1"
    assert decision.effective_model_id == "openai/gpt-5.1"
    assert decision.was_fallback is False


def test_stream_v2_fallback_when_provider_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route("google/gemini-2.5-pro", endpoint="stream_v2")

    assert decision.was_fallback is True
    assert decision.effective_model_id == "openai/gpt-4o"
    assert decision.fallback_reason_code == "ENDPOINT_PROVIDER_UNSUPPORTED"
    assert decision.fallback_reason is not None
    assert "/stream/v2" in decision.fallback_reason
    assert "google" in decision.fallback_reason


def test_openrouter_model_routes_with_openrouter_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    router = ModelRouter()

    decision = router.route("openrouter/claude-3.5-sonnet", endpoint="autonomous")

    assert decision.requested_model_id == "openrouter/claude-3.5-sonnet"
    assert decision.effective_model_id == "openrouter/claude-3.5-sonnet"
    assert decision.provider == "openrouter"
    assert decision.model == "anthropic/claude-3.5-sonnet"
    assert decision.was_fallback is False


def test_runtime_env_alias_maps_production_to_prod() -> None:
    assert ModelRouter._normalize_runtime_env("production") == "prod"
    assert ModelRouter._normalize_runtime_env("PROD") == "prod"
