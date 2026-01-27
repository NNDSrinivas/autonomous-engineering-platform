"""
Apply Diff Tool

Applies unified diff to existing file.
This is the MOST POWERFUL editing tool - allows surgical code changes.

This is a write operation (requires user approval).
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def apply_diff(
    user_id: str, path: str, diff: str, old_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Apply unified diff to file.

    This enables surgical code edits like:
    - Refactoring specific functions
    - Adding imports
    - Fixing bugs
    - Migrating code patterns

    Args:
        user_id: User ID executing the tool
        path: Absolute or relative file path
        diff: Unified diff string (output of difflib.unified_diff)
        old_content: Optional - expected old content for validation

    Returns:
        {
            "success": bool,
            "message": str,
            "path": str (if success),
            "lines_changed": int,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:apply_diff] user={user_id}, path={path}")

    try:
        # Handle escaped newlines that might come from JSON serialization
        # This fixes the issue where diff has literal '\n' instead of actual newlines
        if '\\n' in diff and '\n' not in diff:
            diff = diff.replace('\\n', '\n')
            diff = diff.replace('\\t', '\t')
            diff = diff.replace('\\r', '\r')

        # Check if file exists
        if not os.path.exists(path):
            return {
                "success": False,
                "message": f"❌ File not found: `{path}`",
                "error": "File does not exist",
            }

        # Read current content
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            current_content = fp.read()

        # Validate old_content if provided
        if old_content is not None and current_content != old_content:
            return {
                "success": False,
                "message": "❌ File has changed since diff was generated. Please regenerate diff.",
                "error": "File content mismatch",
            }

        # Parse diff and apply changes
        # This is a simplified implementation
        # In production, use proper patch library (e.g., unidiff, patch)

        current_lines = current_content.splitlines(keepends=True)
        diff_lines = diff.splitlines()

        # Simple diff application (handles basic cases)
        # For production: use proper unified diff parser
        new_lines = current_lines.copy()
        line_offset = 0

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]

            if line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                parts = line.split()
                if len(parts) >= 3:
                    old_range = parts[1].lstrip("-").split(",")
                    old_start = int(old_range[0]) - 1  # 0-indexed

                    # Collect hunk changes
                    hunk_old = []
                    hunk_new = []
                    i += 1

                    while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                        if diff_lines[i].startswith("-"):
                            hunk_old.append(diff_lines[i][1:] + "\n")
                        elif diff_lines[i].startswith("+"):
                            hunk_new.append(diff_lines[i][1:] + "\n")
                        elif diff_lines[i].startswith(" "):
                            hunk_old.append(diff_lines[i][1:] + "\n")
                            hunk_new.append(diff_lines[i][1:] + "\n")
                        i += 1

                    # Apply hunk
                    actual_start = old_start + line_offset
                    new_lines[actual_start : actual_start + len(hunk_old)] = hunk_new
                    line_offset += len(hunk_new) - len(hunk_old)

                    continue

            i += 1

        # Write patched content
        new_content = "".join(new_lines)

        with open(path, "w", encoding="utf-8") as fp:
            fp.write(new_content)

        # Calculate stats
        old_line_count = len(current_lines)
        new_line_count = len(new_lines)
        lines_changed = abs(new_line_count - old_line_count)

        return {
            "success": True,
            "message": f"🔧 Applied diff to `{path}` ({lines_changed} lines changed)",
            "path": path,
            "lines_changed": lines_changed,
            "old_lines": old_line_count,
            "new_lines": new_line_count,
        }

    except PermissionError:
        return {
            "success": False,
            "message": f"❌ Permission denied: `{path}`",
            "error": "Permission denied",
        }

    except Exception as e:
        logger.error(f"[TOOL:apply_diff] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error applying diff: {str(e)}",
            "error": str(e),
        }
