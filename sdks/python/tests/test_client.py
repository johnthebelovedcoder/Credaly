"""Python SDK — unit tests using httpx.MockTransport."""

import pytest
import httpx

from credaly import CredalyClient
from credaly.exceptions import (
    AuthenticationError,
    ValidationError,
    RateLimitError,
    ConsentError,
)

API_KEY = "credaly_test_key_12345"
BASE_URL = "https://api.credaly.com"


def _mock_client(responses: list[tuple[int, dict]]) -> CredalyClient:
    """Helper: create a CredalyClient with a mocked httpx transport."""
    idx = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal idx
        status, body = responses[idx]
        idx += 1
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    c = CredalyClient.__new__(CredalyClient)
    c._api_key = API_KEY
    c._base_url = BASE_URL
    c._timeout = 30.0
    c._max_retries = 1  # No retries in tests
    c._client = httpx.Client(
        transport=transport,
        base_url=BASE_URL,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "credaly-python-sdk/1.0.0",
        },
        timeout=30.0,
    )
    return c


# ── Score ────────────────────────────────────────────────────────────────

class TestScore:
    def test_success(self):
        c = _mock_client([(200, {
            "score": 712,
            "confidence_interval": {"lower": 688, "upper": 736, "level": "95%"},
            "confidence_band": "HIGH",
            "data_coverage_pct": 84.0,
            "positive_factors": ["Consistent mobile money inflows"],
            "negative_factors": ["Limited alternative data"],
            "consent_token_ref": "cst_xyz789",
            "model_version": "v2.3.1",
            "computed_at": "2026-04-09T14:32:00Z",
            "trace_id": "trc_k9mn23",
        })])

        r = c.score(bvn="22412345678", phone="+2348012345678")
        assert r.score == 712
        assert r.confidence_band == "HIGH"
        assert r.data_coverage_pct == 84.0
        assert r.confidence_interval.lower == 688
        assert r.trace_id == "trc_k9mn23"

    def test_validation_error(self):
        c = _mock_client([(422, {
            "error": {"code": "VALIDATION_ERROR", "message": "Bad request", "trace_id": "trc_01"},
        })])
        with pytest.raises(ValidationError) as exc:
            c.score(bvn="22412345678", phone="+2348012345678")
        assert exc.value.code == "VALIDATION_ERROR"

    def test_auth_error(self):
        c = _mock_client([(401, {
            "error": {"code": "INVALID_API_KEY", "message": "Bad key", "trace_id": "trc_02"},
        })])
        with pytest.raises(AuthenticationError):
            c.score(bvn="22412345678", phone="+2348012345678")

    def test_rate_limit_error(self):
        c = _mock_client([(429, {
            "error": {"code": "RATE_LIMITED", "message": "Too many", "trace_id": "trc_03"},
        })])
        with pytest.raises(RateLimitError):
            c.score(bvn="22412345678", phone="+2348012345678")

    def test_invalid_tier(self):
        c = _mock_client([(200, {})])
        with pytest.raises(ValueError, match="invalid_tier"):
            c.score(bvn="22412345678", phone="+2348012345678", tier_config=["invalid_tier"])


# ── Consent ──────────────────────────────────────────────────────────────

class TestConsent:
    def test_grant_success(self):
        c = _mock_client([(200, {
            "consent_id": "cst_abc123",
            "borrower_bvn_hash": "hash123",
            "data_category": "bureau",
            "purpose": "credit scoring",
            "authorized_lenders": ["lnd_test"],
            "expiry_at": None,
            "is_active": True,
            "token_signature": "sig_xyz",
            "created_at": "2026-04-09T14:32:00Z",
        })])

        r = c.grant_consent(
            bvn="22412345678", phone="+2348012345678",
            data_category="bureau", purpose="credit scoring",
            authorized_lenders=["lnd_test"],
        )
        assert r.consent_id == "cst_abc123"
        assert r.is_active is True

    def test_duplicate_error(self):
        c = _mock_client([(409, {
            "error": {"code": "CONSENT_EXISTS", "message": "Already exists", "trace_id": "trc_04"},
        })])
        with pytest.raises(ConsentError):
            c.grant_consent(
                bvn="22412345678", phone="+2348012345678",
                data_category="bureau", purpose="test",
            )

    def test_invalid_category(self):
        c = _mock_client([(200, {})])
        with pytest.raises(ValueError, match="invalid_category"):
            c.grant_consent(
                bvn="22412345678", phone="+2348012345678",
                data_category="invalid_category", purpose="test",
            )


# ── Outcome ──────────────────────────────────────────────────────────────

class TestOutcome:
    def test_submit_success(self):
        c = _mock_client([(200, {
            "loan_id": "ln_test_001",
            "status": "received",
            "message": "Outcome recorded successfully",
        })])
        r = c.submit_outcome(
            loan_id="ln_test_001", bvn="22412345678",
            disbursement_date="2026-01-15T00:00:00Z",
            due_date="2026-04-15T00:00:00Z",
            loan_amount_ngn=150000,
            outcome="REPAID_ON_TIME",
            outcome_date="2026-04-10T00:00:00Z",
            score_at_origination=712,
        )
        assert r.loan_id == "ln_test_001"
        assert r.status == "received"

    def test_invalid_outcome_value(self):
        c = _mock_client([(200, {})])
        with pytest.raises(ValueError, match="INVALID_OUTCOME"):
            c.submit_outcome(
                loan_id="ln_test_001", bvn="22412345678",
                disbursement_date="2026-01-15T00:00:00Z",
                due_date="2026-04-15T00:00:00Z",
                loan_amount_ngn=150000,
                outcome="INVALID_OUTCOME",
                outcome_date="2026-04-10T00:00:00Z",
                score_at_origination=712,
            )


# ── Client Init ──────────────────────────────────────────────────────────

class TestClientInit:
    def test_invalid_api_key(self):
        with pytest.raises(ValueError, match="credaly_"):
            CredalyClient(api_key="invalid_key")

    def test_empty_api_key(self):
        with pytest.raises(ValueError):
            CredalyClient(api_key="")

    def test_custom_base_url(self):
        c = CredalyClient(api_key=API_KEY, base_url="https://sandbox.credaly.com")
        assert c._base_url == "https://sandbox.credaly.com"

    def test_context_manager(self):
        with CredalyClient(api_key=API_KEY) as c:
            assert c._api_key == API_KEY
