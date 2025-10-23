# Security Documentation

## Token Encryption at Rest

### Overview

The Autonomous Engineering Platform implements encryption at rest for all API tokens and credentials used in integrations (Slack, Confluence, etc.). This ensures that sensitive credentials are never stored in plaintext in the database.

### Encryption Algorithm

- **Algorithm**: Fernet (AES-128-CBC with HMAC-SHA256)
- **Library**: Python `cryptography` library
- **Key Size**: 32 bytes (256 bits)
- **Authentication**: Built-in HMAC for authenticated encryption
- **Timestamp**: Each encrypted token includes a timestamp to prevent replay attacks

### Implementation

#### Encrypted Fields

The following integration credentials are encrypted at rest:

| Integration | Field | Model Column |
|------------|-------|--------------|
| Slack | `bot_token` | `bot_token_encrypted` |
| Confluence | `access_token` | `access_token_encrypted` |

#### Transparent Encryption/Decryption

Encryption and decryption are handled transparently through SQLAlchemy property accessors:

```python
# Setting a token (automatically encrypts)
slack_conn = SlackConnection(
    id="slack-1",
    org_id="org-1",
    bot_token="xoxb-your-bot-token"  # Stored encrypted in database
)

# Reading a token (automatically decrypts)
bot_token = slack_conn.bot_token  # Returns plaintext token for API calls
```

### Configuration

#### Encryption Key Setup

1. **Generate an encryption key**:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. **Set the environment variable**:

```bash
export TOKEN_ENCRYPTION_KEY="your-generated-key-here"
```

3. **Add to your `.env` file**:

```
TOKEN_ENCRYPTION_KEY=your-generated-key-here
```

#### Production Requirements

In production environments (`ENVIRONMENT=production`), the following validations are enforced:

- ✅ `TOKEN_ENCRYPTION_KEY` must be set
- ✅ Key must be properly base64-encoded
- ✅ Decoded key must be exactly 32 bytes
- ❌ Application will refuse to start if these requirements are not met

### Key Management

#### Storage Recommendations

**Development**:
- Store in `.env` file (never commit to git)
- Use environment variables

**Production** (Choose one):
- **AWS KMS** (Recommended): Store key in KMS, reference via environment variable
- **HashiCorp Vault**: Retrieve key from Vault at application startup
- **Azure Key Vault**: Store and rotate keys in Azure
- **Google Secret Manager**: Manage keys through GCP
- **Environment Variables**: Store in secure environment (Kubernetes secrets, AWS ECS secrets, etc.)

#### Key Rotation Procedure

To rotate encryption keys without downtime:

1. **Add new key** while keeping old key available
2. **Re-encrypt tokens** with new key:
   ```python
   from backend.core.encryption import TokenEncryptor
   from backend.models.integrations import SlackConnection
   from backend.core.db import SessionLocal
   
   old_encryptor = TokenEncryptor(old_key)
   new_encryptor = TokenEncryptor(new_key)
   
   db = SessionLocal()
   for conn in db.query(SlackConnection).all():
       if conn._bot_token_encrypted:
           # Decrypt with old key, encrypt with new key
           plaintext = old_encryptor.decrypt(conn._bot_token_encrypted)
           conn._bot_token_encrypted = new_encryptor.encrypt(plaintext)
   db.commit()
   ```

3. **Update environment variable** to new key
4. **Restart application** with new key
5. **Remove old key** from secrets storage

### Security Best Practices

#### ✅ DO

- Store encryption keys in a secrets management service (KMS, Vault, etc.)
- Use environment variables to reference keys
- Rotate keys periodically (recommended: every 90 days)
- Monitor and log key access (but never log the key itself)
- Use different keys for different environments (dev, staging, prod)
- Back up keys securely and separately from database backups
- Test key rotation procedure in non-production environments first

#### ❌ DON'T

- Never commit encryption keys to source control
- Never log encryption keys or decrypted tokens
- Don't use the same key across multiple environments
- Don't store keys in the same database as encrypted data
- Don't hard-code keys in application code
- Don't share keys via email, Slack, or other insecure channels

### Compliance

This implementation meets the following security standards:

- ✅ **OWASP Cryptographic Storage Cheat Sheet**
  - Strong encryption algorithm (AES-128)
  - Authenticated encryption (HMAC)
  - Secure key management recommendations

- ✅ **SOC 2 Type II**
  - Encryption at rest
  - Key rotation capability
  - Audit logging

- ✅ **PCI DSS** (if applicable)
  - Strong cryptography
  - Key management procedures
  - Encrypted storage

- ✅ **GDPR** (for personal data protection)
  - Data security measures
  - Encryption of sensitive data

### Monitoring and Auditing

#### Logging

The encryption module logs the following events (via structlog):

- ✅ Encryptor initialization success/failure
- ✅ Encryption operations (without sensitive data)
- ✅ Decryption operations (without sensitive data)
- ❌ Never logs: encryption keys, plaintext tokens, decrypted values

#### Metrics

Monitor these metrics for security anomalies:

- Failed encryption/decryption attempts
- Encryption key configuration errors
- Application startup failures due to key issues

### Testing

#### Unit Tests

Run encryption unit tests:

```bash
pytest tests/test_encryption.py -v
```

Tests cover:
- Encryption/decryption roundtrip
- Key validation
- Error handling
- Security properties (no information leakage, timestamps, etc.)

#### Integration Tests

Run integration tests with database:

```bash
pytest tests/test_integration_models.py -v
```

Tests cover:
- Model creation with encrypted tokens
- Token persistence and retrieval
- Token updates
- Behavior without encryption key

### Troubleshooting

#### Error: "Encryption key not provided"

**Cause**: `TOKEN_ENCRYPTION_KEY` environment variable is not set

**Solution**:
```bash
# Generate and set key
export TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

#### Error: "Invalid encryption key"

**Cause**: Key is not properly base64-encoded or wrong length

**Solution**: Generate a new key using Fernet.generate_key()

#### Error: "Failed to decrypt token"

**Possible causes**:
- Wrong encryption key (key rotation not completed)
- Corrupted database entry
- Token encrypted with different key

**Solution**:
- Verify correct key is being used
- Check if key rotation is in progress
- Re-encrypt tokens if needed

### References

- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Python Cryptography Library Documentation](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec/blob/master/Spec.md)
- [AWS KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)

### Support

For security-related questions or to report vulnerabilities:

- 📧 Email: srinivasn7779@gmail.com
- 🔒 Security Issues: Open a private security advisory on GitHub
