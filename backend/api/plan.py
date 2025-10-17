from fastapi import APIRouter, Body, HTTPException, BackgroundTasks
from typing import Dict, Any
import json
import hashlib
import time
import logging
import os

from ..core.cache import Cache
from ..llm.router import ModelRouter

# Initialize router and dependencies
router = APIRouter(prefix="/api/plan", tags=["plan"])
model_router = None
cache = Cache(ttl=3600)  # 1 hour cache

logger = logging.getLogger(__name__)


def get_model_router():
    """Get the model router instance, initializing if needed."""
    global model_router
    if model_router is None:
        model_router = ModelRouter()
    return model_router


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
    payload: Dict[str, Any] = Body(...),
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
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached plan for key: {key}")
            cached_result["cached"] = True
            return cached_result

        # Load prompt template
        prompt = load_plan_prompt()

        # Call LLM via model router
        logger.info(f"Generating new plan for key: {key}")
        start_time = time.time()

        try:
            response_text, telemetry = get_model_router().call(
                "plan", prompt, context_pack
            )

            # Parse LLM response
            try:
                parsed_response = json.loads(response_text)
                plan = parsed_response.get("plan", {"items": []})
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
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
            # Return error plan - use generic message for security
            plan = {
                "items": [
                    {
                        "id": "error-1",
                        "kind": "edit",
                        "desc": "Plan generation failed due to an internal error. Please check your API credentials and network connection, then try again.",
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
            cache.set(cache_key, result)

        logger.info(
            f"Generated plan for {key}: {len(plan.get('items', []))} steps, "
            f"${telemetry.get('cost_usd', 0):.6f}, {total_time:.0f}ms"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating plan for {key}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get usage metrics and statistics."""
    try:
        usage_stats = get_model_router().get_usage_stats()
        budget_check = get_model_router().check_budget("plan")

        return {
            "usage": usage_stats,
            "budget": budget_check,
            "cache_size": cache.size(),
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/clear-cache")
async def clear_cache() -> Dict[str, str]:
    """Clear the plan cache."""
    try:
        cache.clear()
        logger.info("Plan cache cleared")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "plan-api", "timestamp": str(time.time())}
