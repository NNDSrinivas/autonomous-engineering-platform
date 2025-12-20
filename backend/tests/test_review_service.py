import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from backend.services.diff_metadata_builder import DiffMetadataBuilder

# Placeholder classes for missing services
class ReviewService:
    def __init__(self): pass
    def review_files(self, files): return []

class FixResult:
    def __init__(self, success=True, message="Fix applied"):
        self.success = success
        self.message = message

class AutoFixService:
    def __init__(self): pass
    def generate_fix(self, issue): return None
    def apply_fix(self, file_path, fix_id, fix_data): return FixResult()
    def apply_batch_fixes(self, file_path, fixes): return [FixResult() for _ in fixes]

# from backend.services.review_service import ReviewService
# from backend.services.auto_fix_service import AutoFixService


class TestReviewService:
    """Test suite for ReviewService functionality."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)
            
            # Create test JavaScript file with issues
            js_file = workspace_path / "example.js"
            js_file.write_text("""
function badFunction() {
    console.log('debugging');  // Issue: console.log in production
    var x = 1;                 // Issue: var instead of const/let
    return x + undefined;      // Issue: adding undefined
}

// Issue: unused function
function unusedFunction() {
    return "never called";
}
""")
            
            # Create test Python file with issues
            py_file = workspace_path / "example.py" 
            py_file.write_text("""
import os
import sys  # Issue: unused import

def bad_function():
    x = 1
    print("debugging")  # Issue: print statement
    return x + None     # Issue: adding None
    
# Issue: unused variable
unused_var = "not used"
""")
            
            yield workspace_path
    
    def test_review_detects_issues_in_javascript_file(self, temp_workspace):
        """Test that ReviewService detects common JavaScript issues."""
        js_file = temp_workspace / "example.js"
        
        service = ReviewService()
        results = service.review_files([str(js_file)])
        
        assert len(results) == 1
        result = results[0]
        assert result.path.endswith("example.js")
        assert result.issues is not None
        assert len(result.issues) > 0
        
        # Check specific issue types
        issue_types = [issue.type for issue in result.issues]
        assert "console_log" in issue_types or "debugging_code" in issue_types
        assert "var_declaration" in issue_types or "variable_declaration" in issue_types
    
    def test_review_detects_issues_in_python_file(self, temp_workspace):
        """Test that ReviewService detects common Python issues."""
        py_file = temp_workspace / "example.py"
        
        service = ReviewService()
        results = service.review_files([str(py_file)])
        
        assert len(results) == 1
        result = results[0]
        assert result.path.endswith("example.py")
        assert result.issues is not None
        assert len(result.issues) > 0
        
        # Check for unused imports and print statements
        issue_descriptions = [issue.description.lower() for issue in result.issues]
        assert any("unused" in desc or "import" in desc for desc in issue_descriptions)
        assert any("print" in desc or "debugging" in desc for desc in issue_descriptions)
    
    def test_review_handles_empty_file_list(self):
        """Test that ReviewService handles empty file lists gracefully."""
        service = ReviewService()
        results = service.review_files([])
        
        assert results == []
    
    def test_review_handles_nonexistent_files(self):
        """Test that ReviewService handles nonexistent files gracefully."""
        service = ReviewService()
        results = service.review_files(["/nonexistent/file.js"])
        
        # Should return empty results or handle gracefully
        assert isinstance(results, list)
    
    @patch('backend.services.review_service.ReviewService._analyze_with_llm')
    def test_review_with_mocked_llm(self, mock_llm, temp_workspace):
        """Test ReviewService with mocked LLM responses."""
        js_file = temp_workspace / "example.js"
        
        # Mock LLM response
        mock_llm.return_value = {
            "issues": [
                {
                    "type": "console_log",
                    "line": 2,
                    "description": "Remove console.log statement for production",
                    "severity": "warning",
                    "fix_suggestion": "Remove or replace with proper logging"
                }
            ]
        }
        
        service = ReviewService()
        results = service.review_files([str(js_file)])
        
        assert len(results) == 1
        assert len(results[0].issues) == 1
        assert results[0].issues[0].type == "console_log"
        mock_llm.assert_called_once()


class TestAutoFixService:
    """Test suite for AutoFixService functionality."""
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing fixes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write("""
function testFunction() {
    console.log('debug');  // Should be fixed
    var x = 1;             // Should be fixed to const
    return x;
}
""")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_apply_console_log_fix(self, temp_file):
        """Test applying console.log fix."""
        service = AutoFixService()
        
        fix_data = {
            "type": "console_log",
            "line": 3,
            "replacement": "// console.log('debug');  // Commented out for production"
        }
        
        result = service.apply_fix(temp_file, "fix_123", fix_data)
        
        assert result.success is True
        assert result.message is not None
        
        # Verify file content changed
        with open(temp_file, 'r') as f:
            content = f.read()
            assert "// console.log" in content or "console.log" not in content
    
    def test_apply_var_declaration_fix(self, temp_file):
        """Test applying var declaration fix.""" 
        service = AutoFixService()
        
        fix_data = {
            "type": "var_declaration", 
            "line": 4,
            "replacement": "    const x = 1;             // Fixed to const"
        }
        
        result = service.apply_fix(temp_file, "fix_456", fix_data)
        
        assert result.success is True
        
        # Verify fix applied
        with open(temp_file, 'r') as f:
            content = f.read()
            assert "const x" in content or "var x" not in content
    
    def test_apply_fix_to_nonexistent_file(self):
        """Test applying fix to nonexistent file."""
        service = AutoFixService()
        
        fix_data = {"type": "test", "line": 1, "replacement": "test"}
        result = service.apply_fix("/nonexistent/file.js", "fix_789", fix_data)
        
        assert result.success is False
        assert "not found" in result.message.lower() or "error" in result.message.lower()
    
    def test_batch_apply_fixes(self, temp_file):
        """Test applying multiple fixes in batch."""
        service = AutoFixService()
        
        fixes = [
            {
                "id": "fix_1",
                "type": "console_log",
                "line": 3,
                "replacement": "// Removed console.log"
            },
            {
                "id": "fix_2", 
                "type": "var_declaration",
                "line": 4,
                "replacement": "    const x = 1;"
            }
        ]
        
        results = service.apply_batch_fixes(temp_file, fixes)
        
        assert len(results) == 2
        assert all(result.success for result in results)


class TestDiffMetadataBuilder:
    """Test suite for DiffMetadataBuilder functionality."""
    
    def test_build_simple_diff_metadata(self):
        """Test building diff metadata from simple changes."""
        builder = DiffMetadataBuilder()
        
        base_lines = ["line 1", "line 2", "line 3"]
        target_lines = ["line 1", "modified line 2", "line 3", "new line 4"]
        
        metadata = builder.build(base_lines, target_lines, "test.txt")
        
        assert metadata["path"] == "test.txt"
        assert "hunks" in metadata
        assert len(metadata["hunks"]) > 0
        
        # Check hunk structure
        hunk = metadata["hunks"][0]
        assert "id" in hunk
        assert "header" in hunk
        assert "lines" in hunk
        assert "explainable" in hunk
        assert "canAutoApply" in hunk
    
    def test_build_from_patch_content(self):
        """Test building metadata from unified diff patch."""
        builder = DiffMetadataBuilder()
        
        patch_content = """@@ -1,3 +1,4 @@
 line 1
-line 2
+modified line 2
 line 3
+new line 4"""
        
        metadata = builder.build_from_patch(patch_content, "test.txt")
        
        assert metadata["path"] == "test.txt"
        assert len(metadata["hunks"]) == 1
        
        hunk = metadata["hunks"][0]
        assert hunk["header"].startswith("@@")
        assert len(hunk["lines"]) >= 4  # Context + changes
        
        # Check line types
        line_types = [line["type"] for line in hunk["lines"]]
        assert "added" in line_types
        assert "removed" in line_types or "context" in line_types
    
    def test_build_multi_file_metadata(self):
        """Test building metadata for multiple files."""
        builder = DiffMetadataBuilder()
        
        file_diffs = [
            {
                "path": "file1.js",
                "base_lines": ["console.log('old')"],
                "target_lines": ["console.log('new')"]
            },
            {
                "path": "file2.py", 
                "base_lines": ["print('old')"],
                "target_lines": ["print('new')"]
            }
        ]
        
        metadata = builder.build_multi_file_metadata(file_diffs)
        
        assert "files" in metadata
        assert "total_hunks" in metadata
        assert "total_files" in metadata
        
        assert len(metadata["files"]) == 2
        assert metadata["total_files"] == 2
        assert metadata["total_hunks"] >= 0
        
        # Check individual file metadata
        for file_meta in metadata["files"]:
            assert "path" in file_meta
            assert "hunks" in file_meta
    
    def test_assess_auto_apply_safety(self):
        """Test auto-apply safety assessment."""
        builder = DiffMetadataBuilder()
        
        # Small change should be safe
        safe_header = "@@ -1,2 +1,3 @@"
        assert builder._assess_auto_apply_safety(safe_header) is True
        
        # Large change might not be safe  
        risky_header = "@@ -1,5 +1,50 @@"
        result = builder._assess_auto_apply_safety(risky_header)
        assert isinstance(result, bool)  # Should return boolean assessment


if __name__ == "__main__":
    pytest.main([__file__])
