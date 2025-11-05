# Installation Guide - Phase 1 Enhanced Conversational UI

## Quick Start

### 1. Prerequisites
- **VS Code**: Version 1.85.0 or higher
- **Node.js**: Version 18.0 or higher
- **Python**: Version 3.9 or higher
- **Docker** (optional): For containerized deployment

### 2. Backend Setup

#### Option A: Local Development
```bash
# Clone and navigate to project
git clone https://github.com/NNDSrinivas/autonomous-engineering-platform.git
cd autonomous-engineering-platform

# Install Python dependencies
pip install -r requirements.txt

# Set up environment
cp config/development.env .env
# Edit .env with your configuration

# Run migrations
alembic upgrade head

# Start backend services
python main.py
```

#### Option B: Docker Deployment
```bash
# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. VS Code Extension Setup

#### Install from Source
```bash
# Navigate to extension directory
cd extensions/vscode

# Install dependencies
npm install

# Build extension
npm run compile

# Package extension (optional)
npx vsce package
```

#### Install in VS Code
1. Open VS Code
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
3. Type "Extensions: Install from VSIX"
4. Select the generated `.vsix` file

#### Configure Extension
Add to your VS Code `settings.json`:
```json
{
  "aep.coreApi": "http://localhost:8002",
  "aep.enableProactiveSuggestions": true,
  "aep.chatHistoryEnabled": true,
  "aep.debugMode": false
}
```

### 4. Verify Installation

#### Test Backend
```bash
# Check health endpoint
curl http://localhost:8002/health

# Test chat API
curl -X POST http://localhost:8002/api/chat/respond \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "conversationHistory": []}'
```

#### Test VS Code Extension
1. Open VS Code
2. Press `Ctrl+Shift+P`
3. Type "AEP: Open Chat"
4. Type "Hello" in the chat panel
5. Verify you receive a response

## Detailed Configuration

### Backend Configuration

#### Environment Variables
```bash
# Core settings
API_BASE_URL=http://localhost:8002
DEBUG=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/aep_db

# JIRA Integration (optional)
JIRA_SERVER_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token

# Redis (for caching)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET=your-jwt-secret-here
```

#### Database Setup
```bash
# PostgreSQL setup
createdb aep_db

# Run migrations
alembic upgrade head

# Seed initial data (optional)
python scripts/populate_project.py
```

### VS Code Extension Configuration

#### Full Settings Schema
```json
{
  "aep.coreApi": {
    "type": "string",
    "default": "http://localhost:8002",
    "description": "Backend API base URL"
  },
  "aep.enableProactiveSuggestions": {
    "type": "boolean",
    "default": true,
    "description": "Enable proactive chat suggestions"
  },
  "aep.chatHistoryEnabled": {
    "type": "boolean",
    "default": true,
    "description": "Persist chat history across sessions"
  },
  "aep.debugMode": {
    "type": "boolean",
    "default": false,
    "description": "Enable debug logging"
  },
  "aep.logLevel": {
    "type": "string",
    "enum": ["error", "warn", "info", "debug"],
    "default": "info",
    "description": "Logging level"
  },
  "aep.autoOpenChat": {
    "type": "boolean",
    "default": false,
    "description": "Automatically open chat panel on startup"
  },
  "aep.suggestionRefreshInterval": {
    "type": "number",
    "default": 30000,
    "description": "Proactive suggestions refresh interval (ms)"
  }
}
```

## Integration Setup

### JIRA Integration

#### 1. Create API Token
1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Create new API token
3. Copy token securely

#### 2. Configure Backend
```python
# In backend/core/settings.py
JIRA_SETTINGS = {
    "server": "https://your-company.atlassian.net",
    "username": "your-email@company.com",
    "token": "your-api-token",
    "enabled": True
}
```

#### 3. Test Integration
```bash
# Test JIRA connection
curl http://localhost:8002/api/jira/test-connection
```

### Slack Integration (Optional)

#### 1. Create Slack App
1. Go to [Slack API](https://api.slack.com/apps)
2. Create new app
3. Add required scopes: `chat:write`, `users:read`

#### 2. Configure Backend
```python
SLACK_SETTINGS = {
    "bot_token": "xoxb-your-bot-token",
    "signing_secret": "your-signing-secret",
    "enabled": True
}
```

## Performance Optimization

### Backend Optimization

#### Redis Caching
```python
# Enable Redis for better performance
REDIS_SETTINGS = {
    "url": "redis://localhost:6379",
    "cache_ttl": 300,  # 5 minutes
    "enabled": True
}
```

#### Database Connections
```python
# Optimize database connection pool
DATABASE_SETTINGS = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600
}
```

### Frontend Optimization

#### VS Code Extension
- Enable WebView caching for better startup time
- Configure appropriate refresh intervals
- Use lazy loading for heavy operations

## Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check Python version
python --version  # Should be 3.9+

# Check dependencies
pip list | grep -E "(fastapi|sqlalchemy|alembic)"

# Check port availability
lsof -i :8002
```

#### Extension Not Loading
1. Check VS Code version compatibility
2. Verify extension is installed and enabled
3. Check developer console for errors:
   - `Help` → `Toggle Developer Tools`
   - Look for extension-related errors

#### Chat Panel Empty/Not Responding
1. Verify backend is running: `curl http://localhost:8002/health`
2. Check API configuration in VS Code settings
3. Enable debug mode and check logs

#### JIRA Integration Issues
```bash
# Test JIRA credentials
curl -u "email:token" https://your-company.atlassian.net/rest/api/3/myself

# Check backend logs for JIRA errors
tail -f logs/backend.log | grep -i jira
```

### Debug Mode

#### Enable Full Debugging
```json
{
  "aep.debugMode": true,
  "aep.logLevel": "debug"
}
```

#### Check Extension Logs
1. Open VS Code Developer Tools
2. Navigate to Console tab
3. Filter for "AEP" or "Chat" messages

#### Backend Logging
```python
# In backend/core/logging.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Deployment

### Production Deployment

#### Docker Production Setup
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  backend:
    image: aep-backend:latest
    environment:
      - DEBUG=false
      - LOG_LEVEL=info
      - DATABASE_URL=postgresql://prod_user:prod_pass@db:5432/aep_prod
    ports:
      - "8002:8002"
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: aep_prod
      POSTGRES_USER: prod_user
      POSTGRES_PASSWORD: prod_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

#### Extension Distribution
```bash
# Build for production
npm run compile:production

# Package for marketplace
npx vsce package --no-dependencies

# Publish to marketplace (if approved)
npx vsce publish
```

### Monitoring

#### Health Checks
- Backend: `GET /health`
- Database: Connection pool status
- Redis: Cache hit rates
- Extension: WebView load times

#### Metrics Collection
```python
# Enable metrics endpoint
MONITORING = {
    "enabled": True,
    "endpoint": "/metrics",
    "prometheus_enabled": True
}
```

## Support

### Getting Help
- GitHub Issues: [Report bugs or feature requests](https://github.com/NNDSrinivas/autonomous-engineering-platform/issues)
- Documentation: Check the `/docs/wiki/` directory
- Logs: Always include relevant logs when reporting issues

### Contributing
1. Fork the repository
2. Create feature branch
3. Follow the development guidelines
4. Submit pull request with tests

### Version Updates
```bash
# Check for updates
git fetch origin
git log --oneline HEAD..origin/main

# Update to latest
git pull origin main
pip install -r requirements.txt
npm install  # In extension directory
```