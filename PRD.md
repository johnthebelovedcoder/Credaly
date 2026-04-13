
PRODUCT REQUIREMENTS DOCUMENT
Predictive Behavioral Credit &

Insurance Platform
AI-powered alternative data credit scoring infrastructure for African lenders

Version
1.0 — Initial Release
Date
April 2026
Product Owner
Timilehin Oripeloye
Status
Draft — Internal Review
Classification
Confidential


1. Executive Summary
Nigeria has over 100 million adults without a usable credit file. Traditional credit bureaus — CRC, FirstCentral, CreditRegistry — rely almost entirely on formal loan history, which most Nigerians lack. Yet the data signals that predict creditworthiness exist: telco usage patterns, mobile money velocity, utility payment consistency, savings behavior, and psychographic signals.

This document defines the product requirements for a Predictive Behavioral Credit & Insurance Platform — a B2B SaaS infrastructure layer that aggregates multi-tier alternative data, runs it through a layered ML pipeline, and delivers a composite credit score with confidence intervals via a real-time API. The platform does not lend; it scores. Lenders, insurers, and eventually regulated bureaus are its customers.

Strategic Positioning
The platform is infrastructure, not a product competing with lenders. Every lender that integrates contributes repayment outcome data back into the model, compounding accuracy over time. This creates a proprietary dataset — African repayment ground truth at scale — that becomes the primary competitive moat. This is a Selling the Shovel play: enabling the ecosystem rather than competing within it.


2. Product Vision & Goals
2.1 Vision Statement
To become the foundational credit intelligence layer for African financial services — the data infrastructure that every lender, insurer, and financial institution depends on to make accurate, fair, and compliant credit decisions for thin-file populations.

2.2 Strategic Goals
Goal
Metric
Target (12 months)
Market penetration
Lenders onboarded
25 active integrations
Data moat growth
Repayment outcomes ingested
500,000+ data points
Score accuracy
Model Gini coefficient
> 0.45 (industry benchmark: 0.30)
Revenue
ARR from API subscriptions
₦180M+
Compliance
NDPC registration + DPIA filed
Before first enterprise client
Uptime
API availability
99.9% SLA


2.3 Non-Goals (Out of Scope for v1)
The platform will not originate or disburse loans
The platform will not build a consumer-facing interface for end borrowers
The platform will not operate as a licensed credit bureau in v1 (this is the v3 ambition)
The platform will not process insurance claims


3. User Personas
Persona 1 — The Digital Lender (Primary)
Ifeoma, Head of Risk at a Digital Lending Startup
Company size: 15–80 staff | Loan book: ₦500M–₦5B | Location: Lagos

Context: Ifeoma manages a portfolio of personal and SME loans. Her current underwriting model uses BVN lookup and a basic bureau check, which rejects 60–70% of applicants due to thin files. She knows many of these applicants are creditworthy — she just can't prove it. Her NPA rate is climbing because the approvals she does make are based on incomplete signals.

Goals: Reduce rejection rate without increasing default rate. Shorten time-to-decision from 48 hours to under 5 minutes. Have a defensible, audit-clean underwriting trail for CBN examination.

Pain Points: Bureau data is stale and covers only ~15% of loan applicants. Internal ML models require data science headcount she doesn't have. Alternative data vendors are fragmented, unregulated, and have no audit trail.

How she uses the platform: Integrates via REST API into her loan origination system. Calls the score endpoint at application time. Uses the confidence interval to decide whether to approve, approve with conditions, or refer to manual review.


Persona 2 — The Microfinance Bank (Primary)
Emeka, CEO of a Tier-2 Microfinance Bank
Institution size: CBN-licensed MFB | Deposit base: ₦2B | Location: Lagos + Abuja

Context: Emeka runs a CBN-licensed MFB targeting traders, market women, and informal sector workers. His core customer base has zero formal credit history. His current process is relationship-based — loan officers visit borrowers, collect references, and approve manually. It doesn't scale.

Goals: Digitize underwriting for loans under ₦500,000. Reduce loan officer cost per approval. Demonstrate to CBN examiners that credit decisions have a documented, non-discriminatory basis.

Pain Points: No digital credit data exists for his customers. He needs an explanation for each decision for compliance. He cannot afford to build ML infrastructure internally.

How he uses the platform: Batch score upload for existing portfolio review. Real-time API for new applications. Uses the human-readable explanation output directly in borrower-facing decision letters.


Persona 3 — The Insurance Underwriter (Secondary)
Ngozi, Actuary at a Mid-Tier Insurance Company
Company size: 200+ staff | Products: Life, credit insurance | Location: Lagos

Context: Ngozi prices credit life insurance products (which pay out if a borrower defaults or dies). Her current pricing is demographic-based — age, income bracket, geography. She knows behavioral signals would give her more accurate risk segmentation but has no access to them.

Goals: Dynamic, behavior-based insurance pricing. Reduce loss ratios on credit insurance products. Identify high-risk segments before, not after, a claim.

How she uses the platform: Subscribes to the risk segmentation API. Uses score percentile bands to create insurance tiers. Pays a monthly subscription rather than per-call.


Persona 4 — The Platform Administrator (Internal)
The Platform Engineer / Data Scientist
Internal user responsible for model monitoring, data pipeline health, consent compliance, and client onboarding.

Goals: Monitor model drift in real time. Manage data ingestion pipelines. Onboard new data source partners. Review and respond to data subject requests (access, deletion, correction). Manage lender API keys and usage quotas.

How they use the platform: Admin dashboard with model performance metrics, pipeline status, consent audit log, and client management tools.


4. User Stories
Format: As a [persona], I want to [action], so that [outcome]. Acceptance criteria define the minimum passing condition.

4.1 Lender — Credit Scoring
ID
User Story
Priority
Acceptance Criteria
US-001
As a lender, I want to submit a borrower's BVN and phone number and receive a credit score within 3 seconds, so that I can make real-time loan decisions.
P0
API responds in < 3s p95. Score between 300–850. HTTP 200 on success, structured error on failure.
US-002
As a lender, I want to receive a confidence interval alongside the score, so that I can route low-confidence applications to manual review.
P0
Response includes score, confidence_band (HIGH / MEDIUM / LOW), and data_coverage_pct.
US-003
As a lender, I want to receive a human-readable explanation of the score's key drivers, so that I can use it in borrower-facing decision letters.
P0
Response includes top 3 positive factors and top 3 negative factors, written in plain English, under 50 words each.
US-004
As a lender, I want to pull a borrower's score history over the past 12 months, so that I can see whether creditworthiness is improving or declining.
P1
Score trend endpoint returns monthly scores for last 12 periods where available.
US-005
As a lender, I want to configure which data tiers to include in scoring (formal only, formal + alternative, full), so that I can match the scoring depth to my product risk appetite.
P1
Request body accepts tier_config parameter. Response reflects only included tiers.
US-006
As a lender, I want to subscribe to webhook notifications when a scored borrower's credit profile changes materially, so that I can proactively manage my portfolio.
P2
Webhook fires when score changes by > 40 points or confidence band changes.


4.2 Lender — Onboarding & Integration
ID
User Story
Priority
Acceptance Criteria
US-007
As a lender, I want to generate and manage API keys from a self-serve dashboard, so that I can integrate without waiting for manual provisioning.
P0
Dashboard allows create, rotate, and revoke API key. Keys are scoped to environments (sandbox / production).
US-008
As a lender, I want a sandbox environment with synthetic borrower data, so that I can test my integration before going live.
P0
Sandbox returns realistic but non-real data. 100 synthetic borrower profiles available. No consent requirements in sandbox.
US-009
As a lender, I want to view my API usage, spending, and rate limits in real time, so that I can manage my integration costs.
P1
Dashboard shows daily call volume, monthly spend, and rate limit headroom. Exportable as CSV.
US-010
As a lender, I want to submit repayment outcomes (paid on time / defaulted / restructured) back to the platform, so that I fulfil my data contribution agreement.
P0
Outcome submission endpoint accepts loan_id, borrower_bvn, outcome, and outcome_date. Confirmed receipt in response.


4.3 Borrower — Consent & Data Rights
ID
User Story
Priority
Acceptance Criteria
US-011
As a borrower, I want to see exactly what data is being collected about me and why, before I consent, so that I can make an informed decision.
P0
Consent screen lists each data category, the purpose, the retention period, and the third parties with access. Plain English, no legalese.
US-012
As a borrower, I want to grant or revoke consent for each data category independently, so that I am not forced to share all data or nothing.
P0
Consent UI supports per-category toggle. Minimum consent set required for scoring is disclosed upfront.
US-013
As a borrower, I want to request deletion of my data, so that I can exercise my right to erasure under the NDPA.
P1
Deletion request triggers 30-day workflow. Confirmation sent to borrower. Cascade to derived features and downstream lenders.
US-014
As a borrower, I want to receive a plain-language explanation of why my score is what it is, so that I understand what I can improve.
P1
Borrower-facing score explanation generated separately from lender explanation — different vocabulary, actionable framing.
US-015
As a borrower, I want to request a human review of an automated credit decision, so that I can exercise my rights under NDPA Section 34.
P2
Human review request queued within the platform. Lender notified. SLA: 5 business days.


4.4 Platform Administrator
ID
User Story
Priority
Acceptance Criteria
US-016
As an admin, I want to monitor model performance metrics (Gini, PSI, KS statistic) in real time, so that I can detect model drift before it affects score quality.
P0
Admin dashboard shows daily Gini, monthly PSI, and KS statistic per model version. Alert fires when PSI > 0.2.
US-017
As an admin, I want to manage data ingestion pipelines per source (telco, bureau, mobile money), so that I can isolate and fix failures without affecting other sources.
P0
Each pipeline has independent health status, last-run timestamp, and error log. Failed pipeline falls back gracefully — score produced from available tiers.
US-018
As an admin, I want to onboard a new lender client including signing their DPA, provisioning their API keys, and configuring their tier access, so that the full process is auditable.
P1
Onboarding workflow produces signed DPA record, API key pair, and audit log entry.
US-019
As an admin, I want to view the full consent audit log for any data subject, so that I can respond to regulatory inquiries.
P0
Audit log queryable by BVN or consent token. Returns full consent event history with timestamps, IP, and purpose.


5. Functional Requirements
Requirements are tagged P0 (launch blocker), P1 (launch target), or P2 (post-launch).

5.1 Data Ingestion Module
ID
Requirement
Priority
FR-001
The system shall connect to CRC, FirstCentral, and CreditRegistry credit bureaus via their respective APIs and retrieve bureau data on demand at score request time.
P0
FR-002
The system shall validate BVN against the NIN-NIMC linkage database to verify identity before any data pull.
P0
FR-003
The system shall ingest bank statement data via CBN Open Banking API partners (Mono, Okra, OnePipe) with OAuth-based user authorization.
P0
FR-004
The system shall ingest telco usage signals (airtime top-up frequency, data subscription patterns) via licensed data sharing agreements with MTN, Airtel, and Glo.
P1
FR-005
The system shall ingest mobile money transaction summaries from OPay and PalmPay APIs.
P1
FR-006
The system shall ingest BNPL repayment records from Carbon, Fairmoney, and other BNPL providers that sign data contribution agreements.
P1
FR-007
The system shall ingest utility prepayment data from EKEDC and IKEDC via their customer data APIs.
P2
FR-008
The system shall normalize all ingested data to a canonical schema before feature engineering. Normalization must handle missing fields gracefully without rejecting the record.
P0
FR-009
The system shall deduplicate records across sources using BVN as the primary key and phone number as a secondary key.
P0
FR-010
Each data ingestion pipeline shall be independently monitored and capable of graceful degradation — if a single source fails, scoring proceeds with remaining sources and the confidence band reflects the reduced data coverage.
P0


5.2 Consent & Privacy Module
ID
Requirement
Priority
FR-011
The system shall present a granular consent interface that requires separate explicit consent for each data category (bureau, bank, telco, mobile money, utility, psychographic).
P0
FR-012
Each granted consent shall generate a cryptographically signed consent token containing: data subject ID, data category, stated purpose, authorized recipients, expiry date, and policy version.
P0
FR-013
Consent tokens shall travel with all data through the pipeline. Any API response that includes scored data shall include the relevant consent token reference.
P0
FR-014
The system shall support consent withdrawal. Upon withdrawal, the system must: (a) immediately cease ingesting new data from the revoked source, (b) flag all derived features built from that source, and (c) notify downstream lenders holding active scores.
P0
FR-015
The system shall enforce purpose limitation. Data collected under consent purpose 'credit scoring for Lender X' shall not be used for model training or shared with Lender Y without a separate consent event.
P0
FR-016
The system shall implement automated data retention enforcement. Raw transaction data shall be purged after 24 months. Derived features shall be purged after 36 months or upon consent withdrawal.
P1
FR-017
The system shall provide a Data Subject Access Request (DSAR) workflow that compiles all data held about a subject within 72 hours of request.
P1
FR-018
The system shall generate a human-readable explanation for every automated credit decision, satisfying the right-to-explanation requirement under NDPA Section 34.
P0
FR-019
The system shall maintain a full, immutable consent audit log. Log entries shall be append-only and cryptographically tamper-evident.
P0


5.3 Feature Engineering Module
ID
Requirement
Priority
FR-020
The system shall compute a standardized set of features from ingested raw data. The feature set shall include at minimum: income_stability_score, expense_volatility_score, telco_consistency_index, mobile_money_inflow_trend, utility_payment_streak, bureau_delinquency_flag, debt_to_income_ratio.
P0
FR-021
Computed features shall be stored in a feature store with versioning. Feature values shall be tied to the data snapshot timestamp, not the scoring timestamp.
P0
FR-022
Features shall be recomputed asynchronously on new data ingestion events, not only at score request time, so that scores can be refreshed proactively.
P1
FR-023
The feature engineering pipeline shall produce a data_coverage_pct metric per borrower, indicating the percentage of total feature signals available for that individual.
P0


5.4 ML Scoring Module
ID
Requirement
Priority
FR-024
The system shall operate three parallel ML models: (1) Base Credit Model trained on structured financial data, (2) Alternative Data Booster trained on behavioral signals, (3) Psychometric Engine trained on survey and proxy signals.
P0
FR-025
The Base Credit Model shall use a gradient-boosted tree architecture (XGBoost or LightGBM). Initial training data shall come from partner lenders' historical loan books.
P0
FR-026
The Composite Scoring Engine shall combine outputs from all three models using a weighted ensemble. Weights shall be dynamically adjusted based on data_coverage_pct for the individual being scored.
P0
FR-027
The system shall output a credit score on a 300–850 scale, a confidence interval (±X points at 95%), and a reliability band (HIGH / MEDIUM / LOW).
P0
FR-028
The system shall support model versioning. A/B testing of model versions shall be possible without downtime, with traffic splitting configurable via the admin dashboard.
P1
FR-029
The system shall monitor for model drift using Population Stability Index (PSI). An alert shall fire when PSI > 0.2 on any feature. A retraining job shall be triggered automatically when PSI > 0.25.
P1
FR-030
The system shall ingest repayment outcome data submitted by lenders and automatically incorporate it into scheduled model retraining (minimum: monthly retraining cycle).
P0


5.5 API & Integration Module
ID
Requirement
Priority
FR-031
The platform shall expose a RESTful API with the following core endpoints: POST /v1/score, GET /v1/score/{bvn}/history, POST /v1/outcomes, POST /v1/consent, DELETE /v1/consent/{token_id}, GET /v1/subject/{bvn}/data.
P0
FR-032
All API requests shall be authenticated using HMAC-signed API keys. Keys shall support environment scoping (sandbox / production) and IP allowlisting.
P0
FR-033
The API shall return structured JSON responses with consistent error codes, error messages, and a trace_id for debugging.
P0
FR-034
The API shall enforce rate limiting at 100 requests/minute per API key by default. Rate limits shall be configurable per client in the admin dashboard.
P1
FR-035
The platform shall support outbound webhooks for score change events. Lenders shall be able to register webhook endpoints and choose which events to subscribe to.
P2
FR-036
The platform shall provide an OpenAPI 3.0 specification and auto-generated interactive API documentation (Swagger UI) in the developer portal.
P1
FR-037
The platform shall provide official SDK libraries in Python and JavaScript/TypeScript for initial launch.
P1


5.6 Admin Dashboard
ID
Requirement
Priority
FR-038
The admin dashboard shall display real-time pipeline health status for each data source with last-run timestamp and error rate.
P0
FR-039
The admin dashboard shall display model performance metrics: daily Gini coefficient, monthly PSI per feature, KS statistic, and score distribution histogram.
P0
FR-040
The admin dashboard shall support client management: create, suspend, or terminate lender accounts; view per-client API usage and billing.
P0
FR-041
The admin dashboard shall provide a consent audit log viewer, searchable by BVN, date range, and event type.
P0
FR-042
The admin dashboard shall support manual model retraining trigger with job progress tracking.
P1


6. Non-Functional Requirements

6.1 Performance
Requirement
Target
Notes
API p95 response time (real-time scoring)
< 3 seconds
Includes bureau call + feature retrieval + model inference
API p95 response time (cached score)
< 500ms
When score was computed < 24h ago
Batch scoring throughput
> 10,000 records/hour
For portfolio review use case
API availability
99.9% monthly
Max 43.8 minutes downtime/month
Data pipeline freshness
< 6 hours
Time from new data event to updated feature store


6.2 Security
All data in transit encrypted using TLS 1.3 minimum
All data at rest encrypted using AES-256
API keys hashed in the database using bcrypt — never stored in plaintext
PII fields (BVN, phone, name) tokenized in the data pipeline — raw PII never reaches the ML layer
All infrastructure access requires MFA. No root account usage in production
Penetration testing conducted before launch and quarterly thereafter
SOC 2 Type II audit target within 18 months of launch

6.3 Scalability
The scoring API shall be stateless and horizontally scalable behind a load balancer
The feature store shall support partitioning by BVN prefix to allow horizontal scaling
Database read replicas shall be provisioned for the admin dashboard to prevent reporting queries from impacting API performance

6.4 Compliance
Regulation
Requirement
Implementation
NDPA 2023
Lawful basis for processing
Explicit consent as lawful basis for all PII processing
NDPA 2023
Data Protection Impact Assessment
DPIA filed with NDPC before launch
NDPA 2023
Data subject rights
DSAR, deletion, correction, and human review workflows built into platform
NDPA 2023
Data processor agreements
Signed DPA required from all lender clients before API key issuance
CBN Open Banking Framework
Licensed API provider
All bank data pulled via CBN-recognized API providers (Mono, Okra, OnePipe)
CBN Consumer Protection Framework
Decision explainability
Human-readable explanation generated for every automated score
CBN Consumer Protection Framework
Data sharing agreements
Signed agreements with all partner banks and telcos before data ingestion


7. Technology Stack

7.1 Primary Programming Languages
Language
Version
Used For
Rationale
Python
3.11+
ML pipeline, data ingestion, feature engineering, model training and inference
Dominant language for ML/data work. Rich ecosystem: scikit-learn, XGBoost, LightGBM, pandas, FastAPI.
TypeScript
5.x
API layer, admin dashboard backend, webhook service, SDK
Type safety at scale. Excellent for building reliable, maintainable REST APIs with Node.js/Express or NestJS.
SQL (PostgreSQL dialect)
PostgreSQL 16
Relational data: client accounts, consent records, audit log, API keys
ACID compliance critical for consent and audit data. JSONB support for flexible schema fields.
Go
1.22+
High-throughput data ingestion workers, real-time event processing
Low-latency, high-concurrency for pipeline workers. Optional — Python async can substitute in v1.


7.2 Frameworks & Libraries
Layer
Technology
Purpose
API Framework
FastAPI (Python)
Scoring API — async, auto-generates OpenAPI spec, excellent performance
API Framework
NestJS (TypeScript)
Admin API and webhook service — structured, testable, decorator-based
ML — Gradient Boosting
XGBoost + LightGBM
Base Credit Model and Alternative Booster. LightGBM faster for large datasets.
ML — Feature Engineering
Feast (Feature Store)
Open-source feature store. Supports online (low-latency) and offline (batch training) retrieval.
ML — Model Tracking
MLflow
Experiment tracking, model versioning, A/B deployment registry
ML — Drift Detection
Evidently AI
PSI monitoring, data drift reports, model performance dashboards
Data Pipeline
Apache Airflow
DAG-based scheduling for ingestion pipelines and retraining jobs
Data Processing
pandas + polars
pandas for exploratory work; polars for high-performance production transforms
Frontend — Dashboard
Next.js 14 + Tailwind CSS
Admin dashboard and developer portal. React Server Components for performance.
Authentication
Auth0 or Clerk
Client authentication for dashboard. HMAC signing for API keys.
API Documentation
Swagger UI (via FastAPI)
Auto-generated, interactive API docs served at /docs
Testing
pytest (Python) + Jest (TypeScript)
Unit and integration tests. Coverage target: > 80%


7.3 Infrastructure & Cloud
Component
Technology
Notes
Cloud Provider
AWS (primary)
Nigeria region (af-south-1 via Cape Town; Lagos-specific when available). Data residency compliance.
Container Orchestration
AWS EKS (Kubernetes)
Stateless API pods auto-scale. ML inference as separate deployment.
API Gateway
AWS API Gateway + custom FastAPI
Rate limiting, key validation, and request logging at gateway layer
Message Queue
AWS SQS + Redis (ElastiCache)
SQS for async pipeline jobs. Redis for real-time score caching and rate limiting.
Primary Database
AWS RDS PostgreSQL (Multi-AZ)
Consent records, audit log, client accounts. Read replicas for dashboard.
Feature Store (Online)
Redis / DynamoDB
Low-latency feature retrieval at score time (< 10ms target)
Feature Store (Offline)
AWS S3 + Parquet
Training datasets. Partitioned by date and BVN prefix.
ML Model Serving
AWS SageMaker or self-hosted TorchServe
Model inference endpoint. SageMaker simplifies A/B deployment.
Monitoring & Alerting
Datadog + PagerDuty
Infrastructure metrics, API latency, pipeline health, and on-call alerting
Logging
AWS CloudWatch + OpenSearch
Centralized structured logs. Retention: 90 days hot, 7 years cold (compliance).
Secrets Management
AWS Secrets Manager
API keys, database credentials, third-party API tokens — never in code or env files
CI/CD
GitHub Actions + ArgoCD
GitHub Actions for build/test. ArgoCD for GitOps-based Kubernetes deployment.


7.4 Data Source Integration Stack
Data Source
Integration Method
Auth
SLA
CRC Credit Bureau
REST API
API Key + IP Whitelist
< 1s
FirstCentral Bureau
REST API
API Key
< 1.5s
Mono (Open Banking)
REST API + Webhooks
OAuth 2.0
< 2s
Okra (Open Banking)
REST API
OAuth 2.0
< 2s
OnePipe (Open Banking)
REST API
OAuth 2.0
< 2s
MTN Telco Data
SFTP batch + REST API
Signed data sharing agreement + API key
Batch: 6 hours
Airtel Telco Data
SFTP batch
Signed DSA
Batch: 6 hours
OPay Mobile Money
REST API
API Key + DSA
< 2s
PalmPay Mobile Money
REST API
API Key + DSA
< 2s


8. Core API Specifications

8.1 Score Request
POST /v1/score
Request body (JSON):
{
  "bvn": "22412345678",
  "phone": "+2348012345678",
  "lender_id": "lnd_abc123",
  "tier_config": ["formal", "alternative", "psychographic"],
  "loan_amount_ngn": 150000,
  "loan_tenure_days": 90
}

Response (200 OK):
{
  "score": 712,
  "confidence_interval": { "lower": 688, "upper": 736, "level": "95%" },
  "confidence_band": "HIGH",
  "data_coverage_pct": 84,
  "positive_factors": ["Consistent mobile money inflows for 14 months", ...],
  "negative_factors": ["Missed utility payment in October 2025", ...],
  "consent_token_ref": "cst_xyz789",
  "model_version": "v2.3.1",
  "computed_at": "2026-04-09T14:32:00Z",
  "trace_id": "trc_k9mn23"
}


8.2 Outcome Submission
POST /v1/outcomes
Request body (JSON):
{
  "loan_id": "ln_1234567",
  "bvn": "22412345678",
  "disbursement_date": "2026-01-15",
  "due_date": "2026-04-15",
  "loan_amount_ngn": 150000,
  "outcome": "REPAID_ON_TIME",
  "outcome_date": "2026-04-10",
  "score_at_origination": 712
}

Accepted outcome values: REPAID_ON_TIME | REPAID_LATE | DEFAULTED | RESTRUCTURED | WRITTEN_OFF


8.3 Error Response Format
Standard Error Response
{
  "error": {
    "code": "INSUFFICIENT_CONSENT",
    "message": "Borrower has not consented to telco data sharing. Score produced from available tiers only.",
    "trace_id": "trc_k9mn24",
    "docs_url": "https://docs.platform.com/errors/INSUFFICIENT_CONSENT"
  }
}

HTTP Status codes: 200 (success), 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 422 (validation error), 429 (rate limited), 500 (server error)


9. Core Data Model
Primary entities and their key fields. Full schema defined in the database migration files.

Entity
Key Fields
Storage
Notes
borrower_profile
bvn (PK, tokenized), phone_hash, created_at, data_coverage_pct
PostgreSQL
BVN stored as salted hash. Raw BVN only in encrypted vault.
consent_record
id, borrower_bvn_hash, data_category, purpose, authorized_lenders[], expiry_at, revoked_at, token_signature
PostgreSQL (append-only)
Immutable after insert. Revocation creates a new record, does not delete.
consent_audit_log
id, consent_id, event_type, timestamp, ip_address, user_agent, actor_id
PostgreSQL (append-only)
Tamper-evident: each row stores a hash of the previous row.
feature_snapshot
id, borrower_bvn_hash, feature_name, feature_value, source_tier, computed_at, data_snapshot_at
PostgreSQL + Redis (online)
Redis holds latest snapshot per borrower for low-latency retrieval.
credit_score
id, borrower_bvn_hash, score, confidence_lower, confidence_upper, confidence_band, data_coverage_pct, model_version, computed_at
PostgreSQL
Immutable. New score = new row. History preserved.
loan_outcome
id, loan_id, borrower_bvn_hash, lender_id, outcome, outcome_date, score_at_origination
PostgreSQL
Source of ground truth for model retraining.
lender_client
id, name, api_key_hash, tier_access[], rate_limit, dpa_signed_at, status
PostgreSQL
API keys stored as bcrypt hash. Raw key shown once at creation.
data_pipeline_run
id, source_name, status, started_at, completed_at, records_ingested, error_count, error_log
PostgreSQL
Ops monitoring. Retained for 90 days.


10. Success Metrics & KPIs

10.1 Product Health
Metric
Definition
Target
Frequency
API p95 latency
95th percentile response time for POST /v1/score
< 3 seconds
Real-time dashboard
Score coverage rate
% of score requests that return a score (vs. insufficient data error)
> 75%
Daily
Model Gini coefficient
Discriminatory power of composite model
> 0.45
Monthly
PSI (Population Stability Index)
Stability of score distribution over time
< 0.10 (stable)
Monthly
Data pipeline uptime
% of time all ingestion pipelines are running without error
> 99%
Daily
Consent completion rate
% of consent flows completed (started / completed)
> 65%
Weekly


10.2 Business Metrics
Metric
Target — Month 6
Target — Month 12
Active lender integrations
8
25
Monthly API calls
50,000
300,000
Repayment outcomes ingested
50,000
500,000
Monthly Recurring Revenue (MRR)
₦4M
₦15M
Net Revenue Retention
> 100%
> 110%
Time-to-first-score (new lender)
< 5 business days
< 2 business days


11. Phased Roadmap

Phase
Timeline
Deliverables
Exit Criteria
Phase 0 — Foundation
Months 1–2
Core data model, consent module, BVN + bureau integration, sandbox environment, 3 pilot lenders onboarded
3 lenders actively calling scoring API in sandbox. DPIA draft filed.
Phase 1 — MVP Launch
Months 3–4
Base Credit Model trained on partner loan books, composite score API in production, admin dashboard v1, developer portal + docs
5 lenders live in production. > 1,000 scores/day. < 3s p95 latency.
Phase 2 — Alternative Data
Months 5–7
Telco data integration (MTN, Airtel), mobile money integration (OPay, PalmPay), Alternative Booster model, webhook support
Score coverage rate improves to > 75%. PSI stable.
Phase 3 — Intelligence Layer
Months 8–10
Psychometric engine, score history API, portfolio monitoring webhooks, model A/B testing, Python + JS SDKs
Gini coefficient > 0.45. 15 active lenders.
Phase 4 — Insurance & Scale
Months 11–14
Insurer risk segmentation API, batch scoring, DSAR automation, CBN open banking deeper integrations, 25 lender target
First insurer client live. MRR ₦15M target. SOC 2 audit initiated.
Phase 5 — Bureau Licensing
Months 18–24
Explore CBN credit bureau licensing. Proprietary score becomes licensed product. Consumer-facing credit health portal.
NDPC and CBN licensing conversations initiated. Proprietary dataset > 2M outcome records.


12. Risks & Mitigations

Risk
Probability
Impact
Mitigation
Telco or mobile money partners decline data sharing agreement
Medium
High
Begin with bureau + open banking only (Phase 0/1). Alternative data as an enhancement, not a dependency. Negotiate DSAs in parallel with build.
NDPA enforcement creates blockers on data usage
Low–Medium
High
File DPIA proactively. Engage NDPC early. Build consent architecture to spec before any data collection begins. Retain a data protection lawyer.
Model performance is poor on thin-file population without sufficient training data
Medium
High
Partner with 3–5 lenders who contribute historical loan books for initial model training. Use transfer learning from Kenyan/Ghanaian model priors where available.
Lenders slow to integrate due to technical complexity
Medium
Medium
Invest heavily in DX: sandbox, SDKs, interactive docs, and a dedicated integration support SLA. Target fintechs (not banks) first — faster dev teams.
Competitor (e.g., Lendsqr, Indicina) launches similar product
Medium
Medium
Speed to data moat is the defense. Every month of outcome data ingested widens the gap. Focus on locking in lenders with long-term contracts + outcome data contribution clauses.
Data breach of PII (BVN, financial data)
Low
Critical
PII tokenization in pipeline. AES-256 at rest. TLS 1.3 in transit. Penetration testing pre-launch. Incident response plan + mandatory 72-hour breach notification to NDPC.


13. Open Questions

What is the minimum viable training dataset size before the Base Credit Model is reliable enough for production? (Recommendation: engage a PhD-level credit risk modeller to define the threshold before committing to a launch date.)
Will CBN's Open Banking framework be sufficiently mature in Nigeria to support real-time bank data pulls by our Phase 1 launch date, or should we rely on statement upload as a fallback?
Should the platform support white-labeling — i.e., can a lender serve the scoring engine under their own brand to their own borrowers? (Revenue implication: higher pricing tier.)
What is the pricing model for outcome data contribution — is it a discount on API pricing, or a required condition of API access? The answer significantly affects how quickly the data moat builds.
At what dataset scale does it make commercial and regulatory sense to pursue CBN credit bureau licensing, and what does that process look like in terms of capital and timeline?

Appendix A — Glossary
Term
Definition
BVN
Bank Verification Number — a unique 11-digit identifier issued by CBN, linked to a Nigerian individual's banking identity
Gini Coefficient
A measure of a credit model's discriminatory power. Range 0–1; higher is better. Industry benchmark for bureau models: ~0.45–0.60.
PSI
Population Stability Index — measures whether the distribution of a feature or score has shifted over time. PSI < 0.10 = stable; > 0.20 = significant shift requiring investigation.
NDPA
Nigeria Data Protection Act 2023 — Nigeria's primary data privacy legislation, enforced by the Nigeria Data Protection Commission (NDPC).
DPIA
Data Protection Impact Assessment — a structured document required under NDPA for high-risk processing activities (including automated credit scoring).
DSA
Data Sharing Agreement — a contractual agreement governing how personal data is shared between two organizations.
DPA
Data Processing Agreement — a contract between a data controller (lender) and data processor (this platform) defining responsibilities under NDPA.
Thin-file
A person with insufficient formal credit history for a traditional credit bureau to generate a reliable score.
Confidence interval
The range within which the true credit score would fall with a given probability (e.g., 95%). Wider interval = less data = more uncertainty.
Feature store
A centralized repository for computed ML features, enabling consistent feature values between model training and real-time inference.
Open Banking
A regulatory framework enabling third parties to access financial data from banks with customer consent, via APIs. Governed in Nigeria by CBN's Open Banking Regulatory Framework (2023).


