"""Unit tests for Human Feedback intake and Hindsight learning loop."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.db.base import Base
from app.db.models import PullRequest, Repository, ReviewFinding, ReviewRun
from app.db.repositories import ReviewFindingRepo
from app.integrations.hindsight_client import MockHindsightClient
from app.main import app
from app.services.learning_service import LearningService
from app.services.memory_service import MemoryService


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for feedback tests."""
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


@pytest_asyncio.fixture
async def seeded_review_data(db_session: AsyncSession):
    """Seeds a repository, PR, review run, and finding."""
    repo = Repository(
        owner="acme-corp",
        name="billing-engine",
        full_name="acme-corp/billing-engine",
        default_branch="main",
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        repository_id=repo.id,
        github_pr_number=55,
        title="Add invoice migration",
        author_login="junior_dev",
        head_sha="sha_head_55",
        base_sha="sha_base_55",
        html_url="https://github.com/acme-corp/billing-engine/pull/55",
    )
    db_session.add(pr)
    await db_session.flush()

    run = ReviewRun(
        pull_request_id=pr.id,
        delivery_id="deliv-feedback-test",
        status="reviewed",
    )
    db_session.add(run)
    await db_session.flush()

    finding = ReviewFinding(
        review_run_id=run.id,
        severity="high",
        category="architecture",
        confidence=0.92,
        path="migrations/0012_invoices.py",
        line=25,
        side="RIGHT",
        title="Direct SQL in migration",
        message="Use ORM repository instead of raw SQL queries in migration script.",
        rationale="Violates repository pattern convention.",
        suggestion="use InvoiceRepository()",
    )
    db_session.add(finding)
    await db_session.commit()

    return {
        "repo": repo,
        "pr": pr,
        "run": run,
        "finding": finding,
    }


@pytest.fixture
def mock_hindsight(monkeypatch):
    hs = MockHindsightClient()
    # Patch LearningService to use our MockHindsightClient
    mock_memory_service = MemoryService(client=hs)
    monkeypatch.setattr(
        "app.api.feedback.LearningService",
        lambda *args, **kwargs: LearningService(memory_service=mock_memory_service),
    )
    return hs


@pytest.mark.asyncio
async def test_submit_finding_feedback_rejected_creates_negative_memory(
    db_session: AsyncSession, seeded_review_data, mock_hindsight
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id
        finding_id = seeded_review_data["finding"].id

        payload = {
            "outcome": "rejected",
            "feedback_text": "We allow raw SQL in migration scripts for performance and lock safety.",
            "actor_login": "lead_architect",
            "source_url": "https://github.com/acme-corp/billing-engine/pull/55#comment-1",
        }

        resp = await client.post(
            f"/api/reviews/{run_id}/findings/{finding_id}/feedback",
            json=payload,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "rejected"
        assert data["actor_login"] == "lead_architect"
        assert data["retained_in_hindsight"] is True

        # Verify DB status updated
        updated_finding = await ReviewFindingRepo.get_by_id(db_session, finding_id)
        assert updated_finding is not None
        assert updated_finding.feedback_status == "rejected"

        # Verify Hindsight retention call
        assert len(mock_hindsight.calls_retain) == 1
        call = mock_hindsight.calls_retain[0]
        assert call["bank_id"] == "codedna:acme-corp:billing-engine"
        assert "rejected suggestion 'Direct SQL in migration'" in call["content"]
        assert "raw SQL in migration scripts" in call["content"]
        assert "feedback:rejected" in call["tags"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_finding_feedback_accepted(
    db_session: AsyncSession, seeded_review_data, mock_hindsight
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id
        finding_id = seeded_review_data["finding"].id

        payload = {
            "outcome": "accepted",
            "feedback_text": "Great catch, will refactor to use repository abstraction.",
            "actor_login": "senior_dev",
        }

        resp = await client.post(
            f"/api/reviews/{run_id}/findings/{finding_id}/feedback",
            json=payload,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "accepted"
        assert data["retained_in_hindsight"] is True

        updated_finding = await ReviewFindingRepo.get_by_id(db_session, finding_id)
        assert updated_finding is not None
        assert updated_finding.feedback_status == "accepted"

        assert len(mock_hindsight.calls_retain) == 1
        call = mock_hindsight.calls_retain[0]
        assert "Team convention confirmed" in call["content"]
        assert "feedback:accepted" in call["tags"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_general_review_feedback(
    db_session: AsyncSession, seeded_review_data, mock_hindsight
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id

        payload = {
            "outcome": "modified",
            "feedback_text": "General review quality was accurate, but be more concise in rationale.",
            "actor_login": "tech_lead",
        }

        resp = await client.post(
            f"/api/reviews/{run_id}/feedback",
            json=payload,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "modified"
        assert data["finding_id"] is None
        assert data["retained_in_hindsight"] is True

        assert len(mock_hindsight.calls_retain) == 1
        call = mock_hindsight.calls_retain[0]
        assert "Team standard refinement" in call["content"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_review_feedback(db_session: AsyncSession, seeded_review_data, mock_hindsight):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id
        finding_id = seeded_review_data["finding"].id

        # Submit 2 feedbacks
        await client.post(
            f"/api/reviews/{run_id}/findings/{finding_id}/feedback",
            json={
                "outcome": "rejected",
                "feedback_text": "Disagreed with rule",
                "actor_login": "dev1",
            },
        )
        await client.post(
            f"/api/reviews/{run_id}/feedback",
            json={
                "outcome": "accepted",
                "feedback_text": "PR looks solid overall",
                "actor_login": "dev2",
            },
        )

        resp = await client.get(f"/api/reviews/{run_id}/feedback")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        assert items[0]["actor_login"] == "dev1"
        assert items[1]["actor_login"] == "dev2"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_feedback_nonexistent_ids_return_404(
    db_session: AsyncSession, seeded_review_data, mock_hindsight
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id

        # Non-existent review run
        resp = await client.post(
            "/api/reviews/non-existent-run/feedback",
            json={"outcome": "accepted", "feedback_text": "Hello"},
        )
        assert resp.status_code == 404

        # Non-existent finding
        resp2 = await client.post(
            f"/api/reviews/{run_id}/findings/non-existent-finding/feedback",
            json={"outcome": "accepted", "feedback_text": "Hello"},
        )
        assert resp2.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_learning_loop_rejection_prevents_repeat_finding(
    db_session: AsyncSession, seeded_review_data, mock_hindsight
):
    """Verifies that human rejection of a finding is retained and recalled in future reviews."""
    from app.schemas.diff import ChangedFile, PRDiffContext

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_id = seeded_review_data["run"].id
        finding_id = seeded_review_data["finding"].id

        # 1. Developer rejects the suggestion
        payload = {
            "outcome": "rejected",
            "feedback_text": "Team convention: Raw SQL is explicitly allowed and preferred in migration scripts.",
            "actor_login": "principal_engineer",
        }
        res = await client.post(
            f"/api/reviews/{run_id}/findings/{finding_id}/feedback",
            json=payload,
        )
        assert res.status_code == 201

        # 2. In Hindsight memory bank, the memory is now retained
        assert len(mock_hindsight.calls_retain) >= 1
        bank_id = "codedna:acme-corp:billing-engine"
        assert bank_id in mock_hindsight.banks
        assert len(mock_hindsight.banks[bank_id]) >= 1

        # 3. Simulate future PR touching migrations
        memory_service = MemoryService(client=mock_hindsight)
        diff_context = PRDiffContext(
            repo="acme-corp/billing-engine",
            pr_number=56,
            title="Add payment audit table migration",
            base_sha="sha_base_56",
            head_sha="sha_head_56",
            files=[
                ChangedFile(
                    path="migrations/0013_audit.py",
                    status="added",
                    additions=20,
                    deletions=0,
                    valid_lines=[1, 2, 3],
                    patch="@@ -0,0 +1,5 @@\n+CREATE TABLE audit;",
                )
            ],
            total_files=1,
            total_additions=20,
            total_deletions=0,
            formatted_diff="CREATE TABLE audit;",
        )

        recall_res = await memory_service.recall_for_pr(
            owner="acme-corp", repo="billing-engine", diff_context=diff_context
        )

        # 4. Verify the recalled memories include the rejected convention!
        assert recall_res.status == "ok"
        assert len(recall_res.memories) >= 1
        recalled_texts = [m.text for m in recall_res.memories]
        assert any(
            "rejected suggestion" in t or "Raw SQL is explicitly allowed" in t
            for t in recalled_texts
        )

    app.dependency_overrides.clear()
