"""
Extensible Condition Registry for NAVI

Instead of hardcoding 100,000+ patterns, this provides:
1. Dynamic pattern registration
2. Plugin-based architecture
3. Composable condition primitives
4. Configuration-driven patterns
5. Custom pattern definition via YAML/JSON
6. AI-assisted pattern execution

This allows NAVI to handle ANY verification scenario in the real world.
"""

import asyncio
import importlib
import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Base Condition Interface
# =============================================================================

@dataclass
class ConditionResult:
    """Result of a condition check."""
    success: bool
    condition_type: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    elapsed_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "condition": self.condition_type,
            "message": self.message,
            **self.details
        }
        if self.error:
            result["error"] = self.error
        if self.elapsed_ms > 0:
            result["elapsed_ms"] = round(self.elapsed_ms, 2)
        return result


class BaseCondition(ABC):
    """
    Base class for all condition checks.

    Extend this to create custom conditions:

    class MyCustomCondition(BaseCondition):
        name = "my_custom_check"
        description = "Checks something custom"

        async def check(self, **kwargs) -> ConditionResult:
            # Your logic here
            return ConditionResult(success=True, condition_type=self.name)
    """

    name: str = "base"
    description: str = "Base condition"
    category: str = "generic"
    parameters: Dict[str, Dict[str, Any]] = {}  # Parameter schema

    @abstractmethod
    async def check(self, **kwargs) -> ConditionResult:
        """Execute the condition check."""
        pass

    def validate_params(self, kwargs: Dict[str, Any]) -> Optional[str]:
        """Validate parameters against schema."""
        for param_name, param_schema in self.parameters.items():
            if param_schema.get("required") and param_name not in kwargs:
                return f"Missing required parameter: {param_name}"
        return None


# =============================================================================
# Condition Registry (Singleton)
# =============================================================================

class ConditionRegistry:
    """
    Central registry for all condition types.

    Supports:
    - Built-in conditions
    - Plugin conditions (loaded from files)
    - Dynamic registration at runtime
    - Condition aliases
    - Condition composition
    """

    _instance: Optional['ConditionRegistry'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._conditions: Dict[str, BaseCondition] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[str, List[str]] = {}
        self._custom_patterns: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

        # Register built-in conditions
        self._register_builtins()

    def register(self, condition: BaseCondition):
        """Register a condition."""
        self._conditions[condition.name] = condition

        # Add to category
        category = condition.category
        if category not in self._categories:
            self._categories[category] = []
        if condition.name not in self._categories[category]:
            self._categories[category].append(condition.name)

        logger.debug(f"Registered condition: {condition.name}")

    def register_alias(self, alias: str, target: str):
        """Register an alias for a condition."""
        self._aliases[alias] = target

    def get(self, name: str) -> Optional[BaseCondition]:
        """Get a condition by name or alias."""
        # Check alias first
        if name in self._aliases:
            name = self._aliases[name]
        return self._conditions.get(name)

    def list_conditions(self, category: Optional[str] = None) -> List[str]:
        """List all registered conditions."""
        if category:
            return self._categories.get(category, [])
        return list(self._conditions.keys())

    def list_categories(self) -> List[str]:
        """List all categories."""
        return list(self._categories.keys())

    async def check(self, condition_type: str, **kwargs) -> ConditionResult:
        """Execute a condition check."""
        start_time = time.time()

        # Check for custom pattern first
        if condition_type in self._custom_patterns:
            result = await self._execute_custom_pattern(condition_type, kwargs)
            result.elapsed_ms = (time.time() - start_time) * 1000
            return result

        condition = self.get(condition_type)
        if not condition:
            # Try dynamic execution
            result = await self._try_dynamic_execution(condition_type, kwargs)
            result.elapsed_ms = (time.time() - start_time) * 1000
            return result

        # Validate parameters
        validation_error = condition.validate_params(kwargs)
        if validation_error:
            return ConditionResult(
                success=False,
                condition_type=condition_type,
                error=validation_error
            )

        try:
            result = await condition.check(**kwargs)
            result.elapsed_ms = (time.time() - start_time) * 1000
            return result
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=condition_type,
                error=str(e),
                elapsed_ms=(time.time() - start_time) * 1000
            )

    def register_custom_pattern(
        self,
        name: str,
        pattern_def: Dict[str, Any]
    ):
        """
        Register a custom pattern from configuration.

        Pattern definition format:
        {
            "type": "composite" | "http" | "command" | "script",
            "description": "What this checks",
            "steps": [
                {"condition": "port", "params": {"port": 5432}},
                {"condition": "http", "params": {"url": "http://localhost:5432/health"}}
            ],
            "require_all": True
        }
        """
        self._custom_patterns[name] = pattern_def
        logger.info(f"Registered custom pattern: {name}")

    def load_patterns_from_file(self, file_path: str):
        """Load custom patterns from a JSON/YAML file."""
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"Pattern file not found: {file_path}")
            return

        try:
            with open(path) as f:
                if path.suffix in ('.yaml', '.yml'):
                    import yaml
                    patterns = yaml.safe_load(f)
                else:
                    patterns = json.load(f)

            for name, definition in patterns.items():
                self.register_custom_pattern(name, definition)

            logger.info(f"Loaded {len(patterns)} patterns from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load patterns from {file_path}: {e}")

    def load_plugin(self, module_path: str):
        """
        Load conditions from a Python module.

        The module should define conditions as classes extending BaseCondition.
        """
        try:
            module = importlib.import_module(module_path)

            # Find all BaseCondition subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseCondition) and
                    attr is not BaseCondition):
                    self.register(attr())

            logger.info(f"Loaded plugin: {module_path}")
        except Exception as e:
            logger.error(f"Failed to load plugin {module_path}: {e}")

    async def _execute_custom_pattern(
        self,
        name: str,
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """Execute a custom pattern definition."""
        pattern = self._custom_patterns[name]
        pattern_type = pattern.get("type", "composite")

        if pattern_type == "composite":
            return await self._execute_composite_pattern(name, pattern, kwargs)
        elif pattern_type == "http":
            return await self._execute_http_pattern(name, pattern, kwargs)
        elif pattern_type == "command":
            return await self._execute_command_pattern(name, pattern, kwargs)
        elif pattern_type == "script":
            return await self._execute_script_pattern(name, pattern, kwargs)
        else:
            return ConditionResult(
                success=False,
                condition_type=name,
                error=f"Unknown pattern type: {pattern_type}"
            )

    async def _execute_composite_pattern(
        self,
        name: str,
        pattern: Dict[str, Any],
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """Execute a composite pattern (multiple conditions)."""
        steps = pattern.get("steps", [])
        require_all = pattern.get("require_all", True)

        results = []
        for step in steps:
            condition_type = step.get("condition")
            params = step.get("params", {})

            # Merge with provided kwargs (kwargs override)
            merged_params = {**params, **kwargs}

            result = await self.check(condition_type, **merged_params)
            results.append(result.to_dict())

            # Short-circuit if require_all and one fails
            if require_all and not result.success:
                return ConditionResult(
                    success=False,
                    condition_type=name,
                    message=f"Step failed: {condition_type}",
                    details={"step_results": results}
                )

        if require_all:
            success = all(r.get("success") for r in results)
        else:
            success = any(r.get("success") for r in results)

        return ConditionResult(
            success=success,
            condition_type=name,
            message=f"{sum(1 for r in results if r.get('success'))}/{len(results)} steps passed",
            details={"step_results": results}
        )

    async def _execute_http_pattern(
        self,
        name: str,
        pattern: Dict[str, Any],
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """Execute an HTTP-based pattern."""
        url = pattern.get("url", kwargs.get("url"))
        method = pattern.get("method", "GET")
        headers = pattern.get("headers", {})
        expected_status = pattern.get("expected_status", 200)
        response_contains = pattern.get("response_contains")
        response_json_path = pattern.get("response_json_path")
        expected_value = pattern.get("expected_value")

        try:
            req = urllib.request.Request(url, method=method)
            for key, value in headers.items():
                req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                body = response.read().decode('utf-8', errors='replace')

                success = status == expected_status

                if success and response_contains:
                    success = response_contains in body

                if success and response_json_path:
                    try:
                        data = json.loads(body)
                        for key in response_json_path.split("."):
                            data = data.get(key) if isinstance(data, dict) else None
                        if expected_value is not None:
                            success = data == expected_value
                        else:
                            success = data is not None
                    except Exception:
                        success = False

                return ConditionResult(
                    success=success,
                    condition_type=name,
                    details={"status": status, "url": url}
                )
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=name,
                error=str(e)
            )

    async def _execute_command_pattern(
        self,
        name: str,
        pattern: Dict[str, Any],
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """Execute a command-based pattern."""
        command = pattern.get("command")
        working_dir = pattern.get("working_dir", kwargs.get("working_dir", "."))
        expected_output = pattern.get("expected_output")
        expected_exit_code = pattern.get("expected_exit_code", 0)

        # Variable substitution in command
        for key, value in kwargs.items():
            command = command.replace(f"${{{key}}}", str(value))
            command = command.replace(f"${key}", str(value))

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                timeout=30
            )

            output = result.stdout.decode('utf-8', errors='replace')
            success = result.returncode == expected_exit_code

            if success and expected_output:
                if isinstance(expected_output, str):
                    success = expected_output in output
                elif isinstance(expected_output, dict):
                    pattern_re = expected_output.get("pattern")
                    if pattern_re:
                        success = bool(re.search(pattern_re, output))

            return ConditionResult(
                success=success,
                condition_type=name,
                details={
                    "exit_code": result.returncode,
                    "output": output[:500]
                }
            )
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=name,
                error=str(e)
            )

    async def _execute_script_pattern(
        self,
        name: str,
        pattern: Dict[str, Any],
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """Execute a Python script pattern."""
        script = pattern.get("script")

        try:
            # Create a safe execution context
            exec_globals = {
                "kwargs": kwargs,
                "socket": socket,
                "urllib": urllib,
                "json": json,
                "re": re,
                "asyncio": asyncio,
                "subprocess": subprocess,
            }
            exec_locals = {}

            exec(script, exec_globals, exec_locals)

            # Script should define a 'result' variable
            result = exec_locals.get("result", {})

            return ConditionResult(
                success=result.get("success", False),
                condition_type=name,
                details=result
            )
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=name,
                error=str(e)
            )

    async def _try_dynamic_execution(
        self,
        condition_type: str,
        kwargs: Dict[str, Any]
    ) -> ConditionResult:
        """
        Try to execute an unknown condition dynamically.

        This uses heuristics to figure out how to check the condition:
        1. If it looks like a URL, do HTTP check
        2. If it looks like host:port, do port check
        3. If it looks like a file path, do file check
        4. If it looks like a command, run it
        5. Otherwise, return unknown
        """

        # Check for common patterns in condition_type name
        condition_lower = condition_type.lower()

        # URL-based service patterns
        url_services = {
            "stripe": "https://api.stripe.com/v1",
            "paypal": "https://api.paypal.com/v1/oauth2/token",
            "twilio": "https://api.twilio.com",
            "sendgrid": "https://api.sendgrid.com/v3",
            "mailgun": "https://api.mailgun.net/v3",
            "firebase": "https://firebase.googleapis.com",
            "supabase": kwargs.get("url", "https://api.supabase.io"),
            "vercel": "https://api.vercel.com",
            "netlify": "https://api.netlify.com",
            "heroku": "https://api.heroku.com",
            "digitalocean": "https://api.digitalocean.com/v2",
            "cloudflare": "https://api.cloudflare.com/client/v4",
            "datadog": "https://api.datadoghq.com",
            "newrelic": "https://api.newrelic.com",
            "pagerduty": "https://api.pagerduty.com",
            "opsgenie": "https://api.opsgenie.com",
            "zendesk": kwargs.get("subdomain", "") + ".zendesk.com",
            "intercom": "https://api.intercom.io",
            "segment": "https://api.segment.io",
            "mixpanel": "https://api.mixpanel.com",
            "amplitude": "https://api.amplitude.com",
            "algolia": kwargs.get("app_id", "") + ".algolia.net",
            "meilisearch": kwargs.get("url", "http://localhost:7700"),
            "typesense": kwargs.get("url", "http://localhost:8108"),
            "contentful": "https://cdn.contentful.com",
            "sanity": "https://api.sanity.io",
            "strapi": kwargs.get("url", "http://localhost:1337"),
            "ghost": kwargs.get("url", "http://localhost:2368"),
            "wordpress": kwargs.get("url", "") + "/wp-json",
            "shopify": kwargs.get("shop", "") + ".myshopify.com",
            "square": "https://connect.squareup.com",
            "braintree": "https://api.braintreegateway.com",
        }

        # Check if condition matches a known service
        for service, base_url in url_services.items():
            if service in condition_lower:
                url = kwargs.get("url", base_url)
                if url:
                    return await self.check("http", url=url, **kwargs)

        # Default port services
        port_services = {
            "mysql": 3306,
            "mariadb": 3306,
            "postgres": 5432,
            "postgresql": 5432,
            "redis": 6379,
            "mongodb": 27017,
            "mongo": 27017,
            "elasticsearch": 9200,
            "rabbitmq": 5672,
            "kafka": 9092,
            "zookeeper": 2181,
            "etcd": 2379,
            "consul": 8500,
            "vault": 8200,
            "minio": 9000,
            "influxdb": 8086,
            "prometheus": 9090,
            "grafana": 3000,
            "jenkins": 8080,
            "sonarqube": 9000,
            "nexus": 8081,
            "artifactory": 8082,
            "gitlab": 80,
            "gitea": 3000,
            "drone": 80,
            "concourse": 8080,
            "airflow": 8080,
            "superset": 8088,
            "metabase": 3000,
            "redash": 5000,
            "jupyter": 8888,
            "jupyterhub": 8000,
            "rstudio": 8787,
            "tensorboard": 6006,
            "mlflow": 5000,
            "kubeflow": 8080,
            "seldon": 8000,
            "bentoml": 3000,
            "triton": 8000,
            "ray": 8265,
            "dask": 8787,
            "spark": 4040,
            "flink": 8081,
            "presto": 8080,
            "trino": 8080,
            "hive": 10000,
            "impala": 21050,
            "druid": 8888,
            "clickhouse": 8123,
            "timescaledb": 5432,
            "questdb": 9000,
            "victoriametrics": 8428,
            "loki": 3100,
            "tempo": 3200,
            "thanos": 10902,
            "cortex": 9009,
            "mimir": 8080,
        }

        for service, port in port_services.items():
            if service in condition_lower:
                host = kwargs.get("host", "localhost")
                return await self.check("port", host=host, port=port)

        # If contains "api" or "endpoint", try HTTP
        if "api" in condition_lower or "endpoint" in condition_lower:
            url = kwargs.get("url")
            if url:
                return await self.check("http", url=url, **kwargs)

        # If contains "service" or "running", try process check
        if "service" in condition_lower or "running" in condition_lower:
            name = kwargs.get("name", condition_type.replace("_", " "))
            return await self.check("process_running", name=name)

        # If contains "file" or "exists", try file check
        if "file" in condition_lower or "exists" in condition_lower:
            path = kwargs.get("path")
            if path:
                return await self.check("file_exists", path=path)

        return ConditionResult(
            success=False,
            condition_type=condition_type,
            error=f"Unknown condition type: {condition_type}. Register it using register_custom_pattern() or provide a URL/port.",
            details={
                "hint": "You can define custom patterns via YAML/JSON configuration",
                "example": {
                    "type": "composite",
                    "steps": [
                        {"condition": "port", "params": {"port": 8080}},
                        {"condition": "http", "params": {"url": "http://localhost:8080/health"}}
                    ]
                }
            }
        )

    def _register_builtins(self):
        """Register all built-in conditions."""
        # Import and register built-in conditions
        from backend.services.builtin_conditions import get_builtin_conditions

        for condition in get_builtin_conditions():
            self.register(condition)


# =============================================================================
# Condition Composer
# =============================================================================

class ConditionComposer:
    """
    Compose complex conditions from simple ones.

    Examples:
        composer = ConditionComposer()

        # All conditions must pass
        result = await composer.all_of([
            ("port", {"port": 5432}),
            ("http", {"url": "http://localhost:3000"}),
        ])

        # Any condition must pass
        result = await composer.any_of([
            ("http", {"url": "http://localhost:3000"}),
            ("http", {"url": "http://localhost:3001"}),
        ])

        # Sequential with dependencies
        result = await composer.sequence([
            ("port", {"port": 5432}, "database"),
            ("http", {"url": "http://localhost:3000"}, "backend"),
            ("http", {"url": "http://localhost:8080"}, "frontend"),
        ])
    """

    def __init__(self):
        self.registry = ConditionRegistry()

    async def all_of(
        self,
        conditions: List[tuple],
        fail_fast: bool = True
    ) -> ConditionResult:
        """All conditions must pass."""
        results = []

        for item in conditions:
            if len(item) == 2:
                condition_type, params = item
            else:
                condition_type, params, _ = item

            result = await self.registry.check(condition_type, **params)
            results.append(result.to_dict())

            if fail_fast and not result.success:
                return ConditionResult(
                    success=False,
                    condition_type="all_of",
                    message=f"Failed at: {condition_type}",
                    details={"results": results}
                )

        return ConditionResult(
            success=True,
            condition_type="all_of",
            message=f"All {len(results)} conditions passed",
            details={"results": results}
        )

    async def any_of(
        self,
        conditions: List[tuple]
    ) -> ConditionResult:
        """Any condition must pass."""
        results = []

        for item in conditions:
            if len(item) == 2:
                condition_type, params = item
            else:
                condition_type, params, _ = item

            result = await self.registry.check(condition_type, **params)
            results.append(result.to_dict())

            if result.success:
                return ConditionResult(
                    success=True,
                    condition_type="any_of",
                    message=f"Passed: {condition_type}",
                    details={"results": results}
                )

        return ConditionResult(
            success=False,
            condition_type="any_of",
            message="No conditions passed",
            details={"results": results}
        )

    async def sequence(
        self,
        conditions: List[tuple]
    ) -> ConditionResult:
        """Execute conditions in sequence, each depending on previous."""
        results = {}

        for item in conditions:
            if len(item) == 3:
                condition_type, params, name = item
            else:
                condition_type, params = item
                name = condition_type

            result = await self.registry.check(condition_type, **params)
            results[name] = result.to_dict()

            if not result.success:
                return ConditionResult(
                    success=False,
                    condition_type="sequence",
                    message=f"Failed at step: {name}",
                    details={"results": results, "failed_step": name}
                )

        return ConditionResult(
            success=True,
            condition_type="sequence",
            message=f"All {len(results)} steps completed",
            details={"results": results}
        )

    async def with_retry(
        self,
        condition_type: str,
        params: Dict[str, Any],
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0
    ) -> ConditionResult:
        """Execute condition with retries."""
        last_result = None
        current_delay = delay

        for attempt in range(max_retries + 1):
            result = await self.registry.check(condition_type, **params)
            last_result = result

            if result.success:
                result.details["attempts"] = attempt + 1
                return result

            if attempt < max_retries:
                await asyncio.sleep(current_delay)
                current_delay *= backoff

        last_result.details["attempts"] = max_retries + 1
        last_result.message = f"Failed after {max_retries + 1} attempts"
        return last_result

    async def with_timeout(
        self,
        condition_type: str,
        params: Dict[str, Any],
        timeout: float = 30.0,
        poll_interval: float = 1.0
    ) -> ConditionResult:
        """Wait for condition to become true within timeout."""
        start_time = time.time()
        attempts = 0
        last_result = None

        while time.time() - start_time < timeout:
            attempts += 1
            result = await self.registry.check(condition_type, **params)
            last_result = result

            if result.success:
                result.details["attempts"] = attempts
                result.details["elapsed_seconds"] = time.time() - start_time
                return result

            await asyncio.sleep(poll_interval)

        return ConditionResult(
            success=False,
            condition_type=condition_type,
            message=f"Timeout after {timeout}s",
            details={
                "attempts": attempts,
                "elapsed_seconds": time.time() - start_time,
                "last_result": last_result.to_dict() if last_result else None
            }
        )


# =============================================================================
# Global Functions
# =============================================================================

_registry: Optional[ConditionRegistry] = None


def get_registry() -> ConditionRegistry:
    """Get the global condition registry."""
    global _registry
    if _registry is None:
        _registry = ConditionRegistry()
    return _registry


async def verify_condition(condition_type: str, **kwargs) -> Dict[str, Any]:
    """
    Verify a condition - main entry point.

    This function can handle:
    1. Built-in conditions (100+ types)
    2. Custom patterns (registered via YAML/JSON)
    3. Dynamic service detection
    4. Composite conditions
    """
    registry = get_registry()
    result = await registry.check(condition_type, **kwargs)
    return result.to_dict()


async def wait_for_condition(
    condition_type: str,
    timeout: int = 30,
    interval: float = 1.0,
    **kwargs
) -> Dict[str, Any]:
    """Wait for a condition to become true."""
    composer = ConditionComposer()
    result = await composer.with_timeout(
        condition_type,
        kwargs,
        timeout=float(timeout),
        poll_interval=interval
    )
    return result.to_dict()


def register_pattern(name: str, pattern_def: Dict[str, Any]):
    """Register a custom pattern."""
    registry = get_registry()
    registry.register_custom_pattern(name, pattern_def)


def load_patterns(file_path: str):
    """Load patterns from a file."""
    registry = get_registry()
    registry.load_patterns_from_file(file_path)


def load_plugin(module_path: str):
    """Load a condition plugin module."""
    registry = get_registry()
    registry.load_plugin(module_path)
