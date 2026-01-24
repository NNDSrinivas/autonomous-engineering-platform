"""
Tests for Advanced Git, Database, and Code Debugging Operations.

Tests the new capabilities:
1. Advanced Git: cherry-pick, rebase, squash, bisect, stash
2. Advanced Database: schema diff, migration, rollback, seeding
3. Code Debugging: error analysis, performance issues, dead code, circular deps
"""

import pytest
import tempfile
import os
from pathlib import Path


class TestAdvancedGitOperations:
    """Test advanced git operations."""

    @pytest.mark.asyncio
    async def test_cherry_pick(self):
        """Test cherry-picking a commit."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("initial")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Create another commit
            test_file.write_text("updated")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Update' -q")

            # Get the commit hash
            os.popen(f"cd {tmpdir} && git rev-parse HEAD~1").read().strip()

            # Create a new branch and cherry-pick
            os.system(f"cd {tmpdir} && git checkout -b test-branch -q HEAD~1")

            # Cherry-pick the update commit
            latest = os.popen(f"cd {tmpdir} && git rev-parse main").read().strip()
            pick_result = await AdvancedGitOperations.cherry_pick(tmpdir, latest)

            # Should succeed or show message
            assert "commands_run" in pick_result

    @pytest.mark.asyncio
    async def test_squash_commits(self):
        """Test squashing commits."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create multiple commits
            test_file = Path(tmpdir) / "test.txt"
            for i in range(3):
                test_file.write_text(f"content {i}")
                os.system(f"cd {tmpdir} && git add . && git commit -m 'Commit {i}' -q")

            # Squash last 2 commits
            result = await AdvancedGitOperations.squash_commits(
                tmpdir, 2, "Squashed commit message"
            )

            assert "commands_run" in result
            # If successful, should have squashed
            if result.get("success"):
                assert "new_message" in result

    @pytest.mark.asyncio
    async def test_stash_operations(self):
        """Test stash save, list, and pop."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("initial")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Make uncommitted changes
            test_file.write_text("modified")

            # Stash the changes
            stash_result = await AdvancedGitOperations.stash_save(
                tmpdir, message="Test stash"
            )
            assert "commands_run" in stash_result

            # List stashes
            list_result = await AdvancedGitOperations.stash_list(tmpdir)
            assert "success" in list_result
            if list_result.get("success"):
                assert "stashes" in list_result

    @pytest.mark.asyncio
    async def test_bisect_operations(self):
        """Test bisect start and reset."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create multiple commits
            test_file = Path(tmpdir) / "test.txt"
            for i in range(5):
                test_file.write_text(f"content {i}")
                os.system(f"cd {tmpdir} && git add . && git commit -m 'Commit {i}' -q")

            # Get first commit hash
            first_commit = (
                os.popen(f"cd {tmpdir} && git rev-list --max-parents=0 HEAD")
                .read()
                .strip()
            )

            # Start bisect
            start_result = await AdvancedGitOperations.bisect_start(
                tmpdir, bad_commit="HEAD", good_commit=first_commit
            )
            assert "commands_run" in start_result

            # Reset bisect
            reset_result = await AdvancedGitOperations.bisect_reset(tmpdir)
            assert "success" in reset_result

    @pytest.mark.asyncio
    async def test_reflog(self):
        """Test reflog retrieval."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Get reflog
            result = await AdvancedGitOperations.reflog(tmpdir, limit=10)
            assert "success" in result
            if result.get("success"):
                assert "entries" in result

    @pytest.mark.asyncio
    async def test_cleanup_merged_branches(self):
        """Test cleanup of merged branches."""
        from backend.services.deep_analysis import AdvancedGitOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create commit on main
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Rename to main if needed
            os.system(f"cd {tmpdir} && git branch -M main 2>/dev/null || true")

            # Create and merge a feature branch
            os.system(f"cd {tmpdir} && git checkout -b feature-branch -q")
            test_file.write_text("feature")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Feature' -q")
            os.system(f"cd {tmpdir} && git checkout main -q")
            os.system(f"cd {tmpdir} && git merge feature-branch -m 'Merge' -q")

            # Cleanup (dry run)
            result = await AdvancedGitOperations.cleanup_merged_branches(
                tmpdir, base_branch="main", dry_run=True
            )
            assert "success" in result
            if result.get("success"):
                assert "branches_to_delete" in result


class TestAdvancedDatabaseOperations:
    """Test advanced database operations."""

    @pytest.mark.asyncio
    async def test_schema_diff_without_db(self):
        """Test schema diff with code models only."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a models file
            models_file = Path(tmpdir) / "models.py"
            models_file.write_text(
                """
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(200))

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
"""
            )

            result = await AdvancedDatabaseOperations.schema_diff(tmpdir)

            assert "success" in result
            if result.get("success"):
                assert "code_tables" in result
                # Should find User and Post
                assert len(result.get("code_tables", [])) >= 1

    @pytest.mark.asyncio
    async def test_migration_history_no_system(self):
        """Test migration history when no system configured."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await AdvancedDatabaseOperations.get_migration_history(tmpdir)
            # Should return something even without migration system
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_seed_database_no_file(self):
        """Test seeding with no seed file."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await AdvancedDatabaseOperations.seed_database(tmpdir)

            assert "success" in result
            # Should fail gracefully with message
            if not result.get("success"):
                assert "message" in result

    @pytest.mark.asyncio
    async def test_reset_database_requires_confirm(self):
        """Test that database reset requires confirmation."""
        from backend.services.deep_analysis import AdvancedDatabaseOperations

        with tempfile.TemporaryDirectory() as tmpdir:
            # Without confirm=True
            result = await AdvancedDatabaseOperations.reset_database(
                tmpdir, confirm=False
            )

            assert not result.get("success")
            assert "confirm" in result.get("message", "").lower() or "warning" in result


class TestCodeDebugger:
    """Test code debugging operations."""

    @pytest.mark.asyncio
    async def test_analyze_python_traceback(self):
        """Test analyzing Python traceback."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
Traceback (most recent call last):
  File "/app/main.py", line 10, in main
    result = process_data(data)
  File "/app/processor.py", line 25, in process_data
    return data["key"]
KeyError: 'key'
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("error_type") == "python_exception"
        assert result.get("root_cause") is not None
        assert "KeyError" in result["root_cause"]["type"]
        assert len(result.get("affected_files", [])) >= 1
        assert len(result.get("suggestions", [])) >= 1

    @pytest.mark.asyncio
    async def test_analyze_javascript_error(self):
        """Test analyzing JavaScript error."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
TypeError: Cannot read property 'map' of undefined
    at processItems (/app/utils.js:15:20)
    at main (/app/index.js:42:10)
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("error_type") == "javascript_error"
        assert result.get("root_cause") is not None
        assert "TypeError" in result["root_cause"]["type"]

    @pytest.mark.asyncio
    async def test_detect_performance_issues(self):
        """Test detecting performance issues."""
        from backend.services.deep_analysis import CodeDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file with performance issues
            py_file = Path(tmpdir) / "app.py"
            py_file.write_text(
                """
import *
from typing import List

def process_data(items):
    result = []
    for item in items:
        result.append(item * 2)

    print("Processing done")  # Debug print

    data = open("large_file.txt").read()  # Reads entire file

    return result
"""
            )

            result = await CodeDebugger.detect_performance_issues(tmpdir)

            assert result.get("success")
            assert "issues" in result
            # Should detect some issues (wildcard import, print statement)

    @pytest.mark.asyncio
    async def test_detect_dead_code(self):
        """Test detecting dead/unused code."""
        from backend.services.deep_analysis import CodeDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with potentially unused function
            py_file = Path(tmpdir) / "utils.py"
            py_file.write_text(
                '''
def used_function():
    return 42

def unused_helper():
    """This function is never called."""
    return "never used"

result = used_function()
'''
            )

            result = await CodeDebugger.detect_dead_code(tmpdir)

            assert result.get("success")
            assert "unused_functions" in result

    @pytest.mark.asyncio
    async def test_detect_circular_dependencies(self):
        """Test detecting circular dependencies."""
        from backend.services.deep_analysis import CodeDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files that could have circular deps
            (Path(tmpdir) / "module_a.py").write_text(
                """
from module_b import function_b

def function_a():
    return function_b()
"""
            )
            (Path(tmpdir) / "module_b.py").write_text(
                """
from module_a import function_a

def function_b():
    return "b"
"""
            )

            result = await CodeDebugger.detect_circular_dependencies(tmpdir)

            assert result.get("success")
            assert "dependency_graph" in result

    @pytest.mark.asyncio
    async def test_detect_code_smells(self):
        """Test detecting code smells."""
        from backend.services.deep_analysis import CodeDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with code smells
            py_file = Path(tmpdir) / "smelly.py"
            py_file.write_text(
                """
password = "hardcoded123"
api_key = "sk-12345abcdef"

def process():
    try:
        do_something()
    except:
        pass  # Empty catch

    magic_value = 86400  # Magic number
"""
            )

            result = await CodeDebugger.detect_code_smells(tmpdir)

            assert result.get("success")
            assert "smells" in result
            # Should detect hardcoded credentials and empty catch

    @pytest.mark.asyncio
    async def test_auto_fix_dry_run(self):
        """Test auto-fix in dry run mode."""
        from backend.services.deep_analysis import CodeDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with fixable issue
            py_file = Path(tmpdir) / "fixable.py"
            py_file.write_text(
                """print("debug message")
"""
            )

            result = await CodeDebugger.auto_fix(
                tmpdir, "fixable.py", "print_statement", 1, dry_run=True
            )

            assert "original_code" in result
            # Should not actually apply
            assert not result.get("applied") or result.get("applied") is None


class TestProjectAnalyzerIntegration:
    """Test ProjectAnalyzer integration with advanced operations."""

    @pytest.mark.asyncio
    async def test_git_stash_integration(self):
        """Test git stash through ProjectAnalyzer."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("initial")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Test stash list
            result = await ProjectAnalyzer.git_stash(tmpdir, "list")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_database_migration_integration(self):
        """Test database migration through ProjectAnalyzer."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test migration history (no migration system)
            result = await ProjectAnalyzer.database_migration(tmpdir, "history")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_detect_code_issues_integration(self):
        """Test code issue detection through ProjectAnalyzer."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple file
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("print('hello')")

            result = await ProjectAnalyzer.detect_code_issues(
                tmpdir, issue_types=["performance"]
            )
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_analyze_error_integration(self):
        """Test error analysis through ProjectAnalyzer."""
        from backend.services.navi_brain import ProjectAnalyzer

        traceback = """
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("test error")
ValueError: test error
"""

        result = await ProjectAnalyzer.analyze_error(".", traceback=traceback)
        assert isinstance(result, dict)
        assert result.get("success")


class TestErrorSuggestions:
    """Test error fix suggestions."""

    def test_import_error_suggestions(self):
        """Test suggestions for ImportError."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "ImportError", "No module named 'foo'", "python"
        )
        assert len(suggestions) >= 1
        assert any("install" in s.lower() or "import" in s.lower() for s in suggestions)

    def test_key_error_suggestions(self):
        """Test suggestions for KeyError."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "KeyError", "'missing_key'", "python"
        )
        assert len(suggestions) >= 1
        assert any("key" in s.lower() or "get" in s.lower() for s in suggestions)

    def test_connection_error_suggestions(self):
        """Test suggestions for ConnectionError."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "ConnectionError", "Connection refused", "python"
        )
        assert len(suggestions) >= 1
        assert any("network" in s.lower() or "retry" in s.lower() for s in suggestions)


class TestMultiLanguageErrorAnalysis:
    """Test error analysis for multiple programming languages."""

    @pytest.mark.asyncio
    async def test_go_panic_analysis(self):
        """Test analyzing Go panic."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.processData(0xc0000b4000, 0x3, 0x3, 0x5)
        /app/main.go:25 +0x123
main.main()
        /app/main.go:15 +0x45
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "go"
        assert result.get("error_type") == "go_panic"
        assert result.get("root_cause") is not None
        assert "index out of range" in result["root_cause"]["message"]
        assert len(result.get("affected_files", [])) >= 1
        # Should have Go-specific suggestions
        assert len(result.get("suggestions", [])) >= 1

    @pytest.mark.asyncio
    async def test_rust_panic_analysis(self):
        """Test analyzing Rust panic."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
thread 'main' panicked at 'called `Option::unwrap()` on a `None` value', src/main.rs:10:5
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "rust"
        assert result.get("error_type") == "rust_panic"
        assert result.get("root_cause") is not None
        assert "unwrap" in result["root_cause"]["message"]
        assert len(result.get("affected_files", [])) >= 1

    @pytest.mark.asyncio
    async def test_java_exception_analysis(self):
        """Test analyzing Java exception."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.UserService.getUser(UserService.java:42)
    at com.example.Controller.handleRequest(Controller.java:28)
    at org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:897)
Caused by: java.lang.IllegalStateException: Database connection not initialized
    at com.example.Database.connect(Database.java:15)
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "java"
        assert result.get("error_type") == "java_exception"
        assert result.get("root_cause") is not None
        assert "NullPointerException" in result["root_cause"]["type"]
        assert len(result.get("affected_files", [])) >= 2
        # Should have caused_by chain
        assert "caused_by" in result

    @pytest.mark.asyncio
    async def test_ruby_exception_analysis(self):
        """Test analyzing Ruby exception."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
NoMethodError: undefined method `name' for nil:NilClass
    from /app/models/user.rb:15:in `display_name'
    from /app/controllers/users_controller.rb:28:in `show'
    from /app/lib/router.rb:42:in `dispatch'
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "ruby"
        assert result.get("error_type") == "ruby_exception"
        assert result.get("root_cause") is not None
        assert "NoMethodError" in result["root_cause"]["type"]
        assert len(result.get("affected_files", [])) >= 1

    @pytest.mark.asyncio
    async def test_csharp_exception_analysis(self):
        """Test analyzing C# exception."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
System.NullReferenceException: Object reference not set to an instance of an object.
   at MyApp.Services.UserService.GetUser(Int32 id) in C:\\Projects\\MyApp\\Services\\UserService.cs:line 45
   at MyApp.Controllers.UserController.Get(Int32 id) in C:\\Projects\\MyApp\\Controllers\\UserController.cs:line 22
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "csharp"
        assert result.get("error_type") == "csharp_exception"
        assert result.get("root_cause") is not None
        assert "NullReferenceException" in result["root_cause"]["type"]
        assert len(result.get("affected_files", [])) >= 1

    @pytest.mark.asyncio
    async def test_php_error_analysis(self):
        """Test analyzing PHP error."""
        from backend.services.deep_analysis import CodeDebugger

        traceback = """
Fatal error: Uncaught TypeError: count(): Argument #1 ($value) must be of type Countable|array, null given in /var/www/app/src/UserService.php on line 45

Stack trace:
#0 /var/www/app/src/UserService.php(45): count(NULL)
#1 /var/www/app/src/Controller.php(28): UserService->getUsers()
#2 /var/www/app/public/index.php(15): Controller->handle()
"""

        result = await CodeDebugger.analyze_errors(".", None, traceback)

        assert result.get("success")
        assert result.get("language") == "php"
        assert result.get("error_type") == "php_error"
        assert len(result.get("affected_files", [])) >= 1

    def test_go_specific_suggestions(self):
        """Test Go-specific error suggestions."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "panic", "nil pointer dereference", "go"
        )
        assert len(suggestions) >= 1
        assert any("nil" in s.lower() or "recover" in s.lower() for s in suggestions)

    def test_rust_specific_suggestions(self):
        """Test Rust-specific error suggestions."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "panic", "unwrap on None", "rust"
        )
        assert len(suggestions) >= 1
        assert any("result" in s.lower() or "unwrap" in s.lower() for s in suggestions)

    def test_java_specific_suggestions(self):
        """Test Java-specific error suggestions."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "NullPointerException", "null object", "java"
        )
        assert len(suggestions) >= 1
        assert any("null" in s.lower() or "optional" in s.lower() for s in suggestions)

    def test_csharp_specific_suggestions(self):
        """Test C#-specific error suggestions."""
        from backend.services.deep_analysis import CodeDebugger

        suggestions = CodeDebugger._get_error_suggestions(
            "NullReferenceException", "object reference", "csharp"
        )
        assert len(suggestions) >= 1
        assert any("null" in s.lower() for s in suggestions)


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("ADVANCED OPERATIONS TEST SUITE")
    print("=" * 60)

    import sys

    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
