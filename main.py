"""
Autonomous Engineering Intelligence Platform - Legacy Demo Application.

This is a legacy demo application for showcasing basic AI capabilities.
For production use, please use the modern backend at backend.api.main.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv

# Load environment variables FIRST, before any other imports
load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from typing_extensions import Literal, TypedDict  # noqa: E402

# Local imports
from backend.api.routers.agent_planning import (  # noqa: E402
    router as agent_planning_router,
)
from backend.api.routers.ai_codegen import (  # noqa: E402
    router as ai_codegen_router,
)
from backend.api.routers.ai_feedback import (  # noqa: E402
    router as ai_feedback_router,
)
from backend.api.routers.autonomous_coding import (  # noqa: E402
    router as autonomous_coding_router,
)
from backend.api.routers.jira_integration import (  # noqa: E402
    router as jira_integration_router,
)
from backend.api.routers.oauth_device import (  # noqa: E402
    router as oauth_device_router,
)
from backend.api.routers.connectors import (  # noqa: E402
    router as connectors_router,
)
from backend.api.navi_search import (  # noqa: E402
    router as navi_search_router,
)
from backend.api.navi_brief import (  # noqa: E402
    router as navi_brief_router,
)
from backend.api.navi import (  # noqa: E402
    router as navi_router,
)
from backend.api.navi_analyze import (  # noqa: E402
    router as navi_analyze_router,
)
from backend.api.org_sync import (  # noqa: E402
    router as org_sync_router,
)

# Webhook routers
from backend.api.routers.jira_webhook import (  # noqa: E402
    router as jira_webhook_router,
)
from backend.api.routers.github_webhook import (  # noqa: E402
    router as github_webhook_router,
)
from backend.api.routers.slack_webhook import (  # noqa: E402
    router as slack_webhook_router,
)
from backend.api.routers.teams_webhook import (  # noqa: E402
    router as teams_webhook_router,
)

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FallbackChatCompletionMessageParam(TypedDict, total=False):
    """
    Fallback type for ChatCompletionMessageParam when OpenAI unavailable.

    This mirrors OpenAI's actual ChatCompletionMessageParam structure.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Any], None]
    name: str
    tool_calls: List[Any]
    tool_call_id: str
    function_call: Any


# Import OpenAI for real AI capabilities
try:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    OPENAI_AVAILABLE = True
    logger.info("✅ OpenAI GPT-4 client initialized successfully")
except (ImportError, ValueError, TypeError) as e:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI client failed to initialize: %s", e)
    # Use the fallback type when OpenAI is not available
    ChatCompletionMessageParam = FallbackChatCompletionMessageParam


app = FastAPI(
    title="Autonomous Engineering Intelligence Platform",
    description="AI-powered digital coworker for engineering teams",
    version="2.0.0",
)

# Include the autonomous coding router with concierge endpoints
app.include_router(autonomous_coding_router, prefix="/api")
# OAuth router intentionally doesn't use a prefix - it defines its own
# '/oauth' prefix internally. This design keeps OAuth endpoints at the root
# level (e.g., /oauth/device/start) rather than nesting them under /api
# (e.g., /api/oauth/device/start) for better OAuth standards compatibility
app.include_router(oauth_device_router)
app.include_router(connectors_router)
app.include_router(jira_integration_router, prefix="/api")
app.include_router(agent_planning_router, prefix="/api")
app.include_router(ai_codegen_router, prefix="/api")
app.include_router(ai_feedback_router, prefix="/api")
app.include_router(navi_router)  # STEP K: NAVI chat with agent orchestrator
app.include_router(navi_analyze_router)  # Phase 4.2: NAVI analyze problems with task grounding
app.include_router(navi_search_router)  # Step 3: NAVI RAG Search
app.include_router(navi_brief_router)  # Step 4: NAVI Task Brief (org-aware context)
app.include_router(
    org_sync_router
)  # Step 3+4: Org memory sync (Jira/Confluence/Slack/Teams/Zoom)

# Webhook routers for external integrations
app.include_router(jira_webhook_router)  # Jira webhook ingestion
app.include_router(github_webhook_router)  # GitHub webhook ingestion
app.include_router(slack_webhook_router)  # Slack webhook ingestion
app.include_router(teams_webhook_router)  # Teams webhook ingestion

# CORS middleware - Allow VS Code webviews and other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins including vscode-webview://
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^(https?://.*|vscode-webview://.*|file://.*)",
)


class QuestionRequest(BaseModel):
    """Request model for AI question answering."""

    question: str
    context: Optional[Dict[str, Any]] = None


class CodeAnalysisRequest(BaseModel):
    """Request model for AI code analysis."""

    code: str
    language: str = "python"
    analysis_type: str = "general"


class TeamMember(BaseModel):
    """Model representing a team member."""

    id: str
    name: str
    role: str
    skills: List[str]


def get_ai_response(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Get response from GPT-4."""
    if not OPENAI_AVAILABLE:
        return (
            "AI service is not available. Please check your OpenAI API key "
            "configuration."
        )

    try:
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="gpt-4", messages=messages, max_tokens=1000, temperature=0.7
        )

        return response.choices[0].message.content or "No response generated"
    except (ImportError, ValueError, TypeError, AttributeError) as e:
        logger.error("OpenAI API error: %s", e)
        return "Error generating AI response. Please try again later."


@app.get("/")
async def root():
    """Welcome endpoint."""
    return {
        "message": "🤖 Autonomous Engineering Intelligence Platform",
        "version": "2.0.0",
        "ai_powered": True,
        "features": [
            "GPT-4 Question Answering",
            "Intelligent Code Analysis",
            "Team Analytics",
            "Real-time Collaboration",
        ],
        "endpoints": {
            "health": "/health",
            "ask": "/api/ask",
            "analyze_code": "/api/analyze-code",
            "team_analytics": "/api/team-analytics",
            "documentation": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    """Health check with AI status."""
    api_key_configured = bool(os.getenv("OPENAI_API_KEY"))

    # Test OpenAI connection
    openai_status = False
    if OPENAI_AVAILABLE and api_key_configured:
        try:
            # Simple test call
            client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
            )
            openai_status = True
        except (ImportError, ValueError, TypeError, AttributeError) as e:
            logger.warning("OpenAI connection test failed: %s", e)

    return {
        "status": "healthy",
        "service": "Autonomous Engineering Intelligence Platform",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "ai_model": "GPT-4",
        "api_key_configured": api_key_configured,
        "components": {
            "fastapi": True,
            "openai_gpt4": openai_status,
            "database": True,
            "vector_store": True,
        },
    }


@app.post("/api/ask")
async def ask_question(request: QuestionRequest):
    """AI-powered question answering with GPT-4."""
    try:
        question = request.question
        context = request.context or {}

        # Create enhanced system prompt
        system_prompt = (
            "You are an expert AI engineering assistant with deep knowledge "
            "in:\n"
            "- Software architecture and design patterns\n"
            "- Programming languages and frameworks\n"
            "- DevOps and cloud technologies\n"
            "- Best practices and code quality\n"
            "- System design and scalability\n"
            "- Team collaboration and productivity\n\n"
            "Provide detailed, practical answers with examples when "
            "appropriate.\n"
            "Focus on actionable insights and industry best practices."
        )

        # Enhance the question with context
        context_str = (
            json.dumps(context, indent=2)
            if context
            else "No additional context provided"
        )
        enhanced_prompt = (
            f"Question: {question}\n\n"
            f"Context: {context_str}\n\n"
            "Please provide a comprehensive answer that includes:\n"
            "1. Core concept explanation\n"
            "2. Practical examples or code samples if relevant\n"
            "3. Best practices and recommendations\n"
            "4. Common pitfalls to avoid"
        )

        # Get AI response
        ai_answer = get_ai_response(enhanced_prompt, system_prompt)

        return {
            "question": question,
            "answer": ai_answer,
            "model": "GPT-4",
            "confidence": 0.95,
            "context": context,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error("Error in ask_question: %s", e)
        raise HTTPException(
            status_code=500, detail="Error processing question. Please try again later."
        )


@app.post("/api/analyze-code")
async def analyze_code(request: CodeAnalysisRequest):
    """AI-powered code analysis with GPT-4."""
    try:
        code = request.code
        language = request.language
        analysis_type = request.analysis_type

        # Create system prompt for code analysis
        system_prompt = (
            f"You are an expert code reviewer and software architect.\n"
            f"Analyze the provided {language} code and provide:\n"
            "1. Code quality assessment (1-10 scale)\n"
            "2. Complexity analysis\n"
            "3. Maintainability score\n"
            "4. Specific issues and improvements\n"
            "5. Best practice recommendations\n\n"
            "Return your analysis in JSON format with these fields:\n"
            "- complexity_score (1-10)\n"
            "- maintainability_score (1-10)\n"
            "- quality_score (1-10)\n"
            "- issues (array of strings)\n"
            "- suggestions (array of strings)\n"
            "- summary (string)"
        )

        # Create analysis prompt
        analysis_prompt = (
            f"Please analyze this {language} code with focus on "
            f"{analysis_type}:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Provide a detailed analysis following the JSON format specified."
        )

        # Get AI analysis
        ai_response = get_ai_response(analysis_prompt, system_prompt)

        # Try to parse JSON response
        try:
            # Extract JSON from response if it's wrapped in markdown
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            else:
                json_str = ai_response

            analysis_result = json.loads(json_str)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback if JSON parsing fails
            analysis_result = {
                "complexity_score": 7,
                "maintainability_score": 8,
                "quality_score": 7,
                "issues": ["Unable to parse detailed analysis"],
                "suggestions": ["Review code structure and add comments"],
                "summary": (
                    ai_response[:200] + "..." if len(ai_response) > 200 else ai_response
                ),
            }

        return {
            "language": language,
            "analysis_type": analysis_type,
            "ai_model": "GPT-4",
            "timestamp": datetime.now().isoformat(),
            **analysis_result,
        }

    except Exception as e:
        logger.error("Error in analyze_code: %s", e)
        raise HTTPException(
            status_code=500, detail="Error analyzing code. Please try again later."
        )


@app.get("/api/team-analytics")
async def get_team_analytics():
    """Enhanced team analytics with AI insights."""
    try:
        # Simulate knowledge base stats
        knowledge_base = {
            "total_documents": 15,
            "vector_count": 1250,
            "last_updated": datetime.now().isoformat(),
        }

        # Get AI insights about team performance
        if OPENAI_AVAILABLE:
            insights_prompt = (
                "Based on typical software engineering team metrics, "
                "provide insights about:\n"
                "1. Team productivity trends\n"
                "2. Code quality patterns\n"
                "3. Knowledge sharing effectiveness\n"
                "4. Recommendations for improvement\n\n"
                "Return insights in JSON format with:\n"
                "- productivity_score (1-10)\n"
                "- quality_score (1-10)\n"
                "- collaboration_score (1-10)\n"
                "- recommendations (array)"
            )

            ai_insights_response = get_ai_response(insights_prompt)

            try:
                if "```json" in ai_insights_response:
                    json_start = ai_insights_response.find("```json") + 7
                    json_end = ai_insights_response.find("```", json_start)
                    json_str = ai_insights_response[json_start:json_end].strip()
                else:
                    json_str = ai_insights_response

                ai_insights = json.loads(json_str)
                ai_insights["ai_model"] = "GPT-4"
                ai_insights["response_quality"] = 0.92
                ai_insights["platform_effectiveness"] = "High"
            except (json.JSONDecodeError, ValueError, KeyError):
                ai_insights = {
                    "productivity_score": 8,
                    "quality_score": 7,
                    "collaboration_score": 9,
                    "recommendations": [
                        "Increase code review coverage",
                        "Implement automated testing",
                    ],
                    "ai_model": "GPT-4",
                    "response_quality": 0.85,
                    "platform_effectiveness": "Medium",
                }
        else:
            ai_insights = {
                "message": "AI insights unavailable - OpenAI API key required",
                "platform_effectiveness": "Limited",
            }

        return {
            "knowledge_base": knowledge_base,
            "ai_insights": ai_insights,
            "platform_status": "operational",
            "last_analysis": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error("Error in team_analytics: %s", e)
        raise HTTPException(
            status_code=500, detail="Error getting analytics. Please try again later."
        )


@app.get("/api/features")
async def get_features():
    """List available platform features."""
    return {
        "ai_capabilities": {
            "question_answering": True,
            "code_analysis": True,
            "team_insights": True,
            "model": "GPT-4" if OPENAI_AVAILABLE else "Simulated",
        },
        "integrations": {
            "github": "Available",
            "jira": "Available",
            "slack": "Planned",
            "ide_plugins": "Available",
        },
        "analytics": {
            "team_performance": True,
            "code_quality": True,
            "knowledge_base": True,
            "real_time": True,
        },
    }


@app.get("/api/me")
async def get_me():
    """Get current user information."""
    return {
        "email": "demo@aep.dev",
        "name": "Demo User",
        "sub": "demo-user-id",
        "org": "org-dev",
        "roles": ["user", "developer"],
    }


@app.get("/api/integrations/jira/my-issues")
async def get_my_jira_issues():
    """Get current user's Jira issues."""
    return [
        {
            "id": "AEP-123",
            "key": "AEP-123",
            "summary": "Improve VS Code extension UI",
            "status": "In Progress",
            "assignee": "demo@aep.dev",
            "priority": "High",
            "type": "Task",
        },
        {
            "id": "AEP-124",
            "key": "AEP-124",
            "summary": "Add OAuth authentication flow",
            "status": "Done",
            "assignee": "demo@aep.dev",
            "priority": "Medium",
            "type": "Story",
        },
    ]


@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """Chat endpoint for extension."""
    message = request.get("message", "")
    chat_type = request.get("type", "question")

    # Simulate a chat response
    return {
        "response": (
            f"I received your {chat_type}: '{message}'. "
            "This is a demo response from the AEP backend."
        ),
        "type": "success",
        "timestamp": "2025-11-09T23:40:00Z",
    }


@app.post("/api/agent/propose")
async def propose_plan(request: dict):
    """Propose a plan for a given issue."""
    issue_key = request.get("issue_key", "")

    # Simulate a plan proposal
    return [
        {
            "id": 1,
            "title": "Analyze Current UI State",
            "description": (
                f"Review the current implementation of {issue_key} "
                "to understand the existing UI components and "
                "identify areas for improvement."
            ),
            "type": "analysis",
            "estimated_time": "30 minutes",
            "status": "pending",
        },
        {
            "id": 2,
            "title": "Design New UI Components",
            "description": (
                "Create modern, professional UI components using "
                "CSS Grid and Flexbox with proper accessibility "
                "features."
            ),
            "type": "design",
            "estimated_time": "2 hours",
            "status": "pending",
        },
        {
            "id": 3,
            "title": "Implement Professional Styling",
            "description": (
                "Apply the new design system with consistent "
                "spacing, typography, and color scheme."
            ),
            "type": "implementation",
            "estimated_time": "3 hours",
            "status": "pending",
        },
        {
            "id": 4,
            "title": "Test and Validate",
            "description": (
                "Test the new UI across different scenarios and "
                "validate accessibility compliance."
            ),
            "type": "testing",
            "estimated_time": "1 hour",
            "status": "pending",
        },
    ]


if __name__ == "__main__":
    print("⚠️  DEPRECATION WARNING ⚠️")
    print("This main.py is a legacy demo application.")
    print("Please use the production backend instead:")
    print("")
    print("  python -m backend.api.main")
    print("")
    print("Or use the modern startup commands:")
    print("  make dev    # Start with hot reload")
    print("  make up     # Start with Docker services")
    print("")
    print("Legacy demo will start in 3 seconds...")

    time.sleep(3)

    print("🚀 Starting Legacy Demo Application...")
    print("🤖 AI Model: GPT-4")
    API_STATUS = "✅ Configured" if os.getenv("OPENAI_API_KEY") else "❌ Missing"
    print("🔑 API Key Status:", API_STATUS)
    print("🌐 Server: http://localhost:8000")
    print("📖 Docs: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
