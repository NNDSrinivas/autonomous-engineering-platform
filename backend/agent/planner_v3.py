"""
NAVI Planner v3
===============

Production-grade-ish planner for NAVI autonomous agent.

Key design principles:
- Do NOT refer to IntentKind members that may not exist
- Use message-based shortcuts for Jira / Slack flows
- Fall back to generic per-family planning so we never break
- Be robust against enum changes
"""

import logging
from typing import Any, Dict, Optional

try:
    from backend.orchestrator import PlanResult, PlannedStep
except ImportError:  # pragma: no cover
    # Fallback minimal definitions if backend.orchestrator is unavailable.
    from dataclasses import dataclass

    @dataclass
    class PlannedStep:
        id: Any
        description: str
        tool: str
        arguments: Dict[str, Any]

    @dataclass
    class PlanResult:
        steps: Any
        summary: str


from .intent_schema import NaviIntent, IntentFamily, IntentKind, Provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Planner shortcuts for common patterns
# ---------------------------------------------------------------------------


def maybe_route_jira_my_issues(user_message: str) -> Optional[PlannedStep]:
    """
    Simple rule-based shortcut: if the user is clearly asking
    for 'Jira tasks/issues assigned to me', skip multi-step planning
    and go straight to a Jira tool call.

    This is intentionally simple and ONLY returns a single direct tool step,
    so the agent responds immediately instead of showing a workspace plan card.
    """
    msg = user_message.lower()

    jira_keywords = ("jira", "ticket", "tickets", "issue", "issues", "story", "stories")
    me_keywords = (
        "assigned to me",
        "my tickets",
        "my issues",
        "my tasks",
        "assigned for me",
        "my jira",
        "assigned to myself",
    )

    if any(k in msg for k in jira_keywords) and any(k in msg for k in me_keywords):
        return PlannedStep(
            id="jira_my_issues",
            description="List Jira issues assigned to the current user",
            # NOTE: this must match the tool name registered in ToolExecutor
            tool="jira.list_assigned_issues_for_user",
            arguments={"max_results": 20},
        )

    return None


def maybe_route_slack_channel_summary(user_message: str) -> Optional[PlannedStep]:
    """
    Shortcut for common Slack channel queries like:
    - "summarise the standup slack channel"
    - "what happened in #standup today?"
    - "show recent messages from the release channel"

    This avoids a generic multi-step workspace plan and goes
    directly to slack_fetch_recent_channel_messages.
    """
    msg = user_message.lower()

    # Basic detection: mentions slack OR a '#' channel AND some "summarise / show" verbs
    slack_keywords = ("slack", "channel", "#")
    action_keywords = (
        "summarise",
        "summarize",
        "recap",
        "show",
        "what happened",
        "recent messages",
    )

    if not any(k in msg for k in slack_keywords):
        return None
    if not any(k in msg for k in action_keywords):
        return None

    # Try to guess a channel name from simple patterns like "#standup" or "standup channel"
    channel_name = "standup"  # safe default

    # crude parse for '#xyz'
    hash_idx = msg.find("#")
    if hash_idx != -1:
        # take token after '#'
        tail = msg[hash_idx + 1 :]
        token = ""
        for ch in tail:
            if ch.isalnum() or ch in ("-", "_"):
                token += ch
            else:
                break
        if token:
            channel_name = token
    else:
        # simple heuristics for words before/after "channel"
        for candidate in ("standup", "deploy", "release", "general"):
            if candidate in msg:
                channel_name = candidate
                break

    return PlannedStep(
        id="slack_channel_summary",
        description=f"Fetch recent messages from Slack channel '{channel_name}' and summarise them",
        tool="slack.fetch_recent_channel_messages",
        arguments={
            "channel_name": channel_name,
            "limit": 50,
            "last_n_days": 1,
        },
    )


class PlannerV3:
    """
    Production-grade planner for NAVI autonomous engineering platform.
    Uses safe message-based shortcuts and generic family-based planning.
    """

    def __init__(self, llm_router: Optional[Any] = None):
        self.llm_router = llm_router
        if not self.llm_router:
            try:
                from ..ai.llm_router import LLMRouter

                self.llm_router = LLMRouter()
            except ImportError:
                logger.warning("LLM router not available for planner")

    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """
        Generate execution plan for the given intent.
        Uses provider-aware routing and safe fallbacks.
        """
        try:
            user_message = context.get("message", "") or ""
            ctx_packet = context.get("context_packet") or {}
            packet_key = (
                ctx_packet.get("task_key") if isinstance(ctx_packet, dict) else None
            )

            # 0. If caller already supplied a context packet for the target item,
            # surface it directly to avoid re-querying and to keep responses cited.
            if ctx_packet and intent.kind in (
                IntentKind.SHOW_ITEM_DETAILS,
                IntentKind.JIRA_LIST_MY_ISSUES,
                IntentKind.LIST_MY_ITEMS,
            ):
                # Only use packet when it matches the requested object or no specific object was requested
                if not intent.object_id or intent.object_id == packet_key:
                    summary = f"Using live context packet for {packet_key or 'item'}"
                    return PlanResult(
                        steps=[
                            PlannedStep(
                                id="context_packet",
                                description="Return the live, source-linked context packet for this item",
                                tool="context.present_packet",
                                arguments={},  # executor will pull from context
                            )
                        ],
                        summary=summary,
                    )

            # 1. Provider-based routing (primary strategy)
            if intent.provider == Provider.JIRA and intent.kind in (
                IntentKind.LIST_MY_ITEMS,
                IntentKind.JIRA_LIST_MY_ISSUES,
            ):
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="jira_my_issues",
                            description="List Jira issues assigned to the current user",
                            tool="jira.list_assigned_issues_for_user",
                            arguments={"max_results": 20, "filters": intent.filters},
                        )
                    ],
                    summary="Listing your assigned Jira issues",
                )

            if intent.provider in (Provider.SLACK, Provider.TEAMS) and intent.kind in (
                IntentKind.SUMMARIZE_CHANNEL,
                IntentKind.SLACK_SUMMARIZE_CHANNEL,
            ):
                channel_name = intent.filters.get(
                    "channel_name"
                ) or self._extract_slack_channel(user_message)
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="chat_channel_summary",
                            description=f"Fetch and summarize recent messages from {intent.provider.value} channel '{channel_name}'",
                            tool="chat.fetch_and_summarize_channel",
                            arguments={
                                "provider": intent.provider.value,
                                "channel": channel_name,
                                "limit": 50,
                                "last_n_days": 1,
                            },
                        )
                    ],
                    summary=f"Summarizing {intent.provider.value} channel '{channel_name}'",
                )

            if (
                intent.provider == Provider.GITHUB
                and intent.kind == IntentKind.LIST_MY_ITEMS
            ):
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="github_my_items",
                            description="List GitHub issues/PRs assigned to the current user",
                            tool="github.list_my_items",
                            arguments={
                                "item_type": intent.object_type or "issue",
                                "state": intent.filters.get("status", "open"),
                                "limit": intent.filters.get("limit", 20),
                            },
                        )
                    ],
                    summary="Listing your assigned GitHub items",
                )

            # Linear routing
            if intent.provider == Provider.LINEAR and intent.kind in (
                IntentKind.LIST_MY_ITEMS,
            ):
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="linear_my_issues",
                            description="List Linear issues assigned to the current user",
                            tool="linear.list_my_issues",
                            arguments={
                                "status": intent.filters.get("status"),
                                "max_results": intent.filters.get("limit", 20),
                            },
                        )
                    ],
                    summary="Listing your assigned Linear issues",
                )

            # GitLab routing
            if intent.provider == Provider.GITLAB and intent.kind in (
                IntentKind.LIST_MY_ITEMS,
            ):
                object_type = intent.object_type or "merge_request"
                if object_type in ("mr", "merge_request"):
                    return PlanResult(
                        steps=[
                            PlannedStep(
                                id="gitlab_my_mrs",
                                description="List GitLab merge requests assigned to the current user",
                                tool="gitlab.list_my_merge_requests",
                                arguments={
                                    "status": intent.filters.get("status"),
                                    "max_results": intent.filters.get("limit", 20),
                                },
                            )
                        ],
                        summary="Listing your assigned GitLab merge requests",
                    )
                else:
                    return PlanResult(
                        steps=[
                            PlannedStep(
                                id="gitlab_my_issues",
                                description="List GitLab issues assigned to the current user",
                                tool="gitlab.list_my_issues",
                                arguments={
                                    "status": intent.filters.get("status"),
                                    "max_results": intent.filters.get("limit", 20),
                                },
                            )
                        ],
                        summary="Listing your assigned GitLab issues",
                    )

            # Asana routing
            if intent.provider == Provider.ASANA and intent.kind in (
                IntentKind.LIST_MY_ITEMS,
            ):
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="asana_my_tasks",
                            description="List Asana tasks assigned to the current user",
                            tool="asana.list_my_tasks",
                            arguments={
                                "status": intent.filters.get("status"),
                                "max_results": intent.filters.get("limit", 20),
                            },
                        )
                    ],
                    summary="Listing your assigned Asana tasks",
                )

            # Notion routing
            if intent.provider == Provider.NOTION and intent.kind in (
                IntentKind.LIST_MY_ITEMS,
            ):
                query = intent.filters.get("query", "")
                if query:
                    return PlanResult(
                        steps=[
                            PlannedStep(
                                id="notion_search",
                                description=f"Search Notion pages for '{query}'",
                                tool="notion.search_pages",
                                arguments={
                                    "query": query,
                                    "max_results": intent.filters.get("limit", 20),
                                },
                            )
                        ],
                        summary=f"Searching Notion pages for '{query}'",
                    )
                else:
                    return PlanResult(
                        steps=[
                            PlannedStep(
                                id="notion_recent",
                                description="List recent Notion pages",
                                tool="notion.list_recent_pages",
                                arguments={
                                    "max_results": intent.filters.get("limit", 20),
                                },
                            )
                        ],
                        summary="Listing your recent Notion pages",
                    )

            # Generic cross-provider item details
            if intent.kind == IntentKind.SHOW_ITEM_DETAILS and intent.object_id:
                return PlanResult(
                    steps=[
                        PlannedStep(
                            id="show_item_details",
                            description=f"Show details for {intent.object_type or 'item'} {intent.object_id}",
                            tool=f"{intent.provider.value}.get_item_details",
                            arguments={
                                "object_id": intent.object_id,
                                "object_type": intent.object_type,
                            },
                        )
                    ],
                    summary=f"Showing details for {intent.object_id}",
                )

            # 2. Backward compatibility message-based shortcuts
            jira_shortcut = maybe_route_jira_my_issues(user_message)
            if jira_shortcut is not None:
                return PlanResult(
                    steps=[jira_shortcut],
                    summary="Listing your assigned Jira issues",
                )

            slack_shortcut = maybe_route_slack_channel_summary(user_message)
            if slack_shortcut is not None:
                return PlanResult(
                    steps=[slack_shortcut],
                    summary=f"Summarizing Slack channel '{slack_shortcut.arguments.get('channel_name')}'",
                )

            # 3. Generic family-based planning (safe fallback)
            if intent.family == IntentFamily.ENGINEERING:
                return await self._plan_engineering_family(intent, context)
            elif intent.family == IntentFamily.PROJECT_MANAGEMENT:
                return await self._plan_project_management_family(intent, context)
            elif intent.family == IntentFamily.AUTONOMOUS_ORCHESTRATION:
                return await self._plan_autonomous_family(intent, context)
            else:
                return await self._plan_default_family(intent, context)

        except Exception as e:
            logger.exception(
                "Planning failed for intent %s/%s", intent.family, intent.kind
            )
            return PlanResult(
                steps=[
                    PlannedStep(
                        id="error_step",
                        description=f"Planning failed: {e}",
                        tool="error",
                        arguments={"error": str(e)},
                    )
                ],
                summary=f"Planning failed: {e}",
            )

    # ---------------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------------

    def _extract_slack_channel(self, message: str) -> str:
        """Extract Slack channel name from user message."""
        msg = (message or "").lower()

        # Look for #channel patterns
        hash_idx = msg.find("#")
        if hash_idx != -1:
            tail = msg[hash_idx + 1 :]
            token = ""
            for ch in tail:
                if ch.isalnum() or ch in ("-", "_"):
                    token += ch
                else:
                    break
            if token:
                return token

        # Look for common channel names
        for candidate in (
            "standup",
            "deploy",
            "release",
            "general",
            "platform",
            "engineering",
        ):
            if candidate in msg:
                return candidate

        return "standup"

    # ---------------------------------------------------------------------------
    # Generic family-based planning methods (safe against enum changes)
    # ---------------------------------------------------------------------------

    async def _plan_engineering_family(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> PlanResult:
        """
        Plan ENGINEERING family intents using safe, executable tools.

        This ensures the agent can gather context and let the LLM explain
        results, rather than falling back to safety mode.
        """
        kind_value = (
            intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        )

        # Use safe tools (repo.inspect, code.read_files, code.search) for engineering tasks
        # These tools execute immediately and let the LLM explain the results
        steps = [
            PlannedStep(
                id="repo-overview-1",
                description="Inspect the repository structure and main folders.",
                tool="repo.inspect",
                arguments={"max_depth": 3, "max_files": 200},
            ),
            PlannedStep(
                id="repo-overview-2",
                description="Read key files like README and main entrypoints.",
                tool="code.read_files",
                arguments={
                    "paths": [
                        "README.md",
                        "readme.md",
                        "package.json",
                        "pyproject.toml",
                        "pom.xml",
                        "setup.py",
                        "main.py",
                        "src/main.py",
                        "src/index.tsx",
                        "src/index.ts",
                    ]
                },
            ),
        ]

        return PlanResult(
            steps=steps,
            summary=f"Analyzing codebase for {kind_value}",
        )

    async def _plan_project_management_family(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> PlanResult:
        """
        Plan PROJECT_MANAGEMENT family intents using safe tools.

        Gathers context about the project so LLM can provide relevant guidance.
        """
        kind_value = (
            intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        )

        # Use safe tools to gather project context
        steps = [
            PlannedStep(
                id="repo-overview-1",
                description="Inspect the repository structure.",
                tool="repo.inspect",
                arguments={"max_depth": 2, "max_files": 100},
            ),
            PlannedStep(
                id="repo-overview-2",
                description="Read project configuration files.",
                tool="code.read_files",
                arguments={
                    "paths": [
                        "README.md",
                        "package.json",
                        "pyproject.toml",
                        ".github/workflows",
                    ]
                },
            ),
        ]

        return PlanResult(
            steps=steps,
            summary=f"Gathering project context for {kind_value}",
        )

    async def _plan_autonomous_family(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> PlanResult:
        """
        Plan AUTONOMOUS_ORCHESTRATION family intents using safe tools.

        For autonomous tasks, we need to first gather context about the workspace.
        """
        kind_value = (
            intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        )

        # Use safe tools to gather workspace context
        steps = [
            PlannedStep(
                id="repo-overview-1",
                description="Inspect the repository structure.",
                tool="repo.inspect",
                arguments={"max_depth": 3, "max_files": 200},
            ),
            PlannedStep(
                id="repo-overview-2",
                description="Read project configuration and entry points.",
                tool="code.read_files",
                arguments={
                    "paths": [
                        "README.md",
                        "package.json",
                        "pyproject.toml",
                        "main.py",
                        "src/index.ts",
                    ]
                },
            ),
        ]

        return PlanResult(
            steps=steps,
            summary=f"Gathering context for {kind_value}",
        )

    async def _plan_default_family(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> PlanResult:
        """
        Fallback planning using safe tools for any intent family.

        This ensures we always have executable steps that gather context.
        """
        family_value = (
            intent.family.value
            if hasattr(intent.family, "value")
            else str(intent.family)
        )
        kind_value = (
            intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        )

        # Use safe tools to gather context
        steps = [
            PlannedStep(
                id="repo-overview-1",
                description="Inspect the repository structure.",
                tool="repo.inspect",
                arguments={"max_depth": 2, "max_files": 100},
            ),
            PlannedStep(
                id="repo-overview-2",
                description="Read key project files.",
                tool="code.read_files",
                arguments={
                    "paths": ["README.md", "package.json", "pyproject.toml"]
                },
            ),
        ]

        return PlanResult(
            steps=steps,
            summary=f"Gathering context for {family_value} {kind_value}",
        )

    async def plan_fix(
        self,
        fix_context: Dict[str, Any],
    ) -> PlanResult:
        """
        Generate a plan to fix test failures.

        This is used in iterative mode when tests fail after code changes.
        The plan focuses on analyzing and fixing the specific failures.

        Args:
            fix_context: Context from iteration_controller.create_fix_context()
                Contains:
                - original_request: The user's original request
                - iteration: Current iteration number
                - test_results: Test pass/fail counts
                - failure_summary: Summary of failed tests
                - fix_hints: Suggestions from debug analysis
                - instruction: Guidance for fixing

        Returns:
            PlanResult with steps to fix the failures
        """
        failure_summary = fix_context.get("failure_summary", "Unknown failures")
        iteration = fix_context.get("iteration", 1)
        fix_hints = fix_context.get("fix_hints", [])

        logger.info(
            "[PLANNER] Generating fix plan for iteration %d: %s",
            iteration,
            failure_summary[:100],
        )

        # Build steps to analyze and fix the failures
        steps = []

        # Step 1: Read the failing test files to understand what's expected
        # Extract file paths from failure summary
        test_files = self._extract_test_files_from_failures(failure_summary)
        if test_files:
            steps.append(
                PlannedStep(
                    id="fix-read-tests",
                    description="Read failing test files to understand expected behavior",
                    tool="code.read_files",
                    arguments={"paths": test_files[:5]},  # Limit to 5 files
                )
            )

        # Step 2: Search for related code that might need fixing
        steps.append(
            PlannedStep(
                id="fix-search-related",
                description="Search for code related to the failing tests",
                tool="code.search",
                arguments={
                    "query": self._extract_search_terms(failure_summary),
                    "max_results": 10,
                },
            )
        )

        # Step 3: Apply fixes based on the analysis
        # The actual fix would be generated by the LLM based on context
        steps.append(
            PlannedStep(
                id="fix-apply-changes",
                description=f"Apply fixes for test failures (iteration {iteration})",
                tool="code.apply_patch",
                arguments={
                    "context": {
                        "failures": failure_summary,
                        "hints": fix_hints,
                        "iteration": iteration,
                    },
                    "auto_generate": True,  # Signal that LLM should generate the patch
                },
            )
        )

        # Build summary with fix hints
        hint_text = ""
        if fix_hints:
            hint_text = f" Hints: {', '.join(fix_hints[:2])}"

        return PlanResult(
            steps=steps,
            summary=f"Fixing test failures (iteration {iteration}).{hint_text}",
        )

    def _extract_test_files_from_failures(self, failure_summary: str) -> list:
        """Extract test file paths from failure summary."""
        import re

        # Match common test file patterns
        patterns = [
            r'([^\s:]+(?:_test|test_|\.test|\.spec)\.[a-z]+)',  # test files
            r'\(([^:]+\.(?:py|js|ts|go|rs|java)):',  # file:line patterns
        ]

        files = set()
        for pattern in patterns:
            for match in re.finditer(pattern, failure_summary, re.IGNORECASE):
                files.add(match.group(1))

        return list(files)

    def _extract_search_terms(self, failure_summary: str) -> str:
        """Extract search terms from failure summary."""
        import re

        # Look for function/class names in common error patterns
        patterns = [
            r'(?:test_|Test)(\w+)',  # Test names
            r'(\w+Error|Exception)',  # Error types
            r"'(\w+)'",  # Quoted identifiers
        ]

        terms = []
        for pattern in patterns:
            for match in re.finditer(pattern, failure_summary):
                terms.append(match.group(1))

        # Return first few unique terms
        unique_terms = list(dict.fromkeys(terms))[:3]
        return " ".join(unique_terms) if unique_terms else "test failure"


class SimplePlanner:
    """Minimal planner for FastAPI integration using safe tools."""

    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Create a plan with safe, executable tools."""
        family_value = (
            intent.family.value
            if hasattr(intent.family, "value")
            else str(intent.family)
        )
        kind_value = (
            intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        )

        # Use safe tools that execute immediately
        steps = [
            PlannedStep(
                id="repo-overview-1",
                description="Inspect the repository structure.",
                tool="repo.inspect",
                arguments={"max_depth": 2, "max_files": 100},
            ),
            PlannedStep(
                id="repo-overview-2",
                description="Read key project files.",
                tool="code.read_files",
                arguments={
                    "paths": ["README.md", "package.json", "pyproject.toml"]
                },
            ),
        ]

        return PlanResult(
            steps=steps,
            summary=f"Gathering context for {family_value} {kind_value}",
        )
