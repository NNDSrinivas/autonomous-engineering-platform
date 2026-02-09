# NAVI Grafana Dashboards

**Last Updated:** February 7, 2026

## Overview

This directory contains 4 production-ready Grafana dashboards for monitoring NAVI's performance, errors, and learning systems in real-time.

For hardened production deployment (TLS, external DB, secrets, RBAC), see:
- `grafana/production/README.md`

---

## Dashboard Inventory

| Dashboard | File | Metrics Source | Description |
|-----------|------|----------------|-------------|
| **LLM Metrics** | `navi-llm-metrics.json` | Prometheus | Token usage, costs, latency, error rates |
| **Task Metrics** | `navi-task-metrics.json` | Prometheus | Task completion rates, iterations, success/failure |
| **Error Tracking** | `navi-errors.json` | PostgreSQL | Error types, frequencies, resolution status |
| **Learning System** | `navi-learning.json` | PostgreSQL | Feedback patterns, insights, improvement trends |

---

## Dashboard Details

### 1. LLM Metrics Dashboard

**File:** `dashboards/navi-llm-metrics.json`
**Data Source:** Prometheus (`http://localhost:9090`)
**Refresh:** 5 seconds
**Time Range:** Last 1 hour

#### Panels

| Panel | Type | Description | SLO/Target |
|-------|------|-------------|-----------|
| **LLM Calls per Second** | Stat | Current rate of LLM API calls | - |
| **LLM Cost per Hour** | Stat | Hourly LLM spend | < $50/hour warning |
| **P95 Latency** | Stat | 95th percentile latency | **< 5000ms (SLO)** |
| **Error Rate** | Stat | Percentage of failed LLM calls | < 1% |
| **Call Rate by Model** | Timeseries | LLM calls broken down by model (Claude/GPT) | - |
| **Latency Percentiles** | Timeseries | P50, P95, P99 latency trends | P95 < 5000ms |
| **Token Usage by Model** | Timeseries | Input/output tokens per model | - |
| **Hourly Cost by Model** | Timeseries | Cost breakdown by model | - |
| **Calls by Phase** | Timeseries | Calls by execution phase (autonomous, planning, etc.) | - |
| **Model Usage Distribution** | Pie Chart | 24h usage split by model | - |

#### Key Metrics

```promql
# LLM call rate
sum(rate(aep_llm_calls_total[5m]))

# P95 latency (SLO metric)
histogram_quantile(0.95, rate(aep_llm_latency_ms_bucket[5m]))

# Error rate
sum(rate(aep_llm_calls_total{status="error"}[5m])) / sum(rate(aep_llm_calls_total[5m]))

# Hourly cost
sum(rate(aep_llm_cost_usd_total[1h])) * 3600
```

---

### 2. Task Metrics Dashboard

**File:** `dashboards/navi-task-metrics.json`
**Data Source:** Prometheus
**Refresh:** 5 seconds
**Time Range:** Last 1 hour

#### Panels

| Panel | Type | Description | SLO/Target |
|-------|------|-------------|-----------|
| **Task Success Rate** | Stat | Percentage of successful tasks | **≥ 95% (SLO)** |
| **Tasks per Second** | Stat | Current task execution rate | - |
| **Avg Iterations per Task** | Stat | Average iterations before completion | < 20 |
| **Avg Task Duration** | Stat | Average time to complete a task | < 60s |
| **Task Completion Rate by Status** | Timeseries | Task completion counts by status | - |
| **Avg Iterations by Status** | Timeseries | Iteration trends by task status | - |
| **Task Volume by Status** | Timeseries (Bar) | Hourly task volume by status | - |
| **Task Distribution by Status** | Pie Chart | 24h task split by status | - |
| **Task Metrics Summary (by Status)** | Table | Task metrics table grouped by status | - |

#### Key Metrics

```promql
# Success rate
sum(rate(aep_task_completion_time_ms_count{status="success"}[5m])) / sum(rate(aep_task_completion_time_ms_count[5m]))

# Task rate
sum(rate(aep_task_completion_time_ms_count[5m]))

# Average iterations
sum(rate(aep_task_iterations_total_sum[5m])) / sum(rate(aep_task_iterations_total_count[5m]))

# Average duration
sum(rate(aep_task_completion_time_ms_sum[5m])) / sum(rate(aep_task_completion_time_ms_count[5m]))
```

---

### 3. Error Tracking Dashboard

**File:** `dashboards/navi-errors.json`
**Data Source:** PostgreSQL
**Refresh:** 10 seconds
**Time Range:** Last 24 hours

#### Panels

| Panel | Type | Description | Alert Threshold |
|-------|------|-------------|-----------------|
| **Errors Last Hour** | Stat | Total errors in past hour | > 50 (warning) |
| **Resolution Rate (24h)** | Stat | % of errors resolved | < 80% (warning) |
| **Unresolved Errors (24h)** | Stat | Count of unresolved errors | > 20 (warning) |
| **Critical Unresolved** | Stat | Critical errors needing attention | > 0 (critical) |
| **Error Count by Type** | Timeseries (Stacked) | Error trends by type | - |
| **Error Count by Severity** | Timeseries (Stacked) | Errors by severity (info/warning/error/critical) | - |
| **Top 10 Error Types** | Pie Chart | Most frequent error types | - |
| **Resolution Status Distribution** | Donut Chart | Resolved/unresolved/investigating split | - |
| **Recent Errors** | Table | Last 100 errors with details | - |
| **Errors by Component** | Bar Chart | Error distribution across components | - |

#### SQL Queries

```sql
-- Errors last hour
SELECT COUNT(*) FROM error_events
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Resolution rate
SELECT
  (COUNT(*) FILTER (WHERE resolved = 1)::float / NULLIF(COUNT(*), 0)) * 100
FROM error_events
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Top error types
SELECT error_type, COUNT(*) as count
FROM error_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY error_type
ORDER BY count DESC
LIMIT 10;
```

---

### 4. Learning System Dashboard

**File:** `dashboards/navi-learning.json`
**Data Source:** PostgreSQL
**Refresh:** 10 seconds
**Time Range:** Last 7 days

#### Panels

| Panel | Type | Description | Target |
|-------|------|-------------|--------|
| **Feedback Received (24h)** | Stat | Total feedback submissions | - |
| **Avg Rating (24h)** | Stat | Average user rating (1-5 stars) | ≥ 4.0 |
| **Active Learning Patterns** | Stat | Number of detected patterns | - |
| **Generated Insights (7d)** | Stat | New insights in past week | - |
| **Feedback by Type** | Timeseries (Stacked) | Feedback over time (like/dislike/neutral) | - |
| **Rating Trend (30 days)** | Timeseries | Average rating trend | ≥ 4.0 |
| **Feedback Type Distribution** | Pie Chart | Breakdown of feedback types | - |
| **Rating Distribution** | Donut Chart | Positive/neutral/negative split | - |
| **Active Learning Patterns** | Table | Top 50 patterns with confidence scores | - |
| **Recent Learning Insights** | Table | Top 50 insights with confidence scores | - |
| **Rating Histogram** | Bar Chart | Rating distribution (1-5 stars) | - |

#### SQL Queries

```sql
-- Feedback received (24h)
SELECT COUNT(*) FROM learning_suggestions
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Average rating (24h)
SELECT AVG(rating) FROM learning_suggestions
WHERE rating IS NOT NULL AND created_at > NOW() - INTERVAL '24 hours';

-- Rating trend (30 days)
SELECT
  DATE_TRUNC('day', created_at) as time,
  AVG(rating) as avg_rating
FROM learning_suggestions
WHERE rating IS NOT NULL AND created_at > NOW() - INTERVAL '30 days'
GROUP BY time
ORDER BY time;

-- Learning patterns
SELECT
  pattern_type,
  description,
  confidence,
  occurrences
FROM learning_patterns
WHERE first_seen > NOW() - INTERVAL '7 days'
ORDER BY confidence DESC
LIMIT 50;
```

---

## Setup Instructions

### Prerequisites

1. **Grafana** installed and running
   ```bash
   # Docker
   docker run -d -p 3000:3000 --name=grafana grafana/grafana

   # macOS
   brew install grafana
   brew services start grafana

   # Ubuntu
   sudo apt-get install -y grafana
   sudo systemctl start grafana-server
   ```

2. **Prometheus** running and scraping `/metrics`
   ```bash
   # Add to prometheus.yml
   scrape_configs:
     - job_name: 'navi-backend'
       static_configs:
         - targets: ['localhost:8787']
       metrics_path: '/metrics'
       scrape_interval: 5s
   ```

### Grafana Provisioning (Auto-load Dashboards)

This repo includes provisioning so dashboards and data sources auto-load on startup.

```bash
# From repo root
docker run -d -p 3000:3000 \
  -v $(pwd)/grafana/provisioning:/etc/grafana/provisioning \
  -v $(pwd)/grafana/dashboards:/var/lib/grafana/dashboards \
  --name grafana \
  grafana/grafana
```

If your Postgres credentials differ, update `grafana/provisioning/datasources/datasources.yaml`.

3. **PostgreSQL** data source configured in Grafana
   - Host: `localhost:5432`
   - Database: `mentor` (or your database name)
   - User: Your database user
   - SSL Mode: `disable` (or `require` for production)

### Step 1: Configure Data Sources

#### Add Prometheus Data Source

1. Open Grafana: `http://localhost:3000`
2. Go to **Configuration** → **Data Sources**
3. Click **Add data source**
4. Select **Prometheus**
5. Configure:
   - **Name:** `Prometheus`
   - **URL:** `http://localhost:9090`
   - **Scrape interval:** `5s`
6. Click **Save & Test**

#### Add PostgreSQL Data Source

1. Go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **PostgreSQL**
4. Configure:
   - **Name:** `PostgreSQL`
   - **Host:** `localhost:5432`
   - **Database:** `aep`
   - **User:** `your_db_user`
   - **Password:** `your_db_password`
   - **SSL Mode:** `disable` (or `require` for production)
   - **Version:** `15+`
   - **TimescaleDB:** Disabled (unless using TimescaleDB)
6. Click **Save & Test**

### Step 2: Import Dashboards

#### Import via UI

1. Go to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select one of the dashboard files:
   - `grafana/dashboards/navi-llm-metrics.json`
   - `grafana/dashboards/navi-task-metrics.json`
   - `grafana/dashboards/navi-errors.json`
   - `grafana/dashboards/navi-learning.json`
4. Select data source:
   - For LLM/Task dashboards: Select **Prometheus**
   - For Error/Learning dashboards: Select **PostgreSQL**
5. Click **Import**
6. Repeat for all 4 dashboards

#### Import via API

```bash
# Set Grafana credentials
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"

# Import all dashboards
for dashboard in grafana/dashboards/*.json; do
  curl -X POST \
    -H "Content-Type: application/json" \
    -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
    -d @"$dashboard" \
    "$GRAFANA_URL/api/dashboards/db"
done
```

#### Import via Provisioning

For automated deployment, use Grafana provisioning:

1. Create provisioning config:
   ```yaml
   # /etc/grafana/provisioning/dashboards/navi.yaml
   apiVersion: 1
   providers:
     - name: 'NAVI Dashboards'
       orgId: 1
       folder: 'NAVI'
       type: file
       disableDeletion: false
       updateIntervalSeconds: 10
       allowUiUpdates: true
       options:
         path: /path/to/autonomous-engineering-platform/grafana/dashboards
   ```

2. Restart Grafana:
   ```bash
   sudo systemctl restart grafana-server
   ```

### Step 3: Verify Metrics

1. **Check Prometheus metrics endpoint:**
   ```bash
   curl http://localhost:8787/metrics | grep aep_llm
   ```

   Expected output:
   ```
   # HELP aep_llm_calls_total Total number of LLM API calls
   # TYPE aep_llm_calls_total counter
   aep_llm_calls_total{model="claude-sonnet-4",phase="autonomous",status="success"} 42.0

   # HELP aep_llm_latency_ms LLM API call latency in milliseconds
   # TYPE aep_llm_latency_ms histogram
   aep_llm_latency_ms_bucket{le="100.0",model="claude-sonnet-4",phase="autonomous"} 5.0
   ...
   ```

2. **Check PostgreSQL tables:**
   ```sql
   -- Verify error tracking table
   SELECT COUNT(*) FROM error_events;

   -- Verify learning data table
   SELECT COUNT(*) FROM learning_suggestions;

   -- Verify learning patterns table
   SELECT COUNT(*) FROM learning_patterns;

   -- Verify learning insights table
   SELECT COUNT(*) FROM learning_insights;
   ```

---

## Dashboard Usage

### Creating a Monitoring Workspace

1. **Create a folder:**
   - Go to **Dashboards** → **Browse**
   - Click **New folder**
   - Name: `NAVI Production`

2. **Move dashboards:**
   - Select each dashboard
   - Click **Dashboard settings** (gear icon)
   - **General** → **Folder:** `NAVI Production`
   - **Save**

3. **Create a playlist:**
   - Go to **Dashboards** → **Playlists**
   - Click **New playlist**
   - Add all 4 dashboards
   - Set interval: `30 seconds`
   - **Save** and **Start playlist**

### Setting Up Alerts

#### Prometheus Alerts (LLM & Task Metrics)

Create alert rules in `prometheus/alerts/navi-slos.yaml`:

```yaml
groups:
  - name: navi_llm_alerts
    interval: 30s
    rules:
      # P95 Latency SLO
      - alert: HighLLMLatency
        expr: histogram_quantile(0.95, rate(aep_llm_latency_ms_bucket[5m])) > 5000
        for: 2m
        labels:
          severity: warning
          component: llm
        annotations:
          summary: "LLM P95 latency exceeds SLO (> 5000ms)"
          description: "P95 latency is {{ $value }}ms (target: < 5000ms)"

      # High Error Rate
      - alert: HighLLMErrorRate
        expr: sum(rate(aep_llm_calls_total{status="error"}[5m])) / sum(rate(aep_llm_calls_total[5m])) > 0.01
        for: 5m
        labels:
          severity: critical
          component: llm
        annotations:
          summary: "LLM error rate exceeds threshold (> 1%)"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # High LLM Cost
      - alert: HighLLMCost
        expr: sum(rate(aep_llm_cost_usd_total[1h])) * 3600 > 50
        for: 10m
        labels:
          severity: warning
          component: cost
        annotations:
          summary: "LLM cost exceeds budget (> $50/hour)"
          description: "Current hourly cost: ${{ $value }}"

  - name: navi_task_alerts
    interval: 30s
    rules:
      # Low Task Success Rate
      - alert: LowTaskSuccessRate
        expr: sum(rate(aep_task_completion_time_ms_count{status="success"}[5m])) / sum(rate(aep_task_completion_time_ms_count[5m])) < 0.95
        for: 10m
        labels:
          severity: critical
          component: tasks
        annotations:
          summary: "Task success rate below SLO (< 95%)"
          description: "Success rate: {{ $value | humanizePercentage }}"
```

#### Grafana Alerts (Error & Learning Metrics)

Configure alerts directly in Grafana dashboards:

1. Open dashboard panel
2. Click **Alert** tab
3. Click **Create alert**
4. Configure:
   - **Name:** `High Error Rate`
   - **Evaluate every:** `1m`
   - **For:** `5m`
   - **Conditions:** `WHEN avg() OF query(A, 5m, now) IS ABOVE 50`
5. **Save**

### Best Practices

1. **Regular Review:**
   - Review dashboards daily during initial deployment
   - Weekly review after stabilization
   - Monthly trend analysis

2. **SLO Monitoring:**
   - Set alerts for SLO violations
   - Track SLO compliance weekly
   - Document SLO incidents

3. **Cost Optimization:**
   - Monitor LLM cost trends
   - Set budget alerts
   - Review expensive queries monthly

4. **Performance Tuning:**
   - Identify slow tasks from task metrics
   - Optimize prompts causing high latency
   - Monitor iteration counts

5. **Error Response:**
   - Triage critical errors immediately
   - Review unresolved errors daily
   - Analyze error patterns weekly

---

## Troubleshooting

### Dashboard shows "No data"

**Problem:** Panels show "No data" or "N/A"

**Causes & Fixes:**

1. **Prometheus not scraping:**
   ```bash
   # Check Prometheus targets
   curl http://localhost:9090/api/v1/targets

   # Verify NAVI /metrics endpoint
   curl http://localhost:8787/metrics
   ```

2. **PostgreSQL connection failed:**
   - Test data source in Grafana
   - Verify database credentials
   - Check database is running: `psql -h localhost -U your_user -d aep`

3. **No data in database:**
   ```sql
   -- Check if tables exist and have data
   SELECT COUNT(*) FROM error_events;
   SELECT COUNT(*) FROM learning_suggestions;
   ```

### Queries timing out

**Problem:** Dashboard queries take too long or timeout

**Fix:**

1. **Add database indexes:**
   ```sql
   -- Error events
   CREATE INDEX IF NOT EXISTS idx_error_events_created_at ON error_events(created_at);
   CREATE INDEX IF NOT EXISTS idx_error_events_type ON error_events(error_type);
   CREATE INDEX IF NOT EXISTS idx_error_events_severity ON error_events(severity);

   -- Learning suggestions
   CREATE INDEX IF NOT EXISTS idx_learning_suggestions_created_at ON learning_suggestions(created_at);
   CREATE INDEX IF NOT EXISTS idx_learning_suggestions_rating ON learning_suggestions(rating);
   ```

2. **Reduce time range:**
   - Change dashboard time range from 7d to 24h
   - Use 1h for real-time monitoring

3. **Optimize queries:**
   - Add WHERE clause with time filter
   - Use aggregations instead of raw data

### Permissions errors

**Problem:** "Permission denied" errors in Grafana

**Fix:**

1. **Grant database permissions:**
   ```sql
   GRANT SELECT ON error_events TO grafana_user;
   GRANT SELECT ON learning_suggestions TO grafana_user;
   GRANT SELECT ON learning_patterns TO grafana_user;
   GRANT SELECT ON learning_insights TO grafana_user;
   ```

2. **Verify Grafana user role:**
   - Ensure user has Viewer or Editor role
   - Admin required for data source configuration

---

## Maintenance

### Dashboard Updates

1. **Export modified dashboard:**
   - Dashboard settings → **JSON Model**
   - Copy JSON
   - Save to `grafana/dashboards/*.json`

2. **Version control:**
   ```bash
   git add grafana/dashboards/
   git commit -m "Update Grafana dashboards"
   ```

3. **Deploy to production:**
   - Re-import dashboard via UI or API
   - Or use provisioning (automatic reload)

### Data Retention

**Prometheus:**
```yaml
# prometheus.yml
storage:
  tsdb:
    retention.time: 30d  # Keep metrics for 30 days
    retention.size: 50GB  # Max storage size
```

**PostgreSQL:**
```sql
-- Delete old error events (> 90 days)
DELETE FROM error_events
WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete old learning data (> 180 days)
DELETE FROM learning_suggestions
WHERE created_at < NOW() - INTERVAL '180 days';
```

### Backup & Restore

**Export all dashboards:**
```bash
./scripts/export_grafana_dashboards.sh
```

**Restore from backup:**
```bash
./scripts/import_grafana_dashboards.sh grafana/dashboards/
```

---

## References

- **Grafana Documentation:** https://grafana.com/docs/
- **Prometheus Documentation:** https://prometheus.io/docs/
- **PostgreSQL Grafana Plugin:** https://grafana.com/docs/grafana/latest/datasources/postgres/
- **NAVI Production Readiness:** [docs/NAVI_PROD_READINESS.md](../docs/NAVI_PROD_READINESS.md)

---

**Last Updated:** February 7, 2026
**Dashboard Version:** 1.0
**Grafana Version:** 9.5.2+
