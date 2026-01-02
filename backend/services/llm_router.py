"""
LLM Router Service for Orchestrator

Provides routing and management of LLM requests for the orchestrator.
Wraps the existing LLM service with additional routing capabilities.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from backend.services.llm import get_openai_client

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
    Currently uses OpenAI GPT-4 as the default model.
    """
    
    def __init__(self):
        """Initialize the LLM router."""
        self.client = None
        self.default_model = "gpt-4"
        self.smart_auto_model = "gpt-4"
    
    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self.client is None:
            self.client = get_openai_client()
        return self.client
    
    async def run(
        self, 
        prompt: str, 
        use_smart_auto: bool = False,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Execute an LLM request with intelligent routing.
        
        Args:
            prompt: The prompt to send to the LLM
            use_smart_auto: Whether to use smart auto-routing for model selection
            model: Specific model to use (overrides smart auto)
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            
        Returns:
            LLMResponse with generated text and metadata
        """
        try:
            # Determine which model to use
            selected_model = model or (self.smart_auto_model if use_smart_auto else self.default_model)
            
            client = self._get_client()
            
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Make the API call
            response = await client.chat.completions.create(
                model=selected_model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response text
            response_text = response.choices[0].message.content or ""
            
            # Create usage info
            usage_info = None
            if response.usage:
                usage_info = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return LLMResponse(
                text=response_text,
                model=selected_model,
                usage=usage_info,
                metadata={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "use_smart_auto": use_smart_auto
                }
            )
            
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            logger.error(f"Prompt: {prompt[:200]}..." if len(prompt) > 200 else f"Prompt: {prompt}")
            
            # Return error response
            return LLMResponse(
                text=f"Error: LLM request failed - {str(e)}",
                model=selected_model or self.default_model,
                metadata={"error": str(e)}
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
                "recommended_model": "gpt-4|gpt-3.5-turbo",
                "reasoning": "Brief explanation"
            }}
            """
            
            response = await self.run(prompt=analysis_prompt, use_smart_auto=True)
            
            try:
                analysis = json.loads(response.text)
                return analysis
            except json.JSONDecodeError:
                # Fallback analysis
                return {
                    "complexity": "moderate",
                    "capabilities": ["reasoning"],
                    "response_length": "medium",
                    "time_sensitivity": "normal",
                    "recommended_model": "gpt-4",
                    "reasoning": "Default analysis due to parsing error"
                }
                
        except Exception as e:
            logger.error(f"Instruction analysis failed: {e}")
            return {
                "complexity": "moderate",
                "capabilities": ["reasoning"],
                "response_length": "medium", 
                "time_sensitivity": "normal",
                "recommended_model": "gpt-4",
                "reasoning": f"Default analysis due to error: {str(e)}"
            }
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models.
        
        Returns:
            List of available model names
        """
        return [
            "gpt-4",
            "gpt-4-turbo-preview",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
    
    def set_default_model(self, model: str) -> None:
        """
        Set the default model for non-smart-auto requests.
        
        Args:
            model: Model name to set as default
        """
        if model in self.get_available_models():
            self.default_model = model
        else:
            logger.warning(f"Unknown model {model}, keeping default {self.default_model}")
    
    def set_smart_auto_model(self, model: str) -> None:
        """
        Set the model for smart auto requests.
        
        Args:
            model: Model name to set for smart auto
        """
        if model in self.get_available_models():
            self.smart_auto_model = model
        else:
            logger.warning(f"Unknown model {model}, keeping smart auto {self.smart_auto_model}")