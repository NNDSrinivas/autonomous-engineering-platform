"""
Admin RBAC endpoints for managing organizations, users, and role assignments.

All endpoints require admin role and are intended for administrative
user management workflows.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.auth.role_service import invalidate_role_cache
from backend.database.models.rbac import DBRole, DBUser, Organization, UserRole

router = APIRouter(prefix="/api/admin/rbac", tags=["admin-rbac"])


# --- Request/Response Schemas ---


class OrgCreate(BaseModel):
    """Request body for creating an organization."""

    org_key: str = Field(
        ..., min_length=2, max_length=64, description="Unique organization key"
    )
    name: str = Field(..., description="Human-readable organization name")


class OrgResponse(BaseModel):
    """Organization response model."""

    id: int
    org_key: str
    name: str


class UserUpsert(BaseModel):
    """Request body for creating or updating a user."""

    sub: str = Field(..., description="JWT subject claim (stable user ID)")
    email: str = Field(..., description="User email address")
    display_name: Optional[str] = Field(None, description="User display name")
    org_key: str = Field(..., description="Organization key to assign user to")


class UserResponse(BaseModel):
    """User response model."""

    id: int
    sub: str
    email: str
    display_name: Optional[str]
    org_id: int


class RoleGrant(BaseModel):
    """Request body for granting a role to a user."""

    sub: str = Field(..., description="User's JWT subject")
    org_key: str = Field(..., description="Organization key")
    role: Literal["viewer", "planner", "admin"] = Field(
        ..., description="Role to grant"
    )
    project_key: Optional[str] = Field(
        None, description="Optional project key for scoped role (None = org-wide)"
    )


class RoleGrantResponse(BaseModel):
    """Role grant operation response."""

    ok: bool
    granted: bool  # False if already existed


class RoleAssignment(BaseModel):
    """Individual role assignment."""

    role: str
    project_key: Optional[str]


class UserDetailResponse(BaseModel):
    """Detailed user information including role assignments."""

    sub: str
    email: str
    display_name: Optional[str]
    org_key: str
    roles: list[RoleAssignment]


# --- Organization Endpoints ---


@router.post("/orgs", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Create a new organization.

    Requires admin role.

    Args:
        body: Organization creation data
        db: Database session
        _: Current user (admin check)

    Returns:
        Created organization details

    Raises:
        HTTPException 409: If org_key already exists
    """
    exists = db.query(Organization).filter_by(org_key=body.org_key).one_or_none()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="org_key already exists"
        )

    org = Organization(org_key=body.org_key, name=body.name)
    db.add(org)
    db.commit()
    db.refresh(org)

    return OrgResponse(id=org.id, org_key=org.org_key, name=org.name)


@router.get("/orgs", response_model=list[OrgResponse])
def list_orgs(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    List all organizations.

    Requires admin role.

    Args:
        db: Database session
        _: Current user (admin check)

    Returns:
        List of all organizations
    """
    orgs = db.query(Organization).all()
    return [OrgResponse(id=o.id, org_key=o.org_key, name=o.name) for o in orgs]


# --- User Endpoints ---


@router.post("/users", response_model=UserResponse)
def upsert_user(
    body: UserUpsert,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Create or update a user record.

    Links a JWT subject to an organization. If user already exists,
    updates email and display_name.

    Requires admin role.

    Args:
        body: User data
        db: Database session
        _: Current user (admin check)

    Returns:
        User details

    Raises:
        HTTPException 404: If organization not found
    """
    org = db.query(Organization).filter_by(org_key=body.org_key).one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    user = db.query(DBUser).filter_by(sub=body.sub, org_id=org.id).one_or_none()
    if not user:
        user = DBUser(
            sub=body.sub,
            email=body.email,
            display_name=body.display_name,
            org_id=org.id,
        )
        db.add(user)
    else:
        user.email = body.email
        user.display_name = body.display_name

    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        sub=user.sub,
        email=user.email,
        display_name=user.display_name,
        org_id=user.org_id,
    )


@router.get("/users/{org_key}/{sub}", response_model=UserDetailResponse)
def get_user(
    org_key: str,
    sub: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Get user details including all role assignments.

    Requires admin role.

    Args:
        org_key: Organization key
        sub: User's JWT subject
        db: Database session
        _: Current user (admin check)

    Returns:
        User details with role assignments

    Raises:
        HTTPException 404: If organization or user not found
    """
    org = db.query(Organization).filter_by(org_key=org_key).one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    user = db.query(DBUser).filter_by(sub=sub, org_id=org.id).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in organization",
        )

    # Fetch all role assignments
    roles = (
        db.query(DBRole.name, UserRole.project_key)
        .join(UserRole, UserRole.role_id == DBRole.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )

    return UserDetailResponse(
        sub=user.sub,
        email=user.email,
        display_name=user.display_name,
        org_key=org.org_key,
        roles=[
            RoleAssignment(role=role_name, project_key=proj_key)
            for role_name, proj_key in roles
        ],
    )


# --- Role Assignment Endpoints ---


@router.post("/roles/grant", response_model=RoleGrantResponse)
async def grant_role(
    body: RoleGrant,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Grant a role to a user (org-wide or project-scoped).

    Note: This function is async because it calls invalidate_role_cache (async),
    even though database operations are synchronous. FastAPI handles this correctly
    by running sync dependencies (like get_db) in a threadpool. This pattern may not
    be portable to other async frameworks without similar threadpool handling.

    Requires admin role.

    Args:
        body: Role grant data
        db: Database session
        _: Current user (admin check)

    Returns:
        Grant operation result

    Raises:
        HTTPException 404: If organization or user not found
        HTTPException 400: If role name is invalid
    """
    org = db.query(Organization).filter_by(org_key=body.org_key).one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    user = db.query(DBUser).filter_by(sub=body.sub, org_id=org.id).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in organization",
        )

    role = db.query(DBRole).filter_by(name=body.role).one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role name"
        )

    # Check if assignment already exists
    exists = (
        db.query(UserRole)
        .filter_by(user_id=user.id, role_id=role.id, project_key=body.project_key)
        .one_or_none()
    )

    if exists:
        return RoleGrantResponse(ok=True, granted=False)

    # Create new role assignment
    db.add(UserRole(user_id=user.id, role_id=role.id, project_key=body.project_key))
    db.commit()

    # Invalidate cache for this user
    await invalidate_role_cache(body.org_key, body.sub)

    return RoleGrantResponse(ok=True, granted=True)


@router.delete("/roles/revoke")
async def revoke_role(
    body: RoleGrant,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Revoke a role from a user.

    Note: This function is async because it calls invalidate_role_cache (async),
    even though database operations are synchronous. FastAPI handles this correctly
    by running sync dependencies (like get_db) in a threadpool. This pattern may not
    be portable to other async frameworks without similar threadpool handling.

    Requires admin role.

    Args:
        body: Role revoke data (same format as grant)
        db: Database session
        _: Current user (admin check)

    Returns:
        Revoke operation result

    Raises:
        HTTPException 404: If role assignment not found
    """
    org = db.query(Organization).filter_by(org_key=body.org_key).one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    user = db.query(DBUser).filter_by(sub=body.sub, org_id=org.id).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in organization",
        )

    role = db.query(DBRole).filter_by(name=body.role).one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role name"
        )

    # Find and delete the assignment
    assignment = (
        db.query(UserRole)
        .filter_by(user_id=user.id, role_id=role.id, project_key=body.project_key)
        .one_or_none()
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    db.delete(assignment)
    db.commit()

    # Invalidate cache for this user
    await invalidate_role_cache(body.org_key, body.sub)

    return {"ok": True, "revoked": True}
