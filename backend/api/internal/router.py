from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import os
import subprocess
import platform
from datetime import datetime, timezone
from urllib.parse import urlparse

router = APIRouter(prefix="/internal", tags=["internal"])


class SystemInfo(BaseModel):
    """System and deployment information"""

    service_name: str
    environment: str
    version: str
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    build_timestamp: Optional[str] = None
    python_version: str
    platform: str
    deployment_target: str
    backend_public_url: Optional[str] = None


def get_git_info() -> tuple[Optional[str], Optional[str]]:
    """Get current git commit hash and branch"""
    try:
        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        commit_hash = (
            commit_result.stdout.strip()[:8] if commit_result.returncode == 0 else None
        )

        # Get branch name
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch_name = (
            branch_result.stdout.strip() if branch_result.returncode == 0 else None
        )

        return commit_hash, branch_name
    except Exception:
        return None, None


@router.get("/info", response_model=SystemInfo)
async def get_system_info():
    """
    Get system and deployment information.
    Useful for verifying which version is deployed and environment details.
    """
    git_commit, git_branch = get_git_info()

    # Determine deployment target based on environment
    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8787")

    parsed_url = urlparse(backend_url)
    host = parsed_url.hostname or ""
    if host == "api.navralabs.com":
        deployment_target = "production"
    elif host in ("localhost", "127.0.0.1"):
        deployment_target = "local"
    else:
        deployment_target = "staging"

    return SystemInfo(
        service_name="autonomous-engineering-platform",
        environment=os.getenv("APP_ENV", "development"),
        version="1.0.0",  # TODO: Read from package.json or version file
        git_commit=git_commit,
        git_branch=git_branch,
        build_timestamp=os.getenv("BUILD_TIMESTAMP", datetime.now(timezone.utc).isoformat()),
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.release()}",
        deployment_target=deployment_target,
        backend_public_url=backend_url,
    )


@router.get("/health/detailed")
async def get_detailed_health():
    """
    Detailed health check with dependency status.
    More comprehensive than the basic /health endpoint.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }

    # Check database connectivity
    try:
        from ...core.db import get_db
        from sqlalchemy import text

        db = next(get_db())
        # Simple query to test connection
        db.execute(text("SELECT 1"))
        db.close()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Connected",
        }
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "message": str(e)}
        health_status["status"] = "degraded"

    # Check OpenAI API key presence (not making actual call to avoid cost)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(openai_key) > 10:
        health_status["checks"]["openai"] = {
            "status": "configured",
            "message": "API key present",
        }
    else:
        health_status["checks"]["openai"] = {
            "status": "missing",
            "message": "API key not configured",
        }

    # Check environment variables
    required_vars = ["BACKEND_PUBLIC_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        health_status["checks"]["environment"] = {
            "status": "incomplete",
            "message": f"Missing: {', '.join(missing_vars)}",
        }
    else:
        health_status["checks"]["environment"] = {
            "status": "complete",
            "message": "All required vars set",
        }

    return health_status


@router.get("/version")
async def get_version():
    """Simple version endpoint"""
    git_commit, git_branch = get_git_info()
    return {
        "version": "1.0.0",
        "commit": git_commit,
        "branch": git_branch,
        "environment": os.getenv("APP_ENV", "development"),
    }
