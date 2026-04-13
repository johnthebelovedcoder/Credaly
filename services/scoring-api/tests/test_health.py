"""
Tests for the scoring API health endpoints.
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Test /health and / endpoints."""

    async def test_root_endpoint(self, test_client: AsyncClient):
        """GET / should return API info."""
        response = await test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Credaly Scoring API"

    async def test_health_endpoint(self, test_client: AsyncClient):
        """GET /health should return ok status."""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data
