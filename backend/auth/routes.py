"""
Example protected routes demonstrating Auth0 JWT validation

These routes show how to use the auth guards:
- /api/me - requires valid JWT token
- /api/admin - requires admin role
- /api/healthz - public endpoint (no auth required)
"""
from fastapi import APIRouter, Depends
from backend.auth.auth0 import require_auth, require_role

router = APIRouter()

@router.get("/api/healthz")
async def healthz():
    """Public health check endpoint"""
    return {"ok": True, "auth_domain": "auth.navralabs.com"}

@router.get("/api/me")
async def me(claims = Depends(require_auth)):
    """Protected endpoint - requires valid JWT"""
    return {
        "sub": claims.get("sub"), 
        "email": claims.get("email"),
        "org_id": claims.get("org_id"),
        "permissions": claims.get("permissions", [])
    }

@router.get("/api/admin")
async def admin_only(claims = Depends(require_role("admin"))):
    """Admin-only endpoint - requires admin role"""
    return {
        "admin": True, 
        "sub": claims.get("sub"),
        "message": "Welcome to admin area!"
    }

@router.get("/api/user-profile")
async def user_profile(claims = Depends(require_auth)):
    """User profile endpoint - extracts user info from JWT"""
    return {
        "user_id": claims.get("sub"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "picture": claims.get("picture"),
        "email_verified": claims.get("email_verified"),
        "roles": claims.get("https://navralabs.com/roles", []),
        "permissions": claims.get("permissions", [])
    }