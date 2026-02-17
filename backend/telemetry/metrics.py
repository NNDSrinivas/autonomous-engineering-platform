from prometheus_client import Counter, Histogram, Gauge

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

# RAG (Retrieval Augmented Generation) metrics
RAG_RETRIEVAL_LATENCY = Histogram(
    "aep_rag_retrieval_latency_ms",
    "RAG context retrieval latency in milliseconds",
    ["phase"],
    buckets=(10, 25, 50, 100, 200, 400, 800, 1600),
)

RAG_CHUNKS_RETRIEVED = Counter(
    "aep_rag_chunks_retrieved_total",
    "Total number of RAG chunks retrieved",
    ["phase"],
)

# Iteration-level tracing metrics
TASK_ITERATIONS = Histogram(
    "aep_task_iterations",
    "Number of LLM iterations per task",
    ["status"],
    buckets=(1, 2, 3, 5, 8, 13, 21, 34),
)

TASK_COMPLETION_TIME = Histogram(
    "aep_task_completion_time_ms",
    "Total task completion time in milliseconds",
    ["status"],
    buckets=(1000, 5000, 10000, 30000, 60000, 120000, 300000),
)

# Phase 3: Provider health tracking metrics
PROVIDER_CALLS = Counter(
    "aep_provider_calls_total",
    "Provider calls (attempted)",
    ["provider", "status"],  # success|error|timeout
)

PROVIDER_ERRORS = Counter(
    "aep_provider_errors_total",
    "Provider errors by type",
    ["provider", "error_type"],  # http|timeout|network|rate_limit|auth|unknown
)

CIRCUIT_BREAKER_STATE = Gauge(
    "aep_circuit_breaker_state",
    "Circuit breaker state (0=closed,1=open,2=half_open)",
    ["provider"],
)

# Phase 4: Budget enforcement metrics
BUDGET_RESERVE_TOTAL = Counter(
    "aep_budget_reserve_total",
    "Budget reserve attempts",
    ["scope_type", "status"],  # status: success|exceeded|unavailable
)

BUDGET_TOKENS_RESERVED = Counter(
    "aep_budget_tokens_reserved_total",
    "Total tokens reserved (pre-flight)",
    ["scope_type"],
)

BUDGET_TOKENS_COMMITTED = Counter(
    "aep_budget_tokens_committed_total",
    "Total tokens committed (actual usage)",
    ["scope_type"],
)

BUDGET_TOKENS_RELEASED = Counter(
    "aep_budget_tokens_released_total",
    "Total tokens released (cancelled/error)",
    ["scope_type"],
)

BUDGET_OVERSPEND_ANOMALIES = Counter(
    "aep_budget_overspend_anomalies_total",
    "Overspend anomalies (actual >> estimate)",
    ["scope_type", "severity"],  # severity: moderate|critical
)

# NOTE: BUDGET_CURRENT_USAGE, BUDGET_CURRENT_RESERVED, BUDGET_LIMIT gauges
# intentionally omitted. Properly updating gauges requires a background
# Redis-polling task (to read hashes across all active scopes), which is
# planned for a future observability phase. Shipping always-zero gauges
# would make dashboards and alerts inaccurate.
