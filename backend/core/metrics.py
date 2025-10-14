from fastapi import APIRouter
from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import generate_latest

router = APIRouter()


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
