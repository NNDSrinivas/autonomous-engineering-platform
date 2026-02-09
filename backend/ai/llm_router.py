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
import json

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
from .llm_cache import get_cache

logger = logging.getLogger(__name__)

# ======================================================================
# Tool-Use Support
# ======================================================================


@dataclass
class ToolCall:
    """
    Represents a tool call from the LLM.

    This enables native tool-use support for agentic workflows,
    matching the patterns used by Claude Code, Cline, and Copilot.
    """

    id: str
    name: str
    arguments: Dict[str, Any]

    def __repr__(self):
        return f"<ToolCall {self.name}({', '.join(f'{k}={repr(v)[:20]}' for k, v in self.arguments.items())})>"


# ======================================================================
# Unified Response Object
# ======================================================================


@dataclass
class LLMResponse:
    """
    Normalized output structure for all model providers.

    Extended with tool_calls and stop_reason for agentic workflows.
    """

    text: str
    model: str
    provider: str
    raw: Dict[str, Any]
    latency_ms: float
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None  # For cache info, failover tracking, etc.
    usage: Optional[Dict[str, int]] = None  # For backward compatibility
    # NEW: Tool-use support for agentic workflows
    tool_calls: Optional[List[ToolCall]] = None
    stop_reason: Optional[str] = None  # "end_turn", "tool_use", "stop", "max_tokens"

    def __repr__(self):
        cached = " (cached)" if self.metadata and self.metadata.get("cached") else ""
        tools = f" tools={len(self.tool_calls)}" if self.tool_calls else ""
        return f"<LLMResponse model={self.model} provider={self.provider} latency={self.latency_ms:.0f}ms{cached}{tools}>"

    @property
    def has_tool_calls(self) -> bool:
        """Check if this response contains tool calls."""
        return bool(self.tool_calls)

    @property
    def wants_to_continue(self) -> bool:
        """Check if the LLM wants to continue (made tool calls and expects results)."""
        return self.stop_reason == "tool_use" or (
            self.has_tool_calls and self.stop_reason != "end_turn"
        )


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
# Model Alias Mapping (friendly names -> API model IDs)
# ======================================================================

MODEL_ALIASES = {
    # Anthropic aliases - map friendly names to actual API model IDs
    "claude-sonnet-4-20241022": "claude-3-5-sonnet-20241022",
    "claude-sonnet-4-20250514": "claude-3-5-sonnet-20241022",  # Map to current version
    "claude-sonnet-4": "claude-3-5-sonnet-20241022",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-haiku": "claude-3-haiku-20240307",
    "claude-3.5-haiku": "claude-3-5-haiku-20241022",
    # OpenAI aliases (for consistency)
    "gpt-4-turbo": "gpt-4-turbo-preview",
    "gpt-4": "gpt-4-0613",
}


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
        # NEW: Tool-use parameters for agentic workflows
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",  # "auto", "none", "required", or specific tool name
        messages: Optional[
            List[Dict[str, Any]]
        ] = None,  # For multi-turn with tool results
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
            tools: List of tool definitions (Anthropic format: name, description, input_schema)
            tool_choice: How to choose tools - "auto", "none", "required", or tool name
            messages: Full message history for multi-turn conversations (overrides prompt)

        Returns:
            LLMResponse with normalized output (includes tool_calls if LLM wants to use tools)

        Raises:
            ModelNotFoundError: If model/provider not found
            APIKeyMissingError: If required API key missing
            ProviderError: If provider API fails
        """

        # Select model automatically if needed
        provider_info, model_info = self._resolve_model(
            model, provider, use_smart_auto, allowed_providers
        )

        # Check cache first (skip for vision requests)
        cache_enabled = os.getenv("LLM_CACHE_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if cache_enabled and not images:
            cache = get_cache()
            cached_result = await cache.get(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model_info.model_id,
                temperature=temperature,
            )
            if cached_result:
                cached_text, cached_metadata = cached_result
                return LLMResponse(
                    text=cached_text,
                    model=model_info.model_id,
                    provider=provider_info.provider_id,
                    raw={"cached": True},
                    latency_ms=0.5,  # Near-instant
                    metadata=cached_metadata,
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

        allow_offline = offline_configured or (
            env in {"dev", "test", "local"} and not api_key
        )
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
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )

        # Execute with retry logic and provider failover
        try:
            response_json, latency_ms = await self._execute_with_retry(
                provider_info=provider_info,
                model_info=model_info,
                payload=request_payload,
                api_key=api_key,
                org_id=org_id,
                user_id=user_id,
            )
        except ProviderError as exc:
            # Check if rate limited (429) - try failover to another provider
            if exc.status_code == 429 or "rate limit" in str(exc).lower():
                logger.warning(
                    "[LLM] Rate limited on %s, attempting provider failover",
                    provider_info.provider_id,
                )
                fallback_result = await self._try_provider_failover(
                    original_provider=provider_info.provider_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    images=images,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    org_id=org_id,
                    user_id=user_id,
                )
                if fallback_result:
                    return fallback_result
                # If failover failed too, continue to offline fallback
                if allow_offline:
                    return self._offline_response(
                        prompt=prompt,
                        model=model_info.model_id,
                        provider=provider_info.provider_id,
                        reason=f"Rate limited and failover failed: {exc}",
                    )
                raise
            # Non-rate-limit error
            if allow_offline:
                offline_reason = offline_reason or f"LLM call failed: {exc}"
                logger.warning(
                    "[LLM] %s – returning deterministic offline response",
                    offline_reason,
                )
                return self._offline_response(
                    prompt=prompt,
                    model=model_info.model_id,
                    provider=provider_info.provider_id,
                    reason=offline_reason,
                )
            raise
        except Exception as exc:
            if allow_offline:
                offline_reason = offline_reason or f"LLM call failed: {exc}"
                logger.warning(
                    "[LLM] %s – returning deterministic offline response",
                    offline_reason,
                )
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

        # Extract tool calls if present (for agentic workflows)
        tool_calls = self._extract_tool_calls(provider_info.provider_id, response_json)
        stop_reason = self._extract_stop_reason(
            provider_info.provider_id, response_json
        )

        # Cache the response (skip for vision requests and tool responses)
        if cache_enabled and not images and not tools and text:
            cache = get_cache()
            await cache.set(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model_info.model_id,
                provider=provider_info.provider_id,
                response_text=text,
                tokens_used=tokens_used,
                temperature=temperature,
            )

        return LLMResponse(
            text=text,
            model=model_info.model_id,
            provider=provider_info.provider_id,
            raw=response_json,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
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

    async def _try_provider_failover(
        self,
        *,
        original_provider: str,
        prompt: str,
        system_prompt: Optional[str],
        images: Optional[List[str]],
        temperature: float,
        max_tokens: int,
        org_id: Optional[str],
        user_id: Optional[str],
    ) -> Optional[LLMResponse]:
        """
        Attempt to use a fallback provider when the primary is rate-limited.

        Failover priority:
        1. anthropic -> openai -> google
        2. openai -> anthropic -> google
        3. google -> anthropic -> openai

        Returns None if all fallbacks fail.
        """
        # Define fallback chains for each provider
        fallback_chains = {
            "anthropic": ["openai", "google"],
            "openai": ["anthropic", "google"],
            "google": ["anthropic", "openai"],
            "xai": ["openai", "anthropic"],
            "mistral": ["openai", "anthropic"],
        }

        # Default models for each provider (fast, cheap options for failover)
        fallback_models = {
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o-mini",
            "google": "gemini-1.5-flash",
        }

        # API key env vars
        api_key_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }

        fallbacks = fallback_chains.get(original_provider, ["openai", "anthropic"])

        for fallback_provider in fallbacks:
            # Check if we have API key for this provider
            api_key = os.getenv(api_key_env.get(fallback_provider, ""))
            if not api_key:
                logger.debug(
                    "[LLM] Skipping fallback to %s - no API key", fallback_provider
                )
                continue

            fallback_model = fallback_models.get(fallback_provider)
            if not fallback_model:
                continue

            logger.info(
                "[LLM] Attempting failover to %s:%s",
                fallback_provider,
                fallback_model,
            )

            try:
                # Resolve the fallback provider/model
                registry = get_registry()
                provider_info = registry.get_provider(fallback_provider)
                model_info = registry.get_model(fallback_model)

                if not provider_info or not model_info:
                    logger.warning(
                        "[LLM] Fallback provider %s not found in registry",
                        fallback_provider,
                    )
                    continue

                # Build payload for fallback
                request_payload = self._build_payload(
                    provider_info=provider_info,
                    model_info=model_info,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    images=images,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Execute request
                response_json, latency_ms = await self._execute_with_retry(
                    provider_info=provider_info,
                    model_info=model_info,
                    payload=request_payload,
                    api_key=api_key,
                    org_id=org_id,
                    user_id=user_id,
                )

                # Success! Return the response
                text = self._extract_text(fallback_provider, response_json)
                tokens_used = self._extract_token_count(
                    fallback_provider, response_json
                )

                logger.info(
                    "[LLM] Failover successful to %s:%s",
                    fallback_provider,
                    fallback_model,
                )

                return LLMResponse(
                    text=text,
                    model=fallback_model,
                    provider=fallback_provider,
                    raw=response_json,
                    latency_ms=latency_ms,
                    tokens_used=tokens_used,
                    metadata={"failover_from": original_provider},
                )

            except Exception as e:
                logger.warning("[LLM] Failover to %s failed: %s", fallback_provider, e)
                continue

        # All fallbacks failed
        logger.error("[LLM] All provider failovers failed")
        return None

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

        # Apply model alias mapping (friendly names -> API model IDs)
        if model and model in MODEL_ALIASES:
            resolved_model = MODEL_ALIASES[model]
            logger.info(f"[LLM] Model alias resolved: {model} -> {resolved_model}")
            model = resolved_model

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

        # Nothing provided → use DEFAULT_LLM_PROVIDER if set, else SMART AUTO
        default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "").lower()
        if default_provider:
            provider_info = registry.get_provider(default_provider)
            if provider_info:
                # Get default model for this provider
                default_model = self._get_default_model_for_provider(default_provider)
                model_info = ModelInfo(
                    provider_id=default_provider,
                    model_id=default_model,
                )
                logger.info(
                    f"[LLM] Using DEFAULT_LLM_PROVIDER: {default_provider}:{default_model}"
                )
                return provider_info, model_info

        # Fallback to SMART AUTO
        return self._resolve_model(None, None, True, allowed_providers)

    def _get_default_model_for_provider(self, provider: str) -> str:
        """
        Get the default model for a given provider.

        Uses environment-aware defaults to balance cost and quality:
        - dev/test: cheaper/faster models (e.g., gpt-4o-mini)
        - production: higher quality models (e.g., gpt-4o)
        """
        from backend.core.settings import settings

        # Environment-aware OpenAI default
        openai_default = "gpt-4o" if settings.is_production() else "gpt-4o-mini"

        defaults = {
            "anthropic": os.environ.get(
                "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"
            ),
            "openai": os.environ.get("OPENAI_MODEL", openai_default),
            "google": os.environ.get("GOOGLE_MODEL", "gemini-1.5-flash"),
        }
        return defaults.get(provider, openai_default)

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
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build request payload specific to each provider."""

        provider = provider_info.provider_id
        model = model_info.model_id

        # OpenAI-compatible APIs (OpenAI, xAI, Mistral, Groq)
        if provider in {"openai", "xai", "mistral", "groq"}:
            # Use provided messages or build from prompt
            if messages:
                msg_list = messages
            else:
                msg_list = self._build_openai_messages(prompt, system_prompt, images)

            payload = {
                "model": model,
                "temperature": temperature,
                "messages": msg_list,
            }

            # Use max_completion_tokens for newer OpenAI models (GPT-4o, GPT-5.x)
            if provider == "openai" and any(
                x in model
                for x in ["gpt-4o", "gpt-5", "gpt-4.2", "gpt-4.1", "o1", "o3", "o4"]
            ):
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens

            # Add tools if provided (convert from Anthropic format to OpenAI format)
            if tools:
                payload["tools"] = self._convert_tools_to_openai(tools)
                if tool_choice == "required":
                    payload["tool_choice"] = "required"
                elif tool_choice == "none":
                    payload["tool_choice"] = "none"
                elif tool_choice != "auto":
                    # Specific tool name
                    payload["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_choice},
                    }

            return payload

        # Anthropic Claude
        if provider == "anthropic":
            # Use provided messages or build from prompt
            if messages:
                msg_list = messages
            else:
                msg_list = [{"role": "user", "content": prompt}]

            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": msg_list,
            }
            if system_prompt:
                payload["system"] = system_prompt

            # Add tools if provided (Anthropic native format)
            if tools:
                payload["tools"] = tools
                if tool_choice == "required":
                    payload["tool_choice"] = {"type": "any"}
                elif tool_choice == "none":
                    payload["tool_choice"] = {"type": "none"}
                elif tool_choice != "auto":
                    # Specific tool name
                    payload["tool_choice"] = {"type": "tool", "name": tool_choice}

            return payload

        # Google Gemini
        if provider == "google":
            payload = {
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

            # Add tools if provided (convert to Gemini format)
            if tools:
                payload["tools"] = [
                    {"functionDeclarations": self._convert_tools_to_gemini(tools)}
                ]

            return payload

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
            msg_list = []
            if system_prompt:
                msg_list.append({"role": "system", "content": system_prompt})
            msg_list.append({"role": "user", "content": prompt})

            return {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": msg_list,
            }

        raise ValueError(f"Unsupported provider '{provider}'")

    def _convert_tools_to_openai(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert Anthropic-format tools to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "input_schema", {"type": "object", "properties": {}}
                        ),
                    },
                }
            )
        return openai_tools

    def _convert_tools_to_gemini(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert Anthropic-format tools to Gemini function declarations format."""
        gemini_tools = []
        for tool in tools:
            gemini_tools.append(
                {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "input_schema", {"type": "object", "properties": {}}
                    ),
                }
            )
        return gemini_tools

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
        """
        Extract text content from provider-specific response format.

        Uses safe nested access to prevent KeyError/IndexError crashes.
        """
        if data is None:
            return ""

        try:
            if provider in {"openai", "xai", "mistral", "groq", "openrouter"}:
                # Safe nested access: data["choices"][0]["message"]["content"]
                choices = data.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    if isinstance(first_choice, dict):
                        message = first_choice.get("message", {})
                        if isinstance(message, dict):
                            content = message.get("content")
                            if content is not None:
                                return str(content)
                        # Also check delta for streaming responses
                        delta = first_choice.get("delta", {})
                        if isinstance(delta, dict):
                            content = delta.get("content")
                            if content is not None:
                                return str(content)
                # Fallback for direct content field
                if "content" in data and isinstance(data["content"], str):
                    return data["content"]
                return ""

            elif provider == "anthropic":
                content = data.get("content", [])
                if isinstance(content, str):
                    return content
                if isinstance(content, (list, tuple)) and content:
                    texts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text = block.get("text")
                                if text:
                                    texts.append(str(text))
                        elif isinstance(block, str):
                            texts.append(block)
                    return "".join(texts)
                return ""

            elif provider == "google":
                candidates = data.get("candidates", [])
                if isinstance(candidates, (list, tuple)) and candidates:
                    first_candidate = candidates[0]
                    if isinstance(first_candidate, dict):
                        content = first_candidate.get("content", {})
                        if isinstance(content, dict):
                            parts = content.get("parts", [])
                            if isinstance(parts, (list, tuple)) and parts:
                                first_part = parts[0]
                                if isinstance(first_part, dict):
                                    text = first_part.get("text")
                                    if text is not None:
                                        return str(text)
                                elif isinstance(first_part, str):
                                    return first_part
                return ""

            elif provider == "cohere":
                message = data.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content", [])
                    if isinstance(content, (list, tuple)) and content:
                        first_content = content[0]
                        if isinstance(first_content, dict):
                            text = first_content.get("text")
                            if text is not None:
                                return str(text)
                        elif isinstance(first_content, str):
                            return first_content
                    elif isinstance(content, str):
                        return content
                elif isinstance(message, str):
                    return message
                return ""

            elif provider in {"meta", "ollama"}:
                # Check multiple possible fields
                for field in ["response", "text", "content"]:
                    value = data.get(field)
                    if value is not None:
                        return str(value)
                # Ollama format: {"message": {"content": "..."}}
                message = data.get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if content is not None:
                        return str(content)
                return ""

            else:
                # Generic fallback: look for common response fields
                for field in ["text", "content", "response", "message", "output"]:
                    value = data.get(field)
                    if value is not None:
                        if isinstance(value, str):
                            return value
                        if isinstance(value, dict):
                            # Try nested content
                            nested = value.get("content") or value.get("text")
                            if nested is not None:
                                return str(nested)
                return ""

        except Exception as e:
            logger.warning(
                f"[LLM] Failed to extract text from {provider} response: {e}"
            )
            return ""  # Return empty string, not stringified data

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

    def _extract_tool_calls(
        self, provider: str, data: Dict[str, Any]
    ) -> Optional[List[ToolCall]]:
        """
        Extract tool calls from provider-specific response format.

        This enables native tool-use support for agentic workflows.
        Returns None if no tool calls are present.
        """
        if data is None:
            return None

        try:
            if provider in {"openai", "xai", "mistral", "groq", "openrouter"}:
                # OpenAI format: choices[0].message.tool_calls
                choices = data.get("choices", [])
                if not choices:
                    return None

                message = choices[0].get("message", {})
                tool_calls_data = message.get("tool_calls", [])

                if not tool_calls_data:
                    return None

                tool_calls = []
                for tc in tool_calls_data:
                    func = tc.get("function", {})
                    args_str = func.get("arguments", "{}")
                    try:
                        args = (
                            json.loads(args_str)
                            if isinstance(args_str, str)
                            else args_str
                        )
                    except json.JSONDecodeError:
                        args = {"raw": args_str}

                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", f"call_{len(tool_calls)}"),
                            name=func.get("name", ""),
                            arguments=args,
                        )
                    )

                return tool_calls if tool_calls else None

            elif provider == "anthropic":
                # Anthropic format: content[] with type="tool_use"
                content = data.get("content", [])
                if not isinstance(content, list):
                    return None

                tool_calls = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block.get("id", f"toolu_{len(tool_calls)}"),
                                name=block.get("name", ""),
                                arguments=block.get("input", {}),
                            )
                        )

                return tool_calls if tool_calls else None

            elif provider == "google":
                # Gemini format: candidates[0].content.parts[] with functionCall
                candidates = data.get("candidates", [])
                if not candidates:
                    return None

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])

                tool_calls = []
                for i, part in enumerate(parts):
                    if isinstance(part, dict) and "functionCall" in part:
                        func_call = part["functionCall"]
                        tool_calls.append(
                            ToolCall(
                                id=f"gemini_call_{i}",
                                name=func_call.get("name", ""),
                                arguments=func_call.get("args", {}),
                            )
                        )

                return tool_calls if tool_calls else None

            # Other providers don't support tool calls yet
            return None

        except Exception as e:
            logger.warning(
                f"[LLM] Failed to extract tool calls from {provider} response: {e}"
            )
            return None

    def _extract_stop_reason(
        self, provider: str, data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extract stop reason from provider-specific response format.

        Returns normalized stop reason:
        - "end_turn": LLM finished naturally
        - "tool_use": LLM wants to use tools (expects results)
        - "max_tokens": Hit token limit
        - "stop": Hit stop sequence
        """
        if data is None:
            return None

        try:
            if provider in {"openai", "xai", "mistral", "groq", "openrouter"}:
                # OpenAI format: choices[0].finish_reason
                choices = data.get("choices", [])
                if not choices:
                    return None

                finish_reason = choices[0].get("finish_reason")

                # Normalize OpenAI finish reasons
                if finish_reason == "tool_calls":
                    return "tool_use"
                elif finish_reason == "stop":
                    return "end_turn"
                elif finish_reason == "length":
                    return "max_tokens"
                return finish_reason

            elif provider == "anthropic":
                # Anthropic format: stop_reason
                stop_reason = data.get("stop_reason")
                return stop_reason  # Already normalized

            elif provider == "google":
                # Gemini format: candidates[0].finishReason
                candidates = data.get("candidates", [])
                if not candidates:
                    return None

                finish_reason = candidates[0].get("finishReason")

                # Normalize Gemini finish reasons
                if finish_reason == "STOP":
                    return "end_turn"
                elif finish_reason == "MAX_TOKENS":
                    return "max_tokens"
                elif finish_reason == "SAFETY":
                    return "safety"
                return finish_reason

            return None

        except Exception as e:
            logger.warning(
                f"[LLM] Failed to extract stop reason from {provider} response: {e}"
            )
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
