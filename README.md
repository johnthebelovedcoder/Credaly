# Credaly — Predictive Behavioral Credit & Insurance Platform

AI-powered alternative data credit scoring infrastructure for African lenders.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Services                                 │
│  ┌──────────────────┐       ┌──────────────────────────┐    │
│  │  scoring-api     │       │  admin-api (NestJS)      │    │
│  │  (Python FastAPI)│       │  (TypeScript)             │    │
│  │  :8000           │       │  :3001                   │    │
│  └────────┬─────────┘       └──────────┬───────────────┘    │
│           │                             │                    │
│  ┌────────┴─────────┐       ┌──────────┴───────────────┐    │
│  │  ML Pipeline     │       │  Webhook Service          │    │
│  │  (Async workers) │       │  (TypeScript)             │    │
│  └────────┬─────────┘       └──────────────────────────┘    │
│           │                                                  │
│  ┌────────┴─────────┐                                       │
│  │  Data Ingestion  │                                       │
│  │  (Airflow DAGs)  │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │  PostgreSQL (SQLite)  │
              │  - Consent records    │
              │  - Audit logs         │
              │  - Feature snapshots  │
              │  - Credit scores      │
              │  - Lender clients     │
              └───────────────────────┘
```

## Project Structure

```
credaly/
├── services/
│   ├── scoring-api/          # Python FastAPI — scoring, consent, outcomes
│   │   ├── src/
│   │   │   ├── api/          # REST endpoints
│   │   │   ├── core/         # Config, security, middleware
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   ├── schemas/      # Pydantic request/response schemas
│   │   │   ├── services/     # Business logic
│   │   │   │   ├── consent/
│   │   │   │   ├── ingestion/
│   │   │   │   ├── features/
│   │   │   │   ├── scoring/
│   │   │   │   └── outcomes/
│   │   │   └── main.py
│   │   ├── alembic/          # Database migrations
│   │   ├── tests/
│   │   └── requirements.txt
│   └── admin-api/            # TypeScript NestJS — admin dashboard backend
│       ├── src/
│       ├── test/
│       └── package.json
├── ml-pipeline/              # ML model training, feature engineering
├── docker-compose.yml
└── package.json
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional)

### Local Development (SQLite)

```bash
# Install dependencies
npm install
cd services/scoring-api
pip install -r requirements.txt

# Run migrations
cd services/scoring-api
alembic upgrade head

# Start both services
cd ../..
npm run dev
```

Scoring API: http://localhost:8000
Admin API: http://localhost:3001
API Docs: http://localhost:8000/docs

### Running Tests

```bash
# Python
cd services/scoring-api
pytest

# TypeScript
npm run test:admin
```

## Phase Roadmap

| Phase | Status |
|-------|--------|
| Phase 0 — Foundation | ✅ In Progress |
| Phase 1 — MVP Launch | 🔄 |
| Phase 2 — Alternative Data | |
| Phase 3 — Intelligence Layer | |
| Phase 4 — Insurance & Scale | |
| Phase 5 — Bureau Licensing | |
