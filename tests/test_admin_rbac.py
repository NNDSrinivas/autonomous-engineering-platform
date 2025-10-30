"""
Tests for Admin RBAC endpoints and role resolution service.

Tests cover:
- Organization CRUD operations
- User management (create/update)
- Role assignment and revocation
- Effective role resolution (JWT + DB merge)
- Cache invalidation
"""

import json
import os
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.api.main import app
from backend.core.db import Base
from backend.database.models.rbac import DBRole, DBUser, Organization, UserRole
from backend.database.session import get_db

# Test database setup - each test gets a unique database
# Unique identifier prevents cross-test contamination


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    # Generate a unique DB ID and engine per test function
    test_db_id = uuid.uuid4().hex[:8]
    test_database_url = (
        f"sqlite:///file:memdb_rbac_{test_db_id}?mode=memory&cache=shared"
    )
    engine = create_engine(test_database_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    # Clear in-memory cache before each test
    from backend.infra.cache.redis_cache import cache

    cache.clear_sync()

    # Seed roles
    session = TestingSessionLocal()
    try:
        for role_name in ["viewer", "planner", "admin"]:
            if not session.query(DBRole).filter_by(name=role_name).first():
                session.add(DBRole(name=role_name))
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """Create a test client with database override."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Use dev auth mode for tests
    os.environ["JWT_ENABLED"] = "false"
    os.environ["DEV_USER_ROLE"] = "admin"
    os.environ["DEV_USER_ID"] = "test-admin"

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestOrganizations:
    """Test organization management endpoints."""

    def test_create_org(self, client: TestClient):
        """Test creating a new organization."""
        response = client.post(
            "/api/admin/rbac/orgs",
            json={"org_key": "navra", "name": "Navra Labs"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["org_key"] == "navra"
        assert data["name"] == "Navra Labs"
        assert "id" in data

    def test_create_org_duplicate_key(self, client: TestClient, db: Session):
        """Test that duplicate org_key is rejected."""
        # Create first org
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        # Attempt duplicate
        response = client.post(
            "/api/admin/rbac/orgs",
            json={"org_key": "navra", "name": "Different Name"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_list_orgs(self, client: TestClient, db: Session):
        """Test listing all organizations."""
        # Create test orgs
        db.add(Organization(org_key="org1", name="Org One"))
        db.add(Organization(org_key="org2", name="Org Two"))
        db.commit()

        response = client.get("/api/admin/rbac/orgs")
        assert response.status_code == 200
        orgs = response.json()
        assert len(orgs) == 2
        assert any(o["org_key"] == "org1" for o in orgs)
        assert any(o["org_key"] == "org2" for o in orgs)


class TestUsers:
    """Test user management endpoints."""

    def test_upsert_user_create(self, client: TestClient, db: Session):
        """Test creating a new user."""
        # Create org first
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        response = client.post(
            "/api/admin/rbac/users",
            json={
                "sub": "user-123",
                "email": "user@navra.io",
                "display_name": "Test User",
                "org_key": "navra",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sub"] == "user-123"
        assert data["email"] == "user@navra.io"
        assert data["display_name"] == "Test User"

    def test_upsert_user_update(self, client: TestClient, db: Session):
        """Test updating an existing user."""
        # Create org and user
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123",
            email="old@navra.io",
            display_name="Old Name",
            org_id=org.id,
        )
        db.add(user)
        db.commit()

        # Update user
        response = client.post(
            "/api/admin/rbac/users",
            json={
                "sub": "user-123",
                "email": "new@navra.io",
                "display_name": "New Name",
                "org_key": "navra",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@navra.io"
        assert data["display_name"] == "New Name"

    def test_upsert_user_org_not_found(self, client: TestClient):
        """Test that missing org returns 404."""
        response = client.post(
            "/api/admin/rbac/users",
            json={
                "sub": "user-123",
                "email": "user@example.com",
                "display_name": "Test",
                "org_key": "nonexistent",
            },
        )
        assert response.status_code == 404

    def test_get_user_detail(self, client: TestClient, db: Session):
        """Test getting user details with role assignments."""
        # Setup org, user, and roles
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123",
            email="user@navra.io",
            display_name="Test User",
            org_id=org.id,
        )
        db.add(user)
        db.commit()

        # Grant roles
        planner_role = db.query(DBRole).filter_by(name="planner").first()
        admin_role = db.query(DBRole).filter_by(name="admin").first()

        db.add(UserRole(user_id=user.id, role_id=planner_role.id, project_key="proj-1"))
        db.add(UserRole(user_id=user.id, role_id=admin_role.id, project_key=None))
        db.commit()

        # Get user detail
        response = client.get("/api/admin/rbac/users/navra/user-123")
        assert response.status_code == 200
        data = response.json()
        assert data["sub"] == "user-123"
        assert len(data["roles"]) == 2

        # Check role assignments
        # Use explicit assertions for clearer failure messages when tests fail
        assert any(
            r["role"] == "planner" and r["project_key"] == "proj-1"
            for r in data["roles"]
        ), "Expected planner role with project_key 'proj-1'"
        assert any(
            r["role"] == "admin" and r["project_key"] is None for r in data["roles"]
        ), "Expected admin role with no project_key"


class TestRoleAssignments:
    """Test role grant and revoke operations."""

    def test_grant_role(self, client: TestClient, db: Session):
        """Test granting a role to a user."""
        # Setup
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        # Grant role
        response = client.post(
            "/api/admin/rbac/roles/grant",
            json={
                "sub": "user-123",
                "org_key": "navra",
                "role": "planner",
                "project_key": None,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["granted"] is True

        # Verify in DB
        planner_role = db.query(DBRole).filter_by(name="planner").first()
        assignment = (
            db.query(UserRole)
            .filter_by(user_id=user.id, role_id=planner_role.id, project_key=None)
            .first()
        )
        assert assignment is not None

    def test_grant_role_idempotent(self, client: TestClient, db: Session):
        """Test that granting same role twice is idempotent."""
        # Setup
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        # First grant
        client.post(
            "/api/admin/rbac/roles/grant",
            json={"sub": "user-123", "org_key": "navra", "role": "planner"},
        )

        # Second grant (should not error, but granted=False)
        response = client.post(
            "/api/admin/rbac/roles/grant",
            json={"sub": "user-123", "org_key": "navra", "role": "planner"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["granted"] is False

    def test_grant_role_project_scoped(self, client: TestClient, db: Session):
        """Test granting a project-scoped role."""
        # Setup
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        # Grant project-scoped role
        response = client.post(
            "/api/admin/rbac/roles/grant",
            json={
                "sub": "user-123",
                "org_key": "navra",
                "role": "admin",
                "project_key": "my-project",
            },
        )
        assert response.status_code == 200
        assert response.json()["granted"] is True

        # Verify scope in DB
        admin_role = db.query(DBRole).filter_by(name="admin").first()
        assignment = (
            db.query(UserRole)
            .filter_by(user_id=user.id, role_id=admin_role.id, project_key="my-project")
            .first()
        )
        assert assignment is not None

    def test_revoke_role(self, client: TestClient, db: Session):
        """Test revoking a role from a user."""
        # Setup with existing role
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        planner_role = db.query(DBRole).filter_by(name="planner").first()
        db.add(UserRole(user_id=user.id, role_id=planner_role.id, project_key=None))
        db.commit()

        # Revoke role
        response = client.request(
            method="DELETE",
            url="/api/admin/rbac/roles/revoke",
            content=json.dumps(
                {
                    "sub": "user-123",
                    "org_key": "navra",
                    "role": "planner",
                    "project_key": None,
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["revoked"] is True

        # Verify removed from DB
        assignment = (
            db.query(UserRole)
            .filter_by(user_id=user.id, role_id=planner_role.id)
            .first()
        )
        assert assignment is None


class TestRoleResolution:
    """Test effective role resolution logic."""

    @pytest.mark.asyncio
    async def test_resolve_effective_role_jwt_only(self, db: Session):
        """Test role resolution with JWT role only (no DB records)."""
        from backend.core.auth.role_service import resolve_effective_role

        # No org or user in DB
        role = await resolve_effective_role(
            db, sub="user-123", org_key="navra", jwt_role="planner"
        )
        assert role == "planner"

    @pytest.mark.asyncio
    async def test_resolve_effective_role_db_higher(self, db: Session):
        """Test that DB role wins when higher than JWT."""
        from backend.core.auth.role_service import resolve_effective_role

        # Setup org and user with admin role
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        admin_role = db.query(DBRole).filter_by(name="admin").first()
        db.add(UserRole(user_id=user.id, role_id=admin_role.id, project_key=None))
        db.commit()

        # JWT says viewer, DB says admin -> admin wins
        role = await resolve_effective_role(
            db, sub="user-123", org_key="navra", jwt_role="viewer"
        )
        assert role == "admin"

    @pytest.mark.asyncio
    async def test_resolve_effective_role_jwt_higher(self, db: Session):
        """Test that JWT role wins when higher than DB."""
        from backend.core.auth.role_service import resolve_effective_role

        # Setup org and user with viewer role
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        viewer_role = db.query(DBRole).filter_by(name="viewer").first()
        db.add(UserRole(user_id=user.id, role_id=viewer_role.id, project_key=None))
        db.commit()

        # JWT says admin, DB says viewer -> admin wins
        role = await resolve_effective_role(
            db, sub="user-123", org_key="navra", jwt_role="admin"
        )
        assert role == "admin"

    @pytest.mark.asyncio
    async def test_resolve_effective_role_multiple_db_roles(self, db: Session):
        """Test role resolution with multiple DB role assignments."""
        from backend.core.auth.role_service import resolve_effective_role

        # Setup org and user with multiple roles
        org = Organization(org_key="navra", name="Navra Labs")
        db.add(org)
        db.commit()

        user = DBUser(
            sub="user-123", email="user@navra.io", display_name="Test", org_id=org.id
        )
        db.add(user)
        db.commit()

        # Grant viewer and planner roles
        viewer_role = db.query(DBRole).filter_by(name="viewer").first()
        planner_role = db.query(DBRole).filter_by(name="planner").first()
        db.add(UserRole(user_id=user.id, role_id=viewer_role.id, project_key="proj-1"))
        db.add(UserRole(user_id=user.id, role_id=planner_role.id, project_key="proj-2"))
        db.commit()

        # Should resolve to highest DB role (planner)
        role = await resolve_effective_role(
            db, sub="user-123", org_key="navra", jwt_role="viewer"
        )
        assert role == "planner"


class TestFullAdminFlow:
    """Integration test for complete admin workflow."""

    def test_complete_admin_workflow(self, client: TestClient):
        """Test end-to-end admin RBAC workflow."""
        # 1. Create organization
        response = client.post(
            "/api/admin/rbac/orgs",
            json={"org_key": "navra", "name": "Navra Labs"},
        )
        assert response.status_code == 201

        # 2. Create user
        response = client.post(
            "/api/admin/rbac/users",
            json={
                "sub": "user-123",
                "email": "user@navra.io",
                "display_name": "Test User",
                "org_key": "navra",
            },
        )
        assert response.status_code == 200

        # 3. Grant planner role
        response = client.post(
            "/api/admin/rbac/roles/grant",
            json={
                "sub": "user-123",
                "org_key": "navra",
                "role": "planner",
                "project_key": None,
            },
        )
        assert response.status_code == 200
        assert response.json()["granted"] is True

        # 4. Grant project-scoped admin role
        response = client.post(
            "/api/admin/rbac/roles/grant",
            json={
                "sub": "user-123",
                "org_key": "navra",
                "role": "admin",
                "project_key": "special-project",
            },
        )
        assert response.status_code == 200

        # 5. Verify user has both roles
        response = client.get("/api/admin/rbac/users/navra/user-123")
        assert response.status_code == 200
        data = response.json()
        assert len(data["roles"]) == 2

        # Explicitly assert each expected role assignment for clearer failure messages
        assert any(
            r["role"] == "planner" and r["project_key"] is None for r in data["roles"]
        ), "Expected planner role with no project_key"
        assert any(
            r["role"] == "admin" and r["project_key"] == "special-project"
            for r in data["roles"]
        ), "Expected admin role with project_key 'special-project'"
