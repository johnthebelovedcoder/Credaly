"""
Tests for the consent API endpoints.
"""

import pytest
from httpx import AsyncClient

from src.core.security import hash_bvn
from src.core.config import settings


class TestConsentAPI:
    """Test /v1/consent endpoints."""

    async def test_grant_consent(self, test_client: AsyncClient, sample_consent_request: dict):
        """POST /v1/consent should grant consent and return token."""
        response = await test_client.post("/v1/consent", json=sample_consent_request)
        assert response.status_code == 200
        data = response.json()
        assert "consent_id" in data
        assert data["data_category"] == "bureau"
        assert data["purpose"] == sample_consent_request["purpose"]
        assert data["is_active"] is True
        assert "token_signature" in data

    async def test_grant_consent_duplicate(
        self, test_client: AsyncClient, sample_consent_request: dict
    ):
        """POST /v1/consent with duplicate should return 409."""
        # First grant
        await test_client.post("/v1/consent", json=sample_consent_request)
        # Second attempt
        response = await test_client.post("/v1/consent", json=sample_consent_request)
        assert response.status_code == 409

    async def test_check_consent_status(self, test_client: AsyncClient, sample_consent_request: dict):
        """GET /v1/consent/{bvn}/status should return consent status."""
        # Grant consent first (uses same test_client, no auth needed)
        grant_resp = await test_client.post("/v1/consent", json=sample_consent_request)
        if grant_resp.status_code != 200:
            raise AssertionError(f"Consent grant failed: {grant_resp.json()}")

        # Check status
        bvn = sample_consent_request["bvn"]
        response = await test_client.get(f"/v1/consent/{bvn}/status")
        assert response.status_code == 200
        data = response.json()
        assert "consents" in data
        assert "minimum_consent_met" in data

    async def test_withdraw_consent(self, test_client: AsyncClient, sample_consent_request: dict):
        """DELETE /v1/consent/{consent_id} should withdraw consent."""
        # Grant consent first
        grant_response = await test_client.post("/v1/consent", json=sample_consent_request)
        if grant_response.status_code != 200:
            raise AssertionError(f"Consent grant failed: {grant_response.json()}")
        consent_id = grant_response.json()["consent_id"]

        # Withdraw
        response = await test_client.delete(f"/v1/consent/{consent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "withdrawn"

    async def test_withdraw_nonexistent_consent(self, test_client: AsyncClient):
        """DELETE /v1/consent/{invalid_id} should return 404."""
        response = await test_client.delete("/v1/consent/cst_nonexistent")
        assert response.status_code == 404
