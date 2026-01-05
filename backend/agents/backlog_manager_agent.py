"""
Backlog Manager + Priority Engine

This agent behaves like a product owner, triage engineer, and project coordinator:
- Creates and manages backlog items
- Assigns intelligent priority based on business value, risk, and dependencies
- Reorders tasks automatically based on changing conditions
- Merges duplicates and detects blockers
- Auto-closes stale items and suggests new ones
- Detects technical debt and creates remediation tasks
"""

import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..core.config import get_settings
    from .sprint_planner_agent import BacklogItem
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.core.config import get_settings
    from backend.agents.sprint_planner_agent import BacklogItem


class Priority(Enum):
    """Priority levels for backlog items."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKLOG = 5


class ItemType(Enum):
    """Types of backlog items."""

    FEATURE = "feature"
    BUG = "bug"
    TECHNICAL_DEBT = "tech_debt"
    CHORE = "chore"
    EPIC = "epic"
    SPIKE = "spike"


@dataclass
class PriorityScore:
    """Detailed priority scoring breakdown."""

    business_value: float
    technical_impact: float
    risk_factor: float
    dependency_weight: float
    urgency: float
    final_score: float
    reasoning: str


@dataclass
class BacklogAnalysis:
    """Complete backlog analysis result."""

    total_items: int
    priority_distribution: Dict[str, int]
    estimated_capacity_weeks: float
    technical_debt_percentage: float
    duplicate_candidates: List[Tuple[str, str]]
    stale_items: List[str]
    blocking_items: List[str]
    recommendations: List[str]


class BacklogManagerAgent:
    """
    Intelligent Backlog Manager that acts like a senior product owner.
    Handles backlog prioritization, duplicate detection, capacity planning, and technical debt tracking.
    """

    def __init__(self):
        """Initialize the Backlog Manager Agent."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.settings = get_settings()

        # Backlog management parameters
        self.stale_threshold_days = 90
        self.similarity_threshold = 0.8
        self.max_backlog_size = 200
        self.technical_debt_threshold = 0.25  # 25%

    async def analyze_backlog(
        self, backlog_items: List[BacklogItem]
    ) -> BacklogAnalysis:
        """
        Perform comprehensive backlog analysis with recommendations.

        Args:
            backlog_items: List of backlog items to analyze

        Returns:
            Complete analysis with insights and recommendations
        """

        # Basic metrics
        total_items = len(backlog_items)
        priority_dist = self._calculate_priority_distribution(backlog_items)
        estimated_weeks = self._estimate_capacity_weeks(backlog_items)
        tech_debt_pct = self._calculate_technical_debt_percentage(backlog_items)

        # Find duplicates
        duplicates = await self._find_duplicate_items(backlog_items)

        # Identify stale items
        stale_items = self._find_stale_items(backlog_items)

        # Find blocking items
        blocking_items = self._find_blocking_items(backlog_items)

        # Generate recommendations
        recommendations = await self._generate_backlog_recommendations(
            backlog_items, tech_debt_pct, len(duplicates), len(stale_items)
        )

        return BacklogAnalysis(
            total_items=total_items,
            priority_distribution=priority_dist,
            estimated_capacity_weeks=estimated_weeks,
            technical_debt_percentage=tech_debt_pct,
            duplicate_candidates=duplicates,
            stale_items=stale_items,
            blocking_items=blocking_items,
            recommendations=recommendations,
        )

    async def rank_backlog(
        self,
        backlog_items: List[BacklogItem],
        business_context: Optional[Dict[str, Any]] = None,
        team_velocity: Optional[float] = None,
    ) -> List[Tuple[BacklogItem, PriorityScore]]:
        """
        Intelligently rank backlog items by comprehensive scoring.

        Args:
            backlog_items: Items to rank
            business_context: Current business priorities and constraints
            team_velocity: Team's current velocity for capacity planning

        Returns:
            List of (item, score) tuples sorted by priority
        """

        ranking_prompt = f"""
        You are Navi-ProductOwner, an elite product management AI with deep engineering insight.
        
        Rank these backlog items by comprehensive priority scoring:
        
        BACKLOG ITEMS:
        {json.dumps([asdict(item) for item in backlog_items], indent=2, default=str)}
        
        BUSINESS CONTEXT:
        {json.dumps(business_context or {}, indent=2)}
        
        TEAM VELOCITY: {team_velocity or 'Unknown'}
        
        For each item, provide detailed scoring (0-10 scale):
        
        1. **Business Value**: Revenue impact, user satisfaction, strategic alignment
        2. **Technical Impact**: Code quality improvement, performance, maintainability  
        3. **Risk Factor**: Implementation complexity, dependencies, unknowns
        4. **Urgency**: Time sensitivity, competitive pressure, compliance needs
        5. **Dependencies**: How this enables/blocks other work
        
        Calculate FINAL PRIORITY SCORE using this weighted formula:
        Final = (BusinessValue × 0.35) + (TechnicalImpact × 0.25) + (Urgency × 0.20) + 
                (10-RiskFactor × 0.15) + (DependencyWeight × 0.05)
        
        Return JSON array with this structure:
        [
            {{
                "item_id": "...",
                "business_value": 8.5,
                "technical_impact": 7.0,
                "risk_factor": 4.0,
                "urgency": 6.5,
                "dependency_weight": 8.0,
                "final_score": 7.2,
                "reasoning": "Detailed explanation of scoring decisions",
                "recommended_priority": "CRITICAL|HIGH|MEDIUM|LOW|BACKLOG"
            }},
            ...
        ]
        
        Sort by final_score DESC (highest priority first).
        """

        try:
            response = await self.llm.run(prompt=ranking_prompt, use_smart_auto=True)
            ranking_data = json.loads(response.text)

            # Create scored items
            ranked_items = []

            for score_data in ranking_data:
                # Find corresponding item
                item = next(
                    (
                        item
                        for item in backlog_items
                        if item.id == score_data["item_id"]
                    ),
                    None,
                )
                if item:
                    priority_score = PriorityScore(
                        business_value=score_data["business_value"],
                        technical_impact=score_data["technical_impact"],
                        risk_factor=score_data["risk_factor"],
                        dependency_weight=score_data["dependency_weight"],
                        urgency=score_data["urgency"],
                        final_score=score_data["final_score"],
                        reasoning=score_data["reasoning"],
                    )

                    # Update item priority based on recommendation
                    priority_map = {
                        "CRITICAL": 1,
                        "HIGH": 2,
                        "MEDIUM": 3,
                        "LOW": 4,
                        "BACKLOG": 5,
                    }
                    item.priority = priority_map.get(
                        score_data["recommended_priority"], 3
                    )

                    ranked_items.append((item, priority_score))

            # Sort by final score
            ranked_items.sort(key=lambda x: x[1].final_score, reverse=True)

            return ranked_items

        except Exception:
            # Fallback ranking
            return self._fallback_ranking(backlog_items)

    async def create_backlog_item(
        self,
        title: str,
        description: str,
        item_type: ItemType = ItemType.FEATURE,
        auto_prioritize: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> BacklogItem:
        """
        Create a new backlog item with intelligent auto-prioritization.

        Args:
            title: Item title
            description: Detailed description
            item_type: Type of backlog item
            auto_prioritize: Whether to auto-calculate priority
            context: Additional context for prioritization

        Returns:
            Created backlog item with estimated priority and complexity
        """

        # Generate unique ID
        item_id = hashlib.md5(
            f"{title}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        if auto_prioritize:
            # Get AI estimation
            estimation_prompt = f"""
            You are Navi-Estimator, an expert at sizing and prioritizing engineering work.
            
            Analyze this new backlog item and provide estimates:
            
            ITEM DETAILS:
            Title: {title}
            Description: {description}
            Type: {item_type.value}
            Context: {json.dumps(context or {})}
            
            Provide estimates for:
            1. **Story Points** (1, 2, 3, 5, 8, 13, 21)
            2. **Complexity** (low, medium, high)
            3. **Business Value** (1-10)
            4. **Technical Risk** (1-10)
            5. **Priority Level** (1-5, where 1=Critical, 5=Backlog)
            6. **Estimated Hours** (realistic development time)
            7. **Dependencies** (what this item depends on)
            8. **Tags** (relevant labels/categories)
            
            Return JSON with your analysis:
            {{
                "story_points": 5,
                "complexity": "medium",
                "business_value": 7,
                "technical_risk": 3,
                "priority": 2,
                "estimated_hours": 16.0,
                "dependencies": ["item_123", "api_redesign"],
                "tags": ["frontend", "user-experience"],
                "reasoning": "Explanation of estimates"
            }}
            """

            try:
                response = await self.llm.run(
                    prompt=estimation_prompt, use_smart_auto=True
                )
                estimates = json.loads(response.text)

                # Create item with estimates
                item = BacklogItem(
                    id=item_id,
                    title=title,
                    description=description,
                    story_points=estimates["story_points"],
                    priority=estimates["priority"],
                    tags=estimates.get("tags", []),
                    dependencies=estimates.get("dependencies", []),
                    estimated_hours=estimates.get("estimated_hours"),
                    complexity=estimates["complexity"],
                    business_value=estimates["business_value"],
                    technical_risk=estimates["technical_risk"],
                )

            except Exception:
                # Fallback estimates
                item = BacklogItem(
                    id=item_id,
                    title=title,
                    description=description,
                    story_points=5,
                    priority=3,
                    complexity="medium",
                    business_value=5,
                    technical_risk=3,
                )
        else:
            # Create basic item
            item = BacklogItem(id=item_id, title=title, description=description)

        # Save to database
        await self._save_backlog_item(item)

        return item

    async def merge_duplicate_items(
        self, item_ids: List[str], merge_strategy: str = "smart"
    ) -> BacklogItem:
        """
        Merge duplicate backlog items intelligently.

        Args:
            item_ids: IDs of items to merge
            merge_strategy: How to merge (smart, first_wins, highest_priority)

        Returns:
            Merged backlog item
        """

        # Load items
        items = []
        for item_id in item_ids:
            item = await self._load_backlog_item(item_id)
            if item:
                items.append(item)

        if len(items) < 2:
            raise ValueError("Need at least 2 items to merge")

        if merge_strategy == "smart":
            # Use LLM to intelligently merge
            merge_prompt = f"""
            You are Navi-ItemMerger, expert at combining duplicate backlog items.
            
            Merge these duplicate items into one comprehensive item:
            
            ITEMS TO MERGE:
            {json.dumps([asdict(item) for item in items], indent=2, default=str)}
            
            Create a merged item that:
            1. Combines the best aspects of each description
            2. Uses the highest business value and lowest risk
            3. Merges all relevant tags and dependencies
            4. Chooses appropriate story points (not just sum)
            5. Creates comprehensive acceptance criteria
            
            Return JSON with the merged item structure.
            """

            try:
                response = await self.llm.run(prompt=merge_prompt, use_smart_auto=True)
                merged_data = json.loads(response.text)

                # Create merged item
                merged_item = BacklogItem(
                    id=f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    title=merged_data.get("title", items[0].title),
                    description=merged_data.get("description", items[0].description),
                    story_points=merged_data.get(
                        "story_points", max(item.story_points or 0 for item in items)
                    ),
                    priority=min(
                        item.priority for item in items
                    ),  # Highest priority (lowest number)
                    tags=list(
                        set(sum([item.tags for item in items], []))
                    ),  # Merge all tags
                    dependencies=list(
                        set(sum([item.dependencies for item in items], []))
                    ),
                    business_value=max(item.business_value for item in items),
                    technical_risk=max(item.technical_risk for item in items),
                    complexity=merged_data.get("complexity", "medium"),
                )

            except Exception:
                # Fallback merge
                merged_item = items[0]  # Use first item as base
                merged_item.id = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                merged_item.description += "\n\n" + "\n".join(
                    [f"Merged from: {item.title}" for item in items[1:]]
                )

        else:
            # Simple merge strategies
            if merge_strategy == "first_wins":
                merged_item = items[0]
            elif merge_strategy == "highest_priority":
                merged_item = min(items, key=lambda x: x.priority)
            else:
                merged_item = items[0]

            merged_item.id = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Save merged item and delete originals
        await self._save_backlog_item(merged_item)
        for item_id in item_ids:
            await self._delete_backlog_item(item_id)

        return merged_item

    async def cleanup_stale_items(
        self, max_age_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Automatically close or archive stale backlog items.

        Args:
            max_age_days: Maximum age before item is considered stale

        Returns:
            Cleanup report with actions taken
        """

        age_threshold = max_age_days or self.stale_threshold_days
        cutoff_date = datetime.now() - timedelta(days=age_threshold)

        # Find stale items
        stale_items = await self._find_stale_items_by_date(cutoff_date)

        cleanup_prompt = f"""
        You are Navi-Curator, responsible for maintaining backlog hygiene.
        
        Analyze these stale backlog items and recommend actions:
        
        STALE ITEMS (older than {age_threshold} days):
        {json.dumps(stale_items, indent=2, default=str)}
        
        For each item, recommend:
        - CLOSE: No longer relevant/needed
        - ARCHIVE: Keep for reference but remove from active backlog  
        - REFRESH: Update and keep in backlog
        - MERGE: Combine with another item
        
        Return JSON with recommendations and reasoning.
        """

        try:
            response = await self.llm.run(prompt=cleanup_prompt, use_smart_auto=True)
            cleanup_plan = json.loads(response.text)

            actions_taken = {"closed": 0, "archived": 0, "refreshed": 0, "merged": 0}

            # Execute cleanup actions
            for action in cleanup_plan.get("actions", []):
                item_id = action["item_id"]
                action_type = action["action"].lower()

                if action_type == "close":
                    await self._delete_backlog_item(item_id)
                    actions_taken["closed"] += 1
                elif action_type == "archive":
                    await self._archive_backlog_item(item_id)
                    actions_taken["archived"] += 1
                # Add other action implementations as needed

            return {
                "stale_items_found": len(stale_items),
                "actions_taken": actions_taken,
                "cleanup_plan": cleanup_plan,
            }

        except Exception as e:
            return {"error": f"Cleanup failed: {str(e)}"}

    def _calculate_priority_distribution(
        self, items: List[BacklogItem]
    ) -> Dict[str, int]:
        """Calculate distribution of priorities in backlog."""
        dist = {"critical": 0, "high": 0, "medium": 0, "low": 0, "backlog": 0}
        priority_map = {1: "critical", 2: "high", 3: "medium", 4: "low", 5: "backlog"}

        for item in items:
            priority_name = priority_map.get(item.priority, "medium")
            dist[priority_name] += 1

        return dist

    def _estimate_capacity_weeks(self, items: List[BacklogItem]) -> float:
        """Estimate total capacity needed in weeks."""
        total_points = sum(item.story_points or 5 for item in items)
        # Assume team velocity of 20 points per 2-week sprint = 10 points per week
        return total_points / 10.0

    def _calculate_technical_debt_percentage(self, items: List[BacklogItem]) -> float:
        """Calculate percentage of backlog that is technical debt."""
        if not items:
            return 0.0

        tech_debt_items = sum(
            1
            for item in items
            if "tech" in item.title.lower()
            or "debt" in item.title.lower()
            or "refactor" in item.title.lower()
        )
        return (tech_debt_items / len(items)) * 100

    async def _find_duplicate_items(
        self, items: List[BacklogItem]
    ) -> List[Tuple[str, str]]:
        """Find potential duplicate items using similarity detection."""
        duplicates = []

        for i, item1 in enumerate(items):
            for item2 in items[i + 1 :]:
                # Simple similarity check (can be enhanced with embeddings)
                similarity = self._calculate_text_similarity(
                    item1.title + " " + item1.description,
                    item2.title + " " + item2.description,
                )
                if similarity > self.similarity_threshold:
                    duplicates.append((item1.id, item2.id))

        return duplicates

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity (can be enhanced with embeddings)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _find_stale_items(self, items: List[BacklogItem]) -> List[str]:
        """Find items that haven't been updated recently."""
        cutoff_date = datetime.now() - timedelta(days=self.stale_threshold_days)
        return [
            item.id
            for item in items
            if item.created_at and item.created_at < cutoff_date
        ]

    def _find_blocking_items(self, items: List[BacklogItem]) -> List[str]:
        """Find items that are blocking other items."""
        item_ids = {item.id for item in items}
        blocking_ids = set()

        for item in items:
            if item.dependencies:
                for dep in item.dependencies:
                    if dep in item_ids:
                        blocking_ids.add(dep)

        return list(blocking_ids)

    async def _generate_backlog_recommendations(
        self,
        items: List[BacklogItem],
        tech_debt_pct: float,
        duplicate_count: int,
        stale_count: int,
    ) -> List[str]:
        """Generate intelligent backlog management recommendations."""

        recommendations = []

        if tech_debt_pct > self.technical_debt_threshold * 100:
            recommendations.append(
                f"High technical debt detected ({tech_debt_pct:.1f}%). Consider dedicating 20% of sprint capacity to tech debt."
            )

        if duplicate_count > 0:
            recommendations.append(
                f"Found {duplicate_count} potential duplicate items. Review and merge to reduce backlog noise."
            )

        if stale_count > 0:
            recommendations.append(
                f"Found {stale_count} stale items. Run cleanup to maintain backlog hygiene."
            )

        if len(items) > self.max_backlog_size:
            recommendations.append(
                f"Backlog size ({len(items)}) exceeds recommended maximum ({self.max_backlog_size}). Consider archiving low-priority items."
            )

        return recommendations

    def _fallback_ranking(
        self, items: List[BacklogItem]
    ) -> List[Tuple[BacklogItem, PriorityScore]]:
        """Fallback ranking when LLM fails."""
        ranked = []

        for item in items:
            score = PriorityScore(
                business_value=item.business_value,
                technical_impact=5.0,  # Default
                risk_factor=item.technical_risk,
                dependency_weight=len(item.dependencies or []) * 2,
                urgency=6.0 - item.priority,  # Convert priority to urgency
                final_score=item.business_value * 0.4 + (6.0 - item.priority) * 0.6,
                reasoning="Fallback scoring based on available data",
            )
            ranked.append((item, score))

        # Sort by final score
        ranked.sort(key=lambda x: x[1].final_score, reverse=True)
        return ranked

    async def _save_backlog_item(self, item: BacklogItem) -> None:
        """Save backlog item to database."""
        try:
            query = """
            INSERT OR REPLACE INTO backlog_items 
            (id, title, description, story_points, priority, tags, dependencies, 
             assigned_to, estimated_hours, complexity, business_value, technical_risk, 
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            await self.db.execute(
                query,
                [
                    item.id,
                    item.title,
                    item.description,
                    item.story_points,
                    item.priority,
                    json.dumps(item.tags),
                    json.dumps(item.dependencies),
                    item.assigned_to,
                    item.estimated_hours,
                    item.complexity,
                    item.business_value,
                    item.technical_risk,
                    (item.created_at.isoformat() if item.created_at else "unknown"),
                    datetime.now().isoformat(),
                ],
            )

        except Exception:
            # Create table if doesn't exist
            create_query = """
            CREATE TABLE IF NOT EXISTS backlog_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                story_points INTEGER,
                priority INTEGER,
                tags TEXT,
                dependencies TEXT,
                assigned_to TEXT,
                estimated_hours REAL,
                complexity TEXT,
                business_value INTEGER,
                technical_risk INTEGER,
                created_at TEXT,
                updated_at TEXT,
                archived BOOLEAN DEFAULT 0
            )
            """
            await self.db.execute(create_query, [])
            # Retry insert
            await self.db.execute(
                query,
                [
                    item.id,
                    item.title,
                    item.description,
                    item.story_points,
                    item.priority,
                    json.dumps(item.tags),
                    json.dumps(item.dependencies),
                    item.assigned_to,
                    item.estimated_hours,
                    item.complexity,
                    item.business_value,
                    item.technical_risk,
                    (item.created_at.isoformat() if item.created_at else "unknown"),
                    datetime.now().isoformat(),
                ],
            )

    async def _load_backlog_item(self, item_id: str) -> Optional[BacklogItem]:
        """Load backlog item from database."""
        try:
            query = "SELECT * FROM backlog_items WHERE id = ? AND archived = 0"
            result = await self.db.fetch_one(query, [item_id])

            if result:
                return BacklogItem(
                    id=result["id"],
                    title=result["title"],
                    description=result["description"],
                    story_points=result["story_points"],
                    priority=result["priority"],
                    tags=json.loads(result["tags"] or "[]"),
                    dependencies=json.loads(result["dependencies"] or "[]"),
                    assigned_to=result["assigned_to"],
                    estimated_hours=result["estimated_hours"],
                    complexity=result["complexity"],
                    business_value=result["business_value"],
                    technical_risk=result["technical_risk"],
                    created_at=(
                        datetime.fromisoformat(result["created_at"])
                        if result["created_at"]
                        else None
                    ),
                )
            return None

        except Exception:
            return None

    async def _delete_backlog_item(self, item_id: str) -> None:
        """Delete backlog item from database."""
        try:
            query = "DELETE FROM backlog_items WHERE id = ?"
            await self.db.execute(query, [item_id])
        except Exception:
            pass

    async def _archive_backlog_item(self, item_id: str) -> None:
        """Archive backlog item."""
        try:
            query = "UPDATE backlog_items SET archived = 1, updated_at = ? WHERE id = ?"
            await self.db.execute(query, [datetime.now().isoformat(), item_id])
        except Exception:
            pass

    async def _find_stale_items_by_date(
        self, cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Find stale items by date."""
        try:
            query = """
            SELECT * FROM backlog_items 
            WHERE created_at < ? AND archived = 0 
            ORDER BY created_at ASC
            """
            results = await self.db.fetch_all(query, [cutoff_date.isoformat()])
            return results or []
        except Exception:
            return []
