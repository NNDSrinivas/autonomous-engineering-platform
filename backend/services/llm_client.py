"""
Multi-Provider LLM Client with BYOK Support

Unified interface for calling any LLM provider:
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude 3.5, Claude 3)
- Google (Gemini 2.0, Gemini 1.5)
- Groq (Llama, Mixtral)
- OpenRouter (any model)
- Ollama (local models)
- Azure OpenAI
- AWS Bedrock
- Together AI
- Mistral AI

Supports BYOK (Bring Your Own Key) - users can provide their own API keys.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Union,
)

import httpx


logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    TOGETHER = "together"
    MISTRAL = "mistral"
    LOCAL = "local"  # For local/custom endpoints


@dataclass
class LLMMessage:
    """A message in the conversation"""

    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMResponse:
    """Response from an LLM"""

    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    tool_calls: Optional[List[Dict]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class LLMConfig:
    """Configuration for LLM requests"""

    provider: LLMProvider
    model: str
    api_key: Optional[str] = None  # BYOK support
    api_base: Optional[str] = None  # Custom endpoint
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stream: bool = False
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None  # auto, none, or specific tool
    system_prompt: Optional[str] = None
    timeout: int = 120
    # Provider-specific options
    extra_params: Dict[str, Any] = field(default_factory=dict)


# Default models per provider
DEFAULT_MODELS = {
    LLMProvider.OPENAI: "gpt-4o",
    LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
    LLMProvider.GOOGLE: "gemini-2.0-flash-exp",
    LLMProvider.GROQ: "llama-3.3-70b-versatile",
    LLMProvider.OPENROUTER: "anthropic/claude-3.5-sonnet",
    LLMProvider.OLLAMA: "llama3.2",
    LLMProvider.AZURE_OPENAI: "gpt-4o",
    LLMProvider.TOGETHER: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    LLMProvider.MISTRAL: "mistral-large-latest",
}

# API base URLs
API_BASES = {
    LLMProvider.OPENAI: "https://api.openai.com/v1",
    LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
    LLMProvider.GOOGLE: "https://generativelanguage.googleapis.com/v1beta",
    LLMProvider.GROQ: "https://api.groq.com/openai/v1",
    LLMProvider.OPENROUTER: "https://openrouter.ai/api/v1",
    LLMProvider.OLLAMA: "http://localhost:11434/api",
    LLMProvider.TOGETHER: "https://api.together.xyz/v1",
    LLMProvider.MISTRAL: "https://api.mistral.ai/v1",
}


class BaseLLMAdapter(ABC):
    """Base adapter for LLM providers"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
    ) -> LLMResponse:
        """Generate a completion"""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
    ) -> AsyncGenerator[str, None]:
        """Stream a completion"""
        pass

    def _get_api_key(self) -> str:
        """Get API key from config or environment"""
        if self.config.api_key:
            return self.config.api_key

        env_vars = {
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.GOOGLE: "GOOGLE_API_KEY",
            LLMProvider.GROQ: "GROQ_API_KEY",
            LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
            LLMProvider.TOGETHER: "TOGETHER_API_KEY",
            LLMProvider.MISTRAL: "MISTRAL_API_KEY",
            LLMProvider.AZURE_OPENAI: "AZURE_OPENAI_API_KEY",
        }

        env_var = env_vars.get(self.config.provider, "")
        return os.environ.get(env_var, "")

    def _get_api_base(self) -> str:
        """Get API base URL"""
        if self.config.api_base:
            return self.config.api_base
        return API_BASES.get(self.config.provider, "")


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible APIs (Groq, Together, OpenRouter)"""

    async def complete(self, messages: List[LLMMessage]) -> LLMResponse:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # OpenRouter requires extra headers
        if self.config.provider == LLMProvider.OPENROUTER:
            headers["HTTP-Referer"] = "https://navi.ai"
            headers["X-Title"] = "NAVI Enterprise"

        # Build messages payload
        msgs = []
        if self.config.system_prompt:
            msgs.append({"role": "system", "content": self.config.system_prompt})
        for m in messages:
            msg = {"role": m.role, "content": m.content}
            if m.name:
                msg["name"] = m.name
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            msgs.append(msg)

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            **self.config.extra_params,
        }

        if self.config.tools:
            payload["tools"] = self.config.tools
        if self.config.tool_choice:
            payload["tool_choice"] = self.config.tool_choice

        response = await self.client.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        return LLMResponse(
            content=message.get("content", ""),
            model=data.get("model", self.config.model),
            provider=self.config.provider.value,
            usage=data.get("usage", {}),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
            raw_response=data,
        )

    async def stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        msgs = []
        if self.config.system_prompt:
            msgs.append({"role": "system", "content": self.config.system_prompt})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        # Use max_completion_tokens for newer OpenAI models (GPT-4o, GPT-5.x, o1/o3/o4)
        model_name = self.config.model.lower()
        if any(x in model_name for x in ["gpt-4o", "gpt-5", "gpt-4.2", "gpt-4.1", "o1", "o3", "o4"]):
            payload = {
                "model": self.config.model,
                "messages": msgs,
                "temperature": self.config.temperature,
                "max_completion_tokens": self.config.max_tokens,
                "stream": True,
            }
        else:
            payload = {
                "model": self.config.model,
                "messages": msgs,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "stream": True,
            }

        async with self.client.stream(
            "POST",
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                error_text = error_body.decode(errors="replace")
                max_log_length = 4096
                if len(error_text) > max_log_length:
                    error_text = error_text[:max_log_length] + "...[truncated]"
                logger.error(f"OpenAI API error: {response.status_code} - {error_text}")
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude API"""

    async def complete(self, messages: List[LLMMessage]) -> LLMResponse:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Extract system prompt
        system = self.config.system_prompt or ""

        # Convert messages to Anthropic format
        msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                msgs.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            **self.config.extra_params,
        }

        if system:
            payload["system"] = system

        if self.config.tools:
            # Convert OpenAI tool format to Anthropic format
            anthropic_tools = []
            for tool in self.config.tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append(
                        {
                            "name": func["name"],
                            "description": func.get("description", ""),
                            "input_schema": func.get("parameters", {}),
                        }
                    )
            if anthropic_tools:
                payload["tools"] = anthropic_tools

        response = await self.client.post(
            f"{api_base}/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Extract content from Anthropic response
        content = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                )

        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model),
            provider=self.config.provider.value,
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=data.get("stop_reason"),
            raw_response=data,
        )

    async def stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        system = self.config.system_prompt or ""
        msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                msgs.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with self.client.stream(
            "POST",
            f"{api_base}/messages",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue


class GoogleAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API"""

    async def complete(self, messages: List[LLMMessage]) -> LLMResponse:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        # Convert messages to Gemini format
        contents = []
        system_instruction = self.config.system_prompt

        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            else:
                role = "user" if m.role == "user" else "model"
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": m.content}],
                    }
                )

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "topP": self.config.top_p,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{api_base}/models/{self.config.model}:generateContent?key={api_key}"

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract content from Gemini response
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                content += part.get("text", "")

        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider.value,
            usage=data.get("usageMetadata", {}),
            finish_reason=candidates[0].get("finishReason") if candidates else None,
            raw_response=data,
        )

    async def stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        api_key = self._get_api_key()
        api_base = self._get_api_base()

        contents = []
        system_instruction = self.config.system_prompt

        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            else:
                role = "user" if m.role == "user" else "model"
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": m.content}],
                    }
                )

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{api_base}/models/{self.config.model}:streamGenerateContent?key={api_key}&alt=sse"

        async with self.client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for Ollama local models"""

    async def complete(self, messages: List[LLMMessage]) -> LLMResponse:
        api_base = self._get_api_base()

        msgs = []
        if self.config.system_prompt:
            msgs.append({"role": "system", "content": self.config.system_prompt})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        response = await self.client.post(f"{api_base}/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.config.model),
            provider=self.config.provider.value,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            raw_response=data,
        )

    async def stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        api_base = self._get_api_base()

        msgs = []
        if self.config.system_prompt:
            msgs.append({"role": "system", "content": self.config.system_prompt})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.config.model,
            "messages": msgs,
            "stream": True,
        }

        async with self.client.stream(
            "POST", f"{api_base}/chat", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


def get_adapter(config: LLMConfig) -> BaseLLMAdapter:
    """Get the appropriate adapter for the provider"""
    adapters = {
        LLMProvider.OPENAI: OpenAIAdapter,
        LLMProvider.GROQ: OpenAIAdapter,  # OpenAI-compatible
        LLMProvider.OPENROUTER: OpenAIAdapter,  # OpenAI-compatible
        LLMProvider.TOGETHER: OpenAIAdapter,  # OpenAI-compatible
        LLMProvider.MISTRAL: OpenAIAdapter,  # OpenAI-compatible
        LLMProvider.ANTHROPIC: AnthropicAdapter,
        LLMProvider.GOOGLE: GoogleAdapter,
        LLMProvider.OLLAMA: OllamaAdapter,
    }

    adapter_class = adapters.get(config.provider, OpenAIAdapter)
    return adapter_class(config)


class LLMClient:
    """
    Unified LLM client supporting all providers with BYOK.

    Usage:
        # Using environment API key
        client = LLMClient(provider="openai", model="gpt-4o")
        response = await client.complete("What is 2+2?")

        # Using BYOK (user's own API key)
        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="user-provided-key"
        )
        response = await client.complete("Explain quantum computing")

        # Streaming
        async for chunk in client.stream("Tell me a story"):
            print(chunk, end="")
    """

    def __init__(
        self,
        provider: Union[str, LLMProvider] = LLMProvider.OPENAI,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs,
    ):
        if isinstance(provider, str):
            provider = LLMProvider(provider.lower())

        self.config = LLMConfig(
            provider=provider,
            model=model or DEFAULT_MODELS.get(provider, "gpt-4o"),
            api_key=api_key,
            api_base=api_base,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            tools=tools,
            extra_params=kwargs,
        )

        self.adapter = get_adapter(self.config)

    async def complete(
        self,
        prompt: Union[str, List[LLMMessage]],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a completion.

        Args:
            prompt: Either a string (user message) or list of messages
            **kwargs: Override config options

        Returns:
            LLMResponse with the completion
        """
        if isinstance(prompt, str):
            messages = [LLMMessage(role="user", content=prompt)]
        else:
            messages = prompt

        # Apply any overrides
        if kwargs:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            self.adapter = get_adapter(self.config)

        return await self.adapter.complete(messages)

    async def stream(
        self,
        prompt: Union[str, List[LLMMessage]],
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a completion.

        Args:
            prompt: Either a string (user message) or list of messages

        Yields:
            Chunks of the response text
        """
        if isinstance(prompt, str):
            messages = [LLMMessage(role="user", content=prompt)]
        else:
            messages = prompt

        async for chunk in self.adapter.stream(messages):
            yield chunk

    async def complete_with_tools(
        self,
        prompt: Union[str, List[LLMMessage]],
        tools: List[Dict],
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """
        Generate a completion with tool/function calling support.

        Args:
            prompt: The prompt or messages
            tools: List of tools in OpenAI format
            tool_choice: "auto", "none", or specific tool name

        Returns:
            LLMResponse potentially containing tool_calls
        """
        self.config.tools = tools
        self.config.tool_choice = tool_choice
        self.adapter = get_adapter(self.config)

        if isinstance(prompt, str):
            messages = [LLMMessage(role="user", content=prompt)]
        else:
            messages = prompt

        return await self.adapter.complete(messages)


# Convenience function for quick completions
async def complete(
    prompt: str,
    provider: str = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Quick completion function.

    Args:
        prompt: The prompt
        provider: LLM provider
        model: Model name
        api_key: Optional BYOK key

    Returns:
        The completion text
    """
    client = LLMClient(
        provider=provider,
        model=model,
        api_key=api_key,
        **kwargs,
    )
    response = await client.complete(prompt)
    return response.content
