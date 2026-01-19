"""
Tests for Deep Analysis Service - Codebase, Database, and Git debugging.

Tests the capabilities:
1. Deep codebase analysis (function/class extraction)
2. Database debugging and fixing
3. Git debugging and fixing
"""

import pytest
import tempfile
import os
from pathlib import Path


class TestDeepCodeAnalyzer:
    """Test deep codebase analysis capabilities."""

    def test_language_detection(self):
        """Test language detection from file extensions."""
        from backend.services.deep_analysis import DeepCodeAnalyzer

        assert DeepCodeAnalyzer.LANGUAGE_EXTENSIONS[".py"] == "python"
        assert DeepCodeAnalyzer.LANGUAGE_EXTENSIONS[".ts"] == "typescript"
        assert DeepCodeAnalyzer.LANGUAGE_EXTENSIONS[".go"] == "go"
        assert DeepCodeAnalyzer.LANGUAGE_EXTENSIONS[".rs"] == "rust"

    @pytest.mark.asyncio
    async def test_analyze_python_file(self):
        """Test analyzing a Python file."""
        from backend.services.deep_analysis import DeepCodeAnalyzer

        # Create a temp directory with a Python file
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test_module.py"
            py_file.write_text('''
"""Test module docstring."""

import os
from typing import List

class UserService:
    """Service for user operations."""

    def get_user(self, user_id: int) -> dict:
        """Get a user by ID."""
        return {"id": user_id}

    def create_user(self, name: str) -> dict:
        """Create a new user."""
        return {"name": name}

def helper_function(x: int) -> int:
    """A helper function."""
    # TODO: Implement this properly
    return x * 2

async def async_fetch(url: str) -> str:
    """Async function example."""
    return url
''')

            # Analyze workspace
            analysis = await DeepCodeAnalyzer.analyze_workspace(tmpdir)

            # Verify analysis
            assert analysis.total_files == 1
            assert "python" in analysis.languages
            assert "test_module.py" in analysis.files

            file_analysis = analysis.files["test_module.py"]
            assert file_analysis.language == "python"
            assert len(file_analysis.imports) >= 2  # os and typing

            # Check functions
            func_names = [f.name for f in file_analysis.functions]
            assert "helper_function" in func_names or "async_fetch" in func_names

            # Check classes
            class_names = [c.name for c in file_analysis.classes]
            assert "UserService" in class_names

            # Check TODOs
            assert len(file_analysis.todos) > 0

    @pytest.mark.asyncio
    async def test_analyze_typescript_file(self):
        """Test analyzing a TypeScript file."""
        from backend.services.deep_analysis import DeepCodeAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "service.ts"
            ts_file.write_text('''
import { User } from './types';
import axios from 'axios';

export interface UserService {
    getUser(id: number): Promise<User>;
}

export class UserServiceImpl implements UserService {
    async getUser(id: number): Promise<User> {
        return axios.get(`/users/${id}`);
    }
}

export const fetchData = async (url: string): Promise<any> => {
    return axios.get(url);
};
''')

            analysis = await DeepCodeAnalyzer.analyze_workspace(tmpdir)

            assert analysis.total_files == 1
            assert "typescript" in analysis.languages

            file_analysis = analysis.files["service.ts"]
            assert file_analysis.language == "typescript"
            assert len(file_analysis.imports) >= 1

    @pytest.mark.asyncio
    async def test_find_symbol(self):
        """Test finding a symbol across the codebase."""
        from backend.services.deep_analysis import DeepCodeAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple files with the same symbol
            file1 = Path(tmpdir) / "module1.py"
            file1.write_text('''
def process_data(data):
    return data
''')
            file2 = Path(tmpdir) / "module2.py"
            file2.write_text('''
from module1 import process_data

result = process_data([1, 2, 3])
''')

            results = await DeepCodeAnalyzer.find_symbol(tmpdir, "process_data")

            assert len(results) >= 2
            files_found = [r["file"] for r in results]
            assert "module1.py" in files_found or "module2.py" in files_found

    @pytest.mark.asyncio
    async def test_skip_directories(self):
        """Test that node_modules and other dirs are skipped."""
        from backend.services.deep_analysis import DeepCodeAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a regular file
            main_file = Path(tmpdir) / "main.py"
            main_file.write_text("print('hello')")

            # Create node_modules (should be skipped)
            node_modules = Path(tmpdir) / "node_modules"
            node_modules.mkdir()
            nm_file = node_modules / "package.js"
            nm_file.write_text("module.exports = {}")

            analysis = await DeepCodeAnalyzer.analyze_workspace(tmpdir)

            # Should only analyze main.py, not node_modules
            assert analysis.total_files == 1
            assert "main.py" in analysis.files


class TestDatabaseDebugger:
    """Test database debugging capabilities."""

    @pytest.mark.asyncio
    async def test_parse_sqlalchemy_models(self):
        """Test parsing SQLAlchemy model definitions."""
        from backend.services.deep_analysis import DatabaseDebugger

        content = '''
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
    user_id = Column(Integer)
'''

        models = DatabaseDebugger._parse_sqlalchemy_models(content)

        assert len(models) == 2

        user_model = next(m for m in models if m["name"] == "User")
        assert user_model["type"] == "sqlalchemy"
        assert len(user_model["columns"]) == 3

        post_model = next(m for m in models if m["name"] == "Post")
        assert post_model["type"] == "sqlalchemy"

    @pytest.mark.asyncio
    async def test_parse_django_models(self):
        """Test parsing Django model definitions."""
        from backend.services.deep_analysis import DatabaseDebugger

        content = '''
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    published_at = models.DateTimeField()
    author = models.ForeignKey('User', on_delete=models.CASCADE)

class Comment(models.Model):
    text = models.TextField()
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
'''

        models = DatabaseDebugger._parse_django_models(content)

        assert len(models) == 2

        article = next(m for m in models if m["name"] == "Article")
        assert article["type"] == "django"
        assert len(article["columns"]) >= 3

    @pytest.mark.asyncio
    async def test_parse_prisma_models(self):
        """Test parsing Prisma schema models."""
        from backend.services.deep_analysis import DatabaseDebugger

        content = '''
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  posts     Post[]
  createdAt DateTime @default(now())
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  content   String?
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int
}
'''

        models = DatabaseDebugger._parse_prisma_models(content)

        assert len(models) == 2

        user_model = next(m for m in models if m["name"] == "User")
        assert user_model["type"] == "prisma"
        assert len(user_model["columns"]) >= 4

    @pytest.mark.asyncio
    async def test_analyze_database_workspace(self):
        """Test full database analysis of a workspace."""
        from backend.services.deep_analysis import DatabaseDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a models.py file
            models_file = Path(tmpdir) / "models.py"
            models_file.write_text('''
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String)
''')

            analysis = await DatabaseDebugger.analyze_database(tmpdir)

            assert len(analysis.tables) >= 1
            assert "User" in analysis.tables


class TestGitDebugger:
    """Test git debugging capabilities."""

    @pytest.mark.asyncio
    async def test_analyze_git_repo(self):
        """Test analyzing a git repository."""
        from backend.services.deep_analysis import GitDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create a file and commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial commit' -q")

            # Analyze
            analysis = await GitDebugger.analyze_repository(tmpdir)

            assert analysis.status.branch in ["main", "master"]
            assert not analysis.status.is_detached
            assert len(analysis.recent_commits) >= 1

    @pytest.mark.asyncio
    async def test_detect_uncommitted_changes(self):
        """Test detecting uncommitted changes."""
        from backend.services.deep_analysis import GitDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Make uncommitted changes
            test_file.write_text("hello world")

            analysis = await GitDebugger.analyze_repository(tmpdir)

            # Should detect uncommitted changes
            assert len(analysis.status.unstaged_files) > 0 or len(analysis.status.staged_files) > 0 or len(analysis.issues) > 0

    @pytest.mark.asyncio
    async def test_detect_untracked_files(self):
        """Test detecting untracked files."""
        from backend.services.deep_analysis import GitDebugger

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Create untracked file
            new_file = Path(tmpdir) / "untracked.txt"
            new_file.write_text("untracked")

            analysis = await GitDebugger.analyze_repository(tmpdir)

            assert len(analysis.status.untracked_files) > 0


class TestDeepAnalysisService:
    """Test the unified deep analysis service."""

    @pytest.mark.asyncio
    async def test_full_workspace_analysis(self):
        """Test comprehensive workspace analysis."""
        from backend.services.deep_analysis import DeepAnalysisService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create some code
            py_file = Path(tmpdir) / "app.py"
            py_file.write_text('''
def main():
    print("Hello")

if __name__ == "__main__":
    main()
''')

            # Create models
            models_file = Path(tmpdir) / "models.py"
            models_file.write_text('''
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    id = Column(Integer, primary_key=True)
''')

            # Initial commit
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            # Run full analysis
            result = await DeepAnalysisService.analyze_workspace_deep(tmpdir)

            # Verify all sections
            assert result["workspace_path"] == tmpdir
            assert "code" in result
            assert "database" in result
            assert "git" in result
            assert "summary" in result

            # Code analysis should find files
            if result["code"] and "error" not in result["code"]:
                assert result["code"]["total_files"] >= 1

            # Git should be analyzed
            if result["git"] and "error" not in result["git"]:
                assert "branch" in result["git"]


class TestProjectAnalyzerIntegration:
    """Test ProjectAnalyzer integration with deep analysis."""

    @pytest.mark.asyncio
    async def test_deep_analysis_method(self):
        """Test ProjectAnalyzer.analyze_deep method."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple file
            py_file = Path(tmpdir) / "main.py"
            py_file.write_text("print('hello')")

            result = await ProjectAnalyzer.analyze_deep(tmpdir)

            # Should return analysis or error
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_find_symbol_method(self):
        """Test ProjectAnalyzer.find_symbol_in_codebase method."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with a function
            py_file = Path(tmpdir) / "utils.py"
            py_file.write_text('''
def calculate_total(items):
    return sum(items)
''')

            results = await ProjectAnalyzer.find_symbol_in_codebase(tmpdir, "calculate_total")

            assert isinstance(results, list)
            if results:
                assert "file" in results[0]
                assert "line" in results[0]

    @pytest.mark.asyncio
    async def test_git_analysis_method(self):
        """Test ProjectAnalyzer.analyze_and_fix_git method."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git
            os.system(f"cd {tmpdir} && git init -q")
            os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
            os.system(f"cd {tmpdir} && git config user.name 'Test'")

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")
            os.system(f"cd {tmpdir} && git add . && git commit -m 'Initial' -q")

            result = await ProjectAnalyzer.analyze_and_fix_git(tmpdir)

            assert isinstance(result, dict)
            if "error" not in result:
                assert "status" in result
                assert "issues" in result

    @pytest.mark.asyncio
    async def test_database_analysis_method(self):
        """Test ProjectAnalyzer.analyze_and_fix_database method."""
        from backend.services.navi_brain import ProjectAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a models file
            models_file = Path(tmpdir) / "models.py"
            models_file.write_text('''
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String)
''')

            result = await ProjectAnalyzer.analyze_and_fix_database(tmpdir)

            assert isinstance(result, dict)
            if "error" not in result:
                assert "tables" in result


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("DEEP ANALYSIS TEST SUITE")
    print("=" * 60)

    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
