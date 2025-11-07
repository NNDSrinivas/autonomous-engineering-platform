from __future__ import annotations
import os
import time
import jwt
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ALG = os.getenv("AEP_JWT_ALG", "HS256")
SECRET = os.getenv("AEP_JWT_SECRET", "dev-test-secret-for-ci")
ISS = os.getenv("AEP_JWT_ISSUER", "aep")
TTL = int(os.getenv("AEP_JWT_TTL_SECONDS", "3600"))


class SessionJWT:
    @staticmethod
    def mint(
        sub: str,
        email: str | None,
        org: str | None,
        name: str | None,
        roles: list[str] | None = None,
    ) -> str:
        now = int(time.time())
        claims: Dict[str, Any] = {
            "iss": ISS,
            "sub": sub,
            "iat": now,
            "exp": now + TTL,
            "email": email,
            "name": name,
            "org": org,
            "roles": roles or ["viewer"],
        }
        return jwt.encode(claims, SECRET, algorithm=ALG)

    @staticmethod
    def decode(token: str) -> dict:
        return jwt.decode(
            token, SECRET, algorithms=[ALG], options={"require": ["exp", "sub"]}
        )
