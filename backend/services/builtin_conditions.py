"""
Built-in Conditions for NAVI

This module contains all the built-in condition implementations.
Each condition is a class extending BaseCondition.

To add a new condition:
1. Create a class extending BaseCondition
2. Set name, description, category, and parameters
3. Implement the check() method
4. Add it to get_builtin_conditions()
"""

import asyncio
import json
import os
import re
import socket
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import List

from backend.services.condition_registry import BaseCondition, ConditionResult

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# =============================================================================
# Network Conditions
# =============================================================================


class HTTPCondition(BaseCondition):
    name = "http"
    description = "Check HTTP endpoint responds"
    category = "network"
    parameters = {
        "url": {"type": "string", "required": True},
        "method": {"type": "string", "default": "GET"},
        "expected_status": {"type": "integer"},
        "timeout": {"type": "integer", "default": 10},
        "headers": {"type": "object"},
    }

    async def check(self, **kwargs) -> ConditionResult:
        url = kwargs.get("url")
        method = kwargs.get("method", "GET")
        expected_status = kwargs.get("expected_status")
        timeout = kwargs.get("timeout", 10)
        headers = kwargs.get("headers", {})

        try:
            req = urllib.request.Request(url, method=method)
            for key, value in headers.items():
                req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.status
                body_preview = response.read(500).decode("utf-8", errors="ignore")

                success = True
                if expected_status is not None:
                    success = status == expected_status
                elif status >= 400:
                    success = False

                return ConditionResult(
                    success=success,
                    condition_type=self.name,
                    details={
                        "url": url,
                        "status": status,
                        "responding": True,
                        "body_preview": body_preview[:200],
                    },
                )
        except urllib.error.HTTPError as e:
            return ConditionResult(
                success=expected_status == e.code if expected_status else False,
                condition_type=self.name,
                details={"url": url, "status": e.code, "responding": True},
                error=str(e),
            )
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"url": url, "responding": False},
                error=str(e),
            )


class PortCondition(BaseCondition):
    name = "port"
    description = "Check if port is listening"
    category = "network"
    parameters = {
        "port": {"type": "integer", "required": True},
        "host": {"type": "string", "default": "localhost"},
        "timeout": {"type": "integer", "default": 2},
    }

    async def check(self, **kwargs) -> ConditionResult:
        port = kwargs.get("port")
        host = kwargs.get("host", "localhost")
        timeout = kwargs.get("timeout", 2)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            sock.close()

            listening = result == 0
            return ConditionResult(
                success=listening,
                condition_type=self.name,
                details={"port": port, "host": host, "listening": listening},
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class TCPCondition(BaseCondition):
    name = "tcp"
    description = "Check TCP connection with optional send/expect"
    category = "network"
    parameters = {
        "host": {"type": "string", "required": True},
        "port": {"type": "integer", "required": True},
        "send": {"type": "string"},
        "expect": {"type": "string"},
        "timeout": {"type": "integer", "default": 5},
    }

    async def check(self, **kwargs) -> ConditionResult:
        host = kwargs.get("host")
        port = kwargs.get("port")
        timeout = kwargs.get("timeout", 5)
        send_data = kwargs.get("send")
        expect_pattern = kwargs.get("expect")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))

            response_data = None
            if send_data:
                sock.send(
                    send_data.encode() if isinstance(send_data, str) else send_data
                )
                response_data = sock.recv(1024).decode("utf-8", errors="replace")

            sock.close()

            success = True
            if expect_pattern and response_data:
                success = bool(re.search(expect_pattern, response_data))

            return ConditionResult(
                success=success,
                condition_type=self.name,
                details={
                    "host": host,
                    "port": port,
                    "connected": True,
                    "response": response_data,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class SSLCondition(BaseCondition):
    name = "ssl"
    description = "Check SSL/TLS certificate"
    category = "network"
    parameters = {
        "host": {"type": "string", "required": True},
        "port": {"type": "integer", "default": 443},
    }

    async def check(self, **kwargs) -> ConditionResult:
        host = kwargs.get("host")
        port = kwargs.get("port", 443)

        try:
            from datetime import datetime

            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()

                    not_after = cert.get("notAfter", "")
                    expiry = (
                        datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        if not_after
                        else None
                    )
                    days_until_expiry = (
                        (expiry - datetime.now()).days if expiry else None
                    )

                    return ConditionResult(
                        success=True,
                        condition_type=self.name,
                        details={
                            "host": host,
                            "port": port,
                            "valid": True,
                            "expires": not_after,
                            "days_until_expiry": days_until_expiry,
                            "expired": (
                                days_until_expiry < 0 if days_until_expiry else None
                            ),
                        },
                    )
        except ssl.SSLError as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=f"SSL error: {e}"
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class DNSCondition(BaseCondition):
    name = "dns"
    description = "Check DNS resolution"
    category = "network"
    parameters = {
        "hostname": {"type": "string", "required": True},
    }

    async def check(self, **kwargs) -> ConditionResult:
        hostname = kwargs.get("hostname")

        try:
            result = socket.gethostbyname(hostname)
            return ConditionResult(
                success=True,
                condition_type=self.name,
                details={"hostname": hostname, "resolved": True, "address": result},
            )
        except socket.gaierror as e:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"hostname": hostname},
                error=str(e),
            )


class WebSocketCondition(BaseCondition):
    name = "websocket"
    description = "Check WebSocket connection"
    category = "network"
    parameters = {
        "url": {"type": "string", "required": True},
        "timeout": {"type": "integer", "default": 5},
    }

    async def check(self, **kwargs) -> ConditionResult:
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 5)

        try:
            import websockets

            async def check_ws():
                async with websockets.connect(url, close_timeout=timeout):
                    return True

            await asyncio.wait_for(check_ws(), timeout=timeout)
            return ConditionResult(
                success=True,
                condition_type=self.name,
                details={"url": url, "connected": True},
            )
        except ImportError:
            # Fallback to HTTP upgrade check
            try:
                http_url = url.replace("ws://", "http://").replace("wss://", "https://")
                req = urllib.request.Request(http_url)
                req.add_header("Upgrade", "websocket")
                req.add_header("Connection", "Upgrade")

                try:
                    urllib.request.urlopen(req, timeout=timeout)
                except urllib.error.HTTPError as e:
                    if e.code in (101, 426):
                        return ConditionResult(
                            success=True,
                            condition_type=self.name,
                            details={"url": url, "connected": True},
                        )

                return ConditionResult(
                    success=False,
                    condition_type=self.name,
                    details={"url": url},
                    error="WebSocket not supported",
                )
            except Exception as e:
                return ConditionResult(
                    success=False, condition_type=self.name, error=str(e)
                )
        except Exception as e:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"url": url},
                error=str(e),
            )


# =============================================================================
# File System Conditions
# =============================================================================


class FileExistsCondition(BaseCondition):
    name = "file_exists"
    description = "Check if file or directory exists"
    category = "filesystem"
    parameters = {
        "path": {"type": "string", "required": True},
    }

    async def check(self, **kwargs) -> ConditionResult:
        path = kwargs.get("path")

        exists = os.path.exists(path)
        return ConditionResult(
            success=exists,
            condition_type=self.name,
            details={
                "path": path,
                "exists": exists,
                "is_file": os.path.isfile(path) if exists else None,
                "is_dir": os.path.isdir(path) if exists else None,
                "size_bytes": (
                    os.path.getsize(path) if exists and os.path.isfile(path) else None
                ),
            },
        )


class FileContainsCondition(BaseCondition):
    name = "file_contains"
    description = "Check if file contains pattern"
    category = "filesystem"
    parameters = {
        "path": {"type": "string", "required": True},
        "pattern": {"type": "string", "required": True},
    }

    async def check(self, **kwargs) -> ConditionResult:
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")

        try:
            with open(path, "r", errors="replace") as f:
                content = f.read()

            found = bool(re.search(pattern, content))
            matches = re.findall(pattern, content)[:5]

            return ConditionResult(
                success=found,
                condition_type=self.name,
                details={
                    "path": path,
                    "pattern": pattern,
                    "found": found,
                    "matches": matches,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


# =============================================================================
# Process Conditions
# =============================================================================


class ProcessRunningCondition(BaseCondition):
    name = "process_running"
    description = "Check if process is running"
    category = "system"
    parameters = {
        "name": {"type": "string", "required": True},
        "exact": {"type": "boolean", "default": False},
    }

    async def check(self, **kwargs) -> ConditionResult:
        name = kwargs.get("name")
        exact = kwargs.get("exact", False)

        if not HAS_PSUTIL:
            return ConditionResult(
                success=False, condition_type=self.name, error="psutil not installed"
            )

        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    proc_name = proc.info["name"]
                    cmdline = " ".join(proc.info["cmdline"] or [])

                    if exact:
                        match = name == proc_name
                    else:
                        match = (
                            name.lower() in proc_name.lower()
                            or name.lower() in cmdline.lower()
                        )

                    if match:
                        return ConditionResult(
                            success=True,
                            condition_type=self.name,
                            details={
                                "name": name,
                                "running": True,
                                "pid": proc.info["pid"],
                                "process_name": proc_name,
                            },
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"name": name, "running": False},
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class CommandSucceedsCondition(BaseCondition):
    name = "command_succeeds"
    description = "Check if command exits with 0"
    category = "system"
    parameters = {
        "command": {"type": "string", "required": True},
        "working_dir": {"type": "string", "default": "."},
        "timeout": {"type": "integer", "default": 30},
    }

    async def check(self, **kwargs) -> ConditionResult:
        command = kwargs.get("command")
        working_dir = kwargs.get("working_dir", ".")
        timeout = kwargs.get("timeout", 30)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                timeout=timeout,
            )

            return ConditionResult(
                success=result.returncode == 0,
                condition_type=self.name,
                details={
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout.decode("utf-8", errors="replace")[:1000],
                    "stderr": result.stderr.decode("utf-8", errors="replace")[:500],
                },
            )
        except subprocess.TimeoutExpired:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                error=f"Timeout after {timeout}s",
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


# =============================================================================
# Resource Conditions
# =============================================================================


class DiskSpaceCondition(BaseCondition):
    name = "disk_space"
    description = "Check disk space thresholds"
    category = "resources"
    parameters = {
        "path": {"type": "string", "default": "/"},
        "min_free_gb": {"type": "number", "default": 1.0},
        "max_used_percent": {"type": "number", "default": 90},
    }

    async def check(self, **kwargs) -> ConditionResult:
        path = kwargs.get("path", "/")
        min_free_gb = kwargs.get("min_free_gb", 1.0)
        max_used_percent = kwargs.get("max_used_percent", 90)

        if not HAS_PSUTIL:
            return ConditionResult(
                success=False, condition_type=self.name, error="psutil not installed"
            )

        try:
            usage = psutil.disk_usage(path)
            free_gb = usage.free / 1024 / 1024 / 1024
            used_percent = usage.percent

            success = free_gb >= min_free_gb and used_percent <= max_used_percent

            return ConditionResult(
                success=success,
                condition_type=self.name,
                details={
                    "path": path,
                    "total_gb": usage.total / 1024 / 1024 / 1024,
                    "free_gb": free_gb,
                    "used_percent": used_percent,
                    "threshold_met": success,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class MemoryCondition(BaseCondition):
    name = "memory_available"
    description = "Check available memory"
    category = "resources"
    parameters = {
        "min_available_gb": {"type": "number", "default": 0.5},
        "max_used_percent": {"type": "number", "default": 90},
    }

    async def check(self, **kwargs) -> ConditionResult:
        min_available_gb = kwargs.get("min_available_gb", 0.5)
        max_used_percent = kwargs.get("max_used_percent", 90)

        if not HAS_PSUTIL:
            return ConditionResult(
                success=False, condition_type=self.name, error="psutil not installed"
            )

        try:
            mem = psutil.virtual_memory()
            available_gb = mem.available / 1024 / 1024 / 1024
            used_percent = mem.percent

            success = (
                available_gb >= min_available_gb and used_percent <= max_used_percent
            )

            return ConditionResult(
                success=success,
                condition_type=self.name,
                details={
                    "total_gb": mem.total / 1024 / 1024 / 1024,
                    "available_gb": available_gb,
                    "used_percent": used_percent,
                    "threshold_met": success,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class CPUCondition(BaseCondition):
    name = "cpu_usage"
    description = "Check CPU usage"
    category = "resources"
    parameters = {
        "max_percent": {"type": "number", "default": 90},
    }

    async def check(self, **kwargs) -> ConditionResult:
        max_percent = kwargs.get("max_percent", 90)

        if not HAS_PSUTIL:
            return ConditionResult(
                success=False, condition_type=self.name, error="psutil not installed"
            )

        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            success = cpu_percent <= max_percent

            return ConditionResult(
                success=success,
                condition_type=self.name,
                details={
                    "cpu_percent": cpu_percent,
                    "max_percent": max_percent,
                    "threshold_met": success,
                    "cpu_count": psutil.cpu_count(),
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


# =============================================================================
# Environment Conditions
# =============================================================================


class EnvVarCondition(BaseCondition):
    name = "env_var"
    description = "Check environment variable"
    category = "environment"
    parameters = {
        "name": {"type": "string", "required": True},
        "value": {"type": "string"},
        "pattern": {"type": "string"},
    }

    async def check(self, **kwargs) -> ConditionResult:
        name = kwargs.get("name")
        expected_value = kwargs.get("value")
        pattern = kwargs.get("pattern")

        value = os.environ.get(name)

        if value is None:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"name": name, "exists": False},
            )

        success = True
        if expected_value is not None:
            success = value == expected_value
        elif pattern is not None:
            success = bool(re.search(pattern, value))

        # Mask sensitive values
        display_value = (
            "***"
            if any(
                s in name.lower() for s in ["password", "secret", "token", "key", "api"]
            )
            else value
        )

        return ConditionResult(
            success=success,
            condition_type=self.name,
            details={
                "name": name,
                "exists": True,
                "value": display_value,
                "matches": success,
            },
        )


# =============================================================================
# Database Conditions
# =============================================================================


class DatabaseCondition(BaseCondition):
    name = "database"
    description = "Check database connectivity"
    category = "database"
    parameters = {
        "db_type": {"type": "string", "required": True},
        "host": {"type": "string", "default": "localhost"},
        "port": {"type": "integer"},
        "database": {"type": "string"},
        "user": {"type": "string"},
        "password": {"type": "string"},
    }

    async def check(self, **kwargs) -> ConditionResult:
        db_type = kwargs.get("db_type", "postgres")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port")
        database = kwargs.get("database")

        # Default ports
        default_ports = {
            "postgres": 5432,
            "postgresql": 5432,
            "mysql": 3306,
            "mariadb": 3306,
            "mongodb": 27017,
            "mongo": 27017,
            "redis": 6379,
        }
        port = port or default_ports.get(db_type, 5432)

        # First check port
        port_result = await PortCondition().check(host=host, port=port)
        if not port_result.success:
            return ConditionResult(
                success=False,
                condition_type=self.name,
                details={"db_type": db_type, "host": host, "port": port},
                error=f"Port {port} not listening",
            )

        # Try specific database check
        try:
            if db_type in ("postgres", "postgresql"):
                result = subprocess.run(
                    f"pg_isready -h {host} -p {port}"
                    + (f" -d {database}" if database else ""),
                    shell=True,
                    capture_output=True,
                    timeout=5,
                )
                connected = result.returncode == 0

            elif db_type in ("mysql", "mariadb"):
                result = subprocess.run(
                    f"mysqladmin ping -h {host} -P {port} --silent",
                    shell=True,
                    capture_output=True,
                    timeout=5,
                )
                connected = result.returncode == 0

            elif db_type in ("mongodb", "mongo"):
                result = subprocess.run(
                    f"mongosh --host {host} --port {port} --eval 'db.runCommand({{ping: 1}})' --quiet",
                    shell=True,
                    capture_output=True,
                    timeout=5,
                )
                connected = result.returncode == 0

            elif db_type == "redis":
                result = subprocess.run(
                    f"redis-cli -h {host} -p {port} ping",
                    shell=True,
                    capture_output=True,
                    timeout=5,
                )
                connected = "PONG" in result.stdout.decode()

            else:
                # Fallback to port check
                connected = True

            return ConditionResult(
                success=connected,
                condition_type=self.name,
                details={
                    "db_type": db_type,
                    "host": host,
                    "port": port,
                    "connected": connected,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


# =============================================================================
# Container Conditions
# =============================================================================


class DockerCondition(BaseCondition):
    name = "docker"
    description = "Check Docker container status"
    category = "container"
    parameters = {
        "container": {"type": "string", "required": True},
        "check_health": {"type": "boolean", "default": True},
    }

    async def check(self, **kwargs) -> ConditionResult:
        container = kwargs.get("container")
        check_health = kwargs.get("check_health", True)

        try:
            result = subprocess.run(
                f"docker inspect --format='{{{{.State.Status}}}}' {container}",
                shell=True,
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                return ConditionResult(
                    success=False,
                    condition_type=self.name,
                    details={"container": container},
                    error="Container not found",
                )

            status = result.stdout.decode().strip().strip("'")

            if status != "running":
                return ConditionResult(
                    success=False,
                    condition_type=self.name,
                    details={
                        "container": container,
                        "status": status,
                        "running": False,
                    },
                )

            health_status = None
            if check_health:
                health_result = subprocess.run(
                    f"docker inspect --format='{{{{.State.Health.Status}}}}' {container}",
                    shell=True,
                    capture_output=True,
                    timeout=10,
                )
                if health_result.returncode == 0:
                    health_status = health_result.stdout.decode().strip().strip("'")

            return ConditionResult(
                success=True,
                condition_type=self.name,
                details={
                    "container": container,
                    "status": status,
                    "running": True,
                    "health_status": health_status,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class DockerComposeCondition(BaseCondition):
    name = "docker_compose"
    description = "Check docker-compose services"
    category = "container"
    parameters = {
        "service": {"type": "string"},
        "compose_file": {"type": "string", "default": "docker-compose.yml"},
        "working_dir": {"type": "string", "default": "."},
    }

    async def check(self, **kwargs) -> ConditionResult:
        service = kwargs.get("service")
        compose_file = kwargs.get("compose_file", "docker-compose.yml")
        working_dir = kwargs.get("working_dir", ".")

        try:
            result = subprocess.run(
                f"docker-compose -f {compose_file} ps --format json",
                shell=True,
                capture_output=True,
                timeout=10,
                cwd=working_dir,
            )

            if result.returncode != 0:
                return ConditionResult(
                    success=False,
                    condition_type=self.name,
                    error=result.stderr.decode(),
                )

            output = result.stdout.decode()
            running_services = []

            for line in output.strip().split("\n"):
                if line:
                    try:
                        svc = json.loads(line)
                        running_services.append(svc.get("Service") or svc.get("Name"))
                    except json.JSONDecodeError:
                        pass

            if service:
                found = service in running_services
                return ConditionResult(
                    success=found,
                    condition_type=self.name,
                    details={
                        "service": service,
                        "running": found,
                        "all_services": running_services,
                    },
                )
            else:
                return ConditionResult(
                    success=len(running_services) > 0,
                    condition_type=self.name,
                    details={
                        "services": running_services,
                        "count": len(running_services),
                    },
                )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


class KubernetesCondition(BaseCondition):
    name = "kubernetes"
    description = "Check Kubernetes resource status"
    category = "container"
    parameters = {
        "resource_type": {"type": "string", "default": "pod"},
        "name": {"type": "string", "required": True},
        "namespace": {"type": "string", "default": "default"},
        "context": {"type": "string"},
    }

    async def check(self, **kwargs) -> ConditionResult:
        resource_type = kwargs.get("resource_type", "pod")
        name = kwargs.get("name")
        namespace = kwargs.get("namespace", "default")
        context = kwargs.get("context")

        try:
            ctx_arg = f"--context={context}" if context else ""

            if resource_type == "pod":
                cmd = f"kubectl {ctx_arg} get pod {name} -n {namespace} -o jsonpath='{{.status.phase}}'"
            elif resource_type == "deployment":
                cmd = f"kubectl {ctx_arg} get deployment {name} -n {namespace} -o jsonpath='{{.status.readyReplicas}}/{{.status.replicas}}'"
            elif resource_type == "service":
                cmd = f"kubectl {ctx_arg} get service {name} -n {namespace} -o jsonpath='{{.spec.clusterIP}}'"
            else:
                cmd = f"kubectl {ctx_arg} get {resource_type} {name} -n {namespace}"

            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode != 0:
                return ConditionResult(
                    success=False,
                    condition_type=self.name,
                    details={"resource_type": resource_type, "name": name},
                    error=result.stderr.decode(),
                )

            output = result.stdout.decode().strip().strip("'")

            if resource_type == "pod":
                success = output == "Running"
            elif resource_type == "deployment":
                parts = output.split("/")
                success = len(parts) == 2 and parts[0] == parts[1] and int(parts[0]) > 0
            else:
                success = bool(output)

            return ConditionResult(
                success=success,
                condition_type=self.name,
                details={
                    "resource_type": resource_type,
                    "name": name,
                    "namespace": namespace,
                    "status": output,
                },
            )
        except Exception as e:
            return ConditionResult(
                success=False, condition_type=self.name, error=str(e)
            )


# =============================================================================
# Health Aggregate Condition
# =============================================================================


class HealthAggregateCondition(BaseCondition):
    name = "health_aggregate"
    description = "Combine multiple health checks"
    category = "aggregate"
    parameters = {
        "checks": {"type": "array", "required": True},
        "require_all": {"type": "boolean", "default": True},
    }

    async def check(self, **kwargs) -> ConditionResult:
        from backend.services.condition_registry import get_registry

        checks = kwargs.get("checks", [])
        require_all = kwargs.get("require_all", True)

        registry = get_registry()
        results = []

        for check_config in checks:
            check_config_copy = check_config.copy()
            check_type = check_config_copy.pop("type", "http")
            result = await registry.check(check_type, **check_config_copy)
            results.append({"check": check_type, **result.to_dict()})

        if require_all:
            success = all(r.get("success") for r in results)
        else:
            success = any(r.get("success") for r in results)

        return ConditionResult(
            success=success,
            condition_type=self.name,
            details={
                "checks": results,
                "passed": sum(1 for r in results if r.get("success")),
                "total": len(results),
            },
        )


# =============================================================================
# Factory Function
# =============================================================================


def get_builtin_conditions() -> List[BaseCondition]:
    """Return all built-in condition instances."""
    return [
        # Network
        HTTPCondition(),
        PortCondition(),
        TCPCondition(),
        SSLCondition(),
        DNSCondition(),
        WebSocketCondition(),
        # Filesystem
        FileExistsCondition(),
        FileContainsCondition(),
        # Process
        ProcessRunningCondition(),
        CommandSucceedsCondition(),
        # Resources
        DiskSpaceCondition(),
        MemoryCondition(),
        CPUCondition(),
        # Environment
        EnvVarCondition(),
        # Database
        DatabaseCondition(),
        # Container
        DockerCondition(),
        DockerComposeCondition(),
        KubernetesCondition(),
        # Aggregate
        HealthAggregateCondition(),
    ]
