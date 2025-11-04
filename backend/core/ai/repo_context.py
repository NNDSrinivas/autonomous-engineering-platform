"""
Repo context gathering for AI code generation.
Safely reads files and discovers neighbors for prompt composition.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import logging
import os
import stat

logger = logging.getLogger(__name__)


def path_has_symlink_in_hierarchy(path: str, root: str) -> bool:
    """
    Returns True if any ancestor (including path itself) between root and path is a symlink.
    Uses only trusted, validated paths to avoid CodeQL alerts.
    """
    # Both paths must be absolute
    try:
        path_normalized = os.path.realpath(os.path.normpath(path))
        root_normalized = os.path.realpath(os.path.normpath(root))
    except Exception:
        return True

    if not path_normalized.startswith(root_normalized):
        # Outside repo, bail out
        return True

    # If same directory, no symlinks in hierarchy
    if path_normalized == root_normalized:
        return False

    # Use os.walk to enumerate only real directories, avoiding symlinks
    try:
        # Check if the path itself exists and is not a symlink
        if not os.path.exists(path_normalized):
            return True

        # Get all components between root and path
        rel_path = os.path.relpath(path_normalized, root_normalized)
        if rel_path.startswith(".."):
            return True

        # Check each component by building path incrementally
        current_check = root_normalized
        for component in rel_path.split(os.sep):
            if not component:  # Skip empty components
                continue
            current_check = os.path.join(current_check, component)

            # Use os.lstat to avoid following symlinks during check
            try:
                stat_result = os.lstat(current_check)
                if stat.S_ISLNK(stat_result.st_mode):
                    return True
            except (OSError, AttributeError):
                return True

        return False
    except Exception:
        return True


def is_safe_subpath(path: str, root: str) -> bool:
    """
    Returns True if path is a sub-path of root, and all components between root and path are not symlinks.
    Uses defensive programming to avoid CodeQL alerts about uncontrolled data.
    """
    try:
        # Both absolute, normalized, real paths
        path_resolved = os.path.realpath(os.path.normpath(path))
        root_resolved = os.path.realpath(os.path.normpath(root))

        # Check commonpath with proper exception handling
        try:
            if not os.path.commonpath([path_resolved, root_resolved]) == root_resolved:
                return False
        except ValueError:
            # Paths on different drives on Windows
            return False

        # If same directory, it's safe
        if path_resolved == root_resolved:
            return True

        # Use os.lstat to check each component without following symlinks
        rel_path = os.path.relpath(path_resolved, root_resolved)
        if rel_path.startswith(".."):
            return False

        # Build path incrementally and check each component
        current_path = root_resolved
        for component in rel_path.split(os.sep):
            if not component:  # Skip empty components
                continue
            current_path = os.path.join(current_path, component)

            try:
                stat_result = os.lstat(current_path)
                if stat.S_ISLNK(stat_result.st_mode):
                    return False
            except (OSError, AttributeError):
                return False

        return True
    except Exception:
        return False


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
        # Harden containment: parent must be a true subdirectory of repo root, not root or ancestor or outside
        repo_root_norm = os.path.normpath(repo_root_str)
        safe_parent_real_norm = (
            os.path.normpath(safe_parent_real) if safe_parent_real is not None else None
        )

        # Check containment with proper exception handling for Windows cross-drive paths
        containment_error = False
        try:
            if (
                safe_parent is None
                or os.path.commonpath([safe_parent, repo_root_str]) != repo_root_str
            ):
                containment_error = True
        except ValueError:
            # Paths on different drives on Windows
            containment_error = True

        try:
            if (
                not containment_error
                and safe_parent_real is not None
                and safe_parent_real_norm is not None
                and os.path.commonpath([safe_parent_real_norm, repo_root_norm])
                != repo_root_norm
            ):
                containment_error = True
        except ValueError:
            # Paths on different drives on Windows
            containment_error = True

        if (
            containment_error
            or safe_parent_real is None
            or safe_parent_real_norm is None
            or safe_parent_real_norm == repo_root_norm
            or os.path.relpath(safe_parent_real_norm, repo_root_norm).startswith("..")
        ):
            logger.warning(
                f"Parent directory {parent_dir} is outside repo root or not a directory"
            )
            return []

        # Forbid listing repo root directly to avoid disclosure of special files
        if safe_parent_real == repo_root_str:
            logger.warning(f"Refusing to list repo root directory: {safe_parent_real}")
            return []

        # Extra hardening: avoid symlinks and TOCTOU
        # Ensure safe_parent_real is not a symlink (and not a path with symlinked dirs leading outside)
        final_check_failed = False

        # Check commonpath with exception handling
        try:
            if (
                safe_parent_real is not None
                and not os.path.commonpath([safe_parent_real, repo_root_str])
                == repo_root_str
            ):
                final_check_failed = True
        except ValueError:
            # Paths on different drives on Windows
            final_check_failed = True

        if (
            safe_parent_real is None
            or not os.path.isdir(safe_parent_real)
            or os.path.islink(safe_parent_real)
            or os.path.realpath(safe_parent_real) != safe_parent_real
            or path_has_symlink_in_hierarchy(safe_parent_real, repo_root_str)
            or final_check_failed
            or not is_safe_subpath(safe_parent_real, repo_root_str)
        ):
            logger.warning(
                f"Refusing to list: {safe_parent_real} failed final hardening checks"
            )
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
                # Re-validate by resolving to realpath and checking containment again
                if validated_item_path is not None:
                    item_realpath = os.path.realpath(validated_item_path)

                    # Check commonpath with exception handling for Windows cross-drive paths
                    item_within_repo = False
                    try:
                        if (
                            os.path.commonpath([item_realpath, repo_root_str])
                            == repo_root_str
                        ):
                            item_within_repo = True
                    except ValueError:
                        # Paths on different drives, treat as not within repo
                        item_within_repo = False

                    # Ensure the real path is inside the repo root
                    if (
                        item_within_repo
                        # Never allow symlinks, even if they resolve inside repo root
                        and not os.path.islink(item_realpath)
                        and os.path.isfile(item_realpath)
                        and item_realpath != path_str
                    ):
                        try:
                            rel_path = os.path.relpath(
                                validated_item_path, repo_root_str
                            )
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
