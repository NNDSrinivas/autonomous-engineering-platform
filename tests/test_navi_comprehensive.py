#!/usr/bin/env python3
"""
NAVI Comprehensive Test Suite

Tests NAVI across multiple domains:
1. Backend (Python, Node.js, Go)
2. Frontend (React, Vue, TypeScript)
3. DevOps (Docker, CI/CD, Terraform)
4. Data Engineering (SQL, Pandas, ETL)
5. Architecture (System Design, API Design)

Each test validates:
- Code generation
- Syntax validity
- Language-specific patterns
"""

import asyncio
import aiohttp
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple
from enum import Enum

BASE_URL = "http://localhost:8000"


class Domain(Enum):
    BACKEND_PYTHON = "backend_python"
    BACKEND_NODE = "backend_node"
    BACKEND_GO = "backend_go"
    FRONTEND_REACT = "frontend_react"
    FRONTEND_VUE = "frontend_vue"
    DEVOPS_DOCKER = "devops_docker"
    DEVOPS_CICD = "devops_cicd"
    DATA_SQL = "data_sql"
    DATA_PANDAS = "data_pandas"
    ARCHITECTURE = "architecture"


@dataclass
class TestCase:
    name: str
    domain: Domain
    prompt: str
    expected_files: List[str]  # File patterns to expect
    validation_commands: List[str]  # Commands to validate output
    required_patterns: List[str]  # Patterns that must appear in generated code


# ============================================================
# TEST CASES BY DOMAIN
# ============================================================

BACKEND_PYTHON_TESTS = [
    TestCase(
        name="FastAPI CRUD API",
        domain=Domain.BACKEND_PYTHON,
        prompt="""Create a FastAPI CRUD API for a 'products' resource:
        - models.py: Pydantic Product model (id, name, price, description)
        - routes.py: GET /products, GET /products/{id}, POST /products, PUT /products/{id}, DELETE /products/{id}
        - database.py: In-memory storage (list)
        Create all 3 files.""",
        expected_files=["models.py", "routes.py", "database.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["FastAPI", "BaseModel", "@router", "async def"],
    ),
    TestCase(
        name="SQLAlchemy Models",
        domain=Domain.BACKEND_PYTHON,
        prompt="""Create SQLAlchemy models for a blog:
        - models.py: User (id, email, name), Post (id, title, content, user_id), Comment (id, text, post_id, user_id)
        - Include relationships and foreign keys
        Create the file with all models.""",
        expected_files=["models.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["Column", "ForeignKey", "relationship", "Base"],
    ),
    TestCase(
        name="Async Task Queue",
        domain=Domain.BACKEND_PYTHON,
        prompt="""Create an async task queue system:
        - task_queue.py: AsyncTaskQueue class with add_task(), process_tasks(), get_status()
        - worker.py: Worker class that processes tasks from the queue
        Create both files.""",
        expected_files=["task_queue.py", "worker.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["async", "await", "asyncio", "Queue"],
    ),
    TestCase(
        name="JWT Authentication",
        domain=Domain.BACKEND_PYTHON,
        prompt="""Create JWT authentication utilities:
        - auth.py: create_token(), verify_token(), hash_password(), verify_password()
        - middleware.py: AuthMiddleware class for FastAPI
        Create both files.""",
        expected_files=["auth.py", "middleware.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["jwt", "hash", "verify", "token"],
    ),
]

BACKEND_NODE_TESTS = [
    TestCase(
        name="Express REST API",
        domain=Domain.BACKEND_NODE,
        prompt="""Create an Express.js REST API:
        - app.js: Express app setup with middleware
        - routes/users.js: CRUD routes for users
        - controllers/userController.js: Controller functions
        Create all 3 files.""",
        expected_files=["app.js", "users.js", "userController.js"],
        validation_commands=["node --check {file}"],
        required_patterns=["express", "router", "req", "res", "module.exports"],
    ),
    TestCase(
        name="TypeScript Express API",
        domain=Domain.BACKEND_NODE,
        prompt="""Create a TypeScript Express API:
        - app.ts: Express app with type annotations
        - types.ts: User interface, CreateUserDTO, UpdateUserDTO
        - routes.ts: Typed route handlers
        Create all 3 files.""",
        expected_files=["app.ts", "types.ts", "routes.ts"],
        validation_commands=[],  # TypeScript needs tsc which may not be installed
        required_patterns=["interface", "Request", "Response", "export"],
    ),
]

FRONTEND_REACT_TESTS = [
    TestCase(
        name="React Component with Hooks",
        domain=Domain.FRONTEND_REACT,
        prompt="""Create a React todo list component:
        - TodoList.tsx: Main component with useState, useEffect
        - TodoItem.tsx: Single todo item component
        - useTodos.ts: Custom hook for todo CRUD operations
        - types.ts: Todo interface
        Create all 4 files.""",
        expected_files=["TodoList.tsx", "TodoItem.tsx", "useTodos.ts", "types.ts"],
        validation_commands=[],  # TSX needs special handling
        required_patterns=["useState", "useEffect", "interface", "export"],
    ),
    TestCase(
        name="React Context Provider",
        domain=Domain.FRONTEND_REACT,
        prompt="""Create a React auth context:
        - AuthContext.tsx: Context with user state, login, logout
        - AuthProvider.tsx: Provider component
        - useAuth.ts: Custom hook to use auth context
        Create all 3 files.""",
        expected_files=["AuthContext.tsx", "AuthProvider.tsx", "useAuth.ts"],
        validation_commands=[],
        required_patterns=["createContext", "useContext", "Provider", "useState"],
    ),
]

FRONTEND_VUE_TESTS = [
    TestCase(
        name="Vue 3 Composition API Component",
        domain=Domain.FRONTEND_VUE,
        prompt="""Create a Vue 3 component using Composition API:
        - TaskList.vue: Component with ref, computed, watch
        - useTaskStore.ts: Composable for task management
        Create both files.""",
        expected_files=["TaskList.vue", "useTaskStore.ts"],
        validation_commands=[],
        required_patterns=["ref", "computed", "defineComponent", "setup"],
    ),
]

DEVOPS_DOCKER_TESTS = [
    TestCase(
        name="Multi-stage Dockerfile",
        domain=Domain.DEVOPS_DOCKER,
        prompt="""Create a multi-stage Dockerfile for a Node.js app:
        - Dockerfile: Build stage (npm install, build) and production stage (minimal image)
        - docker-compose.yml: App service + PostgreSQL + Redis
        - .dockerignore: Proper ignore patterns
        Create all 3 files.""",
        expected_files=["Dockerfile", "docker-compose.yml", ".dockerignore"],
        validation_commands=[],  # Docker validation needs docker installed
        required_patterns=["FROM", "COPY", "RUN", "services:", "node_modules"],
    ),
    TestCase(
        name="Python Dockerfile",
        domain=Domain.DEVOPS_DOCKER,
        prompt="""Create Docker setup for a Python FastAPI app:
        - Dockerfile: Python 3.11, requirements install, uvicorn
        - docker-compose.yml: App + MongoDB
        Create both files.""",
        expected_files=["Dockerfile", "docker-compose.yml"],
        validation_commands=[],
        required_patterns=["python", "pip", "uvicorn", "mongo"],
    ),
]

DEVOPS_CICD_TESTS = [
    TestCase(
        name="GitHub Actions CI/CD",
        domain=Domain.DEVOPS_CICD,
        prompt="""Create GitHub Actions workflows:
        - .github/workflows/ci.yml: Test on push/PR (lint, test, build)
        - .github/workflows/deploy.yml: Deploy to production on main branch
        Create both files.""",
        expected_files=["ci.yml", "deploy.yml"],
        validation_commands=[],  # YAML validation
        required_patterns=["on:", "jobs:", "runs-on:", "steps:"],
    ),
]

DATA_TESTS = [
    TestCase(
        name="Pandas Data Pipeline",
        domain=Domain.DATA_PANDAS,
        prompt="""Create a data processing pipeline:
        - pipeline.py: DataPipeline class with extract(), transform(), load() methods
        - transformers.py: Functions for cleaning, normalizing, aggregating data
        Create both files.""",
        expected_files=["pipeline.py", "transformers.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["pandas", "DataFrame", "def extract", "def transform"],
    ),
    TestCase(
        name="SQL Query Builder",
        domain=Domain.DATA_SQL,
        prompt="""Create a SQL query builder:
        - query_builder.py: QueryBuilder class with select(), where(), join(), order_by(), build()
        - Example usage in docstrings
        Create the file.""",
        expected_files=["query_builder.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["SELECT", "WHERE", "JOIN", "class QueryBuilder"],
    ),
]

ARCHITECTURE_TESTS = [
    TestCase(
        name="Repository Pattern",
        domain=Domain.ARCHITECTURE,
        prompt="""Implement the repository pattern:
        - interfaces.py: Abstract Repository class
        - user_repository.py: UserRepository implementing the interface
        - unit_of_work.py: UnitOfWork for transaction management
        Create all 3 files.""",
        expected_files=["interfaces.py", "user_repository.py", "unit_of_work.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["ABC", "abstractmethod", "class.*Repository"],
    ),
    TestCase(
        name="Event-Driven Architecture",
        domain=Domain.ARCHITECTURE,
        prompt="""Create an event-driven system:
        - events.py: Event base class, UserCreated, OrderPlaced events
        - event_bus.py: EventBus with subscribe(), publish()
        - handlers.py: Event handlers
        Create all 3 files.""",
        expected_files=["events.py", "event_bus.py", "handlers.py"],
        validation_commands=["python3 -m py_compile {file}"],
        required_patterns=["Event", "subscribe", "publish", "handler"],
    ),
]

# Combine all tests
ALL_TESTS = (
    BACKEND_PYTHON_TESTS
    + BACKEND_NODE_TESTS
    + FRONTEND_REACT_TESTS
    + FRONTEND_VUE_TESTS
    + DEVOPS_DOCKER_TESTS
    + DEVOPS_CICD_TESTS
    + DATA_TESTS
    + ARCHITECTURE_TESTS
)


# ============================================================
# TEST RUNNER
# ============================================================


async def send_navi_request(prompt: str, workspace: str) -> Dict:
    """Send request to NAVI and collect response."""
    payload = {
        "message": prompt,
        "mode": "agent",
        "workspace_root": workspace,
        "attachments": [],
        "conversationHistory": [],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/navi/chat/stream",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            content = ""
            thinking = ""
            actions = []

            async for line in response.content:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "content" in data:
                            content += data["content"]
                        if "thinking" in data:
                            thinking += data["thinking"]
                        if "actions" in data:
                            actions.extend(data["actions"])
                    except Exception:
                        pass

            return {"content": content, "thinking": thinking, "actions": actions}


def extract_files(response: Dict) -> Dict[str, str]:
    """Extract files from NAVI response."""
    files = {}
    for action in response.get("actions", []):
        if action.get("type") in ("createFile", "create", "editFile", "edit"):
            path = action.get("filePath") or action.get("path", "")
            content = action.get("content", "")
            if path and content:
                # Use just the filename for matching
                files[Path(path).name] = content
    return files


def validate_file(filepath: Path, commands: List[str]) -> Tuple[bool, str]:
    """Run validation commands on a file."""
    for cmd_template in commands:
        cmd = cmd_template.replace("{file}", str(filepath))
        try:
            result = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False, result.stderr[:200]
        except Exception as e:
            return False, str(e)
    return True, ""


def check_patterns(content: str, patterns: List[str]) -> Tuple[bool, List[str]]:
    """Check if required patterns exist in content."""
    import re

    missing = []
    for pattern in patterns:
        if not re.search(pattern, content, re.IGNORECASE):
            missing.append(pattern)
    return len(missing) == 0, missing


async def run_test(test: TestCase, test_dir: Path) -> Dict:
    """Run a single test case."""
    result = {
        "name": test.name,
        "domain": test.domain.value,
        "passed": False,
        "files_generated": 0,
        "files_expected": len(test.expected_files),
        "syntax_valid": 0,
        "patterns_found": 0,
        "patterns_expected": len(test.required_patterns),
        "errors": [],
    }

    try:
        # Send request
        response = await send_navi_request(test.prompt, str(test_dir))
        files = extract_files(response)
        result["files_generated"] = len(files)

        if not files:
            result["errors"].append("No files generated")
            return result

        # Check expected files
        found_files = set(files.keys())
        expected_set = set(test.expected_files)

        # Fuzzy match - check if expected files are in generated files
        matched_files = 0
        for expected in expected_set:
            for found in found_files:
                if (
                    expected.lower() in found.lower()
                    or found.lower() in expected.lower()
                ):
                    matched_files += 1
                    break

        # Write files and validate
        all_content = ""
        for filename, content in files.items():
            filepath = test_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            all_content += content + "\n"

            # Run validation commands
            if test.validation_commands:
                valid, error = validate_file(filepath, test.validation_commands)
                if valid:
                    result["syntax_valid"] += 1
                else:
                    result["errors"].append(f"{filename}: {error}")
            else:
                result["syntax_valid"] += 1  # No validation = assume valid

        # Check patterns
        patterns_ok, missing = check_patterns(all_content, test.required_patterns)
        result["patterns_found"] = len(test.required_patterns) - len(missing)
        if missing:
            result["errors"].append(f"Missing patterns: {missing}")

        # Determine pass/fail
        files_ok = matched_files >= len(expected_set) * 0.75  # 75% of expected files
        syntax_ok = result["syntax_valid"] >= result["files_generated"] * 0.75
        patterns_ok = result["patterns_found"] >= result["patterns_expected"] * 0.5

        result["passed"] = files_ok and syntax_ok and patterns_ok

    except Exception as e:
        result["errors"].append(str(e))

    return result


async def run_domain_tests(domain: Domain, tests: List[TestCase]) -> List[Dict]:
    """Run all tests for a domain."""
    results = []

    for test in tests:
        if test.domain != domain:
            continue

        print(f"\n  Running: {test.name}...")

        # Create temp directory for this test
        test_dir = Path(tempfile.mkdtemp(prefix=f"navi_test_{domain.value}_"))

        try:
            result = await run_test(test, test_dir)
            results.append(result)

            status = "✅" if result["passed"] else "❌"
            print(f"  {status} {test.name}")
            print(f"     Files: {result['files_generated']}/{result['files_expected']}")
            print(f"     Syntax: {result['syntax_valid']}/{result['files_generated']}")
            print(
                f"     Patterns: {result['patterns_found']}/{result['patterns_expected']}"
            )
            if result["errors"]:
                print(f"     Errors: {result['errors'][:2]}")
        finally:
            # Cleanup
            shutil.rmtree(test_dir, ignore_errors=True)

        # Small delay between tests
        await asyncio.sleep(1)

    return results


async def run_all_tests():
    """Run the complete test suite."""
    print("=" * 70)
    print("NAVI COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    all_results = []
    domain_summary = {}

    domains = [
        (Domain.BACKEND_PYTHON, "Backend - Python"),
        (Domain.BACKEND_NODE, "Backend - Node.js"),
        (Domain.FRONTEND_REACT, "Frontend - React"),
        (Domain.FRONTEND_VUE, "Frontend - Vue"),
        (Domain.DEVOPS_DOCKER, "DevOps - Docker"),
        (Domain.DEVOPS_CICD, "DevOps - CI/CD"),
        (Domain.DATA_PANDAS, "Data - Pandas"),
        (Domain.DATA_SQL, "Data - SQL"),
        (Domain.ARCHITECTURE, "Architecture Patterns"),
    ]

    for domain, domain_name in domains:
        domain_tests = [t for t in ALL_TESTS if t.domain == domain]
        if not domain_tests:
            continue

        print(f"\n{'=' * 70}")
        print(f"DOMAIN: {domain_name}")
        print(f"{'=' * 70}")

        results = await run_domain_tests(domain, domain_tests)
        all_results.extend(results)

        passed = sum(1 for r in results if r["passed"])
        total = len(results)
        domain_summary[domain_name] = {"passed": passed, "total": total}

    # Final Summary
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TEST SUMMARY")
    print("=" * 70)

    total_passed = sum(1 for r in all_results if r["passed"])
    total_tests = len(all_results)

    print("\nBy Domain:")
    for domain_name, stats in domain_summary.items():
        pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        status = "✅" if pct >= 75 else "⚠️" if pct >= 50 else "❌"
        print(
            f"  {status} {domain_name}: {stats['passed']}/{stats['total']} ({pct:.0f}%)"
        )

    print(
        f"\nOverall: {total_passed}/{total_tests} tests passed ({total_passed/total_tests*100:.1f}%)"
    )

    # Detailed failures
    failures = [r for r in all_results if not r["passed"]]
    if failures:
        print(f"\nFailed Tests ({len(failures)}):")
        for f in failures:
            print(f"  ❌ {f['name']} ({f['domain']})")
            if f["errors"]:
                print(f"     Reason: {f['errors'][0][:100]}")

    return total_passed == total_tests


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
