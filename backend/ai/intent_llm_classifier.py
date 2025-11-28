"""
LLM-Powered Intent Classifier for AEP (Autonomous Engineering Platform)
=======================================================================

This module upgrades NAVI's intent classification accuracy using LLMs.

Pipeline:
    1. Ask high-accuracy model (Claude Opus / GPT-5.1) for structured classification.
    2. Parse the result.
    3. Validate against intent_schema.py enums.
    4. If LLM returns invalid/missing info → fallback to heuristic classifier.

Public API:
    LLMIntentClassifier.classify(message, metadata=...)

This is used by the orchestrator.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, List

from ..agent.intent_schema import (
    NaviIntent,
    IntentFamily,
    IntentKind,
    IntentPriority,
    Provider,
    AutonomyMode,
    RepoTarget,
    WorkflowHints,
    CodeEditSpec,
    ProjectManagementSpec,
    TestRunSpec,
)
from ..agent.intent_classifier import IntentClassifier
from .llm_router import LLMRouter, LLMResponse

logger = logging.getLogger(__name__)


# ======================================================================
# LLM Intent Classifier
# ======================================================================

class LLMIntentClassifier:
    """
    High-accuracy LLM-powered intent classifier for NAVI.

    Fallback logic:
        - If LLM classification fails or returns malformed data:
              → fallback to heuristic IntentClassifier
    """

    def __init__(
        self,
        *,
        router: Optional[LLMRouter] = None,
        heuristic: Optional[IntentClassifier] = None,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        temperature: float = 0.0,
    ):
        self.router = router or LLMRouter()
        self.heuristic = heuristic or IntentClassifier()
        self.model = model
        self.provider = provider
        self.temperature = temperature

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify(
        self,
        message: Any,
        *,
        repo: Optional[RepoTarget] = None,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,  # BYOK
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent:
        """
        Classify user intent using a high-accuracy model. Fallback to heuristic.
        """
        metadata = metadata or {}
        text = _norm_text(message)

        try:
            llm_response = await self._ask_llm(text, metadata, api_key, org_id)
            parsed = self._parse_json(llm_response.text)
            validated = self._validate_and_convert(parsed, raw=text, metadata=metadata, repo=repo)

            logger.info("[LLM-Intent] Successfully classified using LLM")
            return validated

        except Exception as e:
            logger.error(f"[LLM-Intent] LLM classification failed → fallback. Error: {e}")

        # Fallback to heuristic classifier
        return self.heuristic.classify(message, repo=repo, metadata=metadata)

    # ------------------------------------------------------------------
    # Stage 1 — Ask LLM
    # ------------------------------------------------------------------

    async def _ask_llm(
        self,
        text: str,
        metadata: Dict[str, Any],
        api_key: Optional[str],
        org_id: Optional[str],
    ) -> LLMResponse:
        """
        Call the LLM with the structured intent classification prompt.
        
        Uses the system prompt to instruct the LLM to return provider-aware
        JSON classification for cross-app workflows.
        """
        system_prompt = INTENT_SYSTEM_PROMPT

        # Build user prompt with message and any workspace context
        user_prompt = f"User message: {text}"
        if metadata:
            user_prompt += f"\n\nWorkspace context: {json.dumps(metadata, indent=2)}"

        try:
            return await self.router.run(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=self.model,
                provider=self.provider,
                api_key=api_key,
                org_id=org_id,
                temperature=self.temperature,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"[LLM-Intent] LLM call failed: {e}")
            raise

    # ------------------------------------------------------------------
    # Stage 2 — Parse JSON
    # ------------------------------------------------------------------

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Parse the LLM JSON output.
        """
        try:
            return json.loads(text)
        except Exception:
            # Sometimes LLM wraps JSON in code blocks
            cleaned = text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned)

    # ------------------------------------------------------------------
    # Stage 3 — Convert to NaviIntent
    # ------------------------------------------------------------------

    def _validate_and_convert(
        self,
        data: Dict[str, Any],
        *,
        raw: str,
        metadata: Dict[str, Any],
        repo: Optional[RepoTarget],
    ) -> NaviIntent:

        # Validate enums
        family = _safe_enum(IntentFamily, data.get("family"))
        kind = _safe_enum(IntentKind, data.get("kind"))
        priority = _safe_enum(IntentPriority, data.get("priority"))
        autonomy = _safe_enum(AutonomyMode, data.get("autonomy_mode"))
        provider = _safe_enum(Provider, data.get("provider"))

        # Ensure minimum fields
        if not family or not kind:
            raise ValueError("Missing required intent fields")

        # Build payload
        workflow = WorkflowHints(
            autonomy_mode=autonomy or AutonomyMode.ASSISTED,
            max_steps=data.get("workflow", {}).get("max_steps", 8),
            auto_run_tests=data.get("workflow", {}).get("auto_run_tests", False),
            allow_cross_repo_changes=data.get("workflow", {}).get("allow_cross_repo_changes", False),
            allow_long_running=data.get("workflow", {}).get("allow_long_running", False),
        )

        # Optional code_edit spec
        code_edit = None
        if "code_edit" in data:
            ce = data["code_edit"]
            code_edit = CodeEditSpec(
                goal=ce.get("goal", raw),
                repo=repo or RepoTarget(),
                primary_files=[],  # Improved file selection UI will fill this later
                allowed_languages=ce.get("allowed_languages", []),
            )

        # Optional test_run spec
        test_run = None
        if "test_run" in data:
            tr = data["test_run"]
            test_run = TestRunSpec(
                repo=repo or RepoTarget(),
                command=tr.get("command", "pytest"),
                only_if_files_changed=False,
            )

        # Optional project management spec
        project_mgmt = None
        if "project_mgmt" in data:
            pm = data["project_mgmt"]
            project_mgmt = ProjectManagementSpec(
                tickets=pm.get("tickets", []),
                repo=repo,
                pr_number=pm.get("pr_number"),
                notes_goal=pm.get("notes_goal"),
            )

        return NaviIntent(
            family=family,
            kind=kind,
            priority=priority or IntentPriority.NORMAL,
            raw_text=raw,
            source=data.get("source", "chat"),
            slots=data.get("slots", {}),
            confidence=float(data.get("confidence", 0.85)),
            # New provider-aware fields
            provider=provider or Provider.GENERIC,
            object_type=data.get("object_type"),
            object_id=data.get("object_id"), 
            filters=data.get("filters", {}),
            code_edit=code_edit,
            test_run=test_run,
            project_mgmt=project_mgmt,
            workflow=workflow,
        )


# ======================================================================
# Utility Helpers
# ======================================================================

def _norm_text(msg: Any) -> str:
    if isinstance(msg, str):
        return msg
    return getattr(msg, "content", str(msg))


def _safe_enum(enum_cls, value: Any):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except Exception:
        return None


# ======================================================================
# The System Prompt for Intent Classification
# ======================================================================

INTENT_SYSTEM_PROMPT = """
You are NAVI's Intent Classifier for cross-app autonomous workflows.

Given a user message, classify it into a JSON object with provider-aware fields that work across Jira, Slack, GitHub, Teams, Zoom, Jenkins, and other services.

YOU MUST ALWAYS RETURN VALID JSON IN THIS EXACT FORMAT:

{
  "provider": "jira | slack | github | teams | zoom | confluence | notion | linear | asana | jenkins | generic",
  "family": "ENGINEERING | PROJECT_MANAGEMENT | AUTONOMOUS_ORCHESTRATION",
  "kind": "LIST_MY_ITEMS | LIST_ITEMS | SUMMARIZE_CHANNEL | SHOW_ITEM_DETAILS | IMPLEMENT | FIX | CREATE | DEPLOY | SYNC | CONFIGURE | SEARCH | EXPLAIN | GENERIC",
  "object_type": "issue | pr | channel | meeting | pipeline | doc | repo | code | generic | null",
  "object_id": "specific ID if mentioned (JIRA-123, #standup, PR-456) or null",
  "filters": {
    "status": "open/closed/in-progress (if mentioned)",
    "assignee": "username (if mentioned)",
    "project": "project key (if mentioned)",
    "limit": "number (if mentioned)",
    "timeframe": "today/this week/last 7 days (if mentioned)"
  },
  "priority": "normal | high | critical",
  "autonomy_mode": "assisted",
  "confidence": 0.8,
  "slots": {},
  "workflow": {
    "max_steps": 1,
    "auto_run_tests": false,
    "allow_cross_repo_changes": false,
    "allow_long_running": false
  }
}

CLASSIFICATION RULES:

🔹 PROVIDER (which external system):
- "jira": jira tickets/issues/stories/boards/sprints ("my jira tasks", "jira issues assigned to me")
- "slack": slack channels/messages/threads/teams ("slack channel", "#standup", "what happened in slack")
- "github": repos/PRs/issues/actions/releases ("github issues", "my pull requests", "github repo")
- "teams": microsoft teams channels/meetings/chats ("teams meeting", "teams channel")
- "zoom": meetings/recordings/participants ("zoom meeting", "zoom recordings")
- "confluence": pages/spaces/documentation ("confluence page", "wiki", "documentation")
- "jenkins": builds/pipelines/jobs ("jenkins build", "CI pipeline", "build status")
- "generic": code/files/general engineering ("refactor code", "debug this", "explain function")

🔹 FAMILY (broad category):
- "PROJECT_MANAGEMENT": task management, issue tracking, project status (Jira issues, GitHub issues, project boards)
- "ENGINEERING": code, debugging, testing, builds, development work (code changes, fixes, implementations)
- "AUTONOMOUS_ORCHESTRATION": multi-step workflows, automation, complex orchestration

🔹 KIND (specific action - use these exact values):
- "LIST_MY_ITEMS": "list my jira tickets", "show my github issues", "my assigned tasks"
- "SUMMARIZE_CHANNEL": "summarize slack channel", "what happened in #standup", "teams channel summary"
- "SHOW_ITEM_DETAILS": "show details of JIRA-123", "explain PR-456", "what is issue XYZ about"
- "IMPLEMENT": "implement feature", "add functionality", "build this", "create new code"
- "FIX": "fix bug", "debug error", "resolve issue", "patch problem"
- "CREATE": "create file", "generate code", "make new component"
- "EXPLAIN": "explain code", "what does this do", "help me understand"
- "SEARCH": "find code", "search for", "locate function"
- "GENERIC": fallback for unclear requests

🔹 OBJECT_TYPE (what kind of object):
- "issue": Jira issues, GitHub issues, Linear tasks, Asana tasks
- "pr": Pull requests, merge requests
- "channel": Slack channels, Teams channels, Discord channels
- "meeting": Zoom meetings, Teams meetings, calendar events
- "pipeline": Jenkins builds, CI/CD pipelines, GitHub Actions
- "doc": Confluence pages, Notion pages, documentation, wikis
- "repo": Git repositories, codebases
- "code": Source code, functions, classes, files

EXAMPLES:

"list my jira tasks assigned to me"
→ {"provider": "jira", "family": "PROJECT_MANAGEMENT", "kind": "LIST_MY_ITEMS", "object_type": "issue", "filters": {"assignee": "me"}}

"summarize what happened in the #standup slack channel today"
→ {"provider": "slack", "family": "PROJECT_MANAGEMENT", "kind": "SUMMARIZE_CHANNEL", "object_type": "channel", "object_id": "standup", "filters": {"timeframe": "today"}}

"show me my open github pull requests"
→ {"provider": "github", "family": "ENGINEERING", "kind": "LIST_MY_ITEMS", "object_type": "pr", "filters": {"status": "open", "assignee": "me"}}

"fix the authentication bug in login.js"
→ {"provider": "generic", "family": "ENGINEERING", "kind": "FIX", "object_type": "code", "filters": {"file": "login.js", "area": "authentication"}}

Return ONLY the JSON object. No explanations or extra text.
"""