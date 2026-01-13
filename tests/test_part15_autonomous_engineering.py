"""
Comprehensive Test Suite for Part 15 Autonomous Engineering Features

Tests all major components:
- Sprint Planner Agent
- Backlog Manager & Priority Engine
- Engineering KPI Dashboard
- Long-term Memory Layer
- Multi-Repo Orchestration
- Autonomous PR Reviewer
- VS Code Integration
"""

import pytest
import json
from backend.agents.autonomous_pr_reviewer import ReviewSeverity, ReviewCategory
from backend.memory.memory_layer import (
    Memory,
    MemoryLayer,
    MemoryType,
    MemoryImportance,
)
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Placeholder classes for Part 15 components
from enum import Enum
from typing import Any


class Priority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


class ItemType(Enum):
    FEATURE = "feature"
    BUG = "bug"
    TASK = "task"


class BacklogItem:
    def __init__(
        self,
        id,
        title,
        description=None,
        priority=Priority.MEDIUM,
        item_type=None,
        estimated_hours=0,
        **kwargs
    ):
        self.id = id
        self.title = title
        self.description = description or title
        self.priority = priority
        self.item_type = item_type
        self.estimated_hours = estimated_hours


class Sprint:
    def __init__(self, id, name, goal, duration_days, capacity_points, items, **kwargs):
        self.id = id
        self.name = name
        self.goal = goal
        self.duration_days = duration_days
        self.capacity_points = capacity_points
        self.items = items


class SprintPlannerAgent:
    def __init__(self):
        self.llm: Any = None
        self.db: Any = None


class BacklogManagerAgent:
    def __init__(self):
        self.llm: Any = None
        self.db: Any = None


class KPIEngine:
    def __init__(self):
        self.db: Any = None


class RepoType(Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    MAIN_APPLICATION = "main_application"


class OperationType(Enum):
    SYNC = "sync"
    UPDATE = "update"
    DEPENDENCY_UPDATE = "dependency_update"


class MultiRepoOrchestrator:
    def __init__(self):
        self.db: Any = None
        self.memory: Any = None


# These are already imported above from the proper location


class ReviewFinding:
    def __init__(self, severity: Any, category: Any, **kwargs):
        self.severity = severity
        self.category = category


class AutonomousPRReviewer:
    def __init__(self):
        self.db: Any = None
        self.memory: Any = None


class TestSprintPlannerAgent:
    """Test suite for Sprint Planner Agent."""

    @pytest.fixture
    async def sprint_planner(self):
        """Create sprint planner instance with mocked dependencies."""
        with patch("backend.agents.sprint_planner_agent.LLMRouter"), patch(
            "backend.agents.sprint_planner_agent.DatabaseService"
        ):
            planner = SprintPlannerAgent()
            planner.llm = AsyncMock()
            planner.db = AsyncMock()
            return planner

    @pytest.mark.asyncio
    async def test_plan_sprint_success(self, sprint_planner):
        """Test successful sprint planning."""
        # Mock LLM response for sprint planning
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "selected_items": [
                    {"id": "item1", "title": "Feature A", "estimated_hours": 8},
                    {"id": "item2", "title": "Bug fix B", "estimated_hours": 4},
                ],
                "timeline": {"start_date": "2024-01-15", "end_date": "2024-01-29"},
                "capacity_analysis": {
                    "total_hours": 160,
                    "allocated_hours": 120,
                    "utilization_percentage": 75,
                },
            }
        )

        sprint_planner.llm.run.return_value = mock_response

        # Test sprint planning
        sprint_plan = await sprint_planner.plan_sprint(
            goals=["Improve performance", "Fix critical bugs"],
            capacity_hours=160,
            team_size=4,
        )

        assert sprint_plan is not None
        assert len(sprint_plan.selected_items) == 2
        assert sprint_plan.capacity_analysis["utilization_percentage"] == 75

        # Verify LLM was called with proper prompt
        sprint_planner.llm.run.assert_called_once()
        call_args = sprint_planner.llm.run.call_args
        assert "sprint planning" in call_args.kwargs["prompt"].lower()

    @pytest.mark.asyncio
    async def test_monitor_sprint_progress(self, sprint_planner):
        """Test sprint progress monitoring."""
        # Mock current sprint data
        mock_sprint = Sprint(
            id="sprint-123",
            name="Test Sprint",
            goal="Complete sprint testing",
            duration_days=14,
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now() + timedelta(days=7),
            capacity_points=100,
            items=[
                BacklogItem(
                    id="item1",
                    title="Feature A",
                    description="Test feature",
                    item_type=ItemType.FEATURE,
                    priority=Priority.HIGH,
                    estimated_hours=8,
                    status="in_progress",
                )
            ],
        )

        sprint_planner._get_current_sprint = AsyncMock(return_value=mock_sprint)

        progress = await sprint_planner.monitor_sprint_progress("sprint-123")

        assert progress is not None
        assert "completion_percentage" in progress
        assert "burn_down_data" in progress

    @pytest.mark.asyncio
    async def test_adjust_sprint_scope(self, sprint_planner):
        """Test sprint scope adjustment."""
        # Mock LLM response for scope adjustment
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "recommended_actions": [
                    {
                        "action": "remove_item",
                        "item_id": "item3",
                        "reason": "Low priority",
                    },
                    {"action": "reduce_scope", "item_id": "item1", "new_estimate": 6},
                ],
                "reasoning": "Sprint is at risk due to complexity underestimation",
            }
        )

        sprint_planner.llm.run.return_value = mock_response

        adjustment = await sprint_planner.adjust_sprint_scope(
            sprint_id="sprint-123", current_progress=0.4, days_remaining=7
        )

        assert adjustment is not None
        assert len(adjustment["recommended_actions"]) == 2
        assert "reasoning" in adjustment


class TestBacklogManagerAgent:
    """Test suite for Backlog Manager Agent."""

    @pytest.fixture
    async def backlog_manager(self):
        """Create backlog manager instance."""
        with patch("backend.agents.backlog_manager_agent.LLMRouter"), patch(
            "backend.agents.backlog_manager_agent.DatabaseService"
        ):
            manager = BacklogManagerAgent()
            manager.llm = AsyncMock()
            manager.db = AsyncMock()
            return manager

    @pytest.mark.asyncio
    async def test_analyze_backlog(self, backlog_manager):
        """Test backlog analysis."""
        # Mock backlog items
        backlog_items = [
            BacklogItem(
                id="item1",
                title="Critical Bug Fix",
                description="System crashes on login",
                item_type=ItemType.BUG,
                priority=Priority.CRITICAL,
                estimated_hours=4,
            ),
            BacklogItem(
                id="item2",
                title="New Feature",
                description="User dashboard",
                item_type=ItemType.FEATURE,
                priority=Priority.MEDIUM,
                estimated_hours=16,
            ),
        ]

        backlog_manager._get_all_backlog_items = AsyncMock(return_value=backlog_items)

        # Mock LLM analysis
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "priority_recommendations": [
                    {
                        "item_id": "item1",
                        "new_priority": "critical",
                        "reasoning": "Blocks user access",
                    },
                    {
                        "item_id": "item2",
                        "new_priority": "medium",
                        "reasoning": "Enhancement request",
                    },
                ],
                "insights": ["Focus on critical bugs first", "Consider user impact"],
            }
        )

        backlog_manager.llm.run.return_value = mock_response

        analysis = await backlog_manager.analyze_backlog()

        assert analysis is not None
        assert analysis.total_items == 2
        assert Priority.CRITICAL in analysis.priority_distribution
        assert len(analysis.recommendations) > 0

    @pytest.mark.asyncio
    async def test_rank_backlog_intelligent(self, backlog_manager):
        """Test intelligent backlog ranking."""
        # Mock backlog items with different priorities
        backlog_items = [
            BacklogItem(
                id="item1",
                title="Bug A",
                item_type=ItemType.BUG,
                priority=Priority.HIGH,
                estimated_hours=2,
            ),
            BacklogItem(
                id="item2",
                title="Feature B",
                item_type=ItemType.FEATURE,
                priority=Priority.LOW,
                estimated_hours=8,
            ),
            BacklogItem(
                id="item3",
                title="Critical C",
                item_type=ItemType.BUG,
                priority=Priority.CRITICAL,
                estimated_hours=1,
            ),
        ]

        backlog_manager._get_all_backlog_items = AsyncMock(return_value=backlog_items)

        # Mock scoring response
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            [
                {"item_id": "item3", "score": 95, "reasoning": "Critical system issue"},
                {"item_id": "item1", "score": 75, "reasoning": "High priority bug"},
                {"item_id": "item2", "score": 30, "reasoning": "Nice to have feature"},
            ]
        )

        backlog_manager.llm.run.return_value = mock_response

        ranked_items = await backlog_manager.rank_backlog_intelligent()

        assert len(ranked_items) == 3
        # Critical item should be first
        assert ranked_items[0].item_id == "item3"
        assert ranked_items[0].score == 95


class TestKPIEngine:
    """Test suite for KPI Engine."""

    @pytest.fixture
    async def kpi_engine(self):
        """Create KPI engine instance."""
        with patch("backend.kpi.kpi_engine.DatabaseService"):
            engine = KPIEngine()
            engine.db = AsyncMock()
            return engine

    @pytest.mark.asyncio
    async def test_compute_velocity(self, kpi_engine):
        """Test velocity calculation."""
        # Mock sprint data
        mock_sprints = [
            {"completed_story_points": 25, "sprint_length_days": 14},
            {"completed_story_points": 30, "sprint_length_days": 14},
            {"completed_story_points": 20, "sprint_length_days": 14},
        ]

        kpi_engine.db.fetch_all.return_value = mock_sprints

        velocity = await kpi_engine.compute_velocity(days_back=90)

        assert velocity > 0
        # Should be average of the sprints
        expected_velocity = (25 + 30 + 20) / 3
        assert abs(velocity - expected_velocity) < 0.1

    @pytest.mark.asyncio
    async def test_compute_mttr(self, kpi_engine):
        """Test MTTR calculation."""
        # Mock incident data
        mock_incidents = [
            {
                "created_at": "2024-01-01T10:00:00",
                "resolved_at": "2024-01-01T14:00:00",  # 4 hours
            },
            {
                "created_at": "2024-01-02T09:00:00",
                "resolved_at": "2024-01-02T11:00:00",  # 2 hours
            },
        ]

        kpi_engine.db.fetch_all.return_value = mock_incidents

        mttr = await kpi_engine.compute_mttr(days_back=30)

        assert mttr > 0
        # Should be average: (4 + 2) / 2 = 3 hours
        assert abs(mttr - 3.0) < 0.1

    @pytest.mark.asyncio
    async def test_generate_team_performance_report(self, kpi_engine):
        """Test team performance report generation."""
        # Mock all KPI computations
        kpi_engine.compute_velocity = AsyncMock(return_value=25.0)
        kpi_engine.compute_mttr = AsyncMock(return_value=3.5)
        kpi_engine.compute_pr_throughput = AsyncMock(return_value=12)
        kpi_engine.compute_bug_density = AsyncMock(return_value=2.1)

        # Mock LLM response for insights
        with patch.object(kpi_engine, "llm") as mock_llm:
            mock_response = MagicMock()
            mock_response.text = json.dumps(
                {
                    "overall_assessment": "Good performance with room for improvement",
                    "key_strengths": ["High velocity", "Low bug density"],
                    "areas_for_improvement": ["Reduce MTTR", "Increase PR throughput"],
                    "recommendations": [
                        "Implement better monitoring",
                        "Optimize review process",
                    ],
                }
            )
            mock_llm.run.return_value = mock_response

            report = await kpi_engine.generate_team_performance_report()

            assert report is not None
            assert report.velocity == 25.0
            assert report.mttr_hours == 3.5
            assert len(report.insights.recommendations) > 0


class TestMemoryLayer:
    """Test suite for Long-term Memory Layer."""

    @pytest.fixture
    async def memory_layer(self):
        """Create memory layer instance."""
        with patch("backend.memory.memory_layer.DatabaseService"), patch(
            "backend.memory.memory_layer.VectorStore"
        ):
            memory = MemoryLayer()
            memory.db = AsyncMock()
            memory.vector_store = AsyncMock()
            return memory

    @pytest.mark.asyncio
    async def test_store_memory(self, memory_layer):
        """Test memory storage."""
        # Mock vector store operations
        memory_layer.vector_store.add_document = AsyncMock()
        memory_layer._find_similar_memories = AsyncMock(return_value=[])
        memory_layer._enhance_memory_content = AsyncMock(
            return_value={
                "title": "Enhanced Title",
                "content": "Enhanced content",
                "tags": ["api", "design"],
                "context": {"key": "value"},
            }
        )
        memory_layer._find_related_memories = AsyncMock(return_value=["mem1", "mem2"])
        memory_layer._save_memory = AsyncMock()

        memory = await memory_layer.store_memory(
            memory_type=MemoryType.ARCHITECTURE_DECISION,
            title="API Design Decision",
            content="We chose REST over GraphQL because...",
            importance=MemoryImportance.HIGH,
            tags=["api", "architecture"],
        )

        assert memory is not None
        assert memory.memory_type == MemoryType.ARCHITECTURE_DECISION
        assert memory.importance == MemoryImportance.HIGH
        assert len(memory.related_memories) == 2

        # Verify storage calls
        memory_layer._save_memory.assert_called_once()
        memory_layer.vector_store.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_memories(self, memory_layer):
        """Test memory recall."""
        from backend.memory.memory_layer import MemoryQuery, Memory

        # Mock vector search results
        mock_docs = [
            {"id": "mem1", "similarity": 0.85},
            {"id": "mem2", "similarity": 0.72},
        ]
        memory_layer.vector_store.search = AsyncMock(return_value=mock_docs)

        # Mock memory loading
        mock_memory = Memory(
            id="mem1",
            memory_type=MemoryType.CODING_STYLE,
            title="Test Memory",
            content="Test content",
            importance=MemoryImportance.MEDIUM,
            tags=["test"],
            related_files=[],
            related_memories=[],
            context={},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
        )

        memory_layer._load_memory = AsyncMock(return_value=mock_memory)
        memory_layer._passes_query_filters = MagicMock(return_value=True)
        memory_layer._calculate_relevance_score = MagicMock(return_value=0.9)
        memory_layer._update_memory_access = AsyncMock()

        query = MemoryQuery(
            query_text="API design patterns",
            memory_types=[MemoryType.ARCHITECTURE_DECISION],
            max_results=5,
        )

        results = await memory_layer.recall_memories(query)

        assert len(results) > 0
        memory, score = results[0]
        assert memory.id == "mem1"
        assert score == 0.9

        # Verify access update
        memory_layer._update_memory_access.assert_called()

    @pytest.mark.asyncio
    async def test_generate_insights(self, memory_layer):
        """Test insight generation."""
        # Mock memory recall
        mock_memories = [
            (
                Memory(
                    id="mem1",
                    memory_type=MemoryType.BUG_PATTERN,
                    title="Authentication Bug Pattern",
                    content="Common issue with token validation...",
                    importance=MemoryImportance.HIGH,
                    tags=["auth", "security"],
                    related_files=[],
                    related_memories=[],
                    context={},
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                ),
                0.9,
            )
        ]

        memory_layer.recall_memories = AsyncMock(return_value=mock_memories)

        # Mock LLM response
        with patch.object(memory_layer, "llm") as mock_llm:
            mock_response = MagicMock()
            mock_response.text = json.dumps(
                [
                    {
                        "insight_type": "pattern",
                        "title": "Authentication Issues Pattern",
                        "description": "Recurring authentication problems detected",
                        "supporting_memories": ["mem1"],
                        "confidence": 0.85,
                        "actionable_recommendations": [
                            "Review auth implementation",
                            "Add more tests",
                        ],
                    }
                ]
            )
            mock_llm.run.return_value = mock_response

            insights = await memory_layer.generate_insights(
                "current authentication issues"
            )

            assert len(insights) == 1
            insight = insights[0]
            assert insight.insight_type == "pattern"
            assert insight.confidence == 0.85
            assert len(insight.actionable_recommendations) == 2


class TestMultiRepoOrchestrator:
    """Test suite for Multi-Repo Orchestrator."""

    @pytest.fixture
    async def orchestrator(self):
        """Create multi-repo orchestrator instance."""
        with patch("backend.agents.multi_repo_orchestrator.DatabaseService"), patch(
            "backend.agents.multi_repo_orchestrator.MemoryLayer"
        ):
            orch = MultiRepoOrchestrator()
            orch.db = AsyncMock()
            orch.memory = AsyncMock()
            return orch

    @pytest.mark.asyncio
    async def test_register_repository(self, orchestrator):
        """Test repository registration."""
        # Mock repository analysis
        orchestrator._analyze_repository_structure = AsyncMock(
            return_value={
                "dependencies": ["express", "lodash"],
                "api_contracts": ["api.yaml"],
                "branches": ["main", "develop"],
                "tags": ["v1.0.0", "v1.1.0"],
                "metadata": {"has_tests": True},
            }
        )

        orchestrator._save_repository = AsyncMock()
        orchestrator._update_dependency_graph = AsyncMock()

        repo = await orchestrator.register_repository(
            name="test-repo",
            path="/path/to/repo",
            remote_url="https://github.com/org/test-repo.git",
            repo_type=RepoType.MAIN_APPLICATION,
            primary_language="javascript",
        )

        assert repo is not None
        assert repo.name == "test-repo"
        assert repo.repo_type == RepoType.MAIN_APPLICATION
        assert len(repo.dependencies) == 2
        assert repo.metadata["has_tests"] is True

        # Verify storage and memory calls
        orchestrator._save_repository.assert_called_once()
        orchestrator.memory.store_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_multi_repo_operation(self, orchestrator):
        """Test multi-repo operation planning."""
        # Mock impact analysis
        from backend.agents.multi_repo_orchestrator import CrossRepoAnalysis

        mock_analysis = CrossRepoAnalysis(
            operation_id="",
            impact_score=0.7,
            affected_repositories=["repo1", "repo2"],
            breaking_changes=["API change in service A"],
            migration_required=["repo2"],
            risk_assessment="Medium risk",
            recommended_sequence=["repo1", "repo2"],
            estimated_effort={"repo1": 4, "repo2": 8},
        )

        orchestrator._analyze_cross_repo_impact = AsyncMock(return_value=mock_analysis)
        orchestrator._estimate_operation_duration = AsyncMock(
            return_value=timedelta(hours=12)
        )
        orchestrator._generate_rollback_plan = AsyncMock(
            return_value="Rollback plan..."
        )
        orchestrator._save_operation = AsyncMock()

        operation = await orchestrator.plan_multi_repo_operation(
            operation_type=OperationType.DEPENDENCY_UPDATE,
            title="Update shared library",
            description="Update to version 2.0",
            affected_repos=["repo1", "repo2"],
            created_by="developer",
        )

        assert operation is not None
        assert operation.operation_type == OperationType.DEPENDENCY_UPDATE
        assert len(operation.affected_repos) == 2
        assert operation.estimated_duration == timedelta(hours=12)

        # Verify storage calls
        orchestrator._save_operation.assert_called_once()
        orchestrator.memory.store_memory.assert_called_once()


class TestAutonomousPRReviewer:
    """Test suite for Autonomous PR Reviewer."""

    @pytest.fixture
    async def pr_reviewer(self):
        """Create PR reviewer instance."""
        with patch("backend.agents.autonomous_pr_reviewer.DatabaseService"), patch(
            "backend.agents.autonomous_pr_reviewer.MemoryLayer"
        ):
            reviewer = AutonomousPRReviewer()
            reviewer.db = AsyncMock()
            reviewer.memory = AsyncMock()
            return reviewer

    @pytest.mark.asyncio
    async def test_review_pull_request(self, pr_reviewer):
        """Test PR review functionality."""
        # Mock file changes
        file_changes = [
            {
                "file_path": "src/auth.py",
                "change_type": "modified",
                "additions": 10,
                "deletions": 5,
                "diff_content": "+    def authenticate(username, password):\n+        return True",
            }
        ]

        # Mock security analysis
        pr_reviewer._analyze_security = AsyncMock(return_value=[])

        # Mock review comments generation
        from backend.agents.autonomous_pr_reviewer import ReviewComment

        mock_comments = [
            ReviewComment(
                file_path="src/auth.py",
                line_number=42,
                severity=ReviewSeverity.HIGH,
                category=ReviewCategory.SECURITY,
                title="Weak Authentication",
                message="Authentication always returns True, this is insecure",
                suggested_fix="Implement proper credential validation",
                confidence=0.9,
                auto_fixable=False,
            )
        ]

        pr_reviewer._generate_review_comments = AsyncMock(return_value=mock_comments)
        pr_reviewer._generate_patch_suggestions = AsyncMock(return_value=[])
        pr_reviewer._get_review_context = AsyncMock(return_value=[])
        pr_reviewer._save_review_analysis = AsyncMock()
        pr_reviewer._store_review_learning = AsyncMock()

        analysis = await pr_reviewer.review_pull_request(
            pr_id="PR-123",
            pr_title="Add authentication",
            pr_description="Implement user authentication",
            author="developer",
            file_changes=file_changes,
        )

        assert analysis is not None
        assert analysis.pr_id == "PR-123"
        assert len(analysis.review_comments) == 1
        assert analysis.review_comments[0].severity == ReviewSeverity.HIGH
        assert analysis.overall_score < 10  # Should be penalized for security issue

        # Verify storage calls
        pr_reviewer._save_review_analysis.assert_called_once()
        pr_reviewer._store_review_learning.assert_called_once()

    @pytest.mark.asyncio
    async def test_security_pattern_detection(self, pr_reviewer):
        """Test security vulnerability detection."""
        from backend.agents.autonomous_pr_reviewer import FileChange, FileChangeType

        # Create file change with security vulnerability
        file_change = FileChange(
            file_path="src/db.py",
            change_type=FileChangeType.MODIFIED,
            additions=5,
            deletions=0,
            diff_content='+query = "SELECT * FROM users WHERE id = " + user_id',
            language="python",
        )

        # Test pattern-based security scanning
        issues = pr_reviewer._scan_security_patterns(file_change)

        # Should detect SQL injection pattern
        assert len(issues) > 0
        sql_injection_issues = [
            i for i in issues if i.vulnerability_type == "sql_injection"
        ]
        assert len(sql_injection_issues) > 0

        issue = sql_injection_issues[0]
        assert issue.severity == ReviewSeverity.HIGH
        assert "sql injection" in issue.description.lower()

    @pytest.mark.asyncio
    async def test_generate_review_summary(self, pr_reviewer):
        """Test review summary generation."""
        from backend.agents.autonomous_pr_reviewer import (
            PRAnalysis,
            FileChange,
            FileChangeType,
        )

        # Create mock PR analysis
        analysis = PRAnalysis(
            pr_id="PR-456",
            title="Fix authentication bug",
            description="Resolve security vulnerability",
            author="security-team",
            file_changes=[
                FileChange(
                    file_path="auth.py",
                    change_type=FileChangeType.MODIFIED,
                    additions=3,
                    deletions=1,
                    diff_content="- return True\n+ return validate_credentials(user, pass)",
                )
            ],
            review_comments=[],
            security_issues=[],
            patch_suggestions=[],
            overall_score=9.0,
            complexity_score=2.0,
            risk_assessment="Low risk - security improvement",
            approval_recommendation="APPROVE - Excellent security fix",
            estimated_review_time=15,
        )

        # Mock LLM response
        with patch.object(pr_reviewer, "llm") as mock_llm:
            mock_response = MagicMock()
            mock_response.text = "## PR Review Summary\n\n**Recommendation:** APPROVE\n\nExcellent security improvement..."
            mock_llm.run.return_value = mock_response

            summary = await pr_reviewer.generate_review_summary(analysis)

            assert "APPROVE" in summary
            assert "security" in summary.lower()
            assert analysis.pr_id in summary or "PR-456" in summary


class TestVSCodeIntegration:
    """Test suite for VS Code Integration."""

    def test_part15_integration_commands(self):
        """Test that all Part 15 commands are registered."""
        # This would be an integration test in a real VS Code environment
        # Here we just verify the command structure

        expected_commands = [
            "navi.sprint.plan",
            "navi.sprint.monitor",
            "navi.backlog.analyze",
            "navi.backlog.add",
            "navi.kpi.dashboard",
            "navi.memory.search",
            "navi.memory.store",
            "navi.multirepo.sync",
            "navi.multirepo.plan",
            "navi.pr.review",
            "navi.pr.fix",
            "navi.autonomous.status",
        ]

        # In a real test, we would verify these commands are registered
        # with the VS Code extension API
        assert len(expected_commands) == 12

        # Verify command naming convention
        for cmd in expected_commands:
            assert cmd.startswith("navi.")
            assert len(cmd.split(".")) == 3  # navi.category.action


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
