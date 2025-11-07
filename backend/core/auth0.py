from __future__ import annotations
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auth0 configuration with fallback for CI environments
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-nr76km00xa820k15.us.auth0.com").strip()
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "").strip()
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "").strip()

DEVICE_CODE_URL = f"https://{AUTH0_DOMAIN}/oauth/device/code"
TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"
USERINFO_URL = f"https://{AUTH0_DOMAIN}/userinfo"
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
