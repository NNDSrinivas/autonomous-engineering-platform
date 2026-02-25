from __future__ import annotations
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auth0 configuration with fallback for CI environments
# Normalize domain: strip trailing slashes to prevent double-slash in URLs
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-nr76km00xa820k15.us.auth0.com").strip().rstrip("/")
# Separate domain for OAuth device flow (custom domains often don't support device endpoints)
AUTH0_OAUTH_DOMAIN = os.getenv("AUTH0_OAUTH_DOMAIN", AUTH0_DOMAIN).strip().rstrip("/")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "").strip()
AUTH0_DEVICE_CLIENT_ID = os.getenv("AUTH0_DEVICE_CLIENT_ID", AUTH0_CLIENT_ID).strip()  # Fallback to regular client ID if not set
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "").strip()
# ✅ IMPORTANT: issuer must match the token "iss" exactly (includes trailing slash)
# Normalize issuer: ensure exactly one trailing slash
_issuer_from_env = os.getenv("AUTH0_ISSUER")

# Validate that AUTH0_ISSUER is not empty/whitespace if explicitly set
if _issuer_from_env is not None and not _issuer_from_env.strip():
    raise ValueError(
        "AUTH0_ISSUER is set but empty/whitespace. "
        "Remove the environment variable or set a valid https:// URL."
    )

if _issuer_from_env:
    AUTH0_ISSUER = _issuer_from_env.strip().rstrip("/") + "/"
else:
    AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"

# OAuth device endpoints use tenant domain (custom domains may not support these)
DEVICE_CODE_URL = f"https://{AUTH0_OAUTH_DOMAIN}/oauth/device/code"
TOKEN_URL = f"https://{AUTH0_OAUTH_DOMAIN}/oauth/token"
USERINFO_URL = f"https://{AUTH0_OAUTH_DOMAIN}/userinfo"
# JWKS uses the issuer domain (custom domain) for JWT validation
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
