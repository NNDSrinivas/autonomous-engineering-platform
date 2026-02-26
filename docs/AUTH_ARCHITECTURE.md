# NAVI Authentication Architecture

**Last Updated:** February 25, 2026
**Status:** Production-Ready
**Security Grade:** Fortune 500 / Enterprise

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Flow](#authentication-flow)
3. [Environment Isolation](#environment-isolation)
4. [Security Controls](#security-controls)
5. [Auth0 Configuration](#auth0-configuration)
6. [Backend JWT Validation](#backend-jwt-validation)
7. [Deployment Guide](#deployment-guide)
8. [Troubleshooting](#troubleshooting)

---

## Overview

NAVI uses **Authorization Code + PKCE** (Proof Key for Code Exchange) for authentication - the same OAuth 2.0 flow used by GitHub Desktop, Slack, Spotify, and other premium desktop applications.

### Key Features

- ✅ **Premium UX:** No device codes, no system prompts, clean flow
- ✅ **Environment Isolation:** Separate Auth0 apps for dev/staging/production
- ✅ **Auto-Detection:** Extension detects environment from backend URL
- ✅ **Enterprise Security:** Fortune 500-grade JWT validation
- ✅ **Long-Lived Sessions:** Refresh tokens with silent renewal
- ✅ **Custom Domain:** Branded Auth0 domain (`auth.navralabs.com`)

### Components

**Extension:**
- [`extensions/vscode-aep/src/auth/pkceLoopbackAuth.ts`](../extensions/vscode-aep/src/auth/pkceLoopbackAuth.ts) - PKCE implementation
- [`extensions/vscode-aep/src/auth/authConfig.ts`](../extensions/vscode-aep/src/auth/authConfig.ts) - Environment detection

**Backend:**
- [`backend/core/auth/jwt.py`](../backend/core/auth/jwt.py) - JWT validation (enterprise-grade)
- [`backend/core/auth/deps.py`](../backend/core/auth/deps.py) - FastAPI auth dependency

---

## Authentication Flow

### User Experience (15 seconds total)

1. User clicks **"Sign in"** in VS Code
2. Browser opens to Auth0 login (branded, no codes shown)
3. User signs in with Google/Email
4. Success page appears: **"✓ Signed in successfully"**
5. User closes tab or page auto-closes (if browser allows)
6. VS Code shows: **"✓ Connected as [Name]"**

### Technical Flow (11 steps)

```
┌─────────────┐
│  VS Code    │
│  Extension  │
└──────┬──────┘
       │ 1. User clicks "Sign in"
       │
       ├─────► 2. Detect environment from backendUrl
       │         (localhost → dev, api-staging → staging, api → prod)
       │
       ├─────► 3. Select Auth0 app (G5Ptc... / ZtGrp... / Vieih...)
       │
       ├─────► 4. Start HTTP server on 127.0.0.1:4312
       │
       ├─────► 5. Open browser to auth.navralabs.com/authorize
       │         with PKCE challenge (S256)
       │
       v
┌──────────────┐
│   Browser    │
└──────┬───────┘
       │ 6. User signs in with Google/Email
       │
       v
┌──────────────┐
│    Auth0     │
└──────┬───────┘
       │ 7. Redirect to http://127.0.0.1:4312/callback?code=xxx&state=yyy
       │
       v
┌──────────────┐
│  Loopback    │
│   Server     │
└──────┬───────┘
       │ 8. Validate state (CSRF protection)
       │
       ├─────► 9. Return success HTML (no vscode:// redirect)
       │
       v
┌──────────────┐
│  Extension   │
└──────┬───────┘
       │ 10. Exchange code for tokens (POST to Auth0 /oauth/token)
       │     with PKCE verifier
       │
       ├─────► 11. Store tokens in VS Code SecretStorage (encrypted)
       │
       └─────► 12. Show toast: "✓ Connected as [Name]"
```

### Security Highlights

- **PKCE (S256):** Prevents authorization code interception
- **State parameter:** Prevents CSRF attacks
- **No client secret:** Public client (safe for desktop apps)
- **Loopback server:** Captures OAuth callback securely
- **Encrypted storage:** VS Code SecretStorage (OS keychain)
- **Direct Auth0 refresh:** No backend proxy needed

---

## Environment Isolation

### Auto-Detection Logic

Extension auto-detects environment from `aep.navi.backendUrl` setting:

```typescript
// extensions/vscode-aep/src/auth/authConfig.ts
function inferEnvironment(backendUrl: string): Environment {
  const url = backendUrl.toLowerCase();

  if (url.includes('localhost') || url.includes('127.0.0.1')) {
    return 'dev';
  }

  if (url.includes('staging') || url.includes('api-staging')) {
    return 'staging';
  }

  return 'production';
}
```

### Environment Matrix

| Backend URL | Environment | Auth0 Client ID | Audience |
|-------------|-------------|-----------------|----------|
| `http://localhost:8787` | **dev** | `G5PtcWXaYKJ8JD2ktA9j40wwVnBuwOzu` | `https://api-dev.navralabs.com` |
| `https://api-staging.navralabs.com` | **staging** | `ZtGrpbrjy6LuHHz1yeTiWwfb8FKZc5QT` | `https://api-staging.navralabs.com` |
| `https://api.navralabs.com` | **production** | `VieiheBGMQu3rSq4fyqtjCZj3H9Q0Alq` | `https://api.navralabs.com` |

### Isolation Benefits

✅ **Dev tokens cannot access production API**
✅ **Staging tokens cannot access production API**
✅ **Each environment has separate Auth0 Native app**
✅ **Backend enforces audience validation per environment**
✅ **No cross-environment token leakage**

---

## Security Controls

### Extension Security (PKCE Flow)

1. **PKCE (Proof Key for Code Exchange)**
   - Algorithm: S256 (SHA-256)
   - Code verifier: 32 bytes random
   - Code challenge: base64url(SHA256(verifier))
   - **Prevents:** Authorization code interception

2. **State Parameter**
   - 24 bytes random, base64url encoded
   - Validated on callback
   - **Prevents:** CSRF attacks

3. **Loopback Server**
   - Binds to 127.0.0.1:4312 (localhost only)
   - 2-minute timeout
   - Single-use (closes after callback)
   - **Prevents:** Port conflicts, hanging servers

4. **Encrypted Token Storage**
   - VS Code SecretStorage API
   - Uses OS keychain (Keychain on macOS, Credential Manager on Windows, Secret Service on Linux)
   - **Prevents:** Token theft from disk

5. **Refresh Token Rotation**
   - Auto-refresh 60 seconds before expiry
   - Supports rotation if Auth0 configured
   - **Prevents:** Token expiration, stale tokens

### Backend Security (JWT Validation)

**File:** `backend/core/auth/jwt.py`

#### 1. JWKS Signature Verification

```python
# Line 102-111
jwk_key = _get_jwks_key(token, settings.JWT_JWKS_URL)
payload = jwt.decode(
    token,
    jwk_key,
    algorithms=["RS256", "RS384", "RS512"],
    audience=settings.JWT_AUDIENCE,
    issuer=settings.JWT_ISSUER,
)
```

**Controls:**
- Fetches public keys from `https://auth.navralabs.com/.well-known/jwks.json`
- Caches JWKS with 5-minute TTL
- Only accepts RS256/384/512 algorithms

#### 2. Strict `kid` (Key ID) Matching

```python
# Line 57-66
kid = headers.get("kid")
if not kid:
    raise JWTVerificationError("Token missing required 'kid' header")

keys = _fetch_jwks(jwks_url)
for key in keys:
    if key.get("kid") == kid:
        return key

# SECURITY: Fail if kid doesn't match any known key
raise JWTVerificationError(f"No matching key found for kid: {kid}")
```

**Prevents:**
- Key confusion attacks
- Fallback to wrong key
- Tokens with missing `kid`

#### 3. Algorithm Validation

```python
# Line 96-102
unverified_header = jwt.get_unverified_header(token)
alg = unverified_header.get("alg")
if not alg or alg.lower() == "none":
    raise JWTVerificationError("Token algorithm cannot be 'none'")
if alg not in ["RS256", "RS384", "RS512"]:
    raise JWTVerificationError(f"Unsupported algorithm: {alg}")
```

**Prevents:**
- `alg=none` attacks
- Algorithm confusion attacks
- Weak algorithms (HS256 with public key)

#### 4. Authorized Party (azp) Validation

```python
# Line 113-124
azp = payload.get("azp") or payload.get("client_id")
if azp:
    valid_client_ids = {
        "G5PtcWXaYKJ8JD2ktA9j40wwVnBuwOzu",  # NAVI VSCode (Dev)
        "ZtGrpbrjy6LuHHz1yeTiWwfb8FKZc5QT",  # NAVI VSCode (Staging)
        "VieiheBGMQu3rSq4fyqtjCZj3H9Q0Alq",  # NAVI VSCode (Production)
    }
    if azp not in valid_client_ids:
        logger.warning(f"Invalid authorized party rejected: {azp}")
        raise JWTVerificationError(f"Invalid authorized party: {azp}")
```

**Prevents:**
- Tokens from unauthorized applications
- Tokens from malicious OAuth clients
- Cross-client token reuse

#### 5. Audience Validation

```python
# Line 107
audience=settings.JWT_AUDIENCE
```

**Enforces:**
- Dev backend only accepts `https://api-dev.navralabs.com`
- Staging backend only accepts `https://api-staging.navralabs.com`
- Production backend only accepts `https://api.navralabs.com`

**Prevents:**
- Dev tokens from calling production API
- Cross-environment token leakage

#### 6. Issuer Validation

```python
# Line 108
issuer=settings.JWT_ISSUER
```

**Enforces:**
- All tokens must be issued by `https://auth.navralabs.com/`

**Prevents:**
- Tokens from rogue Auth0 tenants
- Tokens from other identity providers

#### 7. Expiration Validation

Automatic via `python-jose` library:
- Validates `exp` (expiration time)
- Validates `iat` (issued at)
- Allows small clock skew (configurable)

#### 8. Security Logging

```python
# Line 126-138
except ExpiredSignatureError as e:
    logger.warning("JWT verification failed: token expired")
    raise JWTVerificationError("Token has expired") from e
except JWTClaimsError as e:
    logger.warning(
        "JWT verification failed: invalid claims",
        extra={"audience": settings.JWT_AUDIENCE, "issuer": settings.JWT_ISSUER}
    )
    raise JWTVerificationError("Invalid token claims") from e
```

**Provides:**
- Structured logging for security monitoring
- No secrets leaked in logs
- Failure reason tracking

---

## Auth0 Configuration

### Auth0 Tenant

- **Tenant:** `dev-nr76km00xa82ok15.us.auth0.com`
- **Custom Domain:** `auth.navralabs.com` ✅
- **Region:** US

### Native Applications (3 separate apps)

#### 1. NAVI VSCode (Dev)

```
Client ID: G5PtcWXaYKJ8JD2ktA9j40wwVnBuwOzu
Type: Native (Public Client)
Grant Types: Authorization Code, Refresh Token
Callback URLs: http://127.0.0.1:4312/callback, http://localhost:4312/callback
Logout URLs: http://127.0.0.1:4312/logout, http://localhost:4312/logout
API Access: Authorized for navi-api-dev (https://api-dev.navralabs.com)
```

#### 2. NAVI VSCode (Staging)

```
Client ID: ZtGrpbrjy6LuHHz1yeTiWwfb8FKZc5QT
Type: Native (Public Client)
Grant Types: Authorization Code, Refresh Token
Callback URLs: http://127.0.0.1:4312/callback, http://localhost:4312/callback
Logout URLs: http://127.0.0.1:4312/logout, http://localhost:4312/logout
API Access: Authorized for navi-api-staging (https://api-staging.navralabs.com)
```

#### 3. NAVI VSCode (Production)

```
Client ID: VieiheBGMQu3rSq4fyqtjCZj3H9Q0Alq
Type: Native (Public Client)
Grant Types: Authorization Code, Refresh Token
Callback URLs: http://127.0.0.1:4312/callback, http://localhost:4312/callback
Logout URLs: http://127.0.0.1:4312/logout, http://localhost:4312/logout
API Access: Authorized for navi-api (https://api.navralabs.com)
```

### Auth0 APIs (3 separate APIs)

#### 1. navi-api-dev

```
Identifier: https://api-dev.navralabs.com
Allow Offline Access: ON (enables refresh tokens)
Token Lifetime: 900 seconds (15 minutes)
```

#### 2. navi-api-staging

```
Identifier: https://api-staging.navralabs.com
Allow Offline Access: ON (enables refresh tokens)
Token Lifetime: 900 seconds (15 minutes)
```

#### 3. navi-api (Production)

```
Identifier: https://api.navralabs.com
Allow Offline Access: ON (enables refresh tokens)
Token Lifetime: 900 seconds (15 minutes)
```

### Scopes

All Native apps request the same scopes:

```
openid profile email offline_access
```

- `openid`: OpenID Connect authentication
- `profile`: User profile information (name, picture)
- `email`: User email address
- `offline_access`: Refresh token for long-lived sessions

---

## Backend JWT Validation

### Configuration by Environment

#### Development (Local)

```bash
# backend/.env
JWT_ENABLED=false  # Dev uses bypass mode
ALLOW_DEV_AUTH_BYPASS=true
AUTH0_DEVICE_CLIENT_ID=G5PtcWXaYKJ8JD2ktA9j40wwVnBuwOzu
AUTH0_AUDIENCE=https://api-dev.navralabs.com
AUTH0_ISSUER_BASE_URL=https://auth.navralabs.com
```

#### Staging

```bash
# Staging deployment .env
JWT_ENABLED=true
ALLOW_DEV_AUTH_BYPASS=false
JWT_JWKS_URL=https://auth.navralabs.com/.well-known/jwks.json
JWT_AUDIENCE=https://api-staging.navralabs.com
JWT_ISSUER=https://auth.navralabs.com/
AUTH0_DEVICE_CLIENT_ID=ZtGrpbrjy6LuHHz1yeTiWwfb8FKZc5QT
AUTH0_AUDIENCE=https://api-staging.navralabs.com
AUTH0_ISSUER_BASE_URL=https://auth.navralabs.com
```

#### Production

```bash
# Production deployment .env
JWT_ENABLED=true
ALLOW_DEV_AUTH_BYPASS=false
JWT_JWKS_URL=https://auth.navralabs.com/.well-known/jwks.json
JWT_AUDIENCE=https://api.navralabs.com
JWT_ISSUER=https://auth.navralabs.com/
AUTH0_DEVICE_CLIENT_ID=VieiheBGMQu3rSq4fyqtjCZj3H9Q0Alq
AUTH0_AUDIENCE=https://api.navralabs.com
AUTH0_ISSUER_BASE_URL=https://auth.navralabs.com
```

### Authentication Path

```
FastAPI Route
  ↓
backend/core/auth/deps.py::get_current_user()
  ↓
backend/core/auth/jwt.py::verify_token()
  ↓
backend/core/auth/jwt.py::decode_jwt()
  ↓
[All Security Checks]
  - Algorithm validation
  - JWKS signature verification
  - Strict kid matching
  - Audience validation
  - Issuer validation
  - azp validation
  - Expiration validation
  ↓
Return User object
```

---

## Deployment Guide

### Extension Deployment

**No configuration needed!** Extension is packaged with environment detection.

Users just need to:
1. Install NAVI extension from marketplace
2. Set `aep.navi.backendUrl` (optional, defaults to production)
3. Click "Sign in"

### Backend Deployment

#### Staging Deployment

1. **Set environment variables:**
   ```bash
   JWT_ENABLED=true
   ALLOW_DEV_AUTH_BYPASS=false
   JWT_JWKS_URL=https://auth.navralabs.com/.well-known/jwks.json
   JWT_AUDIENCE=https://api-staging.navralabs.com
   JWT_ISSUER=https://auth.navralabs.com/
   ```

2. **Deploy backend to staging**

3. **Test end-to-end:**
   - Point extension to staging: `aep.navi.backendUrl` = `https://api-staging.navralabs.com`
   - Sign in
   - Verify token validation works

#### Production Deployment

1. **Set environment variables:**
   ```bash
   JWT_ENABLED=true
   ALLOW_DEV_AUTH_BYPASS=false
   JWT_JWKS_URL=https://auth.navralabs.com/.well-known/jwks.json
   JWT_AUDIENCE=https://api.navralabs.com
   JWT_ISSUER=https://auth.navralabs.com/
   ```

2. **Deploy backend to production**

3. **Test end-to-end:**
   - Extension uses production by default (or set `aep.navi.backendUrl` = `https://api.navralabs.com`)
   - Sign in
   - Verify token validation works

### Monitoring

**Key metrics to track:**
- JWT validation success/failure rate
- Token refresh success/failure rate
- Invalid `azp` rejections (security incidents)
- Algorithm confusion attempts (security incidents)
- Missing `kid` attempts (security incidents)

**Log queries:**
```bash
# JWT validation failures
grep "JWT verification failed" backend.log

# Invalid authorized party (potential security incident)
grep "Invalid authorized party rejected" backend.log

# Missing kid (potential security incident)
grep "Token missing required 'kid' header" backend.log

# Algorithm attacks (potential security incident)
grep "Token algorithm cannot be 'none'" backend.log
```

---

## Troubleshooting

### Extension Issues

**Issue:** "Login timed out"
- **Cause:** User didn't complete login within 2 minutes
- **Solution:** Try again, complete login faster

**Issue:** "State mismatch (possible CSRF attack)"
- **Cause:** CSRF attack attempt OR browser/extension state desync
- **Solution:** Reload VS Code window and try again

**Issue:** "Port 4312 already in use"
- **Cause:** Another process is using the loopback port
- **Solution:** `lsof -ti:4312 | xargs kill -9`

### Backend Issues

**Issue:** 401 "Token has expired"
- **Cause:** Access token expired, refresh failed
- **Solution:** Sign in again (extension should auto-refresh)

**Issue:** 401 "Invalid token claims"
- **Cause:** Audience or issuer mismatch
- **Solution:** Verify `JWT_AUDIENCE` and `JWT_ISSUER` match Auth0 config

**Issue:** 401 "Invalid authorized party: [client_id]"
- **Cause:** Token from unauthorized OAuth client
- **Solution:** Verify client ID is in the allowlist (backend/core/auth/jwt.py line 115-121)

**Issue:** 401 "No matching key found for kid: [kid]"
- **Cause:** JWKS key not found for token's `kid`
- **Solution:** Verify Auth0 JWKS URL is correct, check Auth0 key rotation

**Issue:** 401 "Token algorithm cannot be 'none'"
- **Cause:** Attempted algorithm confusion attack
- **Solution:** This is a security feature, no action needed (log incident)

### Auth0 Issues

**Issue:** "Client not authorized to access resource server"
- **Cause:** Native app not authorized to access API in Auth0
- **Solution:** Auth0 Dashboard → Applications → [App] → APIs → Authorize [API]

**Issue:** "No refresh_token returned"
- **Cause:** API doesn't have "Allow Offline Access" enabled
- **Solution:** Auth0 Dashboard → APIs → [API] → Settings → Allow Offline Access → ON

---

## Security Audit Checklist

Use this checklist to verify security configuration:

### Extension Security

- [ ] PKCE challenge uses S256 (SHA-256)
- [ ] State parameter is random (24+ bytes)
- [ ] Loopback server binds to 127.0.0.1 (not 0.0.0.0)
- [ ] Server timeout is set (2 minutes)
- [ ] Tokens stored in VS Code SecretStorage
- [ ] No tokens in code or logs
- [ ] Auto-refresh works (60s before expiry)

### Auth0 Security

- [ ] 3 separate Native apps (dev/staging/prod)
- [ ] 3 separate APIs (dev/staging/prod)
- [ ] Native apps authorized for correct APIs
- [ ] Authorization Code grant enabled
- [ ] Refresh Token grant enabled
- [ ] Callback URLs are loopback only
- [ ] Custom domain configured
- [ ] Token lifetime reasonable (15 min)

### Backend Security

- [ ] JWT validation enabled in staging/prod
- [ ] Dev auth bypass disabled in staging/prod
- [ ] JWKS URL configured correctly
- [ ] Audience matches environment
- [ ] Issuer matches Auth0 domain
- [ ] Strict `kid` matching (no fallback)
- [ ] `alg=none` rejected
- [ ] `azp` allowlist enforced
- [ ] Security logging enabled
- [ ] Secrets not in version control

---

## References

- [OAuth 2.0 Authorization Code Flow](https://oauth.net/2/grant-types/authorization-code/)
- [RFC 7636: PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [Auth0 Native Apps](https://auth0.com/docs/get-started/applications/application-settings/native-app-settings)
- [VS Code SecretStorage API](https://code.visualstudio.com/api/references/vscode-api#SecretStorage)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)

---

**Maintained by:** Navra Labs Engineering
**Security Contact:** security@navralabs.com
**Last Security Audit:** February 25, 2026
