"""
OAuth Device Code Flow for VS Code Extension Authentication

Provides secure authentication without client secrets using OAuth 2.0 device
code flow.
This allows the VS Code extension to authenticate users through their browser.
"""

import json
import logging
import os
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from backend.core.config import settings
from backend.core.db import get_db
from backend.core.eventstore.models import AuditLog

try:
    from redis import asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis = None
    HAS_REDIS = False

# Log warning about insecure development mode
logger = logging.getLogger(__name__)
if settings.oauth_device_use_in_memory_store:
    logger.warning(
        "🚨 SECURITY WARNING: OAuth device code flow is running in "
        "DEVELOPMENT MODE with in-memory storage. This is NOT suitable for "
        "production! The OAUTH_DEVICE_USE_IN_MEMORY_STORE flag is enabled. "
        "Replace with Redis or persistent database before production deployment."
    )

router = APIRouter(prefix="/oauth", tags=["OAuth Device Code"])

# SECURITY: In-memory store for development only.
# Replace with Redis/database for production.
# This code should not be used in production environments.
# Set OAUTH_DEVICE_USE_IN_MEMORY_STORE=true in your environment ONLY
# for development/testing.
_device_codes: Dict[str, Dict[str, Any]] = {}
_access_tokens: Dict[str, Dict[str, Any]] = {}
_redis_client = None

DEVICE_CODE_PREFIX = "oauth_device:device:"
USER_CODE_PREFIX = "oauth_device:user:"
TOKEN_PREFIX = "oauth_device:token:"


def _audit_event(
    db: Session | None,
    *,
    event_type: str,
    payload: dict,
    status_code: int,
    actor_sub: str | None = None,
    org_key: str | None = None,
    route: str = "/oauth/device",
    method: str = "POST",
) -> None:
    if db is None:
        return
    try:
        if os.getenv("PYTEST_CURRENT_TEST"):
            inspector = inspect(db.bind)
            if "audit_log_enhanced" not in inspector.get_table_names():
                AuditLog.__table__.create(bind=db.bind, checkfirst=True)
        audit_record = AuditLog(
            org_key=org_key,
            actor_sub=actor_sub,
            actor_email=None,
            route=route,
            method=method,
            event_type=event_type,
            resource_id=payload.get("device_code") or payload.get("token"),
            payload=payload,
            status_code=status_code,
        )
        db.add(audit_record)
        db.commit()
    except Exception as exc:
        logger.warning("oauth_device.audit_failed: %s", exc)


async def _get_redis():
    if settings.oauth_device_use_in_memory_store:
        if settings.app_env in ["prod", "production"]:
            raise HTTPException(
                status_code=500,
                detail="In-memory OAuth device storage is not allowed in production.",
            )
        return None
    if not HAS_REDIS or not settings.redis_url:
        raise HTTPException(
            status_code=500,
            detail="OAuth device storage requires Redis in production mode.",
        )
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
        await _redis_client.ping()
    return _redis_client


def _ttl_seconds(expires_at: datetime) -> int:
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(ttl, 1)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


async def _load_device_info(device_code: str) -> Optional[Dict[str, Any]]:
    if settings.oauth_device_use_in_memory_store:
        return _device_codes.get(device_code)
    redis = await _get_redis()
    raw = await redis.get(f"{DEVICE_CODE_PREFIX}{device_code}")
    if not raw:
        return None
    return json.loads(raw)


async def _save_device_info(device_code: str, info: Dict[str, Any]) -> None:
    if settings.oauth_device_use_in_memory_store:
        _device_codes[device_code] = info
        return
    redis = await _get_redis()
    expires_at = datetime.fromisoformat(info["expires_at"])
    ttl = _ttl_seconds(expires_at)
    payload = json.dumps(info)
    await redis.set(f"{DEVICE_CODE_PREFIX}{device_code}", payload, ex=ttl)
    await redis.set(f"{USER_CODE_PREFIX}{info['user_code']}", device_code, ex=ttl)


async def _delete_device_info(device_code: str, user_code: Optional[str]) -> None:
    if settings.oauth_device_use_in_memory_store:
        _device_codes.pop(device_code, None)
        return
    redis = await _get_redis()
    await redis.delete(f"{DEVICE_CODE_PREFIX}{device_code}")
    if user_code:
        await redis.delete(f"{USER_CODE_PREFIX}{user_code}")


async def _find_device_code_by_user_code(user_code: str) -> Optional[str]:
    if settings.oauth_device_use_in_memory_store:
        for dc, info in _device_codes.items():
            if info["user_code"] == user_code:
                return dc
        return None
    redis = await _get_redis()
    return await redis.get(f"{USER_CODE_PREFIX}{user_code}")


async def _save_access_token(token: str, info: Dict[str, Any]) -> None:
    if settings.oauth_device_use_in_memory_store:
        _access_tokens[token] = info
        return
    redis = await _get_redis()
    expires_at = datetime.fromisoformat(info["expires_at"])
    ttl = _ttl_seconds(expires_at)
    await redis.set(f"{TOKEN_PREFIX}{token}", json.dumps(info), ex=ttl)


async def _load_access_token(token: str) -> Optional[Dict[str, Any]]:
    if settings.oauth_device_use_in_memory_store:
        return _access_tokens.get(token)
    redis = await _get_redis()
    raw = await redis.get(f"{TOKEN_PREFIX}{token}")
    if not raw:
        return None
    return json.loads(raw)


async def _delete_access_token(token: str) -> None:
    if settings.oauth_device_use_in_memory_store:
        _access_tokens.pop(token, None)
        return
    redis = await _get_redis()
    await redis.delete(f"{TOKEN_PREFIX}{token}")


class DeviceCodeStartRequest(BaseModel):
    """Request model for starting OAuth device code flow."""

    client_id: Optional[str] = Field(
        default="aep-vscode-extension", description="Client identifier"
    )
    scope: Optional[str] = Field(default="read write", description="Requested scopes")


class DeviceCodeStartResponse(BaseModel):
    """Response model for device code flow start."""

    device_code: str = Field(description="Device verification code")
    user_code: str = Field(description="User verification code to display")
    verification_uri: str = Field(description="URI for user to visit")
    verification_uri_complete: Optional[str] = Field(
        description="Complete URI with user_code"
    )
    expires_in: int = Field(description="Device code expiration in seconds")
    interval: int = Field(description="Polling interval in seconds")


class DeviceCodePollRequest(BaseModel):
    """Request model for polling device code status."""

    device_code: str = Field(description="Device code from start request")
    client_id: Optional[str] = Field(default="aep-vscode-extension")


class DeviceCodeTokenResponse(BaseModel):
    """Response model for successful device code authorization."""

    access_token: str = Field(description="Access token for API calls")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(description="Token expiration in seconds")
    scope: Optional[str] = Field(description="Granted scopes")


class DeviceCodeErrorResponse(BaseModel):
    """Response model for device code flow errors."""

    error: str = Field(description="Error code")
    error_description: Optional[str] = Field(
        description="Human-readable error description"
    )


@router.post("/device/rotate", response_model=DeviceCodeTokenResponse)
async def rotate_access_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Rotate an access token (invalidate old token, issue new one).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )
    old_token = authorization.split(" ", 1)[1].strip()
    token_info = await validate_access_token(old_token)

    # Invalidate old token and issue a new one with fresh TTL
    await _delete_access_token(old_token)
    new_token = secrets.token_urlsafe(32)
    token_ttl = getattr(settings, "oauth_device_token_ttl_seconds", 86400)
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_ttl)
    new_info = {
        "client_id": token_info.get("client_id"),
        "scope": token_info.get("scope"),
        "expires_at": token_expires_at.isoformat(),
        "user_id": token_info.get("user_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rotated_from": old_token,
    }
    await _save_access_token(new_token, new_info)

    _audit_event(
        db,
        event_type="oauth.device.rotate",
        payload={"token": new_token, "rotated_from": old_token},
        status_code=200,
        actor_sub=token_info.get("user_id"),
        org_key=token_info.get("org_id"),
    )

    return DeviceCodeTokenResponse(
        access_token=new_token,
        token_type="Bearer",
        expires_in=token_ttl,
        scope=token_info.get("scope"),
    )


@router.post("/device/start", response_model=DeviceCodeStartResponse)
async def start_device_code_flow(
    request: DeviceCodeStartRequest,
    db: Session = Depends(get_db),
):
    """
    Initiate OAuth device code flow for VS Code extension authentication.

    Returns device code and user code for browser-based authentication.
    """
    try:
        # Generate device code and user code
        device_code = secrets.token_urlsafe(32)
        user_code = _generate_user_code()

        # Store device code with metadata
        # 10 minute expiry
        ttl_seconds = getattr(settings, "oauth_device_code_ttl_seconds", 600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        device_info = {
            "user_code": user_code,
            "client_id": request.client_id,
            "scope": request.scope,
            "expires_at": expires_at.isoformat(),
            "status": "pending",  # pending, authorized, denied
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await _save_device_info(device_code, device_info)

        # Base verification URI (for development, use localhost)
        base_uri = (
            "http://localhost:8000/docs#/OAuth%20Device%20Code/"
            "authorize_device_code_oauth_device_authorize_post"
        )
        verification_uri = base_uri
        verification_uri_complete = f"{base_uri}&user_code={user_code}"

        _audit_event(
            db,
            event_type="oauth.device.start",
            payload={"device_code": device_code, "client_id": request.client_id},
            status_code=200,
        )
        return DeviceCodeStartResponse(
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            verification_uri_complete=verification_uri_complete,
            expires_in=ttl_seconds,
            interval=5,  # Poll every 5 seconds
        )

    except Exception:
        _audit_event(
            db,
            event_type="oauth.device.start.failed",
            payload={"client_id": request.client_id, "scope": request.scope},
            status_code=500,
        )
        raise HTTPException(status_code=500, detail="Failed to start device code flow")


@router.post("/device/poll", response_model=DeviceCodeTokenResponse)
async def poll_device_code(
    request: DeviceCodePollRequest,
    db: Session = Depends(get_db),
):
    """
    Poll for device code authorization completion.

    Returns access token when user completes browser authentication.
    """
    try:
        device_code = request.device_code

        device_info = await _load_device_info(device_code)
        if device_info is None:
            _audit_event(
                db,
                event_type="oauth.device.poll.invalid",
                payload={"device_code": device_code},
                status_code=400,
            )
            raise HTTPException(
                status_code=400,
                detail="invalid_request",
                headers={"Content-Type": "application/json"},
            )

        # Check if expired
        expires_at = _parse_datetime(device_info["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await _delete_device_info(device_code, device_info.get("user_code"))
            _audit_event(
                db,
                event_type="oauth.device.poll.expired",
                payload={"device_code": device_code},
                status_code=400,
            )
            raise HTTPException(
                status_code=400,
                detail="expired_token",
                headers={"Content-Type": "application/json"},
            )

        # Check authorization status
        if device_info["status"] == "pending":
            # For development/testing: Auto-approve after initial delay to simulate user approval
            # In production, this should be replaced with proper web-based user approval
            current_time = datetime.now(timezone.utc)
            created_at = _parse_datetime(device_info["created_at"])
            time_since_creation = (current_time - created_at).total_seconds()

            # Auto-approve after 30 seconds ONLY if development flags are set
            auto_approve = (
                os.environ.get("OAUTH_DEVICE_AUTO_APPROVE", "false").lower() == "true"
            )
            use_memory_store = (
                os.environ.get("OAUTH_DEVICE_USE_IN_MEMORY_STORE", "false").lower()
                == "true"
            )

            if auto_approve and use_memory_store and time_since_creation > 30:
                # SECURITY WARNING: Auto-approving device code in development mode
                logger.warning(
                    "🚨 SECURITY WARNING: Auto-approving device code '%s' "
                    "after %d seconds. This is ONLY for development! "
                    "Never enable auto-approval in production!",
                    device_code[:8] + "...",
                    int(time_since_creation),
                )
                device_info["status"] = "authorized"
                device_info["authorized_at"] = current_time.isoformat()
                device_info["user_id"] = "dev-user"  # In production, use actual user ID
                await _save_device_info(device_code, device_info)
            else:
                _audit_event(
                    db,
                    event_type="oauth.device.poll.pending",
                    payload={"device_code": device_code},
                    status_code=400,
                )
                raise HTTPException(
                    status_code=400,
                    detail="authorization_pending",
                    headers={"Content-Type": "application/json"},
                )

        elif device_info["status"] == "denied":
            await _delete_device_info(device_code, device_info.get("user_code"))
            _audit_event(
                db,
                event_type="oauth.device.poll.denied",
                payload={"device_code": device_code},
                status_code=400,
            )
            raise HTTPException(
                status_code=400,
                detail="access_denied",
                headers={"Content-Type": "application/json"},
            )

        # Generate access token
        if device_info["status"] == "authorized":
            # Rotate any previously issued token for this device code
            previous_token = device_info.get("access_token")
            if previous_token:
                await _delete_access_token(previous_token)

            access_token = secrets.token_urlsafe(32)
            token_ttl = getattr(settings, "oauth_device_token_ttl_seconds", 86400)
            token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_ttl
            )

            # Store access token
            token_info = {
                "client_id": device_info["client_id"],
                "scope": device_info["scope"],
                "expires_at": token_expires_at.isoformat(),
                "user_id": device_info.get("user_id") or "demo-user",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await _save_access_token(access_token, token_info)

            # Clean up device code
            await _delete_device_info(device_code, device_info.get("user_code"))

            _audit_event(
                db,
                event_type="oauth.device.poll.authorized",
                payload={"device_code": device_code, "token": access_token},
                status_code=200,
                actor_sub=token_info.get("user_id"),
            )
            return DeviceCodeTokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=token_ttl,
                scope=device_info["scope"],
            )

        # If we reach here, status is in an unexpected state
        raise HTTPException(
            status_code=400,
            detail="invalid_grant",
            headers={"Content-Type": "application/json"},
        )

    except HTTPException:
        raise
    except Exception:
        _audit_event(
            db,
            event_type="oauth.device.poll.failed",
            payload={"device_code": request.device_code},
            status_code=500,
        )
        raise HTTPException(status_code=500, detail="Failed to poll device code")


class DeviceAuthorizationRequest(BaseModel):
    """Request model for device authorization."""

    user_code: str = Field(description="User code to authorize")
    action: str = Field(description="Authorization action:" "'approve' or 'deny'")
    user_id: Optional[str] = Field(default=None, description="Optional user identifier")
    org_id: Optional[str] = Field(default=None, description="Optional org identifier")


class DeviceAuthorizationResponse(BaseModel):
    """Response model for device authorization."""

    message: str = Field(description="Authorization result message")
    user_code: str = Field(description="User code that was authorized")


@router.post("/device/authorize", response_model=DeviceAuthorizationResponse)
async def authorize_device_code(
    request: DeviceAuthorizationRequest,
    db: Session = Depends(get_db),
):
    """
    Authorize or deny a device code by user code.

    This endpoint allows users to approve or deny device authorization requests
    through a web interface or API call.
    """
    try:
        # Find device code by user code
        device_code = await _find_device_code_by_user_code(request.user_code)

        if not device_code:
            _audit_event(
                db,
                event_type="oauth.device.authorize.invalid",
                payload={"user_code": request.user_code},
                status_code=404,
            )
            raise HTTPException(status_code=404, detail="Invalid user code")

        device_info = await _load_device_info(device_code)
        if device_info is None:
            _audit_event(
                db,
                event_type="oauth.device.authorize.not_found",
                payload={"device_code": device_code},
                status_code=404,
            )
            raise HTTPException(status_code=404, detail="Invalid user code")

        # Check if already expired
        expires_at = _parse_datetime(device_info["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await _delete_device_info(device_code, device_info.get("user_code"))
            _audit_event(
                db,
                event_type="oauth.device.authorize.expired",
                payload={"device_code": device_code},
                status_code=400,
            )
            raise HTTPException(status_code=400, detail="Device code has expired")

        # Update authorization status
        if request.action.lower() == "approve":
            device_info["status"] = "authorized"
            device_info["authorized_at"] = datetime.now(timezone.utc).isoformat()
            if request.user_id:
                device_info["user_id"] = request.user_id
            if request.org_id:
                device_info["org_id"] = request.org_id
            message = f"Device with user code {request.user_code} has been authorized"
            _audit_event(
                db,
                event_type="oauth.device.authorize.approved",
                payload={"device_code": device_code, "user_code": request.user_code},
                status_code=200,
                actor_sub=request.user_id,
                org_key=request.org_id,
            )
        elif request.action.lower() == "deny":
            device_info["status"] = "denied"
            device_info["denied_at"] = datetime.now(timezone.utc).isoformat()
            message = f"Device with user code {request.user_code} has been denied"
            _audit_event(
                db,
                event_type="oauth.device.authorize.denied",
                payload={"device_code": device_code, "user_code": request.user_code},
                status_code=200,
                actor_sub=request.user_id,
                org_key=request.org_id,
            )
        else:
            raise HTTPException(
                status_code=400, detail="Invalid action. Must be 'approve' or 'deny'"
            )

        await _save_device_info(device_code, device_info)

        return DeviceAuthorizationResponse(message=message, user_code=request.user_code)

    except HTTPException:
        raise
    except Exception:
        _audit_event(
            db,
            event_type="oauth.device.authorize.failed",
            payload={"user_code": request.user_code},
            status_code=500,
        )
        raise HTTPException(status_code=500, detail="Failed to authorize device")


def _generate_user_code() -> str:
    """Generate a human-readable user code."""
    # Generate 8-character code with letters and numbers
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace("0", "").replace("O", "").replace("1", "").replace("I", "")

    return "".join(random.choice(chars) for _ in range(8))


async def validate_access_token(token: str) -> Dict[str, Any]:
    """Validate access token and return user info."""
    token_info = await _load_access_token(token)
    if token_info is None:
        raise HTTPException(status_code=401, detail="Invalid access token")

    expires_at = _parse_datetime(token_info["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        await _delete_access_token(token)
        raise HTTPException(status_code=401, detail="Token expired")

    return token_info


# Dependency for protected endpoints
async def get_current_user(authorization: Optional[str] = None):
    """Extract and validate user from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )

    token = authorization.split(" ")[1]
    token_info = await validate_access_token(token)

    return {
        "user_id": token_info["user_id"],
        "client_id": token_info["client_id"],
        "scope": token_info["scope"],
    }
