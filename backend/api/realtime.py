from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from ..core.config import settings
from ..core.logging import setup_logging
from ..core.middleware import RequestIDMiddleware, RateLimitMiddleware, AuditMiddleware
from ..core.metrics import router as metrics_router

logger = setup_logging()
app = FastAPI(title=f"{settings.app_name} - Realtime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware, service_name="realtime")
app.add_middleware(
    RateLimitMiddleware, service_name="realtime", rpm=120
)  # a bit higher
app.add_middleware(AuditMiddleware, service_name="realtime")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "realtime",
        "time": datetime.utcnow().isoformat(),
    }


@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


app.include_router(metrics_router)

# TODO: /api/sessions, /captions, /answers/stream coming in Feature 1 & 4.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.realtime_port)
