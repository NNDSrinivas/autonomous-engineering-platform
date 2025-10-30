"""
Advanced search and context engine for the Intelligent Context Agent.
Handles semantic search across all integrated data sources.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from backend.core.db import get_db
from .models import ContextSource, ContextQuery, ContextResult, SourceType

logger = logging.getLogger(__name__)


class ContextSearchEngine:
    """
    Advanced search engine that can search across all integrated platforms
    and provide ranked, contextual results with source attribution.
    """

    def __init__(self):
        self.embedding_model = None  # Initialize if semantic search is needed
        
    def search(self, query: ContextQuery, db: Session) -> List[ContextResult]:
        """
        Search across all context sources and return ranked results.
        
        Args:
            query: The search query with filters and context
            db: Database session
            
        Returns:
            List of ranked context results
        """
        start_time = time.time()
        
        # Build the search filter
        filters = [ContextSource.org_key == query.org_key]
        
        if query.source_types:
            source_type_strs = [st.value for st in query.source_types]
            filters.append(ContextSource.source_type.in_(source_type_strs))
        
        # Perform text search across title and content
        search_terms = self._extract_search_terms(query.query)
        text_filter = self._build_text_search_filter(search_terms)
        if text_filter is not None:
            filters.append(text_filter)
        
        # Execute search
        search_query = db.query(ContextSource).filter(and_(*filters))
        
        # Order by relevance (simplified - could be enhanced with ML ranking)
        search_query = search_query.order_by(
            ContextSource.updated_at.desc()
        ).limit(query.limit)
        
        sources = search_query.all()
        
        # Convert to results and calculate relevance scores
        results = []
        for source in sources:
            # Properly access SQLAlchemy model attributes
            content = getattr(source, 'content') or getattr(source, 'title')
            snippet = self._extract_snippet(content, search_terms)
            relevance_score = self._calculate_relevance_score(
                source, search_terms, query.context
            )
            
            result = ContextResult(
                source_type=SourceType(getattr(source, 'source_type')),
                source_id=getattr(source, 'source_id'),
                title=getattr(source, 'title'),
                snippet=snippet,
                url=getattr(source, 'url'),
                author=getattr(source, 'author'),
                created_at=getattr(source, 'created_at'),
                updated_at=getattr(source, 'updated_at'),
                relevance_score=relevance_score,
                source_metadata=getattr(source, 'source_metadata')
            )
            results.append(result)
        
        # Sort by relevance score
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"Search completed in {processing_time}ms, found {len(results)} results")
        
        return results
    
    def search_for_task_context(
        self, 
        task_id: str, 
        task_title: str, 
        org_key: str, 
        db: Session
    ) -> List[ContextResult]:
        """
        Automatically search for context related to a specific task.
        
        Args:
            task_id: The task identifier
            task_title: The task title/summary
            org_key: Organization key for scoping
            db: Database session
            
        Returns:
            List of relevant context results
        """
        # Create a query based on the task information
        query = ContextQuery(
            query=f"task {task_id} {task_title}",
            org_key=org_key,
            context={"task_id": task_id, "auto_context": True},
            limit=20
        )
        
        results = self.search(query, db)
        
        # Filter out the task itself if it's in the results
        filtered_results = [
            r for r in results 
            if not (r.source_type == SourceType.JIRA and r.source_id == task_id)
        ]
        
        return filtered_results[:10]  # Return top 10 most relevant
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from the query."""
        # Simple implementation - could be enhanced with NLP
        import re
        
        # Remove common stop words and clean up
        stop_words = {'the', 'is', 'are', 'was', 'were', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'among', 'against', 'within', 'without', 'upon', 'around', 'under', 'over'}
        
        # Extract words (alphanumeric + some special chars)
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out stop words and short words
        meaningful_words = [
            word for word in words 
            if len(word) > 2 and word not in stop_words
        ]
        
        return meaningful_words
    
    def _build_text_search_filter(self, search_terms: List[str]):
        """Build a text search filter for the given terms."""
        if not search_terms:
            return None
        
        # Create ILIKE filters for title and content
        conditions = []
        for term in search_terms:
            term_pattern = f"%{term}%"
            term_condition = or_(
                ContextSource.title.ilike(term_pattern),
                ContextSource.content.ilike(term_pattern)
            )
            conditions.append(term_condition)
        
        # Combine with OR (any term matches)
        return or_(*conditions)
    
    def _extract_snippet(self, content: str, search_terms: List[str], max_length: int = 200) -> str:
        """Extract a relevant snippet from the content."""
        if not content:
            return ""
        
        content_lower = content.lower()
        
        # Find the first occurrence of any search term
        best_start = 0
        for term in search_terms:
            pos = content_lower.find(term.lower())
            if pos != -1:
                # Start a bit before the term for context
                best_start = max(0, pos - 50)
                break
        
        # Extract snippet
        snippet = content[best_start:best_start + max_length]
        
        # Clean up and add ellipsis if truncated
        if best_start > 0:
            snippet = "..." + snippet
        if len(content) > best_start + max_length:
            snippet = snippet + "..."
        
        return snippet.strip()
    
    def _calculate_relevance_score(
        self, 
        source: ContextSource, 
        search_terms: List[str], 
        context: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate relevance score for a source based on various factors.
        
        This is a simplified scoring algorithm - could be enhanced with ML.
        """
        score = 0.0
        
        # Base score from text matching
        title_lower = getattr(source, 'title', '').lower()
        content_lower = (getattr(source, 'content') or "").lower()
        
        for term in search_terms:
            term_lower = term.lower()
            
            # Title matches are more valuable
            if term_lower in title_lower:
                score += 0.3
            
            # Content matches
            if term_lower in content_lower:
                score += 0.1
        
        # Boost recent content
        updated_at = getattr(source, 'updated_at')
        if updated_at:
            import datetime
            days_old = (datetime.datetime.now() - updated_at).days
            freshness_boost = max(0, 0.2 - (days_old * 0.01))  # Decay over time
            score += freshness_boost
        
        # Source type preferences (can be customized)
        source_type_boosts = {
            SourceType.JIRA: 0.2,
            SourceType.CONFLUENCE: 0.15,
            SourceType.SLACK: 0.1,
            SourceType.MEETINGS: 0.15,
            SourceType.GITHUB: 0.1,
        }
        
        source_type = SourceType(source.source_type)
        score += source_type_boosts.get(source_type, 0.05)
        
        # Context-based boosts
        if context:
            task_id = context.get("task_id")
            if task_id and task_id in (source.title + " " + (source.content or "")):
                score += 0.3
        
        # Normalize score to 0-1 range
        return min(1.0, score)


class ContextIndexer:
    """
    Indexes content from various sources into the context search database.
    """
    
    def __init__(self):
        pass
    
    def index_jira_issue(
        self, 
        issue_data: Dict[str, Any], 
        org_key: str, 
        db: Session
    ) -> ContextSource:
        """Index a JIRA issue into the context database."""
        
        # Check if already exists
        existing = db.query(ContextSource).filter(
            and_(
                ContextSource.source_type == SourceType.JIRA.value,
                ContextSource.source_id == issue_data["id"],
                ContextSource.org_key == org_key
            )
        ).first()
        
        if existing:
            # Update existing using setattr
            setattr(existing, 'title', issue_data.get("summary", ""))
            setattr(existing, 'content', issue_data.get("description", ""))
            setattr(existing, 'url', issue_data.get("url"))
            setattr(existing, 'author', issue_data.get("reporter", {}).get("displayName"))
            setattr(existing, 'source_metadata', {
                "status": issue_data.get("status", {}).get("name"),
                "project": issue_data.get("project", {}).get("key"),
                "assignee": issue_data.get("assignee", {}).get("displayName"),
                "priority": issue_data.get("priority", {}).get("name"),
                "labels": issue_data.get("labels", [])
            })
            db.commit()
            return existing
        else:
            # Create new
            source = ContextSource(
                source_type=SourceType.JIRA.value,
                source_id=issue_data["id"],
                title=issue_data.get("summary", ""),
                content=issue_data.get("description", ""),
                url=issue_data.get("url"),
                author=issue_data.get("reporter", {}).get("displayName"),
                org_key=org_key,
                source_metadata={
                    "status": issue_data.get("status", {}).get("name"),
                    "project": issue_data.get("project", {}).get("key"),
                    "assignee": issue_data.get("assignee", {}).get("displayName"),
                    "priority": issue_data.get("priority", {}).get("name"),
                    "labels": issue_data.get("labels", [])
                }
            )
            db.add(source)
            db.commit()
            return source
    
    def index_slack_message(
        self, 
        message_data: Dict[str, Any], 
        org_key: str, 
        db: Session
    ) -> ContextSource:
        """Index a Slack message into the context database."""
        
        message_id = message_data["ts"]  # Slack timestamp as ID
        
        existing = db.query(ContextSource).filter(
            and_(
                ContextSource.source_type == SourceType.SLACK.value,
                ContextSource.source_id == message_id,
                ContextSource.org_key == org_key
            )
        ).first()
        
        if existing:
            return existing
        
        source = ContextSource(
            source_type=SourceType.SLACK.value,
            source_id=message_id,
            title=f"Slack message in #{message_data.get('channel', 'unknown')}",
            content=message_data.get("text", ""),
            url=message_data.get("permalink"),
            author=message_data.get("user_name"),
            org_key=org_key,
            source_metadata={
                "channel": message_data.get("channel"),
                "channel_name": message_data.get("channel_name"),
                "thread_ts": message_data.get("thread_ts"),
                "reactions": message_data.get("reactions", [])
            }
        )
        db.add(source)
        db.commit()
        return source