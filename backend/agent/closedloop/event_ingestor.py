"""
Phase 5.0 — Closed-Loop Autonomy (Event Ingestion Layer)

Centralized event ingestion system that listens continuously for external signals
from Jira, Slack, GitHub, CI/CD systems, and other platforms. Extends existing
webhook infrastructure with autonomous decision-making capabilities.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable, Set
from dataclasses import dataclass
from enum import Enum
import logging
from contextlib import asynccontextmanager

from backend.api.events.models import IngestEvent, IngestResponse
from backend.agent.planning.long_horizon_orchestrator import LongHorizonOrchestrator


logger = logging.getLogger(__name__)


class EventSource(Enum):
    """Canonical sources for closed-loop events"""

    JIRA = "jira"
    GITHUB = "github"
    SLACK = "slack"
    CI_CD = "ci_cd"
    TEAMS = "teams"
    UNKNOWN = "unknown"

    @classmethod
    def from_raw(cls, value: Optional[str]) -> "EventSource":
        if not value:
            return cls.UNKNOWN
        normalized = value.lower()
        mapping = {
            "jira": cls.JIRA,
            "github": cls.GITHUB,
            "slack": cls.SLACK,
            "ci_cd": cls.CI_CD,
            "cicd": cls.CI_CD,
            "ci": cls.CI_CD,
            "teams": cls.TEAMS,
        }
        return mapping.get(normalized, cls.UNKNOWN)


class EventType(Enum):
    """Normalized event types consumed by closed-loop orchestration"""

    ISSUE_ASSIGNED = "issue_assigned"
    ISSUE_UPDATED = "issue_updated"
    ISSUE_COMMENTED = "issue_commented"
    ISSUE_STATUS_CHANGED = "issue_status_changed"
    PR_COMMENT_ADDED = "pr_comment"
    PR_REVIEW_SUBMITTED = "pr_review"
    CI_FAILURE = "ci_failure"
    CI_SUCCESS = "ci_success"
    PUSH = "push"
    MENTION = "mention"
    DEPLOYMENT_FAILURE = "deployment_failed"
    DEPLOYMENT_SUCCESS = "deployment_succeeded"
    TEST_FAILURE = "test_failed"
    UNKNOWN = "unknown"

    @classmethod
    def from_raw(cls, value: Optional[str]) -> "EventType":
        if not value:
            return cls.UNKNOWN
        normalized = value.lower()
        direct = {member.value: member for member in cls}
        if normalized in direct:
            return direct[normalized]
        aliases = {
            "issue_transitioned": cls.ISSUE_STATUS_CHANGED,
            "pr_comment_added": cls.PR_COMMENT_ADDED,
            "pr_review_submitted": cls.PR_REVIEW_SUBMITTED,
            "pr_review_requested": cls.PR_REVIEW_SUBMITTED,
            "ci_build_failed": cls.CI_FAILURE,
            "ci_build_succeeded": cls.CI_SUCCESS,
            "deployment_failed": cls.DEPLOYMENT_FAILURE,
            "deployment_succeeded": cls.DEPLOYMENT_SUCCESS,
            "test_failed": cls.TEST_FAILURE,
        }
        return aliases.get(normalized, cls.UNKNOWN)


class EventPriority(Enum):
    """Priority levels for incoming events"""

    CRITICAL = "CRITICAL"  # Immediate attention (CI failures, security issues)
    HIGH = "HIGH"  # Important but not urgent (Jira assignments)
    NORMAL = "NORMAL"  # Standard events (PR comments, Slack mentions)
    LOW = "LOW"  # Informational (status updates, notifications)


class AutonomiTrigger(Enum):
    """Triggers that can activate autonomous behavior"""

    JIRA_ISSUE_ASSIGNED = "JIRA_ISSUE_ASSIGNED"
    JIRA_ISSUE_IN_PROGRESS = "JIRA_ISSUE_IN_PROGRESS"
    PR_REVIEW_REQUESTED = "PR_REVIEW_REQUESTED"
    PR_COMMENT_ADDED = "PR_COMMENT_ADDED"
    CI_BUILD_FAILED = "CI_BUILD_FAILED"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"
    SLACK_MENTION = "SLACK_MENTION"
    TEAMS_MENTION = "TEAMS_MENTION"
    MANUAL_REQUEST = "MANUAL_REQUEST"


@dataclass
class ProcessedEvent:
    """Event after initial processing and enrichment"""

    original_event: IngestEvent
    priority: EventPriority
    autonomy_trigger: Optional[AutonomiTrigger]
    confidence_score: float  # 0.0 to 1.0
    context_data: Dict[str, Any]
    requires_human_approval: bool
    expiry_time: Optional[datetime] = None

    @property
    def event_id(self) -> str:
        return self.original_event.external_id

    @property
    def source(self) -> EventSource:
        return EventSource.from_raw(self.original_event.source)

    @property
    def event_type(self) -> EventType:
        return EventType.from_raw(self.original_event.event_type)

    @property
    def received_at(self) -> datetime:
        return self.original_event.occurred_at or datetime.now(timezone.utc)

    @property
    def event_data(self) -> Dict[str, Any]:
        data = dict(self.original_event.tags or {})
        if self.original_event.content is not None:
            data.setdefault("content", self.original_event.content)
        if self.original_event.title is not None:
            data.setdefault("title", self.original_event.title)
        if self.original_event.summary is not None:
            data.setdefault("summary", self.original_event.summary)
        if self.original_event.url is not None:
            data.setdefault("url", self.original_event.url)
        return data

    @property
    def trigger_type(self) -> str:
        return self.original_event.event_type

    @property
    def should_be_filtered(self) -> bool:
        return False

    @property
    def event_summary(self) -> str:
        return (
            self.original_event.summary
            or self.original_event.title
            or self.original_event.content
            or ""
        )


class EventProcessor:
    """Processes raw events and determines autonomous actions"""

    def __init__(self):
        # Event type to trigger mapping
        self.trigger_map = {
            "issue_updated": self._process_jira_issue,
            "issue_assigned": self._process_jira_assignment,
            "issue_transitioned": self._process_jira_transition,
            "pr_opened": self._process_pr_event,
            "pr_comment": self._process_pr_comment,
            "pr_review_requested": self._process_pr_review,
            "ci_build_failed": self._process_ci_failure,
            "deployment_failed": self._process_deployment_failure,
            "slack_mention": self._process_slack_mention,
            "teams_mention": self._process_teams_mention,
        }

    async def process_event(self, event: IngestEvent) -> ProcessedEvent:
        """Process an incoming event and determine autonomous action"""

        logger.info(f"Processing event: {event.source}:{event.event_type}")

        # Get processor for event type
        processor = self.trigger_map.get(event.event_type, self._process_generic)

        try:
            result = await processor(event)
            logger.info(f"Event processed with trigger: {result.autonomy_trigger}")
            return result
        except Exception as e:
            logger.error(f"Failed to process event {event.external_id}: {e}")
            return ProcessedEvent(
                original_event=event,
                priority=EventPriority.LOW,
                autonomy_trigger=None,
                confidence_score=0.0,
                context_data={"error": str(e)},
                requires_human_approval=True,
            )

    async def _process_jira_issue(self, event: IngestEvent) -> ProcessedEvent:
        """Process Jira issue update event"""

        # Extract issue details from tags
        issue_status = event.tags.get("status", "").lower()
        issue_priority = event.tags.get("priority", "medium").lower()
        assignee = event.tags.get("assignee")

        # Determine autonomy trigger
        trigger = None
        confidence = 0.0

        if assignee and issue_status in ["open", "to do", "backlog"]:
            trigger = AutonomiTrigger.JIRA_ISSUE_ASSIGNED
            confidence = 0.8
        elif issue_status == "in progress":
            trigger = AutonomiTrigger.JIRA_ISSUE_IN_PROGRESS
            confidence = 0.6

        # Priority mapping
        priority_map = {
            "critical": EventPriority.CRITICAL,
            "high": EventPriority.HIGH,
            "medium": EventPriority.NORMAL,
            "low": EventPriority.LOW,
        }
        priority = priority_map.get(issue_priority, EventPriority.NORMAL)

        return ProcessedEvent(
            original_event=event,
            priority=priority,
            autonomy_trigger=trigger,
            confidence_score=confidence,
            context_data={
                "issue_key": event.external_id,
                "status": issue_status,
                "priority": issue_priority,
                "assignee": assignee,
                "project": event.tags.get("project"),
            },
            requires_human_approval=priority == EventPriority.CRITICAL,
        )

    async def _process_jira_assignment(self, event: IngestEvent) -> ProcessedEvent:
        """Process Jira issue assignment event"""

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.HIGH,
            autonomy_trigger=AutonomiTrigger.JIRA_ISSUE_ASSIGNED,
            confidence_score=0.9,
            context_data={
                "issue_key": event.external_id,
                "assignee": event.tags.get("assignee"),
                "project": event.tags.get("project"),
            },
            requires_human_approval=False,
        )

    async def _process_jira_transition(self, event: IngestEvent) -> ProcessedEvent:
        """Process Jira issue status transition"""

        new_status = event.tags.get("to_status", "").lower()

        trigger = None
        confidence = 0.0

        if new_status == "in progress":
            trigger = AutonomiTrigger.JIRA_ISSUE_IN_PROGRESS
            confidence = 0.7

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.NORMAL,
            autonomy_trigger=trigger,
            confidence_score=confidence,
            context_data={
                "issue_key": event.external_id,
                "from_status": event.tags.get("from_status"),
                "to_status": new_status,
            },
            requires_human_approval=False,
        )

    async def _process_pr_event(self, event: IngestEvent) -> ProcessedEvent:
        """Process GitHub PR event"""

        action = event.tags.get("action", "").lower()

        trigger = None
        confidence = 0.0

        if action == "review_requested":
            trigger = AutonomiTrigger.PR_REVIEW_REQUESTED
            confidence = 0.5  # Lower confidence for PR reviews

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.NORMAL,
            autonomy_trigger=trigger,
            confidence_score=confidence,
            context_data={
                "pr_number": event.external_id,
                "action": action,
                "repository": event.tags.get("repository"),
                "author": event.tags.get("author"),
            },
            requires_human_approval=True,  # PR operations need approval
        )

    async def _process_pr_comment(self, event: IngestEvent) -> ProcessedEvent:
        """Process PR comment event"""

        comment_text = event.content or ""

        # Look for keywords that suggest changes are needed
        change_keywords = ["fix", "change", "update", "modify", "address", "resolve"]
        needs_changes = any(
            keyword in comment_text.lower() for keyword in change_keywords
        )

        confidence = 0.7 if needs_changes else 0.3

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.NORMAL,
            autonomy_trigger=AutonomiTrigger.PR_COMMENT_ADDED,
            confidence_score=confidence,
            context_data={
                "pr_number": event.external_id,
                "comment_author": event.tags.get("author"),
                "needs_changes": needs_changes,
                "repository": event.tags.get("repository"),
            },
            requires_human_approval=True,
        )

    async def _process_pr_review(self, event: IngestEvent) -> ProcessedEvent:
        """Process PR review request"""

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.NORMAL,
            autonomy_trigger=AutonomiTrigger.PR_REVIEW_REQUESTED,
            confidence_score=0.4,  # Low confidence for automated reviews
            context_data={
                "pr_number": event.external_id,
                "reviewer": event.tags.get("reviewer"),
                "repository": event.tags.get("repository"),
            },
            requires_human_approval=True,
        )

    async def _process_ci_failure(self, event: IngestEvent) -> ProcessedEvent:
        """Process CI build failure"""

        failure_type = event.tags.get("failure_type", "unknown")
        is_flaky = event.tags.get("is_flaky_test", False)

        # Higher confidence for non-flaky test failures
        confidence = 0.8 if not is_flaky else 0.4

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.HIGH,
            autonomy_trigger=AutonomiTrigger.CI_BUILD_FAILED,
            confidence_score=confidence,
            context_data={
                "build_id": event.external_id,
                "failure_type": failure_type,
                "is_flaky": is_flaky,
                "repository": event.tags.get("repository"),
                "branch": event.tags.get("branch"),
            },
            requires_human_approval=failure_type == "security",
        )

    async def _process_deployment_failure(self, event: IngestEvent) -> ProcessedEvent:
        """Process deployment failure"""

        environment = event.tags.get("environment", "unknown")
        error_type = event.tags.get("error_type", "unknown")

        # Production failures are critical
        priority = (
            EventPriority.CRITICAL
            if environment == "production"
            else EventPriority.HIGH
        )

        return ProcessedEvent(
            original_event=event,
            priority=priority,
            autonomy_trigger=AutonomiTrigger.DEPLOYMENT_FAILED,
            confidence_score=0.9,
            context_data={
                "deployment_id": event.external_id,
                "environment": environment,
                "error_type": error_type,
                "service": event.tags.get("service"),
            },
            requires_human_approval=environment == "production",
        )

    async def _process_slack_mention(self, event: IngestEvent) -> ProcessedEvent:
        """Process Slack mention"""

        message_text = event.content or ""
        channel = event.tags.get("channel", "")

        # Look for urgent keywords
        urgent_keywords = ["urgent", "asap", "emergency", "critical", "broken", "down"]
        is_urgent = any(keyword in message_text.lower() for keyword in urgent_keywords)

        # Engineering channels get higher priority
        is_eng_channel = any(
            eng in channel.lower()
            for eng in ["eng", "dev", "tech", "backend", "frontend"]
        )

        priority = (
            EventPriority.HIGH
            if is_urgent
            else (EventPriority.NORMAL if is_eng_channel else EventPriority.LOW)
        )
        confidence = 0.6 if is_eng_channel else 0.3

        return ProcessedEvent(
            original_event=event,
            priority=priority,
            autonomy_trigger=AutonomiTrigger.SLACK_MENTION,
            confidence_score=confidence,
            context_data={
                "channel": channel,
                "author": event.tags.get("user"),
                "is_urgent": is_urgent,
                "is_eng_channel": is_eng_channel,
            },
            requires_human_approval=not is_eng_channel or is_urgent,
        )

    async def _process_teams_mention(self, event: IngestEvent) -> ProcessedEvent:
        """Process Teams mention"""

        # Similar to Slack processing
        message_text = event.content or ""

        urgent_keywords = ["urgent", "asap", "emergency", "critical"]
        is_urgent = any(keyword in message_text.lower() for keyword in urgent_keywords)

        priority = EventPriority.HIGH if is_urgent else EventPriority.NORMAL

        return ProcessedEvent(
            original_event=event,
            priority=priority,
            autonomy_trigger=AutonomiTrigger.TEAMS_MENTION,
            confidence_score=0.5,
            context_data={
                "team": event.tags.get("team"),
                "author": event.tags.get("user"),
                "is_urgent": is_urgent,
            },
            requires_human_approval=is_urgent,
        )

    async def _process_generic(self, event: IngestEvent) -> ProcessedEvent:
        """Process generic/unknown event types"""

        return ProcessedEvent(
            original_event=event,
            priority=EventPriority.LOW,
            autonomy_trigger=None,
            confidence_score=0.0,
            context_data={"processed": False, "reason": "unknown_event_type"},
            requires_human_approval=True,
        )


class EventIngestor:
    """
    Phase 5.0 Event Ingestion Layer

    Continuously listens for external signals and determines autonomous actions.
    Integrates with existing webhook infrastructure and extends it with
    closed-loop decision making.
    """

    def __init__(
        self,
        db_session=None,
        workspace_path: Optional[str] = None,
        orchestrator: Optional[LongHorizonOrchestrator] = None,
        max_concurrent_events: int = 10,
    ):
        self.orchestrator = orchestrator
        self.db = db_session
        self.workspace_path = workspace_path
        self.processor = EventProcessor()

        # Event management
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processing_semaphore = asyncio.Semaphore(max_concurrent_events)
        self.active_processing: Set[str] = set()

        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = {
            "event_received": [],
            "event_processed": [],
            "autonomous_action_triggered": [],
            "human_approval_required": [],
        }

        # Processing state
        self.is_running = False
        self.stats = {
            "total_events": 0,
            "processed_events": 0,
            "autonomous_actions": 0,
            "approval_requests": 0,
        }

    async def process_event(
        self,
        source: Union[EventSource, str],
        event_type: Union[EventType, str],
        event_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ProcessedEvent]:
        """Normalize a raw external event into a ProcessedEvent."""
        source_value = source.value if isinstance(source, EventSource) else str(source)
        event_type_value = (
            event_type.value if isinstance(event_type, EventType) else str(event_type)
        )

        tags = dict(event_data or {})
        if metadata:
            tags["metadata"] = metadata

        external_id = tags.get("external_id")
        if not external_id:
            for key in ("issue", "pr", "build", "deployment", "message"):
                payload = tags.get(key)
                if isinstance(payload, dict):
                    for candidate in ("key", "id", "number", "ts"):
                        if payload.get(candidate):
                            external_id = str(payload[candidate])
                            break
                if external_id:
                    break
        if not external_id:
            external_id = f"{source_value}_{int(datetime.now().timestamp())}"

        event = IngestEvent(
            source=source_value,
            event_type=event_type_value,
            external_id=external_id,
            title=tags.get("title"),
            summary=tags.get("summary"),
            content=tags.get("content"),
            url=tags.get("url"),
            user_id=(metadata or {}).get("user_id", "system"),
            org_id=(metadata or {}).get("org_id"),
            occurred_at=datetime.now(timezone.utc),
            tags=tags,
        )

        return await self.processor.process_event(event)

    def register_event_callback(self, event_type: str, callback: Callable) -> None:
        """Register callback for event processing events"""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)

    async def ingest_event(
        self, event: Union[IngestEvent, Dict[str, Any]]
    ) -> IngestResponse:
        """
        Main entry point for event ingestion

        This is called by existing webhook endpoints and new event sources
        """

        # Normalize to IngestEvent
        if isinstance(event, dict):
            event = IngestEvent(**event)

        logger.info(
            f"Ingesting event: {event.source}:{event.event_type} ({event.external_id})"
        )

        # Fire event received callback
        await self._fire_event_callback("event_received", {"event": event})

        # Add to processing queue
        await self.event_queue.put(event)

        # Update stats
        self.stats["total_events"] += 1

        return IngestResponse(
            status="queued", message=f"Event {event.external_id} queued for processing"
        )

    async def start_processing(self) -> None:
        """Start the event processing loop"""

        self.is_running = True
        logger.info("Event ingestion processing started")

        # Start multiple worker tasks for concurrent processing
        workers = [
            asyncio.create_task(self._event_processing_worker(i))
            for i in range(3)  # 3 concurrent workers
        ]

        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            logger.info("Event processing cancelled")
        finally:
            self.is_running = False

    async def stop_processing(self) -> None:
        """Stop the event processing loop"""
        self.is_running = False
        logger.info("Event processing stopped")

    async def _event_processing_worker(self, worker_id: int) -> None:
        """Worker task for processing events from the queue"""

        logger.info(f"Event worker {worker_id} started")

        while self.is_running:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # Process with semaphore to limit concurrency
                async with self.processing_semaphore:
                    await self._process_single_event(event)

            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                logger.error(f"Event worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    async def _process_single_event(self, event: IngestEvent) -> None:
        """Process a single event through the complete pipeline"""

        event_id = f"{event.source}:{event.external_id}"

        # Prevent duplicate processing
        if event_id in self.active_processing:
            logger.debug(f"Event {event_id} already being processed")
            return

        self.active_processing.add(event_id)

        try:
            logger.info(f"Processing event: {event_id}")

            # Step 1: Process event and determine autonomous action
            processed_event = await self.processor.process_event(event)

            # Step 2: Fire processed callback
            await self._fire_event_callback(
                "event_processed",
                {
                    "event": event,
                    "processed": processed_event,
                },
            )

            # Step 3: Handle autonomous action if triggered
            if processed_event.autonomy_trigger:
                await self._handle_autonomous_action(processed_event)

            # Update stats
            self.stats["processed_events"] += 1

            logger.info(f"Successfully processed event: {event_id}")

        except Exception as e:
            logger.error(f"Failed to process event {event_id}: {e}")

        finally:
            self.active_processing.discard(event_id)

    async def _handle_autonomous_action(self, processed_event: ProcessedEvent) -> None:
        """Handle an event that triggers autonomous action"""

        event = processed_event.original_event
        trigger = processed_event.autonomy_trigger
        trigger_value = trigger.value if trigger else "unknown"

        logger.info(
            f"Handling autonomous action: {trigger_value} for {event.external_id}"
        )

        # Check if human approval is required
        if processed_event.requires_human_approval:
            await self._request_human_approval(processed_event)
            self.stats["approval_requests"] += 1
            return

        # Check confidence threshold
        if processed_event.confidence_score < 0.5:
            logger.info(
                f"Confidence too low ({processed_event.confidence_score}) for autonomous action"
            )
            await self._request_human_approval(processed_event)
            self.stats["approval_requests"] += 1
            return

        # Execute autonomous action
        await self._execute_autonomous_action(processed_event)
        self.stats["autonomous_actions"] += 1

    async def _execute_autonomous_action(self, processed_event: ProcessedEvent) -> None:
        """Execute the determined autonomous action"""

        event = processed_event.original_event
        trigger = processed_event.autonomy_trigger
        context = processed_event.context_data
        trigger_value = trigger.value if trigger else "unknown"

        try:
            if trigger == AutonomiTrigger.JIRA_ISSUE_ASSIGNED:
                await self._handle_jira_assignment(event, context)

            elif trigger == AutonomiTrigger.JIRA_ISSUE_IN_PROGRESS:
                await self._handle_jira_in_progress(event, context)

            elif trigger == AutonomiTrigger.PR_COMMENT_ADDED:
                await self._handle_pr_comment(event, context)

            elif trigger == AutonomiTrigger.CI_BUILD_FAILED:
                await self._handle_ci_failure(event, context)

            elif trigger == AutonomiTrigger.DEPLOYMENT_FAILED:
                await self._handle_deployment_failure(event, context)

            elif trigger == AutonomiTrigger.SLACK_MENTION:
                await self._handle_slack_mention(event, context)

            else:
                logger.warning(f"Unhandled autonomous trigger: {trigger_value}")

            # Fire autonomous action callback
            await self._fire_event_callback(
                "autonomous_action_triggered",
                {
                    "event": event,
                    "trigger": trigger_value,
                    "context": context,
                },
            )

        except Exception as e:
            logger.error(f"Failed to execute autonomous action {trigger_value}: {e}")
            # Fall back to human approval
            await self._request_human_approval(processed_event)

    async def _handle_jira_assignment(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle Jira issue assignment autonomously"""

        issue_key = context["issue_key"]
        assignee = context["assignee"]

        logger.info(
            f"Starting autonomous work on Jira issue {issue_key} for {assignee}"
        )

        if not self.orchestrator:
            logger.warning(
                "No orchestrator configured; skipping autonomous Jira assignment handling."
            )
            return

        # Create initiative from Jira issue
        initiative_id = await self.orchestrator.start_initiative(
            goal=f"Complete Jira issue {issue_key}: {event.title or 'Untitled'}",
            context={
                "source": "jira_autonomous",
                "issue_key": issue_key,
                "assignee": assignee,
                "project": context.get("project"),
                "priority": context.get("priority"),
                "workspace": "default",  # Or determine from context
            },
            org_id=event.org_id or "default",
            owner=assignee or "autonomous",
            jira_key=issue_key,
        )

        logger.info(
            f"Created autonomous initiative {initiative_id} for Jira {issue_key}"
        )

    async def _handle_jira_in_progress(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle Jira issue transition to in progress"""

        issue_key = context["issue_key"]

        # Check if there's an existing initiative for this issue
        # This would require extending the orchestrator to search by Jira key
        logger.info(
            f"Jira issue {issue_key} moved to in progress - monitoring for autonomous actions"
        )

    async def _handle_pr_comment(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle PR comment that requires changes"""

        if not context.get("needs_changes"):
            return

        pr_number = context["pr_number"]
        repository = context["repository"]

        logger.info(
            f"PR #{pr_number} in {repository} has review comments requiring changes"
        )

        # This would integrate with PR analysis and automated fix generation
        # For now, just log the action

    async def _handle_ci_failure(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle CI build failure autonomously"""

        build_id = context["build_id"]
        repository = context["repository"]
        failure_type = context["failure_type"]

        logger.info(f"CI build {build_id} failed in {repository}: {failure_type}")

        # This would integrate with build failure analysis and automated fixes
        # For now, just log the action

    async def _handle_deployment_failure(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle deployment failure autonomously"""

        deployment_id = context["deployment_id"]
        environment = context["environment"]

        logger.info(f"Deployment {deployment_id} failed in {environment}")

        # This would integrate with rollback and recovery procedures
        # For now, just log the action

    async def _handle_slack_mention(
        self, event: IngestEvent, context: Dict[str, Any]
    ) -> None:
        """Handle Slack mention autonomously"""

        channel = context["channel"]
        author = context["author"]

        logger.info(f"Handling Slack mention in {channel} from {author}")

        # This would integrate with natural language understanding and response
        # For now, just log the action

    async def _request_human_approval(self, processed_event: ProcessedEvent) -> None:
        """Request human approval for an action"""

        event = processed_event.original_event
        trigger = processed_event.autonomy_trigger

        logger.info(
            f"Requesting human approval for {trigger.value if trigger else 'unknown'} on {event.external_id}"
        )

        # Fire human approval callback
        await self._fire_event_callback(
            "human_approval_required",
            {
                "event": event,
                "processed": processed_event,
                "reason": (
                    "requires_approval"
                    if processed_event.requires_human_approval
                    else "low_confidence"
                ),
            },
        )

    async def _fire_event_callback(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """Fire event callback to registered handlers"""

        callbacks = self.event_callbacks.get(event_type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)
            except Exception as e:
                logger.error(f"Event callback failed for {event_type}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            "queue_size": self.event_queue.qsize(),
            "active_processing": len(self.active_processing),
            "is_running": self.is_running,
        }

    @asynccontextmanager
    async def processing_context(self):
        """Context manager for event processing lifecycle"""
        processing_task: Optional[asyncio.Task] = None
        try:
            processing_task = asyncio.create_task(self.start_processing())
            yield self
        finally:
            await self.stop_processing()
            if processing_task:
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
