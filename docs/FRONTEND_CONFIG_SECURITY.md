# Frontend Configuration Security

## Overview

The frontend Auth0 configuration uses environment variables to keep sensitive credentials out of the repository. This document explains how to set up and manage the configuration securely.

## Configuration Files

- `frontend/auth_config.template.json` - Template with placeholder variables (committed to git)
- `frontend/auth_config.json` - Generated config with actual values (ignored by git)
- `scripts/generate_frontend_config.py` - Script to generate config from environment variables

## Required Environment Variables

Add these to your `.env` file:

```bash
# Auth0 Configuration (for frontend auth_config.json)
AUTH0_DOMAIN=your-auth0-domain.com
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_AUDIENCE=https://your-api-audience.com
```

## Setup Instructions

### 1. Development Setup

```bash
# 1. Copy environment template (if not already done)
cp .env.example .env

# 2. Add your Auth0 credentials to .env file
# Edit .env and add the AUTH0_* variables

# 3. Generate frontend configuration
python scripts/generate_frontend_config.py

# 4. Verify configuration
cat frontend/auth_config.json
```

### 2. Production Setup

For production deployments, ensure the environment variables are set in your deployment environment:

```bash
# Set via environment variables
export AUTH0_DOMAIN="auth.yourcompany.com"
export AUTH0_CLIENT_ID="your_production_client_id"
export AUTH0_AUDIENCE="https://api.yourcompany.com"

# Generate config
python scripts/generate_frontend_config.py
```

### 3. CI/CD Setup

In your CI/CD pipeline, add the environment variables as secrets and generate the config during build:

```yaml
# Example GitHub Actions step
- name: Generate Frontend Config
  env:
    AUTH0_DOMAIN: ${{ secrets.AUTH0_DOMAIN }}
    AUTH0_CLIENT_ID: ${{ secrets.AUTH0_CLIENT_ID }}  
    AUTH0_AUDIENCE: ${{ secrets.AUTH0_AUDIENCE }}
  run: python scripts/generate_frontend_config.py
```

## Security Benefits

✅ **No hardcoded credentials** in repository  
✅ **Environment-specific configuration** (dev/staging/prod)  
✅ **Audit trail** for configuration changes  
✅ **Template-based approach** prevents configuration drift  
✅ **CI/CD friendly** with secret management integration

## Troubleshooting

### Missing Configuration Error
If you see Auth0 configuration errors, run:
```bash
python scripts/generate_frontend_config.py
```

### Environment Variable Issues
Check that all required variables are set:
```bash
echo "Domain: $AUTH0_DOMAIN"
echo "Client: $AUTH0_CLIENT_ID"  
echo "Audience: $AUTH0_AUDIENCE"
```

### Template Changes
When updating the template, regenerate the configuration:
```bash
# After modifying frontend/auth_config.template.json
python scripts/generate_frontend_config.py
```