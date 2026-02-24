# Production-Grade Auth0 Setup Guide
## Fortune 10 Company Standards

This guide sets up Auth0 with **enterprise-level security** matching standards used by Fortune 10 companies like Microsoft, Apple, Google, and Amazon.

---

## 🏢 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Auth0 Tenant                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Production Environment (auth.navralabs.com)             │  │
│  │  ├── Applications                                         │  │
│  │  │   ├── NAVI Web App (SPA + Backend)                    │  │
│  │  │   ├── NAVI VSCode Extension (Device Flow)             │  │
│  │  │   ├── NAVI Mobile App (future)                        │  │
│  │  │   └── NAVI CLI (Machine-to-Machine)                   │  │
│  │  ├── APIs                                                 │  │
│  │  │   └── NAVI Platform API (https://api.navralabs.com)   │  │
│  │  ├── Organizations (Multi-tenancy)                        │  │
│  │  ├── Roles & Permissions (RBAC)                          │  │
│  │  └── Rules & Actions (Custom Auth Logic)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Development Environment (dev-auth.navralabs.com)        │  │
│  │  └── (Separate tenant for testing)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Step 1: Create Production Tenant

### 1.1 Sign Up for Auth0

1. Go to [auth0.com](https://auth0.com)
2. Click **"Sign Up"**
3. **Use your work email** (not personal) for better support
4. Tenant name: `navralabs` (becomes `navralabs.us.auth0.com`)
5. Region: **US** or closest to your users

**Recommended Plan:**
- **Development:** Free tier (fine for now)
- **Production:** Essential ($240/month) or Professional ($1,400/month)
  - Essential: 7,500 active users, MFA included
  - Professional: 25,000 active users, SAML, advanced features

### 1.2 Create Separate Tenants (Best Practice)

Create **3 separate tenants**:
- `navralabs-dev` - Development
- `navralabs-staging` - Staging
- `navralabs-prod` - Production

> **Why?** Isolates environments, prevents test data from polluting production, allows safe testing.

---

## 📋 Step 2: Create API (Authorization Server)

1. **Go to:** Applications → APIs → Create API

2. **Configuration:**
   ```
   Name: NAVI Platform API
   Identifier: https://api.navralabs.com
   Signing Algorithm: RS256 (recommended for production)
   ```

3. **Settings:**
   ```
   Enable RBAC: ✓ (Role-Based Access Control)
   Add Permissions in the Access Token: ✓
   Allow Skipping User Consent: ✓ (for first-party apps)
   Allow Offline Access: ✓ (refresh tokens)
   Token Expiration: 86400 (24 hours)
   Token Expiration For Browser Flows: 7200 (2 hours)
   ```

4. **Define Permissions (Scopes):**
   ```
   read:chats          - View chat sessions
   write:chats         - Create/edit chats
   delete:chats        - Delete chats
   read:projects       - View projects
   write:projects      - Create/edit projects
   delete:projects     - Delete projects
   read:settings       - View user settings
   write:settings      - Modify user settings
   admin:users         - Manage users (admin only)
   admin:org           - Manage organization
   ```

---

## 📋 Step 3: Create Applications

### 3.1 NAVI Web Application

1. **Go to:** Applications → Applications → Create Application

2. **Basic Settings:**
   ```
   Name: NAVI Web App
   Type: Regular Web Application
   Technology: Next.js
   ```

3. **Application URIs:**
   ```
   Allowed Callback URLs:
   https://app.navralabs.com/api/auth/callback
   http://localhost:3030/api/auth/callback

   Allowed Logout URLs:
   https://app.navralabs.com
   http://localhost:3030

   Allowed Web Origins:
   https://app.navralabs.com
   http://localhost:3030

   Allowed Origins (CORS):
   https://app.navralabs.com
   http://localhost:3030
   ```

4. **Advanced Settings:**

   **Grant Types:**
   ```
   ✓ Authorization Code
   ✓ Refresh Token
   ✓ Client Credentials (for server-to-server)
   ✗ Implicit (deprecated, not secure)
   ✗ Resource Owner Password (not recommended)
   ```

   **ID Token Expiration:** 36000 seconds (10 hours)

   **Refresh Token Rotation:**
   ```
   ✓ Rotation (recommended)
   ✓ Reuse Interval: 10 seconds
   Absolute Lifetime: 2592000 seconds (30 days)
   Inactivity Lifetime: 1296000 seconds (15 days)
   ```

   **Refresh Token Expiration:**
   ```
   Absolute Expiration: ✓
   Absolute Lifetime: 2592000 (30 days)
   Inactivity Expiration: ✓
   Inactivity Lifetime: 1296000 (15 days)
   ```

### 3.2 NAVI VSCode Extension (Device Flow)

1. **Create Application:**
   ```
   Name: NAVI VSCode Extension
   Type: Native
   ```

2. **Grant Types:**
   ```
   ✓ Device Code (RFC 8628)
   ✓ Refresh Token
   ```

3. **Settings:**
   ```
   Allowed Callback URLs:
   https://app.navralabs.com/device/authorized
   http://localhost:3030/device/authorized

   Device Code Settings:
   Polling Interval: 5 seconds
   ```

### 3.3 NAVI CLI (Machine-to-Machine)

1. **Create Application:**
   ```
   Name: NAVI CLI
   Type: Machine to Machine
   Authorized API: NAVI Platform API
   ```

2. **Permissions:**
   ```
   ✓ read:chats
   ✓ write:chats
   ✓ read:projects
   ✓ write:projects
   ```

---

## 📋 Step 4: Configure Social Connections (SSO)

### 4.1 GitHub

1. **Create GitHub OAuth App:**
   - Go to: https://github.com/settings/developers
   - New OAuth App
   ```
   Application name: NAVI by Navra Labs
   Homepage URL: https://navralabs.com
   Authorization callback URL:
   https://navralabs.us.auth0.com/login/callback
   ```

2. **In Auth0:**
   - Authentication → Social → GitHub
   - Client ID: `<from GitHub>`
   - Client Secret: `<from GitHub>`
   - Attributes:
     ```
     ✓ Email
     ✓ Profile
     ✓ Public repositories
     ```

### 4.2 Google

1. **Create Google OAuth Client:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID
   ```
   Application type: Web application
   Authorized redirect URIs:
   https://navralabs.us.auth0.com/login/callback
   ```

2. **In Auth0:**
   - Authentication → Social → Google
   - Client ID: `<from Google>`
   - Client Secret: `<from Google>`
   - Attributes:
     ```
     ✓ Basic Profile
     ✓ Email Address
     ```

### 4.3 Microsoft (Azure AD)

1. **Enterprise SSO for Corporate Customers:**
   - Authentication → Enterprise → Microsoft Azure AD
   - Use OpenID Connect configuration

### 4.4 Email/Password (Database Connection)

1. **Go to:** Authentication → Database → Create DB Connection

2. **Settings:**
   ```
   Name: Username-Password-Authentication
   Requires Username: ✗ (email only)
   Disable Sign Ups: ✗ (allow signups)
   ```

3. **Password Policy:** Good (recommended minimum)
   ```
   Minimum length: 12 characters
   ✓ At least one lowercase character
   ✓ At least one uppercase character
   ✓ At least one number
   ✓ At least one special character
   ```

4. **Password History:** 5 (prevent reuse of last 5 passwords)

5. **Password Dictionary:** Enabled (prevent common passwords)

---

## 📋 Step 5: Enable Multi-Factor Authentication (MFA)

### 5.1 Configure MFA

1. **Go to:** Security → Multi-factor Auth

2. **Enable Factors:**
   ```
   ✓ One-time Password (OTP) - Google Authenticator, Authy
   ✓ SMS (optional, less secure but convenient)
   ✓ Email (fallback option)
   ✓ Push Notification via Guardian (Auth0's app)
   ✓ WebAuthn with FIDO2 Security Keys (most secure)
   ```

3. **Policy:**
   ```
   Require Multi-factor Auth: Always (recommended for production)

   OR

   Use Adaptive MFA (Professional plan):
   - Risk-based: Trigger MFA on suspicious login
   - Context-based: New device, new location, unusual time
   ```

4. **Customize MFA:**
   ```
   Allow users to skip for 30 days: ✗ (enforce always)
   Allow users to enroll from multiple devices: ✓
   ```

### 5.2 Step-Up Authentication

For sensitive operations (delete account, change email), require re-authentication:

```javascript
// In your app, for sensitive operations
<Button onClick={handleDeleteAccount}>
  Delete Account
</Button>

// Trigger step-up auth
const handleDeleteAccount = () => {
  window.location.href = '/api/auth/login?prompt=login&returnTo=/settings/delete-account'
}
```

---

## 📋 Step 6: Attack Protection

### 6.1 Brute Force Protection

1. **Go to:** Security → Attack Protection → Brute Force Protection

2. **Settings:**
   ```
   ✓ Enable Brute Force Protection

   Shields:
   ✓ Block 10 failed login attempts from same IP
   ✓ Block 100 failed login attempts to same account

   Allowlist: (Trusted IPs that bypass protection)
   - Your office IP
   - CI/CD server IP

   Notification Email: security@navralabs.com
   ```

### 6.2 Suspicious IP Throttling

```
✓ Enable Suspicious IP Throttling

Pre-login: 100 requests/hour per IP
Pre-user registration: 50 requests/hour per IP
```

### 6.3 Breached Password Detection

```
✓ Enable Breached Password Detection

Action on Breached Password:
- Block login and send notification
- Force password reset

Integrate with:
✓ Have I Been Pwned (HIBP) API
```

### 6.4 Bot Detection

```
✓ Enable Bot Detection

Use CAPTCHA for:
- Sign up
- Password reset
- After 3 failed login attempts
```

---

## 📋 Step 7: Organizations (Multi-Tenancy)

For B2B SaaS with multiple companies/teams:

1. **Go to:** Organizations → Create Organization

2. **Enable Organizations:**
   ```
   Organization Name: customer-org-name
   Display Name: Customer Company Inc.
   ```

3. **Organization Settings:**
   ```
   ✓ Enable Organization-level branding
   ✓ Organization-specific connections (SSO)
   ✓ Organization-specific roles
   ```

4. **Invite Members:**
   ```
   Add users by email
   Assign roles: admin, member, viewer
   ```

5. **SSO per Organization:**
   ```
   Configure SAML/OIDC per enterprise customer
   ```

---

## 📋 Step 8: Roles & Permissions (RBAC)

### 8.1 Define Roles

1. **Go to:** User Management → Roles → Create Role

2. **Create Roles:**
   ```
   Admin
   ├── Permissions: ALL
   └── Users: Founders, CTO

   Developer
   ├── Permissions: read:*, write:chats, write:projects
   └── Users: Engineers

   Viewer
   ├── Permissions: read:*
   └── Users: Stakeholders, investors

   Free User
   ├── Permissions: read:chats, write:chats (limited)
   └── Users: Free tier customers

   Premium User
   ├── Permissions: read:*, write:*, delete:chats
   └── Users: Paid tier customers
   ```

### 8.2 Assign Permissions to Roles

```
Admin Role:
✓ read:chats
✓ write:chats
✓ delete:chats
✓ read:projects
✓ write:projects
✓ delete:projects
✓ read:settings
✓ write:settings
✓ admin:users
✓ admin:org

Premium User Role:
✓ read:chats
✓ write:chats
✓ delete:chats
✓ read:projects
✓ write:projects
✓ delete:projects
✓ read:settings
✓ write:settings
✗ admin:users
✗ admin:org
```

---

## 📋 Step 9: Custom Authentication Logic (Actions)

Auth0 Actions = serverless functions that execute during auth flows.

### 9.1 Add User to Database (Post-Login)

1. **Go to:** Actions → Flows → Login

2. **Create Action:**
   ```javascript
   /**
   * Handler that will be called during the execution of a PostLogin flow.
   * @param {Event} event - Details about the user and the context in which they are logging in.
   * @param {PostLoginAPI} api - Interface whose methods can be used to change the behavior of the login.
   */
   exports.onExecutePostLogin = async (event, api) => {
     const axios = require('axios');

     // Check if user exists in your database
     const userPayload = {
       auth0_user_id: event.user.user_id,
       email: event.user.email,
       name: event.user.name,
       avatar_url: event.user.picture,
       email_verified: event.user.email_verified
     };

     try {
       // Call your backend to create/update user
       await axios.post('https://api.navralabs.com/internal/auth/sync-user', userPayload, {
         headers: {
           'X-Auth0-Action-Secret': event.secrets.BACKEND_SECRET
         }
       });

       // Add custom claims to token
       api.idToken.setCustomClaim('https://navralabs.com/user_id', event.user.user_id);
       api.idToken.setCustomClaim('https://navralabs.com/roles', event.authorization.roles);
       api.accessToken.setCustomClaim('https://navralabs.com/roles', event.authorization.roles);

     } catch (error) {
       console.error('Failed to sync user:', error);
       // Don't block login, but log error
     }
   };
   ```

3. **Add Secrets:**
   ```
   BACKEND_SECRET: <your backend API secret>
   ```

### 9.2 Enforce Email Verification

```javascript
exports.onExecutePostLogin = async (event, api) => {
  if (!event.user.email_verified) {
    api.access.deny('Please verify your email before logging in.');
  }
};
```

### 9.3 Add User Metadata

```javascript
exports.onExecutePostLogin = async (event, api) => {
  // First login? Set onboarding metadata
  if (event.stats.logins_count === 1) {
    api.user.setAppMetadata('onboarding_completed', false);
    api.user.setAppMetadata('created_at', new Date().toISOString());
  }

  // Track last login
  api.user.setAppMetadata('last_login_at', event.time);
  api.user.setAppMetadata('last_login_ip', event.request.ip);
};
```

### 9.4 Rate Limiting by Plan

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const userPlan = event.user.app_metadata?.subscription_plan || 'free';

  // Add plan to token
  api.idToken.setCustomClaim('https://navralabs.com/plan', userPlan);
  api.accessToken.setCustomClaim('https://navralabs.com/plan', userPlan);
};
```

---

## 📋 Step 10: Branding & User Experience

### 10.1 Universal Login Customization

1. **Go to:** Branding → Universal Login

2. **Customize:**
   ```
   Logo: Upload NAVI logo (SVG, 280x280px)
   Primary Color: #00C9FF (your brand color)
   Page Background: Dark gradient matching your app
   ```

3. **Advanced Customization (HTML):**
   ```html
   <!DOCTYPE html>
   <html>
   <head>
     <title>NAVI Sign In</title>
     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
     {%- auth0:head -%}
     <style>
       body {
         background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
       }
       .main-container {
         max-width: 450px;
         margin: 0 auto;
       }
       /* Add your custom styles */
     </style>
   </head>
   <body>
     <div class="main-container">
       {%- auth0:widget -%}
     </div>
   </body>
   </html>
   ```

### 10.2 Email Templates

Customize all email templates:

1. **Verification Email:**
   ```
   Subject: Verify your NAVI account

   Hi {{user.name}},

   Welcome to NAVI! Please verify your email address:

   {{url}}

   This link expires in 24 hours.

   Thanks,
   The NAVI Team
   ```

2. **Password Reset:**
   ```
   Subject: Reset your NAVI password

   Hi {{user.name}},

   Click here to reset your password:

   {{url}}

   This link expires in 1 hour.

   If you didn't request this, ignore this email.
   ```

3. **MFA Enrollment:**
   ```
   Subject: Secure your NAVI account with MFA

   Hi {{user.name}},

   For added security, we recommend enabling multi-factor authentication.

   Set up MFA: {{url}}
   ```

---

## 📋 Step 11: Monitoring & Logging

### 11.1 Enable Logging

1. **Go to:** Monitoring → Logs

2. **Log Streams:**
   - Send logs to: Datadog, Splunk, or custom webhook
   ```
   Events to track:
   ✓ Success Login (s)
   ✓ Failed Login (f)
   ✓ Success Signup (ss)
   ✓ Failed Signup (fs)
   ✓ Success API Operation (sapi)
   ✓ Failed API Operation (fapi)
   ✓ User Deleted (du)
   ✓ Password Change Request (pc)
   ```

### 11.2 Set Up Alerts

```
Alert on:
- 10+ failed logins from same IP (brute force)
- Login from new country
- Account takeover attempts
- Unusual API usage
```

---

## 📋 Step 12: Compliance & Security

### 12.1 GDPR Compliance

1. **Data Processing Agreement:** Sign Auth0's DPA
2. **Data Retention:**
   ```
   User data: Retained until account deletion
   Logs: 30 days (rotate)
   ```
3. **Right to be Forgotten:**
   ```
   Implement DELETE /api/users/:id endpoint
   Cascade delete all user data
   ```

### 12.2 SOC 2 / ISO 27001

- Auth0 is SOC 2 Type II and ISO 27001 certified
- Download compliance reports from dashboard

### 12.3 Session Management

```
Session Lifetime (Idle): 3 days
Session Lifetime (Absolute): 7 days
Require log in after: 30 days of inactivity
```

---

## 📋 Step 13: Production Environment Variables

Update `web/.env.production`:

```bash
# Auth0 Production Configuration
AUTH0_SECRET='<generated-with-openssl-rand-hex-32>'
AUTH0_BASE_URL='https://app.navralabs.com'
AUTH0_ISSUER_BASE_URL='https://navralabs.us.auth0.com'
AUTH0_CLIENT_ID='<production-client-id>'
AUTH0_CLIENT_SECRET='<production-client-secret>'
AUTH0_AUDIENCE='https://api.navralabs.com'
AUTH0_SCOPE='openid profile email offline_access'

# For client-side
NEXT_PUBLIC_AUTH0_DOMAIN='navralabs.us.auth0.com'
NEXT_PUBLIC_AUTH0_CLIENT_ID='<production-client-id>'
NEXT_PUBLIC_AUTH0_AUDIENCE='https://api.navralabs.com'
```

Update `web/.env.local` (development):

```bash
# Auth0 Development Configuration
AUTH0_SECRET='dev-secret-key-must-be-at-least-32-characters-long-12345678'
AUTH0_BASE_URL='http://localhost:3030'
AUTH0_ISSUER_BASE_URL='https://navralabs-dev.us.auth0.com'
AUTH0_CLIENT_ID='<dev-client-id>'
AUTH0_CLIENT_SECRET='<dev-client-secret>'
AUTH0_AUDIENCE='https://api.navralabs.com'
AUTH0_SCOPE='openid profile email offline_access'

# For client-side
NEXT_PUBLIC_AUTH0_DOMAIN='navralabs-dev.us.auth0.com'
NEXT_PUBLIC_AUTH0_CLIENT_ID='<dev-client-id>'
NEXT_PUBLIC_AUTH0_AUDIENCE='https://api.navralabs.com'
```

---

## 📋 Step 14: Testing Checklist

### Authentication Flows

- [ ] Sign up with GitHub
- [ ] Sign up with Google
- [ ] Sign up with email/password
- [ ] Login with GitHub
- [ ] Login with Google
- [ ] Login with email/password
- [ ] Password reset flow
- [ ] Email verification flow
- [ ] MFA enrollment
- [ ] MFA login
- [ ] Logout
- [ ] Session expiry
- [ ] Refresh token rotation

### Security

- [ ] Brute force protection triggers after 10 failed attempts
- [ ] Breached password detection blocks compromised passwords
- [ ] Bot detection shows CAPTCHA
- [ ] Rate limiting works
- [ ] CORS properly configured
- [ ] CSRF protection enabled
- [ ] JWT validation works

### Edge Cases

- [ ] Unverified email can't log in
- [ ] Deleted user can't log in
- [ ] Suspended user can't log in
- [ ] Token expiry redirects to login
- [ ] Invalid token returns 401

---

## 🚀 Migration Plan

### Phase 1: Development (Week 1)
- Set up dev tenant
- Configure social connections
- Test auth flows

### Phase 2: Staging (Week 2)
- Set up staging tenant
- Configure MFA
- Load test with 1000 concurrent users

### Phase 3: Production (Week 3)
- Set up production tenant
- Enable all security features
- Go live

---

## 📊 Cost Estimation

```
Auth0 Pricing (Monthly):

Free Tier:
- 7,500 active users/month
- Social connections: ✓
- MFA: ✓
- Rate limiting: ✓
Cost: $0

Essential Plan:
- 500 active users included
- $35 per 500 additional users
- Everything in Free +
- Custom domains
- Anomaly detection
Cost: $240/month

Professional Plan:
- 1,000 active users included
- $130 per 1,000 additional users
- Everything in Essential +
- SAML enterprise connections
- Advanced MFA
- SLA: 99.99% uptime
Cost: $1,400/month

Recommended: Start with Free, upgrade to Essential at 7,500 users
```

---

## 🎯 Success Metrics

Track these KPIs:

1. **Authentication Success Rate:** > 99.5%
2. **Average Login Time:** < 2 seconds
3. **MFA Adoption Rate:** > 80%
4. **Failed Login Attempts:** < 1% of total logins
5. **Session Duration:** ~30 minutes average
6. **Conversion Rate (Signup → Activated):** > 70%

---

## 📞 Support

**Auth0 Support:**
- Free tier: Community forums
- Paid tier: Email + phone support
- Critical issues: 24/7 support (Professional plan)

**Documentation:**
- https://auth0.com/docs
- https://community.auth0.com

---

## ✅ Final Checklist

Before going to production:

- [ ] Separate dev/staging/prod tenants created
- [ ] API configured with proper scopes
- [ ] Applications created and configured
- [ ] Social connections enabled and tested
- [ ] MFA enabled for all users
- [ ] Attack protection enabled
- [ ] Brute force protection configured
- [ ] Breached password detection enabled
- [ ] Bot detection enabled
- [ ] RBAC roles and permissions defined
- [ ] Custom actions deployed
- [ ] Branding customized
- [ ] Email templates customized
- [ ] Logging and monitoring configured
- [ ] Compliance requirements met
- [ ] All auth flows tested
- [ ] Security audit completed
- [ ] Load testing completed (staging)
- [ ] Disaster recovery plan documented

---

**This setup matches the security standards of Fortune 10 companies. You're production-ready!** 🚀
