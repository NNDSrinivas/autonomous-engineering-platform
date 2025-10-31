from fastapi import APIRouter, Body, HTTPException, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
import hashlib
import time
import logging
import os

from ..core.cache import cache
from ..core.db import get_db, safe_commit_with_rollback
from ..core.utils import generate_prompt_hash, validate_header_value
from ..llm.router import ModelRouter, AuditContext

# Initialize router and dependencies
router = APIRouter(prefix="/api/plan", tags=["plan"])

logger = logging.getLogger(__name__)

# Configuration constants
MAX_LLM_RESPONSE_SIZE = 1024 * 1024  # 1 MB limit for LLM responses


# Singleton instance for ModelRouter
_model_router_instance = None


def get_model_router():
    """Get the model router singleton instance."""
    global _model_router_instance
    if _model_router_instance is None:
        _model_router_instance = ModelRouter()
    return _model_router_instance


def load_plan_prompt() -> str:
    """Load the plan prompt template."""
    # Allow override via environment variable
    env_prompt_path = os.environ.get("PLAN_PROMPT_PATH")
    if env_prompt_path:
        prompt_path = env_prompt_path
    else:
        # Path relative to this file
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "llm", "prompts", "plan.md"
        )
        prompt_path = os.path.normpath(prompt_path)

    try:
        with open(prompt_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Plan prompt file not found: {prompt_path}")
        return "You are an autonomous engineering planner. Generate a step-by-step plan based on the context provided."


@router.post("/{key}")
async def generate_plan(
    key: str,
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    Generate an execution plan for a given ticket using LLM.

    Args:
        key: Ticket key or identifier
        payload: Request payload containing contextPack

    Returns:
        Dictionary containing the generated plan and telemetry data
    """
    try:
        context_pack = payload.get("contextPack", {})

        if not context_pack:
            raise HTTPException(status_code=400, detail="contextPack is required")

        # Create cache key from context pack content
        cache_key = hashlib.sha256(
            json.dumps(context_pack, sort_keys=True).encode()
        ).hexdigest()

        # Check cache first
        cached_result = await cache.get_json(cache_key)
        if cached_result:
            logger.info(f"Returning cached plan for key: {key}")
            cached_result["cached"] = True
            return cached_result

        # Load prompt template
        prompt = load_plan_prompt()

        # Extract and validate identity headers for audit logging
        raw_org_id = request.headers.get("X-Org-Id") if request else None
        raw_user_id = request.headers.get("X-User-Id") if request else None

        # Validate and sanitize header values
        org_id = validate_header_value(raw_org_id)
        user_id = validate_header_value(raw_user_id)

        # Create audit context for LLM call
        audit_context = AuditContext(
            db=db,
            prompt_hash=generate_prompt_hash(prompt, context_pack),
            org_id=org_id,
            user_id=user_id,
        )

        # Call LLM via model router
        logger.info(f"Generating new plan for key: {key}")
        start_time = time.time()

        try:
            response_text, telemetry = get_model_router().call(
                "plan",
                prompt,
                context_pack,
                audit_context=audit_context,
            )

            # Parse LLM response with size limits
            try:
                # Limit LLM response size to prevent memory exhaustion
                if len(response_text) > MAX_LLM_RESPONSE_SIZE:
                    logger.warning(
                        f"LLM response too large: {len(response_text)} bytes"
                    )
                    raise ValueError("LLM response too large to parse as JSON")

                parsed_response = json.loads(response_text)
                plan = parsed_response.get("plan", {"items": []})
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse LLM response: {e}")
                # Fallback: create a simple plan structure
                plan = {
                    "items": [
                        {
                            "id": "fallback-1",
                            "kind": "edit",
                            "desc": "Review and implement changes based on ticket requirements",
                            "files": [],
                        }
                    ]
                }

        except Exception as e:
            logger.error(f"LLM call failed for key {key}: {e}")

            # Commit audit logging transaction even on error to ensure audit trail is complete
            if audit_context.db:
                safe_commit_with_rollback(
                    audit_context.db, logger, "audit transaction (on error)"
                )

            # Return error plan - use generic message for security
            plan = {
                "items": [
                    {
                        "id": "error-1",
                        "kind": "edit",
                        "desc": "Plan generation failed due to an internal error. Please try again later.",
                        "files": [],
                    }
                ]
            }
            telemetry = {
                "phase": "plan",
                "model": "error",
                "tokens": 0,
                "cost_usd": 0,
                "latency_ms": 0,
                "error": "Internal error",
            }

        # Build result
        total_time = (time.time() - start_time) * 1000
        result = {
            "plan": plan,
            "telemetry": telemetry,
            "key": key,
            "timestamp": time.time(),
            "total_time_ms": round(total_time, 2),
            "cached": False,
        }

        # Only cache successful results (not error responses)
        if not telemetry.get("error"):
            await cache.set_json(cache_key, result, ttl_sec=3600)

        # Commit audit transaction after successful plan generation and caching
        if audit_context.db and not telemetry.get("error"):
            safe_commit_with_rollback(audit_context.db, logger, "audit transaction")

        logger.info(
            f"Generated plan for {key}: {len(plan.get('items', []))} steps, "
            f"${telemetry.get('cost_usd', 0):.6f}, {total_time:.0f}ms"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating plan for {key}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get usage metrics and statistics."""
    try:
        usage_stats = get_model_router().get_usage_stats()
        budget_check = get_model_router().check_budget("plan")

        return {
            "usage": usage_stats,
            "budget": budget_check,
            "cache_enabled": os.getenv("CACHE_ENABLED", "true").lower() == "true",
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get metrics due to an internal error."
        )


@router.post("/clear-cache")
async def clear_cache() -> Dict[str, str]:
    """Clear the plan cache."""
    try:
        # Our distributed cache doesn't support bulk clear
        # In a production environment, you would typically clear specific keys
        logger.info(
            "Cache clear requested - distributed cache doesn't support bulk clear"
        )
        return {"message": "Cache clear requested - individual keys expire naturally"}
    except Exception as e:
        logger.error(f"Cache clearing failed: {type(e).__name__}")
        raise HTTPException(
            status_code=500, detail="Failed to clear cache due to an internal error."
        )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "plan-api", "timestamp": str(time.time())}
