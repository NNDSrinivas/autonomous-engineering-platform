# Auth0 Setup - Quick Reference Card

## 🎯 Quick Links

| Task | URL |
|------|-----|
| Auth0 Dashboard | https://manage.auth0.com |
| Sign Up | https://auth0.com/signup |
| Documentation | https://auth0.com/docs |
| Community Forum | https://community.auth0.com |

---

## 📋 Setup Checklist (10 min)

```
☐ 1. Create Auth0 account (2 min)
   → https://auth0.com/signup
   → Tenant: navralabs-dev
   → Region: US

☐ 2. Create API (3 min)
   → Applications → APIs → Create
   → Name: NAVI Platform API
   → Identifier: https://api.navralabs.com
   → Algorithm: RS256
   → Enable RBAC ✓

☐ 3. Create Web App (3 min)
   → Applications → Applications → Create
   → Name: NAVI Web App
   → Type: Regular Web Application
   → Callback: http://localhost:3030/api/auth/callback
   → Logout: http://localhost:3030

☐ 4. Enable Social (2 min)
   → Authentication → Social
   → Enable GitHub ✓
   → Enable Google ✓

☐ 5. Generate Secrets
   → Run: openssl rand -hex 32 (x2)

☐ 6. Update web/.env.local
   → Copy template below
   → Add your credentials

☐ 7. Restart dev server
   → cd web && npm run dev

☐ 8. Test login
   → http://localhost:3030/login
   → Click "Continue with GitHub"
   → Success! 🎉
```

---

## 🔑 Environment Template

**File:** `web/.env.local`

```bash
# Backend
NEXT_PUBLIC_AEP_CORE=http://localhost:8787
BACKEND_URL=http://localhost:8787

# Auth0 - REPLACE THESE VALUES
AUTH0_SECRET='<run: openssl rand -hex 32>'
AUTH0_BASE_URL='http://localhost:3030'
AUTH0_ISSUER_BASE_URL='https://YOUR-TENANT.us.auth0.com'
AUTH0_CLIENT_ID='YOUR_CLIENT_ID_FROM_AUTH0'
AUTH0_CLIENT_SECRET='YOUR_CLIENT_SECRET_FROM_AUTH0'
AUTH0_AUDIENCE='https://api.navralabs.com'
AUTH0_SCOPE='openid profile email offline_access'

# Client-side
NEXT_PUBLIC_AUTH0_DOMAIN='YOUR-TENANT.us.auth0.com'
NEXT_PUBLIC_AUTH0_CLIENT_ID='YOUR_CLIENT_ID_FROM_AUTH0'
NEXT_PUBLIC_AUTH0_AUDIENCE='https://api.navralabs.com'
```

**Replace:**
- `YOUR-TENANT` → Your tenant name (e.g., navralabs-dev)
- `YOUR_CLIENT_ID_FROM_AUTH0` → From Auth0 Dashboard
- `YOUR_CLIENT_SECRET_FROM_AUTH0` → From Auth0 Dashboard

---

## 🎯 Where to Find Credentials

### In Auth0 Dashboard:

1. **Domain:**
   - Look at top left: `navralabs-dev.us.auth0.com`

2. **Client ID & Secret:**
   - Applications → Applications → NAVI Web App
   - Settings tab
   - Top section shows:
     ```
     Domain: navralabs-dev.us.auth0.com
     Client ID: abc123...
     Client Secret: [click to reveal]
     ```

3. **API Audience:**
   - Applications → APIs → NAVI Platform API
   - Copy "Identifier": `https://api.navralabs.com`

---

## ✅ Testing Commands

```bash
# 1. Generate secrets
openssl rand -hex 32

# 2. Check environment
cd web
cat .env.local | grep AUTH0

# 3. Restart server
npm run dev

# 4. Test login
open http://localhost:3030/login

# 5. Check session
curl http://localhost:3030/api/auth/me

# 6. Test logout
open http://localhost:3030/api/auth/logout
```

---

## 🔧 Common Issues

| Issue | Fix |
|-------|-----|
| Callback URL mismatch | Add `http://localhost:3030/api/auth/callback` to Allowed Callback URLs |
| Invalid state | Clear cookies, regenerate AUTH0_SECRET |
| Audience invalid | Check AUTH0_AUDIENCE matches API identifier exactly |
| Module not found | Run `npm install @auth0/nextjs-auth0` |
| Redirect loop | Clear cookies, check AUTH0_BASE_URL (no trailing slash) |

---

## 📊 Verification Checklist

After setup:

```
✓ Can navigate to http://localhost:3030/login
✓ See "Continue with GitHub" and "Continue with Google" buttons
✓ Click GitHub → redirected to GitHub authorization
✓ Authorize → redirected back to http://localhost:3030/app/chats
✓ Not logged out (session persists)
✓ Refresh page → still logged in
✓ Navigate to /app/chats → works (not redirected to login)
✓ Navigate to /api/auth/logout → logged out
✓ Try to access /app/chats → redirected to login
```

---

## 🚀 Next Steps After Setup

1. **Test Features:**
   ```
   ✓ Chat Interface: http://localhost:3030/app/chats
   ✓ Approvals: http://localhost:3030/app/approvals-demo
   ```

2. **Enable MFA (Optional):**
   - Auth0 Dashboard → Security → Multi-factor Auth
   - Enable OTP, SMS, or Push

3. **Add More Users:**
   - Auth0 Dashboard → User Management → Users
   - Create Test User

4. **Production Setup:**
   - See: `docs/AUTH0_PRODUCTION_SETUP.md`
   - Separate tenant for production
   - Custom domain
   - Advanced security features

---

## 📞 Support

**Auth0:**
- Dashboard: https://manage.auth0.com
- Docs: https://auth0.com/docs
- Community: https://community.auth0.com

**NAVI Platform:**
- Full walkthrough: `docs/AUTH0_SETUP_WALKTHROUGH.md`
- Production guide: `docs/AUTH0_PRODUCTION_SETUP.md`
- Status: `IMPLEMENTATION_STATUS.md`

---

**Ready to set up Auth0? Let's do this! 🚀**

**Estimated time: 10 minutes**
