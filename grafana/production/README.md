# Grafana Production Setup (TLS + External DB + Secrets + RBAC)

This directory contains a production-grade Grafana configuration with:
- **TLS** termination inside Grafana (or behind a reverse proxy)
- **External PostgreSQL** for Grafana storage
- **Secrets** managed via Docker secrets
- **RBAC & admin lockdown** settings
- **Provisioned dashboards + data sources**

## What This Covers
- Grafana configuration for production
- Secure provisioning for Prometheus + NAVI Postgres data sources
- Hardening settings (no anonymous access, no signups)

## Requirements
- A public domain (e.g. `grafana.example.com`)
- TLS certs (`fullchain.pem`, `privkey.pem`)
- External Postgres for Grafana config DB
- External Postgres for NAVI metrics (llm_metrics, task_metrics, error_events, learning_*)
- Prometheus endpoint (managed or self-hosted)

## Setup

1. **Create secrets** (do not commit them)
   ```bash
   cd grafana/production/secrets
   cp grafana_admin_password.txt.example grafana_admin_password.txt
   cp grafana_db_password.txt.example grafana_db_password.txt
   cp navi_db_password.txt.example navi_db_password.txt
   ```

2. **Copy environment config**
   ```bash
   cd grafana/production
   cp .env.example .env
   # Edit .env with real values
   ```

3. **Add TLS certs**
   Place your certs here:
   - `grafana/production/tls/fullchain.pem`
   - `grafana/production/tls/privkey.pem`

4. **Start Grafana**
   ```bash
   docker compose -f grafana/production/docker-compose.prod.yml up -d
   ```

5. **Verify**
   ```bash
   curl -k https://grafana.example.com/api/health
   ```

## Admin Lockdown (Applied)
- Anonymous access disabled
- User signup disabled
- Org creation disabled
- Secure cookies enabled
- Gravatar disabled

If using SSO (OAuth/SAML), you can also set:
- `GF_AUTH_DISABLE_LOGIN_FORM=true`
- `GF_AUTH_GENERIC_OAUTH_ENABLED=true` and configure SSO URLs

## RBAC
Grafana OSS supports **org roles** (Admin/Editor/Viewer) and folder permissions.
Grafana Enterprise supports granular RBAC. If you have an Enterprise license:
- Set `GF_RBAC_ENABLED=true`
- Use folder + datasource permissions for least privilege

## Notes
- For a reverse proxy (recommended), terminate TLS at Nginx/ALB and set:
  - `GF_SERVER_PROTOCOL=https`
  - `GF_SERVER_ROOT_URL=https://grafana.example.com`
  - Remove direct port mapping to 443 if proxy handles it.

- Data sources are provisioned from:
  - `grafana/production/provisioning/datasources/datasources.yaml`
  - `grafana/production/provisioning/dashboards/dashboards.yaml`

