"""
LLM Router for AEP (Autonomous Engineering Platform)
====================================================

This module provides a unified interface for calling ANY LLM provider:

    - OpenAI
    - Anthropic (Claude)
    - Google Gemini
    - xAI (Grok)
    - Meta LLaMA (local or remote)
    - Cohere
    - Mistral

Backed by:
    llm_model_registry.py
    llm_providers.yaml

Capabilities:
    • Smart-Auto model selection
    • BYOK (Bring Your Own Key)
    • Vision + text
    • Structured output
    • Retry & exponential backoff
    • Unified response format (LLMResponse)
    • Compatible with NAVI orchestrator

"""

from __future__ import annotations

import time
import logging
import random
import asyncio
import os
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

try:
    import httpx
except ImportError as exc:
    raise RuntimeError(
        "httpx is required for LLM router. Install it with: pip install httpx"
    ) from exc

from .llm_model_registry import (
    get_registry,
    smart_auto_candidates,
    ModelInfo,
    ProviderInfo,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Unified Response Object
# ======================================================================


@dataclass
class LLMResponse:
    """
    Normalized output structure for all model providers.
    """

    text: str
    model: str
    provider: str
    raw: Dict[str, Any]
    latency_ms: float
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None

    def __repr__(self):
        return f"<LLMResponse model={self.model} provider={self.provider} latency={self.latency_ms:.0f}ms>"


# ======================================================================
# Router Exception Classes
# ======================================================================


class LLMRouterError(Exception):
    """Base exception for LLM router errors."""

    pass


class ModelNotFoundError(LLMRouterError):
    """Raised when requested model/provider combination is not found."""

    pass


class APIKeyMissingError(LLMRouterError):
    """Raised when required API key is missing."""

    pass


class ProviderError(LLMRouterError):
    """Raised when provider API returns an error."""

    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


# ======================================================================
# Router
# ======================================================================


class LLMRouter:
    """
    Main router responsible for executing requests against the chosen LLM.
    """

    def __init__(
        self,
        *,
        timeout_sec: int = 30,
        max_retries: int = 2,
        base_retry_delay: float = 0.5,
    ):
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        images: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        use_smart_auto: bool = False,
        allowed_providers: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Execute an LLM call using the selected provider & model.

        Args:
            prompt: The main user message/prompt
            model: Specific model ID (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
            provider: Provider ID (e.g., "openai", "anthropic")
            images: List of base64-encoded images for vision models
            system_prompt: System/instruction prompt
            api_key: API key for the provider (BYOK)
            org_id: Organization ID (OpenAI only)
            user_id: User identifier for tracking
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            use_smart_auto: Use SMART-AUTO model selection
            allowed_providers: Restrict SMART-AUTO to specific providers

        Returns:
            LLMResponse with normalized output

        Raises:
            ModelNotFoundError: If model/provider not found
            APIKeyMissingError: If required API key missing
            ProviderError: If provider API fails
        """

        # Select model automatically if needed
        provider_info, model_info = self._resolve_model(
            model, provider, use_smart_auto, allowed_providers
        )

        env = os.getenv("APP_ENV", "dev").lower()
        offline_configured = os.getenv("LLM_OFFLINE_MODE", "").lower() in {
            "1",
            "true",
            "yes",
        }

        # Provider-specific default API key resolution (systematic, no hardcoding)
        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "xai": "XAI_API_KEY",
            "mistral": "MISTRAL_API_KEY",
        }
        provider_env_key = provider_env_map.get(provider_info.provider_id)
        default_api_key = os.getenv(provider_env_key) if provider_env_key else None
        api_key = api_key or default_api_key

        allow_offline = offline_configured or (env in {"dev", "test", "local"} and not api_key)
        offline_reason: Optional[str] = None

        if not api_key and not allow_offline:
            # In prod/stage, require a real key to avoid degraded responses
            raise APIKeyMissingError(
                f"Missing API key for provider '{provider_info.provider_id}'. "
                f"Set {provider_env_key or 'PROVIDER_API_KEY'} or pass api_key explicitly."
            )

        if allow_offline and not api_key:
            offline_reason = f"no API key provided (env={env})"
            logger.warning("[LLM] Offline fallback enabled: %s", offline_reason)
            return self._offline_response(
                prompt=prompt,
                model=model_info.model_id,
                provider=provider_info.provider_id,
                reason=offline_reason,
            )

        logger.info(f"[LLM] Using {provider_info.provider_id}:{model_info.model_id}")

        # Prepare payload depending on provider
        request_payload = self._build_payload(
            provider_info=provider_info,
            model_info=model_info,
            prompt=prompt,
            system_prompt=system_prompt,
            images=images,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Execute with retry logic
        try:
            response_json, latency_ms = await self._execute_with_retry(
                provider_info=provider_info,
                model_info=model_info,
                payload=request_payload,
                api_key=api_key,
                org_id=org_id,
                user_id=user_id,
            )
        except Exception as exc:
            if allow_offline:
                offline_reason = offline_reason or f"LLM call failed: {exc}"
                logger.warning("[LLM] %s – returning deterministic offline response", offline_reason)
                return self._offline_response(
                    prompt=prompt,
                    model=model_info.model_id,
                    provider=provider_info.provider_id,
                    reason=offline_reason,
                )
            raise

        # Normalize final response
        text = self._extract_text(provider_info.provider_id, response_json)
        tokens_used = self._extract_token_count(
            provider_info.provider_id, response_json
        )

        return LLMResponse(
            text=text,
            model=model_info.model_id,
            provider=provider_info.provider_id,
            raw=response_json,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )

    def _offline_response(
        self,
        *,
        prompt: str,
        model: str,
        provider: str,
        reason: str,
    ) -> LLMResponse:
        """
        Deterministic offline response used when API keys are missing or network access is disabled.
        """
        preview_lines = [line for line in prompt.splitlines() if line.strip()]
        head = preview_lines[0] if preview_lines else "Request"
        snippet = head[:180] + ("…" if len(head) > 180 else "")
        text = (
            f"[offline] {snippet}\n\n"
            f"(Offline fallback active: {reason}. Provide a provider API key to enable full LLM responses.)"
        )

        return LLMResponse(
            text=text,
            model=model or "offline-model",
            provider=f"{provider}-offline",
            raw={"offline_fallback": True, "reason": reason, "preview": snippet},
            latency_ms=5.0,
            tokens_used=None,
            cost_estimate=0.0,
        )

    # ------------------------------------------------------------------
    # Model resolution
    # ------------------------------------------------------------------

    def _resolve_model(
        self,
        model: Optional[str],
        provider: Optional[str],
        use_smart_auto: bool,
        allowed_providers: Optional[List[str]],
    ) -> tuple[ProviderInfo, ModelInfo]:
        """Resolve the actual provider and model to use."""

        registry = get_registry()

        # SMART AUTO chooses best overall across all providers
        if use_smart_auto:
            candidates = smart_auto_candidates(
                limit=1,
                allowed_providers=allowed_providers,
            )
            if not candidates:
                raise ModelNotFoundError("No SMART-AUTO candidates available")

            best = candidates[0]
            logger.info(
                f"[LLM] SMART-AUTO selected: {best.provider_id}:{best.model_id}"
            )

            provider_info = registry.get_provider(best.provider_id)
            if provider_info is None:
                raise ModelNotFoundError(f"Provider {best.provider_id} not found")
            return provider_info, best

        # Explicit provider + model
        if provider and model:
            provider_info = registry.get_provider(provider)
            if provider_info is None:
                raise ModelNotFoundError(f"Provider {provider} not found")

            # Create a basic ModelInfo since we don't have get_model available
            model_info = ModelInfo(
                provider_id=provider,
                model_id=model,
            )
            return provider_info, model_info

        # Model only → find provider that contains it
        if model:
            # Search all providers for the model
            for prov in registry.list_providers():
                models = registry.list_models(prov.provider_id)
                for model_info in models:
                    if model_info.model_id == model:
                        provider_info = prov
                        return provider_info, model_info

            raise ModelNotFoundError(f"Model '{model}' not found in any provider")

        # Nothing provided → fall back to SMART AUTO
        return self._resolve_model(None, None, True, allowed_providers)

    # ------------------------------------------------------------------
    # Payload building (varies per provider)
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        *,
        provider_info: ProviderInfo,
        model_info: ModelInfo,
        prompt: str,
        system_prompt: Optional[str],
        images: Optional[List[str]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Build request payload specific to each provider."""

        provider = provider_info.provider_id
        model = model_info.model_id

        # OpenAI-compatible APIs (OpenAI, xAI, Mistral)
        if provider in {"openai", "xai", "mistral"}:
            payload = {
                "model": model,
                "temperature": temperature,
                "messages": self._build_openai_messages(prompt, system_prompt, images),
            }
            
            # Use max_completion_tokens for newer OpenAI models (GPT-4o, GPT-5.x)
            if provider == "openai" and any(x in model for x in ["gpt-4o", "gpt-5", "o1"]):
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens
                
            return payload

        # Anthropic Claude
        if provider == "anthropic":
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                payload["system"] = system_prompt
            return payload

        # Google Gemini
        if provider == "google":
            return {
                "model": model,
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": self._build_gemini_parts(prompt, images),
                    }
                ],
                "systemInstruction": (
                    {"parts": [{"text": system_prompt}]} if system_prompt else None
                ),
            }

        # Meta LLaMA (local or Ollama-style)
        if provider == "meta":
            return {
                "model": model,
                "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        # Cohere
        if provider == "cohere":
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            return {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

        raise ValueError(f"Unsupported provider '{provider}'")

    def _build_openai_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
        images: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Build OpenAI-format messages with optional system prompt and images."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            for img in images:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                    }
                )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        return messages

    def _build_gemini_parts(
        self, prompt: str, images: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Build Gemini-format parts with optional images."""

        parts: List[Dict[str, Any]] = [{"text": prompt}]
        if images:
            for img in images:
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": img}})
        return parts

    # ------------------------------------------------------------------
    # Execution with retry + exponential backoff
    # ------------------------------------------------------------------

    async def _execute_with_retry(
        self,
        *,
        provider_info: ProviderInfo,
        model_info: ModelInfo,
        payload: Dict[str, Any],
        api_key: Optional[str],
        org_id: Optional[str],
        user_id: Optional[str],
    ) -> tuple[Dict[str, Any], float]:
        """Execute the request with retries and measure latency."""

        url = self._get_api_url(provider_info, model_info)
        headers = self._build_headers(provider_info.provider_id, api_key, org_id)

        last_error: Exception = LLMRouterError("Unknown error occurred")
        for attempt in range(self.max_retries + 1):
            start_time = time.time()

            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    # Handle different error status codes
                    if response.status_code >= 400:
                        error_detail = self._extract_error_message(response)
                        raise ProviderError(
                            f"Provider API error: {error_detail}",
                            provider_info.provider_id,
                            response.status_code,
                        )

                latency_ms = (time.time() - start_time) * 1000
                return response.json(), latency_ms

            except httpx.TimeoutException as e:
                logger.error(f"[LLM] Timeout on attempt {attempt+1}: {e}")
                last_error = ProviderError("Request timeout", provider_info.provider_id)

            except httpx.RequestError as e:
                logger.error(f"[LLM] Request error on attempt {attempt+1}: {e}")
                last_error = ProviderError(
                    f"Network error: {e}", provider_info.provider_id
                )

            except ProviderError as e:
                logger.error(f"[LLM] Provider error on attempt {attempt+1}: {e}")
                last_error = e

            except Exception as e:
                logger.error(f"[LLM] Unexpected error on attempt {attempt+1}: {e}")
                last_error = LLMRouterError(f"Unexpected error: {e}")

            # Last retry → raise
            if attempt == self.max_retries:
                raise last_error

            # Exponential backoff with jitter
            sleep_time = self.base_retry_delay * (2**attempt) + random.uniform(0, 0.1)
            logger.info(f"[LLM] Retrying in {sleep_time:.1f}s...")
            await asyncio.sleep(sleep_time)

        raise last_error

    def _get_api_url(self, provider_info: ProviderInfo, model_info: ModelInfo) -> str:
        """Get the API URL for the provider."""

        # Use model-specific base_url if available, otherwise provider base_url
        base_url = model_info.base_url or provider_info.base_url

        if not base_url:
            raise ValueError(
                f"No base URL configured for provider {provider_info.provider_id}"
            )

        # Add provider-specific endpoints
        provider = provider_info.provider_id

        if provider == "openai":
            return f"{base_url.rstrip('/')}/chat/completions"
        elif provider == "anthropic":
            return f"{base_url.rstrip('/')}/messages"
        elif provider == "google":
            return f"{base_url.rstrip('/')}/generateContent"
        elif provider in {"xai", "mistral"}:
            return f"{base_url.rstrip('/')}/chat/completions"
        elif provider == "cohere":
            return f"{base_url.rstrip('/')}/chat"
        elif provider == "meta":
            return f"{base_url.rstrip('/')}/generate"  # Ollama-style
        else:
            # Default to chat/completions for unknown providers
            return f"{base_url.rstrip('/')}/chat/completions"

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract error message from provider response."""
        try:
            error_data = response.json()
            if "error" in error_data:
                if isinstance(error_data["error"], dict):
                    return error_data["error"].get("message", str(error_data["error"]))
                return str(error_data["error"])
            return f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception:
            return f"HTTP {response.status_code}: {response.text[:200]}"

    # ------------------------------------------------------------------
    # Headers for each provider
    # ------------------------------------------------------------------

    def _build_headers(
        self, provider: str, api_key: Optional[str], org_id: Optional[str]
    ) -> Dict[str, str]:
        """Build HTTP headers for each provider."""

        if not api_key:
            raise APIKeyMissingError(f"No API key provided for provider '{provider}'")

        base_headers = {"Content-Type": "application/json"}

        if provider == "openai":
            headers = {**base_headers, "Authorization": f"Bearer {api_key}"}
            if org_id:
                headers["OpenAI-Organization"] = org_id
            return headers

        elif provider == "anthropic":
            return {
                **base_headers,
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }

        elif provider == "google":
            return {
                **base_headers,
                "Authorization": f"Bearer {api_key}",
            }

        elif provider in {"xai", "mistral", "cohere", "meta"}:
            return {
                **base_headers,
                "Authorization": f"Bearer {api_key}",
            }

        else:
            # Default to Bearer token for unknown providers
            return {
                **base_headers,
                "Authorization": f"Bearer {api_key}",
            }

    # ------------------------------------------------------------------
    # Response normalization
    # ------------------------------------------------------------------

    def _extract_text(self, provider: str, data: Dict[str, Any]) -> str:
        """Extract text content from provider-specific response format."""

        try:
            if provider in {"openai", "xai", "mistral"}:
                return data["choices"][0]["message"]["content"]

            elif provider == "anthropic":
                content = data.get("content", [])
                if content and isinstance(content, list):
                    return "".join(
                        block.get("text", "")
                        for block in content
                        if block.get("type") == "text"
                    )
                return str(content)

            elif provider == "google":
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""

            elif provider == "cohere":
                message = data.get("message", {})
                content = message.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
                return str(message)

            elif provider == "meta":
                return data.get("response", data.get("text", ""))

            else:
                # Fallback: look for common response fields
                for field in ["text", "content", "response", "message"]:
                    if field in data:
                        return str(data[field])
                return str(data)

        except Exception as e:
            logger.warning(
                f"[LLM] Failed to extract text from {provider} response: {e}"
            )
            return str(data)

    def _extract_token_count(
        self, provider: str, data: Dict[str, Any]
    ) -> Optional[int]:
        """Extract token usage from provider-specific response format."""

        try:
            if provider in {"openai", "xai", "mistral"}:
                usage = data.get("usage", {})
                return usage.get("total_tokens")

            elif provider == "anthropic":
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                return input_tokens + output_tokens

            elif provider == "google":
                usage = data.get("usageMetadata", {})
                return usage.get("totalTokenCount")

            elif provider == "cohere":
                usage = data.get("usage", {})
                return usage.get("total_tokens")

            # Meta/local models typically don't provide token counts
            return None

        except Exception:
            return None


# ======================================================================
# Convenience Functions
# ======================================================================

# Global router instance for convenience
_default_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    """Get the default LLM router instance."""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router


async def quick_chat(
    prompt: str,
    *,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    use_smart_auto: bool = True,
    **kwargs,
) -> str:
    """
    Quick chat function for simple text generation.

    Returns just the text content for convenience.
    """
    router = get_router()
    response = await router.run(
        prompt=prompt,
        model=model,
        provider=provider,
        api_key=api_key,
        use_smart_auto=use_smart_auto,
        **kwargs,
    )
    return response.text


async def smart_auto_chat(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    allowed_providers: Optional[List[str]] = None,
    **kwargs,
) -> LLMResponse:
    """
    Chat using SMART-AUTO model selection.

    This is what NAVI orchestrator will typically use.
    """
    router = get_router()
    return await router.run(
        prompt=prompt,
        api_key=api_key,
        use_smart_auto=True,
        allowed_providers=allowed_providers,
        **kwargs,
    )


async def complete_chat(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    timeout_sec: int = 60,
    task_type: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> str:
    """
    Complete chat function for backward compatibility.

    This matches the interface expected by codegen_service.py and other modules.

    Args:
        system: System prompt/instructions
        user: User prompt/message
        model: Model to use
        provider: Provider to use
        api_key: API key for BYOK
        temperature: Temperature for generation
        max_tokens: Maximum tokens to generate
        timeout_sec: Request timeout (not currently used)
        task_type: Task type for logging/metrics (not currently used)
        tags: Additional tags for logging/metrics (not currently used)
        **kwargs: Additional arguments passed to the router

    Returns:
        Generated text response
    """
    router = get_router()
    response = await router.run(
        prompt=user,
        system_prompt=system,
        model=model,
        provider=provider,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.text
