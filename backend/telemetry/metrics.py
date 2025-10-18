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
