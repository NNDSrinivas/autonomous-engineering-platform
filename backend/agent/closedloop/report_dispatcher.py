"""
Phase 5.0 — Report Dispatcher (Human-Readable Communication)

Creates human-readable progress updates and dispatches them to multiple channels
(Slack, Teams, Jira, email) providing clear communication about autonomous actions
and their outcomes. Integrates with existing notification infrastructure.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

from backend.agent.closedloop.execution_controller import ExecutionResult
from backend.agent.closedloop.verification_engine import VerificationResult
from backend.agent.closedloop.auto_planner import PlannedAction, ActionType, ExecutionPlan
from backend.agent.closedloop.context_resolver import ResolvedContext
from backend.agent.closedloop.event_ingestor import ProcessedEvent
from backend.services.jira import JiraService
from backend.services.slack_service import _get_client as _get_slack_client


logger = logging.getLogger(__name__)


class ReportChannel(Enum):
    """Supported communication channels for reports"""
    SLACK = "slack"
    TEAMS = "teams"
    JIRA = "jira"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class ReportType(Enum):
    """Types of reports to generate"""
    EXECUTION_START = "execution_start"
    EXECUTION_PROGRESS = "execution_progress"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_RESULTS = "verification_results"
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_CANCELLED = "plan_cancelled"
    ESCALATION_ALERT = "escalation_alert"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    COMPLIANCE_REPORT = "compliance_report"
    SAFETY_ALERT = "safety_alert"


class ReportPriority(Enum):
    """Priority levels for reports"""
    CRITICAL = "critical"    # Immediate notification required
    HIGH = "high"           # Important but can wait a few minutes
    MEDIUM = "medium"       # Standard notifications
    LOW = "low"            # Informational only
    DEBUG = "debug"        # Development/debugging only


@dataclass
class ReportTemplate:
    """Template for generating reports"""
    report_type: ReportType
    channels: List[ReportChannel]
    priority: ReportPriority
    
    # Template content
    title_template: str
    summary_template: str
    detailed_template: Optional[str] = None
    
    # Channel-specific formatting
    slack_format: Optional[str] = None
    jira_format: Optional[str] = None
    email_format: Optional[str] = None
    
    # Delivery settings
    immediate_delivery: bool = True
    batch_delivery: bool = False
    suppress_duplicates: bool = True
    
    # Audience targeting
    target_roles: List[str] = field(default_factory=list)
    target_users: List[str] = field(default_factory=list)
    escalation_channels: List[ReportChannel] = field(default_factory=list)


@dataclass
class GeneratedReport:
    """A generated report ready for dispatch"""
    report_id: str
    report_type: ReportType
    priority: ReportPriority
    
    # Content
    title: str
    summary: str
    detailed_content: Optional[str] = None
    
    # Context and metadata
    source_event: Optional[ProcessedEvent] = None
    execution_result: Optional[ExecutionResult] = None
    verification_result: Optional[VerificationResult] = None
    plan: Optional[ExecutionPlan] = None
    
    # Delivery information
    target_channels: List[ReportChannel] = field(default_factory=list)
    target_users: List[str] = field(default_factory=list)
    
    # Formatting per channel
    channel_content: Dict[ReportChannel, str] = field(default_factory=dict)
    
    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    # Delivery tracking
    delivery_attempts: Dict[ReportChannel, List[Dict[str, Any]]] = field(default_factory=dict)
    successful_deliveries: Set[ReportChannel] = field(default_factory=set)
    failed_deliveries: Dict[ReportChannel, str] = field(default_factory=dict)


class ReportDispatcher:
    """
    Human-readable communication system for autonomous operations
    
    Key responsibilities:
    1. Generate human-readable reports from execution results
    2. Format reports appropriately for different channels
    3. Dispatch to multiple communication platforms
    4. Handle delivery failures and retries
    5. Provide executive summaries and detailed technical reports
    6. Integrate with existing notification infrastructure
    """
    
    def __init__(self, db_session, workspace_path: Optional[str] = None):
        self.db = db_session
        self.workspace_path = workspace_path
        
        # Communication clients
        self.slack_client = _get_slack_client()
        
        # Delivery configuration
        self.max_retries = 3
        self.retry_delay_seconds = 30
        self.batch_size = 10
        self.rate_limit_per_minute = 60
        
        # Report templates
        self.templates: Dict[ReportType, ReportTemplate] = {}
        self._initialize_templates()
        
        # Delivery tracking
        self.delivery_queue: asyncio.Queue = asyncio.Queue()
        self.delivery_history: Dict[str, GeneratedReport] = {}
        self.rate_limit_trackers: Dict[ReportChannel, List[datetime]] = {}
        
        # Channel mappings
        self.channel_mappings: Dict[str, Dict[str, Any]] = {
            "engineering": {
                "slack_channel": "#engineering",
                "teams_channel": "Engineering Team",
                "email_list": ["eng@company.com"],
                "priority_threshold": ReportPriority.MEDIUM
            },
            "management": {
                "slack_channel": "#management",
                "teams_channel": "Management",
                "email_list": ["management@company.com"],
                "priority_threshold": ReportPriority.HIGH
            },
            "oncall": {
                "slack_channel": "#oncall",
                "teams_channel": "OnCall",
                "email_list": ["oncall@company.com"],
                "priority_threshold": ReportPriority.CRITICAL
            }
        }
    
    def _initialize_templates(self):
        """Initialize default report templates"""
        
        # Execution Start Reports
        self.templates[ReportType.EXECUTION_START] = ReportTemplate(
            report_type=ReportType.EXECUTION_START,
            channels=[ReportChannel.SLACK, ReportChannel.JIRA],
            priority=ReportPriority.MEDIUM,
            title_template="🚀 Starting Autonomous Action: {action_type}",
            summary_template="NAVI is beginning {action_type} for {target}. Expected duration: {duration} minutes.",
            detailed_template="**Action Details:**\n- Type: {action_type}\n- Target: {target}\n- Confidence: {confidence}%\n- Safety Level: {safety_level}\n- Prerequisites: {prerequisites}\n\n**Context:**\n{context_summary}",
            slack_format="🚀 *Starting {action_type}*\n📋 Target: `{target}`\n⏱️ Est. Duration: {duration}min\n🎯 Confidence: {confidence}%\n\n{context_summary}",
            jira_format="h3. Autonomous Action Started\n\n*Action:* {action_type}\n*Target:* {target}\n*Duration:* {duration} minutes\n*Confidence:* {confidence}%\n\n{context_summary}",
            target_roles=["assignee", "reporter", "watchers"],
            suppress_duplicates=False
        )
        
        # Execution Complete Reports
        self.templates[ReportType.EXECUTION_COMPLETE] = ReportTemplate(
            report_type=ReportType.EXECUTION_COMPLETE,
            channels=[ReportChannel.SLACK, ReportChannel.JIRA],
            priority=ReportPriority.MEDIUM,
            title_template="✅ Completed: {action_type}",
            summary_template="NAVI successfully completed {action_type} for {target} in {actual_duration} minutes.",
            detailed_template="**Execution Summary:**\n- Action: {action_type}\n- Target: {target}\n- Duration: {actual_duration}min (estimated {estimated_duration}min)\n- Status: {status}\n\n**Results:**\n{results_summary}\n\n**Next Steps:**\n{next_steps}",
            slack_format="✅ *Completed {action_type}*\n📋 Target: `{target}`\n⏱️ Duration: {actual_duration}min\n🎯 Status: {status}\n\n*Results:*\n{results_summary}\n\n*Next Steps:*\n{next_steps}",
            jira_format="h3. Action Completed Successfully\n\n*Action:* {action_type}\n*Target:* {target}\n*Duration:* {actual_duration} minutes\n*Status:* {status}\n\n*Results:*\n{results_summary}\n\n*Next Steps:*\n{next_steps}",
            target_roles=["assignee", "reporter", "watchers"]
        )
        
        # Execution Failed Reports
        self.templates[ReportType.EXECUTION_FAILED] = ReportTemplate(
            report_type=ReportType.EXECUTION_FAILED,
            channels=[ReportChannel.SLACK, ReportChannel.JIRA],
            priority=ReportPriority.HIGH,
            title_template="❌ Failed: {action_type}",
            summary_template="NAVI failed to complete {action_type} for {target}. Error: {error_message}",
            detailed_template="**Execution Failed:**\n- Action: {action_type}\n- Target: {target}\n- Error: {error_message}\n- Duration: {actual_duration}min\n- Retry Count: {retry_count}\n\n**Error Details:**\n{error_details}\n\n**Recommended Actions:**\n{recommendations}",
            slack_format="❌ *Failed {action_type}*\n📋 Target: `{target}`\n💥 Error: {error_message}\n🔄 Retries: {retry_count}\n\n*Recommended Actions:*\n{recommendations}",
            jira_format="h3. Action Failed\n\n*Action:* {action_type}\n*Target:* {target}\n*Error:* {error_message}\n*Retries:* {retry_count}\n\n*Error Details:*\n{error_details}\n\n*Recommended Actions:*\n{recommendations}",
            target_roles=["assignee", "reporter", "watchers"],
            escalation_channels=[ReportChannel.EMAIL],
            suppress_duplicates=False
        )
        
        # Verification Results
        self.templates[ReportType.VERIFICATION_RESULTS] = ReportTemplate(
            report_type=ReportType.VERIFICATION_RESULTS,
            channels=[ReportChannel.SLACK],
            priority=ReportPriority.MEDIUM,
            title_template="🔍 Verification Results: {overall_status}",
            summary_template="Verification completed for {action_type}. Overall score: {score}%. Status: {status}",
            detailed_template="**Verification Summary:**\n- Action: {action_type}\n- Overall Score: {score}%\n- Status: {status}\n- Checks Passed: {passed}/{total}\n- Critical Issues: {critical_issues}\n\n**Quality Metrics:**\n{quality_summary}\n\n**Recommendations:**\n{recommendations}",
            slack_format="🔍 *Verification Results*\n📊 Score: {score}% ({status})\n✅ Passed: {passed}/{total}\n🚨 Critical: {critical_issues}\n\n*Recommendations:*\n{recommendations}",
            target_roles=["assignee", "reviewer"]
        )
        
        # Plan Created
        self.templates[ReportType.PLAN_CREATED] = ReportTemplate(
            report_type=ReportType.PLAN_CREATED,
            channels=[ReportChannel.SLACK, ReportChannel.JIRA],
            priority=ReportPriority.MEDIUM,
            title_template="📋 Execution Plan Created",
            summary_template="NAVI created an execution plan with {action_count} actions. Confidence: {confidence}%",
            detailed_template="**Execution Plan:**\n- Actions: {action_count}\n- Overall Confidence: {confidence}%\n- Safety Level: {safety_level}\n- Estimated Duration: {estimated_duration}min\n\n**Primary Actions:**\n{actions_summary}\n\n**Human Approval:** {approval_required}",
            slack_format="📋 *Execution Plan Created*\n🎯 Actions: {action_count}\n📊 Confidence: {confidence}%\n⏱️ Duration: {estimated_duration}min\n👤 Approval: {approval_required}\n\n*Actions:*\n{actions_summary}",
            target_roles=["assignee", "approver"]
        )
        
        # Safety Alerts
        self.templates[ReportType.SAFETY_ALERT] = ReportTemplate(
            report_type=ReportType.SAFETY_ALERT,
            channels=[ReportChannel.SLACK, ReportChannel.EMAIL],
            priority=ReportPriority.CRITICAL,
            title_template="🚨 SAFETY ALERT: {alert_type}",
            summary_template="Critical safety issue detected in {action_type}. Immediate attention required.",
            detailed_template="**SAFETY ALERT:**\n- Alert Type: {alert_type}\n- Action: {action_type}\n- Risk Level: {risk_level}\n- Details: {safety_details}\n\n**Immediate Actions Required:**\n{required_actions}\n\n**Contact:** {contact_info}",
            slack_format="🚨 *SAFETY ALERT* 🚨\n⚠️ Risk: {risk_level}\n🔍 Issue: {alert_type}\n\n*Immediate Actions Required:*\n{required_actions}\n\n<!channel>",
            email_format="CRITICAL SAFETY ALERT\n\nRisk Level: {risk_level}\nIssue: {alert_type}\nAction: {action_type}\n\nDetails: {safety_details}\n\nImmediate Actions Required:\n{required_actions}\n\nContact: {contact_info}",
            target_roles=["oncall", "management", "safety_team"],
            immediate_delivery=True,
            suppress_duplicates=False
        )
        
        # Daily Summary
        self.templates[ReportType.DAILY_SUMMARY] = ReportTemplate(
            report_type=ReportType.DAILY_SUMMARY,
            channels=[ReportChannel.SLACK, ReportChannel.EMAIL],
            priority=ReportPriority.LOW,
            title_template="📊 NAVI Daily Summary - {date}",
            summary_template="Today's autonomous operations: {total_actions} actions, {success_rate}% success rate",
            detailed_template="**NAVI Daily Summary - {date}**\n\n**Overview:**\n- Total Actions: {total_actions}\n- Success Rate: {success_rate}%\n- Average Duration: {avg_duration}min\n\n**Action Breakdown:**\n{action_breakdown}\n\n**Quality Metrics:**\n{quality_metrics}\n\n**Notable Events:**\n{notable_events}",
            slack_format="📊 *NAVI Daily Summary - {date}*\n\n✅ Success Rate: {success_rate}%\n⚡ Total Actions: {total_actions}\n⏱️ Avg Duration: {avg_duration}min\n\n*Top Actions:*\n{action_breakdown}\n\n*Quality Score:* {quality_score}%",
            target_roles=["management", "engineering_leads"],
            immediate_delivery=False,
            batch_delivery=True
        )
    
    async def dispatch_execution_start(
        self,
        plan: ExecutionPlan,
        action: PlannedAction,
        context: ResolvedContext
    ) -> GeneratedReport:
        """Dispatch report for execution start"""
        
        template_data = {
            "action_type": action.action_type.value.replace('_', ' ').title(),
            "target": action.target,
            "duration": action.estimated_duration,
            "confidence": int(action.confidence_score * 100),
            "safety_level": action.safety_level.value.title(),
            "prerequisites": ", ".join(action.prerequisites) if action.prerequisites else "None",
            "context_summary": self._generate_context_summary(context)
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.EXECUTION_START,
            template_data,
            source_event=None,
            plan=plan,
            target_users=self._extract_target_users(action, context)
        )
    
    async def dispatch_execution_complete(
        self,
        execution_result: ExecutionResult,
        verification_result: Optional[VerificationResult] = None,
        context: Optional[ResolvedContext] = None
    ) -> GeneratedReport:
        """Dispatch report for successful execution completion"""
        
        action = execution_result.action
        
        template_data = {
            "action_type": action.action_type.value.replace('_', ' ').title(),
            "target": action.target,
            "estimated_duration": action.estimated_duration,
            "actual_duration": int(execution_result.duration_seconds / 60),
            "status": "Completed Successfully",
            "results_summary": self._format_execution_results(execution_result),
            "next_steps": self._generate_next_steps(execution_result, verification_result)
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.EXECUTION_COMPLETE,
            template_data,
            execution_result=execution_result,
            verification_result=verification_result,
            target_users=self._extract_target_users(action, context)
        )
    
    async def dispatch_execution_failed(
        self,
        execution_result: ExecutionResult,
        context: Optional[ResolvedContext] = None
    ) -> GeneratedReport:
        """Dispatch report for failed execution"""
        
        action = execution_result.action
        
        template_data = {
            "action_type": action.action_type.value.replace('_', ' ').title(),
            "target": action.target,
            "error_message": execution_result.error_message or "Unknown error",
            "actual_duration": int(execution_result.duration_seconds / 60),
            "retry_count": execution_result.retry_count,
            "error_details": execution_result.error_traceback or "No details available",
            "recommendations": self._generate_failure_recommendations(execution_result)
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.EXECUTION_FAILED,
            template_data,
            execution_result=execution_result,
            target_users=self._extract_target_users(action, context)
        )
    
    async def dispatch_verification_results(
        self,
        verification_result: VerificationResult,
        execution_result: ExecutionResult,
        context: Optional[ResolvedContext] = None
    ) -> GeneratedReport:
        """Dispatch verification results report"""
        
        action = execution_result.action
        
        template_data = {
            "action_type": action.action_type.value.replace('_', ' ').title(),
            "score": int(verification_result.overall_score * 100),
            "status": verification_result.verification_status.value.title(),
            "passed": verification_result.passed_checks,
            "total": verification_result.total_checks,
            "critical_issues": len(verification_result.critical_issues),
            "quality_summary": self._format_quality_summary(verification_result),
            "recommendations": "\n".join(verification_result.recommendations)
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.VERIFICATION_RESULTS,
            template_data,
            execution_result=execution_result,
            verification_result=verification_result,
            target_users=self._extract_target_users(action, context)
        )
    
    async def dispatch_plan_created(
        self,
        plan: ExecutionPlan,
        context: ResolvedContext
    ) -> GeneratedReport:
        """Dispatch plan creation report"""
        
        template_data = {
            "action_count": len(plan.primary_actions),
            "confidence": int(plan.overall_confidence * 100),
            "safety_level": plan.overall_safety.value.title(),
            "estimated_duration": sum(action.estimated_duration for action in plan.primary_actions),
            "actions_summary": self._format_actions_summary(plan.primary_actions),
            "approval_required": "Yes" if plan.human_approval_needed else "No"
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.PLAN_CREATED,
            template_data,
            plan=plan,
            target_users=self._extract_plan_stakeholders(plan, context)
        )
    
    async def dispatch_safety_alert(
        self,
        alert_type: str,
        action_type: ActionType,
        risk_level: str,
        safety_details: str,
        required_actions: List[str],
        context: Optional[ResolvedContext] = None
    ) -> GeneratedReport:
        """Dispatch critical safety alert"""
        
        template_data = {
            "alert_type": alert_type,
            "action_type": action_type.value.replace('_', ' ').title(),
            "risk_level": risk_level.upper(),
            "safety_details": safety_details,
            "required_actions": "\n".join(f"• {action}" for action in required_actions),
            "contact_info": "oncall@company.com"
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.SAFETY_ALERT,
            template_data,
            priority_override=ReportPriority.CRITICAL,
            target_users=["oncall", "safety_team", "management"]
        )
    
    async def dispatch_daily_summary(
        self,
        date: datetime,
        execution_stats: Dict[str, Any],
        quality_metrics: Dict[str, Any],
        notable_events: List[str]
    ) -> GeneratedReport:
        """Dispatch daily summary report"""
        
        template_data = {
            "date": date.strftime("%Y-%m-%d"),
            "total_actions": execution_stats.get("total_actions", 0),
            "success_rate": int(execution_stats.get("success_rate", 0) * 100),
            "avg_duration": int(execution_stats.get("avg_duration", 0)),
            "action_breakdown": self._format_action_breakdown(execution_stats.get("action_breakdown", {})),
            "quality_metrics": self._format_quality_metrics(quality_metrics),
            "quality_score": int(quality_metrics.get("overall_score", 0) * 100),
            "notable_events": "\n".join(f"• {event}" for event in notable_events[:5])
        }
        
        return await self._generate_and_dispatch_report(
            ReportType.DAILY_SUMMARY,
            template_data,
            target_users=["management", "engineering_leads"]
        )
    
    async def _generate_and_dispatch_report(
        self,
        report_type: ReportType,
        template_data: Dict[str, Any],
        source_event: Optional[ProcessedEvent] = None,
        execution_result: Optional[ExecutionResult] = None,
        verification_result: Optional[VerificationResult] = None,
        plan: Optional[ExecutionPlan] = None,
        priority_override: Optional[ReportPriority] = None,
        target_users: Optional[List[str]] = None
    ) -> GeneratedReport:
        """Generate and dispatch a report"""
        
        template = self.templates.get(report_type)
        if not template:
            raise ValueError(f"No template found for report type {report_type}")
        
        # Generate report content
        report = GeneratedReport(
            report_id=f"{report_type.value}_{int(datetime.now().timestamp())}",
            report_type=report_type,
            priority=priority_override or template.priority,
            title=template.title_template.format(**template_data),
            summary=template.summary_template.format(**template_data),
            detailed_content=template.detailed_template.format(**template_data) if template.detailed_template else None,
            source_event=source_event,
            execution_result=execution_result,
            verification_result=verification_result,
            plan=plan,
            target_channels=template.channels.copy(),
            target_users=target_users or [],
        )
        
        # Format content for each channel
        for channel in template.channels:
            if channel == ReportChannel.SLACK and template.slack_format:
                report.channel_content[channel] = template.slack_format.format(**template_data)
            elif channel == ReportChannel.JIRA and template.jira_format:
                report.channel_content[channel] = template.jira_format.format(**template_data)
            elif channel == ReportChannel.EMAIL and template.email_format:
                report.channel_content[channel] = template.email_format.format(**template_data)
            else:
                # Use detailed content or summary as fallback
                report.channel_content[channel] = report.detailed_content or report.summary
        
        # Set expiration
        if report.priority == ReportPriority.CRITICAL:
            report.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        elif report.priority == ReportPriority.HIGH:
            report.expires_at = datetime.now(timezone.utc) + timedelta(hours=6)
        else:
            report.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Queue for delivery
        await self.delivery_queue.put(report)
        
        # Track in history
        self.delivery_history[report.report_id] = report
        
        logger.info(f"Generated report {report.report_id} for {report_type.value}")
        
        # Start delivery process (don't wait)
        asyncio.create_task(self._process_delivery_queue())
        
        return report
    
    async def _process_delivery_queue(self):
        """Process the delivery queue"""
        
        try:
            while not self.delivery_queue.empty():
                try:
                    report = await asyncio.wait_for(
                        self.delivery_queue.get(),
                        timeout=1.0
                    )
                    await self._deliver_report(report)
                    self.delivery_queue.task_done()
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Failed to process delivery queue: {e}")
                    break
        except Exception as e:
            logger.error(f"Delivery queue processing error: {e}")
    
    async def _deliver_report(self, report: GeneratedReport):
        """Deliver report to all target channels"""
        
        for channel in report.target_channels:
            try:
                # Check rate limits
                if not self._check_rate_limit(channel):
                    logger.warning(f"Rate limit exceeded for channel {channel}, queuing for later")
                    continue
                
                # Attempt delivery
                success = await self._deliver_to_channel(report, channel)
                
                if success:
                    report.successful_deliveries.add(channel)
                    logger.info(f"Successfully delivered report {report.report_id} to {channel.value}")
                else:
                    await self._handle_delivery_failure(report, channel, "Delivery failed")
                    
            except Exception as e:
                logger.error(f"Failed to deliver report {report.report_id} to {channel.value}: {e}")
                await self._handle_delivery_failure(report, channel, str(e))
    
    async def _deliver_to_channel(self, report: GeneratedReport, channel: ReportChannel) -> bool:
        """Deliver report to a specific channel"""
        
        content = report.channel_content.get(channel, report.summary)
        
        try:
            if channel == ReportChannel.SLACK:
                return await self._deliver_to_slack(report, content)
            elif channel == ReportChannel.TEAMS:
                return await self._deliver_to_teams(report, content)
            elif channel == ReportChannel.JIRA:
                return await self._deliver_to_jira(report, content)
            elif channel == ReportChannel.EMAIL:
                return await self._deliver_to_email(report, content)
            elif channel == ReportChannel.WEBHOOK:
                return await self._deliver_to_webhook(report, content)
            elif channel == ReportChannel.CONSOLE:
                return await self._deliver_to_console(report, content)
            else:
                logger.warning(f"Unsupported delivery channel: {channel}")
                return False
                
        except Exception as e:
            logger.error(f"Channel delivery error for {channel.value}: {e}")
            return False
    
    async def _deliver_to_slack(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report to Slack"""
        
        if not self.slack_client:
            logger.warning("Slack client not configured")
            return False
        
        try:
            # Determine target channel based on report type and target users
            channel = self._get_slack_channel(report)
            
            result = await self.slack_client.post_message(
                channel=channel,
                text=content,
                attachments=self._create_slack_attachments(report) if report.detailed_content else None
            )
            
            return result.get("ok", False)
            
        except Exception as e:
            logger.error(f"Slack delivery failed: {e}")
            return False
    
    async def _deliver_to_teams(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report to Microsoft Teams"""
        
        # Would integrate with Teams webhook or API
        logger.info(f"Teams delivery (mock): {report.title}")
        return True
    
    async def _deliver_to_jira(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report to Jira as a comment"""
        
        if not self.db:
            logger.warning("Jira service not configured")
            return False
        
        try:
            # Find Jira issue to comment on
            issue_key = self._extract_jira_key(report)
            if not issue_key:
                logger.warning("No Jira issue found for report")
                return False
            
            await JiraService.add_comment(self.db, issue_key, content)
            return True
            
        except Exception as e:
            logger.error(f"Jira delivery failed: {e}")
            return False
    
    async def _deliver_to_email(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report via email"""
        
        # Would integrate with email service (SendGrid, SES, etc.)
        logger.info(f"Email delivery (mock): {report.title}")
        return True
    
    async def _deliver_to_webhook(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report to webhook endpoint"""
        
        # Would send HTTP POST to configured webhook
        logger.info(f"Webhook delivery (mock): {report.title}")
        return True
    
    async def _deliver_to_console(self, report: GeneratedReport, content: str) -> bool:
        """Deliver report to console/logs"""
        
        priority_emoji = {
            ReportPriority.CRITICAL: "🚨",
            ReportPriority.HIGH: "⚠️",
            ReportPriority.MEDIUM: "ℹ️",
            ReportPriority.LOW: "💬",
            ReportPriority.DEBUG: "🐛"
        }
        
        emoji = priority_emoji.get(report.priority, "📄")
        logger.info(f"{emoji} REPORT: {report.title}\n{content}")
        return True
    
    async def _handle_delivery_failure(self, report: GeneratedReport, channel: ReportChannel, error: str):
        """Handle delivery failure with retry logic"""
        
        if channel not in report.delivery_attempts:
            report.delivery_attempts[channel] = []
        
        attempt_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "attempt": len(report.delivery_attempts[channel]) + 1
        }
        
        report.delivery_attempts[channel].append(attempt_info)
        report.failed_deliveries[channel] = error
        
        # Retry logic
        if len(report.delivery_attempts[channel]) < self.max_retries:
            logger.info(f"Scheduling retry for report {report.report_id} to {channel.value}")
            
            # Schedule retry after delay
            asyncio.get_event_loop().call_later(
                self.retry_delay_seconds,
                lambda: asyncio.create_task(self._retry_delivery(report, channel))
            )
        else:
            logger.error(f"Max retries exceeded for report {report.report_id} to {channel.value}")
            
            # Escalate if critical
            if report.priority == ReportPriority.CRITICAL:
                await self._escalate_delivery_failure(report, channel)
    
    async def _retry_delivery(self, report: GeneratedReport, channel: ReportChannel):
        """Retry failed delivery"""
        
        try:
            success = await self._deliver_to_channel(report, channel)
            if success:
                report.successful_deliveries.add(channel)
                report.failed_deliveries.pop(channel, None)
                logger.info(f"Retry successful for report {report.report_id} to {channel.value}")
        except Exception as e:
            logger.error(f"Retry failed for report {report.report_id} to {channel.value}: {e}")
    
    async def _escalate_delivery_failure(self, report: GeneratedReport, channel: ReportChannel):
        """Escalate critical delivery failures"""
        
        escalation_message = f"CRITICAL: Failed to deliver report {report.report_id} to {channel.value}. Manual intervention required."
        
        # Try alternative channels
        fallback_channels = [ReportChannel.CONSOLE, ReportChannel.EMAIL]
        
        for fallback in fallback_channels:
            if fallback != channel and fallback not in report.failed_deliveries:
                try:
                    await self._deliver_to_channel(
                        GeneratedReport(
                            report_id=f"escalation_{report.report_id}",
                            report_type=ReportType.SAFETY_ALERT,
                            priority=ReportPriority.CRITICAL,
                            title="Delivery Failure Escalation",
                            summary=escalation_message,
                            target_channels=[fallback]
                        ),
                        fallback
                    )
                    break
                except Exception as e:
                    logger.error(f"Escalation delivery also failed to {fallback.value}: {e}")
    
    def _check_rate_limit(self, channel: ReportChannel) -> bool:
        """Check if channel is within rate limits"""
        
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        
        if channel not in self.rate_limit_trackers:
            self.rate_limit_trackers[channel] = []
        
        # Clean old timestamps
        self.rate_limit_trackers[channel] = [
            ts for ts in self.rate_limit_trackers[channel] 
            if ts > minute_ago
        ]
        
        # Check limit
        if len(self.rate_limit_trackers[channel]) >= self.rate_limit_per_minute:
            return False
        
        # Record this delivery
        self.rate_limit_trackers[channel].append(now)
        return True
    
    # Helper methods for content generation and formatting
    
    def _generate_context_summary(self, context: ResolvedContext) -> str:
        """Generate a human-readable context summary"""
        
        summary_parts = []
        
        if context.primary_object:
            obj_type = context.context_type.value.replace('_', ' ').title()
            summary_parts.append(f"**{obj_type}:** {context.primary_object.get('title', context.primary_object.get('key', 'Unknown'))}")
        
        if context.related_issues:
            summary_parts.append(f"**Related Issues:** {len(context.related_issues)} linked")
        
        if context.team_members:
            members = [member.get('user', 'Unknown') for member in context.team_members[:3]]
            summary_parts.append(f"**Team:** {', '.join(members)}")
        
        if context.urgency_indicators:
            summary_parts.append(f"**Urgency:** {', '.join(context.urgency_indicators[:2])}")
        
        return "\n".join(summary_parts) if summary_parts else "No additional context"
    
    def _format_execution_results(self, execution_result: ExecutionResult) -> str:
        """Format execution results for display"""
        
        if not execution_result.result_data:
            return "Action completed successfully"
        
        result_parts = []
        
        if "pr_created" in execution_result.result_data:
            if execution_result.result_data["pr_created"]:
                result_parts.append(f"✅ Pull request created: {execution_result.result_data.get('pr_url', 'N/A')}")
        
        if "files_modified" in execution_result.result_data:
            files = execution_result.result_data["files_modified"]
            if files:
                result_parts.append(f"📝 Files modified: {len(files)}")
        
        if "comment_added" in execution_result.result_data:
            if execution_result.result_data["comment_added"]:
                result_parts.append("💬 Comment added successfully")
        
        if "message_sent" in execution_result.result_data:
            if execution_result.result_data["message_sent"]:
                result_parts.append("📢 Message sent successfully")
        
        return "\n".join(result_parts) if result_parts else "Action completed"
    
    def _generate_next_steps(
        self, 
        execution_result: ExecutionResult, 
        verification_result: Optional[VerificationResult]
    ) -> str:
        """Generate suggested next steps"""
        
        next_steps = []
        
        if execution_result.action.action_type in [ActionType.IMPLEMENT_FEATURE, ActionType.FIX_BUG]:
            if execution_result.result_data and execution_result.result_data.get("pr_created"):
                next_steps.append("• Review the created pull request")
                next_steps.append("• Run additional tests if needed")
                next_steps.append("• Update issue status after merge")
        
        elif execution_result.action.action_type == ActionType.ADD_COMMENT:
            next_steps.append("• Monitor for responses")
            next_steps.append("• Follow up if no response within 24h")
        
        elif execution_result.action.action_type == ActionType.ESCALATE_ISSUE:
            next_steps.append("• Wait for escalation team response")
            next_steps.append("• Provide additional context if requested")
        
        if verification_result:
            if verification_result.verification_passed:
                next_steps.append("• All quality checks passed")
            else:
                next_steps.append("• Address verification issues before proceeding")
                next_steps.extend(f"• {rec}" for rec in verification_result.recommendations[:2])
        
        return "\n".join(next_steps) if next_steps else "• No additional steps required"
    
    def _generate_failure_recommendations(self, execution_result: ExecutionResult) -> str:
        """Generate recommendations for failed executions"""
        
        recommendations = []
        
        # Generic recommendations based on action type
        if execution_result.action.action_type in [ActionType.IMPLEMENT_FEATURE, ActionType.FIX_BUG]:
            recommendations.extend([
                "• Check workspace for uncommitted changes",
                "• Verify repository access permissions",
                "• Review error logs for specific issues",
                "• Consider manual implementation if issues persist"
            ])
        
        elif execution_result.action.action_type == ActionType.ADD_COMMENT:
            recommendations.extend([
                "• Verify Jira connection and permissions",
                "• Check if issue exists and is accessible",
                "• Retry with simplified comment text"
            ])
        
        elif execution_result.action.action_type == ActionType.NOTIFY_TEAM:
            recommendations.extend([
                "• Check Slack/Teams connectivity",
                "• Verify channel permissions",
                "• Try alternative notification method"
            ])
        
        # Error-specific recommendations
        error_msg = (execution_result.error_message or "").lower()
        
        if "permission" in error_msg or "unauthorized" in error_msg:
            recommendations.append("• Check API credentials and permissions")
        
        if "timeout" in error_msg:
            recommendations.append("• Increase timeout settings or retry during off-peak hours")
        
        if "network" in error_msg or "connection" in error_msg:
            recommendations.append("• Check network connectivity and firewall settings")
        
        return "\n".join(recommendations[:5]) if recommendations else "• Contact support for assistance"
    
    def _format_quality_summary(self, verification_result: VerificationResult) -> str:
        """Format verification quality summary"""
        
        summary_parts = []
        
        if verification_result.checks:
            by_status = {}
            for check in verification_result.checks:
                status = check.status.value
                by_status[status] = by_status.get(status, 0) + 1
            
            for status, count in by_status.items():
                summary_parts.append(f"• {status.title()}: {count}")
        
        if verification_result.corrections_applied:
            summary_parts.append(f"• Auto-corrections: {len(verification_result.corrections_applied)}")
        
        return "\n".join(summary_parts) if summary_parts else "No quality data available"
    
    def _format_actions_summary(self, actions: List[PlannedAction]) -> str:
        """Format actions summary for display"""
        
        summary_lines = []
        
        for i, action in enumerate(actions[:5], 1):  # Limit to 5 actions
            action_name = action.action_type.value.replace('_', ' ').title()
            confidence = int(action.confidence_score * 100)
            duration = action.estimated_duration
            
            summary_lines.append(f"{i}. {action_name} ({confidence}% confidence, {duration}min)")
        
        if len(actions) > 5:
            summary_lines.append(f"... and {len(actions) - 5} more actions")
        
        return "\n".join(summary_lines)
    
    def _format_action_breakdown(self, breakdown: Dict[str, int]) -> str:
        """Format action breakdown for daily summary"""
        
        if not breakdown:
            return "No actions performed"
        
        sorted_actions = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        
        lines = []
        for action_type, count in sorted_actions[:5]:
            action_name = action_type.replace('_', ' ').title()
            lines.append(f"• {action_name}: {count}")
        
        return "\n".join(lines)
    
    def _format_quality_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format quality metrics for display"""
        
        if not metrics:
            return "No quality metrics available"
        
        lines = []
        
        if "overall_score" in metrics:
            lines.append(f"• Overall Score: {int(metrics['overall_score'] * 100)}%")
        
        if "test_pass_rate" in metrics:
            lines.append(f"• Test Pass Rate: {int(metrics['test_pass_rate'] * 100)}%")
        
        if "security_issues" in metrics:
            lines.append(f"• Security Issues: {metrics['security_issues']}")
        
        if "code_coverage" in metrics:
            lines.append(f"• Code Coverage: {int(metrics['code_coverage'] * 100)}%")
        
        return "\n".join(lines) if lines else "Quality metrics not available"
    
    def _extract_target_users(self, action: Optional[PlannedAction], context: Optional[ResolvedContext]) -> List[str]:
        """Extract target users for notifications"""
        
        users = []
        if not action:
            return users
        
        # Add users from action notification recipients
        users.extend(action.notification_recipients)
        
        # Add users from context
        if context:
            for member in context.team_members:
                if member.get('user'):
                    users.append(member['user'])
            
            # Add assignee/reporter from primary object
            if context.primary_object:
                if context.primary_object.get('assignee'):
                    users.append(context.primary_object['assignee'])
                if context.primary_object.get('reporter'):
                    users.append(context.primary_object['reporter'])
        
        return list(set(users))  # Remove duplicates
    
    def _extract_plan_stakeholders(self, plan: ExecutionPlan, context: ResolvedContext) -> List[str]:
        """Extract stakeholders for plan notifications"""
        
        stakeholders = set()
        
        # Add users from all actions
        for action in plan.primary_actions:
            stakeholders.update(action.notification_recipients)
        
        # Add context stakeholders
        stakeholders.update(
            self._extract_target_users(plan.primary_actions[0] if plan.primary_actions else None, context)
        )
        
        return list(stakeholders)
    
    def _get_slack_channel(self, report: GeneratedReport) -> str:
        """Determine appropriate Slack channel for report"""
        
        # Priority-based channel selection
        if report.priority == ReportPriority.CRITICAL:
            return self.channel_mappings["oncall"]["slack_channel"]
        elif report.priority == ReportPriority.HIGH:
            return self.channel_mappings["management"]["slack_channel"]
        else:
            return self.channel_mappings["engineering"]["slack_channel"]
    
    def _create_slack_attachments(self, report: GeneratedReport) -> Optional[List[Dict[str, Any]]]:
        """Create Slack attachments for rich formatting"""
        
        if not report.detailed_content:
            return None
        
        color_map = {
            ReportPriority.CRITICAL: "danger",
            ReportPriority.HIGH: "warning",
            ReportPriority.MEDIUM: "good",
            ReportPriority.LOW: "#36a64f",
            ReportPriority.DEBUG: "#cccccc"
        }
        
        return [{
            "color": color_map.get(report.priority, "good"),
            "title": "Details",
            "text": report.detailed_content,
            "footer": f"NAVI Report {report.report_id}",
            "ts": int(report.generated_at.timestamp())
        }]
    
    def _extract_jira_key(self, report: GeneratedReport) -> Optional[str]:
        """Extract Jira issue key from report context"""
        
        # Check execution result for target
        if report.execution_result and report.execution_result.action.target:
            target = report.execution_result.action.target
            if re.match(r'^[A-Z]+-\d+$', target):
                return target
        
        # Check plan context
        if report.plan and report.plan.context.primary_object:
            primary_obj = report.plan.context.primary_object
            if primary_obj.get('key') and re.match(r'^[A-Z]+-\d+$', primary_obj['key']):
                return primary_obj['key']
        
        return None
