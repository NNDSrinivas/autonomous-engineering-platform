"""
Create File Tool

Creates new file with content.
This is a write operation (requires user approval).
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def create_file(user_id: str, path: str, content: str) -> Dict[str, Any]:
    """
    Create new file in workspace.

    Args:
        user_id: User ID executing the tool
        path: Absolute or relative file path
        content: File content to write

    Returns:
        {
            "success": bool,
            "message": str,
            "path": str (if success),
            "error": str (if failure)
        }
    """
    logger.info(
        f"[TOOL:create_file] user={user_id}, path={path}, size={len(content)} chars"
    )

    try:
        # Handle escaped newlines that might come from JSON serialization.
        # Only convert when content appears to be fully escaped (no actual control characters yet),
        # to avoid corrupting legitimate literals like the text "\n" in source code or docs.
        has_escaped_sequences = any(seq in content for seq in ("\\n", "\\t", "\\r"))
        has_real_control_chars = any(ch in content for ch in ("\n", "\t", "\r"))
        if has_escaped_sequences and not has_real_control_chars:
            content = content.replace("\\n", "\n")
            content = content.replace("\\t", "\t")
            content = content.replace("\\r", "\r")
        # Check if file already exists
        if os.path.exists(path):
            return {
                "success": False,
                "message": f"❌ File already exists: `{path}`\nUse edit_file or apply_diff to modify existing files.",
                "error": "File already exists",
            }

        # Create parent directories if needed
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            logger.info(f"[TOOL:create_file] Created directories: {folder}")

        # Write file
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)

        # Count lines for user feedback
        line_count = content.count("\n") + 1

        return {
            "success": True,
            "message": f"🆕 Created `{path}` ({line_count} lines, {len(content)} chars)",
            "path": path,
            "line_count": line_count,
            "char_count": len(content),
        }

    except PermissionError:
        return {
            "success": False,
            "message": f"❌ Permission denied: `{path}`",
            "error": "Permission denied",
        }

    except Exception as e:
        logger.error(f"[TOOL:create_file] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error creating file: {str(e)}",
            "error": str(e),
        }
