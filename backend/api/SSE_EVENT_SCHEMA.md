# SSE Live Refactor Streaming - Event Schema

This document defines the complete Server-Sent Events (SSE) schema for real-time refactor streaming in the Autonomous Engineering Platform.

## 🔥 **Endpoint**

```
POST /api/refactor/stream
```

## 📡 **Event Types**

| Event Type | Purpose | Stage | Example |
|------------|---------|-------|---------|
| `liveProgress` | High-level progress updates | All | Planning, transforming, generating, applying |
| `refactorPlan` | Complete execution plan | Planning | AST transformation steps |
| `fileStart` | Beginning file analysis | Transforming | Starting work on specific file |
| `fileASTEdit` | AST transformation result | Transforming | Before/after code changes |
| `diffChunk` | Unified diff streaming | Generating | Git-style diff per file |
| `issue` | Issues and suggestions | Any | Warnings, errors, suggestions |
| `patchBundle` | Final multi-file patch | Generating | Complete patch ready for application |
| `done` | Stream completion | Complete | Success/failure summary |
| `error` | Error occurred | Any | Exception details |
| `heartbeat` | Connection keepalive | All | Periodic ping |

---

## 📋 **Event Schemas**

### 1. `liveProgress` - Progress Updates

```json
{
  "event": "liveProgress",
  "data": {
    "stage": "planning|transforming|generating|applying|complete",
    "progress": 0.75,
    "message": "🔧 Transforming dashboard/index.tsx...",
    "details": {
      "current_file": "dashboard/index.tsx",
      "step_count": 5
    }
  }
}
```

**Usage:** Show progress bar and current operation in VS Code UI.

---

### 2. `refactorPlan` - Execution Plan

```json
{
  "event": "refactorPlan", 
  "data": {
    "instruction": "Refactor dashboard to use new Sidebar component",
    "language": "typescript",
    "analyzed_files": ["dashboard/index.tsx", "dashboard/layout.tsx"],
    "execution_plan": {
      "steps": [
        {
          "file": "dashboard/index.tsx",
          "command": "renameSymbol",
          "description": "Rename Sidebar to NewSidebar",
          "params": {"from": "Sidebar", "to": "NewSidebar"}
        }
      ]
    },
    "estimated_changes": 3,
    "complexity": "medium"
  }
}
```

**Usage:** Display execution plan preview before applying changes.

---

### 3. `fileStart` - File Processing

```json
{
  "event": "fileStart",
  "data": {
    "file": "dashboard/index.tsx", 
    "command": "renameSymbol",
    "description": "Rename Sidebar to NewSidebar",
    "progress": 0.33
  }
}
```

**Usage:** Show which file is currently being processed.

---

### 4. `fileASTEdit` - AST Transformation Result

```json
{
  "event": "fileASTEdit",
  "data": {
    "file": "dashboard/index.tsx",
    "command": "renameSymbol", 
    "before": "import { Sidebar } from '../components';",
    "after": "import { NewSidebar } from '../components';",
    "description": "Rename Sidebar to NewSidebar",
    "success": true
  }
}
```

**Usage:** Show before/after code preview for each transformation.

---

### 5. `diffChunk` - Unified Diff Streaming

```json
{
  "event": "diffChunk",
  "data": {
    "file": "dashboard/index.tsx",
    "description": "Rename Sidebar to NewSidebar", 
    "diff": "@@ -1,3 +1,3 @@\n-import { Sidebar } from '../components';\n+import { NewSidebar } from '../components';\n",
    "change_summary": {
      "lines_added": 1,
      "lines_removed": 1,
      "lines_modified": 1
    },
    "change_type": "modify"
  }
}
```

**Usage:** Display Git-style diffs in expandable sections.

---

### 6. `issue` - Issues and Suggestions

```json
{
  "event": "issue",
  "data": {
    "type": "warning|error|suggestion",
    "file": "dashboard/layout.tsx",
    "message": "Could not find symbol 'OldComponent' to rename",
    "severity": "warning",
    "line": 15,
    "column": 8
  }
}
```

**Usage:** Show warnings and errors in problems panel.

---

### 7. `patchBundle` - Final Patch

```json
{
  "event": "patchBundle",
  "data": {
    "files": [
      {
        "path": "dashboard/index.tsx",
        "change_type": "modify",
        "description": "Rename Sidebar to NewSidebar",
        "diff": "@@ -1,3 +1,3 @@...",
        "change_summary": {
          "lines_added": 1,
          "lines_removed": 1
        }
      }
    ],
    "statistics": {
      "lines": {"added": 5, "removed": 3, "net_change": 2},
      "files": {"new": 0, "modified": 2, "deleted": 0, "total_changed": 2},
      "impact": "medium"
    },
    "dry_run": false,
    "ready_to_apply": true
  }
}
```

**Usage:** Show complete patch summary with apply/cancel buttons.

---

### 8. `done` - Completion

```json
{
  "event": "done",
  "data": {
    "success": true,
    "execution_time": 5.42,
    "files_transformed": 3,
    "patches_generated": 2, 
    "diffs_created": 2,
    "dry_run": false,
    "message": "🎉 Refactor completed successfully!"
  }
}
```

**Usage:** Show completion status and cleanup UI.

---

### 9. `error` - Error Handling

```json
{
  "event": "error",
  "data": {
    "message": "File not found: dashboard/missing.tsx",
    "type": "FileNotFoundError",
    "stage": "transforming",
    "traceback": "..."
  }
}
```

**Usage:** Display error messages and allow retry.

---

## 🚀 **Frontend Integration Example**

### TypeScript SSE Client

```typescript
class RefactorSSEClient {
  private eventSource: EventSource | null = null;
  
  async startRefactor(request: RefactorRequest) {
    const response = await fetch('/api/refactor/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(request)
    });
    
    this.eventSource = new EventSource(response.url);
    
    // Listen for all event types
    this.eventSource.addEventListener('liveProgress', (e) => {
      const data = JSON.parse(e.data);
      this.updateProgressBar(data.progress, data.message);
    });
    
    this.eventSource.addEventListener('refactorPlan', (e) => {
      const data = JSON.parse(e.data);
      this.showExecutionPlan(data);
    });
    
    this.eventSource.addEventListener('fileStart', (e) => {
      const data = JSON.parse(e.data);
      this.highlightCurrentFile(data.file);
    });
    
    this.eventSource.addEventListener('fileASTEdit', (e) => {
      const data = JSON.parse(e.data);
      this.showBeforeAfter(data.file, data.before, data.after);
    });
    
    this.eventSource.addEventListener('diffChunk', (e) => {
      const data = JSON.parse(e.data);
      this.renderDiff(data.file, data.diff);
    });
    
    this.eventSource.addEventListener('patchBundle', (e) => {
      const data = JSON.parse(e.data);
      this.showPatchSummary(data);
    });
    
    this.eventSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      this.handleCompletion(data);
      this.eventSource?.close();
    });
    
    this.eventSource.addEventListener('error', (e) => {
      const data = JSON.parse(e.data);
      this.handleError(data);
    });
  }
}
```

---

## 🎯 **Key Features Enabled**

### ✅ **Cursor AI Edit Style**
- Live progress bar with descriptive messages
- File-by-file transformation streaming
- Real-time diff preview
- Expandable diff sections

### ✅ **Replit Agent Style** 
- Step-by-step execution timeline
- Before/after code comparisons
- Issue detection and reporting
- Safe rollback capabilities

### ✅ **VS Code Integration**
- WorkspaceEdit compatibility
- Problems panel integration
- Progress notifications
- Diff view rendering

### ✅ **Enterprise Safety**
- Atomic operations with rollback
- Backup management
- Error recovery
- Validation before application

---

This SSE streaming system transforms Navi into a **production-grade autonomous refactoring engine** that matches the experience of industry-leading AI coding assistants! 🚀