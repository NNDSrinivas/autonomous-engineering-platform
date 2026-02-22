"""
Preview API Router - Static preview endpoints.

Endpoints:
- POST /api/preview/static - Store static HTML
- GET /api/preview/{preview_id} - Retrieve preview
- DELETE /api/preview/{preview_id} - Delete preview

Security:
- ALL endpoints require authentication (VIEWER role)
- Restrictive CSP headers to prevent data exfiltration
- No scripts by default (script-src 'none')
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Literal

from backend.core.auth.deps import require_role
from backend.core.auth.models import Role

router = APIRouter(prefix="/api/preview", tags=["preview"])


class StorePreviewRequest(BaseModel):
    """Request to store static preview content."""

    content: str
    content_type: Literal["html", "markdown"] = "html"


class StorePreviewResponse(BaseModel):
    """Response with preview ID and URL."""

    preview_id: str
    url: str


@router.post("/static", response_model=StorePreviewResponse)
async def store_static_preview(
    body: StorePreviewRequest,
    request: Request,
    user=Depends(require_role(Role.VIEWER)),
):
    """
    Store static HTML/markdown preview content.

    Returns preview ID and retrieval URL.

    Security:
    - Requires authentication (VIEWER role)
    - Content is NOT sanitized (trusted from NAVI)
    - Preview retrieval also requires auth (no public access)
    """
    # Get PreviewService singleton from app state
    preview_service = request.app.state.preview_service

    preview_id = await preview_service.store(
        content=body.content,
        content_type=body.content_type,
    )

    return StorePreviewResponse(
        preview_id=preview_id,
        url=f"/api/preview/{preview_id}",
    )


@router.get("/{preview_id}")
async def get_preview(
    preview_id: str,
    request: Request,
    user=Depends(require_role(Role.VIEWER)),
):
    """
    Retrieve preview content by ID.

    Returns HTML response with restrictive security headers.

    Security:
    - Requires authentication (VIEWER role) - NO public access
    - UUIDs can leak via referrer/logs/screenshots
    - Content-Security-Policy: script-src 'none' (no scripts by default)
    - Cross-Origin-Resource-Policy: same-site
    - Cache-Control: no-store
    """
    # Get PreviewService singleton from app state
    preview_service = request.app.state.preview_service

    preview = await preview_service.get(preview_id)

    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found or expired")

    # Return HTML with restrictive security headers
    # Goal: HTML can render styles/images, but NO scripts and cannot exfiltrate data
    return HTMLResponse(
        content=preview.content,
        headers={
            # Restrictive CSP: default deny, allow only safe inline styles/images
            "Content-Security-Policy": (
                "default-src 'none'; "
                "style-src 'unsafe-inline'; "
                "img-src data: https:; "
                "font-src data: https:; "
                "script-src 'none'; "
                "connect-src 'none'; "
                "frame-ancestors 'self';"
            ),
            # Additional security headers
            "Cross-Origin-Resource-Policy": "same-site",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{preview_id}")
async def delete_preview(
    preview_id: str,
    request: Request,
    user=Depends(require_role(Role.VIEWER)),
):
    """Delete preview by ID (requires auth)."""
    # Get PreviewService singleton from app state
    preview_service = request.app.state.preview_service

    success = await preview_service.delete(preview_id)

    if not success:
        raise HTTPException(status_code=404, detail="Preview not found")

    return {"success": True, "preview_id": preview_id}
