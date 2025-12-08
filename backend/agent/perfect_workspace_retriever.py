import os
from typing import Any, Dict, List, Optional

EXCLUDED_DIRS = {
    "node_modules", ".git", ".venv", "__pycache__", "dist", "build", "out"
}

TEXT_EXT = {".ts", ".tsx", ".py", ".js", ".jsx", ".java", ".md", ".json", ".yaml", ".yml", ".txt"}

MAX_FILE_SIZE = 30_000  # 30 KB


def safe_read_file(path: str) -> Optional[str]:
    try:
        if not os.path.exists(path):
            return None
        if os.path.getsize(path) > MAX_FILE_SIZE:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except:
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


async def retrieve_perfect_workspace_context(
    payload_workspace: Dict[str, Any],
    include_files: bool = True,
) -> Dict[str, Any]:
    """
    PERFECT WORKSPACE RETRIEVER
    Merges workspace context coming from VS Code extension
    with backend-side filesystem context.
    """
    import logging
    logger = logging.getLogger(__name__)

    workspace_root = payload_workspace.get("workspace_root")
    active_file = payload_workspace.get("active_file")
    selected_text = payload_workspace.get("selected_text")
    recent_files = payload_workspace.get("recent_files", [])
    
    logger.info(f"[PERFECT-WORKSPACE] workspace_root: {workspace_root}")
    logger.info(f"[PERFECT-WORKSPACE] payload_workspace: {payload_workspace}")

    file_tree = []
    small_files = []

    if workspace_root and os.path.exists(workspace_root):
        file_tree = build_file_tree(workspace_root, depth=2)

        if include_files:
            for path in recent_files[:10]:
                content = safe_read_file(path)
                if content:
                    ext = os.path.splitext(path)[1]
                    if ext in TEXT_EXT:
                        small_files.append({
                            "path": path,
                            "ext": ext,
                            "content": content
                        })

    return {
        "workspace_root": workspace_root,
        "active_file": active_file,
        "selected_text": selected_text,
        "recent_files": recent_files,
        "file_tree": file_tree,
        "small_files": small_files,
    }