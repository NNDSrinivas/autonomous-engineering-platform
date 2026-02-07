"""
SSO endpoints (OIDC/SAML).

Supports multi-provider OIDC with PKCE and a popup-friendly callback.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.core.auth.sso_config import (
    list_sso_providers,
    get_oidc_provider,
    get_provider,
)
from backend.core.auth.sso_store import create_state, pop_state
from backend.core.jwt_session import SessionJWT


router = APIRouter(prefix="/sso", tags=["sso"])


class SsoProvidersOut(BaseModel):
    providers: list[dict]


@router.get("/providers", response_model=SsoProvidersOut)
def list_providers():
    return {"providers": list_sso_providers()}


class OidcAuthorizeOut(BaseModel):
    authorize_url: str
    state: str


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


async def _resolve_oidc_endpoints(provider: dict) -> dict:
    if provider.get("token_url") and provider.get("userinfo_url"):
        return provider

    issuer = provider.get("issuer")
    if not issuer:
        return provider

    config_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(config_url)
    if resp.status_code != 200:
        return provider

    data = resp.json()
    provider = dict(provider)
    provider["auth_url"] = provider.get("auth_url") or data.get(
        "authorization_endpoint"
    )
    provider["token_url"] = provider.get("token_url") or data.get("token_endpoint")
    provider["userinfo_url"] = provider.get("userinfo_url") or data.get(
        "userinfo_endpoint"
    )
    return provider


@router.get("/oidc/authorize-url", response_model=OidcAuthorizeOut)
async def build_oidc_authorize_url(
    provider: str = Query(..., description="SSO provider id"),
    action: str = Query("signin", pattern="^(signin|signup)$"),
):
    cfg = get_oidc_provider(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="OIDC SSO provider not configured")

    cfg = await _resolve_oidc_endpoints(cfg)
    if not cfg.get("auth_url"):
        raise HTTPException(status_code=500, detail="OIDC auth_url missing")

    verifier, challenge = _pkce_pair()
    state = await create_state(provider, verifier)

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "scope": cfg.get("scope", "openid profile email"),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if action == "signup":
        params["prompt"] = "login"
        params["screen_hint"] = "signup"

    authorize_url = f"{cfg['auth_url']}?{urlencode(params)}"
    return {"authorize_url": authorize_url, "state": state}


class OidcCallbackOut(BaseModel):
    access_token: str
    provider: str
    user: dict


@router.get("/oidc/callback", response_model=OidcCallbackOut | None)
async def oidc_callback(
    code: str = Query(...),
    state: str = Query(...),
    provider: str = Query(...),
    format: str = Query("html", pattern="^(html|json)$"),
):
    stored = await pop_state(state)
    if not stored or stored.get("provider_id") != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    cfg = get_oidc_provider(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail="OIDC SSO provider not configured")

    cfg = await _resolve_oidc_endpoints(cfg)
    if not cfg.get("token_url"):
        raise HTTPException(status_code=500, detail="OIDC token_url missing")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": cfg["redirect_uri"],
        "client_id": cfg["client_id"],
        "code_verifier": stored.get("code_verifier"),
    }
    if cfg.get("client_secret"):
        data["client_secret"] = cfg["client_secret"]

    async with httpx.AsyncClient(timeout=15.0) as http:
        token_resp = await http.post(cfg["token_url"], data=data)
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail=token_resp.text)

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")

    sub = email = name = None
    if id_token:
        try:
            claims = jwt.decode(id_token, options={"verify_signature": False})
            sub = claims.get("sub")
            email = claims.get("email")
            name = claims.get("name")
        except Exception:
            pass

    if not sub and access_token and cfg.get("userinfo_url"):
        async with httpx.AsyncClient(timeout=10.0) as http:
            ui = await http.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if ui.status_code == 200:
            u = ui.json()
            sub = u.get("sub")
            email = u.get("email")
            name = u.get("name")

    if not sub:
        raise HTTPException(status_code=500, detail="Unable to resolve user identity")

    org = email.split("@", 1)[1] if email and "@" in email else "public"
    session_token = SessionJWT.mint(
        sub=sub, email=email, org=org, name=name, roles=["viewer"]
    )

    payload = {
        "type": "navi.sso.success",
        "token": session_token,
        "provider": {"id": provider, "name": cfg.get("name", provider)},
        "user": {"sub": sub, "email": email, "name": name, "org": org},
    }

    if format == "json":
        return {
            "access_token": session_token,
            "provider": provider,
            "user": payload["user"],
        }

    html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>NAVI SSO</title>
    <style>
      body {{ font-family: Arial, sans-serif; background: #0b1120; color: #e5e7eb; display:flex; align-items:center; justify-content:center; height:100vh; }}
      .card {{ background:#111827; border:1px solid rgba(148,163,184,0.2); padding:24px; border-radius:12px; max-width:420px; text-align:center; }}
      .title {{ font-size:16px; font-weight:600; }}
      .hint {{ font-size:12px; color:#94a3b8; margin-top:8px; }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="title">Signed in successfully</div>
      <div class="hint">You can close this window and return to NAVI.</div>
    </div>
    <script>
      (function() {{
        const payload = {json.dumps(payload)};
        if (window.opener) {{
          window.opener.postMessage(payload, "*");
          window.close();
        }}
      }})();
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=html)


class SamlCallbackOut(BaseModel):
    access_token: str
    provider: str
    user: dict


@router.post("/saml/callback", response_model=SamlCallbackOut | None)
async def saml_callback(
    SAMLResponse: str = Query(..., alias="SAMLResponse"),
    RelayState: Optional[str] = Query(None, alias="RelayState"),
    format: str = Query("html", pattern="^(html|json)$"),
):
    """
    Minimal SAML callback handler.

    NOTE: Signature validation is not implemented here. Use a dedicated SAML
    library or validate at the edge before enabling in production.
    """
    provider_id = RelayState or "saml-default"
    provider = get_provider(provider_id)
    if not provider or provider.get("type") != "saml":
        raise HTTPException(status_code=404, detail="SAML provider not configured")

    try:
        import base64
        from xml.etree import ElementTree as ET

        xml_bytes = base64.b64decode(SAMLResponse)
        root = ET.fromstring(xml_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid SAMLResponse") from exc

    ns = {
        "saml2": "urn:oasis:names:tc:SAML:2.0:assertion",
    }
    name_id = root.findtext(".//saml2:Subject/saml2:NameID", default="", namespaces=ns)
    email = root.findtext(
        ".//saml2:Attribute[@Name='email']/saml2:AttributeValue",
        default="",
        namespaces=ns,
    )
    full_name = root.findtext(
        ".//saml2:Attribute[@Name='name']/saml2:AttributeValue",
        default="",
        namespaces=ns,
    )

    if not name_id and not email:
        raise HTTPException(status_code=400, detail="SAML assertion missing subject")

    sub = name_id or email
    org = email.split("@", 1)[1] if email and "@" in email else "public"
    session_token = SessionJWT.mint(
        sub=sub, email=email or None, org=org, name=full_name or None, roles=["viewer"]
    )

    payload = {
        "type": "navi.sso.success",
        "token": session_token,
        "provider": {"id": provider_id, "name": provider.get("name", provider_id)},
        "user": {
            "sub": sub,
            "email": email or None,
            "name": full_name or None,
            "org": org,
        },
    }

    if format == "json":
        return {
            "access_token": session_token,
            "provider": provider_id,
            "user": payload["user"],
        }

    html = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>NAVI SSO</title>
    <style>
      body {{ font-family: Arial, sans-serif; background: #0b1120; color: #e5e7eb; display:flex; align-items:center; justify-content:center; height:100vh; }}
      .card {{ background:#111827; border:1px solid rgba(148,163,184,0.2); padding:24px; border-radius:12px; max-width:420px; text-align:center; }}
      .title {{ font-size:16px; font-weight:600; }}
      .hint {{ font-size:12px; color:#94a3b8; margin-top:8px; }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="title">Signed in successfully</div>
      <div class="hint">You can close this window and return to NAVI.</div>
    </div>
    <script>
      (function() {{
        const payload = {json.dumps(payload)};
        if (window.opener) {{
          window.opener.postMessage(payload, "*");
          window.close();
        }}
      }})();
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=html)
