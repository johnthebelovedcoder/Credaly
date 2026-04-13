# Credaly Monitoring & Alerting Configuration
# Per PRD Section 6.2, 6.3: Security, Scalability, Compliance

## 1. Datadog Dashboard Configuration

### 1.1 API Latency Dashboard
```yaml
dashboard:
  title: "Credaly API Performance"
  description: "Real-time API latency and throughput metrics"
  widgets:
    - timeseries:
        title: "p95 Response Time (Scoring API)"
        query: "perf:scoring_api:latency:p95"
        thresholds:
          critical: 3000  # 3s — PRD target
          warning: 2000
    - timeseries:
        title: "p50 Response Time (Cached Scores)"
        query: "perf:scoring_api:latency:p50_cached"
        thresholds:
          critical: 500  # 500ms — PRD target
    - timeseries:
        title: "Requests per Second"
        query: "rate:scoring_api.requests{env:production}"
    - timeseries:
        title: "Error Rate (%)"
        query: "rate:scoring_api.errors{env:production} / rate:scoring_api.requests{env:production} * 100"
        thresholds:
          critical: 5
          warning: 1
    - timeseries:
        title: "Batch Scoring Throughput (jobs/hour)"
        query: "count:batch_scoring.completed{env:production}"
```

### 1.2 Model Performance Dashboard
```yaml
dashboard:
  title: "ML Model Health"
  description: "Model drift, accuracy, and retraining status"
  widgets:
    - timeseries:
        title: "Gini Coefficient (Monthly)"
        query: "ml:model.gini_coefficient{env:production}"
        thresholds:
          critical: 0.30  # Below industry benchmark
          warning: 0.40
    - timeseries:
        title: "PSI by Feature (All Features)"
        query: "ml:feature.psi{env:production}"
        thresholds:
          critical: 0.25  # Auto-retrain threshold
          warning: 0.20   # Alert threshold
    - timeseries:
        title: "Score Distribution (300-850)"
        query: "histogram:scoring.score{env:production}"
    - timeseries:
        title: "Confidence Band Distribution"
        query: "count:scoring.confidence_band{env:production} by {band}"
    - timeseries:
        title: "Model Version Traffic Split"
        query: "count:scoring.model_version{env:production} by {version}"
```

### 1.3 Pipeline Health Dashboard
```yaml
dashboard:
  title: "Data Pipeline Health"
  description: "Ingestion pipeline status, error rates, uptime"
  widgets:
    - status:
        title: "Pipeline Source Status"
        query: "pipeline:source.status{env:production}"
    - timeseries:
        title: "Ingestion Errors by Source (per hour)"
        query: "count:pipeline.errors{env:production} by {source}"
    - timeseries:
        title: "Pipeline Uptime %"
        query: "pipeline:uptime{env:production}"
        thresholds:
          critical: 95
          warning: 99
    - timeseries:
        title: "Feature Freshness (hours since last update)"
        query: "feature:age_hours{env:production}"
        thresholds:
          critical: 6  # PRD target
```

### 1.4 Compliance & Consent Dashboard
```yaml
dashboard:
  title: "Compliance & Consent Monitoring"
  description: "Consent rates, expiry, DSAR fulfillment"
  widgets:
    - timeseries:
        title: "Consent Grants per Day (by Category)"
        query: "count:consent.granted{env:production} by {category}"
    - timeseries:
        title: "Consent Withdrawals per Day"
        query: "count:consent.withdrawn{env:production}"
    - timeseries:
        title: "Active Consents by Category"
        query: "count:consent.active{env:production} by {category}"
    - timeseries:
        title: "DSAR Fulfillment Time (hours)"
        query: "dsar:fulfillment_hours{env:production}"
        thresholds:
          critical: 72  # PRD SLA
          warning: 48
    - timeseries:
        title: "Human Review SLA Breaches"
        query: "count:review.sla_breach{env:production}"
```

---

## 2. PagerDuty Alerting Rules

### 2.1 Critical Alerts (Page immediately, 24/7)

| Alert | Condition | Severity | Runbook |
|-------|-----------|----------|---------|
| **API Down** | Health check fails for 2 consecutive checks | Critical | Runbook #1: Restart pods, check DB connectivity |
| **Database Unreachable** | PostgreSQL connection failures > 5 in 1 min | Critical | Runbook #2: Check RDS status, failover to standby |
| **Data Breach Detected** | Unauthorized access pattern detected | Critical | Runbook #10: Incident response — notify NDPC within 72h |
| **Consent Audit Log Tampered** | Hash chain integrity check fails | Critical | Runbook #11: Forensic investigation, regulatory notification |

### 2.2 High Priority Alerts (Page on-call, business hours)

| Alert | Condition | Severity | Runbook |
|-------|-----------|----------|---------|
| **API p95 > 3s** | Response time exceeds PRD SLA for 5 min | High | Runbook #3: Check Redis cache, DB query plans |
| **Pipeline Source Down** | Any data source failing for > 30 min | High | Runbook #4: Check circuit breaker, contact data partner |
| **PSI > 0.25** | Any feature exceeds retrain threshold | High | Runbook #5: Trigger model retraining |
| **Rate Limit Breach > 10%** | > 10% of requests rate-limited in 15 min | High | Runbook #6: Review client usage, adjust limits if needed |
| **Human Review SLA Breach** | Any review exceeds 5 business days | High | Runbook #7: Escalate to review team lead |

### 2.3 Warning Alerts (No page — dashboard only)

| Alert | Condition | Severity | Runbook |
|-------|-----------|----------|---------|
| **PSI > 0.2** | Feature approaching retrain threshold | Warning | Monitor — prepare retraining |
| **API p95 > 2s** | Approaching SLA threshold | Warning | Investigate before it becomes critical |
| **Pipeline Error Rate > 1%** | Any source with > 1% error rate | Warning | Check source API status |
| **DSAR nearing SLA** | DSAR not fulfilled within 48 hours | Warning | Escalate to data team |
| **Disk Usage > 80%** | Database or Redis approaching capacity | Warning | Plan capacity expansion |

---

## 3. Runbooks

### Runbook #1: API Pod Restart
```
Trigger: API health check failing
Steps:
1. Check pod status: kubectl get pods -n credaly -l app=scoring-api
2. Check pod logs: kubectl logs -n credaly <pod-name> --tail=100
3. If OOMKilled: increase memory limits, restart
4. If DB connection error: check RDS status, verify credentials
5. Restart pod: kubectl rollout restart deployment/scoring-api -n credaly
6. Verify: curl https://api.credaly.io/health
7. If still failing: escalate to engineering lead
```

### Runbook #2: Database Failover
```
Trigger: PostgreSQL connection failures
Steps:
1. Check RDS console for primary instance status
2. If primary is unhealthy: initiate failover to standby
3. Wait for failover complete (~2-5 min)
4. Verify scoring-api pods reconnect (check logs)
5. If pods don't reconnect: restart pods (Runbook #1)
6. Verify: kubectl exec -n credaly <pod> -- curl http://localhost:8000/health
```

### Runbook #3: API Latency Investigation
```
Trigger: API p95 > 3s
Steps:
1. Check Redis cache hit rate: redis-cli INFO stats | grep keyspace_hits
2. If cache miss rate > 50%: check if Redis is healthy
3. Check DB query performance: SELECT * FROM pg_stat_activity WHERE state = 'active'
4. Check for slow queries: Datadog → APM → Traces → sort by duration
5. If specific endpoint is slow: check if ML model inference is the bottleneck
6. If all endpoints slow: check CPU/memory utilization of pods
7. If infrastructure is saturated: scale up (HPA should auto-scale)
```

### Runbook #4: Pipeline Source Recovery
```
Trigger: Data source down for > 30 min
Steps:
1. Identify source: Datadog → Pipeline Dashboard
2. Check circuit breaker status: circuit breaker dashboard
3. If circuit breaker OPEN: wait for half-open state (default: 5 min)
4. Test source connectivity: curl <source-api-url>/health
5. If source is down: contact data partner support
6. If source returns errors: check API key validity, rate limits
7. Verify scoring continues with degraded confidence: check confidence_band distribution
```

### Runbook #5: Model Retraining
```
Trigger: PSI > 0.25 on any feature
Steps:
1. Identify drifted features: ml:feature.psi dashboard
2. Check available training data: count:outcomes.submitted (need > 1000)
3. Trigger retraining: Admin API → POST /admin/metrics/retrain
4. Monitor retraining job: Celery worker logs
5. When complete: check new model Gini coefficient
6. If new model worse: rollback to previous version
7. If better: gradually increase traffic split (10% → 50% → 100%)
8. Monitor for 24h before fully promoting
```

---

## 4. Log Aggregation

### 4.1 Log Retention Policy
| Log Type | Hot Storage | Cold Storage | Total Retention |
|----------|------------|--------------|-----------------|
| API Access Logs | 30 days (OpenSearch) | 7 years (S3 Glacier) | 7 years |
| Application Logs | 30 days (OpenSearch) | 1 year (S3) | 1 year |
| Audit Logs | 90 days (OpenSearch) | 7 years (S3 Glacier) | 7 years |
| ML Training Logs | 90 days (OpenSearch) | 2 years (S3) | 2 years |
| Infrastructure Logs | 30 days (CloudWatch) | 1 year (S3) | 1 year |

### 4.2 Structured Log Format
```json
{
  "timestamp": "2026-04-12T10:30:00.000Z",
  "level": "INFO",
  "service": "scoring-api",
  "event": "score_computed",
  "trace_id": "trc_abc123",
  "bvn_hash": "sha256_hash",
  "score": 620,
  "confidence_band": "MEDIUM",
  "data_coverage_pct": 65.2,
  "model_version": "v1.0.0",
  "latency_ms": 245,
  "lender_id": "lnd_abc123"
}
```
