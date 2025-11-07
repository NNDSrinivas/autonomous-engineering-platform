from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.security import require_role

router = APIRouter(prefix="/api", tags=["me"])


class Me(BaseModel):
    sub: str
    email: str | None
    name: str | None
    org: str | None
    roles: list[str]


@router.get("/me", response_model=Me)
async def me(u=Depends(require_role("viewer"))):
    return Me(
        sub=u.id, email=u.email, name=None, org=u.org_id, roles=u.roles
    )