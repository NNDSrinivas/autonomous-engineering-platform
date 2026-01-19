"""
Base class for all connector services.

This provides a unified interface for all connector integrations
so NAVI can query and write to them consistently.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import logging
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)
connector_logger = structlog.get_logger(__name__)


@dataclass
class ToolResult:
    """Normalized result from any tool for NAVI agent."""

    output: str
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    items_synced: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    error: Optional[str] = None
    synced_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WriteResult:
    """Result of a write operation (create, update, delete)."""

    success: bool
    item_id: Optional[str] = None
    external_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@dataclass
class ConnectorItem:
    """Generic connector item representation."""

    id: str
    provider: str
    item_type: str
    external_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    url: Optional[str] = None
    assignee: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    external_created_at: Optional[datetime] = None
    external_updated_at: Optional[datetime] = None


class ConnectorServiceBase(ABC):
    """
    Base class for all connector services.

    Each connector (Linear, GitLab, Notion, etc.) should extend this class
    and implement the abstract methods.

    Usage:
        class LinearService(ConnectorServiceBase):
            PROVIDER = "linear"

            @classmethod
            async def sync_items(cls, db, connection, item_types):
                # Fetch from Linear API and store in DB
                ...

            @classmethod
            async def write_item(cls, db, user_id, item_type, action, data):
                # Create/update/delete item via Linear API
                ...
    """

    PROVIDER: str = ""  # Override in subclass: 'linear', 'github', 'notion', etc.

    # Item types this connector supports
    SUPPORTED_ITEM_TYPES: List[str] = []

    # Write operations that require approval
    WRITE_OPERATIONS: List[str] = ["create", "update", "delete", "comment"]

    @classmethod
    def get_connection(
        cls, db: Session, user_id: str, org_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get active connection for user/org from the connectors table.

        Returns connection dict with decrypted credentials if found.
        """
        try:
            # Query the connectors table for this provider and user
            result = db.execute(
                text(
                    """
                SELECT id, provider, name, config_json, secret_json,
                       workspace_root, user_id, org_id, last_synced_at,
                       sync_status, sync_error, created_at, updated_at
                FROM connectors
                WHERE provider = :provider
                AND (user_id = :user_id OR org_id = :org_id)
                ORDER BY updated_at DESC
                LIMIT 1
                """
                ),
                {"provider": cls.PROVIDER, "user_id": user_id, "org_id": org_id},
            ).fetchone()

            if not result:
                return None

            return {
                "id": result[0],
                "provider": result[1],
                "name": result[2],
                "config_json": result[3],
                "secret_json": result[4],
                "workspace_root": result[5],
                "user_id": result[6],
                "org_id": result[7],
                "last_synced_at": result[8],
                "sync_status": result[9],
                "sync_error": result[10],
                "created_at": result[11],
                "updated_at": result[12],
            }

        except Exception as e:
            connector_logger.error(
                "connector_base.get_connection.error",
                provider=cls.PROVIDER,
                user_id=user_id,
                error=str(e),
            )
            return None

    @classmethod
    def get_items(
        cls,
        db: Session,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        item_type: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConnectorItem]:
        """
        Query synced items from database.

        Args:
            db: Database session
            user_id: Filter by user
            org_id: Filter by organization
            item_type: Filter by type (issue, pr, page, etc.)
            assignee: Filter by assignee
            status: Filter by status
            search_query: Search in title/description
            limit: Max results
            offset: Pagination offset

        Returns:
            List of ConnectorItem objects
        """
        try:
            # Build query dynamically
            query = """
                SELECT id, provider, item_type, external_id, title, description,
                       status, url, assignee, data, created_at, updated_at,
                       external_created_at, external_updated_at
                FROM connector_items
                WHERE provider = :provider
            """
            params: Dict[str, Any] = {"provider": cls.PROVIDER}

            if user_id:
                query += " AND user_id = :user_id"
                params["user_id"] = user_id

            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id

            if item_type:
                query += " AND item_type = :item_type"
                params["item_type"] = item_type

            if assignee:
                query += " AND assignee = :assignee"
                params["assignee"] = assignee

            if status:
                query += " AND status = :status"
                params["status"] = status

            if search_query:
                query += " AND (title ILIKE :search OR description ILIKE :search)"
                params["search"] = f"%{search_query}%"

            query += " ORDER BY external_updated_at DESC NULLS LAST, updated_at DESC"
            query += " LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset

            result = db.execute(text(query), params).fetchall()

            items = []
            for row in result:
                items.append(
                    ConnectorItem(
                        id=str(row[0]),
                        provider=row[1],
                        item_type=row[2],
                        external_id=row[3],
                        title=row[4],
                        description=row[5],
                        status=row[6],
                        url=row[7],
                        assignee=row[8],
                        data=row[9] if row[9] else {},
                        created_at=row[10],
                        updated_at=row[11],
                        external_created_at=row[12],
                        external_updated_at=row[13],
                    )
                )

            connector_logger.info(
                "connector_base.get_items.success",
                provider=cls.PROVIDER,
                item_type=item_type,
                count=len(items),
            )

            return items

        except Exception as e:
            connector_logger.error(
                "connector_base.get_items.error",
                provider=cls.PROVIDER,
                error=str(e),
            )
            return []

    @classmethod
    def upsert_item(
        cls,
        db: Session,
        connector_id: int,
        item_type: str,
        external_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        url: Optional[str] = None,
        assignee: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        external_created_at: Optional[datetime] = None,
        external_updated_at: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Insert or update an item in connector_items table.

        Returns the item ID if successful, None otherwise.
        """
        try:
            # Use PostgreSQL's ON CONFLICT for upsert
            query = """
                INSERT INTO connector_items
                    (connector_id, provider, item_type, external_id, title,
                     description, status, url, assignee, user_id, org_id, data,
                     external_created_at, external_updated_at, updated_at)
                VALUES
                    (:connector_id, :provider, :item_type, :external_id, :title,
                     :description, :status, :url, :assignee, :user_id, :org_id,
                     :data::jsonb, :external_created_at, :external_updated_at, NOW())
                ON CONFLICT (connector_id, provider, item_type, external_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    url = EXCLUDED.url,
                    assignee = EXCLUDED.assignee,
                    data = EXCLUDED.data,
                    external_updated_at = EXCLUDED.external_updated_at,
                    updated_at = NOW()
                RETURNING id
            """

            import json

            result = db.execute(
                text(query),
                {
                    "connector_id": connector_id,
                    "provider": cls.PROVIDER,
                    "item_type": item_type,
                    "external_id": external_id,
                    "title": title,
                    "description": description,
                    "status": status,
                    "url": url,
                    "assignee": assignee,
                    "user_id": user_id,
                    "org_id": org_id,
                    "data": json.dumps(data or {}),
                    "external_created_at": external_created_at,
                    "external_updated_at": external_updated_at,
                },
            ).fetchone()

            db.commit()

            if result:
                return str(result[0])
            return None

        except Exception as e:
            db.rollback()
            connector_logger.error(
                "connector_base.upsert_item.error",
                provider=cls.PROVIDER,
                external_id=external_id,
                error=str(e),
            )
            return None

    @classmethod
    def update_sync_status(
        cls,
        db: Session,
        connector_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> bool:
        """Update the sync status of a connector."""
        try:
            db.execute(
                text(
                    """
                UPDATE connectors
                SET sync_status = :status,
                    sync_error = :error,
                    last_synced_at = CASE WHEN :status = 'success' THEN NOW() ELSE last_synced_at END,
                    updated_at = NOW()
                WHERE id = :connector_id
                """
                ),
                {"connector_id": connector_id, "status": status, "error": error},
            )
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            connector_logger.error(
                "connector_base.update_sync_status.error",
                provider=cls.PROVIDER,
                connector_id=connector_id,
                error=str(e),
            )
            return False

    @classmethod
    def get_credentials(cls, connection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Decrypt and return credentials from connection.

        Override this in subclass if you need custom credential handling.
        """
        try:
            from backend.core.crypto import decrypt_token

            secret_json = connection.get("secret_json")
            if not secret_json:
                return None

            import json

            if isinstance(secret_json, bytes):
                decrypted = decrypt_token(secret_json)
                return json.loads(decrypted)
            elif isinstance(secret_json, str):
                return json.loads(secret_json)
            else:
                return secret_json

        except Exception as e:
            connector_logger.error(
                "connector_base.get_credentials.error",
                provider=cls.PROVIDER,
                error=str(e),
            )
            return None

    @classmethod
    @abstractmethod
    async def sync_items(
        cls, db: Session, connection: Dict[str, Any], item_types: Optional[List[str]] = None
    ) -> SyncResult:
        """
        Sync items from external provider to database.

        Subclasses must implement this method to:
        1. Fetch data from external API using credentials from connection
        2. Store/update items in connector_items table
        3. Return SyncResult with stats

        Args:
            db: Database session
            connection: Connection dict with credentials
            item_types: Optional list of item types to sync (if None, sync all)

        Returns:
            SyncResult with success status and counts
        """
        pass

    @classmethod
    @abstractmethod
    async def write_item(
        cls,
        db: Session,
        user_id: str,
        item_type: str,
        action: str,
        data: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Write operation (create, update, delete, comment) to external provider.

        Subclasses must implement this method to:
        1. Get connection credentials
        2. Make API call to external provider
        3. Update local database
        4. Return WriteResult

        Args:
            db: Database session
            user_id: ID of user performing the action
            item_type: Type of item (issue, pr, page, etc.)
            action: Action to perform (create, update, delete, comment)
            data: Data for the operation
            org_id: Optional organization ID

        Returns:
            WriteResult with success status and item details
        """
        pass

    @classmethod
    def get_provider_capabilities(cls) -> Dict[str, Any]:
        """
        Return capabilities of this connector.

        Override in subclass to customize.
        """
        return {
            "provider": cls.PROVIDER,
            "supported_item_types": cls.SUPPORTED_ITEM_TYPES,
            "write_operations": cls.WRITE_OPERATIONS,
            "can_read": True,
            "can_write": True,
            "can_search": True,
        }


# -------------------------------------------------------------------------
# Context Builder for NAVI
# -------------------------------------------------------------------------

# Provider capability definitions
PROVIDER_CAPABILITIES = {
    # Project Management & Work Tracking
    "jira": {
        "name": "Jira",
        "category": "work_tracking",
        "read_capabilities": ["query issues", "get issue details", "list comments"],
        "write_capabilities": ["create issues", "add comments", "transition status", "assign issues"],
    },
    "linear": {
        "name": "Linear",
        "category": "project_management",
        "read_capabilities": ["query issues", "search issues", "list projects"],
        "write_capabilities": ["create issues", "add comments", "update status"],
    },
    "asana": {
        "name": "Asana",
        "category": "project_management",
        "read_capabilities": ["list tasks", "search tasks", "list projects"],
        "write_capabilities": ["create tasks", "complete tasks"],
    },
    "trello": {
        "name": "Trello",
        "category": "project_management",
        "read_capabilities": ["list boards", "list cards", "get card details"],
        "write_capabilities": ["create cards", "move cards"],
    },
    "clickup": {
        "name": "ClickUp",
        "category": "project_management",
        "read_capabilities": ["list tasks", "list spaces", "get task details"],
        "write_capabilities": ["create tasks", "update tasks"],
    },
    "monday": {
        "name": "Monday.com",
        "category": "project_management",
        "read_capabilities": ["list boards", "list items", "get item details"],
        "write_capabilities": ["create items"],
    },
    # Code & DevOps
    "github": {
        "name": "GitHub",
        "category": "code",
        "read_capabilities": ["query PRs", "query issues", "list repos", "get PR details"],
        "write_capabilities": ["create issues", "comment on PRs", "set labels", "create PRs"],
    },
    "gitlab": {
        "name": "GitLab",
        "category": "code",
        "read_capabilities": ["query merge requests", "query issues", "get pipeline status"],
        "write_capabilities": ["create merge requests", "add comments"],
    },
    "bitbucket": {
        "name": "Bitbucket",
        "category": "code",
        "read_capabilities": ["list PRs", "list repos", "get PR details"],
        "write_capabilities": ["create pull requests"],
    },
    "github_actions": {
        "name": "GitHub Actions",
        "category": "ci_cd",
        "read_capabilities": ["list workflows", "list runs", "get run status"],
        "write_capabilities": ["trigger workflows"],
    },
    "circleci": {
        "name": "CircleCI",
        "category": "ci_cd",
        "read_capabilities": ["list pipelines", "get pipeline status", "get job status"],
        "write_capabilities": ["trigger pipelines"],
    },
    "vercel": {
        "name": "Vercel",
        "category": "deployment",
        "read_capabilities": ["list projects", "list deployments", "get deployment status"],
        "write_capabilities": ["redeploy"],
    },
    # Documentation & Knowledge
    "notion": {
        "name": "Notion",
        "category": "documentation",
        "read_capabilities": ["search pages", "get page content", "list recent pages"],
        "write_capabilities": ["create pages"],
    },
    "confluence": {
        "name": "Confluence",
        "category": "wiki",
        "read_capabilities": ["search pages", "get page content", "list pages in space"],
        "write_capabilities": [],
    },
    "google_drive": {
        "name": "Google Drive",
        "category": "documentation",
        "read_capabilities": ["list files", "search files", "get file content"],
        "write_capabilities": [],
    },
    # Communication
    "slack": {
        "name": "Slack",
        "category": "chat",
        "read_capabilities": ["search messages", "list channel messages"],
        "write_capabilities": ["send messages"],
    },
    "discord": {
        "name": "Discord",
        "category": "chat",
        "read_capabilities": ["list channels", "get messages"],
        "write_capabilities": ["send messages"],
    },
    "teams": {
        "name": "Microsoft Teams",
        "category": "chat",
        "read_capabilities": ["list channels", "get messages"],
        "write_capabilities": [],
    },
    # Meetings & Calendar
    "zoom": {
        "name": "Zoom",
        "category": "meetings",
        "read_capabilities": ["list recordings", "get transcripts", "search recordings"],
        "write_capabilities": [],
    },
    "google_calendar": {
        "name": "Google Calendar",
        "category": "calendar",
        "read_capabilities": ["list events", "get event details", "get today's events"],
        "write_capabilities": [],
    },
    "meet": {
        "name": "Google Meet",
        "category": "meetings",
        "read_capabilities": ["list meetings", "get calendar events"],
        "write_capabilities": [],
    },
    "loom": {
        "name": "Loom",
        "category": "video",
        "read_capabilities": ["list videos", "search videos", "get video details"],
        "write_capabilities": [],
    },
    # Design
    "figma": {
        "name": "Figma",
        "category": "design",
        "read_capabilities": ["list files", "get file details", "get comments", "list projects"],
        "write_capabilities": ["add comments"],
    },
    # Monitoring & Observability
    "datadog": {
        "name": "Datadog",
        "category": "monitoring",
        "read_capabilities": ["list monitors", "get alerting monitors", "list incidents", "list dashboards"],
        "write_capabilities": ["mute monitors"],
    },
    "sentry": {
        "name": "Sentry",
        "category": "error_tracking",
        "read_capabilities": ["list issues", "get issue details", "list projects"],
        "write_capabilities": ["resolve issues"],
    },
    "pagerduty": {
        "name": "PagerDuty",
        "category": "incident_management",
        "read_capabilities": ["list incidents", "get on-call", "list services"],
        "write_capabilities": ["acknowledge incidents", "resolve incidents"],
    },
    # Security
    "snyk": {
        "name": "Snyk",
        "category": "security",
        "read_capabilities": ["list vulnerabilities", "list projects", "get security summary"],
        "write_capabilities": [],
    },
    "sonarqube": {
        "name": "SonarQube",
        "category": "code_quality",
        "read_capabilities": ["list projects", "list issues", "get quality gate", "get metrics"],
        "write_capabilities": [],
    },
}


def build_connector_context_for_navi(
    db: Session,
    user_id: str,
    org_id: Optional[str] = None,
) -> str:
    """
    Build the connector context block for NAVI's system prompt.

    This tells NAVI which services the user has connected so it can
    use the appropriate tools.

    Args:
        db: Database session
        user_id: User ID
        org_id: Optional organization ID

    Returns:
        Formatted context string with <navi_connected_services> block
    """
    try:
        from backend.services.connectors import list_connectors

        # Get user's connected services
        connected = list_connectors(db, user_id)

        # Build services list
        services = []
        connected_providers = {c["provider"].lower() for c in connected}

        # Add all known providers with their status
        for provider, info in PROVIDER_CAPABILITIES.items():
            if provider in connected_providers:
                services.append({
                    "provider": provider,
                    "name": info["name"],
                    "status": "connected",
                    "category": info["category"],
                    "capabilities": info["read_capabilities"] + info["write_capabilities"],
                })
            else:
                services.append({
                    "provider": provider,
                    "name": info["name"],
                    "status": "not_connected",
                    "category": info["category"],
                    "capabilities": [],
                })

        # Sort by status (connected first) then by name
        services.sort(key=lambda x: (x["status"] != "connected", x["name"]))

        import json

        context_data = {"services": services}
        context_json = json.dumps(context_data, indent=2)

        return f"<navi_connected_services>\n{context_json}\n</navi_connected_services>"

    except Exception as e:
        connector_logger.error(
            "build_connector_context.error",
            user_id=user_id,
            error=str(e),
        )
        return ""


def get_connected_providers(
    db: Session,
    user_id: str,
    org_id: Optional[str] = None,
) -> List[str]:
    """
    Get list of connected provider names for a user.

    Args:
        db: Database session
        user_id: User ID
        org_id: Optional organization ID

    Returns:
        List of connected provider names (e.g., ["jira", "github", "slack"])
    """
    try:
        from backend.services.connectors import list_connectors

        connected = list_connectors(db, user_id)
        return [c["provider"].lower() for c in connected]

    except Exception as e:
        connector_logger.error(
            "get_connected_providers.error",
            user_id=user_id,
            error=str(e),
        )
        return []
