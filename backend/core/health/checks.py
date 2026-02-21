from __future__ import annotations
import time
from typing import TypedDict
import logging

# Optional deps (best-effort)
# Try both import paths: Docker runs from repo root (/app) so modules live under
# backend.*; local dev may run from backend/ directly where core.* is the root.
text = None
get_engine = None
try:
    from sqlalchemy import text
    try:
        from backend.core.db import get_engine  # Docker / repo-root PYTHONPATH
    except ImportError as e:
        # Only fall back to alternate import path if backend.* module itself is missing.
        # If ImportError is due to a transitive dependency or other problem, log and raise.
        if isinstance(e, ModuleNotFoundError) and e.name in (
            "backend.core.db",
            "backend.core",
            "backend",
        ):
            from core.db import get_engine  # local dev with backend/ as root
        else:
            logging.exception("Error importing get_engine from backend.core.db")
            raise
except ImportError as e:
    # DB module not found at either location — treat as optional dependency
    if isinstance(e, ModuleNotFoundError) and e.name in (
        "core.db",
        "core",
        "sqlalchemy",
    ):
        logging.info(
            "Database module not found; DB-dependent health checks are disabled."
        )
    else:
        logging.exception("Error importing database dependencies")
        raise

cache = None
try:
    try:
        from backend.infra.cache.redis_cache import cache  # Docker / repo-root PYTHONPATH
    except ImportError as e:
        # Only fall back to alternate import path if backend.* module itself is missing.
        if isinstance(e, ModuleNotFoundError) and e.name in (
            "backend.infra.cache.redis_cache",
            "backend.infra.cache",
            "backend.infra",
            "backend",
        ):
            from infra.cache.redis_cache import cache  # local dev with backend/ as root
        else:
            logging.exception(
                "Error importing Redis cache from backend.infra.cache.redis_cache"
            )
            raise
except ImportError as e:
    # Cache module not found at either location — treat as optional dependency
    if isinstance(e, ModuleNotFoundError) and e.name in (
        "infra.cache.redis_cache",
        "infra.cache",
        "infra",
    ):
        logging.info(
            "Redis cache module not found; Redis-dependent health checks are disabled."
        )
    else:
        logging.exception("Error importing Redis cache dependencies")
        raise


class CheckResult(TypedDict):
    name: str
    ok: bool
    latency_ms: int
    detail: str


def _timed(fn, name: str) -> CheckResult:
    start = time.time()
    try:
        fn()
        return {
            "name": name,
            "ok": True,
            "latency_ms": int((time.time() - start) * 1000),
            "detail": "ok",
        }
    # Intentionally catch all exceptions to ensure health checks always return a result.
    # This prevents a single failing check from crashing the health endpoint, which is
    # critical for monitoring and load balancer health checks.
    # Note: Using Exception (not BaseException) to allow SystemExit/KeyboardInterrupt to propagate
    except Exception as e:
        # Log both exception type and message for better debugging
        # Avoid exposing sensitive details in the external response
        logging.error(
            "Health check '%s' failed: %s: %s", name, type(e).__name__, str(e)
        )
        return {
            "name": name,
            "ok": False,
            "latency_ms": int((time.time() - start) * 1000),
            "detail": "check failed",
        }


def check_self() -> CheckResult:
    return _timed(lambda: None, "self")


def check_db() -> CheckResult:
    def _q():
        # Verify that imports succeeded (get_engine and text are None if ImportError occurred)
        if get_engine is None or text is None:
            raise RuntimeError("db not configured")
        # get_engine() implements lazy initialization with caching (see core/db.py)
        # so repeated health checks don't create overhead - engine is reused
        # Uses engine's connection pool efficiently - connections are reused and auto-closed
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))

    return _timed(_q, "db")


def check_redis() -> CheckResult:
    """
    Check Redis connectivity using the centralized client.

    Self-heals from stale connections by resetting the pool on first failure.
    """
    async def _ping():
        # Try centralized Redis client (preferred)
        try:
            from backend.services.redis_client import get_redis, reset_redis
            try:
                await get_redis().ping()
            except Exception:
                # Self-healing: reset pool and retry once
                await reset_redis()
                await get_redis().ping()
            return
        except (ImportError, RuntimeError):
            # Fallback to legacy cache if centralized client not initialized
            pass

        # Legacy fallback (deprecated - will be removed in Phase 2)
        if cache is None or getattr(cache, "_r", None) is None:
            await cache.get("__health__")  # type: ignore
        r = getattr(cache, "_r", None)
        if r:
            await r.ping()

    # run async piece in a tiny runner
    import asyncio

    def run():
        asyncio.run(_ping())

    return _timed(run, "redis")


def readiness_payload() -> dict:
    import os

    checks = [check_self()]
    # include optional checks
    try:
        checks.append(check_db())
    except Exception:
        logging.error("DB readiness check failed")
        checks.append(
            {"name": "db", "ok": False, "latency_ms": 0, "detail": "internal error"}
        )

    # Skip the Redis readiness ping in CI/unit-test environments where Redis is not
    # provisioned, but always include a "redis" check entry to keep the payload
    # shape stable. Restrict skipping to CI/test-like environments so prod/staging
    # don't silently mask real Redis outages on /health/ready.
    skip_raw = os.getenv("SKIP_REDIS_HEALTH_CHECK", "")
    skip_redis = skip_raw.strip().lower() in ("true", "1")
    ci_env = os.getenv("CI", "").strip().lower() in ("true", "1")
    app_env = os.getenv("APP_ENV", "").strip().lower()
    should_skip_redis = skip_redis and (ci_env or app_env == "ci")

    if should_skip_redis:
        checks.append(
            {
                "name": "redis",
                "ok": True,
                "latency_ms": 0,
                "detail": "skipped via SKIP_REDIS_HEALTH_CHECK",
            }
        )
    else:
        try:
            checks.append(check_redis())
        except Exception:
            logging.exception("Redis readiness check failed")
            checks.append(
                {
                    "name": "redis",
                    "ok": False,
                    "latency_ms": 0,
                    "detail": "internal error",
                }
            )

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks}


def liveness_payload() -> dict:
    # keep liveness ultra-simple to avoid kill-loops
    return {"ok": True, "checks": [check_self()]}
