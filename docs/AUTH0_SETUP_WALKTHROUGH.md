# Auth0 Setup - Step-by-Step Walkthrough

**Time Required:** 10 minutes
**Cost:** Free (up to 7,500 monthly active users)

---

## 🎯 Overview

We'll set up:
1. Auth0 account
2. API (authorization server)
3. Web application
4. Social connections (GitHub, Google)
5. Copy credentials to your project

---

## 📝 Step 1: Create Auth0 Account (2 minutes)

### 1.1 Sign Up

1. **Go to:** https://auth0.com/signup
2. **Click:** "Sign up"
3. **Choose:** Sign up with GitHub (recommended) OR enter email
4. **If using email:**
   - Enter your work email
   - Create password
   - Verify email

### 1.2 Complete Account Setup

You'll be asked:

**What will you be building?**
- Select: **"Web App"**

**What's your app name?**
- Enter: **"NAVI"**

**What tech stack?**
- Select: **"Next.js"**

**Where is your app hosted?**
- Select: **"Self-hosted"**

**Click:** "Create Account"

### 1.3 Choose Tenant

**Tenant domain:** This is important!
- You'll see: `your-tenant-name.us.auth0.com`
- Recommended: `navralabs-dev` (for development)
- **Region:** United States (or closest to you)
- Click: **"Create"**

✅ **You now have an Auth0 account!**

---

## 📝 Step 2: Create API (3 minutes)

This defines your backend authorization server.

### 2.1 Navigate to APIs

1. In Auth0 Dashboard, click **"Applications"** in left sidebar
2. Click **"APIs"** tab
3. Click **"+ Create API"** button

### 2.2 Fill in API Details

```
Name: NAVI Platform API
Identifier: https://api.navralabs.com
Signing Algorithm: RS256
```

**Important:**
- The "Identifier" is your API audience - use exactly `https://api.navralabs.com`
- RS256 is recommended for production (asymmetric encryption)

Click **"Create"**

### 2.3 Configure API Settings

You should now see the API settings page.

**Go to "Settings" tab:**

Enable these checkboxes:
```
✓ Enable RBAC
✓ Add Permissions in the Access Token
✓ Allow Skipping User Consent
✓ Allow Offline Access
```

**Token Settings:**
```
Token Expiration: 86400 (24 hours)
Token Expiration For Browser Flows: 7200 (2 hours)
```

Click **"Save"** at the bottom

### 2.4 Define Permissions (Optional, but recommended)

Click **"Permissions"** tab

Add these permissions one by one:

| Permission | Description |
|------------|-------------|
| `read:chats` | View chat sessions |
| `write:chats` | Create and edit chats |
| `delete:chats` | Delete chats |
| `read:projects` | View projects |
| `write:projects` | Create and edit projects |
| `delete:projects` | Delete projects |
| `read:settings` | View user settings |
| `write:settings` | Modify user settings |

Click **"Add"** after each one.

✅ **API created!**

---

## 📝 Step 3: Create Web Application (3 minutes)

### 3.1 Navigate to Applications

1. Click **"Applications"** in left sidebar
2. Click **"Applications"** tab (not APIs)
3. Click **"+ Create Application"**

### 3.2 Create Application

```
Name: NAVI Web App
Application Type: Regular Web Applications
```

Click **"Create"**

### 3.3 Configure Application Settings

You'll see the application settings page. This is where you'll get your credentials!

**Go to "Settings" tab** (should already be there)

**Scroll down to "Application URIs":**

```
Allowed Callback URLs:
http://localhost:3030/api/auth/callback,https://app.navralabs.com/api/auth/callback

Allowed Logout URLs:
http://localhost:3030,https://app.navralabs.com

Allowed Web Origins:
http://localhost:3030,https://app.navralabs.com

Allowed Origins (CORS):
http://localhost:3030,https://app.navralabs.com
```

**Note:** Add both localhost (dev) and production URLs, separated by commas

**Scroll down to "Advanced Settings":**

Click **"Advanced Settings"** accordion

**Go to "Grant Types" tab:**

Enable:
```
✓ Authorization Code
✓ Refresh Token
✓ Client Credentials
```

Disable:
```
✗ Implicit
✗ Password
✗ MFA
```

**Go to "Refresh Token Rotation" tab:**

```
✓ Rotation
Reuse Interval: 10 seconds
Absolute Lifetime: 2592000 seconds (30 days)
Inactivity Lifetime: 1296000 seconds (15 days)
```

**Scroll to bottom and click "Save Changes"**

### 3.4 Copy Credentials

**At the top of the Settings page, you'll see:**

```
Domain: navralabs-dev.us.auth0.com
Client ID: aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
Client Secret: [Click to reveal]
```

**Copy these three values - you'll need them soon!**

✅ **Web app created!**

---

## 📝 Step 4: Enable Social Connections (2 minutes)

This is the easiest part!

### 4.1 Navigate to Social Connections

1. Click **"Authentication"** in left sidebar
2. Click **"Social"**

### 4.2 Enable GitHub

1. Find **"GitHub"** in the list
2. Click the **toggle switch** to enable it
3. A dialog appears - you have two options:

**Option A: Use Auth0's Development Keys (Quickest)**
- Just click **"Save"** or **"Continue"**
- Auth0 provides test keys for development
- **Limitation:** Shows "Auth0" as the app name during login

**Option B: Use Your Own GitHub OAuth App (Recommended)**
- Click **"Use my own keys"**
- **Open new tab:** https://github.com/settings/developers
- Click **"New OAuth App"**
- Fill in:
  ```
  Application name: NAVI by Navra Labs
  Homepage URL: https://navralabs.com
  Authorization callback URL: https://navralabs-dev.us.auth0.com/login/callback
  ```
- Click **"Register application"**
- Copy **Client ID** and **Client Secret**
- Paste into Auth0
- Click **"Save"**

### 4.3 Enable Google

1. Find **"Google"** in the list
2. Click the **toggle switch** to enable it
3. Similar options as GitHub:

**Option A: Use Auth0's Development Keys**
- Click **"Save"**

**Option B: Use Your Own Google OAuth (if needed later)**
- Go to: https://console.cloud.google.com/apis/credentials
- Create OAuth 2.0 Client ID
- Copy credentials to Auth0

### 4.4 Connect to Application

After enabling GitHub and Google:

1. Click **"Applications"** tab at the top
2. Find **"NAVI Web App"**
3. **Toggle it ON** (should show green)
4. Click **"Save"**

✅ **Social login enabled!**

---

## 📝 Step 5: Configure Environment Variables (2 minutes)

Now let's add your Auth0 credentials to your project.

### 5.1 Generate Secrets

**Open terminal and run:**

```bash
# Generate AUTH0_SECRET (required by Next.js Auth0 SDK)
openssl rand -hex 32

# Generate AUTH0_ACTION_SECRET (for backend sync)
openssl rand -hex 32
```

Copy both outputs - you'll need them!

### 5.2 Update web/.env.local

**Open or create:** `web/.env.local`

**Add these values:**

```bash
# Backend API URL
NEXT_PUBLIC_AEP_CORE=http://localhost:8787
BACKEND_URL=http://localhost:8787

# Auth0 Configuration
AUTH0_SECRET='<paste-first-generated-secret-here>'
AUTH0_BASE_URL='http://localhost:3030'
AUTH0_ISSUER_BASE_URL='https://navralabs-dev.us.auth0.com'
AUTH0_CLIENT_ID='<paste-from-auth0-dashboard>'
AUTH0_CLIENT_SECRET='<paste-from-auth0-dashboard>'
AUTH0_AUDIENCE='https://api.navralabs.com'
AUTH0_SCOPE='openid profile email offline_access'

# For client-side (used in browser)
NEXT_PUBLIC_AUTH0_DOMAIN='navralabs-dev.us.auth0.com'
NEXT_PUBLIC_AUTH0_CLIENT_ID='<paste-same-client-id>'
NEXT_PUBLIC_AUTH0_AUDIENCE='https://api.navralabs.com'
```

**Replace:**
- `<paste-first-generated-secret-here>` → Output from first `openssl` command
- `<paste-from-auth0-dashboard>` → Values from Step 3.4
- `navralabs-dev.us.auth0.com` → Your actual tenant domain

### 5.3 Update backend/.env (Optional for now)

**Open:** `backend/.env`

**Add these lines:**

```bash
# Auth0 Configuration
AUTH0_DOMAIN=navralabs-dev.us.auth0.com
AUTH0_CLIENT_ID=<paste-same-client-id>
AUTH0_CLIENT_SECRET=<paste-same-client-secret>
AUTH0_AUDIENCE=https://api.navralabs.com
AUTH0_ISSUER_BASE_URL=https://navralabs-dev.us.auth0.com
AUTH0_ACTION_SECRET=<paste-second-generated-secret-here>
```

**Note:** This is only needed for backend user sync (Phase 2). For now, frontend auth works without it.

✅ **Environment configured!**

---

## 📝 Step 6: Test Authentication (1 minute)

### 6.1 Restart Dev Server

```bash
# Kill current server (Ctrl+C)
cd web
npm run dev
```

Server should start at: http://localhost:3030

### 6.2 Test Login Flow

1. **Open browser:** http://localhost:3030/login

2. **You should see:**
   - "Continue with GitHub" button
   - "Continue with Google" button
   - Email/password form (if database connection enabled)

3. **Click "Continue with GitHub"**

4. **You'll be redirected to GitHub:**
   - Authorize the app
   - Grant permissions

5. **You'll be redirected back to:**
   - http://localhost:3030/app/chats

6. **Success! You're logged in!** 🎉

### 6.3 Verify Session

**Check these:**

- [ ] You see the chat interface (not login page)
- [ ] Top right shows your profile (if you added that UI)
- [ ] Refresh page → still logged in
- [ ] Navigate to http://localhost:3030/app/chats → works

### 6.4 Test Logout

1. **Navigate to:** http://localhost:3030/api/auth/logout
2. **You should be logged out**
3. **Navigate to:** http://localhost:3030/app/chats
4. **You should be redirected to login page**

✅ **Authentication working!**

---

## 🔧 Troubleshooting

### Issue: "Callback URL mismatch"

**Fix:**
1. Go to Auth0 Dashboard → Applications → NAVI Web App → Settings
2. Check "Allowed Callback URLs" includes: `http://localhost:3030/api/auth/callback`
3. Click "Save Changes"
4. Clear browser cache and try again

### Issue: "Invalid state"

**Fix:**
1. Clear browser cookies for localhost:3030
2. Generate new AUTH0_SECRET: `openssl rand -hex 32`
3. Update `web/.env.local`
4. Restart dev server

### Issue: "Audience is invalid"

**Fix:**
1. Check AUTH0_AUDIENCE in `.env.local` matches API identifier
2. Should be: `https://api.navralabs.com` (exact match)

### Issue: "Cannot find module @auth0/nextjs-auth0"

**Fix:**
```bash
cd web
npm install @auth0/nextjs-auth0
npm run dev
```

### Issue: Redirect loops

**Fix:**
1. Check middleware.ts is not conflicting
2. Clear all cookies for localhost:3030
3. Ensure AUTH0_BASE_URL is `http://localhost:3030` (no trailing slash)

---

## ✅ Checklist

Before proceeding, verify:

- [ ] Auth0 account created
- [ ] API created (https://api.navralabs.com)
- [ ] Web app created with callback URLs
- [ ] GitHub and Google enabled
- [ ] Credentials copied to `web/.env.local`
- [ ] Dev server restarted
- [ ] Login with GitHub works
- [ ] Redirected to /app/chats after login
- [ ] Session persists on refresh

---

## 🎯 What's Next?

Now that auth is working, you can:

1. **Test Chat Interface**
   - Go to http://localhost:3030/app/chats
   - Create a chat session
   - Send messages
   - Test streaming responses

2. **Test Approval System**
   - Go to http://localhost:3030/app/approvals-demo
   - Try different risk levels
   - Approve/reject actions

3. **Continue Development**
   - Phase 3: Project Management UI
   - Phase 4: Settings & Account Management
   - Phase 5: Advanced Features

---

## 📞 Need Help?

**Common Issues:**
- https://community.auth0.com (Auth0 community forum)
- https://auth0.com/docs (Official documentation)

**NAVI Platform:**
- Check `docs/AUTH0_PRODUCTION_SETUP.md` for advanced features
- Check `IMPLEMENTATION_STATUS.md` for current progress

---

**You're all set! Authentication is now working. Happy coding! 🚀**
