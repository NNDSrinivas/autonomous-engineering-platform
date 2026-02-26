#!/usr/bin/env python3
"""
End-to-End Integration Tests for NAVI v1

Tests all 4 core systems:
1. Telemetry (LLM metrics, RAG metrics)
2. Feedback (generation logging, genId tracking)
3. RAG (context retrieval)
4. Learning (feedback bridge)

Usage:
    python scripts/test_integrations.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from backend.core.db import SessionLocal
from backend.services.feedback_service import FeedbackService
from backend.services.workspace_rag import get_context_for_task
from backend.services.feedback_learning import get_feedback_manager


class IntegrationTester:
    def __init__(self, backend_url: str = "http://localhost:8787"):
        self.backend_url = backend_url
        self.results = []

    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append((name, passed, details))
        print(f"{status} | {name}")
        if details:
            print(f"     {details}")

    async def test_telemetry_endpoint(self):
        """Test 1: Verify telemetry endpoint is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.backend_url}/api/telemetry/health", timeout=5.0
                )
                passed = response.status_code == 200
                details = f"Status: {response.status_code}"
                if passed:
                    data = response.json()
                    details += f" | Response: {data}"
                self.log_test("Telemetry Endpoint Health", passed, details)
                return passed
        except Exception as e:
            self.log_test("Telemetry Endpoint Health", False, f"Error: {e}")
            return False

    async def test_metrics_endpoint(self):
        """Test 2: Verify Prometheus metrics endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.backend_url}/metrics", timeout=5.0)
                passed = response.status_code == 200
                content = response.text

                # Check for expected metrics
                has_llm_metrics = "aep_llm_calls_total" in content
                has_rag_metrics = "aep_rag_retrieval_latency_ms" in content

                details = f"Status: {response.status_code}"
                if has_llm_metrics:
                    details += " | LLM metrics: ✓"
                if has_rag_metrics:
                    details += " | RAG metrics: ✓"

                passed = passed and has_llm_metrics
                self.log_test("Prometheus Metrics Endpoint", passed, details)
                return passed
        except Exception as e:
            self.log_test("Prometheus Metrics Endpoint", False, f"Error: {e}")
            return False

    async def test_feedback_database_schema(self):
        """Test 3: Verify feedback database tables exist."""
        try:
            db = SessionLocal()
            try:
                from backend.models.ai_feedback import AiGenerationLog, AiFeedback

                # Try to query tables (will fail if tables don't exist)
                from sqlalchemy import select

                result = await db.execute(select(AiGenerationLog).limit(1))
                result = await db.execute(select(AiFeedback).limit(1))

                self.log_test("Feedback Database Schema", True, "Tables exist")
                return True
            finally:
                await db.close()
        except Exception as e:
            self.log_test("Feedback Database Schema", False, f"Error: {e}")
            return False

    async def test_rag_retrieval(self):
        """Test 4: Verify RAG context retrieval works."""
        try:
            workspace_path = str(Path(__file__).parent.parent)

            start_time = time.time()
            context = await get_context_for_task(
                workspace_path=workspace_path,
                task_description="What is the autonomous agent architecture?",
                max_context_tokens=1000,
            )
            duration_ms = (time.time() - start_time) * 1000

            has_content = context and len(context.strip()) > 0
            details = f"Retrieved: {len(context) if context else 0} chars in {duration_ms:.0f}ms"

            self.log_test("RAG Context Retrieval", has_content, details)
            return has_content
        except Exception as e:
            self.log_test("RAG Context Retrieval", False, f"Error: {e}")
            return False

    async def test_learning_manager(self):
        """Test 5: Verify learning system is accessible."""
        try:
            manager = get_feedback_manager()

            # Test tracking a suggestion
            suggestion = manager.track_suggestion(
                suggestion_id="test_001",
                category=manager.store.suggestions.get("test_001", None)
                and "explanation"
                or "explanation",
                content="Test suggestion",
                context="Test context",
                org_id="test-org",
                user_id="test-user",
            )

            passed = suggestion is not None
            details = f"Suggestion ID: {suggestion.id if suggestion else 'None'}"

            self.log_test("Learning System Manager", passed, details)
            return passed
        except Exception as e:
            self.log_test("Learning System Manager", False, f"Error: {e}")
            return False

    async def test_feedback_service(self):
        """Test 6: Verify feedback service can log generations."""
        try:
            db = SessionLocal()
            try:
                service = FeedbackService(db)

                # Test logging a generation
                gen_id = await service.log_generation(
                    org_key="test-org",
                    user_sub="test-user",
                    task_type="chat",
                    model="claude-sonnet-4",
                    temperature=0.0,
                    params={"test": True},
                    prompt="Test prompt",
                )

                passed = gen_id is not None and gen_id > 0
                details = f"Generated ID: {gen_id}"

                self.log_test("Feedback Service Generation Logging", passed, details)
                return passed
            finally:
                await db.close()
        except Exception as e:
            self.log_test("Feedback Service Generation Logging", False, f"Error: {e}")
            return False

    async def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 60)
        print("NAVI v1 Integration Tests")
        print("=" * 60)
        print()

        tests = [
            (
                "Backend Services",
                [
                    self.test_telemetry_endpoint,
                    self.test_metrics_endpoint,
                    self.test_feedback_database_schema,
                ],
            ),
            (
                "Core Systems",
                [
                    self.test_rag_retrieval,
                    self.test_learning_manager,
                    self.test_feedback_service,
                ],
            ),
        ]

        all_passed = True

        for section_name, section_tests in tests:
            print(f"\n📋 {section_name}")
            print("-" * 60)

            for test_func in section_tests:
                passed = await test_func()
                all_passed = all_passed and passed

        print()
        print("=" * 60)
        print("Test Summary")
        print("=" * 60)

        passed_count = sum(1 for _, passed, _ in self.results if passed)
        total_count = len(self.results)

        print(f"Passed: {passed_count}/{total_count}")
        print()

        if all_passed:
            print("✅ ALL TESTS PASSED - v1 Integration Complete!")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Review failures above")
            return 1


async def main():
    """Main entry point."""
    tester = IntegrationTester()
    exit_code = await tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
