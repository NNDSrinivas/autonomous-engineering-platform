import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_safe_path(path: str, workspace_root: str) -> bool:
    """Safely validate that path is within workspace_root to prevent path traversal."""
    try:
        # Convert to pathlib Path objects and resolve
        target_path = Path(path).resolve()
        workspace_path = Path(workspace_root).resolve()

        # Check if target is within workspace
        target_path.relative_to(workspace_path)
        return True
    except (ValueError, OSError):
        return False


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
        # Validate path is within workspace if workspace_root is provided
        if workspace_root and not _is_safe_path(path, workspace_root):
            logger.warning("Rejecting unsafe path: %s", path)
            return None

        # Use pathlib for secure path operations
        file_path = Path(path).resolve()

        if not file_path.exists() or not file_path.is_file():
            return None
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return None

        return file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError) as e:
        logger.warning("Error reading file %s: %s", path, e)
        return None


def build_file_tree(root: str, depth: int = 2) -> List[Dict[str, Any]]:
    result = []
    if depth <= 0:
        return result

    try:
        root_path = Path(root).resolve()
        if not root_path.exists() or not root_path.is_dir():
            return result

        for entry in root_path.iterdir():
            if entry.name in EXCLUDED_DIRS:
                continue

            # Validate the entry is actually within root directory
            if not _is_safe_path(str(entry), str(root_path)):
                continue

            node: Dict[str, Any] = {"name": entry.name}

            if entry.is_dir():
                node["type"] = "dir"
                node["children"] = build_file_tree(str(entry), depth - 1)
            else:
                node["type"] = "file"

            result.append(node)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to process filesystem node: %s", exc)

    return result


def retrieve_workspace_sync(root: str, max_files: int = 20) -> Dict[str, Any]:
    """Retrieve workspace structure and file contents."""
    files = {}
    count = 0

    try:
        root_path = Path(root).resolve()
        if not root_path.exists() or not root_path.is_dir():
            return {"root": root, "structure": [], "files": {}}

        for current_root, dirs, filenames in os.walk(str(root_path)):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for filename in filenames:
                if count >= max_files:
                    break

                _, ext = os.path.splitext(filename)
                if ext not in TEXT_EXT:
                    continue

                file_path = os.path.join(current_root, filename)

                # Validate file path is within root
                if not _is_safe_path(file_path, str(root_path)):
                    continue

                content = safe_read_file(file_path, str(root_path))

                if content:
                    rel_path = os.path.relpath(file_path, str(root_path))
                    files[rel_path] = content
                    count += 1

        return {"root": root, "structure": build_file_tree(root), "files": files}
    except (OSError, ValueError) as exc:
        logger.warning("Error retrieving workspace: %s", exc)
        return {"root": root, "structure": [], "files": {}}
