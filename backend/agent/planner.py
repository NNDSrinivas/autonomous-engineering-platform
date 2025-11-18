"""
Autonomous Planner for NAVI Agent

Generates multi-step execution plans based on user intent + full context.
This is what makes NAVI act like an AGENT, not a chatbot.

The planner decides:
- Should NAVI execute a tool action?
- Should NAVI generate code?
- Should NAVI propose a diff?
- Should NAVI ask for approval first?
- Is this a pure chat response?
- Is this part of ongoing multi-step workflow?

This is the CORE difference between:
- Chatbot: "I can help you with that"
- Agent: *Actually does it*
"""

import json
import logging
from typing import Dict, Any, Optional, List

from backend.llm.llm import call_llm

logger = logging.getLogger(__name__)


# ==============================================================================
# PLANNER SYSTEM PROMPT
# ==============================================================================

PLAN_SYSTEM_PROMPT = """
You are NAVI's autonomous planning engine.

Given:
- User intent classification
- Full organizational context (Jira/Slack/Confluence/GitHub/Zoom)
- Workspace files and code structure
- User state (current task, pending actions)

Your job: Decide WHAT NAVI SHOULD DO.

Return ONLY valid JSON with this structure:

{
  "action_type": "pure_chat|execute_tool|generate_code|apply_diff|multi_step_workflow",
  "requires_approval": true|false,
  "confidence": 0.0-1.0,
  "reasoning": "Why you chose this plan",
  "tool_name": "create_file|apply_diff|run_command|search_repo|...",
  "tool_params": {...},
  "steps": [
    {"description": "Step 1", "action": "..."},
    {"description": "Step 2", "action": "..."}
  ],
  "explanation_to_user": "What NAVI will tell the user before executing"
}

CRITICAL RULES:

1. **Pure Chat Response**:
   - Use for: jira_query, code_explain, documentation, planning, personal
   - No tool execution, just conversational answer
   - action_type = "pure_chat"

2. **Execute Tool**:
   - Use for: repo_navigation, debugging (with logs), meeting_summary
   - Single tool execution
   - action_type = "execute_tool"
   - Set requires_approval = false for read-only tools
   - Set requires_approval = true for write operations

3. **Generate Code**:
   - Use for: code_generate, code_modify
   - NAVI will generate code and show to user
   - action_type = "generate_code"
   - Set requires_approval = true (always ask before applying)

4. **Apply Diff**:
   - Use for: code_modify with specific file target
   - NAVI proposes diff, user approves
   - action_type = "apply_diff"
   - requires_approval = true (ALWAYS)

5. **Multi-Step Workflow**:
   - Use for: jira_execution, workflow_start, complex debugging
   - Break into sequential steps
   - action_type = "multi_step_workflow"
   - Each step may require approval
   - Example for "implement JIRA-123":
     * Step 1: Understand requirements (pure_chat)
     * Step 2: Generate code (generate_code, needs approval)
     * Step 3: Create test file (execute_tool, needs approval)
     * Step 4: Run tests (execute_tool, no approval)

6. **Task Continue**:
   - If intent = "task_continue", get pending_action from state
   - Execute the pending action immediately
   - action_type = same as pending action
   - requires_approval = false (already approved)

7. **Confidence Scoring**:
   - 1.0: Crystal clear, no ambiguity
   - 0.8-0.9: Very confident, minor details missing
   - 0.6-0.7: Moderate confidence, may need clarification
   - <0.6: Low confidence, ask user for clarification

8. **Safety**:
   - ALWAYS require approval for:
     * File creation/modification
     * File deletion
     * Running terminal commands
     * API calls with side effects
   - NO approval needed for:
     * Reading files
     * Searching workspace
     * Fetching Jira/Slack/etc.

AVAILABLE TOOLS:
- create_file: Create new file
- apply_diff: Modify existing file
- delete_file: Delete file
- run_command: Execute terminal command
- search_repo: Search workspace
- open_file: Open file in editor
- fetch_jira: Get Jira issue details
- fetch_slack: Get Slack messages
- fetch_confluence: Get Confluence pages
"""


# ==============================================================================
# PLAN GENERATION
# ==============================================================================

async def generate_plan(
    intent: Dict[str, Any],
    context: Dict[str, Any],
    user_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate autonomous execution plan based on intent + context.
    
    This is the CORE of NAVI's agent behavior.
    
    Args:
        intent: Intent classification result from intent_classifier
        context: Full RAG context (memory + org + workspace)
        user_state: Current user state
    
    Returns:
        Execution plan with action_type, tool details, steps, approval requirements
    """
    if user_state is None:
        user_state = {}
    
    intent_type = intent.get("type")
    logger.info(f"[PLANNER] Generating plan for intent: {intent_type}")
    
    # Special handling for task_continue
    if intent_type == "task_continue":
        pending_action = user_state.get("pending_action")
        if pending_action:
            logger.info(f"[PLANNER] Resuming pending action: {pending_action['type']}")
            return {
                "action_type": "execute_tool",
                "requires_approval": False,  # Already approved by user saying "yes"
                "confidence": 1.0,
                "reasoning": "User approved pending action",
                "tool_name": pending_action["type"],
                "tool_params": pending_action.get("data", {}),
                "steps": [],
                "explanation_to_user": f"Executing: {pending_action.get('description', 'pending action')}"
            }
        else:
            # No pending action, shouldn't happen
            logger.warning("[PLANNER] task_continue intent but no pending_action in state")
            return {
                "action_type": "pure_chat",
                "requires_approval": False,
                "confidence": 0.3,
                "reasoning": "task_continue with no pending action",
                "explanation_to_user": "I don't see any pending action to continue. What would you like me to do?"
            }
    
    # Build LLM prompt with full context
    llm_prompt = f"""
USER INTENT:
{json.dumps(intent, indent=2)}

CURRENT STATE:
{json.dumps(user_state, indent=2)}

CONTEXT:
{json.dumps(context, indent=2)}

Generate an execution plan for this intent.
Return ONLY valid JSON matching the schema.
"""
    
    try:
        response = await call_llm(
            system_prompt=PLAN_SYSTEM_PROMPT,
            user_prompt=llm_prompt,
            model="gpt-4o",  # Use latest model for best planning
            temperature=0.2  # Low temperature for consistent planning
        )
        
        # Parse LLM response as JSON
        plan = json.loads(response)
        
        # Validate action_type
        valid_actions = {"pure_chat", "execute_tool", "generate_code", "apply_diff", "multi_step_workflow"}
        if plan.get("action_type") not in valid_actions:
            plan["action_type"] = "pure_chat"
            plan["confidence"] = 0.3
            plan["reasoning"] = f"Invalid action_type returned: {plan.get('action_type')}"
        
        # Ensure required fields exist
        plan.setdefault("requires_approval", True)  # Default to safe
        plan.setdefault("confidence", 0.5)
        plan.setdefault("reasoning", "No reasoning provided")
        plan.setdefault("steps", [])
        plan.setdefault("explanation_to_user", "")
        
        # Safety check: Enforce approval for write operations
        if plan["action_type"] in {"execute_tool", "generate_code", "apply_diff"}:
            tool_name = plan.get("tool_name", "")
            write_tools = {"create_file", "apply_diff", "delete_file", "run_command"}
            if tool_name in write_tools and not plan.get("requires_approval"):
                logger.warning(f"[PLANNER] Forcing approval for write tool: {tool_name}")
                plan["requires_approval"] = True
        
        logger.info(f"[PLANNER] Generated plan: {plan['action_type']} (approval={plan['requires_approval']})")
        return plan
    
    except json.JSONDecodeError as e:
        # LLM returned invalid JSON
        logger.error(f"Failed to parse planner response: {e}")
        return {
            "action_type": "pure_chat",
            "requires_approval": False,
            "confidence": 0.2,
            "reasoning": f"Failed to parse planner response: {str(e)}",
            "explanation_to_user": "I'm having trouble planning the next steps. Could you clarify what you'd like me to do?"
        }
    
    except Exception as e:
        # Unexpected error
        logger.error(f"Planning error: {e}")
        return {
            "action_type": "pure_chat",
            "requires_approval": False,
            "confidence": 0.1,
            "reasoning": f"Planning error: {str(e)}",
            "explanation_to_user": "Something went wrong while planning. Could you try rephrasing your request?"
        }


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def is_read_only_plan(plan: Dict[str, Any]) -> bool:
    """
    Check if plan is read-only (no side effects).
    
    Read-only plans don't require approval.
    """
    if plan["action_type"] == "pure_chat":
        return True
    
    if plan["action_type"] == "execute_tool":
        read_only_tools = {
            "search_repo", "open_file", "read_file",
            "fetch_jira", "fetch_slack", "fetch_confluence",
            "fetch_github", "fetch_zoom"
        }
        return plan.get("tool_name") in read_only_tools
    
    return False


def requires_user_approval(plan: Dict[str, Any]) -> bool:
    """
    Check if plan requires user approval before execution.
    
    Always returns True for write operations.
    """
    return plan.get("requires_approval", True)


def format_plan_for_approval(plan: Dict[str, Any]) -> str:
    """
    Format plan as human-readable text for approval prompt.
    
    Example output:
    "I'll create a new file `backend/agent/tools.py` with 150 lines of code. Should I proceed?"
    """
    action_type = plan.get("action_type")
    tool_name = plan.get("tool_name")
    explanation = plan.get("explanation_to_user", "")
    
    if action_type == "execute_tool":
        return f"{explanation}\n\nShould I proceed?"
    
    elif action_type == "generate_code":
        return f"{explanation}\n\nShould I generate this code?"
    
    elif action_type == "apply_diff":
        return f"{explanation}\n\nShould I apply these changes?"
    
    elif action_type == "multi_step_workflow":
        steps_text = "\n".join([
            f"{i+1}. {step['description']}"
            for i, step in enumerate(plan.get("steps", []))
        ])
        return f"{explanation}\n\nPlan:\n{steps_text}\n\nShould I proceed with this plan?"
    
    return explanation
