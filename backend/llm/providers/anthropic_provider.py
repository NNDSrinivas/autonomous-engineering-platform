import os
import anthropic
from typing import Dict, Any


class AnthropicProvider:
    """Anthropic API provider for LLM completions."""

    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Model-specific pricing (per 1K tokens) - map actual API model names to pricing
        self.pricing = {
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        }

    def complete(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion using Anthropic API."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.1,
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
                raise RuntimeError(
                    f"Anthropic API returned empty content for model {self.model}"
                )

            return {
                "text": message.content[0].text,
                "tokens": usage.input_tokens + usage.output_tokens,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": round(cost_usd, 6),
            }

        except Exception as e:
            raise RuntimeError(f"Anthropic API error for model {self.model}: {str(e)}")
