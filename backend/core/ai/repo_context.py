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
        # Forbid "." or empty string as relative path (no root or ambiguous access)
        if (
            not norm_rel
            or norm_rel in (".", "")
            or norm_rel.startswith("/")
            or norm_rel.startswith("\\")
            or norm_rel.startswith("..")
            or ".." in norm_rel.split(os.sep)
        ):
            logger.warning(f"Path {rel_path} is not a valid repository-relative file")
            return None

        # Build absolute path then canonicalize using realpath
        repo_root_str = os.path.realpath(str(REPO_ROOT.resolve()))
        full_str = os.path.join(repo_root_str, norm_rel)
        full_realpath = os.path.realpath(full_str)

        # Use commonpath to ensure path is inside repo root (handles symlinks and all edge cases robustly)
        try:
            # commonpath returns the deepest common path shared; must equal repo_root_str.
            # Use normpath to support Windows (where trailing separators can cause mismatches).
            repo_root_str_norm = os.path.normpath(repo_root_str)
            full_realpath_norm = os.path.normpath(full_realpath)
            common = os.path.commonpath([full_realpath_norm, repo_root_str_norm])
        except Exception as e:
            logger.warning(f"Error in commonpath for {rel_path}: {e}")
            return None
        if common != repo_root_str_norm:
            logger.warning(
                f"Rejected path outside repo: {rel_path} resolved to {full_realpath}"
            )
            return None

        # Return the validated real canonical path string
        return full_realpath
    except Exception as e:
        logger.warning(f"Exception while resolving path {rel_path}: {e}")
        return None


def read_text_safe(path_str: str, max_bytes: int = 200_000) -> str:
    """
    Safely read text file with size limit and error handling.
    Always validates path using safe_repo_path to ensure access is strictly controlled.

    Args:
        path_str: Relative path to file within repo root (will be validated internally)
        max_bytes: Maximum bytes to read (default 200KB)

    Returns:
        File content as string, or empty string on error
    """
    try:
        # Validate that path_str is a repo-relative path
        validated_path = safe_repo_path(path_str)
        # safe_repo_path fully enforces containment and normalization
        if validated_path is None:
            logger.warning(f"read_text_safe: Path failed validation: {path_str}")
            return ""

        # Use os.path operations instead of Path operations
        if not os.path.exists(validated_path) or not os.path.isfile(validated_path):
            return ""

        # Read file using built-in open() function
        with open(validated_path, "rb") as f:
            data = f.read(max_bytes)

        if os.path.getsize(validated_path) > max_bytes:
            logger.warning(
                f"File {validated_path} exceeds {max_bytes} bytes, truncating"
            )

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

        # Validate parent directory is safe using safe_repo_path
        repo_root_str = os.path.realpath(str(REPO_ROOT.resolve()))
        parent_rel = os.path.relpath(parent_dir, repo_root_str)
        safe_parent = safe_repo_path(parent_rel)
        # Extra hardening: check resolved path is inside repo, is not root, and is directory
        try:
            safe_parent_real = (
                os.path.realpath(safe_parent) if safe_parent is not None else None
            )
        except Exception:
            safe_parent_real = None
        if (
            safe_parent is None
            or os.path.commonpath([safe_parent, repo_root_str]) != repo_root_str
            or safe_parent_real is None
            or not os.path.commonpath([safe_parent_real, repo_root_str])
            == repo_root_str
            or not os.path.isdir(safe_parent_real)
        ):
            logger.warning(
                f"Parent directory {parent_dir} is outside repo root or not a directory"
            )
            return []

        # Forbid listing repo root directly to avoid disclosure of special files
        if safe_parent_real == repo_root_str:
            logger.warning(f"Refusing to list repo root directory: {safe_parent_real}")
            return []

        # Safely list files in parent directory using os.listdir
        try:
            files = []
            for item_name in os.listdir(safe_parent_real):
                # Skip hidden files (dotfiles) for neighbor lists
                if item_name.startswith("."):
                    continue

                # Compute a relative path from repo root to the item
                rel_item_path = os.path.relpath(
                    os.path.join(safe_parent_real, item_name), repo_root_str
                )
                validated_item_path = safe_repo_path(rel_item_path)
                # Extra hardening: Ensure validated_item_path is strictly within repo_root_str
                # Forbid following symlinks as an extra hardening step
                if (
                    validated_item_path is not None
                    and not os.path.islink(validated_item_path)
                    and os.path.isfile(validated_item_path)
                    and validated_item_path != path_str
                    and os.path.commonpath([validated_item_path, repo_root_str])
                    == repo_root_str
                ):
                    try:
                        rel_path = os.path.relpath(validated_item_path, repo_root_str)
                        # Only accept relative paths (not containing "..")
                        if rel_path.startswith("..") or os.path.isabs(rel_path):
                            continue
                        files.append(rel_path)
                    except Exception:
                        # Skip files that can't be processed
                        continue
            return files[:40]  # Limit to prevent token overflow
        except (OSError, PermissionError):
            logger.warning(f"Could not list directory: {safe_parent_real}")
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
            # Security: Normalize and validate path - read_text_safe will re-validate
            path_str = safe_repo_path(rel)
            if path_str is None:
                logger.warning(f"Skipping {rel} - outside repo root or invalid path")
                continue

            # All file access should go through read_text_safe, which re-validates the path
            content = read_text_safe(rel)
            if content != "":
                snap[rel] = content
            else:
                logger.warning(f"Could not read {rel} or file is empty.")
        except Exception as e:
            logger.warning(f"Failed to snapshot {rel}: {e}")
            snap[rel] = f"# Error reading file: {e}"

    return snap
