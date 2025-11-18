"""
Search Repository Tool

Searches workspace for files containing query string.
This is a read-only operation (no approval needed).
"""

import os
import logging
from typing import Dict, Any, List
import re

logger = logging.getLogger(__name__)


# Directories to exclude from search
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", "dist", "build",
    ".next", ".nuxt", "out", "target", "bin", "obj"
}

# File extensions to search (text files)
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".rb", ".swift",
    ".kt", ".scala", ".sh", ".bash", ".zsh", ".fish",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".xml", ".html", ".css", ".scss", ".less", ".sql"
}


async def search_repo(
    user_id: str,
    query: str,
    workspace_root: str = None,
    max_results: int = 50,
    case_sensitive: bool = False,
    regex: bool = False
) -> Dict[str, Any]:
    """
    Search workspace for files containing query.
    
    Args:
        user_id: User ID executing the tool
        query: Search query (string or regex)
        workspace_root: Root directory to search (defaults to current directory)
        max_results: Maximum number of results to return
        case_sensitive: Whether search is case-sensitive
        regex: Whether query is a regular expression
    
    Returns:
        {
            "success": bool,
            "message": str,
            "matches": List[Dict] with file path and line numbers,
            "total_matches": int,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:search_repo] user={user_id}, query={query}, regex={regex}")
    
    try:
        if workspace_root is None:
            workspace_root = os.getcwd()
        
        # Compile search pattern
        if regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
        else:
            # Escape regex special chars for literal search
            escaped = re.escape(query)
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(escaped, flags)
        
        matches = []
        files_searched = 0
        
        # Walk directory tree
        for root, dirs, files in os.walk(workspace_root):
            # Remove excluded directories from traversal
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            
            for file in files:
                # Check file extension
                _, ext = os.path.splitext(file)
                if ext not in TEXT_EXTENSIONS:
                    continue
                
                file_path = os.path.join(root, file)
                files_searched += 1
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                        file_matches = []
                        for line_num, line in enumerate(fp, start=1):
                            if pattern.search(line):
                                file_matches.append({
                                    "line": line_num,
                                    "content": line.strip()
                                })
                                
                                # Stop if we hit max results
                                if len(matches) + len(file_matches) >= max_results:
                                    break
                        
                        if file_matches:
                            # Make path relative to workspace root
                            rel_path = os.path.relpath(file_path, workspace_root)
                            matches.append({
                                "file": rel_path,
                                "matches": file_matches[:10],  # Limit matches per file
                                "total_matches_in_file": len(file_matches)
                            })
                        
                        # Stop if we hit max results
                        if len(matches) >= max_results:
                            break
                
                except Exception as e:
                    logger.debug(f"[TOOL:search_repo] Skipping file {file_path}: {e}")
                    continue
            
            # Stop if we hit max results
            if len(matches) >= max_results:
                break
        
        # Format results
        total_matches = sum(m["total_matches_in_file"] for m in matches)
        
        if not matches:
            return {
                "success": True,
                "message": f"🔍 No matches found for '{query}' (searched {files_searched} files)",
                "matches": [],
                "total_matches": 0,
                "files_searched": files_searched
            }
        
        # Build summary message
        files_with_matches = len(matches)
        summary_lines = [f"🔍 Found {total_matches} matches in {files_with_matches} files:\n"]
        
        for match in matches[:10]:  # Show first 10 files
            file_path = match["file"]
            match_count = match["total_matches_in_file"]
            first_line = match["matches"][0]["line"]
            summary_lines.append(f"  • `{file_path}` (line {first_line}, {match_count} matches)")
        
        if len(matches) > 10:
            summary_lines.append(f"  ... and {len(matches) - 10} more files")
        
        return {
            "success": True,
            "message": "\n".join(summary_lines),
            "matches": matches,
            "total_matches": total_matches,
            "files_searched": files_searched
        }
    
    except Exception as e:
        logger.error(f"[TOOL:search_repo] Error: {e}")
        return {
            "success": False,
            "message": f"❌ Error searching repository: {str(e)}",
            "error": str(e)
        }
