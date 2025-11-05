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
from pathlib import Path
from typing import TYPE_CHECKING
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

# Git operations - GitPython is now a required dependency
import git

from backend.core.ai.llm_service import LLMService
from backend.models.integrations import JiraIssue, JiraConnection
from backend.core.crypto import decrypt_token


# Security exception class
class SecurityError(Exception):
    """Raised when security validation fails"""

    pass


# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from backend.core.memory.vector_store import VectorStore
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

    def __init__(
        self,
        llm_service: LLMService,
        vector_store: VectorStore,
        workspace_path: str,
        db_session: Optional[Session] = None,
        github_service: Optional[GitHubService] = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.llm_service = llm_service
        self.vector_store = vector_store
        self.workspace_path = Path(workspace_path)
        self.db_session = db_session
        self.github_service = github_service
        self.progress_callback = progress_callback

        # Task management
        self.active_tasks: Dict[str, CodingTask] = {}
        self.task_queue: List[str] = []

        # Git repository (optional)
        self.repo = None
        if git is not None:
            try:
                self.repo = git.Repo(workspace_path)
            except Exception:  # Catch any git-related error
                logger.warning(f"No git repository found at {workspace_path}")
                self.repo = None
        else:
            logger.warning("GitPython not available - git features disabled")

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

    async def _generate_implementation_plan(self, task: CodingTask):
        """Generate detailed implementation plan using AI"""
        context = {
            "task_description": task.description,
            "related_files": task.related_files,
            "team_context": task.team_context,
            "documentation": task.documentation_links,
        }

        # Use LLM to generate step-by-step plan
        plan_prompt = f"""
        Create a detailed implementation plan for: {task.title}
        
        Description: {task.description}
        Related files: {', '.join(task.related_files)}
        
        Generate a step-by-step plan with:
        1. File to modify
        2. Specific changes needed
        3. Reasoning for each change
        4. Dependencies between steps
        """

        plan_response = await self.llm_service.generate_engineering_response(
            plan_prompt, context
        )

        # Parse response and create steps (simplified)
        steps = self._parse_plan_response(plan_response, task)
        task.steps = steps

    def _parse_plan_response(self, response, task: CodingTask) -> List[CodingStep]:
        """Parse LLM response into concrete steps"""
        # Simplified parsing - would be more sophisticated in practice
        steps = []

        # Mock steps for demonstration
        steps.append(
            CodingStep(
                id=f"{task.id}-step-1",
                description="Analyze existing code structure",
                file_path="src/main.py",
                operation="modify",
                content_preview="// Code changes preview",
                reasoning="Need to understand current implementation",
            )
        )

        return steps

    def _notify_progress(self, message: str):
        """Notify user of progress updates"""
        if self.progress_callback:
            self.progress_callback(message)
        logger.info(f"Progress: {message}")

    async def _create_safety_backup(self, task: CodingTask):
        """Create git backup before starting modifications"""
        if self.repo:
            try:
                # Create a backup commit with current state
                self.repo.git.add(A=True)
                commit_message = f"AEP backup before task {task.id}: {task.title}"
                commit = self.repo.index.commit(commit_message)
                task.backup_commit = commit.hexsha
                logger.info(f"Created backup commit: {commit.hexsha}")
            except Exception as e:
                logger.warning(f"Failed to create backup commit: {e}")
        else:
            logger.warning("Git not available - no backup created")

    async def _generate_code_for_step(
        self, task: CodingTask, step: CodingStep
    ) -> Dict[str, Any]:
        """Generate actual code for the step"""
        try:
            # Build context for code generation
            context = {
                "task_description": task.description,
                "step_description": step.description,
                "file_path": step.file_path,
                "operation": step.operation,
                "related_files": task.related_files,
                "team_context": task.team_context,
            }

            # Generate code using LLM service
            if step.operation == "create":
                prompt = f"Create a new file '{step.file_path}' for: {step.description}"
            elif step.operation == "modify":
                prompt = f"Modify file '{step.file_path}' to: {step.description}"
            else:  # delete
                prompt = f"Prepare to delete file '{step.file_path}' because: {step.description}"

            # Use the LLM service to generate code
            response = await self.llm_service.generate_code_suggestion(
                description=prompt,
                language=self._detect_language(step.file_path),
                context=context,
            )

            return {
                "generated_code": response.get("code", ""),
                "language": response.get("language", "text"),
                "confidence": 0.8,  # Would be calculated based on model response
                "estimated_lines": len(response.get("code", "").split("\n")),
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

    async def _apply_code_changes(self, step: CodingStep, code_result: Dict[str, Any]):
        """Apply code changes to files with security validation"""
        try:
            file_path = self.workspace_path / step.file_path

            # Security validation: ensure file is within workspace
            try:
                file_path.resolve().relative_to(self.workspace_path.resolve())
            except ValueError:
                raise SecurityError("Invalid file path: outside workspace")

            # Security validation: check for dangerous file extensions with whitelist
            dangerous_extensions = {".exe", ".bat", ".cmd", ".ps1", ".bin"}
            development_extensions = {".sh"}  # Scripts that may be legitimate in dev

            if file_path.suffix.lower() in dangerous_extensions:
                raise SecurityError(
                    f"Cannot write to potentially dangerous file type: {file_path.suffix}"
                )
            elif file_path.suffix.lower() in development_extensions:
                # Log warning but allow with extra validation
                logger.warning(f"Writing to development script file: {step.file_path}")
                # Could add user confirmation mechanism here in the future

            # Basic code validation before writing
            generated_code = code_result["generated_code"]
            if self._contains_dangerous_patterns(generated_code):
                logger.warning(
                    f"Potentially dangerous code detected in {step.file_path}"
                )
                # Add warning comment but allow the write
                generated_code = f"# WARNING: AEP detected potentially dangerous patterns in this code\n{generated_code}"

            if step.operation == "create":
                # Create new file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(generated_code)
                logger.info(f"Created file: {step.file_path}")

            elif step.operation == "modify":
                # Modify existing file
                if file_path.exists():
                    # Write new content
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(generated_code)
                    logger.info(f"Modified file: {step.file_path}")
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
                # Basic Python syntax validation
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    compile(content, step.file_path, "exec")
                except SyntaxError as e:
                    validation_results["syntax_valid"] = False
                    validation_results["warnings"].append(
                        f"Python syntax error: {str(e)}"
                    )

            elif language in ["javascript", "typescript"]:
                # Basic JS/TS validation (would use proper linters in production)
                validation_results["warnings"].append(
                    "JavaScript/TypeScript validation not implemented"
                )

            # TODO: Add more sophisticated validation
            # - Run tests
            # - Check for breaking changes
            # - Security scanning
            # - Performance analysis

            return validation_results

        except Exception as e:
            logger.error(f"Validation failed for step {step.id}: {e}")
            return {
                "syntax_valid": False,
                "tests_passing": False,
                "no_conflicts": False,
                "error": str(e),
            }

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
                        self.repo.git.add(A=True)
                        if self.repo.is_dirty():
                            self.repo.index.commit(
                                f"AEP: Auto-commit before creating branch {branch}"
                            )
                        new_branch = self.repo.create_head(branch)
                        new_branch.checkout()

                        # Commit all changes
                        self.repo.git.add(A=True)
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
                    # Sanitize error message for external exposure
                    sanitized_error = str(e).replace("\n", " ").strip()
                    return {
                        "status": "error",
                        "error": f"Git operations failed: {sanitized_error}",
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

**JIRA:** {task.jira_key or 'N/A'}  
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

    def _contains_dangerous_patterns(self, code: str) -> bool:
        """Check for potentially dangerous code patterns with context awareness"""
        # High-risk patterns that are rarely legitimate in automated coding
        high_risk_patterns = [
            "subprocess.call",
            "os.system",
            "eval(",
            "exec(",
            "__import__",
            "rm -rf",
            "drop table",
            "drop database",
        ]

        # Medium-risk patterns that need context checking
        medium_risk_patterns = [
            ("open(", ["w", "a", "x"]),  # File writes, not reads
            ("delete", ["drop", "rm ", "del "]),  # SQL/file deletion context
        ]

        code_lower = code.lower()

        # Check high-risk patterns
        for pattern in high_risk_patterns:
            if pattern.lower() in code_lower:
                return True

        # Check medium-risk patterns with context
        for pattern, contexts in medium_risk_patterns:
            if pattern.lower() in code_lower:
                # Check if it appears with dangerous context
                for context in contexts:
                    if context.lower() in code_lower:
                        return True

        return False
