"""
Google Drive content ingestor for NAVI memory system.

Ingests Google Docs, Sheets, and other Drive content
into the memory graph for semantic search.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import structlog

from sqlalchemy.orm import Session

from backend.integrations.gdocs_client import GoogleDocsClient
from backend.models.memory_graph import MemoryNode

logger = structlog.get_logger(__name__)


class GoogleDriveIngestor:
    """
    Ingests Google Drive content into NAVI memory system.

    Supports:
    - Google Docs (full text extraction)
    - Google Sheets (data table extraction)
    - File metadata for all Drive files
    """

    def __init__(
        self,
        client: GoogleDocsClient,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.client = client
        self.org_id = org_id
        self.user_id = user_id
        logger.info("GoogleDriveIngestor initialized", org_id=org_id, user_id=user_id)

    async def ingest_document(
        self,
        document_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Ingest a single Google Doc into memory.

        Args:
            document_id: Google Doc ID
            db: Database session

        Returns:
            Ingestion result
        """
        try:
            # Get document
            doc = await self.client.get_document(document_id)
            title = doc.get("title", "Untitled")

            # Extract content
            text = self.client.extract_document_text(doc)
            headers = self.client.extract_document_headers(doc)

            # Get file metadata for link
            file_meta = await self.client.get_file(document_id)
            web_link = file_meta.get("webViewLink", "")
            modified_time = file_meta.get("modifiedTime", "")

            # Create memory node
            node = MemoryNode(
                org_id=self.org_id,
                node_type="google_doc",
                title=title,
                text=text[:10000] if text else "",
                meta_json={
                    "document_id": document_id,
                    "url": web_link,
                    "modified_time": modified_time,
                    "headers": headers[:20],  # First 20 headers
                    "content_length": len(text) if text else 0,
                    "user_id": self.user_id,
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(node)
            db.commit()

            logger.info(
                "gdrive_ingestor.document_ingested",
                document_id=document_id,
                title=title,
                content_length=len(text) if text else 0,
            )

            return {
                "document_id": document_id,
                "title": title,
                "content_length": len(text) if text else 0,
                "headers_count": len(headers),
            }

        except Exception as exc:
            logger.error(
                "gdrive_ingestor.document_error",
                document_id=document_id,
                error=str(exc),
            )
            raise

    async def ingest_spreadsheet(
        self,
        spreadsheet_id: str,
        db: Session,
        max_rows: int = 1000,
    ) -> Dict[str, Any]:
        """
        Ingest a Google Sheet into memory.

        Args:
            spreadsheet_id: Spreadsheet ID
            db: Database session
            max_rows: Maximum rows to ingest per sheet

        Returns:
            Ingestion result
        """
        try:
            # Get spreadsheet metadata
            sheet = await self.client.get_spreadsheet(spreadsheet_id)
            title = sheet.get("properties", {}).get("title", "Untitled")
            sheets = sheet.get("sheets", [])

            # Get file metadata for link
            file_meta = await self.client.get_file(spreadsheet_id)
            web_link = file_meta.get("webViewLink", "")
            modified_time = file_meta.get("modifiedTime", "")

            total_rows = 0
            sheet_names = []

            for sheet_info in sheets:
                sheet_props = sheet_info.get("properties", {})
                sheet_name = sheet_props.get("title", "Sheet")
                sheet_names.append(sheet_name)

                try:
                    # Get sheet values
                    range_name = f"'{sheet_name}'!A1:Z{max_rows}"
                    values = await self.client.get_sheet_values(spreadsheet_id, range_name)
                    text = self.client.extract_sheet_text(values)
                    rows = len(values.get("values", []))
                    total_rows += rows

                    # Create memory node for each sheet with data
                    if text.strip():
                        node = MemoryNode(
                            org_id=self.org_id,
                            node_type="google_sheet",
                            title=f"{title} - {sheet_name}",
                            text=text[:10000],
                            meta_json={
                                "spreadsheet_id": spreadsheet_id,
                                "sheet_name": sheet_name,
                                "url": web_link,
                                "modified_time": modified_time,
                                "rows": rows,
                                "user_id": self.user_id,
                            },
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(node)

                except Exception as sheet_exc:
                    logger.warning(
                        "gdrive_ingestor.sheet_skipped",
                        spreadsheet_id=spreadsheet_id,
                        sheet_name=sheet_name,
                        error=str(sheet_exc),
                    )

            db.commit()

            logger.info(
                "gdrive_ingestor.spreadsheet_ingested",
                spreadsheet_id=spreadsheet_id,
                title=title,
                sheets=len(sheets),
                total_rows=total_rows,
            )

            return {
                "spreadsheet_id": spreadsheet_id,
                "title": title,
                "sheets": sheet_names,
                "total_rows": total_rows,
            }

        except Exception as exc:
            logger.error(
                "gdrive_ingestor.spreadsheet_error",
                spreadsheet_id=spreadsheet_id,
                error=str(exc),
            )
            raise

    async def ingest_drive(
        self,
        db: Session,
        document_limit: int = 50,
        spreadsheet_limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Ingest accessible Drive content.

        Args:
            db: Database session
            document_limit: Max documents to ingest
            spreadsheet_limit: Max spreadsheets to ingest

        Returns:
            Ingestion summary
        """
        try:
            documents_ingested = 0
            spreadsheets_ingested = 0

            # Ingest Google Docs
            docs_result = await self.client.list_documents(page_size=document_limit)
            docs = docs_result.get("files", [])

            for doc in docs[:document_limit]:
                doc_id = doc.get("id")
                if doc_id:
                    try:
                        await self.ingest_document(doc_id, db)
                        documents_ingested += 1
                    except Exception as exc:
                        logger.warning(
                            "gdrive_ingestor.doc_skipped",
                            document_id=doc_id,
                            error=str(exc),
                        )

            # Ingest Google Sheets
            sheets_result = await self.client.list_spreadsheets(page_size=spreadsheet_limit)
            sheets = sheets_result.get("files", [])

            for sheet in sheets[:spreadsheet_limit]:
                sheet_id = sheet.get("id")
                if sheet_id:
                    try:
                        await self.ingest_spreadsheet(sheet_id, db)
                        spreadsheets_ingested += 1
                    except Exception as exc:
                        logger.warning(
                            "gdrive_ingestor.sheet_skipped",
                            spreadsheet_id=sheet_id,
                            error=str(exc),
                        )

            logger.info(
                "gdrive_ingestor.drive_ingested",
                documents=documents_ingested,
                spreadsheets=spreadsheets_ingested,
            )

            return {
                "documents_ingested": documents_ingested,
                "spreadsheets_ingested": spreadsheets_ingested,
            }

        except Exception as exc:
            logger.error(
                "gdrive_ingestor.drive_error",
                error=str(exc),
            )
            raise

    async def search_and_ingest(
        self,
        query: str,
        db: Session,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Search Drive and ingest matching files.

        Args:
            query: Search query
            db: Database session
            limit: Max files to ingest

        Returns:
            Ingestion summary
        """
        try:
            search_result = await self.client.search_files(query, page_size=limit)
            files = search_result.get("files", [])

            files_ingested = 0
            skipped = 0

            for file in files:
                file_id = file.get("id")
                mime_type = file.get("mimeType", "")

                try:
                    if mime_type == "application/vnd.google-apps.document":
                        await self.ingest_document(file_id, db)
                        files_ingested += 1
                    elif mime_type == "application/vnd.google-apps.spreadsheet":
                        await self.ingest_spreadsheet(file_id, db)
                        files_ingested += 1
                    else:
                        # Ingest file metadata only
                        file_meta = await self.client.get_file(file_id)
                        node = MemoryNode(
                            org_id=self.org_id,
                            node_type="google_drive_file",
                            title=file_meta.get("name", "Untitled"),
                            text=file_meta.get("description", "") or f"Google Drive file: {file_meta.get('name')}",
                            meta_json={
                                "file_id": file_id,
                                "mime_type": mime_type,
                                "url": file_meta.get("webViewLink", ""),
                                "modified_time": file_meta.get("modifiedTime", ""),
                                "size": file_meta.get("size"),
                                "user_id": self.user_id,
                            },
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(node)
                        db.commit()
                        files_ingested += 1

                except Exception as exc:
                    logger.warning(
                        "gdrive_ingestor.file_skipped",
                        file_id=file_id,
                        error=str(exc),
                    )
                    skipped += 1

            logger.info(
                "gdrive_ingestor.search_ingested",
                query=query,
                ingested=files_ingested,
                skipped=skipped,
            )

            return {
                "query": query,
                "files_found": len(files),
                "files_ingested": files_ingested,
                "skipped": skipped,
            }

        except Exception as exc:
            logger.error(
                "gdrive_ingestor.search_error",
                query=query,
                error=str(exc),
            )
            raise


async def ingest_gdrive_for_user(
    access_token: str,
    org_id: Optional[str],
    user_id: Optional[str],
    db: Session,
    document_limit: int = 50,
    spreadsheet_limit: int = 20,
) -> Dict[str, Any]:
    """
    Convenience function to ingest Google Drive for a user.

    Args:
        access_token: Google OAuth access token
        org_id: Organization ID
        user_id: User ID
        db: Database session
        document_limit: Max documents to ingest
        spreadsheet_limit: Max spreadsheets to ingest

    Returns:
        Ingestion summary
    """
    async with GoogleDocsClient(access_token=access_token) as client:
        ingestor = GoogleDriveIngestor(
            client=client,
            org_id=org_id,
            user_id=user_id,
        )
        return await ingestor.ingest_drive(
            db=db,
            document_limit=document_limit,
            spreadsheet_limit=spreadsheet_limit,
        )
