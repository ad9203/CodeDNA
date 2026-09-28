"""Smoke test for application bootstrap and liveness."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_backend_liveness(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "codedna-backend"


@pytest.mark.asyncio
async def test_backend_readiness(async_client: AsyncClient):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "environment" in data


@pytest.mark.asyncio
async def test_correlation_id_header(async_client: AsyncClient):
    response = await async_client.get("/health/live", headers={"X-Request-ID": "test-req-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-req-123"
