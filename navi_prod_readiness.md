# NAVI Production Readiness Checklist

## ✅ Completed

### Code Quality
- [x] Removed print statements from production code (only in migrations)
- [x] No hardcoded console.log/console.debug in TypeScript
- [x] Security fixes applied (IDOR, error logging, HTTPException handling)
- [x] OpenAI API parameter fix for GPT-5 models

### API Fixes
- [x] Fixed `max_completion_tokens` for GPT-5.x/GPT-4o models
- [x] Added `/ping` endpoint for load balancers
- [x] Proper error logging with truncation

### Security
- [x] Conversation ownership verification
- [x] HTTPException proper propagation
- [x] Safe error decoding in LLM client

## 📋 Deferred Items (Address in Upcoming PRs)

### Code Quality Improvements (Non-Blocking)
From PR #87 Copilot code reviews - identified but not critical for merge:

#### Frontend (NaviChatPanel.tsx)
- [ ] **Command Output Handler Optimization**
  - Issue: New `command.output` handler uses `msg.line` but doesn't call `setPerActionOutputForAction`
  - Impact: NaviActionRunner may show empty output in action cards
  - Issue: Bypasses `appendWithLimit` (MAX_COMMAND_OUTPUT), making output unbounded
  - Location: Line 5317 in NaviChatPanel.tsx
  - Priority: Medium (affects inline command output display)

- [ ] **Textarea Arrow Key Navigation**
  - Issue: Arrow key handlers call `preventDefault()` unconditionally
  - Impact: Users can't navigate cursor up/down in multi-line messages
  - Fix: Only intercept at start (ArrowUp) or end (ArrowDown) of content
  - Location: Line 8051+ in NaviChatPanel.tsx (handleKeyDown)
  - Priority: Medium (UX enhancement for multi-line editing)

- [ ] **flushSync Performance Issue**
  - Issue: flushSync fires synchronously on every streamed output line
  - Impact: For commands with many lines (npm install, docker build), this forces full re-render per line, blocking event loop and freezing UI
  - Fix: Debounce/throttle updates (e.g., accumulate lines for 50-100ms) instead of forcing synchronous render per line
  - Location: Lines 5344-5369 in NaviChatPanel.tsx
  - Priority: Medium (performance degradation for verbose commands)

- [ ] **Duplicate command.output Handlers**
  - Issue: Two separate handlers at lines 4839 and 5320, split by msg.text vs msg.line
  - Impact: Fragile design; second handler doesn't call setPerActionOutputForAction or use appendWithLimit
  - Risk: Output becomes unbounded, diverges from first handler's bounded tracking
  - Location: Lines 4839 and 5320 in NaviChatPanel.tsx
  - Priority: Medium (architectural fragility, output consistency)

#### Frontend (NaviChatPanel.css)
- [ ] **CSS List Style Conflicts**
  - Issue: New flex list styles with `!important` override older `display: list-item` styles
  - Impact: `.navi-list-item` inside `.navi-message-content` loses bullet points
  - Location: Lines 7589-7626 conflict with 7554-7562
  - Priority: Low (cosmetic, may affect list rendering)

#### Frontend (NaviActionRunner.tsx)
- [ ] **Remove Dead Code: readonly Prop**
  - Issue: `readonly` prop added but never passed from call site (line 12198 in NaviChatPanel)
  - Impact: Dead code, unused rendering path
  - Action: Either wire up or remove the prop and associated code
  - Location: Lines 54-68 in NaviActionRunner.tsx
  - Priority: Low (cleanup, no functional impact)

#### Frontend (QueuedMessageChip.tsx)
- [ ] **Remove Dead Code: QueuedMessageChip Component**
  - Issue: Component exported but never imported or used anywhere
  - Impact: Dead code with associated unused CSS classes (.navi-queue-panel, .navi-queue-chip, etc.)
  - Action: Remove component file and associated CSS if message queuing feature is not planned
  - Location: QueuedMessageChip.tsx (entire file), NaviChatPanel.css (queue-related styles)
  - Priority: Low (cleanup, adds confusion without functional value)

#### Backend (autonomous_agent.py)
- [ ] **Refactor _result Pattern (Architecture)**
  - Issue: Using `_result` field in events for internal state passing
  - Risk: If not popped before yielding, causes JSON serialization TypeError
  - Suggestion: Use side-channel (return value or wrapper object) instead
  - Location: Line 9944+ in run_single_verification
  - Priority: Low (architectural improvement, currently working with pop() guards)
  - Note: Current implementation with event.pop("_result") works but is fragile

### Technical Debt
- [ ] Consider adding integration tests for streaming command execution
- [ ] Document autonomous_mode behavior and consent gates in developer docs
- [ ] Add JSDoc comments to complex React hooks in NaviChatPanel

## ⚠️  Required Before Production Deploy

### Environment Configuration
- [ ] **CRITICAL**: Generate new secure secrets
  ```bash
  python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
  python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"
  python -c "import secrets; print('AEP_JWT_SECRET=' + secrets.token_urlsafe(32))"
  ```

- [ ] Update `backend/.env` with production values (use `backend/.env.production.template` as template):
  - [ ] Set `ENVIRONMENT=production`
  - [ ] Set `DEBUG=False`
  - [ ] Set `LOG_LEVEL=WARNING` or `ERROR`
  - [ ] Set `ALLOW_DEV_AUTH_BYPASS=false`
  - [ ] Set `ALLOW_DEV_CORS=false`
  - [ ] Set `OAUTH_DEVICE_USE_IN_MEMORY_STORE=false`
  - [ ] Set `OAUTH_DEVICE_AUTO_APPROVE=false`
  - [ ] Replace all `dev-*` secret keys with secure generated ones

### Database & Infrastructure
- [ ] Set up production PostgreSQL database
- [ ] Set up production Redis instance
- [ ] Update `DATABASE_URL` with production credentials
- [ ] Update `REDIS_URL` with production host
- [ ] Run database migrations on production DB
- [ ] Set up database backups

### Security & Authentication
- [ ] Set `JWT_ENABLED=true`
- [ ] Set `VSCODE_AUTH_REQUIRED=true` (if using Auth0)
- [ ] Configure production Auth0 application
- [ ] Update CORS origins to only include production domains
- [ ] Generate new webhook secrets for all integrations
- [ ] Review and update all API keys (OpenAI, Anthropic, etc.)

### Monitoring & Logging
- [ ] Set up application monitoring (e.g., Sentry, DataDog)
- [ ] Configure log aggregation
- [ ] Set up alerts for errors and performance issues
- [ ] Configure uptime monitoring

### Performance
- [ ] Enable production-grade caching (Redis)
- [ ] Configure CDN for static assets (if applicable)
- [ ] Set up load balancer health checks using `/ping` endpoint
- [ ] Review and optimize database queries
- [ ] Enable gzip compression

### Deployment
- [ ] Set up CI/CD pipeline
- [ ] Configure auto-scaling (if using cloud)
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up backup and disaster recovery procedures
- [ ] Document rollback procedures

### Testing
- [ ] Run full integration test suite
- [ ] Perform load testing
- [ ] Security audit/penetration testing
- [ ] Verify all API endpoints work with production config
- [ ] Test authentication and authorization flows

### Documentation
- [ ] Update API documentation
- [ ] Document deployment procedures
- [ ] Create runbooks for common operations
- [ ] Document incident response procedures

## Production Deployment Command

```bash
# 1. Update environment with production values
nano backend/.env  # or copy backend/.env.production.template as template

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python -m alembic upgrade head

# 4. Start application (use process manager like systemd, supervisor, or PM2)
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8787 --workers 4
```

## Health Check Endpoints

- `GET /ping` - Minimal health check (no middleware)
- `GET /health-fast` - Fast health check (no DB dependencies)
- `GET /health` - Full health check (includes DB, Redis, etc.)

## Notes

- The current `backend/.env` is configured for DEVELOPMENT
- Use `backend/.env.production.template` as template for production configuration
- **NEVER commit** `backend/.env` with real secrets to git
- All webhook secrets and API keys should be rotated before production deploy
