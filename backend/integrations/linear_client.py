"""Linear GraphQL API client for AEP connector integration.

Linear uses a GraphQL API exclusively. This client provides
convenient methods for common operations.

Supports:
- Issues (list, get, create, update)
- Projects
- Teams
- Cycles (sprints)
- Users
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class LinearClient:
    """
    Linear GraphQL API client for AEP NAVI integration.
    """

    API_URL = "https://api.linear.app/graphql"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("LinearClient initialized")

    async def __aenter__(self) -> "LinearClient":
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
            "Authorization": self.access_token,
            "Content-Type": "application/json",
        }

    async def _query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self._client.post(self.API_URL, json=payload)
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            errors = data["errors"]
            error_msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise RuntimeError(f"Linear GraphQL error: {error_msg}")

        return data.get("data", {})

    # -------------------------------------------------------------------------
    # User Methods
    # -------------------------------------------------------------------------

    async def get_viewer(self) -> Dict[str, Any]:
        """
        Get the currently authenticated user.

        Returns:
            User information including id, name, email
        """
        query = """
        query {
            viewer {
                id
                name
                email
                displayName
                avatarUrl
                admin
                active
            }
        }
        """
        data = await self._query(query)
        user = data.get("viewer", {})
        logger.info("Linear viewer fetched", name=user.get("name"))
        return user

    # -------------------------------------------------------------------------
    # Team Methods
    # -------------------------------------------------------------------------

    async def list_teams(self, first: int = 50) -> List[Dict[str, Any]]:
        """
        List teams accessible to the authenticated user.

        Args:
            first: Number of teams to fetch

        Returns:
            List of team dictionaries
        """
        query = """
        query($first: Int!) {
            teams(first: $first) {
                nodes {
                    id
                    name
                    key
                    description
                    timezone
                    private
                    issueCount
                }
            }
        }
        """
        data = await self._query(query, {"first": first})
        teams = data.get("teams", {}).get("nodes", [])
        logger.info("Linear teams listed", count=len(teams))
        return teams

    async def get_team(self, team_id: str) -> Dict[str, Any]:
        """
        Get a single team by ID.

        Args:
            team_id: Team ID

        Returns:
            Team details
        """
        query = """
        query($id: String!) {
            team(id: $id) {
                id
                name
                key
                description
                timezone
                private
                issueCount
                members {
                    nodes {
                        id
                        name
                        email
                    }
                }
            }
        }
        """
        data = await self._query(query, {"id": team_id})
        return data.get("team", {})

    # -------------------------------------------------------------------------
    # Issue Methods
    # -------------------------------------------------------------------------

    async def list_issues(
        self,
        team_id: Optional[str] = None,
        first: int = 50,
        after: Optional[str] = None,
        filter_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List issues, optionally filtered by team.

        Args:
            team_id: Optional team ID to filter by
            first: Number of issues to fetch
            after: Cursor for pagination
            filter_state: Filter by state name (e.g., "In Progress", "Done")

        Returns:
            Dictionary with nodes (issues) and pageInfo
        """
        filter_parts = []
        if team_id:
            filter_parts.append(f'team: {{ id: {{ eq: "{team_id}" }} }}')
        if filter_state:
            filter_parts.append(f'state: {{ name: {{ eq: "{filter_state}" }} }}')

        filter_str = ", ".join(filter_parts)
        filter_clause = f"filter: {{ {filter_str} }}" if filter_parts else ""

        query = f"""
        query($first: Int!, $after: String) {{
            issues(first: $first, after: $after, {filter_clause}) {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    priority
                    priorityLabel
                    estimate
                    url
                    createdAt
                    updatedAt
                    state {{
                        id
                        name
                        type
                    }}
                    assignee {{
                        id
                        name
                        email
                    }}
                    creator {{
                        id
                        name
                    }}
                    team {{
                        id
                        name
                        key
                    }}
                    project {{
                        id
                        name
                    }}
                    cycle {{
                        id
                        name
                        number
                    }}
                    labels {{
                        nodes {{
                            id
                            name
                            color
                        }}
                    }}
                }}
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
            }}
        }}
        """
        variables: Dict[str, Any] = {"first": first}
        if after:
            variables["after"] = after

        data = await self._query(query, variables)
        issues_data = data.get("issues", {})
        issues = issues_data.get("nodes", [])
        logger.info("Linear issues listed", count=len(issues), team_id=team_id)
        return issues_data

    async def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Get a single issue by ID.

        Args:
            issue_id: Issue ID or identifier (e.g., "ABC-123")

        Returns:
            Issue details
        """
        query = """
        query($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                priorityLabel
                estimate
                url
                createdAt
                updatedAt
                state {
                    id
                    name
                    type
                }
                assignee {
                    id
                    name
                    email
                }
                creator {
                    id
                    name
                }
                team {
                    id
                    name
                    key
                }
                project {
                    id
                    name
                }
                cycle {
                    id
                    name
                    number
                }
                labels {
                    nodes {
                        id
                        name
                        color
                    }
                }
                comments {
                    nodes {
                        id
                        body
                        createdAt
                        user {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query, {"id": issue_id})
        return data.get("issue", {})

    async def create_issue(
        self,
        team_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        project_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new issue.

        Args:
            team_id: Team ID
            title: Issue title
            description: Issue description (markdown)
            priority: Priority (0=none, 1=urgent, 2=high, 3=normal, 4=low)
            assignee_id: User ID to assign
            project_id: Project ID
            cycle_id: Cycle ID
            label_ids: List of label IDs

        Returns:
            Created issue details
        """
        query = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """
        input_data: Dict[str, Any] = {
            "teamId": team_id,
            "title": title,
        }
        if description:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if project_id:
            input_data["projectId"] = project_id
        if cycle_id:
            input_data["cycleId"] = cycle_id
        if label_ids:
            input_data["labelIds"] = label_ids

        data = await self._query(query, {"input": input_data})
        result = data.get("issueCreate", {})
        if not result.get("success"):
            raise RuntimeError("Failed to create Linear issue")

        issue = result.get("issue", {})
        logger.info("Linear issue created", identifier=issue.get("identifier"))
        return issue

    async def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        state_id: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing issue.

        Args:
            issue_id: Issue ID
            title: New title
            description: New description
            state_id: New state ID
            priority: New priority
            assignee_id: New assignee ID

        Returns:
            Updated issue details
        """
        query = """
        mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    state {
                        name
                    }
                }
            }
        }
        """
        input_data: Dict[str, Any] = {}
        if title is not None:
            input_data["title"] = title
        if description is not None:
            input_data["description"] = description
        if state_id is not None:
            input_data["stateId"] = state_id
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id is not None:
            input_data["assigneeId"] = assignee_id

        data = await self._query(query, {"id": issue_id, "input": input_data})
        result = data.get("issueUpdate", {})
        if not result.get("success"):
            raise RuntimeError("Failed to update Linear issue")

        return result.get("issue", {})

    # -------------------------------------------------------------------------
    # Project Methods
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        team_id: Optional[str] = None,
        first: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List projects.

        Args:
            team_id: Optional team ID to filter by
            first: Number of projects to fetch

        Returns:
            List of project dictionaries
        """
        filter_clause = ""
        if team_id:
            filter_clause = f'filter: {{ teams: {{ id: {{ eq: "{team_id}" }} }} }}'

        query = f"""
        query($first: Int!) {{
            projects(first: $first, {filter_clause}) {{
                nodes {{
                    id
                    name
                    description
                    state
                    progress
                    startDate
                    targetDate
                    url
                    teams {{
                        nodes {{
                            id
                            name
                        }}
                    }}
                    lead {{
                        id
                        name
                    }}
                }}
            }}
        }}
        """
        data = await self._query(query, {"first": first})
        projects = data.get("projects", {}).get("nodes", [])
        logger.info("Linear projects listed", count=len(projects))
        return projects

    # -------------------------------------------------------------------------
    # Cycle Methods
    # -------------------------------------------------------------------------

    async def list_cycles(
        self,
        team_id: str,
        first: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List cycles (sprints) for a team.

        Args:
            team_id: Team ID
            first: Number of cycles to fetch

        Returns:
            List of cycle dictionaries
        """
        query = """
        query($teamId: String!, $first: Int!) {
            team(id: $teamId) {
                cycles(first: $first) {
                    nodes {
                        id
                        name
                        number
                        startsAt
                        endsAt
                        progress
                        completedIssueCountHistory
                        issueCountHistory
                    }
                }
            }
        }
        """
        data = await self._query(query, {"teamId": team_id, "first": first})
        cycles = data.get("team", {}).get("cycles", {}).get("nodes", [])
        logger.info("Linear cycles listed", team_id=team_id, count=len(cycles))
        return cycles

    async def get_active_cycle(self, team_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the currently active cycle for a team.

        Args:
            team_id: Team ID

        Returns:
            Active cycle or None
        """
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                activeCycle {
                    id
                    name
                    number
                    startsAt
                    endsAt
                    progress
                }
            }
        }
        """
        data = await self._query(query, {"teamId": team_id})
        return data.get("team", {}).get("activeCycle")

    # -------------------------------------------------------------------------
    # Webhook Methods
    # -------------------------------------------------------------------------

    async def create_webhook(
        self,
        url: str,
        team_id: Optional[str] = None,
        label: str = "AEP NAVI Webhook",
        resource_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            url: Webhook URL
            team_id: Optional team ID to scope webhook
            label: Webhook label
            resource_types: Resource types to subscribe to (Issue, Comment, Project, Cycle, etc.)

        Returns:
            Created webhook details
        """
        query = """
        mutation($input: WebhookCreateInput!) {
            webhookCreate(input: $input) {
                success
                webhook {
                    id
                    url
                    label
                    enabled
                }
            }
        }
        """
        input_data: Dict[str, Any] = {
            "url": url,
            "label": label,
        }
        if team_id:
            input_data["teamId"] = team_id
        if resource_types:
            input_data["resourceTypes"] = resource_types

        data = await self._query(query, {"input": input_data})
        result = data.get("webhookCreate", {})
        if not result.get("success"):
            raise RuntimeError("Failed to create Linear webhook")

        webhook = result.get("webhook", {})
        logger.info("Linear webhook created", webhook_id=webhook.get("id"))
        return webhook

    async def list_webhooks(self) -> List[Dict[str, Any]]:
        """
        List all webhooks.

        Returns:
            List of webhook dictionaries
        """
        query = """
        query {
            webhooks {
                nodes {
                    id
                    url
                    label
                    enabled
                    resourceTypes
                    team {
                        id
                        name
                    }
                }
            }
        }
        """
        data = await self._query(query)
        return data.get("webhooks", {}).get("nodes", [])
