"""
Figma API client for design file access and collaboration.

Provides access to Figma files, components, comments, and webhooks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class FigmaClient:
    """
    Async Figma API client.

    Supports:
    - File access and metadata
    - Components and styles
    - Comments and annotations
    - Project management
    - Webhooks
    """

    BASE_URL = "https://api.figma.com/v1"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "FigmaClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    # -------------------------------------------------------------------------
    # User
    # -------------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        resp = await self.client.get("/me")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Files
    # -------------------------------------------------------------------------

    async def get_file(
        self,
        file_key: str,
        version: Optional[str] = None,
        depth: Optional[int] = None,
        geometry: Optional[str] = None,
        plugin_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a Figma file.

        Args:
            file_key: The file key (from URL)
            version: Specific version ID
            depth: Depth of nodes to return (1-4)
            geometry: Include geometry data ('paths')
            plugin_data: Specific plugin data to include

        Returns:
            File data including document tree
        """
        params: Dict[str, Any] = {}
        if version:
            params["version"] = version
        if depth:
            params["depth"] = depth
        if geometry:
            params["geometry"] = geometry
        if plugin_data:
            params["plugin_data"] = plugin_data

        resp = await self.client.get(f"/files/{file_key}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_file_nodes(
        self,
        file_key: str,
        ids: List[str],
        version: Optional[str] = None,
        depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get specific nodes from a file."""
        params: Dict[str, Any] = {"ids": ",".join(ids)}
        if version:
            params["version"] = version
        if depth:
            params["depth"] = depth

        resp = await self.client.get(f"/files/{file_key}/nodes", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_file_versions(
        self,
        file_key: str,
    ) -> Dict[str, Any]:
        """Get version history of a file."""
        resp = await self.client.get(f"/files/{file_key}/versions")
        resp.raise_for_status()
        return resp.json()

    async def get_images(
        self,
        file_key: str,
        ids: List[str],
        scale: float = 1.0,
        format: str = "png",
        svg_include_id: bool = False,
        svg_simplify_stroke: bool = True,
    ) -> Dict[str, Any]:
        """
        Render images from a file.

        Args:
            file_key: The file key
            ids: Node IDs to render
            scale: Image scale (0.01 to 4)
            format: Image format (jpg, png, svg, pdf)
            svg_include_id: Include node IDs in SVG
            svg_simplify_stroke: Simplify strokes in SVG

        Returns:
            URLs to rendered images
        """
        params = {
            "ids": ",".join(ids),
            "scale": scale,
            "format": format,
            "svg_include_id": str(svg_include_id).lower(),
            "svg_simplify_stroke": str(svg_simplify_stroke).lower(),
        }
        resp = await self.client.get(f"/images/{file_key}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_image_fills(
        self,
        file_key: str,
    ) -> Dict[str, Any]:
        """Get download links for images used as fills."""
        resp = await self.client.get(f"/files/{file_key}/images")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Components & Styles
    # -------------------------------------------------------------------------

    async def get_file_components(
        self,
        file_key: str,
    ) -> Dict[str, Any]:
        """Get all components in a file."""
        resp = await self.client.get(f"/files/{file_key}/components")
        resp.raise_for_status()
        return resp.json()

    async def get_file_component_sets(
        self,
        file_key: str,
    ) -> Dict[str, Any]:
        """Get all component sets in a file."""
        resp = await self.client.get(f"/files/{file_key}/component_sets")
        resp.raise_for_status()
        return resp.json()

    async def get_file_styles(
        self,
        file_key: str,
    ) -> Dict[str, Any]:
        """Get all styles in a file."""
        resp = await self.client.get(f"/files/{file_key}/styles")
        resp.raise_for_status()
        return resp.json()

    async def get_component(
        self,
        component_key: str,
    ) -> Dict[str, Any]:
        """Get a specific component by key."""
        resp = await self.client.get(f"/components/{component_key}")
        resp.raise_for_status()
        return resp.json()

    async def get_style(
        self,
        style_key: str,
    ) -> Dict[str, Any]:
        """Get a specific style by key."""
        resp = await self.client.get(f"/styles/{style_key}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Team Components & Styles
    # -------------------------------------------------------------------------

    async def get_team_components(
        self,
        team_id: str,
        page_size: int = 30,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all published components for a team."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/teams/{team_id}/components", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_team_component_sets(
        self,
        team_id: str,
        page_size: int = 30,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all published component sets for a team."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/teams/{team_id}/component_sets", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_team_styles(
        self,
        team_id: str,
        page_size: int = 30,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all published styles for a team."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/teams/{team_id}/styles", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------

    async def get_comments(
        self,
        file_key: str,
        as_md: bool = False,
    ) -> Dict[str, Any]:
        """Get all comments on a file."""
        params = {"as_md": str(as_md).lower()}
        resp = await self.client.get(f"/files/{file_key}/comments", params=params)
        resp.raise_for_status()
        return resp.json()

    async def post_comment(
        self,
        file_key: str,
        message: str,
        client_meta: Optional[Dict[str, Any]] = None,
        comment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a comment on a file.

        Args:
            file_key: The file key
            message: Comment text
            client_meta: Position metadata (x, y, node_id, node_offset)
            comment_id: Parent comment ID for replies

        Returns:
            Created comment
        """
        payload: Dict[str, Any] = {"message": message}
        if client_meta:
            payload["client_meta"] = client_meta
        if comment_id:
            payload["comment_id"] = comment_id

        resp = await self.client.post(f"/files/{file_key}/comments", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_comment(
        self,
        file_key: str,
        comment_id: str,
    ) -> Dict[str, Any]:
        """Delete a comment."""
        resp = await self.client.delete(f"/files/{file_key}/comments/{comment_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_comment_reactions(
        self,
        file_key: str,
        comment_id: str,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get reactions on a comment."""
        params = {}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(
            f"/files/{file_key}/comments/{comment_id}/reactions",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def post_comment_reaction(
        self,
        file_key: str,
        comment_id: str,
        emoji: str,
    ) -> Dict[str, Any]:
        """Add a reaction to a comment."""
        resp = await self.client.post(
            f"/files/{file_key}/comments/{comment_id}/reactions",
            json={"emoji": emoji},
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def get_team_projects(
        self,
        team_id: str,
    ) -> Dict[str, Any]:
        """Get all projects for a team."""
        resp = await self.client.get(f"/teams/{team_id}/projects")
        resp.raise_for_status()
        return resp.json()

    async def get_project_files(
        self,
        project_id: str,
        branch_data: bool = False,
    ) -> Dict[str, Any]:
        """Get all files in a project."""
        params = {"branch_data": str(branch_data).lower()}
        resp = await self.client.get(f"/projects/{project_id}/files", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def get_team_webhooks(
        self,
        team_id: str,
    ) -> Dict[str, Any]:
        """Get all webhooks for a team."""
        resp = await self.client.get(f"/webhooks/team/{team_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        team_id: str,
        event_type: str,
        endpoint: str,
        passcode: str,
        status: str = "ACTIVE",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            team_id: Team ID
            event_type: Event type (FILE_UPDATE, FILE_DELETE, FILE_VERSION_UPDATE,
                       LIBRARY_PUBLISH, FILE_COMMENT)
            endpoint: Webhook URL
            passcode: Secret for verification
            status: ACTIVE or PAUSED
            description: Optional description

        Returns:
            Created webhook
        """
        payload: Dict[str, Any] = {
            "event_type": event_type,
            "team_id": team_id,
            "endpoint": endpoint,
            "passcode": passcode,
            "status": status,
        }
        if description:
            payload["description"] = description

        resp = await self.client.post("/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_webhook(
        self,
        webhook_id: str,
        event_type: Optional[str] = None,
        endpoint: Optional[str] = None,
        passcode: Optional[str] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a webhook."""
        payload: Dict[str, Any] = {}
        if event_type:
            payload["event_type"] = event_type
        if endpoint:
            payload["endpoint"] = endpoint
        if passcode:
            payload["passcode"] = passcode
        if status:
            payload["status"] = status
        if description:
            payload["description"] = description

        resp = await self.client.put(f"/webhooks/{webhook_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        webhook_id: str,
    ) -> Dict[str, Any]:
        """Delete a webhook."""
        resp = await self.client.delete(f"/webhooks/{webhook_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_webhook(
        self,
        webhook_id: str,
    ) -> Dict[str, Any]:
        """Get a specific webhook."""
        resp = await self.client.get(f"/webhooks/{webhook_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_webhook_requests(
        self,
        webhook_id: str,
    ) -> Dict[str, Any]:
        """Get recent requests for a webhook (for debugging)."""
        resp = await self.client.get(f"/webhooks/{webhook_id}/requests")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def extract_file_key_from_url(self, url: str) -> Optional[str]:
        """Extract file key from a Figma URL."""
        # URL format: https://www.figma.com/file/{key}/{title}
        # or: https://www.figma.com/design/{key}/{title}
        import re

        patterns = [
            r"figma\.com/file/([a-zA-Z0-9]+)",
            r"figma\.com/design/([a-zA-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def flatten_nodes(
        self,
        node: Dict[str, Any],
        node_list: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Flatten a node tree into a list."""
        if node_list is None:
            node_list = []

        node_list.append(node)
        for child in node.get("children", []):
            self.flatten_nodes(child, node_list)

        return node_list

    def find_nodes_by_type(
        self,
        document: Dict[str, Any],
        node_type: str,
    ) -> List[Dict[str, Any]]:
        """Find all nodes of a specific type in a document."""
        all_nodes = self.flatten_nodes(document.get("document", {}))
        return [n for n in all_nodes if n.get("type") == node_type]

    def extract_text_content(
        self,
        document: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Extract all text content from a document."""
        text_nodes = self.find_nodes_by_type(document, "TEXT")
        return [
            {
                "id": n.get("id", ""),
                "name": n.get("name", ""),
                "characters": n.get("characters", ""),
            }
            for n in text_nodes
        ]
