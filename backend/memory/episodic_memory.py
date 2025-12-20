"""
Episodic Memory for Navi Long-Term Memory System
High-level orchestrated memory that records and retrieves engineering context.
Equivalent to Gemini's memory but specialized for software engineering tasks.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum

from .vector_store import VectorStore

class MemoryEventType(Enum):
    """Types of events that can be recorded in episodic memory."""
    CODE_REVIEW = "code_review"
    REFACTOR = "refactor"
    BUG_FIX = "bug_fix"
    FEATURE_IMPLEMENTATION = "feature_implementation"
    TEST_CREATION = "test_creation"
    DEPLOYMENT = "deployment"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    DOCUMENTATION = "documentation"
    CONVERSATION = "conversation"
    ERROR_ENCOUNTERED = "error_encountered"
    SUCCESS_PATTERN = "success_pattern"
    USER_PREFERENCE = "user_preference"
    ARCHITECTURAL_DECISION = "architectural_decision"
    SYSTEM_EVENT = "system_event"
    DEPENDENCY_UPDATE = "dependency_update"

class EpisodicMemory:
    """
    High-level episodic memory system that records and retrieves engineering context.
    
    This system remembers:
    - Past failures and their solutions
    - Successful patterns and approaches
    - User preferences and coding styles
    - Repo architecture and business rules
    - Conversations and decisions
    - Performance insights and optimizations
    """
    
    def __init__(self, storage_path: str = "data/memory"):
        """
        Initialize episodic memory with vector store backend.
        
        Args:
            storage_path: Path for memory storage
        """
        self.vector_store = VectorStore(storage_path=storage_path)
        self.logger = logging.getLogger(__name__)
        
        # Memory configuration
        self.max_context_items = 50  # Max items to return in context
        self.relevance_threshold = 0.3  # Minimum similarity for relevance
        self.memory_retention_days = 180  # Keep memories for 6 months
        
        self.logger.info("EpisodicMemory initialized")
    
    async def record_event(self, 
                          event_type: Union[MemoryEventType, str],
                          content: str,
                          metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Record a new event in episodic memory.
        
        Args:
            event_type: Type of event being recorded
            content: Main content/description of the event
            metadata: Additional metadata (files, success, duration, etc.)
            
        Returns:
            Index of recorded event
        """
        if isinstance(event_type, MemoryEventType):
            event_type = event_type.value
        
        # Prepare metadata
        event_metadata = {
            'type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'content_preview': content[:100] + "..." if len(content) > 100 else content,
            **(metadata or {})
        }
        
        # Create searchable text combining content and metadata
        searchable_text = self._create_searchable_text(content, event_metadata)
        
        # Store in vector store
        index = self.vector_store.add(searchable_text, event_metadata)
        
        self.logger.debug(f"Recorded {event_type} event at index {index}")
        return index
    
    async def record_code_review(self,
                               files: List[str],
                               findings: List[Dict[str, Any]],
                               success: bool,
                               duration_seconds: float) -> int:
        """
        Record a code review event with structured data.
        
        Args:
            files: List of files reviewed
            findings: List of review findings
            success: Whether review was successful
            duration_seconds: Time taken for review
            
        Returns:
            Index of recorded event
        """
        content = f"Code review of {len(files)} files. Found {len(findings)} issues."
        
        if findings:
            # Add top findings to content
            top_findings = findings[:3]
            content += " Key findings: " + "; ".join([
                f"{f.get('type', 'issue')}: {f.get('description', 'N/A')[:50]}" 
                for f in top_findings
            ])
        
        metadata = {
            'files': files,
            'findings_count': len(findings),
            'findings': findings[:10],  # Store top 10 findings
            'success': success,
            'duration_seconds': duration_seconds,
            'files_count': len(files)
        }
        
        return await self.record_event(MemoryEventType.CODE_REVIEW, content, metadata)
    
    async def record_bug_fix(self,
                           error_message: str,
                           solution: str,
                           files_modified: List[str],
                           success: bool) -> int:
        """
        Record a bug fix event for future reference.
        
        Args:
            error_message: Original error or problem description
            solution: Solution that was applied
            files_modified: Files that were changed
            success: Whether the fix was successful
            
        Returns:
            Index of recorded event
        """
        content = f"Bug fix: {error_message[:100]}. Solution: {solution[:200]}"
        
        metadata = {
            'error_message': error_message,
            'solution': solution,
            'files_modified': files_modified,
            'success': success,
            'files_count': len(files_modified)
        }
        
        return await self.record_event(MemoryEventType.BUG_FIX, content, metadata)
    
    async def record_user_preference(self,
                                   preference_type: str,
                                   preference_value: Any,
                                   context: str) -> int:
        """
        Record a user preference for personalization.
        
        Args:
            preference_type: Type of preference (coding_style, tool_choice, etc.)
            preference_value: The preferred value
            context: Context in which preference was observed
            
        Returns:
            Index of recorded event
        """
        content = f"User preference: {preference_type} = {preference_value} in context: {context}"
        
        metadata = {
            'preference_type': preference_type,
            'preference_value': preference_value,
            'context': context
        }
        
        return await self.record_event(MemoryEventType.USER_PREFERENCE, content, metadata)
    
    async def record_success_pattern(self,
                                   pattern_description: str,
                                   context: Dict[str, Any],
                                   outcome_metrics: Dict[str, Any]) -> int:
        """
        Record a successful pattern for future reuse.
        
        Args:
            pattern_description: Description of what worked
            context: Context in which pattern was successful
            outcome_metrics: Metrics showing success (performance, quality, etc.)
            
        Returns:
            Index of recorded event
        """
        content = f"Success pattern: {pattern_description}"
        
        metadata = {
            'pattern': pattern_description,
            'context': context,
            'outcome_metrics': outcome_metrics
        }
        
        return await self.record_event(MemoryEventType.SUCCESS_PATTERN, content, metadata)
    
    async def retrieve_context(self,
                             query: str,
                             event_types: Optional[List[Union[MemoryEventType, str]]] = None,
                             max_items: Optional[int] = None,
                             time_range_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from episodic memory.
        
        Args:
            query: Search query to find relevant memories
            event_types: Filter by specific event types
            max_items: Maximum number of items to return
            time_range_days: Only include memories from last N days
            
        Returns:
            List of relevant memory items with similarity scores
        """
        # Prepare filters
        filters = {}
        
        if event_types:
            # Convert enum types to strings
            type_strings = []
            for event_type in event_types:
                if isinstance(event_type, MemoryEventType):
                    type_strings.append(event_type.value)
                else:
                    type_strings.append(event_type)
            filters['type'] = type_strings
        
        if time_range_days:
            cutoff_date = datetime.utcnow() - timedelta(days=time_range_days)
            filters['timestamp'] = {'min': cutoff_date.isoformat()}
        
        # Search vector store
        max_items = max_items or self.max_context_items
        results = self.vector_store.search(
            query=query,
            k=max_items,
            filters=filters,
            min_similarity=self.relevance_threshold
        )
        
        # Enhance results with parsed metadata
        enhanced_results = []
        for result in results:
            enhanced_result = {
                **result,
                'relevance_score': result['similarity'],
                'age_days': self._calculate_age_days(result['metadata'].get('timestamp')),
                'summary': result['metadata'].get('content_preview', result['text'][:100])
            }
            enhanced_results.append(enhanced_result)
        
        self.logger.debug(f"Retrieved {len(enhanced_results)} relevant memories for query: {query[:50]}")
        return enhanced_results
    
    async def get_similar_bug_fixes(self, error_message: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar bug fixes from memory.
        
        Args:
            error_message: Error message to find similar fixes for
            limit: Maximum number of similar fixes to return
            
        Returns:
            List of similar bug fix memories
        """
        return await self.retrieve_context(
            query=error_message,
            event_types=[MemoryEventType.BUG_FIX],
            max_items=limit
        )
    
    async def get_user_preferences(self, context: str = "") -> List[Dict[str, Any]]:
        """
        Get user preferences relevant to current context.
        
        Args:
            context: Current context to find relevant preferences
            
        Returns:
            List of relevant user preferences
        """
        query = f"user preference {context}" if context else "user preference"
        return await self.retrieve_context(
            query=query,
            event_types=[MemoryEventType.USER_PREFERENCE],
            max_items=20
        )
    
    async def get_success_patterns(self, context: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get successful patterns similar to current context.
        
        Args:
            context: Description of current situation
            limit: Maximum number of patterns to return
            
        Returns:
            List of relevant success patterns
        """
        return await self.retrieve_context(
            query=context,
            event_types=[MemoryEventType.SUCCESS_PATTERN],
            max_items=limit
        )
    
    async def get_architectural_insights(self, query: str) -> List[Dict[str, Any]]:
        """
        Get architectural decisions and insights.
        
        Args:
            query: Architecture-related query
            
        Returns:
            List of relevant architectural memories
        """
        return await self.retrieve_context(
            query=query,
            event_types=[MemoryEventType.ARCHITECTURAL_DECISION],
            max_items=15
        )
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory usage and content.
        
        Returns:
            Dictionary with memory statistics
        """
        stats = self.vector_store.get_stats()
        
        # Add episodic-memory-specific stats
        event_type_counts = {}
        for meta in self.vector_store.metadata:
            event_type = meta.get('type', 'unknown')
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        stats.update({
            'event_type_distribution': event_type_counts,
            'total_events': len(self.vector_store.metadata),
            'retention_days': self.memory_retention_days,
            'relevance_threshold': self.relevance_threshold
        })
        
        return stats
    
    async def cleanup_old_memories(self, days_to_keep: Optional[int] = None):
        """
        Clean up old memories to manage storage.
        
        Args:
            days_to_keep: Number of days of memories to keep (uses default if None)
        """
        days_to_keep = days_to_keep or self.memory_retention_days
        self.vector_store.cleanup_old_entries(days_old=days_to_keep)
        self.logger.info(f"Cleaned up memories older than {days_to_keep} days")
    
    def _create_searchable_text(self, content: str, metadata: Dict[str, Any]) -> str:
        """
        Create searchable text by combining content and relevant metadata.
        
        Args:
            content: Main content
            metadata: Event metadata
            
        Returns:
            Combined searchable text
        """
        searchable_parts = [content]
        
        # Add relevant metadata fields to searchable text
        if 'files' in metadata:
            files = metadata['files']
            if isinstance(files, list) and files:
                # Include file names and extensions
                file_info = " ".join([
                    f"file:{file}" for file in files[:5]  # Include up to 5 files
                ])
                searchable_parts.append(file_info)
        
        if 'error_message' in metadata:
            searchable_parts.append(f"error: {metadata['error_message']}")
        
        if 'solution' in metadata:
            searchable_parts.append(f"solution: {metadata['solution']}")
        
        if 'preference_type' in metadata:
            searchable_parts.append(f"preference: {metadata['preference_type']}")
        
        return " ".join(searchable_parts)
    
    def _calculate_age_days(self, timestamp_str: Optional[str]) -> Optional[float]:
        """
        Calculate age of memory in days.
        
        Args:
            timestamp_str: ISO timestamp string
            
        Returns:
            Age in days or None if timestamp invalid
        """
        if not timestamp_str:
            return None
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            age = datetime.utcnow() - timestamp
            return age.total_seconds() / (24 * 3600)  # Convert to days
        except Exception:
            return None
