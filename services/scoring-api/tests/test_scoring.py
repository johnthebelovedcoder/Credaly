"""
Tests for the scoring API endpoints.
"""

import pytest
from httpx import AsyncClient


class TestScoreAPI:
    """Test /v1/score endpoints."""

    async def test_score_request_validation(self, auth_client: AsyncClient):
        """POST /v1/score should validate input."""
        # Missing required fields
        response = await auth_client.post("/v1/score", json={})
        assert response.status_code == 422

    async def test_score_request_invalid_bvn(self, auth_client: AsyncClient):
        """POST /v1/score should reject invalid BVN."""
        response = await auth_client.post(
            "/v1/score",
            json={
                "bvn": "invalid",  # Non-numeric
                "phone": "+2348012345678",
                "lender_id": "lnd_test",
            },
        )
        assert response.status_code == 422

    async def test_score_history_empty(self, auth_client: AsyncClient, sample_bvn: str):
        """GET /v1/score/{bvn}/history should return empty for unknown BVN."""
        response = await auth_client.get(f"/v1/score/{sample_bvn}/history")
        assert response.status_code == 200
        data = response.json()
        assert "bvn_hash" in data
        assert data["scores"] == []
