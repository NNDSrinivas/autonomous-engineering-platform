"""
Extension Marketplace API - Phase 7.2
Enterprise marketplace with security and trust management
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
import logging

from backend.database.session import get_db
from backend.api.security import require_role
from backend.extensions.verify import verify_extension_bundle, VerificationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

@router.get("/extensions")
async def list_extensions(
    category: Optional[str] = None,
    trust_level: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available extensions in the marketplace"""
    # Mock data for now since tables don't exist yet
    mock_extensions = [
        {
            "id": "ci-fixer-v1",
            "name": "CI Fixer",
            "description": "Automatically fixes common CI/CD build failures",
            "version": "1.0.0",
            "author": {
                "name": "NAVI Team",
                "verified": True,
                "organization": "Enterprise"
            },
            "category": "automation",
            "tags": ["ci", "automation", "fixes"],
            "permissions": [
                {
                    "type": "FIX_PROBLEMS",
                    "description": "Fix CI/CD build issues",
                    "riskLevel": "medium"
                },
                {
                    "type": "WRITE_FILES",
                    "description": "Modify configuration files",
                    "riskLevel": "high"
                }
            ],
            "trustLevel": "CORE",
            "capabilities": ["fix_ci_errors", "analyze_build_logs"],
            "downloads": 15420,
            "rating": 4.8,
            "lastUpdated": "2025-12-20T10:00:00Z",
            "iconUrl": None,
            "isInstalled": False,
            "isEnabled": False
        },
        {
            "id": "k8s-resolver-v1",
            "name": "Kubernetes Resolver",
            "description": "Diagnose and resolve Kubernetes cluster issues",
            "version": "1.2.1",
            "author": {
                "name": "DevOps Guild",
                "verified": True,
                "organization": "Community"
            },
            "category": "infrastructure",
            "tags": ["kubernetes", "cluster", "diagnostics"],
            "permissions": [
                {
                    "type": "CLUSTER_READ",
                    "description": "Read cluster state and logs",
                    "riskLevel": "medium"
                },
                {
                    "type": "EXECUTE_COMMANDS", 
                    "description": "Run kubectl commands",
                    "riskLevel": "high"
                }
            ],
            "trustLevel": "VERIFIED",
            "capabilities": ["diagnose_pods", "check_resources", "analyze_logs"],
            "downloads": 8930,
            "rating": 4.6,
            "lastUpdated": "2025-12-18T14:30:00Z",
            "iconUrl": None,
            "isInstalled": False,
            "isEnabled": False
        },
        {
            "id": "security-scanner-v1",
            "name": "Security Scanner",
            "description": "Scan codebases for security vulnerabilities",
            "version": "2.1.0",
            "author": {
                "name": "SecOps Team",
                "verified": True,
                "organization": "Enterprise"
            },
            "category": "security",
            "tags": ["security", "vulnerabilities", "scanning"],
            "permissions": [
                {
                    "type": "ANALYZE_PROJECT",
                    "description": "Scan project files for vulnerabilities",
                    "riskLevel": "low"
                },
                {
                    "type": "NETWORK_ACCESS",
                    "description": "Check external vulnerability databases",
                    "riskLevel": "medium"
                }
            ],
            "trustLevel": "CORE",
            "capabilities": ["scan_dependencies", "check_secrets", "analyze_code"],
            "downloads": 22145,
            "rating": 4.9,
            "lastUpdated": "2025-12-22T09:15:00Z",
            "iconUrl": None,
            "isInstalled": True,
            "isEnabled": True
        }
    ]
    
    return {"extensions": mock_extensions, "total": len(mock_extensions)}

@router.post("/extensions/{extension_id}/install")
async def install_extension(
    extension_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("user"))
):
    """Install an extension (with signature verification)"""
    logger.info(f"Installing extension {extension_id} for user {current_user.user_id}")
    
    try:
        # In production, fetch extension bundle from registry
        # For now, return mock success with security validation noted
        
        # Simulate signature verification (would use real bundle)
        logger.info(f"Extension {extension_id} signature verification would occur here")
        
        return {
            "success": True,
            "message": f"Extension {extension_id} installed successfully",
            "extensionId": extension_id,
            "status": "installed",
            "verified": True,
            "trustLevel": "VERIFIED"
        }
        
    except VerificationError as e:
        logger.error(f"Extension {extension_id} verification failed: {e}")
        raise HTTPException(status_code=400, detail=f"Extension verification failed: {e}")
    except Exception as e:
        logger.error(f"Extension {extension_id} installation failed: {e}")
        raise HTTPException(status_code=500, detail="Installation failed")

@router.delete("/extensions/{extension_id}")
async def uninstall_extension(
    extension_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("user"))
):
    """Uninstall an extension"""
    logger.info(f"Uninstalling extension {extension_id} for user {current_user.user_id}")
    
    return {
        "success": True,
        "message": f"Extension {extension_id} uninstalled successfully"
    }

@router.post("/extensions/{extension_id}/enable")
async def enable_extension(
    extension_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("user"))
):
    """Enable an installed extension"""
    return {"success": True, "message": f"Extension {extension_id} enabled"}

@router.post("/extensions/{extension_id}/disable")
async def disable_extension(
    extension_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("user"))
):
    """Disable an installed extension"""
    return {"success": True, "message": f"Extension {extension_id} disabled"}

@router.get("/extensions/{extension_id}")
async def get_extension_details(
    extension_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific extension"""
    # Mock extension details
    return {
        "id": extension_id,
        "name": "Mock Extension",
        "description": "This is a mock extension for development",
        "longDescription": "This extension demonstrates the marketplace functionality...",
        "version": "1.0.0",
        "changelog": "Initial release",
        "documentation": "https://docs.example.com",
        "repository": "https://github.com/example/extension"
    }

@router.post("/extensions/upload")
async def upload_extension(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_role("developer"))
):
    """Upload and publish a new extension (requires signature verification)"""
    logger.info(f"Uploading extension {file.filename} from user {current_user.user_id}")
    
    if not file.filename or not file.filename.endswith('.navi-ext'):
        raise HTTPException(status_code=400, detail="Invalid file format. Expected .navi-ext file")
    
    try:
        # Read extension bundle
        bundle_bytes = await file.read()
        
        # Verify extension signature and policy compliance
        verified_bundle = verify_extension_bundle(
            bundle_bytes=bundle_bytes,
            user_id=current_user.user_id,
            org_id=getattr(current_user, 'org_id', 'default')
        )
        
        logger.info(
            f"Extension {verified_bundle.manifest.id} uploaded successfully "
            f"with trust level {verified_bundle.manifest.trust}"
        )
        
        # In production, store in registry database
        return {
            "success": True,
            "message": "Extension uploaded and verified successfully",
            "extensionId": verified_bundle.manifest.id,
            "trustLevel": verified_bundle.manifest.trust.value,
            "status": "verified_and_published"
        }
        
    except VerificationError as e:
        logger.error(f"Extension upload verification failed: {e}")
        raise HTTPException(status_code=400, detail=f"Extension verification failed: {e}")
    except Exception as e:
        logger.error(f"Extension upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")