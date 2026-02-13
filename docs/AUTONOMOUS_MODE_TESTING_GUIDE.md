# Autonomous Mode Testing Guide

**Status:** ✅ Fixed and ready for testing
**Date:** 2026-02-09

---

## Quick Start

### 1. Start the Backend

```bash
cd backend
python -m uvicorn api.main:app --reload --port 8000
```

**Verify it's running:**
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

### 2. Start VS Code Extension

1. Open VS Code in the project root
2. Press **F5** to launch Extension Development Host
3. In the new window, open NAVI chat panel (View → NAVI Chat)

### 3. Select Agent Mode

In the NAVI chat panel:
1. Look for the **mode selector** (should show "Agent", "Plan", "Ask", "Edit")
2. Ensure **"Agent"** mode is selected (should be default)

### 4. Send a Test Message

Try one of these simple test messages:

**Test 1: List Files**
```
Can you list all the Python files in the backend directory?
```

**Test 2: Check File Count**
```
How many TypeScript files are in the extensions/vscode-aep/webview/src directory?
```

**Test 3: Find Imports**
```
Find all files that import 'useState' from React
```

---

## Expected Behavior

### ✅ Success Indicators

When autonomous mode is working correctly, you should see:

1. **Immediate Response** (within 100ms)
   - No infinite "Thinking..." state
   - Status updates start appearing immediately

2. **Real-time Streaming Updates**
   ```
   **planning**: Analyzing task requirements...

   I'll help you list all Python files in the backend directory...

   🔧 list_files: Listing files in backend/
   ✓ Found 45 Python files

   ✅ Verification: All checks passed

   Successfully listed 45 Python files in the backend directory.
   ```

3. **Progressive Updates**
   - See each step as it happens
   - Tool calls with 🔧 icon
   - Results with ✓ checkmark
   - Verification with ✅ emoji

4. **Clean Completion**
   - Final summary message
   - No errors or timeout
   - Chat ready for next message

### ❌ Failure Indicators

If you see these, autonomous mode is still broken:

1. **Infinite "Thinking..."**
   - Message sent but no response
   - Status stuck on "Thinking..."
   - No streaming updates

2. **Immediate Error**
   - "Request failed: 404" or "Request failed: 500"
   - "No response body for streaming"
   - Network errors in console

3. **Partial Response**
   - Response starts but cuts off
   - Missing final summary
   - Connection drops mid-stream

---

## Detailed Test Cases

### Test Case 1: Simple File Listing

**Input:**
```
List all Python files in the backend/api directory
```

**Expected Output:**
```
**planning**: Analyzing task requirements...

I'll list all Python files in the backend/api directory for you.

🔧 list_files: Listing files in backend/api/
✓ Found 12 Python files

Files found:
- backend/api/__init__.py
- backend/api/main.py
- backend/api/navi.py
- backend/api/chat.py
- backend/api/routes/agent.py
- backend/api/routers/autonomous_coding.py
- ... (and more)

✅ Verification: All files verified

Successfully listed 12 Python files in backend/api/
```

**Success Criteria:**
- [ ] Response starts within 1 second
- [ ] See **planning** status
- [ ] See 🔧 tool_call for list_files
- [ ] See ✓ tool_result with count
- [ ] See ✅ verification
- [ ] See final summary
- [ ] Total time: 5-15 seconds

---

### Test Case 2: Code Search

**Input:**
```
Find all files that use FastAPI decorators
```

**Expected Output:**
```
**planning**: Analyzing search requirements...

I'll search for files using FastAPI decorators like @app.get, @app.post, etc.

🔧 search_code: Searching for "@app\." pattern
✓ Found 8 matches in 5 files

🔧 search_code: Searching for "@router\." pattern
✓ Found 23 matches in 7 files

Results:
- backend/api/main.py: 3 decorators
- backend/api/navi.py: 12 decorators
- backend/api/routes/agent.py: 5 decorators
- ... (and more)

✅ Verification: Search completed successfully

Found 31 FastAPI decorators across 12 files.
```

**Success Criteria:**
- [ ] Multiple tool calls shown
- [ ] Each tool call has a ✓ result
- [ ] Results are summarized clearly
- [ ] Verification passes

---

### Test Case 3: Error Handling

**Input:**
```
List files in /nonexistent/directory
```

**Expected Output:**
```
**planning**: Analyzing task requirements...

I'll attempt to list files in /nonexistent/directory.

🔧 list_files: Listing files in /nonexistent/directory
❌ Error: Directory does not exist

**fixing**: Attempting to recover...

I couldn't access that directory. It appears the path /nonexistent/directory doesn't exist.

Would you like me to:
1. List available directories?
2. Try a different path?
```

**Success Criteria:**
- [ ] Error is caught and handled gracefully
- [ ] Agent attempts to fix or provide alternatives
- [ ] No infinite loop or crash
- [ ] User-friendly error message

---

### Test Case 4: Multi-step Task

**Input:**
```
Create a new file called test.txt in the root directory with the content "Hello World"
```

**Expected Output:**
```
**planning**: Planning file creation...

I'll create a new file test.txt with the content "Hello World".

🔧 write_file: Creating test.txt
✓ File created successfully

🔧 read_file: Verifying file content
✓ Content verified: "Hello World"

✅ Verification: File created and verified

Successfully created test.txt with content "Hello World".
```

**Success Criteria:**
- [ ] Multiple tool calls in sequence
- [ ] Each step completes before next
- [ ] Verification confirms success
- [ ] File actually created (check manually)

---

## Debugging

### Check Browser Console

Open browser DevTools (F12) and look for:

**Good signs:**
```
[NAVI] Sending request to: http://localhost:8000/api/navi/chat/autonomous
[NAVI] Mode: agent Streaming: true
[NAVI] Request body: {message: "...", model: "...", workspace_root: "..."}
[NAVI] Heartbeat received
```

**Bad signs:**
```
[NAVI] Failed to parse SSE data: ...
[NAVI] Stream error: Network error
[NAVI] Request failed: 404
```

### Check Network Tab

1. Open DevTools → Network tab
2. Send a message in NAVI chat
3. Look for request to `/api/navi/chat/autonomous`

**Verify:**
- [ ] Request is POST
- [ ] Content-Type: application/json
- [ ] Response Type: text/event-stream
- [ ] Status: 200 OK
- [ ] Response body shows streaming events

### Check Backend Logs

In the terminal running the backend, look for:

**Good signs:**
```
INFO:     POST /api/navi/chat/autonomous
[NAVI Autonomous] Endpoint called - Message: List all Python...
[NAVI Autonomous] Provider: openai, Model: gpt-4o
[NAVI Autonomous] Creating agent with workspace: /path/to/workspace
```

**Bad signs:**
```
ERROR:    Exception in ASGI application
ValueError: No workspace_root provided
KeyError: 'message'
```

### Common Issues

#### Issue 1: Workspace Root Not Found

**Symptom:** Agent can't access files or returns empty results

**Solution:**
1. Check if workspaceRoot is passed to useNaviChat hook
2. Verify WorkspaceContext is providing the correct path
3. Console log should show: `workspace_root: "/path/to/workspace"`

**Fix:**
```typescript
// In NaviChatPanel.tsx
const { workspaceRoot } = useWorkspace();
const naviChat = useNaviChat({
  selectedTask,
  userName,
  workspaceRoot,  // ✅ Make sure this is passed
});
```

#### Issue 2: Still Using Old Endpoint

**Symptom:** Request goes to `/api/navi/chat` instead of `/api/navi/chat/autonomous`

**Solution:**
1. Check browser console for "Sending request to:" message
2. Should show `/api/navi/chat/autonomous` for agent mode
3. Verify mode selector shows "Agent"

**Fix:** Clear browser cache and hard reload (Ctrl+Shift+R)

#### Issue 3: Events Not Displaying

**Symptom:** Backend is working but no updates in UI

**Solution:**
1. Check if `onDelta` callback is being called
2. Verify event handler is parsing all event types
3. Look for console warnings about parse errors

**Fix:**
```typescript
// Add debug logging
console.log('[NAVI] Event type:', parsed.type);
console.log('[NAVI] Event data:', parsed);
```

#### Issue 4: Connection Timeout

**Symptom:** Stream starts but disconnects after 30-60 seconds

**Solution:**
1. Backend sends heartbeat every 10 seconds to prevent timeout
2. Check if heartbeat events are being received
3. Verify proxy/nginx timeout settings

**Fix:** Backend already handles this with heartbeat_wrapper

---

## Performance Benchmarks

### Expected Timings

| Task | Time | Description |
|------|------|-------------|
| Time to first event | <100ms | Initial status update |
| Time to first tool call | 1-3s | LLM planning complete |
| Tool execution | 0.1-2s | Per tool |
| Verification | 0.5-5s | Depends on tests |
| Total completion | 5-30s | Varies by complexity |

### Test Performance

Run this script to measure performance:

```bash
#!/bin/bash
# test_autonomous_performance.sh

echo "Testing autonomous mode performance..."
START=$(date +%s)

curl -N -X POST http://localhost:8000/api/navi/chat/autonomous \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List Python files in backend/",
    "model": "openai/gpt-4o",
    "workspace_root": "'$(pwd)'",
    "run_verification": true
  }' | while IFS= read -r line; do
    if [[ $line == data:* ]]; then
      CURRENT=$(date +%s)
      ELAPSED=$((CURRENT - START))
      echo "[$ELAPSED s] $line"
    fi
  done

END=$(date +%s)
TOTAL=$((END - START))
echo "Total time: ${TOTAL}s"
```

Run:
```bash
chmod +x test_autonomous_performance.sh
./test_autonomous_performance.sh
```

---

## Manual Testing Checklist

### Pre-flight Check
- [ ] Backend running on port 8000
- [ ] VS Code extension launched
- [ ] NAVI chat panel open
- [ ] Agent mode selected
- [ ] Browser console open (F12)

### Basic Functionality
- [ ] Send message → get immediate response
- [ ] See streaming updates in real-time
- [ ] Tool calls displayed with 🔧 icon
- [ ] Results displayed with ✓ checkmark
- [ ] Verification displayed with ✅ emoji
- [ ] Final summary appears
- [ ] Can send follow-up message

### Edge Cases
- [ ] Empty message → shows error
- [ ] Very long message → handles gracefully
- [ ] Invalid workspace → shows error
- [ ] Network disconnect → reconnects or shows error
- [ ] Cancel during execution → stops cleanly

### Performance
- [ ] First response within 1 second
- [ ] No UI freezing or lag
- [ ] Smooth scrolling during updates
- [ ] Memory usage stable (<500MB)

### Error Handling
- [ ] Backend down → shows connection error
- [ ] Invalid model → shows error
- [ ] Tool failure → agent recovers
- [ ] Verification failure → agent retries

---

## Automated Testing

### Unit Tests (Future)

```typescript
// tests/autonomous-mode.test.ts

describe('Autonomous Mode Streaming', () => {
  it('should stream events in correct order', async () => {
    const events: string[] = [];

    await streamAutonomousRequest({
      message: 'test',
      onEvent: (event) => events.push(event.type)
    });

    expect(events).toEqual([
      'status',  // planning
      'text',    // narrative
      'tool_call',
      'tool_result',
      'verification',
      'complete'
    ]);
  });

  it('should handle errors gracefully', async () => {
    const error = await streamAutonomousRequest({
      message: 'invalid request'
    });

    expect(error.type).toBe('error');
    expect(error.message).toBeDefined();
  });
});
```

### Integration Tests

```bash
# tests/integration/test_autonomous.sh

# Test 1: Basic request
echo "Test 1: Basic request"
curl -X POST http://localhost:8000/api/navi/chat/autonomous \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "model": "openai/gpt-4o", "workspace_root": "/tmp"}' \
  | grep -q "planning" && echo "✅ PASS" || echo "❌ FAIL"

# Test 2: Invalid request
echo "Test 2: Invalid request"
curl -X POST http://localhost:8000/api/navi/chat/autonomous \
  -H "Content-Type: application/json" \
  -d '{}' \
  | grep -q "error" && echo "✅ PASS" || echo "❌ FAIL"
```

---

## Success Criteria

Autonomous mode is considered **fully working** when:

1. ✅ No infinite "Thinking..." state
2. ✅ Real-time streaming updates appear
3. ✅ All event types display correctly (status, text, tool_call, etc.)
4. ✅ Icons display (🔧, ✓, ✅)
5. ✅ Errors handled gracefully
6. ✅ Can send multiple messages in sequence
7. ✅ Performance is acceptable (first response <1s)
8. ✅ No console errors or warnings
9. ✅ Backend logs show successful processing
10. ✅ Network tab shows 200 OK with event-stream

---

## Next Steps After Testing

Once autonomous mode is working:

1. **Test with real tasks**
   - Create components
   - Fix bugs
   - Add features
   - Run tests

2. **Measure user satisfaction**
   - Collect feedback
   - Track completion rates
   - Monitor error rates

3. **Optimize performance**
   - Reduce latency
   - Improve tool selection
   - Better caching

4. **Add features**
   - Multi-turn conversations
   - Context awareness
   - Better verification

5. **Deploy to production**
   - Staging environment first
   - A/B test with users
   - Monitor metrics
   - Gradual rollout

---

## Support

If you encounter issues:

1. **Check this guide** - Follow all debugging steps
2. **Check console logs** - Both browser and backend
3. **Review recent commits** - `git log --oneline`
4. **Check documentation** - [AUTONOMOUS_MODE_FIX.md](AUTONOMOUS_MODE_FIX.md)
5. **Ask for help** - Provide logs and screenshots

---

**Happy Testing! 🚀**

The autonomous mode should now work perfectly with real-time streaming updates.
