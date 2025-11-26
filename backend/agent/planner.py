"""
NAVI Planner v2
===============

This module converts a `NaviIntent` into a concrete execution plan
(a sequence of `PlannedStep` objects) that the ToolExecutor can run.

Design goals:
- No external dependencies.
- Simple, explainable logic, but structured enough to grow later.
- Uses the shared intent schema (NaviIntent, CodeEditSpec, etc.).
- Uses the planning types from `backend.agent.orchestrator`.

The ToolExecutor is expected to understand the following tool IDs
(you can map them however you like in your implementation):

    - "repo.inspect"          → high-level repo scan / summary
    - "code.read_files"       → read one or more files
    - "code.search"           → search within codebase
    - "code.propose_patch"    → produce concrete diffs for a goal
    - "code.apply_patch"      → apply patch operations
    - "tests.run"             → run tests / lint / build commands
    - "pm.create_ticket"      → create a ticket in Jira / GitHub, etc.
    - "pm.update_ticket"      → update ticket status / fields
    - "pm.summarize_tickets"  → summarise a set of tickets
    - "pm.summarize_pr"       → summarise a PR
    - "pm.review_pr"          → code review actions
    - "pm.generate_release_notes" → generate release notes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .intent_schema import (
    IntentFamily,
    IntentKind,
    NaviIntent,
)
from .orchestrator import PlannedStep, PlanResult


@dataclass
class PlannerConfig:
    """
    Configuration knobs for the planner.

    All fields are optional and default to reasonable values. This is
    mainly here to give us a place to add flags later (e.g. to enable
    experimental behaviours).
    """

    # If True, always include an initial repo.inspect step when the
    # intent requires repo context but doesn't specify files explicitly.
    always_inspect_repo_first: bool = True

    # If True, automatically append a tests.run step for code-changing
    # intents (FIX_BUG, IMPLEMENT_FEATURE, etc.) when test_run spec
    # exists in the NaviIntent.
    auto_append_tests_for_code_changes: bool = True


class SimplePlanner:
    """
    A minimal but structured planner for NAVI.

    It converts a `NaviIntent` into a `PlanResult`:

        intent → [PlannedStep, PlannedStep, ...]

    This is intentionally straightforward so we can later:
      - upgrade step descriptions
      - plug in an LLM to refine plan text
      - add parallelism / conditional logic

    For now, plans are always linear and executed in order.
    """

    def __init__(self, config: Optional[PlannerConfig] = None) -> None:
        self.config = config or PlannerConfig()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """
        Build an execution plan for the given intent.

        Parameters
        ----------
        intent:
            Classified NaviIntent from the IntentClassifier.
        context:
            Planner context (state, memory, repo info, etc.) as built by
            the orchestrator.

        Returns
        -------
        PlanResult
            A sequence of `PlannedStep` objects and an optional summary.
        """
        if intent.family == IntentFamily.ENGINEERING:
            steps, summary = self._plan_engineering(intent, context)
        elif intent.family == IntentFamily.PROJECT_MANAGEMENT:
            steps, summary = self._plan_project_management(intent, context)
        else:
            steps, summary = self._plan_autonomous(intent, context)

        return PlanResult(steps=steps, summary=summary)

    # ------------------------------------------------------------------ #
    # Engineering plans
    # ------------------------------------------------------------------ #

    def _plan_engineering(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> tuple[List[PlannedStep], str]:
        kind = intent.kind
        steps: List[PlannedStep] = []

        # Optional first step: inspect repo if requested / needed
        if self._should_inspect_repo_first(intent):
            steps.append(
                self._step(
                    "repo.inspect",
                    "Inspect the repository structure and recent changes.",
                    arguments={"intent_summary": intent.summary()},
                )
            )

        if kind == IntentKind.FIX_BUG:
            steps.extend(self._plan_fix_bug(intent, context))
        elif kind == IntentKind.IMPLEMENT_FEATURE:
            steps.extend(self._plan_implement_feature(intent, context))
        elif kind == IntentKind.REFACTOR_CODE:
            steps.extend(self._plan_refactor_code(intent, context))
        elif kind == IntentKind.UPDATE_DEPENDENCIES:
            steps.extend(self._plan_update_dependencies(intent, context))
        elif kind in {
            IntentKind.RUN_TESTS,
            IntentKind.GENERATE_TESTS,
            IntentKind.RUN_LINT,
            IntentKind.RUN_BUILD,
        }:
            steps.extend(self._plan_test_like(intent, context))
        elif kind == IntentKind.SEARCH_CODE:
            steps.extend(self._plan_search_code(intent, context))
        elif kind in {IntentKind.SUMMARIZE_FILE, IntentKind.INSPECT_REPO}:
            steps.extend(self._plan_summarise_file(intent, context))
        elif kind == IntentKind.EDIT_INFRA:
            steps.extend(self._plan_edit_infra(intent, context))
        else:
            # Default engineering plan: inspect repo + summarise context
            steps.append(
                self._step(
                    "repo.inspect",
                    "Inspect the repository and summarise relevant components.",
                    arguments={"intent_summary": intent.summary()},
                )
            )

        # Optionally append tests for code-changing intents
        if (
            self.config.auto_append_tests_for_code_changes
            and intent.test_run is not None
            and kind
            in {
                IntentKind.FIX_BUG,
                IntentKind.IMPLEMENT_FEATURE,
                IntentKind.REFACTOR_CODE,
                IntentKind.UPDATE_DEPENDENCIES,
                IntentKind.MODIFY_CODE,
                IntentKind.CREATE_FILE,
            }
        ):
            steps.append(
                self._step(
                    "tests.run",
                    "Run tests to verify the changes.",
                    arguments={"test_run": intent.test_run.model_dump()},
                )
            )

        summary = f"Plan for engineering intent: {intent.summary()}"
        return steps, summary

    def _plan_fix_bug(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        files = (intent.code_edit.primary_files if intent.code_edit else []) or []

        steps.append(
            self._step(
                "code.read_files",
                "Read the relevant source files to understand the failing area.",
                arguments={
                    "files": [f.model_dump() for f in files],
                    "raw_text": intent.raw_text,
                },
            )
        )

        steps.append(
            self._step(
                "code.search",
                "Search for error messages, stack traces, or related symbols.",
                arguments={
                    "query": intent.raw_text,
                    "scope": "repo",
                },
            )
        )

        steps.append(
            self._step(
                "code.propose_patch",
                "Propose a concrete code patch that fixes the bug.",
                arguments={
                    "intent": intent.model_dump(),
                    "strategy": "bugfix",
                },
            )
        )

        steps.append(
            self._step(
                "code.apply_patch",
                "Apply the patch to the repository (after validation).",
                arguments={"intent": intent.model_dump()},
            )
        )

        return steps

    def _plan_implement_feature(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        files = (intent.code_edit.primary_files if intent.code_edit else []) or []

        steps.append(
            self._step(
                "code.read_files",
                "Read the main files involved in the feature.",
                arguments={
                    "files": [f.model_dump() for f in files],
                    "raw_text": intent.raw_text,
                },
            )
        )

        steps.append(
            self._step(
                "code.propose_patch",
                "Design and propose a patch implementing the requested feature.",
                arguments={
                    "intent": intent.model_dump(),
                    "strategy": "feature",
                },
            )
        )

        steps.append(
            self._step(
                "code.apply_patch",
                "Apply the feature implementation patch.",
                arguments={"intent": intent.model_dump()},
            )
        )

        return steps

    def _plan_refactor_code(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        files = (intent.code_edit.primary_files if intent.code_edit else []) or []

        steps.append(
            self._step(
                "code.read_files",
                "Read the code that needs refactoring.",
                arguments={"files": [f.model_dump() for f in files]},
            )
        )

        steps.append(
            self._step(
                "code.propose_patch",
                "Propose a patch that refactors the code for clarity and maintainability.",
                arguments={
                    "intent": intent.model_dump(),
                    "strategy": "refactor",
                },
            )
        )

        steps.append(
            self._step(
                "code.apply_patch",
                "Apply the refactoring patch.",
                arguments={"intent": intent.model_dump()},
            )
        )

        return steps

    def _plan_update_dependencies(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []

        steps.append(
            self._step(
                "code.search",
                "Locate dependency manifests (e.g. requirements.txt, package.json).",
                arguments={
                    "query": "requirements.txt OR pyproject.toml OR package.json",
                    "scope": "repo",
                },
            )
        )

        steps.append(
            self._step(
                "code.propose_patch",
                "Propose safe dependency version updates.",
                arguments={
                    "intent": intent.model_dump(),
                    "strategy": "deps_update",
                },
            )
        )

        steps.append(
            self._step(
                "code.apply_patch",
                "Apply the dependency update patch.",
                arguments={"intent": intent.model_dump()},
            )
        )

        return steps

    def _plan_test_like(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []

        if intent.test_run is None:
            # No test_run spec → do a generic command run
            steps.append(
                self._step(
                    "tests.run",
                    "Run the requested test/build/lint command.",
                    arguments={
                        "raw_text": intent.raw_text,
                        "fallback": True,
                    },
                )
            )
            return steps

        steps.append(
            self._step(
                "tests.run",
                "Run the configured test/build/lint command.",
                arguments={"test_run": intent.test_run.model_dump()},
            )
        )
        return steps

    def _plan_search_code(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        return [
            self._step(
                "code.search",
                "Search the codebase based on the user query.",
                arguments={
                    "query": intent.raw_text,
                    "scope": "repo",
                },
            )
        ]

    def _plan_summarise_file(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        files = (intent.code_edit.primary_files if intent.code_edit else []) or []

        return [
            self._step(
                "code.read_files",
                "Read the requested file(s) to summarise or explain.",
                arguments={"files": [f.model_dump() for f in files]},
            )
        ]

    def _plan_edit_infra(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> List[PlannedStep]:
        steps: List[PlannedStep] = []

        steps.append(
            self._step(
                "code.search",
                "Locate infrastructure files (Dockerfile, docker-compose, helm charts, etc.).",
                arguments={
                    "query": "Dockerfile OR docker-compose.yml OR helm OR k8s",
                    "scope": "repo",
                },
            )
        )

        steps.append(
            self._step(
                "code.propose_patch",
                "Propose infrastructure configuration changes.",
                arguments={
                    "intent": intent.model_dump(),
                    "strategy": "infra",
                },
            )
        )

        steps.append(
            self._step(
                "code.apply_patch",
                "Apply the infrastructure patch.",
                arguments={"intent": intent.model_dump()},
            )
        )

        return steps

    # ------------------------------------------------------------------ #
    # Project management plans
    # ------------------------------------------------------------------ #

    def _plan_project_management(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> tuple[List[PlannedStep], str]:
        kind = intent.kind
        steps: List[PlannedStep] = []

        if kind == IntentKind.CREATE_TICKET:
            steps.append(
                self._step(
                    "pm.create_ticket",
                    "Create a new ticket based on the request.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: create a new project management ticket."
        elif kind == IntentKind.UPDATE_TICKET:
            steps.append(
                self._step(
                    "pm.update_ticket",
                    "Update the existing ticket(s) based on the request.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: update one or more tickets."
        elif kind == IntentKind.SUMMARIZE_TICKETS:
            steps.append(
                self._step(
                    "pm.summarize_tickets",
                    "Summarise the relevant tickets (e.g. sprint backlog).",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: summarise tickets."
        elif kind == IntentKind.SUMMARIZE_PR:
            steps.append(
                self._step(
                    "pm.summarize_pr",
                    "Summarise the pull request and its impact.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: summarise the pull request."
        elif kind == IntentKind.REVIEW_PR:
            steps.append(
                self._step(
                    "pm.review_pr",
                    "Review the pull request and provide feedback.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: perform a pull request review."
        elif kind == IntentKind.GENERATE_RELEASE_NOTES:
            steps.append(
                self._step(
                    "pm.generate_release_notes",
                    "Generate release notes based on recent changes.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: generate release notes."
        else:
            steps.append(
                self._step(
                    "pm.summarize_tickets",
                    "Summarise project management items related to the request.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: generic project-management summary."

        return steps, summary

    # ------------------------------------------------------------------ #
    # Autonomous / orchestration plans
    # ------------------------------------------------------------------ #

    def _plan_autonomous(
        self,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> tuple[List[PlannedStep], str]:
        kind = intent.kind
        steps: List[PlannedStep] = []

        if kind == IntentKind.CONTINUE_SESSION:
            steps.append(
                self._step(
                    "orchestrator.resume",
                    "Resume the previous autonomous session and continue the plan.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: resume previous autonomous session."
        elif kind == IntentKind.CANCEL_WORKFLOW:
            steps.append(
                self._step(
                    "orchestrator.cancel",
                    "Cancel the running workflow.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: cancel running workflow."
        elif kind == IntentKind.SCHEDULED_TASK:
            steps.append(
                self._step(
                    "orchestrator.schedule",
                    "Schedule the described task as a recurring/background job.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: schedule the requested task."
        elif kind == IntentKind.BACKGROUND_WORKFLOW:
            steps.append(
                self._step(
                    "orchestrator.start_background",
                    "Start a background workflow for the requested bulk/batch work.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: run background workflow."
        else:
            # Default: run an autonomous session using generic orchestration
            steps.append(
                self._step(
                    "orchestrator.autonomous_session",
                    "Start an autonomous session and iteratively plan & execute steps.",
                    arguments={"intent": intent.model_dump()},
                )
            )
            summary = "Plan: run a generic autonomous session."

        return steps, summary

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def _should_inspect_repo_first(self, intent: NaviIntent) -> bool:
        if not self.config.always_inspect_repo_first:
            return False
        # only for engineering intents that need repo context
        if not intent.is_engineering():
            return False
        return intent.requires_repo()

    _step_counter = 0

    def _step(self, tool: str, description: str, arguments: Dict[str, Any]) -> PlannedStep:
        """
        Helper to build a PlannedStep with a unique ID.

        The `tool` string is a logical identifier; the ToolExecutor
        decides how to route it to actual tools / MCP servers.
        """
        self.__class__._step_counter += 1
        step_id = f"step-{self.__class__._step_counter}"
        return PlannedStep(
            id=step_id,
            description=description,
            tool=tool,
            arguments=arguments,
        )


# Backwards-compatible alias if older code imports `Planner`
Planner = SimplePlanner


# Backwards-compatible function for existing code
def generate_plan(intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
    """
    Backwards-compatible function wrapper for existing code.
    """
    planner = SimplePlanner()
    return planner.plan(intent, context)