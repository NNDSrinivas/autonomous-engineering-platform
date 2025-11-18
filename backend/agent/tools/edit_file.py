"""
Edit File Tool

Replaces entire file content.
This is a write operation (requires user approval).

For partial edits, use apply_diff instead.
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def edit_file(user_id: str, path: str, new_content: str) -> Dict[str, Any]:
    """
    Replace entire file content.
    
    Args:
        user_id: User ID executing the tool
        path: Absolute or relative file path
        new_content: New file content
    
    Returns:
        {
            "success": bool,
            "message": str,
            "path": str (if success),
            "old_size": int,
            "new_size": int,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:edit_file] user={user_id}, path={path}, new_size={len(new_content)} chars")
    
    try:
        # Check if file exists
        if not os.path.exists(path):
            return {
                "success": False,
                "message": f"❌ File not found: `{path}`\nUse create_file to create new files.",
                "error": "File does not exist"
            }
        
        # Read old content for comparison
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            old_content = fp.read()
        
        old_lines = old_content.count("\n") + 1
        new_lines = new_content.count("\n") + 1
        
        # Write new content
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(new_content)
        
        # Calculate diff stats
        lines_changed = abs(new_lines - old_lines)
        change_indicator = "+" if new_lines > old_lines else "-" if new_lines < old_lines else "="
        
        return {
            "success": True,
            "message": f"✏️ Updated `{path}` ({old_lines} → {new_lines} lines, {change_indicator}{lines_changed})",
            "path": path,
            "old_size": len(old_content),
            "new_size": len(new_content),
            "old_lines": old_lines,
            "new_lines": new_lines
        }
    
    except PermissionError:
        return {
            "success": False,
            "message": f"❌ Permission denied: `{path}`",
            "error": "Permission denied"
        }
    
    except Exception as e:
        logger.error(f"[TOOL:edit_file] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error editing file: {str(e)}",
            "error": str(e)
        }
