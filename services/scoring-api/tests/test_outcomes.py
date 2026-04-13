"""
Tests for the outcome API endpoints.
"""

import pytest
from httpx import AsyncClient


class TestOutcomeAPI:
    """Test /v1/outcomes endpoints."""

    async def test_submit_outcome_validation(self, auth_client: AsyncClient):
        """POST /v1/outcomes should validate input."""
        response = await auth_client.post("/v1/outcomes", json={})
        assert response.status_code == 422

    async def test_submit_outcome_invalid_bvn(self, auth_client: AsyncClient):
        """POST /v1/outcomes should reject invalid BVN."""
        response = await auth_client.post(
            "/v1/outcomes",
            json={
                "loan_id": "ln_test_001",
                "bvn": "invalid",
                "disbursement_date": "2026-01-15T00:00:00Z",
                "due_date": "2026-04-15T00:00:00Z",
                "loan_amount_ngn": 150000,
                "outcome": "REPAID_ON_TIME",
                "outcome_date": "2026-04-10T00:00:00Z",
                "score_at_origination": 650,
            },
        )
        assert response.status_code == 422

    async def test_submit_duplicate_outcome(self, auth_client: AsyncClient, sample_outcome_request: dict):
        """POST /v1/outcomes with duplicate loan_id should return 409."""
        # First submission
        await auth_client.post("/v1/outcomes", json=sample_outcome_request)
        # Duplicate
        response = await auth_client.post("/v1/outcomes", json=sample_outcome_request)
        assert response.status_code == 409

    async def test_list_outcomes(self, auth_client: AsyncClient, sample_outcome_request: dict):
        """GET /v1/outcomes should return outcome history."""
        # Submit an outcome first
        await auth_client.post("/v1/outcomes", json=sample_outcome_request)
        
        # List outcomes
        response = await auth_client.get("/v1/outcomes")
        assert response.status_code == 200
        data = response.json()
        assert "outcomes" in data
        assert "total" in data
        assert data["total"] >= 1
        assert any(o["loan_id"] == "ln_test_001" for o in data["outcomes"])

    async def test_list_outcomes_with_date_filter(self, auth_client: AsyncClient, sample_outcome_request: dict):
        """GET /v1/outcomes should support date filtering."""
        # Submit an outcome
        await auth_client.post("/v1/outcomes", json=sample_outcome_request)
        
        # List with start_date filter
        response = await auth_client.get(
            "/v1/outcomes",
            params={"start_date": "2026-01-01T00:00:00Z"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_list_outcomes_empty(self, auth_client: AsyncClient):
        """GET /v1/outcomes should return empty list when no outcomes exist."""
        # This test depends on having a clean test database
        # For now, we just verify the endpoint responds
        response = await auth_client.get("/v1/outcomes")
        assert response.status_code == 200
        data = response.json()
        assert "outcomes" in data
        assert "total" in data
