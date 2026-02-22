# Google OAuth 2.0 Setup for NAVI Platform

**Time Required:** 5 minutes
**Purpose:** Show "navralabs.com" branding instead of "auth0.com" in Google OAuth consent screen

---

## Why Set This Up?

Currently, when users sign in with Google, they see:
> **"Sign in with Google - Choose an account to continue to auth0.com"**

After this setup, they'll see:
> **"Sign in with Google - Choose an account to continue to navralabs.com"**

This provides:
- ✅ Better branding and trust
- ✅ Professional appearance
- ✅ Full control over OAuth app settings
- ✅ Access to advanced Google OAuth features

---

## Step 1: Create Google Cloud Project (2 minutes)

### 1.1 Go to Google Cloud Console

1. **Open:** https://console.cloud.google.com
2. **Sign in** with your Google account (preferably a company account)

### 1.2 Create New Project

1. **Click** the project dropdown at the top left (next to "Google Cloud")
2. **Click** "New Project"
3. **Fill in:**
   ```
   Project name: NAVI Platform
   Organization: (Leave as "No organization" if you don't have one)
   Location: (Leave as default)
   ```
4. **Click** "Create"
5. **Wait** ~30 seconds for project creation

### 1.3 Select the Project

1. Click the project dropdown again
2. Select **"NAVI Platform"**
3. Verify the project name appears at the top

---

## Step 2: Enable Google+ API (1 minute)

### 2.1 Navigate to APIs

1. **Click** the hamburger menu (☰) at top left
2. **Navigate to:** APIs & Services → Library
3. **Search for:** "Google+ API"
4. **Click** on "Google+ API" in results
5. **Click** "Enable"

**Note:** Even though Google+ was shut down, the API is still required for OAuth profile access.

---

## Step 3: Configure OAuth Consent Screen (2 minutes)

### 3.1 Navigate to Consent Screen

1. **Click** hamburger menu (☰)
2. **Navigate to:** APIs & Services → OAuth consent screen

### 3.2 Choose User Type

**Select:** External
**Click:** "Create"

### 3.3 Fill in App Information

**App Information:**
```
App name: NAVI by Navra Labs
User support email: support@navralabs.com (or your email)
App logo: (Optional - upload NAVI logo if you have one)
```

**App domain:**
```
Application home page: https://navralabs.com
Application privacy policy link: https://navralabs.com/privacy
Application terms of service link: https://navralabs.com/terms
```

**Authorized domains:**
```
navralabs.com
auth0.com
```

**Developer contact information:**
```
Email addresses: support@navralabs.com (or your email)
```

**Click:** "Save and Continue"

### 3.4 Configure Scopes

**Click:** "Add or Remove Scopes"

**Select these scopes:**
- ✅ `.../auth/userinfo.email` - See your email address
- ✅ `.../auth/userinfo.profile` - See your personal info
- ✅ `openid` - Authenticate using OpenID Connect

**Click:** "Update"
**Click:** "Save and Continue"

### 3.5 Test Users (Optional for Development)

For now, click **"Save and Continue"**

**Note:** In "Testing" mode, only test users can sign in. To allow anyone:
1. Go back to OAuth consent screen
2. Click "Publish App"
3. Submit for verification (if you want to remove the "unverified app" warning)

For development, keep it in "Testing" mode and add yourself as a test user.

---

## Step 4: Create OAuth 2.0 Client ID (2 minutes)

### 4.1 Navigate to Credentials

1. **Click** hamburger menu (☰)
2. **Navigate to:** APIs & Services → Credentials

### 4.2 Create OAuth Client

1. **Click** "Create Credentials" at top
2. **Select:** "OAuth client ID"

### 4.3 Configure Application Type

**Application type:** Web application

**Name:** NAVI Web App (Development)

### 4.4 Add Authorized Redirect URIs

**Important:** Add ALL three environments:

```
https://dev-h2abtyfvuva0u0lb.us.auth0.com/login/callback
https://staging.navralabs.com/api/auth/callback
https://app.navralabs.com/api/auth/callback
```

**Note:** The first URL is your Auth0 tenant callback URL. Replace `dev-h2abtyfvuva0u0lb` with your actual tenant name.

**Click:** "Create"

### 4.5 Copy Credentials

A dialog will appear with:
```
Client ID: 123456789-abcdefghijklmnop.apps.googleusercontent.com
Client Secret: GOCSPX-abcdefghijklmnop1234567890
```

**⚠️ Important:** Copy both values immediately! You'll need them in the next step.

---

## Step 5: Update Auth0 Google Connection (1 minute)

### 5.1 Go to Auth0 Dashboard

1. **Open:** https://manage.auth0.com
2. **Navigate to:** Authentication → Social

### 5.2 Configure Google Connection

1. **Find:** "Google" in the list
2. **Click** the settings/gear icon
3. **Click** "Use my own keys" (if not already selected)

### 5.3 Enter Google Credentials

```
Client ID: (paste from Google Cloud Console)
Client Secret: (paste from Google Cloud Console)
```

### 5.4 Configure Attributes

**Attributes:**
- ✅ Email
- ✅ Profile

**Permissions:**
Leave as default (Basic Profile)

**Advanced Settings:**

```
Allowed Mobile Client IDs: (leave empty for now)
```

**Click:** "Save Changes"

### 5.5 Test Connection

1. **Click** "Try Connection" button
2. You should see Google's sign-in page
3. After signing in, it should show success

---

## Step 6: Test End-to-End (1 minute)

### 6.1 Restart Web App

```bash
# Kill the current dev server (Ctrl+C)
cd web
npm run dev
```

### 6.2 Test Login Flow

1. **Open:** http://localhost:3030/login
2. **Click:** "Continue with Google"
3. **You should now see:**
   - Direct redirect to Google (no Auth0 login page)
   - Google's sign-in page
   - **Important:** Check the text - it should say something about your app

4. **Sign in with your Google account**
5. **Grant permissions**
6. **You should be redirected to:** http://localhost:3030/app/chats

✅ **Success!** You're now using your own Google OAuth credentials.

---

## Troubleshooting

### "Error 400: redirect_uri_mismatch"

**Fix:**
1. Go to Google Cloud Console → Credentials
2. Edit your OAuth 2.0 Client ID
3. Check "Authorized redirect URIs" includes: `https://dev-h2abtyfvuva0u0lb.us.auth0.com/login/callback`
4. Make sure it's EXACTLY correct (no trailing slashes, correct tenant name)

### "This app isn't verified"

This is normal for apps in "Testing" mode.

**Options:**
1. **Keep in testing mode** - Add specific users as test users in Google Cloud Console
2. **Publish app** - Go to OAuth consent screen → "Publish App"
3. **Submit for verification** - Required to remove the warning permanently (takes 3-7 days)

For development, just click **"Continue"** (or "Advanced" → "Go to [Your App] (unsafe)")

### "Access blocked: This app's request is invalid"

**Fix:**
1. Go to Google Cloud Console → OAuth consent screen
2. Add `auth0.com` to "Authorized domains"
3. Save and try again

### Still seeing "continue to auth0.com"

**Check:**
1. Make sure you clicked "Save Changes" in Auth0 after entering your Google credentials
2. Clear your browser cache and cookies
3. Try in an incognito/private window
4. Check Auth0 Dashboard → Authentication → Social → Google → Verify "Use my own keys" is selected

---

## Security Best Practices

### 1. Restrict OAuth Scopes

Only request the minimum scopes needed:
- `openid` - Required for authentication
- `email` - User's email address
- `profile` - Basic profile info (name, picture)

**Don't request:**
- Gmail access
- Google Drive access
- Calendar access
- etc. (unless specifically needed)

### 2. Use Different Clients for Different Environments

**Recommended Setup:**

| Environment | OAuth Client Name | Redirect URIs |
|-------------|-------------------|---------------|
| Development | NAVI Web App (Dev) | https://dev-tenant.us.auth0.com/login/callback |
| Staging | NAVI Web App (Staging) | https://staging-tenant.us.auth0.com/login/callback |
| Production | NAVI Web App (Prod) | https://prod-tenant.us.auth0.com/login/callback |

### 3. Monitor OAuth Usage

**Google Cloud Console → APIs & Services → Dashboard**
- View API quota usage
- Set up alerts for unusual activity
- Monitor error rates

### 4. Rotate Secrets Regularly

**Best Practice:**
- Rotate OAuth Client Secrets every 90 days
- Keep old secret active for 24 hours during rotation
- Update Auth0 configuration with new secret
- Remove old secret after migration

---

## Production Checklist

Before going to production:

- [ ] OAuth consent screen configured with correct domain
- [ ] Privacy policy and Terms of Service links working
- [ ] App logo added for professional appearance
- [ ] Authorized domains include production domain
- [ ] Redirect URIs include production Auth0 tenant
- [ ] Scopes minimized to only what's needed
- [ ] Test users added (if keeping in Testing mode)
- [ ] OR App published and verified (for public access)
- [ ] Monitoring and alerts configured
- [ ] Backup of Client ID and Secret stored securely (e.g., 1Password, Vault)

---

## Verification

After setup, verify:

✅ **Branding:**
- Google sign-in shows your app name
- No "auth0.com" mentioned in user-facing text

✅ **Flow:**
- Click "Continue with Google" → Direct to Google (no Auth0 page)
- Sign in → Redirect back to your app
- User is logged in successfully

✅ **Security:**
- Only necessary scopes requested
- HTTPS used for all redirect URIs
- Secrets stored securely

---

## Next Steps

1. **Set up GitHub OAuth** (similar process)
   - Go to: https://github.com/settings/developers
   - Create OAuth App
   - Use your own keys in Auth0

2. **Configure Mobile App OAuth**
   - Create separate OAuth client for iOS/Android
   - Configure app bundle IDs

3. **Set up Production Environment**
   - Create production Google Cloud project
   - Publish OAuth consent screen
   - Submit for verification

---

**You now have full control over your Google OAuth branding!** 🎉

Users will see "navralabs.com" instead of "auth0.com" in the Google sign-in flow.
