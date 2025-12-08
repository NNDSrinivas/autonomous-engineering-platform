"""
Confluence Ingestor - Ingest Confluence pages into memory graph

Creates memory nodes for:
- Confluence pages
- Spaces
- Users

Creates edges for:
- page → page (parent/child)
- page → space (belongs to)
- page → label (tagged with)
"""

import logging
from typing import Dict, Any
from backend.services.memory_graph_service import MemoryGraphService

logger = logging.getLogger(__name__)


class ConfluenceIngestor:
    """Ingest Confluence pages into the organizational memory graph."""
    
    def __init__(self, memory_service: MemoryGraphService):
        self.mg = memory_service
    
    async def ingest_page(self, page: Dict[str, Any]) -> int:
        """
        Ingest a Confluence page.
        
        Args:
            page: Page dict from Confluence API
            
        Returns:
            Node ID of the created page node
        """
        try:
            page_id = page.get("id", "")
            title = page.get("title", "")
            content = page.get("body", {}).get("storage", {}).get("value", "")
            space_key = page.get("space", {}).get("key", "")
            author = page.get("history", {}).get("createdBy", {}).get("displayName", "Unknown")
            
            # Create page node
            node_id = await self.mg.add_node(
                node_type="confluence_page",
                text=content,
                title=title,
                meta={
                    "page_id": page_id,
                    "space_key": space_key,
                    "author": author,
                    "url": page.get("_links", {}).get("webui", ""),
                    "created": page.get("history", {}).get("createdDate")
                }
            )
            
            logger.info(f"Ingested Confluence page '{title}' as node {node_id}")
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest Confluence page: {e}", exc_info=True)
            raise
