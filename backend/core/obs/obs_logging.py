from __future__ import annotations
import json
import logging as std_logging
import os
import re
import sys
import time
from typing import Any, Dict

from .obs_context import get_request_context

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SERVICE_NAME = os.getenv("APP_NAME", "aep")


class JsonFormatter(std_logging.Formatter):
    def format(self, record: std_logging.LogRecord) -> str:
        message = _redact_text(record.getMessage())
        base: Dict[str, Any] = {
            "ts": int(time.time() * 1000),
            "level": record.levelname,
            "msg": message,
            "logger": record.name,
            "service": SERVICE_NAME,
        }
        # Fill context if not already present on record
        for key, value in get_request_context().items():
            if value is not None and getattr(record, key, None) is None:
                base[key] = value
        # Attach extra fields if present
        for key in (
            "request_id",
            "trace_id",
            "org_id",
            "user_sub",
            "route",
            "method",
            "status",
            "error_code",
        ):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        if record.exc_info:
            base["exc"] = _redact_text(self.formatException(record.exc_info))
        return json.dumps(base, ensure_ascii=False)


class RequestContextFilter(std_logging.Filter):
    def filter(self, record: std_logging.LogRecord) -> bool:
        ctx = get_request_context()
        for key, value in ctx.items():
            if value is not None and getattr(record, key, None) is None:
                setattr(record, key, value)
        return True


def configure_json_logging() -> None:
    handler = std_logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestContextFilter())
    root = std_logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(std_logging, LOG_LEVEL, std_logging.INFO))
    _configure_structlog()


# Convenience logger
logger = std_logging.getLogger("aep")


_REDACT_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[a-z0-9\-\._~\+/]+=*"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\\s,]+"), r"\\1=[REDACTED]"),
    (re.compile(r"(?i)\"(api[_-]?key|token|secret|password)\"\\s*:\\s*\"[^\"]+\""), r"\"\\1\":\"[REDACTED]\""),
]


def _redact_text(value: str) -> str:
    redacted = value
    for pattern, replacement in _REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def _redact_event(_logger: Any, _method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in list(event_dict.items()):
        event_dict[key] = _redact_value(value)
    return event_dict


def _configure_structlog() -> None:
    try:
        import structlog
    except Exception:
        return

    level = getattr(std_logging, LOG_LEVEL, std_logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_event,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
