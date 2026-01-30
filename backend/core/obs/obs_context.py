from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from contextvars import ContextVar, Token

try:  # Optional structlog support
    from structlog.contextvars import bind_contextvars, clear_contextvars  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    bind_contextvars = None
    clear_contextvars = None


_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_org_id: ContextVar[Optional[str]] = ContextVar("org_id", default=None)
_user_sub: ContextVar[Optional[str]] = ContextVar("user_sub", default=None)


@dataclass
class ContextTokens:
    request_id: Optional[Token]
    trace_id: Optional[Token]
    org_id: Optional[Token]
    user_sub: Optional[Token]


def bind_request_context(
    request_id: Optional[str],
    trace_id: Optional[str],
    org_id: Optional[str],
    user_sub: Optional[str],
) -> ContextTokens:
    tokens = ContextTokens(
        request_id=_request_id.set(request_id) if request_id else None,
        trace_id=_trace_id.set(trace_id) if trace_id else None,
        org_id=_org_id.set(org_id) if org_id else None,
        user_sub=_user_sub.set(user_sub) if user_sub else None,
    )
    if bind_contextvars:
        bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            org_id=org_id,
            user_sub=user_sub,
        )
    return tokens


def clear_request_context(tokens: ContextTokens) -> None:
    if tokens.request_id is not None:
        _request_id.reset(tokens.request_id)
    if tokens.trace_id is not None:
        _trace_id.reset(tokens.trace_id)
    if tokens.org_id is not None:
        _org_id.reset(tokens.org_id)
    if tokens.user_sub is not None:
        _user_sub.reset(tokens.user_sub)
    if clear_contextvars:
        clear_contextvars()


def get_request_context() -> dict[str, Optional[str]]:
    return {
        "request_id": _request_id.get(),
        "trace_id": _trace_id.get(),
        "org_id": _org_id.get(),
        "user_sub": _user_sub.get(),
    }
