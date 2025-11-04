from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from .checks import readiness_payload, liveness_payload

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live():
    data = liveness_payload()
    return JSONResponse(data, status_code=200 if data["ok"] else 500)


@router.get("/ready")
def ready():
    data = readiness_payload()
    return JSONResponse(data, status_code=200 if data["ok"] else 503)


@router.get("/startup")
def startup():
    # mirrors ready; some platforms separate the two
    data = readiness_payload()
    return JSONResponse(data, status_code=200 if data["ok"] else 503)
