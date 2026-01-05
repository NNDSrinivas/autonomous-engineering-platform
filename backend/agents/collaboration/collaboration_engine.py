"""
Multi-Agent Collaboration Framework - Part 14

This framework enables multiple specialized agents to communicate, coordinate, escalate,
delegate, and merge their reasoning in a virtual engineering team setup. This creates
a collaborative autonomous engineering organization that can work on complex projects
with multiple agents specializing in different areas.

Agents communicate through:
- Shared context and memory
- Message passing and event system
- Collaborative reasoning threads
- Task delegation and coordination
- Escalation and conflict resolution
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import uuid

from backend.core.memory.episodic_memory import EpisodicMemory
from backend.services.llm_router import LLMRouter


class MessageType(Enum):
    QUESTION = "question"
    ANSWER = "answer"
    TASK_REQUEST = "task_request"
    TASK_COMPLETION = "task_completion"
    ESCALATION = "escalation"
    COLLABORATION_REQUEST = "collaboration_request"
    STATUS_UPDATE = "status_update"
    KNOWLEDGE_SHARE = "knowledge_share"
    CONFLICT_RESOLUTION = "conflict_resolution"


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentMessage:
    id: str
    sender_id: str
    recipient_id: Optional[str]  # None for broadcast messages
    message_type: MessageType
    subject: str
    content: Dict[str, Any]
    priority: Priority
    timestamp: datetime
    thread_id: str
    parent_message_id: Optional[str] = None
    requires_response: bool = False
    deadline: Optional[datetime] = None


@dataclass
class CollaborationContext:
    session_id: str
    project_goal: str
    current_phase: str
    shared_memory: Dict[str, Any]
    active_agents: List[str]
    message_history: List[AgentMessage]
    decisions_made: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    created_at: datetime


@dataclass
class TaskDelegation:
    task_id: str
    delegator_id: str
    assignee_id: str
    task_description: str
    requirements: List[str]
    deadline: datetime
    priority: Priority
    dependencies: List[str]
    expected_deliverables: List[str]
    status: str = "assigned"


class AgentRole(Enum):
    PRODUCT_MANAGER = "product_manager"
    TECH_LEAD = "tech_lead"
    CODE_GENERATOR = "code_generator"
    SECURITY_SPECIALIST = "security_specialist"
    PERFORMANCE_ENGINEER = "performance_engineer"
    QA_ENGINEER = "qa_engineer"
    SELF_HEALING_AGENT = "self_healing_agent"
    RCA_ANALYST = "rca_analyst"
    ARCHITECTURE_ANALYST = "architecture_analyst"
    OBSERVABILITY_ENGINEER = "observability_engineer"


class BaseCollaborativeAgent(ABC):
    """Base class for all collaborative agents in the multi-agent system."""

    def __init__(
        self, agent_id: str, role: AgentRole, specializations: List[str] = None
    ):
        self.agent_id = agent_id
        self.role = role
        self.specializations = specializations or []
        self.collaboration_engine = None  # Will be set by the engine
        self.llm_router = LLMRouter()
        self.knowledge_base = {}
        self.active_tasks = {}

    @abstractmethod
    async def process_message(
        self, message: AgentMessage, context: CollaborationContext
    ) -> Optional[AgentMessage]:
        """Process an incoming message and optionally return a response."""
        pass

    @abstractmethod
    async def contribute_to_discussion(
        self, topic: str, context: CollaborationContext
    ) -> Dict[str, Any]:
        """Contribute domain expertise to a collaborative discussion."""
        pass

    @abstractmethod
    async def execute_task(
        self, task: TaskDelegation, context: CollaborationContext
    ) -> Dict[str, Any]:
        """Execute a delegated task."""
        pass

    async def send_message(
        self,
        recipient_id: Optional[str],
        message_type: MessageType,
        subject: str,
        content: Dict[str, Any],
        priority: Priority = Priority.MEDIUM,
        requires_response: bool = False,
        deadline: Optional[datetime] = None,
    ) -> str:
        """Send a message to another agent or broadcast."""

        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            message_type=message_type,
            subject=subject,
            content=content,
            priority=priority,
            timestamp=datetime.now(),
            thread_id=f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            requires_response=requires_response,
            deadline=deadline,
        )

        if self.collaboration_engine:
            await self.collaboration_engine.route_message(message)

        return message.id

    async def ask_for_help(
        self,
        question: str,
        required_expertise: List[str],
        priority: Priority = Priority.MEDIUM,
    ) -> List[AgentMessage]:
        """Ask other agents for help with specific expertise."""

        content = {
            "question": question,
            "required_expertise": required_expertise,
            "context": self.get_current_context(),
        }

        await self.send_message(
            recipient_id=None,  # Broadcast
            message_type=MessageType.QUESTION,
            subject=f"Help needed: {question[:50]}...",
            content=content,
            priority=priority,
            requires_response=True,
        )

        # Wait for responses (in real implementation, this would be event-driven)
        await asyncio.sleep(1)  # Simulate response time
        return []  # Responses would be handled by the collaboration engine

    async def delegate_task(
        self,
        task_description: str,
        requirements: List[str],
        preferred_agent_type: Optional[AgentRole] = None,
        deadline: Optional[datetime] = None,
        priority: Priority = Priority.MEDIUM,
    ) -> str:
        """Delegate a task to another agent."""

        task = TaskDelegation(
            task_id=str(uuid.uuid4()),
            delegator_id=self.agent_id,
            assignee_id="",  # Will be assigned by collaboration engine
            task_description=task_description,
            requirements=requirements,
            deadline=deadline or datetime.now().replace(hour=23, minute=59),
            priority=priority,
            dependencies=[],
            expected_deliverables=requirements,
        )

        content = {
            "task": asdict(task),
            "preferred_agent_type": (
                preferred_agent_type.value if preferred_agent_type else None
            ),
        }

        await self.send_message(
            recipient_id=None,
            message_type=MessageType.TASK_REQUEST,
            subject=f"Task delegation: {task_description[:50]}...",
            content=content,
            priority=priority,
            requires_response=True,
        )

        return task.task_id

    async def escalate_issue(
        self,
        issue_description: str,
        attempted_solutions: List[str],
        required_authority: List[str],
    ) -> str:
        """Escalate an issue that requires higher authority or different expertise."""

        content = {
            "issue": issue_description,
            "attempted_solutions": attempted_solutions,
            "required_authority": required_authority,
            "escalation_reason": "Agent capabilities exceeded",
            "context": self.get_current_context(),
        }

        return await self.send_message(
            recipient_id=None,  # Broadcast to find appropriate authority
            message_type=MessageType.ESCALATION,
            subject=f"Escalation: {issue_description[:50]}...",
            content=content,
            priority=Priority.HIGH,
            requires_response=True,
        )

    def get_current_context(self) -> Dict[str, Any]:
        """Get current agent context for sharing with other agents."""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "specializations": self.specializations,
            "active_tasks_count": len(self.active_tasks),
            "knowledge_areas": list(self.knowledge_base.keys()),
        }

    def update_knowledge(self, topic: str, information: Dict[str, Any]):
        """Update agent's knowledge base with new information."""
        self.knowledge_base[topic] = {
            "information": information,
            "updated_at": datetime.now(),
            "source": "collaboration",
        }


class CollaborationEngine:
    """
    Central coordination engine for multi-agent collaboration.

    Manages message routing, task assignment, conflict resolution, and collaborative reasoning.
    """

    def __init__(self):
        self.agents: Dict[str, BaseCollaborativeAgent] = {}
        self.contexts: Dict[str, CollaborationContext] = {}
        self.episodic_memory = EpisodicMemory()
        self.llm_router = LLMRouter()
        self.message_queue = asyncio.Queue()
        self.running = False

    def register_agent(self, agent: BaseCollaborativeAgent):
        """Register an agent with the collaboration engine."""
        self.agents[agent.agent_id] = agent
        agent.collaboration_engine = self

    async def start_collaboration_session(
        self, project_goal: str, participating_agents: List[str]
    ) -> str:
        """Start a new collaboration session."""

        session_id = f"collab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        context = CollaborationContext(
            session_id=session_id,
            project_goal=project_goal,
            current_phase="initiation",
            shared_memory={},
            active_agents=participating_agents,
            message_history=[],
            decisions_made=[],
            conflicts=[],
            created_at=datetime.now(),
        )

        self.contexts[session_id] = context

        # Start message processing if not already running
        if not self.running:
            asyncio.create_task(self._process_messages())
            self.running = True

        # Notify all agents about the new session
        await self._notify_session_start(session_id, context)

        return session_id

    async def route_message(self, message: AgentMessage):
        """Route a message to appropriate recipients."""
        await self.message_queue.put(message)

    async def _process_messages(self):
        """Main message processing loop."""

        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)

                # Find the collaboration context
                context = self._find_context_for_message(message)
                if not context:
                    continue

                # Add to message history
                context.message_history.append(message)

                # Route message
                if message.recipient_id:
                    # Direct message
                    await self._deliver_direct_message(message, context)
                else:
                    # Broadcast message
                    await self._deliver_broadcast_message(message, context)

                # Update episodic memory
                await self.episodic_memory.record_event(
                    session_id=context.session_id,
                    event_type="agent_message",
                    content={
                        "message_type": message.message_type.value,
                        "sender": message.sender_id,
                        "recipient": message.recipient_id,
                        "subject": message.subject,
                    },
                )

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing message: {e}")

    async def _deliver_direct_message(
        self, message: AgentMessage, context: CollaborationContext
    ):
        """Deliver a message to a specific agent."""

        recipient = self.agents.get(message.recipient_id)
        if recipient:
            try:
                response = await recipient.process_message(message, context)
                if response:
                    await self.route_message(response)
            except Exception as e:
                print(f"Error delivering message to {message.recipient_id}: {e}")

    async def _deliver_broadcast_message(
        self, message: AgentMessage, context: CollaborationContext
    ):
        """Deliver a broadcast message to all relevant agents."""

        tasks = []
        for agent_id in context.active_agents:
            if agent_id != message.sender_id:  # Don't send to sender
                agent = self.agents.get(agent_id)
                if agent:
                    tasks.append(self._safe_message_delivery(agent, message, context))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_message_delivery(
        self,
        agent: BaseCollaborativeAgent,
        message: AgentMessage,
        context: CollaborationContext,
    ):
        """Safely deliver a message to an agent with error handling."""
        try:
            response = await agent.process_message(message, context)
            if response:
                await self.route_message(response)
        except Exception as e:
            print(f"Error delivering message to {agent.agent_id}: {e}")

    async def orchestrate_discussion(
        self,
        topic: str,
        context: CollaborationContext,
        required_expertise: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """Orchestrate a collaborative discussion on a specific topic."""

        # Find relevant agents
        relevant_agents = self._find_relevant_agents(
            required_expertise or [], context.active_agents
        )

        # Collect contributions
        contributions = []
        tasks = []

        for agent_id in relevant_agents:
            agent = self.agents.get(agent_id)
            if agent:
                tasks.append(agent.contribute_to_discussion(topic, context))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if not isinstance(result, Exception):
                    contributions.append(
                        {
                            "agent_id": relevant_agents[i],
                            "role": self.agents[relevant_agents[i]].role.value,
                            "contribution": result,
                        }
                    )

        # Synthesize contributions using LLM
        synthesis = await self._synthesize_discussion(topic, contributions, context)

        # Record decision if one was made
        if synthesis.get("decision"):
            context.decisions_made.append(
                {
                    "topic": topic,
                    "decision": synthesis["decision"],
                    "rationale": synthesis.get("rationale", ""),
                    "contributors": [c["agent_id"] for c in contributions],
                    "timestamp": datetime.now(),
                }
            )

        return contributions

    async def assign_task(
        self, task: TaskDelegation, context: CollaborationContext
    ) -> bool:
        """Assign a task to the most suitable agent."""

        # Find suitable agents
        suitable_agents = self._find_suitable_agents_for_task(
            task, context.active_agents
        )

        if not suitable_agents:
            return False

        # For now, assign to the first suitable agent
        # In production, use more sophisticated assignment logic
        assignee_id = suitable_agents[0]
        task.assignee_id = assignee_id

        assignee = self.agents.get(assignee_id)
        if assignee:
            assignee.active_tasks[task.task_id] = task

            # Send task assignment message
            content = {"task": asdict(task)}

            assignment_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="collaboration_engine",
                recipient_id=assignee_id,
                message_type=MessageType.TASK_REQUEST,
                subject=f"Task Assignment: {task.task_description[:50]}...",
                content=content,
                priority=task.priority,
                timestamp=datetime.now(),
                thread_id=f"task_{task.task_id}",
            )

            await self.route_message(assignment_message)
            return True

        return False

    async def resolve_conflict(
        self,
        conflict_description: str,
        involved_agents: List[str],
        context: CollaborationContext,
    ) -> Dict[str, Any]:
        """Resolve conflicts between agents using structured reasoning."""

        prompt = f"""
        You are Navi-Mediator, an expert in conflict resolution and team coordination.
        
        A conflict has arisen in our autonomous engineering team:
        
        CONFLICT: {conflict_description}
        
        INVOLVED AGENTS: {', '.join(involved_agents)}
        
        PROJECT CONTEXT: {context.project_goal}
        
        Analyze this conflict and provide:
        1. Root cause analysis
        2. Each agent's perspective
        3. Recommended resolution
        4. Action steps for each agent
        5. Prevention strategies
        
        Provide a structured resolution that maintains team productivity
        and ensures project success.
        """

        resolution = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        resolution_record = {
            "conflict_id": str(uuid.uuid4()),
            "description": conflict_description,
            "involved_agents": involved_agents,
            "resolution": resolution.text,
            "timestamp": datetime.now(),
            "status": "resolved",
        }

        context.conflicts.append(resolution_record)

        return resolution_record

    def _find_context_for_message(
        self, message: AgentMessage
    ) -> Optional[CollaborationContext]:
        """Find the appropriate collaboration context for a message."""

        # For now, return the most recent active context
        # In production, use message.thread_id or other routing logic
        if self.contexts:
            return list(self.contexts.values())[-1]

        return None

    def _find_relevant_agents(
        self, required_expertise: List[str], active_agents: List[str]
    ) -> List[str]:
        """Find agents with relevant expertise for a discussion."""

        if not required_expertise:
            return active_agents

        relevant = []
        for agent_id in active_agents:
            agent = self.agents.get(agent_id)
            if agent:
                # Check if agent has any of the required expertise
                agent_expertise = agent.specializations + [agent.role.value]
                if any(exp in agent_expertise for exp in required_expertise):
                    relevant.append(agent_id)

        return relevant or active_agents  # Fallback to all agents

    def _find_suitable_agents_for_task(
        self, task: TaskDelegation, active_agents: List[str]
    ) -> List[str]:
        """Find agents suitable for executing a specific task."""

        suitable = []

        for agent_id in active_agents:
            agent = self.agents.get(agent_id)
            if agent:
                # Check if agent is not overloaded
                if len(agent.active_tasks) < 3:  # Max 3 concurrent tasks
                    suitable.append(agent_id)

        return suitable

    async def _synthesize_discussion(
        self,
        topic: str,
        contributions: List[Dict[str, Any]],
        context: CollaborationContext,
    ) -> Dict[str, Any]:
        """Synthesize multiple agent contributions into coherent decisions."""

        contributions_text = "\n\n".join(
            [
                f"**{c['role'].upper()}**: {json.dumps(c['contribution'], indent=2)}"
                for c in contributions
            ]
        )

        prompt = f"""
        You are Navi-Synthesizer, expert at combining multiple expert perspectives
        into coherent decisions and action plans.
        
        DISCUSSION TOPIC: {topic}
        
        PROJECT GOAL: {context.project_goal}
        
        AGENT CONTRIBUTIONS:
        {contributions_text}
        
        Synthesize these contributions into:
        1. Key insights from each perspective
        2. Areas of agreement and disagreement
        3. Recommended decision or approach
        4. Rationale for the recommendation
        5. Next action steps
        
        Provide a clear synthesis that leverages all expertise while
        maintaining focus on the project goal.
        """

        synthesis = await self.llm_router.run(prompt=prompt, use_smart_auto=True)

        return {
            "synthesis": synthesis.get("response", synthesis),
            "decision": self._extract_decision(synthesis.get("response", synthesis)),
            "rationale": self._extract_rationale(synthesis.get("response", synthesis)),
            "next_steps": self._extract_next_steps(
                synthesis.get("response", synthesis)
            ),
        }

    async def _notify_session_start(
        self, session_id: str, context: CollaborationContext
    ):
        """Notify all agents about a new collaboration session."""

        notification_message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="collaboration_engine",
            recipient_id=None,  # Broadcast
            message_type=MessageType.STATUS_UPDATE,
            subject=f"New collaboration session: {context.project_goal[:50]}...",
            content={
                "session_id": session_id,
                "project_goal": context.project_goal,
                "phase": context.current_phase,
                "participating_agents": context.active_agents,
            },
            priority=Priority.MEDIUM,
            timestamp=datetime.now(),
            thread_id=f"session_{session_id}",
        )

        await self.route_message(notification_message)

    def _extract_decision(self, synthesis_text: str) -> Optional[str]:
        """Extract decision from synthesis text."""
        lines = synthesis_text.split("\n")
        for line in lines:
            if "decision" in line.lower() or "recommend" in line.lower():
                return line.strip()
        return None

    def _extract_rationale(self, synthesis_text: str) -> Optional[str]:
        """Extract rationale from synthesis text."""
        lines = synthesis_text.split("\n")
        for line in lines:
            if "rationale" in line.lower() or "because" in line.lower():
                return line.strip()
        return None

    def _extract_next_steps(self, synthesis_text: str) -> List[str]:
        """Extract next steps from synthesis text."""
        lines = synthesis_text.split("\n")
        steps = []
        in_steps_section = False

        for line in lines:
            if "next steps" in line.lower() or "action steps" in line.lower():
                in_steps_section = True
                continue
            elif in_steps_section and line.strip():
                if line.strip().startswith("-") or line.strip().startswith("•"):
                    steps.append(line.strip().lstrip("- •"))

        return steps


class MultiAgentOrchestrator:
    """
    High-level orchestrator that manages multi-agent collaborations for complex projects.

    This orchestrator can coordinate entire engineering projects using multiple
    specialized agents working together.
    """

    def __init__(self):
        self.collaboration_engine = CollaborationEngine()
        self.active_sessions: Dict[str, str] = {}  # project_id -> session_id

    async def start_engineering_project(
        self, project_description: str, required_agents: List[AgentRole] = None
    ) -> str:
        """Start a complete engineering project with multi-agent collaboration."""

        # Default agent team for engineering projects
        if not required_agents:
            required_agents = [
                AgentRole.PRODUCT_MANAGER,
                AgentRole.TECH_LEAD,
                AgentRole.CODE_GENERATOR,
                AgentRole.SECURITY_SPECIALIST,
                AgentRole.QA_ENGINEER,
            ]

        # Create agent instances (in production, these would be persistent)
        agent_ids = []
        for role in required_agents:
            agent_id = f"{role.value}_{datetime.now().strftime('%H%M%S')}"
            agent_ids.append(agent_id)

            # Register mock agents (real implementation would instantiate actual agents)
            mock_agent = self._create_mock_agent(agent_id, role)
            self.collaboration_engine.register_agent(mock_agent)

        # Start collaboration session
        session_id = await self.collaboration_engine.start_collaboration_session(
            project_goal=project_description, participating_agents=agent_ids
        )

        return session_id

    async def coordinate_project_phase(
        self, session_id: str, phase: str, objectives: List[str]
    ) -> Dict[str, Any]:
        """Coordinate a specific phase of project development."""

        context = self.collaboration_engine.contexts.get(session_id)
        if not context:
            raise ValueError(f"No collaboration context found for session {session_id}")

        context.current_phase = phase

        # Orchestrate discussions for each objective
        results = {}

        for objective in objectives:
            discussion_results = await self.collaboration_engine.orchestrate_discussion(
                topic=f"Phase {phase}: {objective}",
                context=context,
                required_expertise=self._determine_required_expertise(objective),
            )

            results[objective] = discussion_results

        return {
            "phase": phase,
            "objectives_addressed": len(objectives),
            "total_contributions": sum(len(r) for r in results.values()),
            "decisions_made": len(context.decisions_made),
            "session_id": session_id,
        }

    def _create_mock_agent(
        self, agent_id: str, role: AgentRole
    ) -> BaseCollaborativeAgent:
        """Create a mock agent for demonstration (real implementation would use actual agents)."""

        class MockAgent(BaseCollaborativeAgent):
            async def process_message(
                self, message: AgentMessage, context: CollaborationContext
            ) -> Optional[AgentMessage]:
                # Mock message processing
                if message.requires_response:
                    return AgentMessage(
                        id=str(uuid.uuid4()),
                        sender_id=self.agent_id,
                        recipient_id=message.sender_id,
                        message_type=MessageType.ANSWER,
                        subject=f"Re: {message.subject}",
                        content={"response": f"Processed by {self.role.value}"},
                        priority=message.priority,
                        timestamp=datetime.now(),
                        thread_id=message.thread_id,
                        parent_message_id=message.id,
                    )
                return None

            async def contribute_to_discussion(
                self, topic: str, context: CollaborationContext
            ) -> Dict[str, Any]:
                return {
                    "perspective": f"{self.role.value} perspective on {topic}",
                    "recommendations": [f"Recommendation from {self.role.value}"],
                    "concerns": [f"Concern from {self.role.value}"],
                    "expertise_applied": self.specializations,
                }

            async def execute_task(
                self, task: TaskDelegation, context: CollaborationContext
            ) -> Dict[str, Any]:
                return {
                    "status": "completed",
                    "deliverables": task.expected_deliverables,
                    "execution_notes": f"Task executed by {self.role.value}",
                    "time_spent": "2 hours",
                }

        return MockAgent(agent_id, role, [role.value])

    def _determine_required_expertise(self, objective: str) -> List[str]:
        """Determine what expertise is needed for a specific objective."""

        objective_lower = objective.lower()
        expertise = []

        if "security" in objective_lower:
            expertise.append("security")
        if "performance" in objective_lower:
            expertise.append("performance")
        if "test" in objective_lower:
            expertise.append("testing")
        if "design" in objective_lower or "architecture" in objective_lower:
            expertise.append("architecture")
        if "product" in objective_lower or "user" in objective_lower:
            expertise.append("product_management")

        return expertise or ["general"]
