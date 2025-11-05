import os
import logging
import openai
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI API provider for LLM completions."""

    # Configuration constants
    MAX_TOKENS = 1500  # Maximum tokens for completion

    def __init__(self, model: str):
        self.model = model

        # Validate API key is present
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. Please set it to your OpenAI API key."
            )

        self.client = openai.OpenAI(api_key=api_key)

        # Model-specific pricing (per 1K tokens) - map actual API model names to pricing
        self.pricing = {
            "gpt-4-1106-preview": {"input": 0.03, "output": 0.06},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        }

    def complete(self, prompt: str, context: Dict[str, Any], temperature: float = 0.1, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Generate completion using OpenAI API."""
        # Use provided max_tokens or fall back to default
        tokens = max_tokens if max_tokens is not None else self.MAX_TOKENS
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": str(context)},
                ],
                max_tokens=tokens,
                temperature=temperature,
                top_p=0.9,
            )

            usage = response.usage
            pricing = self.pricing.get(self.model, {"input": 0.01, "output": 0.01})

            # Safely extract response content
            if not response.choices or len(response.choices) == 0:
                raise RuntimeError("OpenAI API returned empty choices")

            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI API returned null content")

            # Handle potential None usage object
            if usage is None:
                logger.warning(f"OpenAI API returned null usage for model {self.model}")
                return {
                    "text": content.strip(),
                    "tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                }

            # Calculate cost based on actual input/output tokens
            cost_usd = (usage.prompt_tokens / 1000) * pricing["input"] + (
                usage.completion_tokens / 1000
            ) * pricing["output"]

            return {
                "text": content.strip(),
                "tokens": usage.total_tokens,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "cost_usd": round(cost_usd, 6),
            }

        except Exception as e:
            logger.error(f"OpenAI API error for model {self.model}: {str(e)}")
            raise RuntimeError(
                "OpenAI API error. Please check your request and try again."
            )
