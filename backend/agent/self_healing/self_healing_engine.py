"""
Self-Healing Engine for NAVI Phase 3.6

Responsibility:
- Orchestrate autonomous CI failure recovery
- Enforce confidence and retry limits
- Coordinate with existing Phase 3.3-3.5 systems
- Emit transparent progress events to UI

Purpose:
This is the main orchestrator for autonomous self-healing. It coordinates
between FailureAnalyzer (understanding failures), FixPlanner (deciding what
to fix), and the existing code generation pipeline (Phase 3.3-3.5) to
create a bounded, safe autonomous recovery system.

Safety Guarantees:
- Maximum attempt limits (no infinite loops)
- Confidence thresholds (high confidence required)
- Category restrictions (only safe failure types)
- Human oversight hooks (transparent progress reporting)

Flow:
1. Receive CI failure notification
2. Analyze failure → FailureCause objects
3. Plan fix → FixPlan with safety checks
4. Generate code → Phase 3.3 ChangePlan system
5. Validate → Phase 3.4 validation pipeline
6. Commit → Phase 3.5.2 CommitComposer
7. Monitor → Phase 3.5.4 PRLifecycleEngine
8. Repeat or stop based on results and limits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum

from .failure_analyzer import FailureAnalyzer, FailureCause
from .fix_planner import FixPlanner, FixPlan

logger = logging.getLogger(__name__)


class HealingStatus(Enum):
    """Status of self-healing process."""
    IDLE = "idle"                       # No healing in progress
    ANALYZING = "analyzing"             # Analyzing failure causes
    PLANNING = "planning"               # Planning fix strategy
    GENERATING = "generating"           # Generating code fixes
    VALIDATING = "validating"           # Validating generated fixes
    APPLYING = "applying"               # Applying fixes to codebase
    MONITORING = "monitoring"           # Monitoring CI after fix
    COMPLETED = "completed"             # Healing completed successfully
    BLOCKED = "blocked"                 # Healing blocked (needs human)
    FAILED = "failed"                   # Healing failed
    ABORTED = "aborted"                 # Healing aborted (max attempts)


@dataclass(frozen=True)
class HealingAttempt:
    """Record of a single healing attempt."""
    attempt_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: HealingStatus = HealingStatus.IDLE
    failure_cause: Optional[FailureCause] = None
    fix_plan: Optional[FixPlan] = None
    result_message: str = ""
    commit_sha: Optional[str] = None
    confidence_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['status'] = self.status.value
        result['start_time'] = self.start_time.isoformat() if self.start_time else None
        result['end_time'] = self.end_time.isoformat() if self.end_time else None
        if self.failure_cause:
            result['failure_cause'] = self.failure_cause.to_dict()
        if self.fix_plan:
            result['fix_plan'] = self.fix_plan.to_dict()
        return result


@dataclass
class HealingSession:
    """Complete healing session with multiple attempts."""
    session_id: str
    pr_number: int
    workspace_root: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: HealingStatus = HealingStatus.IDLE
    attempts: list[HealingAttempt] = None
    max_attempts: int = 2
    total_confidence: float = 0.0
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []
    
    @property
    def current_attempt_count(self) -> int:
        return len(self.attempts)
    
    @property
    def is_complete(self) -> bool:
        return self.status in {
            HealingStatus.COMPLETED,
            HealingStatus.BLOCKED,
            HealingStatus.FAILED,
            HealingStatus.ABORTED
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['status'] = self.status.value
        result['start_time'] = self.start_time.isoformat()
        result['end_time'] = self.end_time.isoformat() if self.end_time else None
        result['attempts'] = [attempt.to_dict() for attempt in self.attempts]
        return result


class SelfHealingError(Exception):
    """Raised when self-healing encounters an error."""
    pass


class SelfHealingEngine:
    """
    Controls autonomous CI recovery with safety bounds.
    
    This engine orchestrates the entire self-healing process from failure
    analysis through code generation, validation, and monitoring. It enforces
    strict safety limits to prevent runaway autonomous behavior.
    """

    DEFAULT_MAX_ATTEMPTS = 2
    DEFAULT_MIN_CONFIDENCE = 0.7
    DEFAULT_TIMEOUT_MINUTES = 30

    def __init__(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    ):
        """
        Initialize the self-healing engine.
        
        Args:
            max_attempts: Maximum healing attempts per session
            min_confidence: Minimum confidence required for auto-fix
            timeout_minutes: Maximum time for healing session
        """
        self.max_attempts = max_attempts
        self.min_confidence = min_confidence
        self.timeout_minutes = timeout_minutes
        
        # Components
        self.failure_analyzer = FailureAnalyzer()
        self.fix_planner = FixPlanner()
        
        # Active sessions
        self.active_sessions: Dict[str, HealingSession] = {}
        
        # Statistics
        self.stats = {
            'total_sessions': 0,
            'successful_heals': 0,
            'blocked_heals': 0,
            'failed_heals': 0,
            'aborted_heals': 0
        }

    async def attempt_recovery(
        self,
        *,
        ci_payload: Dict[str, Any],
        pr_number: int,
        workspace_root: str,
        attempt_count: int = 0,
        emit_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Attempt autonomous recovery from CI failure.
        
        Args:
            ci_payload: CI failure information (logs, status, etc.)
            pr_number: PR number for tracking
            workspace_root: Repository root path
            attempt_count: Current attempt number (0-based)
            emit_event: Optional callback for UI event emission
            
        Returns:
            Recovery result dictionary
        """
        session_id = f"heal-{pr_number}-{int(datetime.now().timestamp())}"
        
        try:
            # Create healing session
            session = HealingSession(
                session_id=session_id,
                pr_number=pr_number,
                workspace_root=workspace_root,
                start_time=datetime.now(),
                max_attempts=self.max_attempts
            )
            
            self.active_sessions[session_id] = session
            self.stats['total_sessions'] += 1
            
            # Emit healing started event
            if emit_event:
                await emit_event("navi.selfHealing.started", {
                    "sessionId": session_id,
                    "prNumber": pr_number,
                    "reason": "CI failure detected",
                    "maxAttempts": self.max_attempts
                })
            
            # Check if we've exceeded attempt limits
            if attempt_count >= self.max_attempts:
                session.status = HealingStatus.ABORTED
                session.end_time = datetime.now()
                self.stats['aborted_heals'] += 1
                
                if emit_event:
                    await emit_event("navi.selfHealing.aborted", {
                        "sessionId": session_id,
                        "prNumber": pr_number,
                        "reason": "Max self-healing attempts reached",
                        "attemptCount": attempt_count
                    })
                
                return {
                    "status": "aborted",
                    "reason": "Max self-healing attempts reached",
                    "session_id": session_id,
                    "attempt_count": attempt_count
                }
            
            # Create attempt record
            attempt = HealingAttempt(
                attempt_number=attempt_count + 1,
                start_time=datetime.now(),
                status=HealingStatus.ANALYZING
            )
            session.attempts.append(attempt)
            
            # Step 1: Analyze failure
            session.status = HealingStatus.ANALYZING
            if emit_event:
                await emit_event("navi.selfHealing.analyzing", {
                    "sessionId": session_id,
                    "prNumber": pr_number,
                    "attemptNumber": attempt.attempt_number
                })
            
            try:
                failure_causes = self.failure_analyzer.analyze(ci_payload)
                attempt.failure_cause = failure_causes[0] if failure_causes else None
                
                if not failure_causes:
                    return await self._complete_session(
                        session, attempt, HealingStatus.FAILED,
                        "No failure causes could be identified",
                        emit_event
                    )
                
            except Exception as e:
                logger.exception(f"Failure analysis failed for session {session_id}")
                return await self._complete_session(
                    session, attempt, HealingStatus.FAILED,
                    f"Failure analysis error: {e}",
                    emit_event
                )
            
            # Step 2: Plan fix
            session.status = HealingStatus.PLANNING
            attempt.status = HealingStatus.PLANNING
            
            if emit_event:
                await emit_event("navi.selfHealing.planning", {
                    "sessionId": session_id,
                    "prNumber": pr_number,
                    "failureCategory": failure_causes[0].category.value,
                    "failureMessage": failure_causes[0].message
                })
            
            try:
                planning_context = {
                    'attempt_count': attempt_count,
                    'max_attempts': self.max_attempts,
                    'repo_context': {'workspace_root': workspace_root}
                }
                
                fix_plan = self.fix_planner.plan(failure_causes, planning_context)
                attempt.fix_plan = fix_plan
                attempt.confidence_score = fix_plan.confidence
                
                if not fix_plan.allowed:
                    self.stats['blocked_heals'] += 1
                    
                    if emit_event:
                        await emit_event("navi.selfHealing.blocked", {
                            "sessionId": session_id,
                            "prNumber": pr_number,
                            "reason": fix_plan.reason,
                            "strategy": fix_plan.strategy.value
                        })
                    
                    return await self._complete_session(
                        session, attempt, HealingStatus.BLOCKED,
                        fix_plan.reason,
                        emit_event
                    )
                
                # Check confidence threshold
                if fix_plan.confidence < self.min_confidence:
                    return await self._complete_session(
                        session, attempt, HealingStatus.BLOCKED,
                        f"Fix confidence ({fix_plan.confidence:.2f}) below threshold ({self.min_confidence})",
                        emit_event
                    )
                
                if emit_event:
                    await emit_event("navi.selfHealing.plan", {
                        "sessionId": session_id,
                        "prNumber": pr_number,
                        "goal": fix_plan.fix_goal,
                        "confidence": fix_plan.confidence,
                        "strategy": fix_plan.strategy.value,
                        "riskLevel": fix_plan.risk_level
                    })
                
            except Exception as e:
                logger.exception(f"Fix planning failed for session {session_id}")
                return await self._complete_session(
                    session, attempt, HealingStatus.FAILED,
                    f"Fix planning error: {e}",
                    emit_event
                )
            
            # Step 3: For now, return plan for integration with Phase 3.3-3.5
            # TODO: Integrate with code generation pipeline
            session.status = HealingStatus.COMPLETED
            attempt.status = HealingStatus.COMPLETED
            attempt.end_time = datetime.now()
            session.end_time = datetime.now()
            self.stats['successful_heals'] += 1
            
            if emit_event:
                await emit_event("navi.selfHealing.planReady", {
                    "sessionId": session_id,
                    "prNumber": pr_number,
                    "fixPlan": fix_plan.to_dict(),
                    "readyForGeneration": True
                })
            
            return {
                "status": "fix_planned",
                "session_id": session_id,
                "goal": fix_plan.fix_goal,
                "cause": failure_causes[0].message,
                "confidence": fix_plan.confidence,
                "strategy": fix_plan.strategy.value,
                "attempt_count": attempt_count + 1,
                "fix_plan": fix_plan.to_dict()
            }
            
        except Exception as e:
            logger.exception(f"Self-healing failed for session {session_id}")
            raise SelfHealingError(f"Recovery attempt failed: {e}")

    async def _complete_session(
        self,
        session: HealingSession,
        attempt: HealingAttempt,
        status: HealingStatus,
        message: str,
        emit_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Complete a healing session with final status."""
        
        session.status = status
        session.end_time = datetime.now()
        attempt.status = status
        attempt.end_time = datetime.now()
        attempt.result_message = message
        
        if emit_event:
            await emit_event(f"navi.selfHealing.{status.value}", {
                "sessionId": session.session_id,
                "prNumber": session.pr_number,
                "message": message,
                "duration": (session.end_time - session.start_time).total_seconds()
            })
        
        return {
            "status": status.value,
            "session_id": session.session_id,
            "reason": message,
            "attempt_count": len(session.attempts)
        }

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a healing session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return session.to_dict()

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active healing sessions."""
        return {
            session_id: session.to_dict()
            for session_id, session in self.active_sessions.items()
            if not session.is_complete
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get self-healing statistics."""
        total = max(1, self.stats['total_sessions'])  # Avoid division by zero
        
        return {
            **self.stats,
            'success_rate': self.stats['successful_heals'] / total,
            'block_rate': self.stats['blocked_heals'] / total,
            'active_sessions': len([s for s in self.active_sessions.values() if not s.is_complete])
        }

    def cleanup_completed_sessions(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed sessions older than specified hours.
        
        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        sessions_to_remove = []
        
        for session_id, session in self.active_sessions.items():
            if session.is_complete and session.end_time and session.end_time < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
        
        return len(sessions_to_remove)

    def reset_stats(self) -> None:
        """Reset healing statistics."""
        self.stats = {
            'total_sessions': 0,
            'successful_heals': 0,
            'blocked_heals': 0,
            'failed_heals': 0,
            'aborted_heals': 0
        }

    def __str__(self) -> str:
        active_count = len([s for s in self.active_sessions.values() if not s.is_complete])
        return f"SelfHealingEngine(active_sessions={active_count}, max_attempts={self.max_attempts})"

    def __repr__(self) -> str:
        return (
            f"SelfHealingEngine("
            f"max_attempts={self.max_attempts}, "
            f"min_confidence={self.min_confidence}, "
            f"timeout_minutes={self.timeout_minutes})"
        )