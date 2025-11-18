"""
NAVI Agent Orchestrator - Main coordination layer for agent mode

This orchestrator:
1. Gathers organizational context from the memory graph (Jira, Slack, PRs, docs)
2. Plans what NAVI will do (structured steps)
3. Coordinates execution and returns results with progress tracking
4. Enables Copilot-style UI feedback showing NAVI's work

Future enhancements:
- Actual code editing via diff engine
- Multi-step streaming updates
- Background long-running tasks
- Tool execution integration
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
import os

from backend.services.memory_graph_service import MemoryGraphService
from backend.services.org_brain_query import OrgBrainQuery
from backend.agent.agent_types import AgentRunSummary, AgentStep

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class NaviAgentContext:
    """
    Main agent context for NAVI orchestration.
    
    This class coordinates the agent's work by:
    - Querying the organizational memory graph for context
    - Planning execution steps
    - Managing step status and progress
    - Returning structured results for UI rendering
    """
    
    def __init__(
        self,
        db: Session,
        org_id: str,
        user_id: str,
        workspace: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize agent context.
        
        Args:
            db: Database session
            org_id: Organization identifier
            user_id: User identifier
            workspace: Current workspace context (files, folder, etc)
        """
        self.db = db
        self.org_id = org_id
        self.user_id = user_id
        self.workspace = workspace or {}
        
        logger.info(f"Initialized NAVI agent context for user {user_id} in org {org_id}")
    
    async def build_run(
        self,
        user_message: str,
        mode: str = "agent-full",
    ) -> Dict[str, Any]:
        """
        Main orchestrator for agent mode.
        
        This executes the full agent loop:
        1. Understand the user's request
        2. Gather organizational context from memory graph
        3. Plan the response with concrete steps
        4. (Future) Execute code edits or tool calls
        
        Args:
            user_message: User's natural language request
            mode: Execution mode (agent-full, chat-only, etc)
            
        Returns:
            Dict with:
            - assistant_text: NAVI's response text
            - agent_run: AgentRunSummary structure for UI
            - file_actions: List of file edit actions (empty for now)
        """
        run_id = str(uuid.uuid4())
        logger.info(f"Starting agent run {run_id} for message: {user_message[:100]}")
        
        # Define execution steps
        steps: List[AgentStep] = [
            AgentStep(id="understand", label="Understand your request", status="running", detail=None),
            AgentStep(id="org_context", label="Gather org context", status="pending", detail=None),
            AgentStep(id="plan", label="Plan what to do", status="pending", detail=None),
            AgentStep(id="edits", label="Propose or apply code changes", status="pending", detail=None),
        ]
        
        try:
            # --- Step 1: Understand request --------------------------------------
            logger.info(f"[{run_id}] Step 1: Understanding request")
            steps[0].status = "done"
            steps[0].detail = f"Analyzing: '{user_message[:80]}...'"
            
            # --- Step 2: Get org context via Org Brain --------------------------
            logger.info(f"[{run_id}] Step 2: Gathering organizational context")
            steps[1].status = "running"
            org_nodes_count = 0  # Initialize before use
            
            try:
                mg = MemoryGraphService(self.db, self.org_id, self.user_id)
                qb = OrgBrainQuery(mg)
                
                # Build context query
                context_query = (
                    f"User request: {user_message}\n"
                    f"Workspace: {self.workspace.get('rootPath', 'Unknown')}\n"
                    "Find relevant Jira issues, PRs, Slack discussions, documentation, "
                    "and code that relates to this request."
                )
                
                org_context_result = await qb.query(
                    question=context_query,
                    limit=12,
                    include_edges=True
                )
                
                org_context_answer = org_context_result.get("answer", "")
                org_nodes_count = len(org_context_result.get("nodes", []))
                
                steps[1].status = "done"
                steps[1].detail = f"Found {org_nodes_count} related items from Jira, Slack, GitHub, and docs"
                
                logger.info(f"[{run_id}] Org context gathered: {org_nodes_count} nodes")
                
            except Exception as e:
                logger.warning(f"[{run_id}] Failed to gather org context: {e}")
                org_context_answer = "No organizational context available."
                steps[1].status = "done"
                steps[1].detail = "Org context unavailable (proceeding without it)"
            
            # --- Step 3: Plan response ------------------------------------------
            logger.info(f"[{run_id}] Step 3: Planning response")
            steps[2].status = "running"
            
            planning_prompt = (
                "You are NAVI, an autonomous engineering assistant inside VS Code. "
                "You work as a teammate, not a chatbot.\n\n"
                f"The user asked:\n{user_message}\n\n"
                "Here is organizational context from the memory graph:\n"
                f"{org_context_answer}\n\n"
                "Your task:\n"
                "1. Provide a warm, helpful response that addresses their request\n"
                "2. Reference relevant context (Jira issues, PRs, discussions) when applicable\n"
                "3. Give a concrete plan if they're asking how to do something\n"
                "4. If code changes are needed, describe which files and what changes\n"
                "5. Be conversational and supportive - you're a teammate, not an AI assistant\n\n"
                "Keep your response focused and actionable."
            )
            
            planning_chat = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are NAVI, an autonomous engineering assistant embedded in VS Code. "
                            "You have access to organizational memory (Jira, Slack, GitHub, docs). "
                            "Respond as a helpful teammate who understands context, not a generic chatbot. "
                            "Be warm, direct, and actionable."
                        ),
                    },
                    {"role": "user", "content": planning_prompt},
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            assistant_text = planning_chat.choices[0].message.content
            if assistant_text is None:
                assistant_text = "I encountered an issue generating a response. Please try again."
            
            steps[2].status = "done"
            steps[2].detail = "Generated response with organizational context"
            
            logger.info(f"[{run_id}] Planning complete: {len(assistant_text)} chars")
            
            # --- Step 4: (v1) Propose edits in narrative form -------------------
            # Future versions will integrate the diff engine here
            logger.info(f"[{run_id}] Step 4: Checking for code edits")
            steps[3].status = "done"
            steps[3].detail = (
                "Code edits described in response text (v1). "
                "Future versions will generate actual diffs."
            )
            
            # Build agent run summary
            agent_run = AgentRunSummary(
                id=run_id,
                title="NAVI Agent Run",
                status="completed",
                steps=steps,
                meta={
                    "org_context_included": True,
                    "org_nodes_count": org_nodes_count if 'org_nodes_count' in locals() else 0,
                    "mode": mode,
                    "model": "gpt-4",
                }
            )
            
            # File actions (empty for v1, will be populated when diff engine is integrated)
            file_actions: List[Dict[str, Any]] = []
            
            logger.info(f"[{run_id}] Agent run completed successfully")
            
            return {
                "assistant_text": assistant_text,
                "agent_run": agent_run,
                "file_actions": file_actions,
            }
            
        except Exception as e:
            logger.error(f"[{run_id}] Agent run failed: {e}", exc_info=True)
            
            # Mark current step as blocked
            for step in steps:
                if step.status == "running":
                    step.status = "blocked"
                    step.detail = f"Error: {str(e)}"
                    break
            
            agent_run = AgentRunSummary(
                id=run_id,
                title="NAVI Agent Run (Failed)",
                status="failed",
                steps=steps,
                meta={
                    "error": str(e),
                    "mode": mode,
                }
            )
            
            return {
                "assistant_text": (
                    "I encountered an error while processing your request. "
                    "Please check the agent run details for more information."
                ),
                "agent_run": agent_run,
                "file_actions": [],
            }
