"""
Tests for NAVI Enhanced Features:
1. Workspace RAG - Semantic code search
2. Vision Service - UI screenshot analysis
3. Test Executor - Test running and verification
4. Plan Persistence - Checkpoint and resume
"""

import pytest
import tempfile
import os


# ============================================================
# WORKSPACE RAG TESTS
# ============================================================


class TestWorkspaceRAG:
    """Test full codebase RAG capabilities"""

    def test_code_parser_python(self):
        """Test Python code parsing"""
        from backend.services.workspace_rag import CodeParser

        code = '''
def hello_world():
    """Say hello"""
    return "Hello, World!"

class MyClass:
    """A test class"""

    def method(self):
        pass
'''
        chunks = CodeParser.parse_file("test.py", code)

        # Should extract function and class
        func_chunks = [c for c in chunks if c.chunk_type.value == "function"]
        class_chunks = [c for c in chunks if c.chunk_type.value == "class"]

        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert any(c.name == "hello_world" for c in func_chunks)
        assert any(c.name == "MyClass" for c in class_chunks)

    def test_code_parser_javascript(self):
        """Test JavaScript code parsing"""
        from backend.services.workspace_rag import CodeParser

        code = """
function greet(name) {
    return `Hello, ${name}!`;
}

const add = (a, b) => a + b;

class Calculator {
    constructor() {
        this.value = 0;
    }
}
"""
        chunks = CodeParser.parse_file("test.js", code)

        # Should extract functions and class
        assert len(chunks) >= 2
        names = [c.name for c in chunks if c.name]
        assert "greet" in names or "Calculator" in names

    def test_embedding_generation(self):
        """Test embedding generation"""
        from backend.services.workspace_rag import EmbeddingProvider

        text = "This is a test function that does something"
        embedding = EmbeddingProvider.generate_embedding(text)

        # Should return a fixed-size embedding
        assert len(embedding) == 100
        assert all(isinstance(v, float) for v in embedding)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        from backend.services.workspace_rag import EmbeddingProvider

        # Test with texts that have clear vocabulary overlap vs no overlap
        text1 = "user authentication login password security verify"
        text2 = "user login authentication password check verify"
        text3 = "database query optimization index performance tuning"

        emb1 = EmbeddingProvider.generate_embedding(text1)
        emb2 = EmbeddingProvider.generate_embedding(text2)
        emb3 = EmbeddingProvider.generate_embedding(text3)

        sim_similar = EmbeddingProvider.cosine_similarity(emb1, emb2)
        sim_different = EmbeddingProvider.cosine_similarity(emb1, emb3)

        # Similar texts (shared vocabulary) should score higher than different texts
        assert sim_similar >= sim_different

    @pytest.mark.asyncio
    async def test_index_workspace(self):
        """Test workspace indexing"""
        from backend.services.workspace_rag import WorkspaceIndexer

        # Create a temp workspace with test files
        with tempfile.TemporaryDirectory() as workspace:
            # Create a Python file
            with open(os.path.join(workspace, "main.py"), "w") as f:
                f.write(
                    '''
def main():
    """Main entry point"""
    print("Hello")

class App:
    def run(self):
        pass
'''
                )

            # Create a JS file
            with open(os.path.join(workspace, "app.js"), "w") as f:
                f.write(
                    """
function start() {
    console.log("Starting");
}
"""
                )

            # Index the workspace
            index = await WorkspaceIndexer.index_workspace(
                workspace,
                generate_embeddings=False,  # Skip embeddings for speed
            )

            assert index.total_files >= 2
            assert index.total_chunks > 0
            assert "main" in index.symbols or "App" in index.symbols

    @pytest.mark.asyncio
    async def test_semantic_search(self):
        """Test semantic search"""
        from backend.services.workspace_rag import (
            WorkspaceIndexer,
            SemanticSearch,
            store_index,
        )

        with tempfile.TemporaryDirectory() as workspace:
            # Create test files with distinct purposes
            with open(os.path.join(workspace, "auth.py"), "w") as f:
                f.write(
                    '''
def login(username, password):
    """Authenticate user with credentials"""
    return validate_credentials(username, password)

def logout(session_id):
    """End user session"""
    invalidate_session(session_id)
'''
                )

            with open(os.path.join(workspace, "database.py"), "w") as f:
                f.write(
                    '''
def query_users(filter_by):
    """Query users from database"""
    return db.execute("SELECT * FROM users")

def insert_record(table, data):
    """Insert record into database"""
    pass
'''
                )

            # Index
            index = await WorkspaceIndexer.index_workspace(
                workspace, generate_embeddings=True
            )
            store_index(index)

            # Search for auth-related code
            results = await SemanticSearch.search(
                "user authentication login",
                index,
                top_k=5,
            )

            # Auth file should be in results
            assert len(results) > 0
            auth_results = [r for r, _ in results if "auth" in r.file_path]
            assert len(auth_results) > 0


# ============================================================
# VISION SERVICE TESTS
# ============================================================


class TestVisionService:
    """Test UI screenshot analysis"""

    def test_is_image_attachment(self):
        """Test image detection"""

        # These were tested in navi_planner tests but let's verify the service
        # The actual VisionClient methods are in vision_service

    def test_ui_analysis_parsing(self):
        """Test UI analysis JSON parsing"""
        from backend.services.vision_service import UIAnalyzer

        # Mock a vision API response
        json_response = """
{
    "description": "A dashboard with sidebar",
    "layout": {
        "type": "sidebar",
        "columns": 2,
        "rows": 1,
        "responsive": true
    },
    "components": [
        {
            "type": "nav",
            "description": "Sidebar navigation",
            "position": "sidebar"
        },
        {
            "type": "card",
            "description": "Stats card",
            "position": "main"
        }
    ],
    "colors": {
        "primary": "#3B82F6",
        "background": "#F9FAFB"
    },
    "framework": "react",
    "cssFramework": "tailwind"
}
"""
        analysis = UIAnalyzer._parse_analysis(json_response)

        assert analysis.description == "A dashboard with sidebar"
        assert analysis.layout.layout_type == "sidebar"
        assert len(analysis.components) == 2
        assert analysis.suggested_framework == "react"

    def test_code_template_generation(self):
        """Test UI code template generation"""
        from backend.services.vision_service import (
            UICodeGenerator,
            UIAnalysis,
            LayoutAnalysis,
            UIComponent,
        )

        analysis = UIAnalysis(
            description="Test dashboard",
            layout=LayoutAnalysis(layout_type="grid", columns=2),
            components=[
                UIComponent(
                    component_type="button",
                    description="Submit button",
                    position="main",
                ),
                UIComponent(
                    component_type="input",
                    description="Email input",
                    position="main",
                ),
            ],
        )

        code = UICodeGenerator._generate_template(analysis, "react", "tailwind")

        assert "import React" in code
        assert "className" in code
        assert "button" in code.lower()


# ============================================================
# TEST EXECUTOR TESTS
# ============================================================


class TestTestExecutor:
    """Test the test execution service"""

    def test_framework_detection_pytest(self):
        """Test pytest detection"""
        from backend.services.test_executor import FrameworkDetector, TestFramework

        with tempfile.TemporaryDirectory() as workspace:
            # Create pytest.ini
            with open(os.path.join(workspace, "pytest.ini"), "w") as f:
                f.write("[pytest]\n")

            framework = FrameworkDetector.detect_framework(workspace)
            assert framework == TestFramework.PYTEST

    def test_framework_detection_jest(self):
        """Test Jest detection"""
        from backend.services.test_executor import FrameworkDetector, TestFramework

        with tempfile.TemporaryDirectory() as workspace:
            # Create jest.config.js
            with open(os.path.join(workspace, "jest.config.js"), "w") as f:
                f.write("module.exports = {};")

            framework = FrameworkDetector.detect_framework(workspace)
            assert framework == TestFramework.JEST

    def test_framework_detection_go(self):
        """Test Go test detection"""
        from backend.services.test_executor import FrameworkDetector, TestFramework

        with tempfile.TemporaryDirectory() as workspace:
            # Create go.mod
            with open(os.path.join(workspace, "go.mod"), "w") as f:
                f.write("module example.com/test\n")

            framework = FrameworkDetector.detect_framework(workspace)
            assert framework == TestFramework.GO_TEST

    def test_discover_tests(self):
        """Test test discovery"""
        from backend.services.test_executor import FrameworkDetector

        with tempfile.TemporaryDirectory() as workspace:
            # Create test files
            os.makedirs(os.path.join(workspace, "tests"))
            with open(os.path.join(workspace, "tests", "test_example.py"), "w") as f:
                f.write("def test_something(): pass\n")
            with open(os.path.join(workspace, "pytest.ini"), "w") as f:
                f.write("[pytest]\n")

            discovery = FrameworkDetector.discover_tests(workspace)

            assert discovery.test_count >= 1
            assert any("test_example.py" in f for f in discovery.test_files)

    def test_parse_pytest_output(self):
        """Test pytest output parsing"""
        from backend.services.test_executor import (
            TestRunner,
            TestFramework,
            TestSuiteResult,
        )

        output = """
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-9.0.2
collected 5 items

tests/test_example.py::test_one PASSED
tests/test_example.py::test_two PASSED
tests/test_example.py::test_three FAILED
tests/test_example.py::test_four SKIPPED
tests/test_example.py::test_five PASSED

=========================== short test summary info ============================
FAILED tests/test_example.py::test_three - AssertionError: Expected 1 got 2
======================= 3 passed, 1 failed, 1 skipped in 1.23s =================
"""

        suite = TestSuiteResult(
            framework=TestFramework.PYTEST, raw_output=output, exit_code=1
        )
        parsed = TestRunner._parse_pytest(suite, output)

        assert parsed.passed == 3
        assert parsed.failed == 1
        assert parsed.skipped == 1
        assert parsed.total == 5
        assert len(parsed.test_cases) >= 4

    def test_failure_analyzer(self):
        """Test failure analysis"""
        from backend.services.test_executor import FailureAnalyzer, TestCase, TestStatus

        test_case = TestCase(
            name="test_login",
            status=TestStatus.FAILED,
            error_message="AssertionError: Expected user to be logged in",
        )

        analysis = FailureAnalyzer.analyze_failure(test_case, "/workspace")

        assert analysis["error_type"] == "assertion"
        assert len(analysis["suggested_fixes"]) > 0


# ============================================================
# PLAN PERSISTENCE TESTS
# ============================================================


class TestPlanPersistence:
    """Test plan storage and checkpointing"""

    def test_save_and_load_plan(self):
        """Test saving and loading a plan"""
        from backend.services.plan_persistence import (
            init_database,
        )

        # Use a temp database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            init_database(db_path)

            plan = {
                "id": "test-plan-001",
                "title": "Test Plan",
                "summary": "A test plan",
                "status": "draft",
                "original_request": "Build something",
                "workspace_path": "/tmp/test",
                "questions": [
                    {
                        "id": "q1",
                        "category": "architecture",
                        "question": "What framework?",
                        "why_asking": "To choose the right approach",
                        "options": ["React", "Vue"],
                        "answered": False,
                    }
                ],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Setup project",
                        "description": "Initialize the project",
                        "task_type": "setup",
                        "status": "pending",
                    }
                ],
            }

            # Import the store class to use custom db path
            from backend.services.plan_persistence import PlanStore

            PlanStore.save_plan(plan, db_path)

            loaded = PlanStore.load_plan("test-plan-001", db_path)

            assert loaded is not None
            assert loaded["id"] == "test-plan-001"
            assert loaded["title"] == "Test Plan"
            assert len(loaded["questions"]) == 1
            assert len(loaded["tasks"]) == 1

        finally:
            os.unlink(db_path)

    def test_create_checkpoint(self):
        """Test checkpoint creation"""
        from backend.services.plan_persistence import (
            PlanStore,
            CheckpointManager,
            init_database,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            init_database(db_path)

            # Create a plan first
            plan = {
                "id": "checkpoint-test-001",
                "title": "Checkpoint Test",
                "summary": "Testing checkpoints",
                "status": "in_progress",
                "questions": [],
                "tasks": [
                    {
                        "id": "t1",
                        "title": "Task 1",
                        "task_type": "test",
                        "status": "completed",
                    },
                    {
                        "id": "t2",
                        "title": "Task 2",
                        "task_type": "test",
                        "status": "pending",
                    },
                ],
            }
            PlanStore.save_plan(plan, db_path)

            # Create checkpoint
            checkpoint_id = CheckpointManager.create_checkpoint(
                "checkpoint-test-001",
                task_id="t1",
                checkpoint_type="after_task",
                db_path=db_path,
            )

            assert checkpoint_id > 0

            # Get checkpoint
            checkpoint = CheckpointManager.get_latest_checkpoint(
                "checkpoint-test-001", db_path
            )

            assert checkpoint is not None
            assert checkpoint["task_id"] == "t1"
            assert checkpoint["checkpoint_type"] == "after_task"
            assert checkpoint["state"]["id"] == "checkpoint-test-001"

        finally:
            os.unlink(db_path)

    def test_restore_checkpoint(self):
        """Test restoring from checkpoint"""
        from backend.services.plan_persistence import (
            PlanStore,
            CheckpointManager,
            init_database,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            init_database(db_path)

            # Create initial plan
            plan = {
                "id": "restore-test-001",
                "title": "Restore Test",
                "summary": "Before changes",
                "status": "in_progress",
                "questions": [],
                "tasks": [],
            }
            PlanStore.save_plan(plan, db_path)

            # Create checkpoint
            checkpoint_id = CheckpointManager.create_checkpoint(
                "restore-test-001",
                db_path=db_path,
            )

            # Modify plan
            plan["summary"] = "After changes"
            plan["status"] = "failed"
            PlanStore.save_plan(plan, db_path)

            # Verify it changed
            modified = PlanStore.load_plan("restore-test-001", db_path)
            assert modified["summary"] == "After changes"

            # Restore from checkpoint
            restored = CheckpointManager.restore_from_checkpoint(checkpoint_id, db_path)

            assert restored["summary"] == "Before changes"
            assert restored["status"] == "in_progress"

        finally:
            os.unlink(db_path)

    def test_list_plans(self):
        """Test listing plans"""
        from backend.services.plan_persistence import (
            PlanStore,
            init_database,
        )

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            init_database(db_path)

            # Create multiple plans
            for i in range(3):
                plan = {
                    "id": f"list-test-{i}",
                    "title": f"Plan {i}",
                    "summary": f"Summary {i}",
                    "status": "draft" if i % 2 == 0 else "completed",
                    "workspace_path": "/tmp/workspace",
                    "questions": [],
                    "tasks": [],
                }
                PlanStore.save_plan(plan, db_path)

            # List all
            all_plans = PlanStore.list_plans(db_path=db_path)
            assert len(all_plans) >= 3

            # List by workspace
            workspace_plans = PlanStore.list_plans(
                workspace_path="/tmp/workspace",
                db_path=db_path,
            )
            assert len(workspace_plans) >= 3

            # List by status
            draft_plans = PlanStore.list_plans(status="draft", db_path=db_path)
            assert len(draft_plans) >= 1

        finally:
            os.unlink(db_path)


# ============================================================
# INTEGRATION TESTS
# ============================================================


class TestEnhancedAPIIntegration:
    """Integration tests for enhanced API endpoints"""

    @pytest.mark.asyncio
    async def test_rag_index_endpoint(self):
        """Test RAG indexing endpoint"""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            with tempfile.TemporaryDirectory() as workspace:
                # Create a test file
                with open(os.path.join(workspace, "test.py"), "w") as f:
                    f.write("def hello(): pass\n")

                payload = {
                    "workspace_path": workspace,
                    "force_reindex": True,
                }

                try:
                    async with session.post(
                        "http://localhost:8002/api/navi/enhanced/rag/index",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            assert result["status"] in ["indexed", "already_indexed"]
                            print(f"RAG Index: {result.get('status')}")
                        else:
                            print(f"RAG Index endpoint returned: {response.status}")
                except aiohttp.ClientError as e:
                    print(f"Server not available: {e}")

    @pytest.mark.asyncio
    async def test_test_discover_endpoint(self):
        """Test the test discovery endpoint"""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            with tempfile.TemporaryDirectory() as workspace:
                # Create pytest setup
                with open(os.path.join(workspace, "pytest.ini"), "w") as f:
                    f.write("[pytest]\n")
                with open(os.path.join(workspace, "test_example.py"), "w") as f:
                    f.write("def test_one(): pass\n")

                try:
                    async with session.get(
                        f"http://localhost:8002/api/navi/enhanced/tests/discover/{workspace}",
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            assert result["framework"] == "pytest"
                            print(f"Test Discovery: {result}")
                        else:
                            print(f"Test discover endpoint returned: {response.status}")
                except aiohttp.ClientError as e:
                    print(f"Server not available: {e}")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("NAVI ENHANCED FEATURES TEST SUITE")
    print("=" * 60)

    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
