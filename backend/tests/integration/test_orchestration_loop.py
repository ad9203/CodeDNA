"""Integration tests for end-to-end review orchestration, memory recall, and degradation."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import ExternalServiceError
from app.db.base import Base
from app.db.repositories import (
    MemoryAuditRepo,
    ReviewFindingRepo,
    ReviewRunRepo,
)
from app.integrations.github_client import MockGitHubClient
from app.integrations.groq_client import MockGroqClient
from app.integrations.hindsight_client import MockHindsightClient
from app.schemas.diff import ChangedFile
from app.services.orchestration_service import OrchestrationService


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_adapters():
    # 1. Setup Mock GitHub Client
    gh = MockGitHubClient()
    files = [
        ChangedFile(
            path="services/payment_service.py",
            status="modified",
            additions=12,
            deletions=2,
            patch="@@ -10,3 +10,5 @@\n def charge(amount):\n+    validate(amount)\n+    return db.save(amount)\n",
            language="python",
        )
    ]
    gh.seed_pr(
        owner="acme",
        repo="commerce",
        number=42,
        title="Refactor payment logic",
        files=files,
    )

    # 2. Setup Mock Hindsight Client with seeded memory
    hs = MockHindsightClient()
    hs.seed_memory(
        bank_id="codedna:acme:commerce",
        text="Team Rule: All service layer database operations must occur through repository abstractions.",
        source_type="team_rule",
        tags=["architecture"],
        relevance=0.93,
    )

    # 3. Setup Mock Groq Client
    gq = MockGroqClient()
    gq.set_response(
        {
            "summary": "Review identified architectural violation regarding direct DB access.",
            "overall_risk": "medium",
            "findings": [
                {
                    "severity": "high",
                    "category": "architecture",
                    "confidence": 0.95,
                    "path": "services/payment_service.py",
                    "line": 12,
                    "side": "RIGHT",
                    "title": "Direct database call in service layer",
                    "message": "Use PaymentRepository rather than calling db directly.",
                    "rationale": "Violates team architecture convention.",
                    "suggestion": "return self.payment_repo.save(amount)",
                }
            ],
            "team_conventions_applied": [
                "Service layer database operations must occur through repository abstractions"
            ],
            "memory_influence_summary": [
                "Directly identified violation of Team Rule recalled from Hindsight"
            ],
            "uncertainty_notes": [],
        }
    )

    return {"gh": gh, "hs": hs, "gq": gq}


@pytest.mark.asyncio
async def test_full_orchestration_loop_success(db_session: AsyncSession, mock_adapters):
    gh = mock_adapters["gh"]
    hs = mock_adapters["hs"]
    gq = mock_adapters["gq"]

    orchestrator = OrchestrationService(
        github_client=gh,
        hindsight_client=hs,
        groq_client=gq,
    )

    result = await orchestrator.process_pull_request_review(
        session=db_session,
        owner="acme",
        repo="commerce",
        pr_number=42,
        delivery_id="deliv-full-loop-1",
        publish_to_github=True,
    )

    assert result["status"] == "reviewed"
    assert result["findings_count"] == 1
    assert result["memory_recalled_count"] == 1
    assert result["published"] is True

    # Verify DB persistence
    review_run = await ReviewRunRepo.get_by_delivery_id(db_session, "deliv-full-loop-1")
    assert review_run is not None
    assert review_run.status == "reviewed"
    assert review_run.finding_count == 1
    assert review_run.memory_recalled_count == 1

    findings = await ReviewFindingRepo.list_by_run(db_session, review_run.id)
    assert len(findings) == 1
    assert findings[0].title == "Direct database call in service layer"

    mem_audits = await MemoryAuditRepo.list_by_run(db_session, review_run.id)
    assert len(mem_audits) == 1
    assert "repository abstractions" in mem_audits[0].memory_text_sanitized

    # Verify GitHub published review
    reviews = await gh.list_reviews("acme", "commerce", 42)
    assert len(reviews) == 1
    assert "CodeDNA Review" in reviews[0]["body"]
    assert "Direct database call in service layer" in reviews[0]["body"]

    # Verify learning loop retain called
    assert len(hs.calls_retain) >= 1


@pytest.mark.asyncio
async def test_hindsight_failure_degrades_gracefully(db_session: AsyncSession, mock_adapters):
    gh = mock_adapters["gh"]
    hs = mock_adapters["hs"]
    gq = mock_adapters["gq"]

    # Inject Hindsight failure
    hs.should_fail = True

    orchestrator = OrchestrationService(
        github_client=gh,
        hindsight_client=hs,
        groq_client=gq,
    )

    result = await orchestrator.process_pull_request_review(
        session=db_session,
        owner="acme",
        repo="commerce",
        pr_number=42,
        delivery_id="deliv-degraded-loop",
        publish_to_github=True,
    )

    # Review proceeds statelessly without crashing
    assert result["status"] == "degraded"
    assert result["memory_recalled_count"] == 0
    assert result["published"] is True

    review_run = await ReviewRunRepo.get_by_delivery_id(db_session, "deliv-degraded-loop")
    assert review_run.status == "degraded"


@pytest.mark.asyncio
async def test_groq_failure_halts_publishing_and_marks_failed(
    db_session: AsyncSession, mock_adapters
):
    gh = mock_adapters["gh"]
    hs = mock_adapters["hs"]
    gq = mock_adapters["gq"]

    # Inject Groq failure
    gq.should_fail = True

    orchestrator = OrchestrationService(
        github_client=gh,
        hindsight_client=hs,
        groq_client=gq,
    )

    result = await orchestrator.process_pull_request_review(
        session=db_session,
        owner="acme",
        repo="commerce",
        pr_number=42,
        delivery_id="deliv-groq-fail",
        publish_to_github=True,
    )

    assert result["status"] == "failed"

    # Verify no GitHub reviews were posted
    reviews = await gh.list_reviews("acme", "commerce", 42)
    assert len(reviews) == 0

    review_run = await ReviewRunRepo.get_by_delivery_id(db_session, "deliv-groq-fail")
    assert review_run.status == "failed"
    assert review_run.error_code == "GROQ_GENERATION_FAILED"


@pytest.mark.asyncio
async def test_publish_failure_preserves_findings_in_db(db_session: AsyncSession, mock_adapters):
    gh = mock_adapters["gh"]
    hs = mock_adapters["hs"]
    gq = mock_adapters["gq"]

    # Seed PR in GH then break GH before publish
    async def failing_create_review(*args, **kwargs):
        raise ExternalServiceError("github", "Secondary rate limit encountered", retryable=False)

    gh.create_review = failing_create_review  # type: ignore

    orchestrator = OrchestrationService(
        github_client=gh,
        hindsight_client=hs,
        groq_client=gq,
    )

    result = await orchestrator.process_pull_request_review(
        session=db_session,
        owner="acme",
        repo="commerce",
        pr_number=42,
        delivery_id="deliv-publish-fail",
        publish_to_github=True,
    )

    assert result["status"] == "publish_failed"

    # Crucial: findings were saved to DB before publishing failed
    review_run = await ReviewRunRepo.get_by_delivery_id(db_session, "deliv-publish-fail")
    assert review_run.status == "failed"
    assert review_run.error_code == "PUBLISH_FAILED"
    assert review_run.finding_count == 1
