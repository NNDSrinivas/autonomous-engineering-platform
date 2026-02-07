"""Pytest configuration and fixtures for memory graph tests

Provides:
- api_client: HTTP client for testing API endpoints
- seeded_graph: Ensures memory graph fixture is loaded before tests
- test_db: Database session for direct queries
"""

import os

os.environ.setdefault("TOKENIZER_FALLBACK_ENABLED", "true")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("NAVI_DISABLE_LLM", "true")

import pytest  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from httpx import Client  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker, Session  # noqa: E402

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.core.config import settings  # noqa: E402
from backend.core.settings import settings as core_settings  # noqa: E402
from backend.database.models.memory_graph import MemoryNode, MemoryEdge  # noqa: E402


@pytest.fixture(autouse=True)
def reset_jwt_settings(monkeypatch):
    """
    Reset JWT settings for each test to ensure test isolation.

    This prevents JWT_JWKS_URL from leaking between tests and causing
    unexpected authentication behavior.
    """
    # Reset to default test values (JWT disabled)
    # Note: monkeypatch automatically restores original values after test
    monkeypatch.setattr(core_settings, "JWT_ENABLED", False)
    monkeypatch.setattr(core_settings, "JWT_JWKS_URL", None)

    yield


# Test configuration
TEST_ORG_ID = "default"
TEST_BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
NAVI_TEST_TOKEN = os.getenv("NAVI_TEST_TOKEN")


def get_auth_headers() -> dict:
    """Return Authorization header if NAVI_TEST_TOKEN is set."""
    if NAVI_TEST_TOKEN:
        return {"Authorization": f"Bearer {NAVI_TEST_TOKEN}"}
    return {}


def get_default_headers(org_id: str = TEST_ORG_ID) -> dict:
    """Default headers for API tests."""
    headers = {"X-Org-Id": org_id}
    headers.update(get_auth_headers())
    return headers


FIXTURE_PATH = "data/seed/memory_graph_fixture.json"


@pytest.fixture(scope="session")
def test_engine():
    """Create database engine for tests"""
    db_url = (
        settings.database_url
        or f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_db_session(test_engine):
    """Create database session factory"""
    SessionLocal = sessionmaker(bind=test_engine)
    return SessionLocal


@pytest.fixture(scope="session")
def seeded_graph(test_db_session):
    """Seed memory graph fixture data once per test session

    This fixture ensures the test database has the 6-node chain loaded:
    Meeting → Issue → PR → Deploy → Incident → Hotfix

    Runs before all tests and provides:
    - 6 nodes (meeting, jira_issue, pr, run, incident, pr)
    - 12 edges (derived_from, implements, fixes, next, previous, caused_by, references)
    """
    # Skip tests that require seeded_graph if fixture file doesn't exist
    if not os.path.exists(FIXTURE_PATH):
        pytest.skip(
            f"Fixture file not found: {FIXTURE_PATH} - skipping tests that require seeded graph"
        )

    print("\n🌱 Seeding memory graph fixture data...")

    # Run seed script
    result = subprocess.run(
        [sys.executable, "scripts/seed_graph_fixture.py", FIXTURE_PATH],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Seed script failed:\n{result.stdout}\n{result.stderr}")
        pytest.skip(
            f"Seed script failed - skipping seeded_graph tests in CI: {result.stderr[:200]}"
        )

    print(result.stdout)

    # Verify data is present
    session = test_db_session()
    try:
        node_count = (
            session.query(MemoryNode).filter(MemoryNode.org_id == TEST_ORG_ID).count()
        )
        edge_count = (
            session.query(MemoryEdge).filter(MemoryEdge.org_id == TEST_ORG_ID).count()
        )

        assert node_count == 6, f"Expected 6 nodes, found {node_count}"
        assert edge_count == 12, f"Expected 12 edges, found {edge_count}"

        print(f"✅ Fixture verified: {node_count} nodes, {edge_count} edges")
    finally:
        session.close()

    yield {"org_id": TEST_ORG_ID, "nodes": 6, "edges": 12, "test_issue": "ENG-102"}


@pytest.fixture
def api_client(seeded_graph):
    """HTTP client for API testing with default headers

    Automatically includes X-Org-Id header and depends on seeded_graph
    to ensure data is present.
    """
    with Client(
        base_url=TEST_BASE_URL, headers=get_default_headers(), timeout=30.0
    ) as client:
        yield client


@pytest.fixture
def test_db(test_db_session, seeded_graph):
    """Database session for direct queries in tests

    Use when you need to query the database directly rather than
    going through the API.
    """
    session = test_db_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def other_org_client():
    """HTTP client with different org for cross-org testing"""
    with Client(
        base_url=TEST_BASE_URL,
        headers=get_default_headers("other_org"),
        timeout=30.0,
    ) as client:
        yield client


# Test utilities
def assert_response_ok(response, expected_status=200):
    """Assert response status and return JSON"""
    assert (
        response.status_code == expected_status
    ), f"Expected {expected_status}, got {response.status_code}: {response.text}"
    return response.json()


def get_node_by_foreign_id(
    session: Session, foreign_id: str, org_id: str = TEST_ORG_ID
):
    """Helper to fetch node by foreign_id"""
    return (
        session.query(MemoryNode)
        .filter(MemoryNode.org_id == org_id, MemoryNode.foreign_id == foreign_id)
        .first()
    )


def get_edges_for_node(session: Session, foreign_id: str, org_id: str = TEST_ORG_ID):
    """Helper to fetch all edges for a node"""
    node = get_node_by_foreign_id(session, foreign_id, org_id)
    if not node:
        return []

    edges = (
        session.query(MemoryEdge)
        .filter(
            (MemoryEdge.src_id == node.id) | (MemoryEdge.dst_id == node.id),
            MemoryEdge.org_id == org_id,
        )
        .all()
    )

    return edges


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly enabled."""
    if os.getenv("RUN_INTEGRATION_TESTS") == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="integration tests disabled (set RUN_INTEGRATION_TESTS=1 to run)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)

    if os.getenv("RUN_MANUAL_TESTS") == "1":
        return
    skip_manual = pytest.mark.skip(
        reason="manual tests disabled (set RUN_MANUAL_TESTS=1 to run)"
    )
    for item in items:
        if "tests/manual" in str(item.fspath):
            item.add_marker(skip_manual)
