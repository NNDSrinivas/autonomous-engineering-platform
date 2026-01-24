"""
Token Usage and Cost Tracking for NAVI SaaS

Tracks:
1. Token usage per request (input/output tokens)
2. Cost calculation based on model pricing
3. Usage aggregation by org/team/user
4. Rate limiting and quota management
5. Billing reports and analytics

This enables transparent pricing for SaaS customers.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


# ============================================================
# MODEL PRICING (per 1M tokens, in USD)
# ============================================================

MODEL_PRICING = {
    # Anthropic Claude models
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-haiku-20241022": {"input": 1.00, "output": 5.00},
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Google models
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Groq models (very cheap)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    # Mistral models
    "mistral-large-latest": {"input": 2.00, "output": 6.00},
    "mistral-medium": {"input": 2.70, "output": 8.10},
    "mistral-small": {"input": 0.20, "output": 0.60},
    # OpenRouter (varies by model)
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    # Ollama (local, free)
    "llama3": {"input": 0.00, "output": 0.00},
    "codellama": {"input": 0.00, "output": 0.00},
    "mistral": {"input": 0.00, "output": 0.00},
    # Default fallback
    "default": {"input": 3.00, "output": 15.00},
}


@dataclass
class TokenUsage:
    """Token usage for a single request."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Cache tokens (if applicable)
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class UsageRecord:
    """A single usage record for tracking and billing."""

    id: str
    timestamp: datetime
    model: str
    provider: str

    # Token counts
    usage: TokenUsage

    # Cost calculation
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0

    # Context
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_id: Optional[str] = None

    # Request metadata
    request_type: str = "chat"  # chat, completion, embedding
    endpoint: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "total_tokens": self.usage.total_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "org_id": self.org_id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "request_type": self.request_type,
            "latency_ms": self.latency_ms,
        }


@dataclass
class UsageSummary:
    """Aggregated usage summary for a time period."""

    period_start: datetime
    period_end: datetime

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    # Breakdown by model
    by_model: Dict[str, Dict] = field(default_factory=dict)

    # Breakdown by user (if applicable)
    by_user: Dict[str, Dict] = field(default_factory=dict)

    # Average metrics
    avg_tokens_per_request: float = 0.0
    avg_cost_per_request: float = 0.0
    avg_latency_ms: float = 0.0


class CostCalculator:
    """Calculates cost based on model and token usage."""

    @staticmethod
    def calculate(model: str, usage: TokenUsage) -> Dict[str, float]:
        """Calculate cost for a request."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])

        # Cost per million tokens
        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]

        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(input_cost + output_cost, 6),
        }

    @staticmethod
    def estimate_cost(
        model: str, input_tokens: int, estimated_output: int = 1000
    ) -> float:
        """Estimate cost before making a request."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    @staticmethod
    def get_model_pricing(model: str) -> Dict[str, float]:
        """Get pricing for a model."""
        return MODEL_PRICING.get(model, MODEL_PRICING["default"])


class TokenTracker:
    """
    Tracks token usage and costs for billing and analytics.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(
            storage_path
            or os.getenv("NAVI_USAGE_PATH", os.path.expanduser("~/.navi/usage"))
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory records (recent)
        self.records: List[UsageRecord] = []
        self.max_memory_records = 10000

        # Load recent records
        self._load_recent()

    def _load_recent(self):
        """Load recent usage records."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.storage_path / f"usage_{today}.json"

        if today_file.exists():
            try:
                data = json.loads(today_file.read_text())
                for r in data.get("records", []):
                    record = UsageRecord(
                        id=r["id"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                        model=r["model"],
                        provider=r["provider"],
                        usage=TokenUsage(
                            input_tokens=r["input_tokens"],
                            output_tokens=r["output_tokens"],
                            total_tokens=r["total_tokens"],
                        ),
                        input_cost=r["input_cost"],
                        output_cost=r["output_cost"],
                        total_cost=r["total_cost"],
                        org_id=r.get("org_id"),
                        team_id=r.get("team_id"),
                        user_id=r.get("user_id"),
                        request_type=r.get("request_type", "chat"),
                        latency_ms=r.get("latency_ms", 0),
                    )
                    self.records.append(record)
                logger.info(f"Loaded {len(self.records)} usage records for today")
            except Exception as e:
                logger.error(f"Error loading usage records: {e}")

    def _save_records(self):
        """Save records to disk."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = self.storage_path / f"usage_{today}.json"

        # Filter to today's records only
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_records = [r for r in self.records if r.timestamp >= today_start]

        data = {
            "date": today,
            "records": [r.to_dict() for r in today_records],
        }
        today_file.write_text(json.dumps(data, indent=2))

    def track(
        self,
        model: str,
        provider: str,
        usage: TokenUsage,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_type: str = "chat",
        latency_ms: float = 0.0,
    ) -> UsageRecord:
        """Track a new usage record."""
        # Calculate cost
        costs = CostCalculator.calculate(model, usage)

        # Generate ID
        record_id = hashlib.sha256(
            f"{datetime.now().isoformat()}:{model}:{usage.total_tokens}".encode()
        ).hexdigest()[:16]

        record = UsageRecord(
            id=record_id,
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            usage=usage,
            input_cost=costs["input_cost"],
            output_cost=costs["output_cost"],
            total_cost=costs["total_cost"],
            org_id=org_id,
            team_id=team_id,
            user_id=user_id,
            request_type=request_type,
            latency_ms=latency_ms,
        )

        self.records.append(record)

        # Trim old records from memory
        if len(self.records) > self.max_memory_records:
            self.records = self.records[-self.max_memory_records :]

        # Save to disk
        self._save_records()

        logger.info(
            f"Tracked usage: {model} | {usage.total_tokens} tokens | ${costs['total_cost']:.6f}"
        )

        return record

    def get_usage_summary(
        self,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        days: int = 30,
    ) -> UsageSummary:
        """Get usage summary for a time period."""
        cutoff = datetime.now() - timedelta(days=days)
        period_start = cutoff
        period_end = datetime.now()

        # Load records from files if needed
        all_records = self._load_records_for_period(cutoff, datetime.now())

        # Filter by scope
        filtered = []
        for record in all_records:
            if org_id and record.org_id != org_id:
                continue
            if team_id and record.team_id != team_id:
                continue
            if user_id and record.user_id != user_id:
                continue
            filtered.append(record)

        # Aggregate
        summary = UsageSummary(
            period_start=period_start,
            period_end=period_end,
            total_requests=len(filtered),
        )

        total_latency = 0.0
        by_model = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})
        by_user = defaultdict(lambda: {"requests": 0, "tokens": 0, "cost": 0.0})

        for record in filtered:
            summary.total_input_tokens += record.usage.input_tokens
            summary.total_output_tokens += record.usage.output_tokens
            summary.total_tokens += record.usage.total_tokens
            summary.total_cost += record.total_cost
            total_latency += record.latency_ms

            # By model
            by_model[record.model]["requests"] += 1
            by_model[record.model]["tokens"] += record.usage.total_tokens
            by_model[record.model]["cost"] += record.total_cost

            # By user
            if record.user_id:
                by_user[record.user_id]["requests"] += 1
                by_user[record.user_id]["tokens"] += record.usage.total_tokens
                by_user[record.user_id]["cost"] += record.total_cost

        summary.by_model = dict(by_model)
        summary.by_user = dict(by_user)

        if summary.total_requests > 0:
            summary.avg_tokens_per_request = (
                summary.total_tokens / summary.total_requests
            )
            summary.avg_cost_per_request = summary.total_cost / summary.total_requests
            summary.avg_latency_ms = total_latency / summary.total_requests

        return summary

    def _load_records_for_period(
        self, start: datetime, end: datetime
    ) -> List[UsageRecord]:
        """Load all records for a time period from disk."""
        records = []

        # Get all days in range
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            file_path = self.storage_path / f"usage_{date_str}.json"

            if file_path.exists():
                try:
                    data = json.loads(file_path.read_text())
                    for r in data.get("records", []):
                        record = UsageRecord(
                            id=r["id"],
                            timestamp=datetime.fromisoformat(r["timestamp"]),
                            model=r["model"],
                            provider=r["provider"],
                            usage=TokenUsage(
                                input_tokens=r["input_tokens"],
                                output_tokens=r["output_tokens"],
                                total_tokens=r["total_tokens"],
                            ),
                            input_cost=r["input_cost"],
                            output_cost=r["output_cost"],
                            total_cost=r["total_cost"],
                            org_id=r.get("org_id"),
                            team_id=r.get("team_id"),
                            user_id=r.get("user_id"),
                            request_type=r.get("request_type", "chat"),
                            latency_ms=r.get("latency_ms", 0),
                        )
                        if start <= record.timestamp <= end:
                            records.append(record)
                except Exception as e:
                    logger.warning(f"Error loading usage file {file_path}: {e}")

            current += timedelta(days=1)

        # Add in-memory records
        for record in self.records:
            if start <= record.timestamp <= end:
                if record.id not in [r.id for r in records]:
                    records.append(record)

        return records

    def get_recent_usage(
        self,
        limit: int = 10,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[UsageRecord]:
        """Get recent usage records."""
        filtered = []
        for record in reversed(self.records):
            if org_id and record.org_id != org_id:
                continue
            if team_id and record.team_id != team_id:
                continue
            if user_id and record.user_id != user_id:
                continue
            filtered.append(record)
            if len(filtered) >= limit:
                break
        return filtered


# ============================================================
# RESPONSE WRAPPER WITH USAGE
# ============================================================


@dataclass
class NaviResponseWithUsage:
    """
    Wraps a NAVI response with token usage and cost information.
    This is what gets sent back to the client for SaaS billing visibility.
    """

    # The actual response content
    response: Any

    # Usage metrics
    usage: TokenUsage

    # Cost breakdown
    input_cost: float
    output_cost: float
    total_cost: float

    # Model info
    model: str
    provider: str

    # Performance
    latency_ms: float

    def to_dict(self) -> Dict:
        return {
            "response": (
                self.response if isinstance(self.response, dict) else str(self.response)
            ),
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "cost": {
                "input": f"${self.input_cost:.6f}",
                "output": f"${self.output_cost:.6f}",
                "total": f"${self.total_cost:.6f}",
            },
            "model": self.model,
            "provider": self.provider,
            "latency_ms": round(self.latency_ms, 2),
        }


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """Get the global token tracker instance."""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker


def track_usage(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    latency_ms: float = 0.0,
) -> UsageRecord:
    """Convenience function to track usage."""
    tracker = get_token_tracker()
    usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    return tracker.track(
        model=model,
        provider=provider,
        usage=usage,
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        latency_ms=latency_ms,
    )


def get_usage_summary(
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    days: int = 30,
) -> UsageSummary:
    """Convenience function to get usage summary."""
    return get_token_tracker().get_usage_summary(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        days=days,
    )
