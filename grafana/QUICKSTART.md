# Grafana Quick Start Guide

**Status:** ✅ Grafana is running at http://localhost:3001

**Note:** This guide is for local/dev. For production-grade setup (TLS, external DB, secrets, RBAC), see `grafana/production/README.md`.

## One-Command Startup (Recommended)

```bash
./scripts/run_grafana_local.sh
```

This starts Prometheus + Grafana, applies provisioning, and verifies the dashboards load.

### Stop / Reset

```bash
# Stop containers (keeps data)
./scripts/stop_grafana_local.sh

# Remove containers (fresh start next run)
./scripts/reset_grafana_local.sh
```

## 1. Access Grafana

Open your browser and navigate to:
```
http://localhost:3001
```

**Login Credentials:**
- Username: `admin`
- Password: `admin`
- (You'll be prompted to change the password on first login - you can skip this for local testing)

---

## 2. Configure Data Sources

### Option A: Via UI (Only if not using provisioning)

1. Go to **Configuration** → **Data Sources** (gear icon in left sidebar)
2. Click **Add data source**

#### Add Prometheus Data Source

1. Select **Prometheus**
2. Configure:
   - **Name:** `Prometheus`
   - **URL:** `http://localhost:9090` (adjust if your Prometheus is elsewhere)
   - **Access:** `Server (default)`
3. Click **Save & Test**

#### Add PostgreSQL Data Source

1. Click **Add data source** again
2. Select **PostgreSQL**
3. Configure:
   - **Name:** `PostgreSQL`
   - **Host:** `localhost:5432` (adjust for your setup)
   - **Database:** `mentor` (or your database name)
   - **User:** Your database username
   - **Password:** Your database password
   - **TLS/SSL Mode:** `disable` (for local dev)
4. Click **Save & Test**

### Option B: Via API (Only if not using provisioning)

```bash
# Add Prometheus data source
curl -X POST http://admin:admin@localhost:3001/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://localhost:9090",
    "access": "proxy",
    "isDefault": true
  }'

# Add PostgreSQL data source
curl -X POST http://admin:admin@localhost:3001/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PostgreSQL",
    "type": "postgres",
    "url": "localhost:5432",
    "database": "navi_db",
    "user": "your_username",
    "secureJsonData": {
      "password": "your_password"
    },
    "jsonData": {
      "sslmode": "disable",
      "postgresVersion": 1300
    }
  }'
```

---

## 3. Import Dashboards

### Import All 4 Dashboards

1. Go to **Dashboards** → **Import** (+ icon in left sidebar)
2. Click **Upload JSON file**
3. Import each dashboard:
   - `grafana/dashboards/navi-llm-metrics.json` → LLM Performance Metrics
   - `grafana/dashboards/navi-task-metrics.json` → Task Execution Metrics
   - `grafana/dashboards/navi-errors.json` → Error Tracking & Analysis
   - `grafana/dashboards/navi-learning.json` → Learning & Feedback System

4. For each dashboard:
   - Select the data source when prompted (Prometheus or PostgreSQL)
   - Click **Import**

### Quick Import via API

```bash
# Import LLM Metrics Dashboard
curl -X POST http://admin:admin@localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/navi-llm-metrics.json

# Import Task Metrics Dashboard
curl -X POST http://admin:admin@localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/navi-task-metrics.json

# Import Errors Dashboard
curl -X POST http://admin:admin@localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/navi-errors.json

# Import Learning Dashboard
curl -X POST http://admin:admin@localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/navi-learning.json
```

---

## 4. Start Prometheus (If Not Running)

Check if Prometheus is running:
```bash
curl -s http://localhost:9090/-/healthy || echo "Prometheus not running"
```

Start Prometheus:
```bash
# Option A: Using Docker
docker run -d -p 9090:9090 \
  --name prometheus \
  -v $(pwd)/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/prometheus/alerts:/etc/prometheus/alerts \
  prom/prometheus:latest

# Option B: Using local binary (if installed)
prometheus --config.file=prometheus/prometheus.yml
```

---

## 5. Generate Test Data

Run E2E validation to generate metrics:
```bash
# Quick validation (10-15 tests)
make e2e-validation-quick

# Full validation (100+ tests)
make e2e-validation-full
```

Or start the NAVI backend to generate real metrics:
```bash
# Start backend
cd backend
uvicorn api.main:app --reload --port 8000
```

---

## 6. View Dashboards

Navigate to each dashboard:
1. **LLM Performance Metrics** → http://localhost:3001/d/navi-llm/navi-llm-performance-metrics
2. **Task Execution Metrics** → http://localhost:3001/d/navi-tasks/navi-task-execution-metrics
3. **Error Tracking** → http://localhost:3001/d/navi-errors/navi-error-tracking
4. **Learning System** → http://localhost:3001/d/navi-learning/navi-learning-feedback-system

---

## 7. Verify SLO Alerts (Optional)

Check if Prometheus is loading alert rules:
```bash
# Check alert rules
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.type=="alerting") | {alert: .name, state: .state}'
```

---

## Troubleshooting

### Grafana Not Starting
```bash
# Check container logs
docker logs grafana

# Restart container
docker restart grafana
```

### Data Sources Not Connecting
- **Prometheus:** Ensure it's running on port 9090
- **PostgreSQL:** Check connection string and credentials
- **Network:** For Docker, use `host.docker.internal` instead of `localhost`

### Dashboards Show No Data
1. Check data sources are configured correctly
2. Ensure Prometheus is scraping metrics (check http://localhost:9090/targets)
3. Run E2E tests to generate data: `make e2e-validation-quick`
4. Check time range in dashboard (top-right corner)

### Port 3001 Already in Use
```bash
# Stop Grafana
docker stop grafana && docker rm grafana

# Use different port
docker run -d -p 3002:3000 --name grafana -e "GF_SECURITY_ADMIN_PASSWORD=admin" grafana/grafana:latest

# Update URLs again
./scripts/update_grafana_urls.sh http://localhost:3002
```

---

## Next Steps

1. ✅ Import all 4 dashboards
2. ✅ Configure data sources
3. ✅ Run E2E tests to generate metrics
4. ✅ View real-time metrics in dashboards
5. ✅ Test alert firing (optional):
   ```bash
   # Simulate high latency
   curl -X POST http://localhost:8000/api/navi/autonomous \
     -H "Content-Type: application/json" \
     -d '{"message": "complex task that takes time"}'
   ```

---

## Summary

**You now have:**
- ✅ Grafana running at http://localhost:3001
- ✅ 4 production-ready dashboards configured
- ✅ 25+ SLO-based alerts defined
- ✅ Complete observability stack ready for testing

**Next:** Import dashboards and start generating metrics! 🚀
