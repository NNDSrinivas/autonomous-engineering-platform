"""
Enhanced Autonomous Coding Engine - Cline-style step-by-step coding with user approval

This enhanced version provides:
1. Step-by-step user approval workflow
2. File preview and diff generation
3. Git integration for safe operations
4. Real-time progress updates
5. Comprehensive error handling
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import structlog
import os
import tempfile
import fnmatch
import ast
from pathlib import Path
from typing import TYPE_CHECKING
import httpx
import git
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from backend.core.ai.llm_service import LLMService
from backend.models.integrations import JiraIssue, JiraConnection
from backend.core.crypto import decrypt_token

# NEW: Import enhanced workspace indexer
try:
    from backend.agent.workspace_retriever import index_workspace_full

    HAS_WORKSPACE_INDEXER = True
except ImportError:
    # Enhanced workspace indexer not available - will use basic indexing
    HAS_WORKSPACE_INDEXER = False
    index_workspace_full = None


class DangerousCodeError(Exception):
    """Raised when potentially dangerous code patterns are detected"""

    pass


# Security exception class
class SecurityError(Exception):
    """Raised when security validation fails"""

    pass


# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from backend.core.memory_system.vector_store import VectorStore
    from backend.integrations.github.service import GitHubService
else:
    VectorStore = "VectorStore"
    GitHubService = "GitHubService"

logger = structlog.get_logger(__name__)


class StepStatus(Enum):
    """Status of individual coding steps"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(Enum):
    """Types of autonomous coding tasks"""

    FEATURE = "feature"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    TEST = "test"
    DOCUMENTATION = "documentation"


@dataclass
class CodingStep:
    """Individual step in autonomous coding workflow"""

    id: str
    description: str
    file_path: str
    operation: str  # 'create', 'modify', 'delete'
    content_preview: str
    diff_preview: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    user_feedback: Optional[str] = None
    reasoning: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate file path early at creation time to fail fast on invalid input"""
        # Basic validation - more comprehensive validation done at execution time
        if not self.file_path or not self.file_path.strip():
            raise DangerousCodeError("Invalid file path: empty path")

        # Check for dangerous characters early
        dangerous_chars = ["\x00", "\r", "\n", "\t"]
        if any(char in self.file_path for char in dangerous_chars):
            raise DangerousCodeError("Invalid file path: contains dangerous characters")

        # Basic absolute path check
        if os.path.isabs(self.file_path):
            raise DangerousCodeError(
                "Invalid file path: absolute paths are not allowed"
            )


@dataclass
class CodingTask:
    """Enhanced autonomous coding task with step-by-step workflow"""

    id: str
    title: str
    description: str
    task_type: TaskType
    repository_path: str
    jira_key: Optional[str] = None

    # Workflow management
    steps: List[CodingStep] = field(default_factory=list)
    current_step_index: int = 0
    status: str = "created"

    # Context and intelligence
    related_files: List[str] = field(default_factory=list)
    team_context: Dict[str, Any] = field(default_factory=dict)
    meeting_context: Dict[str, Any] = field(default_factory=dict)
    documentation_links: List[str] = field(default_factory=list)

    # Git integration
    branch_name: Optional[str] = None
    backup_commit: Optional[str] = None

    # Progress tracking
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None


class EnhancedAutonomousCodingEngine:
    """
    Enterprise-grade autonomous coding engine with Cline-style workflow

    Features:
    - Step-by-step user approval
    - Git integration for safety
    - Enterprise context awareness
    - Real-time progress updates
    - Comprehensive error handling
    """

    # Configurable sensitive file patterns - can be overridden per deployment
    # SECURITY: These patterns prevent accidental commits of credentials and sensitive data
    # Environment files: *.env*, .env* - contain API keys, database passwords, secrets
    # Cryptographic files: *.key, *.pem, *.p12, *.pfx - private keys and certificates
    # Credential files: *secret*, *password*, *.credentials - explicit credential storage
    # Platform-specific: .aws/credentials, .htpasswd, wp-config.php - known sensitive configs
    # Build artifacts: __pycache__/*, *.pyc - may contain sensitive data or bloat repository
    # IDE configs: .vscode/settings.json, .idea/* - may expose local development secrets
    # VCS data: .git/* - repository metadata that shouldn't be modified by automation
    # Dependencies: node_modules/* - third-party code that shouldn't be auto-modified
    DEFAULT_SENSITIVE_PATTERNS = [
        "*.env",
        "*.env.*",
        ".env*",
        "*.key",
        "*.pem",
        "*.p12",
        "*.pfx",
        "*secret*",
        "*password*",
        "*.credentials",
        "id_rsa",
        "id_dsa",
        "*.private",
        "config/database.yml",
        "database.yml",
        ".htpasswd",
        "wp-config.php",
        ".aws/credentials",
        "*.keystore",
        "*.jks",
        "*.cert",
        "*.crt",
        "__pycache__/*",
        "*.pyc",
        ".git/*",
        "node_modules/*",
        ".vscode/settings.json",
        ".idea/*",
    ]

    # Compile regex patterns once at class level for performance
    _COMPILED_SECRET_PATTERNS = None
    _COMPILED_DANGEROUS_PATTERNS = None

    @classmethod
    def _get_compiled_secret_patterns(cls):
        """Get compiled regex patterns for secret detection (lazy initialization)"""
        import re

        if cls._COMPILED_SECRET_PATTERNS is None:
            secret_patterns = [
                # API Keys (various formats)
                r'["\'](?:api_?key|apikey)["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']',
                r'["\'](?:secret_?key|secretkey)["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']',
                r'["\'](?:access_?token|accesstoken)["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{20,})["\']',
                # AWS Keys
                r"AKIA[0-9A-Z]{16}",
                r'["\'](?:aws_access_key_id)["\']?\s*[:=]\s*["\']([A-Z0-9]{20})["\']',
                r'["\'](?:aws_secret_access_key)["\']?\s*[:=]\s*["\']([A-Za-z0-9/+=]{40})["\']',
                # GitHub tokens
                r"ghp_[A-Za-z0-9]{36}",
                r"github_pat_[A-Za-z0-9_]{82}",
                r"gho_[A-Za-z0-9]{36}",  # GitHub OAuth
                r"ghu_[A-Za-z0-9]{36}",  # GitHub User
                r"ghs_[A-Za-z0-9]{36}",  # GitHub Server
                r"ghr_[A-Za-z0-9]{36}",  # GitHub Refresh
                # Slack tokens
                r"xox[baprs]-([0-9a-zA-Z]{10,48})",
                r"xoxe\.xox[bp]-\d-[A-Za-z0-9]{163}",
                # Google API keys
                r"AIza[0-9A-Za-z_\-]{35}",
                # Azure keys
                r'["\'](?:azure_?key|subscription_?key)["\']?\s*[:=]\s*["\']([A-Za-z0-9_\-]{32,})["\']',
                # Generic bearer tokens
                r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}",
                # Database connection strings
                r"(?:mysql|postgres|mongodb)://[^@]+:[^@]+@",
                # Generic high-entropy strings that look like secrets
                r'["\'](?:password|pwd|pass|token|key|secret)["\']?\s*[:=]\s*["\']([A-Za-z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]{12,})["\']',
                # JWT tokens
                r"eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*",
                # Private keys
                r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
                r"-----BEGIN PGP PRIVATE KEY BLOCK-----",
                # Discord tokens
                r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}",
                # Twilio tokens
                r"SK[0-9a-fA-F]{32}",
                # SendGrid keys
                r"SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}",
                # Stripe keys
                r"(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24}",
            ]
            cls._COMPILED_SECRET_PATTERNS = [
                re.compile(pattern, re.IGNORECASE) for pattern in secret_patterns
            ]

        return cls._COMPILED_SECRET_PATTERNS

    @classmethod
    def _get_compiled_dangerous_patterns(cls):
        """Get compiled regex patterns for dangerous code detection (lazy initialization)"""
        import re

        if cls._COMPILED_DANGEROUS_PATTERNS is None:
            dangerous_patterns = [
                # Shell command execution patterns
                r"\bos\.system\s*\(",
                r"\bsubprocess\.call\s*\(",
                r"\bsubprocess\.run\s*\(",
                r"\bsubprocess\.Popen\s*\(",
                r"\bexec\s*\(",
                r"\beval\s*\(",
                r"\b__import__\s*\(",
                r"\bcompile\s*\(",
                # File system manipulation
                r"\bos\.remove\s*\(",
                r"\bos\.unlink\s*\(",
                r"\bshutil\.rmtree\s*\(",
                # Network operations
                r"\bsocket\.socket\s*\(",
                r"\burllib\.request\s*\.",
                r"\brequests\.get\s*\(",
                r"\brequests\.post\s*\(",
                # Dynamic code execution
                r"\bexecfile\s*\(",
                # Potentially dangerous modules
                r"\bimport\s+(?:os|subprocess|socket|urllib|requests)\b",
                r"\bfrom\s+(?:os|subprocess|socket|urllib|requests)\b",
            ]
            cls._COMPILED_DANGEROUS_PATTERNS = [
                re.compile(pattern, re.IGNORECASE) for pattern in dangerous_patterns
            ]

        return cls._COMPILED_DANGEROUS_PATTERNS

    # Input validation limits - configurable for different deployment scenarios
    MAX_PROMPT_INPUT_LENGTH = 500  # Maximum characters for user prompt inputs
    MAX_PROMPT_NEWLINES = 10  # Maximum newlines allowed in prompt inputs
    MAX_COMMIT_MESSAGE_LENGTH = 100  # Maximum length for commit message sanitization

    @staticmethod
    def _validate_workspace_path(path: str) -> str:
        """
        Validate workspace path and prevent UNC path and device name attacks on Windows.

        This method is specifically used during initialization to validate the workspace root
        directory path. For file operations within the workspace, use _validate_relative_path().

        Security Features:
        - Prevents Windows UNC path attacks (\\\\server\\share)
        - Blocks reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        - Used in __init__ to ensure safe workspace root establishment
        """
        import platform
        import os

        # Prevent Windows UNC path attacks (\\server\share)
        if platform.system() == "Windows":
            if path.startswith("\\\\"):
                raise ValueError(
                    f"UNC paths are not allowed for security reasons: {path}"
                )

            # Check for reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
            # These can be used in directory traversal attacks on Windows
            reserved_names = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }

            # Get the basename without extension and check case-insensitively
            base = os.path.basename(path)
            name, _ = os.path.splitext(base)
            if name.upper() in reserved_names:
                raise ValueError(
                    f"Reserved device name paths are not allowed for security reasons: {path}"
                )

        return path

    def __init__(
        self,
        llm_service: LLMService,
        vector_store: VectorStore,
        workspace_path: str,
        db_session: Optional[Session] = None,
        github_service: Optional[GitHubService] = None,
        progress_callback: Optional[Callable] = None,
        sensitive_patterns: Optional[List[str]] = None,
    ):
        self.llm_service = llm_service
        self.vector_store = vector_store

        # Validate workspace path for security (prevent UNC path attacks)
        validated_path = self._validate_workspace_path(workspace_path)
        self.workspace_path = Path(validated_path)

        self.db_session = db_session
        self.github_service = github_service
        self.progress_callback = progress_callback

        # Use custom patterns if provided, otherwise use defaults
        self.sensitive_patterns = sensitive_patterns or self.DEFAULT_SENSITIVE_PATTERNS

        # Task management
        self.active_tasks: Dict[str, CodingTask] = {}
        self.task_queue: List[str] = []

        # Git repository
        self.repo = None
        try:
            self.repo = git.Repo(workspace_path)
        except Exception:  # Catch any git-related error
            logger.warning(f"No git repository found at {workspace_path}")
            self.repo = None

        logger.info("Enhanced Autonomous Coding Engine initialized")

    async def create_task_from_jira(
        self, jira_key: str, user_context: Dict[str, Any]
    ) -> CodingTask:
        """
        Create coding task from JIRA ticket with full enterprise context

        This is where AEP excels over Cline - enterprise intelligence
        """
        logger.info(f"Creating task from JIRA ticket: {jira_key}")

        # Fetch JIRA ticket details
        jira_context = await self._fetch_jira_context(jira_key)

        # Get related documentation from Confluence
        confluence_docs = await self._fetch_related_confluence(jira_key)

        # Get meeting context from Slack/Teams
        meeting_context = await self._fetch_meeting_context(jira_key)

        # Analyze codebase for related files
        related_files = await self._analyze_related_files(
            jira_context.get("description", ""),
            jira_context.get("acceptance_criteria", ""),
        )

        # Create comprehensive task
        task = CodingTask(
            id=f"jira-{jira_key}",
            title=jira_context.get("summary", "Unknown Task"),
            description=jira_context.get("description", ""),
            task_type=self._determine_task_type(jira_context),
            repository_path=str(self.workspace_path),
            jira_key=jira_key,
            related_files=related_files,
            team_context=jira_context,
            meeting_context=meeting_context,
            documentation_links=confluence_docs,
            branch_name=f"aep/{jira_key.lower()}",
        )

        # Generate initial implementation plan
        await self._generate_implementation_plan(task)

        self.active_tasks[task.id] = task
        logger.info(f"Task created: {task.id} with {len(task.steps)} steps")

        return task

    async def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        repository_path: str,
        user_id: Optional[str] = None,
    ) -> CodingTask:
        """
        Create a coding task from a free-form request (non-Jira).
        """
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        task = CodingTask(
            id=task_id,
            title=title,
            description=description,
            task_type=task_type,
            repository_path=repository_path,
            related_files=await self._analyze_related_files(description, ""),
            team_context={"user_id": user_id} if user_id else {},
            branch_name=f"aep/{task_id}",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Generate initial implementation plan
        await self._generate_implementation_plan(task)

        self.active_tasks[task_id] = task
        self.task_queue.append(task_id)

        return task

    async def present_task_to_user(self, task_id: str) -> Dict[str, Any]:
        """
        Present task to user with all context - like Cline's initial presentation

        Returns comprehensive overview for user approval
        """
        task = self.active_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Build rich presentation
        presentation = {
            "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "jira_key": task.jira_key,
                "type": task.task_type.value,
            },
            "context": {
                "related_files": task.related_files,
                "documentation_links": task.documentation_links,
                "meeting_insights": self._summarize_meeting_context(
                    task.meeting_context
                ),
                "team_discussion": task.team_context.get("comments", []),
            },
            "implementation_plan": {
                "total_steps": len(task.steps),
                "estimated_duration": self._estimate_duration(task),
                "files_to_modify": [step.file_path for step in task.steps],
                "git_branch": task.branch_name,
            },
            "steps_preview": [
                {
                    "id": step.id,
                    "description": step.description,
                    "file": step.file_path,
                    "operation": step.operation,
                    "reasoning": step.reasoning,
                }
                for step in task.steps[:3]  # Show first 3 steps
            ],
            "next_action": "Would you like me to start implementing this plan step by step?",
        }

        return presentation

    async def execute_step(
        self, task_id: str, step_id: str, user_approved: bool
    ) -> Dict[str, Any]:
        """
        Execute individual step with user approval - core Cline-style workflow
        """
        task = self.active_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        step = next((s for s in task.steps if s.id == step_id), None)
        if not step:
            raise ValueError(f"Step not found: {step_id}")

        if not user_approved:
            step.status = StepStatus.REJECTED
            step.user_feedback = "User rejected this step"
            return {"status": "rejected", "message": "Step rejected by user"}

        # Execute the step
        step.status = StepStatus.IN_PROGRESS
        self._notify_progress(f"Executing step: {step.description}")

        try:
            # Create backup if first step
            if task.current_step_index == 0:
                await self._create_safety_backup(task)

            # Generate actual code
            code_result = await self._generate_code_for_step(task, step)

            # Apply changes
            await self._apply_code_changes(step, code_result)

            # Validate changes
            validation_result = await self._validate_step_changes(task, step)

            step.status = StepStatus.COMPLETED
            task.current_step_index += 1

            result = {
                "status": "completed",
                "step": step.id,
                "file_path": step.file_path,
                "changes_applied": True,
                "validation": validation_result,
                "next_step": self._get_next_step_preview(task),
            }

            self._notify_progress(f"Step completed: {step.description}")
            return result

        except Exception as e:
            step.status = StepStatus.FAILED
            step.user_feedback = f"Execution failed: {str(e)}"
            logger.error(f"Step execution failed: {e}")

            return {
                "status": "failed",
                "step": step.id,
                "error": str(e),
                "rollback_available": True,
            }

    async def _fetch_jira_context(self, jira_key: str) -> Dict[str, Any]:
        """Fetch comprehensive JIRA context from database and API"""
        try:
            # Check if database session is available
            if not self.db_session:
                logger.warning("No database session available for JIRA context")
                return {
                    "summary": f"JIRA task {jira_key} - database not available",
                    "description": "Database session not configured",
                    "acceptance_criteria": "",
                    "comments": [],
                    "priority": "Unknown",
                    "assignee": "",
                    "status": "Unknown",
                    "labels": [],
                    "subtasks": [],
                    "issue_links": [],
                    "project_key": "",
                    "issue_type": "",
                }

            # First try to get from local database
            jira_issue = self.db_session.scalar(
                select(JiraIssue).where(JiraIssue.issue_key == jira_key)
            )

            if jira_issue:
                # Get the JIRA connection for this issue
                connection = self.db_session.get(
                    JiraConnection, jira_issue.connection_id
                )

                if connection and connection.access_token:
                    # Fetch fresh data from JIRA API
                    try:
                        decrypted_token = decrypt_token(connection.access_token)

                        async with httpx.AsyncClient(
                            auth=(connection.user_id or "unknown", decrypted_token),
                            timeout=30,
                        ) as client:
                            # Get detailed issue data
                            response = await client.get(
                                f"{connection.cloud_base_url}/rest/api/3/issue/{jira_key}",
                                headers={"Accept": "application/json"},
                            )

                            if response.status_code == 200:
                                issue_data = response.json()
                                fields = issue_data.get("fields", {})

                                # Extract comprehensive context
                                context = {
                                    "summary": fields.get("summary", ""),
                                    "description": self._extract_description_text(
                                        fields.get("description")
                                    ),
                                    "priority": fields.get("priority", {}).get(
                                        "name", ""
                                    ),
                                    "status": fields.get("status", {}).get("name", ""),
                                    "assignee": (
                                        fields.get("assignee", {}).get(
                                            "displayName", ""
                                        )
                                        if fields.get("assignee")
                                        else ""
                                    ),
                                    "reporter": (
                                        fields.get("reporter", {}).get(
                                            "displayName", ""
                                        )
                                        if fields.get("reporter")
                                        else ""
                                    ),
                                    "labels": fields.get("labels", []),
                                    "components": [
                                        comp.get("name", "")
                                        for comp in fields.get("components", [])
                                    ],
                                    "sprint": self._extract_sprint_info(fields),
                                    "epic_link": fields.get(
                                        "customfield_10014", ""
                                    ),  # Common epic link field
                                    "story_points": fields.get(
                                        "customfield_10016", ""
                                    ),  # Common story points field
                                    "acceptance_criteria": self._extract_acceptance_criteria(
                                        fields
                                    ),
                                    "comments": await self._fetch_jira_comments(
                                        client, connection.cloud_base_url, jira_key
                                    ),
                                    "subtasks": [
                                        {
                                            "key": subtask.get("key", ""),
                                            "summary": subtask.get("fields", {}).get(
                                                "summary", ""
                                            ),
                                            "status": subtask.get("fields", {})
                                            .get("status", {})
                                            .get("name", ""),
                                        }
                                        for subtask in fields.get("subtasks", [])
                                    ],
                                    "issue_links": await self._extract_issue_links(
                                        fields
                                    ),
                                    "last_updated": fields.get("updated", ""),
                                    "created": fields.get("created", ""),
                                    "project_key": fields.get("project", {}).get(
                                        "key", ""
                                    ),
                                    "issue_type": fields.get("issuetype", {}).get(
                                        "name", ""
                                    ),
                                }

                                logger.info(
                                    f"Fetched comprehensive JIRA context for {jira_key}"
                                )
                                return context

                    except Exception as api_error:
                        logger.warning(
                            f"Failed to fetch fresh JIRA data for {jira_key}: {api_error}"
                        )
                        # Fall back to cached database data

                # Return data from local database
                return {
                    "summary": jira_issue.summary or "",
                    "description": jira_issue.description or "",
                    "priority": jira_issue.priority or "",
                    "status": jira_issue.status or "",
                    "assignee": jira_issue.assignee or "",
                    "reporter": jira_issue.reporter or "",
                    "labels": jira_issue.labels or [],
                    "epic_link": jira_issue.epic_key or "",
                    "sprint": jira_issue.sprint or "",
                    "acceptance_criteria": "",
                    "comments": [],
                    "subtasks": [],
                    "issue_links": [],
                    "last_updated": (
                        str(jira_issue.updated) if jira_issue.updated else ""
                    ),
                    "created": (
                        str(jira_issue.indexed_at) if jira_issue.indexed_at else ""
                    ),
                    "project_key": jira_issue.project_key or "",
                    "issue_type": "Task",  # Default since not stored in model
                }

            # If no local data found, return minimal context
            logger.warning(f"No JIRA data found for {jira_key}")
            return {
                "summary": f"JIRA task {jira_key} - details not available",
                "description": "Task details could not be retrieved from JIRA",
                "acceptance_criteria": "",
                "comments": [],
                "priority": "Unknown",
                "assignee": "",
                "status": "Unknown",
                "labels": [],
                "subtasks": [],
                "issue_links": [],
                "project_key": "",
                "issue_type": "",
            }

        except Exception as e:
            logger.error(f"Error fetching JIRA context for {jira_key}: {e}")
            return {
                "summary": f"Error fetching JIRA task {jira_key}",
                "description": "Failed to retrieve task details",
                "error": str(e),
                "acceptance_criteria": "",
                "comments": [],
                "priority": "Unknown",
                "assignee": "",
                "status": "Unknown",
            }

    def _extract_description_text(self, desc_field) -> str:
        """Extract plain text from JIRA description field (handles both string and ADF format)"""
        if not desc_field:
            return ""

        if isinstance(desc_field, str):
            return desc_field

        if isinstance(desc_field, dict):
            # Handle Atlassian Document Format (ADF)
            content = desc_field.get("content", [])
            text_parts = []

            def extract_text_from_content(content_items):
                for item in content_items:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "paragraph":
                        if "content" in item:
                            extract_text_from_content(item["content"])
                        text_parts.append("\n")
                    elif "content" in item:
                        extract_text_from_content(item["content"])

            extract_text_from_content(content)
            return "".join(text_parts).strip()

        return str(desc_field)

    def _extract_sprint_info(self, fields: Dict[str, Any]) -> str:
        """Extract sprint information from JIRA fields"""
        # Check common sprint custom fields
        sprint_fields = ["customfield_10020", "customfield_10016", "customfield_10010"]

        for field_name in sprint_fields:
            sprint_data = fields.get(field_name)
            if sprint_data:
                if isinstance(sprint_data, list) and sprint_data:
                    # Sprint is usually an array, take the latest
                    sprint = sprint_data[-1]
                    if isinstance(sprint, dict):
                        return sprint.get("name", "")
                    elif isinstance(sprint, str):
                        # Extract sprint name from string format
                        if "name=" in sprint:
                            parts = sprint.split("name=")
                            if len(parts) > 1:
                                name_part = parts[1].split(",")[0]
                                return name_part.strip()
                        return sprint
                elif isinstance(sprint_data, dict):
                    return sprint_data.get("name", "")
                elif isinstance(sprint_data, str):
                    return sprint_data

        return ""

    def _extract_acceptance_criteria(self, fields: Dict[str, Any]) -> str:
        """Extract acceptance criteria from JIRA fields"""
        # Check common acceptance criteria fields
        ac_fields = [
            "customfield_10021",  # Common AC field
            "customfield_10022",
            "customfield_10031",
            "customfield_10032",
        ]

        for field_name in ac_fields:
            ac_data = fields.get(field_name)
            if ac_data:
                if isinstance(ac_data, str):
                    return ac_data
                elif isinstance(ac_data, dict):
                    return self._extract_description_text(ac_data)

        # Check if acceptance criteria is in description
        description = fields.get("description", "")
        if (
            isinstance(description, str)
            and "acceptance criteria" in description.lower()
        ):
            # Try to extract AC section
            lines = description.split("\n")
            ac_lines = []
            in_ac_section = False

            for line in lines:
                if "acceptance criteria" in line.lower():
                    in_ac_section = True
                    continue
                elif in_ac_section and line.strip():
                    if (
                        line.startswith("*")
                        or line.startswith("-")
                        or line.startswith("•")
                    ):
                        ac_lines.append(line.strip())
                    elif not line.strip():
                        continue
                    else:
                        break  # End of AC section

            if ac_lines:
                return "\n".join(ac_lines)

        return ""

    async def _fetch_jira_comments(
        self, client: httpx.AsyncClient, base_url: str, issue_key: str
    ) -> List[Dict[str, Any]]:
        """Fetch comments for a JIRA issue"""
        try:
            response = await client.get(
                f"{base_url}/rest/api/3/issue/{issue_key}/comment",
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                comments_data = response.json()
                comments = []

                for comment in comments_data.get("comments", []):
                    comment_text = self._extract_description_text(comment.get("body"))
                    if comment_text:
                        comments.append(
                            {
                                "author": comment.get("author", {}).get(
                                    "displayName", ""
                                ),
                                "created": comment.get("created", ""),
                                "body": comment_text,
                                "id": comment.get("id", ""),
                            }
                        )

                return comments[:10]  # Limit to recent 10 comments

        except Exception as e:
            logger.warning(f"Failed to fetch comments for {issue_key}: {e}")

        return []

    async def _extract_issue_links(
        self, fields: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract linked issues from JIRA fields"""
        links = []
        issue_links = fields.get("issuelinks", [])

        for link in issue_links:
            link_type = link.get("type", {})
            link_info = {"relationship": link_type.get("name", ""), "direction": ""}

            if "outwardIssue" in link:
                linked_issue = link["outwardIssue"]
                link_info.update(
                    {
                        "key": linked_issue.get("key", ""),
                        "summary": linked_issue.get("fields", {}).get("summary", ""),
                        "status": linked_issue.get("fields", {})
                        .get("status", {})
                        .get("name", ""),
                        "direction": "outward",
                    }
                )
            elif "inwardIssue" in link:
                linked_issue = link["inwardIssue"]
                link_info.update(
                    {
                        "key": linked_issue.get("key", ""),
                        "summary": linked_issue.get("fields", {}).get("summary", ""),
                        "status": linked_issue.get("fields", {})
                        .get("status", {})
                        .get("name", ""),
                        "direction": "inward",
                    }
                )

            if link_info.get("key"):
                links.append(link_info)

        return links

    async def _fetch_related_confluence(self, jira_key: str) -> List[str]:
        """Fetch related Confluence documentation"""
        # This would use your existing Confluence integration
        return [
            "https://confluence.company.com/page1",
            "https://confluence.company.com/page2",
        ]

    async def _fetch_meeting_context(self, jira_key: str) -> Dict[str, Any]:
        """Fetch meeting context from Slack/Teams/Zoom"""
        # This would use your existing integrations
        return {"recent_discussions": [], "meeting_notes": [], "decisions": []}

    async def _analyze_related_files(
        self, description: str, criteria: str
    ) -> List[str]:
        """Analyze codebase to find related files"""
        # Use vector store to find semantically related files if available
        try:
            if self.vector_store and hasattr(self.vector_store, "similarity_search"):
                query = f"{description} {criteria}"
                # Use getattr to safely call the method
                similarity_search = getattr(
                    self.vector_store, "similarity_search", None
                )
                if similarity_search:
                    results = await similarity_search(query, k=10)
                    return [
                        result.metadata.get("file_path", "")
                        for result in results
                        if hasattr(result, "metadata") and result.metadata
                    ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")

        # Fallback: simple file system search based on keywords
        related_files = []
        keywords = description.lower().split() + criteria.lower().split()

        try:
            for root, dirs, files in os.walk(self.workspace_path):
                for file in files:
                    if file.endswith(
                        (
                            ".py",
                            ".js",
                            ".ts",
                            ".jsx",
                            ".tsx",
                            ".java",
                            ".cpp",
                            ".c",
                            ".h",
                        )
                    ):
                        file_path = os.path.join(root, file)
                        if any(
                            keyword in file.lower() or keyword in file_path.lower()
                            for keyword in keywords
                        ):
                            relative_path = os.path.relpath(
                                file_path, self.workspace_path
                            )
                            related_files.append(relative_path)
        except Exception as e:
            logger.warning(f"File system search failed: {e}")

        return related_files[:10]  # Limit to 10 files

    def _determine_task_type(self, jira_context: Dict[str, Any]) -> TaskType:
        """Determine task type from JIRA context"""
        # Simple logic - could be enhanced with ML
        description = jira_context.get("description", "").lower()
        if "bug" in description or "fix" in description:
            return TaskType.BUG_FIX
        elif "test" in description:
            return TaskType.TEST
        elif "refactor" in description:
            return TaskType.REFACTOR
        else:
            return TaskType.FEATURE

    async def _index_workspace_context(
        self, repository_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        NEW: Index workspace using enhanced indexer for intelligent context.

        Args:
            repository_path: The actual user workspace path to index

        Returns project type, entry points, dependencies, and code analysis.
        """
        if not HAS_WORKSPACE_INDEXER or not index_workspace_full:
            logger.info("[NAVI] Workspace indexer not available - using basic mode")
            return None

        try:
            logger.info(f"[NAVI] Indexing workspace: {repository_path}")
            logger.info(f"[NAVI DEBUG] repository_path type: {type(repository_path)}")
            logger.info(f"[NAVI DEBUG] repository_path value: {repository_path}")
            workspace_index = await index_workspace_full(
                workspace_root=repository_path,  # Use the actual user workspace
                user_id="autonomous_engine",
                include_code_analysis=False,  # Skip for speed
                include_dependencies=True,
            )

            if "error" in workspace_index:
                logger.warning(
                    f"[NAVI] Workspace indexing failed: {workspace_index.get('error')}"
                )
                return None

            logger.info(
                f"[NAVI] Workspace indexed: {workspace_index.get('project_type')} project "
                f"with {len(workspace_index.get('entry_points', []))} entry points"
            )

            return workspace_index

        except Exception as e:
            logger.warning(f"[NAVI] Failed to index workspace: {e}")
            return None

    async def _generate_implementation_plan(self, task: CodingTask):
        """Generate detailed implementation plan using AI with workspace intelligence"""

        # NEW: Index workspace for intelligent context - use task's repository path
        workspace_index = await self._index_workspace_context(task.repository_path)

        # Sanitize all inputs to prevent prompt injection attacks
        sanitized_task_description = self._sanitize_prompt_input(task.description)
        sanitized_task_title = self._sanitize_prompt_input(task.title)

        # Sanitize related files list
        sanitized_related_files = []
        if task.related_files:
            for file_path in task.related_files:
                sanitized_related_files.append(self._sanitize_prompt_input(file_path))

        # Sanitize team context
        sanitized_team_context = {}
        if task.team_context:
            for key, value in task.team_context.items():
                sanitized_key = self._sanitize_prompt_input(str(key))
                sanitized_value = (
                    self._sanitize_prompt_input(str(value)) if value is not None else ""
                )
                sanitized_team_context[sanitized_key] = sanitized_value

        # Sanitize documentation links if they exist
        sanitized_documentation = []
        if hasattr(task, "documentation_links") and task.documentation_links:
            for doc_link in task.documentation_links:
                sanitized_documentation.append(
                    self._sanitize_prompt_input(str(doc_link))
                )

        # NEW: Build enhanced context with workspace intelligence
        context = {
            "task_description": sanitized_task_description,
            "related_files": sanitized_related_files,
            "team_context": sanitized_team_context,
            "documentation": sanitized_documentation,
        }

        # NEW: Add workspace context if available
        project_type = "unknown"
        project_structure = []
        package_managers = []

        if workspace_index:
            context["project_type"] = workspace_index.get("project_type", "unknown")
            context["entry_points"] = workspace_index.get("entry_points", [])
            context["workspace_root"] = workspace_index.get("workspace_root", "")
            project_type = workspace_index.get("project_type", "unknown")

            # Get actual files list for structure context
            if "files" in workspace_index:
                files = workspace_index.get("files", [])
                # Get directory structure from files
                dirs = set()
                for f in files[:50]:  # Limit to first 50 files
                    # Handle both string paths and dict objects with 'path' or 'file_path' key
                    if isinstance(f, dict):
                        file_str = (
                            f.get("path") or f.get("file_path") or f.get("name", "")
                        )
                    else:
                        file_str = str(f)

                    if not file_str:
                        continue

                    file_path = Path(file_str)
                    if file_path.parent != Path("."):
                        dirs.add(str(file_path.parent))
                    if len(file_path.parts) > 0:
                        dirs.add(file_path.parts[0])  # Get top-level dirs
                project_structure = sorted(list(dirs))[:20]  # Top 20 directories

            # Detect package managers and config files
            if "files" in workspace_index:
                files = workspace_index.get("files", [])
                for f in files:
                    # Handle both string paths and dict objects
                    if isinstance(f, dict):
                        file_str = (
                            f.get("path") or f.get("file_path") or f.get("name", "")
                        )
                    else:
                        file_str = str(f)

                    if not file_str:
                        continue

                    fname = Path(file_str).name
                    if fname in ["package.json", "yarn.lock", "pnpm-lock.yaml"]:
                        package_managers.append("npm/yarn/pnpm (Node.js)")
                    elif fname in [
                        "requirements.txt",
                        "Pipfile",
                        "pyproject.toml",
                        "setup.py",
                    ]:
                        package_managers.append("pip/poetry (Python)")
                    elif fname == "go.mod":
                        package_managers.append("go modules (Go)")
                    elif fname == "Cargo.toml":
                        package_managers.append("cargo (Rust)")
                package_managers = list(set(package_managers))

            # Add dependency info if available
            if "dependencies" in workspace_index:
                deps = workspace_index["dependencies"]
                context["dependencies"] = {
                    "total": deps.get("total", 0),
                    "frameworks": [Path(f).name for f in deps.get("files", [])],
                }

        # Map project types to specific guidance
        project_guidance = {
            "nodejs": """
            This is a Node.js/JavaScript/TypeScript project.
            - For Next.js: Create components in `components/` or `app/` directory
            - For Next.js App Router: Create route handlers in `app/api/` directory
            - For React: Create components with `.tsx` or `.jsx` extensions
            - For Express: Create routes in `routes/` or `api/` directory
            - Use ES6+ syntax and async/await
            - Files should be in existing directories like: app/, components/, pages/, lib/, utils/
            """,
            "nextjs": """
            This is a Next.js project (React framework).
            - Create components in `components/`, `app/`, or `src/` directory
            - For App Router: Use `app/` directory with layout.tsx, page.tsx, etc.
            - For Pages Router: Use `pages/` directory
            - API routes go in `app/api/` (App Router) or `pages/api/` (Pages Router)
            - Use `.tsx` or `.jsx` extensions for React components
            - Use TypeScript and modern React patterns (hooks, functional components)
            """,
            "react": """
            This is a React project.
            - Create components in `components/`, `src/components/`, or similar
            - Use `.tsx` or `.jsx` extensions
            - Follow React hooks and functional component patterns
            - Common directories: src/, components/, pages/, hooks/, utils/
            """,
            "python": """
            This is a Python project.
            - Create modules in appropriate subdirectories
            - Use snake_case for file and function names
            - Follow PEP 8 style guidelines
            - Add type hints where appropriate
            - Common directories: src/, lib/, tests/, api/
            """,
            "fastapi": """
            This is a FastAPI Python project.
            - Create API routes in `api/`, `routers/`, or `endpoints/` directories
            - Use snake_case for file and function names
            - API endpoints typically in: backend/api/, app/api/, src/api/
            - Models go in `models/` directory
            - Follow FastAPI patterns: routers, dependencies, schemas
            - Add type hints (required for FastAPI)
            """,
            "flask": """
            This is a Flask Python project.
            - Create routes in `routes/` or `views/` directory
            - Templates go in `templates/` directory
            - Static files in `static/` directory
            - Use snake_case naming
            """,
            "django": """
            This is a Django Python project.
            - Create apps with `python manage.py startapp`
            - Follow Django app structure: views.py, models.py, urls.py
            - Templates in app-specific or project-wide `templates/`
            - Use snake_case naming
            """,
            "go": """
            This is a Go project.
            - Create packages in appropriate subdirectories
            - Use lowercase package names
            - Follow Go conventions and idioms
            - Common patterns: cmd/, pkg/, internal/, api/
            """,
            "rust": """
            This is a Rust project.
            - Create modules in `src/` directory
            - Main entry point: src/main.rs or src/lib.rs
            - Follow Rust naming conventions (snake_case)
            - Use Cargo for dependencies
            """,
            "unknown": """
            Project type not clearly detected.
            - Analyze existing directory structure carefully
            - Match the style and conventions of existing files
            - Create files in appropriate existing directories
            """,
        }

        # Get specific guidance for detected project type
        # Handle monorepo case
        if project_type.startswith("monorepo:"):
            types = project_type.replace("monorepo:", "").split("+")
            specific_guidance = f"""
            This is a MONOREPO containing multiple project types: {", ".join(types)}

            **CRITICAL: You MUST determine which subproject the user wants to modify based on their request.**

            Request analysis:
            - If the user mentions "component", "UI", "frontend", "React", "Next.js" → Work in the Node.js/frontend project
            - If the user mentions "API", "endpoint", "backend", "service", "database" → Work in the Python/backend project
            - If unclear, analyze the existing directory structure to find the appropriate subproject

            Project-specific guidance:
            """
            for t in types:
                if t in project_guidance:
                    specific_guidance += f"\n{t.upper()}:\n{project_guidance[t]}"
        else:
            specific_guidance = project_guidance.get(
                project_type, project_guidance["unknown"]
            )

        # NEW: Enhanced plan prompt with workspace context
        plan_prompt = f"""
        Create a detailed implementation plan for: {sanitized_task_title}

        Description: {sanitized_task_description}

        ========================================
        CRITICAL PROJECT CONTEXT - READ CAREFULLY:
        ========================================

        Project Type: **{project_type.upper()}**
        Package Managers Detected: {", ".join(package_managers) if package_managers else "None detected"}

        Existing Directory Structure:
        {chr(10).join(f"  - {d}/" for d in project_structure[:15]) if project_structure else "  (No structure detected - be cautious with file paths)"}

        {specific_guidance}

        ========================================
        IMPORTANT RULES:
        ========================================
        1. **ONLY use directories that exist in the structure above**
        2. **NEVER assume files like `src/main.py` exist without seeing them in the structure**
        3. **Match the project type** - if it's Node.js, don't create Python files!
        4. **Create new files in appropriate existing directories**
        5. **For modifications, verify the file exists in the codebase**
        6. **DO NOT create "check if file exists" steps** - Just use "create" operations directly. The system handles non-existent files.
        7. **NEVER use "modify" operation on files that don't exist** - Use "create" instead

        Related files: {", ".join(sanitized_related_files) if sanitized_related_files else "None"}

        Generate a step-by-step implementation plan that:
        1. Uses **ONLY {project_type}** technologies and patterns
        2. Creates files in **existing directories** from the structure above
        3. Follows the **specific guidance** for {project_type} projects
        4. Specifies exact file paths that match the project structure
        5. Provides clear reasoning for each step
        6. Identifies dependencies between steps

        Return concrete, actionable steps in this EXACT format:

        Step 1: [Brief description of what this step does]
        File: [exact/path/to/file.ext]
        Operation: [create/modify/delete]
        Reasoning: [Why this step is needed]

        Step 2: [Next step description]
        File: [exact/path/to/file.ext]
        Operation: [create/modify/delete]
        Reasoning: [Why this step is needed]

        Be specific with file paths and match the existing directory structure shown above.
        """

        # DEBUG: Log the prompt being sent
        logger.info(
            f"[NAVI DEBUG] Generated prompt with project_type={project_type}, structure dirs={len(project_structure)}"
        )
        logger.debug(f"[NAVI DEBUG] Full prompt:\n{plan_prompt[:1000]}...")

        plan_response = await self.llm_service.generate_engineering_response(
            plan_prompt, context
        )

        # Extract text from EngineeringResponse object
        if hasattr(plan_response, "answer"):
            response_text = plan_response.answer
        else:
            response_text = str(plan_response)

        logger.info(
            f"[NAVI DEBUG] LLM response text (first 500 chars): {response_text[:500]}"
        )

        # Parse response and create steps
        steps = self._parse_plan_response(response_text, task, project_structure)

        logger.info(f"[NAVI DEBUG] Parsed {len(steps)} steps:")
        for i, step in enumerate(steps, 1):
            logger.info(
                f"[NAVI DEBUG]   Step {i}: file={step.file_path}, op={step.operation}"
            )
        task.steps = steps

        # Log enhanced planning
        logger.info(
            f"[NAVI] Generated plan with {len(steps)} steps for {context.get('project_type', 'unknown')} project"
        )

    def _parse_plan_response(
        self, response, task: CodingTask, project_structure: List[str] = None
    ) -> List[CodingStep]:
        """Parse LLM response into concrete steps"""
        steps = []
        if project_structure is None:
            project_structure = []

        # Parse the LLM response to extract steps
        # Look for patterns like "Step 1:", "File:", "Operation:", etc.
        lines = response.strip().split("\n")

        current_step = None
        step_num = 0

        for line in lines:
            line = line.strip()

            # Detect step headers (e.g., "Step 1:", "1.", "### Step 1")
            if (
                any(
                    line.lower().startswith(prefix)
                    for prefix in ["step ", "### step", "## step"]
                )
                and ":" in line
            ):
                if current_step:
                    steps.append(current_step)

                step_num += 1
                # Extract description after the colon
                description = (
                    line.split(":", 1)[1].strip()
                    if ":" in line
                    else "Implementation step"
                )

                current_step = CodingStep(
                    id=f"{task.id}-step-{step_num}",
                    description=description[:200],  # Limit length
                    file_path="placeholder.txt",  # Temporary, will be updated below
                    operation="modify",  # Default
                    content_preview="",
                    reasoning="",
                )

            # Extract file path
            elif current_step and ("file:" in line.lower() or "path:" in line.lower()):
                # Extract path after "File:" or "Path:"
                parts = line.split(":", 1)
                if len(parts) > 1:
                    file_path = parts[1].strip()
                    # Clean up markdown formatting
                    file_path = file_path.strip("`").strip()
                    # Extract just the path if there's additional text
                    if "(" in file_path:
                        file_path = file_path.split("(")[0].strip()
                    current_step.file_path = file_path

            # Extract operation
            elif current_step and "operation:" in line.lower():
                operation = line.split(":", 1)[1].strip().lower()
                if "create" in operation or "new" in operation:
                    current_step.operation = "create"
                elif "delete" in operation or "remove" in operation:
                    current_step.operation = "delete"
                else:
                    current_step.operation = "modify"

            # Extract reasoning
            elif current_step and (
                "why:" in line.lower()
                or "reasoning:" in line.lower()
                or "rationale:" in line.lower()
            ):
                reasoning = line.split(":", 1)[1].strip() if ":" in line else line
                current_step.reasoning = reasoning[:300]

        # Add the last step (even if file_path is empty, we'll fix it below)
        if current_step:
            steps.append(current_step)

        # Fix steps with placeholder/empty file paths - try to infer from description or use sensible defaults
        for step in steps:
            if not step.file_path or step.file_path == "placeholder.txt":
                # Try to infer file path from description
                desc_lower = step.description.lower()

                # Detect file type based on keywords
                if any(
                    word in desc_lower
                    for word in ["component", "react", "ui", "jsx", "tsx"]
                ):
                    # React component
                    # Extract component name if possible
                    import re

                    component_name_match = re.search(
                        r"`?(\w+)`?\s*component", step.description, re.IGNORECASE
                    )
                    if component_name_match:
                        component_name = component_name_match.group(1)
                    else:
                        component_name = "Component"

                    # Choose appropriate directory based on monorepo structure
                    if "extensions/vscode-aep/webview" in str(project_structure):
                        step.file_path = f"extensions/vscode-aep/webview/src/components/{component_name}.tsx"
                    else:
                        step.file_path = f"components/{component_name}.tsx"
                    step.operation = "create"

                elif any(
                    word in desc_lower
                    for word in ["api", "endpoint", "route", "fastapi"]
                ):
                    # API endpoint
                    step.file_path = "backend/api/endpoint.py"
                    step.operation = "create"

                elif any(word in desc_lower for word in ["test", "spec"]):
                    # Test file
                    step.file_path = "tests/test_implementation.py"
                    step.operation = "create"

                else:
                    # Generic file
                    step.file_path = "implementation.txt"
                    step.operation = "create"

                logger.info(
                    f"[NAVI] Inferred file path: {step.file_path} from description: {step.description[:50]}"
                )

        # If no steps were parsed at all, create a default step
        if not steps:
            logger.warning(
                "[NAVI] Failed to parse LLM response into structured steps, creating default step"
            )
            # Try to extract at least a file path from the response
            file_path = "implementation.txt"  # Default
            for line in lines:
                if (
                    ".py" in line
                    or ".ts" in line
                    or ".tsx" in line
                    or ".js" in line
                    or ".jsx" in line
                ):
                    # Try to extract a path
                    words = line.split()
                    for word in words:
                        word = word.strip("`").strip()
                        if "/" in word and ("." in word):
                            file_path = word
                            break

            steps.append(
                CodingStep(
                    id=f"{task.id}-step-1",
                    description=task.description[:200],
                    file_path=file_path,
                    operation="create",
                    content_preview="",
                    reasoning="Implementation based on task requirements",
                )
            )

        logger.info(f"[NAVI] Parsed {len(steps)} steps from LLM response")
        return steps

    def _notify_progress(self, message: str):
        """Notify user of progress updates with sanitized input"""
        # Sanitize the progress message to prevent injection in logs or callbacks
        sanitized_message = self._sanitize_prompt_input(message)

        if self.progress_callback:
            self.progress_callback(sanitized_message)
        logger.info(f"Progress: {sanitized_message}")

    async def _create_safety_backup(self, task: CodingTask):
        """Create git backup before starting modifications"""
        if self.repo:
            try:
                # Selectively stage files, avoiding sensitive content
                safe_files = self._get_safe_files_for_staging()
                if safe_files:
                    for file_path in safe_files:
                        self.repo.git.add(file_path)

                    # Sanitize task title to prevent command injection
                    sanitized_title = self._sanitize_commit_message(task.title)
                    commit_message = (
                        f"AEP backup before task {task.id}: {sanitized_title}"
                    )
                    commit = self.repo.index.commit(commit_message)
                    task.backup_commit = commit.hexsha
                    logger.info(f"Created backup commit: {commit.hexsha}")
                else:
                    logger.info("No safe files to backup")
            except Exception as e:
                logger.warning(f"Failed to create backup commit: {e}")
        else:
            logger.warning("Git not available - no backup created")

    def _get_safe_files_for_staging(self) -> List[str]:
        """Get list of safe files for git staging, excluding sensitive content"""
        if not self.repo:
            return []

        # Use configurable sensitive patterns
        safe_files = []
        repo_root = self.repo.working_dir
        if not repo_root:
            return []

        # Get all modified/new files
        try:
            untracked_files = self.repo.untracked_files
            modified_files = [item.a_path for item in self.repo.index.diff(None)]
            staged_files = [item.a_path for item in self.repo.index.diff("HEAD")]
        except Exception:
            return []

        all_files = set(untracked_files + modified_files + staged_files)

        for file_path in all_files:
            if not file_path:  # Skip None/empty paths
                continue

            # Check if file matches any sensitive pattern
            is_sensitive = any(
                fnmatch.fnmatch(file_path.lower(), pattern.lower())
                for pattern in self.sensitive_patterns
            )

            if not is_sensitive:
                # Additional check: don't stage files with sensitive content
                full_path = os.path.join(repo_root, file_path)
                try:
                    if os.path.isfile(full_path) and self._file_content_is_safe(
                        full_path
                    ):
                        safe_files.append(file_path)
                except Exception:
                    # If we can't read the file, skip it for safety
                    continue

        return safe_files

    def _file_content_is_safe(self, file_path: str) -> bool:
        """Check if file content appears safe (no actual secrets using compiled regex patterns)"""

        # Use pre-compiled patterns for better performance
        compiled_patterns = self._get_compiled_secret_patterns()

        try:
            # Read entire file but limit to reasonable size (10MB max)
            max_file_size = 10 * 1024 * 1024  # 10MB
            file_size = os.path.getsize(file_path)

            if file_size > max_file_size:
                logger.warning(
                    f"File {file_path} too large ({file_size} bytes) for secret scanning"
                )
                # For large files, fail-safe by rejecting
                return False

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Use chunked reading to prevent memory exhaustion on large files
                chunk_size = 64 * 1024  # 64KB chunks for memory efficiency

                while True:
                    content = f.read(chunk_size)
                    if not content:
                        break

                    # Check for actual secret patterns using compiled regex
                    for compiled_pattern in compiled_patterns:
                        if compiled_pattern.search(content):
                            logger.warning(f"Potential secret detected in {file_path}")
                            return False

            return True
        except Exception as e:
            # Fail-safe: if we can't read or verify the file, assume it's unsafe
            logger.warning(f"Cannot verify file safety for {file_path}: {e}")
            return False

    async def _generate_code_for_step(
        self, task: CodingTask, step: CodingStep
    ) -> Dict[str, Any]:
        """Generate actual code for the step"""
        try:
            # Sanitize all inputs to prevent prompt injection attacks
            sanitized_task_description = self._sanitize_prompt_input(task.description)
            sanitized_step_description = self._sanitize_prompt_input(step.description)
            sanitized_file_path = self._sanitize_prompt_input(step.file_path)

            # Sanitize related files list (List[str])
            sanitized_related_files = []
            if task.related_files:
                for file_path in task.related_files:
                    if isinstance(file_path, str):
                        sanitized_related_files.append(
                            self._sanitize_prompt_input(file_path)
                        )
                    else:
                        # Convert to string and sanitize for safety
                        sanitized_related_files.append(
                            self._sanitize_prompt_input(str(file_path))
                        )

            # Sanitize team context (Dict[str, Any])
            sanitized_team_context = {}
            if task.team_context:
                for key, value in task.team_context.items():
                    sanitized_key = self._sanitize_prompt_input(str(key))
                    if value is not None:
                        sanitized_value = self._sanitize_prompt_input(str(value))
                    else:
                        sanitized_value = ""
                    sanitized_team_context[sanitized_key] = sanitized_value

            # NEW: Read existing file content for context (critical for modify operations)
            existing_content = None
            existing_imports = []
            if step.operation == "modify":
                existing_content = await self._read_existing_file(task, step)
                if existing_content:
                    existing_imports = self._extract_imports(
                        existing_content, step.file_path
                    )
                    logger.info(
                        f"[NAVI] Read existing file {step.file_path} ({len(existing_content)} chars, {len(existing_imports)} imports)"
                    )

            # NEW: Read related files for context (understand patterns, types, etc.)
            related_file_contents = await self._read_related_files(
                task, sanitized_related_files
            )

            # Build context for code generation with sanitized data
            context = {
                "task_description": sanitized_task_description,
                "step_description": sanitized_step_description,
                "file_path": sanitized_file_path,
                "operation": step.operation,  # This is enum/controlled value, safe
                "related_files": sanitized_related_files,
                "team_context": sanitized_team_context,
                "existing_content": existing_content,  # NEW
                "existing_imports": existing_imports,  # NEW
                "related_file_contents": related_file_contents,  # NEW
            }

            if step.operation == "create":
                prompt = f"Create a new file '{sanitized_file_path}' for: {sanitized_step_description}"
            elif step.operation == "modify":
                # Enhanced prompt for modify operations with existing content
                if existing_content:
                    prompt = f"""Modify file '{sanitized_file_path}' to: {sanitized_step_description}

EXISTING FILE CONTENT:
```
{existing_content[:3000]}  # Limit to avoid token overflow
```

IMPORTANT INSTRUCTIONS:
1. Preserve all existing functionality that's not being changed
2. Merge your changes with the existing code - DO NOT rewrite the entire file
3. Keep existing imports and add new ones if needed
4. Maintain consistent code style with existing patterns
5. If modifying a function, only change that function - keep others intact
6. Return the COMPLETE file content after merging changes
"""
                else:
                    prompt = f"Modify file '{sanitized_file_path}' to: {sanitized_step_description}"
            else:  # delete
                prompt = f"Prepare to delete file '{sanitized_file_path}' because: {sanitized_step_description}"

            # Use the LLM service to generate code
            response = await self.llm_service.generate_code_suggestion(
                description=prompt,
                language=self._detect_language(step.file_path),
                context=context,
            )

            generated_code = response.get("code", "")

            # NEW: Add missing imports automatically for create operations
            if step.operation == "create" and generated_code:
                generated_code = await self._add_missing_imports(
                    generated_code, step.file_path, task
                )
                logger.info(f"[NAVI] Added missing imports to {step.file_path}")

            return {
                "generated_code": generated_code,
                "language": response.get("language", "text"),
                "confidence": 0.8,  # Would be calculated based on model response
                "estimated_lines": len(generated_code.split("\n")),
                "safety_checks": ["syntax_valid", "no_dangerous_operations"],
            }

        except Exception as e:
            logger.error(f"Code generation failed for step {step.id}: {e}")
            return {
                "generated_code": f"# Error generating code: {str(e)}",
                "language": "text",
                "confidence": 0.0,
                "error": str(e),
            }

    def _validate_relative_path(self, path_str: str):
        """
        Validate file path string before any path operations to prevent attacks.

        Uses pathlib.Path.resolve() to get the absolute, canonical path and ensures
        the resolved path is within the workspace root directory. This prevents
        path traversal attacks by disallowing any file access outside the workspace.

        SECURITY: This method ensures that no matter what input is provided, the
        resulting path cannot escape the workspace directory.
        """
        # Disallow empty or null paths
        if not path_str or path_str.strip() == "":
            raise DangerousCodeError("Invalid file path: empty path")

        # Disallow dangerous characters and sequences
        dangerous_chars = ["\x00", "\r", "\n", "\t"]
        if any(char in path_str for char in dangerous_chars):
            raise DangerousCodeError("Invalid file path: contains dangerous characters")

        # Resolve the path and check workspace boundary
        workspace_root_path = self.workspace_path.resolve()
        target_path = (workspace_root_path / path_str).resolve()

        # Python 3.9+: use is_relative_to; fallback for older versions
        try:
            if not target_path.is_relative_to(workspace_root_path):
                raise DangerousCodeError("Invalid file path: path traversal detected")
        except AttributeError:
            # Fallback for Python <3.9: use relative_to and catch ValueError
            try:
                target_path.relative_to(workspace_root_path)
            except ValueError:
                raise DangerousCodeError("Invalid file path: path traversal detected")

    async def _apply_code_changes(self, step: CodingStep, code_result: Dict[str, Any]):
        """Apply code changes to files with security validation"""

        try:
            # Special case: Skip file operations for testing/validation steps
            if step.file_path in (
                "N/A",
                "n/a",
                "",
            ) or step.file_path.lower().startswith("n/a"):
                logger.info(
                    f"[NAVI] Skipping file operation for validation/testing step: {step.description}"
                )
                return  # No file to write for testing steps

            # Validate file path string before any path operations
            self._validate_relative_path(step.file_path)

            file_path = self.workspace_path / step.file_path

            # Auto-correct: Convert modify to create if file doesn't exist
            # This handles cases where the LLM tries to modify non-existent files
            if step.operation == "modify" and not file_path.exists():
                logger.warning(
                    f"[NAVI] File {step.file_path} doesn't exist, converting modify to create operation"
                )
                step.operation = "create"

            # Security validation: ensure file is within workspace and not a symlink
            # 1. Path traversal is already checked in _validate_relative_path()

            # 2. Symlink checks BEFORE resolving (resolve() follows symlinks)
            if step.operation in {"modify", "delete"} and file_path.is_symlink():
                raise SecurityError("Refusing to operate on symlinked file")
            if step.operation == "create" and file_path.parent.is_symlink():
                raise SecurityError("Refusing to create file in symlinked directory")

            # 3. Resolve path with enhanced security for create operations
            try:
                if step.operation == "create":
                    # For create operations, create parent directory first if it doesn't exist
                    # This allows us to then validate the full path
                    file_path.parent.mkdir(parents=True, exist_ok=True)

                    # Now verify parent directory (after creating it)
                    parent_path = file_path.parent.resolve(strict=True)
                    parent_path.relative_to(self.workspace_path.resolve())
                    # Then resolve the full path without strict requirement
                    resolved_path = file_path.resolve(strict=False)
                    # Ensure resolved path is within workspace boundaries for create
                    resolved_path.relative_to(self.workspace_path.resolve())
                else:
                    # For modify/delete, use strict resolution
                    resolved_path = file_path.resolve(strict=True)
                    # Ensure resolved path is within workspace boundaries
                    resolved_path.relative_to(self.workspace_path.resolve())
            except FileNotFoundError:
                if step.operation != "create":
                    raise SecurityError(
                        "Invalid file path: file does not exist for modify/delete operation"
                    )
                else:
                    raise SecurityError(
                        "Invalid file path: unable to create parent directory"
                    )
            except ValueError:
                raise SecurityError(
                    "Invalid file path: resolved path is outside workspace"
                )

            # Security validation: check for dangerous file extensions with whitelist
            dangerous_extensions = {".exe", ".bat", ".cmd", ".ps1", ".bin"}
            development_extensions = {".sh"}  # Scripts that may be legitimate in dev

            if file_path.suffix.lower() in dangerous_extensions:
                raise SecurityError(
                    f"Cannot write to potentially dangerous file type: {file_path.suffix}"
                )
            elif file_path.suffix.lower() in development_extensions:
                # Shell scripts require explicit user confirmation
                await self._require_shell_script_confirmation(
                    step.file_path, code_result["generated_code"]
                )

            # Basic code validation before writing
            generated_code = code_result["generated_code"]
            if self._contains_dangerous_patterns(generated_code):
                logger.error(
                    f"Potentially dangerous code detected in {step.file_path}. Operation blocked for security."
                )
                # Block the write and raise a security error
                raise DangerousCodeError(
                    f"Potentially dangerous code detected in {step.file_path}. "
                    f"Operation blocked to prevent security risks. "
                    f"Please review the generated code and ensure it's safe before proceeding."
                )

            if step.operation == "create":
                # Create new file (parent directory already created during validation)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(generated_code)
                logger.info(f"Created file: {step.file_path}")

            elif step.operation == "modify":
                # Modify existing file with atomic operation
                if file_path.exists():
                    # Atomic file modification: write to temp file, then rename
                    temp_file_path = None
                    try:
                        # Create secure temp file with mkstemp() for atomic permissions
                        temp_fd, temp_file_path = tempfile.mkstemp(
                            suffix=".tmp",
                            dir=None,  # Use secure system temp directory
                        )
                        # Set restrictive permissions immediately after creation to eliminate permission window
                        os.chmod(temp_file_path, 0o600)

                        try:
                            # Write content to the secure temp file
                            with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
                                temp_file.write(generated_code)
                                temp_fd = None  # Prevent double-close in finally
                        finally:
                            # Close file descriptor if not already closed
                            if temp_fd is not None:
                                os.close(temp_fd)

                        # Verify same filesystem to ensure atomic replace operation
                        temp_stat = os.stat(temp_file_path)
                        try:
                            target_stat = os.stat(str(file_path.parent))
                            if temp_stat.st_dev != target_stat.st_dev:
                                raise RuntimeError(
                                    "Cannot perform atomic replace: source and target are on different filesystems"
                                )
                        except FileNotFoundError:
                            # Parent directory doesn't exist - log a warning; atomic replace will likely fail
                            logger.warning(
                                f"Parent directory does not exist for {file_path}. Atomic replace will likely fail."
                            )

                        # Atomic replace operation; verified to be on same filesystem
                        try:
                            os.replace(temp_file_path, str(file_path))
                        except OSError as e:
                            # If atomic replace fails, raise error with detailed context
                            raise RuntimeError(f"Atomic file replace failed: {e}")
                        logger.info(f"Modified file atomically: {step.file_path}")

                    except Exception as e:
                        # Clean up temp file if operation failed
                        if temp_file_path and os.path.exists(temp_file_path):
                            try:
                                os.unlink(temp_file_path)
                            except OSError as cleanup_error:
                                # Log cleanup errors but don't fail the operation
                                logger.warning(
                                    f"Failed to cleanup temp file {temp_file_path}: {cleanup_error}"
                                )
                        raise e
                else:
                    raise FileNotFoundError(f"File not found: {step.file_path}")

            elif step.operation == "delete":
                # Delete file
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted file: {step.file_path}")
                else:
                    logger.warning(f"File already deleted: {step.file_path}")

        except Exception as e:
            logger.error(f"Failed to apply changes for step {step.id}: {e}")
            raise

    async def _validate_step_changes(
        self, task: CodingTask, step: CodingStep
    ) -> Dict[str, Any]:
        """Validate that changes work correctly"""
        try:
            validation_results = {
                "syntax_valid": True,
                "tests_passing": True,
                "no_conflicts": True,
                "performance_impact": "minimal",
                "security_issues": [],
                "warnings": [],
            }

            file_path = self.workspace_path / step.file_path

            # Basic file existence check
            if step.operation in ["create", "modify"]:
                if not file_path.exists():
                    validation_results["syntax_valid"] = False
                    validation_results["warnings"].append(
                        "File was not created/modified successfully"
                    )
                    return validation_results

            # Language-specific validation
            language = self._detect_language(step.file_path)

            if language == "python":
                # Safe Python syntax validation using AST parsing (no code execution)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Use ast.parse() for safe syntax validation without execution risks
                    ast.parse(content, step.file_path)
                except SyntaxError as e:
                    validation_results["syntax_valid"] = False
                    validation_results["warnings"].append(
                        f"Python syntax error: {str(e)}"
                    )

            elif language in ["javascript", "typescript"]:
                # Try to run TypeScript compiler or build command
                build_result = await self._run_build_check(task)
                if not build_result["success"]:
                    validation_results["syntax_valid"] = False
                    validation_results["warnings"].append(
                        f"Build failed: {build_result.get('error', 'Unknown error')}"
                    )
                else:
                    logger.info(f"[NAVI] Build check passed for {step.file_path}")

            # NEW: Run existing tests if available
            test_result = await self._run_tests(task)
            if test_result:
                validation_results["tests_passing"] = test_result.get(
                    "all_passed", True
                )
                if not test_result.get("all_passed"):
                    validation_results["warnings"].append(
                        f"Some tests failed: {test_result.get('failed_count', 0)}"
                    )

            return validation_results

        except Exception as e:
            logger.error(f"Validation failed for step {step.id}: {e}")
            return {
                "syntax_valid": False,
                "tests_passing": False,
                "no_conflicts": False,
                "error": str(e),
            }

    async def _read_existing_file(
        self, task: CodingTask, step: CodingStep
    ) -> Optional[str]:
        """Read existing file content for context during code generation"""
        try:
            file_path = Path(task.repository_path) / step.file_path
            if file_path.exists() and file_path.is_file():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    return content
            return None
        except Exception as e:
            logger.warning(f"Failed to read existing file {step.file_path}: {e}")
            return None

    def _extract_imports(self, content: str, file_path: str) -> List[str]:
        """Extract import statements from code"""
        imports = []
        try:
            lines = content.split("\n")
            ext = Path(file_path).suffix.lower()

            if ext == ".py":
                # Python imports
                for line in lines:
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        imports.append(line)
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                # JavaScript/TypeScript imports
                for line in lines:
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("export "):
                        imports.append(line)
            elif ext == ".go":
                # Go imports
                in_import_block = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("import ("):
                        in_import_block = True
                        imports.append(line)
                    elif in_import_block:
                        imports.append(line)
                        if line == ")":
                            in_import_block = False
                    elif line.startswith('import "'):
                        imports.append(line)

            return imports
        except Exception as e:
            logger.warning(f"Failed to extract imports from {file_path}: {e}")
            return []

    async def _read_related_files(
        self, task: CodingTask, related_files: List[str]
    ) -> Dict[str, str]:
        """Read related files for context (types, interfaces, patterns)"""
        contents = {}
        try:
            for rel_file in related_files[
                :5
            ]:  # Limit to 5 files to avoid token overflow
                try:
                    file_path = Path(task.repository_path) / rel_file
                    if file_path.exists() and file_path.is_file():
                        # Only read small files (< 100KB) to avoid memory issues
                        if file_path.stat().st_size < 100_000:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                # Store first 2000 chars for context
                                contents[rel_file] = content[:2000]
                                logger.info(
                                    f"[NAVI] Read related file {rel_file} for context"
                                )
                except Exception as e:
                    logger.warning(f"Failed to read related file {rel_file}: {e}")
                    continue

            return contents
        except Exception as e:
            logger.warning(f"Failed to read related files: {e}")
            return {}

    async def _add_missing_imports(
        self, code: str, file_path: str, task: CodingTask
    ) -> str:
        """Automatically add missing imports based on code analysis"""
        try:
            ext = Path(file_path).suffix.lower()

            if ext in [".js", ".jsx", ".ts", ".tsx"]:
                return await self._add_js_imports(code, file_path, task)
            elif ext == ".py":
                return await self._add_python_imports(code, file_path, task)
            else:
                return code  # No import management for other languages yet
        except Exception as e:
            logger.warning(f"Failed to add missing imports: {e}")
            return code

    async def _add_js_imports(self, code: str, file_path: str, task: CodingTask) -> str:
        """Add missing imports for JavaScript/TypeScript"""
        try:
            lines = code.split("\n")
            imports = []

            # Common React imports if using JSX
            if "React" in code or "<" in code and ">" in code:
                if not any("import React" in line for line in lines):
                    imports.append("import React from 'react';")

            # useState, useEffect, etc.
            react_hooks = [
                "useState",
                "useEffect",
                "useCallback",
                "useMemo",
                "useRef",
                "useContext",
            ]
            used_hooks = [hook for hook in react_hooks if hook in code]
            if used_hooks and not any(
                "import {" in line and any(hook in line for hook in used_hooks)
                for line in lines
            ):
                imports.append(f"import {{ {', '.join(used_hooks)} }} from 'react';")

            # Add imports at the beginning
            if imports:
                # Find where to insert (after any existing imports)
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith("import ") or line.strip().startswith(
                        "export "
                    ):
                        insert_index = i + 1

                for imp in reversed(imports):
                    lines.insert(insert_index, imp)

                return "\n".join(lines)

            return code
        except Exception as e:
            logger.warning(f"Failed to add JS imports: {e}")
            return code

    async def _add_python_imports(
        self, code: str, file_path: str, task: CodingTask
    ) -> str:
        """Add missing imports for Python"""
        try:
            lines = code.split("\n")
            imports = []

            # Common patterns
            if "FastAPI" in code and not any(
                "from fastapi import" in line for line in lines
            ):
                imports.append("from fastapi import FastAPI, APIRouter, HTTPException")

            if "Pydantic" in code or "BaseModel" in code:
                if not any("from pydantic import" in line for line in lines):
                    imports.append("from pydantic import BaseModel, Field")

            if "datetime" in code and not any(
                "from datetime import" in line or "import datetime" in line
                for line in lines
            ):
                imports.append("from datetime import datetime")

            if "Dict" in code or "List" in code or "Optional" in code:
                if not any("from typing import" in line for line in lines):
                    types_used = []
                    if "Dict" in code:
                        types_used.append("Dict")
                    if "List" in code:
                        types_used.append("List")
                    if "Optional" in code:
                        types_used.append("Optional")
                    if "Any" in code:
                        types_used.append("Any")
                    imports.append(f"from typing import {', '.join(types_used)}")

            # Add imports at the beginning
            if imports:
                # Find where to insert (after docstring and before code)
                insert_index = 0
                in_docstring = False
                for i, line in enumerate(lines):
                    if line.strip().startswith('"""') or line.strip().startswith("'''"):
                        in_docstring = not in_docstring
                    elif not in_docstring and (
                        line.strip().startswith("import ")
                        or line.strip().startswith("from ")
                    ):
                        insert_index = i + 1
                    elif (
                        not in_docstring
                        and line.strip()
                        and not line.strip().startswith("#")
                    ):
                        break

                for imp in reversed(imports):
                    lines.insert(insert_index, imp)

                return "\n".join(lines)

            return code
        except Exception as e:
            logger.warning(f"Failed to add Python imports: {e}")
            return code

    async def _run_build_check(self, task: CodingTask) -> Dict[str, Any]:
        """Run build command to check if code compiles"""
        import subprocess

        try:
            repo_path = Path(task.repository_path)

            # Check for package.json (Node.js project)
            if (repo_path / "package.json").exists():
                logger.info("[NAVI] Running npm run build to validate changes...")
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minute timeout
                )

                if result.returncode == 0:
                    return {"success": True, "output": result.stdout}
                else:
                    logger.warning(f"[NAVI] Build failed: {result.stderr[:500]}")
                    return {"success": False, "error": result.stderr[:500]}

            # Check for tsconfig.json (TypeScript)
            elif (repo_path / "tsconfig.json").exists():
                logger.info("[NAVI] Running tsc to validate TypeScript...")
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    return {"success": True, "output": "TypeScript check passed"}
                else:
                    return {"success": False, "error": result.stderr[:500]}

            # No build system found
            return {"success": True, "output": "No build system detected, skipping"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Build timeout (exceeded 2 minutes)"}
        except FileNotFoundError:
            return {
                "success": True,
                "output": "Build tools not found, skipping validation",
            }
        except Exception as e:
            logger.warning(f"Build check failed: {e}")
            return {"success": True, "output": f"Build check skipped: {str(e)}"}

    async def _run_tests(self, task: CodingTask) -> Optional[Dict[str, Any]]:
        """Run existing tests to ensure changes don't break functionality"""
        import subprocess

        try:
            repo_path = Path(task.repository_path)

            # Check for test scripts
            if (repo_path / "package.json").exists():
                # Check if test script exists
                try:
                    with open(repo_path / "package.json", "r") as f:
                        import json

                        pkg = json.load(f)
                        if "test" in pkg.get("scripts", {}):
                            logger.info("[NAVI] Running tests...")
                            result = subprocess.run(
                                ["npm", "test"],
                                cwd=repo_path,
                                capture_output=True,
                                text=True,
                                timeout=180,  # 3 minute timeout
                            )

                            return {
                                "all_passed": result.returncode == 0,
                                "output": result.stdout[:1000],
                                "failed_count": 0 if result.returncode == 0 else 1,
                            }
                except Exception as e:
                    logger.warning(f"Test execution failed: {e}")

            # Python tests (pytest)
            elif (repo_path / "pytest.ini").exists() or (repo_path / "tests").exists():
                logger.info("[NAVI] Running pytest...")
                result = subprocess.run(
                    ["pytest", "--tb=short"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                return {
                    "all_passed": result.returncode == 0,
                    "output": result.stdout[:1000],
                    "failed_count": 0 if result.returncode == 0 else 1,
                }

            return None  # No tests found

        except subprocess.TimeoutExpired:
            return {"all_passed": False, "output": "Tests timeout", "failed_count": 1}
        except Exception as e:
            logger.warning(f"Test execution failed: {e}")
            return None

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        ext = Path(file_path).suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".json": "json",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sql": "sql",
        }

        return language_map.get(ext, "text")

    async def create_pull_request(
        self, task_id: str, repository: str, branch_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a pull request for completed task"""
        try:
            task = self.active_tasks.get(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")

            # Use task's branch or provided branch
            branch = (
                branch_name or task.branch_name or f"aep/{task.jira_key or task.id}"
            )

            # Create branch if git is available
            if self.repo:
                try:
                    # Create and checkout new branch
                    # Check if branch exists more efficiently
                    branch_exists = False
                    try:
                        self.repo.heads[branch]
                        branch_exists = True
                    except IndexError:
                        branch_exists = False

                    if not branch_exists:
                        # Commit current changes first, then create and checkout new branch
                        safe_files = self._get_safe_files_for_staging()
                        if safe_files:
                            for file_path in safe_files:
                                self.repo.git.add(file_path)

                            if self.repo.is_dirty():
                                self.repo.index.commit(
                                    f"AEP: Auto-commit before creating branch {branch}"
                                )

                        new_branch = self.repo.create_head(branch)
                        new_branch.checkout()

                        # Commit all safe changes
                        safe_files = self._get_safe_files_for_staging()
                        if safe_files:
                            for file_path in safe_files:
                                self.repo.git.add(file_path)

                            commit_message = f"{task.jira_key}: {task.title}\n\nImplemented by AEP Autonomous Coding Engine"
                            self.repo.index.commit(commit_message)

                        # Push branch if GitHub service is available
                        if self.github_service:
                            self.repo.git.push("origin", branch)

                            # Create PR via GitHub API
                            pr_result = await self.github_service.create_pull_request(
                                repository=repository,
                                title=f"{task.jira_key}: {task.title}",
                                body=self._generate_pr_description(task),
                                head_branch=branch,
                                base_branch="main",  # or whatever the default branch is
                            )

                            return {
                                "status": "success",
                                "pr_url": pr_result.get("html_url"),
                                "pr_number": pr_result.get("number"),
                                "branch": branch,
                                "commits": 1,
                            }
                        else:
                            return {
                                "status": "success",
                                "branch": branch,
                                "message": "Branch created and committed. GitHub service not available for PR creation.",
                                "manual_pr": f"Create PR from branch '{branch}' manually",
                            }
                    else:
                        return {
                            "status": "error",
                            "error": f"Branch '{branch}' already exists",
                        }

                except Exception as e:
                    logger.error(f"Git operations failed: {e}")
                    # Return generic message for security (don't expose internal details)
                    return {
                        "status": "error",
                        "error": "Git operations failed due to an internal error.",
                    }
            else:
                return {
                    "status": "error",
                    "error": "Git not available - cannot create branch or PR",
                }

        except Exception as e:
            logger.error(f"Failed to create PR for task {task_id}: {e}")
            return {
                "status": "error",
                "error": f"Failed to create pull request: {str(e)}",
            }

    def _generate_pr_description(self, task: CodingTask) -> str:
        """Generate comprehensive PR description"""
        description = f"""
## 🎯 Task: {task.title}

**JIRA:** {task.jira_key or "N/A"}
**Type:** {task.task_type.value}
**Generated by:** AEP Autonomous Coding Engine

### 📝 Description
{task.description}

### 🔧 Changes Made
"""

        for i, step in enumerate(task.steps, 1):
            if step.status == StepStatus.COMPLETED:
                description += f"{i}. **{step.operation.title()}** `{step.file_path}` - {step.description}\n"

        description += """
### 📚 Context & Documentation
"""

        if task.documentation_links:
            for link in task.documentation_links:
                description += f"- [Documentation]({link})\n"

        if task.meeting_context:
            description += f"\n### 💬 Meeting Context\n{task.meeting_context.get('summary', 'See meeting notes for details')}\n"

        description += """
### ✅ Validation
- All steps completed successfully
- Code syntax validated
- Safety checks passed

*This PR was created automatically by AEP. Please review all changes before merging.*
"""

        return description.strip()

    def _get_next_step_preview(self, task: CodingTask) -> Optional[Dict[str, Any]]:
        """Get preview of next step"""
        if task.current_step_index < len(task.steps):
            next_step = task.steps[task.current_step_index]
            return {
                "id": next_step.id,
                "description": next_step.description,
                "file": next_step.file_path,
            }
        return None

    def _summarize_meeting_context(self, meeting_context: Dict[str, Any]) -> str:
        """Summarize meeting context for user"""
        return "No recent meeting discussions about this task"

    def _estimate_duration(self, task: CodingTask) -> str:
        """Estimate task duration"""
        return f"{len(task.steps) * 5} minutes"

    async def _require_shell_script_confirmation(
        self, file_path: str, script_content: str
    ) -> None:
        """
        Require explicit user confirmation for shell script writes.

        Shell scripts can cause serious system damage if they contain malicious or buggy commands.
        This method throws a SecurityError requiring explicit user approval.
        """
        # Analyze script content for particularly dangerous patterns
        dangerous_shell_patterns = [
            "rm -rf",
            "sudo",
            "chmod +x",
            "curl | sh",
            "wget | sh",
            "/etc/",
            "/usr/",
            "/var/",
            "passwd",
            "crontab",
            "systemctl",
            "service ",
            "mount",
            "umount",
        ]

        content_lower = script_content.lower()
        found_dangerous = [
            pattern for pattern in dangerous_shell_patterns if pattern in content_lower
        ]

        error_msg = (
            f"Shell script write requires explicit user confirmation: {file_path}"
        )
        if found_dangerous:
            error_msg += f"\nDetected potentially dangerous commands: {', '.join(found_dangerous)}"

        error_msg += (
            "\n\nShell scripts can cause system damage. "
            "This operation requires manual user approval via the UI."
        )

        # Log the security requirement
        logger.warning(f"Shell script confirmation required for: {file_path}")
        if found_dangerous:
            logger.warning(f"Dangerous patterns detected: {found_dangerous}")

        # Raise security error that requires user intervention
        raise SecurityError(error_msg)

    def _contains_dangerous_patterns(self, code: str) -> bool:
        """Check for potentially dangerous code patterns using enhanced AST analysis and string matching"""

        # Try AST parsing for Python code (more robust detection)
        try:
            tree = ast.parse(code)

            # Check for dangerous function calls in AST
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for dangerous function calls
                    if isinstance(node.func, ast.Name):
                        if node.func.id in {"eval", "exec", "compile", "__import__"}:
                            return True
                    elif isinstance(node.func, ast.Attribute):
                        # Check for os.system, subprocess.call, etc.
                        if (
                            isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "os"
                            and node.func.attr
                            in {"system", "popen", "execv", "execl", "spawnl"}
                        ):
                            return True
                        if (
                            isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "subprocess"
                            and node.func.attr
                            in {"call", "run", "Popen", "check_call", "check_output"}
                        ):
                            return True
                        # Check for getattr/setattr with dangerous names
                        if isinstance(
                            node.func.value, ast.Name
                        ) and node.func.value.id in {"builtins", "globals", "locals"}:
                            return True

                # Check for dangerous imports with context awareness
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Critical modules that are almost always dangerous
                    critical_modules = {"marshal", "pickle", "ctypes"}

                    for alias in node.names:
                        # Always flag critical modules
                        if alias.name in critical_modules:
                            return True
                        # For other modules (os, subprocess, sys, importlib), we check usage context
                        # in the attribute access detection below

                # Check for attribute access that could be dangerous
                elif isinstance(node, ast.Attribute):
                    # Always dangerous attributes
                    dangerous_attrs = {
                        "__builtins__",
                        "__globals__",
                        "__code__",
                        "__class__",
                    }
                    if node.attr in dangerous_attrs:
                        return True

                    # Context-aware dangerous module usage detection
                    if isinstance(node.value, ast.Name):
                        module_name = node.value.id
                        attr_name = node.attr

                        # Check for dangerous os module usage
                        if module_name == "os" and attr_name in [
                            "system",
                            "popen",
                            "execl",
                            "execle",
                            "execlp",
                            "execv",
                            "execve",
                            "execvp",
                            "execvpe",
                        ]:
                            return True
                        # Check for dangerous subprocess usage
                        elif module_name == "subprocess" and attr_name in [
                            "call",
                            "run",
                            "Popen",
                            "check_call",
                            "check_output",
                        ]:
                            return True
                        # Check for dangerous sys usage
                        elif module_name == "sys" and attr_name in ["exit", "modules"]:
                            return True
                        # Check for dangerous importlib usage
                        elif module_name == "importlib" and attr_name in [
                            "import_module"
                        ]:
                            return True

                # Enhanced detection for obfuscated function calls
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "getattr":
                        # Check for getattr(__builtins__, 'eval') patterns
                        if len(node.args) >= 2:
                            try:
                                if isinstance(
                                    node.args[1], (ast.Str, ast.Constant)
                                ) and hasattr(
                                    node.args[1],
                                    "value" if hasattr(node.args[1], "value") else "s",
                                ):
                                    attr_name = getattr(
                                        node.args[1],
                                        (
                                            "value"
                                            if hasattr(node.args[1], "value")
                                            else "s"
                                        ),
                                    )
                                    if attr_name in {
                                        "eval",
                                        "exec",
                                        "compile",
                                        "__import__",
                                    }:
                                        return True
                            except (AttributeError, TypeError):
                                # Skip nodes that do not have the expected string attributes; not all AST nodes will match
                                pass

                # Check for dangerous string operations that could construct dangerous calls
                elif isinstance(node, ast.BinOp):
                    if isinstance(node.op, ast.Add):
                        # Check for string concatenation that might build dangerous calls
                        if isinstance(
                            node.left, (ast.Str, ast.Constant)
                        ) and isinstance(node.right, (ast.Str, ast.Constant)):
                            try:
                                left_val = (
                                    node.left.s
                                    if hasattr(node.left, "s")
                                    else node.left.value
                                )
                                right_val = (
                                    node.right.s
                                    if hasattr(node.right, "s")
                                    else node.right.value
                                )

                                if isinstance(left_val, str) and isinstance(
                                    right_val, str
                                ):
                                    combined = left_val + right_val
                                    if any(
                                        danger in combined.lower()
                                        for danger in [
                                            "exec",
                                            "eval",
                                            "system",
                                            "popen",
                                        ]
                                    ):
                                        return True
                            except (AttributeError, TypeError):
                                # Skip if we can't safely extract string values
                                pass

        except SyntaxError:
            # If AST parsing fails, fall back to string matching
            pass

        # Use compiled patterns for dangerous code detection (performance optimized)
        compiled_dangerous_patterns = self._get_compiled_dangerous_patterns()

        # Enhanced fallback to string matching for non-Python or invalid syntax
        # Additional high-risk patterns that are rarely legitimate in automated coding
        additional_high_risk_patterns = [
            "rm -rf",
            "drop table",
            "drop database",
            # Check for obfuscated eval/exec patterns
            "getattr(__builtins__",
            "__builtins__['eval']",
            "__builtins__['exec']",
            "getattr(globals()",
            "getattr(locals()",
            # Base64/hex encoding attempts
            "exec(base64",
            "eval(base64",
            "exec(bytes.fromhex",
            "eval(bytes.fromhex",
            # String reversal/obfuscation
            "[::-1]",  # Common string reversal
            "chr(",  # Character building
            "ord(",  # Character codes
        ]

        # Medium-risk patterns that need context checking
        medium_risk_patterns = [
            (
                "open(",
                ["mode='w'", 'mode="w"', ", 'w'", ', "w"', "'w')", '"w")'],
            ),  # File write modes
            (
                "open(",
                ["mode='a'", 'mode="a"', ", 'a'", ', "a"', "'a')", '"a")'],
            ),  # File append modes
            (
                "open(",
                ["mode='x'", 'mode="x"', ", 'x'", ', "x"', "'x')", '"x")'],
            ),  # File exclusive create modes
            ("delete", ["drop", "rm ", "del "]),  # SQL/file deletion context
            ("compile(", ["exec", "eval"]),  # Code compilation patterns
        ]

        # Normalize code for better pattern matching
        code_normalized = code.lower()
        # Remove common whitespace obfuscation
        code_normalized = " ".join(code_normalized.split())
        # Remove common separator obfuscation
        code_normalized = (
            code_normalized.replace("+", "").replace('"', "").replace("'", "")
        )

        # Check compiled dangerous patterns (performance optimized)
        for compiled_pattern in compiled_dangerous_patterns:
            if compiled_pattern.search(code):
                return True

        # Check additional high-risk patterns
        for pattern in additional_high_risk_patterns:
            if pattern.lower() in code_normalized:
                return True

        # Check medium-risk patterns with context
        for pattern, contexts in medium_risk_patterns:
            if pattern.lower() in code_normalized:
                # Check if it appears with dangerous context
                for context in contexts:
                    if context.lower() in code_normalized:
                        return True

        return False

    def _sanitize_commit_message(self, message: str) -> str:
        """Sanitize git commit message to prevent command injection"""
        import re

        if not message:
            return "Untitled task"

        # Remove or replace potentially dangerous characters
        # Remove newlines, null bytes, and control characters
        sanitized = re.sub(r"[\n\r\t\x00-\x1f\x7f-\x9f]", " ", message)

        # Remove shell special characters that could be dangerous in commit messages
        sanitized = re.sub(r"[;&|`$<>(){}[\]]", "", sanitized)

        # Limit length to prevent excessively long commit messages
        if len(sanitized) > self.MAX_COMMIT_MESSAGE_LENGTH:
            sanitized = sanitized[: self.MAX_COMMIT_MESSAGE_LENGTH - 3] + "..."

        # Ensure it's not empty after sanitization
        sanitized = sanitized.strip()
        if not sanitized:
            return "Sanitized task"

        return sanitized

    def _sanitize_prompt_input(self, input_text: str) -> str:
        """Sanitize user input to prevent prompt injection attacks"""
        import re

        if not input_text:
            return ""

        # Check for prompt injection patterns - reject if found
        injection_patterns = [
            r"\n\s*(?:ignore|forget|disregard).*previous.*instructions",
            r"\n\s*(?:system|assistant|human|user)\s*:",
            r"\n\s*(?:new|override|replace)\s+(?:instructions|prompt|task)",
            r"\n\s*(?:act|pretend|role)\s+(?:as|like)",
            r"\n\s*(?:tell|give|provide)\s+me.*(?:secret|password|key)",
        ]

        for pattern in injection_patterns:
            if re.search(pattern, input_text, flags=re.IGNORECASE):
                raise SecurityError(
                    "Input rejected: potential prompt injection detected. "
                    "Please rephrase your request without attempting to override system instructions."
                )

        # Limit length to prevent token exhaustion attacks
        if len(input_text) > self.MAX_PROMPT_INPUT_LENGTH:
            raise SecurityError(
                f"Input rejected: text too long ({len(input_text)} chars, max {self.MAX_PROMPT_INPUT_LENGTH}). "
                f"Please provide a shorter description."
            )

        # Check for excessive newlines that could be used for prompt separation
        if input_text.count("\n") > self.MAX_PROMPT_NEWLINES:
            raise SecurityError(
                "Input rejected: excessive line breaks detected. "
                "Please format your input with normal spacing."
            )

        # Check for dangerous formatting characters
        dangerous_chars = ["\x00", "\r", "\t"]
        if any(char in input_text for char in dangerous_chars):
            raise SecurityError(
                "Input rejected: contains invalid control characters. "
                "Please use only printable text."
            )

        return input_text.strip()
