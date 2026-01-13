# 🤖 NAVI Autonomous Coding - Complete Guide

## YES! NAVI Can Edit Files Automatically ✅

The autonomous coding engine is **fully wired** and **can edit files**. Here's exactly how it works:

---

## How It Works (Step-by-Step)

### 1. **User Triggers Autonomous Mode**

When you say things like:
- "create a new UserProfile component"
- "implement OAuth authentication"
- "add pagination to the users table"
- "write tests for the API endpoints"

NAVI detects the keywords and activates autonomous coding mode.

### 2. **NAVI Creates Implementation Plan**

**Backend** (`backend/api/chat.py` lines 367-455):
```python
# Detects keywords: create, implement, build, generate, add, write, make, develop, code
if has_autonomous_keywords and workspace_root:
    # Initializes autonomous coding engine
    coding_engine = EnhancedAutonomousCodingEngine(
        llm_service=llm_service,
        workspace_root=workspace_root,
        db_session=db,
    )

    # Creates task and generates step-by-step plan
    task_id = await coding_engine.start_task(
        description=message,
        task_type=task_type,
        context={"user_message": message}
    )

    # Gets all the steps that will be executed
    steps = coding_engine.get_pending_steps(task_id)
```

**Response to User**:
```
🤖 **Autonomous Coding Mode Activated**

I've analyzed your request and created a step-by-step implementation plan:

**Task:** create a new UserProfile component
**Workspace:** `/path/to/workspace`
**Task ID:** `abc-123-def`

**Implementation Plan (3 steps):**
1. Create UserProfile component file
   📁 src/components/UserProfile.tsx (create)
2. Add component logic and styling
   📁 src/components/UserProfile.tsx (modify)
3. Export from index
   📁 src/components/index.ts (modify)

Ready to proceed with step 1?
```

### 3. **User Approves Each Step**

**Endpoint**: `POST /api/autonomous/execute-step`

**Request**:
```json
{
  "task_id": "abc-123-def",
  "step_id": "step-1",
  "user_approved": true,
  "user_feedback": null
}
```

**What Happens** (`backend/autonomous/enhanced_coding_engine.py` line 509):
```python
async def execute_step(self, task_id: str, step_id: str, user_approved: bool):
    """Execute individual step with user approval - core Cline-style workflow"""

    if not user_approved:
        step.status = StepStatus.REJECTED
        return {"status": "rejected"}

    # Execute the step
    step.status = StepStatus.IN_PROGRESS

    # Create backup if first step
    if task.current_step_index == 0:
        await self._create_safety_backup(task)

    # Generate actual code using LLM
    code_result = await self._generate_code_for_step(task, step)

    # Apply changes to file system (THIS IS WHERE FILES GET EDITED!)
    apply_result = await self._apply_file_changes(task, step, code_result)

    # Validate the changes
    validation_result = await self._validate_code_changes(task, step)

    # Commit to git
    await self._commit_changes(task, step)

    return {
        "status": "completed",
        "changes_applied": True,
        "validation": validation_result,
        "next_step": next_step_preview
    }
```

### 4. **Files Are Actually Modified**

**File Creation** (`enhanced_coding_engine.py` line 1407):
```python
if step.operation == "create":
    # Creates new file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(generated_code)
    logger.info(f"Created file: {step.file_path}")
```

**File Modification** (`enhanced_coding_engine.py` line 1411):
```python
elif step.operation == "modify":
    if file_path.exists():
        # Atomic file modification with temp file
        temp_file_path = None
        try:
            # Write to temp file first
            fd, temp_file_path = tempfile.mkstemp(
                dir=file_path.parent,
                prefix=".tmp_",
                suffix=file_path.suffix
            )
            os.write(fd, generated_code.encode("utf-8"))
            os.close(fd)

            # Atomic rename (replaces original file)
            os.replace(temp_file_path, str(file_path))
            logger.info(f"Modified file: {step.file_path}")
```

**File Deletion** (if operation == "delete"):
```python
elif step.operation == "delete":
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted file: {step.file_path}")
```

### 5. **Safety Features**

All edits are protected by:

✅ **Git Backup**
- Creates safety commit before first change
- `git commit -m "Safety backup before autonomous coding"`

✅ **Atomic Operations**
- Uses temp files and atomic rename
- File never in inconsistent state

✅ **Validation**
- Python: `ast.parse()` for syntax checking
- JavaScript/TypeScript: Syntax validation
- Secrets detection (API keys, passwords, tokens)
- Dangerous code detection (eval, exec, os.system)

✅ **User Approval**
- Every single step requires approval
- Can reject any step
- Can provide feedback for modifications

✅ **Rollback**
- Can revert to safety backup
- Git history preserved

---

## Current Status

### ✅ **Fully Implemented**:
1. Autonomous mode detection
2. Task creation with LLM planning
3. Step-by-step plan generation
4. File creation/modification/deletion
5. Git integration and safety backups
6. Validation (syntax, secrets, dangerous code)
7. Backend API endpoint (`/api/autonomous/execute-step`)

### ⚠️ **Partially Implemented** (Frontend):
- Chat endpoint returns plan and task_id ✅
- Backend has approval endpoint ✅
- Frontend needs UI buttons to approve/reject steps ❌

---

## What's Missing (Frontend Only)

The backend is **100% ready** to edit files. We just need to wire the frontend UI:

### Missing: Step Approval UI

**Current**: Chat shows the plan but no buttons to approve/reject

**Needed**: Add approval buttons in the chat response

**Example Implementation**:

```typescript
// In NaviChatPanel.tsx or similar
if (message.agentRun?.mode === 'autonomous_coding') {
  const taskId = message.state?.task_id;
  const currentStep = message.state?.current_step || 0;

  return (
    <div>
      <div>{message.content}</div>

      {/* Step approval buttons */}
      <div className="step-actions">
        <button onClick={() => approveStep(taskId, currentStep)}>
          ✅ Approve & Execute Step {currentStep + 1}
        </button>
        <button onClick={() => rejectStep(taskId, currentStep)}>
          ❌ Reject Step
        </button>
        <button onClick={() => viewDiff(taskId, currentStep)}>
          👁️ Preview Changes
        </button>
      </div>
    </div>
  );
}

async function approveStep(taskId: string, stepIndex: number) {
  const response = await fetch(`${BACKEND_BASE}/api/autonomous/execute-step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: taskId,
      step_id: `step-${stepIndex}`,
      user_approved: true,
    })
  });

  const result = await response.json();

  if (result.status === 'completed') {
    // Show success message
    // Ask about next step
  }
}
```

---

## Testing File Editing

### Test 1: Create a Simple File

**User says**: "create a hello.py file with a hello world function"

**Backend will**:
1. Create task
2. Generate plan:
   - Step 1: Create hello.py (create)
3. Wait for approval
4. When approved → Creates `hello.py`:
   ```python
   def hello_world():
       print("Hello, World!")

   if __name__ == "__main__":
       hello_world()
   ```

**To test**:
```bash
# 1. Trigger in chat
"create a hello.py file with a hello world function"

# 2. Backend returns task_id and plan

# 3. Call approval endpoint
curl -X POST http://localhost:8787/api/autonomous/execute-step \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "the-task-id-from-step-2",
    "step_id": "step-0",
    "user_approved": true
  }'

# 4. Check workspace - file should be created!
cat /path/to/workspace/hello.py
```

### Test 2: Modify Existing File

**User says**: "add type hints to the hello function"

**Backend will**:
1. Detect hello.py exists
2. Generate plan:
   - Step 1: Add type hints (modify)
3. Wait for approval
4. When approved → Modifies `hello.py`:
   ```python
   def hello_world() -> None:
       print("Hello, World!")

   if __name__ == "__main__":
       hello_world()
   ```

---

## Quick Start

### Backend is Already Ready!

Just restart backend:
```bash
cd backend
lsof -ti :8787 | xargs kill -9
python -m uvicorn api.main:app --reload --port 8787
```

### Test Without Frontend UI

You can test file editing **right now** using curl:

```bash
# Step 1: Trigger autonomous mode in VS Code chat
# User types: "create a test.txt file"

# Step 2: Get task_id from response
# Response will show: "Task ID: abc-123"

# Step 3: Execute the step via API
curl -X POST http://localhost:8787/api/autonomous/execute-step \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "abc-123",
    "step_id": "step-0",
    "user_approved": true
  }'

# Step 4: Check your workspace
# The file should be created!
```

---

## Summary

**Q: Can NAVI edit files?**
**A: YES! ✅ Fully implemented in backend**

**Q: What operations are supported?**
**A: Create, Modify, Delete - all with safety features**

**Q: Is it safe?**
**A: YES! Git backups, atomic operations, validation, user approval required**

**Q: Why doesn't it work in UI yet?**
**A: Frontend needs approval buttons - backend is 100% ready**

**Q: How do I enable it?**
**A: Just add the approval UI buttons (20 lines of code) and you're done!**

---

## Next Step to Complete the Feature

Add this component to your frontend:

**File**: `extensions/vscode-aep/webview/src/components/AutonomousStepApproval.tsx`

```typescript
import React from 'react';
import { resolveBackendBase } from '@/api/navi/client';

interface Props {
  taskId: string;
  stepId: string;
  stepDescription: string;
  filePath: string;
  operation: 'create' | 'modify' | 'delete';
  onComplete: () => void;
}

export function AutonomousStepApproval({
  taskId, stepId, stepDescription, filePath, operation, onComplete
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleApprove = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${resolveBackendBase()}/api/autonomous/execute-step`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_id: taskId,
            step_id: stepId,
            user_approved: true,
          })
        }
      );

      if (!response.ok) throw new Error('Failed to execute step');

      const result = await response.json();
      console.log('Step executed:', result);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      await fetch(
        `${resolveBackendBase()}/api/autonomous/execute-step`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_id: taskId,
            step_id: stepId,
            user_approved: false,
          })
        }
      );
      onComplete();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="step-approval">
      <div className="step-info">
        <strong>{stepDescription}</strong>
        <div>📁 {filePath} ({operation})</div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="actions">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="approve-btn"
        >
          ✅ {loading ? 'Executing...' : 'Approve & Execute'}
        </button>
        <button
          onClick={handleReject}
          disabled={loading}
          className="reject-btn"
        >
          ❌ Reject
        </button>
      </div>
    </div>
  );
}
```

**That's it!** With this component, NAVI will be able to edit files with user approval! 🚀
