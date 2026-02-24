from __future__ import annotations
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auth0 configuration with fallback for CI environments
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-nr76km00xa820k15.us.auth0.com").strip()
# Separate domain for OAuth device flow (custom domains often don't support device endpoints)
AUTH0_OAUTH_DOMAIN = os.getenv("AUTH0_OAUTH_DOMAIN", AUTH0_DOMAIN).strip()
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "").strip()
AUTH0_DEVICE_CLIENT_ID = os.getenv("AUTH0_DEVICE_CLIENT_ID", AUTH0_CLIENT_ID).strip()  # Fallback to regular client ID if not set
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "").strip()
# ✅ IMPORTANT: issuer must match the token "iss" exactly (includes trailing slash)
AUTH0_ISSUER = os.getenv("AUTH0_ISSUER", f"https://{AUTH0_DOMAIN}/")

# OAuth device endpoints use tenant domain (custom domains may not support these)
DEVICE_CODE_URL = f"https://{AUTH0_OAUTH_DOMAIN}/oauth/device/code"
TOKEN_URL = f"https://{AUTH0_OAUTH_DOMAIN}/oauth/token"
USERINFO_URL = f"https://{AUTH0_OAUTH_DOMAIN}/userinfo"
# JWKS uses the issuer domain (custom domain) for JWT validation
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
