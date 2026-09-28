"""Unit tests for Dashboard Read APIs and statistics."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.db.base import Base
from app.db.models import (
    MemoryAudit,
    PullRequest,
    Repository,
    ReviewFeedback,
    ReviewFinding,
    ReviewRun,
)
from app.main import app


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for dashboard API tests."""
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
async def seeded_dashboard_data(db_session: AsyncSession):
    """Seeds two repositories with PRs, review runs, findings, memories, and feedback."""
    repo1 = Repository(
        owner="acme",
        name="web-frontend",
        full_name="acme/web-frontend",
        default_branch="main",
    )
    repo2 = Repository(
        owner="acme",
        name="billing-service",
        full_name="acme/billing-service",
        default_branch="main",
    )
    db_session.add_all([repo1, repo2])
    await db_session.flush()

    # PRs
    pr1 = PullRequest(
        repository_id=repo1.id,
        github_pr_number=10,
        title="Add user profile settings",
        author_login="alice",
        head_sha="sha_web_1",
        base_sha="sha_web_0",
        html_url="https://github.com/acme/web-frontend/pull/10",
    )
    pr2 = PullRequest(
        repository_id=repo2.id,
        github_pr_number=20,
        title="Process stripe webhooks",
        author_login="bob",
        head_sha="sha_bill_1",
        base_sha="sha_bill_0",
        html_url="https://github.com/acme/billing-service/pull/20",
    )
    db_session.add_all([pr1, pr2])
    await db_session.flush()

    # Review runs
    run1 = ReviewRun(
        pull_request_id=pr1.id,
        delivery_id="deliv-dash-1",
        status="reviewed",
        total_duration_ms=1250,
        finding_count=2,
        memory_recalled_count=2,
    )
    run2 = ReviewRun(
        pull_request_id=pr2.id,
        delivery_id="deliv-dash-2",
        status="failed",
        total_duration_ms=450,
        finding_count=0,
        memory_recalled_count=0,
        error_code="RATE_LIMIT",
        error_message_safe="Upstream service rate limit encountered",
    )
    db_session.add_all([run1, run2])
    await db_session.flush()

    # Findings for run1
    f1 = ReviewFinding(
        review_run_id=run1.id,
        severity="critical",
        category="security",
        confidence=0.98,
        path="app/settings.tsx",
        line=42,
        side="RIGHT",
        title="Cross-Site Scripting (XSS)",
        message="Unsanitized dangerouslySetInnerHTML usage.",
        rationale="Enables stored XSS.",
        suggestion="sanitize(userInput)",
        feedback_status="accepted",
    )
    f2 = ReviewFinding(
        review_run_id=run1.id,
        severity="medium",
        category="performance",
        confidence=0.85,
        path="components/avatar.tsx",
        line=15,
        side="RIGHT",
        title="Unoptimized image asset",
        message="Use Next.js Image component instead of raw img tag.",
        rationale="Reduces page load time.",
        suggestion="<Image src={url} width={40} height={40} />",
        feedback_status=None,
    )
    db_session.add_all([f1, f2])

    # Memories for run1
    m1 = MemoryAudit(
        review_run_id=run1.id,
        memory_source_id="mem-xss-rule",
        memory_type="team_rule",
        memory_text_sanitized="Rule: dangerouslySetInnerHTML is prohibited unless reviewed by security team.",
        relevance_score=0.95,
        rank_order=0,
    )
    m2 = MemoryAudit(
        review_run_id=run1.id,
        memory_source_id="mem-img-rule",
        memory_type="applied_convention",
        memory_text_sanitized="Convention: Always use next/image for avatar thumbnails.",
        relevance_score=0.88,
        rank_order=1,
    )
    db_session.add_all([m1, m2])

    # Feedback for run1
    fb = ReviewFeedback(
        review_run_id=run1.id,
        finding_id=f1.id,
        actor_login="lead_reviewer",
        outcome="accepted",
        feedback_text="Spot on, critical fix required.",
    )
    db_session.add(fb)

    await db_session.commit()

    return {
        "repo1": repo1,
        "repo2": repo2,
        "pr1": pr1,
        "pr2": pr2,
        "run1": run1,
        "run2": run2,
        "f1": f1,
        "f2": f2,
        "m1": m1,
        "m2": m2,
    }


@pytest.mark.asyncio
async def test_list_repositories(db_session: AsyncSession, seeded_dashboard_data):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/repositories")
        assert resp.status_code == 200
        repos = resp.json()
        assert len(repos) == 2
        # Verify repository details and metrics
        repo_names = [r["full_name"] for r in repos]
        assert "acme/billing-service" in repo_names
        assert "acme/web-frontend" in repo_names

        web_repo = next(r for r in repos if r["name"] == "web-frontend")
        assert web_repo["pr_count"] == 1
        assert web_repo["review_count"] == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_reviews_pagination_and_filtering(
    db_session: AsyncSession, seeded_dashboard_data
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unfiltered list
        resp = await client.get("/api/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # 2. Filter by status=failed
        resp_failed = await client.get("/api/reviews?status=failed")
        assert resp_failed.status_code == 200
        data_failed = resp_failed.json()
        assert data_failed["total"] == 1
        assert data_failed["items"][0]["status"] == "failed"
        assert data_failed["items"][0]["pr_title"] == "Process stripe webhooks"

        # 3. Filter by repository_id
        repo1_id = seeded_dashboard_data["repo1"].id
        resp_repo = await client.get(f"/api/reviews?repository_id={repo1_id}")
        assert resp_repo.status_code == 200
        data_repo = resp_repo.json()
        assert data_repo["total"] == 1
        assert data_repo["items"][0]["repository_id"] == repo1_id
        assert data_repo["items"][0]["pr_title"] == "Add user profile settings"

        # 4. Pagination limit & offset
        resp_page = await client.get("/api/reviews?limit=1&offset=0")
        assert resp_page.status_code == 200
        data_page = resp_page.json()
        assert data_page["total"] == 2
        assert len(data_page["items"]) == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_review_detail(db_session: AsyncSession, seeded_dashboard_data):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run1_id = seeded_dashboard_data["run1"].id
        resp = await client.get(f"/api/reviews/{run1_id}")
        assert resp.status_code == 200
        detail = resp.json()

        assert detail["id"] == run1_id
        assert detail["status"] == "reviewed"
        assert detail["total_duration_ms"] == 1250
        assert detail["repository"]["full_name"] == "acme/web-frontend"
        assert detail["pull_request"]["title"] == "Add user profile settings"
        assert len(detail["findings"]) == 2
        assert len(detail["memories"]) == 2
        assert detail["feedback_count"] == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_review_findings_and_memories(db_session: AsyncSession, seeded_dashboard_data):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run1_id = seeded_dashboard_data["run1"].id

        # 1. Findings endpoint
        resp_findings = await client.get(f"/api/reviews/{run1_id}/findings")
        assert resp_findings.status_code == 200
        findings = resp_findings.json()
        assert len(findings) == 2
        assert findings[0]["severity"] == "critical"
        assert "Cross-Site Scripting" in findings[0]["title"]
        assert findings[0]["feedback_status"] == "accepted"

        # 2. Memories endpoint
        resp_mem = await client.get(f"/api/reviews/{run1_id}/memory")
        assert resp_mem.status_code == 200
        memories = resp_mem.json()
        assert len(memories) == 2
        assert memories[0]["relevance_score"] == 0.95
        assert "dangerouslySetInnerHTML" in memories[0]["memory_text_sanitized"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_overview_statistics(db_session: AsyncSession, seeded_dashboard_data):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats/overview")
        assert resp.status_code == 200
        stats = resp.json()

        assert stats["total_repositories"] == 2
        assert stats["total_reviews"] == 2
        assert stats["total_findings"] == 2
        assert stats["total_memories_recalled"] == 2
        assert stats["findings_by_severity"]["critical"] == 1
        assert stats["findings_by_severity"]["medium"] == 1
        assert stats["feedback_metrics"]["total"] == 1
        assert stats["feedback_metrics"]["acceptance_rate"] == 100.0
        assert stats["avg_duration_ms"] is not None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_404_endpoints(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Non-existent run detail
        resp1 = await client.get("/api/reviews/missing-run-id")
        assert resp1.status_code == 404

        # Non-existent findings
        resp2 = await client.get("/api/reviews/missing-run-id/findings")
        assert resp2.status_code == 404

        # Non-existent memories
        resp3 = await client.get("/api/reviews/missing-run-id/memory")
        assert resp3.status_code == 404

    app.dependency_overrides.clear()
