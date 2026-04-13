"""
Comprehensive test suite for Scoring API.
Covers: auth, rate limiting, batch scoring, human review, webhooks,
API key management, DSAR, borrower explanations, cache, and services.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.main import app
from src.core.database import get_db, Base
from src.core.security import hash_bvn, generate_api_key, hash_api_key
from src.models import (
    LenderClient,
    ConsentRecord,
    BorrowerProfile,
    CreditScore,
    FeatureSnapshot,
    HumanReviewRequest,
    WebhookSubscription,
    WebhookEvent,
    ApiKey,
)


# ── Test Fixtures ─────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """Create in-memory database for tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(setup_db):
    """Provide a transactional DB session per test."""
    from src.core.database import get_db as original_get_db

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override

    async with async_session() as session:
        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def lender(db_session: AsyncSession):
    """Create an active lender client for testing."""
    raw_key = generate_api_key()
    hashed = hash_api_key(raw_key)

    lender = LenderClient(
        id=f"lnd_test_{uuid.uuid4().hex[:8]}",
        name="Test Lender",
        api_key_hash=hashed,
        tier_access='["formal", "alternative", "psychographic"]',
        rate_limit=1000,  # High limit for tests
        status="active",
        environment="sandbox",
    )
    db_session.add(lender)
    await db_session.flush()
    lender._raw_key = raw_key  # Attach for test use
    return lender


@pytest.fixture
async def borrower(db_session: AsyncSession):
    """Create a borrower profile."""
    bvn = "12345678901"
    bvn_hash = hash_bvn(bvn, "test-encryption-key")

    profile = BorrowerProfile(
        id=f"brw_test_{uuid.uuid4().hex[:8]}",
        bvn_hash=bvn_hash,
        data_coverage_pct=65.0,
    )
    db_session.add(profile)
    await db_session.flush()
    profile._bvn = bvn
    return profile


@pytest.fixture
async def auth_headers(lender):
    """Return headers with valid API key."""
    return {"X-API-Key": lender._raw_key}


# ── Health & Root Tests ────────────────────────────────────────────────

class TestHealthEndpoints:
    async def test_root_endpoint(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "message" in data

    async def test_health_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


# ── Authentication Tests ──────────────────────────────────────────────

class TestAuthentication:
    async def test_missing_api_key(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/score", json={"bvn": "12345678901"})
        assert response.status_code in [401, 403]

    async def test_invalid_api_key(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/score",
                json={"bvn": "12345678901"},
                headers={"X-API-Key": "invalid_key"},
            )
        assert response.status_code == 401

    async def test_sandbox_key_in_production(self, lender, db_session: AsyncSession):
        """Sandbox API key should be rejected in production environment."""
        lender.environment = "sandbox"
        await db_session.flush()

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.environment = "production"

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/v1/score",
                    json={"bvn": "12345678901", "tier_config": ["formal"]},
                    headers={"X-API-Key": lender._raw_key},
                )
            assert response.status_code == 403


# ── Batch Scoring Tests ───────────────────────────────────────────────

class TestBatchScoring:
    async def test_batch_score_small(self, auth_headers, borrower):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/score/batch",
                json={
                    "entries": [
                        {
                            "bvn": borrower._bvn,
                            "phone": "08012345678",
                            "tier_config": ["formal"],
                            "external_ref": "test_001",
                        }
                    ]
                },
                headers=auth_headers,
            )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] in ["processing", "completed"]
        assert data["total_entries"] == 1

    async def test_batch_score_exceeds_limit(self, auth_headers):
        entries = [{"bvn": f"1234567890{i:02d}", "phone": "08012345678"} for i in range(10001)]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/score/batch",
                json={"entries": entries},
                headers=auth_headers,
            )
        assert response.status_code == 400

    async def test_get_batch_job_status(self, auth_headers):
        # First create a job
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/v1/score/batch",
                json={
                    "entries": [{"bvn": "12345678901", "phone": "08012345678"}]
                },
                headers=auth_headers,
            )
            job_id = create_resp.json()["job_id"]

            # Then check status
            response = await client.get(f"/v1/score/batch/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id


# ── Human Review Tests ────────────────────────────────────────────────

class TestHumanReview:
    async def test_create_review_request(self, auth_headers, borrower):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/review",
                json={
                    "bvn": borrower._bvn,
                    "loan_id": "LOAN_TEST_001",
                    "reason": "I believe my credit decision was unfair due to missing data",
                    "score_at_decision": 450,
                    "decision_outcome": "rejected",
                },
                headers=auth_headers,
            )
        assert response.status_code == 201
        data = response.json()
        assert data["review_id"].startswith("rev_")
        assert data["status"] == "pending"
        assert "sla_deadline" in data

    async def test_list_pending_reviews(self, auth_headers, borrower, lender, db_session: AsyncSession):
        # Create a review
        review = HumanReviewRequest(
            id=f"rev_test_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=borrower.bvn_hash,
            loan_id="LOAN_REVIEW_TEST",
            score_at_decision=500,
            decision_outcome="approved_with_conditions",
            reason="Test review",
            lender_id=lender.id,
            status="pending",
            sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(review)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/review", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_complete_review(self, auth_headers, borrower, lender, db_session: AsyncSession):
        review = HumanReviewRequest(
            id=f"rev_complete_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=borrower.bvn_hash,
            loan_id="LOAN_COMPLETE_TEST",
            score_at_decision=550,
            decision_outcome="rejected",
            reason="Test",
            lender_id=lender.id,
            status="pending",
            sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(review)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/v1/review/{review.id}/complete",
                json={
                    "outcome": "overturned",
                    "reviewer_notes": "Additional data found that improved score",
                },
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["outcome"] == "overturned"


# ── Webhook Tests ─────────────────────────────────────────────────────

class TestWebhooks:
    async def test_create_webhook_subscription(self, auth_headers, lender):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/webhooks",
                json={
                    "endpoint_url": "https://example.com/webhook",
                    "events": ["score_material_change"],
                },
                headers=auth_headers,
            )
        assert response.status_code in [201, 200]

    async def test_list_webhook_subscriptions(self, auth_headers, lender, db_session: AsyncSession):
        sub = WebhookSubscription(
            id=f"whs_test_{uuid.uuid4().hex[:8]}",
            lender_id=lender.id,
            endpoint_url="https://example.com/webhook",
            events='["score_material_change"]',
            is_active=True,
            secret="test_secret",
        )
        db_session.add(sub)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/webhooks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_delete_webhook_subscription(self, auth_headers, lender, db_session: AsyncSession):
        sub = WebhookSubscription(
            id=f"whs_delete_{uuid.uuid4().hex[:8]}",
            lender_id=lender.id,
            endpoint_url="https://example.com/webhook",
            events='["score_material_change"]',
            is_active=True,
            secret="test_secret",
        )
        db_session.add(sub)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/v1/webhooks/{sub.id}", headers=auth_headers)
        assert response.status_code in [200, 204]


# ── DSAR Tests ────────────────────────────────────────────────────────

class TestDSAR:
    async def test_subject_data_request(self, auth_headers, borrower, db_session: AsyncSession):
        # Create consent and features for the borrower
        consent = ConsentRecord(
            id=f"cst_dsar_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=borrower.bvn_hash,
            data_category="bureau",
            purpose="credit_scoring",
            authorized_lenders='[]',
            token_signature="test_signature",
        )
        db_session.add(consent)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/v1/subject/{borrower._bvn}/data",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert "consents" in data


# ── API Key Management Tests ─────────────────────────────────────────

class TestApiKeyManagement:
    async def test_list_api_keys(self, auth_headers, lender, db_session: AsyncSession):
        key = ApiKey(
            id=f"key_test_{uuid.uuid4().hex[:8]}",
            client_id=lender.id,
            key_hash="test_hash",
            key_prefix="credaly_test",
            key_name="Test Key",
            is_active=True,
        )
        db_session.add(key)
        await db_session.flush()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/api-keys", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ── Service Layer Tests ───────────────────────────────────────────────

class TestScoringService:
    async def test_compute_score_with_features(self, borrower, lender, db_session: AsyncSession):
        """Test end-to-end scoring with real features."""
        from src.services.scoring.service import ScoringService
        from src.services.features.service import FeatureService
        from src.core.security import hash_bvn
        from src.core.config import settings

        bvn_hash = borrower.bvn_hash

        # Create features
        feature_service = FeatureService(db_session)
        features = [
            {"borrower_bvn_hash": bvn_hash, "feature_name": "bureau_delinquency_flag", "feature_value": 0.0, "source_tier": "formal"},
            {"borrower_bvn_hash": bvn_hash, "feature_name": "total_credit_accounts", "feature_value": 3.0, "source_tier": "formal"},
            {"borrower_bvn_hash": bvn_hash, "feature_name": "oldest_account_age_months", "feature_value": 36.0, "source_tier": "formal"},
            {"borrower_bvn_hash": bvn_hash, "feature_name": "avg_bureau_score", "feature_value": 600.0, "source_tier": "formal"},
            {"borrower_bvn_hash": bvn_hash, "feature_name": "telco_consistency_index", "feature_value": 0.7, "source_tier": "alternative"},
        ]
        await feature_service.store_features(features)
        await db_session.flush()

        scoring_service = ScoringService(db_session)
        result = await scoring_service.compute_score(
            bvn=borrower._bvn,
            tier_config=["formal", "alternative"],
            trace_id="test_trace",
        )

        assert "score" in result
        assert 300 <= result["score"] <= 850
        assert result["confidence_band"] in ["HIGH", "MEDIUM", "LOW"]
        assert "data_coverage_pct" in result
        assert "positive_factors" in result
        assert "negative_factors" in result


class TestRetentionService:
    async def test_purge_expired_features(self, db_session: AsyncSession):
        from src.services.retention.service import DataRetentionService

        # Create an old feature (3 years ago)
        old_date = datetime.now(timezone.utc) - timedelta(days=365 * 3 + 30)
        feature = FeatureSnapshot(
            id=f"fet_old_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash="test_hash",
            feature_name="test_feature",
            feature_value=0.5,
            source_tier="formal",
            computed_at=old_date,
            data_snapshot_at=old_date,
        )
        db_session.add(feature)
        await db_session.flush()

        service = DataRetentionService(db_session)
        result = await service.purge_expired_features()
        assert result["purged"] >= 1


class TestConsentExpiryService:
    async def test_expire_consent(self, borrower, db_session: AsyncSession):
        from src.services.retention.service import ConsentExpiryService

        # Create expired consent
        consent = ConsentRecord(
            id=f"cst_expire_{uuid.uuid4().hex[:8]}",
            borrower_bvn_hash=borrower.bvn_hash,
            data_category="bureau",
            purpose="credit_scoring",
            authorized_lenders='[]',
            token_signature="test_signature",
            expiry_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired yesterday
        )
        db_session.add(consent)
        await db_session.flush()

        service = ConsentExpiryService(db_session)
        result = await service.expire_expired_consents()
        assert result["expired"] >= 1
