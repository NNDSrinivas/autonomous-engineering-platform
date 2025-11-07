from __future__ import annotations
import os

AUTH0_DOMAIN = os.environ["AUTH0_DOMAIN"].strip()
AUTH0_CLIENT_ID = os.environ["AUTH0_CLIENT_ID"].strip()
AUTH0_AUDIENCE = os.environ["AUTH0_AUDIENCE"].strip()

DEVICE_CODE_URL = f"https://{AUTH0_DOMAIN}/oauth/device/code"
TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"
USERINFO_URL = f"https://{AUTH0_DOMAIN}/userinfo"
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"