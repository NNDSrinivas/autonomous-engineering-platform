# NAVI End-to-End Testing - Bug Reports & Fixes

## Status: ✅ Core functionality confirmed working
- Backend + extension wiring ✅
- Chat flow (greetings, code review, Jira generation) ✅  
- Smart routing logs healthy ✅
- Error handling for broken messages ✅

---

## 🐛 Critical Bugs (Fix Priority 1)

### Bug #1: Large File Paste → "Empty content from NAVI backend"
**Severity**: High - Breaks core functionality
**Repro**: Paste 300-350+ line code file → get empty response

**Root Cause**: Backend planner/LLM call fails or times out, returns empty string instead of error handling

**Fix Required**:
```python
# In backend/api/routes/navi.py or chat endpoint
try:
    result = await planner.plan_and_execute(request)
    if not result or not result.content:
        raise ValueError("Empty result from planner")
    return ChatResponse(content=result.content, ...)
except Exception as e:
    logger.exception("NAVI chat failed")
    return ChatResponse(
        content="I hit an internal error processing that large snippet. "
                "Try selecting a smaller region while we improve large-file support.",
        error=str(e)
    )
```

**Follow-up**: Add chunking for large inputs (split into sections 1/3, 2/3, 3/3)

---

### Bug #2: Menu Overlapping (Wand + Plus menus)
**Severity**: Medium - UX confusion
**Repro**: Click ⚡ wand menu → click + menu → both stay open, overlay

**Fix Required**: Single menu state management
```typescript
const [openMenu, setOpenMenu] = useState<'actions' | 'quick' | null>(null);

const toggleActions = () => 
  setOpenMenu(prev => prev === 'actions' ? null : 'actions');
  
const toggleQuick = () => 
  setOpenMenu(prev => prev === 'quick' ? null : 'quick');
```

**Files**: `extensions/vscode-aep/media/panel.js` or React components

---

### Bug #3: Code Block Readability Issues  
**Severity**: Medium - Impacts code review experience
**Symptoms**: Dense, unreadable code blocks in responses

**Fix Required**:
1. **CSS improvements**:
```css
.chat-message pre code {
  font-family: var(--vscode-editor-font-family, Menlo, monospace);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  max-height: 320px;
  overflow: auto;
}
```

2. **Response formatting**: Update planner prompts to use proper markdown fencing and avoid repeating entire large files

---

## 🎨 UI/UX Polish (Priority 2)

### Issue #4: Cramped Chat Viewport
- Large header + thick footer = minimal chat space
- **Fix**: Compact header design, reduce footer padding
- **Goal**: More space for actual conversation

### Issue #5: User Message Bubble Styling
- Too blue, too tall vertical padding
- **Fix**: Softer gradient, reduced padding, smaller border radius

### Issue #6: Static Model Dropdown
- Currently hardcoded 4-5 models
- **Enhancement**: Fetch from `backend/ai/model_registry` dynamically
- **Future**: Group by provider (OpenAI/Anthropic/Google)

---

## 🧪 Suggested Next Test Cases

1. **Selected Code Attachment** (20-30 lines)
2. **Full File Attachment** (moderate size)  
3. **Model Switching** (verify different LLMs work)
4. **Long Conversations** (6-8 follow-ups, context retention)

---

## Implementation Priority

**Week 1**: Fix bugs #1, #2, #3 (core functionality)
**Week 2**: UI polish #4, #5 (user experience) 
**Week 3**: Dynamic model registry #6 (feature enhancement)