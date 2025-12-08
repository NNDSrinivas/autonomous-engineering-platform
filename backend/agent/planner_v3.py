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

from .orchestrator import PlanResult, PlannedStep
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
    action_keywords = ("summarise", "summarize", "recap", "show", "what happened", "recent messages")

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
        }
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
            packet_key = ctx_packet.get("task_key") if isinstance(ctx_packet, dict) else None

            # 0. If caller already supplied a context packet for the target item,
            # surface it directly to avoid re-querying and to keep responses cited.
            if ctx_packet and intent.kind in (IntentKind.SHOW_ITEM_DETAILS, IntentKind.JIRA_LIST_MY_ISSUES, IntentKind.LIST_MY_ITEMS):
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
                channel_name = intent.filters.get("channel_name") or self._extract_slack_channel(user_message)
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

            if intent.provider == Provider.GITHUB and intent.kind == IntentKind.LIST_MY_ITEMS:
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
            logger.exception("Planning failed for intent %s/%s", intent.family, intent.kind)
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
        for candidate in ("standup", "deploy", "release", "general", "platform", "engineering"):
            if candidate in msg:
                return candidate

        return "standup"

    # ---------------------------------------------------------------------------
    # Generic family-based planning methods (safe against enum changes)
    # ---------------------------------------------------------------------------

    async def _plan_engineering_family(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan ENGINEERING family intents using generic approach."""
        kind_value = intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)
        steps = [
            PlannedStep(
                id="engineering_action",
                description=f"Execute {kind_value} engineering action",
                tool="engineering.generic",
                arguments={
                    "intent_family": intent.family.value,
                    "intent_kind": kind_value,
                    "context": context,
                },
            )
        ]

        return PlanResult(
            steps=steps,
            summary=f"Engineering {kind_value} plan",
        )

    async def _plan_project_management_family(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan PROJECT_MANAGEMENT family intents using generic approach."""
        kind_value = intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)

        steps = [
            PlannedStep(
                id="project_management_action",
                description=f"Execute {kind_value} project management action",
                tool="project.generic",
                arguments={
                    "intent_family": intent.family.value,
                    "intent_kind": kind_value,
                    "context": context,
                },
            )
        ]

        return PlanResult(
            steps=steps,
            summary=f"Project Management {kind_value} plan",
        )

    async def _plan_autonomous_family(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Plan AUTONOMOUS_ORCHESTRATION family intents using generic approach."""
        kind_value = intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)

        steps = [
            PlannedStep(
                id="autonomous_action",
                description=f"Execute {kind_value} autonomous action",
                tool="autonomous.generic",
                arguments={
                    "intent_family": intent.family.value,
                    "intent_kind": kind_value,
                    "context": context,
                },
            )
        ]

        return PlanResult(
            steps=steps,
            summary=f"Autonomous {kind_value} plan",
        )

    async def _plan_default_family(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Fallback planning for any intent family."""
        family_value = intent.family.value if hasattr(intent.family, "value") else str(intent.family)
        kind_value = intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)

        steps = [
            PlannedStep(
                id="generic_action",
                description=f"Execute {family_value} {kind_value} action",
                tool="generic",
                arguments={
                    "intent_family": family_value,
                    "intent_kind": kind_value,
                    "context": context,
                },
            )
        ]

        return PlanResult(
            steps=steps,
            summary=f"Generic {family_value} {kind_value} plan",
        )


class SimplePlanner:
    """Minimal planner for FastAPI integration."""

    async def plan(self, intent: NaviIntent, context: Dict[str, Any]) -> PlanResult:
        """Create a simple single-step plan."""
        family_value = intent.family.value if hasattr(intent.family, "value") else str(intent.family)
        kind_value = intent.kind.value if hasattr(intent.kind, "value") else str(intent.kind)

        step = PlannedStep(
            id="simple_step",
            description=f"Execute {family_value} {kind_value}",
            tool="simple",
            arguments={
                "intent_family": family_value,
                "intent_kind": kind_value,
                "context": context,
            },
        )

        return PlanResult(
            steps=[step],
            summary=f"Simple {family_value} {kind_value} plan",
        )
