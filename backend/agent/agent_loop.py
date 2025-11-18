"""
NAVI Agent Loop - The Core 7-Stage Reasoning Pipeline

This is the main entry point for NAVI's autonomous agent behavior.
Called by /api/navi/chat for every user message.

Pipeline stages:
1. Load user state (what were they doing?)
2. Build full context (workspace + org + memory)
3. Classify intent (what do they want?)
4. Generate plan (how to accomplish it?)
5. Check approval (destructive actions need confirmation)
6. Execute or respond (tools vs. chat)
7. Update state (remember for next turn)
"""

import logging
from typing import Dict, Any, Optional

from backend.agent.context_builder import build_context
from backend.agent.memory_retriever import retrieve_memories
from backend.agent.org_retriever import retrieve_org_context
from backend.agent.workspace_retriever import retrieve_workspace_context
from backend.agent.intent_classifier import classify_intent
from backend.agent.planner import generate_plan
from backend.agent.tool_executor import execute_tool
from backend.agent.state_manager import (
    get_user_state,
    update_user_state,
    clear_user_state
)
from backend.services.llm import call_llm

logger = logging.getLogger(__name__)


async def run_agent_loop(
    user_id: str, 
    message: str,
    model: str = "gpt-4",
    mode: str = "chat",
    db = None
) -> Dict[str, Any]:
    """
    Main NAVI agent pipeline.
    This is called every time the user sends a message.
    
    Args:
        user_id: User identifier
        message: User's message
        model: LLM model to use
        mode: "chat" or "agent-full"
        db: Database session
    
    Returns:
        {
            "reply": str,              # NAVI's response
            "actions": List[Dict],     # Proposed actions (for approval)
            "should_stream": bool,     # Whether to stream response
            "state": Dict              # Updated state (for debugging)
        }
    """
    
    try:
        logger.info(f"[AGENT] Starting loop for user={user_id}, message='{message[:50]}...'")
        
        # ---------------------------------------------------------
        # STAGE 1: Load user state (what were they doing last?)
        # ---------------------------------------------------------
        previous_state = await get_user_state(user_id)
        logger.info(f"[AGENT] Previous state: {previous_state}")
        
        # Special case: user typed "yes", "sure", "ok"
        # This is the KEY to making NAVI understand affirmatives
        if message.strip().lower() in ("yes", "sure", "okay", "ok", "go ahead", "yes please", "please"):
            if previous_state and previous_state.get("pending_action"):
                logger.info(f"[AGENT] Affirmative detected, executing pending action")
                return await execute_tool(user_id, previous_state["pending_action"], db=db)
            
            # If no pending action, treat as continuation
            message = f"(user agrees to continue previous task) {message}"
            logger.info(f"[AGENT] Affirmative without pending action, continuing conversation")
        
        # ---------------------------------------------------------
        # STAGE 2: Build full context (workspace + org + memory)
        # ---------------------------------------------------------
        logger.info(f"[AGENT] Retrieving context...")
        workspace_ctx = await retrieve_workspace_context(user_id)
        org_ctx = await retrieve_org_context(user_id, message, db=db)
        memory_ctx = await retrieve_memories(user_id, message, db=db)
        
        full_context = build_context(
            workspace_ctx, 
            org_ctx, 
            memory_ctx, 
            previous_state, 
            message
        )
        logger.info(f"[AGENT] Context built: {len(full_context.get('combined', ''))} chars")
        
        # ---------------------------------------------------------
        # STAGE 3: Ask LLM to classify the user's intent
        # ---------------------------------------------------------
        logger.info(f"[AGENT] Classifying intent...")
        intent = await classify_intent(message, full_context, previous_state)
        logger.info(f"[AGENT] Intent: {intent.get('type')}")
        
        # ---------------------------------------------------------
        # STAGE 4: If intent is ambiguous → ask user
        # ---------------------------------------------------------
        if intent["type"] == "ambiguous":
            logger.info(f"[AGENT] Intent ambiguous, asking for clarification")
            await update_user_state(user_id, {"pending_clarification": intent})
            return {
                "reply": intent["question"],
                "actions": [],
                "should_stream": False,
                "state": {"intent": "ambiguous"}
            }
        
        # ---------------------------------------------------------
        # STAGE 5: Generate multi-step plan for the intent
        # ---------------------------------------------------------
        logger.info(f"[AGENT] Generating plan...")
        plan = await generate_plan(intent, full_context, previous_state)
        logger.info(f"[AGENT] Plan type: {plan.get('type')}, requires_approval: {plan.get('requires_user_approval')}")
        
        # ---------------------------------------------------------
        # STAGE 6: If plan requires tools → stop & ask approval
        # ---------------------------------------------------------
        if plan.get("requires_user_approval"):
            # Save pending tool call
            await update_user_state(user_id, {
                "pending_action": plan["tool"],
                "pending_intent": intent,
                "last_plan": plan
            })
            logger.info(f"[AGENT] Tool requires approval, waiting for user")
            return {
                "reply": plan["explanation"],
                "actions": [plan["tool"]],  # front-end shows "Approve / Reject"
                "should_stream": False,
                "state": {"pending_approval": True}
            }
        
        # ---------------------------------------------------------
        # STAGE 7a: If plan is "LLM-response only", call LLM
        # ---------------------------------------------------------
        if plan["type"] == "pure_chat":
            logger.info(f"[AGENT] Pure chat response, calling LLM")
            answer = await call_llm(
                message, 
                full_context, 
                model=model,
                mode=mode
            )
            clear_user_state(user_id)
            return {
                "reply": answer,
                "actions": [],
                "should_stream": True,
                "state": {"completed": True}
            }
        
        # ---------------------------------------------------------
        # STAGE 7b: If plan demands immediate execution of tools
        # ---------------------------------------------------------
        if plan["type"] == "execute_tool":
            logger.info(f"[AGENT] Executing tool immediately")
            result = await execute_tool(user_id, plan["tool"], db=db)
            clear_user_state(user_id)
            return result
        
        # ---------------------------------------------------------
        # Safety fallback
        # ---------------------------------------------------------
        logger.warning(f"[AGENT] Reached safety fallback, plan type: {plan.get('type')}")
        clear_user_state(user_id)
        return {
            "reply": "I'm a bit unsure how to proceed — can you rephrase your request?",
            "actions": [],
            "should_stream": False,
            "state": {"fallback": True}
        }
    
    except Exception as e:
        logger.error(f"[AGENT] Error in agent loop: {e}", exc_info=True)
        return {
            "reply": f"I encountered an error while processing your request. Let me try a different approach - could you rephrase what you need?",
            "actions": [],
            "should_stream": False,
            "state": {"error": str(e)}
        }
