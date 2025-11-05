"""
Unified diff validation and safe application utilities.
Validates git-format diffs and applies them using git apply.
"""

from __future__ import annotations
import os
import re
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Error message constants
INTERNAL_ERROR_PREFIX = "Error: Patch application failed due to internal error"

# Regex patterns for unified diff validation
DIFF_HEADER = re.compile(r"^diff --git a/.+ b/.+", re.M)
HUNK_HEADER = re.compile(r"^@@ -\d+(,\d+)? \+\d+(,\d+)? @@", re.M)
ALLOWED_PREFIX = ("diff ", "index ", "--- ", "+++ ", "@@ ", "+", "-", " ")
NO_NEWLINE_MARKER = "\\ No newline at end of file"


class DiffValidationError(Exception):
    """Raised when diff validation fails."""

    pass


def count_diff_stats(diff_text: str) -> Tuple[int, int, int]:
    """
    Count files, additions, and deletions in a unified diff.

    Args:
        diff_text: Unified diff content

    Returns:
        Tuple of (num_files, additions, deletions)
    """
    files = len(DIFF_HEADER.findall(diff_text))
    additions = sum(
        1
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1
        for line in diff_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    )
    return files, additions, deletions


def validate_unified_diff(
    diff_text: str, max_files: int = 5, max_additions: int = 2000
) -> None:
    """
    Validate that text is a well-formed unified diff within safety limits.

    Args:
        diff_text: The diff content to validate
        max_files: Maximum number of files allowed (default: 5)
        max_additions: Maximum number of added lines (default: 2000)

    Raises:
        DiffValidationError: If validation fails
    """
    if not diff_text or not diff_text.strip():
        raise DiffValidationError("Empty diff")

    # Check for required diff structure
    if not DIFF_HEADER.search(diff_text):
        raise DiffValidationError(
            "Not a recognizable unified diff - missing 'diff --git' header"
        )

    if not HUNK_HEADER.search(diff_text):
        raise DiffValidationError(
            "Not a recognizable unified diff - missing hunk headers '@@'"
        )

    # Validate line prefixes
    for i, line in enumerate(diff_text.splitlines(), 1):
        # In unified diffs, empty lines are valid context lines
        if line == "":
            continue
        # Check for the specific backslash marker
        if line == NO_NEWLINE_MARKER:
            continue
        if not line.startswith(ALLOWED_PREFIX):
            raise DiffValidationError(
                f"Invalid diff line prefix at line {i}: {line[:30]}..."
            )

    # Check size limits
    files, additions, deletions = count_diff_stats(diff_text)

    if files > max_files:
        raise DiffValidationError(
            f"Diff contains {files} files, exceeds limit of {max_files}"
        )

    if additions > max_additions:
        raise DiffValidationError(
            f"Diff adds {additions} lines, exceeds limit of {max_additions}"
        )

    # Check total size
    size_kb = len(diff_text.encode("utf-8")) / 1024
    if size_kb > 256:
        raise DiffValidationError(f"Diff size {size_kb:.1f}KB exceeds 256KB limit")

    logger.info(
        f"Diff validated: {files} files, +{additions} -{deletions}, {size_kb:.1f}KB"
    )


def apply_diff(
    diff_text: str, repo_root: str = ".", dry_run: bool = False
) -> Tuple[int, str]:
    """
    Apply unified diff using `git apply --index --whitespace=fix`.

    Args:
        diff_text: Unified diff content
        repo_root: Repository root directory (default: current dir)
        dry_run: If True, only validate without applying (default: False)

    Returns:
        Tuple of (exit_code, stdout+stderr combined output)

    Raises:
        DiffValidationError: If diff validation fails before attempting apply
    """
    # Validate first
    validate_unified_diff(diff_text)

    # Create temporary file for diff with secure permissions (atomic)
    # Use mkstemp to create file with proper permissions to prevent race conditions
    temp_fd = None
    patch_file = None

    try:
        # Create temporary file with restricted permissions to prevent race condition
        temp_fd, patch_file = tempfile.mkstemp(
            suffix=".patch", dir=tempfile.gettempdir(), text=True
        )
        # Set restrictive permissions immediately after creation
        os.chmod(patch_file, 0o600)

        # Write diff content using file descriptor
        with os.fdopen(temp_fd, "w", encoding="utf-8") as tf:
            tf.write(diff_text)
        temp_fd = None  # File descriptor closed by fdopen context manager
    except Exception:
        # Clean up on failure
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if patch_file and os.path.exists(patch_file):
            try:
                os.unlink(patch_file)
            except OSError:
                pass
        raise

    try:
        # Build git apply command
        cmd = ["git", "apply", "--index", "--whitespace=fix"]
        if dry_run:
            cmd.append("--check")  # Dry run mode
        cmd.append(patch_file)

        logger.info(f"Applying diff: {' '.join(cmd)}")

        # Execute git apply with timeout
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Combine stdout and stderr
        output = (proc.stdout or "") + (proc.stderr or "")

        if proc.returncode == 0:
            logger.info(f"Diff applied successfully (dry_run={dry_run})")
        else:
            logger.warning(
                f"Diff apply failed with code {proc.returncode}: {output[:200]}"
            )

        return proc.returncode, output

    except subprocess.TimeoutExpired:
        logger.error("git apply timed out after 60 seconds")
        return 1, "Error: git apply timed out"
    except Exception as e:
        logger.error(f"Failed to apply diff: {e}")
        return (
            1,
            f"{INTERNAL_ERROR_PREFIX}. See server logs for details.",
        )
    finally:
        # Clean up temp file
        try:
            Path(patch_file).unlink(missing_ok=True)
        except Exception:
            pass
