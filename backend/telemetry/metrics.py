from prometheus_client import Counter, Histogram

# Total number of LLM calls by phase, model, and status
LLM_CALLS = Counter(
    "aep_llm_calls_total",
    "Total LLM calls",
    ["phase", "model", "status"],
)

# Total tokens used by LLM calls
LLM_TOKENS = Counter(
    "aep_llm_tokens_total",
    "Total tokens used by LLM calls",
    ["phase", "model"],
)

# Total USD cost of LLM calls
LLM_COST = Counter(
    "aep_llm_cost_usd_total",
    "Total USD cost of LLM calls",
    ["phase", "model"],
)

# LLM call latency histogram with buckets optimized for LLM response times
LLM_LATENCY = Histogram(
    "aep_llm_latency_ms",
    "LLM call latency in milliseconds",
    ["phase", "model"],
    buckets=(10, 25, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800),
)

# Plan Mode metrics
plan_events_total = Counter(
    "aep_plan_events_total",
    "Total plan events",
    ["event", "org_id"],
)

plan_step_latency = Histogram(
    "aep_plan_step_latency_ms",
    "Plan step latency in milliseconds",
    ["org_id"],
    buckets=(10, 25, 50, 100, 200, 400, 800),
)

plan_active_total = Counter(
    "aep_plan_active_total",
    "Total active plan sessions",
    ["org_id"],
)
