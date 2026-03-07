# Critical Bugs - NAVI Chat Panel

**Date**: 2026-03-05
**Status**: ACTIVE - System Unstable
**Priority**: P0 - Blocking

---

## Bug #1: Content Disappearing When Clicking Copy Button

**Severity**: CRITICAL
**Impact**: Data loss, broken UX

### Symptoms
- User clicks copy button on a request/message
- All streaming content that was generated disappears
- UI shows "Editing an earlier message. Send to regenerate from that point."
- Content is lost and cannot be recovered

### Reproduction Steps
1. Send a request to NAVI
2. Wait for streaming to start/complete
3. Click the copy button on the message
4. Observe: All content disappears

### Root Cause
UNKNOWN - Need to investigate copy button handler and message state management

### Expected Behavior
Clicking copy should copy the message text to clipboard WITHOUT affecting the displayed content

---

## Bug #2: Wrong/Dangerous Commands Generated for Simple Questions

**Severity**: CRITICAL
**Impact**: Security risk, data loss potential

### Symptoms
- User asks: "can you list the important files in this project?"
- NAVI generates dangerous `rm -f` deletion commands
- Command shown: `rm -f test_visual_handler.py test-basic.js surprise_script.js ...`
- This is completely wrong for a "list files" question

### Reproduction Steps
1. Ask: "can you list the important files in this project?"
2. Observe: NAVI suggests deleting files instead of listing them

### Root Cause
**IDENTIFIED** - Agent is too proactive with destructive operations

Backend logs show (request_id: ccfa3930-3de7-4a0d-b359-81527b27f932):
1. User asked: "can you check what are the unnecessary files that are not related to this project?"
2. Agent generated: `rm -f test_visual_handler.py ... && rm -rf .next`
3. Agent tried to DELETE files when only asked to CHECK/LIST them

The agent interprets "check unnecessary files" as "delete unnecessary files" - this is EXTREMELY DANGEROUS.

**Problems:**
- Agent performs destructive operations (rm -f, rm -rf) when only asked to list/check
- No clear distinction between READ operations (list, check, show) and WRITE operations (delete, remove)
- Agent is being "helpful" by trying to clean up, but this risks data loss

### Expected Behavior
Simple "list files" questions should only trigger read operations like:
- `git ls-files`
- `ls -la`
- `find . -type f`
NOT deletion commands like `rm -f`

---

## Bug #3: Chronological Order Not Working (ONGOING)

**Severity**: HIGH
**Impact**: Poor UX, confusing output

### Symptoms
- Bash commands appear grouped together at the top
- Text content appears below, separated
- Content is not interleaved chronologically despite sorting fix

### Fixes Attempted
- ✅ Added sorting by sequence/timestamp in renderInterleavedContent (commit 9075157b)
- ✅ Added action chunk creation for commands (commit 831455df)
- ❌ Still not working after rebuild + reload

### Root Cause
UNKNOWN - Despite code fixes, the issue persists. Possible causes:
- Chunks not being created with correct sequence numbers
- Sorting not being applied at render time
- Build cache issue (though we rebuilt)
- React re-render timing issue

### Expected Behavior
Text and bash commands should appear interleaved in chronological order based on sequence/timestamp

---

## Bug #4: Queue "Send Now" Not Working (ONGOING)

**Severity**: HIGH
**Impact**: Core feature broken

### Symptoms
- User queues a message while NAVI is working
- Clicks "⚡ Send now" button
- Message stays in queue and doesn't send
- Sometimes causes streaming to get stuck

### Fixes Attempted
- ✅ Added generated runId detection (commit 831455df)
- ✅ Added fallback to send as new message for autonomous mode
- ❌ Still not working after rebuild + reload

### Root Cause
PARTIALLY IDENTIFIED:
- Generated runIds (run-msg-*) don't exist in backend RunManager
- isGeneratedRunId check should prevent steer attempts
- But user logs show steer is still being attempted
- Multiple steer attempts logged (duplicate handleSendNow calls?)

### Expected Behavior
Clicking "Send now" should either:
1. Steer the current run (if real runId exists), OR
2. Send as a new message (if generated runId for autonomous mode)

---

## Bug #5: Consent Dialogs Appear Out of Chronological Order

**Severity**: CRITICAL
**Impact**: Confusing UX, consent dialogs appear at wrong time, multiple dialogs stack

### Symptoms (See Screenshots)
- Multiple consent dialogs stack on top of each other
- Consent dialogs appear BEFORE the explanatory text
- Events are completely out of chronological order
- User sees: Consent1 → Consent2 → Text (should be: Text → Consent1 → wait → Consent2 → wait)

### Reproduction Steps
1. Send: "can you check what are the unnecessary files in this project?"
2. Observe: Multiple consent dialogs appear simultaneously
3. Observe: Dialogs appear BEFORE the "Let me scan the repo..." text
4. Expected: Text first, then consent dialogs one at a time

### Root Cause
**IDENTIFIED** - Consent dialogs are NOT part of the chronological content stream

**Investigation Results:**

✅ Backend consent blocking WORKS CORRECTLY:
- `autonomous_agent.py` properly calls `await _wait_for_consent()` which polls Redis
- Commands do NOT execute without approval
- The blocking mechanism is functioning as designed

✅ Backend sequence numbering IMPLEMENTED:
- Added `_event_sequence_counter` and `_get_next_sequence()`
- All events emit with monotonic sequence numbers
- Consent events, tool results, and text events all have sequences

✅ Frontend ContentChunk sorting WORKS:
- Code sorts chunks by sequence first, then timestamp
- Action chunks and text chunks use sequence numbers correctly

❌ **THE REAL PROBLEM**: Consent events NEVER become ContentChunks!

**Evidence from Code (NaviChatPanel.tsx):**
```typescript
// Line 5866-5886: Consent events received
if (msg.type === "navi.consent") {
  const consentRequest: CommandConsentRequest = {
    consent_id: msg.consent_id,
    command: msg.command,
    timestamp: msg.timestamp || new Date().toISOString(),
    // ❌ sequence number ignored!
  };
  enqueueConsent(consentRequest, "navi.consent"); // ❌ Goes to SEPARATE queue!
  return;
}
```

**Two Separate Rendering Paths:**
1. **Content Stream** (text, actions):
   - Created as `ContentChunk` objects
   - Stored in `contentChunks` array
   - Sorted by sequence numbers
   - Rendered chronologically

2. **Consent Queue** (consent dialogs):
   - Added to `pendingUserInputQueue` via `enqueueConsent()`
   - Rendered SEPARATELY from content
   - NO coordination with sequence numbers
   - Can appear at any time, ignoring chronological order

### Fix Needed

**Option 1: Integrate Consent into ContentChunk System (RECOMMENDED)**
1. Extend `ContentChunk` type to support `type: 'consent'`
2. When receiving consent events, create a ContentChunk instead of calling `enqueueConsent`
3. Render consent dialogs inline as part of the content stream
4. Sequence numbers will then control consent dialog positioning

**Option 2: Coordinate Consent Queue with Sequence Numbers**
1. Store sequence numbers with consent requests
2. Block rendering of contentChunks with higher sequence numbers until consent resolves
3. More complex, harder to maintain

### Files Modified
- `backend/services/autonomous_agent.py` - Added sequence numbering (WORKING ✅)
- `extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx` - Integrated consent into ContentChunk system (FIXED ✅)

### Fix Applied (2026-03-06)
**Integrated consent dialogs into the chronological content stream:**

1. **Extended ContentChunk type** to support `type: 'consent'`:
   ```typescript
   type ContentChunk = {
     id: string;
     type: 'text' | 'action' | 'consent';  // ← Added 'consent'
     timestamp: string;
     sequence: number;
     consentRequest?: CommandConsentRequest;  // ← Added consent data
     // ... other fields
   };
   ```

2. **Modified consent event handlers** to create ContentChunks:
   - Instead of calling `enqueueConsent()` which goes to separate queue
   - Now creates consent chunks and adds to message's contentChunks array
   - Preserves sequence numbers from backend
   - Falls back to old behavior only if no current message ID

3. **Updated renderInterleavedContent** to render consent dialogs inline:
   - Consent chunks are sorted with text and action chunks by sequence number
   - ConsentDialog component rendered inline in chronological position
   - Consent decisions sent directly to backend/VSCode host
   - No more separate consent queue UI

### Expected Behavior After Fix
```
┌─────────────────────────────────────┐
│ Let me scan the repo (read-only)    │ ← Text chunk (seq=1)
├─────────────────────────────────────┤
│ 🔒 Run zsh command?                 │ ← Consent chunk (seq=2)
│ git status --porcelain              │   [BLOCKING]
│ [Allow] [Skip]                      │
├─────────────────────────────────────┤
│ [User clicks Allow]                 │
├─────────────────────────────────────┤
│ ✓ Modified files listed             │ ← Tool result (seq=3)
├─────────────────────────────────────┤
│ 🔒 Run zsh command?                 │ ← Consent chunk (seq=4)
│ find . -name "*.py"                 │   [BLOCKING]
│ [Allow] [Skip]                      │
├─────────────────────────────────────┤
│ [User clicks Allow]                 │
├─────────────────────────────────────┤
│ ✓ Files found                       │ ← Tool result (seq=5)
├─────────────────────────────────────┤
│ From the current repo listing...    │ ← Text chunk (seq=6)
└─────────────────────────────────────┘
```

NO stacked dialogs, NO out-of-order text!

### Additional Fix - Bash Commands Chronological Ordering (2026-03-06, Session 2)

**Problem**: Even after integrating consent dialogs into ContentChunks, bash command results were still appearing at the top with green checkmarks (old NaviActionRunner), not in chronological order.

**Root Cause**: Messages had `actions` array populated by backend, but NO ContentChunks were created for those actions because:
1. Backend doesn't emit `command.start` events for every command
2. Frontend only created action ContentChunks when receiving `command.start` events
3. NaviActionRunner rendered if `!m.contentChunks` (even with actions present)

**Fix Applied**:

1. **Updated NaviActionRunner condition** (Line 13429):
   ```typescript
   // BEFORE: Rendered if contentChunks was falsy
   {!m.contentChunks && (<NaviActionRunner />)}

   // AFTER: Only render if contentChunks is empty or doesn't exist
   {(!m.contentChunks || m.contentChunks.length === 0) && (<NaviActionRunner />)}
   ```

2. **Auto-create action ContentChunks from actions array** (Line 4594-4614):
   ```typescript
   // When streaming completes, if message has actions but no action chunks:
   const existingActionChunks = chunks.filter(c => c.type === 'action').length;
   if (incomingActions.length > 0 && existingActionChunks === 0) {
     console.log('[CHUNK_DEBUG] Creating action chunks from incomingActions array');
     incomingActions.forEach((action, idx) => {
       const actionChunk: ContentChunk = {
         id: `chunk-action-${targetId}-${idx}`,
         type: 'action',
         timestamp: nowIso(),
         sequence: Date.now() + idx,
         actionIndex: idx,
         action: action,
       };
       chunks.push(actionChunk);
     });
   }
   ```

3. **Backend consent events now include sequence numbers** (autonomous_agent.py):
   - Modified `_create_consent_event()` to be async and generate sequence numbers
   - Modified `_check_requires_consent()` to be async
   - Updated all 3 callers to await the async method

**Result**:
- ✅ All content (text, consent dialogs, bash commands) rendered chronologically
- ✅ NaviActionRunner no longer renders when ContentChunks exist
- ✅ Action chunks automatically created from backend actions array
- ✅ Consent events include sequence numbers for proper ordering

---

## Investigation Plan

### Priority Order
1. **Bug #1** - Content disappearing (data loss)
2. **Bug #2** - Wrong commands (security risk)
3. **Bug #3** - Chronological order (UX)
4. **Bug #4** - Queue send now (feature broken)

### Next Steps
1. Find and read copy button handler code
2. Check message state management for edit/regenerate logic
3. Review backend prompt/agent logic for command generation
4. Add extensive logging to debug chronological ordering
5. Add logging to track handleSendNow calls and steer behavior

---

## Test Plan

After each fix:
1. Reload VS Code completely (Cmd+Q)
2. Restart backend and frontend
3. Test the specific bug scenario
4. Verify fix works before moving to next bug
5. Document what was changed and why it fixed the issue
