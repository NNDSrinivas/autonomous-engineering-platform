"""
Test suite for NAVI Intent Classifier v2
==========================================

Focused test scenarios that validate the heuristic classification
logic and ensure proper intent mapping.
"""

import pytest

from backend.agent.intent_classifier import IntentClassifier
from backend.agent.intent_schema import (
    NaviIntent, 
    IntentFamily, 
    IntentKind, 
    IntentPriority, 
    AutonomyMode
)


class TestIntentClassifier:
    """Test the IntentClassifier heuristic rules."""
    
    def setup_method(self):
        """Initialize classifier for each test."""
        self.classifier = IntentClassifier()
    
    # ------------------------------------------------------------------ #
    # Engineering Intent Tests
    # ------------------------------------------------------------------ #
    
    def test_code_review_classification(self):
        """Test code review intent detection."""
        messages = [
            "Review this PR for performance issues",
            "Can you look at my code changes?",
            "Please review the implementation in user_service.py",
            "Code review needed for the authentication logic",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.CODE_REVIEW
            assert intent.priority in [IntentPriority.NORMAL, IntentPriority.HIGH]
    
    def test_bug_fix_classification(self):
        """Test bug fix intent detection."""
        messages = [
            "Fix the failing test in test_auth.py",
            "There's a bug in the login endpoint",
            "The API returns 500 error, need to debug",
            "Fix this broken functionality",
            "Debug the memory leak in the worker process",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.BUG_FIX
            assert intent.priority == IntentPriority.HIGH
    
    def test_feature_development_classification(self):
        """Test feature development intent detection."""
        messages = [
            "Add user authentication to the API",
            "Implement rate limiting middleware",
            "Create a new dashboard component",
            "Build the notification system",
            "Add OAuth integration with GitHub",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.FEATURE_DEVELOPMENT
            assert intent.priority == IntentPriority.NORMAL
    
    def test_refactoring_classification(self):
        """Test refactoring intent detection."""
        messages = [
            "Refactor the user service to use dependency injection",
            "Clean up the legacy authentication code",
            "Restructure the API routes for better organization",
            "Extract common utility functions into a shared module",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.REFACTORING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_testing_classification(self):
        """Test testing intent detection."""
        messages = [
            "Write unit tests for the user authentication",
            "Add integration tests for the API endpoints",
            "Run the test suite and check coverage",
            "Create end-to-end tests for the checkout flow",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.TESTING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_deployment_classification(self):
        """Test deployment intent detection."""
        messages = [
            "Deploy the application to production",
            "Set up CI/CD pipeline for the project",
            "Configure AWS infrastructure for the app",
            "Deploy to staging environment for testing",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == IntentKind.DEPLOYMENT
            assert intent.priority == IntentPriority.HIGH
    
    # ------------------------------------------------------------------ #
    # Project Management Intent Tests
    # ------------------------------------------------------------------ #
    
    def test_planning_classification(self):
        """Test planning intent detection."""
        messages = [
            "Plan the sprint for next two weeks",
            "Create a project roadmap for Q1",
            "Estimate effort for the authentication feature",
            "Break down the e-commerce platform requirements",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.PROJECT_MANAGEMENT
            assert intent.kind == IntentKind.PLANNING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_issue_tracking_classification(self):
        """Test issue tracking intent detection."""
        messages = [
            "Create a ticket for the login bug",
            "Track the API performance issue",
            "Log this as a high-priority defect",
            "Update the status of issue #1234",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.PROJECT_MANAGEMENT
            assert intent.kind == IntentKind.ISSUE_TRACKING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_documentation_classification(self):
        """Test documentation intent detection."""
        messages = [
            "Update the API documentation",
            "Write README for the authentication module",
            "Document the deployment process",
            "Create user guide for the new feature",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.PROJECT_MANAGEMENT
            assert intent.kind == IntentKind.DOCUMENTATION
            assert intent.priority == IntentPriority.LOW
    
    # ------------------------------------------------------------------ #
    # Autonomous Orchestration Intent Tests
    # ------------------------------------------------------------------ #
    
    def test_batch_processing_classification(self):
        """Test batch processing intent detection."""
        messages = [
            "Process all pending user registrations",
            "Run batch analysis on the transaction data",
            "Execute data migration for all customers",
            "Batch update all product prices",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.AUTONOMOUS_ORCHESTRATION
            assert intent.kind == IntentKind.BATCH_PROCESSING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_orchestration_classification(self):
        """Test orchestration intent detection."""
        messages = [
            "Orchestrate the deployment pipeline",
            "Coordinate the microservices startup sequence",
            "Manage the workflow for data processing",
            "Automate the end-to-end user onboarding",
        ]
        
        for message in messages:
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.AUTONOMOUS_ORCHESTRATION
            assert intent.kind == IntentKind.ORCHESTRATION
            assert intent.priority == IntentPriority.HIGH
    
    # ------------------------------------------------------------------ #
    # Edge Cases and Complex Scenarios
    # ------------------------------------------------------------------ #
    
    def test_ambiguous_message_defaults(self):
        """Test that ambiguous messages get reasonable defaults."""
        ambiguous_messages = [
            "Help me",
            "What should I do?",
            "Something is broken",
            "Need assistance",
        ]
        
        for message in ambiguous_messages:
            intent = self.classifier.classify(message)
            # Should default to engineering family for technical contexts
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.priority == IntentPriority.NORMAL
    
    def test_mixed_intent_prioritization(self):
        """Test messages with multiple possible intents."""
        # This message could be bug fix OR feature development
        message = "Fix the authentication and add OAuth support"
        intent = self.classifier.classify(message)
        
        # Should prioritize bug fix (higher urgency)
        assert intent.family == IntentFamily.ENGINEERING
        assert intent.kind == IntentKind.BUG_FIX
        assert intent.priority == IntentPriority.HIGH
    
    def test_metadata_influence(self):
        """Test that metadata influences classification."""
        message = "Handle this request"
        
        # With file context suggesting code
        metadata = {"files": ["backend/auth/user_service.py", "tests/test_auth.py"]}
        intent = self.classifier.classify(message, metadata=metadata)
        assert intent.family == IntentFamily.ENGINEERING
        
        # With documentation context
        metadata = {"files": ["README.md", "docs/api.md"]}
        intent = self.classifier.classify(message, metadata=metadata)
        assert intent.family == IntentFamily.PROJECT_MANAGEMENT
        assert intent.kind == IntentKind.DOCUMENTATION
    
    def test_autonomy_mode_assignment(self):
        """Test that autonomy mode is assigned correctly."""
        # Simple single-step requests
        simple_intent = self.classifier.classify("Fix the typo in README.md")
        assert simple_intent.autonomy_mode == AutonomyMode.SINGLE_STEP
        
        # Complex multi-step requests
        complex_intent = self.classifier.classify(
            "Implement user authentication with OAuth, add tests, update docs, and deploy to staging"
        )
        assert complex_intent.autonomy_mode == AutonomyMode.MULTI_STEP
    
    def test_priority_escalation_keywords(self):
        """Test that urgency keywords elevate priority."""
        urgent_messages = [
            "URGENT: Fix the production database connection",
            "Critical bug in payment processing",
            "Emergency deployment needed for security patch",
        ]
        
        for message in urgent_messages:
            intent = self.classifier.classify(message)
            assert intent.priority == IntentPriority.CRITICAL
    
    # ------------------------------------------------------------------ #
    # Backwards Compatibility Tests
    # ------------------------------------------------------------------ #
    
    def test_classify_intent_function_compatibility(self):
        """Test the backwards-compatible classify_intent function."""
        from backend.agent.intent_classifier import classify_intent
        
        message = "Fix the failing tests"
        result = classify_intent(message)
        
        # Should return the legacy format while still working
        assert isinstance(result, (str, dict, NaviIntent))
        
        # If it returns a NaviIntent, verify it's valid
        if isinstance(result, NaviIntent):
            assert result.family in IntentFamily
            assert result.kind in IntentKind
    
    # ------------------------------------------------------------------ #
    # Payload Structure Tests
    # ------------------------------------------------------------------ #
    
    def test_code_edit_payload_structure(self):
        """Test that code editing intents have proper payload structure."""
        message = "Fix the bug in user_service.py line 45"
        metadata = {"files": ["backend/auth/user_service.py"]}
        
        intent = self.classifier.classify(message, metadata=metadata)
        
        # Should have code edit payload
        assert hasattr(intent, 'payload')
        if hasattr(intent.payload, 'target_files'):
            assert len(intent.payload.target_files) > 0
    
    def test_project_management_payload_structure(self):
        """Test that PM intents have proper payload structure."""
        message = "Create a project plan for the new feature with milestones"
        
        intent = self.classifier.classify(message)
        
        if intent.family == IntentFamily.PROJECT_MANAGEMENT:
            assert hasattr(intent, 'payload')
            # PM payloads should have appropriate structure
            assert intent.payload is not None


class TestIntentClassifierIntegration:
    """Integration tests for classifier with real-world scenarios."""
    
    def setup_method(self):
        """Initialize classifier for each test."""
        self.classifier = IntentClassifier()
    
    def test_realistic_engineering_workflow(self):
        """Test a realistic sequence of engineering tasks."""
        workflow_messages = [
            "Review the authentication PR #123",
            "Fix the failing integration tests", 
            "Add rate limiting to the API endpoints",
            "Deploy the changes to staging environment",
        ]
        
        expected_kinds = [
            IntentKind.CODE_REVIEW,
            IntentKind.BUG_FIX,
            IntentKind.FEATURE_DEVELOPMENT,
            IntentKind.DEPLOYMENT,
        ]
        
        for message, expected_kind in zip(workflow_messages, expected_kinds):
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.ENGINEERING
            assert intent.kind == expected_kind
    
    def test_project_management_workflow(self):
        """Test a realistic PM workflow."""
        pm_messages = [
            "Plan the Q2 roadmap for the platform",
            "Create tickets for the authentication epic", 
            "Update the API documentation with new endpoints",
            "Track progress on the performance optimization initiative",
        ]
        
        expected_kinds = [
            IntentKind.PLANNING,
            IntentKind.ISSUE_TRACKING,
            IntentKind.DOCUMENTATION,
            IntentKind.ISSUE_TRACKING,
        ]
        
        for message, expected_kind in zip(pm_messages, expected_kinds):
            intent = self.classifier.classify(message)
            assert intent.family == IntentFamily.PROJECT_MANAGEMENT
            assert intent.kind == expected_kind


if __name__ == "__main__":
    pytest.main([__file__, "-v"])