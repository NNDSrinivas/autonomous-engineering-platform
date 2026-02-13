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
