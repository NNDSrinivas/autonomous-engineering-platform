"""
Engineering KPI Dashboard Engine

Tracks real engineering metrics that matter:
- Velocity: Story points per sprint
- MTTR: Mean Time To Repair 
- Failure Rate: Bug density and defect rates
- PR Throughput: Pull request processing metrics
- Test Coverage: Code coverage trends
- Lead Time: Idea to production time
- Cycle Time: Development cycle efficiency
- Technical Debt: Accumulation and remediation rates

Navi learns from these metrics and adjusts planning intelligently.
"""

import json
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.core.config import get_settings


class MetricType(Enum):
    """Types of engineering metrics."""
    VELOCITY = "velocity"
    MTTR = "mttr"  
    FAILURE_RATE = "failure_rate"
    PR_THROUGHPUT = "pr_throughput"
    TEST_COVERAGE = "test_coverage"
    LEAD_TIME = "lead_time"
    CYCLE_TIME = "cycle_time"
    TECHNICAL_DEBT = "technical_debt"
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    CHANGE_FAILURE_RATE = "change_failure_rate"


@dataclass
class MetricDataPoint:
    """Single metric measurement."""
    metric_type: MetricType
    value: float
    timestamp: datetime
    context: Optional[Dict[str, Any]] = field(default=None)
    team_id: Optional[str] = None
    sprint_id: Optional[str] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass 
class KPITrend:
    """Trend analysis for a metric."""
    metric_type: MetricType
    current_value: float
    previous_value: float
    change_percentage: float
    trend_direction: str  # "improving", "declining", "stable"
    data_points: List[float]
    analysis: str


@dataclass
class TeamPerformanceReport:
    """Comprehensive team performance analysis."""
    team_id: str
    report_period: str
    velocity: KPITrend
    mttr: KPITrend
    pr_throughput: KPITrend
    test_coverage: KPITrend
    technical_debt_trend: KPITrend
    overall_score: float
    recommendations: List[str]
    achievements: List[str]
    areas_for_improvement: List[str]


class KpiEngine:
    """
    Engineering KPI Dashboard Engine that tracks and analyzes team performance metrics.
    Provides intelligent insights and recommendations based on data trends.
    """
    
    def __init__(self):
        """Initialize the KPI Engine."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.settings = get_settings()
        
        # KPI thresholds and targets
        self.velocity_target = 20  # story points per sprint
        self.mttr_target_hours = 4  # hours
        self.test_coverage_target = 0.8  # 80%
        self.pr_throughput_target = 15  # PRs per week
        self.change_failure_rate_target = 0.1  # 10%
        
    async def record_metric(
        self, 
        metric_type: MetricType,
        value: float,
        context: Optional[Dict[str, Any]] = None,
        team_id: Optional[str] = None,
        sprint_id: Optional[str] = None
    ) -> None:
        """
        Record a new metric data point.
        
        Args:
            metric_type: Type of metric being recorded
            value: Metric value
            context: Additional context about the measurement
            team_id: Team identifier
            sprint_id: Sprint identifier if applicable
        """
        
        data_point = MetricDataPoint(
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            context=context or {},
            team_id=team_id,
            sprint_id=sprint_id
        )
        
        await self._save_metric(data_point)
    
    async def compute_velocity(
        self, 
        team_id: Optional[str] = None, 
        sprint_ids: Optional[List[str]] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Compute team velocity (story points per sprint).
        
        Args:
            team_id: Team to analyze
            sprint_ids: Specific sprints to analyze
            days_back: How many days back to analyze
            
        Returns:
            Velocity analysis with trends
        """
        
        # Get sprint completion data
        if sprint_ids:
            sprint_data = await self._get_sprint_data(sprint_ids)
        else:
            since_date = datetime.now() - timedelta(days=days_back)
            sprint_data = await self._get_team_sprints_since(team_id or "default", since_date)
        
        if not sprint_data:
            return {"velocity": 0, "trend": "no_data", "sprints_analyzed": 0}
        
        # Calculate velocity per sprint
        velocities = []
        for sprint in sprint_data:
            completed_points = sum(item.get("story_points", 0) for item in sprint.get("items", []) 
                                 if item.get("status") == "completed")
            sprint_duration = sprint.get("duration_days", 14)
            normalized_velocity = completed_points * (14 / sprint_duration)  # Normalize to 2-week sprint
            velocities.append(normalized_velocity)
        
        if not velocities:
            return {"velocity": 0, "trend": "no_data", "sprints_analyzed": 0}
        
        current_velocity = statistics.mean(velocities[-3:]) if len(velocities) >= 3 else statistics.mean(velocities)
        previous_velocity = statistics.mean(velocities[:-3]) if len(velocities) >= 6 else velocities[0]
        
        # Record metric
        await self.record_metric(
            MetricType.VELOCITY,
            current_velocity,
            {"sprints_analyzed": len(velocities), "individual_velocities": velocities},
            team_id
        )
        
        return {
            "velocity": current_velocity,
            "previous_velocity": previous_velocity,
            "change_percentage": ((current_velocity - previous_velocity) / previous_velocity * 100) if previous_velocity > 0 else 0,
            "trend": "improving" if current_velocity > previous_velocity else "declining" if current_velocity < previous_velocity else "stable",
            "sprints_analyzed": len(velocities),
            "target_velocity": self.velocity_target,
            "meets_target": current_velocity >= self.velocity_target
        }
    
    async def compute_mttr(
        self, 
        incident_data: Optional[List[Dict[str, Any]]] = None,
        team_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Compute Mean Time To Repair from incident data.
        
        Args:
            incident_data: List of incidents with duration_hours
            team_id: Team to analyze
            days_back: How many days back to analyze
            
        Returns:
            MTTR analysis
        """
        
        if not incident_data:
            # Get incident data from database
            since_date = datetime.now() - timedelta(days=days_back)
            incident_data = await self._get_incidents_since(team_id or "default", since_date)
        
        if not incident_data:
            return {"mttr_hours": 0, "incidents_analyzed": 0, "trend": "no_data"}
        
        # Calculate MTTR
        repair_times = [incident.get("duration_hours", 0) for incident in incident_data if incident.get("duration_hours")]
        
        if not repair_times:
            return {"mttr_hours": 0, "incidents_analyzed": 0, "trend": "no_data"}
        
        current_mttr = statistics.mean(repair_times)
        median_mttr = statistics.median(repair_times)
        
        # Get historical MTTR for comparison
        historical_mttr = await self._get_historical_metric(MetricType.MTTR, team_id, days_back=60)
        previous_mttr = historical_mttr[-1]["value"] if historical_mttr else current_mttr
        
        # Record metric
        await self.record_metric(
            MetricType.MTTR,
            current_mttr,
            {
                "incidents_analyzed": len(incident_data),
                "median_mttr": median_mttr,
                "max_mttr": max(repair_times),
                "min_mttr": min(repair_times)
            },
            team_id
        )
        
        return {
            "mttr_hours": current_mttr,
            "median_mttr": median_mttr,
            "previous_mttr": previous_mttr,
            "change_percentage": ((current_mttr - previous_mttr) / previous_mttr * 100) if previous_mttr > 0 else 0,
            "trend": "improving" if current_mttr < previous_mttr else "declining" if current_mttr > previous_mttr else "stable",
            "incidents_analyzed": len(incident_data),
            "target_mttr": self.mttr_target_hours,
            "meets_target": current_mttr <= self.mttr_target_hours
        }
    
    async def compute_pr_throughput(
        self,
        pr_data: Optional[List[Dict[str, Any]]] = None,
        team_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Compute PR throughput metrics.
        
        Args:
            pr_data: List of PR data with merge times
            team_id: Team to analyze  
            days_back: How many days back to analyze
            
        Returns:
            PR throughput analysis
        """
        
        if not pr_data:
            since_date = datetime.now() - timedelta(days=days_back)
            pr_data = await self._get_prs_since(team_id or "default", since_date)
        
        if not pr_data:
            return {"prs_per_week": 0, "avg_review_time_hours": 0, "merge_rate": 0}
        
        # Calculate metrics
        merged_prs = [pr for pr in pr_data if pr.get("merged", False)]
        total_prs = len(pr_data)
        weeks_analyzed = days_back / 7
        
        prs_per_week = len(merged_prs) / weeks_analyzed if weeks_analyzed > 0 else 0
        merge_rate = len(merged_prs) / total_prs if total_prs > 0 else 0
        
        # Calculate average review time
        review_times = [pr.get("review_time_hours", 0) for pr in merged_prs if pr.get("review_time_hours")]
        avg_review_time = statistics.mean(review_times) if review_times else 0
        
        # Record metric
        await self.record_metric(
            MetricType.PR_THROUGHPUT,
            prs_per_week,
            {
                "total_prs": total_prs,
                "merged_prs": len(merged_prs),
                "merge_rate": merge_rate,
                "avg_review_time_hours": avg_review_time
            },
            team_id
        )
        
        return {
            "prs_per_week": prs_per_week,
            "merge_rate": merge_rate,
            "avg_review_time_hours": avg_review_time,
            "total_prs_analyzed": total_prs,
            "target_throughput": self.pr_throughput_target,
            "meets_target": prs_per_week >= self.pr_throughput_target
        }
    
    async def compute_bug_density(
        self,
        bug_data: Optional[List[Dict[str, Any]]] = None,
        lines_of_code: Optional[int] = None,
        team_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Compute bug density (bugs per KLOC).
        
        Args:
            bug_data: List of bugs found
            lines_of_code: Total lines of code
            team_id: Team to analyze
            days_back: How many days back to analyze
            
        Returns:
            Bug density analysis
        """
        
        if not bug_data:
            since_date = datetime.now() - timedelta(days=days_back)
            bug_data = await self._get_bugs_since(team_id or "default", since_date)
        
        if not lines_of_code:
            lines_of_code = await self._estimate_lines_of_code(team_id or "default")
        
        bug_count = len(bug_data)
        kloc = max(lines_of_code / 1000, 1)  # Convert to thousands of lines
        
        bug_density = bug_count / kloc
        
        # Categorize bugs by severity
        severity_counts = {}
        for bug in bug_data:
            severity = bug.get("severity", "medium")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Record metric
        await self.record_metric(
            MetricType.FAILURE_RATE,
            bug_density,
            {
                "bug_count": bug_count,
                "lines_of_code": lines_of_code,
                "severity_breakdown": severity_counts
            },
            team_id
        )
        
        return {
            "bug_density": bug_density,
            "bug_count": bug_count,
            "lines_of_code": lines_of_code,
            "severity_breakdown": severity_counts,
            "days_analyzed": days_back
        }
    
    async def generate_team_performance_report(
        self,
        team_id: str,
        days_back: int = 30
    ) -> TeamPerformanceReport:
        """
        Generate comprehensive team performance report.
        
        Args:
            team_id: Team to analyze
            days_back: Analysis period in days
            
        Returns:
            Complete performance report with trends and recommendations
        """
        
        # Compute all key metrics
        velocity_data = await self.compute_velocity(team_id, days_back=days_back)
        mttr_data = await self.compute_mttr(team_id=team_id, days_back=days_back)
        pr_data = await self.compute_pr_throughput(team_id=team_id, days_back=days_back)
        
        # Get test coverage trend
        coverage_trend = await self._get_metric_trend(MetricType.TEST_COVERAGE, team_id, days_back)
        
        # Get technical debt trend
        tech_debt_trend = await self._get_metric_trend(MetricType.TECHNICAL_DEBT, team_id, days_back)
        
        # Calculate overall performance score
        overall_score = self._calculate_overall_score({
            "velocity": velocity_data,
            "mttr": mttr_data, 
            "pr_throughput": pr_data,
            "test_coverage": coverage_trend,
            "technical_debt": tech_debt_trend
        })
        
        # Generate AI-powered insights
        insights = await self._generate_performance_insights(team_id, {
            "velocity": velocity_data,
            "mttr": mttr_data,
            "pr_throughput": pr_data,
            "overall_score": overall_score
        })
        
        return TeamPerformanceReport(
            team_id=team_id,
            report_period=f"{days_back} days",
            velocity=self._create_kpi_trend(MetricType.VELOCITY, velocity_data),
            mttr=self._create_kpi_trend(MetricType.MTTR, mttr_data),
            pr_throughput=self._create_kpi_trend(MetricType.PR_THROUGHPUT, pr_data),
            test_coverage=coverage_trend,
            technical_debt_trend=tech_debt_trend,
            overall_score=overall_score,
            recommendations=insights.get("recommendations", []),
            achievements=insights.get("achievements", []),
            areas_for_improvement=insights.get("areas_for_improvement", [])
        )
    
    async def _generate_performance_insights(
        self,
        team_id: str,
        metrics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate AI-powered performance insights."""
        
        insights_prompt = f"""
        You are Navi-PerformanceAnalyst, an expert engineering manager analyzing team performance.
        
        Analyze these team metrics and provide actionable insights:
        
        TEAM METRICS:
        {json.dumps(metrics_data, indent=2, default=str)}
        
        BENCHMARK TARGETS:
        - Velocity: {self.velocity_target} points/sprint
        - MTTR: {self.mttr_target_hours} hours
        - PR Throughput: {self.pr_throughput_target} PRs/week
        - Test Coverage: {self.test_coverage_target * 100}%
        
        Provide analysis in these areas:
        
        1. **Key Achievements**: What is the team doing well?
        2. **Areas for Improvement**: What needs attention?
        3. **Specific Recommendations**: Actionable steps to improve
        4. **Risk Assessment**: Potential issues to watch
        5. **Trend Analysis**: Are things getting better or worse?
        
        Return JSON with your analysis:
        {{
            "achievements": ["Achievement 1", "Achievement 2", ...],
            "areas_for_improvement": ["Area 1", "Area 2", ...],
            "recommendations": [
                {{
                    "area": "velocity|quality|process|tooling",
                    "action": "Specific action to take",
                    "expected_impact": "What should improve",
                    "priority": "high|medium|low"
                }}
            ],
            "risks": ["Risk 1", "Risk 2", ...],
            "trend_summary": "Overall trend description"
        }}
        """
        
        try:
            response = await self.llm.run(prompt=insights_prompt, use_smart_auto=True)
            return json.loads(response.text)
        except Exception:
            return {
                "achievements": ["Team completed analysis period"],
                "areas_for_improvement": ["Monitor metrics more closely"],
                "recommendations": [{"area": "process", "action": "Continue tracking metrics", "priority": "medium"}],
                "risks": [],
                "trend_summary": "Analysis unavailable"
            }
    
    def _calculate_overall_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall performance score (0-100)."""
        scores = []
        
        # Velocity score
        velocity = metrics.get("velocity", {})
        if velocity.get("velocity", 0) > 0:
            velocity_score = min(100, (velocity["velocity"] / self.velocity_target) * 100)
            scores.append(velocity_score)
        
        # MTTR score (inverse - lower is better)
        mttr = metrics.get("mttr", {})
        if mttr.get("mttr_hours", 0) > 0:
            mttr_score = max(0, 100 - (mttr["mttr_hours"] / self.mttr_target_hours) * 50)
            scores.append(mttr_score)
        
        # PR throughput score
        pr_throughput = metrics.get("pr_throughput", {})
        if pr_throughput.get("prs_per_week", 0) > 0:
            pr_score = min(100, (pr_throughput["prs_per_week"] / self.pr_throughput_target) * 100)
            scores.append(pr_score)
        
        return statistics.mean(scores) if scores else 50.0
    
    def _create_kpi_trend(self, metric_type: MetricType, data: Dict[str, Any]) -> KPITrend:
        """Create KPI trend from metric data."""
        current = data.get(metric_type.value.replace("_", ""), 0)
        previous = data.get(f"previous_{metric_type.value.replace('_', '')}", current)
        
        change_pct = ((current - previous) / previous * 100) if previous > 0 else 0
        
        if metric_type in [MetricType.MTTR, MetricType.FAILURE_RATE, MetricType.TECHNICAL_DEBT]:
            # Lower is better for these metrics
            trend = "improving" if change_pct < 0 else "declining" if change_pct > 0 else "stable"
        else:
            # Higher is better for these metrics
            trend = "improving" if change_pct > 0 else "declining" if change_pct < 0 else "stable"
        
        return KPITrend(
            metric_type=metric_type,
            current_value=current,
            previous_value=previous,
            change_percentage=change_pct,
            trend_direction=trend,
            data_points=[previous, current],
            analysis=f"{trend.title()} trend with {abs(change_pct):.1f}% change"
        )
    
    async def _save_metric(self, data_point: MetricDataPoint) -> None:
        """Save metric to database."""
        try:
            query = """
            INSERT INTO kpi_metrics 
            (metric_type, value, timestamp, context, team_id, sprint_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            await self.db.execute(query, [
                data_point.metric_type.value,
                data_point.value,
                data_point.timestamp.isoformat(),
                json.dumps(data_point.context),
                data_point.team_id,
                data_point.sprint_id
            ])
        except Exception:
            # Create table if doesn't exist
            create_query = """
            CREATE TABLE IF NOT EXISTS kpi_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                context TEXT,
                team_id TEXT,
                sprint_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
            await self.db.execute(create_query, [])
            # Retry insert
            await self.db.execute(query, [
                data_point.metric_type.value, data_point.value,
                data_point.timestamp.isoformat(), json.dumps(data_point.context),
                data_point.team_id, data_point.sprint_id
            ])
    
    async def _get_historical_metric(
        self, 
        metric_type: MetricType, 
        team_id: Optional[str] = None, 
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get historical metric data."""
        try:
            since_date = datetime.now() - timedelta(days=days_back)
            query = """
            SELECT * FROM kpi_metrics 
            WHERE metric_type = ? AND timestamp >= ?
            """
            params = [metric_type.value, since_date.isoformat()]
            
            if team_id:
                query += " AND team_id = ?"
                params.append(team_id)
            
            query += " ORDER BY timestamp ASC"
            
            results = await self.db.fetch_all(query, params)
            return results or []
        except Exception:
            return []
    
    async def _get_metric_trend(
        self, 
        metric_type: MetricType, 
        team_id: str, 
        days_back: int
    ) -> KPITrend:
        """Get trend for a specific metric."""
        data = await self._get_historical_metric(metric_type, team_id, days_back)
        
        if len(data) < 2:
            return KPITrend(
                metric_type=metric_type,
                current_value=0,
                previous_value=0,
                change_percentage=0,
                trend_direction="stable",
                data_points=[],
                analysis="Insufficient data"
            )
        
        values = [point["value"] for point in data]
        current = values[-1]
        previous = values[-2] if len(values) >= 2 else values[-1]
        
        change_pct = ((current - previous) / previous * 100) if previous > 0 else 0
        
        return KPITrend(
            metric_type=metric_type,
            current_value=current,
            previous_value=previous,
            change_percentage=change_pct,
            trend_direction="improving" if change_pct > 0 else "declining" if change_pct < 0 else "stable",
            data_points=values,
            analysis=f"Trend analysis based on {len(values)} data points"
        )
    
    # Placeholder methods for data retrieval (would integrate with actual systems)
    async def _get_sprint_data(self, sprint_ids: List[str]) -> List[Dict[str, Any]]:
        """Get sprint data from database.""" 
        return []  # Placeholder
    
    async def _get_team_sprints_since(self, team_id: str, since_date: datetime) -> List[Dict[str, Any]]:
        """Get team sprints since date."""
        return []  # Placeholder
        
    async def _get_incidents_since(self, team_id: str, since_date: datetime) -> List[Dict[str, Any]]:
        """Get incidents since date."""
        return []  # Placeholder
        
    async def _get_prs_since(self, team_id: str, since_date: datetime) -> List[Dict[str, Any]]:
        """Get PRs since date."""
        return []  # Placeholder
        
    async def _get_bugs_since(self, team_id: str, since_date: datetime) -> List[Dict[str, Any]]:
        """Get bugs since date."""
        return []  # Placeholder
        
    async def _estimate_lines_of_code(self, team_id: str) -> int:
        """Estimate lines of code for team."""
        return 10000  # Placeholder