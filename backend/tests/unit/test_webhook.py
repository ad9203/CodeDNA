"""Unit and integration tests for GitHub webhook security and event intake."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.main import app
from tests.fixtures.webhook_fixtures import (
    compute_signature,
    make_issue_comment_payload,
    make_pr_opened_payload,
    make_pr_review_submitted_payload,
    make_pr_sync_payload,
    make_review_comment_created_payload,
)

TEST_SECRET = "test_webhook_secret_xyz_123"


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def override_secret(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", SecretStr(TEST_SECRET))


@pytest.mark.asyncio
async def test_valid_signature_accepted(override_secret):
    payload = make_pr_opened_payload()
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-sig-valid-1",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"


@pytest.mark.asyncio
async def test_missing_signature_rejected(override_secret):
    payload = make_pr_opened_payload()
    body_bytes = json.dumps(payload).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-sig-missing",
            },
        )
    assert res.status_code == 403
    assert "Invalid or missing webhook signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_signature_rejected(override_secret):
    payload = make_pr_opened_payload()
    body_bytes = json.dumps(payload).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-sig-wrong",
                "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            },
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_body_mutation_invalidates_signature(override_secret):
    payload = make_pr_opened_payload()
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    # Mutate payload after computing signature
    mutated_bytes = body_bytes + b" "

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=mutated_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-sig-tampered",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_pull_request_opened_enqueues_review(override_secret):
    payload = make_pr_opened_payload(number=101)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-pr-101",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"
    assert "Pull request #101 opened enqueued for review" in data["message"]


@pytest.mark.asyncio
async def test_pull_request_synchronize_enqueues_review(override_secret):
    payload = make_pr_sync_payload(number=101, head_sha="sync_head_abc")
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-pr-sync-101",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"
    assert "synchronize enqueued" in data["message"]


@pytest.mark.asyncio
async def test_unsupported_pr_action_ignored(override_secret):
    payload = make_pr_opened_payload(number=102)
    payload["action"] = "labeled"
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-pr-labeled",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "ignored"


@pytest.mark.asyncio
async def test_duplicate_delivery_idempotent(override_secret):
    payload = make_pr_opened_payload(number=103)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "deliv-idempotent-103",
        "X-Hub-Signature-256": sig,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First delivery: enqueued
        res1 = await client.post("/api/webhook/github", content=body_bytes, headers=headers)
        assert res1.status_code == 202
        assert res1.json()["status"] == "enqueued"

        # Duplicate delivery: returns duplicate status without re-enqueueing
        res2 = await client.post("/api/webhook/github", content=body_bytes, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_pr_review_submitted_captured_for_learning(override_secret):
    payload = make_pr_review_submitted_payload(number=104)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request_review",
                "X-GitHub-Delivery": "deliv-review-104",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"
    assert "learning loop" in data["message"]


@pytest.mark.asyncio
async def test_review_comment_captured_for_learning(override_secret):
    payload = make_review_comment_created_payload(number=105)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request_review_comment",
                "X-GitHub-Delivery": "deliv-comment-105",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "enqueued"


@pytest.mark.asyncio
async def test_issue_comment_on_pr_captured_vs_plain_issue(override_secret):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Case A: Comment on PR -> enqueued
        pr_payload = make_issue_comment_payload(number=106, is_pr=True)
        pr_bytes = json.dumps(pr_payload).encode("utf-8")
        res_pr = await client.post(
            "/api/webhook/github",
            content=pr_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "deliv-pr-comment-106",
                "X-Hub-Signature-256": compute_signature(TEST_SECRET, pr_bytes),
            },
        )
        assert res_pr.status_code == 202
        assert res_pr.json()["status"] == "enqueued"

        # Case B: Comment on plain Issue -> ignored
        issue_payload = make_issue_comment_payload(number=107, is_pr=False)
        issue_bytes = json.dumps(issue_payload).encode("utf-8")
        res_issue = await client.post(
            "/api/webhook/github",
            content=issue_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "deliv-issue-comment-107",
                "X-Hub-Signature-256": compute_signature(TEST_SECRET, issue_bytes),
            },
        )
        assert res_issue.status_code == 202
        assert res_issue.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_malformed_json_returns_400(override_secret):
    malformed_body = b'{"action": "opened", "invalid_json_missing_brace'
    sig = compute_signature(TEST_SECRET, malformed_body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=malformed_body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-malformed",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 400
    assert "Malformed JSON" in res.json()["detail"]


@pytest.mark.asyncio
async def test_ping_event_acknowledged(override_secret):
    ping_payload = {"zen": "Keep it logically awesome."}
    body_bytes = json.dumps(ping_payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "deliv-ping-1",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 200
    assert res.json()["status"] == "processed"
