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
                # Use relative path to avoid title collisions in nested directories.
                # This creates unique identifiers like 'subfolder/file.md' rather than just 'file.md'
                # when files with the same name exist in different directories.
                # NOTE: The title is used as the foreign_id in upsert_memory_object
                # (see backend/search/router.py) which makes this uniqueness
                # critical for deduplication when ingesting wiki pages.
                title = str(f.relative_to(p))
                out.append({"title": title, "url": None, "content": content})
            except (UnicodeDecodeError, IOError, OSError) as e:
                logger.warning("Failed to read wiki file %s: %s", f, e)
                continue
    return out
