import os
import openai
from typing import Dict, Any

class OpenAIProvider:
    """OpenAI API provider for LLM completions."""
    
    def __init__(self, model: str):
        self.model = model
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Model-specific pricing (per 1K tokens) - map actual API model names to pricing
        self.pricing = {
            "gpt-4-1106-preview": {"input": 0.03, "output": 0.06},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
        }
    
    def complete(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": str(context)}
                ],
                max_tokens=1500,
                temperature=0.1,
                top_p=0.9
            )
            
            usage = response.usage
            pricing = self.pricing.get(self.model, {"input": 0.01, "output": 0.01})
            
            # Calculate cost based on actual input/output tokens
            cost_usd = (
                (usage.prompt_tokens / 1000) * pricing["input"] +
                (usage.completion_tokens / 1000) * pricing["output"]
            )
            
            return {
                "text": response.choices[0].message.content.strip(),
                "tokens": usage.total_tokens,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "cost_usd": round(cost_usd, 6)
            }
            
        except Exception as e:
            raise RuntimeError(f"OpenAI API error for model {self.model}: {str(e)}")