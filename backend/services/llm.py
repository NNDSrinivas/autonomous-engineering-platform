"""
LLM Service - Wrapper for LLM API calls

Multi-provider wrapper for NAVI agent using the LLM Router.
Supports Anthropic, OpenAI, Google, and other providers.
"""

import logging
import os
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client (lazy initialization to avoid startup errors)
_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """Get or initialize OpenAI client with proper error handling."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable."
            )
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def call_llm(
    message: str, context: Dict[str, Any], model: str = "gpt-4", mode: str = "chat"
) -> str:
    """
    Call LLM with message and context.

    Uses the multi-provider LLM router which respects the model parameter.

    Args:
        message: User's message
        context: Full context from context_builder
        model: LLM model to use (e.g., "gpt-4o", "openai/gpt-4o", "claude-3-5-sonnet")
        mode: "chat" or "agent-full"

    Returns:
        LLM's response as string
    """

    try:
        # Use the multi-provider LLM router
        from backend.ai.llm_router import LLMRouter

        router = LLMRouter()

        # Build system prompt with context
        system_prompt = _build_system_prompt(context)

        # Parse model string (may be "provider/model" format)
        provider = None
        model_name = model
        if model and "/" in model:
            parts = model.split("/", 1)
            provider = parts[0].lower()
            model_name = parts[1]
            # Normalize provider names
            if provider in ("openai", "gpt"):
                provider = "openai"
            elif provider in ("anthropic", "claude"):
                provider = "anthropic"
            elif provider in ("google", "gemini"):
                provider = "google"

        # Call LLM through router (uses provided model if specified)
        response = await router.run(
            prompt=message,
            system_prompt=system_prompt,
            model=model_name if model_name else None,
            provider=provider,
            use_smart_auto=False,  # Use explicit model if provided
            temperature=0.6,
        )

        if response.text is None or response.text.startswith("Error:"):
            logger.warning(f"[LLM] Router returned error: {response.text}")
            return "I couldn't generate a response. Please try again."

        logger.info(
            f"[LLM] Generated response via {response.model}: {len(response.text)} chars"
        )
        return response.text

    except Exception as e:
        logger.error(f"[LLM] Error calling LLM: {e}", exc_info=True)
        return "I encountered an error while processing your request. Could you try rephrasing?"


def _build_system_prompt(context: Dict[str, Any]) -> str:
    """Build system prompt with injected context."""

    from backend.agent.prompts import get_system_prompt

    base_prompt = get_system_prompt(
        include_tools=True, include_jira=True, include_code=True
    )

    # Inject context
    context_text = context.get("combined", "")

    if context_text:
        return f"{base_prompt}\n\n# CURRENT CONTEXT\n\n{context_text}"
    else:
        return base_prompt
