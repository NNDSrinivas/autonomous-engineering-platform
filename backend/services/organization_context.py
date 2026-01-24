"""
Multi-Tenant Organization Context System for NAVI

Enables NAVI to adapt to different organizations, teams, and individual users:
1. Organization-level coding standards
2. Team-specific patterns and conventions
3. Personal preferences
4. Project-specific context from codebase analysis

This is the foundation for a SaaS product serving:
- Large enterprises with multiple teams
- Small companies
- Individual developers

Hierarchy: Organization > Team > Project > User
Each level can override or extend the parent level.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ContextLevel(Enum):
    """Hierarchy of context levels."""

    GLOBAL = "global"  # NAVI defaults
    ORGANIZATION = "organization"  # Company-wide standards
    TEAM = "team"  # Team-specific patterns
    PROJECT = "project"  # Project conventions (auto-detected)
    USER = "user"  # Individual preferences


@dataclass
class CodingStandard:
    """A single coding standard/convention."""

    id: str
    name: str
    description: str
    language: Optional[str] = None  # None means applies to all
    framework: Optional[str] = None
    rule: str = ""  # The actual rule/pattern
    examples: List[str] = field(default_factory=list)
    anti_examples: List[str] = field(default_factory=list)  # What NOT to do
    source: str = ""  # Where this standard came from (doc, review, etc.)
    level: ContextLevel = ContextLevel.ORGANIZATION
    enabled: bool = True

    def to_prompt_context(self) -> str:
        """Convert to prompt context string."""
        parts = [f"**{self.name}**"]
        if self.description:
            parts.append(f"  {self.description}")
        if self.rule:
            parts.append(f"  Rule: {self.rule}")
        if self.examples:
            parts.append(f"  Example: {self.examples[0]}")
        if self.anti_examples:
            parts.append(f"  Avoid: {self.anti_examples[0]}")
        return "\n".join(parts)


@dataclass
class ArchitecturePattern:
    """An architectural pattern or decision."""

    id: str
    name: str
    description: str
    pattern_type: str  # "layered", "microservice", "monolith", "event-driven", etc.
    components: List[str] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)
    file_structure: Dict[str, str] = field(
        default_factory=dict
    )  # path pattern -> purpose
    level: ContextLevel = ContextLevel.ORGANIZATION


@dataclass
class CodeReviewInsight:
    """Insight learned from code reviews."""

    id: str
    pattern: str  # What was flagged
    feedback: str  # What the reviewer said
    correction: str  # How it should be done
    frequency: int = 1  # How often this comes up
    language: Optional[str] = None
    reviewer: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrganizationContext:
    """Complete context for an organization."""

    org_id: str
    name: str
    coding_standards: List[CodingStandard] = field(default_factory=list)
    architecture_patterns: List[ArchitecturePattern] = field(default_factory=list)
    review_insights: List[CodeReviewInsight] = field(default_factory=list)

    # Language/framework preferences
    preferred_languages: List[str] = field(default_factory=list)
    preferred_frameworks: Dict[str, List[str]] = field(
        default_factory=dict
    )  # lang -> frameworks

    # Style preferences
    indent_style: str = "spaces"
    indent_size: int = 4
    quote_style: str = "double"  # or "single"
    semicolons: bool = True  # for JS/TS
    naming_conventions: Dict[str, str] = field(
        default_factory=dict
    )  # type -> convention

    # Documentation requirements
    require_docstrings: bool = True
    docstring_style: str = "google"  # google, numpy, sphinx
    require_type_hints: bool = True

    # Testing requirements
    min_test_coverage: int = 80
    test_framework: Optional[str] = None

    # Security policies
    security_scan_required: bool = True
    allowed_dependencies: List[str] = field(default_factory=list)  # Whitelist
    blocked_dependencies: List[str] = field(default_factory=list)  # Blacklist

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_prompt_context(self) -> str:
        """Generate prompt context string for this organization."""
        lines = [f"=== ORGANIZATION CONTEXT: {self.name} ===\n"]

        # Coding standards
        if self.coding_standards:
            lines.append("**Coding Standards:**")
            for std in self.coding_standards[:10]:  # Limit to top 10
                if std.enabled:
                    lines.append(std.to_prompt_context())
            lines.append("")

        # Style preferences
        lines.append("**Code Style:**")
        lines.append(f"- Indentation: {self.indent_size} {self.indent_style}")
        lines.append(f"- Quotes: {self.quote_style}")
        if self.naming_conventions:
            for typ, conv in self.naming_conventions.items():
                lines.append(f"- {typ}: {conv}")
        lines.append("")

        # Architecture patterns
        if self.architecture_patterns:
            lines.append("**Architecture:**")
            for pattern in self.architecture_patterns[:3]:
                lines.append(f"- {pattern.name}: {pattern.description}")
            lines.append("")

        # Common review feedback (top issues)
        if self.review_insights:
            top_insights = sorted(
                self.review_insights, key=lambda x: x.frequency, reverse=True
            )[:5]
            lines.append("**Common Review Feedback (avoid these):**")
            for insight in top_insights:
                lines.append(f"- {insight.pattern} → {insight.correction}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class TeamContext:
    """Team-specific context that extends organization context."""

    team_id: str
    org_id: str
    name: str

    # Team can override org settings
    coding_standards: List[CodingStandard] = field(default_factory=list)
    architecture_patterns: List[ArchitecturePattern] = field(default_factory=list)
    review_insights: List[CodeReviewInsight] = field(default_factory=list)

    # Team-specific preferences
    preferred_languages: List[str] = field(default_factory=list)
    preferred_frameworks: Dict[str, List[str]] = field(default_factory=dict)

    # Team tech stack
    tech_stack: List[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Generate prompt context for this team."""
        lines = [f"=== TEAM CONTEXT: {self.name} ===\n"]

        if self.tech_stack:
            lines.append(f"**Tech Stack:** {', '.join(self.tech_stack)}")

        if self.coding_standards:
            lines.append("\n**Team-Specific Standards:**")
            for std in self.coding_standards[:5]:
                if std.enabled:
                    lines.append(std.to_prompt_context())

        if self.review_insights:
            lines.append("\n**Team Review Patterns:**")
            for insight in self.review_insights[:3]:
                lines.append(f"- {insight.pattern} → {insight.correction}")

        return "\n".join(lines)


@dataclass
class UserPreferences:
    """Individual user preferences."""

    user_id: str
    org_id: Optional[str] = None
    team_id: Optional[str] = None

    # Personal style preferences
    verbose_explanations: bool = True
    auto_apply_changes: bool = False  # Require confirmation
    preferred_languages: List[str] = field(default_factory=list)

    # Learned patterns from this user's code
    personal_patterns: List[str] = field(default_factory=list)

    # Feedback history
    accepted_suggestions: int = 0
    rejected_suggestions: int = 0
    modified_suggestions: int = 0


# ============================================================
# CONTEXT STORAGE AND RETRIEVAL
# ============================================================


class ContextStore:
    """
    Storage for organization, team, and user contexts.

    In production, this would be backed by a database.
    For now, uses file-based storage with optional Redis caching.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(
            storage_path
            or os.getenv("NAVI_CONTEXT_PATH", os.path.expanduser("~/.navi/contexts"))
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._org_cache: Dict[str, OrganizationContext] = {}
        self._team_cache: Dict[str, TeamContext] = {}
        self._user_cache: Dict[str, UserPreferences] = {}

    def _get_org_path(self, org_id: str) -> Path:
        return self.storage_path / "orgs" / f"{org_id}.json"

    def _get_team_path(self, team_id: str) -> Path:
        return self.storage_path / "teams" / f"{team_id}.json"

    def _get_user_path(self, user_id: str) -> Path:
        return self.storage_path / "users" / f"{user_id}.json"

    # Organization methods
    def save_organization(self, org: OrganizationContext) -> None:
        """Save organization context."""
        org.updated_at = datetime.now()
        path = self._get_org_path(org.org_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON-serializable format
        data = self._to_serializable(asdict(org))
        path.write_text(json.dumps(data, indent=2, default=str))

        self._org_cache[org.org_id] = org
        logger.info(f"Saved organization context: {org.org_id}")

    def get_organization(self, org_id: str) -> Optional[OrganizationContext]:
        """Get organization context."""
        if org_id in self._org_cache:
            return self._org_cache[org_id]

        path = self._get_org_path(org_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            org = self._from_org_dict(data)
            self._org_cache[org_id] = org
            return org
        except Exception as e:
            logger.error(f"Error loading organization {org_id}: {e}")
            return None

    # Team methods
    def save_team(self, team: TeamContext) -> None:
        """Save team context."""
        path = self._get_team_path(team.team_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self._to_serializable(asdict(team))
        path.write_text(json.dumps(data, indent=2, default=str))

        self._team_cache[team.team_id] = team
        logger.info(f"Saved team context: {team.team_id}")

    def get_team(self, team_id: str) -> Optional[TeamContext]:
        """Get team context."""
        if team_id in self._team_cache:
            return self._team_cache[team_id]

        path = self._get_team_path(team_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            team = self._from_team_dict(data)
            self._team_cache[team_id] = team
            return team
        except Exception as e:
            logger.error(f"Error loading team {team_id}: {e}")
            return None

    # User methods
    def save_user(self, user: UserPreferences) -> None:
        """Save user preferences."""
        path = self._get_user_path(user.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = self._to_serializable(asdict(user))
        path.write_text(json.dumps(data, indent=2, default=str))

        self._user_cache[user.user_id] = user

    def get_user(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        path = self._get_user_path(user_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            user = UserPreferences(**data)
            self._user_cache[user_id] = user
            return user
        except Exception as e:
            logger.error(f"Error loading user {user_id}: {e}")
            return None

    def _to_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_serializable(v) for v in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        return obj

    def _from_org_dict(self, data: Dict) -> OrganizationContext:
        """Reconstruct OrganizationContext from dict."""
        # Handle nested objects
        coding_standards = [
            CodingStandard(**std) for std in data.get("coding_standards", [])
        ]
        architecture_patterns = [
            ArchitecturePattern(**pat) for pat in data.get("architecture_patterns", [])
        ]
        review_insights = [
            CodeReviewInsight(**ins) for ins in data.get("review_insights", [])
        ]

        return OrganizationContext(
            org_id=data["org_id"],
            name=data["name"],
            coding_standards=coding_standards,
            architecture_patterns=architecture_patterns,
            review_insights=review_insights,
            preferred_languages=data.get("preferred_languages", []),
            preferred_frameworks=data.get("preferred_frameworks", {}),
            indent_style=data.get("indent_style", "spaces"),
            indent_size=data.get("indent_size", 4),
            quote_style=data.get("quote_style", "double"),
            semicolons=data.get("semicolons", True),
            naming_conventions=data.get("naming_conventions", {}),
            require_docstrings=data.get("require_docstrings", True),
            docstring_style=data.get("docstring_style", "google"),
            require_type_hints=data.get("require_type_hints", True),
            min_test_coverage=data.get("min_test_coverage", 80),
            test_framework=data.get("test_framework"),
            security_scan_required=data.get("security_scan_required", True),
            allowed_dependencies=data.get("allowed_dependencies", []),
            blocked_dependencies=data.get("blocked_dependencies", []),
        )

    def _from_team_dict(self, data: Dict) -> TeamContext:
        """Reconstruct TeamContext from dict."""
        coding_standards = [
            CodingStandard(**std) for std in data.get("coding_standards", [])
        ]
        architecture_patterns = [
            ArchitecturePattern(**pat) for pat in data.get("architecture_patterns", [])
        ]
        review_insights = [
            CodeReviewInsight(**ins) for ins in data.get("review_insights", [])
        ]

        return TeamContext(
            team_id=data["team_id"],
            org_id=data["org_id"],
            name=data["name"],
            coding_standards=coding_standards,
            architecture_patterns=architecture_patterns,
            review_insights=review_insights,
            preferred_languages=data.get("preferred_languages", []),
            preferred_frameworks=data.get("preferred_frameworks", {}),
            tech_stack=data.get("tech_stack", []),
        )


# ============================================================
# CONTEXT RESOLVER - Merges all levels
# ============================================================


class ContextResolver:
    """
    Resolves the final context by merging:
    Organization > Team > Project > User

    Lower levels can override higher levels.
    """

    def __init__(self, store: ContextStore = None):
        self.store = store or ContextStore()

    def resolve(
        self,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_context: Optional[Dict] = None,
    ) -> str:
        """
        Resolve and merge all context levels into a prompt string.
        """
        context_parts = []

        # Organization level
        if org_id:
            org = self.store.get_organization(org_id)
            if org:
                context_parts.append(org.to_prompt_context())

        # Team level (extends/overrides org)
        if team_id:
            team = self.store.get_team(team_id)
            if team:
                context_parts.append(team.to_prompt_context())

        # Project level (auto-detected from codebase)
        if project_context:
            context_parts.append(self._format_project_context(project_context))

        # User level
        if user_id:
            user = self.store.get_user(user_id)
            if user:
                context_parts.append(self._format_user_context(user))

        return "\n\n".join(context_parts)

    def _format_project_context(self, ctx: Dict) -> str:
        """Format auto-detected project context."""
        lines = ["=== PROJECT CONTEXT (auto-detected) ==="]

        if ctx.get("languages"):
            lines.append(f"Languages: {', '.join(ctx['languages'])}")
        if ctx.get("frameworks"):
            lines.append(f"Frameworks: {', '.join(ctx['frameworks'])}")
        if ctx.get("detected_style"):
            lines.append(f"Detected Style: {ctx['detected_style']}")

        return "\n".join(lines)

    def _format_user_context(self, user: UserPreferences) -> str:
        """Format user preferences."""
        lines = ["=== USER PREFERENCES ==="]

        if user.preferred_languages:
            lines.append(f"Preferred languages: {', '.join(user.preferred_languages)}")
        if user.verbose_explanations:
            lines.append("Prefers detailed explanations")
        if not user.auto_apply_changes:
            lines.append("Requires confirmation before applying changes")

        return "\n".join(lines)


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_context_store: Optional[ContextStore] = None
_context_resolver: Optional[ContextResolver] = None


def get_context_store() -> ContextStore:
    """Get the global context store."""
    global _context_store
    if _context_store is None:
        _context_store = ContextStore()
    return _context_store


def get_context_resolver() -> ContextResolver:
    """Get the global context resolver."""
    global _context_resolver
    if _context_resolver is None:
        _context_resolver = ContextResolver(get_context_store())
    return _context_resolver


def resolve_context(
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    project_context: Optional[Dict] = None,
) -> str:
    """Convenience function to resolve context."""
    return get_context_resolver().resolve(org_id, team_id, user_id, project_context)
