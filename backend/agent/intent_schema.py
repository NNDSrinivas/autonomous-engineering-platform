"""
NAVI Intent Schema v2
=====================

This module defines the *canonical contract* between:

- intent_classifier     → decides what the user wants
- planner               → breaks the intent into a plan
- tool_executor         → performs concrete actions
- orchestrator/agent    → runs multi-step autonomous workflows

The goal is to support three layers of capability:

1) Engineering           (code, tests, infra, debugging)
2) Project Management    (Jira/PRs/release notes/quality gates)
3) Autonomous Orchestration
   (multi-step agents, scheduled work, long-running tasks)

Nothing in this module talks to the network, filesystem, DB, etc.
It is purely data models + enums and should be safe to import
from anywhere in the backend.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# High-level intent metadata
# ---------------------------------------------------------------------------


class IntentFamily(str, Enum):
    """Broad category of what NAVI is doing."""

    ENGINEERING = "engineering"
    PROJECT_MANAGEMENT = "project_management"
    AUTONOMOUS_ORCHESTRATION = "autonomous_orchestration"


class IntentKind(str, Enum):
    """
    Fine-grained intent type.

    These are the *core verbs* of the NAVI platform and should be stable.
    If you add new ones, also update:
      - planner rules
      - tool routing
      - UI affordances
    """

    # --- Repository discovery / understanding --------------------------------
    INSPECT_REPO = "inspect_repo"  # high-level overview of repo
    SUMMARIZE_FILE = "summarize_file"  # explain one file
    SUMMARIZE_DIFF = "summarize_diff"  # explain a patch or diff
    SEARCH_CODE = "search_code"  # semantic or text search

    # --- Code authoring / refactoring ----------------------------------------
    MODIFY_CODE = "modify_code"  # edit existing code
    CREATE_FILE = "create_file"  # add new source/test/config
    REFACTOR_CODE = "refactor_code"  # structural improvements
    IMPLEMENT_FEATURE = "implement_feature"  # end-to-end change
    FIX_BUG = "fix_bug"  # debug + patch
    FIX_DIAGNOSTICS = "fix_diagnostics"  # Phase 4.1.2: Fix Problems tab errors
    UPDATE_DEPENDENCIES = "update_dependencies"
    EDIT_INFRA = "edit_infra"  # Dockerfile, CI, infra-as-code

    # --- Testing / verification ----------------------------------------------
    RUN_TESTS = "run_tests"
    GENERATE_TESTS = "generate_tests"
    RUN_LINT = "run_lint"
    RUN_BUILD = "run_build"
    RUN_CUSTOM_COMMAND = "run_custom_command"

    # --- Project management / collaboration ----------------------------------
    CREATE_TICKET = "create_ticket"  # Jira / GitHub issue, etc.
    UPDATE_TICKET = "update_ticket"
    SUMMARIZE_TICKETS = "summarize_tickets"

    # Cross-app general intents (provider-agnostic)
    LIST_MY_ITEMS = "list_my_items"  # general: Jira issues, GitHub issues, tasks
    SUMMARIZE_CHANNEL = "summarize_channel"  # general: Slack, Teams, Discord channels
    SHOW_ITEM_DETAILS = (
        "show_item_details"  # general: show details of any item (issue, PR, doc)
    )

    # Provider-specific intents (for backward compatibility)
    JIRA_LIST_MY_ISSUES = "jira_list_my_issues"  # list Jira issues assigned to user
    SLACK_SUMMARIZE_CHANNEL = (
        "slack_summarize_channel"  # summarize Slack channel messages
    )
    SUMMARIZE_PR = "summarize_pr"
    REVIEW_PR = "review_pr"
    GENERATE_RELEASE_NOTES = "generate_release_notes"

    # --- Knowledge & explanation ---------------------------------------------
    EXPLAIN_CODE = "explain_code"
    EXPLAIN_ERROR = "explain_error"
    ARCHITECTURE_OVERVIEW = "architecture_overview"
    DESIGN_PROPOSAL = "design_proposal"
    GREET = "greet"  # simple greeting/hello

    # --- Autonomous orchestration --------------------------------------------
    AUTONOMOUS_SESSION = "autonomous_session"  # multi-step agent run
    BACKGROUND_WORKFLOW = "background_workflow"
    SCHEDULED_TASK = "scheduled_task"
    CONTINUE_SESSION = "continue_session"  # resume previous run
    CANCEL_WORKFLOW = "cancel_workflow"

    # --- Fallback / meta -----------------------------------------------------
    UNKNOWN = "unknown"  # classifier unsure

    # --- Additional core kinds to fix planner errors -----
    CREATE = "create"  # generic create operation
    IMPLEMENT = "implement"  # generic implementation
    FIX = "fix"  # generic fix operation
    SEARCH = "search"  # generic search
    EXPLAIN = "explain"  # generic explanation
    DEPLOY = "deploy"  # deployment operations
    SYNC = "sync"  # synchronization operations
    CONFIGURE = "configure"  # configuration operations
    GENERIC = "generic"  # fallback generic


class IntentPriority(str, Enum):
    """Relative importance – helps orchestration & queueing."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Provider(str, Enum):
    """External service/app that NAVI integrates with for cross-app workflows."""

    JIRA = "jira"
    SLACK = "slack"
    GITHUB = "github"
    TEAMS = "teams"
    ZOOM = "zoom"
    CONFLUENCE = "confluence"
    NOTION = "notion"
    LINEAR = "linear"
    ASANA = "asana"
    JENKINS = "jenkins"
    GENERIC = "generic"


class IntentSource(str, Enum):
    """Where this intent originated from."""

    CHAT = "chat"  # user message in UI
    IDE_EVENT = "ide_event"  # VS Code / JetBrains triggers
    WEBHOOK = "webhook"  # Jira / GitHub / CI hooks
    SYSTEM = "system"  # internal automation
    SCHEDULE = "schedule"  # cron / time-based agent


class AutonomyMode(str, Enum):
    """
    How much NAVI is allowed to do without explicit confirmation.

    The frontend and orchestrator should enforce these semantics.
    """

    SINGLE_STEP = "single_step"  # one tool call, then ask
    ASSISTED = "assisted"  # propose plan, ask before execute
    AUTONOMOUS_SESSION = "autonomous_session"  # run full plan, show results
    BATCH = "batch"  # background, many tasks (dangerous)


# ---------------------------------------------------------------------------
# Shared target / selector models
# ---------------------------------------------------------------------------


class RepoTarget(BaseModel):
    """
    Points to a repo NAVI is working in.

    For now we assume a single local repo root, but this model is flexible
    enough to support multiple roots or remote workspaces later.
    """

    repo_id: Optional[str] = Field(
        default=None,
        description="Logical ID of the repo (for multi-repo setups).",
    )
    root_path: Optional[str] = Field(
        default=None,
        description="Absolute path on the NAVI backend host, if known.",
    )


class FileRegion(BaseModel):
    """Optional sub-portion of a file NAVI should focus on."""

    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)
    symbol: Optional[str] = Field(
        default=None,
        description="Function/class/method name when the region is symbolic.",
    )


class FileSelector(BaseModel):
    """
    Describes one or more files NAVI should interact with.

    This is intentionally expressive to support:
      - single path
      - globs
      - language-scoped queries
    """

    path: Optional[str] = Field(
        default=None,
        description="File path relative to repo root.",
    )
    glob: Optional[str] = Field(
        default=None,
        description="Glob for multiple files, e.g. 'backend/**/*.py'.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Preferred language, e.g. 'python', 'typescript'.",
    )
    region: Optional[FileRegion] = None


class CommandSpec(BaseModel):
    """
    Command NAVI should run in the dev environment.

    This powers: tests, builds, linters, migrations, etc.
    """

    command: str = Field(
        ...,
        description="Shell command to execute (without user secrets).",
    )
    cwd: Optional[str] = Field(
        default=None,
        description="Working directory (relative to repo root if not absolute).",
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Extra environment variables to set.",
    )
    timeout_seconds: Optional[int] = Field(
        default=1800,
        description="Hard timeout for the command.",
    )


class PatchOperation(BaseModel):
    """
    High-level patch description.

    We keep this abstract – planner/tool layer can decide whether to apply
    a textual diff, AST transform, etc.
    """

    description: str = Field(
        ...,
        description="Human description of what this patch does.",
    )
    target_file: FileSelector
    # textual patch; can be unified diff, inline patch, etc.
    patch_text: Optional[str] = Field(
        default=None,
        description="Optional textual patch representation.",
    )


# ---------------------------------------------------------------------------
# Intent-specific payloads
# ---------------------------------------------------------------------------


class CodeEditSpec(BaseModel):
    """Details for MODIFY_CODE / IMPLEMENT_FEATURE / FIX_BUG / REFACTOR_CODE."""

    goal: str = Field(..., description="What should the code change achieve?")
    repo: RepoTarget
    primary_files: List[FileSelector] = Field(
        default_factory=list,
        description="Files NAVI should focus on first.",
    )
    related_files: List[FileSelector] = Field(
        default_factory=list,
        description="Other files likely involved (tests, config, etc.).",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Hard constraints (e.g. 'do not change public APIs').",
    )
    allowed_languages: List[str] = Field(default_factory=list)
    patches: List[PatchOperation] = Field(
        default_factory=list,
        description="Optional pre-computed patch suggestions (from planner).",
    )


class TestRunSpec(BaseModel):
    """Details for RUN_TESTS / RUN_LINT / RUN_BUILD / RUN_CUSTOM_COMMAND."""

    repo: RepoTarget
    command: CommandSpec
    only_if_files_changed: bool = Field(
        default=False,
        description="Skip if no relevant files changed in this workflow.",
    )


class TicketInfo(BaseModel):
    """Generic representation of a Jira / GitHub / etc. ticket."""

    provider: str = Field(..., description="e.g. 'jira', 'github'")
    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ProjectManagementSpec(BaseModel):
    """Payload for CREATE_TICKET / UPDATE_TICKET / PR summaries, etc."""

    tickets: List[TicketInfo] = Field(default_factory=list)
    repo: Optional[RepoTarget] = None
    pr_number: Optional[str] = None
    notes_goal: Optional[str] = Field(
        default=None,
        description="What kind of summary/notes we want.",
    )


class WorkflowHints(BaseModel):
    """
    Hints for the orchestrator about how aggressive NAVI should be.

    This is where we encode user preferences like:
      - number of steps
      - whether to auto-run tests
      - whether to touch multiple services
    """

    autonomy_mode: AutonomyMode = AutonomyMode.ASSISTED
    max_steps: int = Field(
        default=12,
        description="Hard cap on tool steps for this intent.",
    )
    max_parallel_tasks: int = Field(
        default=1,
        description="How many tasks can run in parallel.",
    )
    auto_run_tests: bool = Field(
        default=True,
        description="Whether NAVI should automatically run tests when relevant.",
    )
    allow_cross_repo_changes: bool = Field(
        default=False,
        description="Whether the agent may touch multiple repos/services.",
    )
    allow_long_running: bool = Field(
        default=False,
        description="If True, workflows may exceed typical UI timeouts and "
        "run in the background.",
    )


# ---------------------------------------------------------------------------
# Root Intent model
# ---------------------------------------------------------------------------


class NaviIntent(BaseModel):
    """
    Root intent object flowing through the NAVI backend.

    Lifecycle:
      1) Built by intent_classifier from a user/system message.
      2) Consumed by planner to generate a concrete plan.
      3) Passed to tool_executor/orchestrator as context during execution.

    Only one of the *_spec fields is usually populated, depending on kind.
    """

    # --- identity / metadata -------------------------------------------------
    id: Optional[str] = Field(
        default=None,
        description="Optional stable ID for tracking in logs / DB.",
    )
    family: IntentFamily = IntentFamily.ENGINEERING
    kind: IntentKind = IntentKind.UNKNOWN
    source: IntentSource = IntentSource.CHAT
    priority: IntentPriority = IntentPriority.NORMAL
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Classifier confidence in [0, 1].",
    )

    # --- cross-app provider context ------------------------------------------
    provider: Provider = Field(
        default=Provider.GENERIC,
        description="External service/app this intent targets (jira, slack, github, etc.)",
    )
    object_type: Optional[str] = Field(
        default=None,
        description="Type of object being acted upon: 'issue', 'message', 'pr', 'build', 'doc', etc.",
    )
    object_id: Optional[str] = Field(
        default=None,
        description="Specific ID if mentioned (e.g., 'JIRA-123', 'PR-456', '#general')",
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional filters: status, date range, channel name, assignee, etc.",
    )

    # raw inputs
    raw_text: str = Field(
        ...,
        description="Original user/system message that produced this intent.",
    )

    # Phase 4.1.2 compatibility fields
    critical: bool = Field(
        default=False, description="Whether this intent is critical/urgent"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the intent"
    )

    # structured/query arguments extracted by the classifier (free-form)
    slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="Loose slot filling data (e.g. 'service_name', 'env').",
    )

    # --- specialized payloads -----------------------------------------------
    code_edit: Optional[CodeEditSpec] = None
    test_run: Optional[TestRunSpec] = None
    project_mgmt: Optional[ProjectManagementSpec] = None

    # --- orchestration hints -------------------------------------------------
    workflow: WorkflowHints = Field(
        default_factory=WorkflowHints,
        description="Hints controlling how the orchestrator executes this intent.",
    )

    # --- misc / extensibility ------------------------------------------------
    labels: List[str] = Field(
        default_factory=list,
        description="Optional labels, e.g. ['jira', 'critical_path'] for routing.",
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible bag for future fields without schema changes.",
    )

    # --- legacy compatibility fields -----------------------------------------
    # These are kept for backwards compatibility with existing routes and UI glue.
    # New code should use the structured fields above (workflow, code_edit, etc.)

    requires_approval: bool = Field(
        default=True,
        description="Whether NAVI should ask before applying changes (legacy field)",
    )

    target: Optional[str] = Field(
        default=None,
        description="High-level target used by older flows (legacy field)",
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form parameter bag used in older APIs (legacy field)",
    )

    time: Optional[str] = Field(
        default=None,
        description="Timestamp field used in some logging/UI code (legacy field)",
    )

    model_used: Optional[str] = Field(
        default=None,
        description="Model used for classification (telemetry field)",
    )

    provider_used: Optional[str] = Field(
        default=None,
        description="Provider used for classification (telemetry field)",
    )

    # ---------------------------------------------------------------------
    # Convenience helpers (used by planner / executor / UI)
    # ---------------------------------------------------------------------

    def is_engineering(self) -> bool:
        return self.family == IntentFamily.ENGINEERING

    def is_project_management(self) -> bool:
        return self.family == IntentFamily.PROJECT_MANAGEMENT

    def is_autonomous(self) -> bool:
        return (
            self.family == IntentFamily.AUTONOMOUS_ORCHESTRATION
            or self.workflow.autonomy_mode
            in {
                AutonomyMode.AUTONOMOUS_SESSION,
                AutonomyMode.BATCH,
            }
        )

    def requires_repo(self) -> bool:
        """True if this intent needs repo context to be meaningful."""
        if self.code_edit and self.code_edit.repo:
            return True
        if self.test_run and self.test_run.repo:
            return True
        if self.project_mgmt and self.project_mgmt.repo:
            return True
        return self.kind in {
            IntentKind.INSPECT_REPO,
            IntentKind.SEARCH_CODE,
            IntentKind.SUMMARIZE_DIFF,
            IntentKind.RUN_TESTS,
            IntentKind.RUN_BUILD,
            IntentKind.RUN_LINT,
            IntentKind.EDIT_INFRA,
            IntentKind.UPDATE_DEPENDENCIES,
            IntentKind.IMPLEMENT_FEATURE,
            IntentKind.FIX_BUG,
        }

    def summary(self) -> str:
        """Short human-readable summary for logs / UI."""
        return (
            f"[{self.kind.value}] "
            f"family={self.family.value} "
            f"priority={self.priority.value} "
            f"conf={self.confidence:.2f}"
        )


__all__ = [
    "IntentFamily",
    "IntentKind",
    "IntentPriority",
    "IntentSource",
    "AutonomyMode",
    "RepoTarget",
    "FileRegion",
    "FileSelector",
    "CommandSpec",
    "PatchOperation",
    "CodeEditSpec",
    "TestRunSpec",
    "TicketInfo",
    "ProjectManagementSpec",
    "WorkflowHints",
    "NaviIntent",
]
