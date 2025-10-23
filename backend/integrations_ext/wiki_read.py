"""Wiki Read Connector - scan local markdown documentation"""

from pathlib import Path
from typing import List, Dict
import logging
from ..search.constants import MAX_CONTENT_LENGTH

logger = logging.getLogger(__name__)


def scan_docs(root="docs") -> List[Dict]:
    """Scan local docs directory for markdown files"""
    p = Path(root)
    out = []
    if p.exists():
        for f in p.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")[:MAX_CONTENT_LENGTH]
                # Use relative path to avoid title collisions in nested directories
                title = str(f.relative_to(p))
                out.append({"title": title, "url": None, "content": content})
            except (UnicodeDecodeError, IOError, OSError) as e:
                logger.warning(f"Failed to read wiki file {f}: {e}")
                continue
    return out
