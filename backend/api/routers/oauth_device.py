"""
OAuth Device Code Flow for VS Code Extension Authentication

Provides secure authentication without client secrets using OAuth 2.0 device code flow.
This allows the VS Code extension to authenticate users through their browser.
"""

import os
import random
import string
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import secrets
from datetime import datetime, timedelta

# Production safety check
if os.environ.get("OAUTH_DEVICE_USE_IN_MEMORY_STORE", "false").lower() != "true":
    raise RuntimeError(
        "In-memory device code and access token store is NOT suitable for production. "
        "Set OAUTH_DEVICE_USE_IN_MEMORY_STORE=true in your environment to acknowledge you are running in development/testing mode. "
        "Replace with Redis or persistent database before production deployment."
    )

router = APIRouter(prefix="/oauth", tags=["OAuth Device Code"])

# TODO: Replace in-memory store with Redis or a persistent database before deploying to production.
#       This code should not be used in production environments.
#       Set OAUTH_DEVICE_USE_IN_MEMORY_STORE=true in your environment ONLY for development/testing.
_device_codes: Dict[str, Dict[str, Any]] = {}
_access_tokens: Dict[str, Dict[str, Any]] = {}


class DeviceCodeStartRequest(BaseModel):
    client_id: Optional[str] = Field(
        default="aep-vscode-extension", description="Client identifier"
    )
    scope: Optional[str] = Field(default="read write", description="Requested scopes")


class DeviceCodeStartResponse(BaseModel):
    device_code: str = Field(description="Device verification code")
    user_code: str = Field(description="User verification code to display")
    verification_uri: str = Field(description="URI for user to visit")
    verification_uri_complete: Optional[str] = Field(
        description="Complete URI with user_code"
    )
    expires_in: int = Field(description="Device code expiration in seconds")
    interval: int = Field(description="Polling interval in seconds")


class DeviceCodePollRequest(BaseModel):
    device_code: str = Field(description="Device code from start request")
    client_id: Optional[str] = Field(default="aep-vscode-extension")


class DeviceCodeTokenResponse(BaseModel):
    access_token: str = Field(description="Access token for API calls")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(description="Token expiration in seconds")
    scope: Optional[str] = Field(description="Granted scopes")


class DeviceCodeErrorResponse(BaseModel):
    error: str = Field(description="Error code")
    error_description: Optional[str] = Field(
        description="Human-readable error description"
    )


@router.post("/device/start", response_model=DeviceCodeStartResponse)
async def start_device_code_flow(request: DeviceCodeStartRequest):
    """
    Initiate OAuth device code flow for VS Code extension authentication.

    Returns device code and user code for browser-based authentication.
    """
    try:
        # Generate device code and user code
        device_code = secrets.token_urlsafe(32)
        user_code = _generate_user_code()

        # Store device code with metadata
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # 10 minute expiry
        _device_codes[device_code] = {
            "user_code": user_code,
            "client_id": request.client_id,
            "scope": request.scope,
            "expires_at": expires_at,
            "status": "pending",  # pending, authorized, denied
            "created_at": datetime.utcnow(),
        }

        # Base verification URI (would be your actual auth page)
        base_uri = "https://auth.aep.dev/device"  # Replace with actual URI
        verification_uri = base_uri
        verification_uri_complete = f"{base_uri}?user_code={user_code}"

        return DeviceCodeStartResponse(
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            verification_uri_complete=verification_uri_complete,
            expires_in=600,  # 10 minutes
            interval=5,  # Poll every 5 seconds
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start device code flow: {str(e)}"
        )


@router.post("/device/poll", response_model=DeviceCodeTokenResponse)
async def poll_device_code(request: DeviceCodePollRequest):
    """
    Poll for device code authorization completion.

    Returns access token when user completes browser authentication.
    """
    try:
        device_code = request.device_code

        if device_code not in _device_codes:
            raise HTTPException(
                status_code=400,
                detail="invalid_request",
                headers={"Content-Type": "application/json"},
            )

        device_info = _device_codes[device_code]

        # Check if expired
        if datetime.utcnow() > device_info["expires_at"]:
            del _device_codes[device_code]
            raise HTTPException(
                status_code=400,
                detail="expired_token",
                headers={"Content-Type": "application/json"},
            )

        # Check authorization status
        if device_info["status"] == "pending":
            # For development/testing: Auto-approve after initial delay to simulate user approval
            # In production, this should be replaced with proper web-based user approval
            current_time = datetime.utcnow()
            time_since_creation = (
                current_time - device_info["created_at"]
            ).total_seconds()

            # Auto-approve after 30 seconds ONLY if BOTH explicit development flags are set
            if (
                os.environ.get("OAUTH_DEVICE_AUTO_APPROVE", "false").lower() == "true"
                and os.environ.get("OAUTH_DEVICE_USE_IN_MEMORY_STORE", "false").lower()
                == "true"
                and time_since_creation > 30
            ):
                # SECURITY WARNING: Auto-approving device code in development mode
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "🚨 SECURITY WARNING: Auto-approving device code '%s' after %d seconds. "
                    "This is ONLY for development! Never enable auto-approval in production!",
                    device_code[:8] + "...",
                    int(time_since_creation)
                )
                device_info["status"] = "authorized"
                device_info["authorized_at"] = current_time
                device_info["user_id"] = "dev-user"  # In production, use actual user ID
            else:
                raise HTTPException(
                    status_code=400,
                    detail="authorization_pending",
                    headers={"Content-Type": "application/json"},
                )

        elif device_info["status"] == "denied":
            del _device_codes[device_code]
            raise HTTPException(
                status_code=400,
                detail="access_denied",
                headers={"Content-Type": "application/json"},
            )

        # Generate access token
        if device_info["status"] == "authorized":
            access_token = secrets.token_urlsafe(32)
            token_expires_at = datetime.utcnow() + timedelta(hours=24)  # 24 hour token

            # Store access token
            _access_tokens[access_token] = {
                "client_id": device_info["client_id"],
                "scope": device_info["scope"],
                "expires_at": token_expires_at,
                "user_id": "demo-user",  # In production, get from authorization
                "created_at": datetime.utcnow(),
            }

            # Clean up device code
            del _device_codes[device_code]

            return DeviceCodeTokenResponse(
                access_token=access_token,
                token_type="Bearer",
                expires_in=86400,  # 24 hours
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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to poll device code: {str(e)}"
        )


class DeviceAuthorizationRequest(BaseModel):
    user_code: str = Field(description="User code to authorize")
    action: str = Field(description="Authorization action: 'approve' or 'deny'")


class DeviceAuthorizationResponse(BaseModel):
    message: str = Field(description="Authorization result message")
    user_code: str = Field(description="User code that was authorized")


@router.post("/device/authorize", response_model=DeviceAuthorizationResponse)
async def authorize_device_code(request: DeviceAuthorizationRequest):
    """
    Authorize or deny a device code by user code.

    This endpoint allows users to approve or deny device authorization requests
    through a web interface or API call.
    """
    try:
        # Find device code by user code
        device_code = None
        for dc, info in _device_codes.items():
            if info["user_code"] == request.user_code:
                device_code = dc
                break

        if not device_code:
            raise HTTPException(status_code=404, detail="Invalid user code")

        device_info = _device_codes[device_code]

        # Check if already expired
        if datetime.utcnow() > device_info["expires_at"]:
            del _device_codes[device_code]
            raise HTTPException(status_code=400, detail="Device code has expired")

        # Update authorization status
        if request.action.lower() == "approve":
            device_info["status"] = "authorized"
            device_info["authorized_at"] = datetime.utcnow()
            message = f"Device with user code {request.user_code} has been authorized"
        elif request.action.lower() == "deny":
            device_info["status"] = "denied"
            device_info["denied_at"] = datetime.utcnow()
            message = f"Device with user code {request.user_code} has been denied"
        else:
            raise HTTPException(
                status_code=400, detail="Invalid action. Must be 'approve' or 'deny'"
            )

        return DeviceAuthorizationResponse(message=message, user_code=request.user_code)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to authorize device: {str(e)}"
        )


def _generate_user_code() -> str:
    """Generate a human-readable user code."""
    # Generate 8-character code with letters and numbers
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace("0", "").replace("O", "").replace("1", "").replace("I", "")

    return "".join(random.choice(chars) for _ in range(8))


def validate_access_token(token: str) -> Dict[str, Any]:
    """Validate access token and return user info."""
    if token not in _access_tokens:
        raise HTTPException(status_code=401, detail="Invalid access token")

    token_info = _access_tokens[token]

    if datetime.utcnow() > token_info["expires_at"]:
        del _access_tokens[token]
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
    token_info = validate_access_token(token)

    return {
        "user_id": token_info["user_id"],
        "client_id": token_info["client_id"],
        "scope": token_info["scope"],
    }
