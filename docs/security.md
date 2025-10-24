# Security Documentation

## Token Encryption

This system implements **envelope encryption** for sensitive API tokens (GitHub, JIRA, Slack, Confluence) using AWS KMS and AES-256-GCM encryption.

### Architecture

- **Envelope Encryption**: Each token is encrypted with a unique AES-256 data key
- **Key Management**: Data keys are encrypted using AWS KMS Customer Master Key (CMK)
- **Storage Format**: Encrypted tokens stored as base64 strings in database
- **Decryption**: On-demand decryption when tokens are needed for API calls

### Implementation Details

#### Encryption Process
1. Generate unique AES-256 data key via AWS KMS
2. Encrypt token using AES-GCM with 96-bit nonce
3. Encrypt data key with KMS CMK
4. Store: `version|encrypted_data_key|nonce|ciphertext` (base64 encoded)

#### Decryption Process  
1. Parse encrypted blob into components
2. Decrypt data key using KMS
3. Decrypt token using recovered data key and stored nonce
4. Return plaintext token for API usage

### Configuration

#### Required Environment Variables

```bash
# AWS KMS Key ID for token encryption
TOKEN_ENCRYPTION_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012

# AWS credentials (via IAM role, instance profile, or environment)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

#### KMS Key Policy

The KMS key must allow the application to:
- `kms:GenerateDataKey` - Generate data keys for encryption
- `kms:Decrypt` - Decrypt data keys for token retrieval

Example key policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/autonomous-platform-role"
      },
      "Action": [
        "kms:GenerateDataKey",
        "kms:Decrypt"
      ],
      "Resource": "*"
    }
  ]
}
```

### Key Rotation

#### Automatic Rotation (Recommended)
1. Enable automatic key rotation in AWS KMS (annually)
2. Old encrypted tokens remain decryptable with rotated keys
3. New tokens use the current key version

#### Manual Rotation Process
1. Create new KMS key
2. Update `TOKEN_ENCRYPTION_KEY_ID` environment variable
3. Optionally re-encrypt existing tokens:
   ```python
   # Re-encryption script (if needed)
   from backend.core.crypto import decrypt_token, encrypt_token
   
   # Decrypt with old key, encrypt with new key
   old_encrypted = connection.access_token
   plaintext = decrypt_token(old_encrypted)  # Uses old key
   new_encrypted = encrypt_token(plaintext)  # Uses new key
   connection.access_token = new_encrypted
   ```

### Security Features

#### Threat Mitigation
- **Database compromise**: Tokens encrypted, attacker needs KMS access
- **Backup exposure**: Encrypted tokens in database backups
- **Log leakage**: Only encrypted blobs logged, never plaintext
- **Memory dumps**: Plaintext tokens only in memory during API calls

#### Compliance
- **OWASP**: Follows cryptographic storage best practices
- **SOC 2**: Encryption at rest for sensitive data
- **PCI DSS**: Strong cryptography and key management (if applicable)

### Monitoring & Alerting

#### KMS CloudTrail Events
Monitor these CloudTrail events for security:
- `GenerateDataKey` - Token encryption operations
- `Decrypt` - Token decryption operations
- Failed KMS operations - Potential attacks or misconfigurations

#### Application Metrics
- Encryption/decryption success rates
- KMS operation latency
- Token encryption errors

### Incident Response

#### Suspected Token Compromise
1. **Immediate**: Revoke compromised tokens at source (GitHub/JIRA/etc.)
2. **Short-term**: Generate new tokens and re-save connections
3. **Long-term**: Investigate access logs, rotate KMS keys if needed

#### KMS Key Compromise
1. **Immediate**: Create new KMS key, update environment variable
2. **Re-encrypt**: All existing tokens with new key
3. **Monitoring**: Enhanced CloudTrail monitoring for old key usage

### Testing

#### Unit Tests
```bash
# Run crypto unit tests
pytest tests/test_crypto.py -v

# Run integration encryption tests  
pytest tests/test_integrations_encryption.py -v
```

#### Security Validation
```bash
# Verify tokens are encrypted in database
psql -c "SELECT LENGTH(access_token), access_token LIKE 'github_pat_%' FROM gh_connection;"

# Should show:
# - LENGTH > 50 (encrypted tokens are longer)  
# - LIKE result = false (no plaintext patterns)
```

### Performance Impact

- **Encryption**: ~1-2ms per token (KMS network call)
- **Decryption**: ~1-2ms per token (KMS network call)
- **Caching**: Consider token caching for high-frequency API usage
- **Batch operations**: KMS supports batch encrypt/decrypt for efficiency

### Disaster Recovery

#### KMS Key Loss
- **Prevention**: Cross-region key replication
- **Recovery**: Restore from encrypted database backups requires key access
- **Mitigation**: Regular key backups to AWS CloudHSM or external HSM

#### Database Recovery
- Encrypted tokens in backups remain encrypted
- Restore requires same KMS key access
- Test restore procedures regularly with encryption validation