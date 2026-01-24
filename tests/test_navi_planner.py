"""
Tests for NAVI Planner - Plan Mode and Clarifying Questions

Tests the workflow:
1. User submits request (optionally with UI screenshots)
2. NAVI asks senior-engineer-level clarifying questions
3. User answers, NAVI generates structured plan
4. User approves, NAVI executes task-by-task
"""

import pytest
import asyncio
import aiohttp
import json
import base64
import tempfile

# Test server URL
BASE_URL = "http://localhost:8002"
TIMEOUT = 60


class TestPlanCreation:
    """Test plan creation with clarifying questions"""

    @pytest.mark.asyncio
    async def test_create_plan_simple(self):
        """Test creating a simple plan"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()
            payload = {
                "message": "Create a REST API for user management",
                "workspace_path": workspace,
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Verify plan structure
                assert "id" in result
                assert "title" in result
                assert "status" in result
                assert "questions" in result

                print(f"Plan created: {result['id']}")
                print(f"Status: {result['status']}")
                print(f"Questions: {len(result['questions'])}")

                # Should have clarifying questions for API work
                if result["questions"]:
                    print("\nClarifying Questions:")
                    for q in result["questions"]:
                        print(f"  - {q['question']}")
                        print(f"    Why: {q['why_asking']}")
                        print(f"    Options: {q['options']}")

    @pytest.mark.asyncio
    async def test_create_plan_with_auth(self):
        """Test that auth-related requests generate auth questions"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()
            payload = {
                "message": "Build a user authentication system with login and signup",
                "workspace_path": workspace,
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Should ask about auth strategy
                questions = result.get("questions", [])
                auth_questions = [
                    q for q in questions if "auth" in q.get("question", "").lower()
                ]

                print(f"\nAuth-related questions: {len(auth_questions)}")
                for q in auth_questions:
                    print(f"  - {q['question']}")

    @pytest.mark.asyncio
    async def test_create_plan_with_database(self):
        """Test that database requests generate database questions"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()
            payload = {
                "message": "Create a data pipeline to store user events in a database",
                "workspace_path": workspace,
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Should ask about database strategy
                questions = result.get("questions", [])
                db_questions = [
                    q for q in questions if "database" in q.get("question", "").lower()
                ]

                print(f"\nDatabase-related questions: {len(db_questions)}")


class TestPlanWithImages:
    """Test plan creation with UI screenshots"""

    @pytest.mark.asyncio
    async def test_create_plan_with_image(self):
        """Test creating a plan with a UI screenshot"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()

            # Create a simple test image (1x1 pixel PNG)
            # This is a valid minimal PNG
            minimal_png = base64.b64encode(
                bytes(
                    [
                        0x89,
                        0x50,
                        0x4E,
                        0x47,
                        0x0D,
                        0x0A,
                        0x1A,
                        0x0A,  # PNG signature
                        0x00,
                        0x00,
                        0x00,
                        0x0D,
                        0x49,
                        0x48,
                        0x44,
                        0x52,  # IHDR chunk
                        0x00,
                        0x00,
                        0x00,
                        0x01,
                        0x00,
                        0x00,
                        0x00,
                        0x01,
                        0x08,
                        0x02,
                        0x00,
                        0x00,
                        0x00,
                        0x90,
                        0x77,
                        0x53,
                        0xDE,
                        0x00,
                        0x00,
                        0x00,
                        0x0C,
                        0x49,
                        0x44,
                        0x41,  # IDAT chunk
                        0x54,
                        0x08,
                        0xD7,
                        0x63,
                        0xF8,
                        0xFF,
                        0xFF,
                        0x3F,
                        0x00,
                        0x05,
                        0xFE,
                        0x02,
                        0xFE,
                        0xDC,
                        0xCC,
                        0x59,
                        0xE7,
                        0x00,
                        0x00,
                        0x00,
                        0x00,
                        0x49,
                        0x45,
                        0x4E,  # IEND chunk
                        0x44,
                        0xAE,
                        0x42,
                        0x60,
                        0x82,
                    ]
                )
            ).decode("utf-8")

            payload = {
                "message": "Build this dashboard UI from the screenshot",
                "workspace_path": workspace,
                "images": [
                    {
                        "filename": "dashboard-mockup.png",
                        "mime_type": "image/png",
                        "data": minimal_png,
                        "description": "Dashboard mockup with sidebar and main content area",
                    }
                ],
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Should have UI-specific questions
                questions = result.get("questions", [])
                ui_questions = [
                    q
                    for q in questions
                    if any(
                        keyword in q.get("question", "").lower()
                        for keyword in ["ui", "component", "state", "responsive"]
                    )
                ]

                print(f"\nUI-related questions: {len(ui_questions)}")
                for q in ui_questions:
                    print(f"  - {q['question']}")

                # Plan title should mention UI
                assert (
                    "UI" in result.get("title", "")
                    or "ui" in result.get("title", "").lower()
                )


class TestQuestionAnswering:
    """Test answering clarifying questions"""

    @pytest.mark.asyncio
    async def test_answer_questions(self):
        """Test answering questions and getting updated plan"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()

            # First, create a plan
            create_payload = {
                "message": "Create a user API with authentication",
                "workspace_path": workspace,
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=create_payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                plan = await response.json()

            # Get questions
            questions = plan.get("questions", [])
            if not questions:
                print("No questions to answer - plan is ready")
                return

            # Answer all questions with first option
            answers = {}
            for q in questions:
                answers[q["id"]] = q["options"][0] if q["options"] else "default"

            # Submit answers
            answer_payload = {"answers": answers}

            async with session.post(
                f"{BASE_URL}/api/navi/plan/{plan['id']}/answer",
                json=answer_payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                updated_plan = await response.json()

                print(f"\nAnswered {len(answers)} questions")
                print(f"Plan status: {updated_plan['status']}")
                print(f"Tasks generated: {updated_plan['total_tasks']}")

                # After answering all questions, should be ready or have tasks
                if updated_plan["unanswered_questions"] == 0:
                    assert updated_plan["status"] in ["ready", "approved"]


class TestPlanApproval:
    """Test plan approval workflow"""

    @pytest.mark.asyncio
    async def test_approve_plan(self):
        """Test approving a ready plan"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()

            # Create a simple plan (no questions expected for very simple requests)
            create_payload = {
                "message": "Add a hello world function",
                "workspace_path": workspace,
            }

            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=create_payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                plan = await response.json()

            # If there are questions, answer them first
            if plan.get("questions"):
                answers = {
                    q["id"]: q["options"][0]
                    for q in plan["questions"]
                    if q.get("options")
                }
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/{plan['id']}/answer",
                    json={"answers": answers},
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ) as response:
                    plan = await response.json()

            # Now approve if ready
            if plan["status"] == "ready":
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/{plan['id']}/approve",
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ) as response:
                    assert response.status == 200
                    approved_plan = await response.json()

                    print("\nPlan approved!")
                    print(f"Status: {approved_plan['status']}")
                    assert approved_plan["status"] == "approved"


class TestPlanExecution:
    """Test plan execution"""

    @pytest.mark.asyncio
    async def test_execute_plan(self):
        """Test executing an approved plan"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()

            # Create and approve a plan
            create_payload = {
                "message": "Create a simple utility function",
                "workspace_path": workspace,
            }

            # Create
            async with session.post(
                f"{BASE_URL}/api/navi/plan/create",
                json=create_payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                plan = await response.json()

            # Answer questions if any
            if plan.get("questions"):
                answers = {
                    q["id"]: q["options"][0]
                    for q in plan["questions"]
                    if q.get("options")
                }
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/{plan['id']}/answer",
                    json={"answers": answers},
                ) as response:
                    plan = await response.json()

            # Approve
            if plan["status"] == "ready":
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/{plan['id']}/approve",
                ) as response:
                    plan = await response.json()

            # Execute (if approved)
            if plan["status"] == "approved":
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/{plan['id']}/execute",
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    assert response.status == 200

                    # Read streaming response
                    events = []
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data:"):
                            event = json.loads(line[5:].strip())
                            events.append(event)
                            print(f"Event: {event.get('type')}")

                    print(f"\nExecution events: {len(events)}")


class TestPlanListing:
    """Test plan listing functionality"""

    @pytest.mark.asyncio
    async def test_list_workspace_plans(self):
        """Test listing plans for a workspace"""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()

            # Create a couple of plans
            for i in range(2):
                payload = {
                    "message": f"Create feature {i+1}",
                    "workspace_path": workspace,
                }
                async with session.post(
                    f"{BASE_URL}/api/navi/plan/create",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ) as response:
                    assert response.status == 200

            # List plans
            async with session.get(
                f"{BASE_URL}/api/navi/plan/workspace/{workspace}",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                assert response.status == 200
                result = await response.json()

                print(f"\nPlans in workspace: {result['total']}")
                assert result["total"] >= 2


class TestClarifyingQuestionGenerator:
    """Test the clarifying question generation logic"""

    def test_auth_questions_generated(self):
        """Test that auth-related keywords trigger auth questions"""
        from backend.services.navi_planner import ClarifyingQuestionGenerator

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Create a login system with user authentication"
        )

        # Should have auth-related question
        auth_questions = [q for q in questions if "auth" in q.question.lower()]
        assert len(auth_questions) > 0
        print(f"Auth questions: {[q.question for q in auth_questions]}")

    def test_database_questions_generated(self):
        """Test that database keywords trigger database questions"""
        from backend.services.navi_planner import ClarifyingQuestionGenerator

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Store user data in a database"
        )

        # Should have database-related question
        db_questions = [q for q in questions if "database" in q.question.lower()]
        assert len(db_questions) > 0

    def test_api_questions_generated(self):
        """Test that API keywords trigger architecture questions"""
        from backend.services.navi_planner import ClarifyingQuestionGenerator

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Build a REST API endpoint for users"
        )

        # Should have API architecture question
        api_questions = [
            q
            for q in questions
            if "api" in q.question.lower() or "architecture" in q.question.lower()
        ]
        assert len(api_questions) > 0

    def test_ui_questions_generated(self):
        """Test that UI keywords trigger UI questions"""
        from backend.services.navi_planner import ClarifyingQuestionGenerator

        questions = ClarifyingQuestionGenerator.generate_ui_questions(
            image_analysis="Dashboard with sidebar navigation"
        )

        # Should have UI-related questions
        assert len(questions) > 0
        print(f"UI questions: {[q.question for q in questions]}")

    def test_questions_have_options(self):
        """Test that all questions have options"""
        from backend.services.navi_planner import ClarifyingQuestionGenerator

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Build a full-stack application with auth, database, and API"
        )

        for q in questions:
            assert len(q.options) >= 2, f"Question '{q.question}' has < 2 options"
            assert q.why_asking, f"Question '{q.question}' missing 'why_asking'"


class TestVisionAnalyzer:
    """Test vision/image analysis capabilities"""

    def test_is_image_attachment(self):
        """Test image attachment detection"""
        from backend.services.navi_planner import VisionAnalyzer

        # Should detect image
        assert VisionAnalyzer.is_image_attachment({"mime_type": "image/png"})
        assert VisionAnalyzer.is_image_attachment({"type": "image/jpeg"})
        assert VisionAnalyzer.is_image_attachment({"kind": "image"})

        # Should not detect non-image
        assert not VisionAnalyzer.is_image_attachment({"mime_type": "text/plain"})
        assert not VisionAnalyzer.is_image_attachment({"kind": "code"})


class TestPlanTaskGeneration:
    """Test task generation for plans"""

    def test_plan_has_testing_task(self):
        """Test that plans include testing tasks"""
        from backend.services.navi_planner import PlanGenerator, ExecutionPlan

        async def run_test():
            plan = ExecutionPlan(
                id="test-123",
                title="Test Plan",
                summary="Test summary",
                original_request="Create a new feature",
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should have a testing task
            testing_tasks = [t for t in plan.tasks if t.task_type == "testing"]
            assert len(testing_tasks) > 0
            print(f"Testing tasks: {[t.title for t in testing_tasks]}")

        asyncio.run(run_test())

    def test_plan_has_documentation_task(self):
        """Test that plans include documentation tasks"""
        from backend.services.navi_planner import PlanGenerator, ExecutionPlan

        async def run_test():
            plan = ExecutionPlan(
                id="test-123",
                title="Test Plan",
                summary="Test summary",
                original_request="Create a new feature",
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should have a documentation task
            doc_tasks = [t for t in plan.tasks if t.task_type == "documentation"]
            assert len(doc_tasks) > 0

        asyncio.run(run_test())


class TestRefactoringQuestions:
    """Test refactoring question generation"""

    def test_refactoring_questions_on_feature_request(self):
        """Test that feature requests trigger refactoring questions"""
        from backend.services.navi_planner import (
            ClarifyingQuestionGenerator,
            QuestionCategory,
        )

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Add a new user profile feature"
        )

        # Should have refactoring question
        refactoring_questions = [
            q for q in questions if q.category == QuestionCategory.REFACTORING
        ]
        assert len(refactoring_questions) > 0
        print(f"Refactoring questions: {[q.question for q in refactoring_questions]}")

    def test_refactoring_questions_have_options(self):
        """Test that refactoring questions have proper options"""
        from backend.services.navi_planner import (
            ClarifyingQuestionGenerator,
            QuestionCategory,
        )

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Build a new authentication system"
        )

        refactoring_questions = [
            q for q in questions if q.category == QuestionCategory.REFACTORING
        ]
        for q in refactoring_questions:
            assert len(q.options) >= 2
            assert (
                "Yes" in q.options[0] or "No" in q.options[2]
            )  # Should have yes/no options


class TestCommitQuestions:
    """Test commit question generation"""

    def test_commit_questions_on_feature_request(self):
        """Test that feature requests trigger commit questions"""
        from backend.services.navi_planner import (
            ClarifyingQuestionGenerator,
            QuestionCategory,
        )

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Implement a new dashboard feature"
        )

        # Should have commit question
        commit_questions = [
            q for q in questions if q.category == QuestionCategory.COMMIT
        ]
        assert len(commit_questions) > 0
        print(f"Commit questions: {[q.question for q in commit_questions]}")

    def test_commit_questions_have_strategies(self):
        """Test that commit questions have different strategy options"""
        from backend.services.navi_planner import (
            ClarifyingQuestionGenerator,
            QuestionCategory,
        )

        questions = ClarifyingQuestionGenerator.generate_questions(
            request="Create a new API endpoint"
        )

        commit_questions = [
            q for q in questions if q.category == QuestionCategory.COMMIT
        ]
        if commit_questions:
            options = commit_questions[0].options
            # Should have auto-commit, single, manual options
            options_text = " ".join(options).lower()
            assert "auto" in options_text or "each task" in options_text
            assert "single" in options_text or "end" in options_text
            assert "manual" in options_text or "don't" in options_text


class TestRefactoringTaskGeneration:
    """Test refactoring task generation in plans"""

    def test_refactoring_task_added_when_requested(self):
        """Test that refactoring task is added when user requests it"""
        from backend.services.navi_planner import (
            PlanGenerator,
            ExecutionPlan,
            ClarifyingQuestion,
            QuestionCategory,
        )

        async def run_test():
            plan = ExecutionPlan(
                id="test-refactor",
                title="Test Plan with Refactoring",
                summary="Test summary",
                original_request="Add a new feature",
                questions=[
                    ClarifyingQuestion(
                        id="q1",
                        category=QuestionCategory.REFACTORING,
                        question="Should I review and improve code?",
                        why_asking="Code quality matters",
                        options=[
                            "Yes, suggest improvements inline",
                            "No, just implement",
                        ],
                        answer="Yes, suggest improvements inline",
                        answered=True,
                    )
                ],
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should have a refactoring task
            refactoring_tasks = [t for t in plan.tasks if t.task_type == "refactoring"]
            assert len(refactoring_tasks) > 0
            print(f"Refactoring task: {refactoring_tasks[0].title}")

        asyncio.run(run_test())

    def test_no_refactoring_task_when_declined(self):
        """Test that no refactoring task when user declines"""
        from backend.services.navi_planner import (
            PlanGenerator,
            ExecutionPlan,
            ClarifyingQuestion,
            QuestionCategory,
        )

        async def run_test():
            plan = ExecutionPlan(
                id="test-no-refactor",
                title="Test Plan without Refactoring",
                summary="Test summary",
                original_request="Add a simple feature",
                questions=[
                    ClarifyingQuestion(
                        id="q1",
                        category=QuestionCategory.REFACTORING,
                        question="Should I review and improve code?",
                        why_asking="Code quality matters",
                        options=["Yes", "No, just implement the feature"],
                        answer="No, just implement the feature",
                        answered=True,
                    )
                ],
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should NOT have a refactoring task
            refactoring_tasks = [t for t in plan.tasks if t.task_type == "refactoring"]
            assert len(refactoring_tasks) == 0

        asyncio.run(run_test())


class TestCommitTaskGeneration:
    """Test commit task generation in plans"""

    def test_commit_task_added_for_auto_commit(self):
        """Test that commit task is added when user wants auto-commit"""
        from backend.services.navi_planner import (
            PlanGenerator,
            ExecutionPlan,
            ClarifyingQuestion,
            QuestionCategory,
        )

        async def run_test():
            plan = ExecutionPlan(
                id="test-auto-commit",
                title="Test Plan with Auto Commit",
                summary="Test summary",
                original_request="Create a new feature",
                questions=[
                    ClarifyingQuestion(
                        id="q1",
                        category=QuestionCategory.COMMIT,
                        question="How to handle git commits?",
                        why_asking="Clean history",
                        options=[
                            "Auto-commit after each task",
                            "Single commit at end",
                            "Don't commit",
                        ],
                        answer="Auto-commit after each task",
                        answered=True,
                    )
                ],
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should have a commit task
            commit_tasks = [t for t in plan.tasks if t.task_type == "commit"]
            assert len(commit_tasks) > 0
            print(f"Commit task: {commit_tasks[0].title}")

        asyncio.run(run_test())

    def test_no_commit_task_when_manual(self):
        """Test that no commit task when user wants manual commits"""
        from backend.services.navi_planner import (
            PlanGenerator,
            ExecutionPlan,
            ClarifyingQuestion,
            QuestionCategory,
        )

        async def run_test():
            plan = ExecutionPlan(
                id="test-manual-commit",
                title="Test Plan with Manual Commits",
                summary="Test summary",
                original_request="Create a simple feature",
                questions=[
                    ClarifyingQuestion(
                        id="q1",
                        category=QuestionCategory.COMMIT,
                        question="How to handle git commits?",
                        why_asking="Clean history",
                        options=[
                            "Auto-commit",
                            "Single commit",
                            "Don't commit, I'll handle it manually",
                        ],
                        answer="Don't commit, I'll handle it manually",
                        answered=True,
                    )
                ],
            )
            plan = await PlanGenerator._generate_tasks(plan, None)

            # Should NOT have a commit task
            commit_tasks = [t for t in plan.tasks if t.task_type == "commit"]
            assert len(commit_tasks) == 0

        asyncio.run(run_test())


class TestCommitMessageGeneration:
    """Test commit message generation"""

    def test_commit_message_uses_conventional_format(self):
        """Test that commit messages follow conventional commit format"""
        from backend.services.navi_planner import PlanExecutor, ExecutionPlan

        plan = ExecutionPlan(
            id="test-msg",
            title="Add user authentication",
            summary="Implement JWT auth",
            original_request="Add user login feature",
        )

        message = PlanExecutor._generate_commit_message(plan, ["auth.py", "login.tsx"])

        # Should use conventional commit format
        assert message.startswith("feat:")
        assert "Add user authentication" in message
        assert "(2 files)" in message

    def test_commit_message_detects_fix_type(self):
        """Test that fix requests generate fix: commits"""
        from backend.services.navi_planner import PlanExecutor, ExecutionPlan

        plan = ExecutionPlan(
            id="test-fix",
            title="Fix login bug",
            summary="Fix auth issue",
            original_request="Fix the login error",
        )

        message = PlanExecutor._generate_commit_message(plan, ["auth.py"])

        assert message.startswith("fix:")

    def test_commit_message_detects_refactor_type(self):
        """Test that refactor requests generate refactor: commits"""
        from backend.services.navi_planner import PlanExecutor, ExecutionPlan

        plan = ExecutionPlan(
            id="test-refactor",
            title="Refactor user service",
            summary="Clean up code",
            original_request="Refactor the user module",
        )

        message = PlanExecutor._generate_commit_message(plan, ["user.py"])

        assert message.startswith("refactor:")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("NAVI PLANNER TEST SUITE")
    print("=" * 60)

    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
