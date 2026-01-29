from __future__ import annotations

from typing import Dict

_STATUS_TO_CODE: Dict[int, str] = {
    400: "INVALID_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def error_code_for_status(status_code: int) -> str:
    return _STATUS_TO_CODE.get(status_code, "UNKNOWN_ERROR")
