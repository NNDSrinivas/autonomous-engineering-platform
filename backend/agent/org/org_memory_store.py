"""
OrgMemoryStore — Company Brain

Persistent organizational memory that stores learned behaviors, patterns, and 
institutional knowledge across all teams and repositories. This becomes the
long-term institutional memory that makes NAVI impossible to replicate.

Key Capabilities:
- Store organizational signals (CI failures, PR patterns, rollbacks, successes)
- Persistent SQLite storage with organizational context
- Cross-team and cross-repo learning
- Time-based pattern analysis
- Institutional knowledge preservation
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class SignalType(Enum):
    """Types of organizational signals we capture"""
    CI_FAILURE = "ci_failure"
    CI_SUCCESS = "ci_success"
    PR_COMMENT = "pr_comment"
    PR_APPROVAL = "pr_approval"
    PR_REJECTION = "pr_rejection"
    ROLLBACK = "rollback"
    HOTFIX = "hotfix"
    INCIDENT = "incident"
    DEPLOYMENT_SUCCESS = "deployment_success"
    DEPLOYMENT_FAILURE = "deployment_failure"
    MANUAL_OVERRIDE = "manual_override"
    POLICY_VIOLATION = "policy_violation"
    REVIEW_FEEDBACK = "review_feedback"
    FLAKY_TEST = "flaky_test"
    PERFORMANCE_REGRESSION = "performance_regression"

@dataclass
class OrgSignal:
    """A signal captured from organizational engineering activities"""
    id: Optional[str] = None
    signal_type: SignalType = SignalType.CI_FAILURE
    repo: str = ""
    org: str = ""
    team: str = ""
    files: List[str] = field(default_factory=list)
    cause: Optional[str] = None
    resolution: Optional[str] = None
    author: Optional[str] = None
    reviewer: Optional[str] = None
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    impact_scope: str = "LOCAL"  # LOCAL, TEAM, ORG, CUSTOMER
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
class OrgMemoryStore:
    """
    Central organizational memory store that captures, persists, and retrieves
    institutional engineering knowledge across all teams and repositories.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the organizational memory store"""
        if db_path is None:
            # Use workspace data directory 
            workspace_root = Path(__file__).parent.parent.parent.parent
            data_dir = workspace_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "org_memory.db")
        
        self.db_path = db_path
        self._init_database()
        logger.info(f"OrgMemoryStore initialized with database: {db_path}")
    
    def _init_database(self) -> None:
        """Initialize the database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS org_signals (
                    id TEXT PRIMARY KEY,
                    signal_type TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    org TEXT NOT NULL,
                    team TEXT,
                    files TEXT,  -- JSON array
                    cause TEXT,
                    resolution TEXT,
                    author TEXT,
                    reviewer TEXT,
                    severity TEXT,
                    impact_scope TEXT,
                    timestamp DATETIME NOT NULL,
                    metadata TEXT,  -- JSON object
                    tags TEXT  -- JSON array
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_repo_timestamp 
                ON org_signals (repo, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_org_timestamp
                ON org_signals (org, timestamp DESC)  
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_type_timestamp
                ON org_signals (signal_type, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_author_timestamp
                ON org_signals (author, timestamp DESC)
            """)
            
            conn.commit()
    
    def store_signal(self, signal: OrgSignal) -> str:
        """
        Store an organizational signal
        
        Args:
            signal: The signal to store
            
        Returns:
            The signal ID
        """
        if not signal.id:
            signal.id = f"{signal.signal_type.value}_{signal.repo}_{int(signal.timestamp.timestamp())}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO org_signals
                (id, signal_type, repo, org, team, files, cause, resolution,
                 author, reviewer, severity, impact_scope, timestamp, metadata, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.id,
                signal.signal_type.value,
                signal.repo,
                signal.org,
                signal.team,
                json.dumps(signal.files),
                signal.cause,
                signal.resolution,
                signal.author,
                signal.reviewer,
                signal.severity,
                signal.impact_scope,
                signal.timestamp.isoformat(),
                json.dumps(signal.metadata),
                json.dumps(signal.tags)
            ))
            conn.commit()
        
        logger.info(f"Stored organizational signal: {signal.id}")
        return signal.id
    
    def get_signals(self, 
                   repo: Optional[str] = None,
                   org: Optional[str] = None,
                   signal_type: Optional[SignalType] = None,
                   author: Optional[str] = None,
                   since_days: Optional[int] = None,
                   limit: int = 1000) -> List[OrgSignal]:
        """
        Retrieve organizational signals with filtering
        
        Args:
            repo: Filter by repository
            org: Filter by organization  
            signal_type: Filter by signal type
            author: Filter by author
            since_days: Only include signals from last N days
            limit: Maximum number of signals to return
            
        Returns:
            List of matching signals
        """
        query = "SELECT * FROM org_signals WHERE 1=1"
        params = []
        
        if repo:
            query += " AND repo = ?"
            params.append(repo)
            
        if org:
            query += " AND org = ?"
            params.append(org)
            
        if signal_type:
            query += " AND signal_type = ?"
            params.append(signal_type.value)
            
        if author:
            query += " AND author = ?"
            params.append(author)
            
        if since_days:
            since_date = (datetime.now() - timedelta(days=since_days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(since_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        
        signals = []
        for row in rows:
            signal = OrgSignal(
                id=row['id'],
                signal_type=SignalType(row['signal_type']),
                repo=row['repo'],
                org=row['org'],
                team=row['team'],
                files=json.loads(row['files'] or '[]'),
                cause=row['cause'],
                resolution=row['resolution'],
                author=row['author'],
                reviewer=row['reviewer'],
                severity=row['severity'],
                impact_scope=row['impact_scope'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                metadata=json.loads(row['metadata'] or '{}'),
                tags=json.loads(row['tags'] or '[]')
            )
            signals.append(signal)
        
        logger.info(f"Retrieved {len(signals)} organizational signals")
        return signals
    
    def get_org_patterns(self, org: str, days: int = 30) -> Dict[str, Any]:
        """
        Get organizational patterns and trends
        
        Args:
            org: Organization name
            days: Days of history to analyze
            
        Returns:
            Dictionary of organizational patterns
        """
        signals = self.get_signals(org=org, since_days=days)
        
        # Analyze patterns
        patterns = {
            "total_signals": len(signals),
            "signal_breakdown": {},
            "failure_hotspots": {},
            "author_patterns": {},
            "team_patterns": {},
            "temporal_trends": {},
            "severity_distribution": {},
            "most_problematic_files": [],
            "most_active_authors": [],
            "incident_rate": 0.0
        }
        
        # Signal type breakdown
        for signal in signals:
            signal_type = signal.signal_type.value
            patterns["signal_breakdown"][signal_type] = patterns["signal_breakdown"].get(signal_type, 0) + 1
        
        # Failure hotspots (files with most issues)
        file_failures = {}
        for signal in signals:
            if signal.signal_type in [SignalType.CI_FAILURE, SignalType.ROLLBACK, SignalType.INCIDENT]:
                for file_path in signal.files:
                    file_failures[file_path] = file_failures.get(file_path, 0) + 1
        
        patterns["failure_hotspots"] = dict(sorted(file_failures.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Author patterns
        author_signals = {}
        for signal in signals:
            if signal.author:
                if signal.author not in author_signals:
                    author_signals[signal.author] = {"total": 0, "failures": 0, "successes": 0}
                author_signals[signal.author]["total"] += 1
                if signal.signal_type in [SignalType.CI_FAILURE, SignalType.ROLLBACK]:
                    author_signals[signal.author]["failures"] += 1
                elif signal.signal_type in [SignalType.CI_SUCCESS, SignalType.DEPLOYMENT_SUCCESS]:
                    author_signals[signal.author]["successes"] += 1
        
        patterns["author_patterns"] = author_signals
        
        # Team patterns  
        team_signals = {}
        for signal in signals:
            if signal.team:
                team_signals[signal.team] = team_signals.get(signal.team, 0) + 1
        patterns["team_patterns"] = team_signals
        
        # Severity distribution
        severity_dist = {}
        for signal in signals:
            severity_dist[signal.severity] = severity_dist.get(signal.severity, 0) + 1
        patterns["severity_distribution"] = severity_dist
        
        # Most problematic files
        patterns["most_problematic_files"] = list(patterns["failure_hotspots"].keys())[:5]
        
        # Most active authors
        patterns["most_active_authors"] = sorted(
            author_signals.items(), 
            key=lambda x: x[1]["total"], 
            reverse=True
        )[:5]
        
        # Calculate incident rate (incidents per day)
        incident_signals = [s for s in signals if s.signal_type == SignalType.INCIDENT]
        patterns["incident_rate"] = len(incident_signals) / max(1, days)
        
        return patterns
    
    def get_team_knowledge(self, team: str, days: int = 90) -> Dict[str, Any]:
        """
        Get team-specific knowledge and patterns
        
        Args:
            team: Team name
            days: Days of history to analyze
            
        Returns:
            Team knowledge summary
        """
        signals = self.get_signals(since_days=days)
        team_signals = [s for s in signals if s.team == team]
        
        knowledge = {
            "team": team,
            "total_activity": len(team_signals),
            "preferred_practices": [],
            "common_issues": [],
            "review_patterns": [],
            "deployment_patterns": [],
            "expertise_areas": [],
            "risk_factors": []
        }
        
        # Analyze team's preferred practices from successful signals
        [
            s for s in team_signals 
            if s.signal_type in [SignalType.CI_SUCCESS, SignalType.PR_APPROVAL, SignalType.DEPLOYMENT_SUCCESS]
        ]
        
        # Common issues analysis
        failure_signals = [
            s for s in team_signals
            if s.signal_type in [SignalType.CI_FAILURE, SignalType.PR_REJECTION, SignalType.ROLLBACK]
        ]
        
        issue_causes = {}
        for signal in failure_signals:
            if signal.cause:
                issue_causes[signal.cause] = issue_causes.get(signal.cause, 0) + 1
        
        knowledge["common_issues"] = sorted(issue_causes.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Review patterns
        review_signals = [s for s in team_signals if s.reviewer]
        reviewer_patterns = {}
        for signal in review_signals:
            reviewer = signal.reviewer
            if reviewer not in reviewer_patterns:
                reviewer_patterns[reviewer] = {"approvals": 0, "rejections": 0}
            if signal.signal_type == SignalType.PR_APPROVAL:
                reviewer_patterns[reviewer]["approvals"] += 1
            elif signal.signal_type == SignalType.PR_REJECTION:
                reviewer_patterns[reviewer]["rejections"] += 1
        
        knowledge["review_patterns"] = reviewer_patterns
        
        # Expertise areas (files team works on most)
        team_files = {}
        for signal in team_signals:
            for file_path in signal.files:
                team_files[file_path] = team_files.get(file_path, 0) + 1
        
        knowledge["expertise_areas"] = sorted(team_files.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return knowledge
    
    def get_cross_team_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze patterns across teams
        
        Args:
            days: Days of history to analyze
            
        Returns:
            Cross-team pattern analysis
        """
        signals = self.get_signals(since_days=days)
        
        # Group by team
        team_signals = {}
        for signal in signals:
            if signal.team:
                if signal.team not in team_signals:
                    team_signals[signal.team] = []
                team_signals[signal.team].append(signal)
        
        patterns = {
            "team_collaboration": {},
            "shared_repositories": {},
            "cross_team_incidents": [],
            "knowledge_sharing_opportunities": [],
            "coordination_issues": []
        }
        
        # Identify shared repositories
        repo_teams = {}
        for team, team_sigs in team_signals.items():
            for signal in team_sigs:
                if signal.repo not in repo_teams:
                    repo_teams[signal.repo] = set()
                repo_teams[signal.repo].add(team)
        
        patterns["shared_repositories"] = {
            repo: list(teams) for repo, teams in repo_teams.items() 
            if len(teams) > 1
        }
        
        # Cross-team incidents (incidents affecting multiple teams)
        incident_signals = [s for s in signals if s.signal_type == SignalType.INCIDENT]
        for signal in incident_signals:
            affected_teams = set()
            for file_path in signal.files:
                for team, team_sigs in team_signals.items():
                    team_files = set()
                    for ts in team_sigs:
                        team_files.update(ts.files)
                    if file_path in team_files:
                        affected_teams.add(team)
            
            if len(affected_teams) > 1:
                patterns["cross_team_incidents"].append({
                    "incident_id": signal.id,
                    "affected_teams": list(affected_teams),
                    "files": signal.files
                })
        
        return patterns
    
    def calculate_org_health_score(self, org: str, days: int = 30) -> float:
        """
        Calculate overall organizational health score
        
        Args:
            org: Organization name
            days: Days to analyze
            
        Returns:
            Health score between 0.0 and 1.0
        """
        signals = self.get_signals(org=org, since_days=days)
        
        if not signals:
            return 0.8  # Neutral score for orgs with no data
        
        # Count different signal types
        success_count = len([s for s in signals if s.signal_type in [
            SignalType.CI_SUCCESS, SignalType.PR_APPROVAL, SignalType.DEPLOYMENT_SUCCESS
        ]])
        
        failure_count = len([s for s in signals if s.signal_type in [
            SignalType.CI_FAILURE, SignalType.PR_REJECTION, SignalType.ROLLBACK, 
            SignalType.INCIDENT, SignalType.DEPLOYMENT_FAILURE
        ]])
        
        total_meaningful = success_count + failure_count
        
        if total_meaningful == 0:
            return 0.8
        
        success_rate = success_count / total_meaningful
        
        # Adjust for incident severity
        critical_incidents = len([s for s in signals if s.severity == "CRITICAL"])
        critical_penalty = min(0.3, critical_incidents * 0.05)
        
        # Adjust for recent trend (more recent failures are worse)
        recent_signals = [s for s in signals if (datetime.now() - s.timestamp).days <= 7]
        recent_failures = len([s for s in recent_signals if s.signal_type in [
            SignalType.CI_FAILURE, SignalType.ROLLBACK, SignalType.INCIDENT
        ]])
        recent_penalty = min(0.2, recent_failures * 0.02)
        
        health_score = max(0.0, min(1.0, success_rate - critical_penalty - recent_penalty))
        
        logger.info(f"Calculated health score for {org}: {health_score:.2f}")
        return health_score
    
    def get_learning_insights(self, days: int = 90) -> Dict[str, Any]:
        """
        Get insights for organizational learning
        
        Args:
            days: Days of history to analyze
            
        Returns:
            Learning insights
        """
        signals = self.get_signals(since_days=days)
        
        insights = {
            "total_signals_analyzed": len(signals),
            "key_learnings": [],
            "policy_suggestions": [],
            "improvement_opportunities": [],
            "success_patterns": [],
            "failure_patterns": []
        }
        
        # Identify success patterns
        success_signals = [s for s in signals if s.signal_type in [
            SignalType.CI_SUCCESS, SignalType.PR_APPROVAL, SignalType.DEPLOYMENT_SUCCESS
        ]]
        
        # Identify failure patterns  
        failure_signals = [s for s in signals if s.signal_type in [
            SignalType.CI_FAILURE, SignalType.PR_REJECTION, SignalType.ROLLBACK, SignalType.INCIDENT
        ]]
        
        # Generate insights
        if len(failure_signals) > len(success_signals):
            insights["key_learnings"].append("Organization has more failures than successes - focus on quality improvements")
        
        # File-based patterns
        failure_files = {}
        for signal in failure_signals:
            for file_path in signal.files:
                failure_files[file_path] = failure_files.get(file_path, 0) + 1
        
        high_risk_files = [f for f, count in failure_files.items() if count >= 3]
        if high_risk_files:
            insights["policy_suggestions"].append(f"Require extra review for high-risk files: {high_risk_files[:3]}")
        
        # Author patterns
        author_failures = {}
        for signal in failure_signals:
            if signal.author:
                author_failures[signal.author] = author_failures.get(signal.author, 0) + 1
        
        high_failure_authors = [a for a, count in author_failures.items() if count >= 5]
        if high_failure_authors:
            insights["improvement_opportunities"].append("Provide additional training or support for developers with high failure rates")
        
        return insights