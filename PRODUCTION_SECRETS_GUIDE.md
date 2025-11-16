# 🔒 Production Secrets Management Guide

## ✅ Current Status: Development Setup Complete

Your OpenAI API key is now securely stored in `.env` which is **protected by .gitignore** and will never be committed to git.

---

## 🏠 Local Development (What You Just Did)

**File Structure:**
```
.env              ← Your actual secrets (NEVER commit this)
.env.example      ← Template with fake values (safe to commit)
.gitignore        ← Contains .env (already configured)
```

**How it works:**
1. `.env.example` - Template file with placeholder values (committed to git)
2. `.env` - Your real secrets (ignored by git via `.gitignore`)
3. Backend reads from environment variables at runtime

**Current Configuration:**
```bash
# .env (local only, never pushed)
OPENAI_API_KEY=sk-proj-ozLgKIn...
```

✅ **Verified Safe**: Running `git status .env` shows nothing - it's properly ignored!

---

## 🚀 Production Deployment Options

### Option 1: Docker / Docker Compose (Recommended)

**Method A: Environment Variables in docker-compose.yml**
```yaml
# docker-compose.yml
services:
  backend:
    image: your-registry/aep-backend:latest
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}  # Reads from host environment
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
    ports:
      - "8787:8787"
```

**Deploy:**
```bash
# On production server, set environment variables first:
export OPENAI_API_KEY="sk-proj-your-prod-key"
export DATABASE_URL="postgresql://..."
export JWT_SECRET="your-jwt-secret"

# Then deploy:
docker-compose up -d
```

**Method B: Docker Secrets (More Secure)**
```yaml
# docker-compose.yml
services:
  backend:
    image: your-registry/aep-backend:latest
    secrets:
      - openai_api_key
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
    
secrets:
  openai_api_key:
    external: true  # Created separately via: docker secret create
```

**Create secrets:**
```bash
echo "sk-proj-your-prod-key" | docker secret create openai_api_key -
```

---

### Option 2: Kubernetes (Cloud-Native)

**Create Kubernetes Secret:**
```bash
kubectl create secret generic aep-secrets \
  --from-literal=OPENAI_API_KEY="sk-proj-your-prod-key" \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=JWT_SECRET="your-jwt-secret" \
  --namespace=production
```

**Reference in Deployment:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aep-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        image: your-registry/aep-backend:latest
        env:
          - name: OPENAI_API_KEY
            valueFrom:
              secretKeyRef:
                name: aep-secrets
                key: OPENAI_API_KEY
          - name: DATABASE_URL
            valueFrom:
              secretKeyRef:
                name: aep-secrets
                key: DATABASE_URL
```

**Best Practice: Use Sealed Secrets or External Secrets Operator**
```bash
# Install sealed-secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Create encrypted secret (safe to commit!)
echo "sk-proj-your-key" | kubectl create secret generic aep-secrets \
  --dry-run=client --from-file=OPENAI_API_KEY=/dev/stdin -o yaml | \
  kubeseal -o yaml > sealed-secret.yaml

# Commit sealed-secret.yaml to git (encrypted, safe!)
git add sealed-secret.yaml
```

---

### Option 3: AWS

**AWS ECS (Elastic Container Service):**
```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name aep/openai-api-key \
  --secret-string "sk-proj-your-prod-key"

# Store in AWS Systems Manager Parameter Store
aws ssm put-parameter \
  --name /aep/openai-api-key \
  --value "sk-proj-your-prod-key" \
  --type SecureString
```

**ECS Task Definition:**
```json
{
  "containerDefinitions": [{
    "name": "aep-backend",
    "image": "your-registry/aep-backend:latest",
    "secrets": [
      {
        "name": "OPENAI_API_KEY",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:aep/openai-api-key"
      }
    ]
  }]
}
```

**AWS Lambda:**
```bash
# Set environment variable in Lambda console
aws lambda update-function-configuration \
  --function-name aep-backend \
  --environment "Variables={OPENAI_API_KEY=sk-proj-your-key}"

# Or use AWS Secrets Manager reference
aws lambda update-function-configuration \
  --function-name aep-backend \
  --environment "Variables={OPENAI_API_KEY_SECRET_ARN=arn:aws:secretsmanager:...}"
```

---

### Option 4: Google Cloud Platform (GCP)

**Cloud Run:**
```bash
# Set secret via gcloud CLI
gcloud run deploy aep-backend \
  --image gcr.io/your-project/aep-backend \
  --set-env-vars OPENAI_API_KEY="sk-proj-your-key"

# Or use Secret Manager (more secure)
echo "sk-proj-your-key" | gcloud secrets create openai-api-key --data-file=-

# Reference in Cloud Run
gcloud run deploy aep-backend \
  --image gcr.io/your-project/aep-backend \
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest
```

**GKE (Google Kubernetes Engine):**
```bash
# Use Google Secret Manager with Workload Identity
gcloud secrets create openai-api-key --data-file=- <<< "sk-proj-your-key"

# Grant service account access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:aep-backend@your-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

### Option 5: Microsoft Azure

**Azure App Service:**
```bash
# Set environment variable via Azure CLI
az webapp config appsettings set \
  --name aep-backend \
  --resource-group aep-rg \
  --settings OPENAI_API_KEY="sk-proj-your-key"

# Or use Azure Key Vault (more secure)
az keyvault secret set \
  --vault-name aep-keyvault \
  --name openai-api-key \
  --value "sk-proj-your-key"

# Reference in App Service
az webapp config appsettings set \
  --name aep-backend \
  --resource-group aep-rg \
  --settings OPENAI_API_KEY="@Microsoft.KeyVault(SecretUri=https://aep-keyvault.vault.azure.net/secrets/openai-api-key/)"
```

**Azure Container Instances:**
```bash
az container create \
  --name aep-backend \
  --image your-registry/aep-backend:latest \
  --secure-environment-variables OPENAI_API_KEY="sk-proj-your-key"
```

---

### Option 6: Platform-as-a-Service (PaaS)

**Heroku:**
```bash
# Set via Heroku CLI
heroku config:set OPENAI_API_KEY="sk-proj-your-key" --app aep-backend

# Or via Heroku Dashboard:
# Settings → Config Vars → Add OPENAI_API_KEY
```

**Vercel:**
```bash
# Set via Vercel CLI
vercel env add OPENAI_API_KEY production
# Paste: sk-proj-your-key

# Or via Vercel Dashboard:
# Project Settings → Environment Variables
```

**Railway:**
```bash
# Railway automatically reads .env in dashboard
# Settings → Variables → Add OPENAI_API_KEY
```

**Render:**
```yaml
# render.yaml
services:
  - type: web
    name: aep-backend
    env: docker
    envVars:
      - key: OPENAI_API_KEY
        sync: false  # Manual entry in dashboard
```

---

## 🛡️ Security Best Practices

### 1. **Never Commit Secrets to Git**
```bash
# ✅ Good: Use .env locally (in .gitignore)
# ❌ Bad: Hardcode in source code
# ❌ Bad: Commit .env file

# Verify before pushing:
git status  # .env should NOT appear
git log -p | grep -i "api.key"  # Check history
```

### 2. **Use Different Keys for Different Environments**
```bash
# Development: sk-proj-dev-key
OPENAI_API_KEY=sk-proj-ozLgKIn...

# Staging: sk-proj-staging-key
OPENAI_API_KEY=sk-proj-staging-xyz...

# Production: sk-proj-prod-key
OPENAI_API_KEY=sk-proj-prod-abc...
```

### 3. **Rotate Keys Regularly**
```bash
# Set expiration reminders (every 90 days)
# When rotating:
1. Generate new key in OpenAI dashboard
2. Update in production secret manager
3. Deploy/restart services
4. Verify new key works
5. Revoke old key
```

### 4. **Limit Key Permissions**
- Use OpenAI project-specific keys (not account-wide)
- Set rate limits on keys
- Monitor usage in OpenAI dashboard
- Set up billing alerts

### 5. **Audit Access**
```bash
# AWS: Check who can access secrets
aws secretsmanager describe-secret --secret-id aep/openai-api-key

# Kubernetes: Check RBAC
kubectl auth can-i get secrets --as=system:serviceaccount:default:aep-backend

# Docker: Restrict secret access
docker secret inspect openai_api_key --format='{{.Spec.Labels}}'
```

---

## 🧪 Testing Your Setup

### Verify Local Development:
```bash
# 1. Check .env exists and has key
cd /Users/mounikakapa/Desktop/Personal\ Projects/autonomous-engineering-platform
grep OPENAI_API_KEY .env  # Should show your key

# 2. Verify git won't commit it
git status .env  # Should show nothing

# 3. Test backend
curl http://127.0.0.1:8787/health
# Should show: "openai_configured": true

# 4. Test NAVI chat
curl -X POST http://127.0.0.1:8787/api/navi/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "mode": "chat", "model": "gpt-5.1"}'
# Should get real OpenAI response
```

### Verify Production Deployment:
```bash
# 1. Check environment variables are set (without exposing values)
# Docker:
docker exec aep-backend sh -c 'echo $OPENAI_API_KEY | cut -c1-10'  # Should show: sk-proj-oz

# Kubernetes:
kubectl exec deployment/aep-backend -- sh -c 'echo $OPENAI_API_KEY | cut -c1-10'

# 2. Test health endpoint
curl https://your-production-domain.com/health

# 3. Monitor logs for OpenAI errors
kubectl logs deployment/aep-backend | grep -i openai
```

---

## 📋 Deployment Checklist

- [ ] Local `.env` file created with real API key
- [ ] `.env` is in `.gitignore` (verified with `git status`)
- [ ] `.env.example` committed with placeholder values
- [ ] Backend starts successfully with key loaded
- [ ] Health check shows `openai_configured: true`
- [ ] NAVI returns real OpenAI responses (not mocks)
- [ ] Production secret manager chosen (AWS/GCP/Azure/K8s)
- [ ] Secrets stored in production platform (not in code)
- [ ] Different keys for dev/staging/prod environments
- [ ] Team members know how to access production secrets
- [ ] Key rotation schedule established (every 90 days)
- [ ] Billing alerts configured in OpenAI dashboard
- [ ] Access audit logs enabled

---

## 🚨 What If Secrets Get Exposed?

**If you accidentally commit secrets to git:**

1. **Immediately revoke the key:**
   ```bash
   # Go to OpenAI dashboard → API Keys → Revoke key
   ```

2. **Remove from git history:**
   ```bash
   # Use BFG Repo-Cleaner
   git clone --mirror git://github.com/your-repo.git
   java -jar bfg.jar --replace-text passwords.txt your-repo.git
   cd your-repo.git
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   git push --force
   ```

3. **Generate new key and update:**
   ```bash
   # Update .env
   echo "OPENAI_API_KEY=sk-proj-new-key" >> .env
   
   # Update production
   kubectl create secret generic aep-secrets \
     --from-literal=OPENAI_API_KEY="sk-proj-new-key" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

4. **Enable GitHub secret scanning:**
   ```bash
   # Go to: Settings → Security → Secret scanning → Enable
   ```

---

## 📚 Additional Resources

- [OpenAI API Key Management](https://platform.openai.com/docs/api-reference/authentication)
- [12-Factor App: Config](https://12factor.net/config)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [Kubernetes Secrets Management](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)

---

## 🎉 You're All Set!

Your current setup is **production-ready**:
- ✅ Secrets protected locally with `.gitignore`
- ✅ Backend running with OpenAI integration
- ✅ Clear path to production deployment

**Next Steps:**
1. Reload VS Code extension (Cmd+Shift+P → "Developer: Reload Window")
2. Open NAVI panel
3. Send "hi" message
4. You should now get **real OpenAI responses**! 🚀

For production deployment, choose one of the options above based on your infrastructure.
