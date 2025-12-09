import yaml
import time
import os
import logging
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Dict, List, Any, Tuple, Optional, Union
from sqlalchemy.orm import Session
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .audit import get_audit_service, AuditLogEntry
from ..core.utils import generate_prompt_hash, format_cost_usd
from ..core.validation_helpers import validate_telemetry_value
from ..telemetry.metrics import LLM_CALLS, LLM_TOKENS, LLM_COST, LLM_LATENCY

logger = logging.getLogger(__name__)


@dataclass
class AuditContext:
    """Encapsulates audit logging parameters for LLM calls."""

    db: Optional[Session] = None
    prompt_hash: Optional[str] = None
    org_id: Optional[str] = None
    user_id: Optional[str] = None


class ModelRouter:
    """Routes LLM requests to appropriate providers with fallback support."""

    # Security and validation constants
    MAX_STRING_LENGTH = 10000  # Limit individual string values
    MAX_CONTEXT_SIZE = 50000  # Limit total context size
    MAX_LIST_SIZE = 100  # Limit list size in sanitization

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize context data to prevent injection attacks and limit size."""
        sanitized = {}

        def sanitize_value(value, max_len=self.MAX_STRING_LENGTH):
            if isinstance(value, str):
                # Remove potentially dangerous characters and normalize Unicode

                # Normalize Unicode to prevent normalization attacks
                sanitized_str = unicodedata.normalize("NFKC", value)

                # Remove control characters (except whitespace: \t, \n, \r)
                sanitized_str = re.sub(
                    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", sanitized_str
                )

                # Remove potentially dangerous Unicode categories
                sanitized_str = "".join(
                    char
                    for char in sanitized_str
                    if unicodedata.category(char) not in ["Cc", "Cf", "Co", "Cs"]
                )

                # Truncate to max_len to prevent excessively long strings (security limit)
                return sanitized_str[:max_len]
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [
                    sanitize_value(item) for item in value[: self.MAX_LIST_SIZE]
                ]  # Limit list size
            else:
                return value

        for key, value in context.items():
            if len(str(sanitized)) > self.MAX_CONTEXT_SIZE:
                break
            sanitized[key] = sanitize_value(value)

        return sanitized

    def __init__(self, config_path: str = "config/model-router.yaml"):
        self.providers = {
            "gpt-4-1106-preview": OpenAIProvider("gpt-4-1106-preview"),
            "gpt-4o": OpenAIProvider("gpt-4o"),
            "gpt-4o-mini": OpenAIProvider("gpt-4o-mini"),
            "claude-3-5": AnthropicProvider("claude-3-5-sonnet-20241022"),
            "claude-3-haiku": AnthropicProvider("claude-3-haiku-20240307"),
            "claude-3-sonnet": AnthropicProvider("claude-3-sonnet-20240229"),
        }

        self.routes: Dict[str, str] = {}
        self.budgets: Dict[str, Any] = {}
        self.fallbacks: Dict[str, List[str]] = {}
        self.usage_stats: Dict[str, Dict[str, Any]] = {}

        self._load_config(config_path)

    def _load_config(self, path: str) -> None:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(path):
                logger.warning(f"Config file {path} not found, using defaults")
                self._use_defaults()
                return

            with open(path, "r") as f:
                config = yaml.safe_load(f)

            self.routes = config.get("routes", {})
            self.budgets = config.get("budgets", {})
            self.fallbacks = config.get("fallbacks", {})

            logger.info(f"Loaded model router config from {path}")

        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            self._use_defaults()

    def _use_defaults(self) -> None:
        """Use default configuration."""
        self.routes = {
            "plan": "claude-3-5",
            "code": "gpt-4-1106-preview",
            "codegen": "gpt-4-1106-preview",  # Add codegen routing
            "review": "gpt-4o-mini",
        }
        self.budgets = {
            "plan": {"tokens": 40000, "seconds": 60},
            "code": {"tokens": 40000, "seconds": 60},
            "codegen": {"tokens": 40000, "seconds": 60},  # Add codegen budget
            "review": {"tokens": 40000, "seconds": 60},
        }
        self.fallbacks = {
            "plan": ["gpt-4o", "claude-3-haiku"],
            "code": ["gpt-4o", "claude-3-5"],
            "codegen": ["gpt-4o", "claude-3-5"],  # Add codegen fallbacks
            "review": ["gpt-4-1106-preview", "claude-3-haiku"],
        }

    def call(
        self,
        phase: str,
        prompt: str,
        context: Dict[str, Any],
        audit_context: Optional[AuditContext] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Route LLM call to appropriate provider with fallback support.
        Records telemetry metrics and audit logs for each attempt.

        Args:
            phase: The phase/task type (plan, code, review, etc.)
            prompt: The system prompt
            context: Context data to send to the model
            audit_context: Optional AuditContext object containing audit information such as
                - db: Database session for audit logging
                - prompt_hash: SHA256 hash of prompt+context for audit
                - org_id: Organization ID for multi-tenant support
                - user_id: User ID for audit tracking
            temperature: Optional temperature override for the model
            max_tokens: Optional max_tokens override for the model

        Returns:
            Tuple of (response_text, telemetry_data)
        """
        model_name = self.routes.get(phase)
        if not model_name:
            raise ValueError(f"No model configured for phase: {phase}")

        fallback_models = self.fallbacks.get(phase, [])
        candidates = [model_name] + fallback_models

        # Initialize audit context if not provided
        if audit_context is None:
            audit_context = AuditContext()

        # Ensure prompt hash is generated
        if audit_context.prompt_hash is None:
            generated_hash = generate_prompt_hash(prompt, context)
            audit_context = replace(audit_context, prompt_hash=generated_hash)

        last_error = None

        for candidate in candidates:
            provider = self.providers.get(candidate)
            if not provider:
                logger.warning(f"Provider not found for model: {candidate}")
                continue

            start_time = time.time()
            status = "ok"
            tokens = 0
            cost = 0.0
            error_message = None

            try:
                logger.info(f"Calling model {candidate} for phase {phase}")
                sanitized_context = self._sanitize_context(context)

                # Prepare parameters for provider.complete call
                complete_kwargs = {}
                if temperature is not None:
                    complete_kwargs["temperature"] = temperature
                if max_tokens is not None:
                    complete_kwargs["max_tokens"] = max_tokens

                result = provider.complete(prompt, sanitized_context, **complete_kwargs)

                # Safely convert telemetry values with validation using centralized helpers
                tokens_raw = result.get("tokens", 0)
                cost_raw = result.get("cost_usd", 0.0)

                # Use centralized validation for consistent error handling
                tokens = validate_telemetry_value(tokens_raw, int)
                cost = validate_telemetry_value(cost_raw, float)

                # Calculate latency for successful call
                latency_ms = (time.time() - start_time) * 1000

                # Record Prometheus metrics
                self._record_metrics(phase, candidate, status, latency_ms, tokens, cost)

                # Record audit log (transaction managed by caller)
                if audit_context.db is not None:
                    # Log warning if prompt_hash is missing for debugging
                    if audit_context.prompt_hash is None:
                        logger.warning(
                            f"Missing prompt_hash in audit context for phase {phase}, model {candidate}"
                        )

                    audit_entry = AuditLogEntry(
                        phase=phase,
                        model=candidate,
                        status=status,
                        prompt_hash=audit_context.prompt_hash or "<missing>",
                        tokens=tokens,
                        cost_usd=cost,
                        latency_ms=int(latency_ms),
                        org_id=audit_context.org_id,
                        user_id=audit_context.user_id,
                    )
                    get_audit_service().log_success(audit_context.db, audit_entry)

                # Build telemetry data
                telemetry = {
                    "phase": phase,
                    "model": candidate,
                    "tokens": tokens,
                    "input_tokens": result.get("input_tokens", 0),
                    "output_tokens": result.get("output_tokens", 0),
                    "cost_usd": cost,
                    "latency_ms": int(latency_ms),
                    "timestamp": time.time(),
                }

                # Track usage statistics
                self._update_usage_stats(candidate, telemetry)

                # Format log message using telemetry values for consistency
                formatted_cost = format_cost_usd(telemetry["cost_usd"])
                logger.info(
                    f"Successfully completed {phase} with {candidate}: "
                    f"{telemetry['tokens']} tokens, {formatted_cost}, {telemetry['latency_ms']}ms"
                )

                return result["text"], telemetry

            except Exception as e:
                status = "error"
                error_message = str(e)
                last_error = e

                # Calculate latency for failed call
                latency_ms = (time.time() - start_time) * 1000

                # Record error metrics
                self._record_metrics(phase, candidate, status, latency_ms)

                # Record error audit log
                if audit_context.db is not None:
                    # Log warning if prompt_hash is missing for debugging
                    if audit_context.prompt_hash is None:
                        logger.warning(
                            f"Missing prompt_hash in audit context for error in phase {phase}, model {candidate}"
                        )

                    audit_entry = AuditLogEntry(
                        phase=phase,
                        model=candidate,
                        status=status,
                        prompt_hash=audit_context.prompt_hash or "<missing>",
                        tokens=0,
                        cost_usd=0.0,
                        latency_ms=int(latency_ms),
                        org_id=audit_context.org_id,
                        user_id=audit_context.user_id,
                        error_message=error_message,
                    )
                    get_audit_service().log_error(audit_context.db, audit_entry)

                logger.warning(f"Model {candidate} failed for phase {phase}: {e}")
                continue

        # All models failed
        raise RuntimeError(
            f"All models failed for phase {phase}. Last error: {last_error}"
        )

    def _validate_metrics_params(
        self,
        phase: str,
        candidate: str,
        status: str,
        latency_ms: float,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> Tuple[str, str, str, float, int, float]:
        """Validate and sanitize metrics parameters once for efficiency."""
        # Use centralized validation helpers
        validated_phase = validate_telemetry_value(phase, str, "unknown")
        validated_candidate = validate_telemetry_value(candidate, str, "unknown")
        validated_status = validate_telemetry_value(status, str, "unknown")
        validated_latency = validate_telemetry_value(latency_ms, float)
        validated_tokens = validate_telemetry_value(tokens, int)
        validated_cost = validate_telemetry_value(cost, float)

        # Additional string validation
        if not validated_phase.strip():
            validated_phase = "unknown"
        if not validated_candidate.strip():
            validated_candidate = "unknown"
        if not validated_status.strip():
            validated_status = "unknown"

        return (
            validated_phase,
            validated_candidate,
            validated_status,
            validated_latency,
            validated_tokens,
            validated_cost,
        )

    def _record_metrics(
        self,
        phase: str,
        candidate: str,
        status: str,
        latency_ms: float,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """
        Record Prometheus metrics for LLM calls.
        Parameters are validated for safety before recording.
        """
        try:
            # Validate parameters once for efficiency
            phase, candidate, status, latency_ms, tokens, cost = (
                self._validate_metrics_params(
                    phase, candidate, status, latency_ms, tokens, cost
                )
            )

            LLM_CALLS.labels(phase=phase, model=candidate, status=status).inc()
            LLM_LATENCY.labels(phase=phase, model=candidate).observe(latency_ms)
            if status == "ok":
                LLM_TOKENS.labels(phase=phase, model=candidate).inc(tokens)
                LLM_COST.labels(phase=phase, model=candidate).inc(cost)
        except Exception as metrics_exc:
            logger.warning(f"Failed to record LLM metrics: {metrics_exc}")

    def _update_usage_stats(self, model: str, telemetry: Dict[str, Any]) -> None:
        """Update usage statistics for the model."""
        if model not in self.usage_stats:
            self.usage_stats[model] = {
                "calls": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_latency": 0.0,
                "last_used": None,
            }

        stats = self.usage_stats[model]
        stats["calls"] += 1
        stats["total_tokens"] += telemetry.get("tokens", 0)
        stats["total_cost"] += telemetry.get("cost_usd", 0)
        stats["total_latency"] += telemetry.get("latency_ms", 0)
        stats["last_used"] = telemetry.get("timestamp")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all models."""
        return {
            "models": self.usage_stats,
            "total_calls": sum(stats["calls"] for stats in self.usage_stats.values()),
            "total_tokens": sum(
                stats["total_tokens"] for stats in self.usage_stats.values()
            ),
            "total_cost": sum(
                stats["total_cost"] for stats in self.usage_stats.values()
            ),
        }

    def check_budget(self, phase: str) -> Dict[str, Union[bool, int, float]]:
        """Check if current usage is within budget limits for the specified phase.

        Returns:
            Dictionary containing:
            - within_token_budget (bool): Whether token usage is within budget
            - tokens_used (int): Current token usage for the phase
            - token_budget (int|float): Token budget limit (may be inf)
            - token_usage_percent (float): Percentage of budget used
        """
        phase_stats = self.usage_stats.get(phase, {})
        phase_budget = self.budgets.get(
            phase, {"tokens": float("inf"), "seconds": float("inf")}
        )

        phase_tokens = phase_stats.get("total_tokens", 0)
        token_budget = phase_budget.get("tokens", float("inf"))

        return {
            "within_token_budget": phase_tokens <= token_budget,
            "tokens_used": phase_tokens,
            "token_budget": token_budget,
            "token_usage_percent": (
                (phase_tokens / token_budget * 100) if token_budget > 0 else 0
            ),
        }


# Global instance for convenience
_router_instance = None


def get_model_router() -> ModelRouter:
    """Get the singleton model router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance


def complete_chat(
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout_sec: Optional[int] = None,
    task_type: str = "code",
    tags: Optional[Dict[str, str]] = None,
    audit_context: Optional[AuditContext] = None,
) -> str:
    """
    Convenience wrapper for model router that provides a chat-completion interface.

    Args:
        system: System prompt content
        user: User prompt content
        model: Optional model override (otherwise uses task_type routing)
        temperature: Optional temperature override
        max_tokens: Optional max tokens override
        timeout_sec: Optional timeout override (currently unused)
        task_type: Task type for routing (codegen, plan, review, etc.)
        tags: Optional metadata tags for telemetry
        audit_context: Optional audit context for logging

    Returns:
        Generated text response
    """
    router = get_model_router()

    # Build context from parameters for the provider
    context = {"user_prompt": user}
    if tags:
        context.update(tags)

    # Use the model router's call method with task_type as phase
    # Pass through temperature and max_tokens parameters to enable bandit learning
    response_text, telemetry = router.call(
        phase=task_type,
        prompt=system,
        context=context,
        audit_context=audit_context,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response_text

    async def chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000):
        """Simple chat method for compatibility"""
        # Convert messages to prompt
        prompt_parts = []
        for msg in messages:
            role = getattr(msg, 'role', 'user')
            content = getattr(msg, 'content', str(msg))
            prompt_parts.append(f"{role}: {content}")
        
        prompt = "\n".join(prompt_parts)
        
        # Use the call method with general phase
        result_text, telemetry = self.call(
            phase="general",
            prompt=prompt,
            context={},
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Return a simple result object
        class ChatResult:
            def __init__(self, content):
                self.content = content
        
        return ChatResult(result_text)
