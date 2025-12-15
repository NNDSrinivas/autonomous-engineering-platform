# backend/api/routers/logs_websocket.py

"""
WebSocket endpoint for live log streaming.

Provides real-time log tailing from Docker containers, Kubernetes pods,
or local log files with filtering by service, level, and search terms.
"""

import asyncio
import logging
import subprocess
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogFilter(BaseModel):
    """Filter criteria for log streaming."""
    service: Optional[str] = None
    level: Optional[str] = None
    search: Optional[str] = None
    environment: str = "local"


@router.websocket("/stream")
async def stream_logs(
    websocket: WebSocket,
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    environment: str = Query("local"),
):
    """
    WebSocket endpoint for live log streaming.
    
    Query params:
        service: Service name to tail logs for
        level: Filter by log level (error, warn, info, debug)
        search: Search term to filter log lines
        environment: Target environment (local, staging, prod, k8s)
    
    Example usage:
        ws://localhost:8787/api/logs/stream?service=backend&level=error
    """
    await websocket.accept()
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to log stream for service: {service or 'all'}",
            "filters": {
                "service": service,
                "level": level,
                "search": search,
                "environment": environment,
            }
        })
        
        # Strategy 1: Try Docker container logs
        if environment == "local":
            await _stream_docker_logs(websocket, service, level, search)
        
        # Strategy 2: Try Kubernetes pod logs
        elif environment in ("staging", "prod", "production", "k8s", "kubernetes"):
            await _stream_k8s_logs(websocket, service, level, search)
        
        # Strategy 3: File-based logs
        else:
            await _stream_file_logs(websocket, service, level, search)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for service: {service}")
    except Exception as e:
        logger.error(f"Error in log streaming: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Log streaming error: {str(e)}"
        })
    finally:
        await websocket.close()


async def _stream_docker_logs(
    websocket: WebSocket,
    service: Optional[str],
    level: Optional[str],
    search: Optional[str]
):
    """Stream logs from Docker containers."""
    try:
        # Find matching containers
        ps_result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if ps_result.returncode != 0:
            await websocket.send_json({
                "type": "error",
                "message": "Docker is not running or not installed"
            })
            return
        
        running_containers = [c.strip() for c in ps_result.stdout.strip().split("\n") if c.strip()]
        
        if service:
            matching_containers = [c for c in running_containers if service.lower() in c.lower()]
            if not matching_containers:
                await websocket.send_json({
                    "type": "error",
                    "message": f"No containers found matching '{service}'. Available: {', '.join(running_containers)}"
                })
                return
            container = matching_containers[0]
        else:
            if not running_containers:
                await websocket.send_json({
                    "type": "error",
                    "message": "No running containers found"
                })
                return
            container = running_containers[0]
        
        # Start streaming logs with follow
        process = subprocess.Popen(
            ["docker", "logs", "-f", "--tail", "10", container],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        await websocket.send_json({
            "type": "stream_started",
            "message": f"Streaming logs from container: {container}"
        })
        
        # Stream logs line by line
        try:
            while True:
                line = process.stdout.readline()
                
                if not line:
                    break
                
                # Apply filters
                if level and level.upper() not in line.upper():
                    continue
                
                if search and search.lower() not in line.lower():
                    continue
                
                # Send log line
                await websocket.send_json({
                    "type": "log",
                    "source": "docker",
                    "container": container,
                    "line": line.rstrip(),
                })
                
                # Check if client disconnected
                await asyncio.sleep(0)
        
        finally:
            process.terminate()
            process.wait(timeout=5)
    
    except Exception as e:
        logger.error(f"Error streaming Docker logs: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Docker log streaming failed: {str(e)}"
        })


async def _stream_k8s_logs(
    websocket: WebSocket,
    service: Optional[str],
    level: Optional[str],
    search: Optional[str]
):
    """Stream logs from Kubernetes pods."""
    try:
        # Find matching pods
        pods_result = subprocess.run(
            ["kubectl", "get", "pods", "-o", "name"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if pods_result.returncode != 0:
            await websocket.send_json({
                "type": "error",
                "message": "kubectl not available or not configured"
            })
            return
        
        all_pods = [p.strip() for p in pods_result.stdout.strip().split("\n") if p.strip()]
        
        if service:
            matching_pods = [p for p in all_pods if service.lower() in p.lower()]
            if not matching_pods:
                await websocket.send_json({
                    "type": "error",
                    "message": f"No pods found matching '{service}'. Available: {', '.join(all_pods)}"
                })
                return
            pod = matching_pods[0]
        else:
            if not all_pods:
                await websocket.send_json({
                    "type": "error",
                    "message": "No pods found"
                })
                return
            pod = all_pods[0]
        
        # Start streaming logs with follow
        process = subprocess.Popen(
            ["kubectl", "logs", "-f", "--tail", "10", pod],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        await websocket.send_json({
            "type": "stream_started",
            "message": f"Streaming logs from pod: {pod}"
        })
        
        # Stream logs line by line
        try:
            while True:
                line = process.stdout.readline()
                
                if not line:
                    break
                
                # Apply filters
                if level and level.upper() not in line.upper():
                    continue
                
                if search and search.lower() not in line.lower():
                    continue
                
                # Send log line
                await websocket.send_json({
                    "type": "log",
                    "source": "kubernetes",
                    "pod": pod,
                    "line": line.rstrip(),
                })
                
                # Check if client disconnected
                await asyncio.sleep(0)
        
        finally:
            process.terminate()
            process.wait(timeout=5)
    
    except Exception as e:
        logger.error(f"Error streaming Kubernetes logs: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Kubernetes log streaming failed: {str(e)}"
        })


async def _stream_file_logs(
    websocket: WebSocket,
    service: Optional[str],
    level: Optional[str],
    search: Optional[str]
):
    """Stream logs from local log files."""
    try:
        # Find log files (simplified implementation)
        workspace_root = Path.cwd()
        log_dirs = [
            workspace_root / "logs",
            workspace_root / "backend" / "logs",
        ]
        
        log_files = []
        for log_dir in log_dirs:
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    if not service or service in str(log_file):
                        log_files.append(log_file)
        
        if not log_files:
            await websocket.send_json({
                "type": "error",
                "message": f"No log files found for service: {service or 'all'}"
            })
            return
        
        log_file = sorted(log_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
        
        # Tail log file
        process = subprocess.Popen(
            ["tail", "-f", "-n", "10", str(log_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        await websocket.send_json({
            "type": "stream_started",
            "message": f"Streaming logs from file: {log_file.name}"
        })
        
        # Stream logs line by line
        try:
            while True:
                line = process.stdout.readline()
                
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                
                # Apply filters
                if level and level.upper() not in line.upper():
                    continue
                
                if search and search.lower() not in line.lower():
                    continue
                
                # Send log line
                await websocket.send_json({
                    "type": "log",
                    "source": "file",
                    "file": str(log_file),
                    "line": line.rstrip(),
                })
                
                # Check if client disconnected
                await asyncio.sleep(0)
        
        finally:
            process.terminate()
            process.wait(timeout=5)
    
    except Exception as e:
        logger.error(f"Error streaming file logs: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"File log streaming failed: {str(e)}"
        })
