# Staging Environment

> **Audience:** QA engineers, product managers, and developers who need to test against the live staging environment without running the backend locally.

The staging environment runs on AWS ECS Fargate and is the canonical integration environment for QA, demos, and pre-production validation.

---

## Resources

| Resource | URL / Value |
|---|---|
| **Web App** | https://staging.navralabs.com |
| **API base** | https://staging.navralabs.com/api |
| **Health check** | https://staging.navralabs.com/health/live |
| **AWS region** | `us-east-1` |
| **ECS cluster** | `aep-staging` |
| **CloudWatch logs** | `/ecs/aep-backend-staging`, `/ecs/aep-frontend-staging` |

## What's Deployed

| Component | Details |
|---|---|
| Backend | FastAPI + Uvicorn, ECS Fargate, `aep-backend-staging:latest` |
| Frontend | React + Vite + nginx, ECS Fargate, `aep-frontend-staging:latest` |
| Database | RDS PostgreSQL 15 (`aep-staging-db`) |
| Cache | ElastiCache Redis 7.1 (`aep-staging-redis`) |
| Budget enforcement | `BUDGET_ENFORCEMENT_MODE=advisory` (flip to `strict` after soak) |
| Secrets | All secrets in AWS Secrets Manager under `aep/staging/*` |

---

## Accessing Staging

### Web browser

Open https://staging.navralabs.com — no login required (`JWT_ENABLED=false` is set explicitly in the ECS task definition).

### VS Code extension — workspace files

The repo ships three workspace files. Open the right one based on what you're working on:

| Workspace file | Backend URL | When to use |
|---|---|---|
| `aep.dev.code-workspace` | `http://127.0.0.1:8787` | Local development |
| `aep.staging.code-workspace` | `https://staging.navralabs.com` | Testing against staging |
| `aep.prod.code-workspace` | `https://app.navralabs.com` | Production access (future) |

```
File → Open Workspace from File → aep.staging.code-workspace
```

The NAVI extension immediately connects to staging — no manual settings change needed.

> **Limitation:** The `.code-workspace` file only exists in this repo. If you open a different project in VS Code, the file won't be there. See the options below for using staging from any project.

> **No repo access?** Ask the team for the `navi-assistant-staging-<version>.vsix` file and install it with:
> ```bash
> code --install-extension navi-assistant-staging-<version>.vsix
> ```

### Using staging from any project / repo

The `.code-workspace` approach only works when you have the AEP repo open. If you're working in a different codebase and still want NAVI pointing at staging, use one of these instead:

**Option A — Global VS Code user setting** (applies to every project on your machine)

Open global settings (`Cmd+Shift+P` → "Open User Settings JSON") and add:

```json
"aep.navi.backendUrl": "https://staging.navralabs.com"
```

Remove it when you want to go back to local dev or production.

**Option B — Per-project `.vscode/settings.json`** (only for that specific project)

Add to `.vscode/settings.json` in the other project:

```json
{
  "aep.navi.backendUrl": "https://staging.navralabs.com"
}
```

Commit this if the whole team should use staging, or add `.vscode/settings.json` to `.gitignore` to keep it personal.

**Long-term fix — VS Code Marketplace publishing**

Once the extension is published as two separate editions (`NAVI Assistant` for prod, `NAVI Assistant Staging` for staging), users install the right edition and it always points at the correct backend — no workspace files or settings changes needed, works in any project. See [Publishing the VS Code Extension](#publishing-the-vs-code-extension-future) below.

### Checking staging health

```bash
curl https://staging.navralabs.com/health/live
curl https://staging.navralabs.com/api/health/ready
```

---

## Deploying to Staging

Run from the repo root. Requires the `navra-staging` AWS CLI profile and Docker Desktop.

### Refresh ECR credentials

```bash
aws ecr get-login-password --region us-east-1 --profile navra-staging \
  | docker login --username AWS --password-stdin 625847798833.dkr.ecr.us-east-1.amazonaws.com
```

### Build and push backend

```bash
docker buildx build --platform linux/amd64 \
  -t 625847798833.dkr.ecr.us-east-1.amazonaws.com/navralabs/aep-backend:staging \
  --push .
```

### Build and push frontend

The frontend bakes API URLs at build time via `--build-arg`:

```bash
docker buildx build --platform linux/amd64 \
  --build-arg VITE_CORE_API=https://staging.navralabs.com \
  --build-arg VITE_API_BASE_URL=https://staging.navralabs.com \
  --build-arg VITE_NAVI_BACKEND_URL=https://staging.navralabs.com \
  -t 625847798833.dkr.ecr.us-east-1.amazonaws.com/navralabs/aep-frontend:staging \
  --push ./frontend
```

### Force redeploy ECS services

```bash
aws ecs update-service --cluster aep-staging --service aep-backend-staging-svc \
  --force-new-deployment --region us-east-1 --profile navra-staging

aws ecs update-service --cluster aep-staging --service aep-frontend-staging-svc \
  --force-new-deployment --region us-east-1 --profile navra-staging
```

### Run database migrations

Run after any schema change (Alembic one-off task):

```bash
# Set these from your AWS console (VPC → Subnets / Security Groups for the staging cluster)
SUBNET_ID=subnet-xxxxxxxxxxxxxxx
SG_ID=sg-xxxxxxxxxxxxxxx

aws ecs run-task \
  --cluster aep-staging \
  --task-definition aep-backend-staging \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"aep-backend","command":["python","-m","alembic","upgrade","head"]}]}' \
  --region us-east-1 --profile navra-staging
```

---

## Publishing the VS Code Extension (Future)

Until the extension is on the VS Code Marketplace, distribute the `.vsix` file directly.

Once a Microsoft publisher account is created at https://marketplace.visualstudio.com/manage:

1. Generate a Personal Access Token in Azure DevOps (`dev.azure.com`) → User Settings → PAT → scope: `Marketplace → Manage`
2. Build and publish:

```bash
# Production extension (connects to app.navralabs.com)
cd extensions/vscode-aep
npx @vscode/vsce publish --pat <token>

# Staging extension (connects to staging.navralabs.com)
# Update package.json: name → navi-assistant-staging, default backendUrl → https://staging.navralabs.com
npx @vscode/vsce publish --pat <token>
```

Users then install via the Extensions tab: search `NAVI Assistant` (prod) or `NAVI Assistant Staging` (staging).

---

## AWS Infrastructure Reference

| Resource | ID / ARN |
|---|---|
| ECS cluster | `aep-staging` |
| Backend task definition | `aep-backend-staging` |
| Frontend task definition | `aep-frontend-staging` |
| ECR — backend | `<AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/navralabs/aep-backend` |
| ECR — frontend | `<AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/navralabs/aep-frontend` |
| ECS execution role | `NavraLabsEcsTaskExecutionRole-Staging` |
| VPC subnet | `<STAGING_SUBNET_ID>` |
| Security group | `<STAGING_SECURITY_GROUP_ID>` |
| RDS | `aep-staging-db` (PostgreSQL 15, `us-east-1`) |
| Redis | `aep-staging-redis` (ElastiCache 7.1, `us-east-1`) |
| Secrets Manager prefix | `aep/staging/*` |
| ALB | `aep-staging-alb` |
| HTTPS cert | ACM `staging.navralabs.com` (TLS 1.3) |
| Route53 record | `staging.navralabs.com` → ALB alias |

---

*For production deployment and hardening plans see [docs/NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md).*
