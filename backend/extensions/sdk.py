"""
NAVI SDK - Development Kit for Extension Authors

This SDK provides easy-to-use APIs for developing NAVI extensions.
It handles authentication, API communication, and provides helper utilities
for common extension development patterns.

Usage:
    from navi_sdk import NaviClient, Extension, capability

    # Create extension
    ext = Extension("my-extension", "1.0.0", "My awesome extension")

    # Define capabilities
    @ext.capability("process_data")
    def process_data(inputs):
        return {"result": "processed"}

    # Register extension
    client = NaviClient(api_key="...")
    client.register_extension(ext)

Key Features:
- Simple extension definition API
- Automatic capability registration
- Built-in input/output validation
- Authentication and API management
- Local development and testing tools
- Extension packaging and deployment
"""

import json
import requests
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

# SDK Version
__version__ = "1.0.0"


class ExtensionType(Enum):
    SKILL = "skill"
    ACTION = "action"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    INTELLIGENCE = "intelligence"
    TOOL = "tool"


class Permission(Enum):
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    EXECUTE_COMMANDS = "execute_commands"
    NETWORK_ACCESS = "network_access"
    TENANT_DATA = "tenant_data"
    SYSTEM_INTEGRATION = "system_integration"


@dataclass
class CapabilityDefinition:
    """Definition of an extension capability"""

    name: str
    description: str
    function: Callable
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    async_execution: bool = False
    streaming: bool = False


class NaviClient:
    """Client for interacting with NAVI API"""

    def __init__(
        self, api_key: str, base_url: str = "https://api.navi.ai/v1", timeout: int = 30
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"navi-sdk/{__version__}",
            }
        )

    def start_initiative(
        self, goal: str, repo: str, mode: str = "semi-autonomous"
    ) -> Dict[str, Any]:
        """Start a new NAVI initiative"""
        response = self.session.post(
            f"{self.base_url}/initiatives",
            json={"goal": goal, "repo": repo, "mode": mode},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_initiative_status(self, initiative_id: str) -> Dict[str, Any]:
        """Get status of an initiative"""
        response = self.session.get(
            f"{self.base_url}/initiatives/{initiative_id}", timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def approve_action(self, approval_id: str) -> Dict[str, Any]:
        """Approve a pending action"""
        response = self.session.post(
            f"{self.base_url}/approvals/{approval_id}",
            json={"decision": "approve"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def execute_capability(
        self,
        capability_name: str,
        inputs: Dict[str, Any],
        preferred_extension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an extension capability"""
        response = self.session.post(
            f"{self.base_url}/extensions/execute",
            json={
                "capability_name": capability_name,
                "inputs": inputs,
                "preferred_extension": preferred_extension,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def list_capabilities(self) -> List[Dict[str, Any]]:
        """List available capabilities"""
        response = self.session.get(
            f"{self.base_url}/extensions/capabilities", timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def install_extension(
        self, extension_id: str, auto_approve: bool = False
    ) -> Dict[str, Any]:
        """Install an extension"""
        response = self.session.post(
            f"{self.base_url}/extensions/install",
            json={
                "extension_id": extension_id,
                "auto_approve_permissions": auto_approve,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def search_extensions(
        self, query: str = "", categories: Optional[List[str]] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search extensions in marketplace"""
        response = self.session.post(
            f"{self.base_url}/extensions/marketplace/search",
            json={"query": query, "categories": categories or [], "limit": limit},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def register_extension(self, extension: "Extension") -> Dict[str, Any]:
        """Register/publish an extension"""
        manifest = extension.to_manifest()

        response = self.session.post(
            f"{self.base_url}/extensions/publish",
            json={"manifest": manifest},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def validate_manifest(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extension manifest"""
        response = self.session.post(
            f"{self.base_url}/extensions/validate", json=manifest, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


class Extension:
    """Extension definition builder"""

    def __init__(
        self,
        id: str,
        version: str,
        name: str,
        description: str = "",
        author: str = "",
        extension_type: ExtensionType = ExtensionType.ACTION,
        category: str = "utility",
    ):
        self.id = id
        self.version = version
        self.name = name
        self.description = description
        self.author = author
        self.extension_type = extension_type
        self.category = category
        self.tags: List[str] = []
        self.permissions: List[Permission] = []
        self.dependencies: List[str] = []
        self.capabilities: List[CapabilityDefinition] = []
        self.environment: Dict[str, str] = {}

    def add_tag(self, tag: str) -> "Extension":
        """Add a tag to the extension"""
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def add_permission(self, permission: Permission) -> "Extension":
        """Add required permission"""
        if permission not in self.permissions:
            self.permissions.append(permission)
        return self

    def add_dependency(self, extension_id: str) -> "Extension":
        """Add dependency on another extension"""
        if extension_id not in self.dependencies:
            self.dependencies.append(extension_id)
        return self

    def set_environment(self, key: str, value: str) -> "Extension":
        """Set environment variable"""
        self.environment[key] = value
        return self

    def capability(
        self,
        name: str,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        async_execution: bool = False,
        streaming: bool = False,
    ):
        """Decorator to define extension capability"""

        def decorator(func: Callable):
            capability_def = CapabilityDefinition(
                name=name,
                description=description or func.__doc__ or "",
                function=func,
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                async_execution=async_execution,
                streaming=streaming,
            )
            self.capabilities.append(capability_def)
            return func

        return decorator

    def to_manifest(self) -> Dict[str, Any]:
        """Convert extension to manifest dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "extension_type": self.extension_type.value,
            "category": self.category,
            "tags": self.tags,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema,
                    "async_execution": cap.async_execution,
                    "streaming": cap.streaming,
                }
                for cap in self.capabilities
            ],
            "permissions": [perm.value for perm in self.permissions],
            "dependencies": self.dependencies,
            "entry_point": "main.py",
            "runtime": "python3.11",
            "environment": self.environment,
            "scope": "public",
            "trust_level": "community",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "state": "draft",
            "compliance_frameworks": [],
            "security_review_required": True,
            "data_access_patterns": [],
            "pricing": "free",
            "license": "MIT",
            "homepage_url": None,
            "documentation_url": None,
            "support_url": None,
        }

    def save_manifest(self, path: Union[str, Path] = "manifest.json"):
        """Save manifest to file"""
        manifest_path = Path(path)
        with open(manifest_path, "w") as f:
            json.dump(self.to_manifest(), f, indent=2)
        print(f"Manifest saved to {manifest_path}")


class ExtensionContext:
    """Execution context provided to extension capabilities"""

    def __init__(
        self,
        tenant_id: str,
        org_id: str,
        user_id: str,
        extension_id: str,
        capabilities: List[str],
        permissions: List[str],
        workspace_dir: str,
    ):
        self.tenant_id = tenant_id
        self.org_id = org_id
        self.user_id = user_id
        self.extension_id = extension_id
        self.capabilities = capabilities
        self.permissions = permissions
        self.workspace_dir = Path(workspace_dir)
        self.logs: List[str] = []

    def log(self, message: str, level: str = "info"):
        """Log a message"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level.upper()}] {message}"
        self.logs.append(log_entry)
        print(log_entry)

    def read_file(self, path: Union[str, Path]) -> str:
        """Read file from workspace (requires read_files permission)"""
        if "read_files" not in self.permissions:
            raise PermissionError("read_files permission required")

        file_path = self.workspace_dir / path
        try:
            return file_path.read_text()
        except Exception as e:
            self.log(f"Failed to read file {path}: {str(e)}", "error")
            raise

    def write_file(self, path: Union[str, Path], content: str):
        """Write file to workspace (requires write_files permission)"""
        if "write_files" not in self.permissions:
            raise PermissionError("write_files permission required")

        file_path = self.workspace_dir / path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            self.log(f"Wrote file {path}")
        except Exception as e:
            self.log(f"Failed to write file {path}: {str(e)}", "error")
            raise

    def request_approval(self, action: str, reason: str) -> bool:
        """Request user approval for action"""
        # In real implementation, this would integrate with approval system
        self.log(f"Approval requested: {action} - {reason}")
        return True  # Auto-approve for SDK demo

    def emit_insight(self, insight: Any):
        """Emit insight to NAVI system"""
        self.log(f"Insight emitted: {json.dumps(insight)}")


# Utility functions for extension development


def create_schema(
    properties: Dict[str, str], required: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Helper to create JSON schema for inputs/outputs"""
    return {
        "type": "object",
        "properties": {
            name: {"type": prop_type} for name, prop_type in properties.items()
        },
        "required": required or [],
    }


def validate_input(inputs: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Basic input validation against schema"""
    if schema.get("type") != "object":
        return True  # Skip validation for non-object schemas

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for required_field in required:
        if required_field not in inputs:
            return False

    # Check field types (basic validation)
    for field_name, value in inputs.items():
        if field_name in properties:
            expected_type = properties[field_name].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return False
            elif expected_type == "number" and not isinstance(value, (int, float)):
                return False
            elif expected_type == "boolean" and not isinstance(value, bool):
                return False
            elif expected_type == "array" and not isinstance(value, list):
                return False
            elif expected_type == "object" and not isinstance(value, dict):
                return False

    return True


class ExtensionTester:
    """Local testing utilities for extensions"""

    def __init__(self, extension: Extension):
        self.extension = extension

    def test_capability(
        self,
        capability_name: str,
        inputs: Dict[str, Any],
        mock_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Test extension capability locally"""
        # Find capability
        capability = None
        for cap in self.extension.capabilities:
            if cap.name == capability_name:
                capability = cap
                break

        if not capability:
            raise ValueError(f"Capability '{capability_name}' not found")

        # Validate inputs
        if capability.input_schema and not validate_input(
            inputs, capability.input_schema
        ):
            raise ValueError("Input validation failed")

        # Create mock context
        context_data = mock_context or {}
        context = ExtensionContext(
            tenant_id=context_data.get("tenant_id", "test-tenant"),
            org_id=context_data.get("org_id", "test-org"),
            user_id=context_data.get("user_id", "test-user"),
            extension_id=self.extension.id,
            capabilities=[cap.name for cap in self.extension.capabilities],
            permissions=[perm.value for perm in self.extension.permissions],
            workspace_dir=context_data.get("workspace_dir", "/tmp/test-workspace"),
        )

        # Execute capability
        try:
            if capability.async_execution:
                # Handle async execution (simplified)
                result = asyncio.run(capability.function(inputs, context))
            else:
                result = capability.function(inputs, context)

            return {"success": True, "output": result, "logs": context.logs}
        except Exception as e:
            return {"success": False, "error": str(e), "logs": context.logs}

    def validate_extension(self) -> Dict[str, Any]:
        """Validate extension definition"""
        errors = []
        warnings = []

        # Basic validation
        if not self.extension.id:
            errors.append("Extension ID is required")
        if not self.extension.name:
            errors.append("Extension name is required")
        if not self.extension.version:
            errors.append("Extension version is required")

        # Capability validation
        if not self.extension.capabilities:
            warnings.append("Extension defines no capabilities")

        for cap in self.extension.capabilities:
            if not cap.name:
                errors.append("Capability name is required")
            if not cap.function:
                errors.append(f"Capability '{cap.name}' has no function")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# Example extension templates


def create_ci_fixer_extension() -> Extension:
    """Example: CI Pipeline Fixer Extension"""
    ext = Extension(
        id="navi.ci.fixer",
        version="1.0.0",
        name="CI Pipeline Auto-Fixer",
        description="Automatically diagnose and fix common CI/CD pipeline failures",
        category="ci_cd",
        extension_type=ExtensionType.ACTION,
    )

    ext.add_tag("ci").add_tag("automation").add_tag("debugging")
    ext.add_permission(Permission.READ_FILES)
    ext.add_permission(Permission.WRITE_FILES)
    ext.add_permission(Permission.NETWORK_ACCESS)

    @ext.capability(
        name="fix_ci_failure",
        description="Analyze CI logs and apply automatic fixes",
        input_schema=create_schema(
            {
                "pipeline_id": "string",
                "failure_logs": "string",
                "repository_url": "string",
            },
            required=["pipeline_id", "failure_logs"],
        ),
    )
    def fix_ci_failure(inputs: Dict[str, Any], context: ExtensionContext):
        context.log("Starting CI failure analysis")

        # Mock CI fixing logic
        failure_logs = inputs["failure_logs"]
        fixes_applied = []

        if "npm test" in failure_logs and "command not found" in failure_logs:
            context.write_file(
                ".github/workflows/ci.yml",
                """
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm test
""",
            )
            fixes_applied.append("Added Node.js setup to CI workflow")

        context.log(f"Applied {len(fixes_applied)} fixes")

        return {
            "fixes_applied": fixes_applied,
            "success": len(fixes_applied) > 0,
            "pipeline_id": inputs["pipeline_id"],
        }

    return ext


def create_security_scanner_extension() -> Extension:
    """Example: Security Scanner Extension"""
    ext = Extension(
        id="navi.security.scanner",
        version="1.0.0",
        name="Security Vulnerability Scanner",
        description="Scan code for security vulnerabilities and suggest fixes",
        category="security",
        extension_type=ExtensionType.SKILL,
    )

    ext.add_tag("security").add_tag("vulnerability").add_tag("scanning")
    ext.add_permission(Permission.READ_FILES)
    ext.add_permission(Permission.NETWORK_ACCESS)

    @ext.capability(
        name="scan_vulnerabilities",
        description="Scan codebase for security vulnerabilities",
        input_schema=create_schema(
            {
                "scan_path": "string",
                "language": "string",
                "severity_threshold": "string",
            },
            required=["scan_path"],
        ),
    )
    def scan_vulnerabilities(inputs: Dict[str, Any], context: ExtensionContext):
        context.log("Starting security vulnerability scan")

        inputs["scan_path"]
        inputs.get("language", "auto")

        # Mock vulnerability scanning
        vulnerabilities = [
            {
                "file": "src/auth.py",
                "line": 42,
                "severity": "high",
                "type": "sql_injection",
                "description": "Potential SQL injection vulnerability",
                "suggestion": "Use parameterized queries",
            },
            {
                "file": "config/secrets.json",
                "line": 1,
                "severity": "critical",
                "type": "hardcoded_secret",
                "description": "Hardcoded API key detected",
                "suggestion": "Move secrets to environment variables",
            },
        ]

        context.log(f"Found {len(vulnerabilities)} vulnerabilities")

        return {
            "vulnerabilities": vulnerabilities,
            "scan_summary": {
                "total": len(vulnerabilities),
                "critical": sum(
                    1 for v in vulnerabilities if v["severity"] == "critical"
                ),
                "high": sum(1 for v in vulnerabilities if v["severity"] == "high"),
                "medium": sum(1 for v in vulnerabilities if v["severity"] == "medium"),
                "low": sum(1 for v in vulnerabilities if v["severity"] == "low"),
            },
        }

    return ext


# Export main SDK components
__all__ = [
    "NaviClient",
    "Extension",
    "ExtensionContext",
    "ExtensionTester",
    "ExtensionType",
    "Permission",
    "create_schema",
    "validate_input",
    "create_ci_fixer_extension",
    "create_security_scanner_extension",
]
