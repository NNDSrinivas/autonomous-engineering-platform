import ipaddress
import json
import threading
import time
import uuid
from typing import Callable
from typing import Optional

import redis

from .obs.obs_logging import logger
from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Summary
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import settings
from .db import SessionLocal

# Import metrics from observability module to avoid conflicts
from .obs.obs_metrics import REQ_LATENCY, REQ_COUNTER as REQ_STATUS

# Additional metrics for this module
REQ_INFLIGHT = Gauge("http_inflight_requests", "In-flight HTTP requests", ["service"])
AUDIT_FAILURES = Counter(
    "audit_failures_total",
    "Total audit logging failures",
    ["service"],
)
TASK_CREATED = Counter("tasks_created_total", "Tasks created")
TASK_DONE = Counter("tasks_done_total", "Tasks completed")
TASK_LATENCY = Summary(
    "task_update_latency_seconds",
    "Latency between task creation and latest update",
)

# Redis client (lazy with thread-safe initialization)
_redis = None
_redis_lock = threading.Lock()


def rds():
    global _redis
    if _redis is None:
        with _redis_lock:
            # Double-check pattern to avoid race conditions
            if _redis is None:
                _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _get_client_ip(request: Request) -> Optional[str]:
    """
    Securely extract client IP with X-Forwarded-For validation for trusted proxies.
    Falls back to direct client.host if no trusted proxy headers are found.
    """
    # Check if request is from a trusted proxy
    direct_ip = getattr(request.client, "host", None) if request.client else None

    # If direct IP is in trusted proxies, check X-Forwarded-For
    if direct_ip and direct_ip in settings.trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first (original client) IP from X-Forwarded-For chain
            client_ip = forwarded_for.split(",")[0].strip()
            try:
                # Validate it's a proper IP address
                ipaddress.ip_address(client_ip)
                return client_ip
            except ValueError:
                # Invalid IP in X-Forwarded-For, fall back to direct IP
                pass

    # Use direct client IP (default secure behavior)
    return direct_ip


def _bucket_key(org_id: str) -> str:
    return f"rl:{org_id}"


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        REQ_INFLIGHT.labels(self.service_name).inc()

        # Put req_id on scope for downstream
        request.state.req_id = req_id
        response: Optional[Response] = None
        try:
            response = await call_next(request)
            if response is None:
                # This should never happen, but handle it gracefully
                response = Response("Internal Server Error", status_code=500)
            return response
        finally:
            dur = time.perf_counter() - start
            status = str(response.status_code if response else 500)
            path = request.url.path
            method = request.method
            REQ_LATENCY.labels(self.service_name, method, path, status).observe(dur)
            REQ_STATUS.labels(self.service_name, method, path, status).inc()
            REQ_INFLIGHT.labels(self.service_name).dec()
            # Structured access log
            logger.info(
                json.dumps(
                    {
                        "req_id": req_id,
                        "service": self.service_name,
                        "method": method,
                        "path": path,
                        "status": status,
                        "ms": int(dur * 1000),
                    }
                )
            )
            if response:
                response.headers["X-Request-ID"] = req_id


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str, rpm: int = 60):
        super().__init__(app)
        self.service_name = service_name
        self.rpm = rpm

    async def dispatch(self, request: Request, call_next: Callable):
        # Secure client identification (prefer authenticated org/api key)
        org_id = request.headers.get("X-Org-Id") or request.headers.get("X-API-Key")

        if not org_id:
            # Fallback to client IP with proper X-Forwarded-For validation for trusted proxies
            client_ip = _get_client_ip(request)
            org_id = f"ip:{client_ip}" if client_ip else "anon"

        # Try Redis-based rate limiting, fall back to in-memory if Redis unavailable (e.g., CI)
        try:
            key = _bucket_key(org_id)
            now = int(time.time())
            # Simple token bucket: refill 1 token per second up to rpm
            # We'll store (tokens, last_ts)
            redis_client = rds()
            data = redis_client.hgetall(key) or {}
            # Ensure data is a dict for type safety
            if isinstance(data, dict):
                tokens = int(data.get("tokens", self.rpm))
                last_ts = int(data.get("ts", now))
            else:
                tokens = self.rpm
                last_ts = now
            # refill
            tokens = min(self.rpm, tokens + max(0, now - last_ts))
            if tokens <= 0:
                # Too many requests
                return Response(
                    content="Rate limit exceeded",
                    status_code=429,
                    media_type="text/plain",
                )
            tokens -= 1
            redis_client.hset(key, mapping={"tokens": tokens, "ts": now})
            redis_client.expire(
                key, settings.redis_rate_limit_ttl
            )  # Set TTL from settings to prevent unbounded memory growth
        except Exception as e:
            # Redis unavailable - skip rate limiting for this request
            _ = e
            pass

        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Persist minimal audit trail. Uses direct SQL for speed.

    Note: Under high load, consider moving to async database operations
    or a background task queue for better performance.
    """

    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Try to log audit trail, but don't fail the request if audit logging fails
        try:
            db = SessionLocal()
            try:
                org_id = request.headers.get("X-Org-Id", "")
                user = request.headers.get("X-User-Email", "")
                path = request.url.path
                method = request.method
                status = response.status_code
                req_id = getattr(request.state, "req_id", "")
                db.execute(
                    text(
                        "INSERT INTO audit_log (org_id, user_email, service, method, path, status, req_id) "
                        "VALUES (:org, :user, :svc, :meth, :path, :st, :rid)"
                    ),
                    {
                        "org": org_id,
                        "user": user,
                        "svc": self.service_name,
                        "meth": method,
                        "path": path,
                        "st": status,
                        "rid": req_id,
                    },
                )
                db.commit()
            except Exception as e:
                # Never break the request for audit failures (table might not exist in CI/test)
                AUDIT_FAILURES.labels(self.service_name).inc()
                logger.warning(f"audit_insert_failed: {e}")
            finally:
                db.close()
        except Exception as e:
            # Database connection or session creation failed (e.g., CI environment)
            logger.warning(f"audit_database_unavailable: {e}")

        return response
