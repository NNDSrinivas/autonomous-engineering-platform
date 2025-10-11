"""
Autonomous Engineering Intelligence Platform - Core API
FastAPI application serving the main engineering intelligence endpoints
"""
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import structlog

from backend.core.config import get_settings
from backend.core.database import init_database
from backend.core.ai.llm_service import LLMService
from backend.core.memory.vector_store import VectorStore
from backend.integrations.github.service import GitHubService
from backend.integrations.jira.service import JiraService

logger = structlog.get_logger(__name__)

# Global services
llm_service: LLMService = None
vector_store: VectorStore = None
github_service: GitHubService = None
jira_service: JiraService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources"""
    settings = get_settings()
    
    # Initialize core services
    global llm_service, vector_store, github_service, jira_service
    
    logger.info("Initializing Autonomous Engineering Intelligence Platform...")
    
    # Database
    await init_database()
    
    # AI Services
    llm_service = LLMService(settings)
    vector_store = VectorStore(settings.vector_db_path)
    
    # External Integrations
    if settings.github_token:
        github_service = GitHubService(settings.github_token)
    
    if settings.jira_url and settings.jira_token:
        jira_service = JiraService(
            url=settings.jira_url,
            email=settings.jira_user,
            token=settings.jira_token
        )
    
    logger.info("Platform initialization complete!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down platform services...")
    if vector_store:
        await vector_store.close()

# Create FastAPI app
app = FastAPI(
    title="Autonomous Engineering Intelligence Platform",
    description="AI-Powered Digital Coworker for Software Engineering Teams",
    version="1.0.0",
    lifespan=lifespan
)

# Security
security = HTTPBearer()
settings = get_settings()

# CORS Configuration
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for the engineering platform"""
    return {
        "status": "healthy",
        "service": "Autonomous Engineering Intelligence Platform",
        "version": "1.0.0",
        "components": {
            "llm_service": llm_service is not None,
            "vector_store": vector_store is not None,
            "github_integration": github_service is not None,
            "jira_integration": jira_service is not None,
        }
    }

# Core engineering endpoints
@app.post("/api/ask")
async def ask_question(request: Dict[str, Any]) -> Dict[str, Any]:
    """Ask the AI engineering assistant a question with full context"""
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    question = request.get("question", "")
    context = request.get("context", {})
    
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    try:
        # Get relevant context from vector store
        if vector_store:
            relevant_docs = await vector_store.search(question, limit=5)
            context["relevant_knowledge"] = relevant_docs
        
        # Generate AI response
        response = await llm_service.generate_engineering_response(
            question=question,
            context=context
        )
        
        return {
            "answer": response.answer,
            "reasoning": response.reasoning,
            "suggested_actions": response.suggested_actions,
            "confidence": response.confidence
        }
        
    except Exception as e:
        logger.error("Error processing engineering question", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process question")

@app.post("/api/analyze-code")
async def analyze_code(request: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze code and provide engineering insights"""
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    code = request.get("code", "")
    language = request.get("language", "python")
    context = request.get("context", {})
    
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    
    try:
        analysis = await llm_service.analyze_code(
            code=code,
            language=language,
            context=context
        )
        
        return {
            "quality_score": analysis.quality_score,
            "issues": analysis.issues,
            "suggestions": analysis.suggestions,
            "complexity": analysis.complexity,
            "test_coverage_suggestions": analysis.test_suggestions
        }
        
    except Exception as e:
        logger.error("Error analyzing code", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to analyze code")

@app.get("/api/team-context")
async def get_team_context() -> Dict[str, Any]:
    """Get current team context and project status"""
    context = {}
    
    try:
        # GitHub context
        if github_service:
            github_context = await github_service.get_team_context()
            context["github"] = github_context
        
        # JIRA context
        if jira_service:
            jira_context = await jira_service.get_team_context()
            context["jira"] = jira_context
        
        # Memory context
        if vector_store:
            recent_knowledge = await vector_store.get_recent_knowledge(limit=10)
            context["recent_knowledge"] = recent_knowledge
        
        return {
            "status": "success",
            "context": context,
            "timestamp": "2025-10-11T00:00:00Z"
        }
        
    except Exception as e:
        logger.error("Error getting team context", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get team context")

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.debug
    )
