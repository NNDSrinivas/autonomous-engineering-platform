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

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.db import get_db

try:
    from redis import asyncio as aioredis  # type: ignore

    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore
    HAS_REDIS = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth Device Code"])

if settings.oauth_device_use_in_memory_store:
    logger.warning(
        "OAuth device flow using in-memory store (development only). "
        "Set REDIS_URL and disable OAUTH_DEVICE_USE_IN_MEMORY_STORE for production."
    )

DEVICE_CODE_TTL_SEC = int(getattr(settings, "oauth_device_code_ttl_seconds", 600))
ACCESS_TOKEN_TTL_SEC = int(
    getattr(settings, "oauth_device_access_token_ttl_seconds", 86400)
)

_device_codes: Dict[str, Dict[str, Any]] = {}
_access_tokens: Dict[str, Dict[str, Any]] = {}
_redis = None
_redis_init_attempted = False


def _audit_event(
    _db: Session,
    *,
    event_type: str,
    payload: Dict[str, Any],
    status_code: int,
    actor_sub: Optional[str] = None,
    org_key: Optional[str] = None,
) -> None:
    """Best-effort audit logging; never break auth flow if audit fails."""
    try:
        logger.info(
            "oauth.device.audit",
            extra={
                "event_type": event_type,
                "status_code": status_code,
                "actor_sub": actor_sub,
                "org_key": org_key,
                "payload": payload,
            },
        )
    except Exception:
        # Avoid blocking auth flow on logging failures
        pass


def _use_memory_store() -> bool:
    return bool(settings.oauth_device_use_in_memory_store)


async def _get_redis():
    global _redis, _redis_init_attempted
    if _use_memory_store():
        return None
    if not settings.redis_url or not HAS_REDIS:
        return None
    if _redis is None and not _redis_init_attempted:
        _redis_init_attempted = True
        try:
            _redis = aioredis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=getattr(settings, "redis_max_connections", 20),
            )
            await _redis.ping()
        except Exception as e:
            logger.error("OAuth device Redis connection failed: %s", e)
            _redis = None
    return _redis


async def _require_persistent_store():
    if _use_memory_store():
        return
    if not settings.redis_url or not HAS_REDIS:
        raise HTTPException(
            status_code=503,
            detail="OAuth device store unavailable (Redis required)",
        )
    redis = await _get_redis()
    if not redis:
        raise HTTPException(
            status_code=503,
            detail="OAuth device store unavailable (Redis not reachable)",
        )


def _utc_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _device_key(device_code: str) -> str:
    return f"oauth:device:{device_code}"


def _user_code_key(user_code: str) -> str:
    return f"oauth:user_code:{user_code}"


def _access_token_key(token: str) -> str:
    return f"oauth:access_token:{token}"


async def _store_device_code(device_code: str, info: Dict[str, Any]) -> None:
    if _use_memory_store():
        _device_codes[device_code] = info
        return
    redis = await _get_redis()
    if not redis:
        await _require_persistent_store()
    await redis.setex(_device_key(device_code), DEVICE_CODE_TTL_SEC, json.dumps(info))
    await redis.setex(
        _user_code_key(info["user_code"]),
        DEVICE_CODE_TTL_SEC,
        device_code,
    )


async def _get_device_info(device_code: str) -> Optional[Dict[str, Any]]:
    if _use_memory_store():
        return _device_codes.get(device_code)
    redis = await _get_redis()
    if not redis:
        await _require_persistent_store()
    raw = await redis.get(_device_key(device_code))
    return json.loads(raw) if raw else None


async def _set_device_info(device_code: str, info: Dict[str, Any]) -> None:
    await _store_device_code(device_code, info)


async def _delete_device_code(device_code: str) -> None:
    if _use_memory_store():
        _device_codes.pop(device_code, None)
        return
    redis = await _get_redis()
    if redis:
        info = await _get_device_info(device_code)
        await redis.delete(_device_key(device_code))
        if info and info.get("user_code"):
            await redis.delete(_user_code_key(info["user_code"]))


async def _get_device_code_by_user_code(user_code: str) -> Optional[str]:
    if _use_memory_store():
        for dc, info in _device_codes.items():
            if info.get("user_code") == user_code:
                return dc
        return None
    redis = await _get_redis()
    if not redis:
        await _require_persistent_store()
    return await redis.get(_user_code_key(user_code))


async def _store_access_token(token: str, info: Dict[str, Any]) -> None:
    if _use_memory_store():
        _access_tokens[token] = info
        return
    redis = await _get_redis()
    if not redis:
        await _require_persistent_store()
    await redis.setex(_access_token_key(token), ACCESS_TOKEN_TTL_SEC, json.dumps(info))


async def _get_access_token_info(token: str) -> Optional[Dict[str, Any]]:
    if _use_memory_store():
        return _access_tokens.get(token)
    redis = await _get_redis()
    if not redis:
        await _require_persistent_store()
    raw = await redis.get(_access_token_key(token))
    return json.loads(raw) if raw else None


async def _delete_access_token(token: str) -> None:
    if _use_memory_store():
        _access_tokens.pop(token, None)
        return
    redis = await _get_redis()
    if redis:
        await redis.delete(_access_token_key(token))


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


@router.get("/device/verify", response_class=HTMLResponse)
async def device_verify_page(user_code: Optional[str] = None) -> str:
    """Simple device verification page for local/dev sign-in."""
    prefill = user_code or ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>NAVI Device Sign-In</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: #0b0f1a;
      color: #e8edf5;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }}
    .card {{
      background: #12182a;
      border: 1px solid #1d2740;
      border-radius: 16px;
      padding: 28px 32px;
      width: min(480px, 92vw);
      box-shadow: 0 12px 30px rgba(0,0,0,0.35);
    }}
    h1 {{ font-size: 20px; margin: 0 0 12px; }}
    p {{ color: #b7c2d9; margin: 0 0 16px; }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid #2a3653;
      background: #0f1424;
      color: #e8edf5;
      font-size: 16px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      box-sizing: border-box;
    }}
    button {{
      margin-top: 14px;
      width: 100%;
      padding: 12px 14px;
      border-radius: 10px;
      border: none;
      background: #2d6cdf;
      color: #fff;
      font-size: 16px;
      cursor: pointer;
    }}
    .status {{ margin-top: 12px; font-size: 14px; }}
    .success {{ color: #58d890; }}
    .error {{ color: #ff8a8a; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Finish signing in to NAVI</h1>
    <p>Enter the device code shown in VS Code to authorize this device.</p>
    <input id="code" value="{prefill}" placeholder="XXXX-XXXX"/>
    <button id="submit">Authorize</button>
    <div id="status" class="status"></div>
  </div>
  <script>
    const statusEl = document.getElementById('status');
    const input = document.getElementById('code');
    const button = document.getElementById('submit');
    const submit = async () => {{
      const user_code = (input.value || '').trim();
      if (!user_code) {{
        statusEl.textContent = 'Please enter the code.';
        statusEl.className = 'status error';
        return;
      }}
      statusEl.textContent = 'Authorizing...';
      statusEl.className = 'status';
      try {{
        const res = await fetch('/oauth/device/authorize', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ user_code, action: 'approve' }})
        }});
        if (!res.ok) {{
          const text = await res.text();
          statusEl.textContent = 'Authorization failed: ' + text;
          statusEl.className = 'status error';
          return;
        }}
        statusEl.textContent = 'Authorized! You can return to VS Code.';
        statusEl.className = 'status success';
      }} catch (err) {{
        statusEl.textContent = 'Authorization failed. Please try again.';
        statusEl.className = 'status error';
      }}
    }};
    button.addEventListener('click', submit);
    input.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') submit();
    }});
  </script>
</body>
</html>"""


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
    await _store_access_token(new_token, new_info)

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
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Initiate OAuth device code flow for VS Code extension authentication.

    Returns device code and user code for browser-based authentication.
    """
    try:
        if not _use_memory_store():
            await _require_persistent_store()

        # Generate device code and user code
        device_code = secrets.token_urlsafe(32)
        user_code = _generate_user_code()

        # Store device code with metadata
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEVICE_CODE_TTL_SEC)
        await _store_device_code(
            device_code,
            {
                "user_code": user_code,
                "client_id": request.client_id,
                "scope": request.scope,
                "expires_at": int(expires_at.timestamp()),
                "status": "pending",  # pending, authorized, denied
                "created_at": _utc_ts(),
                "org_id": http_request.headers.get("X-Org-Id"),
                "user_id": http_request.headers.get("X-User-Id"),
            },
        )

        # Base verification URI (defaults to local backend when not configured)
        base_root = settings.public_base_url or "http://localhost:8787"
        verification_uri = f"{base_root}/oauth/device/verify"
        verification_uri_complete = f"{verification_uri}?user_code={user_code}"

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
            expires_in=DEVICE_CODE_TTL_SEC,
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
        device_info = await _get_device_info(device_code)
        if not device_info:
            raise HTTPException(
                status_code=400,
                detail="invalid_request",
                headers={"Content-Type": "application/json"},
            )

        # Check if expired
        expires_at = device_info.get("expires_at")
        if expires_at and _utc_ts() > int(expires_at):
            await _delete_device_code(device_code)
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
            created_at = device_info.get("created_at", _utc_ts())
            time_since_creation = current_time.timestamp() - int(created_at)

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
                device_info["authorized_at"] = int(current_time.timestamp())
                device_info["user_id"] = "dev-user"  # In production, use actual user ID
                await _set_device_info(device_code, device_info)
            else:
                _audit_event(
                    db,
                    event_type="oauth.device.poll.pending",
                    payload={"device_code": device_code},
                    status_code=428,
                )
                # Use 428 to signal client to keep polling (matches DeviceAuthService)
                raise HTTPException(
                    status_code=428,
                    detail="authorization_pending",
                    headers={"Content-Type": "application/json"},
                )

        elif device_info["status"] == "denied":
            await _delete_device_code(device_code)
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
            getattr(settings, "oauth_device_token_ttl_seconds", 86400)
            token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=ACCESS_TOKEN_TTL_SEC
            )

            # Store access token
            await _store_access_token(
                access_token,
                {
                    "client_id": device_info["client_id"],
                    "scope": device_info["scope"],
                    "expires_at": int(token_expires_at.timestamp()),
                    "user_id": device_info.get("user_id") or "demo-user",
                    "org_id": device_info.get("org_id"),
                    "created_at": _utc_ts(),
                },
            )

            # Clean up device code
            await _delete_device_code(device_code)

            _audit_event(
                db,
                event_type="oauth.device.poll.authorized",
                payload={"device_code": device_code, "token": access_token},
                status_code=200,
                actor_sub=device_info.get("user_id"),
            )
            return DeviceCodeTokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=ACCESS_TOKEN_TTL_SEC,
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
        device_code = await _get_device_code_by_user_code(request.user_code)

        if not device_code:
            _audit_event(
                db,
                event_type="oauth.device.authorize.invalid",
                payload={"user_code": request.user_code},
                status_code=404,
            )
            raise HTTPException(status_code=404, detail="Invalid user code")

        device_info = await _get_device_info(device_code)
        if not device_info:
            raise HTTPException(status_code=404, detail="Invalid user code")

        # Check if already expired
        expires_at = device_info.get("expires_at")
        if expires_at and _utc_ts() > int(expires_at):
            await _delete_device_code(device_code)
            raise HTTPException(status_code=400, detail="Device code has expired")

        # Update authorization status
        if request.action.lower() == "approve":
            device_info["status"] = "authorized"
            device_info["authorized_at"] = _utc_ts()
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
            device_info["denied_at"] = _utc_ts()
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

        await _set_device_info(device_code, device_info)

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
    token_info = await _get_access_token_info(token)
    if not token_info:
        raise HTTPException(status_code=401, detail="Invalid access token")

    expires_at = token_info.get("expires_at")
    if expires_at and _utc_ts() > int(expires_at):
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
