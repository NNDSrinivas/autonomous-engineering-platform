"""
Intelligent Context Agent - The core AI that answers user questions
by searching across all integrated platforms.
"""

from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.core.db import get_db
# from backend.llm.client import get_llm_client  # TODO: Implement LLM client
from .models import (
    ContextQuery, 
    ContextResponse, 
    ContextResult, 
    TaskContext, 
    UserQuestion,
    SourceType
)
from .search import ContextSearchEngine

logger = logging.getLogger(__name__)


class IntelligentContextAgent:
    """
    The core AI agent that provides intelligent, contextual answers
    to user questions by searching across all integrated platforms.
    """
    
    def __init__(self):
        self.search_engine = ContextSearchEngine()
        self.llm_client = None  # Will be initialized when needed
    
    async def answer_question(
        self, 
        question: str, 
        org_key: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        source_types: Optional[List[SourceType]] = None
    ) -> ContextResponse:
        """
        Answer a user's question by searching across all available context.
        
        Args:
            question: The user's question
            org_key: Organization key for scoping
            user_id: User asking the question
            context: Additional context (current task, project, etc.)
            source_types: Limit search to specific source types
            
        Returns:
            Comprehensive response with sources and AI-generated summary
        """
        start_time = time.time()
        
        # Create search query
        query = ContextQuery(
            query=question,
            org_key=org_key,
            source_types=source_types,
            context=context,
            user_id=user_id,
            limit=20  # Get more results for better AI summarization
        )
        
        # Search for relevant context
        db = next(get_db())
        try:
            search_results = self.search_engine.search(query, db)
            
            # Log the question for learning/improvement
            self._log_user_question(question, org_key, user_id, context, len(search_results), db)
            
            # Generate AI summary if we have an LLM available
            answer_summary = await self._generate_ai_summary(question, search_results)
            
            # Generate suggested follow-up questions
            suggested_questions = self._generate_suggested_questions(question, search_results)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            response = ContextResponse(
                query=question,
                results=search_results,
                total_found=len(search_results),
                processing_time_ms=processing_time,
                suggested_questions=suggested_questions,
                answer_summary=answer_summary
            )
            
            # Update the logged question with response data
            self._update_question_response(question, org_key, response, db)
            
            return response
            
        finally:
            db.close()
    
    async def get_task_context(
        self, 
        task_id: str, 
        task_title: str,
        task_type: SourceType,
        org_key: str
    ) -> TaskContext:
        """
        Automatically gather all relevant context for a specific task.
        
        This is called when a user selects/opens a task to work on.
        """
        db = next(get_db())
        try:
            # Search for related context
            related_context = self.search_engine.search_for_task_context(
                task_id, task_title, org_key, db
            )
            
            task_context = TaskContext(
                task_id=task_id,
                task_type=task_type,
                title=task_title,
                related_context=related_context
            )
            
            logger.info(f"Generated task context for {task_id}: {len(related_context)} related items")
            return task_context
            
        finally:
            db.close()
    
    def answer_dev_environment_question(self, org_key: str) -> ContextResponse:
        """
        Specialized handler for development environment questions.
        
        Example: "What is the dev environment link?"
        """
        # Search for development environment related content
        query = ContextQuery(
            query="development environment dev env staging server link URL",
            org_key=org_key,
            context={"question_type": "dev_environment"},
            limit=10
        )
        
        db = next(get_db())
        try:
            results = self.search_engine.search(query, db)
            
            # Filter for likely environment-related results
            env_results = []
            for result in results:
                content_lower = (result.snippet + " " + result.title).lower()
                if any(keyword in content_lower for keyword in [
                    "environment", "staging", "dev", "development", 
                    "server", "url", "link", "deploy", "endpoint"
                ]):
                    env_results.append(result)
            
            processing_time = 150  # Estimated
            
            return ContextResponse(
                query="Development environment information",
                results=env_results,
                total_found=len(env_results),
                processing_time_ms=processing_time,
                suggested_questions=[
                    "How do I deploy to staging?",
                    "What are the database credentials?",
                    "How do I access the logs?",
                    "What is the production URL?"
                ]
            )
            
        finally:
            db.close()
    
    async def _generate_ai_summary(
        self, 
        question: str, 
        results: List[ContextResult]
    ) -> Optional[str]:
        """Generate an AI summary of the search results."""
        if not results:
            return None
        
        try:
            # TODO: Implement LLM client integration
            # if not self.llm_client:
            #     self.llm_client = get_llm_client()
            
            # For now, return a simple concatenated response
            if results:
                return f"Based on {len(results)} sources found, here are the key points: " + \
                       "; ".join([r.snippet[:100] + "..." for r in results[:3]])
            return None
            
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")
            return None
    
    def _generate_suggested_questions(
        self, 
        original_question: str, 
        results: List[ContextResult]
    ) -> List[str]:
        """Generate suggested follow-up questions based on search results."""
        suggestions = []
        
        # Based on source types found
        source_types_found = set(result.source_type for result in results)
        
        if SourceType.JIRA in source_types_found:
            suggestions.extend([
                "What tasks are assigned to me?",
                "What is the status of this project?",
                "Are there any blockers for this task?"
            ])
        
        if SourceType.CONFLUENCE in source_types_found:
            suggestions.extend([
                "Is there documentation for this feature?",
                "What are the technical specifications?",
                "Are there any architectural decisions documented?"
            ])
        
        if SourceType.SLACK in source_types_found:
            suggestions.extend([
                "What have people been discussing about this?",
                "Who was involved in the decision?",
                "Are there any recent updates on this topic?"
            ])
        
        if SourceType.MEETINGS in source_types_found:
            suggestions.extend([
                "What was decided in the last meeting?",
                "Who are the stakeholders for this?",
                "What are the next steps?"
            ])
        
        # Remove duplicates and limit
        unique_suggestions = list(dict.fromkeys(suggestions))
        return unique_suggestions[:4]
    
    def _log_user_question(
        self, 
        question: str, 
        org_key: str, 
        user_id: Optional[str],
        context: Optional[Dict[str, Any]],
        results_count: int,
        db: Session
    ):
        """Log user questions for learning and improvement."""
        try:
            user_question = UserQuestion(
                org_key=org_key,
                user_id=user_id,
                question=question,
                context_provided=context,
                results_found=results_count
            )
            db.add(user_question)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to log user question: {e}")
    
    def _update_question_response(
        self, 
        question: str, 
        org_key: str, 
        response: ContextResponse,
        db: Session
    ):
        """Update the logged question with response data."""
        try:
            recent_question = db.query(UserQuestion).filter(
                UserQuestion.org_key == org_key,
                UserQuestion.question == question
            ).order_by(UserQuestion.created_at.desc()).first()
            
            if recent_question:
                # Update using setattr for SQLAlchemy
                setattr(recent_question, 'response_data', {
                    "total_found": response.total_found,
                    "processing_time_ms": response.processing_time_ms,
                    "has_ai_summary": response.answer_summary is not None,
                    "source_types": [r.source_type.value for r in response.results]
                })
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to update question response: {e}")


# Convenience functions for common use cases

async def ask_agent(
    question: str, 
    org_key: str, 
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ContextResponse:
    """Convenience function to ask the intelligent agent a question."""
    agent = IntelligentContextAgent()
    return await agent.answer_question(question, org_key, user_id, context)


async def get_task_context_auto(
    task_id: str, 
    task_title: str, 
    org_key: str
) -> TaskContext:
    """Convenience function to get automatic task context."""
    agent = IntelligentContextAgent()
    return await agent.get_task_context(task_id, task_title, SourceType.JIRA, org_key)