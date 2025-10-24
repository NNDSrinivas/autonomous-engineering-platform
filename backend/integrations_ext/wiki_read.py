"""Wiki Read Connector - scan local markdown documentation"""

from pathlib import Path
from typing import List, Dict
import logging
from ..search.constants import MAX_CONTENT_LENGTH

logger = logging.getLogger(__name__)


def scan_docs(root="docs") -> List[Dict]:
    """
    Scan local docs directory for markdown files.

    Uses root + relative path to create unique identifiers that prevent collisions
    if different root directories contain files with the same relative paths.
    For example: 'docs/api/overview.md' vs 'wiki/api/overview.md'

    NOTE: The title is used as the foreign_id in upsert_memory_object (see backend/search/router.py),
    which makes this uniqueness critical for deduplication when ingesting wiki pages.
    """
    p = Path(root)
    out = []
    if p.exists():
        for f in p.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")[:MAX_CONTENT_LENGTH]
                # Include root in title to avoid collisions across different root directories
                title = f"{root}/{f.relative_to(p)}"
                out.append({"title": title, "url": None, "content": content})
            except (UnicodeDecodeError, OSError) as e:
                # IOError is an alias of OSError in Python 3; catching OSError is sufficient
                logger.warning("Failed to read wiki file %s: %s", f, e)
                continue
    return out
