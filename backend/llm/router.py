import yaml
import time
import os
import logging
from dataclasses import dataclass, replace
from typing import Dict, List, Any, Tuple, Optional
from sqlalchemy.orm import Session
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .audit import get_audit_service, AuditLogEntry
from ..core.utils import generate_prompt_hash
from ..telemetry.metrics import LLM_CALLS, LLM_TOKENS, LLM_COST, LLM_LATENCY

logger = logging.getLogger(__name__)

# Formatting constants
COST_DECIMAL_PLACES = 6  # Number of decimal places for cost formatting


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
                import unicodedata
                import re

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

                return (
                    sanitized_str[:max_len]
                    if len(sanitized_str) > max_len
                    else sanitized_str
                )
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
            "review": "gpt-4o-mini",
        }
        self.budgets = {
            "plan": {"tokens": 40000, "seconds": 60},
            "code": {"tokens": 40000, "seconds": 60},
            "review": {"tokens": 40000, "seconds": 60},
        }
        self.fallbacks = {
            "plan": ["gpt-4o", "claude-3-haiku"],
            "code": ["gpt-4o", "claude-3-5"],
            "review": ["gpt-4-1106-preview", "claude-3-haiku"],
        }

    def call(
        self,
        phase: str,
        prompt: str,
        context: Dict[str, Any],
        audit_context: Optional[AuditContext] = None,
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

        # Generate prompt hash if not provided (use replace() to maintain immutability)
        if audit_context.prompt_hash is None:
            audit_context = replace(
                audit_context, 
                prompt_hash=generate_prompt_hash(prompt, context)
            )

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
                result = provider.complete(prompt, sanitized_context)

                # Safely convert telemetry values with validation
                tokens_raw = result.get("tokens", 0)
                cost_raw = result.get("cost_usd", 0.0)

                # Validate and convert tokens (should be integers)
                try:
                    tokens = int(tokens_raw)
                except (ValueError, TypeError):
                    tokens = 0

                # Validate and convert cost (handles all numeric formats)
                try:
                    cost = float(cost_raw)
                except (ValueError, TypeError):
                    cost = 0.0

                # Calculate latency for successful call
                latency_ms = (time.time() - start_time) * 1000

                # Record Prometheus metrics
                LLM_CALLS.labels(phase=phase, model=candidate, status=status).inc()
                LLM_TOKENS.labels(phase=phase, model=candidate).inc(tokens)
                LLM_COST.labels(phase=phase, model=candidate).inc(cost)
                LLM_LATENCY.labels(phase=phase, model=candidate).observe(latency_ms)

                # Record audit log (transaction managed by caller)
                if audit_context.db is not None:
                    audit_entry = AuditLogEntry(
                        phase=phase,
                        model=candidate,
                        status=status,
                        prompt_hash=audit_context.prompt_hash,
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
                formatted_cost = f"${telemetry['cost_usd']:.{COST_DECIMAL_PLACES}f}"
                logger.info(
                    f"Successfully completed {phase} with {candidate}: "
                    f"{telemetry['tokens']} tokens, {formatted_cost}, {int(telemetry['latency_ms'])}ms"
                )

                return result["text"], telemetry

            except Exception as e:
                status = "error"
                error_message = str(e)
                last_error = e

                # Calculate latency for failed call
                latency_ms = (time.time() - start_time) * 1000

                # Record error metrics
                LLM_CALLS.labels(phase=phase, model=candidate, status=status).inc()
                LLM_LATENCY.labels(phase=phase, model=candidate).observe(latency_ms)

                # Record error audit log
                if audit_context.db is not None:
                    audit_entry = AuditLogEntry(
                        phase=phase,
                        model=candidate,
                        status=status,
                        prompt_hash=audit_context.prompt_hash,
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

    def check_budget(self, phase: str) -> Dict[str, bool]:
        """Check if current usage is within budget limits for the specified phase."""
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
