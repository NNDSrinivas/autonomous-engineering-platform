# NAVI Setup Guide: API Keys and Environment Configuration

## 🔐 Setting Up OpenAI API Key

### For Development (Local Testing)

#### Option 1: Environment Variable (Recommended)
```bash
# macOS/Linux - Add to ~/.zshrc or ~/.bashrc
export OPENAI_API_KEY="sk-your-key-here"

# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"

# Windows CMD  
set OPENAI_API_KEY=sk-your-key-here
```

#### Option 2: .env File (Also Recommended)
1. Create `.env` file in project root:
```bash
cd /path/to/autonomous-engineering-platform
cp .env.template .env
```

2. Edit `.env` and add your key:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

3. **IMPORTANT**: Ensure `.env` is in `.gitignore`:
```bash
echo ".env" >> .gitignore
```

4. Install python-dotenv:
```bash
pip install python-dotenv
```

5. Load in backend (`backend/core/settings.py`):
```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
```

### For Production Deployments

#### AWS (ECS/Lambda/EC2)
```bash
# Set via AWS Console → Service → Environment Variables
OPENAI_API_KEY=sk-xxx

# Or via AWS CLI
aws lambda update-function-configuration \
  --function-name navi-backend \
  --environment "Variables={OPENAI_API_KEY=sk-xxx}"
```

#### Google Cloud (Cloud Run/GKE)
```bash
# Via gcloud CLI
gcloud run services update navi-backend \
  --set-env-vars OPENAI_API_KEY=sk-xxx
```

#### Azure (App Service/Container Instances)
```bash
# Via Azure CLI
az webapp config appsettings set \
  --name navi-backend \
  --resource-group mygroup \
  --settings OPENAI_API_KEY=sk-xxx
```

#### Docker Compose
```yaml
# docker-compose.yml
services:
  backend:
    image: navi-backend
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    env_file:
      - .env  # Load from .env file
```

#### Kubernetes
```yaml
# Create secret
apiVersion: v1
kind: Secret
metadata:
  name: navi-secrets
type: Opaque
stringData:
  openai-api-key: sk-your-key-here

---
# Use in deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: navi-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: navi-secrets
              key: openai-api-key
```

## 🚀 Running NAVI Backend

### Development Server
```bash
# 1. Set environment variable
export OPENAI_API_KEY="sk-your-key-here"

# 2. Start backend
cd backend
uvicorn api.main:app --reload --host 127.0.0.1 --port 8787

# 3. Test endpoint
curl http://127.0.0.1:8787/api/navi/health
```

### Production Server
```bash
# With gunicorn for production
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8787
```

## 🔍 Troubleshooting

### Backend Returns 500 Error

1. **Check if OpenAI key is set:**
```bash
echo $OPENAI_API_KEY
```

2. **Check backend logs:**
```bash
# Look for "[NAVI] Backend error:" messages
# These will show the actual OpenAI error
```

3. **Common issues:**
- Missing API key → Set `OPENAI_API_KEY`
- Invalid model name → Check `gpt-4-turbo-preview` vs `gpt-4o`
- Rate limiting → Wait or upgrade OpenAI plan
- Invalid key → Regenerate at platform.openai.com

### Frontend Shows "commandMenu is not defined"

Fixed in latest commit - reload VS Code extension host:
```
Cmd+Shift+P → Developer: Reload Window
```

## 🎯 Getting Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Name it "NAVI Backend"
4. Copy the key (starts with `sk-`)
5. **Save it immediately** - you can't see it again!

## 💡 Best Practices

1. **Never commit API keys** to git
2. **Use environment variables** in production
3. **Rotate keys** periodically
4. **Set usage limits** on OpenAI dashboard
5. **Monitor costs** at platform.openai.com/usage
6. **Use different keys** for dev/staging/prod

## 📝 Backend Configuration

The backend automatically detects if OpenAI is available:
- ✅ If `OPENAI_API_KEY` is set → Uses real OpenAI
- ⚠️ If key missing → Falls back to mock responses

Check health endpoint:
```bash
curl http://127.0.0.1:8787/api/navi/health
# Response: {"status": "ok", "openai_enabled": true/false}
```
