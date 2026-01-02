"""
Plan Graph — DAG Execution Engine

Manages task dependencies as a Directed Acyclic Graph (DAG) and orchestrates
safe, step-by-step execution with proper dependency resolution.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import networkx as nx

from backend.agent.planning.task_decomposer import DecomposedTask, TaskPriority


class TaskStatus(Enum):
    """Status of individual tasks in the graph"""
    PLANNED = "PLANNED"
    READY = "READY"           # Dependencies satisfied
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"       # Waiting for dependencies
    FAILED = "FAILED"         # Execution failed
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"       # Skipped due to conditions


@dataclass 
class TaskNode:
    """Node in the plan graph representing a task"""
    task: DecomposedTask
    status: TaskStatus = TaskStatus.PLANNED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assignee: Optional[str] = None
    execution_log: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    approval_status: Optional[str] = None  # pending, approved, rejected
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "task": self.task.to_plan_step(),
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "assignee": self.assignee,
            "execution_log": self.execution_log,
            "failure_reason": self.failure_reason,
            "approval_status": self.approval_status,
        }


class PlanGraph:
    """Manages task execution as a DAG"""
    
    def __init__(self, tasks: List[DecomposedTask]):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, TaskNode] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
        self._build_graph(tasks)
    
    def _build_graph(self, tasks: List[DecomposedTask]) -> None:
        """Build the DAG from tasks and dependencies"""
        
        # Add all tasks as nodes
        for task in tasks:
            node = TaskNode(task=task)
            self.nodes[task.id] = node
            self.graph.add_node(task.id, data=node)
        
        # Add dependency edges
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in self.nodes:
                    # Edge from dependency to dependent task
                    self.graph.add_edge(dep_id, task.id)
        
        # Validate DAG (no cycles)
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"Circular dependencies detected: {cycles}")
    
    def get_ready_tasks(self) -> List[TaskNode]:
        """Get tasks that are ready to execute (dependencies satisfied)"""
        
        ready_tasks = []
        
        for task_id, node in self.nodes.items():
            if node.status != TaskStatus.PLANNED:
                continue
            
            # Check if all dependencies are completed
            dependencies_ready = True
            for pred_id in self.graph.predecessors(task_id):
                pred_node = self.nodes[pred_id]
                if pred_node.status != TaskStatus.COMPLETED:
                    dependencies_ready = False
                    break
            
            if dependencies_ready:
                node.status = TaskStatus.READY
                ready_tasks.append(node)
        
        # Sort by priority
        priority_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, 
                         TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        ready_tasks.sort(key=lambda n: priority_order[n.task.priority])
        
        return ready_tasks
    
    def start_task(self, task_id: str, assignee: Optional[str] = None) -> bool:
        """Start execution of a task"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        
        if node.status != TaskStatus.READY:
            return False
        
        node.status = TaskStatus.IN_PROGRESS
        node.started_at = datetime.now(timezone.utc)
        node.assignee = assignee
        
        self._log_event(task_id, "started", {"assignee": assignee})
        return True
    
    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a task as completed"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        
        if node.status != TaskStatus.IN_PROGRESS:
            return False
        
        node.status = TaskStatus.COMPLETED
        node.completed_at = datetime.now(timezone.utc)
        
        if result:
            node.execution_log.append(f"Completed: {json.dumps(result)}")
        
        self._log_event(task_id, "completed", result)
        return True
    
    def fail_task(self, task_id: str, reason: str) -> bool:
        """Mark a task as failed"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        
        if node.status != TaskStatus.IN_PROGRESS:
            return False
        
        node.status = TaskStatus.FAILED
        node.failure_reason = reason
        node.execution_log.append(f"Failed: {reason}")
        
        self._log_event(task_id, "failed", {"reason": reason})
        return True
    
    def block_task(self, task_id: str, reason: str) -> bool:
        """Mark a task as blocked"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        node.status = TaskStatus.BLOCKED
        node.execution_log.append(f"Blocked: {reason}")
        
        self._log_event(task_id, "blocked", {"reason": reason})
        return True
    
    def skip_task(self, task_id: str, reason: str) -> bool:
        """Skip a task (e.g., due to conditions)"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        node.status = TaskStatus.SKIPPED
        node.execution_log.append(f"Skipped: {reason}")
        
        self._log_event(task_id, "skipped", {"reason": reason})
        return True
    
    def get_execution_plan(self) -> List[List[str]]:
        """Get execution plan as phases of parallel tasks"""
        
        phases = []
        remaining_tasks = set(self.nodes.keys())
        
        while remaining_tasks:
            # Find tasks with no incomplete dependencies
            ready_in_phase = []
            for task_id in remaining_tasks:
                deps_complete = True
                for pred_id in self.graph.predecessors(task_id):
                    if pred_id in remaining_tasks:
                        deps_complete = False
                        break
                
                if deps_complete:
                    ready_in_phase.append(task_id)
            
            if not ready_in_phase:
                # Handle circular dependencies by picking highest priority
                priority_map = {t: self.nodes[t].task.priority for t in remaining_tasks}
                priority_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, 
                                TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
                best_task = min(remaining_tasks, key=lambda t: priority_order[priority_map[t]])
                ready_in_phase = [best_task]
            
            phases.append(ready_in_phase)
            remaining_tasks -= set(ready_in_phase)
        
        return phases
    
    def get_critical_path(self) -> List[str]:
        """Get the critical path through the graph"""
        
        # Calculate longest path using topological sort
        topo_order = list(nx.topological_sort(self.graph))
        
        # Calculate earliest start times
        earliest_start = {}
        for task_id in topo_order:
            task = self.nodes[task_id].task
            
            if not list(self.graph.predecessors(task_id)):
                # No dependencies
                earliest_start[task_id] = 0
            else:
                # Max of predecessor finish times
                max_pred_finish = 0
                for pred_id in self.graph.predecessors(task_id):
                    pred_finish = earliest_start[pred_id] + self.nodes[pred_id].task.estimated_hours
                    max_pred_finish = max(max_pred_finish, pred_finish)
                earliest_start[task_id] = max_pred_finish
        
        # Calculate latest start times (working backwards)
        latest_start = {}
        project_duration = max(
            earliest_start[task_id] + self.nodes[task_id].task.estimated_hours
            for task_id in self.nodes
        )
        
        for task_id in reversed(topo_order):
            task = self.nodes[task_id].task
            
            if not list(self.graph.successors(task_id)):
                # No successors - can start as late as project allows
                latest_start[task_id] = project_duration - task.estimated_hours
            else:
                # Min of successor start times minus our duration
                min_succ_start = float('inf')
                for succ_id in self.graph.successors(task_id):
                    min_succ_start = min(min_succ_start, latest_start[succ_id])
                latest_start[task_id] = min_succ_start - task.estimated_hours
        
        # Critical path: tasks with zero slack (earliest = latest)
        critical_tasks = [
            task_id for task_id in self.nodes
            if abs(earliest_start[task_id] - latest_start[task_id]) < 0.1  # Float comparison
        ]
        
        # Sort by earliest start time
        critical_tasks.sort(key=lambda t: earliest_start[t])
        
        return critical_tasks
    
    def get_blocked_tasks(self) -> List[TaskNode]:
        """Get currently blocked tasks"""
        return [node for node in self.nodes.values() if node.status == TaskStatus.BLOCKED]
    
    def get_failed_tasks(self) -> List[TaskNode]:
        """Get failed tasks"""
        return [node for node in self.nodes.values() if node.status == TaskStatus.FAILED]
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get overall progress summary"""
        
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for node in self.nodes.values() if node.status == status
            )
        
        total_tasks = len(self.nodes)
        completed_tasks = status_counts[TaskStatus.COMPLETED.value]
        progress_percent = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate time estimates
        total_estimated_hours = sum(node.task.estimated_hours for node in self.nodes.values())
        completed_hours = sum(
            node.task.estimated_hours for node in self.nodes.values() 
            if node.status == TaskStatus.COMPLETED
        )
        
        return {
            "total_tasks": total_tasks,
            "status_counts": status_counts,
            "progress_percent": round(progress_percent, 1),
            "total_estimated_hours": total_estimated_hours,
            "completed_hours": completed_hours,
            "critical_path": self.get_critical_path(),
            "ready_tasks_count": len(self.get_ready_tasks()),
            "blocked_tasks_count": len(self.get_blocked_tasks()),
            "failed_tasks_count": len(self.get_failed_tasks()),
        }
    
    def can_execute_task(self, task_id: str) -> Tuple[bool, str]:
        """Check if a task can be executed"""
        
        if task_id not in self.nodes:
            return False, "Task not found"
        
        node = self.nodes[task_id]
        
        if node.status == TaskStatus.COMPLETED:
            return False, "Task already completed"
        
        if node.status == TaskStatus.FAILED:
            return False, "Task has failed"
        
        if node.status == TaskStatus.SKIPPED:
            return False, "Task was skipped"
        
        if node.status == TaskStatus.IN_PROGRESS:
            return False, "Task already in progress"
        
        # Check dependencies
        for pred_id in self.graph.predecessors(task_id):
            pred_node = self.nodes[pred_id]
            if pred_node.status != TaskStatus.COMPLETED:
                return False, f"Dependency {pred_id} not completed (status: {pred_node.status.value})"
        
        # Check approval requirements
        if node.task.approval_required and node.approval_status != "approved":
            return False, "Task requires approval before execution"
        
        return True, "Ready to execute"
    
    def set_task_approval(self, task_id: str, approved: bool, approver: str) -> bool:
        """Set approval status for a task"""
        
        if task_id not in self.nodes:
            return False
        
        node = self.nodes[task_id]
        node.approval_status = "approved" if approved else "rejected"
        
        status = "approved" if approved else "rejected"
        self._log_event(task_id, "approval", {"status": status, "approver": approver})
        
        return True
    
    def get_tasks_needing_approval(self) -> List[TaskNode]:
        """Get tasks that need approval"""
        
        return [
            node for node in self.nodes.values()
            if node.task.approval_required and node.approval_status is None
        ]
    
    def visualize_graph(self) -> Dict[str, Any]:
        """Generate graph visualization data"""
        
        nodes = []
        edges = []
        
        for task_id, node in self.nodes.items():
            nodes.append({
                "id": task_id,
                "label": node.task.title,
                "status": node.status.value,
                "priority": node.task.priority.value,
                "estimated_hours": node.task.estimated_hours,
                "assignee": node.assignee,
            })
        
        for source, target in self.graph.edges():
            edges.append({
                "source": source,
                "target": target,
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_tasks": len(nodes),
                "total_edges": len(edges),
                "is_dag": nx.is_directed_acyclic_graph(self.graph),
                "critical_path": self.get_critical_path(),
            }
        }
    
    def _log_event(self, task_id: str, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Log an event in the execution history"""
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "event_type": event_type,
            "data": data or {},
        }
        
        self.execution_history.append(event)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire graph to dictionary"""
        
        return {
            "nodes": {task_id: node.to_dict() for task_id, node in self.nodes.items()},
            "edges": [(source, target) for source, target in self.graph.edges()],
            "execution_history": self.execution_history,
            "progress_summary": self.get_progress_summary(),
        }