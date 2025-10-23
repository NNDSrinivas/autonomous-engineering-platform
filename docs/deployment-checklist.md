# Production Deployment Checklist

## Pre-Deployment Security Requirements

### 🔐 Token Encryption (CRITICAL - BLOCKING)

Before deploying to production, token encryption **MUST** be properly configured:

- [ ] **Generate encryption key**
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- [ ] **Store key securely**
  - AWS: Store in AWS KMS or Secrets Manager
  - Azure: Store in Azure Key Vault
  - GCP: Store in Google Secret Manager
  - Kubernetes: Store in Kubernetes Secrets
  - HashiCorp Vault: Store in Vault

- [ ] **Set environment variable**
  ```bash
  export TOKEN_ENCRYPTION_KEY="your-generated-key-here"
  ```

- [ ] **Verify production configuration**
  ```bash
  # Application will fail to start if key is missing in production
  ENVIRONMENT=production python -c "from backend.core.config import settings; print('✓ Config valid')"
  ```

- [ ] **Test encryption/decryption**
  ```bash
  export TOKEN_ENCRYPTION_KEY="your-key"
  pytest tests/test_encryption.py tests/test_integration_models.py -v
  ```

- [ ] **Backup encryption key securely**
  - Store in separate secure location
  - Document key recovery procedure
  - Test key restoration process

### 🔑 Other Security Keys

- [ ] **SECRET_KEY**: Generate and set (min 32 chars, mixed alphanumeric)
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] **JWT_SECRET**: Generate and set (min 32 chars, mixed alphanumeric)
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

### 🗄️ Database

- [ ] **Database URL**: Set production database URL
- [ ] **Migrations**: Run all migrations
  ```bash
  alembic upgrade head
  ```
- [ ] **Verify tables**: Ensure `slack_connection` and `confluence_connection` tables exist
  ```sql
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema = 'public' AND table_name LIKE '%connection';
  ```

### 🌐 API Configuration

- [ ] **CORS Origins**: Set production frontend URLs
- [ ] **API Keys**: Configure OpenAI/Anthropic API keys
- [ ] **Rate Limits**: Configure Redis for rate limiting
- [ ] **ENVIRONMENT**: Set to `production`

### 🔒 RBAC & Policy

- [ ] **Organization Policy**: Configure org policy with sensible defaults
  ```bash
  make seed-policy
  ```

- [ ] **User Roles**: Set up admin and maintainer users
- [ ] **Command Restrictions**: Configure allowed/denied commands
- [ ] **Protected Branches**: Configure protected branch list

### 📊 Monitoring & Logging

- [ ] **Prometheus**: Verify metrics endpoint `/metrics` is accessible
- [ ] **Logging**: Configure log aggregation (e.g., CloudWatch, Datadog)
- [ ] **Alerts**: Set up alerts for:
  - Failed encryption/decryption attempts
  - Invalid encryption key errors
  - Database connection failures
  - High token encryption latency

### 🧪 Pre-Deployment Testing

- [ ] **Unit Tests**: All tests pass
  ```bash
  pytest tests/ -v
  ```

- [ ] **Integration Tests**: Test with production-like configuration
  ```bash
  ENVIRONMENT=production pytest tests/ -v
  ```

- [ ] **Smoke Tests**: Test critical endpoints
  ```bash
  curl http://your-api/health
  curl http://your-api/metrics
  ```

- [ ] **Security Scan**: Run CodeQL or similar security scanner

### 📝 Documentation

- [ ] **Security Documentation**: Review `docs/security.md`
- [ ] **Runbook**: Document incident response procedures
- [ ] **Key Rotation**: Document key rotation procedure
- [ ] **Access Control**: Document who has access to encryption keys

## Deployment Steps

### 1. Pre-Deployment

- [ ] **Backup Database**: Take full database backup
- [ ] **Tag Release**: Create git tag for deployment
  ```bash
  git tag -a v1.0.0 -m "Production release with token encryption"
  git push origin v1.0.0
  ```

### 2. Deploy

- [ ] **Deploy Code**: Deploy application code
- [ ] **Set Environment Variables**: Configure all required environment variables
- [ ] **Run Migrations**: Apply database migrations
  ```bash
  alembic upgrade head
  ```

- [ ] **Start Services**: Start application services
- [ ] **Verify Health**: Check health endpoints
  ```bash
  curl https://your-api.com/health
  ```

### 3. Post-Deployment Verification

- [ ] **Verify Encryption**: Test token encryption/decryption
- [ ] **Check Metrics**: Verify Prometheus metrics are being collected
- [ ] **Check Logs**: Ensure no errors in application logs
- [ ] **Test Integrations**: Verify Slack/Confluence integrations work (if configured)
- [ ] **Monitor Performance**: Watch for any performance issues

### 4. Rollback Plan

If deployment fails:

- [ ] **Rollback Code**: Revert to previous version
- [ ] **Restore Database**: Restore from backup (if needed)
- [ ] **Verify Rollback**: Test application functionality
- [ ] **Document Issues**: Record what went wrong

## Post-Deployment

### Security Review

- [ ] **Access Logs**: Review access logs for anomalies
- [ ] **Encryption Metrics**: Verify encryption operations are working
- [ ] **Key Access**: Audit who has accessed encryption keys
- [ ] **Vulnerability Scan**: Run security vulnerability scan

### Ongoing Maintenance

- [ ] **Key Rotation Schedule**: Set up quarterly key rotation
- [ ] **Backup Verification**: Test backup restoration monthly
- [ ] **Security Updates**: Monitor for cryptography library updates
- [ ] **Compliance Audit**: Schedule regular compliance reviews

## Emergency Procedures

### Encryption Key Compromised

If encryption key is compromised:

1. **Immediately**: Rotate encryption key using documented procedure
2. **Audit**: Review all access logs to identify potential data exposure
3. **Notify**: Alert security team and potentially affected users
4. **Investigate**: Determine how key was compromised
5. **Remediate**: Fix security gap that allowed compromise
6. **Document**: Record incident and response actions

### Database Breach

If database is breached:

1. **Verify Encryption**: Confirm tokens are encrypted at rest
2. **Rotate Keys**: Immediately rotate encryption key
3. **Audit**: Review stolen data to assess impact
4. **Notify**: Alert affected users per data breach protocol
5. **Remediate**: Fix security vulnerabilities
6. **Monitor**: Watch for unauthorized API usage

## Compliance Checklist

### OWASP

- [x] Strong encryption algorithm (AES-128)
- [x] Authenticated encryption (HMAC)
- [x] Secure key management
- [x] No plaintext storage
- [x] Secure key rotation

### SOC 2

- [x] Encryption at rest
- [x] Key rotation capability
- [x] Audit logging
- [x] Access controls
- [x] Incident response plan

### PCI DSS (if applicable)

- [x] Strong cryptography
- [x] Key management procedures
- [x] Encrypted storage
- [x] Access controls
- [x] Security monitoring

### GDPR

- [x] Data security measures
- [x] Encryption of sensitive data
- [x] Breach notification procedures
- [x] Data minimization
- [x] Privacy by design

## Sign-Off

Before deploying to production, obtain sign-off from:

- [ ] **Security Team**: Approve security configuration
- [ ] **DevOps Team**: Approve infrastructure setup
- [ ] **Engineering Lead**: Approve code changes
- [ ] **Product Owner**: Approve deployment timing
- [ ] **Compliance Officer**: Approve compliance requirements

---

**Deployment Date**: _________________

**Deployed By**: _________________

**Verified By**: _________________

**Notes**: _________________________________________________
