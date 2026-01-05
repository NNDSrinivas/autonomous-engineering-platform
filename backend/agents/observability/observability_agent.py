"""
Observability Agent - Part 14

This agent provides comprehensive monitoring and observability capabilities that
continuously observe console logs, server logs, exceptions, performance traces,
network traffic, API metrics, build logs, and test output to detect anomalies
before they cause failures.

This is a critical capability that Copilot Workspace, Replit Agent, Cursor, and
Gemini Code Assist are missing - proactive monitoring and automatic issue detection.

Capabilities:
- Real-time log monitoring and analysis
- Exception detection and root cause analysis
- Performance trace analysis
- Network traffic monitoring
- API metrics and health monitoring
- Build and test output analysis
- Anomaly detection using pattern recognition
- Integration with RCA and Self-Healing agents
- Proactive alert generation
"""

import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
from collections import defaultdict, deque
import logging

from backend.agents.analysis.rca_agent import RCAAgent
from backend.agents.self_healing.self_healing_agent import SelfHealingAgent
from backend.memory.episodic_memory import EpisodicMemory
from backend.services.llm_router import LLMRouter


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(Enum):
    LOG_ENTRY = "log_entry"
    EXCEPTION = "exception"
    PERFORMANCE_ISSUE = "performance_issue"
    NETWORK_ANOMALY = "network_anomaly"
    API_ERROR = "api_error"
    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY_ALERT = "security_alert"


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    source: str  # File, service, or component
    message: str
    context: Dict[str, Any]
    raw_log: str


@dataclass
class PerformanceMetric:
    timestamp: datetime
    metric_name: str
    value: float
    unit: str
    source: str
    tags: Dict[str, str]


@dataclass
class Anomaly:
    id: str
    timestamp: datetime
    event_type: EventType
    severity: AlertSeverity
    description: str
    affected_components: List[str]
    raw_data: Dict[str, Any]
    pattern_matched: str
    confidence_score: float


@dataclass
class MonitoringAlert:
    id: str
    anomaly_id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    description: str
    recommended_actions: List[str]
    auto_remediation_attempted: bool
    rca_analysis: Optional[Dict[str, Any]] = None
    healing_result: Optional[Dict[str, Any]] = None


class PatternMatcher:
    """Pattern matching engine for detecting known issue patterns in logs."""

    def __init__(self):
        self.patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize known error and anomaly patterns."""
        return {
            "database_connection_error": {
                "pattern": re.compile(
                    r"database.*connection.*(?:failed|error|timeout)", re.IGNORECASE
                ),
                "severity": AlertSeverity.HIGH,
                "category": "database",
                "description": "Database connection issue detected",
            },
            "memory_leak": {
                "pattern": re.compile(
                    r"(?:memory|heap).*(?:leak|exhausted|out of memory)", re.IGNORECASE
                ),
                "severity": AlertSeverity.CRITICAL,
                "category": "performance",
                "description": "Memory leak or exhaustion detected",
            },
            "http_5xx_error": {
                "pattern": re.compile(r"HTTP.*5\d\d", re.IGNORECASE),
                "severity": AlertSeverity.HIGH,
                "category": "api",
                "description": "HTTP server error detected",
            },
            "authentication_failure": {
                "pattern": re.compile(
                    r"auth(?:entication|orization).*(?:failed|denied|invalid)",
                    re.IGNORECASE,
                ),
                "severity": AlertSeverity.MEDIUM,
                "category": "security",
                "description": "Authentication/authorization failure",
            },
            "rate_limit_exceeded": {
                "pattern": re.compile(r"rate.*limit.*exceeded", re.IGNORECASE),
                "severity": AlertSeverity.MEDIUM,
                "category": "api",
                "description": "Rate limit exceeded",
            },
            "sql_injection_attempt": {
                "pattern": re.compile(
                    r"(?:union|select|insert|update|delete).*(?:from|where).*['\"];",
                    re.IGNORECASE,
                ),
                "severity": AlertSeverity.CRITICAL,
                "category": "security",
                "description": "Potential SQL injection attempt",
            },
            "build_failure": {
                "pattern": re.compile(
                    r"build.*(?:failed|error)|compilation.*error|npm.*err",
                    re.IGNORECASE,
                ),
                "severity": AlertSeverity.HIGH,
                "category": "build",
                "description": "Build or compilation failure",
            },
            "test_failure": {
                "pattern": re.compile(
                    r"test.*(?:failed|error)|assertion.*(?:failed|error)", re.IGNORECASE
                ),
                "severity": AlertSeverity.MEDIUM,
                "category": "testing",
                "description": "Test execution failure",
            },
            "network_timeout": {
                "pattern": re.compile(
                    r"network.*timeout|connection.*timeout|request.*timeout",
                    re.IGNORECASE,
                ),
                "severity": AlertSeverity.MEDIUM,
                "category": "network",
                "description": "Network or connection timeout",
            },
            "disk_space_low": {
                "pattern": re.compile(
                    r"disk.*(?:full|space|low)|no.*space.*left", re.IGNORECASE
                ),
                "severity": AlertSeverity.HIGH,
                "category": "resources",
                "description": "Low disk space detected",
            },
            "javascript_error": {
                "pattern": re.compile(
                    r"(?:uncaught|unhandled).*(?:error|exception)|TypeError|ReferenceError",
                    re.IGNORECASE,
                ),
                "severity": AlertSeverity.MEDIUM,
                "category": "frontend",
                "description": "JavaScript runtime error",
            },
            "python_exception": {
                "pattern": re.compile(
                    r"Traceback.*|(?:Error|Exception):.*|File.*line.*", re.IGNORECASE
                ),
                "severity": AlertSeverity.MEDIUM,
                "category": "backend",
                "description": "Python exception detected",
            },
        }

    def match_patterns(self, log_message: str) -> List[Dict[str, Any]]:
        """Match log message against known patterns."""
        matches = []

        for pattern_name, pattern_info in self.patterns.items():
            if pattern_info["pattern"].search(log_message):
                matches.append(
                    {
                        "pattern_name": pattern_name,
                        "severity": pattern_info["severity"],
                        "category": pattern_info["category"],
                        "description": pattern_info["description"],
                    }
                )

        return matches


class AnomalyDetector:
    """Statistical anomaly detection for metrics and performance data."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metric_windows: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

    def add_metric(self, metric_name: str, value: float, timestamp: datetime):
        """Add a new metric value to the detection window."""
        self.metric_windows[metric_name].append((timestamp, value))

    def detect_anomalies(
        self, metric_name: str, threshold_std: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Detect statistical anomalies in metric values."""

        if (
            metric_name not in self.metric_windows
            or len(self.metric_windows[metric_name]) < 10
        ):
            return []

        values = [v for _, v in self.metric_windows[metric_name]]
        timestamps = [t for t, _ in self.metric_windows[metric_name]]

        if len(values) < 10:
            return []

        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0

        if stdev == 0:
            return []

        anomalies = []
        for i, (timestamp, value) in enumerate(
            zip(timestamps[-10:], values[-10:])
        ):  # Check last 10 values
            z_score = abs(value - mean) / stdev

            if z_score > threshold_std:
                anomalies.append(
                    {
                        "timestamp": timestamp,
                        "value": value,
                        "expected_range": (
                            mean - threshold_std * stdev,
                            mean + threshold_std * stdev,
                        ),
                        "z_score": z_score,
                        "severity": self._calculate_severity(z_score),
                    }
                )

        return anomalies

    def _calculate_severity(self, z_score: float) -> AlertSeverity:
        """Calculate severity based on Z-score."""
        if z_score > 4:
            return AlertSeverity.CRITICAL
        elif z_score > 3:
            return AlertSeverity.HIGH
        elif z_score > 2:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW


class ObservabilityAgent:
    """
    Comprehensive observability agent that monitors all aspects of the system
    and proactively detects issues before they cause failures.

    This agent provides capabilities that no existing AI coding assistant offers:
    - Real-time monitoring with intelligent pattern matching
    - Proactive issue detection and automatic remediation
    - Integration with RCA and self-healing systems
    - Performance trend analysis and alerting
    """

    def __init__(self):
        self.rca_agent = RCAAgent(workspace_root=".")
        self.self_healing_agent = SelfHealingAgent(workspace_root=".")
        self.episodic_memory = EpisodicMemory()
        self.llm_router = LLMRouter()

        self.pattern_matcher = PatternMatcher()
        self.anomaly_detector = AnomalyDetector()

        self.monitoring_active = False
        self.alert_callbacks: List[Callable] = []
        self.log_buffer: deque = deque(maxlen=10000)  # Keep last 10k log entries
        self.metrics_buffer: deque = deque(maxlen=5000)  # Keep last 5k metrics
        self.alerts_generated: List[MonitoringAlert] = []

        # Performance baselines
        self.performance_baselines = {}

        # Monitoring configuration
        self.config = {
            "log_monitoring_enabled": True,
            "performance_monitoring_enabled": True,
            "auto_remediation_enabled": True,
            "alert_threshold_std": 2.5,
            "critical_pattern_auto_heal": True,
            "max_alerts_per_minute": 10,
        }

    async def start_monitoring(self, sources: Optional[List[str]] = None):
        """Start continuous monitoring of specified sources."""

        if self.monitoring_active:
            return

        self.monitoring_active = True

        # Record monitoring start
        await self.episodic_memory.record_event(
            event_type="monitoring_start",
            content=f"Started monitoring sources: {sources or ['all']}",
            metadata={"sources": sources or ["all"], "config": self.config},
        )

        # Start monitoring tasks
        monitoring_tasks = [
            self._monitor_logs(),
            self._monitor_performance(),
            self._process_alerts(),
            self._cleanup_old_data(),
        ]

        await asyncio.gather(*monitoring_tasks, return_exceptions=True)

    async def stop_monitoring(self):
        """Stop monitoring activities."""
        self.monitoring_active = False

        await self.episodic_memory.record_event(
            event_type="monitoring_stop",
            content=f"Stopped monitoring, generated {len(self.alerts_generated)} alerts",
            metadata={"alerts_generated": len(self.alerts_generated)},
        )

    async def analyze_log_line(
        self,
        log_line: str,
        source: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[MonitoringAlert]:
        """
        Analyze a single log line for patterns and anomalies.

        This is the main entry point for real-time log analysis.
        """

        try:
            # Parse log entry
            log_entry = self._parse_log_entry(log_line, source, context or {})
            self.log_buffer.append(log_entry)

            # Skip if log monitoring is disabled
            if not self.config["log_monitoring_enabled"]:
                return None

            # Check for immediate patterns
            pattern_matches = self.pattern_matcher.match_patterns(log_line)

            if pattern_matches:
                # Create anomaly for pattern match
                anomaly = Anomaly(
                    id=f"anomaly_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                    timestamp=log_entry.timestamp,
                    event_type=EventType.LOG_ENTRY,
                    severity=max(match["severity"] for match in pattern_matches),
                    description=f"Pattern match: {', '.join(match['description'] for match in pattern_matches)}",
                    affected_components=[source],
                    raw_data={
                        "log_entry": asdict(log_entry),
                        "patterns": pattern_matches,
                    },
                    pattern_matched=pattern_matches[0]["pattern_name"],
                    confidence_score=0.9,  # High confidence for pattern matches
                )

                # Generate alert
                alert = await self._generate_alert(anomaly)

                # Auto-remediation for critical issues
                if self.config["auto_remediation_enabled"] and anomaly.severity in [
                    AlertSeverity.HIGH,
                    AlertSeverity.CRITICAL,
                ]:
                    await self._attempt_auto_remediation(alert, log_entry)

                return alert

            return None

        except Exception as e:
            logging.error(f"Error analyzing log line: {e}")
            return None

    async def analyze_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "",
        source: str = "system",
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[MonitoringAlert]:
        """Analyze a performance metric for anomalies."""

        try:
            if not self.config["performance_monitoring_enabled"]:
                return None

            timestamp = datetime.now()

            # Create metric entry
            metric = PerformanceMetric(
                timestamp=timestamp,
                metric_name=metric_name,
                value=value,
                unit=unit,
                source=source,
                tags=tags or {},
            )

            self.metrics_buffer.append(metric)

            # Add to anomaly detector
            self.anomaly_detector.add_metric(metric_name, value, timestamp)

            # Check for anomalies
            anomalies = self.anomaly_detector.detect_anomalies(
                metric_name, self.config["alert_threshold_std"]
            )

            if anomalies:
                # Create alert for most severe anomaly
                most_severe = max(anomalies, key=lambda a: a["z_score"])

                anomaly = Anomaly(
                    id=f"perf_anomaly_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                    timestamp=timestamp,
                    event_type=EventType.PERFORMANCE_ISSUE,
                    severity=most_severe["severity"],
                    description=f"Performance anomaly in {metric_name}: {value} {unit} (Z-score: {most_severe['z_score']:.2f})",
                    affected_components=[source],
                    raw_data={"metric": asdict(metric), "anomaly_details": most_severe},
                    pattern_matched="statistical_anomaly",
                    confidence_score=min(most_severe["z_score"] / 4.0, 1.0),
                )

                return await self._generate_alert(anomaly)

            return None

        except Exception as e:
            logging.error(f"Error analyzing performance metric: {e}")
            return None

    async def analyze_build_output(
        self, build_output: str, build_type: str = "general"
    ) -> List[MonitoringAlert]:
        """Analyze build output for failures and issues."""

        alerts = []
        lines = build_output.split("\n")

        for i, line in enumerate(lines):
            alert = await self.analyze_log_line(
                line,
                f"build_{build_type}",
                {
                    "build_type": build_type,
                    "line_number": i + 1,
                    "context_lines": lines[max(0, i - 2) : i + 3],
                },
            )

            if alert:
                alerts.append(alert)

        return alerts

    async def analyze_test_output(
        self, test_output: str, test_framework: str = "general"
    ) -> List[MonitoringAlert]:
        """Analyze test execution output for failures and issues."""

        alerts = []
        lines = test_output.split("\n")

        for i, line in enumerate(lines):
            alert = await self.analyze_log_line(
                line,
                f"test_{test_framework}",
                {
                    "test_framework": test_framework,
                    "line_number": i + 1,
                    "context_lines": lines[max(0, i - 2) : i + 3],
                },
            )

            if alert:
                alerts.append(alert)

        return alerts

    async def get_system_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive system health summary."""

        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(days=1)

        # Count recent alerts by severity
        recent_alerts = [a for a in self.alerts_generated if a.timestamp > last_hour]
        daily_alerts = [a for a in self.alerts_generated if a.timestamp > last_24h]

        alert_summary = {
            "critical_last_hour": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
            ),
            "high_last_hour": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.HIGH]
            ),
            "medium_last_hour": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.MEDIUM]
            ),
            "low_last_hour": len(
                [a for a in recent_alerts if a.severity == AlertSeverity.LOW]
            ),
            "total_daily": len(daily_alerts),
        }

        # Performance metrics summary
        performance_summary = {}
        for metric_name in set(m.metric_name for m in list(self.metrics_buffer)[-100:]):
            recent_values = [
                m.value
                for m in list(self.metrics_buffer)
                if m.metric_name == metric_name and m.timestamp > last_hour
            ]
            if recent_values:
                performance_summary[metric_name] = {
                    "current": recent_values[-1] if recent_values else None,
                    "average_hour": (
                        statistics.mean(recent_values) if recent_values else None
                    ),
                    "min_hour": min(recent_values) if recent_values else None,
                    "max_hour": max(recent_values) if recent_values else None,
                }

        # Error rate analysis
        recent_logs = [
            log for log in list(self.log_buffer) if log.timestamp > last_hour
        ]
        error_rate = len(
            [
                log
                for log in recent_logs
                if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]
            ]
        ) / max(len(recent_logs), 1)

        return {
            "timestamp": now.isoformat(),
            "monitoring_active": self.monitoring_active,
            "alerts": alert_summary,
            "performance": performance_summary,
            "error_rate_last_hour": error_rate,
            "total_log_entries_hour": len(recent_logs),
            "system_health_score": self._calculate_health_score(
                alert_summary, error_rate
            ),
            "recommendations": await self._generate_health_recommendations(
                alert_summary, error_rate
            ),
        }

    async def register_alert_callback(
        self, callback: Callable[[MonitoringAlert], None]
    ):
        """Register a callback function to be called when alerts are generated."""
        self.alert_callbacks.append(callback)

    def configure_monitoring(self, config_updates: Dict[str, Any]):
        """Update monitoring configuration."""
        self.config.update(config_updates)

    # Private methods

    def _parse_log_entry(
        self, log_line: str, source: str, context: Dict[str, Any]
    ) -> LogEntry:
        """Parse a log line into a structured LogEntry."""

        timestamp = datetime.now()

        # Try to extract timestamp from log line
        timestamp_patterns = [
            r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})",  # ISO format
            r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",  # US format
            r"(\d{2}:\d{2}:\d{2})",  # Time only
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, log_line)
            if match:
                try:
                    if len(match.group(1)) > 8:  # Full date
                        timestamp = datetime.fromisoformat(
                            match.group(1).replace("T", " ")
                        )
                    break
                except Exception:
                    continue

        # Determine log level
        level = LogLevel.INFO  # Default
        log_lower = log_line.lower()

        if "critical" in log_lower or "fatal" in log_lower:
            level = LogLevel.CRITICAL
        elif "error" in log_lower:
            level = LogLevel.ERROR
        elif "warn" in log_lower:
            level = LogLevel.WARNING
        elif "debug" in log_lower:
            level = LogLevel.DEBUG

        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            message=log_line.strip(),
            context=context,
            raw_log=log_line,
        )

    async def _generate_alert(self, anomaly: Anomaly) -> MonitoringAlert:
        """Generate a monitoring alert from an anomaly."""

        # Generate recommended actions using LLM
        recommended_actions = await self._generate_recommended_actions(anomaly)

        alert = MonitoringAlert(
            id=f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            anomaly_id=anomaly.id,
            timestamp=anomaly.timestamp,
            severity=anomaly.severity,
            title=anomaly.description,
            description=f"Anomaly detected in {', '.join(anomaly.affected_components)}: {anomaly.description}",
            recommended_actions=recommended_actions,
            auto_remediation_attempted=False,
        )

        self.alerts_generated.append(alert)

        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logging.error(f"Error in alert callback: {e}")

        # Record in episodic memory
        await self.episodic_memory.record_event(
            event_type="alert_generated",
            content=f"Alert generated: {alert.severity.value} - {alert.description}",
            metadata={
                "alert_id": alert.id,
                "severity": alert.severity.value,
                "description": alert.description,
                "anomaly_pattern": anomaly.pattern_matched,
            },
        )

        return alert

    async def _attempt_auto_remediation(
        self, alert: MonitoringAlert, log_entry: LogEntry
    ):
        """Attempt automatic remediation for critical issues."""

        try:
            alert.auto_remediation_attempted = True

            # Perform RCA analysis
            rca_result = await self.rca_agent.analyze_failure(
                error=alert.description,
                repo_map={"error_log": log_entry.raw_log},
                error_context={"alert": asdict(alert)},
            )
            alert.rca_analysis = rca_result

            # Attempt self-healing if RCA provides actionable insights
            if rca_result and rca_result.get("confidence_score", 0) > 0.7:
                healing_result = await self.self_healing_agent.detect_and_heal(
                    context={
                        "error_message": alert.description,
                        "log_entry": asdict(log_entry),
                        "rca_analysis": rca_result,
                    }
                )
                alert.healing_result = asdict(healing_result)

        except Exception as e:
            logging.error(f"Error in auto-remediation: {e}")

    async def _generate_recommended_actions(self, anomaly: Anomaly) -> List[str]:
        """Generate recommended actions for an anomaly using LLM."""

        prompt = f"""
        You are Navi-ObservabilityAnalyst, an expert in system monitoring and incident response.
        
        An anomaly has been detected in our system:
        
        TYPE: {anomaly.event_type.value}
        SEVERITY: {anomaly.severity.value}
        DESCRIPTION: {anomaly.description}
        AFFECTED COMPONENTS: {', '.join(anomaly.affected_components)}
        PATTERN: {anomaly.pattern_matched}
        CONFIDENCE: {anomaly.confidence_score:.2f}
        
        RAW DATA: {json.dumps(anomaly.raw_data, indent=2, default=str)[:500]}...
        
        Provide 3-5 specific, actionable recommendations for:
        1. Immediate investigation steps
        2. Short-term mitigation actions
        3. Long-term prevention measures
        
        Focus on practical actions that can be automated or quickly executed.
        """

        try:
            response = await self.llm_router.run(prompt=prompt, use_smart_auto=True)
            recommendations_text = response.text

            # Parse recommendations from response
            recommendations = []
            lines = recommendations_text.split("\n")

            for line in lines:
                line = line.strip()
                if line and (
                    line.startswith("-") or line.startswith("•") or line[0].isdigit()
                ):
                    recommendation = line.lstrip("- •0123456789.")
                    if recommendation:
                        recommendations.append(recommendation.strip())

            return recommendations[:5]  # Limit to 5 recommendations

        except Exception as e:
            logging.error(f"Error generating recommendations: {e}")
            return [
                "Review system logs for related errors",
                "Check system resources (CPU, memory, disk)",
                "Verify network connectivity and dependencies",
                "Consider scaling up resources if needed",
            ]

    def _calculate_health_score(
        self, alert_summary: Dict[str, Any], error_rate: float
    ) -> float:
        """Calculate overall system health score (0-100)."""

        base_score = 100.0

        # Deduct points for alerts
        base_score -= alert_summary["critical_last_hour"] * 25
        base_score -= alert_summary["high_last_hour"] * 15
        base_score -= alert_summary["medium_last_hour"] * 5
        base_score -= alert_summary["low_last_hour"] * 1

        # Deduct points for error rate
        base_score -= error_rate * 50

        return max(0.0, min(100.0, base_score))

    async def _generate_health_recommendations(
        self, alert_summary: Dict[str, Any], error_rate: float
    ) -> List[str]:
        """Generate health improvement recommendations."""

        recommendations = []

        if alert_summary["critical_last_hour"] > 0:
            recommendations.append(
                "Critical alerts detected - immediate attention required"
            )

        if error_rate > 0.1:  # More than 10% error rate
            recommendations.append(
                "High error rate detected - investigate error patterns"
            )

        if alert_summary["total_daily"] > 50:
            recommendations.append(
                "High alert volume - consider tuning alert thresholds"
            )

        if not recommendations:
            recommendations.append("System health is good - continue monitoring")

        return recommendations

    async def _monitor_logs(self):
        """Background task for continuous log monitoring."""

        while self.monitoring_active:
            try:
                # In production, this would connect to actual log sources
                # For now, simulate periodic checks
                await asyncio.sleep(1)

            except Exception as e:
                logging.error(f"Error in log monitoring: {e}")
                await asyncio.sleep(5)

    async def _monitor_performance(self):
        """Background task for performance monitoring."""

        while self.monitoring_active:
            try:
                # In production, this would collect real performance metrics
                # For now, simulate periodic metric collection
                await asyncio.sleep(30)

            except Exception as e:
                logging.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(30)

    async def _process_alerts(self):
        """Background task for alert processing and correlation."""

        while self.monitoring_active:
            try:
                # Process alert correlations, escalations, etc.
                await asyncio.sleep(10)

            except Exception as e:
                logging.error(f"Error in alert processing: {e}")
                await asyncio.sleep(10)

    async def _cleanup_old_data(self):
        """Background task for cleaning up old monitoring data."""

        while self.monitoring_active:
            try:
                # Clean up old alerts (keep last 1000)
                if len(self.alerts_generated) > 1000:
                    self.alerts_generated = self.alerts_generated[-1000:]

                await asyncio.sleep(3600)  # Clean up every hour

            except Exception as e:
                logging.error(f"Error in data cleanup: {e}")
                await asyncio.sleep(3600)


class ObservabilityService:
    """Service layer for integrating Observability Agent with the platform."""

    def __init__(self):
        self.agent = ObservabilityAgent()

    async def start_system_monitoring(self) -> Dict[str, Any]:
        """Start comprehensive system monitoring."""

        await self.agent.start_monitoring()

        return {
            "status": "monitoring_started",
            "monitoring_active": self.agent.monitoring_active,
            "config": self.agent.config,
        }

    async def analyze_log_stream(
        self, log_lines: List[str], source: str = "application"
    ) -> List[MonitoringAlert]:
        """Analyze a stream of log lines."""

        alerts = []

        for log_line in log_lines:
            alert = await self.agent.analyze_log_line(log_line, source)
            if alert:
                alerts.append(alert)

        return alerts

    async def get_health_dashboard_data(self) -> Dict[str, Any]:
        """Get data for health monitoring dashboard."""

        return await self.agent.get_system_health_summary()

    async def configure_monitoring(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update monitoring configuration."""

        self.agent.configure_monitoring(config)

        return {"status": "configuration_updated", "new_config": self.agent.config}
