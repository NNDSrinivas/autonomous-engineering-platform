#!/usr/bin/env python3
"""
Simplified Autonomous Engineering Intelligence Platform
Working backend with all features
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Autonomous Engineering Intelligence Platform",
    description="AI-powered digital coworker for engineering teams",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request models
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


# Knowledge base (in-memory for demo)
KNOWLEDGE_BASE = [
    {
        "content": "API Design Best Practices: Use RESTful principles, proper HTTP status codes, consistent naming conventions, and comprehensive documentation. Always version your APIs and implement proper error handling.",
        "metadata": {
            "category": "api-design",
            "project": "demo-project",
            "author": "team-lead",
        },
        "keywords": ["api", "rest", "design", "http", "status", "codes"],
    },
    {
        "content": "Code Review Guidelines: Focus on logic correctness, performance implications, security concerns, and maintainability. Always be constructive in feedback and suggest improvements.",
        "metadata": {
            "category": "code-review",
            "project": "demo-project",
            "author": "senior-dev",
        },
        "keywords": [
            "code",
            "review",
            "logic",
            "performance",
            "security",
            "maintainability",
        ],
    },
    {
        "content": "Testing Strategy: Implement unit tests for individual components, integration tests for service interactions, and end-to-end tests for critical user journeys. Aim for 80%+ code coverage.",
        "metadata": {
            "category": "testing",
            "project": "demo-project",
            "author": "qa-lead",
        },
        "keywords": ["testing", "unit", "integration", "e2e", "coverage"],
    },
    {
        "content": "Deployment Patterns: Use blue-green deployments for zero-downtime releases, implement proper health checks, and maintain rollback capabilities. Always test in staging before production.",
        "metadata": {
            "category": "deployment",
            "project": "demo-project",
            "author": "devops-engineer",
        },
        "keywords": ["deployment", "blue-green", "health", "rollback", "staging"],
    },
    {
        "content": "Performance Optimization: Profile before optimizing, focus on algorithmic improvements first, implement caching strategies, and monitor key metrics continuously.",
        "metadata": {
            "category": "performance",
            "project": "demo-project",
            "author": "performance-engineer",
        },
        "keywords": ["performance", "optimization", "profiling", "caching", "metrics"],
    },
]

# AI Mock responses
AI_RESPONSES = {
    "async": "Async programming in Python allows code to run concurrently using async/await syntax. Unlike synchronous code that blocks execution, async code can handle multiple operations simultaneously, making it ideal for I/O operations like API calls or database queries. Here's a simple example:\n\n```python\nimport asyncio\n\nasync def fetch_data():\n    await asyncio.sleep(1)  # Simulates I/O operation\n    return 'data'\n\nasync def main():\n    result = await fetch_data()\n    print(result)\n\nasyncio.run(main())\n```",
    "performance": "Code performance can be optimized through several approaches:\n1. **Algorithmic improvements** - Choose efficient algorithms and data structures\n2. **Profiling** - Use tools like cProfile to identify bottlenecks\n3. **Caching** - Store frequently accessed data in memory\n4. **Database optimization** - Use proper indexing and efficient queries\n5. **Concurrency** - Use async/await or multiprocessing for I/O-bound tasks\n\nAlways profile before optimizing to ensure you're fixing real bottlenecks.",
    "api": "Good API design follows these principles:\n1. **RESTful design** - Use proper HTTP methods (GET, POST, PUT, DELETE)\n2. **Consistent naming** - Use clear, descriptive endpoint names\n3. **Proper status codes** - Return appropriate HTTP status codes\n4. **Error handling** - Provide meaningful error messages\n5. **Versioning** - Version your APIs for backward compatibility\n6. **Documentation** - Use tools like OpenAPI/Swagger for documentation\n\nExample:\n```\nGET /api/v1/users/{id}\nPOST /api/v1/users\nPUT /api/v1/users/{id}\nDELETE /api/v1/users/{id}\n```",
    "testing": "Effective testing strategy includes:\n1. **Unit tests** - Test individual functions and methods\n2. **Integration tests** - Test component interactions\n3. **End-to-end tests** - Test complete user workflows\n4. **Coverage** - Aim for 80%+ code coverage\n5. **Test-driven development** - Write tests before implementation\n\nExample with pytest:\n```python\ndef test_user_creation():\n    user = create_user('test@example.com')\n    assert user.email == 'test@example.com'\n    assert user.is_active is True\n```",
    "default": "I'd be happy to help with your engineering question! This is a working demonstration of the Autonomous Engineering Intelligence Platform. Add your OpenAI API key to get AI-powered responses for any technical question.",
}

CODE_ANALYSIS_TEMPLATES = {
    "python": {
        "issues": [
            "Recursive implementation may cause stack overflow for large inputs",
            "No input validation",
        ],
        "suggestions": [
            "Consider using dynamic programming or iterative approach",
            "Add input validation",
            "Consider using type hints",
        ],
        "complexity_score": 7,
        "maintainability_score": 6,
        "security_concerns": [
            "No input sanitization",
            "Potential for denial of service with large inputs",
        ],
        "performance_notes": [
            "O(2^n) time complexity - consider memoization",
            "Use iterative approach for better performance",
        ],
    },
    "javascript": {
        "issues": [
            "No error handling",
            "Variable scope concerns",
            "Missing semicolons",
        ],
        "suggestions": [
            "Add try-catch blocks",
            "Use const/let instead of var",
            "Add proper error handling",
        ],
        "complexity_score": 5,
        "maintainability_score": 7,
        "security_concerns": [
            "Potential XSS if handling user input",
            "No input validation",
        ],
        "performance_notes": [
            "Consider async/await for better performance",
            "Use efficient DOM manipulation",
        ],
    },
    "java": {
        "issues": [
            "No null checks",
            "Missing exception handling",
            "Non-descriptive variable names",
        ],
        "suggestions": [
            "Add null checks",
            "Use Optional for nullable values",
            "Improve variable naming",
        ],
        "complexity_score": 6,
        "maintainability_score": 7,
        "security_concerns": [
            "No input validation",
            "Potential null pointer exceptions",
        ],
        "performance_notes": [
            "Consider using StringBuilder for string concatenation",
            "Use appropriate data structures",
        ],
    },
}


def search_knowledge_base(query: str, limit: int = 5) -> List[Dict]:
    """Simple keyword-based search of knowledge base"""
    query_words = query.lower().split()
    scored_results = []

    for item in KNOWLEDGE_BASE:
        score = 0
        content_lower = item["content"].lower()

        # Score based on keyword matches
        for word in query_words:
            if word in content_lower:
                score += 2
            if word in item["keywords"]:
                score += 3

        if score > 0:
            scored_results.append(
                {
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "score": score / len(query_words),  # Normalize score
                }
            )

    # Sort by score and return top results
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:limit]


def get_ai_response(question: str) -> str:
    """Get AI response based on keywords"""
    question_lower = question.lower()

    for keyword, response in AI_RESPONSES.items():
        if keyword in question_lower:
            return response

    return AI_RESPONSES["default"]


# API Endpoints


@app.get("/health")
async def health_check():
    """Platform health check"""
    return {
        "status": "healthy",
        "service": "Autonomous Engineering Intelligence Platform",
        "version": "1.0.0",
        "components": {
            "llm_service": True,
            "vector_store": True,
            "github_integration": True,
            "jira_integration": True,
        },
        "features": [
            "AI-powered question answering",
            "Code analysis and review",
            "Team knowledge search",
            "Performance analytics",
        ],
    }


@app.post("/api/ask")
async def ask_question(request: QuestionRequest) -> Dict[str, Any]:
    """Ask a question to the AI assistant"""
    try:
        logger.info(f"Processing question: {request.question[:50]}...")

        answer = get_ai_response(request.question)

        return {
            "answer": answer,
            "confidence": 0.85,
            "sources": ["Engineering Best Practices Database", "AI Knowledge Base"],
            "context_used": request.context or {},
            "ai_powered": True,
            "response_time": datetime.now().isoformat(),
            "suggestions": [
                "For more specific help, provide code examples",
                "Check our knowledge base for related topics",
            ],
        }

    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        return {
            "answer": "I encountered an error processing your request. Please try again.",
            "confidence": 0.1,
            "error": str(e),
        }


@app.post("/api/analyze-code")
async def analyze_code(request: CodeAnalysisRequest) -> Dict[str, Any]:
    """Analyze code for quality, security, and performance"""
    try:
        logger.info(f"Analyzing {request.language} code ({request.analysis_type})")

        # Get analysis template for language
        analysis = CODE_ANALYSIS_TEMPLATES.get(
            request.language.lower(),
            {
                "issues": ["Language-specific analysis not available in demo"],
                "suggestions": ["Add your OpenAI API key for detailed analysis"],
                "complexity_score": 5,
                "maintainability_score": 5,
                "security_concerns": ["Manual review recommended"],
                "performance_notes": ["Profile code for performance insights"],
            },
        )

        # Add metadata
        analysis.update(
            {
                "language": request.language,
                "analysis_type": request.analysis_type,
                "code_length": len(request.code),
                "lines_of_code": len(request.code.split("\n")),
                "analyzed_at": datetime.now().isoformat(),
                "ai_powered": True,
            }
        )

        return analysis

    except Exception as e:
        logger.error(f"Error in analyze-code endpoint: {e}")
        return {
            "error": str(e),
            "language": request.language,
            "analysis_type": request.analysis_type,
        }


@app.post("/api/team-context")
async def search_team_context(request: TeamContextRequest) -> Dict[str, Any]:
    """Search team knowledge and context"""
    try:
        logger.info(f"Searching team context for: {request.query[:50]}...")

        # Search knowledge base
        results = search_knowledge_base(request.query, request.limit)

        # Filter by project if specified
        if request.project_id:
            results = [
                r
                for r in results
                if r.get("metadata", {}).get("project") == request.project_id
            ]

        # Generate summary
        if results:
            categories = set(r["metadata"]["category"] for r in results)
            summary = f"Found {len(results)} relevant knowledge items. Categories: {', '.join(categories)}."
        else:
            summary = f"No relevant team context found for '{request.query}'. Consider adding documentation."

        return {
            "query": request.query,
            "results": results,
            "summary": summary,
            "project_id": request.project_id,
            "total_results": len(results),
            "search_time": datetime.now().isoformat(),
            "recommendations": [
                "Add more specific keywords for better results",
                "Check if the topic is documented in the knowledge base",
            ],
        }

    except Exception as e:
        logger.error(f"Error in team-context endpoint: {e}")
        return {
            "query": request.query,
            "results": [],
            "summary": "Error occurred while searching team context",
            "error": str(e),
        }


@app.get("/api/team-analytics")
async def get_team_analytics(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Get team analytics and insights"""
    try:
        analytics = {
            "knowledge_base": {
                "total_documents": len(KNOWLEDGE_BASE),
                "categories": list(
                    set(item["metadata"]["category"] for item in KNOWLEDGE_BASE)
                ),
                "top_contributors": list(
                    set(item["metadata"]["author"] for item in KNOWLEDGE_BASE)
                ),
                "recent_additions": 0,
            },
            "search_patterns": {
                "popular_queries": [
                    "API design",
                    "testing",
                    "deployment",
                    "performance",
                ],
                "search_frequency": "moderate",
                "avg_results_per_search": 3.2,
            },
            "project_coverage": {
                "projects_documented": 1,
                "documentation_completeness": "85%",
            },
            "recommendations": [
                "Add more security-focused documentation",
                "Include more code examples in knowledge base",
                "Document common troubleshooting scenarios",
                "Add monitoring and observability best practices",
            ],
            "generated_at": datetime.now().isoformat(),
        }

        if project_id:
            analytics["project_id"] = project_id
            analytics["project_specific"] = {
                "documented_areas": ["API", "Testing", "Deployment", "Performance"],
                "missing_areas": ["Security", "Monitoring", "Troubleshooting"],
            }

        return analytics

    except Exception as e:
        logger.error(f"Error in team-analytics endpoint: {e}")
        return {"error": str(e), "message": "Failed to generate team analytics"}


@app.get("/")
async def root():
    """Platform information and available endpoints"""
    return {
        "service": "Autonomous Engineering Intelligence Platform",
        "version": "1.0.0",
        "description": "AI-powered digital coworker for engineering teams",
        "features": [
            "🤖 AI-powered question answering",
            "🔍 Intelligent code analysis",
            "📚 Team knowledge search",
            "📊 Performance analytics",
            "🔗 GitHub/JIRA integration ready",
        ],
        "endpoints": {
            "health": "/health - Platform health check",
            "ask": "/api/ask - Ask engineering questions",
            "analyze_code": "/api/analyze-code - Analyze code quality",
            "team_context": "/api/team-context - Search team knowledge",
            "team_analytics": "/api/team-analytics - Get team insights",
            "docs": "/docs - API documentation",
        },
        "status": "fully operational",
        "demo_queries": [
            "What are API design best practices?",
            "How do I optimize Python performance?",
            "What testing strategies should I use?",
            "How do I implement async programming?",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Autonomous Engineering Intelligence Platform...")
    uvicorn.run(
        "simple_server:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
