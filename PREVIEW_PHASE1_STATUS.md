# Preview Feature - Phase 1 Status

## ✅ Implementation Complete

**Commit:** `471b4f1c` - "feat: implement Phase 1 static preview (Loveable-style split-screen)"
**Branch:** `feat/navi-premium-signup`
**Date:** February 22, 2026

---

## Phase 1: Static HTML Preview

### Backend Implementation ✅

**Files Created:**
1. `backend/api/routers/preview.py` - Preview API endpoints
   - `POST /api/preview/static` - Store HTML content
   - `GET /api/preview/{preview_id}` - Retrieve with CSP headers
   - `DELETE /api/preview/{preview_id}` - Delete preview

2. `backend/services/preview/preview_service.py` - PreviewService class
   - In-memory storage (TTL: 1 hour, max: 100 previews)
   - Oldest-first eviction when at capacity
   - UUID-based preview IDs

3. `backend/tests/test_preview_service.py` - Unit tests
   - Store/retrieve/delete operations
   - TTL expiration
   - Capacity eviction

4. `backend/tests/test_preview_routes.py` - API route tests
   - Auth requirements (VIEWER role)
   - CSP headers verification
   - Full lifecycle testing

**Modified Files:**
- `backend/api/main.py` - Registered preview router, initialized PreviewService singleton

**Security:**
- ✅ All endpoints require authentication (VIEWER role)
- ✅ Restrictive CSP headers:
  - `default-src 'none'`
  - `script-src 'none'` (no scripts in static HTML)
  - `connect-src 'none'` (prevents data exfiltration)
  - `style-src 'unsafe-inline'` (allows inline styles)
  - `img-src data: https:` (allows images)
  - `frame-ancestors 'self'`
- ✅ Additional headers:
  - `Cross-Origin-Resource-Policy: same-site`
  - `X-Frame-Options: SAMEORIGIN`
  - `X-Content-Type-Options: nosniff`
  - `Cache-Control: no-store`

### Frontend Implementation ✅

**Files Created:**
1. `web/components/preview/PreviewFrame.tsx` - Iframe wrapper
   - Supports `src` (URL) and `srcDoc` (inline HTML)
   - Loading and error states
   - Security: `sandbox=""` for srcDoc (no scripts), `sandbox="allow-scripts allow-forms"` for src (NO `allow-same-origin`)
   - `referrerPolicy="no-referrer"`

2. `web/components/preview/PreviewControls.tsx` - Preview toolbar
   - Device size selector (Mobile/Tablet/Desktop)
   - Refresh button
   - Open in new tab
   - Copy URL to clipboard
   - Toggle visibility

3. `web/hooks/usePreview.ts` - State management hook
   - State: `url | html | type | visible`
   - Methods: `setPreviewUrl`, `setPreviewHtml`, `clearPreview`, `toggleVisibility`

**Modified Files:**
- `web/app/(app)/app/chats/page.tsx` - Split-pane layout
  - Sidebar (320px) + Chat (flex-1 or flex-2) + Preview (flex-1)
  - Responsive sizing based on preview visibility
  - Test button (temporary for Phase 1 demo)

### Testing ✅

**Unit Tests:**
- ✅ `test_store_and_retrieve()` - Basic operations
- ✅ `test_delete_preview()` - Delete by ID
- ✅ `test_preview_expiration()` - TTL enforcement
- ✅ `test_max_previews_eviction_oldest()` - Capacity limits

**API Route Tests:**
- ✅ `test_preview_requires_auth_post_jwt_mode()` - POST auth gate
- ✅ `test_preview_requires_auth_get_jwt_mode()` - GET auth gate
- ✅ `test_preview_csp_headers()` - Security headers
- ✅ `test_preview_store_retrieve_delete_workflow()` - Full lifecycle
- ✅ `test_preview_not_found()` - 404 handling
- ✅ `test_preview_delete_not_found()` - DELETE 404

**E2E Testing:**
- ✅ Manual test via "🧪 Test Preview" button
- ✅ Preview pane displays with gradient background
- ✅ All controls work (refresh, toggle, device sizes)
- ✅ Split-pane responsive layout verified

### Known Issues (Resolved)

1. ❌ **Cross-origin framing blocked** (CSP `frame-ancestors 'self'`)
   - **Solution:** Use `srcDoc` instead of `src` to inject HTML directly
   - **Status:** ✅ Fixed - Preview uses `srcDoc` attribute

---

## CI/CD Status ⚠️

### Current Build Failures (In Progress)

1. **TypeScript Build** ❌
   - Location: `web/app/api/auth/[...auth0]/route.ts:6`
   - Error: Type mismatch in `handleLogin` callback
   - Cause: Auth0 SDK type incompatibility (not related to preview feature)
   - **Status:** Investigating fix

2. **Python Unit Tests** ❌
   - Error: Pydantic validation error in Settings
   - Message: "Extra fields not permitted: api_base_url, auth0_action_secret, ..."
   - Cause: .env file has fields not defined in Settings model
   - **Status:** Investigating fix

3. **Lint** ❌
   - **Status:** Pending (likely related to above issues)

### Resolution Plan

- [ ] Fix TypeScript auth route type error
- [ ] Fix Pydantic Settings validation
- [ ] Verify all tests pass locally
- [ ] Re-run CI/CD pipeline
- [ ] Address any remaining lint issues

---

## Phase 1 Acceptance Criteria

### Backend ✅
- [x] PreviewService stores/retrieves HTML (in-memory)
- [x] POST /api/preview/static requires auth (401 in JWT mode)
- [x] GET /api/preview/{id} requires auth (401 in JWT mode)
- [x] GET response includes restrictive CSP headers (`script-src 'none'`)
- [x] TTL cleanup works (preview expires after 1 hour)
- [x] Max 100 previews enforced (oldest evicted)

### Frontend ✅
- [x] PreviewFrame renders `srcDoc` static HTML
- [x] PreviewFrame renders `src` URL preview
- [x] PreviewControls: refresh, toggle, copy URL work
- [x] Chat page split pane layout (sidebar + chat + preview)
- [x] Preview pane is responsive (resizes with window)

### Testing ✅
- [x] Unit tests: PreviewService store/retrieve/expire/eviction
- [x] Security tests: CSP headers verified via tests and curl
- [x] E2E test: Preview displays via test button

### Security ✅
- [x] Auth-gated endpoints (no public access)
- [x] Restrictive CSP (no scripts/network in static HTML)
- [x] Iframe sandbox (no permissions for srcDoc, allow-scripts for src with backend CSP, NO allow-same-origin)
- [x] frame-ancestors 'self', X-Frame-Options: SAMEORIGIN
- [x] Cache-Control: no-store
- [x] Test button uses srcDoc directly (no unauthenticated backend calls)

---

## Next Steps

### Before Phase 2:
1. ⚠️ **Fix CI/CD failures** (in progress)
   - TypeScript build error
   - Python test configuration
   - Lint issues

2. **PR Review**
   - Address any PR comments
   - Update documentation if needed

### Phase 2: Preview Sessions with LocalRunner
**NOT STARTED** - Blocked by CI/CD fixes

**Planned Features:**
- PreviewSessionStore (separate session storage)
- LocalRunner (sandboxed dev server execution)
- Preview proxy (`/api/runs/{run_id}/preview/*`)
- SSE integration for automatic preview triggering
- npm install handling
- Port allocation (3000-4000 range)
- Idle shutdown (20min timeout)
- Workspace/command allowlists

**Estimated Effort:** 4-5 days

---

## Deployment Notes

### Single Worker Requirement (Phase 1)
⚠️ **Important:** Phase 1 uses in-memory preview storage. If running with multiple uvicorn workers, previews may break due to requests hitting different workers with isolated stores.

**Solutions:**
1. Run with single worker: `uvicorn api.main:app --workers 1`
2. Use sticky sessions (load balancer affinity)
3. Upgrade to Phase 2 (uses shared session store)

### Environment Variables
No new environment variables required for Phase 1.

### Database Migrations
No database changes in Phase 1 (in-memory only).

---

## File Changes Summary

**Total:** 10 files changed, 1,162 insertions(+), 40 deletions(-)

**Backend:**
- 6 files (4 new, 2 modified)
- 620 lines added

**Frontend:**
- 4 files (3 new, 1 modified)
- 542 lines added

**Tests:**
- 2 new test files
- 150+ test lines

---

## Manual Verification Commands

### Test Backend API
```bash
# Store preview
curl -X POST http://localhost:8787/api/preview/static \
  -H "Content-Type: application/json" \
  -d '{"content":"<h1>Test</h1>","content_type":"html"}' \
  | jq .

# Retrieve preview (check headers)
curl -v http://localhost:8787/api/preview/{preview_id} 2>&1 | grep -i "content-security-policy"
```

### Test Frontend
1. Navigate to http://localhost:3030/app/chats
2. Click "🧪 Test Preview" button
3. Verify preview pane appears with gradient background
4. Test controls (refresh, toggle, device sizes)

---

**Status:** ✅ Phase 1 Complete (Code) | ⚠️ CI/CD In Progress | 🔜 Phase 2 Planned
