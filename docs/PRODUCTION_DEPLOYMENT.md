# NAVI Production Deployment Guide

**Status:** 📋 Planning Document
**Last Updated:** February 7, 2026
**Current Environment:** Local Development Only

---

## 🚨 Important Notice

**The current setup is for LOCAL DEVELOPMENT only.**

This document outlines what you'll need to deploy NAVI to production. The monitoring infrastructure (Grafana, Prometheus, alerts) is production-ready but currently configured for local testing.

---

## Current Status: Local Development

### ✅ What's Ready (Dev Environment)

1. **Code & Infrastructure**
   - ✅ Production-quality code (98.7% production-ready per review)
   - ✅ No hardcoded credentials
   - ✅ No dev-only code in production paths
   - ✅ Proper error handling and security

2. **Monitoring Stack (Local)**
   - ✅ Grafana running on `localhost:3001` (Docker)
   - ✅ 4 dashboards created (40+ panels)
   - ✅ 25+ Prometheus alert rules defined
   - ✅ 8 SLOs with error budgets

3. **Testing & Validation**
   - ✅ E2E test suite (100+ tests with real LLMs)
   - ✅ SLO compliance checking
   - ✅ P50/P95/P99 latency measurement

4. **Documentation**
   - ✅ 30+ documentation files
   - ✅ On-call playbook with 6 runbooks
   - ✅ Incident response procedures

### ⚠️ What's NOT Production-Ready

1. **Infrastructure**
   - ❌ Grafana on `localhost` (not accessible externally)
   - ❌ Single Docker container (no high availability)
   - ❌ No load balancing or auto-scaling
   - ❌ Ephemeral Docker volumes (data loss on restart)

2. **Security**
   - ❌ Default credentials (admin/admin)
   - ❌ No SSO/SAML integration
   - ❌ No RBAC (role-based access control)
   - ❌ No network security policies

3. **Alerting**
   - ❌ Alerts defined but not routed
   - ❌ No PagerDuty integration
   - ❌ No Slack notifications
   - ❌ No on-call rotation configured

4. **Data & Backups**
   - ❌ No database backups configured
   - ❌ No metrics retention policy
   - ❌ No disaster recovery plan

---

## Production Deployment Options

### Option 1: AWS Deployment (Recommended)

**Best for:** Scalability, managed services, enterprise features

**Infrastructure:**
```
┌─────────────────────────────────────────────┐
│ AWS Cloud                                   │
│                                             │
│  ┌──────────────┐      ┌─────────────────┐│
│  │   Route 53   │─────▶│  Application    ││
│  │   (DNS)      │      │  Load Balancer  ││
│  └──────────────┘      └────────┬────────┘│
│                                  │         │
│         ┌────────────────────────┼─────┐   │
│         ▼                        ▼     │   │
│  ┌─────────────┐         ┌─────────────┐  │
│  │   ECS/EKS   │         │   ECS/EKS   │  │
│  │  (Backend)  │         │ (Prometheus)│  │
│  └──────┬──────┘         └──────┬──────┘  │
│         │                       │         │
│         └───────────┬───────────┘         │
│                     ▼                     │
│         ┌────────────────────┐            │
│         │   Amazon RDS       │            │
│         │   (PostgreSQL)     │            │
│         └────────────────────┘            │
│                                           │
│  ┌──────────────────────────────────┐    │
│  │ Amazon Managed Grafana           │    │
│  │ https://g-xxx.grafana-...com     │    │
│  └──────────────────────────────────┘    │
│                                           │
│  ┌──────────────────────────────────┐    │
│  │ Amazon Managed Prometheus        │    │
│  │ (AMP)                            │    │
│  └──────────────────────────────────┘    │
└───────────────────────────────────────────┘
```

**Services Needed:**
- **Compute:** ECS/EKS for NAVI backend
- **Database:** Amazon RDS for PostgreSQL (with Multi-AZ)
- **Monitoring:** Amazon Managed Grafana + Amazon Managed Prometheus
- **Alerts:** SNS → PagerDuty/Slack
- **Storage:** S3 for logs and backups
- **CDN:** CloudFront for frontend
- **Security:** IAM roles, VPC, Security Groups

**Estimated Monthly Cost:** $500-2000 (depending on scale)

---

### Option 2: Self-Hosted (On-Premises)

**Best for:** Full control, compliance requirements, existing infrastructure

**Infrastructure:**
```
┌─────────────────────────────────────────────┐
│ On-Premises Data Center                     │
│                                             │
│  ┌──────────────────────────────────┐      │
│  │ Kubernetes Cluster               │      │
│  │                                  │      │
│  │  ┌──────────┐  ┌──────────┐     │      │
│  │  │  NAVI    │  │Prometheus│     │      │
│  │  │ Backend  │  │          │     │      │
│  │  └────┬─────┘  └────┬─────┘     │      │
│  │       │             │            │      │
│  └───────┼─────────────┼────────────┘      │
│          │             │                   │
│          ▼             ▼                   │
│  ┌──────────────┐  ┌──────────────┐       │
│  │ PostgreSQL   │  │  Grafana     │       │
│  │ (HA Cluster) │  │  (HA Setup)  │       │
│  └──────────────┘  └──────────────┘       │
│                                            │
│  ┌──────────────────────────────────┐     │
│  │ Load Balancer (HAProxy/NGINX)    │     │
│  └──────────────────────────────────┘     │
└────────────────────────────────────────────┘
```

**Requirements:**
- Kubernetes cluster (3+ nodes)
- PostgreSQL HA cluster
- Prometheus HA setup (Thanos for long-term storage)
- Grafana HA setup
- Load balancers
- Storage (SAN/NAS for persistent volumes)

---

### Option 3: Hybrid (Grafana Cloud + Self-Hosted Backend)

**Best for:** Quick start, managed observability, flexibility

**Infrastructure:**
```
┌──────────────────────┐       ┌──────────────────┐
│ Your Infrastructure  │       │  Grafana Cloud   │
│                      │       │                  │
│  ┌────────────┐      │       │  ┌────────────┐ │
│  │   NAVI     │──────┼──────▶│  │  Grafana   │ │
│  │  Backend   │      │       │  │            │ │
│  └─────┬──────┘      │       │  └────────────┘ │
│        │             │       │                  │
│  ┌─────▼──────┐      │       │  ┌────────────┐ │
│  │PostgreSQL  │      │       │  │ Prometheus │ │
│  │            │      │       │  │ (Managed)  │ │
│  └────────────┘      │       │  └────────────┘ │
└──────────────────────┘       └──────────────────┘
```

**What You Manage:**
- NAVI backend (your servers)
- PostgreSQL database

**What Grafana Cloud Manages:**
- Grafana dashboards
- Prometheus metrics storage
- Alerting (PagerDuty/Slack integration)

**Estimated Monthly Cost:** $50-500 (Grafana Cloud only)

---

## Production Deployment Checklist

### Phase 1: Infrastructure Setup (1-2 weeks)

#### 1.1 Compute & Networking
- [ ] Provision compute resources (ECS/EKS/VMs)
- [ ] Set up VPC/network with private subnets
- [ ] Configure load balancers (ALB/NLB/HAProxy)
- [ ] Set up auto-scaling policies
- [ ] Configure DNS (Route 53 or equivalent)

#### 1.2 Database
- [ ] Provision PostgreSQL (RDS Multi-AZ or HA cluster)
- [ ] Configure backup policies (automated daily backups)
- [ ] Set up read replicas for scaling
- [ ] Configure connection pooling (PgBouncer)
- [ ] Test failover procedures

#### 1.3 Monitoring Infrastructure
- [ ] **Option A:** Set up Amazon Managed Grafana + Prometheus
- [ ] **Option B:** Deploy self-hosted Grafana + Prometheus HA
- [ ] **Option C:** Configure Grafana Cloud account
- [ ] Update Grafana URL in configs:
  ```bash
  ./scripts/update_grafana_urls.sh https://your-grafana-url.com
  ```

#### 1.4 Storage & Backups
- [ ] Configure S3/object storage for logs
- [ ] Set up automated database backups
- [ ] Configure metrics retention (30 days recommended)
- [ ] Test restore procedures

---

### Phase 2: Security Configuration (1 week)

#### 2.1 Authentication & Authorization
- [ ] Remove default admin/admin credentials
- [ ] Configure SSO (SAML/OAuth) for Grafana
- [ ] Set up RBAC for Grafana dashboards
- [ ] Configure API authentication for NAVI backend
- [ ] Implement secret management (AWS Secrets Manager/Vault)

#### 2.2 Network Security
- [ ] Configure security groups/firewall rules
- [ ] Enable TLS/HTTPS for all endpoints
- [ ] Set up WAF (Web Application Firewall)
- [ ] Configure VPN for internal access
- [ ] Enable audit logging

#### 2.3 Compliance
- [ ] Data encryption at rest
- [ ] Data encryption in transit
- [ ] Configure log retention policies
- [ ] Set up compliance monitoring
- [ ] Document security procedures

---

### Phase 3: Monitoring & Alerting (3-5 days)

#### 3.1 Deploy Prometheus
- [ ] Deploy Prometheus to production environment
- [ ] Configure scrape targets for NAVI backend
- [ ] Import alert rules from `prometheus/alerts/navi-slos.yaml`
- [ ] Configure long-term storage (Thanos/Cortex if needed)
- [ ] Test metric collection

#### 3.2 Deploy Grafana Dashboards
- [ ] Import 4 production dashboards
  ```bash
  # Update to production Grafana URL first
  ./scripts/update_grafana_urls.sh https://your-production-grafana.com

  # Import dashboards
  ./scripts/import_dashboards.sh
  ```
- [ ] Configure Prometheus data source
- [ ] Configure PostgreSQL data source
- [ ] Set up dashboard permissions
- [ ] Test dashboard functionality

#### 3.3 Configure Alert Routing
- [ ] Set up PagerDuty integration
  - Create PagerDuty service
  - Configure escalation policies
  - Add integration key to Alertmanager

- [ ] Set up Slack notifications
  - Create Slack app
  - Add webhook URL to Alertmanager
  - Configure channel routing

- [ ] Configure email alerts (SMTP)

- [ ] Update `prometheus/alertmanager.yml`:
  ```yaml
  route:
    receiver: 'pagerduty-critical'
    group_by: ['alertname', 'severity']
    routes:
      - match:
          severity: critical
        receiver: 'pagerduty-critical'
      - match:
          severity: warning
        receiver: 'slack-warnings'

  receivers:
    - name: 'pagerduty-critical'
      pagerduty_configs:
        - service_key: '<YOUR_PAGERDUTY_KEY>'

    - name: 'slack-warnings'
      slack_configs:
        - api_url: '<YOUR_SLACK_WEBHOOK>'
          channel: '#navi-alerts'
  ```

#### 3.4 Test Alerting
- [ ] Test each alert by simulating threshold violations
- [ ] Verify PagerDuty pages on-call engineer
- [ ] Verify Slack notifications arrive
- [ ] Test escalation procedures
- [ ] Document alert response procedures

---

### Phase 4: Application Deployment (3-5 days)

#### 4.1 Environment Configuration
- [ ] Set production environment variables
  ```bash
  # Database
  DATABASE_URL=postgresql://user:pass@prod-db.region.rds.amazonaws.com:5432/navi

  # LLM APIs
  ANTHROPIC_API_KEY=<production-key>
  OPENAI_API_KEY=<production-key>

  # Monitoring
  PROMETHEUS_PUSH_GATEWAY=https://prometheus.your-domain.com

  # Application
  ENVIRONMENT=production
  LOG_LEVEL=info
  ```

- [ ] Configure secrets management
- [ ] Set resource limits (CPU, memory)
- [ ] Configure health checks

#### 4.2 Deploy Application
- [ ] Deploy NAVI backend to production
- [ ] Run database migrations
- [ ] Deploy frontend (if applicable)
- [ ] Configure CDN
- [ ] Set up DNS records

#### 4.3 Validation
- [ ] Run E2E validation tests against production
  ```bash
  NAVI_BASE_URL=https://api.your-domain.com make e2e-validation-quick
  ```
- [ ] Verify metrics collection
- [ ] Check dashboard data
- [ ] Test all API endpoints
- [ ] Performance testing

---

### Phase 5: Operations Setup (1 week)

#### 5.1 On-Call Rotation
- [ ] Set up PagerDuty on-call schedule
- [ ] Add team members to rotation
- [ ] Configure escalation policies
- [ ] Update emergency contacts in `docs/ONCALL_PLAYBOOK.md`
  ```markdown
  | Engineering Manager | John Doe | +1-555-123-4567 | @john | john@company.com |
  ```

#### 5.2 Runbook Updates
- [ ] Update runbooks with production URLs
- [ ] Add production-specific troubleshooting steps
- [ ] Document deployment procedures
- [ ] Create rollback procedures
- [ ] Test incident response

#### 5.3 Monitoring & SLOs
- [ ] Establish baseline metrics
- [ ] Verify SLO thresholds are appropriate
- [ ] Set up error budget tracking
- [ ] Configure SLO dashboards
- [ ] Document SLO review process

---

### Phase 6: Go-Live (2-3 days)

#### 6.1 Pre-Launch
- [ ] Final security review
- [ ] Load testing
- [ ] Disaster recovery drill
- [ ] Communication plan ready
- [ ] Rollback plan documented

#### 6.2 Launch
- [ ] Deploy to production
- [ ] Monitor metrics closely (first 24 hours)
- [ ] Watch for alerts
- [ ] Check error rates and latency
- [ ] Verify SLO compliance

#### 6.3 Post-Launch
- [ ] 24-hour monitoring review
- [ ] Week 1 retrospective
- [ ] Tune alert thresholds if needed
- [ ] Update documentation based on learnings
- [ ] Plan next improvements

---

## Production Configuration Changes

### Update URLs for Production

When deploying to production, update all URLs:

```bash
# 1. Update Grafana URLs
./scripts/update_grafana_urls.sh https://grafana.your-domain.com

# 2. Commit changes
git add .
git commit -m "Update monitoring URLs for production"

# 3. Deploy updated configs
```

### Configuration Files to Update

1. **Grafana Dashboards**
   - `grafana/dashboards/*.json` - Update via script

2. **Prometheus Alerts**
   - `prometheus/alerts/navi-slos.yaml` - Update via script
   - `prometheus/alertmanager.yml` - Add PagerDuty/Slack

3. **Application Config**
   - `backend/.env.production` - Set production variables
   - Database URLs
   - API endpoints
   - Feature flags

4. **Documentation**
   - `docs/ONCALL_PLAYBOOK.md` - Update contact info
   - `CUSTOMIZATION_STATUS.md` - Update URLs

---

## Production Best Practices

### High Availability
- **Minimum 2 instances** of NAVI backend (load balanced)
- **Database replicas** for failover
- **Multi-AZ deployment** (if using AWS)
- **Auto-scaling** based on CPU/memory/request rate

### Security
- **Never use default credentials** in production
- **Rotate secrets regularly** (90-day policy)
- **Enable audit logging** for all actions
- **Network isolation** (private subnets, VPC)
- **Regular security scanning**

### Monitoring
- **Alert fatigue prevention:** Tune thresholds carefully
- **On-call rotation:** No single points of failure
- **Escalation policies:** 5-minute initial response time
- **Post-mortem culture:** Learn from incidents
- **SLO reviews:** Monthly review of error budgets

### Data Management
- **Daily backups** with 30-day retention
- **Test restores** monthly
- **Metrics retention:** 30 days (detailed), 1 year (downsampled)
- **Log retention:** 90 days (compliance requirement)

---

## Cost Estimates

### AWS Deployment (Medium Scale)

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| ECS/EKS (2-4 instances) | $150-300/mo | t3.large or equivalent |
| RDS PostgreSQL (Multi-AZ) | $200-400/mo | db.r5.large |
| Amazon Managed Grafana | $50-100/mo | Active users pricing |
| Amazon Managed Prometheus | $50-150/mo | Based on metrics volume |
| Load Balancer | $20-30/mo | Application Load Balancer |
| S3 Storage | $10-30/mo | Logs and backups |
| CloudWatch/Logs | $20-50/mo | Log storage |
| **Total** | **$500-1,060/mo** | Can scale up/down |

### Self-Hosted (Medium Scale)

| Component | Hardware Cost | Monthly OpEx |
|-----------|---------------|--------------|
| 3 Kubernetes nodes | - | Existing infra |
| PostgreSQL HA (3 nodes) | - | Existing infra |
| Storage (1TB) | - | $50-100 |
| Network | - | $20-50 |
| **Total** | Uses existing | $70-150/mo |

**Note:** Self-hosted assumes existing infrastructure. Actual costs vary.

---

## Timeline Summary

| Phase | Duration | Complexity |
|-------|----------|------------|
| Infrastructure Setup | 1-2 weeks | Medium-High |
| Security Configuration | 1 week | High |
| Monitoring & Alerting | 3-5 days | Medium |
| Application Deployment | 3-5 days | Medium |
| Operations Setup | 1 week | Low-Medium |
| Go-Live & Stabilization | 2-3 days | High |
| **Total** | **4-6 weeks** | |

**Recommended:** Run parallel staging environment for 1-2 weeks before production launch.

---

## Support & Resources

### Documentation
- [Production Readiness Review](PRODUCTION_READINESS_REVIEW.md)
- [On-Call Playbook](ONCALL_PLAYBOOK.md)
- [SLO Definitions](SLO_DEFINITIONS.md)
- [E2E Validation Guide](E2E_VALIDATION.md)

### Tools
- [Grafana Dashboard Import Script](../scripts/import_dashboards.sh)
- [URL Update Script](../scripts/update_grafana_urls.sh)
- [E2E Validation Suite](../scripts/e2e_real_llm_validation.py)

### External Resources
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Google SRE Book](https://sre.google/books/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Documentation](https://grafana.com/docs/)

---

## Questions?

**Contact:** support@Navi.com
**GitHub:** https://github.com/NNDSrinivas/autonomous-engineering-platform
**Documentation:** [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
