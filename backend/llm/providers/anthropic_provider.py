import os
import logging
import anthropic
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic API provider for LLM completions."""

    # Configuration constants
    MAX_TOKENS = 1500  # Maximum tokens for completion

    def __init__(self, model: str):
        self.model = model

        # Validate API key is present
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable is not set.")
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is required to use the AnthropicProvider."
            )

        self.client = anthropic.Anthropic(api_key=api_key)

        # Model-specific pricing (per 1K tokens) - map actual API model names to pricing
        self.pricing = {
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        }

    def complete(self, prompt: str, context: Dict[str, Any], temperature: float = 0.1, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Generate completion using Anthropic API."""
        # Use provided max_tokens or fall back to default
        tokens = max_tokens if max_tokens is not None else self.MAX_TOKENS
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=tokens,
                temperature=temperature,
                system=prompt,
                messages=[{"role": "user", "content": str(context)}],
            )

            usage = message.usage
            pricing = self.pricing.get(self.model, {"input": 0.008, "output": 0.008})

            # Calculate cost based on actual input/output tokens
            cost_usd = (usage.input_tokens / 1000) * pricing["input"] + (
                usage.output_tokens / 1000
            ) * pricing["output"]

            # Safely extract text content
            if not message.content or len(message.content) == 0:
                raise RuntimeError("Anthropic API returned empty content")

            # Get first text content block
            first_content = message.content[0]
            try:
                # Try to access text attribute for TextBlock
                text_content = getattr(first_content, 'text', str(first_content))
            except Exception:
                text_content = str(first_content)

            return {
                "text": text_content,
                "tokens": usage.input_tokens + usage.output_tokens,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": round(cost_usd, 6),
            }

        except Exception as e:
            logger.error(f"Anthropic API error for model {self.model}: {str(e)}")
            raise RuntimeError("Anthropic API error. Please check logs for details.")
