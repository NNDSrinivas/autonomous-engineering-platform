"""SQL query constants for the LLM module."""

# Audit logging queries
INSERT_LLM_CALL_SUCCESS = """
INSERT INTO llm_call (phase, model, status, prompt_hash, tokens, cost_usd, latency_ms, org_id, user_id)
VALUES (:phase, :model, :status, :prompt_hash, :tokens, :cost_usd, :latency_ms, :org_id, :user_id)
"""

INSERT_LLM_CALL_ERROR = """
INSERT INTO llm_call (phase, model, status, prompt_hash, tokens, cost_usd, latency_ms, error_message, org_id, user_id)
VALUES (:phase, :model, :status, :prompt_hash, :tokens, :cost_usd, :latency_ms, :error_message, :org_id, :user_id)
"""