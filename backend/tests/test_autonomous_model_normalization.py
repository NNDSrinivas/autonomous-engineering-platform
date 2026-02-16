from backend.services.autonomous_agent import AutonomousAgent


def _agent(provider: str) -> AutonomousAgent:
    agent = AutonomousAgent.__new__(AutonomousAgent)
    agent.provider = provider
    return agent


def test_openai_model_prefix_is_stripped_for_openai_compatible_calls() -> None:
    agent = _agent("openai")
    assert (
        agent._normalize_openai_compatible_model_name("openai/gpt-4o")  # type: ignore[attr-defined]
        == "gpt-4o"
    )


def test_openrouter_preserves_namespaced_model_id() -> None:
    agent = _agent("openrouter")
    assert (
        agent._normalize_openai_compatible_model_name("anthropic/claude-3.5-sonnet")  # type: ignore[attr-defined]
        == "anthropic/claude-3.5-sonnet"
    )


def test_openrouter_internal_prefix_is_stripped_only_once() -> None:
    agent = _agent("openrouter")
    assert (
        agent._normalize_openai_compatible_model_name("openrouter/anthropic/claude-3.5-sonnet")  # type: ignore[attr-defined]
        == "anthropic/claude-3.5-sonnet"
    )
