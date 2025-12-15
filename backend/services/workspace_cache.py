"""
Workspace context cache service.

Caches repository structure, key files, and detected technologies to avoid
redundant scanning on every query.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional
import hashlib

from backend.core.db import get_redis_client

# Cache TTL: 24 hours (can be adjusted based on usage patterns)
WORKSPACE_CACHE_TTL = 24 * 60 * 60  # seconds


def _get_workspace_cache_key(workspace_root: str, user_id: str) -> str:
    """
    Generate a unique cache key for a workspace.

    Uses workspace path hash to ensure consistent keys across sessions.
    """
    path_hash = hashlib.md5(workspace_root.encode()).hexdigest()[:16]
    return f"workspace:context:{user_id}:{path_hash}"


async def get_cached_workspace_context(
    workspace_root: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached workspace context if available and not stale.

    Args:
        workspace_root: Absolute path to workspace
        user_id: User identifier

    Returns:
        Cached context dict or None if not found/stale
    """
    try:
        redis = get_redis_client()
        if not redis:
            return None

        cache_key = _get_workspace_cache_key(workspace_root, user_id)
        cached_data = redis.get(cache_key)

        if not cached_data:
            return None

        context = json.loads(cached_data)

        # Check if cache is still valid (redundant with TTL but useful for manual invalidation)
        cached_at = context.get("cached_at", 0)
        age_seconds = time.time() - cached_at

        if age_seconds > WORKSPACE_CACHE_TTL:
            # Expired, remove from cache
            redis.delete(cache_key)
            return None

        return context

    except Exception:
        # If cache retrieval fails, fall back to fresh scan
        return None


async def cache_workspace_context(
    workspace_root: str,
    user_id: str,
    context: Dict[str, Any],
) -> bool:
    """
    Cache workspace context for future queries.

    Args:
        workspace_root: Absolute path to workspace
        user_id: User identifier
        context: Context dict to cache (repo structure, key files, etc.)

    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis = get_redis_client()
        if not redis:
            return False

        cache_key = _get_workspace_cache_key(workspace_root, user_id)

        # Add metadata
        cache_data = {
            **context,
            "cached_at": time.time(),
            "workspace_root": workspace_root,
            "user_id": user_id,
        }

        redis.setex(
            cache_key,
            WORKSPACE_CACHE_TTL,
            json.dumps(cache_data),
        )

        return True

    except Exception:
        # Cache write failure is non-critical
        return False


async def invalidate_workspace_cache(
    workspace_root: str,
    user_id: str,
) -> bool:
    """
    Manually invalidate workspace cache (e.g., after file changes).

    Args:
        workspace_root: Absolute path to workspace
        user_id: User identifier

    Returns:
        True if invalidated successfully
    """
    try:
        redis = get_redis_client()
        if not redis:
            return False

        cache_key = _get_workspace_cache_key(workspace_root, user_id)
        redis.delete(cache_key)

        return True

    except Exception:
        return False


def extract_workspace_context_from_tool_results(
    repo_inspect_result: Dict[str, Any],
    key_files_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract cacheable context from tool execution results.

    Args:
        repo_inspect_result: Result from repo.inspect tool
        key_files_result: Result from code.read_files tool

    Returns:
        Structured context ready for caching
    """
    files = repo_inspect_result.get("files", [])
    key_files = repo_inspect_result.get("key_files", [])
    workspace_root = repo_inspect_result.get("workspace_root", "")

    # Extract read file contents
    read_files = key_files_result.get("files", [])
    file_contents = {}
    for file_data in read_files:
        if "content" in file_data:
            file_contents[file_data["path"]] = file_data["content"]

    # Detect technologies from file names and contents
    technologies = detect_technologies(files, file_contents)

    return {
        "files": files[:200],  # Limit to first 200 for cache size
        "key_files": key_files,
        "file_contents": file_contents,
        "technologies": technologies,
        "workspace_root": workspace_root,
        "file_count": len(files),
    }


def detect_technologies(files: list[str], file_contents: Dict[str, str]) -> list[str]:
    """
    Detect technologies/frameworks used in the workspace.

    Args:
        files: List of relative file paths
        file_contents: Dict of file path -> content for key files

    Returns:
        List of detected technology names
    """
    techs = set()

    # File-based detection
    for file_path in files:
        file_lower = file_path.lower()

        if "package.json" in file_lower:
            techs.add("Node.js/JavaScript")
        if (
            "pyproject.toml" in file_lower
            or "requirements.txt" in file_lower
            or "setup.py" in file_lower
        ):
            techs.add("Python")
        if "pom.xml" in file_lower or "build.gradle" in file_lower:
            techs.add("Java")
        if "Cargo.toml" in file_lower:
            techs.add("Rust")
        if "go.mod" in file_lower:
            techs.add("Go")
        if "Dockerfile" in file_path:
            techs.add("Docker")
        if "docker-compose" in file_lower:
            techs.add("Docker Compose")
        if ".github/workflows" in file_path:
            techs.add("GitHub Actions")
        if file_path.endswith(".tsx") or file_path.endswith(".jsx"):
            techs.add("React")
        if file_path.endswith(".vue"):
            techs.add("Vue")
        if "angular.json" in file_lower:
            techs.add("Angular")

    # Content-based detection
    for path, content in file_contents.items():
        content_lower = content.lower()

        if "package.json" in path:
            if '"react"' in content_lower:
                techs.add("React")
            if '"vue"' in content_lower:
                techs.add("Vue")
            if '"angular"' in content_lower:
                techs.add("Angular")
            if '"next"' in content_lower:
                techs.add("Next.js")
            if '"express"' in content_lower:
                techs.add("Express")
            if '"fastify"' in content_lower:
                techs.add("Fastify")

        if "requirements.txt" in path or "pyproject.toml" in path:
            if "django" in content_lower:
                techs.add("Django")
            if "flask" in content_lower:
                techs.add("Flask")
            if "fastapi" in content_lower:
                techs.add("FastAPI")
            if "sqlalchemy" in content_lower:
                techs.add("SQLAlchemy")

        if "pom.xml" in path:
            if "spring" in content_lower:
                techs.add("Spring")
            if "hibernate" in content_lower:
                techs.add("Hibernate")

    return sorted(list(techs))
