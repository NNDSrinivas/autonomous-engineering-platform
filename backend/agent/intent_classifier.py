"""
Intent Classifier for NAVI Agent

LLM-driven dynamic intent classification using full RAG context.
This is the BRAIN that determines what the user wants.

Unlike scripted chatbots, this uses:
- Conversation memory
- Organizational context (Jira/Slack/Confluence/GitHub/Zoom)
- Workspace files and code
- User state and preferences

To dynamically understand ANY user request, even extremely vague ones.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List

from backend.agent.intent_schema import (
    INTENT_TYPES,
    INTENT_DESCRIPTIONS,
    AFFIRMATIVE_PATTERNS,
    ENTITY_HINTS
)
from backend.llm.llm import call_llm

logger = logging.getLogger(__name__)


# ==============================================================================
# INTENT CLASSIFICATION SYSTEM PROMPT
# ==============================================================================

INTENT_SYSTEM_PROMPT = """
You are NAVI's intent classification engine.

Your job: Determine the user's TRUE intent given:
- Full conversation memory
- Organizational context (Jira/Slack/Confluence/GitHub/Zoom)
- Workspace files and code structure
- Current user state (what they're working on)
- User message

Return ONLY valid JSON with this structure:

{
  "type": "jira_query|jira_execution|code_explain|code_modify|code_generate|repo_navigation|debugging|planning|documentation|meeting_summary|task_continue|workflow_start|personal|ambiguous",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why you chose this intent",
  "entities": {
    "jira_keys": ["SCRUM-123"],
    "files": ["backend/api/navi.py"],
    "functions": ["run_agent_loop"],
    "topics": ["authentication", "RAG"],
    "modifications": ["refactor", "add logging"]
  },
  "clarification_question": "Ask if ambiguous (optional)"
}

CRITICAL RULES:

1. **Affirmative Responses** (yes/sure/ok/continue):
   - ALWAYS classify as "task_continue" if user state shows pending action
   - confidence = 1.0

2. **Context Awareness**:
   - Use org context to infer implicit Jira IDs
   - Use workspace context to infer code targets
   - Use memory to understand user preferences
   - Use state to understand "this", "that", "the issue"

3. **Vague Messages**:
   - If truly ambiguous, return type="ambiguous"
   - Provide 2-3 possible interpretations in clarification_question
   - Example: "fix it" → ask "Fix what? The current Jira (SCRUM-123), the error in server.py, or something else?"

4. **Entity Extraction**:
   - Extract ALL relevant entities from message + context
   - Include implicit references (e.g., "this file" → get from workspace context)
   - Jira keys from BOTH message AND org context

5. **Confidence Scoring**:
   - 1.0: Completely clear (affirmatives, explicit commands)
   - 0.8-0.9: Very clear with minor ambiguity
   - 0.6-0.7: Moderate clarity, multiple interpretations
   - <0.6: Ambiguous, needs clarification

6. **Multi-Intent Detection**:
   - If message contains multiple intents, choose PRIMARY intent
   - Mention secondary intents in reasoning

INTENT CATALOG:
"""

# Append intent descriptions to system prompt
for intent_type, details in INTENT_DESCRIPTIONS.items():
    INTENT_SYSTEM_PROMPT += f"\n- **{intent_type}**: {details['description']}"
    INTENT_SYSTEM_PROMPT += f"\n  Examples: {', '.join(details['examples'][:3])}"


# ==============================================================================
# QUICK PATTERN-BASED DETECTION (Before LLM)
# ==============================================================================

def quick_intent_check(user_message: str, user_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fast pattern-based intent detection for common cases.
    Avoids LLM call for obvious intents.
    
    Returns:
        Intent dict if matched, None otherwise
    """
    msg_lower = user_message.lower().strip()
    
    # 1. Affirmative responses → task_continue
    if msg_lower in AFFIRMATIVE_PATTERNS:
        if user_state.get("pending_action"):
            return {
                "type": "task_continue",
                "confidence": 1.0,
                "reasoning": "Affirmative response with pending action in state",
                "entities": {},
                "clarification_question": None
            }
    
    # 2. Single word affirmatives with punctuation
    if re.match(r'^(yes|yeah|sure|ok|okay|continue|proceed)[!.?]*$', msg_lower):
        if user_state.get("pending_action"):
            return {
                "type": "task_continue",
                "confidence": 1.0,
                "reasoning": "Single-word affirmative with pending action",
                "entities": {},
                "clarification_question": None
            }
    
    # 3. Extremely short messages without context → ambiguous
    if len(msg_lower) < 5 and not user_state.get("current_task"):
        return {
            "type": "ambiguous",
            "confidence": 0.9,
            "reasoning": "Message too short without context",
            "entities": {},
            "clarification_question": "Could you provide more details? I'm not sure what you're referring to."
        }
    
    return None


# ==============================================================================
# LLM-DRIVEN INTENT CLASSIFICATION
# ==============================================================================

async def classify_intent(
    user_message: str,
    context: Dict[str, Any],
    user_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify user intent using full RAG context + LLM reasoning.
    
    This is the CORE of NAVI's intelligence. It understands:
    - Vague messages ("fix this", "continue")
    - Implicit references ("the Jira", "that file")
    - Conversational continuity ("yes", "sure")
    - Multi-step workflows
    
    Args:
        user_message: Raw user input
        context: Full RAG context (memory + org + workspace)
        user_state: Current user state (optional)
    
    Returns:
        Intent classification with confidence, entities, reasoning
    """
    if user_state is None:
        user_state = {}
    
    # Try quick pattern matching first
    quick_result = quick_intent_check(user_message, user_state)
    if quick_result:
        logger.info(f"Quick intent match: {quick_result['type']}")
        return quick_result
    
    # Build LLM prompt with full context
    llm_prompt = f"""
USER MESSAGE:
{user_message}

CURRENT STATE:
{json.dumps(user_state, indent=2)}

CONTEXT:
{json.dumps(context, indent=2)}

Classify the user's intent and extract entities.
Return ONLY valid JSON matching the schema.
"""
    
    try:
        response = await call_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=llm_prompt,
            model="gpt-4o",  # Use latest model for best reasoning
            temperature=0.1  # Low temperature for consistent classification
        )
        
        # Parse LLM response as JSON
        intent_result = json.loads(response)
        
        # Validate intent type
        if intent_result.get("type") not in INTENT_TYPES:
            intent_result["type"] = "ambiguous"
            intent_result["confidence"] = 0.3
            intent_result["reasoning"] = f"Invalid intent type returned: {intent_result.get('type')}"
        
        # Ensure all required fields exist
        intent_result.setdefault("entities", {})
        intent_result.setdefault("confidence", 0.5)
        intent_result.setdefault("reasoning", "No reasoning provided")
        intent_result.setdefault("clarification_question", None)
        
        logger.info(f"Classified intent: {intent_result['type']} (confidence: {intent_result['confidence']})")
        return intent_result
    
    except json.JSONDecodeError as e:
        # LLM returned invalid JSON
        logger.error(f"Failed to parse LLM response: {e}")
        return {
            "type": "ambiguous",
            "confidence": 0.2,
            "reasoning": f"Failed to parse LLM response: {str(e)}",
            "entities": {},
            "clarification_question": "I'm having trouble understanding. Could you rephrase that?"
        }
    
    except Exception as e:
        # Unexpected error
        logger.error(f"Intent classification error: {e}")
        return {
            "type": "ambiguous",
            "confidence": 0.1,
            "reasoning": f"Intent classification error: {str(e)}",
            "entities": {},
            "clarification_question": "Something went wrong. Could you try rephrasing your request?"
        }


# ==============================================================================
# ENTITY EXTRACTION HELPERS
# ==============================================================================

def extract_jira_keys(text: str) -> List[str]:
    """Extract Jira keys from text (e.g., SCRUM-123, ENG-45)."""
    pattern = r'\b[A-Z]{2,10}-\d+\b'
    return list(set(re.findall(pattern, text)))


def extract_file_references(text: str, workspace_context: Dict[str, Any]) -> List[str]:
    """Extract file references from text and workspace context."""
    files = []
    
    # Direct file mentions
    file_pattern = r'\b[\w\/\-\.]+\.(py|js|ts|tsx|jsx|java|go|rs|cpp|c|h|md|yaml|json|xml|sql)\b'
    files.extend(re.findall(file_pattern, text))
    
    # "this file", "current file" → use workspace context
    if re.search(r'\b(this|current|the)\s+file\b', text.lower()):
        if workspace_context.get("active_file"):
            files.append(workspace_context["active_file"])
    
    return list(set(files))


def enrich_entities_from_context(
    entities: Dict[str, Any],
    context: Dict[str, Any],
    user_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Enrich extracted entities with context-aware inference.
    
    Examples:
    - "this Jira" → add current_jira from state
    - "that file" → add active_file from workspace
    - "the error" → add last_error from state
    """
    enriched = entities.copy()
    
    # Infer Jira keys from state/context
    if user_state.get("current_jira"):
        enriched.setdefault("jira_keys", []).append(user_state["current_jira"])
    
    if context.get("org_context", {}).get("jira_keys"):
        enriched.setdefault("jira_keys", []).extend(context["org_context"]["jira_keys"])
    
    # Infer files from workspace
    if context.get("workspace_context", {}).get("active_file"):
        enriched.setdefault("files", []).append(context["workspace_context"]["active_file"])
    
    # Deduplicate
    for key in enriched:
        if isinstance(enriched[key], list):
            enriched[key] = list(set(enriched[key]))
    
    return enriched

    matches = re.findall(pattern, text)
    return list(set(matches))
