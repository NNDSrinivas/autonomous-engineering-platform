"""
Enterprise-grade CI Auto-Repair Type System

Comprehensive type definitions for autonomous CI failure detection,
analysis, and repair workflows with safety guarantees.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import Field

class CIProvider(Enum):
    """Supported CI/CD providers for autonomous repair"""
    GITHUB_ACTIONS = "github_actions"
    JENKINS = "jenkins"
    CIRCLECI = "circleci"
    GITLAB_CI = "gitlab_ci"
    AZURE_DEVOPS = "azure_devops"

class FailureType(Enum):
    """Intelligent failure classification for targeted repairs"""
    TEST_FAILURE = "test_failure"          # Unit/integration test failures
    BUILD_ERROR = "build_error"            # Compilation/build process errors
    TYPE_ERROR = "type_error"              # TypeScript/Python type errors  
    LINT_ERROR = "lint_error"              # Code style/linting failures
    ENV_MISSING = "env_missing"            # Missing environment variables/secrets
    DEPENDENCY_ERROR = "dependency_error"   # Package/module resolution issues
    SECURITY_SCAN = "security_scan"        # Security vulnerability findings
    PERFORMANCE_REGRESSION = "perf_regression"  # Performance test failures
    DEPLOYMENT_ERROR = "deployment_error"   # Deployment/infrastructure errors
    UNKNOWN = "unknown"                     # Unclassified failures

class RepairAction(Enum):
    """Actions NAVI can take for CI failures"""
    AUTO_FIX = "auto_fix"                  # Apply automated fix
    SUGGEST_FIX = "suggest_fix"            # Propose fix to human
    ESCALATE = "escalate"                  # Requires human intervention
    ROLLBACK = "rollback"                  # Rollback to previous state
    RETRY = "retry"                        # Simple retry without changes
    INVESTIGATE = "investigate"            # Needs more analysis

class RepairConfidence(Enum):
    """Confidence levels for repair decisions"""
    HIGH = "high"          # >90% confidence, auto-apply
    MEDIUM = "medium"      # 60-90% confidence, suggest
    LOW = "low"           # <60% confidence, escalate

@dataclass
class CIEvent:
    """CI pipeline event triggering repair workflow"""
    provider: CIProvider
    repo_owner: str
    repo_name: str
    run_id: str
    status: str  # 'failed', 'success', 'cancelled'
    branch: str
    commit_sha: str
    workflow_name: str
    job_name: Optional[str] = None
    triggered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    webhook_payload: Optional[Dict[str, Any]] = None

@dataclass 
class CILogs:
    """Structured CI logs with metadata"""
    raw_logs: str
    structured_logs: List[Dict[str, Any]]
    error_lines: List[str] 
    warning_lines: List[str]
    log_size_bytes: int
    fetched_at: datetime
    source_url: str

@dataclass
class FailureContext:
    """Rich context about CI failure for intelligent repair"""
    failure_type: FailureType
    confidence: float  # 0.0 to 1.0
    affected_files: List[str]
    error_messages: List[str]
    stack_traces: List[str]
    relevant_logs: List[str]
    failure_location: Optional[Dict[str, Any]] = None  # file:line:column
    related_errors: List[str] = Field(default_factory=list)
    dependencies_involved: List[str] = Field(default_factory=list)
    environment_context: Dict[str, Any] = Field(default_factory=dict)

@dataclass
class RepairPlan:
    """Autonomous repair execution plan"""
    action: RepairAction
    confidence: RepairConfidence
    target_files: List[str]
    repair_strategy: str
    expected_changes: List[str]
    rollback_plan: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None
    requires_approval: bool = False
    safety_checks: List[str] = Field(default_factory=list)

@dataclass
class RepairResult:
    """Result of autonomous CI repair attempt"""
    success: bool
    action_taken: RepairAction
    files_modified: List[str]
    commit_sha: Optional[str] = None
    ci_rerun_id: Optional[str] = None
    repair_duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    confidence_achieved: Optional[float] = None
    rollback_performed: bool = False
    
@dataclass
class CIRepairSession:
    """Complete autonomous repair session tracking"""
    session_id: str
    original_event: CIEvent
    logs: CILogs
    failure_context: FailureContext
    repair_plan: RepairPlan
    result: Optional[RepairResult] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    human_escalated: bool = False
    safety_snapshot_id: Optional[str] = None

# GitHub Actions specific types for production integration
@dataclass
class GitHubActionsConfig:
    """GitHub Actions API configuration"""
    token: str
    base_url: str = "https://api.github.com"
    timeout_seconds: int = 300
    max_log_size_mb: int = 50

# Safety and audit types for enterprise deployment
@dataclass 
class RepairAuditLog:
    """Enterprise audit log for CI repairs"""
    session_id: str
    timestamp: datetime
    action: str
    user_context: Optional[str]
    files_affected: List[str]
    confidence_score: float
    approval_required: bool
    approved_by: Optional[str] = None
    rollback_available: bool = True

# Integration types for existing Phase 4.4 infrastructure
@dataclass
class CIIntegrationContext:
    """Integration context with existing NAVI systems"""
    commit_engine_available: bool
    pr_engine_available: bool  
    ci_monitor_active: bool
    safety_system_enabled: bool
    rollback_engine_ready: bool
    github_credentials_configured: bool