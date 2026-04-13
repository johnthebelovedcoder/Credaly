# Data Protection Impact Assessment (DPIA)
## Predictive Behavioral Credit & Insurance Platform

**Document Version:** 1.0  
**Date:** April 2026  
**Prepared by:** Credaly Engineering & Legal Team  
**Submitted to:** Nigeria Data Protection Commission (NDPC)  
**Classification:** Confidential — Regulatory Filing  

---

## 1. Description of Processing Operations

### 1.1 Product Overview
The Credaly Predictive Behavioral Credit & Insurance Platform is a B2B SaaS infrastructure layer that aggregates multi-tier alternative data, runs it through a layered ML pipeline, and delivers a composite credit score with confidence intervals via a real-time API.

The platform does **not** lend. It scores. Lenders, insurers, and regulated bureaus are its customers.

### 1.2 Nature of Processing
| Aspect | Description |
|--------|-------------|
| **Data Subjects** | Nigerian adults (borrowers) whose creditworthiness is being assessed |
| **Data Controllers** | Lender clients who integrate with the API and make credit decisions |
| **Data Processor** | Credaly (processes data on behalf of lenders) |
| **Lawful Basis** | Explicit consent (NDPA Section 24) — obtained per data category |
| **Purpose** | Credit scoring and risk assessment for thin-file populations |

### 1.3 Data Categories Processed
| Category | Examples | Sensitivity | Retention |
|----------|----------|-------------|-----------|
| Identity | BVN, phone number, name | High (PII) | Until consent withdrawal + 30 days |
| Formal Credit | Bureau scores, account history, delinquency flags | Medium | 24 months (raw), 36 months (derived) |
| Bank/Financial | Transaction patterns, income stability, expense volatility | High | 24 months (raw), 36 months (derived) |
| Telco | Airtime top-up frequency, data subscription patterns | Medium | 24 months (raw), 36 months (derived) |
| Mobile Money | Transaction summaries, inflow/outflow trends | High | 24 months (raw), 36 months (derived) |
| Utility | Prepayment history, payment streaks | Low | 24 months (raw), 36 months (derived) |
| Psychographic | App usage signals, address stability, employment tenure | Medium | 36 months (derived only) |

### 1.4 Data Sources
| Source | Type | Integration Method |
|--------|------|-------------------|
| CRC (Credit Registry Company) | Credit Bureau | API with signed DPA |
| FirstCentral | Credit Bureau | API with signed DPA |
| Credit Registry | Credit Bureau | API with signed DPA |
| Mono, Okra, OnePipe | Open Banking Partners | CBN-licensed API providers |
| MTN, Airtel, Glo | Telco Operators | Licensed data sharing agreements |
| OPay, PalmPay | Mobile Money | API with signed DPA |
| BNPL Providers | Credit Providers | Data contribution agreements |

---

## 2. Necessity and Proportionality Assessment

### 2.1 Necessity
**Why is this processing necessary?**  
Nigeria has over 100 million adults without a usable credit file. Traditional credit scoring excludes the majority of the population. This platform enables lenders to assess creditworthiness using alternative data signals, expanding financial inclusion while maintaining responsible lending standards.

**Could the purpose be achieved with less intrusive processing?**  
- Minimum consent set (bureau + bank) is required for any meaningful score
- Alternative data tiers (telco, mobile money, utility) are optional and consented to separately
- Psychographic data is the most intrusive and is only used with explicit, separate consent
- Data minimization is enforced: only the minimum signals needed for scoring are collected

### 2.2 Proportionality
| Principle | Implementation |
|-----------|---------------|
| **Purpose Limitation** | Each consent event specifies exact purpose. Data collected for "credit scoring for Lender X" cannot be used for model training or shared with Lender Y without separate consent. |
| **Data Minimization** | API pulls are scoped to minimum datasets. E.g., telco consistency index requires only top-up frequency, not call records. |
| **Storage Limitation** | Automated purge workflows enforce 24-month raw data retention, 36-month derived feature retention. |
| **Accuracy** | Features are recomputed on new data ingestion events. Scores are refreshed proactively. |

---

## 3. Risk Assessment

### 3.1 Risks to Data Subjects

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Unfair credit decision** based on inaccurate data | Medium | High | Confidence intervals flag low-data scores for manual review. Borrowers can request human review (NDPA Section 34). |
| **Discrimination** through biased ML model | Medium | High | Model fairness audits conducted quarterly. PSI monitoring detects population drift. Model versioning enables rollback. |
| **Unauthorized access** to sensitive financial data | Low | High | AES-256 encryption at rest, TLS 1.3 in transit. PII tokenized before ML layer. API keys bcrypt-hashed. |
| **Consent not meaningful** — users forced to accept all | Low | Medium | Granular per-category consent. Minimum set disclosed upfront. No "accept all or nothing." |
| **Data breach** exposing personal information | Low | Critical | Multi-layered security: network isolation, encrypted storage, tamper-evident audit logs, SOC 2 target. |
| **Function creep** — data used beyond consented purpose | Low | High | Purpose limitation enforced at pipeline level. Cryptographic consent tokens travel with data. |
| **Automated decision without human oversight** | Medium | High | Right to human review built into platform (US-015). 5-business-day SLA. Lenders notified of review requests. |
| **Inaccurate score harming financial opportunities** | Medium | High | Confidence bands (HIGH/MEDIUM/LOW) indicate score reliability. Lenders advised to use bands for decision routing. |

### 3.2 Risk Matrix Summary

| Risk Level | Count | Actions Required |
|------------|-------|-----------------|
| **Critical** | 1 (data breach) | Penetration testing, SOC 2 audit, incident response plan |
| **High** | 2 (unfair decision, function creep) | Human review workflow, purpose limitation enforcement, model fairness audits |
| **Medium** | 3 (discrimination, automated decision, inaccurate score) | Quarterly bias audits, confidence intervals, SLA monitoring |
| **Low** | 2 (unauthorized access, meaningless consent) | Existing mitigations adequate, ongoing monitoring |

---

## 4. Safeguards and Security Measures

### 4.1 Technical Safeguards
| Measure | Implementation |
|---------|---------------|
| **Encryption at rest** | AES-256 for all PII fields (BVN, phone, name) |
| **Encryption in transit** | TLS 1.3 minimum for all internal and external communications |
| **PII tokenization** | Raw PII never reaches the ML layer. Salted SHA-256 hashes used as foreign keys. |
| **API key security** | Bcrypt hashing (12 rounds). Keys shown once at creation, never retrievable. |
| **Consent tokenization** | Cryptographic HMAC signatures on every consent record. Tamper-evident audit log chain. |
| **Access control** | MFA for all infrastructure access. No root account usage in production. |
| **Network security** | Service isolation via Kubernetes namespaces and network policies. |
| **Monitoring** | Centralized structured logging. Datadog for infrastructure metrics. PagerDuty for on-call alerting. |
| **Backup & recovery** | Multi-AZ PostgreSQL with automated backups. RTO: 1 hour, RPO: 15 minutes. |

### 4.2 Organizational Safeguards
| Measure | Implementation |
|---------|---------------|
| **Data Processing Agreements** | Signed DPA with every data source and lender client |
| **Employee training** | Annual data protection training for all staff |
| **Access reviews** | Quarterly access review for all systems |
| **Incident response** | Documented incident response plan with 72-hour breach notification |
| **Vendor management** | Third-party security assessments for all data source partners |
| **Penetration testing** | Before launch and quarterly thereafter |
| **Audit trail** | Immutable consent audit log with hash-chain tamper evidence |

### 4.3 Compliance Safeguards
| Requirement | Implementation |
|-------------|---------------|
| **Right to Access (DSAR)** | GET /v1/subject/{bvn}/data — compiles all data within 72 hours |
| **Right to Erasure** | DELETE /v1/consent/{token_id} — cascades to derived features and notifies lenders |
| **Right to Correction** | Data correction workflow with 30-day SLA |
| **Right to Human Review** | POST /v1/review — 5-business-day SLA, lender notification |
| **Right to Explanation** | Human-readable explanations generated for every automated score |
| **Consent Withdrawal** | Immediate cessation of data ingestion, feature flagging, lender notification |
| **Data Portability** | DSAR response includes all data in machine-readable JSON format |

---

## 5. ML Model Governance

### 5.1 Model Development
| Aspect | Practice |
|--------|----------|
| **Training Data** | Historical loan books from partner lenders (with signed DPAs) |
| **Feature Selection** | Based on predictive power, not demographic proxies |
| **Bias Testing** | Disparate impact analysis across gender, age, geography |
| **Validation** | Train/test/validation split. Out-of-time validation for temporal robustness |

### 5.2 Model Monitoring
| Metric | Threshold | Action |
|--------|-----------|--------|
| **Gini Coefficient** | > 0.45 target | Monthly review. Retraining if declining. |
| **Population Stability Index (PSI)** | Alert at 0.2, retrain at 0.25 | Automated alerting and retraining trigger |
| **KS Statistic** | > 0.35 target | Monthly review |
| **Score Distribution** | No dramatic shift | Histogram monitoring |

### 5.3 Model Versioning and A/B Testing
- All models versioned via MLflow
- A/B testing with configurable traffic splitting
- Rollback capability within 5 minutes
- Previous model versions retained for 12 months

---

## 6. Data Flow Map

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Data Sources     │     │  Consent Engine   │     │  Lender Client   │
│  (Bureau, Bank,  │────▶│  (Per-category    │────▶│  (API Request    │
│  Telco, etc.)     │     │   consent req'd)  │     │   + consent ref) │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
         │                          │                       │
         ▼                          ▼                       ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Ingestion &     │     │  Audit Log       │     │  Scoring Engine  │
│  Normalization   │────▶│  (Tamper-evident)│     │  (3-model        │
│  (Circuit        │     │                  │     │   ensemble)      │
│   breaker)       │     └──────────────────┘     └────────┬─────────┘
└──────────────────┘                                        │
         │                                                  ▼
         ▼                                         ┌──────────────────┐
┌──────────────────┐                               │  Score +         │
│  Feature Store   │                               │  Confidence +    │
│  (Online: Redis) │◀─────────────────────────────▶│  Explanation     │
│  (Offline: S3)   │                               │  (Lender +       │
└──────────────────┘                               │   Borrower)      │
                                                   └──────────────────┘
```

---

## 7. Residual Risk Assessment

After applying all mitigations:

| Risk | Residual Likelihood | Residual Impact | Residual Level | Acceptable? |
|------|-------------------|----------------|----------------|-------------|
| Data breach | Low | High | Medium | Yes — with ongoing monitoring |
| Unfair credit decision | Low | Medium | Low | Yes — human review available |
| Model discrimination | Low | Medium | Low | Yes — quarterly audits |
| Function creep | Very Low | High | Low | Yes — technical enforcement |
| Meaningless consent | Very Low | Medium | Very Low | Yes — granular design |

**Overall Residual Risk: LOW — Processing may proceed with safeguards as described.**

---

## 8. Consultation

### 8.1 Internal Consultation
- **Data Protection Officer:** [Name] — reviewed and approved
- **Engineering Lead:** [Name] — technical controls verified
- **Legal Counsel:** [Name] — NDPA compliance confirmed
- **Risk/Compliance:** [Name] — CBN framework alignment confirmed

### 8.2 External Consultation
- **NDPC Filing:** Submitted [Date]
- **CBN Notification:** In progress (Open Banking compliance)

---

## 9. Action Plan

| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| File DPIA with NDPC | Legal | Before first enterprise client | Pending |
| Complete penetration test | Security | Before launch | Pending |
| Implement automated retention purge | Engineering | Phase 1 | In Progress |
| SOC 2 Type II audit initiation | Compliance | 18 months from launch | Planned |
| Quarterly model fairness audits | Data Science | Monthly from launch | Planned |
| Annual DPIA review | Legal/DPO | Annual | Planned |

---

## 10. Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | Timilehin Oripeloye | | |
| Data Protection Officer | [Name] | | |
| Engineering Lead | [Name] | | |
| Legal Counsel | [Name] | | |

---

*This DPIA is a living document. It must be reviewed and updated at least annually, or whenever there is a material change to the processing operations.*
