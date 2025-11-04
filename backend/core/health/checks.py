from __future__ import annotations
import time
from typing import TypedDict
import logging

# Optional deps (best-effort)
text = None
get_engine = None
try:
    from sqlalchemy import text
    from core.db import get_engine
except ImportError:
    pass  # text and get_engine remain None

cache = None
try:
    from infra.cache.redis_cache import cache
except ImportError:
    pass  # cache remains None


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
            "detail": f"check failed: {type(e).__name__}",
        }


def check_self() -> CheckResult:
    return _timed(lambda: None, "self")


def check_db() -> CheckResult:
    def _q():
        if get_engine is None or text is None:
            raise RuntimeError("db not configured")
        # Uses engine's connection pool efficiently - connections are reused and auto-closed
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))

    return _timed(_q, "db")


def check_redis() -> CheckResult:
    async def _ping():
        if cache is None or getattr(cache, "_r", None) is None:
            # lazy-init by attempting a GET on a nonsense key
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
    checks = [check_self()]
    # include optional checks
    try:
        checks.append(check_db())
    except Exception:
        logging.exception("DB readiness check failed")
        checks.append(
            {"name": "db", "ok": False, "latency_ms": 0, "detail": "internal error"}
        )
    try:
        checks.append(check_redis())
    except Exception:
        logging.exception("Redis readiness check failed")
        checks.append(
            {"name": "redis", "ok": False, "latency_ms": 0, "detail": "internal error"}
        )

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks}


def liveness_payload() -> dict:
    # keep liveness ultra-simple to avoid kill-loops
    return {"ok": True, "checks": [check_self()]}
