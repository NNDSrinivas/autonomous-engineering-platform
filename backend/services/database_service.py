"""
Database Service for Memory Agent

Provides async database operations using SQLAlchemy with the existing 
database session management from backend/database/session.py
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio
from sqlalchemy import text
from backend.database.session import db_session

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Async database service that wraps SQLAlchemy operations
    for use by the Memory Agent and other async components.
    """
    
    def __init__(self):
        """Initialize the database service."""
        pass
    
    async def fetch_all(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return all results as a list of dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of row dictionaries
        """
        try:
            # Run the sync database operation in a thread pool
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_fetch_all, query, params or []
            )
        except Exception as e:
            logger.error(f"Database fetch_all error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    async def fetch_one(self, query: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return the first result as a dictionary.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Row dictionary or None if no results
        """
        try:
            # Run the sync database operation in a thread pool
            return await asyncio.get_event_loop().run_in_executor(
                None, self._sync_fetch_one, query, params or []
            )
        except Exception as e:
            logger.error(f"Database fetch_one error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    async def execute(self, query: str, params: Optional[List[Any]] = None) -> None:
        """
        Execute an INSERT, UPDATE, or DELETE query.
        
        Args:
            query: SQL query string
            params: Query parameters
        """
        try:
            # Run the sync database operation in a thread pool
            await asyncio.get_event_loop().run_in_executor(
                None, self._sync_execute, query, params or []
            )
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    def _sync_fetch_all(self, query: str, params: List[Any]) -> List[Dict[str, Any]]:
        """
        Synchronous fetch_all implementation.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of row dictionaries
        """
        with db_session() as session:
            result = session.execute(text(query), params)
            # Convert rows to dictionaries
            columns = result.keys()
            rows = []
            for row in result.fetchall():
                row_dict = {}
                for i, column in enumerate(columns):
                    row_dict[column] = row[i]
                rows.append(row_dict)
            return rows
    
    def _sync_fetch_one(self, query: str, params: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Synchronous fetch_one implementation.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Row dictionary or None if no results
        """
        with db_session() as session:
            result = session.execute(text(query), params)
            row = result.fetchone()
            if row is None:
                return None
            
            # Convert row to dictionary
            columns = result.keys()
            row_dict = {}
            for i, column in enumerate(columns):
                row_dict[column] = row[i]
            return row_dict
    
    def _sync_execute(self, query: str, params: List[Any]) -> None:
        """
        Synchronous execute implementation.
        
        Args:
            query: SQL query string
            params: Query parameters
        """
        with db_session() as session:
            session.execute(text(query), params)
            session.commit()