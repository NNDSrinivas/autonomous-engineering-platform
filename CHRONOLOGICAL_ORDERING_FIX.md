# Chronological Event Ordering Fix (Bug5)

## Problem
Events (text, commands, results) were displaying out of order in the UI:
- Bash command panel appeared BEFORE explanatory text
- Text chunks appeared without proper spacing ("dry-runscan" instead of "dry-run scan")
- Caused confusing UX where commands appeared before the agent explained what it was doing

## Root Cause
1. **Backend** was sending events without sequence numbers, causing race conditions
2. **Extension** was passing events immediately without buffering/sorting
3. **Webview** was using local sequence counters instead of backend sequence numbers
4. **Text chunks** were not being added to the narrative stream, only to message content

## Solution Architecture

### 1. Backend Changes (`backend/services/autonomous_agent.py`)

**Added sequence counter and generator:**
```python
# Lines 1921-1924
self._event_sequence_counter = 0
self._sequence_lock = asyncio.Lock()

# Lines 1935-1948
async def _get_next_sequence(self) -> int:
    """Generate monotonically increasing sequence numbers for event ordering"""
    async with self._sequence_lock:
        self._event_sequence_counter += 1
        return self._event_sequence_counter
```

**Add sequence to ALL yielded events:**
- Text events (OpenAI: lines ~7690-7732, Anthropic: lines ~7217-7222)
- Tool call events (OpenAI: lines ~7805-7956, Anthropic: lines ~7244-7252)
- Tool result events (lines ~5350-5376, made `_create_tool_result_event` async)

**Example:**
```python
sequence = await self._get_next_sequence()
yield {
    "type": "text",
    "text": text_buffer,
    "timestamp": get_event_timestamp(),
    "sequence": sequence,  # ← Critical for chronological ordering
}
```

### 2. Extension Changes (`extensions/vscode-aep/src/extension.ts`)

**Event buffering system (lines ~9229-9260):**
```typescript
// Buffer events by sequence number
const eventBuffer = new Map<number, any>();
let nextExpectedSequence = 1;

// Flush events in sequence order
const flushSequencedEvents = async () => {
  while (eventBuffer.has(nextExpectedSequence)) {
    const event = eventBuffer.get(nextExpectedSequence)!;
    eventBuffer.delete(nextExpectedSequence);

    // Process event (text, tool_call, tool_result)
    // ...

    nextExpectedSequence++;
  }
};
```

**Buffer text events (lines ~9533-9539):**
```typescript
if (seq !== null) {
  eventBuffer.set(seq, {
    type: 'text',
    text: parsed.text,
  });
  await flushSequencedEvents();
}
```

**Pass sequence to webview messages:**
- `botMessageChunk` (line ~9248): Added `sequence: nextExpectedSequence`
- `command.start` (line ~9638): Added `sequence: seq`
- `navi.agent.event` (line ~9626): Added `sequence: seq`

### 3. Webview Changes (`extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx`)

**A. Use backend sequence for activity events (lines ~2375-2382):**
```typescript
const pushActivityEvent = (event: ActivityEvent) => {
  // Use backend sequence if provided, otherwise use local counter
  const backendSequence = event._sequence;
  if (!backendSequence) {
    activitySequenceRef.current += 1;
  }
  const sequencedEvent: ActivityEvent = {
    ...event,
    _sequence: backendSequence || activitySequenceRef.current,
  };
  // ...
};
```

**B. Add text chunks to narrative stream (lines ~4066-4093):**
```typescript
// botMessageChunk handler
if (msg.chunk && typeof msg.chunk === 'string' && msg.chunk.trim()) {
  const chunkSequence = typeof msg.sequence === 'number' ? msg.sequence : undefined;
  setNarrativeLines((prev) => {
    if (!chunkSequence) {
      return appendNarrativeChunk(prev, msg.chunk, narrativeTimestamp);
    }

    // Merge consecutive chunks to preserve spacing
    const lastItem = prev[prev.length - 1];
    const isConsecutive = lastItem &&
      typeof lastItem._sequence === 'number' &&
      chunkSequence === lastItem._sequence + 1;

    if (lastItem && isConsecutive) {
      // Append to last narrative (preserves spaces in chunk)
      const updated = [...prev];
      updated[updated.length - 1] = {
        ...lastItem,
        text: lastItem.text + msg.chunk,  // Direct concatenation preserves spaces
        timestamp: narrativeTimestamp,
        _sequence: chunkSequence,
      };
      return updated.slice(-400);
    } else {
      // Create new narrative chunk (gap in sequence)
      return [...prev, {
        id: makeActivityId(),
        text: msg.chunk,
        timestamp: narrativeTimestamp,
        _sequence: chunkSequence,
      }].slice(-400);
    }
  });
}
```

**C. Pass sequence to activity events:**
- `command.start` handler (line ~4741): Added `_sequence: typeof msg.sequence === 'number' ? msg.sequence : undefined`
- `navi.agent.event` handler (line ~6183): Added `_sequence: typeof msg.sequence === 'number' ? msg.sequence : undefined`

**D. Chronological rendering (lines ~11278-11286):**
```typescript
// Sort by sequence first, then timestamp
allItems.sort((a, b) => {
  if (a.sequence > 0 || b.sequence > 0) {
    if (a.sequence !== b.sequence) return a.sequence - b.sequence;
  }
  const timeA = a.timestamp;
  const timeB = b.timestamp;
  return new Date(timeA).getTime() - new Date(timeB).getTime();
});
```

## Key Implementation Details

### Why Merge Consecutive Text Chunks?
Backend streaming splits text at arbitrary boundaries:
- Chunk 1: "Let me run a git-ignored dry-run"
- Chunk 2: " scan to list unnecessary files"  ← Starts with space
- Chunk 3: " precisely."  ← Starts with space

If each chunk is a separate narrative item, the merge logic concatenates them. By checking `chunkSequence === lastItem._sequence + 1`, we detect consecutive chunks and merge them, preserving the natural spacing from the backend.

### Why Check for Consecutive Sequences?
When a command appears between text chunks:
- Seq 1-3: Text chunks (merge together)
- Seq 4: Command (creates activity, not narrative)
- Seq 5: Tool result
- Seq 6-10: More text chunks (merge together)

The gap at seq 4 prevents merging chunks before and after the command, which is correct.

### Why Both Narrative Stream AND Message Content?
- **Message content** (`msg.content`): Backward compatibility, full text storage
- **Narrative stream** (`narrativeLines`): Chronological rendering with activities
- **Rendering logic**: Shows narratives in `streamItems` (interleaved with activities), falls back to message content only if no narratives

## Testing Checklist

To verify the fix is working:

1. **Console logs should show sequences:**
   ```
   📝 V2 Text chunk: Let me run... seq: 1
   📝 Flushing text seq: 1 length: 32
   📝 V2 Text chunk:  scan to list... seq: 2
   📝 Flushing text seq: 2 length: 31
   🔧 V2 Tool Call: run_command ... seq: 4
   🔧 Executing tool_call seq: 4 kind: command
   ```

2. **UI should show correct order:**
   - Introductory text appears FIRST
   - Bash command panel appears AFTER text
   - Command results appear AFTER command
   - Explanation text appears AFTER results

3. **Text should have proper spacing:**
   - "dry-run scan" not "dry-runscan"
   - "files precisely" not "filesprecisely"
   - No missing spaces between words

## Common Issues and Fixes

### Issue: Text appears after command panel
**Cause:** Text chunks not being added to narrative stream
**Fix:** Ensure `botMessageChunk` handler adds chunks to `narrativeLines` with sequence numbers

### Issue: Missing spaces between words
**Cause:** Each chunk creates separate narrative item, merge logic doesn't add spaces
**Fix:** Check for consecutive sequences and merge chunks in the same narrative item

### Issue: Events out of order
**Cause:** Extension not buffering events by sequence
**Fix:** Implement `eventBuffer` and `flushSequencedEvents()` in extension

### Issue: Webview uses local sequence counter
**Cause:** `pushActivityEvent` always increments local counter
**Fix:** Check for `event._sequence` and use it if provided, only increment local counter as fallback

## Files Modified

- `backend/services/autonomous_agent.py`: Sequence counter and event sequencing
- `extensions/vscode-aep/src/extension.ts`: Event buffering and sequence passing
- `extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx`: Narrative stream and sequence rendering

## Git Commit Message Template

```
fix(bug5): implement chronological event ordering with sequence numbers

Backend:
- Add monotonic sequence counter with async lock
- Include sequence in all yielded events (text, tool_call, tool_result)

Extension:
- Buffer events by sequence number
- Flush events in chronological order
- Pass sequence to webview in all messages

Webview:
- Use backend sequence instead of local counter
- Add text chunks to narrative stream with sequence
- Merge consecutive chunks to preserve spacing
- Render events chronologically by sequence

Fixes: Events now appear in correct order (text → command → result)
Fixes: Text has proper spacing (no more "dry-runscan")
```

## Future Maintenance

If chronological ordering breaks again:

1. **Check console logs** for sequence numbers in events
2. **Verify extension buffering** - are events being flushed in order?
3. **Check webview sequence usage** - is `_sequence` from backend being used?
4. **Verify narrative stream** - are text chunks being added with sequences?
5. **Review merge logic** - are consecutive chunks being merged correctly?

## Related Documentation

- `SEQUENCE_FIX_PLAN.md`: Original planning document
- `BUG5_ROOT_CAUSE_FINAL.md`: Root cause analysis
- Git branch: `fix/chronological-event-ordering`
