"""
Multi-Tenant Core Architecture for NAVI Enterprise

This module provides the foundational tenant isolation system that ensures:
- Complete data isolation between organizations
- No cross-tenant data leakage
- Per-org policy enforcement
- Secure tenant context management
"""

from typing import Optional, List, Any, Dict
from dataclasses import dataclass
from contextvars import ContextVar
from functools import wraps
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Global tenant context - thread-safe per request
_tenant_context: ContextVar[Optional['TenantContext']] = ContextVar('tenant_context', default=None)

class TenantRole(Enum):
    """Enterprise roles with hierarchical permissions"""
    ORG_ADMIN = "org_admin"          # Full org control
    TEAM_LEAD = "team_lead"          # Team management
    ENGINEER = "engineer"            # Standard user
    VIEWER = "viewer"                # Read-only access
    AUDITOR = "auditor"              # Audit access only

@dataclass
class TenantContext:
    """Complete tenant context for request isolation"""
    org_id: str                      # Primary tenant identifier
    user_id: str                     # User within tenant  
    roles: List[TenantRole]          # User's roles in this org
    permissions: List[str]           # Specific permissions
    session_id: str                  # Unique session identifier
    encryption_key_id: str           # Org-specific encryption key
    region: Optional[str] = None     # Data residency region
    compliance_flags: Optional[Dict[str, bool]] = None  # GDPR, SOC2, etc.
    
    def has_role(self, role: TenantRole) -> bool:
        """Check if user has specific role"""
        return role in self.roles
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions or TenantRole.ORG_ADMIN in self.roles
    
    def is_admin(self) -> bool:
        """Check if user is org admin"""
        return TenantRole.ORG_ADMIN in self.roles

    @property
    def tenant_id(self) -> str:
        """Compatibility alias for legacy callers expecting tenant_id."""
        return self.org_id

class TenantIsolationError(Exception):
    """Raised when tenant isolation is violated"""
    pass

def get_current_tenant() -> Optional[TenantContext]:
    """Get the current tenant context"""
    return _tenant_context.get()

def require_tenant() -> TenantContext:
    """Get current tenant context or raise error"""
    context = get_current_tenant()
    if not context:
        raise TenantIsolationError("No tenant context available - request must be scoped to an organization")
    return context

def set_tenant_context(context: TenantContext) -> None:
    """Set tenant context for current request"""
    _tenant_context.set(context)
    logger.debug(f"Set tenant context: org_id={context.org_id}, user_id={context.user_id}")

def clear_tenant_context() -> None:
    """Clear tenant context"""
    _tenant_context.set(None)

def with_tenant_context(context: TenantContext):
    """Decorator to run function with specific tenant context"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            old_context = get_current_tenant()
            set_tenant_context(context)
            try:
                return await func(*args, **kwargs)
            finally:
                if old_context:
                    set_tenant_context(old_context)
                else:
                    clear_tenant_context()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            old_context = get_current_tenant()
            set_tenant_context(context)
            try:
                return func(*args, **kwargs)
            finally:
                if old_context:
                    set_tenant_context(old_context)
                else:
                    clear_tenant_context()
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def require_role(required_role: TenantRole):
    """Decorator to enforce role-based access control"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            context = require_tenant()
            if not context.has_role(required_role) and not context.is_admin():
                raise TenantIsolationError(
                    f"Access denied: requires {required_role.value}, user has {[r.value for r in context.roles]}"
                )
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            context = require_tenant()
            if not context.has_role(required_role) and not context.is_admin():
                raise TenantIsolationError(
                    f"Access denied: requires {required_role.value}, user has {[r.value for r in context.roles]}"
                )
            return func(*args, **kwargs)
            
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def require_permission(permission: str):
    """Decorator to enforce permission-based access control"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            context = require_tenant()
            if not context.has_permission(permission):
                raise TenantIsolationError(f"Access denied: missing permission '{permission}'")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            context = require_tenant()
            if not context.has_permission(permission):
                raise TenantIsolationError(f"Access denied: missing permission '{permission}'")
            return func(*args, **kwargs)
            
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

class TenantAwareModel:
    """Base class for tenant-aware data models"""
    
    @classmethod
    def get_tenant_filter(cls) -> Dict[str, Any]:
        """Get filter clause for current tenant"""
        context = require_tenant()
        return {"org_id": context.org_id}
    
    @classmethod
    def validate_tenant_access(cls, obj_org_id: str) -> None:
        """Validate that object belongs to current tenant"""
        context = require_tenant()
        if obj_org_id != context.org_id:
            raise TenantIsolationError(
                f"Cross-tenant access denied: object belongs to {obj_org_id}, "
                f"current tenant is {context.org_id}"
            )

def ensure_tenant_scoped(query_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all queries are scoped to current tenant"""
    context = require_tenant()
    
    # Always add org_id filter
    if "org_id" in query_dict and query_dict["org_id"] != context.org_id:
        raise TenantIsolationError("Attempted cross-tenant query")
    
    query_dict["org_id"] = context.org_id
    return query_dict

# Audit logging for tenant operations
class TenantAuditLogger:
    """Audit logger for tenant operations"""
    
    @staticmethod
    def log_access(resource: str, action: str, details: Optional[Dict] = None):
        """Log tenant access for audit trail"""
        context = get_current_tenant()
        if not context:
            logger.warning(f"Unscoped access to {resource}: {action}")
            return
        
        audit_entry = {
            "timestamp": "now",  # Use proper timestamp
            "org_id": context.org_id,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "resource": resource,
            "action": action,
            "details": details or {}
        }
        
        logger.info(f"TENANT_AUDIT: {audit_entry}")

# Export key components
__all__ = [
    'TenantContext',
    'TenantRole', 
    'TenantIsolationError',
    'get_current_tenant',
    'require_tenant',
    'set_tenant_context',
    'with_tenant_context',
    'require_role',
    'require_permission',
    'TenantAwareModel',
    'ensure_tenant_scoped',
    'TenantAuditLogger'
]
