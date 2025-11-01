from __future__ import annotations
import json
import logging as std_logging
import os
import sys
import time
from typing import Any, Dict

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SERVICE_NAME = os.getenv("APP_NAME", "aep")


class JsonFormatter(std_logging.Formatter):
    def format(self, record: std_logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "ts": int(time.time() * 1000),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "service": SERVICE_NAME,
        }
        # Attach extra fields if present
        for key in ("request_id", "org_id", "user_sub", "route", "method", "status"):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


def configure_json_logging() -> None:
    handler = std_logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = std_logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(std_logging, LOG_LEVEL, std_logging.INFO))


# Convenience logger
logger = std_logging.getLogger("aep")
