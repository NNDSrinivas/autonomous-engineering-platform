"""
Phase 5.0 — Context Resolver (Full Situational Awareness)

Builds comprehensive context from external events by integrating with existing
Phase 4.8 memory systems, knowledge graphs, and organizational intelligence.
Never acts blindly - always builds full situational awareness first.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

from backend.api.events.models import IngestEvent
from backend.services.memory_graph_service import MemoryGraphService
from backend.agent.context_packet import build_context_packet


logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context that can be resolved"""
    JIRA_ISSUE = "JIRA_ISSUE"
    GITHUB_PR = "GITHUB_PR"
    SLACK_THREAD = "SLACK_THREAD"
    CI_BUILD = "CI_BUILD"
    DEPLOYMENT = "DEPLOYMENT"
    USER_MENTION = "USER_MENTION"


@dataclass
class ResolvedContext:
    """Comprehensive context resolved from an event"""
    event_id: str
    context_type: ContextType
    
    # Core context
    primary_object: Dict[str, Any]  # The main object (issue, PR, etc.)
    
    # Related objects
    related_issues: List[Dict[str, Any]]
    related_prs: List[Dict[str, Any]]
    related_conversations: List[Dict[str, Any]]
    related_documentation: List[Dict[str, Any]]
    related_code_files: List[str]
    
    # Organizational context
    team_members: List[Dict[str, Any]]
    project_context: Dict[str, Any]
    historical_patterns: List[Dict[str, Any]]
    
    # Technical context
    repository_info: Optional[Dict[str, Any]]
    deployment_info: Optional[Dict[str, Any]]
    dependencies: List[str]
    
    # Risk assessment
    risk_factors: List[str]
    complexity_score: float  # 0.0 to 1.0
    urgency_indicators: List[str]
    
    # Confidence metrics
    context_completeness: float  # 0.0 to 1.0
    data_freshness: float       # 0.0 to 1.0
    resolution_time_ms: int
    user_id: Optional[str] = None
    org_id: Optional[str] = None

    @property
    def confidence_score(self) -> float:
        """Compatibility alias for callers expecting a confidence score."""
        return self.context_completeness


class ContextResolver:
    """
    Builds comprehensive situational awareness from events
    
    Integrates with:
    - Phase 4.8 Memory Graph for organizational knowledge
    - Existing context packet system for cached context
    - Live APIs for fresh data when needed
    - Historical pattern analysis for insights
    """
    
    def __init__(self, db_session, memory_service: Optional[MemoryGraphService] = None, org_id: str = "default", user_id: str = "system"):
        self.db = db_session
        self.org_id = org_id
        self.user_id = user_id
        self.memory_service = memory_service or MemoryGraphService(db_session, org_id, user_id)
        
        # Context resolvers by type
        self.resolvers = {
            "jira": self._resolve_jira_context,
            "github": self._resolve_github_context,
            "slack": self._resolve_slack_context,
            "ci": self._resolve_ci_context,
            "deployment": self._resolve_deployment_context,
        }
        
        # Cache for resolved contexts (short-term)
        self.context_cache: Dict[str, ResolvedContext] = {}
        self.cache_ttl_seconds = 300  # 5 minutes
    
    async def resolve_context(self, event: IngestEvent) -> ResolvedContext:
        """
        Resolve comprehensive context from an event
        
        This is the main entry point that builds full situational awareness
        """
        
        resolution_start = datetime.now()
        
        logger.info(f"Resolving context for {event.source}:{event.external_id}")
        
        # Check cache first
        cache_key = f"{event.source}:{event.external_id}"
        if cache_key in self.context_cache:
            cached = self.context_cache[cache_key]
            if self._is_cache_valid(cached):
                logger.debug(f"Using cached context for {cache_key}")
                return cached
        
        # Get resolver for event source
        resolver = self.resolvers.get(event.source, self._resolve_generic_context)
        
        try:
            # Resolve context
            context = await resolver(event)
            
            # Calculate resolution time
            resolution_time = (datetime.now() - resolution_start).total_seconds() * 1000
            context.resolution_time_ms = int(resolution_time)
            context.user_id = self.user_id
            context.org_id = self.org_id
            
            # Cache the result
            self.context_cache[cache_key] = context
            
            logger.info(f"Context resolved for {cache_key} in {resolution_time:.1f}ms")
            return context
            
        except Exception as e:
            logger.error(f"Failed to resolve context for {cache_key}: {e}")
            
            # Return minimal context on failure
            return ResolvedContext(
                event_id=cache_key,
                context_type=ContextType.USER_MENTION,  # Generic fallback
                primary_object={"error": str(e)},
                related_issues=[],
                related_prs=[],
                related_conversations=[],
                related_documentation=[],
                related_code_files=[],
                team_members=[],
                project_context={},
                historical_patterns=[],
                repository_info=None,
                deployment_info=None,
                dependencies=[],
                risk_factors=["context_resolution_failed"],
                complexity_score=1.0,  # Max complexity due to unknown
                urgency_indicators=[],
                context_completeness=0.0,
                data_freshness=1.0,
                resolution_time_ms=int((datetime.now() - resolution_start).total_seconds() * 1000),
                user_id=self.user_id,
                org_id=self.org_id,
            )
    
    async def _resolve_jira_context(self, event: IngestEvent) -> ResolvedContext:
        """Resolve context for Jira events"""
        
        issue_key = event.external_id
        
        # 1. Get primary Jira issue
        primary_issue = await self._get_jira_issue_details(issue_key)
        
        # 2. Find related issues via memory graph
        related_issues = await self._find_related_jira_issues(issue_key, primary_issue)
        
        # 3. Find linked PRs
        related_prs = await self._find_linked_github_prs(issue_key)
        
        # 4. Get conversation history
        related_conversations = await self._get_jira_conversations(issue_key)
        
        # 5. Find related documentation
        related_documentation = await self._find_related_documentation(issue_key, primary_issue)
        
        # 6. Analyze code files mentioned/related
        related_code_files = await self._identify_related_code_files(issue_key, primary_issue)
        
        # 7. Get team context
        team_members = await self._get_team_context(primary_issue)
        
        # 8. Get project context
        project_context = await self._get_project_context(primary_issue)
        
        # 9. Find historical patterns
        historical_patterns = await self._find_historical_patterns(issue_key, primary_issue)
        
        # 10. Assess risk and complexity
        risk_factors = self._assess_jira_risk_factors(primary_issue, related_issues)
        complexity_score = self._calculate_complexity_score(primary_issue, related_issues, related_code_files)
        urgency_indicators = self._identify_urgency_indicators(primary_issue)
        
        # 11. Calculate context quality metrics
        context_completeness = self._calculate_context_completeness([
            primary_issue, related_issues, related_prs, related_conversations
        ])
        data_freshness = self._calculate_data_freshness(primary_issue)
        
        return ResolvedContext(
            event_id=f"jira:{issue_key}",
            context_type=ContextType.JIRA_ISSUE,
            primary_object=primary_issue,
            related_issues=related_issues,
            related_prs=related_prs,
            related_conversations=related_conversations,
            related_documentation=related_documentation,
            related_code_files=related_code_files,
            team_members=team_members,
            project_context=project_context,
            historical_patterns=historical_patterns,
            repository_info=await self._get_repository_info_from_issue(primary_issue),
            deployment_info=None,
            dependencies=await self._extract_dependencies_from_issue(primary_issue),
            risk_factors=risk_factors,
            complexity_score=complexity_score,
            urgency_indicators=urgency_indicators,
            context_completeness=context_completeness,
            data_freshness=data_freshness,
            resolution_time_ms=0  # Will be set by caller
        )
    
    async def _resolve_github_context(self, event: IngestEvent) -> ResolvedContext:
        """Resolve context for GitHub events"""
        
        pr_number = event.external_id
        repository = event.tags.get("repository", "")
        
        # Get PR details from memory graph or API
        primary_pr = await self._get_github_pr_details(pr_number, repository)
        
        # Find linked Jira issues
        related_issues = await self._find_issues_from_pr(primary_pr)
        
        return ResolvedContext(
            event_id=f"github:{repository}#{pr_number}",
            context_type=ContextType.GITHUB_PR,
            primary_object=primary_pr,
            related_issues=related_issues,
            related_prs=[],
            related_conversations=await self._get_pr_conversations(pr_number, repository),
            related_documentation=[],
            related_code_files=await self._get_pr_changed_files(primary_pr),
            team_members=await self._get_pr_team_context(primary_pr),
            project_context={"repository": repository},
            historical_patterns=[],
            repository_info={"name": repository, "pr_number": pr_number},
            deployment_info=None,
            dependencies=[],
            risk_factors=self._assess_pr_risk_factors(primary_pr),
            complexity_score=self._calculate_pr_complexity(primary_pr),
            urgency_indicators=self._identify_pr_urgency_indicators(primary_pr),
            context_completeness=0.8,  # Generally good for PRs
            data_freshness=1.0,  # Fresh from webhook
            resolution_time_ms=0
        )
    
    async def _resolve_slack_context(self, event: IngestEvent) -> ResolvedContext:
        """Resolve context for Slack events"""
        
        channel = event.tags.get("channel", "")
        message_ts = event.external_id
        
        # Get Slack message details
        primary_message = {
            "channel": channel,
            "timestamp": message_ts,
            "text": event.content or "",
            "user": event.tags.get("user"),
        }
        
        # Find mentioned Jira issues
        related_issues = await self._find_jira_issues_in_text(event.content or "")
        
        return ResolvedContext(
            event_id=f"slack:{channel}:{message_ts}",
            context_type=ContextType.SLACK_THREAD,
            primary_object=primary_message,
            related_issues=related_issues,
            related_prs=[],
            related_conversations=await self._get_slack_thread_context(channel, message_ts),
            related_documentation=[],
            related_code_files=[],
            team_members=await self._get_slack_channel_members(channel),
            project_context={"channel": channel},
            historical_patterns=[],
            repository_info=None,
            deployment_info=None,
            dependencies=[],
            risk_factors=self._assess_slack_risk_factors(primary_message),
            complexity_score=0.3,  # Usually simple
            urgency_indicators=self._identify_slack_urgency_indicators(primary_message),
            context_completeness=0.6,  # Limited context
            data_freshness=1.0,
            resolution_time_ms=0
        )
    
    async def _resolve_ci_context(self, event: IngestEvent) -> ResolvedContext:
        """Resolve context for CI/CD events"""
        
        build_id = event.external_id
        
        primary_build = {
            "build_id": build_id,
            "status": event.tags.get("status", "failed"),
            "repository": event.tags.get("repository"),
            "branch": event.tags.get("branch"),
            "failure_type": event.tags.get("failure_type"),
        }
        
        return ResolvedContext(
            event_id=f"ci:{build_id}",
            context_type=ContextType.CI_BUILD,
            primary_object=primary_build,
            related_issues=[],
            related_prs=(
                await self._find_pr_for_branch(event.tags.get("branch"), event.tags.get("repository"))
                if event.tags.get("branch") and event.tags.get("repository")
                else []
            ),
            related_conversations=[],
            related_documentation=[],
            related_code_files=await self._get_failed_test_files(primary_build),
            team_members=[],
            project_context={"repository": event.tags.get("repository")},
            historical_patterns=[],
            repository_info={"name": event.tags.get("repository")},
            deployment_info=None,
            dependencies=[],
            risk_factors=self._assess_ci_risk_factors(primary_build),
            complexity_score=self._calculate_ci_complexity(primary_build),
            urgency_indicators=self._identify_ci_urgency_indicators(primary_build),
            context_completeness=0.7,
            data_freshness=1.0,
            resolution_time_ms=0
        )
    
    async def _resolve_deployment_context(self, event: IngestEvent) -> ResolvedContext:
        """Resolve context for deployment events"""
        
        deployment_id = event.external_id
        
        primary_deployment = {
            "deployment_id": deployment_id,
            "status": event.tags.get("status", "failed"),
            "environment": event.tags.get("environment"),
            "service": event.tags.get("service"),
            "error_type": event.tags.get("error_type"),
        }
        
        return ResolvedContext(
            event_id=f"deployment:{deployment_id}",
            context_type=ContextType.DEPLOYMENT,
            primary_object=primary_deployment,
            related_issues=[],
            related_prs=[],
            related_conversations=[],
            related_documentation=[],
            related_code_files=[],
            team_members=[],
            project_context={"service": event.tags.get("service")},
            historical_patterns=[],
            repository_info=None,
            deployment_info=primary_deployment,
            dependencies=[],
            risk_factors=self._assess_deployment_risk_factors(primary_deployment),
            complexity_score=0.8,  # Deployments are typically complex
            urgency_indicators=self._identify_deployment_urgency_indicators(primary_deployment),
            context_completeness=0.5,  # Often limited context
            data_freshness=1.0,
            resolution_time_ms=0
        )
    
    async def _resolve_generic_context(self, event: IngestEvent) -> ResolvedContext:
        """Fallback resolver for unknown event types"""
        
        return ResolvedContext(
            event_id=f"{event.source}:{event.external_id}",
            context_type=ContextType.USER_MENTION,
            primary_object={"source": event.source, "id": event.external_id, "content": event.content},
            related_issues=[],
            related_prs=[],
            related_conversations=[],
            related_documentation=[],
            related_code_files=[],
            team_members=[],
            project_context={},
            historical_patterns=[],
            repository_info=None,
            deployment_info=None,
            dependencies=[],
            risk_factors=["unknown_event_type"],
            complexity_score=0.5,
            urgency_indicators=[],
            context_completeness=0.1,
            data_freshness=1.0,
            resolution_time_ms=0
        )
    
    # Helper methods for context resolution
    
    async def _get_jira_issue_details(self, issue_key: str) -> Dict[str, Any]:
        """Get detailed Jira issue information"""
        
        try:
            # Use existing context packet system
            context_packet = await build_context_packet(
                issue_key,
                self.db,
                user_id=self.user_id,
                org_id=self.org_id,
            )
            if context_packet and context_packet.jira:
                return context_packet.jira
            
            # Fallback to basic info
            return {
                "key": issue_key,
                "title": f"Issue {issue_key}",
                "status": "unknown",
                "priority": "medium",
                "assignee": None,
                "description": "",
            }
            
        except Exception as e:
            logger.error(f"Failed to get Jira issue details for {issue_key}: {e}")
            return {"key": issue_key, "error": str(e)}
    
    async def _find_related_jira_issues(self, issue_key: str, primary_issue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find related Jira issues using memory graph"""
        
        try:
            node_id = await self._find_node_id("jira_issue", issue_key)
            if not node_id:
                return []
            related_nodes, _ = self.memory_service.get_related_nodes(
                node_id,
                edge_types=["links", "blocks", "relates_to"],
                depth=2,
            )
            return [
                meta
                for node in related_nodes
                for meta in [self._extract_node_meta(node)]
                if meta
            ]
            
        except Exception as e:
            logger.error(f"Failed to find related Jira issues for {issue_key}: {e}")
            return []
    
    async def _find_linked_github_prs(self, issue_key: str) -> List[Dict[str, Any]]:
        """Find GitHub PRs linked to this Jira issue"""
        
        try:
            node_id = await self._find_node_id("jira_issue", issue_key)
            if not node_id:
                return []
            pr_nodes, _ = self.memory_service.get_related_nodes(
                node_id,
                edge_types=["implements"],
                depth=1,
            )
            return [
                meta
                for node in pr_nodes
                for meta in [self._extract_node_meta(node)]
                if meta
            ]
            
        except Exception as e:
            logger.error(f"Failed to find linked PRs for {issue_key}: {e}")
            return []
    
    async def _get_jira_conversations(self, issue_key: str) -> List[Dict[str, Any]]:
        """Get conversation history for Jira issue"""
        
        try:
            node_id = await self._find_node_id("jira_issue", issue_key)
            if not node_id:
                return []
            comment_nodes, _ = self.memory_service.get_related_nodes(
                node_id,
                edge_types=["has_comment"],
                depth=1,
            )
            
            conversations = []
            for node in comment_nodes:
                meta = self._extract_node_meta(node) or {}
                if meta:
                    created_at = self._extract_node_created_at(node)
                    conversations.append({
                        "type": "comment",
                        "author": meta.get("author"),
                        "body": self._extract_node_text(node) or meta.get("body"),
                        "created": created_at.isoformat() if created_at else None,
                    })
            
            return sorted(conversations, key=lambda x: x.get("created", ""))
            
        except Exception as e:
            logger.error(f"Failed to get Jira conversations for {issue_key}: {e}")
            return []
    
    async def _find_related_documentation(self, issue_key: str, issue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find related documentation (Confluence, wikis, etc.)"""
        
        try:
            # Search for documentation mentioning this issue
            doc_nodes = await self.memory_service.search(
                query=f"{issue_key} {issue.get('title', '')}",
                node_types=["confluence_page", "wiki_page", "documentation"],
                limit=5
            )
            
            return [
                {
                    "type": node.get("node_type"),
                    "title": node.get("title"),
                    "url": (node.get("meta_json") or {}).get("url"),
                    "summary": (node.get("text") or "")[:200],
                }
                for node in doc_nodes
            ]
            
        except Exception as e:
            logger.error(f"Failed to find related documentation for {issue_key}: {e}")
            return []
    
    async def _identify_related_code_files(self, issue_key: str, issue: Dict[str, Any]) -> List[str]:
        """Identify code files related to this issue"""
        
        try:
            # Look for file mentions in issue description and comments
            description = issue.get("description", "")
            title = issue.get("title", "")
            
            # Simple file pattern matching
            import re
            file_patterns = [
                r'\b[\w\-_/]+\.\w+\b',  # file.ext
                r'\b[\w\-_/]+/[\w\-_/]+\b',  # path/to/file
            ]
            
            files = set()
            for pattern in file_patterns:
                for text in [description, title]:
                    matches = re.findall(pattern, text)
                    files.update(matches)
            
            # Filter for likely code files
            code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.h'}
            code_files = [
                f for f in files 
                if any(f.endswith(ext) for ext in code_extensions)
            ]
            
            return list(code_files)[:10]  # Limit to 10 files
            
        except Exception as e:
            logger.error(f"Failed to identify related code files for {issue_key}: {e}")
            return []
    
    async def _get_team_context(self, issue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get team member context for this issue"""
        
        team_members = []
        
        # Add assignee
        if issue.get("assignee"):
            team_members.append({
                "role": "assignee",
                "user": issue["assignee"],
                "email": f"{issue['assignee']}@company.com",  # Would be resolved from directory
            })
        
        # Add reporter
        if issue.get("reporter") and issue["reporter"] != issue.get("assignee"):
            team_members.append({
                "role": "reporter", 
                "user": issue["reporter"],
                "email": f"{issue['reporter']}@company.com",
            })
        
        return team_members
    
    async def _get_project_context(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Get project context for this issue"""
        
        return {
            "project_key": issue.get("project", {}).get("key"),
            "project_name": issue.get("project", {}).get("name"),
            "issue_type": issue.get("issuetype", {}).get("name"),
            "components": issue.get("components", []),
            "labels": issue.get("labels", []),
        }
    
    async def _find_historical_patterns(self, issue_key: str, issue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find historical patterns for similar issues"""
        
        try:
            # Search for similar issues by title/description
            similar_nodes = await self.memory_service.search(
                query=issue.get("title", ""),
                node_types=["jira_issue"],
                limit=5
            )
            
            patterns = []
            for node in similar_nodes:
                meta = node.get("meta_json") or {}
                if meta.get("key") == issue_key or meta.get("issue_key") == issue_key:
                    continue
                patterns.append({
                    "issue_key": meta.get("key") or meta.get("issue_key") or node.get("title"),
                    "title": node.get("title"),
                    "resolution": meta.get("resolution"),
                    "time_to_resolve": meta.get("time_to_resolve"),
                    "similarity": 0.8,  # Would be calculated from embeddings
                })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to find historical patterns for {issue_key}: {e}")
            return []
    
    # Risk and complexity assessment methods
    
    def _assess_jira_risk_factors(self, issue: Dict[str, Any], related_issues: List[Dict[str, Any]]) -> List[str]:
        """Assess risk factors for a Jira issue"""
        
        risks = []
        
        # Priority-based risks
        if issue.get("priority", "").lower() in ["critical", "blocker"]:
            risks.append("high_priority_issue")
        
        # Status-based risks
        if issue.get("status", "").lower() in ["blocked", "impediment"]:
            risks.append("blocked_status")
        
        # Relationship-based risks
        if len(related_issues) > 5:
            risks.append("many_dependencies")
        
        # Time-based risks
        created = issue.get("created")
        if created:
            # Would calculate age and add risk if old
            risks.append("aging_issue")
        
        return risks
    
    def _calculate_complexity_score(self, issue: Dict[str, Any], related_issues: List[Dict[str, Any]], code_files: List[str]) -> float:
        """Calculate complexity score for an issue"""
        
        score = 0.0
        
        # Base complexity from description length
        description_len = len(issue.get("description", ""))
        score += min(description_len / 1000, 0.3)  # Max 0.3 from description
        
        # Complexity from related issues
        score += min(len(related_issues) / 10, 0.3)  # Max 0.3 from relationships
        
        # Complexity from code files
        score += min(len(code_files) / 20, 0.3)  # Max 0.3 from files
        
        # Issue type complexity
        issue_type = issue.get("issuetype", {}).get("name", "").lower()
        type_complexity = {
            "epic": 0.1,
            "story": 0.0,
            "task": 0.0,
            "bug": 0.1,
            "incident": 0.2,
        }
        score += type_complexity.get(issue_type, 0.1)
        
        return min(score, 1.0)
    
    def _identify_urgency_indicators(self, issue: Dict[str, Any]) -> List[str]:
        """Identify urgency indicators in an issue"""
        
        indicators = []
        
        # Priority indicators
        priority = issue.get("priority", "").lower()
        if priority in ["critical", "blocker", "highest"]:
            indicators.append(f"priority_{priority}")
        
        # Keyword indicators
        text_content = f"{issue.get('title', '')} {issue.get('description', '')}".lower()
        urgent_keywords = ["urgent", "asap", "emergency", "critical", "broken", "down", "outage"]
        
        for keyword in urgent_keywords:
            if keyword in text_content:
                indicators.append(f"keyword_{keyword}")
        
        # Time-based indicators
        if issue.get("duedate"):
            indicators.append("has_due_date")
        
        return indicators
    
    # Context quality assessment
    
    def _calculate_context_completeness(self, context_objects: List[Any]) -> float:
        """Calculate how complete the resolved context is"""
        
        completeness = 0.0
        total_weight = 0.0
        
        # Weight different context types
        weights = [0.4, 0.2, 0.2, 0.1, 0.1]  # Primary, related, conversations, etc.
        
        for i, obj in enumerate(context_objects[:5]):  # Max 5 objects
            weight = weights[i] if i < len(weights) else 0.1
            total_weight += weight
            
            if obj:  # Has content
                if isinstance(obj, list):
                    completeness += weight * min(len(obj) / 3, 1.0)  # Diminishing returns
                elif isinstance(obj, dict):
                    completeness += weight * min(len(obj) / 5, 1.0)
                else:
                    completeness += weight
        
        return completeness / total_weight if total_weight > 0 else 0.0
    
    def _calculate_data_freshness(self, primary_object: Dict[str, Any]) -> float:
        """Calculate how fresh the data is"""
        
        try:
            updated = primary_object.get("updated") or primary_object.get("created")
            if not updated:
                return 0.5  # Unknown freshness
            
            # Parse timestamp (would need proper parsing)
            # For now, assume recent data
            return 1.0
            
        except Exception:
            return 0.5
    
    def _is_cache_valid(self, context: ResolvedContext) -> bool:
        """Check if cached context is still valid"""
        
        # Simple TTL check - could be enhanced with more sophisticated invalidation
        cache_age = (datetime.now() - datetime.fromisoformat(context.event_id.split(":")[-1])).total_seconds()
        return cache_age < self.cache_ttl_seconds
    
    # Additional helper methods for other event types...
    
    async def _get_github_pr_details(self, pr_number: str, repository: str) -> Dict[str, Any]:
        """Get GitHub PR details"""
        # Placeholder - would integrate with GitHub API or memory graph
        return {"number": pr_number, "repository": repository}
    
    async def _find_issues_from_pr(self, pr: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find Jira issues referenced in PR"""
        # Placeholder - would parse PR description for issue keys
        return []
    
    async def _get_pr_conversations(self, pr_number: str, repository: str) -> List[Dict[str, Any]]:
        """Get PR conversation history"""
        return []
    
    async def _get_pr_changed_files(self, pr: Dict[str, Any]) -> List[str]:
        """Get files changed in PR"""
        return []
    
    async def _get_pr_team_context(self, pr: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get team context for PR"""
        return []
    
    async def _get_slack_thread_context(self, channel: str, message_ts: str) -> List[Dict[str, Any]]:
        """Get Slack thread context"""
        return []
    
    async def _get_slack_channel_members(self, channel: str) -> List[Dict[str, Any]]:
        """Get Slack channel team members"""
        return []
    
    async def _find_jira_issues_in_text(self, text: str) -> List[Dict[str, Any]]:
        """Find Jira issue keys mentioned in text"""
        import re
        issue_keys = re.findall(r'\b[A-Z]{2,10}-\d+\b', text)
        # Would resolve each key to full issue details
        return [{"key": key} for key in issue_keys]
    
    # Risk assessment helpers for other event types
    
    def _assess_pr_risk_factors(self, pr: Dict[str, Any]) -> List[str]:
        """Assess PR risk factors"""
        risks = []
        # Would analyze PR size, files changed, etc.
        return risks
    
    def _calculate_pr_complexity(self, pr: Dict[str, Any]) -> float:
        """Calculate PR complexity"""
        # Would analyze lines changed, files modified, etc.
        return 0.5
    
    def _identify_pr_urgency_indicators(self, pr: Dict[str, Any]) -> List[str]:
        """Identify PR urgency indicators"""
        return []
    
    def _assess_slack_risk_factors(self, message: Dict[str, Any]) -> List[str]:
        """Assess Slack message risk factors"""
        return []
    
    def _identify_slack_urgency_indicators(self, message: Dict[str, Any]) -> List[str]:
        """Identify Slack urgency indicators"""
        text = message.get("text", "").lower()
        urgent_keywords = ["urgent", "asap", "emergency", "critical"]
        return [f"keyword_{keyword}" for keyword in urgent_keywords if keyword in text]
    
    def _assess_ci_risk_factors(self, build: Dict[str, Any]) -> List[str]:
        """Assess CI build risk factors"""
        risks = []
        if build.get("failure_type") == "security":
            risks.append("security_failure")
        return risks
    
    def _calculate_ci_complexity(self, build: Dict[str, Any]) -> float:
        """Calculate CI failure complexity"""
        return 0.6  # CI failures are generally moderately complex
    
    def _identify_ci_urgency_indicators(self, build: Dict[str, Any]) -> List[str]:
        """Identify CI urgency indicators"""
        indicators = []
        if build.get("status") == "failed":
            indicators.append("build_failed")
        return indicators
    
    def _assess_deployment_risk_factors(self, deployment: Dict[str, Any]) -> List[str]:
        """Assess deployment risk factors"""
        risks = []
        if deployment.get("environment") == "production":
            risks.append("production_environment")
        return risks
    
    def _identify_deployment_urgency_indicators(self, deployment: Dict[str, Any]) -> List[str]:
        """Identify deployment urgency indicators"""
        indicators = []
        if deployment.get("environment") == "production":
            indicators.append("production_failure")
        return indicators
    
    async def _get_repository_info_from_issue(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get repository info related to an issue"""
        # Would extract from issue links or project configuration
        return None
    
    async def _extract_dependencies_from_issue(self, issue: Dict[str, Any]) -> List[str]:
        """Extract dependencies mentioned in issue"""
        # Would parse description for dependency mentions
        return []
    
    async def _find_pr_for_branch(self, branch: Optional[str], repository: Optional[str]) -> List[Dict[str, Any]]:
        """Find PR for a given branch"""
        # Would query GitHub API or memory graph
        return []

    async def _find_node_id(self, node_type: str, external_id: str) -> Optional[int]:
        """Locate a memory node ID using best-effort search."""
        if not external_id:
            return None
        try:
            results = await self.memory_service.search(
                query=external_id,
                node_types=[node_type],
                limit=1,
            )
        except Exception as e:
            logger.debug(f"Memory search failed for {node_type}:{external_id}: {e}")
            return None
        if not results:
            return None
        return results[0].get("id")

    def _extract_node_meta(self, node: Any) -> Optional[Dict[str, Any]]:
        """Best-effort extraction of meta payloads from memory nodes."""
        if isinstance(node, dict):
            return node.get("meta_json") or node.get("meta")
        return getattr(node, "meta_json", None)

    def _extract_node_text(self, node: Any) -> Optional[str]:
        """Best-effort extraction of text from memory nodes."""
        if isinstance(node, dict):
            return node.get("text")
        return getattr(node, "text", None)

    def _extract_node_created_at(self, node: Any) -> Optional[datetime]:
        """Best-effort extraction of timestamps from memory nodes."""
        if isinstance(node, dict):
            created_at = node.get("created_at")
            if isinstance(created_at, datetime):
                return created_at
            return None
        return getattr(node, "created_at", None)
    
    async def _get_failed_test_files(self, build: Dict[str, Any]) -> List[str]:
        """Get files related to failed tests"""
        # Would parse build logs for test failures
        return []
