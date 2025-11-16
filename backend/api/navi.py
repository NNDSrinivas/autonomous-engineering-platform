"""
NAVI Chat API - Autonomous Engineering Assistant for VS Code Extension
Handles file attachments, context-aware responses, and agent actions
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi"])


# ============================================================================
# REQUEST / RESPONSE MODELS
# ============================================================================


class Attachment(BaseModel):
    """File attachment from VS Code workspace"""

    kind: Literal["selection", "file"] = "file"
    path: str
    content: str
    language: Optional[str] = None


class Message(BaseModel):
    """Chat message"""

    role: Literal["user", "assistant", "system"]
    content: str


class NaviChatRequest(BaseModel):
    """Request from VS Code extension"""

    id: str  # conversation ID
    model: str = Field(default="gpt-4", description="Model ID to use")
    mode: str = Field(
        default="chat", description="Mode: chat, agent-full, agent-limited"
    )
    messages: List[Message] = Field(default_factory=list)
    attachments: Optional[List[Attachment]] = Field(
        default=None, description="PR-5: Attached files from workspace"
    )
    stream: bool = False


class AgentAction(BaseModel):
    """Agent-proposed action (PR-6)"""

    type: Literal["replaceFile", "editFile", "createFile"]
    filePath: str
    description: str
    newContent: Optional[str] = None  # for replaceFile
    diff: Optional[str] = None  # for editFile


class NaviChatResponse(BaseModel):
    """Response to VS Code extension"""

    reply: str
    usage: Optional[Dict[str, int]] = None
    actions: Optional[List[AgentAction]] = Field(
        default=None, description="PR-6: Proposed agent actions"
    )


# ============================================================================
# MAIN ENDPOINT
# ============================================================================


@router.post("/chat", response_model=NaviChatResponse)
async def navi_chat(request: NaviChatRequest) -> NaviChatResponse:
    """
    Handle NAVI chat from VS Code extension

    PR-5: Uses attachments to build file context
    PR-6: Returns agent actions when in agent mode
    """
    try:
        logger.info(
            f"[NAVI] Request - conversation: {request.id}, model: {request.model}, "
            f"mode: {request.mode}, messages: {len(request.messages)}, "
            f"attachments: {len(request.attachments) if request.attachments else 0}"
        )

        # Build system prompt with file context (PR-5)
        system_prompt = _build_system_prompt(request)

        # Build messages array for LLM
        llm_messages = [{"role": "system", "content": system_prompt}]

        # Add file context as separate system message if attachments exist
        if request.attachments and len(request.attachments) > 0:
            files_context = _build_files_context(request.attachments)
            llm_messages.append({"role": "system", "content": files_context})

        # Add conversation history
        for msg in request.messages:
            llm_messages.append({"role": msg.role, "content": msg.content})

        # Call LLM (mocked for now - you'll replace with actual LLM call)
        assistant_reply, actions = await _call_llm(
            llm_messages, request.model, request.mode
        )

        logger.info(
            f"[NAVI] Response - reply length: {len(assistant_reply)}, "
            f"actions: {len(actions) if actions else 0}"
        )

        return NaviChatResponse(
            reply=assistant_reply,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            actions=actions,
        )

    except Exception as e:
        logger.error(f"[NAVI] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NAVI error: {str(e)}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _build_system_prompt(request: NaviChatRequest) -> str:
    """Build system prompt based on mode and attachments (PR-5)"""

    base_prompt = """You are NAVI, an autonomous engineering assistant running INSIDE VS Code.

You help developers with:
- Code explanations and reviews
- Debugging and error analysis
- Refactoring and optimization
- Test generation
- Documentation

"""

    # Add attachment awareness
    if request.attachments and len(request.attachments) > 0:
        base_prompt += f"""The user has attached {len(request.attachments)} file(s) from their workspace.
You MUST use ONLY these attached files to answer questions about their code.
Be specific and reference actual code from the attachments.

"""
    else:
        base_prompt += """The user has not attached any files yet.
If they ask about specific code, politely ask them to attach the relevant file using the attachment menu.

"""

    # Add mode-specific instructions (PR-6)
    if request.mode.startswith("agent"):
        base_prompt += """You are in AGENT MODE. You can propose code changes.

When you want to modify code, respond with:
1. A natural language explanation of what you'll do
2. An "actions" array with proposed edits

Action format:
{
  "type": "replaceFile",
  "filePath": "relative/path/from/workspace",
  "description": "Short human-friendly summary",
  "newContent": "Full updated file contents"
}

RULES:
- Always explain what you're doing in natural language first
- Keep changes minimal and safe
- Never perform destructive actions without user approval
- Only modify files that were attached or explicitly mentioned
"""

    return base_prompt.strip()


def _build_files_context(attachments: List[Attachment]) -> str:
    """Build formatted file context from attachments (PR-5)"""

    context_parts = ["Here are the attached files from the VS Code workspace:\n"]

    for idx, att in enumerate(attachments[:5], 1):  # Limit to 5 files
        language = att.language or "unknown"
        content = att.content[:8000]  # Token limit guard

        context_parts.append(
            f"""
--- File {idx}: {att.path} ({language}) ---
{content}
---
"""
        )

    return "\n".join(context_parts)


async def _call_llm(
    messages: List[Dict[str, str]], model: str, mode: str
) -> tuple[str, Optional[List[AgentAction]]]:
    """
    Call LLM and parse response

    TODO: Replace this mock with actual OpenAI/Anthropic/etc. call
    """

    # MOCK IMPLEMENTATION - Replace with actual LLM call
    # Example with OpenAI:
    # from openai import AsyncOpenAI
    # client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    # response = await client.chat.completions.create(
    #     model=model,
    #     messages=messages,
    # )
    # assistant_text = response.choices[0].message.content

    # For now, generate a mock response based on context
    user_message = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    has_attachments = any(
        "attached files" in m["content"].lower()
        for m in messages
        if m["role"] == "system"
    )

    # Mock response logic
    if has_attachments:
        if "debug" in user_message.lower() or "bug" in user_message.lower():
            reply = """I can see the attached file. Let me analyze it for potential issues.

Looking at the code, I notice a few things that could be improved:

1. **Missing error handling** - The function doesn't catch potential exceptions
2. **Type safety** - Some parameters lack proper type annotations
3. **Edge cases** - No validation for empty inputs

Would you like me to propose fixes for these issues?"""

            # In agent mode, propose an action
            actions = None
            if mode.startswith("agent"):
                actions = [
                    AgentAction(
                        type="replaceFile",
                        filePath="example.ts",  # Would extract from attachment
                        description="Add error handling and type safety improvements",
                        newContent="// Mock improved code\n// In production, this would be the actual fixed code",
                    )
                ]
        else:
            reply = """I can see your attached file. It looks like you're working on [description based on file content].

What specific aspect would you like me to help with?
- Code review and suggestions
- Debugging specific behavior
- Refactoring for better structure
- Adding tests"""
            actions = None
    else:
        reply = """Hello! I'm **NAVI**, your autonomous engineering assistant.

I can help you with code-related tasks, but I need to see your code first.

Please use the **📎 attachment button** to attach:
- **Selection** - specific code you've highlighted
- **Current File** - the entire file you're viewing
- **Pick File...** - any file from your workspace

Once you attach a file, I can provide concrete help with debugging, refactoring, reviews, and more!"""
        actions = None

    return reply, actions


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "navi", "version": "0.1.0"}
