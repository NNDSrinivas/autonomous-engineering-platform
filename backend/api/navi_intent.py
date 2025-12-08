# backend/api/navi_intent.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal
import os
import logging
import json

from openai import AsyncOpenAI

router = APIRouter(prefix="/api/navi", tags=["navi-intent"])

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class IntentRequest(BaseModel):
    message: str

class IntentResponse(BaseModel):
    intent: Literal[
        "greeting",
        "jira_list",
        "jira_ticket", 
        "jira_priority",
        "code",
        "workspace",
        "general",
        "other",
    ]

INTENT_SYSTEM_PROMPT = """
You classify a single user message into one high-level intent for NAVI,
an engineering assistant inside VS Code.

Return ONLY a compact JSON object with this exact shape:
{"intent": "<one of: greeting,jira_list,jira_ticket,jira_priority,code,workspace,general,other>"}

Definitions:
- greeting: messages like "hi", "hello", "hey", "good morning", etc., with no other request.
- jira_list: asking for Jira tasks/issues assigned to them, their queue/board, or "what tickets do I have".
- jira_ticket: asking about a specific ticket key (e.g., LAB-158, SCRUM-2) or "what is this ticket about".
- jira_priority: asking which ticket to do first, priority between tickets, what to pick next, etc.
- code: questions about code, bugs, errors, refactors, tests, performance, etc.
- workspace: questions about project structure, repo layout, tooling setup, configuration.
- general: general questions or conversation not covered above.
- other: anything that clearly doesn't fit.

Be conservative:
- A plain "hi", "hello", etc. MUST be "greeting".
- Only use jira_list / jira_ticket / jira_priority when Jira is clearly mentioned
  (words like jira, ticket, issue, story, bug, sprint, or keys like ABC-123).
"""

@router.post("/intent", response_model=IntentResponse)
async def classify_intent(req: IntentRequest) -> IntentResponse:
    """Classify user message intent to route appropriately."""
    if not client:
        # Fallback: simple heuristic if OpenAI is not configured
        text = req.message.lower().strip()
        if text in {"hi", "hello", "hey", "yo", "hola", "good morning", "good afternoon"}:
            return IntentResponse(intent="greeting")
        if any(word in text for word in ["jira", "ticket", "issue", "task", "story", "sprint"]):
            if any(phrase in text for phrase in ["my tasks", "what tickets", "show", "list"]):
                return IntentResponse(intent="jira_list")
            elif any(phrase in text for phrase in ["priority", "first", "next", "should I"]):
                return IntentResponse(intent="jira_priority")
            else:
                return IntentResponse(intent="jira_ticket")
        if any(word in text for word in ["code", "function", "bug", "error", "refactor", "test"]):
            return IntentResponse(intent="code")
        return IntentResponse(intent="general")

    try:
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": req.message},
            ],
            temperature=0,
            max_tokens=50,
        )
        raw = completion.choices[0].message.content or "{}"
        # Very thin parse – rely on the model to follow the JSON format
        data = json.loads(raw)
        intent = data.get("intent", "general")
        
        logger.info(f"[NAVI-INTENT] Classified '{req.message}' as: {intent}")
        return IntentResponse(intent=intent)
    except Exception:
        logger.error("[INTENT] Failed to classify", exc_info=True)
        # Fallback to simple heuristic on error
        text = req.message.lower().strip()
        if text in {"hi", "hello", "hey", "yo", "hola"}:
            return IntentResponse(intent="greeting")
        return IntentResponse(intent="general")