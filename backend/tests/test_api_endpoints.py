import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import status

# Import the FastAPI app
from backend.api.main import app

# from backend.api.repo_routes import router as repo_router  # Module needs to be created


class TestApplyFixAPI:
    """Test suite for auto-fix API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    def test_apply_fix_success(self, client):
        """Test successful fix application."""
        payload = {
            "filePath": "src/app/page.js",
            "fixId": "fix_console_log_123",
            "fixData": {
                "type": "console_log",
                "line": 5,
                "replacement": "// console.log removed for production",
            },
        }

        with patch(
            "backend.services.auto_fix_service.AutoFixService.apply_fix"
        ) as mock_apply:
            mock_apply.return_value = Mock(
                success=True,
                message="Fix applied successfully",
                file_path="src/app/page.js",
            )

            response = client.post("/api/repo/fix/fix_console_log_123", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "applied"
            assert data["success"] is True
            assert "src/app/page.js" in data["message"]

    def test_apply_fix_failure(self, client):
        """Test fix application failure."""
        payload = {"filePath": "nonexistent/file.js", "fixId": "fix_invalid_456"}

        with patch(
            "backend.services.auto_fix_service.AutoFixService.apply_fix"
        ) as mock_apply:
            mock_apply.return_value = Mock(
                success=False, message="File not found: nonexistent/file.js"
            )

            response = client.post("/api/repo/fix/fix_invalid_456", json=payload)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["message"].lower()

    def test_apply_batch_fixes(self, client):
        """Test batch fix application."""
        payload = {
            "fixes": [
                {
                    "filePath": "src/utils.js",
                    "fixId": "fix_1",
                    "fixData": {"type": "console_log", "line": 3},
                },
                {
                    "filePath": "src/helpers.js",
                    "fixId": "fix_2",
                    "fixData": {"type": "var_declaration", "line": 8},
                },
            ]
        }

        with patch(
            "backend.services.auto_fix_service.AutoFixService.apply_batch_fixes"
        ) as mock_batch:
            mock_batch.return_value = [
                Mock(success=True, message="Fix 1 applied", fix_id="fix_1"),
                Mock(success=True, message="Fix 2 applied", fix_id="fix_2"),
            ]

            response = client.post("/api/repo/fixes/batch", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_fixes"] == 2
            assert data["successful_fixes"] == 2
            assert len(data["results"]) == 2

    def test_get_available_fixes(self, client):
        """Test retrieving available fixes for a file."""
        with patch(
            "backend.services.review_service.ReviewService.review_files"
        ) as mock_review:
            mock_review.return_value = [
                Mock(
                    path="src/test.js",
                    issues=[
                        Mock(
                            id="issue_1",
                            type="console_log",
                            line=5,
                            description="Remove console.log",
                            fix_available=True,
                        ),
                        Mock(
                            id="issue_2",
                            type="unused_var",
                            line=12,
                            description="Remove unused variable",
                            fix_available=True,
                        ),
                    ],
                )
            ]

            response = client.get("/api/repo/fixes?file=src/test.js")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["available_fixes"]) == 2
            assert all(fix["fix_available"] for fix in data["available_fixes"])


class TestReviewAPI:
    """Test suite for review API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_review_working_tree(self, client):
        """Test review working tree endpoint."""
        payload = {
            "workspace_root": "/test/workspace",
            "files": ["src/app.js", "src/utils.js"],
        }

        with patch(
            "backend.services.review_service.ReviewService.review_working_tree"
        ) as mock_review:
            mock_review.return_value = {
                "total_files": 2,
                "files_with_issues": 1,
                "total_issues": 3,
                "results": [
                    {
                        "path": "src/app.js",
                        "issues": [
                            {"type": "console_log", "line": 5, "severity": "warning"},
                            {"type": "unused_var", "line": 10, "severity": "info"},
                        ],
                    }
                ],
            }

            response = client.post("/api/review/working-tree", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_files"] == 2
            assert data["files_with_issues"] == 1
            assert len(data["results"]) == 1

    def test_review_single_file(self, client):
        """Test single file review endpoint."""
        with patch(
            "backend.services.review_service.ReviewService.review_files"
        ) as mock_review:
            mock_review.return_value = [
                Mock(
                    path="src/single.js",
                    issues=[
                        Mock(
                            type="syntax_error",
                            line=15,
                            description="Missing semicolon",
                            severity="error",
                        )
                    ],
                )
            ]

            response = client.get("/api/review/file?path=src/single.js")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["file_path"] == "src/single.js"
            assert len(data["issues"]) == 1
            assert data["issues"][0]["severity"] == "error"


class TestSmartModeAPI:
    """Test suite for Smart Mode API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_smart_review_assessment(self, client):
        """Test Smart Mode risk assessment."""
        payload = {
            "files": ["src/critical.js", "src/utils.js"],
            "instruction": "Add error handling to all functions",
            "llm_confidence": 0.8,
        }

        with patch(
            "backend.services.planner.smart_mode.SmartModePlanner.assess_risk"
        ) as mock_assess:
            mock_assess.return_value = Mock(
                mode="smart",
                risk_score=0.45,
                risk_level="medium",
                reasons=["Modifying multiple files", "Adding error handling"],
                confidence=0.8,
                explanation="Medium risk due to multiple file changes",
            )

            response = client.post("/api/smart/assess", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["mode"] == "smart"
            assert data["risk_score"] == 0.45
            assert data["risk_level"] == "medium"
            assert len(data["reasons"]) == 2

    @patch("backend.api.smart_review.SmartModePlanner")
    @patch("backend.api.smart_review.AutonomousRefactorEngine")
    def test_smart_review_auto_mode(self, mock_engine, mock_planner, client):
        """Test Smart Mode auto-apply flow."""
        # Mock risk assessment for auto mode
        mock_planner.return_value.assess_risk.return_value = Mock(
            mode="auto", risk_score=0.15, risk_level="low"
        )

        # Mock successful auto-application
        mock_engine.return_value.apply_changes.return_value = {
            "success": True,
            "files_modified": ["src/safe.js"],
            "patch_summary": "Applied safe formatting changes",
        }

        payload = {
            "files": ["src/safe.js"],
            "instruction": "Fix formatting",
            "llm_confidence": 0.9,
        }

        response = client.post("/api/smart/review", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "auto"
        assert len(data["files_modified"]) == 1


class TestDiffAPI:
    """Test suite for diff-related API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_apply_hunk(self, client):
        """Test applying individual hunk."""
        payload = {"hunk_id": "hunk_abc123", "file_path": "src/component.js"}

        with patch(
            "backend.services.diff_service.DiffService.apply_hunk"
        ) as mock_apply:
            mock_apply.return_value = {
                "success": True,
                "message": "Hunk applied successfully",
                "lines_changed": 3,
            }

            response = client.post("/api/diff/apply-hunk", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "successfully" in data["message"]

    def test_explain_hunk(self, client):
        """Test AI explanation for hunk."""
        payload = {"hunk_id": "hunk_def456", "file_path": "src/service.js"}

        with patch(
            "backend.services.explanation_service.ExplanationService.explain_hunk"
        ) as mock_explain:
            mock_explain.return_value = {
                "explanation": "This change adds null checking to prevent runtime errors when the input parameter might be undefined.",
                "complexity": "low",
                "impact": "Improves error handling and code robustness",
            }

            response = client.post("/api/diff/explain-hunk", json=payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "null checking" in data["explanation"]
            assert data["complexity"] == "low"

    def test_generate_diff_metadata(self, client):
        """Test generating diff metadata for UI."""
        payload = {
            "base_content": "function test() {\n  console.log('old');\n}",
            "target_content": "function test() {\n  console.log('new');\n}",
            "file_path": "src/test.js",
        }

        response = client.post("/api/diff/metadata", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["path"] == "src/test.js"
        assert "hunks" in data
        assert len(data["hunks"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__])
