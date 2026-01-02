"""
Phase 5.1 Governance Integration Test

Tests the complete integration between Phase 5.1 Human-in-the-Loop Governance
and Phase 5.0 Closed-Loop autonomous system.

This test validates:
1. Governance controls work end-to-end
2. Approval workflows function correctly  
3. Risk scoring and audit logging operate properly
4. Rollback capabilities are available
5. Emergency bypass mechanisms work
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from typing import Dict, Any

from backend.agent.governance.integration import (
    GovernedClosedLoopOrchestrator, 
    GovernanceIntegrationMixin
)
from backend.agent.governance.execution_controller import GovernedExecutionController
from backend.agent.governance import DecisionType
from backend.agent.closedloop.auto_planner import PlannedAction, ActionType, ActionPriority
from backend.agent.closedloop.execution_controller import ExecutionResult, ExecutionStatus


class TestGovernanceIntegration:
    """Test governance integration with Phase 5.0 system"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture 
    def governed_orchestrator(self, mock_db_session):
        """Create governed orchestrator for testing"""
        return GovernedClosedLoopOrchestrator(
            db_session=mock_db_session,
            workspace_path="/test/workspace",
            org_key="test_org",
            user_id="test_user"
        )
    
    @pytest.fixture
    def governed_execution_controller(self, mock_db_session):
        """Create governed execution controller for testing"""
        return GovernedExecutionController(
            db_session=mock_db_session,
            workspace_path="/test/workspace", 
            org_key="test_org",
            user_id="test_user"
        )
    
    @pytest.fixture
    def sample_action(self):
        """Create sample PlannedAction for testing"""
        return PlannedAction(
            action_id="test_action_001",
            action_type=ActionType.CODE_EDIT,
            description="Update user authentication module",
            estimated_impact="medium",
            priority=ActionPriority.HIGH
        )
    
    @pytest.fixture
    def sample_context(self):
        """Create sample execution context"""
        return {
            "target_files": ["/app/auth/user_auth.py", "/app/auth/permissions.py"],
            "repo": "test-repo",
            "branch": "main", 
            "org_id": "test_org",
            "environment_indicators": ["production"],
            "user_id": "test_user"
        }
    
    @pytest.mark.asyncio
    async def test_auto_execution_low_risk(
        self, 
        governed_orchestrator, 
        sample_action,
        sample_context
    ):
        """Test automatic execution for low-risk actions"""
        
        # Mock approval engine to return AUTO decision
        with patch.object(governed_orchestrator.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (DecisionType.AUTO, 0.2, ["Low impact"], None)
            
            # Mock successful execution
            with patch.object(governed_orchestrator, '_execute_with_governance') as mock_execute:
                mock_result = ExecutionResult(
                    action=sample_action,
                    status=ExecutionStatus.COMPLETED,
                    message="Action completed successfully"
                )
                mock_execute.return_value = mock_result
                
                # Execute action
                result = await governed_orchestrator.execute_governed_action(
                    sample_action, sample_context
                )
                
                # Verify auto execution
                assert result.status == ExecutionStatus.COMPLETED
                assert result.message == "Action completed successfully"
                
                # Verify governance was consulted
                mock_evaluate.assert_called_once()
                mock_execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_approval_required_high_risk(
        self, 
        governed_orchestrator,
        sample_action,
        sample_context
    ):
        """Test approval workflow for high-risk actions"""
        
        # Make action high-risk (auth + production)
        sample_context["branch"] = "main"
        
        # Mock approval engine to return APPROVAL decision
        with patch.object(governed_orchestrator.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (
                DecisionType.APPROVAL, 
                0.8, 
                ["Affects authentication", "Production branch"], 
                "approval_123"
            )
            
            # Execute action
            result = await governed_orchestrator.execute_governed_action(
                sample_action, sample_context
            )
            
            # Verify approval required
            assert result.status == ExecutionStatus.PENDING_APPROVAL
            assert "requires approval" in result.message.lower()
            assert "approval_123" == result.metadata["approval_id"]
            assert result.metadata["risk_score"] == 0.8
            
            # Verify action stored for later execution
            assert "approval_123" in governed_orchestrator.pending_approvals
    
    @pytest.mark.asyncio
    async def test_blocked_execution_policy(
        self, 
        governed_orchestrator,
        sample_action, 
        sample_context
    ):
        """Test policy blocking dangerous actions"""
        
        # Mock approval engine to return BLOCKED decision
        with patch.object(governed_orchestrator.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (
                DecisionType.BLOCKED,
                0.95,
                ["Destructive operation", "No rollback possible"],
                None
            )
            
            # Execute action
            result = await governed_orchestrator.execute_governed_action(
                sample_action, sample_context
            )
            
            # Verify blocked
            assert result.status == ExecutionStatus.BLOCKED
            assert "blocked by governance policy" in result.message.lower()
            assert result.metadata["risk_score"] == 0.95
            assert "Destructive operation" in result.metadata["reasons"]
    
    @pytest.mark.asyncio
    async def test_approval_execution_flow(
        self, 
        governed_orchestrator,
        sample_action,
        sample_context
    ):
        """Test complete approval and execution flow"""
        
        # Step 1: Action requires approval
        with patch.object(governed_orchestrator.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (
                DecisionType.APPROVAL, 
                0.7, 
                ["High-risk operation"], 
                "approval_456"
            )
            
            result = await governed_orchestrator.execute_governed_action(
                sample_action, sample_context
            )
            
            assert result.status == ExecutionStatus.PENDING_APPROVAL
        
        # Step 2: Execute after approval
        with patch.object(governed_orchestrator.execution_controller, 'execute_action') as mock_execute:
            mock_execute.return_value = ExecutionResult(
                action=sample_action,
                status=ExecutionStatus.COMPLETED,
                message="Approved action executed"
            )
            
            result = await governed_orchestrator.execute_approved_action(
                "approval_456", "approver_user"
            )
            
            assert result.status == ExecutionStatus.COMPLETED
            assert "approval_456" not in governed_orchestrator.pending_approvals
    
    @pytest.mark.asyncio
    async def test_governed_execution_controller(
        self, 
        governed_execution_controller,
        sample_action,
        sample_context
    ):
        """Test the governed execution controller directly"""
        
        # Mock governance components
        with patch.object(governed_execution_controller.approval_engine, 'evaluate_action') as mock_evaluate:
            with patch.object(governed_execution_controller, '_execute_with_safety_checks') as mock_execute:
                
                # Setup mocks
                mock_evaluate.return_value = (DecisionType.AUTO, 0.3, ["Low risk"], None)
                mock_execute.return_value = ExecutionResult(
                    action=sample_action,
                    status=ExecutionStatus.COMPLETED,
                    message="Execution completed",
                    rollback_available=True
                )
                
                # Execute action
                result = await governed_execution_controller.execute_action(
                    sample_action, sample_context
                )
                
                # Verify execution
                assert result.status == ExecutionStatus.COMPLETED
                assert result.rollback_available
                
                # Verify audit logging
                assert governed_execution_controller.audit_logger.log_execution.called
    
    @pytest.mark.asyncio
    async def test_rollback_capability(
        self, 
        governed_execution_controller,
        sample_action
    ):
        """Test rollback functionality"""
        
        # Mock rollback controller
        with patch.object(governed_execution_controller.rollback_controller, 'rollback_action') as mock_rollback:
            mock_rollback.return_value = (
                True, 
                "Rollback completed successfully", 
                {"files_restored": 2}
            )
            
            # Execute rollback
            result = await governed_execution_controller.rollback_action(
                "rollback_123", "test_user", "Testing rollback"
            )
            
            # Verify rollback
            assert result.status == ExecutionStatus.COMPLETED
            assert "rollback completed" in result.message.lower()
            assert result.metadata["rollback"]["success"] is True
    
    def test_governance_integration_mixin(self, mock_db_session):
        """Test governance integration mixin"""
        
        class MockExecutor(GovernanceIntegrationMixin):
            def __init__(self, db_session):
                self.db = db_session
                super().__init__()
            
            async def _direct_execute(self, action_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
                return {"success": True, "action_type": action_type}
        
        executor = MockExecutor(mock_db_session)
        
        # Verify governance components initialized
        assert hasattr(executor, 'approval_engine')
        assert hasattr(executor, 'risk_scorer')
        assert hasattr(executor, 'audit_logger')
        assert executor.governance_enabled is True
    
    @pytest.mark.asyncio
    async def test_emergency_bypass(
        self, 
        governed_execution_controller,
        sample_action,
        sample_context
    ):
        """Test emergency governance bypass"""
        
        # Mock high-risk action that would normally require approval
        with patch.object(governed_execution_controller.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (
                DecisionType.APPROVAL, 
                0.9, 
                ["Emergency situation"], 
                "emergency_approval"
            )
            
            # Mock direct execution
            with patch.object(governed_execution_controller, '_execute_with_safety_checks') as mock_execute:
                mock_execute.return_value = ExecutionResult(
                    action=sample_action,
                    status=ExecutionStatus.COMPLETED,
                    message="Emergency action executed"
                )
                
                # Execute with governance bypass
                result = await governed_execution_controller.execute_action(
                    sample_action, sample_context, bypass_governance=True
                )
                
                # Verify bypass worked
                assert result.status == ExecutionStatus.COMPLETED
                assert "emergency action executed" in result.message.lower()
                
                # Verify governance was bypassed (not called)
                mock_evaluate.assert_not_called()
    
    def test_governance_status_reporting(self, governed_orchestrator):
        """Test governance status and metrics reporting"""
        
        # Get status
        status = governed_orchestrator.get_governance_status()
        
        # Verify status structure
        assert "governance_enabled" in status
        assert "pending_approvals" in status 
        assert "user_id" in status
        assert "org_id" in status
        assert "config" in status
        
        # Verify values
        assert status["governance_enabled"] is True
        assert status["user_id"] == "test_user"
        assert status["org_id"] == "test_org"
    
    def test_governance_controls(self, governed_orchestrator):
        """Test governance enable/disable controls"""
        
        # Initially enabled
        assert governed_orchestrator.governance_enabled is True
        
        # Disable governance
        governed_orchestrator.disable_governance()
        assert governed_orchestrator.governance_enabled is False
        
        # Re-enable governance
        governed_orchestrator.enable_governance() 
        assert governed_orchestrator.governance_enabled is True
    
    @pytest.mark.asyncio
    async def test_safety_checks(
        self, 
        governed_execution_controller,
        sample_action,
        sample_context
    ):
        """Test safety check integration"""
        
        # Enable safety mode
        governed_execution_controller.set_safety_mode(True)
        
        # Mock safety check failure
        with patch.object(governed_execution_controller, '_run_safety_checks') as mock_safety:
            mock_safety.return_value = ["Destructive operation requires confirmation"]
            
            # Mock governance to allow execution
            with patch.object(governed_execution_controller.approval_engine, 'evaluate_action') as mock_evaluate:
                mock_evaluate.return_value = (DecisionType.AUTO, 0.1, ["Low risk"], None)
                
                # Execute action
                result = await governed_execution_controller.execute_action(
                    sample_action, sample_context
                )
                
                # Verify safety checks blocked execution
                assert result.status == ExecutionStatus.FAILED
                assert "safety checks failed" in result.message.lower()
    
    def test_action_context_creation(
        self, 
        governed_execution_controller,
        sample_action,
        sample_context
    ):
        """Test action context creation from execution parameters"""
        
        # Create action context
        context = governed_execution_controller._create_action_context(
            sample_action, sample_context
        )
        
        # Verify context fields
        assert context.action_type == sample_action.action_type.value
        assert context.target_files == sample_context["target_files"]
        assert context.repo == sample_context["repo"] 
        assert context.branch == sample_context["branch"]
        assert context.user_id == governed_execution_controller.user_id
        assert context.org_id == governed_execution_controller.org_key
        
        # Verify risk detection
        assert context.touches_auth is True  # auth files in target_files
        assert context.touches_prod is True  # main branch
    
    def test_risk_detection_methods(self, governed_execution_controller, sample_action):
        """Test auth and production impact detection"""
        
        # Test auth detection
        auth_context = {
            "target_files": ["/app/auth/login.py", "/app/security/permissions.py"]
        }
        assert governed_execution_controller._detect_auth_impact(sample_action, auth_context) is True
        
        non_auth_context = {
            "target_files": ["/app/utils/helpers.py", "/app/models/user.py"] 
        }
        assert governed_execution_controller._detect_auth_impact(sample_action, non_auth_context) is False
        
        # Test production detection
        prod_context = {"branch": "main", "environment": "production"}
        assert governed_execution_controller._detect_prod_impact(prod_context) is True
        
        dev_context = {"branch": "feature/test", "environment": "development"}
        assert governed_execution_controller._detect_prod_impact(dev_context) is False
    
    def test_rollback_support_detection(self, governed_execution_controller):
        """Test rollback support detection for different action types"""
        
        # Create actions of different types
        rollback_supported_action = PlannedAction(
            action_id="test_001",
            action_type=ActionType.CODE_EDIT,
            description="Edit code file"
        )
        
        rollback_forbidden_action = PlannedAction(
            action_id="test_002", 
            action_type=ActionType.DATA_DELETION,
            description="Delete user data"
        )
        
        # Test rollback support
        assert governed_execution_controller._supports_rollback(rollback_supported_action) is True
        assert governed_execution_controller._supports_rollback(rollback_forbidden_action) is False


class TestGovernancePerformance:
    """Test governance system performance and reliability"""
    
    @pytest.mark.asyncio
    async def test_concurrent_governance_decisions(self, mock_db_session):
        """Test governance handles concurrent action evaluation"""
        
        orchestrator = GovernedClosedLoopOrchestrator(
            db_session=mock_db_session,
            user_id="test_user"
        )
        
        # Create multiple actions
        action_types = [
            ActionType.CODE_EDIT,
            ActionType.DOCUMENTATION_UPDATE,
            ActionType.SECURITY_PATCH,
        ]
        actions = [
            PlannedAction(
                action_id=f"action_{i}",
                action_type=action_types[i % len(action_types)],
                description=f"Description {i}",
            )
            for i in range(10)
        ]
        
        contexts = [
            {"target_files": [f"/app/file_{i}.py"], "repo": f"repo_{i}"}
            for i in range(10)
        ]
        
        # Mock approval engine for all calls
        with patch.object(orchestrator.approval_engine, 'evaluate_action') as mock_evaluate:
            mock_evaluate.return_value = (DecisionType.AUTO, 0.1, ["Low risk"], None)
            
            with patch.object(orchestrator, '_execute_with_governance') as mock_execute:
                mock_execute.return_value = ExecutionResult(
                    action=actions[0],
                    status=ExecutionStatus.COMPLETED,
                    message="Success"
                )
                
                # Execute actions concurrently
                tasks = [
                    orchestrator.execute_governed_action(action, context)
                    for action, context in zip(actions, contexts)
                ]
                
                results = await asyncio.gather(*tasks)
                
                # Verify all executions completed
                assert len(results) == 10
                assert all(result.status == ExecutionStatus.COMPLETED for result in results)
                
                # Verify governance was consulted for each
                assert mock_evaluate.call_count == 10
    
    def test_governance_metrics_collection(self, mock_db_session):
        """Test governance metrics and status collection"""
        
        controller = GovernedExecutionController(
            db_session=mock_db_session,
            user_id="test_user"
        )
        
        # Get metrics
        metrics = controller.get_execution_metrics()
        
        # Verify metrics structure
        expected_keys = [
            "governance_enabled", "safety_mode", "pending_executions",
            "user_id", "org_id", "workspace_path", "components"
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Verify component status
        assert metrics["components"]["approval_engine"] is True
        assert metrics["components"]["audit_logger"] is True  
        assert metrics["components"]["rollback_controller"] is True


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])
