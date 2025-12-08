"""
LLM Service - Wrapper for LLM API calls

Simple wrapper around OpenAI API for NAVI agent.
"""

import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
import os

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

    Args:
        message: User's message
        context: Full context from context_builder
        model: LLM model to use
        mode: "chat" or "agent-full"

    Returns:
        LLM's response as string
    """

    try:
        # Build system prompt with context
        system_prompt = _build_system_prompt(context)

        # Call OpenAI
        client = get_openai_client()
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.6,
            # Remove max_tokens limit for comprehensive responses
        )

        answer = response.choices[0].message.content
        if answer is None:
            logger.warning("[LLM] Received None response from API")
            return "I couldn't generate a response. Please try again."

        logger.info(f"[LLM] Generated response: {len(answer)} chars")
        return answer

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
