"""
Repo context gathering for AI code generation.
Safely reads files and discovers neighbors for prompt composition.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# Repo root resolution - handles both dev and container environments
try:
    REPO_ROOT = Path(".").resolve()
except Exception:
    REPO_ROOT = Path("/app").resolve()  # Fallback for containerized environments


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
        p = (REPO_ROOT / file_path).resolve()
        if not p.exists():
            return []

        # Security: Ensure path is within repo
        if REPO_ROOT not in p.parents and p != REPO_ROOT:
            logger.warning(f"Path {file_path} is outside repo root")
            return []

        parent = p.parent
        files = [
            str(x.relative_to(REPO_ROOT))
            for x in parent.glob("*.*")
            if x.is_file() and x != p
        ]
        return files[:40]  # Limit to prevent token overflow
    except Exception as e:
        logger.warning(f"Failed to list neighbors for {file_path}: {e}")
        return []


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
            p = (REPO_ROOT / rel).resolve()
            if REPO_ROOT not in p.parents and p != REPO_ROOT:
                logger.warning(f"Skipping {rel} - outside repo root")
                continue

            if p.is_file():
                snap[rel] = read_text_safe(p)
        except Exception as e:
            logger.warning(f"Failed to snapshot {rel}: {e}")
            snap[rel] = f"# Error reading file: {e}"

    return snap
