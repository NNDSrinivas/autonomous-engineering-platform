"""Budget Manager singleton for global access across services."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.budget_manager import BudgetManager

logger = logging.getLogger(__name__)

_budget_manager_instance: Optional["BudgetManager"] = None
_budget_manager_init_error: Optional[str] = None


def get_budget_manager() -> Optional["BudgetManager"]:
    """
    Get or create the global BudgetManager instance.

    Returns None if:
    - Redis is unavailable
    - Budget policy file is missing
    - BUDGET_ENFORCEMENT_MODE=disabled

    This fail-safe approach ensures budget enforcement doesn't block
    the application when budget infrastructure is unavailable.
    """
    global _budget_manager_instance, _budget_manager_init_error

    if _budget_manager_instance is not None:
        return _budget_manager_instance

    if _budget_manager_init_error is not None:
        # Already tried and failed, don't retry on every request
        return None

    try:
        from backend.services.budget_manager import BudgetManager
        import redis

        # Get enforcement mode
        enforcement_mode = os.getenv("BUDGET_ENFORCEMENT_MODE", "strict").lower()

        # If disabled, return None (skip budget enforcement entirely)
        if enforcement_mode == "disabled":
            logger.info("Budget enforcement disabled via BUDGET_ENFORCEMENT_MODE=disabled")
            _budget_manager_init_error = "disabled"
            return None

        # Initialize Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

        # Test Redis connection
        redis_client.ping()

        # Load budget policy
        env = os.getenv("APP_ENV", "dev").lower()
        policy_path_override = os.getenv("BUDGET_POLICY_PATH")

        if policy_path_override:
            policy_path = Path(policy_path_override)
        else:
            # Default mapping per environment
            repo_root = Path(__file__).parent.parent.parent
            if env == "prod":
                policy_path = repo_root / "shared" / "budget-policy-prod.json"
            elif env == "staging":
                policy_path = repo_root / "shared" / "budget-policy-staging.json"
            else:
                policy_path = repo_root / "shared" / "budget-policy-dev.json"

        if not policy_path.exists():
            if env == "prod":
                # Fail-closed in production
                raise FileNotFoundError(
                    f"Budget policy required in prod: {policy_path}"
                )
            else:
                # Fallback to dev policy in non-prod
                fallback_path = (
                    Path(__file__).parent.parent.parent
                    / "shared"
                    / "budget-policy-dev.json"
                )
                if not fallback_path.exists():
                    raise FileNotFoundError(
                        f"Budget policy not found: {policy_path} (fallback: {fallback_path})"
                    )
                policy_path = fallback_path
                logger.warning(
                    f"Using fallback dev budget policy for env={env}"
                )

        with open(policy_path, "r") as f:
            policy = json.load(f)

        # Create budget manager
        _budget_manager_instance = BudgetManager(
            redis_client=redis_client,
            policy=policy,
            enforcement_mode=enforcement_mode,
        )

        logger.info(
            f"✅ Budget manager initialized | env={env} | mode={enforcement_mode} | policy={policy_path.name}"
        )
        return _budget_manager_instance

    except FileNotFoundError as e:
        _budget_manager_init_error = f"policy_missing: {e}"
        logger.warning(f"⚠️  Budget manager unavailable: {e}")
        return None

    except redis.ConnectionError as e:
        _budget_manager_init_error = f"redis_unavailable: {e}"
        logger.warning(f"⚠️  Budget manager unavailable (Redis error): {e}")
        return None

    except Exception as e:
        _budget_manager_init_error = f"init_error: {e}"
        logger.error(f"❌ Budget manager initialization failed: {e}", exc_info=True)
        return None


def reset_budget_manager() -> None:
    """Reset budget manager instance (for testing)."""
    global _budget_manager_instance, _budget_manager_init_error
    _budget_manager_instance = None
    _budget_manager_init_error = None
