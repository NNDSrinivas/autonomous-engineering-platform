from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

# Here we only expose a header when upstream circuits are open via context; attach if you route via circuit.
class ResilienceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        try:
            resp = await call_next(request)
            return resp
        except RuntimeError as e:
            # If a handler chooses to bubble up "circuit-open", standardize response
            if "circuit-open" in str(e):
                return JSONResponse({"detail":"upstream temporarily unavailable"}, status_code=503, headers={"X-Circuit":"open"})
            raise