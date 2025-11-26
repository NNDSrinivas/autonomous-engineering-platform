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
        model: str = "claude-3.7-opus",
        provider: str = "anthropic",
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

        system_prompt = INTENT_SYSTEM_PROMPT

        user_prompt = json.dumps(
            {
                "text": text,
                "metadata": metadata,
            },
            indent=2,
        )

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
You are NAVI, the Autonomous Engineering Platform's Intent Classifier.
Your job is to classify user messages into structured engineering intents.

YOU MUST ALWAYS RETURN VALID JSON IN THIS EXACT FORMAT:

{
  "family": "...",
  "kind": "...",
  "priority": "...",
  "autonomy_mode": "...",
  "confidence": 0.0,
  "slots": {},
  "code_edit": {},
  "test_run": {},
  "project_mgmt": {},
  "workflow": {
    "max_steps": 0,
    "auto_run_tests": false,
    "allow_cross_repo_changes": false,
    "allow_long_running": false
  }
}

Rules:
- Do NOT insert text outside JSON.
- Do NOT add commentary or explanations.
- Classify precisely.
- Use the strongest engineering-analysis ability.
- If message describes code changes → use MODIFY_CODE or IMPLEMENT_FEATURE.
- If message is about bugs → FIX_BUG.
- If message asks to run tests → RUN_TESTS.
- If message asks for JIRA/PR/story → PROJECT_MANAGEMENT family.
- Use HIGH or CRITICAL priority only when clearly justified.
- autonomy_mode:
    - "AUTONOMOUS_SESSION" for "just do it", "don't ask", "fully automate".
    - "SINGLE_STEP" for one-off commands.
    - "ASSISTED" for normal interaction.
    - "BATCH" for bulk and multi-repo changes.
"""