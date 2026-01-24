"""
Comprehensive Process & Environment Manager for NAVI

This module provides COMPLETE capabilities for handling ANY software engineering scenario:

## Core Process Management
1. run_background - Start any long-running process
2. run_interactive - Handle commands that need stdin input
3. run_parallel - Run multiple commands simultaneously
4. check_process - Check process status and output
5. kill_process - Stop processes gracefully or forcefully
6. cleanup_session - Clean up all managed processes

## Condition Verification (Generic)
7. verify_condition - Single check for any condition
8. wait_for_condition - Poll until condition is true (with backoff)
9. wait_for_log_pattern - Wait for specific output in process logs

## Service Orchestration
10. start_service_chain - Start dependent services in order

## Resource Monitoring
11. check_resources - Monitor CPU, memory, disk usage

## Database Connectivity
12. verify_database - Test actual database connections

## Network Verification
13. verify_websocket - Test WebSocket connections
14. verify_ssl - Check SSL/TLS certificates

## Environment Management
15. create_environment - Set up Node/Python/etc environments
16. run_with_environment - Run commands with specific env

## Security
17. Secrets masking in all output

## Additional Patterns
18. OAuth flow handling
19. Retry with exponential backoff
20. Health check aggregation
"""

import asyncio
import json
import logging
import os
import psutil  # For resource monitoring
import re
import signal
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Secret Masking
# =============================================================================


class SecretMasker:
    """Masks sensitive values in output."""

    # Common patterns that indicate secrets
    SECRET_PATTERNS = [
        r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+",
        r"(?i)(api[_-]?key|apikey)\s*[=:]\s*\S+",
        r"(?i)(secret|token|auth)\s*[=:]\s*\S+",
        r"(?i)(access[_-]?key|private[_-]?key)\s*[=:]\s*\S+",
        r"(?i)bearer\s+\S+",
        r"(?i)basic\s+[A-Za-z0-9+/=]+",
        r"ghp_[A-Za-z0-9]{36}",  # GitHub PAT
        r"sk-[A-Za-z0-9]{48}",  # OpenAI key
        r"sk-ant-[A-Za-z0-9-]+",  # Anthropic key
    ]

    def __init__(self):
        self.explicit_secrets: Set[str] = set()
        self._compiled_patterns = [re.compile(p) for p in self.SECRET_PATTERNS]

    def add_secret(self, secret: str):
        """Add a value that should always be masked."""
        if secret and len(secret) > 3:
            self.explicit_secrets.add(secret)

    def mask(self, text: str) -> str:
        """Mask all secrets in text."""
        result = text

        # Mask explicit secrets
        for secret in self.explicit_secrets:
            if secret in result:
                result = result.replace(secret, "***MASKED***")

        # Mask pattern-based secrets
        for pattern in self._compiled_patterns:
            result = pattern.sub(lambda m: m.group(0)[:10] + "***MASKED***", result)

        return result


# Global secret masker
_secret_masker = SecretMasker()


def mask_secrets(text: str) -> str:
    """Mask secrets in text."""
    return _secret_masker.mask(text)


def register_secret(secret: str):
    """Register a secret value to be masked in all output."""
    _secret_masker.add_secret(secret)


# =============================================================================
# Process Management
# =============================================================================


@dataclass
class ManagedProcess:
    """A background process managed by the ProcessManager."""

    process_id: str
    command: str
    pid: int
    start_time: datetime
    working_dir: str
    output_buffer: deque = field(default_factory=lambda: deque(maxlen=2000))
    is_running: bool = True
    exit_code: Optional[int] = None
    process: Optional[asyncio.subprocess.Process] = None
    env: Optional[Dict[str, str]] = None
    tags: Set[str] = field(default_factory=set)  # For grouping/cleanup

    def add_output(self, line: str):
        """Add a line of output to the buffer (with masking)."""
        masked_line = mask_secrets(line)
        self.output_buffer.append(
            {"time": datetime.now().isoformat(), "text": masked_line}
        )

    def get_recent_output(self, lines: int = 50) -> str:
        """Get the most recent output lines."""
        recent = list(self.output_buffer)[-lines:]
        return "\n".join(item["text"] for item in recent)

    def get_all_output(self) -> str:
        """Get all buffered output."""
        return "\n".join(item["text"] for item in self.output_buffer)

    def search_output(self, pattern: str) -> List[str]:
        """Search output for lines matching a regex pattern."""
        regex = re.compile(pattern)
        matches = []
        for item in self.output_buffer:
            if regex.search(item["text"]):
                matches.append(item["text"])
        return matches


class ProcessManager:
    """
    Comprehensive process manager for NAVI agents.

    Handles:
    - Background processes
    - Interactive processes
    - Parallel execution
    - Process groups and cleanup
    """

    _instance: Optional["ProcessManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.processes: Dict[str, ManagedProcess] = {}
        self._output_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._initialized = True
        self._session_id = uuid.uuid4().hex[:8]

    def _generate_process_id(self) -> str:
        """Generate a unique process ID."""
        return f"proc_{uuid.uuid4().hex[:8]}"

    async def start_background(
        self,
        command: str,
        working_dir: str,
        env: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Start a command in background and return immediately.

        Args:
            command: The command to run
            working_dir: Working directory
            env: Optional environment variables
            tags: Optional tags for grouping (e.g., ["session-123", "server"])
        """
        process_id = self._generate_process_id()

        try:
            # Merge environment
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
                # Register any secrets in env
                for key in ["PASSWORD", "SECRET", "TOKEN", "API_KEY", "APIKEY"]:
                    for env_key, env_val in env.items():
                        if key.lower() in env_key.lower():
                            register_secret(env_val)

            # Start the process
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=full_env,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

            # Create managed process record
            managed = ManagedProcess(
                process_id=process_id,
                command=command,
                pid=process.pid,
                start_time=datetime.now(),
                working_dir=working_dir,
                process=process,
                env=env,
                tags=set(tags) if tags else {self._session_id},
            )

            async with self._lock:
                self.processes[process_id] = managed

            # Start background task to collect output
            task = asyncio.create_task(self._collect_output(process_id, process))
            self._output_tasks[process_id] = task

            logger.info(
                f"[ProcessManager] Started background process {process_id}: {command[:50]}..."
            )

            return {
                "success": True,
                "process_id": process_id,
                "pid": process.pid,
                "message": f"Process started. Use check_process('{process_id}') to monitor.",
            }

        except Exception as e:
            logger.error(f"[ProcessManager] Failed to start process: {e}")
            return {"success": False, "error": str(e)}

    async def run_interactive(
        self,
        command: str,
        working_dir: str,
        inputs: List[Dict[str, str]],
        timeout: int = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Run an interactive command that requires stdin input.

        Args:
            command: The command to run
            working_dir: Working directory
            inputs: List of {expect: "pattern", send: "response"} pairs
            timeout: Maximum time to wait
            env: Optional environment variables

        Example:
            run_interactive("npm init", "/app", [
                {"expect": "package name", "send": "my-app"},
                {"expect": "version", "send": "1.0.0"},
                {"expect": "description", "send": "My app"},
            ])
        """
        try:
            full_env = os.environ.copy()
            if env:
                full_env.update(env)

            process = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=full_env,
            )

            output_lines = []
            input_index = 0

            async def read_and_respond():
                nonlocal input_index
                buffer = ""

                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            process.stdout.read(100), timeout=5
                        )
                        if not chunk:
                            break

                        text = chunk.decode("utf-8", errors="replace")
                        buffer += text
                        output_lines.append(text)

                        # Check if we should send input
                        if input_index < len(inputs):
                            expected = inputs[input_index].get("expect", "")
                            if expected.lower() in buffer.lower():
                                response = inputs[input_index].get("send", "") + "\n"
                                process.stdin.write(response.encode())
                                await process.stdin.drain()
                                input_index += 1
                                buffer = ""

                    except asyncio.TimeoutError:
                        # Check if process is still running
                        if process.returncode is not None:
                            break
                        continue

            try:
                await asyncio.wait_for(read_and_respond(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": f"Timeout after {timeout}s",
                    "output": mask_secrets("".join(output_lines)),
                    "inputs_sent": input_index,
                }

            await process.wait()

            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "output": mask_secrets("".join(output_lines)),
                "inputs_sent": input_index,
                "all_inputs_used": input_index == len(inputs),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_parallel(
        self,
        commands: List[Dict[str, Any]],
        working_dir: str,
        timeout: int = 300,
        fail_fast: bool = False,
    ) -> Dict[str, Any]:
        """
        Run multiple commands in parallel and wait for all to complete.

        Args:
            commands: List of {command: str, name: str (optional)}
            working_dir: Working directory
            timeout: Maximum time to wait for all
            fail_fast: Stop all if one fails

        Example:
            run_parallel([
                {"command": "npm run lint", "name": "lint"},
                {"command": "npm run test", "name": "test"},
                {"command": "npm run build", "name": "build"}
            ], "/app")
        """
        results = {}
        tasks = []

        async def run_one(cmd_info: Dict) -> Tuple[str, Dict]:
            name = cmd_info.get("name", cmd_info["command"][:20])
            command = cmd_info["command"]

            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                return name, {
                    "success": process.returncode == 0,
                    "exit_code": process.returncode,
                    "stdout": mask_secrets(
                        stdout.decode("utf-8", errors="replace")[:5000]
                    ),
                    "stderr": mask_secrets(
                        stderr.decode("utf-8", errors="replace")[:2000]
                    ),
                }
            except asyncio.TimeoutError:
                return name, {"success": False, "error": "Timeout"}
            except Exception as e:
                return name, {"success": False, "error": str(e)}

        # Start all tasks
        for cmd_info in commands:
            tasks.append(asyncio.create_task(run_one(cmd_info)))

        # Wait for completion
        if fail_fast:
            # Return on first failure
            for coro in asyncio.as_completed(tasks):
                name, result = await coro
                results[name] = result
                if not result.get("success"):
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    break
        else:
            # Wait for all
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for item in completed:
                if isinstance(item, tuple):
                    name, result = item
                    results[name] = result

        all_success = all(r.get("success", False) for r in results.values())

        return {
            "success": all_success,
            "results": results,
            "total": len(commands),
            "passed": sum(1 for r in results.values() if r.get("success")),
            "failed": sum(1 for r in results.values() if not r.get("success")),
        }

    async def _collect_output(
        self, process_id: str, process: asyncio.subprocess.Process
    ):
        """Background task to collect output from a process."""
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace").rstrip()

                async with self._lock:
                    if process_id in self.processes:
                        self.processes[process_id].add_output(text)

            exit_code = await process.wait()

            async with self._lock:
                if process_id in self.processes:
                    self.processes[process_id].is_running = False
                    self.processes[process_id].exit_code = exit_code

            logger.info(
                f"[ProcessManager] Process {process_id} exited with code {exit_code}"
            )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ProcessManager] Error collecting output: {e}")

    async def check_process(self, process_id: str) -> Dict[str, Any]:
        """Check the status of a background process."""
        async with self._lock:
            if process_id not in self.processes:
                return {
                    "success": False,
                    "error": f"Unknown process: {process_id}",
                    "known_processes": list(self.processes.keys()),
                }

            proc = self.processes[process_id]

            return {
                "success": True,
                "process_id": process_id,
                "command": proc.command,
                "pid": proc.pid,
                "is_running": proc.is_running,
                "exit_code": proc.exit_code,
                "uptime_seconds": (datetime.now() - proc.start_time).total_seconds(),
                "recent_output": proc.get_recent_output(20),
                "output_lines": len(proc.output_buffer),
            }

    async def get_output(self, process_id: str, lines: int = 50) -> Dict[str, Any]:
        """Get recent output from a background process."""
        async with self._lock:
            if process_id not in self.processes:
                return {"success": False, "error": f"Unknown process: {process_id}"}

            proc = self.processes[process_id]
            return {
                "success": True,
                "process_id": process_id,
                "is_running": proc.is_running,
                "output": proc.get_recent_output(lines),
                "total_lines": len(proc.output_buffer),
            }

    async def wait_for_log_pattern(
        self, process_id: str, pattern: str, timeout: int = 60, interval: float = 0.5
    ) -> Dict[str, Any]:
        """
        Wait for a specific pattern to appear in process output.

        Args:
            process_id: The process to monitor
            pattern: Regex pattern to search for
            timeout: Maximum seconds to wait
            interval: Seconds between checks

        Example:
            wait_for_log_pattern(proc_id, r"Server started on port \d+")
            wait_for_log_pattern(proc_id, "Database connected")
            wait_for_log_pattern(proc_id, "ready|started|listening", timeout=30)
        """
        start_time = time.time()
        regex = re.compile(pattern, re.IGNORECASE)
        checked_lines = 0

        while time.time() - start_time < timeout:
            async with self._lock:
                if process_id not in self.processes:
                    return {
                        "success": False,
                        "error": f"Process {process_id} not found",
                    }

                proc = self.processes[process_id]
                output_list = list(proc.output_buffer)

                # Check new lines since last check
                for item in output_list[checked_lines:]:
                    if regex.search(item["text"]):
                        return {
                            "success": True,
                            "pattern": pattern,
                            "matched_line": item["text"],
                            "elapsed_seconds": time.time() - start_time,
                        }

                checked_lines = len(output_list)

                # Check if process died
                if not proc.is_running:
                    return {
                        "success": False,
                        "error": "Process exited before pattern was found",
                        "exit_code": proc.exit_code,
                        "recent_output": proc.get_recent_output(20),
                    }

            await asyncio.sleep(interval)

        return {
            "success": False,
            "error": f"Pattern not found after {timeout}s",
            "pattern": pattern,
            "recent_output": (
                self.processes.get(
                    process_id,
                    ManagedProcess(
                        process_id="",
                        command="",
                        pid=0,
                        start_time=datetime.now(),
                        working_dir="",
                    ),
                ).get_recent_output(30)
                if process_id in self.processes
                else ""
            ),
        }

    async def kill_process(
        self, process_id: str, signal_type: str = "TERM", timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Kill a background process.

        Args:
            process_id: The process to kill
            signal_type: "TERM" for graceful, "KILL" for force
            timeout: Seconds to wait for graceful shutdown before forcing
        """
        async with self._lock:
            if process_id not in self.processes:
                return {"success": False, "error": f"Unknown process: {process_id}"}

            proc = self.processes[process_id]

            if not proc.is_running:
                return {
                    "success": True,
                    "message": "Process already stopped",
                    "exit_code": proc.exit_code,
                }

            try:
                sig = signal.SIGKILL if signal_type == "KILL" else signal.SIGTERM

                # Kill the entire process group
                if hasattr(os, "killpg"):
                    try:
                        os.killpg(os.getpgid(proc.pid), sig)
                    except ProcessLookupError:
                        pass
                else:
                    if signal_type == "KILL":
                        proc.process.kill()
                    else:
                        proc.process.terminate()

                # Wait for process to end
                await asyncio.sleep(0.5)

                # Force kill if still running and we used TERM
                if proc.is_running and signal_type == "TERM":
                    await asyncio.sleep(timeout)
                    if proc.is_running:
                        if hasattr(os, "killpg"):
                            try:
                                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                            except ProcessLookupError:
                                pass

                proc.is_running = False

                return {
                    "success": True,
                    "message": f"Process {process_id} killed",
                    "pid": proc.pid,
                }

            except Exception as e:
                return {"success": False, "error": f"Failed to kill: {e}"}

    async def cleanup_session(
        self, tags: Optional[List[str]] = None, force: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up processes, optionally filtered by tags.

        Args:
            tags: Only clean up processes with these tags. If None, cleans all.
            force: Use SIGKILL instead of SIGTERM
        """
        killed = []
        errors = []

        async with self._lock:
            to_kill = []
            for proc_id, proc in self.processes.items():
                if tags is None or proc.tags.intersection(set(tags)):
                    if proc.is_running:
                        to_kill.append(proc_id)

        for proc_id in to_kill:
            result = await self.kill_process(
                proc_id, signal_type="KILL" if force else "TERM"
            )
            if result.get("success"):
                killed.append(proc_id)
            else:
                errors.append({"process_id": proc_id, "error": result.get("error")})

        # Remove stopped processes from tracking
        async with self._lock:
            stopped = [
                pid for pid, proc in self.processes.items() if not proc.is_running
            ]
            for pid in stopped:
                del self.processes[pid]
                if pid in self._output_tasks:
                    self._output_tasks[pid].cancel()
                    del self._output_tasks[pid]

        return {
            "success": len(errors) == 0,
            "killed": killed,
            "errors": errors,
            "cleaned_up": len(stopped),
        }

    async def list_processes(self) -> Dict[str, Any]:
        """List all managed processes."""
        async with self._lock:
            processes = []
            for proc_id, proc in self.processes.items():
                processes.append(
                    {
                        "process_id": proc_id,
                        "command": (
                            proc.command[:50] + "..."
                            if len(proc.command) > 50
                            else proc.command
                        ),
                        "pid": proc.pid,
                        "is_running": proc.is_running,
                        "uptime_seconds": (
                            (datetime.now() - proc.start_time).total_seconds()
                            if proc.is_running
                            else None
                        ),
                        "exit_code": proc.exit_code,
                        "tags": list(proc.tags),
                    }
                )

            return {
                "success": True,
                "processes": processes,
                "total": len(processes),
                "running": sum(1 for p in processes if p["is_running"]),
            }


# =============================================================================
# Service Orchestration
# =============================================================================


async def start_service_chain(
    services: List[Dict[str, Any]], working_dir: str
) -> Dict[str, Any]:
    """
    Start multiple services in order, with dependency handling.

    Args:
        services: List of service definitions:
            {
                "name": "database",
                "command": "docker-compose up -d postgres",
                "health_check": {"type": "port", "port": 5432},
                "startup_timeout": 30
            },
            {
                "name": "backend",
                "command": "npm run dev",
                "depends_on": ["database"],
                "health_check": {"type": "http", "url": "http://localhost:3000/health"},
                "startup_timeout": 60
            }
        working_dir: Base working directory

    Returns:
        Status of all services with their process IDs
    """
    pm = ProcessManager()
    results = {}
    started_services = {}

    # Build dependency graph
    service_map = {s["name"]: s for s in services}

    def get_start_order():
        """Topological sort for dependencies."""
        visited = set()
        order = []

        def visit(name):
            if name in visited:
                return
            visited.add(name)
            service = service_map.get(name, {})
            for dep in service.get("depends_on", []):
                visit(dep)
            order.append(name)

        for service in services:
            visit(service["name"])

        return order

    start_order = get_start_order()

    for service_name in start_order:
        if service_name not in service_map:
            continue

        service = service_map[service_name]

        # Check dependencies are healthy
        for dep in service.get("depends_on", []):
            if dep not in started_services:
                results[service_name] = {
                    "success": False,
                    "error": f"Dependency '{dep}' not started",
                }
                continue

        # Start the service
        start_result = await pm.start_background(
            command=service["command"],
            working_dir=working_dir,
            tags=[service_name, "service-chain"],
        )

        if not start_result.get("success"):
            results[service_name] = start_result
            continue

        process_id = start_result["process_id"]

        # Wait for health check
        health_check = service.get("health_check", {})
        timeout = service.get("startup_timeout", 30)

        if health_check:
            health_result = await wait_for_condition(
                condition_type=health_check.get("type", "port"),
                timeout=timeout,
                **{k: v for k, v in health_check.items() if k != "type"},
            )

            if not health_result.get("success"):
                results[service_name] = {
                    "success": False,
                    "process_id": process_id,
                    "error": f"Health check failed: {health_result.get('error')}",
                    "health_check": health_result,
                }
                continue

        started_services[service_name] = process_id
        results[service_name] = {
            "success": True,
            "process_id": process_id,
            "pid": start_result.get("pid"),
        }

    all_success = all(r.get("success", False) for r in results.values())

    return {
        "success": all_success,
        "services": results,
        "started": list(started_services.keys()),
        "failed": [name for name, r in results.items() if not r.get("success")],
    }


# =============================================================================
# Resource Monitoring
# =============================================================================


async def check_resources(
    process_id: Optional[str] = None, pid: Optional[int] = None
) -> Dict[str, Any]:
    """
    Check resource usage of a process or the system.

    Args:
        process_id: Managed process ID (from ProcessManager)
        pid: Direct PID to check

    Returns system resources if no process specified.
    """
    try:
        if process_id:
            pm = ProcessManager()
            async with pm._lock:
                if process_id not in pm.processes:
                    return {"success": False, "error": f"Unknown process: {process_id}"}
                pid = pm.processes[process_id].pid

        if pid:
            try:
                proc = psutil.Process(pid)
                with proc.oneshot():
                    return {
                        "success": True,
                        "pid": pid,
                        "cpu_percent": proc.cpu_percent(interval=0.1),
                        "memory_mb": proc.memory_info().rss / 1024 / 1024,
                        "memory_percent": proc.memory_percent(),
                        "num_threads": proc.num_threads(),
                        "status": proc.status(),
                        "create_time": datetime.fromtimestamp(
                            proc.create_time()
                        ).isoformat(),
                    }
            except psutil.NoSuchProcess:
                return {"success": False, "error": f"Process {pid} not found"}

        # System-wide resources
        return {
            "success": True,
            "system": True,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "memory_available_gb": psutil.virtual_memory().available
            / 1024
            / 1024
            / 1024,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_gb": psutil.disk_usage("/").total / 1024 / 1024 / 1024,
            "disk_free_gb": psutil.disk_usage("/").free / 1024 / 1024 / 1024,
            "disk_percent": psutil.disk_usage("/").percent,
        }

    except ImportError:
        return {
            "success": False,
            "error": "psutil not installed. Run: pip install psutil",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Condition Verification (Extended)
# =============================================================================


async def verify_condition(condition_type: str, **kwargs) -> Dict[str, Any]:
    """
    Verify if a condition is true. Comprehensive verification for any scenario.

    Condition types:
    - "http": Check HTTP endpoint responds
    - "port": Check if port is listening
    - "file_exists": Check if file exists
    - "file_contains": Check if file contains pattern
    - "process_running": Check if process is running
    - "command_succeeds": Run command and check exit code
    - "database": Check database connectivity
    - "websocket": Check WebSocket connection
    - "ssl": Check SSL certificate
    - "dns": Check DNS resolution
    - "tcp": Check TCP connection
    """

    if condition_type == "http":
        url = kwargs.get("url", "http://localhost:3000")
        method = kwargs.get("method", "GET")
        expected_status = kwargs.get("expected_status")
        timeout = kwargs.get("timeout", 5)
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

                return {
                    "success": success,
                    "condition": "http",
                    "url": url,
                    "status": status,
                    "responding": True,
                    "body_preview": body_preview[:200],
                }
        except urllib.error.HTTPError as e:
            return {
                "success": expected_status == e.code if expected_status else False,
                "condition": "http",
                "url": url,
                "status": e.code,
                "responding": True,
                "error": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "condition": "http",
                "url": url,
                "responding": False,
                "error": str(e),
            }

    elif condition_type == "port":
        port = kwargs.get("port")
        host = kwargs.get("host", "localhost")
        timeout = kwargs.get("timeout", 2)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            sock.close()

            listening = result == 0
            return {
                "success": listening,
                "condition": "port",
                "port": port,
                "host": host,
                "listening": listening,
            }
        except Exception as e:
            return {"success": False, "condition": "port", "error": str(e)}

    elif condition_type == "tcp":
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

            return {
                "success": success,
                "condition": "tcp",
                "host": host,
                "port": port,
                "connected": True,
                "response": response_data,
            }
        except Exception as e:
            return {"success": False, "condition": "tcp", "error": str(e)}

    elif condition_type == "file_exists":
        path = kwargs.get("path")

        exists = os.path.exists(path)
        return {
            "success": exists,
            "condition": "file_exists",
            "path": path,
            "exists": exists,
            "is_file": os.path.isfile(path) if exists else None,
            "is_dir": os.path.isdir(path) if exists else None,
            "size_bytes": (
                os.path.getsize(path) if exists and os.path.isfile(path) else None
            ),
        }

    elif condition_type == "file_contains":
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")

        try:
            with open(path, "r", errors="replace") as f:
                content = f.read()

            found = bool(re.search(pattern, content))
            matches = re.findall(pattern, content)[:5]

            return {
                "success": found,
                "condition": "file_contains",
                "path": path,
                "pattern": pattern,
                "found": found,
                "matches": matches,
            }
        except Exception as e:
            return {"success": False, "condition": "file_contains", "error": str(e)}

    elif condition_type == "process_running":
        name = kwargs.get("name")
        exact = kwargs.get("exact", False)

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
                        return {
                            "success": True,
                            "condition": "process_running",
                            "name": name,
                            "running": True,
                            "pid": proc.info["pid"],
                            "process_name": proc_name,
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "success": False,
                "condition": "process_running",
                "name": name,
                "running": False,
            }
        except Exception as e:
            return {"success": False, "condition": "process_running", "error": str(e)}

    elif condition_type == "command_succeeds":
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

            return {
                "success": result.returncode == 0,
                "condition": "command_succeeds",
                "command": command,
                "exit_code": result.returncode,
                "stdout": mask_secrets(
                    result.stdout.decode("utf-8", errors="replace")[:1000]
                ),
                "stderr": mask_secrets(
                    result.stderr.decode("utf-8", errors="replace")[:500]
                ),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "condition": "command_succeeds",
                "error": f"Timeout after {timeout}s",
            }
        except Exception as e:
            return {"success": False, "condition": "command_succeeds", "error": str(e)}

    elif condition_type == "database":
        db_type = kwargs.get("db_type", "postgres")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port")
        database = kwargs.get("database")
        user = kwargs.get("user")
        password = kwargs.get("password")

        # Register password as secret
        if password:
            register_secret(password)

        # Default ports
        default_ports = {
            "postgres": 5432,
            "postgresql": 5432,
            "mysql": 3306,
            "mariadb": 3306,
            "mongodb": 27017,
            "mongo": 27017,
            "redis": 6379,
            "sqlite": None,
        }
        port = port or default_ports.get(db_type, 5432)

        # First check port is open
        if port:
            port_check = await verify_condition("port", host=host, port=port)
            if not port_check.get("success"):
                return {
                    "success": False,
                    "condition": "database",
                    "db_type": db_type,
                    "error": f"Port {port} not listening",
                    "port_check": port_check,
                }

        # Try actual connection based on db type
        try:
            if db_type in ("postgres", "postgresql"):
                # Try psycopg2 or pg_isready
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
                # Generic TCP check as fallback
                return await verify_condition("port", host=host, port=port)

            return {
                "success": connected,
                "condition": "database",
                "db_type": db_type,
                "host": host,
                "port": port,
                "connected": connected,
            }
        except Exception as e:
            return {"success": False, "condition": "database", "error": str(e)}

    elif condition_type == "websocket":
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 5)

        try:
            import websockets

            async def check_ws():
                async with websockets.connect(url, close_timeout=timeout):
                    return True

            await asyncio.wait_for(check_ws(), timeout=timeout)
            return {
                "success": True,
                "condition": "websocket",
                "url": url,
                "connected": True,
            }
        except ImportError:
            # Fallback to basic HTTP upgrade check
            try:
                http_url = url.replace("ws://", "http://").replace("wss://", "https://")
                req = urllib.request.Request(http_url)
                req.add_header("Upgrade", "websocket")
                req.add_header("Connection", "Upgrade")

                try:
                    urllib.request.urlopen(req, timeout=timeout)
                except urllib.error.HTTPError as e:
                    # 101 Switching Protocols or 426 Upgrade Required indicates WS support
                    if e.code in (101, 426):
                        return {
                            "success": True,
                            "condition": "websocket",
                            "url": url,
                            "connected": True,
                        }

                return {
                    "success": False,
                    "condition": "websocket",
                    "url": url,
                    "error": "WebSocket not supported",
                }
            except Exception as e:
                return {"success": False, "condition": "websocket", "error": str(e)}
        except Exception as e:
            return {
                "success": False,
                "condition": "websocket",
                "url": url,
                "error": str(e),
            }

    elif condition_type == "ssl":
        host = kwargs.get("host")
        port = kwargs.get("port", 443)

        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()

                    # Parse expiry
                    not_after = cert.get("notAfter", "")
                    expiry = (
                        datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        if not_after
                        else None
                    )
                    days_until_expiry = (
                        (expiry - datetime.now()).days if expiry else None
                    )

                    return {
                        "success": True,
                        "condition": "ssl",
                        "host": host,
                        "port": port,
                        "valid": True,
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "expires": not_after,
                        "days_until_expiry": days_until_expiry,
                        "expired": days_until_expiry < 0 if days_until_expiry else None,
                    }
        except ssl.SSLError as e:
            return {"success": False, "condition": "ssl", "error": f"SSL error: {e}"}
        except Exception as e:
            return {"success": False, "condition": "ssl", "error": str(e)}

    elif condition_type == "dns":
        hostname = kwargs.get("hostname")
        record_type = kwargs.get("record_type", "A")

        try:
            if record_type == "A":
                result = socket.gethostbyname(hostname)
                return {
                    "success": True,
                    "condition": "dns",
                    "hostname": hostname,
                    "record_type": record_type,
                    "resolved": True,
                    "address": result,
                }
            else:
                # Use getaddrinfo for more control
                results = socket.getaddrinfo(hostname, None)
                addresses = list(set(r[4][0] for r in results))
                return {
                    "success": len(addresses) > 0,
                    "condition": "dns",
                    "hostname": hostname,
                    "resolved": len(addresses) > 0,
                    "addresses": addresses,
                }
        except socket.gaierror as e:
            return {
                "success": False,
                "condition": "dns",
                "hostname": hostname,
                "error": str(e),
            }
        except Exception as e:
            return {"success": False, "condition": "dns", "error": str(e)}

    elif condition_type == "health_aggregate":
        checks = kwargs.get("checks", [])
        require_all = kwargs.get("require_all", True)

        results = []
        for check in checks:
            check_copy = check.copy()
            check_type = check_copy.pop("type", "http")
            result = await verify_condition(check_type, **check_copy)
            results.append({"check": check_type, **result})

        if require_all:
            success = all(r.get("success") for r in results)
        else:
            success = any(r.get("success") for r in results)

        return {
            "success": success,
            "condition": "health_aggregate",
            "checks": results,
            "passed": sum(1 for r in results if r.get("success")),
            "total": len(results),
        }

    elif condition_type == "docker":
        # Check Docker container status
        container = kwargs.get("container")
        check_health = kwargs.get("check_health", True)

        try:
            # Check if container is running
            result = subprocess.run(
                f"docker inspect --format='{{{{.State.Status}}}}' {container}",
                shell=True,
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "condition": "docker",
                    "container": container,
                    "error": "Container not found",
                }

            status = result.stdout.decode().strip().strip("'")

            if status != "running":
                return {
                    "success": False,
                    "condition": "docker",
                    "container": container,
                    "status": status,
                    "running": False,
                }

            # Check health status if requested
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

            return {
                "success": True,
                "condition": "docker",
                "container": container,
                "status": status,
                "running": True,
                "health_status": health_status,
            }
        except Exception as e:
            return {"success": False, "condition": "docker", "error": str(e)}

    elif condition_type == "docker_compose":
        # Check docker-compose services
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
                return {
                    "success": False,
                    "condition": "docker_compose",
                    "error": result.stderr.decode(),
                }

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
                return {
                    "success": found,
                    "condition": "docker_compose",
                    "service": service,
                    "running": found,
                    "all_services": running_services,
                }
            else:
                return {
                    "success": len(running_services) > 0,
                    "condition": "docker_compose",
                    "services": running_services,
                    "count": len(running_services),
                }
        except Exception as e:
            return {"success": False, "condition": "docker_compose", "error": str(e)}

    elif condition_type == "queue":
        # Check message queue connectivity
        queue_type = kwargs.get("queue_type", "rabbitmq")
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port")

        # Default ports
        default_ports = {
            "rabbitmq": 5672,
            "kafka": 9092,
            "redis": 6379,  # Redis can be used as queue
            "nats": 4222,
            "sqs": None,  # AWS SQS is HTTP-based
        }
        port = port or default_ports.get(queue_type, 5672)

        try:
            if queue_type == "rabbitmq":
                # Check RabbitMQ management API if available
                mgmt_port = kwargs.get("management_port", 15672)
                try:
                    result = await verify_condition(
                        "http", url=f"http://{host}:{mgmt_port}/api/overview", timeout=5
                    )
                    if result.get("success"):
                        return {
                            "success": True,
                            "condition": "queue",
                            "queue_type": queue_type,
                            "host": host,
                            "connected": True,
                            "via": "management_api",
                        }
                except Exception:
                    pass

                # Fallback to port check
                port_result = await verify_condition("port", host=host, port=port)
                return {
                    "success": port_result.get("success"),
                    "condition": "queue",
                    "queue_type": queue_type,
                    "host": host,
                    "port": port,
                    "connected": port_result.get("success"),
                    "via": "port_check",
                }

            elif queue_type == "kafka":
                # Check Kafka broker
                port_result = await verify_condition("port", host=host, port=port)
                return {
                    "success": port_result.get("success"),
                    "condition": "queue",
                    "queue_type": queue_type,
                    "host": host,
                    "port": port,
                    "connected": port_result.get("success"),
                }

            else:
                # Generic port check
                port_result = await verify_condition("port", host=host, port=port)
                return {
                    "success": port_result.get("success"),
                    "condition": "queue",
                    "queue_type": queue_type,
                    "host": host,
                    "port": port,
                    "connected": port_result.get("success"),
                }
        except Exception as e:
            return {"success": False, "condition": "queue", "error": str(e)}

    elif condition_type == "graphql":
        # Check GraphQL endpoint with introspection
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 5)

        try:
            introspection_query = json.dumps(
                {"query": "{ __schema { types { name } } }"}
            ).encode()

            req = urllib.request.Request(
                url,
                data=introspection_query,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode()
                data = json.loads(body)

                has_schema = "data" in data and "__schema" in data.get("data", {})

                return {
                    "success": has_schema,
                    "condition": "graphql",
                    "url": url,
                    "responding": True,
                    "has_schema": has_schema,
                }
        except Exception as e:
            return {
                "success": False,
                "condition": "graphql",
                "url": url,
                "error": str(e),
            }

    elif condition_type == "grpc":
        # Check gRPC health
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 50051)

        try:
            # Try grpc_health_probe if available
            result = subprocess.run(
                f"grpc_health_probe -addr={host}:{port}",
                shell=True,
                capture_output=True,
                timeout=5,
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "condition": "grpc",
                    "host": host,
                    "port": port,
                    "healthy": True,
                    "via": "grpc_health_probe",
                }

            # Fallback to port check
            port_result = await verify_condition("port", host=host, port=port)
            return {
                "success": port_result.get("success"),
                "condition": "grpc",
                "host": host,
                "port": port,
                "connected": port_result.get("success"),
                "via": "port_check",
            }
        except Exception as e:
            return {"success": False, "condition": "grpc", "error": str(e)}

    elif condition_type == "elasticsearch":
        # Check Elasticsearch cluster health
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 9200)
        cluster_health = kwargs.get("require_green", False)

        try:
            url = f"http://{host}:{port}/_cluster/health"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                status = data.get("status", "unknown")

                success = True
                if cluster_health and status != "green":
                    success = False
                elif status == "red":
                    success = False

                return {
                    "success": success,
                    "condition": "elasticsearch",
                    "host": host,
                    "port": port,
                    "cluster_status": status,
                    "number_of_nodes": data.get("number_of_nodes"),
                    "active_shards": data.get("active_shards"),
                }
        except Exception as e:
            return {"success": False, "condition": "elasticsearch", "error": str(e)}

    elif condition_type == "kubernetes":
        # Check Kubernetes resource status
        resource_type = kwargs.get("resource_type", "pod")  # pod, deployment, service
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
                return {
                    "success": False,
                    "condition": "kubernetes",
                    "resource_type": resource_type,
                    "name": name,
                    "error": result.stderr.decode(),
                }

            output = result.stdout.decode().strip().strip("'")

            if resource_type == "pod":
                success = output == "Running"
            elif resource_type == "deployment":
                parts = output.split("/")
                success = len(parts) == 2 and parts[0] == parts[1] and int(parts[0]) > 0
            else:
                success = bool(output)

            return {
                "success": success,
                "condition": "kubernetes",
                "resource_type": resource_type,
                "name": name,
                "namespace": namespace,
                "status": output,
            }
        except Exception as e:
            return {"success": False, "condition": "kubernetes", "error": str(e)}

    elif condition_type == "s3":
        # Check S3/object storage bucket access
        bucket = kwargs.get("bucket")
        endpoint = kwargs.get("endpoint")  # For MinIO, etc.
        region = kwargs.get("region", "us-east-1")

        try:
            # Use AWS CLI
            endpoint_arg = f"--endpoint-url {endpoint}" if endpoint else ""
            cmd = f"aws s3 ls s3://{bucket} {endpoint_arg} --region {region} --max-items 1"

            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            return {
                "success": result.returncode == 0,
                "condition": "s3",
                "bucket": bucket,
                "accessible": result.returncode == 0,
                "error": result.stderr.decode() if result.returncode != 0 else None,
            }
        except Exception as e:
            return {"success": False, "condition": "s3", "error": str(e)}

    elif condition_type == "smtp":
        # Check SMTP server connectivity
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 25)
        use_tls = kwargs.get("use_tls", False)

        try:
            import smtplib

            if use_tls:
                server = smtplib.SMTP_SSL(host, port, timeout=5)
            else:
                server = smtplib.SMTP(host, port, timeout=5)

            server.ehlo()
            server.quit()

            return {
                "success": True,
                "condition": "smtp",
                "host": host,
                "port": port,
                "connected": True,
            }
        except ImportError:
            # Fallback to port check
            port_result = await verify_condition("port", host=host, port=port)
            return {
                "success": port_result.get("success"),
                "condition": "smtp",
                "host": host,
                "port": port,
                "connected": port_result.get("success"),
                "via": "port_check",
            }
        except Exception as e:
            return {"success": False, "condition": "smtp", "error": str(e)}

    elif condition_type == "ssh":
        # Check SSH connectivity
        host = kwargs.get("host")
        port = kwargs.get("port", 22)
        user = kwargs.get("user")
        key_file = kwargs.get("key_file")

        try:
            # First check port
            port_result = await verify_condition("port", host=host, port=port)
            if not port_result.get("success"):
                return {
                    "success": False,
                    "condition": "ssh",
                    "host": host,
                    "port": port,
                    "error": "SSH port not accessible",
                }

            # Try actual SSH connection
            key_arg = f"-i {key_file}" if key_file else ""
            user_arg = f"{user}@" if user else ""
            cmd = f"ssh {key_arg} -o ConnectTimeout=5 -o BatchMode=yes {user_arg}{host} -p {port} exit 2>&1"

            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            # SSH returns 0 on success, or error messages
            success = result.returncode == 0

            return {
                "success": success,
                "condition": "ssh",
                "host": host,
                "port": port,
                "connected": success,
                "error": result.stderr.decode() if not success else None,
            }
        except Exception as e:
            return {"success": False, "condition": "ssh", "error": str(e)}

    elif condition_type == "ldap":
        # Check LDAP/Active Directory connectivity
        host = kwargs.get("host")
        port = kwargs.get("port", 389)
        use_ssl = kwargs.get("use_ssl", False)

        try:
            actual_port = port if port else (636 if use_ssl else 389)
            port_result = await verify_condition("port", host=host, port=actual_port)

            return {
                "success": port_result.get("success"),
                "condition": "ldap",
                "host": host,
                "port": actual_port,
                "connected": port_result.get("success"),
            }
        except Exception as e:
            return {"success": False, "condition": "ldap", "error": str(e)}

    elif condition_type == "ftp":
        # Check FTP/SFTP connectivity
        host = kwargs.get("host")
        port = kwargs.get("port", 21)
        sftp = kwargs.get("sftp", False)

        try:
            actual_port = port if port else (22 if sftp else 21)
            port_result = await verify_condition("port", host=host, port=actual_port)

            return {
                "success": port_result.get("success"),
                "condition": "ftp",
                "host": host,
                "port": actual_port,
                "protocol": "sftp" if sftp else "ftp",
                "connected": port_result.get("success"),
            }
        except Exception as e:
            return {"success": False, "condition": "ftp", "error": str(e)}

    elif condition_type == "url_accessible":
        # Check if URL is accessible (HEAD request, good for checking downloads)
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 10)
        check_content_length = kwargs.get("check_content_length", False)

        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "NAVI-HealthCheck/1.0")

            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")

                result = {
                    "success": True,
                    "condition": "url_accessible",
                    "url": url,
                    "status": response.status,
                    "accessible": True,
                    "content_type": response.headers.get("Content-Type"),
                }

                if content_length:
                    result["content_length"] = int(content_length)

                if check_content_length and content_length:
                    result["success"] = int(content_length) > 0

                return result
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "condition": "url_accessible",
                "url": url,
                "status": e.code,
                "error": str(e),
            }
        except Exception as e:
            return {
                "success": False,
                "condition": "url_accessible",
                "url": url,
                "error": str(e),
            }

    elif condition_type == "git_remote":
        # Check if git remote is accessible
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 10)

        try:
            result = subprocess.run(
                f"git ls-remote --exit-code {url} HEAD",
                shell=True,
                capture_output=True,
                timeout=timeout,
            )

            return {
                "success": result.returncode == 0,
                "condition": "git_remote",
                "url": url,
                "accessible": result.returncode == 0,
                "error": result.stderr.decode() if result.returncode != 0 else None,
            }
        except Exception as e:
            return {"success": False, "condition": "git_remote", "error": str(e)}

    elif condition_type == "npm_registry":
        # Check npm registry accessibility
        registry = kwargs.get("registry", "https://registry.npmjs.org")
        package = kwargs.get("package")

        try:
            url = f"{registry}/{package}" if package else f"{registry}/-/ping"

            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "success": True,
                    "condition": "npm_registry",
                    "registry": registry,
                    "accessible": True,
                    "package": package,
                }
        except Exception as e:
            return {"success": False, "condition": "npm_registry", "error": str(e)}

    elif condition_type == "docker_registry":
        # Check Docker registry accessibility
        registry = kwargs.get("registry", "docker.io")
        # image parameter reserved for future image-specific checks
        _ = kwargs.get("image")

        try:
            if registry == "docker.io":
                url = "https://registry.hub.docker.com/v2/"
            else:
                url = f"https://{registry}/v2/"

            req = urllib.request.Request(url)

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    return {
                        "success": True,
                        "condition": "docker_registry",
                        "registry": registry,
                        "accessible": True,
                    }
            except urllib.error.HTTPError as e:
                # 401 is expected for registries requiring auth
                if e.code == 401:
                    return {
                        "success": True,
                        "condition": "docker_registry",
                        "registry": registry,
                        "accessible": True,
                        "requires_auth": True,
                    }
                raise
        except Exception as e:
            return {"success": False, "condition": "docker_registry", "error": str(e)}

    elif condition_type == "systemd_service":
        # Check systemd service status (Linux)
        service = kwargs.get("service")

        try:
            result = subprocess.run(
                f"systemctl is-active {service}",
                shell=True,
                capture_output=True,
                timeout=5,
            )

            status = result.stdout.decode().strip()
            active = status == "active"

            return {
                "success": active,
                "condition": "systemd_service",
                "service": service,
                "status": status,
                "active": active,
            }
        except Exception as e:
            return {"success": False, "condition": "systemd_service", "error": str(e)}

    elif condition_type == "launchd_service":
        # Check launchd service status (macOS)
        service = kwargs.get("service")

        try:
            result = subprocess.run(
                f"launchctl list | grep {service}",
                shell=True,
                capture_output=True,
                timeout=5,
            )

            running = result.returncode == 0 and service in result.stdout.decode()

            return {
                "success": running,
                "condition": "launchd_service",
                "service": service,
                "running": running,
            }
        except Exception as e:
            return {"success": False, "condition": "launchd_service", "error": str(e)}

    elif condition_type == "disk_space":
        # Check disk space threshold
        path = kwargs.get("path", "/")
        min_free_gb = kwargs.get("min_free_gb", 1.0)
        max_used_percent = kwargs.get("max_used_percent", 90)

        try:
            usage = psutil.disk_usage(path)
            free_gb = usage.free / 1024 / 1024 / 1024
            used_percent = usage.percent

            success = free_gb >= min_free_gb and used_percent <= max_used_percent

            return {
                "success": success,
                "condition": "disk_space",
                "path": path,
                "total_gb": usage.total / 1024 / 1024 / 1024,
                "free_gb": free_gb,
                "used_percent": used_percent,
                "threshold_met": success,
            }
        except Exception as e:
            return {"success": False, "condition": "disk_space", "error": str(e)}

    elif condition_type == "memory_available":
        # Check available memory threshold
        min_available_gb = kwargs.get("min_available_gb", 0.5)
        max_used_percent = kwargs.get("max_used_percent", 90)

        try:
            mem = psutil.virtual_memory()
            available_gb = mem.available / 1024 / 1024 / 1024
            used_percent = mem.percent

            success = (
                available_gb >= min_available_gb and used_percent <= max_used_percent
            )

            return {
                "success": success,
                "condition": "memory_available",
                "total_gb": mem.total / 1024 / 1024 / 1024,
                "available_gb": available_gb,
                "used_percent": used_percent,
                "threshold_met": success,
            }
        except Exception as e:
            return {"success": False, "condition": "memory_available", "error": str(e)}

    elif condition_type == "cpu_usage":
        # Check CPU usage threshold
        max_percent = kwargs.get("max_percent", 90)
        interval = kwargs.get("interval", 1)

        try:
            cpu_percent = psutil.cpu_percent(interval=interval)
            success = cpu_percent <= max_percent

            return {
                "success": success,
                "condition": "cpu_usage",
                "cpu_percent": cpu_percent,
                "max_percent": max_percent,
                "threshold_met": success,
                "cpu_count": psutil.cpu_count(),
            }
        except Exception as e:
            return {"success": False, "condition": "cpu_usage", "error": str(e)}

    elif condition_type == "env_var":
        # Check environment variable exists and optionally matches value
        name = kwargs.get("name")
        expected_value = kwargs.get("value")
        pattern = kwargs.get("pattern")

        try:
            value = os.environ.get(name)

            if value is None:
                return {
                    "success": False,
                    "condition": "env_var",
                    "name": name,
                    "exists": False,
                }

            success = True
            if expected_value is not None:
                success = value == expected_value
            elif pattern is not None:
                success = bool(re.search(pattern, value))

            return {
                "success": success,
                "condition": "env_var",
                "name": name,
                "exists": True,
                "value": mask_secrets(value) if value else None,
                "matches": success,
            }
        except Exception as e:
            return {"success": False, "condition": "env_var", "error": str(e)}

    elif condition_type == "json_schema":
        # Validate JSON response against schema
        url = kwargs.get("url")
        schema = kwargs.get("schema")  # JSON schema dict
        json_path = kwargs.get("json_path")  # Path to extract before validation

        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                # Extract nested path if specified
                if json_path:
                    for key in json_path.split("."):
                        if isinstance(data, dict):
                            data = data.get(key, {})
                        elif isinstance(data, list) and key.isdigit():
                            data = data[int(key)] if int(key) < len(data) else {}

                # Basic schema validation (type checking)
                if schema:
                    expected_type = schema.get("type")
                    if expected_type == "object":
                        valid = isinstance(data, dict)
                        required = schema.get("required", [])
                        if valid and required:
                            valid = all(k in data for k in required)
                    elif expected_type == "array":
                        valid = isinstance(data, list)
                    elif expected_type == "string":
                        valid = isinstance(data, str)
                    elif expected_type == "number":
                        valid = isinstance(data, (int, float))
                    elif expected_type == "boolean":
                        valid = isinstance(data, bool)
                    else:
                        valid = True
                else:
                    valid = True

                return {
                    "success": valid,
                    "condition": "json_schema",
                    "url": url,
                    "valid": valid,
                    "data_type": type(data).__name__,
                }
        except Exception as e:
            return {"success": False, "condition": "json_schema", "error": str(e)}

    elif condition_type == "api_response":
        # Validate API response with custom conditions
        url = kwargs.get("url")
        method = kwargs.get("method", "GET")
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")
        expected_status = kwargs.get("expected_status", 200)
        response_contains = kwargs.get("response_contains")
        response_json_path = kwargs.get("response_json_path")
        response_json_value = kwargs.get("response_json_value")

        try:
            data = json.dumps(body).encode() if body else None
            req = urllib.request.Request(url, data=data, method=method)

            for key, value in headers.items():
                req.add_header(key, value)

            if body and "Content-Type" not in headers:
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                body_content = response.read().decode()

                success = status == expected_status

                if success and response_contains:
                    success = response_contains in body_content

                if success and response_json_path:
                    try:
                        data = json.loads(body_content)
                        for key in response_json_path.split("."):
                            data = data.get(key) if isinstance(data, dict) else None
                        if response_json_value is not None:
                            success = data == response_json_value
                        else:
                            success = data is not None
                    except json.JSONDecodeError:
                        success = False

                return {
                    "success": success,
                    "condition": "api_response",
                    "url": url,
                    "status": status,
                    "body_preview": body_content[:200] if body_content else None,
                }
        except urllib.error.HTTPError as e:
            return {
                "success": e.code == expected_status,
                "condition": "api_response",
                "url": url,
                "status": e.code,
            }
        except Exception as e:
            return {"success": False, "condition": "api_response", "error": str(e)}

    elif condition_type == "cron_job":
        # Check if cron job exists
        pattern = kwargs.get("pattern")  # Regex to match in crontab
        user = kwargs.get("user")

        try:
            user_arg = f"-u {user}" if user else ""
            result = subprocess.run(
                f"crontab {user_arg} -l 2>/dev/null",
                shell=True,
                capture_output=True,
                timeout=5,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "condition": "cron_job",
                    "error": "No crontab or access denied",
                }

            crontab = result.stdout.decode()
            found = (
                bool(re.search(pattern, crontab)) if pattern else bool(crontab.strip())
            )

            return {
                "success": found,
                "condition": "cron_job",
                "pattern": pattern,
                "found": found,
            }
        except Exception as e:
            return {"success": False, "condition": "cron_job", "error": str(e)}

    elif condition_type == "network_interface":
        # Check network interface status
        interface = kwargs.get("interface")
        check_ip = kwargs.get("check_ip", True)

        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            if interface:
                if interface not in addrs:
                    return {
                        "success": False,
                        "condition": "network_interface",
                        "interface": interface,
                        "exists": False,
                    }

                is_up = stats.get(interface, {}).isup if interface in stats else False
                has_ip = any(
                    a.family.name == "AF_INET" for a in addrs.get(interface, [])
                )

                success = is_up and (has_ip if check_ip else True)

                return {
                    "success": success,
                    "condition": "network_interface",
                    "interface": interface,
                    "is_up": is_up,
                    "has_ip": has_ip,
                }
            else:
                # List all interfaces
                interfaces = []
                for name, addr_list in addrs.items():
                    is_up = stats.get(name, {}).isup if name in stats else False
                    has_ip = any(a.family.name == "AF_INET" for a in addr_list)
                    interfaces.append({"name": name, "is_up": is_up, "has_ip": has_ip})

                return {
                    "success": True,
                    "condition": "network_interface",
                    "interfaces": interfaces,
                }
        except Exception as e:
            return {"success": False, "condition": "network_interface", "error": str(e)}

    elif condition_type == "sse":
        # Check Server-Sent Events endpoint
        url = kwargs.get("url")
        timeout = kwargs.get("timeout", 5)

        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "text/event-stream")

            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                is_sse = "text/event-stream" in content_type

                return {
                    "success": is_sse,
                    "condition": "sse",
                    "url": url,
                    "is_sse": is_sse,
                    "content_type": content_type,
                }
        except Exception as e:
            return {"success": False, "condition": "sse", "error": str(e)}

    # ==========================================================================
    # CLOUD PROVIDERS
    # ==========================================================================

    elif condition_type == "aws_lambda":
        # Check AWS Lambda function
        function_name = kwargs.get("function_name")
        region = kwargs.get("region", "us-east-1")

        try:
            cmd = f"aws lambda get-function --function-name {function_name} --region {region} --query 'Configuration.State' --output text"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                state = result.stdout.decode().strip()
                return {
                    "success": state == "Active",
                    "condition": "aws_lambda",
                    "function_name": function_name,
                    "state": state,
                }
            return {
                "success": False,
                "condition": "aws_lambda",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "aws_lambda", "error": str(e)}

    elif condition_type == "aws_ecs":
        # Check AWS ECS service
        cluster = kwargs.get("cluster")
        service = kwargs.get("service")
        region = kwargs.get("region", "us-east-1")

        try:
            cmd = f"aws ecs describe-services --cluster {cluster} --services {service} --region {region} --query 'services[0].runningCount' --output text"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                running = int(result.stdout.decode().strip())
                return {
                    "success": running > 0,
                    "condition": "aws_ecs",
                    "cluster": cluster,
                    "service": service,
                    "running_count": running,
                }
            return {
                "success": False,
                "condition": "aws_ecs",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "aws_ecs", "error": str(e)}

    elif condition_type == "aws_rds":
        # Check AWS RDS instance
        instance_id = kwargs.get("instance_id")
        region = kwargs.get("region", "us-east-1")

        try:
            cmd = f"aws rds describe-db-instances --db-instance-identifier {instance_id} --region {region} --query 'DBInstances[0].DBInstanceStatus' --output text"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                status = result.stdout.decode().strip()
                return {
                    "success": status == "available",
                    "condition": "aws_rds",
                    "instance_id": instance_id,
                    "status": status,
                }
            return {
                "success": False,
                "condition": "aws_rds",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "aws_rds", "error": str(e)}

    elif condition_type == "aws_sqs":
        # Check AWS SQS queue
        queue_url = kwargs.get("queue_url")
        region = kwargs.get("region", "us-east-1")
        max_messages = kwargs.get("max_messages")  # Alert if queue too deep

        try:
            cmd = f"aws sqs get-queue-attributes --queue-url {queue_url} --attribute-names ApproximateNumberOfMessages --region {region} --query 'Attributes.ApproximateNumberOfMessages' --output text"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                count = int(result.stdout.decode().strip())
                success = True
                if max_messages is not None:
                    success = count <= max_messages
                return {
                    "success": success,
                    "condition": "aws_sqs",
                    "queue_url": queue_url,
                    "message_count": count,
                }
            return {
                "success": False,
                "condition": "aws_sqs",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "aws_sqs", "error": str(e)}

    elif condition_type == "aws_cloudwatch_alarm":
        # Check CloudWatch alarm state
        alarm_name = kwargs.get("alarm_name")
        region = kwargs.get("region", "us-east-1")

        try:
            cmd = f"aws cloudwatch describe-alarms --alarm-names {alarm_name} --region {region} --query 'MetricAlarms[0].StateValue' --output text"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                state = result.stdout.decode().strip()
                return {
                    "success": state == "OK",
                    "condition": "aws_cloudwatch_alarm",
                    "alarm_name": alarm_name,
                    "state": state,
                }
            return {
                "success": False,
                "condition": "aws_cloudwatch_alarm",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {
                "success": False,
                "condition": "aws_cloudwatch_alarm",
                "error": str(e),
            }

    elif condition_type == "gcp_cloud_run":
        # Check Google Cloud Run service
        service = kwargs.get("service")
        region = kwargs.get("region", "us-central1")
        project = kwargs.get("project")

        try:
            project_arg = f"--project {project}" if project else ""
            cmd = f"gcloud run services describe {service} --region {region} {project_arg} --format='value(status.conditions[0].status)'"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                status = result.stdout.decode().strip()
                return {
                    "success": status == "True",
                    "condition": "gcp_cloud_run",
                    "service": service,
                    "ready": status == "True",
                }
            return {
                "success": False,
                "condition": "gcp_cloud_run",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "gcp_cloud_run", "error": str(e)}

    elif condition_type == "gcp_cloud_sql":
        # Check Google Cloud SQL instance
        instance = kwargs.get("instance")
        project = kwargs.get("project")

        try:
            project_arg = f"--project {project}" if project else ""
            cmd = f"gcloud sql instances describe {instance} {project_arg} --format='value(state)'"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                state = result.stdout.decode().strip()
                return {
                    "success": state == "RUNNABLE",
                    "condition": "gcp_cloud_sql",
                    "instance": instance,
                    "state": state,
                }
            return {
                "success": False,
                "condition": "gcp_cloud_sql",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "gcp_cloud_sql", "error": str(e)}

    elif condition_type == "azure_app_service":
        # Check Azure App Service
        name = kwargs.get("name")
        resource_group = kwargs.get("resource_group")

        try:
            cmd = f"az webapp show --name {name} --resource-group {resource_group} --query 'state' --output tsv"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                state = result.stdout.decode().strip()
                return {
                    "success": state == "Running",
                    "condition": "azure_app_service",
                    "name": name,
                    "state": state,
                }
            return {
                "success": False,
                "condition": "azure_app_service",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "azure_app_service", "error": str(e)}

    # ==========================================================================
    # CI/CD & DEVOPS
    # ==========================================================================

    elif condition_type == "github_actions":
        # Check GitHub Actions workflow status
        repo = kwargs.get("repo")  # owner/repo
        workflow = kwargs.get("workflow")  # workflow name or ID
        branch = kwargs.get("branch", "main")

        try:
            cmd = f"gh run list --repo {repo} --workflow {workflow} --branch {branch} --limit 1 --json conclusion --jq '.[0].conclusion'"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                conclusion = result.stdout.decode().strip()
                return {
                    "success": conclusion == "success",
                    "condition": "github_actions",
                    "repo": repo,
                    "workflow": workflow,
                    "conclusion": conclusion,
                }
            return {
                "success": False,
                "condition": "github_actions",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "github_actions", "error": str(e)}

    elif condition_type == "gitlab_pipeline":
        # Check GitLab pipeline status
        project = kwargs.get("project")  # project ID or path
        ref = kwargs.get("ref", "main")

        try:
            cmd = f"glab ci status --repo {project} --ref {ref}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            success = (
                result.returncode == 0 and "passed" in result.stdout.decode().lower()
            )
            return {
                "success": success,
                "condition": "gitlab_pipeline",
                "project": project,
                "output": result.stdout.decode()[:200],
            }
        except Exception as e:
            return {"success": False, "condition": "gitlab_pipeline", "error": str(e)}

    elif condition_type == "jenkins_job":
        # Check Jenkins job status
        url = kwargs.get("url")  # Jenkins URL
        job = kwargs.get("job")
        user = kwargs.get("user")
        token = kwargs.get("token")

        try:
            api_url = f"{url}/job/{job}/lastBuild/api/json"
            req = urllib.request.Request(api_url)

            if user and token:
                import base64

                credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
                req.add_header("Authorization", f"Basic {credentials}")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                result_status = data.get("result")

                return {
                    "success": result_status == "SUCCESS",
                    "condition": "jenkins_job",
                    "job": job,
                    "result": result_status,
                    "building": data.get("building", False),
                }
        except Exception as e:
            return {"success": False, "condition": "jenkins_job", "error": str(e)}

    elif condition_type == "argocd_app":
        # Check ArgoCD application sync status
        app = kwargs.get("app")
        server = kwargs.get("server")

        try:
            server_arg = f"--server {server}" if server else ""
            cmd = f"argocd app get {app} {server_arg} -o json"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                data = json.loads(result.stdout.decode())
                sync_status = data.get("status", {}).get("sync", {}).get("status")
                health_status = data.get("status", {}).get("health", {}).get("status")

                return {
                    "success": sync_status == "Synced" and health_status == "Healthy",
                    "condition": "argocd_app",
                    "app": app,
                    "sync_status": sync_status,
                    "health_status": health_status,
                }
            return {
                "success": False,
                "condition": "argocd_app",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "argocd_app", "error": str(e)}

    elif condition_type == "helm_release":
        # Check Helm release status
        release = kwargs.get("release")
        namespace = kwargs.get("namespace", "default")

        try:
            cmd = f"helm status {release} -n {namespace} -o json"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)

            if result.returncode == 0:
                data = json.loads(result.stdout.decode())
                status = data.get("info", {}).get("status")

                return {
                    "success": status == "deployed",
                    "condition": "helm_release",
                    "release": release,
                    "status": status,
                }
            return {
                "success": False,
                "condition": "helm_release",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "helm_release", "error": str(e)}

    elif condition_type == "terraform_state":
        # Check Terraform state
        working_dir = kwargs.get("working_dir", ".")
        resource = kwargs.get("resource")

        try:
            cmd = "terraform state list"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=30, cwd=working_dir
            )

            if result.returncode == 0:
                resources = result.stdout.decode().strip().split("\n")
                if resource:
                    found = resource in resources
                    return {
                        "success": found,
                        "condition": "terraform_state",
                        "resource": resource,
                        "found": found,
                    }
                return {
                    "success": len(resources) > 0,
                    "condition": "terraform_state",
                    "resource_count": len(resources),
                }
            return {
                "success": False,
                "condition": "terraform_state",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "terraform_state", "error": str(e)}

    # ==========================================================================
    # MONITORING & OBSERVABILITY
    # ==========================================================================

    elif condition_type == "prometheus":
        # Check Prometheus metric or alert
        url = kwargs.get("url", "http://localhost:9090")
        query = kwargs.get("query")
        alert_name = kwargs.get("alert_name")

        try:
            if alert_name:
                api_url = f"{url}/api/v1/alerts"
                req = urllib.request.Request(api_url)

                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    alerts = data.get("data", {}).get("alerts", [])
                    firing = [
                        a
                        for a in alerts
                        if a.get("labels", {}).get("alertname") == alert_name
                        and a.get("state") == "firing"
                    ]

                    return {
                        "success": len(firing) == 0,  # Success if alert NOT firing
                        "condition": "prometheus",
                        "alert_name": alert_name,
                        "firing": len(firing) > 0,
                        "count": len(firing),
                    }
            elif query:
                api_url = f"{url}/api/v1/query?query={urllib.parse.quote(query)}"
                req = urllib.request.Request(api_url)

                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    results = data.get("data", {}).get("result", [])

                    return {
                        "success": len(results) > 0,
                        "condition": "prometheus",
                        "query": query,
                        "result_count": len(results),
                        "results": results[:5],
                    }
            return {
                "success": False,
                "condition": "prometheus",
                "error": "Provide query or alert_name",
            }
        except Exception as e:
            return {"success": False, "condition": "prometheus", "error": str(e)}

    elif condition_type == "grafana":
        # Check Grafana health or dashboard
        url = kwargs.get("url", "http://localhost:3000")
        api_key = kwargs.get("api_key")

        try:
            api_url = f"{url}/api/health"
            req = urllib.request.Request(api_url)
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": data.get("database") == "ok",
                    "condition": "grafana",
                    "url": url,
                    "database": data.get("database"),
                    "version": data.get("version"),
                }
        except Exception as e:
            return {"success": False, "condition": "grafana", "error": str(e)}

    elif condition_type == "jaeger":
        # Check Jaeger tracing
        url = kwargs.get("url", "http://localhost:16686")
        service = kwargs.get("service")

        try:
            if service:
                api_url = f"{url}/api/services"
            else:
                api_url = f"{url}/api/services"

            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                services = data.get("data", [])

                if service:
                    found = service in services
                    return {
                        "success": found,
                        "condition": "jaeger",
                        "service": service,
                        "found": found,
                    }
                return {
                    "success": len(services) > 0,
                    "condition": "jaeger",
                    "services": services[:10],
                    "service_count": len(services),
                }
        except Exception as e:
            return {"success": False, "condition": "jaeger", "error": str(e)}

    elif condition_type == "sentry":
        # Check Sentry project health
        url = kwargs.get("url", "https://sentry.io")
        project = kwargs.get("project")
        org = kwargs.get("org")
        token = kwargs.get("token")

        try:
            api_url = f"{url}/api/0/projects/{org}/{project}/"
            req = urllib.request.Request(api_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "sentry",
                    "project": project,
                    "status": data.get("status"),
                    "platform": data.get("platform"),
                }
        except Exception as e:
            return {"success": False, "condition": "sentry", "error": str(e)}

    # ==========================================================================
    # CACHING
    # ==========================================================================

    elif condition_type == "memcached":
        # Check Memcached
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 11211)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.send(b"stats\r\n")
            response = sock.recv(1024).decode()
            sock.send(b"quit\r\n")
            sock.close()

            return {
                "success": "STAT" in response,
                "condition": "memcached",
                "host": host,
                "port": port,
                "connected": True,
            }
        except Exception as e:
            return {"success": False, "condition": "memcached", "error": str(e)}

    elif condition_type == "varnish":
        # Check Varnish cache
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 6081)

        try:
            # Check via HTTP with X-Varnish header
            result = await verify_condition("http", url=f"http://{host}:{port}/")
            if result.get("success"):
                return {
                    "success": True,
                    "condition": "varnish",
                    "host": host,
                    "port": port,
                    "responding": True,
                }
            return {
                "success": False,
                "condition": "varnish",
                "error": "Varnish not responding",
            }
        except Exception as e:
            return {"success": False, "condition": "varnish", "error": str(e)}

    # ==========================================================================
    # MORE DATABASES
    # ==========================================================================

    elif condition_type == "cassandra":
        # Check Cassandra
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 9042)

        try:
            cmd = f"cqlsh {host} {port} -e 'DESCRIBE KEYSPACES;'"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            return {
                "success": result.returncode == 0,
                "condition": "cassandra",
                "host": host,
                "port": port,
                "connected": result.returncode == 0,
            }
        except Exception:
            # Fallback to port check
            return await verify_condition("port", host=host, port=port)

    elif condition_type == "neo4j":
        # Check Neo4j graph database
        url = kwargs.get("url", "http://localhost:7474")

        try:
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "success": response.status == 200,
                    "condition": "neo4j",
                    "url": url,
                    "connected": True,
                }
        except Exception as e:
            return {"success": False, "condition": "neo4j", "error": str(e)}

    elif condition_type == "clickhouse":
        # Check ClickHouse
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 8123)

        try:
            url = f"http://{host}:{port}/ping"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode().strip()
                return {
                    "success": body == "Ok.",
                    "condition": "clickhouse",
                    "host": host,
                    "port": port,
                    "connected": True,
                }
        except Exception as e:
            return {"success": False, "condition": "clickhouse", "error": str(e)}

    elif condition_type == "influxdb":
        # Check InfluxDB
        url = kwargs.get("url", "http://localhost:8086")

        try:
            api_url = f"{url}/health"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                status = data.get("status")

                return {
                    "success": status == "pass",
                    "condition": "influxdb",
                    "url": url,
                    "status": status,
                }
        except Exception as e:
            return {"success": False, "condition": "influxdb", "error": str(e)}

    # ==========================================================================
    # VECTOR DATABASES (AI/ML)
    # ==========================================================================

    elif condition_type == "pinecone":
        # Check Pinecone vector DB
        api_key = kwargs.get("api_key")
        environment = kwargs.get("environment")
        index = kwargs.get("index")

        try:
            url = f"https://controller.{environment}.pinecone.io/databases"
            req = urllib.request.Request(url)
            req.add_header("Api-Key", api_key)

            with urllib.request.urlopen(req, timeout=10) as response:
                indexes = json.loads(response.read().decode())

                if index:
                    found = index in indexes
                    return {
                        "success": found,
                        "condition": "pinecone",
                        "index": index,
                        "found": found,
                    }
                return {"success": True, "condition": "pinecone", "indexes": indexes}
        except Exception as e:
            return {"success": False, "condition": "pinecone", "error": str(e)}

    elif condition_type == "weaviate":
        # Check Weaviate vector DB
        url = kwargs.get("url", "http://localhost:8080")

        try:
            api_url = f"{url}/v1/.well-known/ready"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "success": response.status == 200,
                    "condition": "weaviate",
                    "url": url,
                    "ready": True,
                }
        except Exception as e:
            return {"success": False, "condition": "weaviate", "error": str(e)}

    elif condition_type == "qdrant":
        # Check Qdrant vector DB
        url = kwargs.get("url", "http://localhost:6333")

        try:
            api_url = f"{url}/healthz"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "success": response.status == 200,
                    "condition": "qdrant",
                    "url": url,
                    "healthy": True,
                }
        except Exception as e:
            return {"success": False, "condition": "qdrant", "error": str(e)}

    elif condition_type == "chromadb":
        # Check ChromaDB
        url = kwargs.get("url", "http://localhost:8000")

        try:
            api_url = f"{url}/api/v1/heartbeat"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return {
                    "success": True,
                    "condition": "chromadb",
                    "url": url,
                    "nanosecond_heartbeat": data.get("nanosecond heartbeat"),
                }
        except Exception as e:
            return {"success": False, "condition": "chromadb", "error": str(e)}

    # ==========================================================================
    # ML/AI SERVING
    # ==========================================================================

    elif condition_type == "ollama":
        # Check Ollama local LLM
        url = kwargs.get("url", "http://localhost:11434")
        model = kwargs.get("model")

        try:
            if model:
                api_url = f"{url}/api/show"
                data = json.dumps({"name": model}).encode()
                req = urllib.request.Request(api_url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
            else:
                api_url = f"{url}/api/tags"
                req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                if model:
                    return {
                        "success": True,
                        "condition": "ollama",
                        "model": model,
                        "available": True,
                    }
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "success": True,
                    "condition": "ollama",
                    "models": models,
                    "model_count": len(models),
                }
        except Exception as e:
            return {"success": False, "condition": "ollama", "error": str(e)}

    elif condition_type == "openai_api":
        # Check OpenAI API connectivity
        api_key = kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY")
        model = kwargs.get("model", "gpt-3.5-turbo")

        try:
            url = "https://api.openai.com/v1/models"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                models = [m.get("id") for m in data.get("data", [])]

                if model:
                    found = model in models
                    return {
                        "success": found,
                        "condition": "openai_api",
                        "model": model,
                        "available": found,
                    }
                return {
                    "success": True,
                    "condition": "openai_api",
                    "model_count": len(models),
                }
        except Exception as e:
            return {"success": False, "condition": "openai_api", "error": str(e)}

    elif condition_type == "huggingface":
        # Check Hugging Face Inference API
        model = kwargs.get("model")
        api_key = kwargs.get("api_key") or os.environ.get("HF_TOKEN")

        try:
            url = f"https://api-inference.huggingface.co/models/{model}"
            req = urllib.request.Request(url, method="POST")
            req.add_header("Authorization", f"Bearer {api_key}")
            data = json.dumps({"inputs": "test"}).encode()
            req.add_header("Content-Type", "application/json")

            try:
                with urllib.request.urlopen(req, data=data, timeout=30) as response:
                    return {
                        "success": True,
                        "condition": "huggingface",
                        "model": model,
                        "available": True,
                    }
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    return {
                        "success": False,
                        "condition": "huggingface",
                        "model": model,
                        "loading": True,
                        "error": "Model is loading",
                    }
                raise
        except Exception as e:
            return {"success": False, "condition": "huggingface", "error": str(e)}

    elif condition_type == "mlflow":
        # Check MLflow tracking server
        url = kwargs.get("url", "http://localhost:5000")

        try:
            api_url = f"{url}/api/2.0/mlflow/experiments/list"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "mlflow",
                    "url": url,
                    "experiment_count": len(data.get("experiments", [])),
                }
        except Exception as e:
            return {"success": False, "condition": "mlflow", "error": str(e)}

    # ==========================================================================
    # STREAMING & REAL-TIME
    # ==========================================================================

    elif condition_type == "kafka_topic":
        # Check Kafka topic exists and has messages
        topic = kwargs.get("topic")
        bootstrap_servers = kwargs.get("bootstrap_servers", "localhost:9092")

        try:
            cmd = f"kafka-topics.sh --bootstrap-server {bootstrap_servers} --describe --topic {topic}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)

            if result.returncode == 0:
                output = result.stdout.decode()
                return {
                    "success": True,
                    "condition": "kafka_topic",
                    "topic": topic,
                    "exists": True,
                    "info": output[:500],
                }
            return {
                "success": False,
                "condition": "kafka_topic",
                "error": result.stderr.decode(),
            }
        except Exception as e:
            return {"success": False, "condition": "kafka_topic", "error": str(e)}

    elif condition_type == "mqtt":
        # Check MQTT broker
        host = kwargs.get("host", "localhost")
        port = kwargs.get("port", 1883)

        try:
            port_result = await verify_condition("port", host=host, port=port)
            return {
                "success": port_result.get("success"),
                "condition": "mqtt",
                "host": host,
                "port": port,
                "connected": port_result.get("success"),
            }
        except Exception as e:
            return {"success": False, "condition": "mqtt", "error": str(e)}

    # ==========================================================================
    # API GATEWAYS & PROXIES
    # ==========================================================================

    elif condition_type == "nginx":
        # Check Nginx status
        url = kwargs.get("url", "http://localhost/nginx_status")

        try:
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode()
                active_connections = None

                for line in body.split("\n"):
                    if "Active connections" in line:
                        active_connections = int(line.split(":")[1].strip())

                return {
                    "success": True,
                    "condition": "nginx",
                    "url": url,
                    "active_connections": active_connections,
                }
        except Exception as e:
            return {"success": False, "condition": "nginx", "error": str(e)}

    elif condition_type == "traefik":
        # Check Traefik dashboard/API
        url = kwargs.get("url", "http://localhost:8080")

        try:
            api_url = f"{url}/api/overview"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "traefik",
                    "url": url,
                    "http_routers": data.get("http", {})
                    .get("routers", {})
                    .get("total", 0),
                    "http_services": data.get("http", {})
                    .get("services", {})
                    .get("total", 0),
                }
        except Exception as e:
            return {"success": False, "condition": "traefik", "error": str(e)}

    elif condition_type == "kong":
        # Check Kong API Gateway
        url = kwargs.get("url", "http://localhost:8001")

        try:
            api_url = f"{url}/status"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "kong",
                    "url": url,
                    "database_reachable": data.get("database", {}).get("reachable"),
                    "server": data.get("server", {}),
                }
        except Exception as e:
            return {"success": False, "condition": "kong", "error": str(e)}

    # ==========================================================================
    # WEBHOOKS & NOTIFICATIONS
    # ==========================================================================

    elif condition_type == "slack_webhook":
        # Check Slack webhook
        webhook_url = kwargs.get("webhook_url")

        try:
            data = json.dumps({"text": "Health check"}).encode()
            req = urllib.request.Request(webhook_url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "success": response.status == 200,
                    "condition": "slack_webhook",
                    "accessible": True,
                }
        except Exception as e:
            return {"success": False, "condition": "slack_webhook", "error": str(e)}

    elif condition_type == "discord_webhook":
        # Check Discord webhook
        webhook_url = kwargs.get("webhook_url")

        try:
            # Just check the webhook exists (GET returns webhook info)
            req = urllib.request.Request(webhook_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return {
                    "success": True,
                    "condition": "discord_webhook",
                    "name": data.get("name"),
                    "guild_id": data.get("guild_id"),
                }
        except Exception as e:
            return {"success": False, "condition": "discord_webhook", "error": str(e)}

    # ==========================================================================
    # AUTHENTICATION PROVIDERS
    # ==========================================================================

    elif condition_type == "auth0":
        # Check Auth0 tenant
        domain = kwargs.get("domain")

        try:
            url = f"https://{domain}/.well-known/openid-configuration"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "auth0",
                    "domain": domain,
                    "issuer": data.get("issuer"),
                    "authorization_endpoint": data.get("authorization_endpoint")
                    is not None,
                }
        except Exception as e:
            return {"success": False, "condition": "auth0", "error": str(e)}

    elif condition_type == "keycloak":
        # Check Keycloak
        url = kwargs.get("url", "http://localhost:8080")
        realm = kwargs.get("realm", "master")

        try:
            api_url = f"{url}/realms/{realm}/.well-known/openid-configuration"
            req = urllib.request.Request(api_url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "keycloak",
                    "url": url,
                    "realm": realm,
                    "issuer": data.get("issuer"),
                }
        except Exception as e:
            return {"success": False, "condition": "keycloak", "error": str(e)}

    elif condition_type == "oidc":
        # Check any OIDC provider
        issuer = kwargs.get("issuer")

        try:
            url = f"{issuer}/.well-known/openid-configuration"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                return {
                    "success": True,
                    "condition": "oidc",
                    "issuer": issuer,
                    "authorization_endpoint": data.get("authorization_endpoint")
                    is not None,
                    "token_endpoint": data.get("token_endpoint") is not None,
                }
        except Exception as e:
            return {"success": False, "condition": "oidc", "error": str(e)}

    # ==========================================================================
    # FEATURE FLAGS
    # ==========================================================================

    elif condition_type == "launchdarkly":
        # Check LaunchDarkly
        sdk_key = kwargs.get("sdk_key")
        flag_key = kwargs.get("flag_key")

        try:
            url = "https://app.launchdarkly.com/api/v2/flags"
            req = urllib.request.Request(url)
            req.add_header("Authorization", sdk_key)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                flags = data.get("items", [])

                if flag_key:
                    flag = next((f for f in flags if f.get("key") == flag_key), None)
                    return {
                        "success": flag is not None,
                        "condition": "launchdarkly",
                        "flag_key": flag_key,
                        "found": flag is not None,
                        "on": flag.get("on") if flag else None,
                    }
                return {
                    "success": True,
                    "condition": "launchdarkly",
                    "flag_count": len(flags),
                }
        except Exception as e:
            return {"success": False, "condition": "launchdarkly", "error": str(e)}

    # ==========================================================================
    # BUILD TOOLS
    # ==========================================================================

    elif condition_type == "webpack_dev_server":
        # Check Webpack dev server
        url = kwargs.get("url", "http://localhost:8080")

        try:
            result = await verify_condition("http", url=url)
            return {
                "success": result.get("success"),
                "condition": "webpack_dev_server",
                "url": url,
                "running": result.get("success"),
            }
        except Exception as e:
            return {
                "success": False,
                "condition": "webpack_dev_server",
                "error": str(e),
            }

    elif condition_type == "vite_dev_server":
        # Check Vite dev server
        url = kwargs.get("url", "http://localhost:5173")

        try:
            result = await verify_condition("http", url=url)
            return {
                "success": result.get("success"),
                "condition": "vite_dev_server",
                "url": url,
                "running": result.get("success"),
            }
        except Exception as e:
            return {"success": False, "condition": "vite_dev_server", "error": str(e)}

    elif condition_type == "next_dev_server":
        # Check Next.js dev server
        url = kwargs.get("url", "http://localhost:3000")

        try:
            result = await verify_condition("http", url=url)
            return {
                "success": result.get("success"),
                "condition": "next_dev_server",
                "url": url,
                "running": result.get("success"),
            }
        except Exception as e:
            return {"success": False, "condition": "next_dev_server", "error": str(e)}

    # ==========================================================================
    # PACKAGE MANAGERS / REGISTRIES
    # ==========================================================================

    elif condition_type == "pypi":
        # Check PyPI package
        package = kwargs.get("package")
        version = kwargs.get("version")

        try:
            url = f"https://pypi.org/pypi/{package}/json"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                versions = list(data.get("releases", {}).keys())

                if version:
                    found = version in versions
                    return {
                        "success": found,
                        "condition": "pypi",
                        "package": package,
                        "version": version,
                        "found": found,
                    }
                return {
                    "success": True,
                    "condition": "pypi",
                    "package": package,
                    "latest_version": data.get("info", {}).get("version"),
                    "version_count": len(versions),
                }
        except Exception as e:
            return {"success": False, "condition": "pypi", "error": str(e)}

    elif condition_type == "maven":
        # Check Maven Central
        group_id = kwargs.get("group_id")
        artifact_id = kwargs.get("artifact_id")
        version = kwargs.get("version")

        try:
            group_path = group_id.replace(".", "/")
            url = f"https://repo1.maven.org/maven2/{group_path}/{artifact_id}/maven-metadata.xml"
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode()

                if version:
                    found = f"<version>{version}</version>" in content
                    return {
                        "success": found,
                        "condition": "maven",
                        "artifact": f"{group_id}:{artifact_id}",
                        "version": version,
                        "found": found,
                    }
                return {
                    "success": True,
                    "condition": "maven",
                    "artifact": f"{group_id}:{artifact_id}",
                    "accessible": True,
                }
        except Exception as e:
            return {"success": False, "condition": "maven", "error": str(e)}

    elif condition_type == "cargo":
        # Check Cargo/crates.io
        crate = kwargs.get("crate")
        version = kwargs.get("version")

        try:
            url = f"https://crates.io/api/v1/crates/{crate}"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "NAVI-HealthCheck")

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                crate_data = data.get("crate", {})
                versions = [v.get("num") for v in data.get("versions", [])]

                if version:
                    found = version in versions
                    return {
                        "success": found,
                        "condition": "cargo",
                        "crate": crate,
                        "version": version,
                        "found": found,
                    }
                return {
                    "success": True,
                    "condition": "cargo",
                    "crate": crate,
                    "max_version": crate_data.get("max_version"),
                    "downloads": crate_data.get("downloads"),
                }
        except Exception as e:
            return {"success": False, "condition": "cargo", "error": str(e)}

    # ==========================================================================
    # PERFORMANCE THRESHOLDS
    # ==========================================================================

    elif condition_type == "response_time":
        # Check response time threshold
        url = kwargs.get("url")
        max_ms = kwargs.get("max_ms", 1000)

        try:
            start = time.time()
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=30) as response:
                elapsed_ms = (time.time() - start) * 1000

                return {
                    "success": elapsed_ms <= max_ms,
                    "condition": "response_time",
                    "url": url,
                    "response_time_ms": round(elapsed_ms, 2),
                    "max_ms": max_ms,
                    "within_threshold": elapsed_ms <= max_ms,
                }
        except Exception as e:
            return {"success": False, "condition": "response_time", "error": str(e)}

    elif condition_type == "error_rate":
        # Check error rate (requires multiple requests)
        url = kwargs.get("url")
        requests_count = kwargs.get("requests", 10)
        max_error_percent = kwargs.get("max_error_percent", 5)

        try:
            errors = 0
            for _ in range(requests_count):
                try:
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status >= 400:
                            errors += 1
                except Exception:
                    errors += 1

            error_rate = (errors / requests_count) * 100

            return {
                "success": error_rate <= max_error_percent,
                "condition": "error_rate",
                "url": url,
                "error_rate_percent": round(error_rate, 2),
                "max_error_percent": max_error_percent,
                "requests": requests_count,
                "errors": errors,
            }
        except Exception as e:
            return {"success": False, "condition": "error_rate", "error": str(e)}

    # ==========================================================================
    # SECURITY CHECKS
    # ==========================================================================

    elif condition_type == "security_headers":
        # Check security headers
        url = kwargs.get("url")
        required_headers = kwargs.get(
            "required_headers",
            ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"],
        )

        try:
            req = urllib.request.Request(url)

            with urllib.request.urlopen(req, timeout=10) as response:
                headers = dict(response.headers)
                missing = [h for h in required_headers if h not in headers]

                return {
                    "success": len(missing) == 0,
                    "condition": "security_headers",
                    "url": url,
                    "missing_headers": missing,
                    "present_headers": [h for h in required_headers if h in headers],
                }
        except Exception as e:
            return {"success": False, "condition": "security_headers", "error": str(e)}

    elif condition_type == "cors":
        # Check CORS configuration
        url = kwargs.get("url")
        origin = kwargs.get("origin", "http://localhost:3000")

        try:
            req = urllib.request.Request(url, method="OPTIONS")
            req.add_header("Origin", origin)
            req.add_header("Access-Control-Request-Method", "GET")

            with urllib.request.urlopen(req, timeout=10) as response:
                allow_origin = response.headers.get("Access-Control-Allow-Origin")
                allow_methods = response.headers.get("Access-Control-Allow-Methods")

                allowed = allow_origin == "*" or allow_origin == origin

                return {
                    "success": allowed,
                    "condition": "cors",
                    "url": url,
                    "origin": origin,
                    "allowed": allowed,
                    "allow_origin": allow_origin,
                    "allow_methods": allow_methods,
                }
        except Exception as e:
            return {"success": False, "condition": "cors", "error": str(e)}

    else:
        return {
            "success": False,
            "error": f"Unknown condition type: {condition_type}",
            "supported_types": [
                # Network & Connectivity
                "http",
                "port",
                "tcp",
                "websocket",
                "ssl",
                "dns",
                "ssh",
                "ftp",
                "smtp",
                "ldap",
                "mqtt",
                # Files & System
                "file_exists",
                "file_contains",
                "process_running",
                "command_succeeds",
                "disk_space",
                "memory_available",
                "cpu_usage",
                "env_var",
                "cron_job",
                # Databases
                "database",
                "elasticsearch",
                "cassandra",
                "neo4j",
                "clickhouse",
                "influxdb",
                # Vector DBs
                "pinecone",
                "weaviate",
                "qdrant",
                "chromadb",
                # Containers & Orchestration
                "docker",
                "docker_compose",
                "kubernetes",
                "helm_release",
                "argocd_app",
                # Cloud Providers
                "aws_lambda",
                "aws_ecs",
                "aws_rds",
                "aws_sqs",
                "aws_cloudwatch_alarm",
                "gcp_cloud_run",
                "gcp_cloud_sql",
                "azure_app_service",
                # CI/CD
                "github_actions",
                "gitlab_pipeline",
                "jenkins_job",
                "terraform_state",
                # Monitoring
                "prometheus",
                "grafana",
                "jaeger",
                "sentry",
                # Caching
                "memcached",
                "varnish",
                # Message Queues
                "queue",
                "kafka_topic",
                # APIs & Protocols
                "graphql",
                "grpc",
                "sse",
                "api_response",
                "json_schema",
                "url_accessible",
                # ML/AI
                "ollama",
                "openai_api",
                "huggingface",
                "mlflow",
                # API Gateways
                "nginx",
                "traefik",
                "kong",
                # Webhooks
                "slack_webhook",
                "discord_webhook",
                # Auth Providers
                "auth0",
                "keycloak",
                "oidc",
                "launchdarkly",
                # Storage & Registries
                "s3",
                "npm_registry",
                "docker_registry",
                "git_remote",
                "pypi",
                "maven",
                "cargo",
                # Services
                "systemd_service",
                "launchd_service",
                "network_interface",
                # Dev Servers
                "webpack_dev_server",
                "vite_dev_server",
                "next_dev_server",
                # Performance
                "response_time",
                "error_rate",
                # Security
                "security_headers",
                "cors",
                # Aggregation
                "health_aggregate",
            ],
        }


async def wait_for_condition(
    condition_type: str,
    timeout: int = 30,
    interval: float = 1.0,
    backoff: str = "linear",  # "linear", "exponential", "none"
    max_interval: float = 10.0,
    **kwargs,
) -> Dict[str, Any]:
    """
    Wait for a condition to become true with configurable retry strategy.

    Args:
        condition_type: Type of condition to check
        timeout: Maximum seconds to wait
        interval: Initial interval between checks
        backoff: Retry strategy - "linear", "exponential", or "none"
        max_interval: Maximum interval for backoff
        **kwargs: Arguments passed to verify_condition
    """
    start_time = time.time()
    attempts = 0
    current_interval = interval
    last_result = None

    while time.time() - start_time < timeout:
        attempts += 1
        result = await verify_condition(condition_type, **kwargs)
        last_result = result

        if result.get("success"):
            return {
                "success": True,
                "condition": condition_type,
                "attempts": attempts,
                "elapsed_seconds": time.time() - start_time,
                "result": result,
            }

        # Calculate next interval based on backoff strategy
        if backoff == "exponential":
            current_interval = min(current_interval * 2, max_interval)
        elif backoff == "linear":
            current_interval = min(current_interval + 0.5, max_interval)
        # "none" keeps the same interval

        await asyncio.sleep(current_interval)

    return {
        "success": False,
        "condition": condition_type,
        "error": f"Timeout after {timeout} seconds",
        "attempts": attempts,
        "last_result": last_result,
    }


# =============================================================================
# Environment Management
# =============================================================================


async def create_environment(
    env_type: str, version: Optional[str] = None, working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create/activate a development environment.

    Args:
        env_type: "node", "python", "ruby", "java", etc.
        version: Specific version to use
        working_dir: Directory for environment (for Python venv)

    Returns:
        Environment variables dict to pass to run commands
    """
    env = os.environ.copy()

    if env_type == "node":
        # Try multiple version managers
        version = version or "default"

        # Check for nvm
        nvm_dir = os.environ.get("NVM_DIR", os.path.expanduser("~/.nvm"))
        if os.path.exists(nvm_dir):
            # Get node path from nvm
            result = subprocess.run(
                f'source "{nvm_dir}/nvm.sh" && nvm which {version}',
                shell=True,
                capture_output=True,
                executable="/bin/bash",
            )
            if result.returncode == 0:
                node_path = result.stdout.decode().strip()
                node_bin = os.path.dirname(node_path)
                env["PATH"] = f"{node_bin}:{env.get('PATH', '')}"
                return {
                    "success": True,
                    "env_type": "node",
                    "version_manager": "nvm",
                    "version": version,
                    "env": env,
                    "shell_prefix": f'source "{nvm_dir}/nvm.sh" && nvm use {version} && ',
                }

        # Check for fnm
        fnm_path = os.path.expanduser("~/.fnm")
        if os.path.exists(fnm_path):
            return {
                "success": True,
                "env_type": "node",
                "version_manager": "fnm",
                "shell_prefix": f'eval "$(fnm env)" && fnm use {version} && ',
            }

        # Check for volta
        volta_home = os.environ.get("VOLTA_HOME", os.path.expanduser("~/.volta"))
        if os.path.exists(volta_home):
            env["VOLTA_HOME"] = volta_home
            env["PATH"] = f"{volta_home}/bin:{env.get('PATH', '')}"
            return {
                "success": True,
                "env_type": "node",
                "version_manager": "volta",
                "env": env,
            }

        return {
            "success": False,
            "error": "No Node version manager found (nvm, fnm, volta)",
        }

    elif env_type == "python":
        version = version or "3"

        # Check for pyenv
        pyenv_root = os.environ.get("PYENV_ROOT", os.path.expanduser("~/.pyenv"))
        if os.path.exists(pyenv_root):
            env["PYENV_ROOT"] = pyenv_root
            env["PATH"] = f"{pyenv_root}/bin:{pyenv_root}/shims:{env.get('PATH', '')}"
            return {
                "success": True,
                "env_type": "python",
                "version_manager": "pyenv",
                "env": env,
                "shell_prefix": f'eval "$(pyenv init -)" && pyenv shell {version} && ',
            }

        # Create virtualenv if working_dir specified
        if working_dir:
            venv_path = os.path.join(working_dir, "venv")
            if not os.path.exists(venv_path):
                result = subprocess.run(
                    f"python{version} -m venv {venv_path}",
                    shell=True,
                    capture_output=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to create venv: {result.stderr.decode()}",
                    }

            # Add venv to path
            venv_bin = os.path.join(venv_path, "bin")
            env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = venv_path

            return {
                "success": True,
                "env_type": "python",
                "version_manager": "venv",
                "venv_path": venv_path,
                "env": env,
                "shell_prefix": f"source {venv_bin}/activate && ",
            }

        return {"success": True, "env_type": "python", "env": env}

    elif env_type == "ruby":
        # Check for rbenv
        rbenv_root = os.path.expanduser("~/.rbenv")
        if os.path.exists(rbenv_root):
            env["PATH"] = f"{rbenv_root}/bin:{rbenv_root}/shims:{env.get('PATH', '')}"
            return {
                "success": True,
                "env_type": "ruby",
                "version_manager": "rbenv",
                "env": env,
                "shell_prefix": 'eval "$(rbenv init -)" && ',
            }

        # Check for rvm
        rvm_path = os.path.expanduser("~/.rvm")
        if os.path.exists(rvm_path):
            return {
                "success": True,
                "env_type": "ruby",
                "version_manager": "rvm",
                "shell_prefix": f'source "{rvm_path}/scripts/rvm" && rvm use {version or "default"} && ',
            }

        return {"success": False, "error": "No Ruby version manager found (rbenv, rvm)"}

    elif env_type == "java":
        # Check for SDKMAN
        sdkman_dir = os.environ.get("SDKMAN_DIR", os.path.expanduser("~/.sdkman"))
        if os.path.exists(sdkman_dir):
            return {
                "success": True,
                "env_type": "java",
                "version_manager": "sdkman",
                "shell_prefix": f'source "{sdkman_dir}/bin/sdkman-init.sh" && sdk use java {version or ""} && ',
            }

        # Check for jenv
        jenv_root = os.path.expanduser("~/.jenv")
        if os.path.exists(jenv_root):
            env["PATH"] = f"{jenv_root}/bin:{env.get('PATH', '')}"
            return {
                "success": True,
                "env_type": "java",
                "version_manager": "jenv",
                "env": env,
                "shell_prefix": 'eval "$(jenv init -)" && ',
            }

        return {
            "success": False,
            "error": "No Java version manager found (sdkman, jenv)",
        }

    else:
        return {
            "success": False,
            "error": f"Unsupported environment type: {env_type}",
            "supported_types": ["node", "python", "ruby", "java"],
        }


async def run_with_environment(
    command: str,
    working_dir: str,
    env_type: str,
    version: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Run a command with a specific environment activated.

    This handles the shell state issue where version managers need to be
    sourced in the same shell as the command.
    """
    env_result = await create_environment(env_type, version, working_dir)

    if not env_result.get("success"):
        return env_result

    shell_prefix = env_result.get("shell_prefix", "")
    env = env_result.get("env", os.environ.copy())

    full_command = f"{shell_prefix}{command}"

    try:
        process = await asyncio.create_subprocess_shell(
            full_command,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            executable="/bin/bash",
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

        return {
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "stdout": mask_secrets(stdout.decode("utf-8", errors="replace")),
            "stderr": mask_secrets(stderr.decode("utf-8", errors="replace")),
            "command": command,
            "environment": env_type,
            "version": version,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# OAuth / Browser Flow Handling
# =============================================================================


async def run_oauth_flow(
    command: str,
    working_dir: str,
    callback_port: int = 0,
    timeout: int = 300,
    success_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run a command that triggers OAuth/browser authentication.

    This handles CLIs like:
    - vercel login
    - gh auth login
    - gcloud auth login
    - firebase login

    Args:
        command: The CLI command
        working_dir: Working directory
        callback_port: Port for OAuth callback (0 = auto)
        timeout: Max seconds to wait for auth
        success_patterns: Regex patterns indicating successful auth
    """
    success_patterns = success_patterns or [
        r"(?i)success|logged in|authenticated|authorized",
        r"(?i)welcome|hello",
        r"(?i)token saved|credentials saved",
    ]

    pm = ProcessManager()

    # Start the auth command
    result = await pm.start_background(
        command=command, working_dir=working_dir, tags=["oauth-flow"]
    )

    if not result.get("success"):
        return result

    process_id = result["process_id"]

    # Wait for success pattern in output
    combined_pattern = "|".join(f"({p})" for p in success_patterns)

    auth_result = await pm.wait_for_log_pattern(
        process_id=process_id, pattern=combined_pattern, timeout=timeout
    )

    if auth_result.get("success"):
        # Collect any remaining output
        await asyncio.sleep(1)
        output = await pm.get_output(process_id, lines=100)

        return {
            "success": True,
            "message": "Authentication successful",
            "matched_line": auth_result.get("matched_line"),
            "output": output.get("output", ""),
        }
    else:
        # Get output for debugging
        output = await pm.get_output(process_id, lines=50)

        return {
            "success": False,
            "error": "Authentication did not complete",
            "output": output.get("output", ""),
            "hint": "Check if browser opened. You may need to complete auth manually.",
        }


# =============================================================================
# Tool Definitions for LLM
# =============================================================================

PROCESS_TOOLS = [
    {
        "name": "run_background",
        "description": "Start a long-running command in background. Returns immediately with process_id. Use for dev servers, watchers, docker, anything that runs indefinitely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"},
                "env": {"type": "object", "description": "Environment variables"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for grouping",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "run_interactive",
        "description": "Run a command that requires stdin input (npm init, git rebase -i, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "expect": {
                                "type": "string",
                                "description": "Pattern to wait for",
                            },
                            "send": {
                                "type": "string",
                                "description": "Response to send",
                            },
                        },
                    },
                    "description": "Expect/send pairs for automation",
                },
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command", "inputs"],
        },
    },
    {
        "name": "run_parallel",
        "description": "Run multiple commands in parallel, wait for all to complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "name": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
                "timeout": {"type": "integer", "default": 300},
                "fail_fast": {"type": "boolean", "default": False},
            },
            "required": ["commands"],
        },
    },
    {
        "name": "check_process",
        "description": "Check status and recent output of a background process.",
        "input_schema": {
            "type": "object",
            "properties": {"process_id": {"type": "string"}},
            "required": ["process_id"],
        },
    },
    {
        "name": "get_process_output",
        "description": "Get recent output/logs from a background process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string"},
                "lines": {"type": "integer", "default": 50},
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "wait_for_log_pattern",
        "description": "Wait for a specific pattern in process output. Use when HTTP check isn't the right signal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string"},
                "pattern": {"type": "string", "description": "Regex pattern to match"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["process_id", "pattern"],
        },
    },
    {
        "name": "kill_process",
        "description": "Stop a background process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["process_id"],
        },
    },
    {
        "name": "cleanup_session",
        "description": "Kill all managed processes and clean up. Use when done or on error.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only clean processes with these tags",
                },
                "force": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "list_processes",
        "description": "List all managed background processes.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "start_service_chain",
        "description": "Start multiple dependent services in order with health checks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "command": {"type": "string"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "health_check": {"type": "object"},
                            "startup_timeout": {"type": "integer", "default": 30},
                        },
                        "required": ["name", "command"],
                    },
                }
            },
            "required": ["services"],
        },
    },
    {
        "name": "check_resources",
        "description": "Check CPU, memory, disk usage of a process or system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {
                    "type": "string",
                    "description": "Check specific process (optional)",
                },
                "pid": {
                    "type": "integer",
                    "description": "Direct PID to check (optional)",
                },
            },
        },
    },
    {
        "name": "verify_condition",
        "description": "Check if a condition is true. Types: http, port, tcp, file_exists, file_contains, process_running, command_succeeds, database, websocket, ssl, dns, health_aggregate",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_type": {
                    "type": "string",
                    "enum": [
                        "http",
                        "port",
                        "tcp",
                        "file_exists",
                        "file_contains",
                        "process_running",
                        "command_succeeds",
                        "database",
                        "websocket",
                        "ssl",
                        "dns",
                        "health_aggregate",
                    ],
                },
                "url": {"type": "string"},
                "port": {"type": "integer"},
                "host": {"type": "string"},
                "path": {"type": "string"},
                "pattern": {"type": "string"},
                "name": {"type": "string"},
                "command": {"type": "string"},
                "db_type": {"type": "string"},
                "database": {"type": "string"},
                "user": {"type": "string"},
                "password": {"type": "string"},
                "hostname": {"type": "string"},
                "checks": {
                    "type": "array",
                    "description": "For health_aggregate: list of checks",
                },
            },
            "required": ["condition_type"],
        },
    },
    {
        "name": "wait_for_condition",
        "description": "Wait for a condition to become true with retry and backoff.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_type": {"type": "string"},
                "timeout": {"type": "integer", "default": 30},
                "interval": {"type": "number", "default": 1.0},
                "backoff": {
                    "type": "string",
                    "enum": ["none", "linear", "exponential"],
                    "default": "linear",
                },
                "url": {"type": "string"},
                "port": {"type": "integer"},
                "path": {"type": "string"},
                "pattern": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["condition_type"],
        },
    },
    {
        "name": "create_environment",
        "description": "Set up a development environment (node, python, ruby, java) with version managers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "env_type": {
                    "type": "string",
                    "enum": ["node", "python", "ruby", "java"],
                },
                "version": {
                    "type": "string",
                    "description": "Version to use (e.g., '18', '3.11')",
                },
            },
            "required": ["env_type"],
        },
    },
    {
        "name": "run_with_environment",
        "description": "Run a command with a specific environment (handles version manager sourcing).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "env_type": {
                    "type": "string",
                    "enum": ["node", "python", "ruby", "java"],
                },
                "version": {"type": "string"},
                "timeout": {"type": "integer", "default": 120},
            },
            "required": ["command", "env_type"],
        },
    },
    {
        "name": "run_oauth_flow",
        "description": "Run a command that triggers browser OAuth (vercel login, gh auth, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 300},
            },
            "required": ["command"],
        },
    },
]
