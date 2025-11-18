"""
Workspace Retriever - Fetch Workspace Context (STEP C Enhanced)

Retrieves relevant context from the user's workspace:
- Currently open files
- Selected text/code
- Project structure
- Git branch/status
- Recent file changes
- Small files (for context)

This helps NAVI understand what the user is working on right now.
Enables code explanation, refactoring, and generation.
"""

import logging
from typing import Dict, Any, Optional, List
import os

logger = logging.getLogger(__name__)


async def retrieve_workspace_context(
    user_id: str,
    workspace_root: Optional[str] = None,
    include_files: bool = True
) -> Dict[str, Any]:
    """
    Retrieve workspace context for the user.
    
    Args:
        user_id: User identifier
        workspace_root: Root path of workspace (if known)
        include_files: Whether to read small files
    
    Returns:
        {
            "active_file": str,           # Currently open file path
            "selected_text": str,         # Selected code/text
            "project_root": str,          # Workspace root path
            "git_branch": str,            # Current git branch
            "recent_files": List[Dict],   # Recently edited files
            "file_tree": Dict             # Project structure summary
        }
    """
    
    # TODO: This needs integration with VS Code extension
    # Extension should send workspace context in the request
    
    logger.info(f"[WORKSPACE] Retrieving context for user={user_id}")
    
    context = {
        "active_file": None,
        "selected_text": None,
        "project_root": workspace_root,
        "git_branch": None,
        "recent_files": [],
        "file_tree": {}
    }
    
    # If workspace root is provided, scan for small files
    if workspace_root and include_files and os.path.exists(workspace_root):
        context["recent_files"] = await _scan_small_files(workspace_root)
        context["git_branch"] = await _get_git_branch(workspace_root)
        context["file_tree"] = await _build_file_tree_summary(workspace_root)
    
    return context


async def _scan_small_files(
    root: str,
    max_size: int = 50000,  # 50KB
    max_files: int = 10
) -> List[Dict[str, Any]]:
    """
    Scan for small files that can fit in context window.
    
    Only includes text files, excludes:
    - node_modules, .venv, __pycache__, .git
    - Binary files
    - Large files
    """
    
    excluded_dirs = {
        "node_modules", ".venv", "venv", "__pycache__", 
        ".git", "dist", "build", "out", ".next",
        "target", "vendor"
    }
    
    text_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go",
        ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb",
        ".php", ".swift", ".kt", ".scala", ".sh", ".bash",
        ".yaml", ".yml", ".json", ".toml", ".xml", ".md",
        ".txt", ".sql", ".html", ".css", ".scss", ".sass"
    }
    
    small_files = []
    
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip excluded directories
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
            
            for filename in filenames:
                ext = os.path.splitext(filename)[1]
                if ext not in text_extensions:
                    continue
                
                filepath = os.path.join(dirpath, filename)
                
                try:
                    file_size = os.path.getsize(filepath)
                    if file_size > max_size:
                        continue
                    
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    rel_path = os.path.relpath(filepath, root)
                    small_files.append({
                        "path": rel_path,
                        "content": content,
                        "size": file_size
                    })
                    
                    if len(small_files) >= max_files:
                        break
                
                except Exception as e:
                    continue
            
            if len(small_files) >= max_files:
                break
        
        logger.info(f"[WORKSPACE] Scanned {len(small_files)} small files")
        return small_files
    
    except Exception as e:
        logger.error(f"[WORKSPACE] Error scanning files: {e}")
        return []


async def _get_git_branch(root: str) -> Optional[str]:
    """Get current git branch."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"[WORKSPACE] Could not get git branch: {e}")
    
    return None


async def _build_file_tree_summary(root: str, max_depth: int = 2) -> Dict[str, Any]:
    """
    Build a summary of the file tree structure.
    
    Returns a nested dict showing directories and key files.
    """
    
    excluded_dirs = {
        "node_modules", ".venv", "venv", "__pycache__", 
        ".git", "dist", "build", "out"
    }
    
    try:
        tree = {}
        
        for dirpath, dirnames, filenames in os.walk(root):
            # Calculate depth
            rel_path = os.path.relpath(dirpath, root)
            depth = rel_path.count(os.sep) if rel_path != "." else 0
            
            if depth > max_depth:
                continue
            
            # Skip excluded directories
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
            
            # Add this level to tree
            parts = rel_path.split(os.sep) if rel_path != "." else []
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add file count
            current["__files__"] = len(filenames)
            current["__dirs__"] = len(dirnames)
        
        return tree
    
    except Exception as e:
        logger.error(f"[WORKSPACE] Error building file tree: {e}")
        return {}
