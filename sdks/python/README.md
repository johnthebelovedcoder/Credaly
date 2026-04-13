# Credaly Python SDK

Official Python client for the [Credaly Predictive Behavioral Credit API](https://credaly.com).

## Installation

```bash
pip install credaly
```

## Quick Start

```python
from credaly import CredalyClient

# Initialize the client (sandbox or production key)
client = CredalyClient(api_key="credaly_your_api_key_here")

# 1. Grant consent before scoring (required by NDPA 2023)
consent = client.grant_consent(
    bvn="22412345678",
    phone="+2348012345678",
    data_category="bureau",
    purpose="credit scoring for loan application",
)
print(f"Consent ID: {consent.consent_id}")

# 2. Score a borrower
result = client.score(
    bvn="22412345678",
    phone="+2348012345678",
    tier_config=["formal", "alternative"],  # optional
)
print(f"Score: {result.score}")
print(f"Confidence: {result.confidence_band}")
print(f"Data coverage: {result.data_coverage_pct}%")
print(f"Positive factors: {result.positive_factors}")
print(f"Negative factors: {result.negative_factors}")

# 3. View score history
history = client.get_score_history(bvn="22412345678")
for entry in history.scores:
    print(f"  {entry.computed_at}: {entry.score} ({entry.confidence_band})")

# 4. Submit repayment outcome (contributes to model training)
outcome = client.submit_outcome(
    loan_id="ln_123456",
    bvn="22412345678",
    disbursement_date="2026-01-15T00:00:00Z",
    due_date="2026-04-15T00:00:00Z",
    loan_amount_ngn=150000,
    outcome="REPAID_ON_TIME",
    outcome_date="2026-04-10T00:00:00Z",
    score_at_origination=712,
)
```

## API Reference

### `CredalyClient(api_key, base_url, timeout, max_retries)`

| Parameter | Default | Description |
|---|---|---|
| `api_key` | (required) | Your Credaly API key |
| `base_url` | `https://api.credaly.com` | API base URL |
| `timeout` | `30.0` | Request timeout in seconds |
| `max_retries` | `3` | Retries on transient errors |

### Methods

#### `client.score(bvn, phone, tier_config, loan_amount_ngn, loan_tenure_days) → ScoreResult`
Compute a credit score. Response in < 3s p95.

#### `client.get_score_history(bvn) → ScoreHistoryResult`
Get up to 12 monthly score entries.

#### `client.grant_consent(bvn, phone, data_category, purpose, authorized_lenders, expiry_date) → ConsentResult`
Grant granular consent for a data category.

#### `client.check_consent_status(bvn) → ConsentStatusResult`
Check consent status across all categories.

#### `client.withdraw_consent(consent_id, reason) → ConsentWithdrawResult`
Withdraw consent. Triggers cascade invalidation.

#### `client.submit_outcome(...) → OutcomeResult`
Submit loan repayment outcome.

#### `client.get_subject_data(bvn) → SubjectDataResult`
Retrieve all data about a borrower (DSAR).

#### `client.health() → dict`
Check API health.

## Error Handling

```python
from credaly import (
    CredalyError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ConsentError,
    ServerError,
)

try:
    result = client.score(bvn="...", phone="...")
except AuthenticationError as e:
    print(f"Invalid API key: {e}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ConsentError as e:
    print(f"Consent issue: {e}")
except ValidationError as e:
    print(f"Bad request: {e}")
except ServerError as e:
    print(f"Server error, trace: {e.trace_id}")
```

## Configuration

Use the sandbox environment for testing:

```python
client = CredalyClient(
    api_key="credaly_sandbox_...",
    base_url="https://sandbox-api.credaly.com",
)
```

## License

MIT
