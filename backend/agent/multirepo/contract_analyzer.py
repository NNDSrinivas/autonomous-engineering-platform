"""
ContractAnalyzer — API & Schema Intelligence

API and schema contract analyzer that detects breaking changes in REST APIs,
GraphQL schemas, event schemas, and shared DTOs. This enables NAVI to understand
contract compatibility and prevent breaking changes across repositories.

Key Capabilities:
- Analyze REST API specifications (OpenAPI, Swagger)
- Parse GraphQL schemas for breaking changes
- Detect event schema modifications
- Analyze shared data transfer objects (DTOs)
- Calculate breaking change impact and compatibility scores
"""

import logging
import json
import re
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class BreakingChangeType(Enum):
    """Types of breaking changes"""

    FIELD_REMOVED = "field_removed"
    FIELD_TYPE_CHANGED = "field_type_changed"
    FIELD_MADE_REQUIRED = "field_made_required"
    ENDPOINT_REMOVED = "endpoint_removed"
    HTTP_METHOD_CHANGED = "http_method_changed"
    RESPONSE_FORMAT_CHANGED = "response_format_changed"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    SCHEMA_VERSION_INCOMPATIBLE = "schema_version_incompatible"
    QUERY_REMOVED = "query_removed"  # GraphQL
    MUTATION_CHANGED = "mutation_changed"  # GraphQL
    EVENT_FORMAT_CHANGED = "event_format_changed"


class ChangeImpact(Enum):
    """Impact levels for contract changes"""

    NONE = "none"
    PATCH = "patch"  # Backward compatible
    MINOR = "minor"  # New features, backward compatible
    MAJOR = "major"  # Breaking changes
    CRITICAL = "critical"  # System-wide breaking changes


@dataclass
class BreakingChange:
    """Represents a breaking change in a contract"""

    change_type: BreakingChangeType
    field_path: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: str = ""
    impact: ChangeImpact = ChangeImpact.MAJOR
    affected_endpoints: List[str] = field(default_factory=list)
    mitigation: Optional[str] = None


@dataclass
class ContractChange:
    """Complete analysis of contract changes"""

    file_path: str
    contract_type: str  # "openapi", "graphql", "json_schema", "proto"
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    non_breaking_changes: List[str] = field(default_factory=list)
    overall_impact: ChangeImpact = ChangeImpact.NONE
    compatibility_score: float = 1.0  # 0.0 - 1.0
    version_change_suggested: str = "patch"  # patch, minor, major
    affected_consumers: List[str] = field(default_factory=list)
    migration_required: bool = False


@dataclass
class APIContract:
    """Represents an API contract"""

    file_path: str
    contract_type: str
    version: Optional[str] = None
    endpoints: List[str] = field(default_factory=list)
    schemas: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContractAnalyzer:
    """
    Analyzer for API contracts and schemas that can detect breaking changes
    and assess compatibility impact across repository boundaries.
    """

    def __init__(self):
        """Initialize the contract analyzer"""
        self.supported_formats = [
            "openapi",
            "swagger",
            "json_schema",
            "graphql",
            "protobuf",
            "avro",
            "asyncapi",
        ]
        logger.info("ContractAnalyzer initialized for multi-format contract analysis")

    def analyze_contract_changes(
        self,
        old_file_path: str,
        new_file_path: str,
        contract_type: Optional[str] = None,
    ) -> ContractChange:
        """
        Analyze changes between two contract files

        Args:
            old_file_path: Path to the old contract file
            new_file_path: Path to the new contract file
            contract_type: Type of contract (auto-detected if None)

        Returns:
            Complete analysis of contract changes
        """
        old_path = Path(old_file_path)
        new_path = Path(new_file_path)

        if not old_path.exists() or not new_path.exists():
            logger.warning(
                f"Contract file not found: {old_file_path} or {new_file_path}"
            )
            return ContractChange(file_path=new_file_path, contract_type="unknown")

        # Auto-detect contract type if not provided
        if contract_type is None:
            contract_type = self._detect_contract_type(new_path)

        logger.info(
            f"Analyzing {contract_type} contract changes: {old_file_path} -> {new_file_path}"
        )

        # Parse contracts based on type
        if contract_type in ["openapi", "swagger"]:
            return self._analyze_openapi_changes(old_path, new_path)
        elif contract_type == "graphql":
            return self._analyze_graphql_changes(old_path, new_path)
        elif contract_type == "json_schema":
            return self._analyze_json_schema_changes(old_path, new_path)
        elif contract_type == "protobuf":
            return self._analyze_protobuf_changes(old_path, new_path)
        elif contract_type == "avro":
            return self._analyze_avro_changes(old_path, new_path)
        else:
            logger.warning(f"Unsupported contract type: {contract_type}")
            return ContractChange(file_path=new_file_path, contract_type=contract_type)

    def discover_contracts(self, repo_path: str) -> List[APIContract]:
        """
        Discover API contracts in a repository

        Args:
            repo_path: Path to the repository

        Returns:
            List of discovered contracts
        """
        repo_path = Path(repo_path)
        contracts = []

        # Common contract file patterns
        patterns = {
            "openapi": [
                "**/*openapi*.{yaml,yml,json}",
                "**/*swagger*.{yaml,yml,json}",
                "**/api-docs*.{yaml,yml,json}",
            ],
            "graphql": ["**/*.graphql", "**/*.gql", "**/schema.graphql"],
            "json_schema": ["**/*schema*.json", "**/schemas/**/*.json"],
            "protobuf": ["**/*.proto"],
            "avro": ["**/*.avsc", "**/*.avro"],
        }

        for contract_type, file_patterns in patterns.items():
            for pattern in file_patterns:
                for file_path in repo_path.glob(pattern):
                    contract = self._parse_contract(file_path, contract_type)
                    if contract:
                        contracts.append(contract)

        logger.info(f"Discovered {len(contracts)} contracts in {repo_path}")
        return contracts

    def _detect_contract_type(self, file_path: Path) -> str:
        """Auto-detect contract type from file"""
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()

        if "openapi" in name or "swagger" in name:
            return "openapi"
        elif suffix in [".graphql", ".gql"]:
            return "graphql"
        elif "schema" in name and suffix == ".json":
            return "json_schema"
        elif suffix == ".proto":
            return "protobuf"
        elif suffix in [".avsc", ".avro"]:
            return "avro"
        elif suffix in [".yaml", ".yml", ".json"]:
            # Try to detect from content
            try:
                content = file_path.read_text()
                if "openapi" in content.lower() or "swagger" in content.lower():
                    return "openapi"
                elif "$schema" in content and "json-schema" in content:
                    return "json_schema"
            except Exception:
                pass

        return "unknown"

    def _analyze_openapi_changes(
        self, old_path: Path, new_path: Path
    ) -> ContractChange:
        """Analyze changes in OpenAPI/Swagger specifications"""
        try:
            old_spec = self._load_yaml_or_json(old_path)
            new_spec = self._load_yaml_or_json(new_path)

            breaking_changes = []
            non_breaking_changes = []

            # Check version changes
            old_spec.get("info", {}).get("version", "1.0.0")
            new_spec.get("info", {}).get("version", "1.0.0")

            # Analyze paths (endpoints)
            old_paths = set(old_spec.get("paths", {}).keys())
            new_paths = set(new_spec.get("paths", {}).keys())

            # Removed endpoints are breaking
            removed_paths = old_paths - new_paths
            for path in removed_paths:
                breaking_changes.append(
                    BreakingChange(
                        change_type=BreakingChangeType.ENDPOINT_REMOVED,
                        field_path=path,
                        description=f"Endpoint {path} was removed",
                        impact=ChangeImpact.MAJOR,
                    )
                )

            # New endpoints are non-breaking
            added_paths = new_paths - old_paths
            for path in added_paths:
                non_breaking_changes.append(f"Added new endpoint: {path}")

            # Analyze existing endpoints for changes
            common_paths = old_paths & new_paths
            for path in common_paths:
                old_path_spec = old_spec["paths"][path]
                new_path_spec = new_spec["paths"][path]

                path_changes = self._analyze_openapi_path_changes(
                    path, old_path_spec, new_path_spec
                )
                breaking_changes.extend(path_changes)

            # Analyze schema changes
            schema_changes = self._analyze_openapi_schema_changes(
                old_spec.get("components", {}).get("schemas", {}),
                new_spec.get("components", {}).get("schemas", {}),
            )
            breaking_changes.extend(schema_changes)

            # Calculate overall impact
            if any(bc.impact == ChangeImpact.CRITICAL for bc in breaking_changes):
                overall_impact = ChangeImpact.CRITICAL
                version_suggestion = "major"
            elif any(bc.impact == ChangeImpact.MAJOR for bc in breaking_changes):
                overall_impact = ChangeImpact.MAJOR
                version_suggestion = "major"
            elif non_breaking_changes:
                overall_impact = ChangeImpact.MINOR
                version_suggestion = "minor"
            else:
                overall_impact = ChangeImpact.PATCH
                version_suggestion = "patch"

            # Calculate compatibility score
            compatibility_score = max(0.0, 1.0 - (len(breaking_changes) * 0.2))

            return ContractChange(
                file_path=str(new_path),
                contract_type="openapi",
                breaking_changes=breaking_changes,
                non_breaking_changes=non_breaking_changes,
                overall_impact=overall_impact,
                compatibility_score=compatibility_score,
                version_change_suggested=version_suggestion,
                migration_required=len(breaking_changes) > 0,
            )

        except Exception as e:
            logger.error(f"Failed to analyze OpenAPI changes: {e}")
            return ContractChange(file_path=str(new_path), contract_type="openapi")

    def _analyze_openapi_path_changes(
        self, path: str, old_spec: Dict[str, Any], new_spec: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Analyze changes in a specific OpenAPI path"""
        breaking_changes = []

        # Check HTTP methods
        old_methods = set(old_spec.keys())
        new_methods = set(new_spec.keys())

        # Removed HTTP methods are breaking
        removed_methods = old_methods - new_methods
        for method in removed_methods:
            breaking_changes.append(
                BreakingChange(
                    change_type=BreakingChangeType.HTTP_METHOD_CHANGED,
                    field_path=f"{path}:{method}",
                    description=f"HTTP method {method.upper()} removed from {path}",
                    impact=ChangeImpact.MAJOR,
                )
            )

        # Analyze common methods
        common_methods = old_methods & new_methods
        for method in common_methods:
            old_method_spec = old_spec[method]
            new_method_spec = new_spec[method]

            # Check parameters
            old_params = {
                p.get("name"): p for p in old_method_spec.get("parameters", [])
            }
            new_params = {
                p.get("name"): p for p in new_method_spec.get("parameters", [])
            }

            # Removed parameters are breaking
            removed_params = set(old_params.keys()) - set(new_params.keys())
            for param in removed_params:
                if old_params[param].get("required", False):
                    breaking_changes.append(
                        BreakingChange(
                            change_type=BreakingChangeType.FIELD_REMOVED,
                            field_path=f"{path}:{method}:params:{param}",
                            description=f"Required parameter {param} removed",
                            impact=ChangeImpact.MAJOR,
                        )
                    )

            # Parameters made required are breaking
            for param_name in set(old_params.keys()) & set(new_params.keys()):
                old_required = old_params[param_name].get("required", False)
                new_required = new_params[param_name].get("required", False)

                if not old_required and new_required:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=BreakingChangeType.FIELD_MADE_REQUIRED,
                            field_path=f"{path}:{method}:params:{param_name}",
                            description=f"Parameter {param_name} is now required",
                            impact=ChangeImpact.MAJOR,
                        )
                    )

        return breaking_changes

    def _analyze_openapi_schema_changes(
        self, old_schemas: Dict[str, Any], new_schemas: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Analyze changes in OpenAPI schemas"""
        breaking_changes = []

        # Check removed schemas
        removed_schemas = set(old_schemas.keys()) - set(new_schemas.keys())
        for schema_name in removed_schemas:
            breaking_changes.append(
                BreakingChange(
                    change_type=BreakingChangeType.FIELD_REMOVED,
                    field_path=f"schemas:{schema_name}",
                    description=f"Schema {schema_name} was removed",
                    impact=ChangeImpact.MAJOR,
                )
            )

        # Analyze common schemas
        common_schemas = set(old_schemas.keys()) & set(new_schemas.keys())
        for schema_name in common_schemas:
            old_schema = old_schemas[schema_name]
            new_schema = new_schemas[schema_name]

            schema_changes = self._analyze_json_schema_object_changes(
                f"schemas:{schema_name}", old_schema, new_schema
            )
            breaking_changes.extend(schema_changes)

        return breaking_changes

    def _analyze_json_schema_changes(
        self, old_path: Path, new_path: Path
    ) -> ContractChange:
        """Analyze changes in JSON Schema files"""
        try:
            old_schema = json.loads(old_path.read_text())
            new_schema = json.loads(new_path.read_text())

            breaking_changes = self._analyze_json_schema_object_changes(
                "root", old_schema, new_schema
            )

            overall_impact = (
                ChangeImpact.MAJOR if breaking_changes else ChangeImpact.PATCH
            )
            compatibility_score = max(0.0, 1.0 - (len(breaking_changes) * 0.3))

            return ContractChange(
                file_path=str(new_path),
                contract_type="json_schema",
                breaking_changes=breaking_changes,
                overall_impact=overall_impact,
                compatibility_score=compatibility_score,
                migration_required=len(breaking_changes) > 0,
            )

        except Exception as e:
            logger.error(f"Failed to analyze JSON Schema changes: {e}")
            return ContractChange(file_path=str(new_path), contract_type="json_schema")

    def _analyze_json_schema_object_changes(
        self, path: str, old_schema: Dict[str, Any], new_schema: Dict[str, Any]
    ) -> List[BreakingChange]:
        """Analyze changes in JSON Schema objects"""
        breaking_changes = []

        # Check properties
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})

        # Removed properties are potentially breaking
        removed_props = set(old_props.keys()) - set(new_props.keys())
        for prop in removed_props:
            breaking_changes.append(
                BreakingChange(
                    change_type=BreakingChangeType.FIELD_REMOVED,
                    field_path=f"{path}.{prop}",
                    description=f"Property {prop} was removed",
                    impact=ChangeImpact.MAJOR,
                )
            )

        # Check required fields
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        # Newly required fields are breaking
        newly_required = new_required - old_required
        for required_field in newly_required:
            breaking_changes.append(
                BreakingChange(
                    change_type=BreakingChangeType.FIELD_MADE_REQUIRED,
                    field_path=f"{path}.{field}",
                    description=f"Field {field} is now required",
                    impact=ChangeImpact.MAJOR,
                )
            )

        # Check type changes in common properties
        common_props = set(old_props.keys()) & set(new_props.keys())
        for prop in common_props:
            old_prop_type = old_props[prop].get("type")
            new_prop_type = new_props[prop].get("type")

            if old_prop_type and new_prop_type and old_prop_type != new_prop_type:
                breaking_changes.append(
                    BreakingChange(
                        change_type=BreakingChangeType.FIELD_TYPE_CHANGED,
                        field_path=f"{path}.{prop}",
                        old_value=old_prop_type,
                        new_value=new_prop_type,
                        description=f"Property {prop} type changed from {old_prop_type} to {new_prop_type}",
                        impact=ChangeImpact.MAJOR,
                    )
                )

        return breaking_changes

    def _analyze_graphql_changes(
        self, old_path: Path, new_path: Path
    ) -> ContractChange:
        """Analyze changes in GraphQL schemas"""
        try:
            old_schema_text = old_path.read_text()
            new_schema_text = new_path.read_text()

            # Simple GraphQL parsing (would use proper GraphQL parser in production)
            old_types = self._extract_graphql_types(old_schema_text)
            new_types = self._extract_graphql_types(new_schema_text)

            breaking_changes = []

            # Check removed types
            removed_types = set(old_types.keys()) - set(new_types.keys())
            for type_name in removed_types:
                breaking_changes.append(
                    BreakingChange(
                        change_type=BreakingChangeType.FIELD_REMOVED,
                        field_path=f"type:{type_name}",
                        description=f"GraphQL type {type_name} was removed",
                        impact=ChangeImpact.MAJOR,
                    )
                )

            overall_impact = (
                ChangeImpact.MAJOR if breaking_changes else ChangeImpact.PATCH
            )

            return ContractChange(
                file_path=str(new_path),
                contract_type="graphql",
                breaking_changes=breaking_changes,
                overall_impact=overall_impact,
                migration_required=len(breaking_changes) > 0,
            )

        except Exception as e:
            logger.error(f"Failed to analyze GraphQL changes: {e}")
            return ContractChange(file_path=str(new_path), contract_type="graphql")

    def _analyze_protobuf_changes(
        self, old_path: Path, new_path: Path
    ) -> ContractChange:
        """Analyze changes in Protocol Buffer definitions"""
        # Placeholder for protobuf analysis
        return ContractChange(
            file_path=str(new_path),
            contract_type="protobuf",
            overall_impact=ChangeImpact.MINOR,
        )

    def _analyze_avro_changes(self, old_path: Path, new_path: Path) -> ContractChange:
        """Analyze changes in Avro schemas"""
        # Placeholder for Avro analysis
        return ContractChange(
            file_path=str(new_path),
            contract_type="avro",
            overall_impact=ChangeImpact.MINOR,
        )

    def _parse_contract(
        self, file_path: Path, contract_type: str
    ) -> Optional[APIContract]:
        """Parse a contract file and extract metadata"""
        try:
            if contract_type == "openapi":
                spec = self._load_yaml_or_json(file_path)
                return APIContract(
                    file_path=str(file_path),
                    contract_type=contract_type,
                    version=spec.get("info", {}).get("version"),
                    endpoints=list(spec.get("paths", {}).keys()),
                    schemas=list(spec.get("components", {}).get("schemas", {}).keys()),
                    metadata={"title": spec.get("info", {}).get("title")},
                )
            elif contract_type == "graphql":
                schema_text = file_path.read_text()
                types = self._extract_graphql_types(schema_text)
                return APIContract(
                    file_path=str(file_path),
                    contract_type=contract_type,
                    schemas=list(types.keys()),
                )
            # Add more contract types as needed

        except Exception as e:
            logger.warning(f"Failed to parse contract {file_path}: {e}")

        return None

    def _load_yaml_or_json(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML or JSON file"""
        content = file_path.read_text()

        if file_path.suffix.lower() in [".yaml", ".yml"]:
            return yaml.safe_load(content)
        else:
            return json.loads(content)

    def _extract_graphql_types(self, schema_text: str) -> Dict[str, str]:
        """Extract GraphQL types from schema text (simplified)"""
        types = {}

        # Simple regex to find type definitions
        type_matches = re.finditer(
            r"type\s+(\w+)\s*{([^}]*)}", schema_text, re.MULTILINE | re.DOTALL
        )

        for match in type_matches:
            type_name = match.group(1)
            type_body = match.group(2)
            types[type_name] = type_body.strip()

        return types


# Convenience function
def analyze_contract_changes(
    old_file: str, new_file: str, contract_type: Optional[str] = None
) -> ContractChange:
    """Convenience function to analyze contract changes"""
    analyzer = ContractAnalyzer()
    return analyzer.analyze_contract_changes(old_file, new_file, contract_type)
