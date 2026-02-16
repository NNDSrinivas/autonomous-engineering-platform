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


def _map_error_type(status_code: int) -> str:
    """Map HTTP status code to error type for health tracking"""
    if status_code == 401 or status_code == 403:
        return "auth"
    elif status_code == 429:
        return "rate_limit"
    elif status_code >= 500:
        return "http"
    else:
        return "unknown"


class BaseLLMAdapter(ABC):
    """Base adapter for LLM providers"""

    def __init__(self, config: LLMConfig, health_tracker=None, health_provider_id=None):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self.health_tracker = health_tracker
        self.health_provider_id = health_provider_id

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

    def _normalize_openai_model_name(self, model: str) -> str:
        """Normalize internal provider-qualified model IDs for OpenAI-compatible APIs."""
        normalized = (model or "").strip()
        if "/" not in normalized:
            return normalized

        prefix, remainder = normalized.split("/", 1)
        provider_prefixes = {provider.value for provider in LLMProvider}
        preserve_namespaced = {LLMProvider.OPENROUTER, LLMProvider.TOGETHER}

        # OpenRouter/Together model IDs are frequently namespaced (for example,
        # anthropic/claude-3.5-sonnet and meta-llama/Llama-3.3-70B-...).
        if self.config.provider in preserve_namespaced:
            if prefix == self.config.provider.value:
                return remainder
            return normalized

        # Strip only internal provider-qualified IDs (openai/gpt-4o, groq/llama-...).
        if prefix in provider_prefixes:
            return remainder
        return normalized

    @staticmethod
    def _parse_error_body(response: httpx.Response) -> Union[Dict[str, Any], str]:
        """Best-effort parse of provider error body for actionable diagnostics."""
        try:
            return response.json()
        except Exception:
            return response.text

    @staticmethod
    def _summarize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize request payload without exposing sensitive content."""
        if not isinstance(payload, dict):
            return {"payload_type": type(payload).__name__}

        messages = payload.get("messages", [])
        message_count = len(messages) if isinstance(messages, list) else 0

        summary = {
            "payload_keys": sorted(payload.keys()),
            "model": payload.get("model"),
            "message_count": message_count,
            "stream": payload.get("stream"),
        }
        if "max_tokens" in payload:
            summary["max_tokens"] = payload["max_tokens"]
        if "temperature" in payload:
            summary["temperature"] = payload["temperature"]
        return summary

    @staticmethod
    def _summarize_error(error_body: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Summarize error response without exposing sensitive details."""
        if isinstance(error_body, dict):
            # Extract only high-level error info, not detailed messages that may contain user data
            error_data = error_body.get("error", {})
            if isinstance(error_data, dict):
                return {
                    "error_type": error_data.get("type"),
                    "error_code": error_data.get("code"),
                }
            return {"error_keys": sorted(error_body.keys())}
        # For string errors, only log type and length
        return {"error_type": "string", "length": len(str(error_body))}

    @staticmethod
    def _extract_error_code(error_body: Union[Dict[str, Any], str]) -> str | None:
        """Extract non-sensitive error code/type for exception messages."""
        if isinstance(error_body, dict):
            error_data = error_body.get("error", {})
            if isinstance(error_data, dict):
                # Try common error code/type fields
                return (
                    error_data.get("code")
                    or error_data.get("type")
                    or error_body.get("code")
                    or error_body.get("type")
                )
        return None

    def _log_openai_400_debug(
        self,
        *,
        endpoint: str,
        model: str,
        stream: bool,
        payload: Dict[str, Any],
        error_body: Union[Dict[str, Any], str],
    ) -> None:
        logger.error(
            "[LLMClient] OpenAI-compatible 400 debug | provider=%s model=%s endpoint=%s stream=%s payload_summary=%s error_summary=%s",
            self.config.provider.value,
            model,
            endpoint,
            stream,
            self._summarize_payload(payload),
            self._summarize_error(error_body),
        )

    async def complete(self, messages: List[LLMMessage]) -> LLMResponse:
        api_key = self._get_api_key()
        api_base = self._get_api_base()
        normalized_model = self._normalize_openai_model_name(self.config.model)

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
            "model": normalized_model,
            "messages": msgs,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            **self.config.extra_params,
        }

        # OpenAI GPT-4o/GPT-4.1/GPT-4.2/GPT-5/o-series expect max_completion_tokens
        # on /chat/completions; max_tokens can trigger 400 invalid_request_error.
        model_name = normalized_model.lower()
        if self.config.provider == LLMProvider.OPENAI and any(
            x in model_name
            for x in ["gpt-4o", "gpt-5", "gpt-4.2", "gpt-4.1", "o1", "o3", "o4"]
        ):
            payload["max_completion_tokens"] = self.config.max_tokens
        else:
            payload["max_tokens"] = self.config.max_tokens

        if self.config.tools:
            payload["tools"] = self.config.tools
        if self.config.tool_choice:
            payload["tool_choice"] = self.config.tool_choice

        endpoint = f"{api_base}/chat/completions"
        logger.info(
            "[LLMClient] OpenAI request | provider=%s endpoint=%s model=%s stream=%s messages=%s has_tools=%s",
            self.config.provider.value,
            endpoint,
            normalized_model,
            False,
            len(msgs),
            bool(payload.get("tools")),
        )

        provider_id = self.health_provider_id or self.config.provider.value

        try:
            response = await self.client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise

        if response.status_code >= 400:
            error_body = self._parse_error_body(response)
            if self.health_tracker:
                self.health_tracker.record_failure(
                    provider_id,
                    _map_error_type(response.status_code),
                )
            if response.status_code == 400:
                self._log_openai_400_debug(
                    endpoint=endpoint,
                    model=normalized_model,
                    stream=False,
                    payload=payload,
                    error_body=error_body,
                )
            # Raise sanitized error to avoid leaking provider error bodies into API responses/events
            error_code = self._extract_error_code(error_body)
            if error_code:
                raise RuntimeError(
                    f"OpenAI-compatible API error (status={response.status_code}, code={error_code})"
                )
            raise RuntimeError(
                f"OpenAI-compatible API error (status={response.status_code}). See server logs for details."
            )
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        resp = LLMResponse(
            content=message.get("content", ""),
            model=data.get("model", self.config.model),
            provider=self.config.provider.value,
            usage=data.get("usage", {}),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
            raw_response=data,
        )

        # Success - record after all error paths checked
        if self.health_tracker:
            self.health_tracker.record_success(provider_id)

        return resp

    async def stream(self, messages: List[LLMMessage]) -> AsyncGenerator[str, None]:
        api_key = self._get_api_key()
        api_base = self._get_api_base()
        normalized_model = self._normalize_openai_model_name(self.config.model)

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
        model_name = normalized_model.lower()
        if any(
            x in model_name
            for x in ["gpt-4o", "gpt-5", "gpt-4.2", "gpt-4.1", "o1", "o3", "o4"]
        ):
            payload = {
                "model": normalized_model,
                "messages": msgs,
                "temperature": self.config.temperature,
                "max_completion_tokens": self.config.max_tokens,
                "stream": True,
            }
        else:
            payload = {
                "model": normalized_model,
                "messages": msgs,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "stream": True,
            }

        endpoint = f"{api_base}/chat/completions"
        provider_id = self.health_provider_id or self.config.provider.value

        try:
            async with self.client.stream(
                "POST",
                endpoint,
                headers=headers,
                json=payload,
            ) as response:
                logger.info(
                    "[LLMClient] OpenAI request | provider=%s endpoint=%s model=%s stream=%s messages=%s has_tools=%s",
                    self.config.provider.value,
                    endpoint,
                    normalized_model,
                    True,
                    len(msgs),
                    bool(payload.get("tools")),
                )
                if response.status_code >= 400:
                    if self.health_tracker:
                        self.health_tracker.record_failure(
                            provider_id,
                            _map_error_type(response.status_code),
                        )
                    error_text = (await response.aread()).decode(errors="replace")
                    try:
                        error_body: Union[Dict[str, Any], str] = json.loads(error_text)
                    except Exception:
                        error_body = error_text

                    if response.status_code == 400:
                        self._log_openai_400_debug(
                            endpoint=endpoint,
                            model=normalized_model,
                            stream=True,
                            payload=payload,
                            error_body=error_body,
                        )
                    else:
                        max_log_length = 4096
                        if len(error_text) > max_log_length:
                            error_text = error_text[:max_log_length] + "...[truncated]"
                        logger.error(
                            "OpenAI API error: %s - %s",
                            response.status_code,
                            error_text,
                        )
                    # Raise sanitized error to avoid leaking provider error bodies into API responses/events
                    error_code = self._extract_error_code(error_body)
                    if error_code:
                        raise RuntimeError(
                            f"OpenAI-compatible API error (status={response.status_code}, code={error_code})"
                        )
                    raise RuntimeError(
                        f"OpenAI-compatible API error (status={response.status_code}). See server logs for details."
                    )
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
        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise
        else:
            # Success - only if no exception
            if self.health_tracker:
                self.health_tracker.record_success(provider_id)


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

        provider_id = self.health_provider_id or self.config.provider.value

        try:
            response = await self.client.post(
                f"{api_base}/messages",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise

        if response.status_code >= 400:
            if self.health_tracker:
                self.health_tracker.record_failure(
                    provider_id,
                    _map_error_type(response.status_code),
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

        resp = LLMResponse(
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

        # Success - record after all error paths checked
        if self.health_tracker:
            self.health_tracker.record_success(provider_id)

        return resp

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

        provider_id = self.health_provider_id or self.config.provider.value

        try:
            async with self.client.stream(
                "POST",
                f"{api_base}/messages",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    if self.health_tracker:
                        self.health_tracker.record_failure(
                            provider_id,
                            _map_error_type(response.status_code),
                        )
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

            # Success - stream completed without errors
            if self.health_tracker:
                self.health_tracker.record_success(provider_id)

        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise


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
        provider_id = self.health_provider_id or self.config.provider.value

        try:
            response = await self.client.post(url, json=payload)
        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise

        if response.status_code >= 400:
            if self.health_tracker:
                self.health_tracker.record_failure(
                    provider_id,
                    _map_error_type(response.status_code),
                )
            response.raise_for_status()

        data = response.json()

        # Extract content from Gemini response
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                content += part.get("text", "")

        resp = LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider.value,
            usage=data.get("usageMetadata", {}),
            finish_reason=candidates[0].get("finishReason") if candidates else None,
            raw_response=data,
        )

        # Success - record after all error paths checked
        if self.health_tracker:
            self.health_tracker.record_success(provider_id)

        return resp

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
        provider_id = self.health_provider_id or self.config.provider.value

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    if self.health_tracker:
                        self.health_tracker.record_failure(
                            provider_id,
                            _map_error_type(response.status_code),
                        )
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

            # Success - stream completed without errors
            if self.health_tracker:
                self.health_tracker.record_success(provider_id)

        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise


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

        provider_id = self.health_provider_id or self.config.provider.value

        try:
            response = await self.client.post(f"{api_base}/chat", json=payload)
        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise

        if response.status_code >= 400:
            if self.health_tracker:
                self.health_tracker.record_failure(
                    provider_id,
                    _map_error_type(response.status_code),
                )
            response.raise_for_status()

        data = response.json()

        resp = LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", self.config.model),
            provider=self.config.provider.value,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
            raw_response=data,
        )

        # Success - record after all error paths checked
        if self.health_tracker:
            self.health_tracker.record_success(provider_id)

        return resp

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

        provider_id = self.health_provider_id or self.config.provider.value

        try:
            async with self.client.stream(
                "POST", f"{api_base}/chat", json=payload
            ) as response:
                if response.status_code >= 400:
                    if self.health_tracker:
                        self.health_tracker.record_failure(
                            provider_id,
                            _map_error_type(response.status_code),
                        )
                    response.raise_for_status()

                async for line in response.aiter_lines():
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

            # Success - stream completed without errors
            if self.health_tracker:
                self.health_tracker.record_success(provider_id)

        except httpx.TimeoutException:
            if self.health_tracker:
                self.health_tracker.record_timeout(provider_id)
            raise
        except (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError):
            if self.health_tracker:
                self.health_tracker.record_failure(provider_id, "network")
            raise


def get_adapter(config: LLMConfig, health_tracker=None, health_provider_id=None) -> BaseLLMAdapter:
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
    return adapter_class(
        config,
        health_tracker=health_tracker,
        health_provider_id=health_provider_id,
    )


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
        health_tracker=None,
        health_provider_id: Optional[str] = None,
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

        self.health_tracker = health_tracker
        self.health_provider_id = health_provider_id
        self.adapter = get_adapter(
            self.config,
            health_tracker=self.health_tracker,
            health_provider_id=self.health_provider_id,
        )

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
            self.adapter = get_adapter(
                self.config,
                health_tracker=self.health_tracker,
                health_provider_id=self.health_provider_id,
            )

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
