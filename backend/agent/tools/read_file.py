"""
Read File Tool

Reads and returns file contents.
This is a read-only operation (no approval needed).
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def read_file(user_id: str, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read file contents from workspace.
    
    Args:
        user_id: User ID executing the tool
        path: Absolute or relative file path
        start_line: Optional start line (1-indexed)
        end_line: Optional end line (1-indexed, inclusive)
    
    Returns:
        {
            "success": bool,
            "message": str,
            "content": str (if success),
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:read_file] user={user_id}, path={path}")
    
    try:
        # Check if file exists
        if not os.path.exists(path):
            return {
                "success": False,
                "message": f"❌ File not found: `{path}`",
                "error": "File does not exist"
            }
        
        # Check if it's a file (not directory)
        if not os.path.isfile(path):
            return {
                "success": False,
                "message": f"❌ Not a file: `{path}`",
                "error": "Path is not a file"
            }
        
        # Read file contents
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            if start_line is not None or end_line is not None:
                # Read specific lines
                lines = fp.readlines()
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else len(lines)
                content = "".join(lines[start:end])
            else:
                # Read entire file
                content = fp.read()
        
        # Format response
        line_info = ""
        if start_line or end_line:
            line_info = f" (lines {start_line or 1}-{end_line or 'EOF'})"
        
        return {
            "success": True,
            "message": f"📄 Read `{path}`{line_info} ({len(content)} chars)",
            "content": content,
            "path": path
        }
    
    except PermissionError:
        return {
            "success": False,
            "message": f"❌ Permission denied: `{path}`",
            "error": "Permission denied"
        }
    
    except Exception as e:
        logger.error(f"[TOOL:read_file] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error reading file: {str(e)}",
            "error": str(e)
        }
