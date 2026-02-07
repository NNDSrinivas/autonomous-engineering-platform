# Week 1 Action Plan: NAVI Production Launch

**Week:** February 6-13, 2026
**Goal:** Validate real-world performance and deploy to staging
**Team:** All hands on deck

---

## 🎯 Week 1 Objectives

By end of Week 1, we will have:
1. ✅ Real LLM performance benchmarks (p50/p95/p99 latency)
2. ✅ Staging environment deployed and validated
3. ✅ Audit encryption mandatory in production mode
4. ✅ Performance baseline established

---

## 📅 Daily Schedule

### **Monday, Feb 6** - Real LLM Testing Setup

#### Backend Team
**Task:** Set up real LLM E2E testing infrastructure
**Owner:** Backend Lead
**Deliverable:** Test suite ready to run with real models

**Actions:**
```bash
# 1. Create real LLM test configuration
cat > tests/e2e/real_llm_config.yaml <<EOF
llm_provider: anthropic
model: claude-sonnet-4
api_key_env: ANTHROPIC_API_KEY
test_runs: 100
timeout_seconds: 30
track_metrics:
  - latency
  - tokens
  - cost
  - error_rate
EOF

# 2. Create test runner script
cat > scripts/run_real_llm_tests.sh <<'EOF'
#!/bin/bash
set -e

export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"
export USE_REAL_LLM=true
export TRACK_PERFORMANCE_METRICS=true

echo "🚀 Running 100 E2E tests with real LLM..."
pytest tests/e2e/ \
  --real-llm \
  --runs=100 \
  --output=docs/performance_results.json \
  --verbose

echo "📊 Analyzing results..."
python scripts/analyze_performance.py docs/performance_results.json

echo "✅ Tests complete. Check docs/PERFORMANCE_BENCHMARKS.md"
EOF

chmod +x scripts/run_real_llm_tests.sh
```

**Checklist:**
- [ ] API keys configured (ANTHROPIC_API_KEY, OPENAI_API_KEY)
- [ ] Test scenarios defined (10 representative tasks)
- [ ] Metrics collection code added to test runner
- [ ] Results analysis script created

---

#### DevOps Team
**Task:** Provision AWS/GCP staging environment
**Owner:** DevOps Lead
**Deliverable:** Staging infrastructure ready

**Actions:**

**Option A: AWS**
```bash
# 1. Provision RDS PostgreSQL (staging)
aws rds create-db-instance \
  --db-instance-identifier navi-staging \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username navi_staging \
  --master-user-password "${STAGING_DB_PASSWORD}" \
  --allocated-storage 50 \
  --storage-type gp3 \
  --backup-retention-period 7 \
  --vpc-security-group-ids sg-staging \
  --db-subnet-group-name navi-staging-subnet \
  --storage-encrypted \
  --publicly-accessible false

# 2. Wait for RDS to be available (5-10 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier navi-staging

# 3. Get RDS endpoint
export STAGING_DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier navi-staging \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo "✅ RDS Endpoint: $STAGING_DB_HOST"
```

**Option B: GCP**
```bash
# 1. Provision Cloud SQL PostgreSQL (staging)
gcloud sql instances create navi-staging \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=us-central1 \
  --backup \
  --backup-start-time=02:00 \
  --storage-auto-increase \
  --network=projects/PROJECT_ID/global/networks/default

# 2. Create database
gcloud sql databases create navi_staging \
  --instance=navi-staging

# 3. Set password
gcloud sql users set-password navi_staging \
  --instance=navi-staging \
  --password="${STAGING_DB_PASSWORD}"

# 4. Get connection name
export STAGING_DB_CONN=$(gcloud sql instances describe navi-staging \
  --format='value(connectionName)')

echo "✅ Cloud SQL Connection: $STAGING_DB_CONN"
```

**Checklist:**
- [ ] Cloud provider account configured
- [ ] VPC/Network security groups configured
- [ ] Database instance provisioned
- [ ] Database credentials stored in secrets manager
- [ ] Network connectivity tested

---

### **Tuesday, Feb 7** - Real LLM Testing Execution

#### Backend Team
**Task:** Run 100+ E2E tests with real LLMs
**Owner:** Backend Lead + QA
**Deliverable:** Performance benchmarks documented

**Actions:**
```bash
# 1. Run test suite (expect 2-3 hours)
./scripts/run_real_llm_tests.sh 2>&1 | tee logs/real_llm_tests_$(date +%Y%m%d).log

# 2. Monitor progress
watch -n 10 'tail -20 logs/real_llm_tests_*.log'

# 3. Check for failures
grep -i "FAILED\|ERROR" logs/real_llm_tests_*.log

# 4. Generate performance report
python scripts/generate_performance_report.py \
  --input docs/performance_results.json \
  --output docs/PERFORMANCE_BENCHMARKS.md

# 5. Review results
cat docs/PERFORMANCE_BENCHMARKS.md
```

**Expected Metrics:**
```
Target Metrics:
- p50 latency: < 2s
- p95 latency: < 5s ✅ TARGET
- p99 latency: < 10s
- Success rate: > 99%
- Average cost per request: < $0.XX

If p95 > 5s, investigate and optimize before proceeding.
```

**Checklist:**
- [ ] All 100 tests completed
- [ ] Results analyzed and documented
- [ ] Performance meets targets (p95 < 5s)
- [ ] Cost per request acceptable
- [ ] Error patterns identified

---

#### DevOps Team
**Task:** Set up K8s cluster for staging
**Owner:** DevOps Lead
**Deliverable:** Kubernetes cluster ready

**Actions:**

**AWS EKS:**
```bash
# 1. Create EKS cluster
eksctl create cluster \
  --name navi-staging \
  --region us-west-2 \
  --node-type t3.large \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# 2. Configure kubectl
aws eks update-kubeconfig \
  --region us-west-2 \
  --name navi-staging

# 3. Create namespace
kubectl create namespace navi-staging

# 4. Install metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

**GCP GKE:**
```bash
# 1. Create GKE cluster
gcloud container clusters create navi-staging \
  --region us-central1 \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 5

# 2. Configure kubectl
gcloud container clusters get-credentials navi-staging \
  --region us-central1

# 3. Create namespace
kubectl create namespace navi-staging
```

**Checklist:**
- [ ] Kubernetes cluster created
- [ ] kubectl configured
- [ ] Namespace created (navi-staging)
- [ ] Metrics server installed
- [ ] Node autoscaling configured

---

### **Wednesday, Feb 8** - Audit Encryption + Staging Secrets

#### Backend Team
**Task:** Make audit encryption mandatory in production
**Owner:** Backend Lead
**Deliverable:** Audit encryption enforced

**Actions:**
```python
# File: backend/api/main.py
# Add startup validation

@app.on_event("startup")
async def validate_production_config():
    """Validate required production configuration."""
    import os
    from backend.core.config import settings

    # In production mode, audit encryption MUST be configured
    if settings.app_env == "production":
        if not os.getenv("AUDIT_ENCRYPTION_KEY"):
            raise RuntimeError(
                "AUDIT_ENCRYPTION_KEY is required in production mode. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        logger.info("✅ Production config validated: audit encryption enabled")
```

**Test:**
```bash
# 1. Test production startup without encryption key (should fail)
APP_ENV=production python -m uvicorn backend.api.main:app
# Expected: RuntimeError about missing AUDIT_ENCRYPTION_KEY

# 2. Test with encryption key (should succeed)
export AUDIT_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
APP_ENV=production python -m uvicorn backend.api.main:app
# Expected: Startup successful with log "audit encryption enabled"
```

**Checklist:**
- [ ] Startup validation added to main.py
- [ ] Error message clear and actionable
- [ ] Tested failure case (no key)
- [ ] Tested success case (with key)
- [ ] Documentation updated

---

#### DevOps Team
**Task:** Create staging database secret and deploy
**Owner:** DevOps Lead
**Deliverable:** Database secret configured

**Actions:**
```bash
# 1. Create database secret
kubectl create secret generic navi-database-staging \
  --from-literal=DATABASE_URL="postgresql+psycopg2://navi_staging:${STAGING_DB_PASSWORD}@${STAGING_DB_HOST}:5432/navi_staging" \
  --from-literal=DB_HOST="${STAGING_DB_HOST}" \
  --from-literal=DB_PORT="5432" \
  --from-literal=DB_NAME="navi_staging" \
  --from-literal=DB_USER="navi_staging" \
  --from-literal=DB_PASSWORD="${STAGING_DB_PASSWORD}" \
  --from-literal=DB_SSLMODE="require" \
  --namespace navi-staging

# 2. Create ConfigMap for DB settings
kubectl create configmap navi-database-config-staging \
  --from-literal=DB_POOL_SIZE="20" \
  --from-literal=DB_MAX_OVERFLOW="40" \
  --from-literal=DB_POOL_TIMEOUT="30" \
  --from-literal=DB_POOL_RECYCLE="3600" \
  --from-literal=ALEMBIC_AUTO_UPGRADE="true" \
  --from-literal=DB_ECHO="false" \
  --namespace navi-staging

# 3. Verify secrets
kubectl get secrets -n navi-staging
kubectl describe secret navi-database-staging -n navi-staging
```

**Checklist:**
- [ ] Database secret created
- [ ] ConfigMap created
- [ ] Connection string format validated
- [ ] SSL mode set to "require"
- [ ] Secrets verified in cluster

---

### **Thursday, Feb 9** - Deploy to Staging

#### DevOps Team
**Task:** Deploy NAVI backend to staging
**Owner:** DevOps Lead
**Deliverable:** Application running in staging

**Actions:**
```bash
# 1. Build and push Docker image
docker build -t gcr.io/PROJECT_ID/navi-backend:staging .
docker push gcr.io/PROJECT_ID/navi-backend:staging

# Or for AWS ECR:
docker build -t ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/navi-backend:staging .
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-west-2.amazonaws.com
docker push ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/navi-backend:staging

# 2. Update deployment manifest with correct image
sed -i 's|your-registry/navi-backend:staging|gcr.io/PROJECT_ID/navi-backend:staging|g' \
  kubernetes/deployments/backend-staging.yaml

# 3. Deploy to staging
kubectl apply -f kubernetes/deployments/backend-staging.yaml

# 4. Watch deployment progress
kubectl rollout status deployment/navi-backend -n navi-staging --timeout=5m

# 5. Check pods
kubectl get pods -n navi-staging
kubectl logs -n navi-staging deployment/navi-backend -c db-migrate
kubectl logs -n navi-staging deployment/navi-backend -c backend --tail=50
```

**Verify Deployment:**
```bash
# 1. Check health endpoint
kubectl port-forward -n navi-staging service/navi-backend 8787:8787 &
curl http://localhost:8787/health
# Expected: {"status":"ok"}

# 2. Check database migration
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  alembic current
# Expected: 0031_metrics_learning (head)

# 3. Check database tables
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "\dt" | grep -E "(llm_metrics|telemetry_events)"
# Expected: 9 new tables visible
```

**Checklist:**
- [ ] Docker image built and pushed
- [ ] Deployment manifest applied
- [ ] Pods running (2 replicas)
- [ ] Init container completed successfully (migrations)
- [ ] Health check passing
- [ ] Database tables verified
- [ ] Logs showing no errors

---

### **Friday, Feb 10** - Staging Validation

#### QA Team
**Task:** Run validation tests in staging
**Owner:** QA Lead
**Deliverable:** Staging environment validated

**Validation Checklist:**

**1. Smoke Tests**
```bash
# Get staging URL
export STAGING_URL="http://$(kubectl get service navi-backend -n navi-staging -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"

# Run smoke tests
pytest tests/smoke/ --base-url=$STAGING_URL --real-llm

# Check logs for any errors
kubectl logs -n navi-staging deployment/navi-backend --tail=100 | grep -i error
```

**2. Database Connectivity**
```bash
# Test database connections
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'navi_staging';"

# Should show 2-5 active connections
```

**3. Real Workload Test**
```bash
# Send real NAVI request through staging
curl -X POST $STAGING_URL/api/navi/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a simple hello world Python script",
    "workspace_path": "/tmp/test"
  }'

# Check that:
# - Response received (< 10s)
# - LLM metrics recorded in database
# - Telemetry events captured
```

**4. Metrics Verification**
```bash
# Check Prometheus metrics
curl $STAGING_URL/metrics | grep aep_llm_calls_total

# Check database metrics
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM llm_metrics;"
# Should show > 0 rows after workload test
```

**Validation Criteria:**
- [ ] Health endpoint responding
- [ ] Database migrations applied
- [ ] Real NAVI requests succeeding
- [ ] Metrics being recorded (Prometheus + database)
- [ ] No error logs in past hour
- [ ] Pod autoscaling configured
- [ ] Resource usage reasonable (< 50% CPU/memory)

---

### **Weekend, Feb 11-12** - Monitor Staging

#### On-Call Team
**Task:** Monitor staging environment for 48 hours
**Owner:** Rotating on-call
**Deliverable:** Stability report

**Monitoring Checklist:**
```bash
# Every 4 hours, check:

# 1. Pod health
kubectl get pods -n navi-staging
# All pods should be Running

# 2. Resource usage
kubectl top pods -n navi-staging
# CPU < 1 core, Memory < 2Gi per pod

# 3. Logs for errors
kubectl logs -n navi-staging deployment/navi-backend --since=4h | grep -i -E "error|exception|failed"
# Should be minimal/none

# 4. Database connections
kubectl exec -n navi-staging deployment/navi-backend -c backend -- \
  psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
# Should be < 10

# 5. Metrics endpoint
curl http://staging-url/metrics | grep -E "aep_llm_calls|http_requests_total"
# Should show increasing counters
```

**Log Issues:**
Document any issues in `docs/staging_validation_log.md`:
```markdown
# Staging Validation Log

## Saturday, Feb 11
- 10:00 - Deployment healthy, 2 pods running
- 14:00 - Spike in CPU (pod restarted) - investigating
- 18:00 - CPU spike resolved (GC tuning needed)

## Sunday, Feb 12
- 10:00 - No issues, system stable
- 14:00 - Database connections growing (connection leak?) - monitoring
- 18:00 - Connection leak confirmed in streaming endpoint - fix needed Week 2
```

---

## 📊 Week 1 Success Criteria

By end of Friday (or Saturday), we should have:

### ✅ Real LLM Performance
- [x] 100+ tests completed with real models
- [x] p50/p95/p99 latency documented
- [x] Performance meets targets (p95 < 5s)
- [x] Cost per request acceptable
- [x] Error patterns identified and documented

### ✅ Staging Environment
- [x] Cloud infrastructure provisioned (RDS/Cloud SQL + K8s)
- [x] Database migrations applied
- [x] Application deployed (2 replicas)
- [x] Health checks passing
- [x] Metrics collection working
- [x] Validated with real workloads

### ✅ Security Hardening
- [x] Audit encryption mandatory in production
- [x] Startup validation implemented
- [x] Tested and documented

### ✅ Documentation
- [x] Performance benchmarks documented
- [x] Staging deployment runbook created
- [x] Known issues logged
- [x] Week 2 priorities identified

---

## 🚨 Escalation Paths

**If something blocks progress:**

1. **Real LLM tests failing** (< 95% success rate)
   - **Owner:** Backend Lead investigates
   - **Escalate to:** CTO if > 4 hours blocked
   - **Mitigation:** Focus on fixing top 3 failure patterns

2. **Staging deployment fails**
   - **Owner:** DevOps Lead investigates
   - **Escalate to:** Infrastructure team if > 2 hours blocked
   - **Mitigation:** Deploy to local K8s (kind/minikube) as fallback

3. **Performance doesn't meet targets** (p95 > 8s)
   - **Owner:** Backend + Platform teams collaborate
   - **Escalate to:** CTO if optimization > 1 day
   - **Mitigation:** Identify top 3 bottlenecks, create optimization plan

4. **Database issues**
   - **Owner:** Infrastructure team investigates
   - **Escalate to:** Database specialist if > 2 hours
   - **Mitigation:** Use snapshot of working local database

---

## 📞 Daily Standup (10:00 AM)

**Format:** 15 minutes max, all teams

**Questions:**
1. What did you complete yesterday?
2. What are you working on today?
3. Any blockers?

**Action Items:**
- Document blockers in shared doc
- Assign owners for blockers
- Set deadline for resolution (4 hours max)

---

## 🎯 Week 1 Deliverables (Final Checklist)

**Documentation:**
- [ ] `docs/PERFORMANCE_BENCHMARKS.md` - Real LLM performance data
- [ ] `docs/staging_deployment_log.md` - Staging deployment steps
- [ ] `docs/staging_validation_log.md` - 48-hour monitoring results
- [ ] `docs/week1_lessons_learned.md` - Issues and resolutions

**Infrastructure:**
- [ ] Staging database provisioned and backed up
- [ ] Kubernetes cluster configured
- [ ] Staging deployment running (2+ replicas)
- [ ] Metrics collection verified

**Code:**
- [ ] Audit encryption mandatory (PR merged)
- [ ] Real LLM test suite (PR merged)
- [ ] Performance analysis script (committed)

**Metrics:**
- [ ] Baseline performance established (p50/p95/p99)
- [ ] Cost per request documented
- [ ] Error rate documented
- [ ] Resource usage profiled

---

## 🚀 Week 2 Preview

Based on Week 1 results, Week 2 will focus on:

1. **Monitoring Dashboards** (Monday-Tuesday)
   - Create 4 Grafana dashboards
   - Import to staging

2. **SLO Definitions** (Wednesday-Thursday)
   - Define reliability targets
   - Configure Prometheus alerts

3. **Incident Runbooks** (Thursday-Friday)
   - Document common issues from Week 1
   - Create resolution procedures

---

## 📝 Daily Checklist Template

**Copy this for each team member:**

```markdown
## [Your Name] - [Date]

### Morning (9:00 - 12:00)
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

### Afternoon (13:00 - 17:00)
- [ ] Task 4
- [ ] Task 5

### Blockers
- None / [Describe blocker + who can help]

### Notes
- [Any observations, issues, or suggestions]
```

---

## 💪 Let's Ship It!

**Week 1 is the foundation for production launch.**

Stay focused, communicate blockers early, and let's validate that NAVI is ready for the world! 🚀

**Questions? Check #navi-launch Slack channel**
