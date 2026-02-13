# CRITICAL BUG: Chat/Activity Data Loss on VS Code Reload

**Status:** 🔴 **CRITICAL** - Production Blocker
**Priority:** P0 - Immediate fix required
**Created:** 2026-02-09
**Severity:** Data Loss

---

## Problem Statement

**Chats, activities, and command panels disappear after VS Code/webview reload**, causing permanent data loss. Users lose their entire conversation history, work context, and ongoing tasks.

### User Impact
- 💔 **Permanent data loss** - All chat history lost on reload
- 🔄 **Loss of work context** - Can't resume interrupted tasks
- 😤 **Poor user experience** - Users afraid to reload VS Code
- 📉 **Trust erosion** - "How can I trust NAVI with production code if it can't even save my chats?"

---

## Root Cause Analysis

### What We Have

✅ **Backend Infrastructure EXISTS:**
- Database model: `Conversation` table ([backend/database/models/memory.py:623](backend/database/models/memory.py#L623))
- API endpoints: `/api/navi-memory/conversations` ([backend/api/routers/navi_memory.py:433](backend/api/routers/navi_memory.py#L433))
  - `GET /conversations` - List conversations
  - `POST /conversations` - Create conversation
  - `GET /conversations/{id}` - Get conversation with messages
  - `POST /conversations/{id}/messages` - Add message

✅ **Frontend Session Management EXISTS:**
- [extensions/vscode-aep/webview/src/utils/chatSessions.ts](extensions/vscode-aep/webview/src/utils/chatSessions.ts)
- Complete session CRUD operations
- Checkpoint system for task recovery
- Backend sync functions (lines 656-960)

### What's Broken

❌ **Frontend uses localStorage as PRIMARY storage:**
```typescript
// chatSessions.ts:24-31
const SESSIONS_KEY = "aep.navi.chatSessions.v1";
const HISTORY_PREFIX = "aep.navi.chatHistory.v1.";

const readStorage = (key: string): string | null => {
  return window.localStorage.getItem(key);  // ← PROBLEM: Lost on reload!
};
```

❌ **VS Code webview behavior:**
- Webviews are isolated iframes that **completely reset on reload**
- `localStorage` in webviews **does not persist** across VS Code restarts
- Even developer reload (`Cmd+R`) **wipes all localStorage**

❌ **Backend API is NEVER called:**
- No calls to `POST /conversations` when user sends message
- No calls to `GET /conversations` on webview initialization
- `backendConversationId` field exists but is never populated
- Sync functions exist but are never invoked

---

## Evidence

### 1. Database Schema (backend/database/models/memory.py)
```python
class Conversation(Base):
    __tablename__ = "navi_conversations"

    id: Mapped[str] = Column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"))
    title: Mapped[Optional[str]] = Column(String(255))
    workspace_path: Mapped[Optional[str]] = Column(Text)
    is_pinned: Mapped[bool] = Column(Boolean, default=False)
    is_starred: Mapped[bool] = Column(Boolean, default=False)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

### 2. Backend API Endpoints (backend/api/routers/navi_memory.py)
```python
@router.get("/conversations")
async def list_conversations(user_id: int, limit: int = 50) -> List[Dict]:
    """List user's conversations."""

@router.post("/conversations")
async def create_conversation(user_id: int, conversation: ConversationCreate):
    """Create a new conversation."""

@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: UUID, include_messages: bool = True):
    """Get a conversation with messages."""

@router.post("/conversations/{conversation_id}/messages")
async def add_message(conversation_id: UUID, message: MessageCreate):
    """Add a message to conversation."""
```

### 3. Frontend Storage (chatSessions.ts:37-62)
```typescript
const readStorage = (key: string): string | null => {
  if (!isBrowser) return null;
  try {
    return window.localStorage.getItem(key);  // ← VS Code webview loses this!
  } catch {
    return null;
  }
};

export const loadSessionMessages = <T = unknown>(id: string): T[] => {
  return safeJsonParse<T[]>(readStorage(`${HISTORY_PREFIX}${id}`), []);
};
```

### 4. Backend Sync Functions Exist But Never Called
```typescript
// chatSessions.ts:663-745 - These functions exist but are NEVER invoked!
export const syncCheckpointToBackend = async (checkpoint: TaskCheckpoint): Promise<boolean> => {
  // Would save to backend, but never called
};

export const loadCheckpointFromBackend = async (sessionId: string): Promise<TaskCheckpoint | null> => {
  // Would load from backend, but never called
};
```

---

## Impact Assessment

### Data Loss Scenarios

1. **User reloads VS Code** → All chats lost
2. **VS Code crashes** → All in-progress work lost
3. **Developer uses "Reload Window"** → Hours of conversation history gone
4. **Extension updates** → Complete chat history wiped

### Business Impact

- **User Trust:** Users can't rely on NAVI for serious work
- **Adoption:** Major blocker for production use
- **Support:** Constant user complaints about "lost conversations"
- **Reputation:** "NAVI loses my work" becomes common feedback

---

## Solution Architecture

### Phase 1: Backend Persistence (Required for MVP)

#### 1.1 Create Conversation on First Message
```typescript
// When user sends first message in a session
const createBackendConversation = async (sessionId: string, title: string) => {
  const response = await fetch(`${apiBase}/api/navi-memory/conversations`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      user_id: USER_ID,
      org_id: ORG_ID,
      title,
      workspace_path: workspaceRoot,
    }),
  });
  const { id } = await response.json();
  // Save backend conversation ID to session
  updateSession(sessionId, { backendConversationId: id });
};
```

#### 1.2 Save Every Message to Backend
```typescript
// After each message (user or assistant)
const saveMessageToBackend = async (conversationId: string, message: Message) => {
  await fetch(`${apiBase}/api/navi-memory/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      role: message.role,
      content: message.content,
      metadata: message.metadata,
    }),
  });
};
```

#### 1.3 Load Conversations on Startup
```typescript
// On webview initialization
const loadConversationsFromBackend = async () => {
  const response = await fetch(
    `${apiBase}/api/navi-memory/conversations?user_id=${USER_ID}&limit=50`,
    { headers: buildHeaders() }
  );
  const conversations = await response.json();

  // Sync to localStorage for offline access
  for (const conv of conversations) {
    const session = {
      id: generateLocalId(),
      backendConversationId: conv.id,
      title: conv.title,
      createdAt: conv.created_at,
      updatedAt: conv.updated_at,
      isStarred: conv.is_starred,
      isPinned: conv.is_pinned,
    };
    // Save to localStorage as cache
    writeSessions([...readSessionsRaw(), session]);
  }
};
```

#### 1.4 Sync Session Metadata
```typescript
// When user stars/pins/archives a conversation
const syncSessionMetadata = async (sessionId: string, updates: Partial<Session>) => {
  const session = getSession(sessionId);
  if (!session.backendConversationId) return;

  await fetch(`${apiBase}/api/navi-memory/conversations/${session.backendConversationId}`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify({
      is_starred: updates.isStarred,
      is_pinned: updates.isPinned,
      status: updates.isArchived ? 'archived' : 'active',
    }),
  });
};
```

### Phase 2: VS Code State Persistence (Enhanced)

VS Code provides **persistent state storage** that survives reloads:
```typescript
// Use VS Code's built-in state persistence
const vscodeState = vscode.getState() || {};

// Save state before reload
vscode.setState({
  activeSessionId: getActiveSessionId(),
  recentSessions: listSessions().slice(0, 10),
});

// Restore on init
const restored = vscode.getState();
if (restored?.activeSessionId) {
  setActiveSessionId(restored.activeSessionId);
}
```

### Phase 3: Hybrid Storage Strategy (Optimal)

```typescript
/**
 * Hybrid storage: Backend is source of truth, localStorage is cache
 *
 * Write path:
 * 1. Write to backend (async)
 * 2. Write to localStorage (sync, for immediate UI update)
 * 3. If backend fails, queue for retry
 *
 * Read path:
 * 1. Load from localStorage (fast, for immediate render)
 * 2. Load from backend (authoritative)
 * 3. Merge and update localStorage cache
 */
```

---

## Implementation Plan

### Sprint 1: Backend Integration (3 days)

**Day 1: Core Save Flow**
- [ ] Add `createBackendConversation()` call on first message
- [ ] Add `saveMessageToBackend()` call after each message
- [ ] Test: Messages persist after reload

**Day 2: Load Flow**
- [ ] Add `loadConversationsFromBackend()` on webview init
- [ ] Implement localStorage cache sync
- [ ] Test: Conversations load from backend on startup

**Day 3: Metadata Sync**
- [ ] Wire star/pin/archive to backend PATCH endpoint
- [ ] Add error handling and retry logic
- [ ] Test: Metadata changes persist

### Sprint 2: Robustness (2 days)

**Day 4: Offline Support**
- [ ] Implement write queue for offline mode
- [ ] Add conflict resolution (local vs backend)
- [ ] Test: Works offline, syncs when online

**Day 5: Migration & Testing**
- [ ] Migrate existing localStorage sessions to backend
- [ ] Add integration tests
- [ ] Load testing (1000+ conversations)

---

## Files to Modify

### Backend (No changes needed - APIs already exist!)
- ✅ `backend/database/models/memory.py` - Models exist
- ✅ `backend/api/routers/navi_memory.py` - Endpoints exist

### Frontend (Critical changes)
1. **[extensions/vscode-aep/webview/src/utils/chatSessions.ts](extensions/vscode-aep/webview/src/utils/chatSessions.ts)**
   - Lines 141-161: `createSession()` - Call backend API
   - Lines 270-276: `saveSessionMessages()` - Call backend API
   - Lines 320-339: `ensureActiveSession()` - Load from backend

2. **[extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx](extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx)**
   - Add `useEffect` to load conversations on mount
   - Call `saveMessageToBackend()` after each message
   - Handle backend errors gracefully

3. **[extensions/vscode-aep/webview/src/hooks/useActivityPanel.ts](extensions/vscode-aep/webview/src/hooks/useActivityPanel.ts)**
   - Sync activity panel state to backend
   - Restore from backend on mount

---

## Testing Strategy

### Unit Tests
```typescript
describe('Chat Persistence', () => {
  it('saves message to backend after send', async () => {
    const message = { role: 'user', content: 'test' };
    await sendMessage(message);

    const saved = await fetch(`/api/navi-memory/conversations/${conversationId}/messages`);
    expect(saved).toContainEqual(message);
  });

  it('loads conversations from backend on init', async () => {
    // Create backend conversation
    await createBackendConversation();

    // Simulate reload
    clearLocalStorage();
    await initWebview();

    // Should load from backend
    const sessions = listSessions();
    expect(sessions.length).toBeGreaterThan(0);
  });

  it('survives VS Code reload', async () => {
    const session = createSession({ title: 'Test Chat' });
    await sendMessage({ role: 'user', content: 'Hello' });

    // Simulate VS Code reload (wipe localStorage)
    clearLocalStorage();

    // Reload should restore from backend
    await loadConversationsFromBackend();
    const restored = getSession(session.id);
    expect(restored).toBeDefined();
    expect(restored.title).toBe('Test Chat');
  });
});
```

### Integration Tests
- [ ] Create conversation → Reload → Verify restored
- [ ] Send 100 messages → Reload → Verify all messages present
- [ ] Star conversation → Reload → Verify still starred
- [ ] Offline mode → Send messages → Go online → Verify synced

### Performance Tests
- [ ] Load 1,000 conversations (target: <1s)
- [ ] Save message (target: <100ms perceived, async backend)
- [ ] Sync queue (target: 100 messages/second)

---

## Rollout Plan

### Week 1: Development
- Implement backend integration
- Add error handling
- Write unit tests

### Week 2: Testing
- QA testing with real workloads
- Beta users testing
- Performance profiling

### Week 3: Deployment
- Deploy to staging
- Monitor error rates
- Gradual rollout to production

---

## Success Criteria

✅ **Must Have:**
1. Conversations persist after VS Code reload
2. Messages are saved to backend automatically
3. No data loss on crash/reload
4. Works offline with queue sync

✅ **Nice to Have:**
1. Migration of existing localStorage sessions
2. Conflict resolution (local vs backend)
3. Real-time sync across multiple VS Code windows
4. Export conversations to JSON/markdown

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend API failure | Message loss | Write queue + retry logic |
| Network latency | Slow UI | Optimistic updates + background sync |
| Large conversation load time | Slow startup | Paginated loading + lazy loading |
| Migration data loss | User complaints | Careful migration script + backup |

---

## Related Issues

- Settings consolidation: [docs/SETTINGS_CONSOLIDATION_TODO.md](SETTINGS_CONSOLIDATION_TODO.md)
- Production readiness: [docs/NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md)

---

## Questions for Product/Engineering

1. **Migration:** What happens to existing localStorage sessions? Migrate or start fresh?
2. **Retention:** How long to keep conversations? (30 days, 90 days, forever?)
3. **Storage limits:** Max conversations per user? Max messages per conversation?
4. **Sync strategy:** Real-time sync or batched? Retry policy?
5. **Offline mode:** How long to queue offline writes?

---

## Contact

For questions or to start this fix:
1. Review this document thoroughly
2. Check existing backend APIs work correctly
3. Create feature branch: `fix/chat-persistence-backend-integration`
4. Follow the implementation plan above
5. Request code review before merging

**This is a P0 production blocker. Do NOT ship to customers without fixing this.**
