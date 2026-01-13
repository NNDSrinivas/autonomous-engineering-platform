#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

"""Debug version of main.py - loads imports step by step to find the bottleneck"""

print("🔍 IMPORT DEBUG: Starting imports...")
print("✅ Future imports loaded")

from contextlib import asynccontextmanager

print("✅ Standard library imports loaded")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

print("✅ FastAPI and basic dependencies loaded")

# ---- Observability imports ----

print("✅ Observability logging loaded")

# Try to import tracing module, provide no-op implementations if not available
try:
    from backend.core.obs.obs_tracing import init_tracing, instrument_fastapi_app  # type: ignore[import]

    print("✅ Observability tracing loaded")
except (ImportError, ModuleNotFoundError):

    def init_tracing() -> None:  # type: ignore[unused-ignore]
        """Fallback no-op if tracing module is absent."""
        pass

    def instrument_fastapi_app(app: FastAPI) -> None:  # type: ignore[unused-ignore]
        """Fallback no-op if tracing module is absent."""
        pass

    print("⚠️ Observability tracing not available - using fallback")

from backend.core.health.router import router as health_router
from backend.core.settings import settings

print("✅ Core backend modules loaded")

# NOW TEST THE HEAVY IMPORTS ONE BY ONE
print("🔍 IMPORT DEBUG: Testing router imports...")

try:
    print("✅ Tasks router loaded")
except Exception as e:
    print(f"❌ Tasks router failed: {e}")

try:
    print("✅ Plan router loaded")
except Exception as e:
    print(f"❌ Plan router failed: {e}")

try:
    print("✅ Deliver router loaded")
except Exception as e:
    print(f"❌ Deliver router failed: {e}")

try:
    print("✅ Policy router loaded")
except Exception as e:
    print(f"❌ Policy router failed: {e}")

try:
    print("✅ Audit router loaded")
except Exception as e:
    print(f"❌ Audit router failed: {e}")

try:
    print("✅ Change router loaded")
except Exception as e:
    print(f"❌ Change router failed: {e}")

try:
    print("✅ Chat router loaded")
except Exception as e:
    print(f"❌ Chat router failed: {e}")

print("🔍 IMPORT DEBUG: Testing NAVI imports (this might hang)...")

try:
    print("✅ NAVI router loaded")
except Exception as e:
    print(f"❌ NAVI router failed: {e}")

print("🔍 IMPORT DEBUG: All imports complete!")


# Continue with minimal app for now
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⚡ FAST START MODE - Skipping slow initialization")
    yield


app = FastAPI(title=f"{settings.APP_NAME} - Debug Version", lifespan=lifespan)

# Basic middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3007", "http://127.0.0.1:3007"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add health endpoint
app.include_router(health_router, tags=["health"])


# Add basic chat endpoint for testing
@app.post("/api/navi/chat")
async def navi_chat():
    return {"message": "NAVI backend is working!", "status": "debug_mode"}


print("🚀 DEBUG BACKEND: Ready to start!")
