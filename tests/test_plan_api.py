"""
Tests for Live Plan Mode API endpoints
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./data/test_plan_api.db"
os.environ["JWT_ENABLED"] = "false"
os.environ["DEV_USER_ROLE"] = "admin"
os.environ["DEV_USER_ID"] = "test-user"
os.environ["DEV_ORG_ID"] = "test-org"

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.api.main import app
from sqlalchemy.orm import sessionmaker

from backend.core.auth.deps import _get_db_for_auth
from backend.core.db import Base, get_db, get_engine
from backend.database.models.live_plan import LivePlan
import backend.core.db as core_db
import backend.api.routers.plan as plan_router

# Use file-based SQLite to keep a shared test database and avoid Postgres dependencies
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


# Create a dedicated engine/session factory for tests and wire it into core_db helpers
core_db.settings.database_url = TEST_DATABASE_URL  # force config to use test DB
core_db._engine = None
core_db._SessionLocal = None
engine = get_engine()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
core_db._engine = engine  # ensure lazy proxies reuse the test engine
core_db._SessionLocal = TestingSessionLocal


# Override the database dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def test_client():
    """Create test client with test database"""
    # Ensure clean slate and only create the tables required for plan tests to avoid SQLite incompatibilities
    Base.metadata.drop_all(bind=engine, tables=[LivePlan.__table__])
    Base.metadata.create_all(bind=engine, tables=[LivePlan.__table__])
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_db_for_auth] = override_get_db

    # Stub out Postgres-only event store functions for SQLite test runs
    async def _noop_append(*args, **kwargs):
        return None

    plan_router.append_and_broadcast = _noop_append
    plan_router.replay = lambda *args, **kwargs: []
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine, tables=[LivePlan.__table__])


@pytest.fixture
def org_id():
    """Test organization ID"""
    return "test-org-123"


@pytest.fixture
def headers(org_id):
    """Request headers with org ID"""
    return {"X-Org-Id": org_id}


class TestPlanCreation:
    """Test plan creation endpoint"""

    def test_create_plan_success(self, test_client, headers):
        """Test creating a new plan"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={
                "title": "Test Plan",
                "description": "A test plan description",
                "participants": ["user1", "user2"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "plan_id" in data
        assert uuid.UUID(data["plan_id"])  # Valid UUID

    def test_create_plan_missing_title(self, test_client, headers):
        """Test creating plan without title fails"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={"description": "No title", "participants": ["user1"]},
        )

        assert response.status_code == 422  # Validation error

    def test_create_plan_no_org_header(self, test_client):
        """Test creating plan without org header fails"""
        response = test_client.post(
            "/api/plan/start", json={"title": "Test Plan", "participants": ["user1"]}
        )

        assert response.status_code in [400, 403, 422]  # Missing org


class TestPlanRetrieval:
    """Test plan retrieval endpoints"""

    @pytest.fixture
    def created_plan_id(self, test_client, headers):
        """Create a plan for testing"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={
                "title": "Retrieval Test Plan",
                "description": "Testing retrieval",
                "participants": ["user1"],
            },
        )
        return response.json()["plan_id"]

    def test_get_plan_success(self, test_client, headers, created_plan_id):
        """Test retrieving an existing plan"""
        response = test_client.get(f"/api/plan/{created_plan_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_plan_id
        assert data["title"] == "Retrieval Test Plan"
        assert data["description"] == "Testing retrieval"
        assert data["participants"] == ["user1"]
        assert data["steps"] == []
        assert data["archived"] is False

    def test_get_plan_not_found(self, test_client, headers):
        """Test retrieving non-existent plan"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(f"/api/plan/{fake_id}", headers=headers)

        assert response.status_code == 404

    def test_get_plan_no_org_header(self, test_client, created_plan_id):
        """Test retrieving plan without org header fails"""
        response = test_client.get(f"/api/plan/{created_plan_id}")

        assert response.status_code in [400, 403, 422]


class TestAddStep:
    """Test adding steps to plan"""

    @pytest.fixture
    def created_plan_id(self, test_client, headers):
        """Create a plan for testing"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={"title": "Step Test Plan", "participants": ["user1", "user2"]},
        )
        return response.json()["plan_id"]

    def test_add_step_success(self, test_client, headers, created_plan_id):
        """Test adding a step to a plan"""
        response = test_client.post(
            "/api/plan/step",
            headers=headers,
            json={"plan_id": created_plan_id, "text": "First step", "owner": "user1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "step_added"
        assert data["step"]["text"] == "First step"
        assert data["step"]["owner"] == "user1"
        assert "ts" in data["step"]

        # Verify step was saved
        get_response = test_client.get(f"/api/plan/{created_plan_id}", headers=headers)
        plan_data = get_response.json()
        assert len(plan_data["steps"]) == 1
        assert plan_data["steps"][0]["text"] == "First step"

    def test_add_multiple_steps(self, test_client, headers, created_plan_id):
        """Test adding multiple steps"""
        steps = [
            {"plan_id": created_plan_id, "text": "Step 1", "owner": "user1"},
            {"plan_id": created_plan_id, "text": "Step 2", "owner": "user2"},
            {"plan_id": created_plan_id, "text": "Step 3", "owner": "user1"},
        ]

        for step in steps:
            response = test_client.post("/api/plan/step", headers=headers, json=step)
            assert response.status_code == 200

        # Verify all steps saved
        get_response = test_client.get(f"/api/plan/{created_plan_id}", headers=headers)
        plan_data = get_response.json()
        assert len(plan_data["steps"]) == 3
        assert plan_data["steps"][0]["text"] == "Step 1"
        assert plan_data["steps"][2]["text"] == "Step 3"

    def test_add_step_to_nonexistent_plan(self, test_client, headers):
        """Test adding step to non-existent plan"""
        fake_id = str(uuid.uuid4())
        response = test_client.post(
            "/api/plan/step",
            headers=headers,
            json={"plan_id": fake_id, "text": "Step", "owner": "user1"},
        )

        assert response.status_code == 404


class TestPlanList:
    """Test listing plans"""

    @pytest.fixture
    def multiple_plans(self, test_client, headers):
        """Create multiple plans for testing"""
        plans = []
        for i in range(3):
            response = test_client.post(
                "/api/plan/start",
                headers=headers,
                json={"title": f"List Test Plan {i+1}", "participants": ["user1"]},
            )
            plans.append(response.json()["plan_id"])
        return plans

    def test_list_active_plans(self, test_client, headers, multiple_plans):
        """Test listing active plans"""
        response = test_client.get("/api/plan/list", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert "count" in data
        assert data["count"] >= 3
        assert all(not p["archived"] for p in data["plans"])

    def test_list_archived_plans(self, test_client, headers, multiple_plans):
        """Test listing archived plans"""
        # Archive one plan
        test_client.post(f"/api/plan/{multiple_plans[0]}/archive", headers=headers)

        response = test_client.get(
            "/api/plan/list", headers=headers, params={"archived": "true"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert all(p["archived"] for p in data["plans"])


class TestArchivePlan:
    """Test archiving plans"""

    @pytest.fixture
    def created_plan_id(self, test_client, headers):
        """Create a plan with steps for testing"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={"title": "Archive Test Plan", "participants": ["user1"]},
        )
        plan_id = response.json()["plan_id"]

        # Add some steps
        test_client.post(
            "/api/plan/step",
            headers=headers,
            json={"plan_id": plan_id, "text": "Step 1", "owner": "user1"},
        )

        return plan_id

    def test_archive_plan_success(self, test_client, headers, created_plan_id):
        """Test archiving a plan"""
        response = test_client.post(
            f"/api/plan/{created_plan_id}/archive", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "archived"
        assert data["plan_id"] == created_plan_id

        # Verify plan is archived
        get_response = test_client.get(f"/api/plan/{created_plan_id}", headers=headers)
        plan_data = get_response.json()
        assert plan_data["archived"] is True

    def test_archive_nonexistent_plan(self, test_client, headers):
        """Test archiving non-existent plan"""
        fake_id = str(uuid.uuid4())
        response = test_client.post(f"/api/plan/{fake_id}/archive", headers=headers)

        assert response.status_code == 404

    def test_archive_already_archived(self, test_client, headers, created_plan_id):
        """Test archiving already archived plan"""
        # Archive once
        test_client.post(f"/api/plan/{created_plan_id}/archive", headers=headers)

        # Try to archive again (should still succeed)
        response = test_client.post(
            f"/api/plan/{created_plan_id}/archive", headers=headers
        )

        assert response.status_code == 200


class TestSSEStream:
    """Test Server-Sent Events streaming"""

    @pytest.fixture
    def created_plan_id(self, test_client, headers):
        """Create a plan for testing"""
        response = test_client.post(
            "/api/plan/start",
            headers=headers,
            json={"title": "SSE Test Plan", "participants": ["user1"]},
        )
        return response.json()["plan_id"]

    def test_stream_endpoint_exists(self, test_client, headers, created_plan_id):
        """Test SSE stream endpoint responds"""
        # Note: TestClient has limitations with streaming responses
        # This tests basic connectivity, not actual streaming behavior
        response = test_client.get(
            f"/api/plan/{created_plan_id}/stream", headers=headers
        )

        # Should get 200 or streaming response
        assert response.status_code in [200, 499]  # 499 = client closed

    def test_stream_nonexistent_plan(self, test_client, headers):
        """Test streaming from non-existent plan"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(f"/api/plan/{fake_id}/stream", headers=headers)

        # Should fail before streaming starts
        assert response.status_code == 404
