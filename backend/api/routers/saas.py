"""
SaaS Management API for NAVI

Provides REST endpoints for:
1. Organization management
2. Team management
3. User preferences
4. Knowledge base (RAG) management
5. Approval workflow management
6. Feedback and analytics

This enables NAVI to be deployed as a multi-tenant SaaS
serving enterprises, teams, and individual developers.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

# Import our SaaS systems
from backend.services.organization_context import (
    OrganizationContext,
    TeamContext,
    UserPreferences,
    CodingStandard,
    ArchitecturePattern,
    ContextLevel,
    get_context_store,
    resolve_context,
)
from backend.services.knowledge_rag import (
    DocumentType,
    get_rag_manager,
    get_rag_context,
)
from backend.services.feedback_learning import (
    FeedbackType,
    get_feedback_manager,
    get_learning_context,
)
from backend.services.gated_approval import (
    get_approval_manager,
    evaluate_for_approval,
)
from backend.services.token_tracking import (
    get_token_tracker,
    get_usage_summary,
    CostCalculator,
    MODEL_PRICING,
)

router = APIRouter(prefix="/saas", tags=["SaaS Management"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class CodingStandardCreate(BaseModel):
    """Request to create a coding standard."""
    name: str
    description: str
    language: Optional[str] = None
    framework: Optional[str] = None
    rule: str = ""
    examples: List[str] = []
    anti_examples: List[str] = []
    source: str = ""


class ArchitecturePatternCreate(BaseModel):
    """Request to create an architecture pattern."""
    name: str
    description: str
    pattern_type: str
    components: List[str] = []
    rules: List[str] = []
    file_structure: Dict[str, str] = {}


class OrganizationCreate(BaseModel):
    """Request to create an organization."""
    org_id: str
    name: str
    preferred_languages: List[str] = []
    preferred_frameworks: Dict[str, List[str]] = {}
    indent_style: str = "spaces"
    indent_size: int = 4
    quote_style: str = "double"
    semicolons: bool = True
    naming_conventions: Dict[str, str] = {}
    require_docstrings: bool = True
    docstring_style: str = "google"
    require_type_hints: bool = True
    min_test_coverage: int = 80
    test_framework: Optional[str] = None
    security_scan_required: bool = True
    allowed_dependencies: List[str] = []
    blocked_dependencies: List[str] = []


class OrganizationUpdate(BaseModel):
    """Request to update an organization."""
    name: Optional[str] = None
    preferred_languages: Optional[List[str]] = None
    preferred_frameworks: Optional[Dict[str, List[str]]] = None
    indent_style: Optional[str] = None
    indent_size: Optional[int] = None
    quote_style: Optional[str] = None
    semicolons: Optional[bool] = None
    naming_conventions: Optional[Dict[str, str]] = None
    require_docstrings: Optional[bool] = None
    docstring_style: Optional[str] = None
    require_type_hints: Optional[bool] = None
    min_test_coverage: Optional[int] = None
    test_framework: Optional[str] = None
    security_scan_required: Optional[bool] = None
    allowed_dependencies: Optional[List[str]] = None
    blocked_dependencies: Optional[List[str]] = None


class TeamCreate(BaseModel):
    """Request to create a team."""
    team_id: str
    org_id: str
    name: str
    preferred_languages: List[str] = []
    preferred_frameworks: Dict[str, List[str]] = {}
    tech_stack: List[str] = []


class UserPreferencesUpdate(BaseModel):
    """Request to update user preferences."""
    verbose_explanations: Optional[bool] = None
    auto_apply_changes: Optional[bool] = None
    preferred_languages: Optional[List[str]] = None


class DocumentIngest(BaseModel):
    """Request to ingest a document into RAG."""
    content: str
    doc_type: str  # coding_standard, architecture_doc, code_review, etc.
    language: Optional[str] = None
    framework: Optional[str] = None
    tags: List[str] = []
    source_url: Optional[str] = None
    author: Optional[str] = None


class FeedbackSubmit(BaseModel):
    """Request to submit feedback on a suggestion."""
    suggestion_id: str
    feedback_type: str  # accepted, modified, rejected, ignored
    original_content: str
    modified_content: Optional[str] = None
    reason: Optional[str] = None
    response_time: float = 0.0


class ApprovalAction(BaseModel):
    """Request to approve or reject an operation."""
    request_id: str
    action: str  # approve, reject
    comment: Optional[str] = None
    reason: Optional[str] = None  # For rejection


# ============================================================
# ORGANIZATION ENDPOINTS
# ============================================================

@router.post("/organizations")
async def create_organization(org: OrganizationCreate):
    """Create a new organization."""
    store = get_context_store()

    # Check if org already exists
    existing = store.get_organization(org.org_id)
    if existing:
        raise HTTPException(status_code=400, detail="Organization already exists")

    # Create organization context
    org_context = OrganizationContext(
        org_id=org.org_id,
        name=org.name,
        preferred_languages=org.preferred_languages,
        preferred_frameworks=org.preferred_frameworks,
        indent_style=org.indent_style,
        indent_size=org.indent_size,
        quote_style=org.quote_style,
        semicolons=org.semicolons,
        naming_conventions=org.naming_conventions,
        require_docstrings=org.require_docstrings,
        docstring_style=org.docstring_style,
        require_type_hints=org.require_type_hints,
        min_test_coverage=org.min_test_coverage,
        test_framework=org.test_framework,
        security_scan_required=org.security_scan_required,
        allowed_dependencies=org.allowed_dependencies,
        blocked_dependencies=org.blocked_dependencies,
    )

    store.save_organization(org_context)

    return {"status": "created", "org_id": org.org_id}


@router.get("/organizations/{org_id}")
async def get_organization(org_id: str):
    """Get organization details."""
    store = get_context_store()
    org = store.get_organization(org_id)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {
        "org_id": org.org_id,
        "name": org.name,
        "preferred_languages": org.preferred_languages,
        "preferred_frameworks": org.preferred_frameworks,
        "indent_style": org.indent_style,
        "indent_size": org.indent_size,
        "quote_style": org.quote_style,
        "semicolons": org.semicolons,
        "naming_conventions": org.naming_conventions,
        "require_docstrings": org.require_docstrings,
        "docstring_style": org.docstring_style,
        "require_type_hints": org.require_type_hints,
        "min_test_coverage": org.min_test_coverage,
        "test_framework": org.test_framework,
        "security_scan_required": org.security_scan_required,
        "coding_standards_count": len(org.coding_standards),
        "architecture_patterns_count": len(org.architecture_patterns),
        "review_insights_count": len(org.review_insights),
    }


@router.patch("/organizations/{org_id}")
async def update_organization(org_id: str, update: OrganizationUpdate):
    """Update organization settings."""
    store = get_context_store()
    org = store.get_organization(org_id)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Update fields that are provided
    if update.name is not None:
        org.name = update.name
    if update.preferred_languages is not None:
        org.preferred_languages = update.preferred_languages
    if update.preferred_frameworks is not None:
        org.preferred_frameworks = update.preferred_frameworks
    if update.indent_style is not None:
        org.indent_style = update.indent_style
    if update.indent_size is not None:
        org.indent_size = update.indent_size
    if update.quote_style is not None:
        org.quote_style = update.quote_style
    if update.semicolons is not None:
        org.semicolons = update.semicolons
    if update.naming_conventions is not None:
        org.naming_conventions = update.naming_conventions
    if update.require_docstrings is not None:
        org.require_docstrings = update.require_docstrings
    if update.docstring_style is not None:
        org.docstring_style = update.docstring_style
    if update.require_type_hints is not None:
        org.require_type_hints = update.require_type_hints
    if update.min_test_coverage is not None:
        org.min_test_coverage = update.min_test_coverage
    if update.test_framework is not None:
        org.test_framework = update.test_framework
    if update.security_scan_required is not None:
        org.security_scan_required = update.security_scan_required
    if update.allowed_dependencies is not None:
        org.allowed_dependencies = update.allowed_dependencies
    if update.blocked_dependencies is not None:
        org.blocked_dependencies = update.blocked_dependencies

    store.save_organization(org)

    return {"status": "updated", "org_id": org_id}


@router.post("/organizations/{org_id}/standards")
async def add_coding_standard(org_id: str, standard: CodingStandardCreate):
    """Add a coding standard to an organization."""
    store = get_context_store()
    org = store.get_organization(org_id)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Create standard
    import hashlib
    std_id = hashlib.sha256(
        f"{org_id}:{standard.name}:{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    coding_std = CodingStandard(
        id=std_id,
        name=standard.name,
        description=standard.description,
        language=standard.language,
        framework=standard.framework,
        rule=standard.rule,
        examples=standard.examples,
        anti_examples=standard.anti_examples,
        source=standard.source,
        level=ContextLevel.ORGANIZATION,
    )

    org.coding_standards.append(coding_std)
    store.save_organization(org)

    return {"status": "added", "standard_id": std_id}


@router.post("/organizations/{org_id}/patterns")
async def add_architecture_pattern(org_id: str, pattern: ArchitecturePatternCreate):
    """Add an architecture pattern to an organization."""
    store = get_context_store()
    org = store.get_organization(org_id)

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    import hashlib
    pattern_id = hashlib.sha256(
        f"{org_id}:{pattern.name}:{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    arch_pattern = ArchitecturePattern(
        id=pattern_id,
        name=pattern.name,
        description=pattern.description,
        pattern_type=pattern.pattern_type,
        components=pattern.components,
        rules=pattern.rules,
        file_structure=pattern.file_structure,
        level=ContextLevel.ORGANIZATION,
    )

    org.architecture_patterns.append(arch_pattern)
    store.save_organization(org)

    return {"status": "added", "pattern_id": pattern_id}


# ============================================================
# TEAM ENDPOINTS
# ============================================================

@router.post("/teams")
async def create_team(team: TeamCreate):
    """Create a new team."""
    store = get_context_store()

    # Verify org exists
    org = store.get_organization(team.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if team exists
    existing = store.get_team(team.team_id)
    if existing:
        raise HTTPException(status_code=400, detail="Team already exists")

    team_context = TeamContext(
        team_id=team.team_id,
        org_id=team.org_id,
        name=team.name,
        preferred_languages=team.preferred_languages,
        preferred_frameworks=team.preferred_frameworks,
        tech_stack=team.tech_stack,
    )

    store.save_team(team_context)

    return {"status": "created", "team_id": team.team_id}


@router.get("/teams/{team_id}")
async def get_team(team_id: str):
    """Get team details."""
    store = get_context_store()
    team = store.get_team(team_id)

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    return {
        "team_id": team.team_id,
        "org_id": team.org_id,
        "name": team.name,
        "preferred_languages": team.preferred_languages,
        "preferred_frameworks": team.preferred_frameworks,
        "tech_stack": team.tech_stack,
        "coding_standards_count": len(team.coding_standards),
    }


@router.post("/teams/{team_id}/standards")
async def add_team_standard(team_id: str, standard: CodingStandardCreate):
    """Add a team-specific coding standard."""
    store = get_context_store()
    team = store.get_team(team_id)

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    import hashlib
    std_id = hashlib.sha256(
        f"{team_id}:{standard.name}:{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    coding_std = CodingStandard(
        id=std_id,
        name=standard.name,
        description=standard.description,
        language=standard.language,
        framework=standard.framework,
        rule=standard.rule,
        examples=standard.examples,
        anti_examples=standard.anti_examples,
        source=standard.source,
        level=ContextLevel.TEAM,
    )

    team.coding_standards.append(coding_std)
    store.save_team(team)

    return {"status": "added", "standard_id": std_id}


# ============================================================
# USER ENDPOINTS
# ============================================================

@router.get("/users/{user_id}/preferences")
async def get_user_preferences(user_id: str):
    """Get user preferences."""
    store = get_context_store()
    user = store.get_user(user_id)

    if not user:
        # Return defaults for new user
        return {
            "user_id": user_id,
            "verbose_explanations": True,
            "auto_apply_changes": False,
            "preferred_languages": [],
            "accepted_suggestions": 0,
            "rejected_suggestions": 0,
        }

    return {
        "user_id": user.user_id,
        "org_id": user.org_id,
        "team_id": user.team_id,
        "verbose_explanations": user.verbose_explanations,
        "auto_apply_changes": user.auto_apply_changes,
        "preferred_languages": user.preferred_languages,
        "accepted_suggestions": user.accepted_suggestions,
        "rejected_suggestions": user.rejected_suggestions,
        "modified_suggestions": user.modified_suggestions,
    }


@router.patch("/users/{user_id}/preferences")
async def update_user_preferences(
    user_id: str,
    update: UserPreferencesUpdate,
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
):
    """Update user preferences."""
    store = get_context_store()
    user = store.get_user(user_id)

    if not user:
        # Create new user
        user = UserPreferences(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
        )

    if update.verbose_explanations is not None:
        user.verbose_explanations = update.verbose_explanations
    if update.auto_apply_changes is not None:
        user.auto_apply_changes = update.auto_apply_changes
    if update.preferred_languages is not None:
        user.preferred_languages = update.preferred_languages

    store.save_user(user)

    return {"status": "updated", "user_id": user_id}


# ============================================================
# KNOWLEDGE BASE (RAG) ENDPOINTS
# ============================================================

@router.post("/knowledge/{org_id}/ingest")
async def ingest_document(
    org_id: str,
    doc: DocumentIngest,
    team_id: Optional[str] = Query(None),
):
    """Ingest a document into the knowledge base."""
    manager = get_rag_manager()

    try:
        doc_type = DocumentType(doc.doc_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc.doc_type}")

    result = await manager.ingest_document(
        content=doc.content,
        doc_type=doc_type,
        org_id=org_id,
        team_id=team_id,
        metadata={
            "language": doc.language,
            "framework": doc.framework,
            "tags": doc.tags,
            "source_url": doc.source_url,
            "author": doc.author,
        }
    )

    return {"status": "ingested", "document_id": result.id}


@router.post("/knowledge/{org_id}/ingest/coding-standard")
async def ingest_coding_standard(
    org_id: str,
    content: str = Body(...),
    language: Optional[str] = Body(None),
    source: Optional[str] = Body(None),
    team_id: Optional[str] = Query(None),
):
    """Ingest a coding standard document."""
    manager = get_rag_manager()

    result = await manager.ingest_coding_standard(
        content=content,
        org_id=org_id,
        team_id=team_id,
        language=language,
        source=source,
    )

    return {"status": "ingested", "document_id": result.id}


@router.post("/knowledge/{org_id}/ingest/code-review")
async def ingest_code_review(
    org_id: str,
    content: str = Body(...),
    language: Optional[str] = Body(None),
    reviewer: Optional[str] = Body(None),
    team_id: Optional[str] = Query(None),
):
    """Ingest code review feedback."""
    manager = get_rag_manager()

    result = await manager.ingest_code_review(
        review_content=content,
        org_id=org_id,
        team_id=team_id,
        language=language,
        reviewer=reviewer,
    )

    return {"status": "ingested", "document_id": result.id}


@router.get("/knowledge/{org_id}/search")
async def search_knowledge(
    org_id: str,
    query: str,
    team_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
):
    """Search the knowledge base."""
    manager = get_rag_manager()

    filters = {}
    if language:
        filters["language"] = language
    if framework:
        filters["framework"] = framework

    results = await manager.retrieve(
        query=query,
        org_id=org_id,
        team_id=team_id,
        filters=filters if filters else None,
        top_k=top_k,
    )

    return {
        "query": query,
        "results": [
            {
                "document_id": r.document.id,
                "doc_type": r.document.doc_type.value,
                "score": r.score,
                "snippet": r.snippet,
                "language": r.document.language,
                "framework": r.document.framework,
            }
            for r in results
        ]
    }


# ============================================================
# FEEDBACK ENDPOINTS
# ============================================================

@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackSubmit,
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
):
    """Submit feedback on a NAVI suggestion."""
    manager = get_feedback_manager()

    try:
        feedback_type = FeedbackType(feedback.feedback_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback_type: {feedback.feedback_type}"
        )

    manager.record_user_feedback(
        suggestion_id=feedback.suggestion_id,
        feedback_type=feedback_type,
        original_content=feedback.original_content,
        modified_content=feedback.modified_content,
        reason=feedback.reason,
        response_time=feedback.response_time,
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
    )

    return {"status": "recorded", "suggestion_id": feedback.suggestion_id}


@router.get("/feedback/stats")
async def get_feedback_stats(
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """Get feedback statistics."""
    manager = get_feedback_manager()

    stats = manager.get_acceptance_stats(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        days=days,
    )

    return {
        "period_days": days,
        "total_suggestions": stats["total"],
        "accepted": stats["accepted"],
        "modified": stats["modified"],
        "rejected": stats["rejected"],
        "ignored": stats["ignored"],
        "acceptance_rate": stats["acceptance_rate"],
        "by_category": dict(stats["by_category"]),
    }


@router.get("/feedback/insights")
async def get_learning_insights(
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
):
    """Get learning insights from feedback."""
    context = get_learning_context(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        language=language,
    )

    return {"insights": context}


# ============================================================
# APPROVAL ENDPOINTS
# ============================================================

@router.post("/approvals/evaluate")
async def evaluate_operation(
    operation_type: str = Body(...),
    content: str = Body(...),
    filepath: Optional[str] = Body(None),
    org_id: Optional[str] = Body(None),
    team_id: Optional[str] = Body(None),
    user_id: Optional[str] = Body(None),
):
    """Evaluate an operation for approval requirements."""
    request = evaluate_for_approval(
        operation_type=operation_type,
        content=content,
        filepath=filepath,
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
    )

    manager = get_approval_manager()
    summary = manager.get_risk_summary(request)

    return {
        "request_id": request.id,
        "operation_type": operation_type,
        "filepath": filepath,
        "risk_summary": summary,
        "requires_approval": request.required_level.value != "none",
    }


@router.get("/approvals/pending")
async def get_pending_approvals(
    user_id: Optional[str] = Query(None),
    approver_role: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
):
    """Get pending approval requests."""
    manager = get_approval_manager()

    if user_id:
        # Get requests created by this user
        requests = manager.get_pending_for_user(user_id)
    elif approver_role:
        # Get requests this role can approve
        requests = manager.get_pending_for_approver(approver_role, org_id, team_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Must specify either user_id or approver_role"
        )

    return {
        "pending_count": len(requests),
        "requests": [
            {
                "request_id": r.id,
                "operation_type": r.operation_type,
                "filepath": r.filepath,
                "risk_summary": manager.get_risk_summary(r),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in requests
        ]
    }


@router.post("/approvals/action")
async def process_approval_action(
    action: ApprovalAction,
    approver_id: str = Query(...),
    approver_role: str = Query("user"),
):
    """Approve or reject an operation."""
    manager = get_approval_manager()

    if action.action == "approve":
        fully_approved = manager.approve(
            request_id=action.request_id,
            approver_id=approver_id,
            approver_role=approver_role,
            comment=action.comment,
        )
        return {
            "status": "approved" if fully_approved else "pending_more_approvals",
            "request_id": action.request_id,
        }

    elif action.action == "reject":
        if not action.reason:
            raise HTTPException(status_code=400, detail="Reason required for rejection")

        manager.reject(
            request_id=action.request_id,
            rejecter_id=approver_id,
            reason=action.reason,
        )
        return {"status": "rejected", "request_id": action.request_id}

    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")


@router.get("/approvals/{request_id}")
async def get_approval_request(request_id: str):
    """Get details of an approval request."""
    manager = get_approval_manager()
    request = manager.pending_requests.get(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return {
        "request_id": request.id,
        "operation_type": request.operation_type,
        "filepath": request.filepath,
        "content_preview": request.content[:500] + "..." if len(request.content) > 500 else request.content,
        "risk_summary": manager.get_risk_summary(request),
        "status": request.status,
        "approvals": request.approvals,
        "rejections": request.rejections,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "expires_at": request.expires_at.isoformat() if request.expires_at else None,
    }


# ============================================================
# CONTEXT RESOLUTION ENDPOINT
# ============================================================

@router.get("/context")
async def get_full_context(
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    task: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
):
    """
    Get the full resolved context for a NAVI session.
    Combines organization, team, user, RAG, and learning contexts.
    """
    # Resolve hierarchical context
    org_team_context = resolve_context(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
    )

    # Get RAG context if task provided
    rag_context = ""
    if task and org_id:
        rag_context = await get_rag_context(
            task=task,
            org_id=org_id,
            team_id=team_id,
            language=language,
            framework=framework,
        )

    # Get learning context
    learning_ctx = get_learning_context(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        language=language,
    )

    # Combine all contexts
    full_context = "\n\n".join(filter(None, [
        org_team_context,
        rag_context,
        learning_ctx,
    ]))

    return {
        "context": full_context,
        "has_org_context": bool(org_team_context),
        "has_rag_context": bool(rag_context),
        "has_learning_context": bool(learning_ctx),
    }


# ============================================================
# USAGE & BILLING ENDPOINTS
# ============================================================

@router.get("/usage/summary")
async def get_usage_stats(
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """
    Get token usage and cost summary for billing.
    Returns aggregate stats for the specified scope and time period.
    """
    summary = get_usage_summary(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        days=days,
    )

    return {
        "period": {
            "start": summary.period_start.isoformat(),
            "end": summary.period_end.isoformat(),
            "days": days,
        },
        "totals": {
            "requests": summary.total_requests,
            "input_tokens": summary.total_input_tokens,
            "output_tokens": summary.total_output_tokens,
            "total_tokens": summary.total_tokens,
            "cost": f"${summary.total_cost:.4f}",
        },
        "averages": {
            "tokens_per_request": round(summary.avg_tokens_per_request, 1),
            "cost_per_request": f"${summary.avg_cost_per_request:.6f}",
            "latency_ms": round(summary.avg_latency_ms, 2),
        },
        "by_model": {
            model: {
                "requests": data["requests"],
                "tokens": data["tokens"],
                "cost": f"${data['cost']:.4f}",
            }
            for model, data in summary.by_model.items()
        },
        "by_user": {
            user: {
                "requests": data["requests"],
                "tokens": data["tokens"],
                "cost": f"${data['cost']:.4f}",
            }
            for user, data in summary.by_user.items()
        } if summary.by_user else None,
    }


@router.get("/usage/recent")
async def get_recent_usage(
    limit: int = Query(10, ge=1, le=100),
    org_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
):
    """Get recent usage records for detailed billing view."""
    tracker = get_token_tracker()
    records = tracker.get_recent_usage(
        limit=limit,
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
    )

    return {
        "count": len(records),
        "records": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "model": r.model,
                "provider": r.provider,
                "tokens": {
                    "input": r.usage.input_tokens,
                    "output": r.usage.output_tokens,
                    "total": r.usage.total_tokens,
                },
                "cost": {
                    "input": f"${r.input_cost:.6f}",
                    "output": f"${r.output_cost:.6f}",
                    "total": f"${r.total_cost:.6f}",
                },
                "latency_ms": round(r.latency_ms, 2),
                "user_id": r.user_id,
            }
            for r in records
        ]
    }


@router.get("/usage/pricing")
async def get_model_pricing():
    """Get current model pricing for cost estimation."""
    return {
        "pricing": {
            model: {
                "input_per_1m": f"${prices['input']:.2f}",
                "output_per_1m": f"${prices['output']:.2f}",
            }
            for model, prices in MODEL_PRICING.items()
            if model != "default"
        },
        "note": "Prices are per 1 million tokens in USD",
    }


@router.post("/usage/estimate")
async def estimate_cost(
    model: str = Body(...),
    input_tokens: int = Body(...),
    estimated_output_tokens: int = Body(1000),
):
    """Estimate cost for a request before making it."""
    estimated_cost = CostCalculator.estimate_cost(
        model=model,
        input_tokens=input_tokens,
        estimated_output=estimated_output_tokens,
    )

    pricing = CostCalculator.get_model_pricing(model)

    return {
        "model": model,
        "input_tokens": input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": f"${estimated_cost:.6f}",
        "breakdown": {
            "input_cost": f"${(input_tokens / 1_000_000) * pricing['input']:.6f}",
            "output_cost": f"${(estimated_output_tokens / 1_000_000) * pricing['output']:.6f}",
        }
    }
