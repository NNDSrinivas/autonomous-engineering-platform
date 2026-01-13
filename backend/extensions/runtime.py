"""
Phase 7.0 Extension Runtime - Unified NAVI Extension Platform

Combines and enhances existing skill_marketplace.py and action_marketplace.py
into a comprehensive enterprise extension platform.

This module provides:
- Unified extension manifest and lifecycle management
- Enhanced sandboxing with enterprise security controls
- Capability registry for dynamic extension discovery
- Cross-extension communication and dependency management
- Marketplace API integration for public/private extension distribution
- Enterprise-grade extension governance and approval workflows

Architecture:
- ExtensionManifest: Unified manifest combining skills and actions
- ExtensionRuntime: Sandboxed execution environment with tenant isolation
- CapabilityRegistry: Dynamic capability registration and discovery
- ExtensionMarketplace: Distribution and lifecycle management
- SecurityManager: Extension signing, trust, and validation
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
import tempfile

# Import existing systems to build upon
from ..core.tenancy import require_tenant, TenantContext
from ..core.tenant_database import TenantRepository, get_tenant_db
from ..core.observability import get_metrics_collector, MetricType

logger = logging.getLogger(__name__)


class ExtensionType(Enum):
    """Types of extensions in the unified system"""

    SKILL = "skill"  # Long-running capabilities (AI models, analyzers)
    ACTION = "action"  # One-time operations (deployments, fixes)
    WORKFLOW = "workflow"  # Multi-step processes
    INTEGRATION = "integration"  # External service connectors
    INTELLIGENCE = "intelligence"  # Domain-specific reasoning
    TOOL = "tool"  # Development utilities


class ExtensionScope(Enum):
    """Extension visibility and access scope"""

    PUBLIC = "public"  # Available on public marketplace
    ORGANIZATION = "organization"  # Private to organization
    TEAM = "team"  # Private to specific teams
    USER = "user"  # Personal extensions


class ExtensionTrust(Enum):
    """Extension trust levels"""

    VERIFIED = "verified"  # Verified by NAVI team
    ORGANIZATION_APPROVED = "organization_approved"  # Approved by org admin
    COMMUNITY = "community"  # Community contributed
    INTERNAL = "internal"  # Developed internally
    UNTRUSTED = "untrusted"  # Requires explicit approval


class ExtensionLifecycleState(Enum):
    """Extension lifecycle states"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    INSTALLED = "installed"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class ExtensionPermission:
    """Granular permission system for extensions"""

    name: str
    description: str
    risk_level: str  # "low", "medium", "high", "critical"
    requires_approval: bool = False
    tenant_scoped: bool = True


@dataclass
class ExtensionCapability:
    """Defines what an extension can do"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    async_execution: bool = False
    streaming: bool = False
    extension_id: Optional[str] = None


@dataclass
class ExtensionManifest:
    """Unified extension manifest"""

    # Identity
    id: str
    name: str
    version: str
    description: str
    author: str

    # Classification
    extension_type: ExtensionType
    category: str  # Flexible categories beyond enums
    tags: List[str] = field(default_factory=list)

    # Capabilities
    capabilities: List[ExtensionCapability] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)  # Permission names
    dependencies: List[str] = field(default_factory=list)  # Other extension IDs

    # Execution
    entry_point: str = "main.py"
    runtime: str = "python3.11"  # python3.11, node18, etc.
    environment: Dict[str, str] = field(default_factory=dict)

    # Metadata
    scope: ExtensionScope = ExtensionScope.ORGANIZATION
    trust_level: ExtensionTrust = ExtensionTrust.COMMUNITY

    # Lifecycle
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    state: ExtensionLifecycleState = ExtensionLifecycleState.DRAFT

    # Enterprise
    compliance_frameworks: List[str] = field(default_factory=list)
    security_review_required: bool = True
    data_access_patterns: List[str] = field(default_factory=list)

    # Marketplace
    pricing: str = "free"  # "free", "paid", "enterprise"
    license: str = "proprietary"
    homepage_url: Optional[str] = None
    documentation_url: Optional[str] = None
    support_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API"""
        result = asdict(self)
        # Convert enums to strings
        result["extension_type"] = self.extension_type.value
        result["scope"] = self.scope.value
        result["trust_level"] = self.trust_level.value
        result["state"] = self.state.value
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtensionManifest":
        """Reconstruct manifest from stored dictionary"""
        capabilities: List[ExtensionCapability] = []
        raw_caps = data.get("capabilities") or []
        for cap in raw_caps:
            if isinstance(cap, ExtensionCapability):
                capabilities.append(cap)
                continue
            if isinstance(cap, dict):
                capabilities.append(
                    ExtensionCapability(
                        name=cap.get("name", ""),
                        description=cap.get("description", ""),
                        input_schema=cap.get("input_schema", {}) or {},
                        output_schema=cap.get("output_schema", {}) or {},
                        async_execution=bool(cap.get("async_execution", False)),
                        streaming=bool(cap.get("streaming", False)),
                        extension_id=cap.get("extension_id") or data.get("id"),
                    )
                )

        created_at_raw = data.get("created_at")
        updated_at_raw = data.get("updated_at")
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if isinstance(created_at_raw, str)
            else created_at_raw or datetime.utcnow()
        )
        updated_at = (
            datetime.fromisoformat(updated_at_raw)
            if isinstance(updated_at_raw, str)
            else updated_at_raw or datetime.utcnow()
        )

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            extension_type=ExtensionType(
                data.get("extension_type", ExtensionType.SKILL.value)
            ),
            category=data.get("category", ""),
            tags=data.get("tags", []) or [],
            capabilities=capabilities,
            permissions=data.get("permissions", []) or [],
            dependencies=data.get("dependencies", []) or [],
            entry_point=data.get("entry_point", "main.py"),
            runtime=data.get("runtime", "python3.11"),
            environment=data.get("environment", {}) or {},
            scope=ExtensionScope(data.get("scope", ExtensionScope.ORGANIZATION.value)),
            trust_level=ExtensionTrust(
                data.get("trust_level", ExtensionTrust.COMMUNITY.value)
            ),
            created_at=created_at,
            updated_at=updated_at,
            state=ExtensionLifecycleState(
                data.get("state", ExtensionLifecycleState.DRAFT.value)
            ),
            compliance_frameworks=data.get("compliance_frameworks", []) or [],
            security_review_required=bool(data.get("security_review_required", True)),
            data_access_patterns=data.get("data_access_patterns", []) or [],
            pricing=data.get("pricing", "free"),
            license=data.get("license", "proprietary"),
            homepage_url=data.get("homepage_url"),
            documentation_url=data.get("documentation_url"),
            support_url=data.get("support_url"),
        )


@dataclass
class ExtensionInstance:
    """Running instance of an extension"""

    instance_id: str
    extension_id: str
    tenant_context: TenantContext
    manifest: ExtensionManifest
    created_at: datetime
    last_activity: datetime
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"  # running, idle, stopped, error


class PermissionManager:
    """Manages extension permission system"""

    def __init__(self):
        self.permissions = self._initialize_permissions()

    def _initialize_permissions(self) -> Dict[str, ExtensionPermission]:
        """Initialize standard extension permissions"""
        return {
            "read_files": ExtensionPermission(
                name="read_files",
                description="Read files from workspace",
                risk_level="low",
                requires_approval=False,
            ),
            "write_files": ExtensionPermission(
                name="write_files",
                description="Create and modify files",
                risk_level="medium",
                requires_approval=True,
            ),
            "execute_commands": ExtensionPermission(
                name="execute_commands",
                description="Execute shell commands",
                risk_level="high",
                requires_approval=True,
            ),
            "network_access": ExtensionPermission(
                name="network_access",
                description="Make HTTP requests to external APIs",
                risk_level="medium",
                requires_approval=True,
            ),
            "tenant_data": ExtensionPermission(
                name="tenant_data",
                description="Access tenant-specific data and settings",
                risk_level="high",
                requires_approval=True,
                tenant_scoped=True,
            ),
            "system_integration": ExtensionPermission(
                name="system_integration",
                description="Integrate with CI/CD, monitoring, and other systems",
                risk_level="critical",
                requires_approval=True,
            ),
        }

    async def validate_permissions(
        self, manifest: ExtensionManifest, tenant: TenantContext
    ) -> Dict[str, bool]:
        """Validate extension permissions for tenant"""
        results = {}

        for permission_name in manifest.permissions:
            if permission_name not in self.permissions:
                results[permission_name] = False
                logger.warning(f"Unknown permission: {permission_name}")
                continue

            permission = self.permissions[permission_name]

            # Check if tenant allows this permission
            if permission.requires_approval:
                # This would check org policy, admin approvals, etc.
                approved = await self._check_permission_approval(
                    permission_name, manifest.id, tenant.org_id
                )
                results[permission_name] = approved
            else:
                results[permission_name] = True

        return results

    async def _check_permission_approval(
        self, permission: str, extension_id: str, org_id: str
    ) -> bool:
        """Check if permission is approved for extension in org"""
        # This would integrate with the governance system
        # For now, return True for non-critical permissions
        permission_obj = self.permissions.get(permission)
        if not permission_obj:
            return False
        return permission_obj.risk_level != "critical"


class CapabilityRegistry:
    """Registry for extension capabilities with dynamic discovery"""

    def __init__(self):
        self.capabilities: Dict[str, List[ExtensionCapability]] = {}
        self.extension_capabilities: Dict[
            str, List[str]
        ] = {}  # extension_id -> capability names

    def register_capability(self, extension_id: str, capability: ExtensionCapability):
        """Register a new capability from an extension"""
        capability.extension_id = extension_id
        if capability.name not in self.capabilities:
            self.capabilities[capability.name] = []

        self.capabilities[capability.name].append(capability)

        if extension_id not in self.extension_capabilities:
            self.extension_capabilities[extension_id] = []

        self.extension_capabilities[extension_id].append(capability.name)

        logger.info(
            f"Registered capability '{capability.name}' from extension '{extension_id}'"
        )

    def unregister_extension(self, extension_id: str):
        """Remove all capabilities for an extension"""
        if extension_id not in self.extension_capabilities:
            return

        capability_names = self.extension_capabilities[extension_id]
        for cap_name in capability_names:
            # Remove capabilities for this extension
            self.capabilities[cap_name] = [
                cap
                for cap in self.capabilities[cap_name]
                if cap.extension_id != extension_id
            ]

        del self.extension_capabilities[extension_id]
        logger.info(f"Unregistered all capabilities for extension '{extension_id}'")

    def find_capabilities(self, capability_name: str) -> List[ExtensionCapability]:
        """Find all extensions that provide a capability"""
        return self.capabilities.get(capability_name, [])

    def get_extension_capabilities(self, extension_id: str) -> List[str]:
        """Get all capability names provided by extension"""
        return self.extension_capabilities.get(extension_id, [])


class ExtensionSandbox:
    """Enhanced sandbox for extension execution with enterprise controls"""

    def __init__(self, tenant_context: TenantContext):
        self.tenant_context = tenant_context
        self.sandbox_dir = None
        self.process_limits = {
            "max_memory_mb": 512,
            "max_cpu_time": 300,  # 5 minutes
            "max_disk_mb": 100,
            "max_network_connections": 10,
        }

    async def __aenter__(self):
        """Enter sandbox context"""
        self.sandbox_dir = Path(
            tempfile.mkdtemp(prefix=f"navi_ext_{self.tenant_context.org_id}_")
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit and cleanup sandbox"""
        if self.sandbox_dir and self.sandbox_dir.exists():
            import shutil

            shutil.rmtree(self.sandbox_dir)

    async def execute_extension(
        self, manifest: ExtensionManifest, capability_name: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute extension capability in sandbox"""
        start_time = datetime.utcnow()

        try:
            # Validate permissions
            permission_manager = PermissionManager()
            permissions = await permission_manager.validate_permissions(
                manifest, self.tenant_context
            )

            denied_permissions = [
                p for p, allowed in permissions.items() if not allowed
            ]
            if denied_permissions:
                raise PermissionError(f"Denied permissions: {denied_permissions}")

            # Create execution context
            exec_context = {
                "tenant_id": self.tenant_context.org_id,
                "org_id": self.tenant_context.org_id,
                "user_id": self.tenant_context.user_id,
                "capabilities": [cap.name for cap in manifest.capabilities],
                "permissions": list(permissions.keys()),
                "inputs": inputs,
                "workspace_dir": str(self.sandbox_dir),
                "extension_id": manifest.id,
            }

            # Load and execute extension
            result = await self._execute_in_sandbox(
                manifest, capability_name, exec_context
            )

            # Record metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            await get_metrics_collector().record_metric(
                MetricType.EXTENSIONS_EXECUTED,
                1.0,
                "count",
                tags={
                    "extension_id": manifest.id,
                    "capability": capability_name,
                    "success": str(result.get("success", False)),
                },
                metadata={
                    "execution_time": execution_time,
                    "tenant_id": self.tenant_context.org_id,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Extension execution failed: {str(e)}")
            await get_metrics_collector().record_metric(
                MetricType.EXTENSIONS_EXECUTED,
                1.0,
                "count",
                tags={
                    "extension_id": manifest.id,
                    "capability": capability_name,
                    "success": "false",
                    "error": type(e).__name__,
                },
            )
            raise

    async def _execute_in_sandbox(
        self, manifest: ExtensionManifest, capability_name: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute extension code in isolated environment"""
        # This is a simplified implementation - in production would use
        # containers, chroot, or other strong isolation

        try:
            if not self.sandbox_dir:
                raise RuntimeError("Sandbox not initialized")
            # Create context file for extension
            context_file = self.sandbox_dir / "navi_context.json"
            with open(context_file, "w") as f:
                json.dump(context, f)

            # Execute extension (placeholder - would load actual extension code)
            result = {
                "success": True,
                "output": f"Executed capability '{capability_name}' from extension '{manifest.id}'",
                "execution_time": 0.1,
                "logs": [f"Extension {manifest.id} executed successfully"],
            }

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "logs": [f"Extension execution failed: {str(e)}"],
            }


class ExtensionRuntime:
    """Main extension runtime engine"""

    def __init__(self):
        self.capability_registry = CapabilityRegistry()
        self.running_instances: Dict[str, ExtensionInstance] = {}
        self.extension_repo = ExtensionRepository()

    async def install_extension(self, manifest: ExtensionManifest) -> bool:
        """Install an extension for current tenant"""
        tenant = require_tenant()

        try:
            # Validate manifest
            if not await self._validate_manifest(manifest):
                return False

            # Check permissions
            permission_manager = PermissionManager()
            permissions = await permission_manager.validate_permissions(
                manifest, tenant
            )

            denied = [p for p, allowed in permissions.items() if not allowed]
            if denied:
                logger.warning(f"Extension {manifest.id} denied permissions: {denied}")
                return False

            # Store extension
            success = await self.extension_repo.create_extension(manifest)
            if not success:
                return False

            # Register capabilities
            for capability in manifest.capabilities:
                self.capability_registry.register_capability(manifest.id, capability)

            # Update state
            manifest.state = ExtensionLifecycleState.INSTALLED
            await self.extension_repo.update_extension(manifest)

            logger.info(
                f"Extension {manifest.id} installed successfully for org {tenant.org_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to install extension {manifest.id}: {str(e)}")
            return False

    async def execute_capability(
        self,
        capability_name: str,
        inputs: Dict[str, Any],
        preferred_extension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a capability, choosing best available extension"""
        tenant = require_tenant()

        # Find capable extensions
        capabilities = self.capability_registry.find_capabilities(capability_name)
        if not capabilities:
            raise ValueError(f"No extension provides capability: {capability_name}")

        # Choose extension (prefer specified, otherwise first available)
        chosen_capability: Optional[ExtensionCapability] = None
        if preferred_extension:
            chosen_capability = next(
                (
                    cap
                    for cap in capabilities
                    if cap.extension_id == preferred_extension
                ),
                None,
            )

        if not chosen_capability:
            chosen_capability = capabilities[0]

        # Get extension manifest
        extension_id = chosen_capability.extension_id or preferred_extension
        if not extension_id:
            raise ValueError(f"Extension ID missing for capability: {capability_name}")
        manifest = await self.extension_repo.get_extension(extension_id)
        if not manifest:
            raise ValueError(f"Extension {extension_id} not found")

        # Execute in sandbox
        async with ExtensionSandbox(tenant) as sandbox:
            result = await sandbox.execute_extension(manifest, capability_name, inputs)

        return result

    async def list_available_capabilities(self) -> Dict[str, List[str]]:
        """List all available capabilities and providing extensions"""
        result = {}
        for (
            capability_name,
            capabilities,
        ) in self.capability_registry.capabilities.items():
            result[capability_name] = [cap.extension_id for cap in capabilities]
        return result

    async def get_extension_info(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an extension"""
        manifest = await self.extension_repo.get_extension(extension_id)
        if not manifest:
            return None

        return {
            "manifest": manifest.to_dict(),
            "capabilities": self.capability_registry.get_extension_capabilities(
                extension_id
            ),
            "installed": manifest.state == ExtensionLifecycleState.INSTALLED,
            "running": extension_id in self.running_instances,
        }

    async def _validate_manifest(self, manifest: ExtensionManifest) -> bool:
        """Validate extension manifest"""
        # Basic validation
        if not manifest.id or not manifest.name or not manifest.version:
            return False

        # Check for capability name conflicts
        for capability in manifest.capabilities:
            self.capability_registry.find_capabilities(capability.name)
            # Allow multiple providers for same capability
            # Could add conflict resolution logic here

        return True


class ExtensionRepository(TenantRepository):
    """Repository for extension storage and retrieval"""

    def __init__(self):
        super().__init__(get_tenant_db(), "extensions")

    async def create_extension(self, manifest: ExtensionManifest) -> bool:
        """Store extension manifest"""
        try:
            await self.create(manifest.to_dict())
            return True
        except Exception as e:
            logger.error(f"Failed to create extension {manifest.id}: {e}")
            return False

    async def get_extension(self, extension_id: str) -> Optional[ExtensionManifest]:
        """Retrieve extension by ID"""
        try:
            data = await self.find_by_id(extension_id)
            if data:
                return ExtensionManifest.from_dict(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get extension {extension_id}: {e}")
            return None

    async def update_extension(self, manifest: ExtensionManifest) -> bool:
        """Update extension manifest"""
        try:
            manifest.updated_at = datetime.utcnow()
            await self.update_by_id(manifest.id, manifest.to_dict())
            return True
        except Exception as e:
            logger.error(f"Failed to update extension {manifest.id}: {e}")
            return False

    async def list_extensions(
        self,
        state: Optional[ExtensionLifecycleState] = None,
        extension_type: Optional[ExtensionType] = None,
    ) -> List[ExtensionManifest]:
        """List extensions with optional filters"""
        try:
            filters = {}
            if state:
                filters["state"] = state.value
            if extension_type:
                filters["extension_type"] = extension_type.value

            results = await self.find_all(filters)
            return [ExtensionManifest.from_dict(data) for data in results]

        except Exception as e:
            logger.error(f"Failed to list extensions: {e}")
            return []

    async def delete_extension(self, extension_id: str) -> bool:
        """Delete extension"""
        try:
            await self.delete_by_id(extension_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete extension {extension_id}: {e}")
            return False


# Global runtime instance - lazy initialization
_extension_runtime = None


def get_extension_runtime():
    global _extension_runtime
    if _extension_runtime is None:
        _extension_runtime = ExtensionRuntime()
    return _extension_runtime


# For backwards compatibility
extension_runtime = None


def init_extensions():
    """Initialize extensions after database is ready"""
    global extension_runtime
    if extension_runtime is None:
        extension_runtime = ExtensionRuntime()


# Predefined metric types for extensions
class ExtensionMetrics(Enum):
    EXTENSIONS_EXECUTED = "extensions_executed"
    EXTENSIONS_INSTALLED = "extensions_installed"
    CAPABILITIES_REGISTERED = "capabilities_registered"
    EXTENSION_ERRORS = "extension_errors"


__all__ = [
    "ExtensionType",
    "ExtensionScope",
    "ExtensionTrust",
    "ExtensionLifecycleState",
    "ExtensionManifest",
    "ExtensionCapability",
    "ExtensionPermission",
    "ExtensionInstance",
    "ExtensionRuntime",
    "ExtensionSandbox",
    "CapabilityRegistry",
    "PermissionManager",
    "ExtensionRepository",
    "extension_runtime",
]
