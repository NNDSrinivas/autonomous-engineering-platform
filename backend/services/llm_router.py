"""
LLM Router Service for Orchestrator

Wrapper around the multi-provider LLM router from backend/ai/llm_router.py
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM with text and metadata."""

    text: str
    model: str = "gpt-4"
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMRouter:
    """
    LLM Router for intelligent routing of requests to different models.
    Wraps the multi-provider router from backend/ai/llm_router.py
    """

    def __init__(self):
        """Initialize the LLM router."""
        from backend.ai.llm_router import LLMRouter as MultiProviderRouter
        self._router = MultiProviderRouter()

    async def run(
        self,
        prompt: str,
        use_smart_auto: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Execute an LLM request with intelligent routing.

        Args:
            prompt: The prompt to send to the LLM
            use_smart_auto: Whether to use smart auto-routing for model selection
            model: Specific model to use (overrides smart auto)
            provider: Specific provider to use
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with generated text and metadata
        """
        try:
            resolved_max_tokens = max_tokens if max_tokens is not None else 4096
            response = await self._router.run(
                prompt=prompt,
                system_prompt=system_prompt,
                use_smart_auto=use_smart_auto,
                model=model,
                provider=provider,
                temperature=temperature,
                max_tokens=resolved_max_tokens,
            )

            return LLMResponse(
                text=response.text,
                model=response.model,
                usage=response.usage,
                metadata=response.metadata,
            )

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return LLMResponse(
                text=f"Error: LLM request failed - {str(e)}",
                model=model or "unknown",
                metadata={"error": str(e)},
            )

    async def analyze_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        Analyze an instruction to determine routing strategy.

        Args:
            instruction: The instruction to analyze

        Returns:
            Dictionary with analysis results
        """
        try:
            import json
            analysis_prompt = f"""
            Analyze this instruction to determine the best LLM routing strategy:

            Instruction: {instruction}

            Consider:
            1. Complexity level (simple, moderate, complex)
            2. Required capabilities (coding, reasoning, creativity, factual)
            3. Expected response length (short, medium, long)
            4. Time sensitivity (urgent, normal, batch)

            Respond with JSON:
            {{
                "complexity": "simple|moderate|complex",
                "capabilities": ["coding", "reasoning", "creativity", "factual"],
                "response_length": "short|medium|long",
                "time_sensitivity": "urgent|normal|batch",
                "recommended_model": "gpt-4|claude-sonnet",
                "reasoning": "Brief explanation"
            }}
            """

            response = await self.run(prompt=analysis_prompt, use_smart_auto=True)

            try:
                analysis = json.loads(response.text)
                return analysis
            except json.JSONDecodeError:
                return {
                    "complexity": "moderate",
                    "capabilities": ["reasoning"],
                    "response_length": "medium",
                    "time_sensitivity": "normal",
                    "recommended_model": "gpt-4",
                    "reasoning": "Default analysis due to parsing error",
                }

        except Exception as e:
            logger.error(f"Instruction analysis failed: {e}")
            return {
                "complexity": "moderate",
                "capabilities": ["reasoning"],
                "response_length": "medium",
                "time_sensitivity": "normal",
                "recommended_model": "gpt-4",
                "reasoning": f"Default analysis due to error: {str(e)}",
            }

    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return [
            "gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo",
            "claude-sonnet-4-20241022", "claude-3.5-sonnet",
            "gemini-1.5-pro", "gemini-1.5-flash"
        ]

    def set_default_model(self, model: str) -> None:
        """Set the default model for non-smart-auto requests."""
        logger.info(f"Default model set to {model}")

    def set_smart_auto_model(self, model: str) -> None:
        """Set the model for smart auto requests."""
        logger.info(f"Smart auto model set to {model}")
