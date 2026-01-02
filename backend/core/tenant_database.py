"""
Tenant-Aware Database Layer for NAVI Enterprise

Provides database abstraction with built-in tenant isolation:
- All queries automatically scoped to current tenant
- Prevents cross-tenant data leakage
- Supports multiple database backends
- Enterprise audit logging
"""

from typing import Any, Dict, List, Optional, Union, cast
from sqlalchemy import create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
import logging

from .tenancy import require_tenant, ensure_tenant_scoped, TenantAuditLogger

logger = logging.getLogger(__name__)

class TenantAwareBase(DeclarativeBase):
    """Base class for all tenant-aware models"""
    pass

class TenantDatabase:
    """Tenant-aware database connection manager"""
    
    def __init__(self, database_url: str, async_database_url: Optional[str] = None):
        self.database_url = database_url
        self.async_database_url = async_database_url or database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        
        # Sync engine
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal: sessionmaker[Session] = sessionmaker(bind=self.engine)
        
        # Async engine
        self.async_engine = create_async_engine(self.async_database_url, echo=False)
        self.AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.async_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    
    def get_session(self) -> Session:
        """Get synchronous database session"""
        return self.SessionLocal()
    
    def get_async_session(self) -> AsyncSession:
        """Get asynchronous database session"""
        return self.AsyncSessionLocal()

class TenantQueryBuilder:
    """Builds tenant-scoped queries with automatic isolation"""
    
    def __init__(self, session: Union[Session, AsyncSession]):
        self.session = session
        self.tenant_context = require_tenant()
    
    def _add_tenant_filter(self, query_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add tenant filter to all queries"""
        return ensure_tenant_scoped(query_dict)
    
    async def find_one(self, table: str, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find single record with tenant isolation"""
        filters = self._add_tenant_filter(filters)
        
        TenantAuditLogger.log_access(table, "read", {"filters": filters})
        
        # Build WHERE clause
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters.keys()])
        query = text(f"SELECT * FROM {table} WHERE {where_clause} LIMIT 1")
        
        if isinstance(self.session, AsyncSession):
            result = await self.session.execute(query, filters)
        else:
            result = self.session.execute(query, filters)
        
        row = result.fetchone()
        return dict(row._mapping) if row else None
    
    async def find_many(self, table: str, filters: Dict[str, Any], 
                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find multiple records with tenant isolation"""
        filters = self._add_tenant_filter(filters)
        
        TenantAuditLogger.log_access(table, "read_many", {"filters": filters, "limit": limit})
        
        # Build query
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters.keys()])
        query_str = f"SELECT * FROM {table} WHERE {where_clause}"
        if limit:
            query_str += f" LIMIT {limit}"
        
        query = text(query_str)
        
        if isinstance(self.session, AsyncSession):
            result = await self.session.execute(query, filters)
        else:
            result = self.session.execute(query, filters)
        
        return [dict(row._mapping) for row in result.fetchall()]
    
    async def create(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create record with tenant isolation"""
        # Ensure org_id is set
        data["org_id"] = self.tenant_context.org_id
        
        TenantAuditLogger.log_access(table, "create", {"data_keys": list(data.keys())})
        
        # Build INSERT query
        columns = ", ".join(data.keys())
        values = ", ".join([f":{k}" for k in data.keys()])
        query = text(f"INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING *")
        
        if isinstance(self.session, AsyncSession):
            result = await self.session.execute(query, data)
            await self.session.commit()
        else:
            result = self.session.execute(query, data)
            self.session.commit()
        
        row = result.fetchone()
        return dict(row._mapping) if row else data
    
    async def update(self, table: str, filters: Dict[str, Any], 
                    updates: Dict[str, Any]) -> int:
        """Update records with tenant isolation"""
        filters = self._add_tenant_filter(filters)
        
        TenantAuditLogger.log_access(
            table, "update", 
            {"filters": filters, "updates_keys": list(updates.keys())}
        )
        
        # Build UPDATE query
        set_clause = ", ".join([f"{k} = :update_{k}" for k in updates.keys()])
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters.keys()])
        
        # Prepare parameters (avoid key conflicts)
        params = filters.copy()
        params.update({f"update_{k}": v for k, v in updates.items()})
        
        query = text(f"UPDATE {table} SET {set_clause} WHERE {where_clause}")
        
        if isinstance(self.session, AsyncSession):
            result = await self.session.execute(query, params)
            await self.session.commit()
        else:
            result = self.session.execute(query, params)
            self.session.commit()
        
        return cast(CursorResult, result).rowcount
    
    async def delete(self, table: str, filters: Dict[str, Any]) -> int:
        """Delete records with tenant isolation"""
        filters = self._add_tenant_filter(filters)
        
        TenantAuditLogger.log_access(table, "delete", {"filters": filters})
        
        # Build DELETE query
        where_clause = " AND ".join([f"{k} = :{k}" for k in filters.keys()])
        query = text(f"DELETE FROM {table} WHERE {where_clause}")
        
        if isinstance(self.session, AsyncSession):
            result = await self.session.execute(query, filters)
            await self.session.commit()
        else:
            result = self.session.execute(query, filters)
            self.session.commit()
        
        return cast(CursorResult, result).rowcount

class TenantRepository:
    """Base repository class with tenant isolation"""
    
    def __init__(self, db: TenantDatabase, table_name: str):
        self.db = db
        self.table_name = table_name
    
    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Find record by ID within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.find_one(self.table_name, {"id": id})

    async def find_one(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single record by filters within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.find_one(self.table_name, filters)
    
    async def find_all(self, filters: Optional[Dict[str, Any]] = None, 
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find all records within current tenant"""
        filters = filters or {}
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.find_many(self.table_name, filters, limit)
    
    async def create(self, data: Dict[str, Any], table_name: Optional[str] = None) -> Dict[str, Any]:
        """Create new record within current tenant"""
        target_table = table_name or self.table_name
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.create(target_table, data)

    async def create_or_update(self, data: Dict[str, Any], record_id: Optional[str] = None) -> Dict[str, Any]:
        """Create or update a record by ID within current tenant"""
        target_id = record_id or data.get("id")
        if target_id:
            existing = await self.find_by_id(target_id)
            if existing:
                await self.update_by_id(target_id, data)
                return data
        return await self.create(data)
    
    async def update_by_id(self, id: str, updates: Dict[str, Any]) -> bool:
        """Update record by ID within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            count = await query_builder.update(self.table_name, {"id": id}, updates)
            return count > 0

    async def update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update records matching filters within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.update(self.table_name, filters, updates)
    
    async def delete_by_id(self, id: str) -> bool:
        """Delete record by ID within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            count = await query_builder.delete(self.table_name, {"id": id})
            return count > 0

    async def delete(self, filters: Dict[str, Any]) -> int:
        """Delete records matching filters within current tenant"""
        async with self.db.get_async_session() as session:
            query_builder = TenantQueryBuilder(session)
            return await query_builder.delete(self.table_name, filters)

# Database migration support
class TenantMigration:
    """Handles schema migrations for tenant-aware tables"""
    
    def __init__(self, db: TenantDatabase):
        self.db = db
    
    def create_tenant_aware_table(self, table_name: str, columns: Dict[str, str]) -> str:
        """Generate SQL for tenant-aware table creation"""
        # Always include org_id as primary tenant isolation column
        if "org_id" not in columns:
            columns["org_id"] = "VARCHAR(255) NOT NULL"
        
        columns_sql = ",\n  ".join([f"{name} {definition}" for name, definition in columns.items()])
        
        return f"""
CREATE TABLE IF NOT EXISTS {table_name} (
  {columns_sql},
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_{table_name}_org_id (org_id)
);
"""

# Global database instance (initialized by app)
tenant_db: Optional[TenantDatabase] = None

def init_tenant_database(database_url: str, async_database_url: Optional[str] = None):
    """Initialize global tenant database"""
    global tenant_db
    tenant_db = TenantDatabase(database_url, async_database_url)

def get_tenant_db() -> TenantDatabase:
    """Get global tenant database instance"""
    if not tenant_db:
        raise RuntimeError("Tenant database not initialized. Call init_tenant_database() first.")
    return tenant_db

__all__ = [
    'TenantDatabase',
    'TenantQueryBuilder', 
    'TenantRepository',
    'TenantMigration',
    'init_tenant_database',
    'get_tenant_db'
]
