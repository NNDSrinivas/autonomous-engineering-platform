"""
NAVI Intent Classifier v2
=========================

Light-weight, dependency-free classifier that maps a user message +
(optional) metadata into a `NaviIntent`.

This is **rule / heuristic based** so it works out-of-the-box without
calling an LLM, but the public API is designed so you can later swap in
an LLM-powered implementation without touching the rest of the system.

Public entry points
-------------------

- `IntentClassifier` class
- `classify_intent(...)`      → returns `NaviIntent`
- `detect_intent(...)`        → alias for `classify_intent`

The classifier accepts either a **string** or an object with a
`.content` attribute (to stay compatible with typical chat message
types used elsewhere).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from .intent_schema import (
    AutonomyMode,
    CodeEditSpec,
    CommandSpec,
    IntentFamily,
    IntentKind,
    IntentPriority,
    IntentSource,
    NaviIntent,
    ProjectManagementSpec,
    Provider,
    RepoTarget,
    TestRunSpec,
    WorkflowHints,
    FileSelector,
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _norm_text(message: Any) -> str:
    """
    Normalise the incoming message to a plain string.

    We deliberately accept "anything" here to be forgiving with upstream
    types (e.g. Pydantic models, chat message objects, etc.).
    """
    if isinstance(message, str):
        return message

    # Common pattern: ChatMessage(content="...")
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content

    return str(message)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def _is_prod_readiness_query(text: str) -> bool:
    """Detect prod-readiness / go-live verification requests."""
    readiness_signals = (
        "prod ready",
        "production ready",
        "ready for prod",
        "ready for production",
        "prod readiness",
        "production readiness",
        "go live",
        "fully implemented",
        "end-to-end",
        "end to end",
        "ready for prod deployment",
        "ready for production deployment",
    )
    if not _contains_any(text, readiness_signals):
        return False

    verification_signals = (
        "check",
        "verify",
        "working",
        "stable",
        "deployment",
        "deploy",
        "?",
    )
    return _contains_any(text, verification_signals)


def _priority_from_text(text: str) -> IntentPriority:
    if _contains_any(text, ("p0", "sev0", "sev 0", "production down", "outage")):
        return IntentPriority.CRITICAL
    if _contains_any(text, ("urgent", "asap", "p1", "sev1", "blocker")):
        return IntentPriority.HIGH
    if _contains_any(text, ("low priority", "whenever", "nice to have")):
        return IntentPriority.LOW
    return IntentPriority.NORMAL


def _detect_provider(text: str) -> Optional[Provider]:
    """
    Detect which connector/provider the user is asking about.

    Returns None if no specific provider is mentioned.
    """
    # -------------------------------------------------------------------------
    # Issue Tracking & Project Management
    # -------------------------------------------------------------------------

    # Jira keywords
    if _contains_any(
        text, ("jira", "jira ticket", "jira issue", "jira task", "jira sprint")
    ):
        return Provider.JIRA

    # Linear keywords
    if _contains_any(text, ("linear", "lin-", "linear issue", "linear ticket")):
        return Provider.LINEAR

    # Asana keywords
    if _contains_any(text, ("asana", "asana task", "asana project")):
        return Provider.ASANA

    # Trello keywords
    if _contains_any(text, ("trello", "trello board", "trello card", "trello list")):
        return Provider.TRELLO

    # Monday.com keywords
    if _contains_any(text, ("monday", "monday.com", "monday board", "monday item")):
        return Provider.MONDAY

    # ClickUp keywords
    if _contains_any(text, ("clickup", "click up", "clickup task", "clickup space")):
        return Provider.CLICKUP

    # -------------------------------------------------------------------------
    # Code & Version Control
    # -------------------------------------------------------------------------

    # GitLab keywords (check before GitHub to handle "merge request" properly)
    if _contains_any(
        text,
        (
            "gitlab",
            "merge request",
            " mr ",
            "gitlab issue",
            "gitlab pipeline",
            "gitlab ci",
        ),
    ):
        return Provider.GITLAB

    # Bitbucket keywords
    if _contains_any(
        text,
        ("bitbucket", "bitbucket pr", "bitbucket pipeline", "bitbucket repo"),
    ):
        return Provider.BITBUCKET

    # -------------------------------------------------------------------------
    # CI/CD & Deployment
    # -------------------------------------------------------------------------

    # GitHub Actions keywords (check before general GitHub)
    if _contains_any(
        text,
        ("github action", "github actions", "workflow run", "action run", "gh action"),
    ):
        return Provider.GITHUB_ACTIONS

    # GitHub keywords
    if _contains_any(
        text,
        (
            "github",
            "gh issue",
            "gh pr",
            "github issue",
            "github pr",
            "pull request",
            " pr ",
        ),
    ):
        return Provider.GITHUB

    # CircleCI keywords
    if _contains_any(
        text, ("circleci", "circle ci", "circle pipeline", "circleci job")
    ):
        return Provider.CIRCLECI

    # Vercel keywords
    if _contains_any(
        text, ("vercel", "vercel deployment", "vercel project", "vercel preview")
    ):
        return Provider.VERCEL

    # Jenkins keywords
    if _contains_any(
        text, ("jenkins", "jenkins job", "jenkins pipeline", "jenkins build")
    ):
        return Provider.JENKINS

    # -------------------------------------------------------------------------
    # Communication
    # -------------------------------------------------------------------------

    # Slack keywords
    if _contains_any(
        text,
        ("slack", "slack channel", "slack message", "slack dm"),
    ):
        return Provider.SLACK

    # Teams keywords
    if _contains_any(
        text, ("teams", "microsoft teams", "teams channel", "teams message")
    ):
        return Provider.TEAMS

    # Discord keywords
    if _contains_any(
        text, ("discord", "discord channel", "discord server", "discord message")
    ):
        return Provider.DISCORD

    # -------------------------------------------------------------------------
    # Documentation & Knowledge
    # -------------------------------------------------------------------------

    # Confluence keywords
    if _contains_any(
        text,
        ("confluence", "confluence page", "confluence doc", "confluence space"),
    ):
        return Provider.CONFLUENCE

    # Notion keywords
    if _contains_any(
        text,
        ("notion", "notion page", "notion doc", "notion database"),
    ):
        return Provider.NOTION

    # Google Drive keywords
    if _contains_any(
        text,
        ("google drive", "gdrive", "drive file", "drive folder", "my drive"),
    ):
        return Provider.GOOGLE_DRIVE

    # Google Docs keywords
    if _contains_any(text, ("google doc", "gdoc", "google docs")):
        return Provider.GOOGLE_DOCS

    # -------------------------------------------------------------------------
    # Meetings & Calendar
    # -------------------------------------------------------------------------

    # Zoom keywords
    if _contains_any(
        text, ("zoom", "zoom recording", "zoom meeting", "zoom transcript")
    ):
        return Provider.ZOOM

    # Google Calendar keywords
    if _contains_any(
        text,
        (
            "google calendar",
            "gcal",
            "calendar event",
            "my calendar",
            "today's meetings",
        ),
    ):
        return Provider.GOOGLE_CALENDAR

    # Loom keywords
    if _contains_any(text, ("loom", "loom video", "loom recording", "loom transcript")):
        return Provider.LOOM

    # -------------------------------------------------------------------------
    # Monitoring & Security
    # -------------------------------------------------------------------------

    # Datadog keywords
    if _contains_any(
        text,
        (
            "datadog",
            "dd monitor",
            "datadog monitor",
            "datadog incident",
            "datadog dashboard",
        ),
    ):
        return Provider.DATADOG

    # Sentry keywords
    if _contains_any(
        text, ("sentry", "sentry issue", "sentry error", "sentry project")
    ):
        return Provider.SENTRY

    # PagerDuty keywords
    if _contains_any(
        text,
        ("pagerduty", "pager duty", "oncall", "on-call", "pagerduty incident"),
    ):
        return Provider.PAGERDUTY

    # Snyk keywords
    if _contains_any(
        text, ("snyk", "snyk vulnerability", "snyk project", "snyk issue")
    ):
        return Provider.SNYK

    # SonarQube keywords
    if _contains_any(
        text,
        ("sonarqube", "sonar", "code quality", "quality gate", "sonar issue"),
    ):
        return Provider.SONARQUBE

    # -------------------------------------------------------------------------
    # Design
    # -------------------------------------------------------------------------

    # Figma keywords
    if _contains_any(text, ("figma", "figma file", "figma design", "figma comment")):
        return Provider.FIGMA

    return None


def _autonomy_from_text(text: str) -> AutonomyMode:
    if _contains_any(
        text,
        (
            "run this in the background",
            "batch of tasks",
            "bulk apply",
            "auto apply everywhere",
        ),
    ):
        return AutonomyMode.BATCH

    if _contains_any(
        text,
        (
            "just do it",
            "don't ask me",
            "no confirmation",
            "fully autonomous",
            "hands free",
            "end to end",
        ),
    ):
        return AutonomyMode.AUTONOMOUS_SESSION

    if _contains_any(
        text,
        (
            "just run this once",
            "one-off",
            "one time",
            "single command",
        ),
    ):
        return AutonomyMode.SINGLE_STEP

    # Default: NAVI proposes and the user approves
    return AutonomyMode.ASSISTED


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------


@dataclass
class IntentClassifierConfig:
    """
    Configuration / defaults for the classifier.

    Nothing here is persisted; it purely controls classification hints.
    """

    default_repo: Optional[RepoTarget] = None
    default_test_command: str = "pytest"
    default_lint_command: str = "ruff check ."
    default_build_command: str = "npm run build"


class IntentClassifier:
    """
    Heuristic intent classifier.

    Later you can plug in an LLM here; just keep the `classify()` contract.
    """

    def __init__(self, config: Optional[IntentClassifierConfig] = None) -> None:
        self.config = config or IntentClassifierConfig()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def classify(
        self,
        message: Any,
        *,
        repo: Optional[RepoTarget] = None,
        source: IntentSource = IntentSource.CHAT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NaviIntent:
        """
        Classify an incoming message into a `NaviIntent`.

        Parameters
        ----------
        message:
            User message or object with `.content`.
        repo:
            Optional repository context.
        source:
            Where the message came from (chat, IDE, webhook, ...).
        metadata:
            Optional structured hints. The classifier understands a few
            special keys, all of which are **optional**:

            - "family": override IntentFamily
            - "kind": override IntentKind
            - "priority": override IntentPriority
            - "autonomy_mode": override AutonomyMode
            - "files": list of file paths to focus on
            - "language": primary language (e.g. "python")
            - "tickets": ticket metadata for project mgmt intents
        """
        metadata = metadata or {}
        raw_text = _norm_text(message)
        text = raw_text.lower()

        # --- base metadata -------------------------------------------------
        family = metadata.get("family") or self._infer_family(text)
        kind = metadata.get("kind") or self._infer_kind(text, family)
        priority = metadata.get("priority") or _priority_from_text(text)
        autonomy_mode = metadata.get("autonomy_mode") or _autonomy_from_text(text)

        repo_target = repo or self.config.default_repo

        workflow = WorkflowHints(
            autonomy_mode=autonomy_mode,
            max_steps=self._default_max_steps_for_kind(kind),
            auto_run_tests=self._default_auto_run_tests(kind),
            allow_cross_repo_changes=_contains_any(
                text, ("all services", "every repo", "monorepo", "multi repo")
            ),
            allow_long_running=_contains_any(
                text, ("long running", "background", "overnight", "nightly")
            ),
        )

        # --- main payloads -------------------------------------------------
        code_edit = None
        test_run = None
        project_mgmt = None

        # Files hint from metadata (e.g. current file in IDE)
        files_hint = metadata.get("files") or []
        language_hint = metadata.get("language")

        if isinstance(files_hint, str):
            files_hint = [files_hint]

        file_selectors = [
            FileSelector(path=f, language=language_hint) for f in files_hint
        ]

        if kind in {
            IntentKind.MODIFY_CODE,
            IntentKind.CREATE_FILE,
            IntentKind.REFACTOR_CODE,
            IntentKind.IMPLEMENT_FEATURE,
            IntentKind.FIX_BUG,
            IntentKind.UPDATE_DEPENDENCIES,
            IntentKind.EDIT_INFRA,
        }:
            goal = self._goal_from_text(kind, raw_text)
            code_edit = CodeEditSpec(
                goal=goal,
                repo=repo_target or RepoTarget(),
                primary_files=file_selectors,
                allowed_languages=[language_hint] if language_hint else [],
            )

        if kind in {
            IntentKind.RUN_TESTS,
            IntentKind.RUN_LINT,
            IntentKind.RUN_BUILD,
            IntentKind.RUN_CUSTOM_COMMAND,
        }:
            command = self._command_for_test_like_intent(kind, text, metadata)
            test_run = TestRunSpec(
                repo=repo_target or RepoTarget(),
                command=command,
                only_if_files_changed=metadata.get("only_if_files_changed", False),
            )

        if family == IntentFamily.PROJECT_MANAGEMENT:
            project_mgmt = ProjectManagementSpec(
                tickets=metadata.get("tickets", []),
                repo=repo_target,
                pr_number=metadata.get("pr_number"),
                notes_goal=metadata.get("notes_goal"),
            )

        # crude confidence score based on how specific we were
        confidence = self._confidence_score(kind, raw_text)

        # --- provider detection ------------------------------------------------
        # Detect which connector/provider the user is referring to
        provider = metadata.get("provider") or _detect_provider(text)
        provider_str = provider.value if provider else None

        intent = NaviIntent(
            family=family,
            kind=kind,
            source=source,
            priority=priority,
            confidence=confidence,
            raw_text=raw_text,
            slots={
                "language": language_hint,
                "provider": provider_str,  # Add detected provider to slots
                **{
                    k: v
                    for k, v in metadata.items()
                    if k not in {"files", "language", "provider"}
                },
            },
            code_edit=code_edit,
            test_run=test_run,
            project_mgmt=project_mgmt,
            workflow=workflow,
        )

        return intent

    # ------------------------------------------------------------------ #
    # Inference helpers
    # ------------------------------------------------------------------ #

    def _infer_family(self, text: str) -> IntentFamily:
        # Keep readiness audits in engineering so they route to repo tooling,
        # not project-management ticket summaries.
        if _is_prod_readiness_query(text):
            return IntentFamily.ENGINEERING

        # Check for simple greetings first (before other classifications)
        if _contains_any(
            text,
            (
                "hi",
                "hello",
                "hey",
                "good morning",
                "good afternoon",
                "good evening",
                "howdy",
                "greetings",
            ),
        ):
            # Only if it's a pure greeting with no other intent
            words = text.strip().split()
            if len(words) <= 3 and not any(
                work_word in text
                for work_word in ["jira", "code", "help", "task", "work", "project"]
            ):
                return IntentFamily.ENGINEERING  # Will be handled as GREET in kind

        if _contains_any(
            text,
            (
                # Jira keywords
                "jira",
                "ticket",
                "story",
                "backlog",
                "sprint",
                "epic",
                "release notes",
                "changelog",
                # GitHub/GitLab PR keywords
                "pull request",
                "pr ",
                "merge request",
                " mr ",
                # Linear keywords
                "linear",
                "lin-",
                # Asana keywords
                "asana",
                "asana task",
                "asana project",
                # GitLab keywords
                "gitlab",
                "pipeline",
                # Notion keywords
                "notion",
                "notion page",
                "notion doc",
                # Trello keywords
                "trello",
                "trello board",
                "trello card",
                # Monday.com keywords
                "monday",
                "monday.com",
                "monday board",
                # ClickUp keywords
                "clickup",
                "click up",
                # Bitbucket keywords
                "bitbucket",
                # Confluence keywords
                "confluence",
                "confluence page",
                # Google Drive/Docs keywords
                "google drive",
                "gdrive",
                "google doc",
                # Figma keywords
                "figma",
                "figma file",
                # General issue/task keywords
                "my issues",
                "my tasks",
                "assigned to me",
                "my open",
            ),
        ):
            return IntentFamily.PROJECT_MANAGEMENT

        # CI/CD and Monitoring intents
        if _contains_any(
            text,
            (
                # CI/CD keywords
                "github action",
                "circleci",
                "vercel",
                "deployment",
                "deploy status",
                "build status",
                "workflow run",
                # Monitoring keywords
                "datadog",
                "monitor",
                "incident",
                "alerting",
                "sentry",
                "sentry issue",
                "pagerduty",
                "oncall",
                "on-call",
                # Security keywords
                "snyk",
                "vulnerability",
                "sonarqube",
                "code quality",
                "quality gate",
            ),
        ):
            return IntentFamily.PROJECT_MANAGEMENT

        # Communication intents
        if _contains_any(
            text,
            (
                "slack",
                "slack channel",
                "discord",
                "discord channel",
                "teams",
                "teams channel",
            ),
        ):
            return IntentFamily.PROJECT_MANAGEMENT

        # Meetings/Calendar intents
        if _contains_any(
            text,
            (
                "zoom",
                "zoom recording",
                "loom",
                "loom video",
                "google calendar",
                "gcal",
                "calendar event",
                "today's meetings",
                "upcoming meetings",
            ),
        ):
            return IntentFamily.PROJECT_MANAGEMENT

        if _contains_any(
            text,
            (
                "run this every",
                "schedule",
                "nightly",
                "cron",
                "background worker",
                "long running workflow",
                "auto apply jobs",
            ),
        ):
            return IntentFamily.AUTONOMOUS_ORCHESTRATION

        return IntentFamily.ENGINEERING

    def _infer_kind(self, text: str, family: IntentFamily) -> IntentKind:
        # Engineering intents
        if family == IntentFamily.ENGINEERING:
            if _is_prod_readiness_query(text):
                return IntentKind.PROD_READINESS_AUDIT

            # Check for greetings first
            greeting_terms = (
                "hi",
                "hello",
                "hey",
                "good morning",
                "good afternoon",
                "good evening",
                "howdy",
                "greetings",
            )
            if any(
                re.search(rf"\b{re.escape(term)}\b", text) for term in greeting_terms
            ):
                # Only if it's a pure greeting with minimal other words
                words = text.strip().split()
                if len(words) <= 3 and not any(
                    work_word in text
                    for work_word in ["jira", "code", "help", "task", "work", "project"]
                ):
                    return IntentKind.GREET

            # Phase 4.1.2: Problems tab / VS Code diagnostics
            if _contains_any(
                text,
                (
                    "problems tab",
                    "fix errors",
                    "fix problems",
                    "diagnostics",
                    "errors in problems",
                    "fix all errors",
                    "problems panel",
                    "vs code errors",
                    "compilation errors",
                ),
            ):
                return IntentKind.FIX_DIAGNOSTICS

            if _contains_any(
                text,
                (
                    "failing test",
                    "tests are failing",
                    "fix the bug",
                    "bug",
                    "bugs",
                    "stack trace",
                    "exception",
                    "runtime error",
                    "compile error",
                    "fix this bug",
                    "error:",
                    "typeerror",
                    "syntaxerror",
                    "referenceerror",
                    "nameerror",
                    "valueerror",
                    "attributeerror",
                    "keyerror",
                    "indexerror",
                    "importerror",
                    "modulenotfounderror",
                    "cannot read property",
                    "undefined is not",
                    "null is not",
                    "is not defined",
                    "is not a function",
                    "how do i fix",
                    "getting this error",
                    "getting an error",
                    "i'm getting",
                    "im getting",
                    "this error",
                    "fix error",
                    "resolve error",
                    "debug",
                    "not working",
                    "doesn't work",
                    "broken",
                    "crash",
                    "fails",
                    "failed",
                ),
            ):
                return IntentKind.FIX_BUG

            if "refactor" in text or "clean up" in text or "cleanup" in text:
                return IntentKind.REFACTOR_CODE

            if _contains_any(
                text,
                (
                    "implement feature",
                    "add feature",
                    "new endpoint",
                    "api endpoint",
                    "new api endpoint",
                    "add api",
                    "create endpoint",
                    "support this use case",
                    "create a",
                    "build a",
                    "build the",
                    "write a",
                    "make a",
                    "implement a",
                    "add a new",
                    "create new",
                    "build new",
                    "write new",
                    "implement the",
                    "add functionality",
                    "develop a",
                    "code a",
                    "set up",
                    "setup",
                    "crud",
                    "api for",
                    "component for",
                    "module for",
                    "service for",
                    "function that",
                    "method that",
                    "class that",
                    "authentication",
                    "login",
                    "logout",
                    "signup",
                    "registration",
                    "user management",
                    "form validation",
                    "data validation",
                    "error handling",
                    "logging",
                    "caching",
                    "pagination",
                    "search functionality",
                    "filter",
                    "sort",
                    "export",
                    "import",
                    "upload",
                    "download",
                    "notification",
                    "email",
                    "webhook",
                    "integration",
                ),
            ):
                return IntentKind.IMPLEMENT_FEATURE

            if _contains_any(
                text,
                (
                    "write tests",
                    "add tests",
                    "generate tests",
                    "unit tests for",
                    "test coverage",
                ),
            ):
                return IntentKind.GENERATE_TESTS

            if _contains_any(
                text,
                (
                    "run tests",
                    "run the tests",
                    "run all unit tests",
                    "execute tests",
                    "execute pytest",
                    "run pytest",
                    "run unit tests",
                    "ci tests",
                ),
            ):
                return IntentKind.RUN_TESTS

            if _contains_any(
                text,
                (
                    "run lint",
                    "lint the code",
                    "ruff",
                    "flake8",
                    "eslint",
                ),
            ):
                return IntentKind.RUN_LINT

            if _contains_any(
                text,
                (
                    "build the project",
                    "build the app",
                    "run build",
                    "webpack build",
                    "vite build",
                ),
            ):
                return IntentKind.RUN_BUILD

            if _contains_any(
                text,
                (
                    "run this project",
                    "run the project",
                    "run this app",
                    "run the app",
                    "start the server",
                    "start server",
                    "start the app",
                    "start this",
                    "run this",
                    "execute this",
                    "how do i run",
                    "how to run",
                    "how to start",
                    "npm start",
                    "npm run dev",
                    "python run",
                    "uvicorn",
                    "flask run",
                    "django runserver",
                    "node index",
                    "node server",
                    "yarn start",
                    "yarn dev",
                ),
            ):
                return IntentKind.RUN_CUSTOM_COMMAND

            if _contains_any(
                text,
                (
                    "explain this code",
                    "what does this code do",
                    "explain how this works",
                    "help me understand this function",
                    "what is this",
                    "what does this",
                    "how does this",
                    "what is the purpose",
                    "what are the",
                    "describe this",
                    "tell me about",
                    "explain the",
                    "what is this project",
                    "what does this project",
                    "what framework",
                    "what language",
                    "what technologies",
                    "tech stack",
                    "architecture",
                ),
            ):
                return IntentKind.EXPLAIN_CODE

            if _contains_any(
                text,
                (
                    "search the code",
                    "find usages",
                    "grep for",
                    "where is",
                    "search for",
                ),
            ):
                return IntentKind.SEARCH_CODE

            if _contains_any(
                text,
                (
                    "dockerfile",
                    "docker-compose",
                    "helm chart",
                    "kubernetes",
                    "infra",
                    "terraform",
                ),
            ):
                return IntentKind.EDIT_INFRA

            if _contains_any(
                text,
                (
                    "upgrade dependencies",
                    "bump versions",
                    "update packages",
                    "dependency update",
                    "update requirements.txt",
                    "update package.json",
                ),
            ):
                return IntentKind.UPDATE_DEPENDENCIES

            # Deployment intents
            if _contains_any(
                text,
                (
                    "deploy",
                    "deploy to",
                    "deploy this",
                    "push to production",
                    "push to prod",
                    "ship to",
                    "ship it",
                    "go live",
                    "release to",
                    "deploy to vercel",
                    "deploy to railway",
                    "deploy to fly",
                    "deploy to netlify",
                    "deploy to heroku",
                    "deploy to render",
                    "deploy to cloudflare",
                    "deploy to aws",
                    "deploy to gcp",
                    "deploy to azure",
                    "vercel deploy",
                    "railway up",
                    "fly deploy",
                    "netlify deploy",
                    "production deployment",
                    "staging deployment",
                ),
            ):
                return IntentKind.DEPLOY

            if _contains_any(
                text,
                (
                    "summarize this diff",
                    "summarise this diff",
                    "explain this diff",
                    "explain this change",
                ),
            ):
                return IntentKind.SUMMARIZE_DIFF

            if "summarize file" in text or "explain this file" in text:
                return IntentKind.SUMMARIZE_FILE

            # default engineering intent: inspect repo / context
            return IntentKind.INSPECT_REPO

        # Project management intents
        if family == IntentFamily.PROJECT_MANAGEMENT:
            if _is_prod_readiness_query(text):
                return IntentKind.PROD_READINESS_AUDIT

            # Check for Jira "my issues" patterns
            if _contains_any(
                text,
                (
                    "list the jira tasks assigned to me",
                    "show my jira tickets",
                    "my jira issues",
                    "jira tasks assigned to me",
                    "list my jira tasks",
                    "show jira issues assigned to me",
                    "what jira tickets am i currently on",
                    "my open jira tickets",
                ),
            ):
                return IntentKind.JIRA_LIST_MY_ISSUES

            # Check for Linear "my issues" patterns
            if (
                _contains_any(
                    text,
                    (
                        "my linear issues",
                        "linear issues assigned to me",
                        "show my linear tasks",
                        "list my linear issues",
                        "linear tasks",
                        "lin-",
                    ),
                )
                and "linear" in text
            ):
                return (
                    IntentKind.LIST_MY_ITEMS
                )  # Provider detected via _detect_provider

            # Check for GitLab "my MRs/issues" patterns
            if _contains_any(
                text,
                (
                    "my gitlab",
                    "my merge requests",
                    "my mrs",
                    "gitlab issues assigned to me",
                    "gitlab mrs",
                    "gitlab merge requests",
                    "my pipelines",
                    "pipeline status",
                ),
            ) and ("gitlab" in text or "merge request" in text or " mr " in text):
                return (
                    IntentKind.LIST_MY_ITEMS
                )  # Provider detected via _detect_provider

            # Check for GitHub "my PRs/issues" patterns
            if (
                _contains_any(
                    text,
                    (
                        "my github issues",
                        "my github prs",
                        "github issues assigned to me",
                        "github prs assigned to me",
                        "my pull requests",
                    ),
                )
                and "github" in text
            ):
                return (
                    IntentKind.LIST_MY_ITEMS
                )  # Provider detected via _detect_provider

            # Check for Asana "my tasks" patterns
            if (
                _contains_any(
                    text,
                    (
                        "my asana tasks",
                        "asana tasks assigned to me",
                        "show my asana tasks",
                        "list my asana tasks",
                        "asana projects",
                    ),
                )
                and "asana" in text
            ):
                return (
                    IntentKind.LIST_MY_ITEMS
                )  # Provider detected via _detect_provider

            # Check for Notion "search/list" patterns
            if (
                _contains_any(
                    text,
                    (
                        "search notion",
                        "find notion",
                        "notion pages",
                        "my notion docs",
                        "notion databases",
                        "recent notion pages",
                    ),
                )
                and "notion" in text
            ):
                return (
                    IntentKind.LIST_MY_ITEMS
                )  # Provider detected via _detect_provider

            # Check for Trello patterns
            if (
                _contains_any(
                    text,
                    (
                        "my trello cards",
                        "trello boards",
                        "show my trello",
                        "list trello cards",
                        "trello tasks",
                    ),
                )
                and "trello" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Monday.com patterns
            if (
                _contains_any(
                    text,
                    (
                        "my monday items",
                        "monday boards",
                        "show my monday",
                        "list monday items",
                        "monday tasks",
                    ),
                )
                and "monday" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for ClickUp patterns
            if _contains_any(
                text,
                (
                    "my clickup tasks",
                    "clickup spaces",
                    "show my clickup",
                    "list clickup tasks",
                ),
            ) and ("clickup" in text or "click up" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for Bitbucket patterns
            if (
                _contains_any(
                    text,
                    (
                        "my bitbucket prs",
                        "bitbucket repos",
                        "show my bitbucket",
                        "bitbucket pipelines",
                    ),
                )
                and "bitbucket" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Confluence patterns
            if (
                _contains_any(
                    text,
                    (
                        "search confluence",
                        "confluence pages",
                        "confluence spaces",
                        "find confluence",
                    ),
                )
                and "confluence" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Google Drive patterns
            if _contains_any(
                text,
                (
                    "my drive files",
                    "google drive files",
                    "search drive",
                    "list drive files",
                    "recent files",
                ),
            ) and ("drive" in text or "gdrive" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for Figma patterns
            if (
                _contains_any(
                    text,
                    (
                        "my figma files",
                        "figma projects",
                        "show figma",
                        "list figma files",
                    ),
                )
                and "figma" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Zoom patterns
            if (
                _contains_any(
                    text,
                    (
                        "zoom recordings",
                        "my zoom meetings",
                        "zoom transcripts",
                        "list zoom recordings",
                    ),
                )
                and "zoom" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Loom patterns
            if (
                _contains_any(
                    text,
                    (
                        "loom videos",
                        "my loom recordings",
                        "loom transcripts",
                        "list loom videos",
                    ),
                )
                and "loom" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Google Calendar patterns
            if _contains_any(
                text,
                (
                    "my calendar events",
                    "today's calendar",
                    "upcoming events",
                    "calendar meetings",
                    "show my calendar",
                ),
            ) and ("calendar" in text or "gcal" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for Datadog patterns
            if (
                _contains_any(
                    text,
                    (
                        "datadog monitors",
                        "alerting monitors",
                        "datadog incidents",
                        "datadog dashboards",
                        "show monitors",
                    ),
                )
                and "datadog" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Sentry patterns
            if (
                _contains_any(
                    text,
                    (
                        "sentry issues",
                        "sentry errors",
                        "sentry projects",
                        "show sentry",
                        "list sentry issues",
                    ),
                )
                and "sentry" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for PagerDuty patterns
            if _contains_any(
                text,
                (
                    "pagerduty incidents",
                    "who's on call",
                    "oncall schedule",
                    "show oncall",
                    "pagerduty schedule",
                ),
            ) and ("pagerduty" in text or "oncall" in text or "on-call" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for Snyk patterns
            if (
                _contains_any(
                    text,
                    (
                        "snyk vulnerabilities",
                        "snyk issues",
                        "snyk projects",
                        "security vulnerabilities",
                    ),
                )
                and "snyk" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for SonarQube patterns
            if _contains_any(
                text,
                (
                    "sonarqube issues",
                    "code quality issues",
                    "quality gate status",
                    "sonar projects",
                ),
            ) and ("sonarqube" in text or "sonar" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for GitHub Actions patterns
            if _contains_any(
                text,
                (
                    "github actions",
                    "workflow runs",
                    "action status",
                    "list workflows",
                ),
            ) and ("github action" in text or "workflow" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for CircleCI patterns
            if _contains_any(
                text,
                (
                    "circleci pipelines",
                    "circleci jobs",
                    "circle builds",
                    "circleci status",
                ),
            ) and ("circleci" in text or "circle ci" in text):
                return IntentKind.LIST_MY_ITEMS

            # Check for Vercel patterns
            if (
                _contains_any(
                    text,
                    (
                        "vercel deployments",
                        "vercel projects",
                        "deployment status",
                        "vercel preview",
                    ),
                )
                and "vercel" in text
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Discord patterns
            if (
                _contains_any(
                    text,
                    (
                        "discord channels",
                        "discord messages",
                        "discord servers",
                        "show discord",
                    ),
                )
                and "discord" in text
            ):
                return IntentKind.SUMMARIZE_CHANNEL

            # Check for general "my items" across any provider
            if _contains_any(
                text,
                (
                    "my issues",
                    "my tasks",
                    "assigned to me",
                    "show my",
                    "list my",
                    "what am i working on",
                    "my open issues",
                    "my open tasks",
                ),
            ):
                return IntentKind.LIST_MY_ITEMS

            # Check for Slack channel summary patterns
            if _contains_any(
                text,
                (
                    "summarise today's standup channel",
                    "summarize the standup slack channel",
                    "what happened in #standup",
                    "show recent messages from",
                    "what did i miss in #",
                    "summarize slack channel",
                    "slack standup summary",
                    "slack messages",
                    "recent slack",
                ),
            ):
                return IntentKind.SLACK_SUMMARIZE_CHANNEL

            if _contains_any(
                text,
                (
                    "create ticket",
                    "open a ticket",
                    "file a bug",
                    "new jira",
                    "new story",
                    "new issue",
                ),
            ):
                return IntentKind.CREATE_TICKET

            if _contains_any(
                text,
                (
                    "update ticket",
                    "update the jira",
                    "move this to",
                    "transition ticket",
                ),
            ):
                return IntentKind.UPDATE_TICKET

            if _contains_any(
                text,
                (
                    "summarize the sprint",
                    "summarize tickets",
                    "ticket summary",
                    "backlog summary",
                ),
            ):
                return IntentKind.SUMMARIZE_TICKETS

            if _contains_any(
                text,
                (
                    "summarize this pr",
                    "summarise this pr",
                    "pr summary",
                    "review this pr",
                    "code review",
                ),
            ):
                if "review" in text:
                    return IntentKind.REVIEW_PR
                return IntentKind.SUMMARIZE_PR

            if _contains_any(
                text,
                (
                    "release notes",
                    "changelog",
                    "what changed in this release",
                ),
            ):
                return IntentKind.GENERATE_RELEASE_NOTES

            return IntentKind.SUMMARIZE_TICKETS

        # Autonomous / orchestration intents
        if family == IntentFamily.AUTONOMOUS_ORCHESTRATION:
            if _contains_any(
                text,
                (
                    "continue previous session",
                    "continue where we left off",
                    "resume session",
                ),
            ):
                return IntentKind.CONTINUE_SESSION

            if _contains_any(
                text,
                (
                    "cancel workflow",
                    "stop the agent",
                    "abort run",
                ),
            ):
                return IntentKind.CANCEL_WORKFLOW

            if _contains_any(
                text,
                (
                    "nightly job",
                    "run every day",
                    "run every night",
                    "schedule this task",
                ),
            ):
                return IntentKind.SCHEDULED_TASK

            if _contains_any(
                text,
                (
                    "background job",
                    "batch job",
                    "bulk change",
                    "mass update",
                ),
            ):
                return IntentKind.BACKGROUND_WORKFLOW

            return IntentKind.AUTONOMOUS_SESSION

        # Fallback
        return IntentKind.UNKNOWN

    # ------------------------------------------------------------------ #

    def _default_max_steps_for_kind(self, kind: IntentKind) -> int:
        if kind in {IntentKind.RUN_TESTS, IntentKind.RUN_LINT, IntentKind.RUN_BUILD}:
            return 4
        if kind == IntentKind.PROD_READINESS_AUDIT:
            return 10
        if kind in {
            IntentKind.FIX_BUG,
            IntentKind.IMPLEMENT_FEATURE,
            IntentKind.UPDATE_DEPENDENCIES,
            IntentKind.EDIT_INFRA,
        }:
            return 16
        if kind in {IntentKind.AUTONOMOUS_SESSION, IntentKind.BACKGROUND_WORKFLOW}:
            return 32
        return 8

    def _default_auto_run_tests(self, kind: IntentKind) -> bool:
        return kind in {
            IntentKind.FIX_BUG,
            IntentKind.IMPLEMENT_FEATURE,
            IntentKind.REFACTOR_CODE,
            IntentKind.UPDATE_DEPENDENCIES,
            IntentKind.PROD_READINESS_AUDIT,
        }

    def _command_for_test_like_intent(
        self,
        kind: IntentKind,
        text: str,
        metadata: Dict[str, Any],
    ) -> CommandSpec:
        # Allow explicit override
        explicit = metadata.get("command")
        if isinstance(explicit, str):
            return CommandSpec(command=explicit)

        if kind == IntentKind.RUN_TESTS:
            return CommandSpec(command=self.config.default_test_command)
        if kind == IntentKind.RUN_LINT:
            return CommandSpec(command=self.config.default_lint_command)
        if kind == IntentKind.RUN_BUILD:
            return CommandSpec(command=self.config.default_build_command)

        # Generic one-off command – try to grab a shell fragment
        # e.g. "run `make ci`" → "make ci"
        import re

        m = re.search(r"`([^`]+)`", text)
        if m:
            return CommandSpec(command=m.group(1))

        # last resort: pass the whole message
        return CommandSpec(command=text.strip() or "echo 'no command specified'")

    def _goal_from_text(self, kind: IntentKind, raw_text: str) -> str:
        if kind == IntentKind.FIX_BUG:
            return "Fix the reported bug and ensure all tests pass."
        if kind == IntentKind.IMPLEMENT_FEATURE:
            return "Implement the described feature end-to-end."
        if kind == IntentKind.REFACTOR_CODE:
            return "Refactor the targeted code for clarity and maintainability."
        if kind == IntentKind.UPDATE_DEPENDENCIES:
            return "Update the relevant dependencies safely."
        if kind == IntentKind.EDIT_INFRA:
            return "Update infrastructure / deployment configuration as requested."
        if kind == IntentKind.CREATE_FILE:
            return "Create the requested file(s) with appropriate implementation."
        if kind == IntentKind.MODIFY_CODE:
            return "Apply the requested edits to the codebase."
        if kind == IntentKind.PROD_READINESS_AUDIT:
            return "Run concrete verification commands and report whether this repo is production-ready."
        return raw_text

    def _confidence_score(self, kind: IntentKind, raw_text: str) -> float:
        # Very rough heuristic: more specific kinds get higher confidence.
        if kind == IntentKind.UNKNOWN:
            return 0.3
        if kind in {
            IntentKind.FIX_BUG,
            IntentKind.IMPLEMENT_FEATURE,
            IntentKind.REFACTOR_CODE,
            IntentKind.RUN_TESTS,
            IntentKind.RUN_LINT,
            IntentKind.RUN_BUILD,
            IntentKind.CREATE_TICKET,
            IntentKind.REVIEW_PR,
            IntentKind.GENERATE_RELEASE_NOTES,
            IntentKind.DEPLOY,
            IntentKind.PROD_READINESS_AUDIT,
        }:
            return 0.85
        return 0.6


# ---------------------------------------------------------------------------
# Module-level helpers (backwards compatibility)
# ---------------------------------------------------------------------------

_default_classifier = IntentClassifier()


def classify_intent(
    message: Any,
    *,
    repo: Optional[RepoTarget] = None,
    source: IntentSource = IntentSource.CHAT,
    metadata: Optional[Dict[str, Any]] = None,
) -> NaviIntent:
    """
    Convenience wrapper around `IntentClassifier.classify`.

    Many existing call sites may already be using a function named
    `classify_intent`. Keeping this here avoids churn in the rest of the
    codebase.
    """
    return _default_classifier.classify(
        message,
        repo=repo,
        source=source,
        metadata=metadata,
    )


# Alias used in some older branches / experiments.
detect_intent = classify_intent
