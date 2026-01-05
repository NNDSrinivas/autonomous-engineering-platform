"""
Enhanced NAVI Chat API - Ported from code-companion Supabase functions
Provides advanced conversational AI with multi-LLM support and context awareness
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import os
from datetime import datetime
import logging

from ...api.deps import get_current_user
from ...models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/navi-chat-enhanced", tags=["navi-chat-enhanced"])

# Model mapping for different providers
MODEL_MAPPING = {
    # OpenAI models
    "openai/gpt-4": "gpt-4",
    "openai/gpt-4-turbo": "gpt-4-turbo-preview",
    "openai/gpt-3.5-turbo": "gpt-3.5-turbo",
    # Anthropic models
    "anthropic/claude-3": "claude-3-sonnet-20240229",
    "anthropic/claude-3-haiku": "claude-3-haiku-20240307",
    # Auto selection (defaults to GPT-4)
    "auto/recommended": "gpt-4",
    # Fallback
    "lovable/gemini-flash": "gpt-4",
    "lovable/gemini-pro": "gpt-4",
}

NAVI_SYSTEM_PROMPT = """You are NAVI, an Autonomous Engineering Intelligence (AEI) assistant. When users greet you, introduce yourself as "Hello! I'm NAVI, your Autonomous Engineering Intelligence."

Your capabilities include:
1. Understanding engineering context from Jira tasks, Slack/Teams conversations, Confluence docs, GitHub PRs, and meeting notes
2. Providing intelligent code suggestions and implementations
3. Explaining complex engineering concepts clearly
4. Helping debug issues and suggesting fixes
5. Generating code based on requirements
6. Always asking for approval before making any changes

You have access to organizational memory and can retrieve relevant context from past conversations, documentation, and team decisions. Always provide helpful, accurate, and contextual responses while maintaining a professional yet friendly tone.

When working with code, always explain your reasoning and ask for confirmation before making changes."""


class ChatRequest(BaseModel):
    message: str
    model: str = "auto/recommended"
    provider: str = "auto"
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    use_memory: bool = True


class ChatResponse(BaseModel):
    response: str
    model_used: str
    conversation_id: str
    timestamp: str
    context_used: Optional[Dict[str, Any]] = None


@router.post("/chat", response_model=ChatResponse)
async def enhanced_chat(
    request: ChatRequest, current_user: User = Depends(get_current_user)
):
    """
    Enhanced chat endpoint with multi-LLM support and memory integration
    """
    try:
        # Get the actual model to use
        model_to_use = MODEL_MAPPING.get(request.model, "gpt-4")

        # Prepare the conversation context
        messages = [{"role": "system", "content": NAVI_SYSTEM_PROMPT}]

        # Add user context if provided
        if request.context:
            context_msg = f"Context: {request.context}"
            messages.append({"role": "system", "content": context_msg})

        # Add the user message
        messages.append({"role": "user", "content": request.message})

        # Call OpenAI API (can be extended for other providers)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_to_use,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )

        if response.status_code != 200:
            logger.error(f"OpenAI API error: {response.text}")
            raise HTTPException(status_code=500, detail="AI service unavailable")

        result = response.json()
        ai_response = result["choices"][0]["message"]["content"]

        # Generate conversation ID if not provided
        conversation_id = (
            request.conversation_id
            or f"conv_{current_user.id}_{int(datetime.now().timestamp())}"
        )

        return ChatResponse(
            response=ai_response,
            model_used=model_to_use,
            conversation_id=conversation_id,
            timestamp=datetime.now().isoformat(),
            context_used=request.context,
        )

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10
    memory_types: Optional[List[str]] = None


@router.post("/memory-search")
async def search_memory(
    request: MemorySearchRequest, current_user: User = Depends(get_current_user)
):
    """
    Search organizational memory for relevant context
    """
    try:
        # This would integrate with the existing memory system
        # For now, return a placeholder response
        return {
            "results": [],
            "query": request.query,
            "total_results": 0,
            "message": "Memory search integration in progress",
        }
    except Exception as e:
        logger.error(f"Memory search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.get("/models")
async def get_available_models():
    """
    Get list of available AI models
    """
    return {
        "providers": [
            {
                "id": "auto",
                "name": "Auto",
                "models": [
                    {
                        "id": "auto/recommended",
                        "name": "Auto (Recommended)",
                        "description": "Automatically selects the best model",
                    }
                ],
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "models": [
                    {
                        "id": "openai/gpt-4",
                        "name": "GPT-4",
                        "description": "Most capable model",
                    },
                    {
                        "id": "openai/gpt-4-turbo",
                        "name": "GPT-4 Turbo",
                        "description": "Faster GPT-4",
                    },
                    {
                        "id": "openai/gpt-3.5-turbo",
                        "name": "GPT-3.5 Turbo",
                        "description": "Fast and efficient",
                    },
                ],
            },
            {
                "id": "anthropic",
                "name": "Anthropic",
                "models": [
                    {
                        "id": "anthropic/claude-3",
                        "name": "Claude 3 Sonnet",
                        "description": "Balanced performance",
                    },
                    {
                        "id": "anthropic/claude-3-haiku",
                        "name": "Claude 3 Haiku",
                        "description": "Fastest Claude model",
                    },
                ],
            },
        ]
    }
