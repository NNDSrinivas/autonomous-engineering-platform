from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from ..core.config import settings
from ..core.logging import setup_logging
from ..core.middleware import RequestIDMiddleware, RateLimitMiddleware, AuditMiddleware
from ..core.metrics import router as metrics_router

logger = setup_logging()
app = FastAPI(title=f"{settings.app_name} - Core API")

app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestIDMiddleware, service_name="core")
app.add_middleware(RateLimitMiddleware, service_name="core", rpm=60)
app.add_middleware(AuditMiddleware, service_name="core")

@app.get("/health")
def health():
    return {"status": "ok", "service": "core", "time": datetime.utcnow().isoformat()}

@app.get("/version")
def version():
    return {"name": settings.app_name, "env": settings.app_env, "version": "0.1.0"}

# Prometheus
app.include_router(metrics_router)

# TODO: Feature endpoints (meetings/jira/github) land here.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
