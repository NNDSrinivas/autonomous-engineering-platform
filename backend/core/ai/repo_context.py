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


def safe_repo_path(rel_path: str) -> str | None:
    """
    Return resolved path string if and only if rel_path is safely inside the REPO_ROOT.
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

        # Build absolute path using string operations only
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

        # Return the validated string path instead of Path object
        return full_normalized
    except Exception as e:
        logger.warning(f"Exception while resolving path {rel_path}: {e}")
        return None


def read_text_safe(path_str: str, max_bytes: int = 200_000) -> str:
    """
    Safely read text file with size limit and error handling.
    Path must already be validated by safe_repo_path.

    Args:
        path_str: Pre-validated string path to file within repo root
        max_bytes: Maximum bytes to read (default 200KB)

    Returns:
        File content as string, or empty string on error
    """
    try:
        # Path should already be validated, but double-check
        repo_root_str = str(REPO_ROOT.resolve())
        if (
            not path_str.startswith(repo_root_str + os.sep)
            and path_str != repo_root_str
        ):
            logger.warning(f"Attempted to read file outside repo root: {path_str}")
            return ""

        # Use os.path operations instead of Path operations
        if not os.path.exists(path_str) or not os.path.isfile(path_str):
            return ""
        
        # Read file using built-in open() function
        with open(path_str, 'rb') as f:
            data = f.read(max_bytes)
        
        if os.path.getsize(path_str) > max_bytes:
            logger.warning(f"File {path_str} exceeds {max_bytes} bytes, truncating")
        
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {path_str}: {e}")
        return ""


def list_neighbors(file_path: str) -> List[str]:
    """
    List neighboring files in the same directory.

    Args:
        file_path: Relative path from repo root

    Returns:
        List of relative file paths (up to 40 neighbors)
    """
    try:
        path_str = safe_repo_path(file_path)
        if path_str is None:
            return []

        # Use os.path operations instead of Path operations
        if not os.path.exists(path_str):
            return []

        parent_dir = os.path.dirname(path_str)

        # Validate parent directory is safe
        repo_root_str = str(REPO_ROOT.resolve())
        if (
            not parent_dir.startswith(repo_root_str + os.sep)
            and parent_dir != repo_root_str
        ):
            logger.warning(f"Parent directory {parent_dir} is outside repo root")
            return []

        # Safely list files in parent directory using os.listdir
        try:
            files = []
            for item_name in os.listdir(parent_dir):
                item_path = os.path.join(parent_dir, item_name)
                if os.path.isfile(item_path) and item_path != path_str:
                    try:
                        # Calculate relative path using string operations
                        if item_path.startswith(repo_root_str + os.sep):
                            rel_path = item_path[len(repo_root_str + os.sep):]
                        elif item_path == repo_root_str:
                            rel_path = "."
                        else:
                            continue  # Skip files outside repo root
                        
                        files.append(rel_path)
                    except Exception:
                        # Skip files that can't be processed
                        continue
            return files[:40]  # Limit to prevent token overflow
        except (OSError, PermissionError):
            logger.warning(f"Could not list directory: {parent_dir}")
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
            path_str = safe_repo_path(rel)
            if path_str is None:
                logger.warning(f"Skipping {rel} - outside repo root or invalid path")
                continue

            # Use os.path operations instead of Path operations
            if os.path.exists(path_str) and os.path.isfile(path_str):
                snap[rel] = read_text_safe(path_str)
        except Exception as e:
            logger.warning(f"Failed to snapshot {rel}: {e}")
            snap[rel] = f"# Error reading file: {e}"

    return snap
