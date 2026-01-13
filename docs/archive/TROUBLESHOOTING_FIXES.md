# NAVI Troubleshooting & Fixes

## Current Issues

### 🔴 Issue 1: Backend Not Starting (fetch failed)

**Problem**: Backend process runs but doesn't listen on port 8787
```
TypeError: fetch failed
Failed to connect to localhost port 8787 after 10112 ms
```

**Root Cause**: Backend initialization hanging (likely database/import issues)

**Logs Show**:
- Process PID exists: ✅
- Port 8787 listening: ❌
- Import hangs on `from backend.api.main import app`

**Quick Fix**:

```bash
# 1. Kill all backend processes
pkill -9 -f "uvicorn"
pkill -9 -f "python.*backend"

# 2. Create minimal .env
cd backend
cat > .env << 'EOF'
DEBUG=true
ENVIRONMENT=development
DATABASE_URL=sqlite:///./dev.db
API_BASE_URL=http://localhost:8787
OPENAI_API_KEY=your-key-here
EOF

# 3. Start with simpler command (no reload)
cd ..
PYTHONPATH=. python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8787
```

**Alternative**: Check what's blocking:
```bash
# Test database connection
cd backend
python3 -c "from core.db import engine; print('DB OK')"

# Test imports one by one
python3 -c "from api import main; print('Import OK')"
```

---

### 🟡 Issue 2: Unwanted Context Attachment

**Problem**: Extension auto-attaches currently open file for all questions

**Console Shows**:
```
[AEP] Auto-attached editor context: {
  attachments: Array(1),
  summary: 'Using whole file `components/LoginForm.js` as context.'
}
```

**User Asked**: "Hello, can you explain async/await in JavaScript?"
**System Attached**: `components/LoginForm.js` (completely unrelated!)

**Root Cause**: Extension logic in `extension.js` line ~5049

**Where the Code Is**:
```typescript
// In extensions/vscode-aep/src/extension.ts (or similar)
// Around the handleSmartRouting or message processing

// CURRENT BEHAVIOR (BAD):
const activeEditor = vscode.window.activeTextEditor;
if (activeEditor) {
  // Auto-attach active file - ALWAYS HAPPENS
  attachments.push({
    type: 'file',
    path: activeEditor.document.fileName,
    content: activeEditor.document.getText()
  });
}
```

**Fix Needed**:
```typescript
// BETTER BEHAVIOR:
const activeEditor = vscode.window.activeTextEditor;

// Only attach if user explicitly mentions "this file" or similar
const mentionsCurrentFile = /\b(this file|current file|this code|here)\b/i.test(userMessage);

// OR only attach if the question seems code-specific
const isCodeQuestion = await classifyAsCodeQuestion(userMessage);

if (activeEditor && (mentionsCurrentFile || isCodeQuestion)) {
  attachments.push({
    type: 'file',
    path: activeEditor.document.fileName,
    content: activeEditor.document.getText()
  });

  summary = `Using whole file \`${path.basename(activeEditor.document.fileName)}\` as context.`;
} else {
  summary = 'No file context attached (general question).';
}
```

**Files to Check**:
1. `extensions/vscode-aep/src/extension.ts` - Main extension logic
2. Look for: `activeTextEditor`, `Auto-attached editor context`
3. Search for: `handleSmartRouting` or similar message handlers

---

## Immediate Actions

### Step 1: Fix Backend Startup

**Option A - Minimal Start (Recommended)**:
```bash
# Kill everything
pkill -9 python3

# Set required env vars
export PYTHONPATH=/Users/mounikakapa/Desktop/Personal\ Projects/autonomous-engineering-platform
export DATABASE_URL=sqlite:///./dev.db
export DEBUG=true

# Start without reload (faster)
cd "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8787
```

**Option B - Check Dependencies**:
```bash
cd backend
pip list | grep -E "fastapi|uvicorn|sqlalchemy"

# If missing:
pip install fastapi uvicorn sqlalchemy
```

**Option C - Skip Database Init**:
Look for database initialization in `backend/api/main.py` or `backend/core/db.py` and add try/except to skip if not configured.

### Step 2: Disable Auto-Attach

**Quick Fix (Temporary)**:
Find where attachments are added in the extension and comment it out:

```typescript
// extensions/vscode-aep/src/extension.ts

// COMMENT THIS OUT:
/*
if (activeEditor) {
  attachments.push({
    type: 'file',
    path: activeEditor.document.fileName,
    content: activeEditor.document.getText()
  });
}
*/

// ADD THIS INSTEAD:
if (activeEditor && userMessage.includes('this file')) {
  // Only attach if explicitly requested
  attachments.push({
    type: 'file',
    path: activeEditor.document.fileName,
    content: activeEditor.document.getText()
  });
}
```

Then rebuild:
```bash
cd extensions/vscode-aep/webview
npm run build

cd ../
npm run compile  # or tsc

# Reload VS Code
```

---

## Testing After Fixes

### Test 1: Backend Health
```bash
curl http://localhost:8787/health
# Expected: {"status":"ok"} or similar
```

### Test 2: Backend API Docs
Open: http://localhost:8787/docs
Should load Swagger UI

### Test 3: NAVI Chat (No Auto-Attach)
1. Open a random file (e.g., LoginForm.js)
2. Ask: "What is async/await in JavaScript?"
3. Check console - should NOT see "Auto-attached editor context"
4. Should get response about async/await (not about LoginForm)

### Test 4: NAVI Chat (With Explicit Context)
1. Open a file
2. Ask: "Explain this file"
3. Should attach the file
4. Should get explanation of that specific file

---

## Root Cause Summary

| Issue | Cause | Fix Complexity |
|-------|-------|----------------|
| Backend not starting | Slow imports/DB init | Medium - Need to debug startup |
| Auto-attach unwanted context | Overeager attachment logic | Easy - Add condition check |
| fetch failed errors | Backend not listening | Depends on fixing startup |

---

## Quick Wins

1. **Simplify backend startup** - Remove database if not needed for chat
2. **Make context attachment opt-in** - Only attach when explicitly asked
3. **Add timeout to backend init** - Fail fast if DB/imports take >10s
4. **Better error messages** - Tell user "backend not ready" instead of "fetch failed"

---

## Files to Edit

### Backend:
1. `backend/core/db.py` - Make DB optional or add timeout
2. `backend/api/main.py` - Add startup logging
3. `backend/.env` - Create with minimal config

### Extension:
1. `extensions/vscode-aep/src/extension.ts` - Fix auto-attach logic
2. Search for `Auto-attached editor context` in codebase
3. Look for `activeTextEditor` usage

---

## Next Steps

1. ✅ Identify slow import in backend
2. ✅ Add conditional check to context attachment
3. ✅ Test with general question (no file context)
4. ✅ Test with specific question (with file context)
5. ✅ Document expected behavior

**Status**: Ready for implementation
