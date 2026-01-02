"""
Phase 7.0 Extension API - Public API for NAVI Extensions

Provides REST API endpoints for:
- Extension marketplace operations
- Extension installation and management  
- Capability discovery and execution
- Extension development and testing
- Marketplace browsing and search

This API serves both:
1. Public marketplace for third-party developers
2. Enterprise internal extension management
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.security import HTTPBearer
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging
import asyncio

from .runtime import (
    ExtensionManifest, ExtensionType, ExtensionTrust, ExtensionLifecycleState,
    get_extension_runtime, ExtensionRepository
)
from .security_service import create_security_service
from ..core.tenancy import require_tenant
from ..core.observability import metrics_collector, MetricType
from ..core.db import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/extensions", tags=["extensions"])
security = HTTPBearer()

# Request/Response Models

class CreateExtensionRequest(BaseModel):
    """Request to create/publish new extension"""
    manifest: Dict[str, Any]
    bundle_data: Optional[str] = None  # Base64 encoded extension bundle

class InstallExtensionRequest(BaseModel):
    """Request to install extension"""
    extension_id: str
    version: Optional[str] = None
    auto_approve_permissions: bool = False

class ExecuteCapabilityRequest(BaseModel):
    """Request to execute extension capability"""
    capability_name: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    preferred_extension: Optional[str] = None
    async_execution: bool = False

class ExtensionSearchRequest(BaseModel):
    """Search extensions in marketplace"""
    query: str = ""
    categories: List[str] = Field(default_factory=list)
    extension_type: Optional[ExtensionType] = None
    trust_level: Optional[ExtensionTrust] = None
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)

class ExtensionResponse(BaseModel):
    """Extension information response"""
    id: str
    name: str
    version: str
    description: str
    author: str
    extension_type: str
    category: str
    tags: List[str]
    capabilities: List[str]
    permissions: List[str]
    scope: str
    trust_level: str
    state: str
    created_at: datetime
    updated_at: datetime
    installed: bool = False
    download_count: int = 0
    rating: float = 0.0

class CapabilityResponse(BaseModel):
    """Capability information response"""
    name: str
    description: str
    providers: List[str]  # Extension IDs that provide this capability
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]

class ExecutionResult(BaseModel):
    """Extension execution result"""
    execution_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    execution_time: float
    resource_usage: Dict[str, Any] = Field(default_factory=dict)

class SecurityFindingResponse(BaseModel):
    """Security finding information"""
    finding_id: str
    threat_type: str
    risk_level: str
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    remediation: Optional[str] = None
    references: Optional[List[str]] = None
    cve_ids: Optional[List[str]] = None

class ExtensionCertificateResponse(BaseModel):
    """Extension certificate information"""
    certificate_id: str
    extension_id: str
    issuer: str
    subject: str
    valid_from: datetime
    valid_until: datetime
    is_self_signed: bool
    revocation_status: str

class SecurityReportResponse(BaseModel):
    """Security assessment report"""
    extension_id: str
    report_id: str
    generated_at: datetime
    security_level: str
    overall_score: int
    findings: List[SecurityFindingResponse]
    certificate: Optional[ExtensionCertificateResponse] = None
    policy_compliance: Dict[str, bool]
    recommendations: List[str]
    scan_metadata: Dict[str, Any]

class SecurityValidationRequest(BaseModel):
    """Request for extension security validation"""
    extension_manifest: Dict[str, Any]
    force_rescan: bool = False

class SecurityPolicyRequest(BaseModel):
    """Request to update security policies"""
    policies: Dict[str, Any]

class CertificateSigningRequest(BaseModel):
    """Request for extension certificate signing"""
    extension_manifest: Dict[str, Any]

# Marketplace Endpoints

@router.get("/marketplace/featured", response_model=List[ExtensionResponse])
async def get_featured_extensions():
    """Get featured extensions in marketplace"""
    try:
        # This would integrate with actual marketplace data
        # For now, return mock featured extensions
        featured = [
            {
                "id": "navi.terraform.optimizer",
                "name": "Terraform Infrastructure Optimizer", 
                "version": "1.2.0",
                "description": "Automatically optimize Terraform configurations for cost and security",
                "author": "NAVI Team",
                "extension_type": "intelligence",
                "category": "infrastructure",
                "tags": ["terraform", "optimization", "cost", "security"],
                "capabilities": ["optimize_terraform", "validate_terraform", "cost_estimate"],
                "permissions": ["read_files", "write_files", "network_access"],
                "scope": "public",
                "trust_level": "verified",
                "state": "published",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "download_count": 1523,
                "rating": 4.8
            },
            {
                "id": "navi.k8s.security",
                "name": "Kubernetes Security Scanner",
                "version": "2.1.1", 
                "description": "Comprehensive security analysis for Kubernetes manifests and clusters",
                "author": "Security Team",
                "extension_type": "skill",
                "category": "security",
                "tags": ["kubernetes", "security", "compliance"],
                "capabilities": ["scan_k8s_security", "generate_rbac", "audit_cluster"],
                "permissions": ["read_files", "network_access", "execute_commands"],
                "scope": "public",
                "trust_level": "verified", 
                "state": "published",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "download_count": 892,
                "rating": 4.6
            }
        ]
        
        await metrics_collector.record_metric(
            MetricType.API_REQUESTS,
            1.0,
            "count",
            tags={"endpoint": "marketplace_featured", "method": "GET"}
        )
        
        return [ExtensionResponse(**ext) for ext in featured]
        
    except Exception as e:
        logger.error(f"Failed to get featured extensions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve featured extensions")

@router.post("/marketplace/search", response_model=List[ExtensionResponse])
async def search_extensions(request: ExtensionSearchRequest):
    """Search extensions in marketplace"""
    try:
        # This would integrate with actual search backend (Elasticsearch, etc.)
        # For now, return mock search results based on query
        
        all_extensions = [
            {
                "id": "navi.ci.fixer",
                "name": "CI Pipeline Auto-Fixer",
                "description": "Automatically diagnose and fix common CI/CD pipeline failures",
                "category": "ci_cd",
                "tags": ["ci", "automation", "debugging"]
            },
            {
                "id": "navi.docs.generator", 
                "name": "Smart Documentation Generator",
                "description": "Generate comprehensive documentation from code and comments",
                "category": "documentation",
                "tags": ["docs", "automation", "markdown"]
            },
            {
                "id": "navi.perf.analyzer",
                "name": "Performance Bottleneck Analyzer", 
                "description": "Identify and suggest fixes for application performance issues",
                "category": "performance",
                "tags": ["performance", "optimization", "profiling"]
            }
        ]
        
        # Mock search filtering
        results = []
        for ext in all_extensions:
            if (not request.query or 
                request.query.lower() in ext["name"].lower() or
                request.query.lower() in ext["description"].lower() or
                any(request.query.lower() in tag for tag in ext["tags"])):
                
                # Build full extension response
                result = {
                    **ext,
                    "version": "1.0.0",
                    "author": "Community",
                    "extension_type": "action",
                    "capabilities": [f"{ext['id']}.execute"],
                    "permissions": ["read_files", "write_files"],
                    "scope": "public",
                    "trust_level": "community",
                    "state": "published", 
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "download_count": 100,
                    "rating": 4.2
                }
                results.append(result)
        
        # Apply pagination
        paginated = results[request.offset:request.offset + request.limit]
        
        await metrics_collector.record_metric(
            MetricType.API_REQUESTS,
            1.0,
            "count", 
            tags={"endpoint": "marketplace_search", "method": "POST"}
        )
        
        return [ExtensionResponse(**ext) for ext in paginated]
        
    except Exception as e:
        logger.error(f"Extension search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/marketplace/{extension_id}", response_model=ExtensionResponse)
async def get_extension_details(extension_id: str):
    """Get detailed information about specific extension"""
    try:
        info = await get_extension_runtime().get_extension_info(extension_id)
        if not info:
            raise HTTPException(status_code=404, detail="Extension not found")
        
        manifest = info["manifest"]
        
        response = ExtensionResponse(
            id=manifest["id"],
            name=manifest["name"],
            version=manifest["version"],
            description=manifest["description"],
            author=manifest["author"],
            extension_type=manifest["extension_type"],
            category=manifest["category"],
            tags=manifest["tags"],
            capabilities=[cap["name"] for cap in manifest["capabilities"]],
            permissions=manifest["permissions"],
            scope=manifest["scope"],
            trust_level=manifest["trust_level"],
            state=manifest["state"],
            created_at=datetime.fromisoformat(manifest["created_at"]),
            updated_at=datetime.fromisoformat(manifest["updated_at"]),
            installed=info["installed"]
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extension {extension_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve extension details")

# Extension Management Endpoints

@router.post("/install", response_model=Dict[str, Any])
async def install_extension(request: InstallExtensionRequest, tenant=Depends(require_tenant)):
    """Install extension for current organization"""
    try:
        # Get extension manifest from marketplace or repository
        extension_repo = ExtensionRepository()
        manifest = await extension_repo.get_extension(request.extension_id)
        
        if not manifest:
            # Try to fetch from public marketplace
            # This would be implemented as a separate marketplace service
            raise HTTPException(status_code=404, detail="Extension not found")
        
        # Install extension
        success = await get_extension_runtime().install_extension(manifest)
        
        if not success:
            raise HTTPException(status_code=400, detail="Installation failed")
        
        await metrics_collector.record_metric(
            MetricType.EXTENSIONS_INSTALLED,
            1.0,
            "count",
            tags={
                "extension_id": request.extension_id,
                "org_id": tenant.org_id
            }
        )
        
        return {
            "success": True,
            "extension_id": request.extension_id,
            "message": f"Extension {manifest.name} installed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extension installation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Installation failed")

@router.get("/installed", response_model=List[ExtensionResponse])
async def list_installed_extensions(tenant=Depends(require_tenant)):
    """List extensions installed in current organization"""
    try:
        extension_repo = ExtensionRepository()
        extensions = await extension_repo.list_extensions(
            state=ExtensionLifecycleState.INSTALLED
        )
        
        responses = []
        for manifest in extensions:
            response = ExtensionResponse(
                id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                author=manifest.author,
                extension_type=manifest.extension_type.value,
                category=manifest.category,
                tags=manifest.tags,
                capabilities=[cap.name for cap in manifest.capabilities],
                permissions=manifest.permissions,
                scope=manifest.scope.value,
                trust_level=manifest.trust_level.value,
                state=manifest.state.value,
                created_at=manifest.created_at,
                updated_at=manifest.updated_at,
                installed=True
            )
            responses.append(response)
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list installed extensions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list extensions")

@router.delete("/{extension_id}")
async def uninstall_extension(extension_id: str, tenant=Depends(require_tenant)):
    """Uninstall extension from current organization"""
    try:
        extension_repo = ExtensionRepository()
        
        # Verify extension exists and is installed
        manifest = await extension_repo.get_extension(extension_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="Extension not found")
        
        if manifest.state != ExtensionLifecycleState.INSTALLED:
            raise HTTPException(status_code=400, detail="Extension not installed")
        
        # Unregister capabilities
        get_extension_runtime().capability_registry.unregister_extension(extension_id)
        
        # Delete extension
        success = await extension_repo.delete_extension(extension_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to uninstall extension")
        
        return {"success": True, "message": f"Extension {extension_id} uninstalled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extension uninstall failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Uninstall failed")

# Capability Execution Endpoints

@router.get("/capabilities", response_model=List[CapabilityResponse])
async def list_capabilities():
    """List all available capabilities"""
    try:
        capabilities_map = await get_extension_runtime().list_available_capabilities()
        
        responses = []
        for capability_name, provider_extensions in capabilities_map.items():
            # Get capability details from first provider
            capabilities = get_extension_runtime().capability_registry.find_capabilities(capability_name)
            if capabilities:
                capability = capabilities[0]
                response = CapabilityResponse(
                    name=capability_name,
                    description=capability.description,
                    providers=provider_extensions,
                    input_schema=capability.input_schema,
                    output_schema=capability.output_schema
                )
                responses.append(response)
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list capabilities: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list capabilities")

@router.post("/execute", response_model=ExecutionResult)
async def execute_capability(request: ExecuteCapabilityRequest, tenant=Depends(require_tenant)):
    """Execute an extension capability"""
    try:
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Execute capability
        result = await get_extension_runtime().execute_capability(
            capability_name=request.capability_name,
            inputs=request.inputs,
            preferred_extension=request.preferred_extension
        )
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        await metrics_collector.record_metric(
            MetricType.EXTENSIONS_EXECUTED,
            1.0,
            "count",
            tags={
                "capability": request.capability_name,
                "success": str(result.get("success", False)),
                "org_id": tenant.org_id
            }
        )
        
        return ExecutionResult(
            execution_id=execution_id,
            success=result.get("success", False),
            output=result.get("output"),
            error=result.get("error"),
            logs=result.get("logs", []),
            execution_time=execution_time,
            resource_usage={}
        )
        
    except Exception as e:
        logger.error(f"Capability execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

# Extension Development Endpoints

@router.post("/validate")
async def validate_extension_manifest(manifest: Dict[str, Any]):
    """Validate extension manifest for development"""
    try:
        # Parse and validate manifest
        extension_manifest = ExtensionManifest.from_dict(manifest)
        
        # Run validation checks
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Basic validation
        if not extension_manifest.id:
            validation_result["errors"].append("Extension ID is required")
            validation_result["valid"] = False
        
        if not extension_manifest.name:
            validation_result["errors"].append("Extension name is required")
            validation_result["valid"] = False
        
        if not extension_manifest.version:
            validation_result["errors"].append("Extension version is required")
            validation_result["valid"] = False
        
        # Capability validation
        if not extension_manifest.capabilities:
            validation_result["warnings"].append("Extension defines no capabilities")
        
        # Permission validation
        from .runtime import PermissionManager  # Import here to avoid circular imports

        permission_manager = PermissionManager()
        for perm in extension_manifest.permissions:
            if perm not in permission_manager.permissions:
                validation_result["errors"].append(f"Unknown permission: {perm}")
                validation_result["valid"] = False
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Manifest validation failed: {str(e)}")
        return {
            "valid": False,
            "errors": [f"Manifest parsing failed: {str(e)}"],
            "warnings": [],
            "suggestions": []
        }

@router.post("/publish")
async def publish_extension(
    request: CreateExtensionRequest,
    background_tasks: BackgroundTasks,
    tenant=Depends(require_tenant)
):
    """Publish extension to marketplace (development endpoint)"""
    try:
        # Parse manifest
        manifest = ExtensionManifest.from_dict(request.manifest)
        
        # Set publishing metadata
        manifest.state = ExtensionLifecycleState.SUBMITTED
        manifest.created_at = datetime.utcnow()
        manifest.updated_at = datetime.utcnow()
        
        # Store extension (would also handle bundle upload in production)
        extension_repo = ExtensionRepository()
        success = await extension_repo.create_extension(manifest)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to publish extension")
        
        # In production, this would trigger review workflow
        background_tasks.add_task(
            _mock_extension_review_workflow,
            manifest.id
        )
        
        return {
            "success": True,
            "extension_id": manifest.id,
            "message": "Extension submitted for review",
            "state": manifest.state.value
        }
        
    except Exception as e:
        logger.error(f"Extension publishing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Publishing failed")

# Security Endpoints

@router.post("/security/validate", response_model=SecurityReportResponse)
async def validate_extension_security(
    request: SecurityValidationRequest,
    extension_file: UploadFile = File(...),
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Validate extension security and generate security report"""
    try:
        # Read extension content
        extension_content = await extension_file.read()
        
        # Create security service
        security_service = create_security_service(db)
        
        # Validate security
        security_report, is_approved = await security_service.validate_extension_security(
            request.extension_manifest,
            extension_content,
            tenant.id
        )
        
        # Convert to response model
        response = SecurityReportResponse(
            extension_id=security_report.extension_id,
            report_id=security_report.report_id,
            generated_at=security_report.generated_at,
            security_level=security_report.security_level.value,
            overall_score=security_report.overall_score,
            findings=[
                SecurityFindingResponse(
                    finding_id=f.finding_id,
                    threat_type=f.threat_type.value,
                    risk_level=f.risk_level.value,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_number=f.line_number,
                    code_snippet=f.code_snippet,
                    remediation=f.remediation,
                    references=f.references,
                    cve_ids=f.cve_ids
                ) for f in security_report.findings
            ],
            certificate=ExtensionCertificateResponse(
                certificate_id=security_report.certificate.certificate_id,
                extension_id=security_report.certificate.extension_id,
                issuer=security_report.certificate.issuer,
                subject=security_report.certificate.subject,
                valid_from=security_report.certificate.valid_from,
                valid_until=security_report.certificate.valid_until,
                is_self_signed=security_report.certificate.is_self_signed,
                revocation_status=security_report.certificate.revocation_status
            ) if security_report.certificate else None,
            policy_compliance=security_report.policy_compliance,
            recommendations=security_report.recommendations,
            scan_metadata=security_report.scan_metadata
        )
        
        await metrics_collector.increment(
            metric_type=MetricType.COUNTER,
            amount=1,
            unit="extensions_security_validated",
            tags={"approved": str(is_approved), "score": str(security_report.overall_score)}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Security validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Security validation failed")

@router.get("/security/report/{extension_id}", response_model=SecurityReportResponse)
async def get_security_report(
    extension_id: str,
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Get security report for an extension"""
    try:
        security_service = create_security_service(db)
        security_report = await security_service.get_security_report(extension_id, tenant.id)
        
        if not security_report:
            raise HTTPException(status_code=404, detail="Security report not found")
        
        return SecurityReportResponse(
            extension_id=security_report.extension_id,
            report_id=security_report.report_id,
            generated_at=security_report.generated_at,
            security_level=security_report.security_level.value,
            overall_score=security_report.overall_score,
            findings=[
                SecurityFindingResponse(
                    finding_id=f.finding_id,
                    threat_type=f.threat_type.value,
                    risk_level=f.risk_level.value,
                    title=f.title,
                    description=f.description,
                    file_path=f.file_path,
                    line_number=f.line_number,
                    code_snippet=f.code_snippet,
                    remediation=f.remediation,
                    references=f.references,
                    cve_ids=f.cve_ids
                ) for f in security_report.findings
            ],
            certificate=ExtensionCertificateResponse(
                certificate_id=security_report.certificate.certificate_id,
                extension_id=security_report.certificate.extension_id,
                issuer=security_report.certificate.issuer,
                subject=security_report.certificate.subject,
                valid_from=security_report.certificate.valid_from,
                valid_until=security_report.certificate.valid_until,
                is_self_signed=security_report.certificate.is_self_signed,
                revocation_status=security_report.certificate.revocation_status
            ) if security_report.certificate else None,
            policy_compliance=security_report.policy_compliance,
            recommendations=security_report.recommendations,
            scan_metadata=security_report.scan_metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get security report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get security report")

@router.post("/security/sign", response_model=ExtensionCertificateResponse)
async def sign_extension(
    request: CertificateSigningRequest,
    extension_file: UploadFile = File(...),
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Sign extension and issue certificate"""
    try:
        # Read extension content
        extension_content = await extension_file.read()
        
        # Create security service
        security_service = create_security_service(db)
        
        # Sign extension
        certificate = await security_service.sign_extension(
            request.extension_manifest,
            extension_content,
            tenant.id
        )
        
        await metrics_collector.increment(
            metric_type=MetricType.COUNTER,
            amount=1,
            unit="extensions_certificates_issued",
            tags={"extension_id": certificate.extension_id}
        )
        
        return ExtensionCertificateResponse(
            certificate_id=certificate.certificate_id,
            extension_id=certificate.extension_id,
            issuer=certificate.issuer,
            subject=certificate.subject,
            valid_from=certificate.valid_from,
            valid_until=certificate.valid_until,
            is_self_signed=certificate.is_self_signed,
            revocation_status=certificate.revocation_status
        )
        
    except Exception as e:
        logger.error(f"Extension signing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Extension signing failed")

@router.get("/security/certificate/{extension_id}", response_model=ExtensionCertificateResponse)
async def get_extension_certificate(
    extension_id: str,
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Get certificate for an extension"""
    try:
        security_service = create_security_service(db)
        certificate = await security_service.get_extension_certificate(extension_id, tenant.id)
        
        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        return ExtensionCertificateResponse(
            certificate_id=certificate.certificate_id,
            extension_id=certificate.extension_id,
            issuer=certificate.issuer,
            subject=certificate.subject,
            valid_from=certificate.valid_from,
            valid_until=certificate.valid_until,
            is_self_signed=certificate.is_self_signed,
            revocation_status=certificate.revocation_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get certificate")

@router.put("/security/policies", response_model=Dict[str, str])
async def update_security_policies(
    request: SecurityPolicyRequest,
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Update security policies for tenant"""
    try:
        security_service = create_security_service(db)
        success = await security_service.update_security_policies(tenant.id, request.policies)
        
        if success:
            return {"status": "success", "message": "Security policies updated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update security policies")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update security policies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update security policies")

@router.get("/security/policies", response_model=Dict[str, Any])
async def get_security_policies(
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Get security policies for tenant"""
    try:
        security_service = create_security_service(db)
        policies = await security_service.get_security_policies(tenant.id)
        
        return policies
        
    except Exception as e:
        logger.error(f"Failed to get security policies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get security policies")

@router.get("/security/dashboard", response_model=Dict[str, Any])
async def get_security_dashboard(
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Get security dashboard data"""
    try:
        security_service = create_security_service(db)
        dashboard_data = await security_service.get_security_dashboard_data(tenant.id)
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Failed to get security dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get security dashboard data")

@router.delete("/security/certificate/{certificate_id}", response_model=Dict[str, str])
async def revoke_certificate(
    certificate_id: str,
    reason: str = "unspecified",
    tenant=Depends(require_tenant),
    db: Session = Depends(get_db)
):
    """Revoke an extension certificate"""
    try:
        security_service = create_security_service(db)
        success = await security_service.revoke_certificate(certificate_id, tenant.id, reason)
        
        if success:
            await metrics_collector.increment(
                metric_type=MetricType.COUNTER,
                amount=1,
                unit="extensions_certificates_revoked",
                tags={"reason": reason}
            )
            return {"status": "success", "message": "Certificate revoked"}
        else:
            raise HTTPException(status_code=404, detail="Certificate not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke certificate")

# Helper functions

class CIFixerRequest(BaseModel):
    """Request to run CI failure fixer extension"""
    project_name: str
    repo_url: Optional[str] = None
    ci_provider: str = "github"

class CIFixerResult(BaseModel):
    """CI failure fixer result"""
    success: bool
    message: str
    requires_approval: bool
    proposal: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None
    execution_id: str
    execution_time: float

@router.post("/ci-fixer/execute", response_model=CIFixerResult)
async def execute_ci_fixer(
    request: CIFixerRequest,
    tenant=Depends(require_tenant)
):
    """Execute CI failure fixer extension with mock TypeScript invocation"""
    start_time = datetime.utcnow()
    try:
        execution_id = str(uuid.uuid4())
        
        # Mock extension context that would be passed to TypeScript extension
        {
            "project": {
                "name": request.project_name,
                "path": f"/workspace/{request.project_name}",
                "repoUrl": request.repo_url
            },
            "user": {
                "id": tenant.user_id if hasattr(tenant, 'user_id') else "test-user",
                "name": "Test User",
                "permissions": ["CI_READ", "REPO_READ", "PROPOSE_CODE_CHANGES", "REQUEST_APPROVAL"]
            },
            "ci": {
                "provider": request.ci_provider,
                "apiUrl": "https://api.github.com",
                "accessToken": "mock-token"
            },
            "navi": {
                "apiUrl": "http://localhost:8787",
                "version": "1.0.0"
            }
        }
        
        # In a real implementation, this would invoke the TypeScript extension
        # For now, we'll simulate the extension's behavior
        
        # Step 1: Mock fetching CI failure (would call /api/ci/failures/latest)
        mock_failure = {
            "job": "build",
            "step": "install-dependencies",
            "error_message": "npm ERR! Cannot resolve dependency \"react-nonexistent-lib\"",
            "log_snippet": "npm ERR! Cannot resolve dependency \"react-nonexistent-lib\"\\nnpm ERR! Could not resolve dependency:",
            "file_path": "package.json",
            "line_number": 15,
            "failure_type": "DEPENDENCY",
            "logs": "npm install logs with dependency error"
        }
        
        # Step 2: Mock analysis and classification
        failure_type = "DEPENDENCY"
        confidence = 0.85
        
        # Step 3: Mock fix proposal generation
        mock_proposal = {
            "summary": "Install missing dependency: react-nonexistent-lib",
            "changes": [
                {
                    "filePath": "package.json",
                    "action": "update",
                    "reason": "Install missing dependency: react-nonexistent-lib",
                    "diff": '+ "react-nonexistent-lib": "latest" // Auto-install missing dependency'
                }
            ],
            "confidence": confidence,
            "rollback": True,
            "riskLevel": "medium"
        }
        
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Record metrics
        await metrics_collector.record_metric(
            MetricType.EXTENSIONS_EXECUTED,
            1.0,
            "count",
            tags={
                "extension": "navi-ci-failure-fixer",
                "failure_type": failure_type,
                "success": "true",
                "org_id": tenant.org_id
            }
        )
        
        return CIFixerResult(
            success=True,
            message=f"🔧 CI failed due to {failure_type}. Fix proposal ready for approval.",
            requires_approval=True,
            proposal=mock_proposal,
            details={
                "failureType": failure_type,
                "errorMessage": mock_failure["error_message"],
                "affectedFiles": ["package.json"],
                "confidence": confidence
            },
            execution_id=execution_id,
            execution_time=execution_time
        )
        
    except Exception as e:
        logger.error(f"CI Failure Fixer execution failed: {str(e)}")
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return CIFixerResult(
            success=False,
            message=f"❌ Extension execution failed: {str(e)}",
            requires_approval=False,
            execution_id=str(uuid.uuid4()),
            execution_time=execution_time
        )

async def _mock_extension_review_workflow(extension_id: str):
    """Mock extension review workflow (background task)"""
    try:
        # Simulate review process
        await asyncio.sleep(5)  # Mock review time
        
        extension_repo = ExtensionRepository()
        manifest = await extension_repo.get_extension(extension_id)
        
        if manifest:
            # Auto-approve for demo (in production would have actual review)
            manifest.state = ExtensionLifecycleState.APPROVED
            await extension_repo.update_extension(manifest)
            
            logger.info(f"Extension {extension_id} approved after review")
        
    except Exception as e:
        logger.error(f"Review workflow failed for {extension_id}: {str(e)}")

# Note: PermissionManager import moved to function level to avoid circular imports

__all__ = ["router"]
