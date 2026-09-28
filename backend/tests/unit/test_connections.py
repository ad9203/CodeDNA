"""Tests for external connection verification, production hardening, and strict CORS."""

import hashlib
import hmac

import pytest
from httpx import AsyncClient
from pydantic import AnyHttpUrl, SecretStr, ValidationError

from app.core.config import Settings, settings
from app.core.security import verify_github_signature
from app.db.base import Base
from app.db.session import engine


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_production_cors_wildcard_rejection():
    """Ensures production configuration strictly forbids wildcard CORS origin."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            frontend_origin=AnyHttpUrl("http://*"),
            github_token="ghp_dummy_token_12345678901234567890",  # pragma: allowlist secret
            github_webhook_secret="sec_dummy_webhook_secret_12345",  # pragma: allowlist secret
            groq_api_key="gsk_dummy_groq_api_key_1234567890",  # pragma: allowlist secret
            hindsight_api_key="hs_dummy_hindsight_api_key_12345",  # pragma: allowlist secret
        )
    assert "Wildcard CORS origin is strictly prohibited" in str(exc_info.value)


def test_signature_verification_integrity():
    """Ensures HMAC-SHA256 constant-time signature verification prevents tampering."""
    secret = "production-webhook-secret-999"
    payload = b'{"pull_request": {"number": 101, "title": "Test PR"}}'
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert verify_github_signature(payload, valid_sig, secret) is True
    assert verify_github_signature(payload, "sha256=invalidhex", secret) is False
    assert verify_github_signature(b'{"tampered": true}', valid_sig, secret) is False


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejection(async_client: AsyncClient, monkeypatch):
    """Ensures untrusted webhook payloads with invalid signatures are rejected when secret is configured."""
    monkeypatch.setattr(settings, "github_webhook_secret", SecretStr("test_configured_secret"))
    resp = await async_client.post(
        "/api/webhook/github",
        content=b'{"action": "opened"}',
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-invalid-sig",
            "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cors_options_preflight(async_client: AsyncClient):
    """Ensures CORS preflight accepts configured frontend origin."""
    resp = await async_client.options(
        "/api/webhook/github",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_overview_stats_endpoint(async_client: AsyncClient):
    """Ensures overview stats endpoint returns aggregated metrics."""
    resp = await async_client.get("/api/stats/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_reviews" in data
    assert "total_repositories" in data
    assert "findings_by_severity" in data
