"""
OAuth state helpers for connector flows.

Creates signed, time-limited state tokens so we don't need server-side storage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict


class OAuthStateError(ValueError):
    """Raised when an OAuth state token is invalid or expired."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_state(payload: Dict[str, Any], secret: str, ttl_seconds: int) -> str:
    """
    Create a signed, expiring OAuth state token.
    """
    now = int(time.time())
    data = dict(payload)
    data["iat"] = now
    data["exp"] = now + ttl_seconds
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _b64url_encode(raw)
    signature = _sign(secret, encoded)
    return f"{encoded}.{signature}"


def parse_state(state: str, secret: str) -> Dict[str, Any]:
    """
    Validate and parse an OAuth state token.
    """
    if not state or "." not in state:
        raise OAuthStateError("State token is missing or malformed")
    encoded, signature = state.split(".", 1)
    expected = _sign(secret, encoded)
    if not hmac.compare_digest(signature, expected):
        raise OAuthStateError("State token signature mismatch")
    payload = json.loads(_b64url_decode(encoded))
    now = int(time.time())
    if now > int(payload.get("exp", 0)):
        raise OAuthStateError("State token has expired")
    return payload

