"""
Phase 5.1 — Human-in-the-Loop Governance Layer

This module provides real-time governance controls for NAVI's autonomous operations,
ensuring every action is either:
1. Pre-approved for autonomous execution
2. Queued for human approval
3. Blocked by policy

Key Features:
- Real-time risk scoring and approval gating
- Granular autonomy policies (per user, per repo, per action)
- Fast 1-click approval flows
- Complete audit trails
- Rollback capabilities
- Enterprise compliance
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ActionRisk(Enum):
    """Risk levels for actions"""
    LOW = "low"      # 0.0 - 0.3
    MEDIUM = "medium"  # 0.3 - 0.7
    HIGH = "high"    # 0.7 - 1.0


class DecisionType(Enum):
    """Decision types for actions"""
    AUTO = "auto"           # Execute immediately
    APPROVAL = "approval"   # Requires human approval
    BLOCKED = "blocked"     # Not allowed


class AutonomyLevel(Enum):
    """User autonomy levels"""
    MINIMAL = "minimal"     # Most actions require approval
    STANDARD = "standard"   # Balanced autonomy
    ELEVATED = "elevated"   # High autonomy for senior devs
    FULL = "full"          # Maximum autonomy (platform team)


@dataclass
class ActionContext:
    """Context for an action being evaluated"""
    action_type: str
    target_files: Optional[List[str]] = None
    repo: Optional[str] = None
    branch: Optional[str] = None
    command: Optional[str] = None
    touches_auth: bool = False
    touches_prod: bool = False
    is_multi_repo: bool = False
    has_recent_incidents: bool = False
    estimated_impact: str = "low"  # low, medium, high
    user_id: Optional[str] = None
    org_id: str = "default"


@dataclass
class ApprovalRequest:
    """Represents a pending approval request"""
    id: str
    action_type: str
    context: ActionContext
    risk_score: float
    risk_reasons: List[str]
    created_at: datetime
    expires_at: datetime
    requester_id: str
    org_id: str
    plan_summary: str
    artifacts: Optional[Dict[str, Any]] = None


@dataclass
class AutonomyPolicy:
    """Per-user autonomy policy configuration"""
    user_id: str
    org_id: str = "default"
    repo: Optional[str] = None  # If None, applies globally
    autonomy_level: AutonomyLevel = AutonomyLevel.STANDARD
    max_auto_risk: float = 0.3
    blocked_actions: Optional[List[str]] = None
    auto_allowed_actions: Optional[List[str]] = None
    require_approval_for: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class AuditEntry:
    """Immutable audit record"""
    id: str
    timestamp: datetime
    user_id: str
    org_id: str
    action_type: str
    decision: str  # AUTO, APPROVED, REJECTED, BLOCKED
    risk_score: float
    artifacts: Dict[str, Any]
    execution_result: Optional[str] = None
    rollback_available: bool = False