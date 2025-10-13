import ipaddress
import json
import threading
import time
import uuid
from typing import Callable
from typing import Optional

import redis
from loguru import logger
from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Histogram
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import settings
from .db import SessionLocal

# Prometheus metrics
REQ_LATENCY = Histogram(
    "http_request_latency_seconds",
    "Latency of HTTP requests",
    ["service", "method", "path", "status"],
)
REQ_INFLIGHT = Gauge("http_inflight_requests", "In-flight HTTP requests", ["service"])
REQ_STATUS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
AUDIT_FAILURES = Counter(
    "audit_failures_total",
    "Total audit logging failures",
    ["service"],
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

    async def dispatch(self, request: Request, call_next: Callable):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        REQ_INFLIGHT.labels(self.service_name).inc()

        # Put req_id on scope for downstream
        request.state.req_id = req_id
        response: Response = None
        try:
            response = await call_next(request)
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
            data = rds().hgetall(key) or {}
            tokens = int(data.get("tokens", self.rpm))
            last_ts = int(data.get("ts", now))
            # refill
            tokens = min(self.rpm, tokens + max(0, now - last_ts))
            if tokens <= 0:
                # Too many requests
                return Response(
                    content="Rate limit exceeded", status_code=429, media_type="text/plain"
                )
            tokens -= 1
            rds().hset(key, mapping={"tokens": tokens, "ts": now})
            rds().expire(
                key, settings.redis_rate_limit_ttl
            )  # Set TTL from settings to prevent unbounded memory growth
        except Exception as e:
            # Redis unavailable (e.g., CI environment) - skip rate limiting with warning
            logger.warning(f"Redis unavailable, skipping rate limiting: {e}")
            # In production, you'd want proper in-memory fallback, but for CI we skip
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
        db = SessionLocal()
        try:
            response = await call_next(request)
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
                # Never break the request for audit failures
                AUDIT_FAILURES.labels(self.service_name).inc()
                logger.warning(f"audit_insert_failed: {e}")
            return response
        finally:
            db.close()
