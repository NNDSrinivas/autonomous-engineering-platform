"""Wiki Read Connector - scan local markdown documentation"""

from pathlib import Path
from typing import List, Dict

# Maximum content length for text files
MAX_CONTENT_LENGTH = 200000  # Characters


def scan_docs(root="docs") -> List[Dict]:
    """Scan local docs directory for markdown files"""
    p = Path(root)
    out = []
    if p.exists():
        for f in p.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")[:MAX_CONTENT_LENGTH]
                out.append({"title": f.stem, "url": None, "content": content})
            except Exception:
                continue
    return out
