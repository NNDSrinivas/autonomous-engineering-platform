# Device Authorization Flow for VSCode Extension

This document describes the end-to-end OAuth 2.0 Device Authorization Grant flow that allows users to authenticate the NAVI VSCode extension through the browser-based web app.

## Overview

The device authorization flow enables secure authentication for the VSCode extension without requiring users to manually copy/paste tokens. Instead, users authenticate through their browser and authorize the extension with a simple confirmation.

## Architecture

### Components

1. **VSCode Extension** (`extensions/vscode-aep/`)
   - Initiates device code flow via `DeviceAuthService`
   - Opens browser to web app authorization page
   - Polls backend for token issuance

2. **Web App** (`web/`)
   - Handles user signup/login via Auth0
   - Displays device authorization confirmation page
   - Sends authorization approval to backend

3. **Backend API** (`backend/`)
   - Manages device code lifecycle (creation, polling, authorization)
   - Issues access tokens after successful authorization
   - Stores device codes in Redis (production) or in-memory (dev)

## Flow Diagram

```
┌─────────────┐                                    ┌──────────────┐
│   VSCode    │                                    │   Web App    │
│  Extension  │                                    │ (Next.js +   │
│             │                                    │   Auth0)     │
└──────┬──────┘                                    └───────┬──────┘
       │                                                   │
       │ 1. POST /oauth/device/start                      │
       ├──────────────────────────────────────────────────┼────►
       │                                                   │
       │ 2. Returns:                                      │
       │    {                                             │
       │      device_code: "xxx",                         │
       │      user_code: "ABCD-1234",                     │
       │      verification_uri_complete:                  │
       │        "http://localhost:3030/device/authorize?  │
       │         user_code=ABCD-1234"                     │
       │    }                                             │
       ◄────────────────────────────────────────────────┼─┤
       │                                                   │
       │ 3. Opens browser to verification_uri_complete    │
       ├──────────────────────────────────────────────►  │
       │                                                   │
       │                                                   │ 4a. User not logged in?
       │                                                   │     → Redirect to /api/auth/login
       │                                                   │       (Auth0 signup/login flow)
       │                                                   │
       │                                                   │ 4b. User returns after Auth0 login
       │                                                   │     with user_code in URL
       │                                                   │
       │                                                   │ 5. Auto-approve device
       │                                                   │    POST /oauth/device/authorize
       │                                                   │    { user_code: "ABCD-1234",
       │                                                   │      action: "approve",
       │                                                   │      user_id: "auth0|123" }
       │                                                   ├────►
       │                                                   │
       │                                                   │ 6. Device marked as authorized
       │                                                   ◄────┤
       │                                                   │
       │ 7. Polling: POST /oauth/device/poll              │
       │    { device_code: "xxx" }                        │
       ├──────────────────────────────────────────────────┼────►
       │                                                   │
       │ 8. Returns: { access_token: "yyy" }              │
       ◄────────────────────────────────────────────────┼─┤
       │                                                   │
       │ 9. Token stored securely in VSCode secrets       │
       │                                                   │
       │ 10. User sees success message in web app         │
       │                                                   │
```

## Implementation Details

### 1. Device Code Initialization

**VSCode Extension**: [`extensions/vscode-aep/src/auth/deviceAuth.ts`](../extensions/vscode-aep/src/auth/deviceAuth.ts)

```typescript
async startLogin(onStatus?: (status: AuthSignInStatus) => void): Promise<void> {
  // 1. Call backend to start device flow
  const response = await fetch(`${this.apiBaseUrl}/oauth/device/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  const data = await response.json();

  // 2. Open browser to verification page
  await vscode.env.openExternal(vscode.Uri.parse(data.verification_uri_complete));

  // 3. Start polling for authorization
  await this.pollForToken(data.device_code, data.interval, data.expires_in, emit);
}
```

**Backend**: [`backend/api/routers/oauth_device.py`](../backend/api/routers/oauth_device.py)

```python
@router.post("/device/start", response_model=DeviceCodeStartResponse)
async def start_device_code_flow(request: DeviceCodeStartRequest):
    # Generate unique device_code and human-readable user_code
    device_code = secrets.token_urlsafe(32)
    user_code = _generate_user_code()  # e.g., "ABCD-1234"

    # Store in Redis with TTL (600 seconds default)
    await _store_device_code(device_code, {
        "user_code": user_code,
        "status": "pending",
        "expires_at": int((datetime.now(timezone.utc) + timedelta(seconds=600)).timestamp()),
    })

    # Return verification URL pointing to web app
    web_app_url = settings.web_app_base_url or "http://localhost:3030"
    return DeviceCodeStartResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri=f"{web_app_url}/device/authorize",
        verification_uri_complete=f"{web_app_url}/device/authorize?user_code={user_code}",
        expires_in=600,
        interval=5,
    )
```

### 2. User Authentication & Authorization

**Web App**: [`web/app/(auth)/device/authorize/page.tsx`](../web/app/(auth)/device/authorize/page.tsx)

The device authorization page:
- Checks if user is logged in (via Auth0 session)
- If not, redirects to `/api/auth/login` with `returnTo` parameter
- After login, user returns to authorization page with `user_code` query param
- Auto-approves the device using the authenticated user's identity

```typescript
useEffect(() => {
  // Redirect to login if not authenticated
  if (!authLoading && !user) {
    const currentUrl = window.location.pathname + window.location.search;
    window.location.href = `/api/auth/login?returnTo=${encodeURIComponent(currentUrl)}`;
    return;
  }

  // Auto-approve if user_code is in URL
  if (user && searchParams.get("user_code")) {
    handleApproval(searchParams.get("user_code")!);
  }
}, [user, authLoading, searchParams]);

const handleApproval = async (code: string) => {
  const backendUrl = process.env.NEXT_PUBLIC_AEP_CORE || "http://localhost:8787";
  const response = await fetch(`${backendUrl}/oauth/device/authorize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_code: code.trim().toUpperCase(),
      action: "approve",
      user_id: user?.sub,
      org_id: user?.["https://navralabs.com/org"] || "public",
    }),
  });
  // ... handle success/error
};
```

### 3. Token Polling & Issuance

**VSCode Extension Polling**:

```typescript
private async pollForToken(deviceCode: string, interval: number, expiresIn: number) {
  const maxAttempts = Math.floor(expiresIn / interval);

  const poll = async () => {
    const response = await fetch(`${this.apiBaseUrl}/oauth/device/poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code: deviceCode }),
    });

    if (response.status === 200) {
      const data = await response.json();
      await this.storeToken(data.access_token, data.expires_in);
      // Success! Extension is now authenticated
    } else if (response.status === 428) {
      // Still pending, continue polling
      setTimeout(poll, interval * 1000);
    } else {
      // Error or denied
      throw new Error("Authorization failed");
    }
  };

  poll();
}
```

**Backend Token Issuance**:

```python
@router.post("/device/poll", response_model=DeviceCodeTokenResponse)
async def poll_device_code(request: DeviceCodePollRequest):
    device_info = await _get_device_info(request.device_code)

    if device_info["status"] == "pending":
        # Not authorized yet - return 428 to signal keep polling
        raise HTTPException(status_code=428, detail="authorization_pending")

    if device_info["status"] == "authorized":
        # Generate and store access token
        access_token = secrets.token_urlsafe(32)
        await _store_access_token(access_token, {
            "user_id": device_info["user_id"],
            "org_id": device_info["org_id"],
            "expires_at": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        })

        # Clean up device code
        await _delete_device_code(request.device_code)

        return DeviceCodeTokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=86400,  # 24 hours
        )
```

## Configuration

### Environment Variables

#### Backend (`.env`)

```bash
# Web app base URL for device authorization pages
WEB_APP_BASE_URL=http://localhost:3030  # Dev
# WEB_APP_BASE_URL=https://navralabs.com  # Production

# Public base URL for OAuth callbacks (backend API)
PUBLIC_BASE_URL=http://localhost:8787  # Dev
# PUBLIC_BASE_URL=https://api.navralabs.com  # Production

# Auth0 configuration for user authentication
AUTH0_DOMAIN=your-auth0-domain.auth0.com
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
AUTH0_AUDIENCE=https://your-api.example.com

# Redis for device code storage (production)
REDIS_URL=redis://localhost:6379/0

# Development mode (uses in-memory storage, no Auth0 required)
OAUTH_DEVICE_USE_IN_MEMORY_STORE=false
OAUTH_DEVICE_AUTO_APPROVE=false  # Auto-approve after 30s (dev only, NEVER in prod)
```

#### Web App (`web/.env.local`)

```bash
# Backend API URL
NEXT_PUBLIC_AEP_CORE=http://localhost:8787  # Dev
# NEXT_PUBLIC_AEP_CORE=https://api.navralabs.com  # Production
BACKEND_URL=http://localhost:8787

# Auth0 configuration
AUTH0_SECRET='generate-with-openssl-rand-hex-32'
AUTH0_BASE_URL='http://localhost:3030'
AUTH0_ISSUER_BASE_URL='https://your-auth0-domain.auth0.com'
AUTH0_CLIENT_ID='your-client-id'
AUTH0_CLIENT_SECRET='your-client-secret'
AUTH0_AUDIENCE='https://your-api.example.com'
```

#### VSCode Extension (`extensions/vscode-aep/.vscode/settings.json`)

```json
{
  "aep.navi.backendUrl": "http://localhost:8787"
}
```

## Development Workflow

### Local Development Setup

1. **Start Redis** (for device code storage):
   ```bash
   docker compose up -d redis
   ```

2. **Start Backend**:
   ```bash
   ./start_backend_dev.sh
   ```

3. **Start Web App**:
   ```bash
   cd web && npm run dev
   ```

4. **Launch VSCode Extension**:
   - Press `F5` in VSCode with the extension workspace open
   - This launches the extension development host

### Testing the Flow

1. In the extension development host, click "Sign in to NAVI" in the extension sidebar
2. Browser opens to `http://localhost:3030/device/authorize?user_code=XXXX-XXXX`
3. Sign up or log in via Auth0
4. After login, you're redirected back to the authorization page
5. Device is auto-approved (user_code from URL)
6. Extension receives access token and shows "Successfully signed in"

### Development Mode Options

For faster local development without Auth0:

```bash
# In backend .env
OAUTH_DEVICE_USE_IN_MEMORY_STORE=true  # Use in-memory storage (no Redis)
OAUTH_DEVICE_AUTO_APPROVE=true         # Auto-approve after 30 seconds
```

⚠️ **WARNING**: NEVER enable these in staging or production!

## Production Deployment

### Requirements

- ✅ Redis cluster for device code storage
- ✅ Auth0 tenant configured for production domain
- ✅ Web app deployed to production URL (e.g., `https://navralabs.com`)
- ✅ Backend API deployed with HTTPS (e.g., `https://api.navralabs.com`)

### Environment Configuration

```bash
# Backend production .env
WEB_APP_BASE_URL=https://navralabs.com
PUBLIC_BASE_URL=https://api.navralabs.com
REDIS_URL=redis://production-redis-cluster:6379/0
OAUTH_DEVICE_USE_IN_MEMORY_STORE=false  # MUST be false
OAUTH_DEVICE_AUTO_APPROVE=false         # MUST be false
AUTH0_DOMAIN=auth.navralabs.com
# ... other Auth0 production credentials
```

### Security Considerations

1. **Device Code TTL**: Device codes expire after 10 minutes (600 seconds)
2. **Access Token TTL**: Access tokens expire after 24 hours
3. **Redis Security**: Use TLS for Redis connections in production
4. **Auth0 Security**:
   - Enable MFA for user accounts
   - Configure allowed callback URLs
   - Use secure client secrets
5. **CORS**: Web app must be allowed in backend CORS origins

## Troubleshooting

### Extension shows "Could not open browser"

- **Cause**: VSCode failed to open the default browser
- **Solution**: Extension provides fallback actions (manual browser open, copy code)

### "Invalid user code" error in web app

- **Cause**: Device code expired (> 10 minutes old) or already used
- **Solution**: Restart sign-in flow in extension

### Extension polling times out

- **Cause**: User didn't complete authorization within timeout period
- **Solution**: Extension shows timeout error, user can retry

### Redis connection failed

- **Cause**: Redis not reachable or misconfigured
- **Solution**: Check `REDIS_URL` environment variable, ensure Redis is running

### Auth0 callback fails

- **Cause**: Misconfigured Auth0 callback URLs
- **Solution**: Verify Auth0 Application settings include all allowed callback URLs

## API Reference

### Backend Endpoints

#### `POST /oauth/device/start`

Initiate device authorization flow.

**Request**:
```json
{
  "client_id": "aep-vscode-extension",
  "scope": "read write"
}
```

**Response**:
```json
{
  "device_code": "NgAyZDJjODUxYjc1MzE...",
  "user_code": "ABCD-1234",
  "verification_uri": "http://localhost:3030/device/authorize",
  "verification_uri_complete": "http://localhost:3030/device/authorize?user_code=ABCD-1234",
  "expires_in": 600,
  "interval": 5
}
```

#### `POST /oauth/device/poll`

Poll for device authorization status.

**Request**:
```json
{
  "device_code": "NgAyZDJjODUxYjc1MzE..."
}
```

**Response (pending)**:
```
HTTP 428 Precondition Required
{
  "detail": "authorization_pending"
}
```

**Response (success)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

#### `POST /oauth/device/authorize`

Authorize a device (called by web app after user login).

**Request**:
```json
{
  "user_code": "ABCD-1234",
  "action": "approve",
  "user_id": "auth0|123456",
  "org_id": "org-1"
}
```

**Response**:
```json
{
  "message": "Device with user code ABCD-1234 has been authorized",
  "user_code": "ABCD-1234"
}
```

## Related Documentation

- [OAuth 2.0 Device Authorization Grant (RFC 8628)](https://datatracker.ietf.org/doc/html/rfc8628)
- [Auth0 Device Authorization Flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/device-authorization-flow)
- [VSCode Extension Authentication](../extensions/vscode-aep/README.md)
