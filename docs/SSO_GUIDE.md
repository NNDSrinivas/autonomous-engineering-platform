# NAVI SSO Guide (OIDC + SAML)

This guide documents the initial SSO readiness work. It exposes provider
configuration and a minimal OIDC authorize URL builder.

## 1) OIDC (Recommended)

### Multi-provider config (preferred)

Set `SSO_PROVIDERS_JSON` to a JSON array. Example covering Okta, Auth0, Azure AD, and Google:

```json
[
  {
    "id": "okta",
    "type": "oidc",
    "name": "Okta",
    "issuer": "https://your-okta-domain/oauth2/default",
    "client_id": "OKTA_CLIENT_ID",
    "client_secret": "OKTA_CLIENT_SECRET",
    "redirect_uri": "https://your-app.example.com/api/sso/oidc/callback",
    "scope": "openid profile email"
  },
  {
    "id": "auth0",
    "type": "oidc",
    "name": "Auth0",
    "issuer": "https://your-tenant.us.auth0.com",
    "client_id": "AUTH0_CLIENT_ID",
    "client_secret": "AUTH0_CLIENT_SECRET",
    "redirect_uri": "https://your-app.example.com/api/sso/oidc/callback",
    "scope": "openid profile email"
  },
  {
    "id": "azuread",
    "type": "oidc",
    "name": "Azure AD",
    "issuer": "https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0",
    "client_id": "AZURE_CLIENT_ID",
    "client_secret": "AZURE_CLIENT_SECRET",
    "redirect_uri": "https://your-app.example.com/api/sso/oidc/callback",
    "scope": "openid profile email"
  },
  {
    "id": "google",
    "type": "oidc",
    "name": "Google",
    "issuer": "https://accounts.google.com",
    "client_id": "GOOGLE_CLIENT_ID",
    "client_secret": "GOOGLE_CLIENT_SECRET",
    "redirect_uri": "https://your-app.example.com/api/sso/oidc/callback",
    "scope": "openid profile email"
  }
]
```

The backend will fetch the OIDC endpoints from the issuer’s `.well-known/openid-configuration`.
For multi-node deployments, set `REDIS_URL` so SSO state is shared across nodes.

### Legacy single-provider config

Set these environment variables:
- `SSO_OIDC_ENABLED=true`
- `SSO_OIDC_NAME=Your IdP`
- `SSO_OIDC_ISSUER=https://issuer.example.com`
- `SSO_OIDC_AUTH_URL=https://issuer.example.com/oauth2/v2/authorize`
- `SSO_OIDC_TOKEN_URL=https://issuer.example.com/oauth2/v2/token`
- `SSO_OIDC_USERINFO_URL=https://issuer.example.com/oauth2/v2/userinfo`
- `SSO_OIDC_CLIENT_ID=...`
- `SSO_OIDC_CLIENT_SECRET=...`
- `SSO_OIDC_REDIRECT_URI=https://your-app.example.com/api/sso/oidc/callback`
- `SSO_OIDC_SCOPE=openid profile email`

API endpoints:
- `GET /api/sso/providers` to list configured providers
- `GET /api/sso/oidc/authorize-url?provider=okta` to build an authorize URL

## 2) SAML (Planned)

Set these environment variables:
- `SSO_SAML_ENABLED=true`
- `SSO_SAML_NAME=Your SAML IdP`
- `SSO_SAML_ENTRYPOINT=https://idp.example.com/sso`
- `SSO_SAML_ISSUER=urn:your-app`
- `SSO_SAML_CALLBACK_URL=https://your-app.example.com/api/sso/saml/callback`

Currently, SAML endpoints are not implemented. This config is a placeholder for
enterprise integration work.
SAML callback endpoint is now available at `/api/sso/saml/callback` but requires
proper signature validation before production use.

## 3) Next Implementation Steps

- Move state storage to Redis for multi-node deployments.
- Implement SAML callback parsing and certificate validation.
- Add org-mapping + role assignment policies.
