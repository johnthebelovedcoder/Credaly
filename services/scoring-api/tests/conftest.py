"""
Shared test fixtures — database session, test client, sample data.
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.models.base import Base
from src.models import LenderClient

# Test database — in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test.

    IMPORTANT: We override the app's engine to point at the same in-memory DB
    so that the lifespan create_all and the test fixture share tables.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Patch the app's engine AND session factory to use the test engine
    from src.core import database as db_module
    original_engine = db_module.engine
    original_factory = db_module.async_session_factory

    db_module.engine = engine
    db_module.async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables (replaces the app's lifespan)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    # Restore original engine
    db_module.engine = original_engine
    db_module.async_session_factory = original_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client with overridden DB dependency."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Auth bypass for tests ──────────────────────────────────────────────

@pytest.fixture
def mock_lender(db_session: AsyncSession) -> LenderClient:
    """Create a mock lender client in the test DB and return it."""
    import bcrypt
    import hashlib
    raw_key = "credaly_test_key_12345"
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=4)).decode()

    lender = LenderClient(
        id="lnd_test123",
        name="Test Lender",
        api_key_hash=hashed,
        api_key_raw=raw_key,
        tier_access='["formal", "alternative", "psychographic"]',
        rate_limit=100,
        status="active",
        environment="sandbox",
    )
    db_session.add(lender)
    # Note: we don't flush — the test endpoint doesn't actually hit auth
    # because we override the dependency below.
    return lender


def _mock_auth():
    """Return a fake lender for auth dependency override."""
    import hashlib
    return LenderClient(
        id="lnd_test123",
        name="Test Lender",
        api_key_hash="mock_hash",
        tier_access='["formal", "alternative", "psychographic"]',
        rate_limit=100,
        status="active",
        environment="sandbox",
    )


@pytest_asyncio.fixture
async def auth_client(test_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Test client with authentication bypass via dependency override."""
    from src.core.auth import authenticate_lender
    app.dependency_overrides[authenticate_lender] = _mock_auth
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_bvn() -> str:
    """A valid test BVN (11 digits)."""
    return "22412345678"


@pytest.fixture
def sample_phone() -> str:
    """A valid test Nigerian phone number."""
    return "+2348012345678"


@pytest.fixture
def sample_lender_id() -> str:
    """A test lender ID."""
    return "lnd_test123"


@pytest.fixture
def sample_consent_request(sample_bvn: str, sample_phone: str) -> dict:
    """Sample consent grant request."""
    return {
        "bvn": sample_bvn,
        "phone": sample_phone,
        "data_category": "bureau",
        "purpose": "credit scoring for test lender",
        "authorized_lenders": ["lnd_test123"],
        "policy_version": "1.0",
    }


@pytest.fixture
def sample_score_request(sample_bvn: str, sample_phone: str, sample_lender_id: str) -> dict:
    """Sample score request body per PRD Section 8.1."""
    return {
        "bvn": sample_bvn,
        "phone": sample_phone,
        "lender_id": sample_lender_id,
        "tier_config": ["formal"],
        "loan_amount_ngn": 150000,
        "loan_tenure_days": 90,
    }


@pytest.fixture
def sample_outcome_request(sample_bvn: str) -> dict:
    """Sample outcome submission per PRD Section 8.2."""
    return {
        "loan_id": "ln_test_001",
        "bvn": sample_bvn,
        "disbursement_date": "2026-01-15T00:00:00Z",
        "due_date": "2026-04-15T00:00:00Z",
        "loan_amount_ngn": 150000,
        "outcome": "REPAID_ON_TIME",
        "outcome_date": "2026-04-10T00:00:00Z",
        "score_at_origination": 650,
    }
