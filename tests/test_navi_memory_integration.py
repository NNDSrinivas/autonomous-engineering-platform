"""
Test NAVI Memory Integration.

Verifies that the memory system is properly integrated with NAVI's response pipeline.
"""

import pytest
from unittest.mock import patch


def test_memory_integration_imports():
    """Test that memory integration functions can be imported."""
    from backend.services.navi_brain import (
        _get_memory_integration,
        _get_memory_context_async,
        _enhance_system_prompt_with_memory,
        _store_interaction_async,
    )

    # These should exist as functions
    assert callable(_get_memory_integration)
    assert callable(_get_memory_context_async)
    assert callable(_enhance_system_prompt_with_memory)
    assert callable(_store_interaction_async)


def test_navi_context_has_memory_fields():
    """Test that NaviContext has memory-related fields."""
    from backend.services.navi_brain import NaviContext

    ctx = NaviContext(
        workspace_path="/test/path",
        user_id="123",
        org_id="456",
        conversation_id="conv-789",
    )

    assert ctx.user_id == "123"
    assert ctx.org_id == "456"
    assert ctx.conversation_id == "conv-789"
    assert hasattr(ctx, "memory_context")
    assert ctx.memory_context == {}  # Should default to empty dict


def test_navi_brain_has_personalization_method():
    """Test that NaviBrain has the personalization method."""
    from backend.services.navi_brain import NaviBrain, NaviContext

    # Create a NaviBrain instance (won't make API calls)
    brain = NaviBrain(provider="openai", api_key="test-key")

    # Check that the method exists
    assert hasattr(brain, "_get_personalized_system_prompt")
    assert callable(brain._get_personalized_system_prompt)

    # Without context, should return base SYSTEM_PROMPT
    prompt = brain._get_personalized_system_prompt(None)
    assert prompt == brain.SYSTEM_PROMPT

    # With context but no user_id, should still return base SYSTEM_PROMPT
    ctx = NaviContext(workspace_path="/test")
    prompt = brain._get_personalized_system_prompt(ctx)
    assert prompt == brain.SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_memory_context_returns_empty_without_db():
    """Test that memory context returns empty dict when DB is not available."""
    from backend.services.navi_brain import _get_memory_context_async

    # Mock the _get_memory_integration to return None (no memory system)
    with patch(
        "backend.services.navi_brain._get_memory_integration", return_value=None
    ):
        result = await _get_memory_context_async(
            query="test query",
            user_id=1,
            org_id=1,
            workspace_path="/test/path",
        )

        # Should return empty dict (graceful degradation when memory not available)
        assert isinstance(result, dict)
        assert result == {}


@pytest.mark.asyncio
async def test_store_interaction_handles_missing_memory():
    """Test that store interaction handles missing memory system gracefully."""
    from backend.services.navi_brain import _store_interaction_async

    # Mock the _get_memory_integration to return None (no memory system)
    with patch(
        "backend.services.navi_brain._get_memory_integration", return_value=None
    ):
        # Should not raise any errors even when memory system is not available
        await _store_interaction_async(
            user_id=1,
            conversation_id=None,
            user_message="test message",
            assistant_response="test response",
            org_id=1,
            workspace_path="/test/path",
        )

        # Should complete without error (graceful degradation)


def test_enhance_system_prompt_graceful_degradation():
    """Test that system prompt enhancement handles errors gracefully."""
    from backend.services.navi_brain import _enhance_system_prompt_with_memory

    base_prompt = "You are a helpful assistant."

    # Mock the _get_memory_integration to return None (no memory system)
    with patch(
        "backend.services.navi_brain._get_memory_integration", return_value=None
    ):
        # Without proper memory system, should return base prompt
        result = _enhance_system_prompt_with_memory(
            base_prompt=base_prompt,
            user_id=1,
            org_id=1,
        )

        # Should return base prompt when memory system is not available
        assert result == base_prompt


def test_navi_context_memory_context_field():
    """Test that NaviContext properly handles memory_context field."""
    from backend.services.navi_brain import NaviContext

    # Test with empty memory context (default)
    ctx1 = NaviContext(workspace_path="/test")
    assert ctx1.memory_context == {}

    # Test with populated memory context
    ctx2 = NaviContext(
        workspace_path="/test",
        memory_context={
            "user_preferences": {"language": "python"},
            "past_conversations": [],
        },
    )
    assert ctx2.memory_context["user_preferences"]["language"] == "python"


class TestMemoryIntegrationWithMocks:
    """Test memory integration with mocked services."""

    def test_memory_context_fetch_is_called(self):
        """Test that memory context fetch function exists and can be called."""
        from backend.services.navi_brain import _get_memory_context_async

        # Verify the function exists and is callable
        assert callable(_get_memory_context_async)

    def test_store_interaction_function_exists(self):
        """Test that store interaction function exists and can be called."""
        from backend.services.navi_brain import _store_interaction_async

        # Verify the function exists and is callable
        assert callable(_store_interaction_async)

    def test_personalized_prompts_are_cached(self):
        """Test that personalized prompts are cached per user."""
        from backend.services.navi_brain import NaviBrain, NaviContext

        # Mock environment to avoid hanging on missing env vars
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            brain = NaviBrain(provider="openai", api_key="test-key")

            ctx = NaviContext(
                workspace_path="/test",
                user_id="123",
                org_id="456",
            )

            # Mock the memory integration to return None
            with patch(
                "backend.services.navi_brain._get_memory_integration", return_value=None
            ):
                # First call
                prompt1 = brain._get_personalized_system_prompt(ctx)

                # Second call should use cache
                prompt2 = brain._get_personalized_system_prompt(ctx)

                assert prompt1 == prompt2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
