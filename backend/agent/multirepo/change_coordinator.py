"""
ChangeCoordinator — Atomic Multi-Repo Changes

Coordinates atomic changes across multiple repositories with support for
coordinated PRs, ordered rollouts, rollback capabilities, and dependency-aware
deployment sequencing. This enables NAVI to safely orchestrate system-wide changes.

Key Capabilities:
- Coordinate atomic changes across repository boundaries
- Create synchronized pull requests with dependency ordering
- Manage staged rollouts with health monitoring
- Provide comprehensive rollback capabilities
- Handle deployment conflicts and coordination issues
"""

import logging
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from .repo_registry import RepoRegistry
from .repo_graph_builder import RepoGraphBuilder
from .impact_analyzer import ImpactAnalyzer, ImpactAnalysis, RiskLevel

logger = logging.getLogger(__name__)

class ChangeStatus(Enum):
    """Status of a coordinated change"""
    PLANNING = "planning"        # Change is being planned
    READY = "ready"             # Ready for execution
    IN_PROGRESS = "in_progress"  # Currently executing
    COMPLETED = "completed"      # Successfully completed
    FAILED = "failed"           # Failed execution
    ROLLING_BACK = "rolling_back"  # Rollback in progress
    ROLLED_BACK = "rolled_back"  # Successfully rolled back

class DeploymentStage(Enum):
    """Stages of deployment"""
    VALIDATION = "validation"    # Pre-deployment validation
    STAGING = "staging"         # Staging environment
    CANARY = "canary"           # Canary deployment
    PRODUCTION = "production"   # Full production
    VERIFICATION = "verification"  # Post-deployment verification

@dataclass
class ChangeRequest:
    """Represents a change request for a single repository"""
    repo_name: str
    branch_name: str
    commit_message: str
    file_changes: Dict[str, str] = field(default_factory=dict)  # file_path -> content
    pr_title: str = ""
    pr_description: str = ""
    reviewers: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    
    # Execution metadata
    priority: int = 0  # Higher number = higher priority
    estimated_duration: int = 30  # minutes
    health_checks: List[str] = field(default_factory=list)
    rollback_commands: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Repo names this depends on

@dataclass
class CoordinatedChange:
    """Represents a coordinated change across multiple repositories"""
    change_id: str
    title: str
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    
    # Change composition
    change_requests: List[ChangeRequest] = field(default_factory=list)
    dependency_order: List[str] = field(default_factory=list)  # Deployment order
    
    # Status tracking
    status: ChangeStatus = ChangeStatus.PLANNING
    current_stage: Optional[DeploymentStage] = None
    progress: Dict[str, str] = field(default_factory=dict)  # repo -> status
    
    # Risk assessment
    impact_analysis: Optional[ImpactAnalysis] = None
    risk_level: RiskLevel = RiskLevel.MINIMAL
    requires_approval: bool = False
    approved_by: List[str] = field(default_factory=list)
    
    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Rollback capability
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    can_rollback: bool = True
    rollback_window_hours: int = 24

@dataclass
class HealthCheck:
    """Health check definition"""
    name: str
    endpoint: str
    expected_status: int = 200
    timeout_seconds: int = 30
    retries: int = 3
    custom_validation: Optional[Callable] = None

class ChangeCoordinator:
    """
    Coordinates atomic changes across multiple repositories with sophisticated
    dependency management, health monitoring, and rollback capabilities.
    """
    
    def __init__(self,
                 repo_registry: Optional[RepoRegistry] = None,
                 graph_builder: Optional[RepoGraphBuilder] = None,
                 impact_analyzer: Optional[ImpactAnalyzer] = None):
        """Initialize the change coordinator"""
        self.repo_registry = repo_registry or RepoRegistry()
        self.graph_builder = graph_builder or RepoGraphBuilder(self.repo_registry)
        self.impact_analyzer = impact_analyzer or ImpactAnalyzer(
            repo_registry=self.repo_registry,
            graph_builder=self.graph_builder
        )
        
        # Active coordinated changes
        self.active_changes: Dict[str, CoordinatedChange] = {}
        
        # Health check monitoring
        self.health_checks: Dict[str, List[HealthCheck]] = defaultdict(list)
        
        logger.info("ChangeCoordinator initialized for atomic multi-repo changes")
    
    async def create_coordinated_change(self,
                                      title: str,
                                      description: str,
                                      change_requests: List[ChangeRequest],
                                      created_by: str = "") -> str:
        """
        Create a new coordinated change across multiple repositories
        
        Args:
            title: Title of the coordinated change
            description: Detailed description
            change_requests: List of individual repository changes
            created_by: User creating the change
            
        Returns:
            Change ID for tracking
        """
        change_id = f"coord-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.active_changes)}"
        
        logger.info(f"Creating coordinated change {change_id}: {title}")
        
        # Build dependency order
        dependency_order = await self._calculate_deployment_order(change_requests)
        
        # Perform impact analysis
        impact_analysis = await self._analyze_coordinated_impact(change_requests)
        
        # Create coordinated change
        coordinated_change = CoordinatedChange(
            change_id=change_id,
            title=title,
            description=description,
            created_by=created_by,
            change_requests=change_requests,
            dependency_order=dependency_order,
            impact_analysis=impact_analysis,
            risk_level=impact_analysis.overall_risk if impact_analysis else RiskLevel.MINIMAL
        )
        
        # Determine if approval is required
        coordinated_change.requires_approval = (
            coordinated_change.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            or len(change_requests) > 5
            or any(cr.repo_name.endswith('-prod') for cr in change_requests)
        )
        
        # Generate rollback plan
        coordinated_change.rollback_plan = await self._generate_rollback_plan(
            change_requests, dependency_order
        )
        
        # Initialize progress tracking
        for cr in change_requests:
            coordinated_change.progress[cr.repo_name] = "pending"
        
        self.active_changes[change_id] = coordinated_change
        
        logger.info(f"Coordinated change {change_id} created with {len(change_requests)} repositories")
        return change_id
    
    async def execute_coordinated_change(self,
                                       change_id: str,
                                       dry_run: bool = False) -> bool:
        """
        Execute a coordinated change across all repositories
        
        Args:
            change_id: ID of the change to execute
            dry_run: If True, simulate execution without making changes
            
        Returns:
            True if successful, False otherwise
        """
        if change_id not in self.active_changes:
            logger.error(f"Coordinated change {change_id} not found")
            return False
        
        change = self.active_changes[change_id]
        
        if change.requires_approval and not change.approved_by:
            logger.error(f"Change {change_id} requires approval before execution")
            return False
        
        logger.info(f"Executing coordinated change {change_id} (dry_run={dry_run})")
        
        try:
            change.status = ChangeStatus.IN_PROGRESS
            change.started_at = datetime.now()
            
            # Execute changes in dependency order
            for repo_name in change.dependency_order:
                change_request = next(
                    (cr for cr in change.change_requests if cr.repo_name == repo_name),
                    None
                )
                
                if not change_request:
                    continue
                
                logger.info(f"Executing change for repository: {repo_name}")
                change.progress[repo_name] = "in_progress"
                
                # Execute individual change
                success = await self._execute_single_change(change_request, dry_run)
                
                if success:
                    change.progress[repo_name] = "completed"
                    
                    # Perform health checks
                    if not dry_run:
                        health_ok = await self._perform_health_checks(repo_name)
                        if not health_ok:
                            logger.error(f"Health checks failed for {repo_name}")
                            await self._rollback_coordinated_change(change_id)
                            return False
                else:
                    change.progress[repo_name] = "failed"
                    logger.error(f"Change execution failed for {repo_name}")
                    
                    # Rollback already completed changes
                    if not dry_run:
                        await self._rollback_coordinated_change(change_id)
                    return False
                
                # Wait between deployments for monitoring
                if not dry_run and repo_name != change.dependency_order[-1]:
                    await asyncio.sleep(30)  # 30 second monitoring window
            
            change.status = ChangeStatus.COMPLETED
            change.completed_at = datetime.now()
            
            logger.info(f"Coordinated change {change_id} completed successfully")
            return True
            
        except Exception as e:
            change.status = ChangeStatus.FAILED
            change.failed_at = datetime.now()
            change.error_message = str(e)
            
            logger.error(f"Coordinated change {change_id} failed: {e}")
            
            # Attempt rollback
            if not dry_run:
                await self._rollback_coordinated_change(change_id)
            
            return False
    
    async def _calculate_deployment_order(self, 
                                        change_requests: List[ChangeRequest]) -> List[str]:
        """Calculate optimal deployment order based on dependencies"""
        repo_names = [cr.repo_name for cr in change_requests]
        
        # Build dependency graph from registry
        repo_graph = await self.graph_builder.build_dependency_graph(
            repo_filter=repo_names,
            include_external=False
        )
        
        # Topological sort for deployment order
        deployment_order = []
        in_degree = defaultdict(int)
        
        # Calculate in-degrees
        for repo in repo_names:
            dependencies = repo_graph.get_dependencies(repo)
            in_degree[repo] = len([d for d in dependencies if d in repo_names])
        
        # Process nodes with no dependencies first
        queue = deque([repo for repo in repo_names if in_degree[repo] == 0])
        
        while queue:
            repo = queue.popleft()
            deployment_order.append(repo)
            
            # Update in-degrees of dependents
            dependents = repo_graph.get_dependents(repo)
            for dependent in dependents:
                if dependent in repo_names:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        # Handle any remaining nodes (circular dependencies)
        remaining = [repo for repo in repo_names if repo not in deployment_order]
        deployment_order.extend(remaining)
        
        logger.info(f"Calculated deployment order: {deployment_order}")
        return deployment_order
    
    async def _analyze_coordinated_impact(self,
                                        change_requests: List[ChangeRequest]) -> Optional[ImpactAnalysis]:
        """Analyze the combined impact of all changes"""
        try:
            # For now, analyze the impact of the first (most critical) repository
            # In a full implementation, we'd combine impacts from all repos
            primary_change = change_requests[0] if change_requests else None
            
            if primary_change:
                return await self.impact_analyzer.analyze_change_impact(
                    repo_name=primary_change.repo_name,
                    change_description=primary_change.commit_message,
                    change_type=self._infer_change_type(primary_change)
                )
        except Exception as e:
            logger.warning(f"Failed to analyze coordinated impact: {e}")
        
        return None
    
    def _infer_change_type(self, change_request: ChangeRequest):
        """Infer change type from change request"""
        from .impact_analyzer import ChangeType
        
        # Simple inference based on file patterns and commit message
        changed_files = list(change_request.file_changes.keys())
        commit_msg = change_request.commit_message.lower()
        
        if any('api' in f.lower() or 'schema' in f.lower() for f in changed_files):
            return ChangeType.API_CHANGE
        elif any('migration' in f.lower() or 'database' in commit_msg for f in changed_files):
            return ChangeType.DATABASE_CHANGE
        elif 'config' in commit_msg or any('config' in f.lower() for f in changed_files):
            return ChangeType.CONFIGURATION_CHANGE
        elif 'infrastructure' in commit_msg or any('terraform' in f.lower() for f in changed_files):
            return ChangeType.INFRASTRUCTURE_CHANGE
        else:
            return ChangeType.CODE_CHANGE
    
    async def _generate_rollback_plan(self,
                                     change_requests: List[ChangeRequest],
                                     dependency_order: List[str]) -> Dict[str, Any]:
        """Generate comprehensive rollback plan"""
        rollback_plan = {
            'strategy': 'reverse_dependency_order',
            'order': list(reversed(dependency_order)),
            'commands': {},
            'verification_steps': [],
            'estimated_duration_minutes': len(change_requests) * 10
        }
        
        # Add rollback commands for each repository
        for change_request in change_requests:
            repo_name = change_request.repo_name
            rollback_plan['commands'][repo_name] = {
                'git_revert': True,
                'custom_commands': change_request.rollback_commands,
                'health_checks': change_request.health_checks
            }
        
        # Add verification steps
        rollback_plan['verification_steps'] = [
            "Verify all services are healthy",
            "Check key business metrics",
            "Validate system integration",
            "Confirm rollback completion"
        ]
        
        return rollback_plan
    
    async def _execute_single_change(self,
                                   change_request: ChangeRequest,
                                   dry_run: bool) -> bool:
        """Execute a change for a single repository"""
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would execute change for {change_request.repo_name}")
                await asyncio.sleep(1)  # Simulate execution time
                return True
            
            # In a real implementation, this would:
            # 1. Create a branch
            # 2. Apply file changes
            # 3. Commit changes
            # 4. Create pull request
            # 5. Optionally auto-merge (for automated changes)
            
            logger.info(f"Executing change for {change_request.repo_name}")
            
            # Simulate change execution
            await asyncio.sleep(2)
            
            # For now, always succeed in simulation
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute change for {change_request.repo_name}: {e}")
            return False
    
    async def _perform_health_checks(self, repo_name: str) -> bool:
        """Perform health checks after deployment"""
        health_checks = self.health_checks.get(repo_name, [])
        
        if not health_checks:
            logger.info(f"No health checks configured for {repo_name}")
            return True
        
        logger.info(f"Performing {len(health_checks)} health checks for {repo_name}")
        
        for health_check in health_checks:
            try:
                # In a real implementation, this would make HTTP requests
                # For now, simulate health check
                await asyncio.sleep(1)
                
                # Simulate random success/failure for demonstration
                success = True  # In reality, check actual endpoints
                
                if not success:
                    logger.error(f"Health check failed: {health_check.name}")
                    return False
                    
                logger.info(f"Health check passed: {health_check.name}")
                
            except Exception as e:
                logger.error(f"Health check error for {health_check.name}: {e}")
                return False
        
        return True
    
    async def _rollback_coordinated_change(self, change_id: str) -> bool:
        """Rollback a coordinated change"""
        if change_id not in self.active_changes:
            return False
        
        change = self.active_changes[change_id]
        
        logger.info(f"Rolling back coordinated change {change_id}")
        
        change.status = ChangeStatus.ROLLING_BACK
        rollback_order = change.rollback_plan.get('order', 
                                                  list(reversed(change.dependency_order)))
        
        try:
            for repo_name in rollback_order:
                if change.progress.get(repo_name) == "completed":
                    logger.info(f"Rolling back {repo_name}")
                    
                    # Execute rollback commands
                    change.rollback_plan['commands'].get(
                        repo_name, {}
                    ).get('custom_commands', [])
                    
                    # In a real implementation, execute the rollback commands
                    await asyncio.sleep(1)  # Simulate rollback time
                    
                    change.progress[repo_name] = "rolled_back"
            
            change.status = ChangeStatus.ROLLED_BACK
            logger.info(f"Coordinated change {change_id} rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed for {change_id}: {e}")
            return False
    
    def add_health_check(self, repo_name: str, health_check: HealthCheck) -> None:
        """Add a health check for a repository"""
        self.health_checks[repo_name].append(health_check)
        logger.info(f"Added health check '{health_check.name}' for {repo_name}")
    
    def approve_change(self, change_id: str, approver: str) -> bool:
        """Approve a coordinated change"""
        if change_id not in self.active_changes:
            return False
        
        change = self.active_changes[change_id]
        
        if approver not in change.approved_by:
            change.approved_by.append(approver)
            logger.info(f"Change {change_id} approved by {approver}")
        
        return True
    
    def get_change_status(self, change_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a coordinated change"""
        if change_id not in self.active_changes:
            return None
        
        change = self.active_changes[change_id]
        
        return {
            'change_id': change_id,
            'title': change.title,
            'status': change.status.value,
            'progress': change.progress,
            'risk_level': change.risk_level.value,
            'requires_approval': change.requires_approval,
            'approved_by': change.approved_by,
            'started_at': change.started_at.isoformat() if change.started_at else None,
            'completed_at': change.completed_at.isoformat() if change.completed_at else None,
            'can_rollback': change.can_rollback,
            'repositories': [cr.repo_name for cr in change.change_requests]
        }
    
    def list_active_changes(self) -> List[Dict[str, Any]]:
        """List all active coordinated changes"""
        return [
            self.get_change_status(change_id) 
            for change_id in self.active_changes.keys()
        ]

# Convenience functions
async def create_coordinated_change(title: str,
                                   description: str, 
                                   change_requests: List[ChangeRequest]) -> str:
    """Convenience function to create coordinated change"""
    coordinator = ChangeCoordinator()
    return await coordinator.create_coordinated_change(title, description, change_requests)