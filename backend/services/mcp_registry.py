from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

import httpx
import ipaddress
from urllib.parse import urlparse
from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from backend.core.crypto import decrypt_token, encrypt_token
from backend.core.config import settings
from backend.models.mcp_server import McpServer

logger = logging.getLogger(__name__)

_IN_MEMORY_SERVERS: Dict[str, Dict[int, Dict[str, Any]]] = {}
_IN_MEMORY_ID = -1
_FALLBACK_WARNING = (
    "MCP servers table is unavailable. Falling back to in-memory storage. "
    "Run Alembic migrations and ensure DATABASE_URL/sqlalchemy_url is configured."
)


def _warn_once() -> None:
    if not getattr(_warn_once, "_did_warn", False):
        logger.warning(_FALLBACK_WARNING)
        _warn_once._did_warn = True  # type: ignore[attr-defined]


def _table_exists(db: Session, table_name: str) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table(table_name)
    except Exception:
        return False


def _bucket_key(org_id: Optional[str], user_id: Optional[str]) -> str:
    if org_id:
        return f"org:{org_id}"
    return f"user:{user_id or 'unknown'}"


def _ensure_bucket(
    org_id: Optional[str], user_id: Optional[str]
) -> Dict[int, Dict[str, Any]]:
    key = _bucket_key(org_id, user_id)
    if key not in _IN_MEMORY_SERVERS:
        _IN_MEMORY_SERVERS[key] = {}
    return _IN_MEMORY_SERVERS[key]


def _normalize_host(hostname: str) -> str:
    return hostname.strip().lower().rstrip(".")


def _is_private_host(hostname: str) -> bool:
    host = _normalize_host(hostname)
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        )
    except ValueError:
        return False


def _validate_server_url(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Server URL must include protocol and host")
    scheme = parsed.scheme.lower()
    if settings.mcp_require_https and scheme != "https":
        raise ValueError("External MCP servers must use HTTPS")
    hostname = parsed.hostname or ""
    if settings.mcp_block_private_networks and _is_private_host(hostname):
        raise ValueError("Private or localhost MCP endpoints are not allowed")
    allowed_hosts: Sequence[str] = settings.mcp_allowed_hosts or []
    if allowed_hosts:
        normalized = _normalize_host(hostname)
        allowed = {_normalize_host(h) for h in allowed_hosts}
        if normalized not in allowed:
            raise ValueError("MCP server host is not in the allowed list")


def _build_config(
    auth_type: str,
    header_name: Optional[str],
    headers: Optional[Dict[str, str]],
    username: Optional[str],
) -> Dict[str, Any]:
    return {
        "auth_header_name": header_name,
        "headers": headers or {},
        "username": username,
    }


def _build_secrets(
    token: Optional[str],
    password: Optional[str],
) -> Dict[str, str]:
    secrets: Dict[str, str] = {}
    if token:
        secrets["token"] = token
    if password:
        secrets["password"] = password
    return secrets


def _serialize_server(row: McpServer, include_config: bool = True) -> Dict[str, Any]:
    config = {}
    if include_config and row.config_json:
        try:
            config = json.loads(row.config_json)
        except Exception:
            config = {}
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "transport": row.transport,
        "auth_type": row.auth_type,
        "enabled": row.enabled,
        "status": row.status,
        "tool_count": row.tool_count,
        "last_checked_at": row.last_checked_at.isoformat()
        if row.last_checked_at
        else None,
        "last_error": row.last_error,
        "config": config,
        "source": "external",
        "scope": "org" if row.org_id else "user",
    }


def _decrypt_secrets(row: McpServer) -> Dict[str, Any]:
    if not row.secret_json:
        return {}
    try:
        decoded = json.loads(row.secret_json.decode("utf-8"))
    except Exception:
        return {}
    secrets: Dict[str, Any] = {}
    for k, v in decoded.items():
        try:
            secrets[k] = decrypt_token(v)
        except Exception:
            secrets[k] = None
    return secrets


def list_servers(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    scope: str = "auto",
) -> List[Dict[str, Any]]:
    """
    scope:
      - "org": org-managed only
      - "user": user-managed only
      - "all": both
      - "auto": org if org_id present, else user
    """
    effective_scope = scope
    if scope == "auto":
        effective_scope = "org" if org_id else "user"

    if db and _table_exists(db, "mcp_servers"):
        query = db.query(McpServer)
        filters = []
        if effective_scope in {"org", "all"} and org_id:
            filters.append(McpServer.org_id == str(org_id))
        if effective_scope in {"user", "all"} and user_id:
            filters.append(
                (McpServer.user_id == str(user_id)) & (McpServer.org_id.is_(None))
            )
        if not filters:
            return []
        query = query.filter(or_(*filters))
        rows = query.order_by(McpServer.created_at.desc()).all()
        return [_serialize_server(row) for row in rows]

    _warn_once()
    buckets: List[Dict[int, Dict[str, Any]]] = []
    if effective_scope in {"org", "all"} and org_id:
        buckets.append(_ensure_bucket(org_id, None))
    if effective_scope in {"user", "all"} and user_id:
        buckets.append(_ensure_bucket(None, user_id))
    if not buckets:
        return []
    items: List[Dict[str, Any]] = []
    for bucket in buckets:
        for item in bucket.values():
            if item.get("scope") and effective_scope in {"org", "user"}:
                if item.get("scope") != effective_scope:
                    continue
            items.append({k: v for k, v in item.items() if k != "secrets"})
    return items


def get_server(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    server_id: int,
    scope: str = "auto",
) -> Optional[Dict[str, Any]]:
    if db and _table_exists(db, "mcp_servers"):
        query = db.query(McpServer).filter(McpServer.id == server_id)
        if scope == "org" and org_id:
            query = query.filter(McpServer.org_id == str(org_id))
        elif scope == "user" and user_id:
            query = query.filter(
                McpServer.user_id == str(user_id), McpServer.org_id.is_(None)
            )
        else:
            if org_id and user_id:
                query = query.filter(
                    (McpServer.org_id == str(org_id))
                    | (
                        (McpServer.user_id == str(user_id))
                        & (McpServer.org_id.is_(None))
                    )
                )
            elif org_id:
                query = query.filter(McpServer.org_id == str(org_id))
            elif user_id:
                query = query.filter(
                    McpServer.user_id == str(user_id), McpServer.org_id.is_(None)
                )
        row = query.first()
        if not row:
            return None
        data = _serialize_server(row)
        data["secrets"] = _decrypt_secrets(row)
        return data
    _warn_once()
    if scope == "org" and org_id:
        return _ensure_bucket(org_id, None).get(server_id)
    if scope == "user" and user_id:
        return _ensure_bucket(None, user_id).get(server_id)
    if org_id:
        server = _ensure_bucket(org_id, None).get(server_id)
        if server:
            return server
    if user_id:
        return _ensure_bucket(None, user_id).get(server_id)
    return None


def create_server(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    name: str,
    url: str,
    transport: str,
    auth_type: str,
    header_name: Optional[str],
    headers: Optional[Dict[str, str]],
    username: Optional[str],
    token: Optional[str],
    password: Optional[str],
    enabled: bool = True,
) -> Dict[str, Any]:
    _validate_server_url(url)
    config = _build_config(auth_type, header_name, headers, username)
    secrets = _build_secrets(token, password)
    if db and _table_exists(db, "mcp_servers"):
        secret_blob = (
            json.dumps({k: encrypt_token(v) for k, v in secrets.items()}).encode(
                "utf-8"
            )
            if secrets
            else None
        )
        row = McpServer(
            name=name,
            url=url,
            transport=transport,
            auth_type=auth_type,
            config_json=json.dumps(config),
            secret_json=secret_blob,
            enabled=enabled,
            status="unknown",
            user_id=str(user_id) if user_id else None,
            org_id=str(org_id) if org_id else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_server(row)
    _warn_once()
    global _IN_MEMORY_ID
    bucket = _ensure_bucket(org_id, user_id)
    server_id = _IN_MEMORY_ID
    _IN_MEMORY_ID -= 1
    bucket[server_id] = {
        "id": server_id,
        "name": name,
        "url": url,
        "transport": transport,
        "auth_type": auth_type,
        "enabled": enabled,
        "status": "unknown",
        "tool_count": None,
        "last_checked_at": None,
        "last_error": None,
        "config": config,
        "source": "external",
        "scope": "org" if org_id else "user",
        "secrets": secrets,
    }
    return bucket[server_id]


def update_server(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    server_id: int,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if "url" in updates and updates["url"]:
        _validate_server_url(str(updates["url"]))
    if db and _table_exists(db, "mcp_servers"):
        query = db.query(McpServer).filter(McpServer.id == server_id)
        if org_id:
            query = query.filter(McpServer.org_id == str(org_id))
        elif user_id:
            query = query.filter(McpServer.user_id == str(user_id))
        row = query.first()
        if not row:
            return None

        config = {}
        if row.config_json:
            try:
                config = json.loads(row.config_json)
            except Exception:
                config = {}

        if "name" in updates:
            row.name = updates["name"]
        if "url" in updates:
            row.url = updates["url"]
        if "transport" in updates:
            row.transport = updates["transport"]
        if "auth_type" in updates:
            row.auth_type = updates["auth_type"]
        if "enabled" in updates:
            row.enabled = bool(updates["enabled"])
        if "auth_header_name" in updates:
            config["auth_header_name"] = updates["auth_header_name"]
        if "headers" in updates and isinstance(updates["headers"], dict):
            config["headers"] = updates["headers"]
        if "username" in updates:
            config["username"] = updates["username"]

        if updates.get("clear_secrets"):
            row.secret_json = None
        if "secrets" in updates:
            secret_blob = json.dumps(
                {k: encrypt_token(v) for k, v in updates["secrets"].items() if v}
            ).encode("utf-8")
            row.secret_json = secret_blob

        row.config_json = json.dumps(config)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_server(row)

    _warn_once()
    bucket = _ensure_bucket(org_id, user_id)
    existing = bucket.get(server_id)
    if not existing:
        return None
    existing.update(
        {k: v for k, v in updates.items() if k not in {"secrets", "clear_secrets"}}
    )
    if updates.get("clear_secrets"):
        existing["secrets"] = {}
    if "secrets" in updates:
        existing["secrets"] = updates["secrets"]
    return existing


def delete_server(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    server_id: int,
) -> bool:
    if db and _table_exists(db, "mcp_servers"):
        query = db.query(McpServer).filter(McpServer.id == server_id)
        if org_id:
            query = query.filter(McpServer.org_id == str(org_id))
        elif user_id:
            query = query.filter(McpServer.user_id == str(user_id))
        row = query.first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    _warn_once()
    bucket = _ensure_bucket(org_id, user_id)
    return bucket.pop(server_id, None) is not None


def _build_headers(server: Dict[str, Any]) -> Dict[str, str]:
    config = server.get("config") or {}
    secrets = server.get("secrets") or {}
    headers: Dict[str, str] = {"Content-Type": "application/json"}

    for k, v in (config.get("headers") or {}).items():
        if v:
            headers[str(k)] = str(v)

    auth_type = (server.get("auth_type") or "none").lower()
    if auth_type == "bearer" and secrets.get("token"):
        headers["Authorization"] = f"Bearer {secrets['token']}"
    elif auth_type == "header" and secrets.get("token"):
        header_name = config.get("auth_header_name") or "X-API-Key"
        headers[str(header_name)] = str(secrets["token"])
    elif auth_type == "basic" and secrets.get("password"):
        import base64

        username = config.get("username") or ""
        raw = f"{username}:{secrets['password']}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('utf-8')}"

    return headers


async def _parse_sse_response(stream, request_id: str) -> Dict[str, Any]:
    event_data: List[str] = []
    async for line in stream:
        if line is None:
            continue
        line = line.strip()
        if not line:
            if not event_data:
                continue
            payload = "\n".join(event_data)
            event_data = []
            if payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            if obj.get("id") == request_id:
                return obj
            continue
        if line.startswith("data:"):
            event_data.append(line[5:].strip())
    raise RuntimeError("No MCP response received from server")


async def _jsonrpc_call(
    server: Dict[str, Any],
    method: str,
    params: Optional[Dict[str, Any]],
    timeout: float = 12.0,
) -> Dict[str, Any]:
    _validate_server_url(server["url"])
    request_id = uuid4().hex
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params

    headers = _build_headers(server)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream(
            "POST", server["url"], json=payload, headers=headers
        ) as resp:
            if resp.status_code >= 400:
                text = await resp.aread()
                raise RuntimeError(
                    f"HTTP {resp.status_code}: {text.decode(errors='ignore')}"
                )
            content_type = (resp.headers.get("content-type") or "").lower()
            if "text/event-stream" in content_type:
                return await _parse_sse_response(resp.aiter_lines(), request_id)
            data = await resp.json()
            return data


async def list_remote_tools(server: Dict[str, Any]) -> List[Dict[str, Any]]:
    response = await _jsonrpc_call(server, "tools/list", {})
    if "error" in response:
        raise RuntimeError(
            response["error"].get("message")
            if isinstance(response["error"], dict)
            else response["error"]
        )
    result = response.get("result")
    if isinstance(result, dict) and "tools" in result:
        return result["tools"] or []
    if isinstance(result, list):
        return result
    return []


async def call_remote_tool(
    server: Dict[str, Any],
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    response = await _jsonrpc_call(
        server,
        "tools/call",
        {"name": tool_name, "arguments": arguments},
    )
    if "error" in response:
        raise RuntimeError(
            response["error"].get("message")
            if isinstance(response["error"], dict)
            else response["error"]
        )
    return response.get("result") or {}


def _update_server_status(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    server_id: int,
    status: str,
    tool_count: Optional[int],
    error: Optional[str],
) -> None:
    if db and _table_exists(db, "mcp_servers"):
        query = db.query(McpServer).filter(McpServer.id == server_id)
        if org_id:
            query = query.filter(McpServer.org_id == str(org_id))
        elif user_id:
            query = query.filter(McpServer.user_id == str(user_id))
        row = query.first()
        if not row:
            return
        row.status = status
        row.tool_count = tool_count
        row.last_error = error
        row.last_checked_at = datetime.utcnow()
        db.add(row)
        db.commit()
        return
    bucket = _ensure_bucket(org_id, user_id)
    if server_id in bucket:
        bucket[server_id]["status"] = status
        bucket[server_id]["tool_count"] = tool_count
        bucket[server_id]["last_error"] = error
        bucket[server_id]["last_checked_at"] = datetime.utcnow().isoformat()


async def test_server(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    server_id: int,
) -> Dict[str, Any]:
    server = get_server(db, user_id, org_id, server_id)
    if not server:
        raise RuntimeError("Server not found")
    try:
        tools = await list_remote_tools(server)
        _update_server_status(
            db, user_id, org_id, server_id, "connected", len(tools), None
        )
        return {"ok": True, "tool_count": len(tools)}
    except Exception as exc:
        _update_server_status(db, user_id, org_id, server_id, "error", None, str(exc))
        return {"ok": False, "error": str(exc)}


async def list_external_tools(
    db: Optional[Session],
    user_id: Optional[str],
    org_id: Optional[str],
    servers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for server in servers:
        if not server.get("enabled"):
            continue
        full_server = get_server(db, user_id, org_id, int(server["id"]))
        if not full_server:
            continue
        try:
            remote_tools = await list_remote_tools(full_server)
            _update_server_status(
                db,
                user_id,
                org_id,
                int(server["id"]),
                "connected",
                len(remote_tools),
                None,
            )
            for tool in remote_tools:
                metadata = tool.get("metadata") or {}
                category = metadata.get("category") or "external"
                tool["metadata"] = {
                    **metadata,
                    "category": category,
                    "requires_approval": bool(metadata.get("requires_approval", False)),
                    "server_id": server["id"],
                    "server_name": server["name"],
                    "source": "external",
                    "transport": server.get("transport"),
                    "scope": server.get("scope"),
                }
                tools.append(tool)
        except Exception as exc:
            _update_server_status(
                db, user_id, org_id, int(server["id"]), "error", None, str(exc)
            )
            logger.warning(
                "Failed to fetch MCP tools from %s: %s", server.get("name"), exc
            )
    return tools
