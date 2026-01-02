"""
Organization Management for NAVI Enterprise

Handles:
- Organization creation and configuration
- Multi-tenant organization isolation
- Organization-level settings and policies
- Team and user management within organizations
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from .tenancy import TenantContext, TenantRole, require_tenant, require_role
from .tenant_database import TenantRepository, get_tenant_db

class OrgTier(Enum):
    """Organization subscription tiers"""
    STARTER = "starter"          # Small teams, basic features
    PROFESSIONAL = "professional" # Mid-size teams, advanced features  
    ENTERPRISE = "enterprise"   # Large orgs, full features + compliance
    
class OrgStatus(Enum):
    """Organization account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"

@dataclass
class OrganizationConfig:
    """Organization configuration and settings"""
    id: str
    name: str
    slug: str                    # URL-friendly name
    tier: OrgTier
    status: OrgStatus
    
    # Settings
    default_autonomy_level: float = 0.5  # 0=manual, 1=full auto
    allowed_integrations: List[str] = field(default_factory=list)
    compliance_mode: bool = False
    data_region: Optional[str] = None
    
    # Limits based on tier
    max_users: int = 100
    max_repositories: int = 50
    max_monthly_actions: int = 10000
    
    # Audit and compliance
    audit_retention_days: int = 90
    gdpr_enabled: bool = False
    soc2_enabled: bool = False
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tier": self.tier.value,
            "status": self.status.value,
            "default_autonomy_level": self.default_autonomy_level,
            "allowed_integrations": ",".join(self.allowed_integrations),
            "compliance_mode": self.compliance_mode,
            "data_region": self.data_region,
            "max_users": self.max_users,
            "max_repositories": self.max_repositories,
            "max_monthly_actions": self.max_monthly_actions,
            "audit_retention_days": self.audit_retention_days,
            "gdpr_enabled": self.gdpr_enabled,
            "soc2_enabled": self.soc2_enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrganizationConfig':
        """Create from dictionary"""
        return cls(
            id=data["id"],
            name=data["name"],
            slug=data["slug"],
            tier=OrgTier(data["tier"]),
            status=OrgStatus(data["status"]),
            default_autonomy_level=data.get("default_autonomy_level", 0.5),
            allowed_integrations=data.get("allowed_integrations", "").split(",") if data.get("allowed_integrations") else [],
            compliance_mode=data.get("compliance_mode", False),
            data_region=data.get("data_region"),
            max_users=data.get("max_users", 100),
            max_repositories=data.get("max_repositories", 50),
            max_monthly_actions=data.get("max_monthly_actions", 10000),
            audit_retention_days=data.get("audit_retention_days", 90),
            gdpr_enabled=data.get("gdpr_enabled", False),
            soc2_enabled=data.get("soc2_enabled", False),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow()
        )

@dataclass
class UserMembership:
    """User membership within an organization"""
    user_id: str
    org_id: str
    roles: List[TenantRole]
    permissions: List[str]
    team_ids: List[str] = field(default_factory=list)
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "org_id": self.org_id,
            "roles": ",".join([r.value for r in self.roles]),
            "permissions": ",".join(self.permissions),
            "team_ids": ",".join(self.team_ids),
            "joined_at": self.joined_at.isoformat(),
            "last_active": self.last_active.isoformat() if self.last_active else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserMembership':
        return cls(
            user_id=data["user_id"],
            org_id=data["org_id"],
            roles=[TenantRole(r) for r in data.get("roles", "").split(",") if r],
            permissions=data.get("permissions", "").split(",") if data.get("permissions") else [],
            team_ids=data.get("team_ids", "").split(",") if data.get("team_ids") else [],
            joined_at=datetime.fromisoformat(data["joined_at"]) if "joined_at" in data else datetime.utcnow(),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None
        )

class OrganizationRepository(TenantRepository):
    """Repository for organization management"""
    
    def __init__(self):
        super().__init__(get_tenant_db(), "organizations")
    
    async def create_organization(self, config: OrganizationConfig) -> OrganizationConfig:
        """Create new organization (system-level operation)"""
        data = config.to_dict()
        result = await self.create(data)
        return OrganizationConfig.from_dict(result)
    
    async def get_organization(self) -> Optional[OrganizationConfig]:
        """Get current organization"""
        tenant = require_tenant()
        org_data = await self.find_by_id(tenant.org_id)
        return OrganizationConfig.from_dict(org_data) if org_data else None
    
    @require_role(TenantRole.ORG_ADMIN)
    async def update_organization(self, updates: Dict[str, Any]) -> bool:
        """Update organization settings (admin only)"""
        tenant = require_tenant()
        updates["updated_at"] = datetime.utcnow().isoformat()
        return await self.update_by_id(tenant.org_id, updates)
    
    @require_role(TenantRole.ORG_ADMIN)
    async def delete_organization(self) -> bool:
        """Delete organization (admin only)"""
        tenant = require_tenant()
        return await self.delete_by_id(tenant.org_id)

class UserMembershipRepository(TenantRepository):
    """Repository for user memberships within organizations"""
    
    def __init__(self):
        super().__init__(get_tenant_db(), "user_memberships")
    
    async def add_user(self, user_id: str, roles: List[TenantRole], 
                      permissions: Optional[List[str]] = None) -> UserMembership:
        """Add user to organization"""
        tenant = require_tenant()
        membership = UserMembership(
            user_id=user_id,
            org_id=tenant.org_id,
            roles=roles,
            permissions=permissions or []
        )
        
        data = membership.to_dict()
        result = await self.create(data)
        return UserMembership.from_dict(result)
    
    async def get_user_membership(self, user_id: str) -> Optional[UserMembership]:
        """Get user's membership in current organization"""
        data = await self.find_one({"user_id": user_id})
        return UserMembership.from_dict(data) if data else None
    
    async def list_organization_users(self) -> List[UserMembership]:
        """List all users in current organization"""
        data_list = await self.find_all()
        return [UserMembership.from_dict(data) for data in data_list]
    
    @require_role(TenantRole.ORG_ADMIN)
    async def update_user_roles(self, user_id: str, 
                               roles: List[TenantRole]) -> bool:
        """Update user's roles (admin only)"""
        updates = {"roles": ",".join([r.value for r in roles])}
        count = await self.update({"user_id": user_id}, updates)
        return count > 0
    
    @require_role(TenantRole.ORG_ADMIN)
    async def remove_user(self, user_id: str) -> bool:
        """Remove user from organization (admin only)"""
        count = await self.delete({"user_id": user_id})
        return count > 0

class OrganizationService:
    """High-level organization management service"""
    
    def __init__(self):
        self.org_repo = OrganizationRepository()
        self.membership_repo = UserMembershipRepository()
    
    async def create_organization_with_admin(self, org_config: OrganizationConfig, 
                                           admin_user_id: str) -> OrganizationConfig:
        """Create organization and add admin user"""
        # This is a system-level operation, requires special handling
        # In practice, would be called during signup/onboarding
        
        # 1. Create organization
        org = await self.org_repo.create_organization(org_config)
        
        # 2. Create tenant context for new org
        admin_context = TenantContext(
            org_id=org.id,
            user_id=admin_user_id,
            roles=[TenantRole.ORG_ADMIN],
            permissions=["*"],  # Admin has all permissions
            session_id=str(uuid.uuid4()),
            encryption_key_id=f"org-{org.id}-key"
        )
        
        # 3. Add admin user with org context
        from .tenancy import with_tenant_context
        
        @with_tenant_context(admin_context)
        async def add_admin():
            return await self.membership_repo.add_user(
                admin_user_id, 
                [TenantRole.ORG_ADMIN],
                ["*"]
            )
        
        await add_admin()
        return org
    
    async def get_organization_info(self) -> Dict[str, Any]:
        """Get comprehensive organization information"""
        org = await self.org_repo.get_organization()
        if not org:
            raise ValueError("Organization not found")
        
        users = await self.membership_repo.list_organization_users()
        
        return {
            "organization": org.to_dict(),
            "user_count": len(users),
            "admin_count": len([u for u in users if TenantRole.ORG_ADMIN in u.roles]),
            "tier_limits": {
                "max_users": org.max_users,
                "max_repositories": org.max_repositories,
                "max_monthly_actions": org.max_monthly_actions
            },
            "compliance": {
                "gdpr_enabled": org.gdpr_enabled,
                "soc2_enabled": org.soc2_enabled,
                "audit_retention_days": org.audit_retention_days
            }
        }

# Global service instance
org_service = OrganizationService()

__all__ = [
    'OrganizationConfig',
    'UserMembership', 
    'OrgTier',
    'OrgStatus',
    'OrganizationRepository',
    'UserMembershipRepository',
    'OrganizationService',
    'org_service'
]
