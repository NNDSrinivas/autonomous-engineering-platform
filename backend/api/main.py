from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import asyncio
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our services (with correct paths)
from backend.core.config import settings
from backend.core.ai_service import AIService
from backend.core.memory.vector_store import VectorStore
from backend.core.team_service import TeamService
from backend.integrations.github.service import GitHubService
from backend.integrations.jira.service import JiraService

# Global service instances
ai_service = None
team_service = None
github_service = None
jira_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global ai_service, team_service, github_service, jira_service
    
    try:
        logger.info("Initializing Autonomous Engineering Intelligence Platform...")
        
        # Initialize services
        ai_service = AIService()
        vector_store = VectorStore()
        team_service = TeamService(vector_store)
        github_service = GitHubService()
        jira_service = JiraService()
        
        logger.info("✅ All services initialized successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise e
    finally:
        logger.info("Shutting down services...")

# Create FastAPI app
app = FastAPI(
    title="Autonomous Engineering Intelligence Platform",
    description="AI-powered digital coworker for engineering teams",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QuestionRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None

class CodeAnalysisRequest(BaseModel):
    code: str
    language: str
    analysis_type: Optional[str] = "general"

class TeamContextRequest(BaseModel):
    query: str
    project_id: Optional[str] = None
    limit: Optional[int] = 5

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    components: Dict[str, bool]

# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Platform health check"""
    return HealthResponse(
        status="healthy",
        service="Autonomous Engineering Intelligence Platform", 
        version="1.0.0",
        components={
            "llm_service": ai_service is not None,
            "vector_store": team_service is not None,
            "github_integration": github_service is not None,
            "jira_integration": jira_service is not None
        }
    )

@app.post("/api/ask")
async def ask_question(request: QuestionRequest) -> Dict[str, Any]:
    """Ask a question to the AI assistant"""
    try:
        if not ai_service:
            raise HTTPException(status_code=503, detail="AI service not available")
        
        result = await ai_service.ask_question(request.question, request.context)
        return result
        
    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        return {
            "answer": "I encountered an error processing your request. Please try again.",
            "reasoning": "Technical error occurred",
            "suggested_actions": [
                "Try rephrasing your question",
                "Check system status"
            ],
            "confidence": 0.1
        }

@app.post("/api/analyze-code")
async def analyze_code(request: CodeAnalysisRequest) -> Dict[str, Any]:
    """Analyze code for quality, security, and performance"""
    try:
        if not ai_service:
            raise HTTPException(status_code=503, detail="AI service not available")
        
        result = await ai_service.analyze_code(
            request.code, 
            request.language, 
            request.analysis_type
        )
        return result
        
    except Exception as e:
        logger.error(f"Error in analyze-code endpoint: {e}")
        return {
            "quality_score": 0.5,
            "issues": [
                {
                    "type": "analysis_error",
                    "message": "Could not analyze code"
                }
            ],
            "suggestions": [
                "Manual code review recommended"
            ],
            "complexity": {
                "cyclomatic": "unknown"
            },
            "test_coverage_suggestions": [
                "Add basic unit tests"
            ]
        }

@app.post("/api/team-context")
async def search_team_context(request: TeamContextRequest) -> Dict[str, Any]:
    """Search team knowledge and context"""
    try:
        if not team_service:
            raise HTTPException(status_code=503, detail="Team service not available")
        
        result = await team_service.search_team_context(
            request.query,
            request.project_id,
            request.limit
        )
        return result
        
    except Exception as e:
        logger.error(f"Error in team-context endpoint: {e}")
        return {
            "query": request.query,
            "results": [],
            "summary": "Error occurred while searching team context",
            "error": str(e),
            "project_id": request.project_id
        }

@app.get("/api/team-analytics")
async def get_team_analytics(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Get team analytics and insights"""
    try:
        if not team_service:
            raise HTTPException(status_code=503, detail="Team service not available")
        
        result = await team_service.get_team_analytics(project_id)
        return result
        
    except Exception as e:
        logger.error(f"Error in team-analytics endpoint: {e}")
        return {
            "error": str(e),
            "message": "Failed to generate team analytics"
        }

@app.get("/")
async def root():
    """Platform information"""
    return {
        "service": "Autonomous Engineering Intelligence Platform",
        "version": "1.0.0",
        "description": "AI-powered digital coworker for engineering teams",
        "endpoints": {
            "health": "/health",
            "ask": "/api/ask",
            "analyze_code": "/api/analyze-code", 
            "team_context": "/api/team-context",
            "team_analytics": "/api/team-analytics",
            "docs": "/docs"
        },
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
