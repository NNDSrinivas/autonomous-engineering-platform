# Loveable-Style Live Preview - Complete Implementation Plan

**Status:** Ready for Implementation
**Architecture:** Option C (Hybrid) - Build abstraction now, ship NaviOS local, swap to ECS later
**Last Updated:** February 22, 2026

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Static Preview (Week 1)](#phase-1-static-preview-week-1)
3. [Phase 2: Preview Sessions with NaviOS (Weeks 2-3)](#phase-2-preview-sessions-with-navios-weeks-2-3)
4. [Phase 3: Remote ECS Runners (Future)](#phase-3-remote-ecs-runners-future)
5. [Implementation Checklist](#implementation-checklist)
6. [Testing Strategy](#testing-strategy)
7. [Security Considerations](#security-considerations)

---

## Architecture Overview

### The Abstraction Layer (Key Innovation)

**Build interfaces NOW as if runners are remote**, even though Phase 2 uses NaviOS local subprocess:

```
Backend (Control Plane)
├── runner.start_preview(run_id, workspace_path, framework)  ← Interface
│   ├── LocalRunner (Phase 2) → NaviOS subprocess
│   └── RemoteRunner (Phase 3) → ECS Fargate task
├── Preview Proxy: /api/runs/:run_id/preview/*
│   ├── Phase 2: → http://127.0.0.1:<port>
│   └── Phase 3: → ECS task IP or tunnel
└── SSE Events: preview.starting, preview.ready, preview.failed
```

**No rewrites when moving to ECS:**
- Same API endpoints
- Same SSE events
- Same frontend code
- Only executor implementation changes

### End-to-End Flow (Loveable-style)

```
1. User starts "web build" run
   Web → Backend: POST /api/runs

2. Backend triggers preview
   Backend → Runner: start_preview(run_id, workspace_path, "nextjs")

3. Runner starts dev server
   NaviOS/ECS → npm install && npm run dev

4. Backend emits SSE
   preview.ready { url: "/api/runs/<run_id>/preview/" }

5. Web loads iframe
   <iframe src="/api/runs/<run_id>/preview/" />

6. Backend proxies traffic
   GET /api/runs/:id/preview/* → 127.0.0.1:<port> (Phase 2)
                                → ECS task IP (Phase 3)

7. Navi edits files → HMR updates automatically
   (Next.js/Vite HMR handles live reload)
```

---

## Phase 1: Static Preview (Week 1)

### Goal
Ship basic split-screen preview with static HTML rendering.

### Backend: New Files

#### 1. `/backend/services/preview/preview_service.py`

```python
"""
Preview Service - Static HTML storage and retrieval.

Phase 1: In-memory storage (MVP)
Phase 2+: Redis/S3 backend (swap implementation, same interface)
"""

import logging
import time
import uuid
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreviewContent:
    """Static preview content metadata."""

    preview_id: str
    content: str
    content_type: str  # "html", "markdown", etc.
    created_at: float
    expires_at: float


class PreviewService:
    """
    Manages static preview content storage.

    Phase 1: In-memory store (simple dict)
    Later: Swap to Redis/S3 with same interface
    """

    def __init__(self, ttl_seconds: int = 3600, max_previews: int = 100):
        self.ttl_seconds = ttl_seconds
        self.max_previews = max_previews
        self._store: Dict[str, PreviewContent] = {}
        logger.info(f"PreviewService initialized (TTL={ttl_seconds}s, max={max_previews})")

    async def store(self, content: str, content_type: str = "html") -> str:
        """
        Store preview content and return preview ID.

        Args:
            content: HTML/markdown content
            content_type: Content type ("html", "markdown")

        Returns:
            preview_id: Unique preview identifier
        """
        # Cleanup if at capacity
        if len(self._store) >= self.max_previews:
            self._cleanup_oldest()

        preview_id = str(uuid.uuid4())
        now = time.time()

        preview = PreviewContent(
            preview_id=preview_id,
            content=content,
            content_type=content_type,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )

        self._store[preview_id] = preview
        logger.info(f"Stored preview {preview_id} ({len(content)} chars)")

        return preview_id

    async def get(self, preview_id: str) -> Optional[PreviewContent]:
        """
        Retrieve preview content by ID.

        Args:
            preview_id: Preview identifier

        Returns:
            PreviewContent or None if not found/expired
        """
        preview = self._store.get(preview_id)

        if not preview:
            return None

        # Check expiration
        if time.time() > preview.expires_at:
            del self._store[preview_id]
            logger.info(f"Preview {preview_id} expired")
            return None

        return preview

    async def delete(self, preview_id: str) -> bool:
        """Delete preview by ID."""
        if preview_id in self._store:
            del self._store[preview_id]
            logger.info(f"Deleted preview {preview_id}")
            return True
        return False

    def _cleanup_oldest(self):
        """Remove oldest preview to make space."""
        if not self._store:
            return

        oldest_id = min(self._store.keys(), key=lambda k: self._store[k].created_at)
        del self._store[oldest_id]
        logger.info(f"Cleaned up oldest preview {oldest_id}")


# Global singleton instance
_preview_service: Optional[PreviewService] = None


def get_preview_service() -> PreviewService:
    """Get global PreviewService instance."""
    global _preview_service
    if _preview_service is None:
        _preview_service = PreviewService()
    return _preview_service
```

#### 2. `/backend/api/routers/preview.py`

```python
"""
Preview API Router - Static preview endpoints.

Endpoints:
- POST /api/preview/static - Store static HTML
- GET /api/preview/{preview_id} - Retrieve preview
- DELETE /api/preview/{preview_id} - Delete preview
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Literal

from backend.services.preview.preview_service import get_preview_service
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role

router = APIRouter(prefix="/api/preview", tags=["preview"])


class StorePreviewRequest(BaseModel):
    """Request to store static preview content."""

    content: str
    content_type: Literal["html", "markdown"] = "html"


class StorePreviewResponse(BaseModel):
    """Response with preview ID and URL."""

    preview_id: str
    url: str


@router.post("/static", response_model=StorePreviewResponse)
async def store_static_preview(
    request: StorePreviewRequest,
    user = Depends(require_role(Role.VIEWER)),
):
    """
    Store static HTML/markdown preview content.

    Returns preview ID and retrieval URL.

    Security:
    - Requires authentication (VIEWER role)
    - Content is NOT sanitized (trusted from NAVI)
    - Preview URLs are public (anyone with ID can access)
    """
    preview_service = get_preview_service()

    preview_id = await preview_service.store(
        content=request.content,
        content_type=request.content_type,
    )

    return StorePreviewResponse(
        preview_id=preview_id,
        url=f"/api/preview/{preview_id}",
    )


@router.get("/{preview_id}")
async def get_preview(preview_id: str):
    """
    Retrieve preview content by ID.

    Returns HTML response with sandbox restrictions.

    Security:
    - No authentication required (preview IDs are UUIDs = hard to guess)
    - Content-Security-Policy headers for iframe safety
    - X-Frame-Options allows same-origin only
    """
    preview_service = get_preview_service()

    preview = await preview_service.get(preview_id)

    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found or expired")

    # Return HTML with security headers
    return HTMLResponse(
        content=preview.content,
        headers={
            "Content-Security-Policy": "default-src 'self' 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'self';",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{preview_id}")
async def delete_preview(
    preview_id: str,
    user = Depends(require_role(Role.VIEWER)),
):
    """Delete preview by ID (requires auth)."""
    preview_service = get_preview_service()

    success = await preview_service.delete(preview_id)

    if not success:
        raise HTTPException(status_code=404, detail="Preview not found")

    return {"success": True, "preview_id": preview_id}
```

#### 3. Register Router in `/backend/api/main.py`

```python
# Add to imports
from backend.api.routers import preview

# Add to router registration section (around line 90-100)
app.include_router(preview.router)
```

### Frontend: New Files

#### 4. `/web/components/preview/PreviewFrame.tsx`

```typescript
/**
 * PreviewFrame - Iframe wrapper for preview content
 *
 * Supports:
 * - Static HTML via srcDoc
 * - URLs via src
 * - Loading states
 * - Error handling
 */

import React, { useState } from 'react';

interface PreviewFrameProps {
  src?: string;
  srcDoc?: string;
  className?: string;
}

export function PreviewFrame({ src, srcDoc, className = '' }: PreviewFrameProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleLoad = () => {
    setIsLoading(false);
    setHasError(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
  };

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* Loading State */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
            <p className="text-sm text-gray-600">Loading preview...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {hasError && !isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-50">
          <div className="text-center p-6">
            <svg className="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3 className="text-lg font-medium text-red-900 mb-2">Preview Failed</h3>
            <p className="text-sm text-red-700">Unable to load preview content</p>
          </div>
        </div>
      )}

      {/* Preview Iframe */}
      <iframe
        src={src}
        srcDoc={srcDoc}
        sandbox="allow-scripts"  // NO allow-same-origin for security
        referrerPolicy="no-referrer"
        className="w-full h-full border-0"
        onLoad={handleLoad}
        onError={handleError}
        title="Preview"
      />
    </div>
  );
}
```

#### 5. `/web/components/preview/PreviewControls.tsx`

```typescript
/**
 * PreviewControls - Preview toolbar with actions
 *
 * Actions:
 * - Refresh preview
 * - Open in new tab
 * - Device size selector
 * - Toggle visibility
 */

import React from 'react';

interface PreviewControlsProps {
  previewUrl?: string;
  onRefresh: () => void;
  onToggleVisibility: () => void;
  visible: boolean;
}

type DeviceSize = 'mobile' | 'tablet' | 'desktop';

export function PreviewControls({
  previewUrl,
  onRefresh,
  onToggleVisibility,
  visible,
}: PreviewControlsProps) {
  const [deviceSize, setDeviceSize] = React.useState<DeviceSize>('desktop');

  const handleOpenNewTab = () => {
    if (previewUrl) {
      window.open(previewUrl, '_blank');
    }
  };

  const handleCopyUrl = () => {
    if (previewUrl) {
      navigator.clipboard.writeText(window.location.origin + previewUrl);
    }
  };

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
      {/* Left: Device Selector */}
      <div className="flex items-center space-x-2">
        <button
          onClick={() => setDeviceSize('mobile')}
          className={`px-3 py-1 text-xs rounded ${
            deviceSize === 'mobile'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300'
          }`}
          title="Mobile (375px)"
        >
          📱 Mobile
        </button>
        <button
          onClick={() => setDeviceSize('tablet')}
          className={`px-3 py-1 text-xs rounded ${
            deviceSize === 'tablet'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300'
          }`}
          title="Tablet (768px)"
        >
          📱 Tablet
        </button>
        <button
          onClick={() => setDeviceSize('desktop')}
          className={`px-3 py-1 text-xs rounded ${
            deviceSize === 'desktop'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300'
          }`}
          title="Desktop (100%)"
        >
          🖥️ Desktop
        </button>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-2">
        {/* Refresh */}
        <button
          onClick={onRefresh}
          className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50"
          title="Refresh preview"
        >
          🔄 Refresh
        </button>

        {/* Open in new tab */}
        {previewUrl && (
          <button
            onClick={handleOpenNewTab}
            className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50"
            title="Open in new tab"
          >
            ↗️ Open
          </button>
        )}

        {/* Copy URL */}
        {previewUrl && (
          <button
            onClick={handleCopyUrl}
            className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50"
            title="Copy preview URL"
          >
            📋 Copy URL
          </button>
        )}

        {/* Toggle visibility */}
        <button
          onClick={onToggleVisibility}
          className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50"
          title={visible ? 'Hide preview' : 'Show preview'}
        >
          {visible ? '👁️ Hide' : '👁️ Show'}
        </button>
      </div>
    </div>
  );
}
```

#### 6. `/web/hooks/usePreview.ts`

```typescript
/**
 * usePreview - Preview state management hook
 */

import { useState, useCallback } from 'react';

export interface PreviewState {
  url: string | null;
  html: string | null;
  type: 'url' | 'html' | null;
  visible: boolean;
}

export function usePreview() {
  const [state, setState] = useState<PreviewState>({
    url: null,
    html: null,
    type: null,
    visible: false,
  });

  const setPreviewUrl = useCallback((url: string) => {
    setState({
      url,
      html: null,
      type: 'url',
      visible: true,
    });
  }, []);

  const setPreviewHtml = useCallback((html: string) => {
    setState({
      url: null,
      html,
      type: 'html',
      visible: true,
    });
  }, []);

  const clearPreview = useCallback(() => {
    setState({
      url: null,
      html: null,
      type: null,
      visible: false,
    });
  }, []);

  const toggleVisibility = useCallback(() => {
    setState((prev) => ({
      ...prev,
      visible: !prev.visible,
    }));
  }, []);

  return {
    ...state,
    setPreviewUrl,
    setPreviewHtml,
    clearPreview,
    toggleVisibility,
  };
}
```

#### 7. Modify `/web/app/(app)/app/chats/page.tsx`

```typescript
// Add imports
import { PreviewFrame } from '@/components/preview/PreviewFrame';
import { PreviewControls } from '@/components/preview/PreviewControls';
import { usePreview } from '@/hooks/usePreview';

// Inside the component:
export default function ChatsPage() {
  const preview = usePreview();

  // ... existing code ...

  return (
    <div className="flex h-[calc(100vh-112px)]">
      {/* Sidebar */}
      <div className="w-80">
        {/* ... existing sidebar code ... */}
      </div>

      {/* Chat Area */}
      <div className={preview.visible ? "flex-1" : "flex-[2]"}>
        {/* ... existing chat code ... */}
      </div>

      {/* Preview Pane (NEW) */}
      {preview.visible && (
        <div className="flex-1 border-l border-gray-200 flex flex-col">
          <PreviewControls
            previewUrl={preview.url || undefined}
            onRefresh={() => {
              // Trigger iframe reload
              const iframe = document.querySelector('iframe');
              if (iframe) iframe.src = iframe.src;
            }}
            onToggleVisibility={preview.toggleVisibility}
            visible={preview.visible}
          />
          <div className="flex-1">
            <PreviewFrame
              src={preview.url || undefined}
              srcDoc={preview.html || undefined}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

### Phase 1 Testing Checklist

- [ ] POST /api/preview/static stores HTML and returns preview_id
- [ ] GET /api/preview/{id} returns HTML with correct headers
- [ ] Preview expires after 1 hour (TTL)
- [ ] Max 100 previews enforced (oldest deleted)
- [ ] PreviewFrame renders static HTML via srcDoc
- [ ] PreviewControls actions work (refresh, toggle, copy)
- [ ] Preview pane is responsive and resizable
- [ ] Security: iframe sandbox="allow-scripts" (no allow-same-origin)

---

## Phase 2: Preview Sessions with NaviOS (Weeks 2-3)

### Goal
Start live dev servers for web projects, proxy traffic, emit SSE events.

### Backend: Runner Abstraction

#### 8. `/backend/services/runner/__init__.py`

```python
"""
Runner Package - Execution environment abstraction.

Phase 2: LocalRunner (NaviOS subprocess)
Phase 3: RemoteRunner (ECS Fargate)
"""

from .runner_interface import RunnerInterface, PreviewSession, PreviewStatus
from .local_runner import LocalRunner
from .remote_runner import RemoteRunner

__all__ = [
    "RunnerInterface",
    "PreviewSession",
    "PreviewStatus",
    "LocalRunner",
    "RemoteRunner",
]
```

#### 9. `/backend/services/runner/runner_interface.py`

```python
"""
Runner Interface - Abstract base for execution environments.

Defines the contract for starting/stopping preview sessions.
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PreviewStatus(Enum):
    """Preview session status."""

    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class PreviewSession:
    """Preview session metadata."""

    run_id: str
    workspace_path: str
    framework: str
    port: Optional[int] = None
    pid: Optional[int] = None
    status: PreviewStatus = PreviewStatus.STARTING
    error: Optional[str] = None
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None


class RunnerInterface(ABC):
    """
    Abstract interface for execution environments.

    Implementations:
    - LocalRunner: NaviOS subprocess (Phase 2)
    - RemoteRunner: ECS Fargate task (Phase 3)
    """

    @abstractmethod
    async def start_preview(
        self,
        run_id: str,
        workspace_path: str,
        framework: str,
    ) -> PreviewSession:
        """
        Start a preview session (dev server).

        Args:
            run_id: Unique run identifier
            workspace_path: Path to workspace/repo
            framework: Framework name ("nextjs", "vite", "cra")

        Returns:
            PreviewSession with status and port

        Raises:
            RuntimeError: If preview fails to start
        """
        pass

    @abstractmethod
    async def stop_preview(self, run_id: str) -> bool:
        """
        Stop a preview session.

        Args:
            run_id: Run identifier

        Returns:
            True if stopped successfully
        """
        pass

    @abstractmethod
    async def get_preview_status(self, run_id: str) -> Optional[PreviewSession]:
        """
        Get current preview session status.

        Args:
            run_id: Run identifier

        Returns:
            PreviewSession or None if not found
        """
        pass
```

#### 10. `/backend/services/runner/local_runner.py`

```python
"""
LocalRunner - NaviOS-based local execution.

Uses NaviOS sandbox to run dev servers as subprocesses.
Phase 2 implementation.
"""

import asyncio
import logging
import time
import httpx
from pathlib import Path
from typing import Dict, Optional

from .runner_interface import RunnerInterface, PreviewSession, PreviewStatus
from backend.agents.sandbox.navios_sandbox import NaviOSSandbox

logger = logging.getLogger(__name__)


class LocalRunner(RunnerInterface):
    """
    Local preview runner using NaviOS sandbox.

    Phase 2: Runs dev servers as subprocesses on localhost.
    Phase 3: Replace with RemoteRunner (ECS Fargate).
    """

    def __init__(self):
        self._sessions: Dict[str, PreviewSession] = {}
        self._port_allocator = PortAllocator(start_port=3000, end_port=4000)
        logger.info("LocalRunner initialized")

    async def start_preview(
        self,
        run_id: str,
        workspace_path: str,
        framework: str,
    ) -> PreviewSession:
        """Start dev server via NaviOS sandbox."""

        logger.info(f"Starting preview for run {run_id} (framework={framework})")

        # Allocate port
        port = self._port_allocator.allocate()
        if not port:
            raise RuntimeError("No available ports for preview")

        # Create session
        session = PreviewSession(
            run_id=run_id,
            workspace_path=workspace_path,
            framework=framework,
            port=port,
            status=PreviewStatus.STARTING,
            started_at=time.time(),
        )
        self._sessions[run_id] = session

        try:
            # Detect dev command
            dev_command = self._get_dev_command(workspace_path, framework, port)

            # Start dev server using NaviOS (background process)
            # NOTE: This is simplified - you'll need to extend NaviOS to support
            # long-running background processes
            sandbox = NaviOSSandbox(workspace_root=workspace_path)

            # Execute dev server start (this blocks until server is ready)
            await self._start_dev_server(sandbox, dev_command, port)

            # Wait for server to be healthy
            healthy = await self._wait_for_health(port, timeout=30)

            if healthy:
                session.status = PreviewStatus.RUNNING
                logger.info(f"Preview running on port {port}")
            else:
                session.status = PreviewStatus.FAILED
                session.error = "Dev server failed health check"
                self._port_allocator.release(port)
                logger.error(f"Preview failed for run {run_id}")

        except Exception as e:
            session.status = PreviewStatus.FAILED
            session.error = str(e)
            self._port_allocator.release(port)
            logger.error(f"Preview start error for run {run_id}: {e}")

        return session

    async def stop_preview(self, run_id: str) -> bool:
        """Stop dev server and clean up."""

        session = self._sessions.get(run_id)
        if not session:
            return False

        logger.info(f"Stopping preview for run {run_id}")

        # Kill process (if PID tracked)
        if session.pid:
            try:
                import os
                import signal
                os.kill(session.pid, signal.SIGTERM)
            except Exception as e:
                logger.warning(f"Failed to kill process {session.pid}: {e}")

        # Release port
        if session.port:
            self._port_allocator.release(session.port)

        session.status = PreviewStatus.STOPPED
        session.stopped_at = time.time()

        return True

    async def get_preview_status(self, run_id: str) -> Optional[PreviewSession]:
        """Get session status."""
        return self._sessions.get(run_id)

    def _get_dev_command(self, workspace_path: str, framework: str, port: int) -> str:
        """Detect dev command based on framework."""

        workspace = Path(workspace_path)
        package_json = workspace / "package.json"

        if not package_json.exists():
            raise RuntimeError("No package.json found")

        # Framework-specific commands
        if framework == "nextjs" or "next" in str(package_json.read_text()):
            return f"npm run dev -- --port {port}"
        elif framework == "vite" or "vite" in str(package_json.read_text()):
            return f"npm run dev -- --port {port} --host 127.0.0.1"
        elif framework == "cra":
            return f"PORT={port} npm start"
        else:
            # Generic fallback
            return f"npm run dev -- --port {port}"

    async def _start_dev_server(self, sandbox: NaviOSSandbox, command: str, port: int):
        """
        Start dev server using NaviOS.

        NOTE: This is a simplified placeholder.
        You'll need to extend NaviOS to support background processes
        or use asyncio.create_subprocess_exec directly.
        """

        # For now, use subprocess directly (bypassing NaviOS)
        # In production, extend NaviOS to support this pattern

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=sandbox.workspace_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        logger.info(f"Started dev server (PID={proc.pid}, port={port})")

    async def _wait_for_health(self, port: int, timeout: int = 30) -> bool:
        """Poll dev server until healthy or timeout."""

        start = time.time()
        async with httpx.AsyncClient() as client:
            while time.time() - start < timeout:
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/")
                    if response.status_code < 500:
                        logger.info(f"Dev server healthy on port {port}")
                        return True
                except Exception:
                    pass  # Server not ready yet

                await asyncio.sleep(1)

        return False


class PortAllocator:
    """Simple port allocator for local dev servers."""

    def __init__(self, start_port: int = 3000, end_port: int = 4000):
        self.start_port = start_port
        self.end_port = end_port
        self._allocated = set()

    def allocate(self) -> Optional[int]:
        """Allocate next available port."""
        for port in range(self.start_port, self.end_port):
            if port not in self._allocated:
                self._allocated.add(port)
                return port
        return None

    def release(self, port: int):
        """Release port back to pool."""
        self._allocated.discard(port)
```

#### 11. `/backend/services/runner/remote_runner.py`

```python
"""
RemoteRunner - ECS Fargate-based remote execution.

Phase 3 implementation (stub for now).
"""

import logging
from typing import Optional

from .runner_interface import RunnerInterface, PreviewSession, PreviewStatus

logger = logging.getLogger(__name__)


class RemoteRunner(RunnerInterface):
    """
    Remote preview runner using ECS Fargate.

    Phase 3: To be implemented.
    """

    def __init__(self):
        logger.info("RemoteRunner initialized (stub)")

    async def start_preview(
        self,
        run_id: str,
        workspace_path: str,
        framework: str,
    ) -> PreviewSession:
        """Start preview on ECS Fargate (not implemented)."""
        raise NotImplementedError("RemoteRunner not implemented yet (Phase 3)")

    async def stop_preview(self, run_id: str) -> bool:
        """Stop preview (not implemented)."""
        raise NotImplementedError("RemoteRunner not implemented yet (Phase 3)")

    async def get_preview_status(self, run_id: str) -> Optional[PreviewSession]:
        """Get status (not implemented)."""
        raise NotImplementedError("RemoteRunner not implemented yet (Phase 3)")
```

### Backend: Preview Proxy Router

#### 12. `/backend/api/routers/run_preview_proxy.py`

```python
"""
Preview Proxy Router - Auth-gated reverse proxy to dev servers.

Routes:
- GET /api/runs/{run_id}/preview/* → Dev server port
- Supports Phase 2 (localhost) and Phase 3 (ECS) transparently
"""

import logging
import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from backend.services.runner.local_runner import LocalRunner
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["preview-proxy"])

# Global runner instance (switch to RemoteRunner in Phase 3)
_runner = LocalRunner()


@router.get("/{run_id}/preview/{path:path}")
async def proxy_preview(
    run_id: str,
    path: str,
    request: Request,
    user = Depends(require_role(Role.VIEWER)),
):
    """
    Reverse proxy to preview dev server.

    Security:
    - Requires authentication
    - TODO: Check org ownership of run_id
    - Proxies to localhost (Phase 2) or ECS task (Phase 3)
    """

    # Get preview session
    session = await _runner.get_preview_status(run_id)

    if not session:
        raise HTTPException(status_code=404, detail="Preview session not found")

    if session.status != "running":
        raise HTTPException(
            status_code=503,
            detail=f"Preview not ready (status={session.status})",
        )

    # Build target URL
    # Phase 2: localhost
    # Phase 3: ECS task IP or tunnel URL
    target_url = f"http://127.0.0.1:{session.port}/{path}"

    # Proxy request
    async with httpx.AsyncClient() as client:
        try:
            # Forward request to dev server
            response = await client.request(
                method=request.method,
                url=target_url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                params=request.query_params,
                timeout=30.0,
            )

            # Stream response back
            return StreamingResponse(
                content=response.iter_bytes(),
                status_code=response.status_code,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-encoding")
                },
            )

        except httpx.RequestError as e:
            logger.error(f"Proxy error for run {run_id}: {e}")
            raise HTTPException(status_code=502, detail="Preview server unavailable")


@router.post("/{run_id}/preview/start")
async def start_preview_session(
    run_id: str,
    workspace_path: str,
    framework: str,
    user = Depends(require_role(Role.VIEWER)),
):
    """
    Start a preview session for a run.

    Typically called by agent loop when detecting web project.
    """

    try:
        session = await _runner.start_preview(run_id, workspace_path, framework)

        return {
            "success": True,
            "session": {
                "run_id": session.run_id,
                "status": session.status.value,
                "port": session.port,
                "url": f"/api/runs/{run_id}/preview/" if session.status == "running" else None,
            },
        }

    except Exception as e:
        logger.error(f"Failed to start preview for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/preview/stop")
async def stop_preview_session(
    run_id: str,
    user = Depends(require_role(Role.VIEWER)),
):
    """Stop preview session."""

    success = await _runner.stop_preview(run_id)

    if not success:
        raise HTTPException(status_code=404, detail="Preview session not found")

    return {"success": True}
```

#### 13. Register Proxy Router in `/backend/api/main.py`

```python
# Add to imports
from backend.api.routers import run_preview_proxy

# Add to router registration
app.include_router(run_preview_proxy.router)
```

### Backend: SSE Events from Agent Loop

#### 14. Modify `/backend/api/navi.py` (around line 6920)

```python
# Add preview event emission after detecting web project

# Inside generate_stream() function, after workspace detection:

# =================================================================
# PREVIEW DETECTION: Auto-start preview for web projects
# =================================================================
if workspace_root and _is_web_project(workspace_root):
    logger.info(f"[NAVI-STREAM] Detected web project, starting preview...")

    yield f"data: {json.dumps({'activity': {'kind': 'preview', 'label': 'Starting Preview', 'detail': 'Initializing dev server...', 'status': 'running'}})}\n\n"

    try:
        from backend.services.runner.local_runner import LocalRunner

        runner = LocalRunner()
        framework = _detect_framework(workspace_root)  # "nextjs", "vite", etc.

        # Start preview session
        session = await runner.start_preview(
            run_id=request.conversation_id or f"run-{uuid4()}",
            workspace_path=workspace_root,
            framework=framework,
        )

        if session.status.value == "running":
            # Emit preview.ready event
            yield f"data: {json.dumps({'preview': {'event': 'ready', 'url': f'/api/runs/{session.run_id}/preview/', 'framework': framework, 'port': session.port}})}\n\n"
        else:
            # Emit preview.failed event
            yield f"data: {json.dumps({'preview': {'event': 'failed', 'error': session.error or 'Unknown error'}})}\n\n"

    except Exception as preview_err:
        logger.error(f"[NAVI-STREAM] Preview start failed: {preview_err}")
        yield f"data: {json.dumps({'preview': {'event': 'failed', 'error': str(preview_err)}})}\n\n"


def _is_web_project(workspace_path: str) -> bool:
    """Check if workspace contains a web project."""
    from pathlib import Path

    workspace = Path(workspace_path)
    package_json = workspace / "package.json"

    if not package_json.exists():
        return False

    # Check for common web frameworks
    content = package_json.read_text()
    return any(fw in content for fw in ["next", "vite", "react", "vue", "svelte"])


def _detect_framework(workspace_path: str) -> str:
    """Detect web framework from package.json."""
    from pathlib import Path
    import json as json_lib

    workspace = Path(workspace_path)
    package_json = workspace / "package.json"

    if not package_json.exists():
        return "unknown"

    try:
        data = json_lib.loads(package_json.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        if "next" in deps:
            return "nextjs"
        elif "vite" in deps:
            return "vite"
        elif "react-scripts" in deps:
            return "cra"
        else:
            return "unknown"

    except Exception:
        return "unknown"
```

### Frontend: Preview Session Integration

#### 15. Modify `/web/lib/streaming/sseClient.ts`

```typescript
// Extend SSEMessage type to include preview events

export interface SSEMessage {
  type?: string;
  data?: any;
  preview?: {
    event: 'ready' | 'failed' | 'starting';
    url?: string;
    framework?: string;
    port?: number;
    error?: string;
  };
  activity?: {
    kind: string;
    label: string;
    detail: string;
    status: string;
  };
  // ... existing fields
}
```

#### 16. Modify `/web/app/(app)/app/chats/page.tsx` (SSE handling)

```typescript
// Inside SSE event handler:

useEffect(() => {
  const eventSource = new EventSource('/api/navi/chat/stream');

  eventSource.onmessage = (event) => {
    const data: SSEMessage = JSON.parse(event.data);

    // Handle preview events
    if (data.preview) {
      switch (data.preview.event) {
        case 'ready':
          preview.setPreviewUrl(data.preview.url!);
          console.log('[Preview] Dev server ready:', data.preview);
          break;

        case 'failed':
          console.error('[Preview] Failed:', data.preview.error);
          // Show error toast
          break;

        case 'starting':
          console.log('[Preview] Starting dev server...');
          break;
      }
    }

    // ... existing handlers
  };

  return () => eventSource.close();
}, []);
```

### Phase 2 Testing Checklist

- [ ] LocalRunner starts Next.js dev server on allocated port
- [ ] Dev server health check passes within 30s
- [ ] GET /api/runs/:id/preview/* proxies to localhost:port
- [ ] SSE event preview.ready emitted with correct URL
- [ ] Frontend iframe loads preview URL successfully
- [ ] HMR works (edit file → preview updates automatically)
- [ ] Stop preview releases port and kills process
- [ ] Multiple concurrent previews work (different ports)
- [ ] Auth gate: unauthenticated requests to proxy fail with 401

---

## Phase 3: Remote ECS Runners (Future)

### Goal
Replace LocalRunner with RemoteRunner (ECS Fargate tasks).

### Changes Required

1. **Implement RemoteRunner:**
   - Dispatch ECS task via SQS
   - Track task IP + port
   - Return tunnel URL or task IP for proxy

2. **Update Proxy Route:**
   - Change target from `127.0.0.1:<port>` to `<task_ip>:<port>` or tunnel URL

3. **No Frontend Changes:**
   - Same `/api/runs/:id/preview/*` URL
   - Same SSE events
   - Same iframe integration

**That's it!** The abstraction layer makes this swap trivial.

---

## Implementation Checklist

### Phase 1 (Week 1)
- [ ] Create `/backend/services/preview/preview_service.py`
- [ ] Create `/backend/api/routers/preview.py`
- [ ] Register preview router in main.py
- [ ] Create `/web/components/preview/PreviewFrame.tsx`
- [ ] Create `/web/components/preview/PreviewControls.tsx`
- [ ] Create `/web/hooks/usePreview.ts`
- [ ] Modify `/web/app/(app)/app/chats/page.tsx` for split layout
- [ ] Test static HTML preview end-to-end
- [ ] Security audit: iframe sandbox, CSP headers

### Phase 2 (Weeks 2-3)
- [ ] Create runner package: `/backend/services/runner/__init__.py`
- [ ] Create `/backend/services/runner/runner_interface.py`
- [ ] Create `/backend/services/runner/local_runner.py`
- [ ] Create `/backend/services/runner/remote_runner.py` (stub)
- [ ] Create `/backend/api/routers/run_preview_proxy.py`
- [ ] Register proxy router in main.py
- [ ] Modify `/backend/api/navi.py` for preview detection + SSE events
- [ ] Extend `/web/lib/streaming/sseClient.ts` for preview events
- [ ] Update `/web/app/(app)/app/chats/page.tsx` for preview SSE handling
- [ ] Test Next.js dev server start + proxy + HMR
- [ ] Test Vite dev server start + proxy + HMR
- [ ] Test multiple concurrent previews
- [ ] Load test: 5 concurrent previews
- [ ] Security audit: auth gate, org ownership check

### Phase 3 (Future)
- [ ] Implement RemoteRunner with ECS Fargate
- [ ] Update proxy route for ECS task IPs
- [ ] Test ECS-based preview end-to-end
- [ ] Migrate from LocalRunner to RemoteRunner in production

---

## Testing Strategy

### Unit Tests

```python
# /backend/tests/test_preview_service.py
async def test_store_and_retrieve_preview():
    service = PreviewService()
    preview_id = await service.store("<h1>Test</h1>", "html")
    preview = await service.get(preview_id)
    assert preview.content == "<h1>Test</h1>"

async def test_preview_expiration():
    service = PreviewService(ttl_seconds=1)
    preview_id = await service.store("<h1>Test</h1>")
    await asyncio.sleep(2)
    preview = await service.get(preview_id)
    assert preview is None

# /backend/tests/test_local_runner.py
async def test_start_nextjs_preview():
    runner = LocalRunner()
    session = await runner.start_preview(
        run_id="test-run",
        workspace_path="/path/to/nextjs-app",
        framework="nextjs",
    )
    assert session.status == PreviewStatus.RUNNING
    assert session.port is not None
```

### Integration Tests

```typescript
// /web/tests/preview-integration.test.ts
describe('Preview Integration', () => {
  it('should load preview iframe on SSE event', async () => {
    const { getByTitle } = render(<ChatsPage />);

    // Simulate SSE event
    mockSSE.emit({
      preview: {
        event: 'ready',
        url: '/api/runs/test-run/preview/',
      },
    });

    // Check iframe loaded
    await waitFor(() => {
      const iframe = getByTitle('Preview');
      expect(iframe).toHaveAttribute('src', '/api/runs/test-run/preview/');
    });
  });
});
```

### E2E Tests

1. **Static Preview:**
   - Create HTML via NAVI → Preview appears in right pane
   - Click refresh → Iframe reloads
   - Toggle visibility → Pane hides/shows

2. **Dev Server Preview:**
   - Create Next.js app → Dev server auto-starts
   - Preview loads in < 30s
   - Edit component → HMR updates preview
   - Multiple sessions → Unique ports allocated

---

## Security Considerations

### Phase 1: Static Preview

- **Iframe Sandbox:** `sandbox="allow-scripts"` (NO `allow-same-origin`)
- **CSP Headers:** `default-src 'self' 'unsafe-inline' 'unsafe-eval'`
- **X-Frame-Options:** `SAMEORIGIN`
- **Preview IDs:** UUIDs (hard to guess, but not secret)
- **TTL:** 1 hour expiration

### Phase 2: Dev Server Preview

- **Auth Gate:** Proxy route requires authentication
- **Org Ownership:** TODO: Check user owns run_id before proxying
- **Port Binding:** `127.0.0.1` only (not `0.0.0.0`)
- **Port Range:** 3000-4000 (limited blast radius)
- **Timeouts:** 30s health check, 20min idle shutdown (TODO)
- **Process Isolation:** Each preview = separate subprocess

### Phase 3: Remote Runners

- **Network Isolation:** ECS tasks in private subnet
- **IAM Roles:** Minimal permissions (no secrets access)
- **Task Quotas:** Max N concurrent tasks per org
- **Secrets:** Never inject into preview responses

---

## Rollout Plan

### Phase 1 Rollout (Week 1)

1. **Internal Testing (Day 1-2):**
   - Team tests static preview with NAVI-generated HTML
   - Verify security headers, iframe sandbox

2. **Staged Rollout (Day 3-5):**
   - 10% of users (feature flag `preview_static_enabled`)
   - Monitor error rates, latency
   - Collect feedback on UX

3. **100% Rollout (Day 5):**
   - Enable for all users
   - Monitor storage usage (in-memory → Redis if needed)

### Phase 2 Rollout (Weeks 2-3)

1. **Internal Testing (Days 1-5):**
   - Team tests Next.js, Vite, CRA projects
   - Verify dev server start, proxy, HMR
   - Load test: 5 concurrent previews

2. **Canary Rollout (Days 6-10):**
   - 10% of users (feature flag `preview_dev_server_enabled`)
   - Monitor port allocation, process crashes
   - Collect feedback on latency

3. **Gradual Rollout (Days 11-15):**
   - 25% → 50% → 100%
   - Monitor resource usage (CPU, memory)

### Phase 3 Rollout (Future)

1. **ECS Infrastructure Setup:**
   - Create ECS cluster, task definition
   - Set up SQS queue for task dispatch
   - Configure networking (ALB, security groups)

2. **Parallel Testing:**
   - Run RemoteRunner in parallel with LocalRunner
   - Compare latency, reliability
   - Validate tunnel/proxy setup

3. **Gradual Migration:**
   - 10% → 25% → 50% → 100%
   - Deprecate LocalRunner after 2 weeks of stable RemoteRunner

---

## Open Questions

1. **Multi-user editing:**
   - **Decision:** One preview per run/session (not shared across users)
   - **Rationale:** Simpler isolation, clearer ownership

2. **Preview persistence:**
   - **Decision:** Previews do NOT survive page refresh (restart dev server)
   - **Rationale:** Simpler MVP, avoid state synchronization issues

3. **Mobile device testing:**
   - **Decision:** Phase 4 feature (tunneling via ngrok or similar)
   - **Rationale:** Out of scope for MVP, requires public URLs

4. **Workspace cloning:**
   - **Decision:** Phase 2 uses existing local workspace (no clone)
   - **Decision:** Phase 3 ECS runners will clone repos on-demand
   - **Rationale:** Faster MVP, avoid Git complexity in Phase 2

---

## Next Steps

### This Week (Phase 1)

1. **Day 1-2:** Create backend preview service + router
2. **Day 3-4:** Create frontend components + state management
3. **Day 5:** Integration testing + security audit

### Next 2 Weeks (Phase 2)

1. **Week 2:** Implement runner abstraction + local runner
2. **Week 3:** Implement preview proxy + SSE events + testing

### Future (Phase 3)

1. **Design ECS runner architecture**
2. **Implement RemoteRunner**
3. **Test + migrate production traffic**

---

## Success Metrics

### Phase 1

- Static preview renders in < 500ms
- Zero XSS vulnerabilities
- Preview pane resizable without jank
- 95% user satisfaction with UX

### Phase 2

- Dev server starts in < 30s (p95)
- Zero port collisions in load testing
- Preview URL loads in < 2s after server ready
- HMR updates preview in < 1s

### Phase 3

- ECS runner starts in < 45s (p95)
- 99.9% preview availability
- No noisy neighbor issues (process isolation)
- Cost < $0.10 per preview session

---

**END OF IMPLEMENTATION PLAN**
