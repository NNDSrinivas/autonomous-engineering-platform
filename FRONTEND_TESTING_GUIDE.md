# NAVI RAG Search - Frontend Testing Guide

## 🚀 Quick Start

### 1. Start Services

**Backend** (Terminal 1):
```bash
cd /path/to/autonomous-engineering-platform
python main.py
# or
python -m backend.api.main
```
Backend will start on `http://localhost:8000` or `http://localhost:8787`

**Frontend** (Terminal 2):
```bash
cd /path/to/autonomous-engineering-platform/frontend
npm run dev
```
Frontend will start on `http://localhost:3000`

### 2. Access the NAVI Search Interface

**Option A: React Frontend** (Recommended)
1. Open browser to `http://localhost:3000`
2. Click "🔍 NAVI RAG Search" from homepage
3. Or navigate directly to `http://localhost:3000/navi/search`

**Option B: Standalone HTML Test**
1. Open `test_navi_search.html` in your browser
2. This works without npm and tests API directly

## 🧪 Testing Features

### Test 1: Health Check
1. Click "🏥 Test Health" button
2. Should see: `{"status": "ok", "service": "navi-search", ...}`
3. ✅ Confirms search API is running

### Test 2: Memory Stats
1. Click "📊 Stats" button (or "Memory Stats" tab in React app)
2. Should see memory counts by category:
   - `profile`: User preferences
   - `workspace`: Org documentation
   - `task`: Jira issues
   - `interaction`: Chat history
3. If all zeros → Need to populate memory first (see below)

### Test 3: Search Query
1. Enter search query: "What's the dev environment URL?"
2. Select categories (or leave all selected)
3. Adjust limit (1-20 results) and min importance (1-5)
4. Click "🔍 Search" button
5. Should see ranked results with:
   - Similarity scores (0-100%)
   - Importance ratings (1-5)
   - Content with highlighted query terms
   - Source metadata

## 📊 Populating Test Memory

Before searching, you need memory data. Use Step 2 org sync endpoints:

### Sync Jira Issues
```bash
curl -X POST http://localhost:8000/api/org/sync/jira \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "project_key": "LAB",
    "max_issues": 10
  }'
```

### Sync Confluence Pages
```bash
curl -X POST http://localhost:8000/api/org/sync/confluence \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "space_key": "DEV",
    "max_pages": 5
  }'
```

**Note**: Requires valid Jira/Confluence credentials in `.env`:
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-token

CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_API_TOKEN=your-token
```

## 🔍 Example Queries to Try

Once memory is populated:

1. **Environment Info**: "What's the dev environment URL?"
2. **Issue Context**: "Any Confluence pages for LAB-158?"
3. **Discussions**: "Where did we discuss barcode overrides?"
4. **Tasks**: "Show me my current tasks"
5. **Preferences**: "What are my preferences?"
6. **Documentation**: "Find documentation about deployment"

## 🎨 React Frontend Features

The React app (`frontend/src/pages/NaviSearchPage.tsx`) includes:

### Search Tab
- **Query Input**: Natural language questions
- **User ID**: Filter by user
- **Category Toggles**: Select which memory types to search
- **Sliders**: Adjust max results and min importance
- **Real-time Highlighting**: Query terms highlighted in results
- **Result Cards**: 
  - Category emoji indicators
  - Similarity percentage
  - Importance badges
  - Expandable metadata
  - Creation timestamps

### Stats Tab
- **Total Memories**: Big number display
- **Category Breakdown**: Count per category
- **Visual Icons**: 👤 profile, 🏢 workspace, ✅ task, 💬 interaction
- **Empty State**: Guidance if no data

### Example Queries Section
- One-click example queries
- Covers common use cases
- Demonstrates search capabilities

## 🛠️ Troubleshooting

### Backend Not Starting
- Check port not in use: `lsof -i :8000` or `lsof -i :8787`
- Check logs for errors
- Verify PostgreSQL running: `psql -h localhost -p 5432`
- Check `.env` file has `OPENAI_API_KEY`

### Search Returns No Results
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check memory exists: `curl http://localhost:8000/api/navi/search/stats?user_id=test-user`
3. Run org sync to populate data (see above)
4. Lower `min_importance` threshold
5. Try broader search terms

### Frontend Not Loading
- Check `npm run dev` output for errors
- Verify frontend port (usually 3000 or 5173)
- Check browser console for errors
- Ensure `VITE_API_BASE_URL` matches backend port

### CORS Errors
- Backend should have CORS middleware enabled
- Check `backend/api/main.py` for `CORSMiddleware`
- Verify frontend origin in allowed origins

### Search Health Returns 404
- Router not registered in `main.py`
- Check `backend/api/main.py` includes:
  ```python
  from .navi_search import router as navi_search_router
  app.include_router(navi_search_router)
  ```
- Restart backend after code changes

## 📸 What You Should See

### Successful Health Check
```json
{
  "status": "ok",
  "service": "navi-search",
  "message": "Unified RAG search engine is running",
  "endpoints": ["/search", "/search/stats", "/search/health"]
}
```

### Search Results
```json
{
  "query": "dev environment",
  "results": [
    {
      "id": 123,
      "category": "workspace",
      "title": "Development Environment Setup",
      "content": "The dev environment is at https://dev.example.com...",
      "similarity": 0.87,
      "importance": 4,
      "meta": {"source": "confluence"}
    }
  ],
  "total": 1
}
```

### Memory Stats
```json
{
  "user_id": "test-user",
  "total_memories": 15,
  "by_category": {
    "workspace": 5,
    "task": 8,
    "profile": 1,
    "interaction": 1
  }
}
```

## 🎯 Testing Checklist

- [ ] Backend starts without errors
- [ ] Frontend loads at localhost:3000
- [ ] Health check passes (green checkmark)
- [ ] Can navigate to NAVI Search page
- [ ] Stats show memory counts (or zero if empty)
- [ ] Search returns results (after populating memory)
- [ ] Query terms are highlighted in results
- [ ] Similarity scores make sense
- [ ] Can filter by categories
- [ ] Can adjust result limit
- [ ] Example queries work
- [ ] Metadata expands/collapses
- [ ] No console errors in browser

## 📚 Related Files

- **Frontend**: `frontend/src/pages/NaviSearchPage.tsx`
- **Backend API**: `backend/api/navi_search.py`
- **Router Registration**: `backend/api/main.py`
- **Memory Service**: `backend/services/navi_memory_service.py`
- **Test HTML**: `test_navi_search.html` (standalone)

## 🚀 Next Steps

After verifying Step 3 works:
1. Populate real org data via Step 2 sync
2. Test NAVI chat integration (VS Code extension)
3. Verify context injection improves responses
4. Monitor search quality and ranking
5. Consider adding user feedback (thumbs up/down)

## 💡 Tips

- **Use specific queries**: Better results than vague questions
- **Filter categories**: Faster search, more relevant results
- **Adjust importance**: Filter low-quality memories
- **Check metadata**: See source (Jira, Confluence, etc.)
- **Monitor similarity**: >0.7 is high relevance, <0.3 is low

Happy testing! 🎉
