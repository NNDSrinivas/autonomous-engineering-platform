"""Google Docs and Drive API client for AEP connector integration.

Uses existing Google OAuth tokens with extended scopes for Docs/Drive access.

Supports:
- Google Drive file listing and search
- Google Docs content extraction
- Google Sheets data access
- Google Slides content
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class GoogleDocsClient:
    """
    Google Docs/Drive API client for AEP NAVI integration.

    Requires OAuth scopes:
    - https://www.googleapis.com/auth/drive.readonly
    - https://www.googleapis.com/auth/documents.readonly
    - https://www.googleapis.com/auth/spreadsheets.readonly
    """

    DRIVE_API_URL = "https://www.googleapis.com/drive/v3"
    DOCS_API_URL = "https://docs.googleapis.com/v1"
    SHEETS_API_URL = "https://sheets.googleapis.com/v4"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("GoogleDocsClient initialized")

    async def __aenter__(self) -> "GoogleDocsClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a GET request."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Drive Methods
    # -------------------------------------------------------------------------

    async def list_files(
        self,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        fields: str = "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, parents, size)",
        order_by: str = "modifiedTime desc",
    ) -> Dict[str, Any]:
        """
        List files in Google Drive.

        Args:
            query: Drive search query (e.g., "mimeType='application/vnd.google-apps.document'")
            page_size: Number of results per page
            page_token: Token for pagination
            fields: Fields to include in response
            order_by: Sort order

        Returns:
            Files list with pagination info
        """
        params: Dict[str, Any] = {
            "pageSize": page_size,
            "fields": fields,
            "orderBy": order_by,
        }
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        data = await self._get(f"{self.DRIVE_API_URL}/files", params=params)
        files = data.get("files", [])
        logger.info("Google Drive files listed", count=len(files))
        return data

    async def list_documents(
        self,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List Google Docs documents.

        Args:
            page_size: Number of results per page
            page_token: Token for pagination

        Returns:
            Documents list
        """
        query = "mimeType='application/vnd.google-apps.document'"
        return await self.list_files(
            query=query, page_size=page_size, page_token=page_token
        )

    async def list_spreadsheets(
        self,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List Google Sheets spreadsheets.

        Args:
            page_size: Number of results per page
            page_token: Token for pagination

        Returns:
            Spreadsheets list
        """
        query = "mimeType='application/vnd.google-apps.spreadsheet'"
        return await self.list_files(
            query=query, page_size=page_size, page_token=page_token
        )

    async def list_presentations(
        self,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List Google Slides presentations.

        Args:
            page_size: Number of results per page
            page_token: Token for pagination

        Returns:
            Presentations list
        """
        query = "mimeType='application/vnd.google-apps.presentation'"
        return await self.list_files(
            query=query, page_size=page_size, page_token=page_token
        )

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """
        Get file metadata.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata
        """
        params = {
            "fields": "id, name, mimeType, modifiedTime, webViewLink, parents, size, description, owners"
        }
        return await self._get(f"{self.DRIVE_API_URL}/files/{file_id}", params=params)

    async def search_files(
        self,
        query: str,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Search files by name.

        Args:
            query: Search query
            page_size: Number of results

        Returns:
            Search results
        """
        search_query = f"name contains '{query}' and trashed=false"
        return await self.list_files(query=search_query, page_size=page_size)

    # -------------------------------------------------------------------------
    # Google Docs Methods
    # -------------------------------------------------------------------------

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get a Google Doc document.

        Args:
            document_id: Document ID

        Returns:
            Document content and metadata
        """
        doc = await self._get(f"{self.DOCS_API_URL}/documents/{document_id}")
        logger.info(
            "Google Doc fetched", document_id=document_id, title=doc.get("title")
        )
        return doc

    def extract_document_text(self, document: Dict[str, Any]) -> str:
        """
        Extract plain text from a Google Doc.

        Args:
            document: Google Docs document object

        Returns:
            Plain text content
        """
        content = document.get("body", {}).get("content", [])
        text_parts = []

        for element in content:
            paragraph = element.get("paragraph")
            if paragraph:
                for elem in paragraph.get("elements", []):
                    text_run = elem.get("textRun")
                    if text_run:
                        text = text_run.get("content", "")
                        text_parts.append(text)

            # Handle tables
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    row_text = []
                    for cell in row.get("tableCells", []):
                        cell_content = cell.get("content", [])
                        cell_text = self._extract_paragraph_text(cell_content)
                        row_text.append(cell_text)
                    text_parts.append(" | ".join(row_text))

        return "".join(text_parts)

    def _extract_paragraph_text(self, content: List[Dict[str, Any]]) -> str:
        """Extract text from paragraph content."""
        text_parts = []
        for element in content:
            paragraph = element.get("paragraph")
            if paragraph:
                for elem in paragraph.get("elements", []):
                    text_run = elem.get("textRun")
                    if text_run:
                        text_parts.append(text_run.get("content", ""))
        return "".join(text_parts).strip()

    def extract_document_headers(self, document: Dict[str, Any]) -> List[str]:
        """
        Extract headers/headings from a Google Doc.

        Args:
            document: Google Docs document object

        Returns:
            List of header texts
        """
        content = document.get("body", {}).get("content", [])
        headers = []

        for element in content:
            paragraph = element.get("paragraph")
            if paragraph:
                style = paragraph.get("paragraphStyle", {})
                named_style = style.get("namedStyleType", "")

                if named_style.startswith("HEADING"):
                    text = ""
                    for elem in paragraph.get("elements", []):
                        text_run = elem.get("textRun")
                        if text_run:
                            text += text_run.get("content", "")
                    if text.strip():
                        headers.append(text.strip())

        return headers

    # -------------------------------------------------------------------------
    # Google Sheets Methods
    # -------------------------------------------------------------------------

    async def get_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Get spreadsheet metadata.

        Args:
            spreadsheet_id: Spreadsheet ID

        Returns:
            Spreadsheet metadata
        """
        sheet = await self._get(f"{self.SHEETS_API_URL}/spreadsheets/{spreadsheet_id}")
        logger.info(
            "Google Sheet fetched",
            spreadsheet_id=spreadsheet_id,
            title=sheet.get("properties", {}).get("title"),
        )
        return sheet

    async def get_sheet_values(
        self,
        spreadsheet_id: str,
        range_name: str = "Sheet1",
    ) -> Dict[str, Any]:
        """
        Get values from a spreadsheet range.

        Args:
            spreadsheet_id: Spreadsheet ID
            range_name: A1 notation range (e.g., "Sheet1!A1:Z100")

        Returns:
            Values in the range
        """
        encoded_range = range_name.replace(" ", "%20")
        data = await self._get(
            f"{self.SHEETS_API_URL}/spreadsheets/{spreadsheet_id}/values/{encoded_range}"
        )
        values = data.get("values", [])
        logger.info(
            "Google Sheet values fetched",
            spreadsheet_id=spreadsheet_id,
            rows=len(values),
        )
        return data

    def extract_sheet_text(self, values_response: Dict[str, Any]) -> str:
        """
        Convert sheet values to plain text.

        Args:
            values_response: Response from get_sheet_values

        Returns:
            Tab-separated text representation
        """
        values = values_response.get("values", [])
        rows = []
        for row in values:
            rows.append("\t".join(str(cell) for cell in row))
        return "\n".join(rows)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_mime_type_name(self, mime_type: str) -> str:
        """
        Get human-readable name for Google Workspace mime types.

        Args:
            mime_type: Google mime type

        Returns:
            Human-readable name
        """
        types = {
            "application/vnd.google-apps.document": "Google Doc",
            "application/vnd.google-apps.spreadsheet": "Google Sheet",
            "application/vnd.google-apps.presentation": "Google Slides",
            "application/vnd.google-apps.form": "Google Form",
            "application/vnd.google-apps.drawing": "Google Drawing",
            "application/vnd.google-apps.folder": "Folder",
            "application/vnd.google-apps.site": "Google Site",
            "application/pdf": "PDF",
            "text/plain": "Text File",
            "text/html": "HTML File",
            "image/png": "PNG Image",
            "image/jpeg": "JPEG Image",
        }
        return types.get(mime_type, mime_type.split("/")[-1])

    async def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Get content from a Google Workspace file.

        Automatically handles different file types.

        Args:
            file_id: File ID

        Returns:
            Plain text content or None if unsupported
        """
        file_meta = await self.get_file(file_id)
        mime_type = file_meta.get("mimeType", "")

        if mime_type == "application/vnd.google-apps.document":
            doc = await self.get_document(file_id)
            return self.extract_document_text(doc)

        elif mime_type == "application/vnd.google-apps.spreadsheet":
            values = await self.get_sheet_values(file_id)
            return self.extract_sheet_text(values)

        else:
            logger.info(
                "Unsupported file type for content extraction", mime_type=mime_type
            )
            return None
