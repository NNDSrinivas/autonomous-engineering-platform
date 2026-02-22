# Quick Auth0 Setup - 10 Minute Guide

## ⚡ Fast Track (Development)

### 1. Create Auth0 Account (2 min)
```
1. Go to https://auth0.com/signup
2. Sign up with your work email
3. Tenant name: navralabs-dev
4. Region: US
```

### 2. Create API (2 min)
```
Dashboard → APIs → Create API

Name: NAVI Platform API
Identifier: https://api.navralabs.com
Algorithm: RS256

Settings:
✓ Enable RBAC
✓ Add Permissions in Access Token
✓ Allow Offline Access
```

### 3. Create Web App (2 min)
```
Dashboard → Applications → Create Application

Name: NAVI Web App
Type: Regular Web Application

Allowed Callback URLs:
http://localhost:3030/api/auth/callback

Allowed Logout URLs:
http://localhost:3030

Allowed Web Origins:
http://localhost:3030
```

### 4. Enable Social Login (2 min)
```
Dashboard → Authentication → Social

✓ Enable GitHub (uses Auth0's dev keys - works immediately!)
✓ Enable Google (uses Auth0's dev keys - works immediately!)
```

### 5. Copy Credentials (1 min)

From application settings, copy:
- Domain
- Client ID
- Client Secret

### 6. Update .env.local (1 min)

```bash
# Generate secret
openssl rand -hex 32

# Update web/.env.local
AUTH0_SECRET='<generated-secret>'
AUTH0_BASE_URL='http://localhost:3030'
AUTH0_ISSUER_BASE_URL='https://navralabs-dev.us.auth0.com'
AUTH0_CLIENT_ID='<your-client-id>'
AUTH0_CLIENT_SECRET='<your-client-secret>'
AUTH0_AUDIENCE='https://api.navralabs.com'

NEXT_PUBLIC_AUTH0_DOMAIN='navralabs-dev.us.auth0.com'
NEXT_PUBLIC_AUTH0_CLIENT_ID='<your-client-id>'
```

### 7. Restart Dev Server
```bash
cd web && npm run dev
```

### 8. Test!
```
1. Go to http://localhost:3030/login
2. Click "Continue with GitHub"
3. Authorize
4. Redirected to http://localhost:3030/app/chats ✓
```

---

## 🔐 Production Setup

Follow the comprehensive guide: `docs/AUTH0_PRODUCTION_SETUP.md`

Required for production:
- ✓ MFA enabled
- ✓ Attack protection configured
- ✓ Brute force protection
- ✓ Breached password detection
- ✓ RBAC roles & permissions
- ✓ Custom actions for user sync
- ✓ Separate prod tenant
- ✓ Custom domain (auth.navralabs.com)
- ✓ Email templates customized
- ✓ Monitoring & logging

---

## 📊 What's Built

### Frontend (web/)
- ✓ Login page
- ✓ Signup page
- ✓ Social login buttons (GitHub, Google)
- ✓ Email/password form
- ✓ Forgot password flow
- ✓ Route protection middleware
- ✓ Session management
- ✓ Device authorization page (VSCode extension)

### Backend (backend/)
- ✓ User model & database
- ✓ Auth sync endpoint (`/internal/auth/sync-user`)
- ✓ RBAC middleware
- ✓ Permission decorators
- ✓ JWT validation

### Security Features
- ✓ JWT token verification (RS256)
- ✓ Role-based access control
- ✓ Permission-based authorization
- ✓ Plan-based feature gating
- ✓ Session expiry handling
- ✓ Refresh token rotation

---

## 🎯 Testing Checklist

- [ ] Sign up with GitHub → Works
- [ ] Sign up with Google → Works
- [ ] Login with GitHub → Works
- [ ] Login with email/password → Works
- [ ] Access protected route without login → Redirects to /login
- [ ] Access protected route with login → Shows page
- [ ] Logout → Clears session
- [ ] Token expiry → Redirects to login

---

## 🚀 Next: Continue Building Features

With auth working, you can now:
1. ✓ Test chat interface (authenticated)
2. ✓ Test approval system
3. → Build project management (Phase 3)
4. → Build settings & account management (Phase 4)
