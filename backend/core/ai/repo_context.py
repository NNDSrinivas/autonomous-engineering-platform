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
        if os.path.isabs(rel_path):
            logger.warning(f"Rejected absolute path: {rel_path}")
            return None

        # Normalize to prevent .. traversal
        norm_rel = os.path.normpath(rel_path)
        if (
            norm_rel.startswith("/")
            or norm_rel.startswith("\\")
            or norm_rel.startswith("..")
            or ".." in norm_rel.split(os.sep)
        ):
            logger.warning(f"Path {rel_path} is not a valid repository-relative file")
            return None

        # Build absolute path using string operations first
        repo_root_str = str(REPO_ROOT.resolve())
        full_str = os.path.join(repo_root_str, norm_rel)
        full_normalized = os.path.normpath(full_str)

        # Ensure the normalized path is still within repo root using string comparison
        if (
            not full_normalized.startswith(repo_root_str + os.sep)
            and full_normalized != repo_root_str
        ):
            logger.warning(
                f"Rejected path outside repo: {rel_path} resolved to {full_normalized}"
            )
            return None

        # Only now create Path object after validation
        return Path(full_normalized)
    except Exception as e:
        logger.warning(f"Exception while resolving path {rel_path}: {e}")
        return None


def read_text_safe(p: Path, max_bytes: int = 200_000) -> str:
    """
    Safely read text file with size limit and error handling.
    Path must already be validated by safe_repo_path.

    Args:
        p: Pre-validated Path to file within repo root
        max_bytes: Maximum bytes to read (default 200KB)

    Returns:
        File content as string, or empty string on error
    """
    try:
        # Path should already be validated, but double-check
        repo_root_str = str(REPO_ROOT.resolve())
        path_str = str(p)
        if (
            not path_str.startswith(repo_root_str + os.sep)
            and path_str != repo_root_str
        ):
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
        if p is None:
            return []

        if not p.exists():
            return []

        parent = p.parent

        # Validate parent directory is safe
        repo_root_str = str(REPO_ROOT.resolve())
        parent_str = str(parent)
        if (
            not parent_str.startswith(repo_root_str + os.sep)
            and parent_str != repo_root_str
        ):
            logger.warning(f"Parent directory {parent} is outside repo root")
            return []

        # Safely list files in parent directory
        try:
            files = []
            for item in parent.iterdir():
                if item.is_file() and item != p:
                    try:
                        rel_path = item.relative_to(REPO_ROOT)
                        files.append(str(rel_path))
                    except ValueError:
                        # Skip files that can't be made relative to repo root
                        continue
            return files[:40]  # Limit to prevent token overflow
        except (OSError, PermissionError):
            logger.warning(f"Could not list directory: {parent}")
            return []

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
            p = safe_repo_path(rel)
            if p is None:
                logger.warning(f"Skipping {rel} - outside repo root or invalid path")
                continue

            if p.exists() and p.is_file():
                snap[rel] = read_text_safe(p)
        except Exception as e:
            logger.warning(f"Failed to snapshot {rel}: {e}")
            snap[rel] = f"# Error reading file: {e}"

    return snap
