import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {"node_modules", ".git", ".venv", "__pycache__", "dist", "build", "out"}

TEXT_EXT = {
    ".ts",
    ".tsx",
    ".py",
    ".js",
    ".jsx",
    ".java",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
}

MAX_FILE_SIZE = 30_000  # 30 KB


def safe_read_file(path: str, workspace_root: Optional[str] = None) -> Optional[str]:
    try:
        # Normalize paths to prevent path traversal attacks
        normalized_path = os.path.normpath(os.path.abspath(path))

        # Validate path is within workspace if workspace_root is provided
        if workspace_root:
            normalized_workspace = os.path.normpath(os.path.abspath(workspace_root))
            if not normalized_path.startswith(normalized_workspace):
                logger.warning("Rejecting path outside workspace: %s", normalized_path)
                return None

        if not os.path.exists(normalized_path):
            return None
        if os.path.getsize(normalized_path) > MAX_FILE_SIZE:
            return None
        with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def build_file_tree(root: str, depth: int = 2) -> List[Dict[str, Any]]:
    result = []
    if depth <= 0:
        return result

    try:
        for entry in os.listdir(root):
            if entry in EXCLUDED_DIRS:
                continue

            full_path = os.path.join(root, entry)
            node: Dict[str, Any] = {"name": entry}

            if os.path.isdir(full_path):
                node["type"] = "dir"
                node["children"] = build_file_tree(full_path, depth - 1)
            else:
                node["type"] = "file"

            result.append(node)
    except Exception as exc:
        logger.warning("Failed to process filesystem node", extra={"error": str(exc)})

    return result


def retrieve_workspace(root: str, max_files: int = 20) -> Dict[str, Any]:
    """Retrieve workspace structure and file contents."""
    files = {}
    count = 0

    for root_path, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for filename in filenames:
            if count >= max_files:
                break

            _, ext = os.path.splitext(filename)
            if ext not in TEXT_EXT:
                continue

            file_path = os.path.join(root_path, filename)
            content = safe_read_file(file_path, root)

            if content:
                rel_path = os.path.relpath(file_path, root)
                files[rel_path] = content
                count += 1

    return {"root": root, "structure": build_file_tree(root), "files": files}
