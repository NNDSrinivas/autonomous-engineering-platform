"""
RepoRegistry — Org-Wide Repo Awareness

Organizational repository registry that tracks all repos, their types, languages,
ownership, and metadata across the entire organization. This gives NAVI
comprehensive awareness of what exists, not just where it currently operates.

Key Capabilities:
- Track all organizational repositories and their metadata
- Map repository types, languages, and ownership
- Enable discovery of shared libraries and services
- Maintain repository relationships and dependencies
- Support both monorepo and polyrepo architectures
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

class RepoType(Enum):
    """Types of repositories in an organization"""
    SERVICE = "service"  # Microservice or API
    LIBRARY = "library"  # Shared library or SDK
    FRONTEND = "frontend"  # UI application
    MOBILE = "mobile"  # Mobile application
    INFRASTRUCTURE = "infrastructure"  # Terraform, Kubernetes configs
    TOOLING = "tooling"  # Build tools, scripts
    DOCUMENTATION = "documentation"  # Docs, wikis
    MONOREPO = "monorepo"  # Multi-project repository
    TEMPLATE = "template"  # Project templates
    ARCHIVED = "archived"  # Deprecated repositories

@dataclass
class RepoMeta:
    """Comprehensive metadata about a repository"""
    name: str
    full_name: str  # org/repo-name
    repo_type: RepoType
    languages: List[str] = field(default_factory=list)
    primary_language: Optional[str] = None
    owner_team: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    clone_url: Optional[str] = None
    default_branch: str = "main"
    is_private: bool = False
    is_archived: bool = False
    is_fork: bool = False
    topics: List[str] = field(default_factory=list)
    business_domain: Optional[str] = None
    criticality: str = "low"  # low, medium, high, critical
    business_criticality: str = "low"  # Alias for criticality
    sla_tier: Optional[str] = None
    package_managers: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    cloud_services: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    shared_libraries: List[str] = field(default_factory=list)
    deployment_frequency: Optional[str] = None
    last_activity: Optional[datetime] = None
    contributors: List[str] = field(default_factory=list)
    main_contributors: List[str] = field(default_factory=list)
    lines_of_code: Optional[int] = None
    test_coverage: Optional[float] = None
    security_score: Optional[float] = None
    quality_score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    clone_url: Optional[str] = None
    default_branch: str = "main"
    is_private: bool = True
    is_archived: bool = False
    is_fork: bool = False
    topics: List[str] = field(default_factory=list)
    
    # Organizational context
    business_domain: Optional[str] = None  # "auth", "payments", "analytics"
    criticality: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    sla_tier: Optional[str] = None  # "tier1", "tier2", "tier3"
    
    # Technical metadata
    package_managers: List[str] = field(default_factory=list)  # npm, pip, maven, etc.
    frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    cloud_services: List[str] = field(default_factory=list)
    
    # Dependency information
    depends_on: List[str] = field(default_factory=list)  # Direct dependencies
    dependents: List[str] = field(default_factory=list)  # Who depends on this
    shared_libraries: List[str] = field(default_factory=list)
    
    # Operational metadata
    deployment_frequency: Optional[str] = None  # daily, weekly, monthly
    last_activity: Optional[datetime] = None
    contributors: List[str] = field(default_factory=list)
    main_contributors: List[str] = field(default_factory=list)
    
    # Metrics
    lines_of_code: Optional[int] = None
    test_coverage: Optional[float] = None
    security_score: Optional[float] = None
    quality_score: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class RepoRegistry:
    """
    Central registry for all organizational repositories with comprehensive
    metadata, relationships, and discovery capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the repository registry"""
        if db_path is None:
            # Use workspace data directory
            workspace_root = Path(__file__).parent.parent.parent.parent
            data_dir = workspace_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "repo_registry.db")
        
        self.db_path = db_path
        self._init_database()
        logger.info(f"RepoRegistry initialized with database: {db_path}")
    
    def _init_database(self) -> None:
        """Initialize the database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    name TEXT PRIMARY KEY,
                    full_name TEXT UNIQUE NOT NULL,
                    repo_type TEXT NOT NULL,
                    languages TEXT,  -- JSON array
                    primary_language TEXT,
                    owner_team TEXT,
                    description TEXT,
                    url TEXT,
                    clone_url TEXT,
                    default_branch TEXT,
                    is_private BOOLEAN,
                    is_archived BOOLEAN,
                    is_fork BOOLEAN,
                    topics TEXT,  -- JSON array
                    business_domain TEXT,
                    criticality TEXT,
                    sla_tier TEXT,
                    package_managers TEXT,  -- JSON array
                    frameworks TEXT,  -- JSON array
                    databases TEXT,  -- JSON array
                    cloud_services TEXT,  -- JSON array
                    depends_on TEXT,  -- JSON array
                    dependents TEXT,  -- JSON array
                    shared_libraries TEXT,  -- JSON array
                    deployment_frequency TEXT,
                    last_activity DATETIME,
                    contributors TEXT,  -- JSON array
                    main_contributors TEXT,  -- JSON array
                    lines_of_code INTEGER,
                    test_coverage REAL,
                    security_score REAL,
                    quality_score REAL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    metadata TEXT  -- JSON object
                )
            """)
            
            # Indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_type 
                ON repositories (repo_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_owner_team 
                ON repositories (owner_team)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_business_domain 
                ON repositories (business_domain)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_criticality 
                ON repositories (criticality)
            """)
            
            conn.commit()
    
    def register_repo(self, repo: RepoMeta) -> None:
        """
        Register a repository in the registry
        
        Args:
            repo: Repository metadata to register
        """
        repo.updated_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO repositories (
                    name, full_name, repo_type, languages, primary_language, owner_team,
                    description, url, clone_url, default_branch, is_private, is_archived,
                    is_fork, topics, business_domain, criticality, sla_tier,
                    package_managers, frameworks, databases, cloud_services,
                    depends_on, dependents, shared_libraries, deployment_frequency,
                    last_activity, contributors, main_contributors, lines_of_code,
                    test_coverage, security_score, quality_score, created_at,
                    updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                repo.name, repo.full_name, repo.repo_type.value, json.dumps(repo.languages),
                repo.primary_language, repo.owner_team, repo.description, repo.url,
                repo.clone_url, repo.default_branch, repo.is_private, repo.is_archived,
                repo.is_fork, json.dumps(repo.topics), repo.business_domain,
                repo.criticality, repo.sla_tier, json.dumps(repo.package_managers),
                json.dumps(repo.frameworks), json.dumps(repo.databases),
                json.dumps(repo.cloud_services), json.dumps(repo.depends_on),
                json.dumps(repo.dependents), json.dumps(repo.shared_libraries),
                repo.deployment_frequency, 
                repo.last_activity.isoformat() if repo.last_activity else None,
                json.dumps(repo.contributors), json.dumps(repo.main_contributors),
                repo.lines_of_code, repo.test_coverage, repo.security_score,
                repo.quality_score, repo.created_at.isoformat(),
                repo.updated_at.isoformat(), json.dumps(repo.metadata)
            ))
            conn.commit()
        
        logger.info(f"Registered repository: {repo.full_name} ({repo.repo_type.value})")
    
    def get_repo(self, name: str) -> Optional[RepoMeta]:
        """
        Get repository metadata by name
        
        Args:
            name: Repository name or full name
            
        Returns:
            Repository metadata if found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Try both name and full_name
            row = conn.execute(
                "SELECT * FROM repositories WHERE name = ? OR full_name = ?", 
                (name, name)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_repo_meta(row)
    
    async def get_repository(self, name: str) -> Optional[RepoMeta]:
        """
        Async version of get_repo for compatibility
        
        Args:
            name: Repository name or full name
            
        Returns:
            Repository metadata if found
        """
        return self.get_repo(name)
    
    async def list_repositories(self, **kwargs) -> List[RepoMeta]:
        """
        Async version of list_repos for compatibility
        
        Args:
            **kwargs: Same arguments as list_repos method
            
        Returns:
            List of repository metadata
        """
        return self.list_repos(**kwargs)
    
    def list_repos(self, 
                   repo_type: Optional[RepoType] = None,
                   owner_team: Optional[str] = None,
                   business_domain: Optional[str] = None,
                   criticality: Optional[str] = None,
                   archived: bool = False) -> List[RepoMeta]:
        """
        List repositories with optional filtering
        
        Args:
            repo_type: Filter by repository type
            owner_team: Filter by owning team
            business_domain: Filter by business domain
            criticality: Filter by criticality level
            archived: Include archived repositories
            
        Returns:
            List of matching repositories
        """
        query = "SELECT * FROM repositories WHERE 1=1"
        params = []
        
        if repo_type:
            query += " AND repo_type = ?"
            params.append(repo_type.value)
        
        if owner_team:
            query += " AND owner_team = ?"
            params.append(owner_team)
        
        if business_domain:
            query += " AND business_domain = ?"
            params.append(business_domain)
        
        if criticality:
            query += " AND criticality = ?"
            params.append(criticality)
        
        if not archived:
            query += " AND NOT is_archived"
        
        query += " ORDER BY name"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        
        repos = [self._row_to_repo_meta(row) for row in rows]
        logger.info(f"Listed {len(repos)} repositories")
        return repos
    
    def find_dependencies(self, repo_name: str, 
                         include_transitive: bool = False) -> List[str]:
        """
        Find repositories that depend on the given repository
        
        Args:
            repo_name: Name of the repository to find dependencies for
            include_transitive: Whether to include transitive dependencies
            
        Returns:
            List of dependent repository names
        """
        repo = self.get_repo(repo_name)
        if not repo:
            return []
        
        direct_dependents = repo.dependents
        
        if not include_transitive:
            return direct_dependents
        
        # Find transitive dependencies using BFS
        all_dependents = set(direct_dependents)
        to_process = list(direct_dependents)
        
        while to_process:
            current = to_process.pop(0)
            current_repo = self.get_repo(current)
            
            if current_repo:
                for dependent in current_repo.dependents:
                    if dependent not in all_dependents:
                        all_dependents.add(dependent)
                        to_process.append(dependent)
        
        return list(all_dependents)
    
    def find_shared_libraries(self) -> List[RepoMeta]:
        """Find repositories that are shared libraries"""
        return self.list_repos(repo_type=RepoType.LIBRARY)
    
    def find_critical_repos(self) -> List[RepoMeta]:
        """Find repositories marked as critical"""
        return self.list_repos(criticality="CRITICAL")
    
    def get_team_repos(self, team: str) -> List[RepoMeta]:
        """Get all repositories owned by a team"""
        return self.list_repos(owner_team=team)
    
    def get_domain_repos(self, domain: str) -> List[RepoMeta]:
        """Get all repositories in a business domain"""
        return self.list_repos(business_domain=domain)
    
    def update_dependencies(self, repo_name: str, 
                          dependencies: List[str],
                          dependents: List[str]) -> None:
        """
        Update dependency relationships for a repository
        
        Args:
            repo_name: Name of the repository to update
            dependencies: List of repos this repo depends on
            dependents: List of repos that depend on this repo
        """
        repo = self.get_repo(repo_name)
        if not repo:
            logger.warning(f"Repository {repo_name} not found for dependency update")
            return
        
        repo.depends_on = dependencies
        repo.dependents = dependents
        self.register_repo(repo)
        
        logger.info(f"Updated dependencies for {repo_name}: {len(dependencies)} deps, {len(dependents)} dependents")
    
    def get_organization_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the organization's repositories
        
        Returns:
            Dictionary of statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Total counts
            stats["total_repos"] = conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
            stats["active_repos"] = conn.execute("SELECT COUNT(*) FROM repositories WHERE NOT is_archived").fetchone()[0]
            
            # By type
            type_counts = {}
            for repo_type in RepoType:
                count = conn.execute(
                    "SELECT COUNT(*) FROM repositories WHERE repo_type = ? AND NOT is_archived",
                    (repo_type.value,)
                ).fetchone()[0]
                type_counts[repo_type.value] = count
            stats["by_type"] = type_counts
            
            # By language
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT primary_language FROM repositories WHERE NOT is_archived AND primary_language IS NOT NULL").fetchall()
            language_counts = {}
            for row in rows:
                lang = row['primary_language']
                language_counts[lang] = language_counts.get(lang, 0) + 1
            stats["by_language"] = dict(sorted(language_counts.items(), key=lambda x: x[1], reverse=True))
            
            # By criticality
            criticality_counts = {}
            for criticality in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM repositories WHERE criticality = ? AND NOT is_archived",
                    (criticality,)
                ).fetchone()[0]
                criticality_counts[criticality] = count
            stats["by_criticality"] = criticality_counts
        
        return stats
    
    def _row_to_repo_meta(self, row: sqlite3.Row) -> RepoMeta:
        """Convert database row to RepoMeta object"""
        return RepoMeta(
            name=row['name'],
            full_name=row['full_name'],
            repo_type=RepoType(row['repo_type']),
            languages=json.loads(row['languages'] or '[]'),
            primary_language=row['primary_language'],
            owner_team=row['owner_team'],
            description=row['description'],
            url=row['url'],
            clone_url=row['clone_url'],
            default_branch=row['default_branch'] or 'main',
            is_private=bool(row['is_private']),
            is_archived=bool(row['is_archived']),
            is_fork=bool(row['is_fork']),
            topics=json.loads(row['topics'] or '[]'),
            business_domain=row['business_domain'],
            criticality=row['criticality'] or 'MEDIUM',
            sla_tier=row['sla_tier'],
            package_managers=json.loads(row['package_managers'] or '[]'),
            frameworks=json.loads(row['frameworks'] or '[]'),
            databases=json.loads(row['databases'] or '[]'),
            cloud_services=json.loads(row['cloud_services'] or '[]'),
            depends_on=json.loads(row['depends_on'] or '[]'),
            dependents=json.loads(row['dependents'] or '[]'),
            shared_libraries=json.loads(row['shared_libraries'] or '[]'),
            deployment_frequency=row['deployment_frequency'],
            last_activity=datetime.fromisoformat(row['last_activity']) if row['last_activity'] else None,
            contributors=json.loads(row['contributors'] or '[]'),
            main_contributors=json.loads(row['main_contributors'] or '[]'),
            lines_of_code=row['lines_of_code'],
            test_coverage=row['test_coverage'],
            security_score=row['security_score'],
            quality_score=row['quality_score'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            metadata=json.loads(row['metadata'] or '{}')
        )

# Global registry instance
_registry = None

def get_registry() -> RepoRegistry:
    """Get the global repository registry instance"""
    global _registry
    if _registry is None:
        _registry = RepoRegistry()
    return _registry

# Convenience functions
def register_repo(repo: RepoMeta) -> None:
    """Register a repository in the global registry"""
    get_registry().register_repo(repo)

def list_repos(**kwargs) -> List[RepoMeta]:
    """List repositories from the global registry"""
    return get_registry().list_repos(**kwargs)