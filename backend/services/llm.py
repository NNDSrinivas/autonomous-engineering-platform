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

    Uses the multi-provider LLM router which respects DEFAULT_LLM_PROVIDER.

    Args:
        message: User's message
        context: Full context from context_builder
        model: LLM model to use (may be overridden by DEFAULT_LLM_PROVIDER)
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

        # Call LLM through router (respects DEFAULT_LLM_PROVIDER)
        response = await router.run(
            prompt=message,
            system_prompt=system_prompt,
            use_smart_auto=False,  # Let DEFAULT_LLM_PROVIDER take precedence
            temperature=0.6,
        )

        if response.text is None or response.text.startswith("Error:"):
            logger.warning(f"[LLM] Router returned error: {response.text}")
            return "I couldn't generate a response. Please try again."

        logger.info(f"[LLM] Generated response via {response.model}: {len(response.text)} chars")
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
