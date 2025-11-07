from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import jwt

from backend.core.auth0 import (
    DEVICE_CODE_URL,
    TOKEN_URL,
    USERINFO_URL,
    AUTH0_CLIENT_ID,
    AUTH0_AUDIENCE,
)
from backend.core.jwt_session import SessionJWT

router = APIRouter(prefix="/oauth/device", tags=["oauth-device"])


class StartOut(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    interval: int | None = None


@router.post("/start", response_model=StartOut)
async def start():
    async with httpx.AsyncClient(timeout=15.0) as http:
        r = await http.post(
            DEVICE_CODE_URL,
            data={
                "client_id": AUTH0_CLIENT_ID,
                "audience": AUTH0_AUDIENCE,
                "scope": "openid profile email offline_access",
            },
        )
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    j = r.json()
    return StartOut(
        device_code=j["device_code"],
        user_code=j["user_code"],
        verification_uri=j["verification_uri"],
        verification_uri_complete=j.get("verification_uri_complete"),
        interval=j.get("interval"),
    )


class PollIn(BaseModel):
    device_code: str


class TokenOut(BaseModel):
    access_token: str  # AEP session token
    expires_in: int
    token_type: str = "Bearer"


@router.post("/poll", response_model=TokenOut)
async def poll(body: PollIn):
    async with httpx.AsyncClient(timeout=15.0) as http:
        r = await http.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": body.device_code,
                "client_id": AUTH0_CLIENT_ID,
            },
        )
    # 400 during pending/slow_down/expired — surface as 428 to keep polling client-side
    if r.status_code == 400:
        raise HTTPException(428, r.text)
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    j = r.json()

    # Prefer id_token for profile; otherwise /userinfo
    sub = email = name = None
    if "id_token" in j:
        claims = jwt.decode(j["id_token"], options={"verify_signature": False})
        sub, email, name = claims.get("sub"), claims.get("email"), claims.get("name")
    if not sub:
        async with httpx.AsyncClient(timeout=10.0) as http:
            ui = await http.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {j['access_token']}"}
            )
        if ui.status_code == 200:
            u = ui.json()
            sub, email, name = u.get("sub"), u.get("email"), u.get("name")
    if not sub:
        raise HTTPException(500, "Unable to resolve user identity")

    org = email.split("@", 1)[1] if email and "@" in email else "public"
    aep_token = SessionJWT.mint(
        sub=sub, email=email, org=org, name=name, roles=["viewer"]
    )
    return TokenOut(access_token=aep_token, expires_in=3600)
