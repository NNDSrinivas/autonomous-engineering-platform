"""Pytest configuration and fixtures for memory graph tests

Provides:
- api_client: HTTP client for testing API endpoints
- seeded_graph: Ensures memory graph fixture is loaded before tests
- test_db: Database session for direct queries
"""

import json
import pytest
import subprocess
import sys
from pathlib import Path
from httpx import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.core.config import settings  # noqa: E402
from backend.database.models.memory_graph import MemoryNode, MemoryEdge  # noqa: E402
from backend.services.model_router import ModelRouter  # noqa: E402

# Test configuration
TEST_ORG_ID = "default"
TEST_BASE_URL = "http://localhost:8000"
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
    print("\n🌱 Seeding memory graph fixture data...")

    # Run seed script
    result = subprocess.run(
        [sys.executable, "scripts/seed_graph_fixture.py", FIXTURE_PATH],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Seed script failed:\n{result.stdout}\n{result.stderr}")
        pytest.fail("Failed to seed memory graph fixture data")

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
        base_url=TEST_BASE_URL, headers={"X-Org-Id": TEST_ORG_ID}, timeout=30.0
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
        base_url=TEST_BASE_URL, headers={"X-Org-Id": "other_org"}, timeout=30.0
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


# ============================================================================
# Phase 2 Model Router Test Fixtures
# ============================================================================


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _minimal_legacy_registry() -> dict:
    """
    Minimal legacy registry (shared/model-registry.json shape) that:
    - defines providers + models referenced by modes
    - keeps provider IDs aligned with facts registry providers
    """
    return {
        "version": "1.0.0",
        "defaults": {
            "defaultModeId": "navi/intelligence",
            "defaultModelId": "openai/gpt-4o",
        },
        "providers": [
            {
                "id": "openai",
                "type": "saas",
                "models": [
                    {
                        "id": "openai/gpt-4o",
                        "providerModel": "gpt-4o",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                        "vision": True,
                    },
                    {
                        "id": "openai/gpt-4o-mini",
                        "providerModel": "gpt-4o-mini",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                    {
                        "id": "openai/gpt-5.2",
                        "providerModel": "gpt-5.2",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                        "vision": True,
                    },
                    {
                        "id": "openai/gpt-5-mini",
                        "providerModel": "gpt-5-mini",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                    {
                        "id": "openai/o3",
                        "providerModel": "o3",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                ],
            },
            {
                "id": "anthropic",
                "type": "saas",
                "models": [
                    {
                        "id": "anthropic/claude-sonnet-4",
                        "providerModel": "claude-sonnet-4",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                    {
                        "id": "anthropic/claude-opus-4",
                        "providerModel": "claude-opus-4",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                ],
            },
            {
                "id": "google",
                "type": "saas",
                "models": [
                    {
                        "id": "google/gemini-2.5-pro",
                        "providerModel": "gemini-2.5-pro",
                        "streaming": True,
                        "json": True,
                    },
                ],
            },
            {
                "id": "groq",
                "type": "saas",
                "models": [
                    {
                        "id": "groq/llama-3.3-70b-versatile",
                        "providerModel": "llama-3.3-70b-versatile",
                        "streaming": True,
                    },
                ],
            },
            {
                "id": "ollama",
                "type": "local",
                "models": [
                    {
                        "id": "ollama/llama3.2",
                        "providerModel": "llama3.2",
                        "streaming": True,
                    },
                ],
            },
            {
                "id": "self_hosted",
                "type": "self_hosted",
                "models": [
                    {
                        "id": "self_hosted/qwen2.5-coder",
                        "providerModel": "qwen2.5-coder",
                        "streaming": True,
                        "tools": True,
                    },
                ],
            },
            {
                "id": "test",
                "type": "saas",
                "models": [
                    {
                        "id": "test/model-1",
                        "providerModel": "test-model-1",
                        "streaming": True,
                        "tools": True,
                        "json": True,
                    },
                    {
                        "id": "test/expensive-model",
                        "providerModel": "test-expensive",
                        "streaming": True,
                        "tools": True,
                    },
                    {
                        "id": "test/vision-model",
                        "providerModel": "test-vision",
                        "streaming": True,
                        "vision": True,
                    },
                    {
                        "id": "test/premium-model",
                        "providerModel": "test-premium",
                        "streaming": True,
                    },
                    {
                        "id": "test/disabled-model",
                        "providerModel": "test-disabled",
                        "streaming": True,
                    },
                ],
            },
        ],
        "naviModes": [
            {
                "id": "navi/intelligence",
                "label": "NAVI Intelligence",
                "candidateModelIds": [
                    "openai/gpt-5.2",
                    "anthropic/claude-sonnet-4",
                    "openai/gpt-4o",
                ],
                "policy": {"strictPrivate": False},
            },
            {
                "id": "navi/fast",
                "label": "NAVI Fast",
                "candidateModelIds": [
                    "openai/gpt-5-mini",
                    "openai/gpt-4o-mini",
                    "groq/llama-3.3-70b-versatile",
                ],
                "policy": {"strictPrivate": False},
            },
            {
                "id": "navi/deep",
                "label": "NAVI Deep",
                "candidateModelIds": [
                    "anthropic/claude-opus-4",
                    "openai/o3",
                    "google/gemini-2.5-pro",
                ],
                "policy": {"strictPrivate": False},
            },
            {
                "id": "navi/private",
                "label": "NAVI Private",
                "candidateModelIds": ["ollama/llama3.2", "self_hosted/qwen2.5-coder"],
                "policy": {"strictPrivate": True},
            },
            {
                "id": "navi/test-policy",
                "label": "Test Mode with Policy",
                "candidateModelIds": ["test/model-1", "test/expensive-model"],
                "policy": {
                    "requiredCapabilities": ["tool-use"],
                    "maxCostUSD": 0.01,
                    "strictPrivate": False,
                },
            },
        ],
    }


@pytest.fixture()
def router_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
):
    """
    Creates a ModelRouter wired to:
    - a temp legacy registry (registry_path param)
    - a temp facts registry (MODEL_REGISTRY_PATH env var)
    - deterministic env vars for provider config checks
    """
    # Ensure deterministic environment
    monkeypatch.setenv("APP_ENV", "dev")

    # Provider creds (make providers "configured" when needed)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("TEST_API_KEY", "test")  # For test provider

    # Special cases:
    # Ollama requires OLLAMA_HOST if provider_id == "ollama"
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")

    # self_hosted requires one of: SELF_HOSTED_API_BASE_URL / SELF_HOSTED_LLM_URL / VLLM_BASE_URL
    monkeypatch.setenv("SELF_HOSTED_LLM_URL", "http://localhost:8000")

    # Monkeypatch "test" provider into credential keys (test-only, not in production)
    from backend.services import model_router

    original_keys = model_router._PROVIDER_CREDENTIAL_KEYS.copy()
    model_router._PROVIDER_CREDENTIAL_KEYS["test"] = ("TEST_API_KEY",)

    # Cleanup after test using finalizer to avoid breaking pytest's monkeypatch cleanup
    def restore_keys():
        model_router._PROVIDER_CREDENTIAL_KEYS.clear()
        model_router._PROVIDER_CREDENTIAL_KEYS.update(original_keys)

    request.addfinalizer(restore_keys)

    # Write legacy registry to temp
    legacy_path = tmp_path / "shared" / "model-registry.json"
    _write_json(legacy_path, _minimal_legacy_registry())

    # Write facts registry to temp
    # IMPORTANT: this must match your Phase 1 schema shape: {environment, models:[...]}
    facts_path = tmp_path / "shared" / "model-registry-dev.json"
    facts = {
        "schemaVersion": 1,
        "environment": "dev",
        "models": [
            # Production models
            {
                "id": "openai/gpt-4o",
                "provider": "openai",
                "enabled": True,
                "capabilities": ["chat", "tool-use", "json", "vision", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.0025,
                    "outputPer1KTokens": 0.01,
                },
                "governance": {
                    "tier": "standard",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 128000, "maxOutputTokens": 16384},
                "displayName": "GPT-4o",
                "productionApproved": True,
            },
            {
                "id": "openai/gpt-5.2",
                "provider": "openai",
                "enabled": True,
                "capabilities": [
                    "chat",
                    "tool-use",
                    "json",
                    "vision",
                    "streaming",
                    "long-context",
                ],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.00175,
                    "outputPer1KTokens": 0.014,
                },
                "governance": {
                    "tier": "premium",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 128000, "maxOutputTokens": 16384},
                "displayName": "GPT-5.2",
                "productionApproved": True,
            },
            {
                "id": "ollama/llama3.2",
                "provider": "ollama",
                "enabled": True,
                "capabilities": ["chat", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.0,
                    "outputPer1KTokens": 0.0,
                },
                "governance": {
                    "tier": "budget",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 8192, "maxOutputTokens": 2048},
                "displayName": "Llama 3.2 (Ollama)",
                "productionApproved": True,
            },
            {
                "id": "self_hosted/qwen2.5-coder",
                "provider": "self_hosted",
                "enabled": True,
                "capabilities": ["chat", "tool-use", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.0,
                    "outputPer1KTokens": 0.0,
                },
                "governance": {
                    "tier": "standard",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 8192, "maxOutputTokens": 2048},
                "displayName": "Qwen 2.5 Coder (Self-hosted)",
                "productionApproved": True,
            },
            # Test models for Phase 2 tests
            {
                "id": "test/model-1",
                "provider": "test",
                "enabled": True,
                "capabilities": ["chat", "tool-use", "json", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.001,
                    "outputPer1KTokens": 0.002,
                },
                "governance": {
                    "tier": "budget",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 8192, "maxOutputTokens": 2048},
                "displayName": "Test Model 1",
                "productionApproved": True,
            },
            {
                "id": "test/expensive-model",
                "provider": "test",
                "enabled": True,
                "capabilities": ["chat", "tool-use", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.05,
                    "outputPer1KTokens": 0.1,
                },
                "governance": {
                    "tier": "premium",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 32768, "maxOutputTokens": 8192},
                "displayName": "Expensive Test Model",
                "productionApproved": True,
            },
            {
                "id": "test/vision-model",
                "provider": "test",
                "enabled": True,
                "capabilities": ["chat", "vision", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.003,
                    "outputPer1KTokens": 0.012,
                },
                "governance": {
                    "tier": "standard",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 16384, "maxOutputTokens": 4096},
                "displayName": "Vision Test Model",
                "productionApproved": True,
            },
            {
                "id": "test/premium-model",
                "provider": "test",
                "enabled": True,
                "capabilities": ["chat", "tool-use", "json", "streaming"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.01,
                    "outputPer1KTokens": 0.03,
                },
                "governance": {
                    "tier": "premium",
                    "allowedEnvironments": ["dev", "staging", "prod"],
                },
                "limits": {"maxInputTokens": 32768, "maxOutputTokens": 8192},
                "displayName": "Premium Test Model",
                "productionApproved": True,
            },
            {
                "id": "test/disabled-model",
                "provider": "test",
                "enabled": False,  # Explicitly disabled for testing factsEnabled
                "capabilities": ["chat"],
                "pricing": {
                    "currency": "USD",
                    "inputPer1KTokens": 0.001,
                    "outputPer1KTokens": 0.002,
                },
                "governance": {"tier": "budget", "allowedEnvironments": ["dev"]},
                "limits": {"maxInputTokens": 4096, "maxOutputTokens": 1024},
                "displayName": "Disabled Test Model",
                "productionApproved": False,
            },
        ],
    }
    _write_json(facts_path, facts)

    # Force router to use our temp facts registry regardless of repo_root
    monkeypatch.setenv("MODEL_REGISTRY_PATH", str(facts_path))

    router = ModelRouter(registry_path=legacy_path)
    return router, legacy_path, facts_path
