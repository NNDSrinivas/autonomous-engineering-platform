"""
Repo context gathering for AI code generation.
Safely reads files and discovers neighbors for prompt composition.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import logging
import os

logger = logging.getLogger(__name__)

# Repo root resolution - handles both dev and container environments
try:
    REPO_ROOT = Path(".").resolve()
except Exception:
    REPO_ROOT = Path("/app").resolve()  # Fallback for containerized environments


def safe_repo_path(rel_path: str) -> Path | None:
    """
    Return resolved path if and only if rel_path is safely inside the REPO_ROOT.
    Returns None if the path is absolute, escapes, or invalid.
    """
    try:
        # Reject absolute paths (should be relative from repo root)
        rel_path_obj = Path(rel_path)
        if rel_path_obj.is_absolute():
            logger.warning(f"Rejected absolute path: {rel_path}")
            return None

        # Normalize to prevent .. traversal
        norm_rel = os.path.normpath(rel_path)
        if (
            norm_rel.startswith("/")
            or norm_rel.startswith("\\")
            or norm_rel.startswith("..")
        ):
            logger.warning(f"Path {rel_path} is not a valid repository-relative file")
            return None

        full = (REPO_ROOT / norm_rel).resolve()

        # Ensure resolved path is within REPO_ROOT using relative_to
        try:
            full.relative_to(REPO_ROOT)
        except ValueError:
            logger.warning(f"Rejected path outside repo: {rel_path} resolved to {full}")
            return None

        return full
    except Exception as e:
        logger.warning(f"Exception while resolving path {rel_path}: {e}")
        return None


def read_text_safe(p: Path, max_bytes: int = 200_000) -> str:
    """
    Safely read text file with size limit and error handling.

    Args:
        p: Path to file
        max_bytes: Maximum bytes to read (default 200KB)

    Returns:
        File content as string, or empty string on error
    """
    try:
        # Ensure path is within repo root
        try:
            p.resolve().relative_to(REPO_ROOT)
        except ValueError:
            logger.warning(f"Attempted to read file outside repo root: {p}")
            return ""

        if not p.exists() or not p.is_file():
            return ""
        data = p.read_bytes()
        if len(data) > max_bytes:
            logger.warning(f"File {p} exceeds {max_bytes} bytes, truncating")
        return data[:max_bytes].decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {p}: {e}")
        return ""


def list_neighbors(file_path: str, radius: int = 1) -> List[str]:
    """
    List neighboring files in the same directory.

    Args:
        file_path: Relative path from repo root
        radius: Not used currently, reserved for future expansion

    Returns:
        List of relative file paths (up to 40 neighbors)
    """
    try:
        p = safe_repo_path(file_path)
        if p is None or not p.exists():
            return []

        parent = p.parent.resolve()

        # Robust containment check for parent
        try:
            parent.relative_to(REPO_ROOT)
        except ValueError:
            logger.warning(f"Parent directory {parent} is outside repo root")
            return []

        files = [
            str(x.relative_to(REPO_ROOT))
            for x in parent.glob("*.*")
            if x.is_file() and x != p and _is_safe_path(x.resolve())
        ]
        return files[:40]  # Limit to prevent token overflow
    except Exception as e:
        logger.warning(f"Failed to list neighbors for {file_path}: {e}")
        return []


def _is_safe_path(p: Path) -> bool:
    """Helper to check if resolved path is within repo root."""
    try:
        p.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def repo_snapshot(target_files: List[str]) -> Dict[str, str]:
    """
    Create a snapshot of multiple files' contents.

    Args:
        target_files: List of relative paths from repo root

    Returns:
        Dict mapping file paths to their contents
    """
    snap: Dict[str, str] = {}
    for rel in target_files:
        try:
            # Security: Normalize and validate path
            p = safe_repo_path(rel)
            if p is None:
                logger.warning(f"Skipping {rel} - outside repo root or invalid path")
                continue

            if p.is_file():
                snap[rel] = read_text_safe(p)
        except Exception as e:
            logger.warning(f"Failed to snapshot {rel}: {e}")
            snap[rel] = f"# Error reading file: {e}"

    return snap
