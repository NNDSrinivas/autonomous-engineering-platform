"""
Google Drive service for NAVI connector integration.

Provides syncing and querying of Google Drive files and folders.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class GoogleDriveService(ConnectorServiceBase):
    """Service for Google Drive file management integration."""

    PROVIDER = "google_drive"
    SUPPORTED_ITEM_TYPES = ["file", "folder", "document", "spreadsheet"]
    WRITE_OPERATIONS = ["create_folder", "upload_file"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Google Drive files to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (file, folder, document)
            **kwargs: Additional args (query filter, etc.)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.google_drive_client import GoogleDriveClient
        from backend.core.config import settings

        config = connection.get("config", {})
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        expires_at = config.get("expires_at")

        if not access_token and not refresh_token:
            raise ValueError("Google Drive credentials not configured")

        user_id = connection.get("user_id")
        counts = {"file": 0}

        client = GoogleDriveClient(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        # Default query to get recent files
        query = kwargs.get("query", "trashed = false")
        files = await client.list_files(query=query, page_size=100)

        for f in files:
            file_id = f.get("id", "")
            name = f.get("name", "Untitled")
            mime_type = f.get("mimeType", "")

            # Determine item type from mime type
            if "folder" in mime_type:
                item_type = "folder"
            elif "document" in mime_type:
                item_type = "document"
            elif "spreadsheet" in mime_type:
                item_type = "spreadsheet"
            else:
                item_type = "file"

            cls.upsert_item(
                db=db,
                user_id=user_id,
                provider=cls.PROVIDER,
                item_type=item_type,
                external_id=file_id,
                title=name,
                url=f.get("webViewLink", ""),
                metadata={
                    "mime_type": mime_type,
                    "modified_time": f.get("modifiedTime"),
                    "created_time": f.get("createdTime"),
                },
            )
            counts["file"] += 1

        logger.info(
            "google_drive.sync_files",
            user_id=user_id,
            count=counts["file"],
        )

        return counts

    @classmethod
    async def list_files(
        cls,
        db,
        connection: Dict[str, Any],
        query: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Google Drive files.

        Args:
            db: Database session
            connection: Connector connection dict
            query: Drive query string (e.g., "name contains 'report'")
            max_results: Maximum results to return

        Returns:
            List of file dicts
        """
        from backend.integrations.google_drive_client import GoogleDriveClient
        from backend.core.config import settings

        config = connection.get("config", {})
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        expires_at = config.get("expires_at")

        if not access_token and not refresh_token:
            return []

        client = GoogleDriveClient(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        drive_query = query or "trashed = false"
        files = await client.list_files(query=drive_query, page_size=max_results)

        return [
            {
                "id": f.get("id", ""),
                "name": f.get("name", "Untitled"),
                "mime_type": f.get("mimeType", ""),
                "url": f.get("webViewLink", ""),
                "modified_time": f.get("modifiedTime", ""),
                "created_time": f.get("createdTime", ""),
            }
            for f in files
        ]

    @classmethod
    async def search_files(
        cls,
        db,
        connection: Dict[str, Any],
        search_term: str,
        file_type: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search Google Drive files by name or content.

        Args:
            db: Database session
            connection: Connector connection dict
            search_term: Search term
            file_type: Filter by type (document, spreadsheet, folder, etc.)
            max_results: Maximum results to return

        Returns:
            List of matching files
        """
        # Build query
        query_parts = [f"name contains '{search_term}'", "trashed = false"]

        if file_type:
            mime_type_map = {
                "document": "application/vnd.google-apps.document",
                "spreadsheet": "application/vnd.google-apps.spreadsheet",
                "presentation": "application/vnd.google-apps.presentation",
                "folder": "application/vnd.google-apps.folder",
                "pdf": "application/pdf",
            }
            if file_type in mime_type_map:
                query_parts.append(f"mimeType = '{mime_type_map[file_type]}'")

        query = " and ".join(query_parts)
        return await cls.list_files(
            db, connection, query=query, max_results=max_results
        )

    @classmethod
    async def get_file_content(
        cls,
        db,
        connection: Dict[str, Any],
        file_id: str,
    ) -> Optional[str]:
        """
        Get the text content of a Google Drive file.

        Args:
            db: Database session
            connection: Connector connection dict
            file_id: Google Drive file ID

        Returns:
            File content as text, or None if not available
        """
        from backend.integrations.google_drive_client import GoogleDriveClient
        from backend.core.config import settings

        config = connection.get("config", {})
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        expires_at = config.get("expires_at")

        if not access_token and not refresh_token:
            return None

        client = GoogleDriveClient(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        # First get file metadata to determine mime type
        files = await client.list_files(
            query=f"'{file_id}' in parents or id = '{file_id}'",
            page_size=1,
        )

        if not files:
            return None

        file_info = files[0]
        mime_type = file_info.get("mimeType", "")

        return await client.download_text(file_id, mime_type)

    @classmethod
    async def list_recent_files(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List recently modified Google Drive files.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of recent files
        """
        return await cls.list_files(
            db, connection, query="trashed = false", max_results=max_results
        )
