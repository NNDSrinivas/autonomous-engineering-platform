"""
Role resolution service for merging JWT and database-backed role assignments.

Determines effective user role by combining:
1. JWT role claim (from SSO/authentication provider)
2. Database role assignments (org-wide or project-scoped)

The highest role wins: admin > planner > viewer
"""

from typing import Literal, Optional, cast

from sqlalchemy.orm import Session

from backend.database.models.rbac import DBRole, DBUser, Organization, UserRole
from backend.infra.cache.redis_cache import cache

RoleName = Literal["viewer", "planner", "admin"]

# Role hierarchy ranking
ROLE_RANK = {"viewer": 0, "planner": 1, "admin": 2}


def _max_role(a: RoleName, b: RoleName) -> RoleName:
    """
    Return the higher-ranked role between two roles.

    Args:
        a: First role
        b: Second role

    Returns:
        The role with higher rank (admin > planner > viewer)
    """
    return a if ROLE_RANK[a] >= ROLE_RANK[b] else b


async def resolve_effective_role(
    session: Session, sub: str, org_key: str, jwt_role: RoleName
) -> RoleName:
    """
    Resolve effective role by merging JWT claim with database assignments.

    Process:
    1. Check cache for recent resolution
    2. Look up user in specified organization
    3. Query all role assignments for the user
    4. Compute max role from DB assignments
    5. Return max(JWT role, DB role)
    6. Cache result for 60 seconds

    Args:
        session: Database session
        sub: User's JWT subject claim (stable identifier)
        org_key: Organization key (e.g., 'navralabs')
        jwt_role: Role claim from JWT token

    Returns:
        Effective role (highest of JWT vs DB roles)

    Note:
        If org or user doesn't exist in DB, returns jwt_role as fallback.
        Project-scoped roles are included in max computation.
    """
    cache_key = f"role:{org_key}:{sub}"

    # Check cache first
    cached = await cache.get_json(cache_key)
    if cached:
        cached_role = cached.get("role")
        if cached_role and cached_role in ROLE_RANK:
            # Explicitly cast validated cached role for type consistency
            cached_role_typed = cast(RoleName, cached_role)
            return _max_role(jwt_role, cached_role_typed)
        # Cache corrupted or invalid - fall through to DB lookup

    # Look up organization
    org = session.query(Organization).filter_by(org_key=org_key).one_or_none()
    if not org:
        # No org in DB - could auto-create or just return JWT role
        return jwt_role

    # Look up user in this org
    user = session.query(DBUser).filter_by(sub=sub, org_id=org.id).one_or_none()
    if not user:
        # No user record - fallback to JWT role
        # Could auto-provision user here if desired
        return jwt_role

    # Query all DB role assignments for this user
    role_assignments = (
        session.query(DBRole.name)
        .join(UserRole, UserRole.role_id == DBRole.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )

    # If no DB role assignments, return JWT role directly
    # This ensures JWT is the single source of truth when DB roles are absent
    if not role_assignments:
        return jwt_role

    # Compute maximum role from all DB assignments
    # Initialize with None and only set when we find a valid role
    max_db_role: Optional[RoleName] = None

    for (role_name,) in role_assignments:
        # Validate role is in hierarchy before casting to RoleName type
        if role_name in ROLE_RANK:
            validated_role: RoleName = role_name  # Explicitly cast after validation
            if max_db_role is None:
                max_db_role = validated_role
            else:
                max_db_role = _max_role(max_db_role, validated_role)
        else:
            # Skip invalid role names from DB (e.g., from manual insertion or migration errors)
            continue

    # If no valid roles found in DB, fallback to JWT role
    if max_db_role is None:
        return jwt_role

    # Cache the DB result
    await cache.set_json(cache_key, {"role": max_db_role}, ttl_sec=60)

    # Return highest of JWT vs DB
    return _max_role(jwt_role, max_db_role)


async def invalidate_role_cache(org_key: str, sub: str) -> None:
    """
    Invalidate cached role for a user.

    Call this after modifying user role assignments to ensure
    next request fetches fresh data.

    Args:
        org_key: Organization key
        sub: User's JWT subject
    """
    cache_key = f"role:{org_key}:{sub}"
    await cache.delete(cache_key)
