"""Unit and integration tests for persistence and review lifecycle repositories."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.repositories import (
    MemoryAuditRepo,
    PullRequestRepo,
    RepositoryRepo,
    ReviewFeedbackRepo,
    ReviewFindingRepo,
    ReviewRunRepo,
    WebhookDeliveryRepo,
)


@pytest_asyncio.fixture
async def test_db_session():
    """Provides a fresh in-memory SQLite database session for testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_repository_get_or_create(test_db_session: AsyncSession):
    repo1 = await RepositoryRepo.get_or_create(
        test_db_session, owner="acme", name="commerce", default_branch="main"
    )
    await test_db_session.commit()
    assert repo1.id is not None
    assert repo1.full_name == "acme/commerce"

    # Deterministic lookup: Calling again returns the exact same repository
    repo2 = await RepositoryRepo.get_or_create(test_db_session, owner="acme", name="commerce")
    assert repo2.id == repo1.id


@pytest.mark.asyncio
async def test_pull_request_lifecycle_and_synchronize(test_db_session: AsyncSession):
    repo = await RepositoryRepo.get_or_create(test_db_session, owner="acme", name="payments")
    await test_db_session.commit()

    pr = await PullRequestRepo.get_or_create(
        test_db_session,
        repository_id=repo.id,
        github_pr_number=42,
        title="Add payment validation",
        author_login="alice",
        head_sha="sha_initial_123",
        base_sha="sha_base_000",
        html_url="https://github.com/acme/payments/pull/42",
    )
    await test_db_session.commit()
    assert pr.github_pr_number == 42
    assert pr.head_sha == "sha_initial_123"

    # Synchronize event with updated head SHA
    pr_updated = await PullRequestRepo.get_or_create(
        test_db_session,
        repository_id=repo.id,
        github_pr_number=42,
        title="Add payment validation (amended)",
        author_login="alice",
        head_sha="sha_synchronize_456",
        base_sha="sha_base_000",
        html_url="https://github.com/acme/payments/pull/42",
    )
    await test_db_session.commit()
    assert pr_updated.id == pr.id
    assert pr_updated.head_sha == "sha_synchronize_456"
    assert pr_updated.title == "Add payment validation (amended)"


@pytest.mark.asyncio
async def test_webhook_delivery_idempotency(test_db_session: AsyncSession):
    delivery_id = "deliv-guid-unique-12345"
    assert await WebhookDeliveryRepo.is_duplicate(test_db_session, delivery_id) is False

    await WebhookDeliveryRepo.record_delivery(
        test_db_session,
        delivery_id=delivery_id,
        event_name="pull_request",
        action="opened",
    )
    await test_db_session.commit()

    assert await WebhookDeliveryRepo.is_duplicate(test_db_session, delivery_id) is True

    # Update delivery status
    updated = await WebhookDeliveryRepo.update_status(
        test_db_session, delivery_id=delivery_id, status="processed"
    )
    await test_db_session.commit()
    assert updated is not None
    assert updated.status == "processed"
    assert updated.processed_at is not None


@pytest.mark.asyncio
async def test_one_pr_multiple_review_runs(test_db_session: AsyncSession):
    repo = await RepositoryRepo.get_or_create(test_db_session, owner="acme", name="auth")
    pr = await PullRequestRepo.get_or_create(
        test_db_session,
        repository_id=repo.id,
        github_pr_number=10,
        title="Add JWT auth",
        author_login="bob",
        head_sha="sha1",
        base_sha="base1",
        html_url="https://github.com/acme/auth/pull/10",
    )
    await test_db_session.commit()

    # First review run (on opened)
    run1 = await ReviewRunRepo.create(
        test_db_session,
        pull_request_id=pr.id,
        delivery_id="deliv-opened",
        status="reviewed",
    )
    # Second review run (on synchronize)
    run2 = await ReviewRunRepo.create(
        test_db_session,
        pull_request_id=pr.id,
        delivery_id="deliv-synced",
        status="processing",
    )
    await test_db_session.commit()

    assert run1.id != run2.id
    assert run1.pull_request_id == pr.id
    assert run2.pull_request_id == pr.id


@pytest.mark.asyncio
async def test_findings_and_memory_audit_persistence(test_db_session: AsyncSession):
    repo = await RepositoryRepo.get_or_create(test_db_session, owner="acme", name="billing")
    pr = await PullRequestRepo.get_or_create(
        test_db_session,
        repository_id=repo.id,
        github_pr_number=5,
        title="Fix invoice calculation",
        author_login="carol",
        head_sha="sha5",
        base_sha="base5",
        html_url="https://github.com/acme/billing/pull/5",
    )
    run = await ReviewRunRepo.create(
        test_db_session,
        pull_request_id=pr.id,
        delivery_id="deliv-5",
    )
    await test_db_session.commit()

    # Create findings
    findings_data = [
        {
            "severity": "high",
            "category": "correctness",
            "confidence": 0.95,
            "path": "billing/service.py",
            "line": 42,
            "side": "RIGHT",
            "title": "Unrounded float arithmetic",
            "message": "Use Decimal for monetary calculations",
            "rationale": "Floating point rounding errors can accumulate in ledger",
            "suggestion": "from decimal import Decimal\ntotal = Decimal(str(amount))",
        }
    ]
    findings = await ReviewFindingRepo.create_many(test_db_session, run.id, findings_data)
    await test_db_session.commit()
    assert len(findings) == 1
    assert findings[0].id is not None
    assert findings[0].severity == "high"

    # Create memory audits
    memories_data = [
        {
            "memory_source_id": "mem-rule-14",
            "memory_type": "team_rule",
            "memory_text_sanitized": "All billing calculations must use Decimal, never float.",
            "relevance_context": "billing/service.py invoice arithmetic",
            "relevance_score": 0.92,
            "rank_order": 0,
        }
    ]
    audits = await MemoryAuditRepo.create_many(test_db_session, run.id, memories_data)
    await test_db_session.commit()
    assert len(audits) == 1
    assert audits[0].memory_type == "team_rule"

    # Record feedback on finding
    feedback = await ReviewFeedbackRepo.record_feedback(
        test_db_session,
        review_run_id=run.id,
        finding_id=findings[0].id,
        actor_login="carol",
        outcome="accepted",
        feedback_text="Applied Decimal fix as suggested.",
    )
    await test_db_session.commit()
    assert feedback.outcome == "accepted"

    # Verify finding feedback_status was updated
    listed_findings = await ReviewFindingRepo.list_by_run(test_db_session, run.id)
    assert listed_findings[0].feedback_status == "accepted"


@pytest.mark.asyncio
async def test_review_run_completion_and_metrics(test_db_session: AsyncSession):
    repo = await RepositoryRepo.get_or_create(test_db_session, owner="acme", name="ops")
    pr = await PullRequestRepo.get_or_create(
        test_db_session,
        repository_id=repo.id,
        github_pr_number=1,
        title="Infra update",
        author_login="dev",
        head_sha="s1",
        base_sha="b1",
        html_url="https://github.com/acme/ops/pull/1",
    )
    run = await ReviewRunRepo.create(test_db_session, pr.id, "deliv-comp")
    await test_db_session.commit()

    completed = await ReviewRunRepo.complete_run(
        test_db_session,
        review_run_id=run.id,
        status="reviewed",
        total_duration_ms=3240,
        finding_count=3,
        memory_recalled_count=2,
    )
    await test_db_session.commit()
    assert completed is not None
    assert completed.status == "reviewed"
    assert completed.total_duration_ms == 3240
    assert completed.finding_count == 3
    assert completed.memory_recalled_count == 2
    assert completed.completed_at is not None
