"""
NAVI Multi-Repository Intelligence API Endpoints

Exposes Phase 4.8 multi-repository intelligence capabilities through REST API
endpoints that integrate with NAVI's core reasoning engine.

These endpoints enable:
- Cross-repository impact analysis
- System health monitoring 
- Coordinated multi-repository changes
- Principal Engineer-level architectural decisions

This transforms NAVI from repository-aware to organization-system-aware.
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from ...agent.multirepo_integration import (
    get_multi_repo_integration,
    enhance_navi_intent_with_system_context,
    analyze_navi_change_impact,
    get_navi_architectural_guidance,
    get_navi_system_health
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi/multirepo", tags=["navi-multirepo"])

# ============================================================================
# Request/Response Models
# ============================================================================

class ImpactAnalysisRequest(BaseModel):
    """Request for cross-repository impact analysis"""
    change_description: str = Field(..., description="Description of the proposed change")
    workspace_root: str = Field(..., description="Root path of the workspace")
    changed_files: Optional[List[str]] = Field(None, description="List of files being changed")
    change_type: Optional[str] = Field("code_change", description="Type of change (code_change, api_change, etc.)")

class ImpactAnalysisResponse(BaseModel):
    """Response for impact analysis"""
    analysis_available: bool
    blast_radius: Optional[int] = None
    affected_repositories: Optional[List[str]] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    critical_systems: Optional[List[str]] = None
    estimated_effort_hours: Optional[int] = None
    recommended_approach: Optional[str] = None
    rollback_strategy: Optional[str] = None
    testing_recommendations: Optional[List[str]] = None
    requires_coordination: Optional[bool] = None
    confidence: Optional[str] = None
    error: Optional[str] = None

class ArchitecturalGuidanceRequest(BaseModel):
    """Request for architectural guidance"""
    problem_description: str = Field(..., description="Description of the architectural problem")
    workspace_root: str = Field(..., description="Root path of the workspace")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class ArchitecturalGuidanceResponse(BaseModel):
    """Response for architectural guidance"""
    guidance_available: bool
    decision_id: Optional[str] = None
    title: Optional[str] = None
    recommended_action: Optional[str] = None
    technical_rationale: Optional[str] = None
    business_justification: Optional[str] = None
    confidence_level: Optional[str] = None
    risk_assessment: Optional[str] = None
    implementation_plan: Optional[List[str]] = None
    estimated_effort_weeks: Optional[int] = None
    alternatives_considered: Optional[List[str]] = None
    trade_offs: Optional[Dict[str, str]] = None
    principal_engineer_recommendation: Optional[bool] = None
    error: Optional[str] = None

class SystemHealthResponse(BaseModel):
    """Response for system health insights"""
    insights_available: bool
    overall_health_score: Optional[float] = None
    system_status: Optional[str] = None
    repository_summary: Optional[Dict[str, int]] = None
    dependency_summary: Optional[Dict[str, int]] = None
    technology_stack: Optional[Dict[str, Any]] = None
    immediate_actions: Optional[List[str]] = None
    strategic_improvements: Optional[List[str]] = None
    single_points_of_failure: Optional[List[str]] = None
    generated_at: Optional[str] = None
    recommendations_count: Optional[int] = None
    error: Optional[str] = None

class CoordinatedChangeRequest(BaseModel):
    """Request for coordinated multi-repository change"""
    title: str = Field(..., description="Title of the coordinated change")
    description: str = Field(..., description="Description of the change")
    workspace_root: str = Field(..., description="Root path of the workspace")
    change_requests: List[Dict[str, Any]] = Field(..., description="Individual repository changes")
    created_by: Optional[str] = Field("navi", description="Creator of the change")

class EnhanceIntentRequest(BaseModel):
    """Request to enhance intent with system context"""
    intent: Dict[str, Any] = Field(..., description="NAVI intent to enhance")
    workspace_root: str = Field(..., description="Root path of the workspace")

# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/analyze-impact", response_model=ImpactAnalysisResponse)
async def analyze_cross_repo_impact(request: ImpactAnalysisRequest):
    """
    Analyze the cross-repository impact of a proposed change.
    
    This endpoint enables NAVI to understand system-wide consequences
    before making changes, preventing cascading failures.
    """
    try:
        logger.info(f"Analyzing cross-repo impact: {request.change_description[:100]}...")
        
        impact_analysis = await analyze_navi_change_impact(
            change_description=request.change_description,
            workspace_root=request.workspace_root,
            changed_files=request.changed_files or [],
            change_type=request.change_type or "code_change"
        )
        
        return ImpactAnalysisResponse(**impact_analysis)
        
    except Exception as e:
        logger.error(f"Impact analysis failed: {e}")
        return ImpactAnalysisResponse(
            analysis_available=False,
            error=str(e)
        )

@router.post("/architectural-guidance", response_model=ArchitecturalGuidanceResponse)
async def get_architectural_guidance(request: ArchitecturalGuidanceRequest):
    """
    Get Principal Engineer-level architectural guidance for complex problems.
    
    This endpoint elevates NAVI's reasoning to system architecture level,
    providing strategic technical leadership.
    """
    try:
        logger.info(f"Requesting architectural guidance: {request.problem_description[:100]}...")
        
        guidance = await get_navi_architectural_guidance(
            problem_description=request.problem_description,
            workspace_root=request.workspace_root,
            context=request.context or {}
        )
        
        return ArchitecturalGuidanceResponse(**guidance)
        
    except Exception as e:
        logger.error(f"Architectural guidance failed: {e}")
        return ArchitecturalGuidanceResponse(
            guidance_available=False,
            error=str(e)
        )

@router.get("/system-health/{workspace_root:path}", response_model=SystemHealthResponse)
async def get_system_health(workspace_root: str):
    """
    Get comprehensive system health insights across all repositories.
    
    This endpoint provides NAVI with organization-wide visibility
    for proactive engineering decisions.
    """
    try:
        logger.info(f"Analyzing system health for workspace: {workspace_root}")
        
        health_insights = await get_navi_system_health(workspace_root)
        
        return SystemHealthResponse(**health_insights)
        
    except Exception as e:
        logger.error(f"System health analysis failed: {e}")
        return SystemHealthResponse(
            insights_available=False,
            error=str(e)
        )

@router.post("/enhance-intent")
async def enhance_intent_with_system_context(request: EnhanceIntentRequest):
    """
    Enhance NAVI intent classification with system-wide context.
    
    This endpoint adds organization-level intelligence to every NAVI operation,
    transforming it from repository-aware to system-aware.
    """
    try:
        logger.info("Enhancing intent with system context")
        
        enhanced_intent = await enhance_navi_intent_with_system_context(
            intent=request.intent,
            workspace_root=request.workspace_root
        )
        
        return {
            "success": True,
            "enhanced_intent": enhanced_intent,
            "system_aware": True
        }
        
    except Exception as e:
        logger.error(f"Intent enhancement failed: {e}")
        return {
            "success": False,
            "enhanced_intent": request.intent,
            "system_aware": False,
            "error": str(e)
        }

@router.post("/coordinate-change")
async def coordinate_multi_repo_change(request: CoordinatedChangeRequest, background_tasks: BackgroundTasks):
    """
    Coordinate atomic changes across multiple repositories.
    
    This endpoint enables NAVI to orchestrate system-wide changes
    with proper dependency ordering and rollback capabilities.
    """
    try:
        logger.info(f"Coordinating multi-repo change: {request.title}")
        
        integration = get_multi_repo_integration(request.workspace_root)
        
        # Create coordinated change plan
        change_plan = await integration.plan_coordinated_change(
            title=request.title,
            description=request.description,
            impact_analysis={"affected_repositories": [cr.get("repo_name") for cr in request.change_requests]}
        )
        
        if not change_plan.get("plan_available", False):
            raise HTTPException(status_code=400, detail=change_plan.get("reason", "Failed to create plan"))
        
        return {
            "success": True,
            "change_id": change_plan["change_id"],
            "affected_repositories": change_plan["affected_repositories"],
            "deployment_order": change_plan["deployment_order"],
            "requires_approval": change_plan["requires_approval"],
            "estimated_duration": change_plan["estimated_duration"],
            "coordination_complexity": change_plan["coordination_complexity"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change coordination failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integration-status/{workspace_root:path}")
async def get_integration_status(workspace_root: str):
    """
    Get the status of multi-repository intelligence integration.
    
    This endpoint provides visibility into the health and capabilities
    of the multi-repo intelligence system.
    """
    try:
        integration = get_multi_repo_integration(workspace_root)
        system_context = await integration.get_system_context()
        
        return {
            "integration_enabled": True,
            "workspace_root": workspace_root,
            "current_repository": system_context.current_repository,
            "total_repositories": len(system_context.organization_repos),
            "system_health_score": system_context.system_health_score,
            "last_health_check": system_context.last_health_check.isoformat() if system_context.last_health_check else None,
            "capabilities": [
                "cross_repository_impact_analysis",
                "system_health_monitoring",
                "coordinated_multi_repo_changes", 
                "principal_engineer_decisions",
                "architectural_guidance",
                "dependency_resolution",
                "contract_analysis",
                "blast_radius_calculation"
            ],
            "status": "operational"
        }
        
    except Exception as e:
        logger.error(f"Integration status check failed: {e}")
        return {
            "integration_enabled": False,
            "error": str(e),
            "status": "error"
        }

@router.post("/discover-repositories/{workspace_root:path}")
async def discover_repositories(workspace_root: str, background_tasks: BackgroundTasks):
    """
    Discover and register repositories in the organization.
    
    This endpoint helps bootstrap the multi-repository intelligence
    by discovering available repositories and their metadata.
    """
    try:
        logger.info(f"Discovering repositories for workspace: {workspace_root}")
        
        integration = get_multi_repo_integration(workspace_root)
        
        # Run repository discovery in background
        background_tasks.add_task(_discover_repositories_background, integration, workspace_root)
        
        return {
            "success": True,
            "message": "Repository discovery started in background",
            "workspace_root": workspace_root,
            "status": "discovery_in_progress"
        }
        
    except Exception as e:
        logger.error(f"Repository discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _discover_repositories_background(integration, workspace_root: str):
    """Background task to discover repositories"""
    try:
        logger.info(f"Running background repository discovery for {workspace_root}")
        
        # Force refresh of system context to discover new repositories
        await integration.get_system_context(force_refresh=True)
        
        logger.info(f"Repository discovery completed for {workspace_root}")
        
    except Exception as e:
        logger.error(f"Background repository discovery failed: {e}")

# ============================================================================
# Health Check Endpoints
# ============================================================================

@router.get("/health")
async def health_check():
    """Basic health check for multi-repo intelligence API"""
    return {
        "status": "healthy",
        "service": "navi-multirepo-intelligence",
        "version": "4.8.0",
        "capabilities": [
            "cross_repository_analysis",
            "system_health_monitoring",
            "coordinated_changes",
            "architectural_guidance"
        ],
        "timestamp": datetime.now().isoformat()
    }

@router.get("/capabilities")
async def get_capabilities():
    """Get detailed capabilities of multi-repo intelligence system"""
    return {
        "phase": "4.8",
        "name": "Multi-Repository Intelligence",
        "description": "Principal Engineer-level system reasoning across repository boundaries",
        "components": {
            "repo_registry": "Organization-wide repository awareness",
            "graph_builder": "System topology and dependency graphs", 
            "dependency_resolver": "Language-agnostic dependency resolution",
            "contract_analyzer": "API contract and schema intelligence",
            "impact_analyzer": "Cross-repository blast radius analysis",
            "change_coordinator": "Atomic multi-repository changes",
            "multi_repo_orchestrator": "Principal Engineer decision making"
        },
        "supported_languages": [
            "JavaScript/TypeScript (npm)",
            "Python (pip, poetry)",
            "Java (maven)",
            "Go (go.mod)",
            "Rust (cargo)",
            "Terraform",
            "Docker"
        ],
        "supported_contracts": [
            "OpenAPI/Swagger",
            "GraphQL",
            "JSON Schema", 
            "Protocol Buffers",
            "Apache Avro"
        ],
        "integration_points": [
            "NAVI intent enhancement",
            "Impact analysis",
            "Architectural guidance",
            "System health monitoring",
            "Coordinated change orchestration"
        ]
    }