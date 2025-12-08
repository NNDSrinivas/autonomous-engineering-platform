"""
Simple test suite for NAVI Intent Classifier v2
===============================================

Basic validation that the classifier works correctly.
"""

import pytest
from backend.agent.intent_classifier import IntentClassifier
from backend.agent.intent_schema import NaviIntent, IntentFamily, IntentKind


class TestIntentClassifier:
    """Basic tests for the IntentClassifier."""

    def setup_method(self):
        """Initialize classifier for each test."""
        self.classifier = IntentClassifier()

    def test_basic_classification(self):
        """Test that classifier returns valid NaviIntent objects."""
        message = "Fix the failing tests"
        intent = self.classifier.classify(message)

        # Should return a NaviIntent
        assert isinstance(intent, NaviIntent)

        # Should have valid family and kind
        assert isinstance(intent.family, IntentFamily)
        assert isinstance(intent.kind, IntentKind)

        # Should have basic attributes
        assert intent.raw_text == message
        assert intent.confidence > 0.0

    def test_bug_fix_classification(self):
        """Test bug fix intent detection."""
        messages = [
            "Fix the failing test",
            "There's a bug in the code",
            "Debug this issue",
        ]

        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.FIX_BUG

    def test_feature_development_classification(self):
        """Test feature development intent detection."""
        messages = [
            "Add user authentication",
            "Implement new API endpoint",
            "Build the dashboard",
        ]

        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.IMPLEMENT_FEATURE

    def test_test_running_classification(self):
        """Test running tests intent detection."""
        messages = [
            "Run the tests",
            "Execute pytest",
            "Run all unit tests",
        ]

        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.RUN_TESTS

    def test_project_management_classification(self):
        """Test project management intent detection."""
        messages = [
            "Create a ticket for this bug",
            "Update the Jira issue",
            "Plan the next sprint",
        ]

        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.PROJECT_MANAGEMENT

    def test_metadata_influence(self):
        """Test that metadata influences classification."""
        message = "Handle this request"

        # With code file context
        metadata = {"files": ["backend/auth/user_service.py"]}
        intent = self.classifier.classify(message, metadata=metadata)
        assert intent.family == IntentFamily.ENGINEERING

    def test_backwards_compatibility(self):
        """Test backwards compatibility function."""
        from backend.agent.intent_classifier import classify_intent

        message = "Fix the tests"
        result = classify_intent(message)

        # Should work without errors
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
