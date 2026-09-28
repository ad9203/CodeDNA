"""Unit and integration tests for GitHub webhook security and event intake."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base
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
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


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


@pytest.mark.asyncio
async def test_review_comment_dispatches_learning_task(override_secret, monkeypatch):
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_review_comment_created_payload(number=108)
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
                "X-GitHub-Delivery": "deliv-comment-108",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "enqueued"
    assert len(dispatched_tasks) == 1
    _, kwargs = dispatched_tasks[0]
    assert kwargs["owner"] == "acme"
    assert kwargs["repo"] == "commerce"
    assert kwargs["actor_login"] == "lead_architect"
    assert kwargs["pr_number"] == 108
    assert "Rejected" in kwargs["comment_body"]


@pytest.mark.asyncio
async def test_human_ad9203_comment_dispatches_learning_task(override_secret, monkeypatch):
    """Case A: Human ad9203 feedback comment triggers Hindsight learning task."""
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_review_comment_created_payload(number=120)
    payload["comment"]["user"]["login"] = "ad9203"
    payload["comment"]["user"]["type"] = "User"
    payload["comment"]["body"] = (
        "For documentation-only changes, missing a final newline should not be treated as an actionable finding."
    )
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
                "X-GitHub-Delivery": "deliv-human-ad9203",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "enqueued"
    assert len(dispatched_tasks) == 1
    _, kwargs = dispatched_tasks[0]
    assert kwargs["actor_login"] == "ad9203"
    assert "documentation-only changes" in kwargs["comment_body"]


@pytest.mark.asyncio
async def test_codedna_automated_review_comment_ignored(override_secret, monkeypatch):
    """Case B: CodeDNA automated review comments (inline & summary) are ignored even from token owner."""
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # B.1: Inline automated comment with **[INFO]
        payload_inline = make_review_comment_created_payload(number=121)
        payload_inline["comment"]["user"]["login"] = "ad9203"
        payload_inline["comment"]["user"]["type"] = "User"
        payload_inline["comment"]["body"] = (
            "**[INFO] Missing newline at end of file**\n\nThe file does not end with a newline."
        )
        bytes_inline = json.dumps(payload_inline).encode("utf-8")
        res1 = await client.post(
            "/api/webhook/github",
            content=bytes_inline,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request_review_comment",
                "X-GitHub-Delivery": "deliv-bot-inline",
                "X-Hub-Signature-256": compute_signature(TEST_SECRET, bytes_inline),
            },
        )
        assert res1.status_code == 202
        assert res1.json()["status"] == "ignored"

        # B.2: Review summary with ## CodeDNA Review
        payload_summary = make_review_comment_created_payload(number=122)
        payload_summary["comment"]["user"]["login"] = "ad9203"
        payload_summary["comment"]["body"] = "## CodeDNA Review\n\n**Overall Risk**: `LOW`"
        bytes_summary = json.dumps(payload_summary).encode("utf-8")
        res2 = await client.post(
            "/api/webhook/github",
            content=bytes_summary,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request_review_comment",
                "X-GitHub-Delivery": "deliv-bot-summary",
                "X-Hub-Signature-256": compute_signature(TEST_SECRET, bytes_summary),
            },
        )
        assert res2.status_code == 202
        assert res2.json()["status"] == "ignored"

    assert len(dispatched_tasks) == 0


@pytest.mark.asyncio
async def test_github_user_type_bot_ignored(override_secret, monkeypatch):
    """Case C: GitHub user.type == 'Bot' or [bot] username is ignored."""
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_review_comment_created_payload(number=123)
    payload["comment"]["user"]["login"] = "custom-ci[bot]"
    payload["comment"]["user"]["type"] = "Bot"
    payload["comment"]["body"] = "Automated benchmark passed."
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
                "X-GitHub-Delivery": "deliv-bot-usertype",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "ignored"
    assert len(dispatched_tasks) == 0


@pytest.mark.asyncio
async def test_normal_human_comment_from_another_user_dispatched(override_secret, monkeypatch):
    """Case D: Normal human comment from another user is dispatched to learning task."""
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_review_comment_created_payload(number=124)
    payload["comment"]["user"]["login"] = "senior_dev"
    payload["comment"]["user"]["type"] = "User"
    payload["comment"]["body"] = "We require strict typing for all new API request models."
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
                "X-GitHub-Delivery": "deliv-human-other",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "enqueued"
    assert len(dispatched_tasks) == 1
    _, kwargs = dispatched_tasks[0]
    assert kwargs["actor_login"] == "senior_dev"
    assert "strict typing" in kwargs["comment_body"]


@pytest.mark.asyncio
async def test_issue_comment_on_pr_dispatches_learning_task(override_secret, monkeypatch):
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_issue_comment_payload(number=111, is_pr=True)
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "deliv-issue-comment-111",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "enqueued"
    assert len(dispatched_tasks) == 1
    _, kwargs = dispatched_tasks[0]
    assert kwargs["owner"] == "acme"
    assert kwargs["repo"] == "commerce"
    assert kwargs["actor_login"] == "engineer"
    assert kwargs["pr_number"] == 111
    assert "switching to Decimal" in kwargs["comment_body"]


@pytest.mark.asyncio
async def test_issue_comment_on_pr_bot_ignored(override_secret, monkeypatch):
    dispatched_tasks: list[tuple[tuple, dict]] = []

    async def mock_learning_task(*args, **kwargs):
        dispatched_tasks.append((args, kwargs))
        return True

    monkeypatch.setattr("app.api.webhook.run_comment_learning_task", mock_learning_task)

    payload = make_issue_comment_payload(number=112, is_pr=True)
    payload["comment"]["user"]["login"] = "github-actions"
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_signature(TEST_SECRET, body_bytes)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/webhook/github",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "deliv-issue-comment-112",
                "X-Hub-Signature-256": sig,
            },
        )
    assert res.status_code == 202
    assert res.json()["status"] == "ignored"
    assert len(dispatched_tasks) == 0


@pytest.mark.asyncio
async def test_run_comment_learning_task_success():
    from unittest.mock import AsyncMock, MagicMock

    from app.workers.tasks import run_comment_learning_task

    mock_service = MagicMock()
    mock_service.process_feedback_outcome = AsyncMock(return_value=True)

    result = await run_comment_learning_task(
        owner="org",
        repo="repo",
        comment_body="Convention feedback",
        actor_login="dev",
        pr_number=5,
        learning_service=mock_service,
    )
    assert result is True
    mock_service.process_feedback_outcome.assert_awaited_once_with(
        owner="org",
        repo="repo",
        finding=None,
        outcome="rejected",
        feedback_text="Convention feedback",
        actor_login="dev",
    )


@pytest.mark.asyncio
async def test_run_comment_learning_task_handles_exception():
    from unittest.mock import AsyncMock, MagicMock

    from app.workers.tasks import run_comment_learning_task

    mock_service = MagicMock()
    mock_service.process_feedback_outcome = AsyncMock(side_effect=RuntimeError("Hindsight offline"))

    result = await run_comment_learning_task(
        owner="org",
        repo="repo",
        comment_body="Convention feedback",
        actor_login="dev",
        pr_number=5,
        learning_service=mock_service,
    )
    assert result is False


@pytest.mark.asyncio
async def test_run_comment_learning_task_closes_created_service(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.workers.tasks import run_comment_learning_task

    mock_instance = MagicMock()
    mock_instance.process_feedback_outcome = AsyncMock(return_value=True)
    mock_instance.aclose = AsyncMock()

    monkeypatch.setattr(
        "app.services.learning_service.LearningService", lambda *a, **kw: mock_instance
    )

    result = await run_comment_learning_task(
        owner="org",
        repo="repo",
        comment_body="Convention feedback",
        actor_login="dev",
        pr_number=5,
        learning_service=None,
    )
    assert result is True
    mock_instance.aclose.assert_awaited_once()
