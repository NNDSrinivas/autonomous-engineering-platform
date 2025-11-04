"""
Repo context gathering for AI code generation.
Safely reads files and discovers neighbors for prompt composition.
Uses a secure path allowlist system to satisfy CodeQL requirements.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Set
import logging
import os
import stat

logger = logging.getLogger(__name__)

# Repo root resolution - handles both dev and container environments
try:
    REPO_ROOT = Path(".").resolve()
except Exception:
    REPO_ROOT = Path("/app").resolve()  # Fallback for containerized environments

# Pre-computed secure repository root for allowlist checking
SECURE_REPO_ROOT = str(REPO_ROOT.resolve())


def _create_secure_path_allowlist() -> Set[str]:
    """
    Create a pre-computed allowlist of all valid paths in the repository.
    This approach eliminates tainted path usage by using only pre-enumerated paths.
    """
    allowlist = set()
    try:
        # Use os.walk to enumerate all valid paths
        for root, dirs, files in os.walk(SECURE_REPO_ROOT):
            # Filter out hidden directories and common exclusions
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in {"__pycache__", "node_modules", ".git"}
            ]

            for file in files:
                if not file.startswith("."):
                    full_path = os.path.join(root, file)
                    try:
                        # Only include regular files, not symlinks
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            rel_path = os.path.relpath(full_path, SECURE_REPO_ROOT)
                            allowlist.add(rel_path)
                    except (OSError, ValueError):
                        continue
    except Exception:
        pass
    return allowlist


# Pre-computed allowlist of valid repository paths
_PATH_ALLOWLIST = _create_secure_path_allowlist()


def is_path_in_allowlist(rel_path: str) -> bool:
    """
    Check if a relative path is in the pre-computed allowlist.
    This avoids any filesystem operations on user-controlled data.
    """
    try:
        normalized = os.path.normpath(rel_path)
        return normalized in _PATH_ALLOWLIST
    except Exception:
        return False


def get_secure_absolute_path(rel_path: str) -> str | None:
    """
    Return secure absolute path only if the relative path is in the allowlist.
    Uses only pre-validated paths to avoid CodeQL taint issues.
    """
    if not is_path_in_allowlist(rel_path):
        return None

    try:
        return os.path.join(SECURE_REPO_ROOT, rel_path)
    except Exception:
        return None


def safe_repo_path(rel_path: str) -> str | None:
    """
    Return resolved path string if and only if rel_path is in the pre-computed allowlist.
    Uses allowlist-based validation to avoid CodeQL taint tracking issues.
    """
    try:
        # Use allowlist-based validation instead of filesystem operations
        if not is_path_in_allowlist(rel_path):
            logger.warning(f"Path not in allowlist: {rel_path}")
            return None

        return get_secure_absolute_path(rel_path)
    except Exception as e:
        logger.warning(f"Exception while resolving path {rel_path}: {e}")
        return None


def read_text_safe(path_str: str, max_bytes: int = 200_000) -> str:
    """
    Safely read text file using allowlist-based validation.
    Only reads files that are in the pre-computed allowlist.

    Args:
        path_str: Relative path to file within repo root
        max_bytes: Maximum bytes to read (default 200KB)

    Returns:
        File content as string, or empty string on error
    """
    try:
        # Use allowlist-based validation
        validated_path = safe_repo_path(path_str)
        if validated_path is None:
            logger.warning(f"read_text_safe: Path failed validation: {path_str}")
            return ""

        # Use only the allowlist-validated path for filesystem operations
        # Since the path came from allowlist, it's already verified as safe
        with open(validated_path, "rb") as f:
            data = f.read(max_bytes)

        # Check file size using the same validated path
        try:
            file_size = os.path.getsize(validated_path)
            if file_size > max_bytes:
                logger.warning(f"File {path_str} exceeds {max_bytes} bytes, truncating")
        except OSError:
            pass  # File size check is optional

        return data.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {path_str}: {e}")
        return ""


def list_neighbors(file_path: str) -> List[str]:
    """
    List neighboring files in the same directory using allowlist-based approach.
    Only returns files that are in the pre-computed allowlist.

    Args:
        file_path: Relative path from repo root

    Returns:
        List of relative file paths (up to 40 neighbors)
    """
    try:
        # Validate the input path using allowlist
        if not is_path_in_allowlist(file_path):
            logger.warning(f"File path not in allowlist: {file_path}")
            return []

        # Get the directory of the file
        parent_dir = os.path.dirname(file_path)

        # Find all allowlisted files in the same directory
        neighbors = []
        for allowed_path in _PATH_ALLOWLIST:
            try:
                # Check if this allowed path is in the same directory
                allowed_dir = os.path.dirname(allowed_path)
                if allowed_dir == parent_dir and allowed_path != file_path:
                    neighbors.append(allowed_path)
            except Exception:
                continue

        return neighbors[:40]  # Limit to prevent token overflow
    except Exception as e:
        logger.warning(f"Failed to list neighbors for {file_path}: {e}")
        return []


def repo_snapshot(files: List[str], max_files: int = 50) -> Dict[str, str]:
    """
    Generate a snapshot of multiple repository files using allowlist validation.
    Only reads files that are in the pre-computed allowlist.

    Args:
        files: List of relative file paths from repo root
        max_files: Maximum number of files to include

    Returns:
        Dict mapping file paths to their content
    """
    snapshot = {}
    processed = 0

    for file_path in files[:max_files]:
        try:
            # Only read files that are in the allowlist
            if is_path_in_allowlist(file_path):
                content = read_text_safe(file_path)
                if content:  # Only include files with content
                    snapshot[file_path] = content
                    processed += 1
                    if processed >= max_files:
                        break
            else:
                logger.warning(f"File not in allowlist, skipping: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            continue

    return snapshot
