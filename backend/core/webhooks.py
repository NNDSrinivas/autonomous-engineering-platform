"""
Shared webhook verification utilities.

Supports simple shared secret headers today; can be extended to HMAC signatures
per connector (GitHub, Slack, etc.).
"""

from __future__ import annotations

import hmac
import logging
from hashlib import sha256
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def verify_shared_secret(
    incoming: Optional[str],
    expected: Optional[str],
    connector: str,
) -> None:
    """
    Verify a shared secret header; raise HTTPException on failure.
    """
    if not expected:
        logger.warning("webhook.secret_not_configured", extra={"connector": connector})
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    if not incoming or not hmac.compare_digest(incoming, expected):
        logger.warning("webhook.invalid_secret", extra={"connector": connector})
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def verify_hmac_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
    connector: str,
    scheme_prefix: str = "sha256=",
) -> None:
    """
    Verify an HMAC signature (e.g., GitHub style).
    """
    if not secret:
        logger.warning(
            "webhook.hmac_secret_not_configured", extra={"connector": connector}
        )
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    if not signature or not signature.startswith(scheme_prefix):
        logger.warning(
            "webhook.invalid_signature_header", extra={"connector": connector}
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    expected = hmac.new(secret.encode(), payload, sha256).hexdigest()
    provided = signature[len(scheme_prefix) :]
    if not hmac.compare_digest(expected, provided):
        logger.warning("webhook.signature_mismatch", extra={"connector": connector})
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def verify_slack_signature(
    timestamp: Optional[str],
    signature: Optional[str],
    payload: bytes,
    signing_secret: Optional[str],
    tolerance_seconds: int = 60 * 5,
) -> None:
    """
    Verify Slack-style signatures: v0={hash}, where hash = HMAC_SHA256(secret, "v0:{ts}:{body}")
    """
    if not signing_secret:
        logger.warning("webhook.slack_secret_missing")
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    if not (timestamp and signature):
        logger.warning("webhook.slack_signature_missing")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    if not signature.startswith("v0="):
        logger.warning("webhook.slack_signature_prefix")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Optional: timestamp tolerance check to prevent replay
    try:
        import time

        ts_int = int(timestamp)
        if abs(time.time() - ts_int) > tolerance_seconds:
            logger.warning("webhook.slack_signature_stale")
            raise HTTPException(status_code=401, detail="Stale webhook timestamp")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid webhook timestamp")

    basestring = f"v0:{timestamp}:{payload.decode('utf-8')}"
    expected = hmac.new(
        signing_secret.encode(), basestring.encode(), sha256
    ).hexdigest()
    provided = signature.split("=", 1)[1]
    if not hmac.compare_digest(expected, provided):
        try:
            import json

            payload_obj = json.loads(payload.decode("utf-8"))
            alt_variants = [
                json.dumps(payload_obj),
                json.dumps(payload_obj, separators=(",", ":"), ensure_ascii=False),
            ]
            for alt_body in alt_variants:
                alt_basestring = f"v0:{timestamp}:{alt_body}"
                alt_expected = hmac.new(
                    signing_secret.encode(), alt_basestring.encode(), sha256
                ).hexdigest()
                if hmac.compare_digest(alt_expected, provided):
                    return
        except Exception:
            pass
        logger.warning("webhook.slack_signature_mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
