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


def _priority_from_text(text: str) -> IntentPriority:
    if _contains_any(text, ("p0", "sev0", "sev 0", "production down", "outage")):
        return IntentPriority.CRITICAL
    if _contains_any(text, ("urgent", "asap", "p1", "sev1", "blocker")):
        return IntentPriority.HIGH
    if _contains_any(text, ("low priority", "whenever", "nice to have")):
        return IntentPriority.LOW
    return IntentPriority.NORMAL


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

        intent = NaviIntent(
            family=family,
            kind=kind,
            source=source,
            priority=priority,
            confidence=confidence,
            raw_text=raw_text,
            slots={
                "language": language_hint,
                **{k: v for k, v in metadata.items() if k not in {"files", "language"}},
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
                "jira",
                "ticket",
                "story",
                "issue",
                "backlog",
                "sprint",
                "epic",
                "release notes",
                "changelog",
                "pull request",
                "pr ",
                "merge request",
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
            # Check for greetings first
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
                    "compilation errors"
                ),
            ):
                return IntentKind.FIX_DIAGNOSTICS

            if _contains_any(
                text,
                (
                    "failing test",
                    "tests are failing",
                    "fix the bug",
                    "stack trace",
                    "exception",
                    "runtime error",
                    "compile error",
                    "fix this bug",
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
                    "add api",
                    "create endpoint",
                    "support this use case",
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
                    "execute tests",
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
                    "explain this code",
                    "what does this code do",
                    "explain how this works",
                    "help me understand this function",
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
