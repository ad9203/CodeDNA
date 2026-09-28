"""Unit tests for GitHub Review Publishing Service."""

import pytest

from app.core.errors import ExternalServiceError
from app.integrations.github_client import MockGitHubClient
from app.schemas.diff import ChangedFile, PRDiffContext
from app.schemas.memory import RecalledMemory
from app.schemas.review import ReviewFinding, ReviewResult
from app.services.publishing_service import PublishingService


@pytest.fixture
def diff_context():
    """Provides a sample PR diff context with known valid lines."""
    files = [
        ChangedFile(
            path="services/payment.py",
            status="modified",
            additions=10,
            deletions=2,
            valid_lines=[10, 11, 12, 13, 14, 15],
            patch="@@ -10,3 +10,6 @@\n def pay():\n+    process()\n",
        ),
        ChangedFile(
            path="services/auth.py",
            status="modified",
            additions=5,
            deletions=1,
            valid_lines=[50, 51, 52],
            patch="@@ -50,2 +50,3 @@\n def verify():\n+    check()\n",
        ),
    ]
    return PRDiffContext(
        repo="test-owner/test-repo",
        pr_number=101,
        title="Payment and Auth overhaul",
        base_sha="sha_base_00000",
        head_sha="sha_head_12345",
        files=files,
        total_files=2,
        total_additions=15,
        total_deletions=3,
        formatted_diff="mock diff content",
    )


@pytest.fixture
def sample_memories():
    return [
        RecalledMemory(
            memory_id="mem-1",
            text="Team Rule: All service layer database operations must occur through repository abstractions.",
            source_type="team_rule",
            relevance=0.92,
        )
    ]


@pytest.mark.asyncio
async def test_publish_review_with_inline_comments(diff_context, sample_memories):
    gh = MockGitHubClient()
    service = PublishingService(client=gh, max_inline_comments=5)

    findings = [
        ReviewFinding(
            severity="high",
            category="architecture",
            confidence=0.95,
            path="services/payment.py",
            line=12,
            side="RIGHT",
            title="Direct DB Access",
            message="Use repository instead of direct DB access.",
            rationale="Violates architecture convention.",
            suggestion="return self.repo.save()",
        ),
        ReviewFinding(
            severity="medium",
            category="security",
            confidence=0.88,
            path="services/auth.py",
            line=51,
            side="RIGHT",
            title="Weak token entropy",
            message="Use secrets.token_urlsafe instead.",
            rationale="Security hardening.",
            suggestion="secrets.token_urlsafe(32)",
        ),
    ]

    review_result = ReviewResult(
        summary="Found 2 issues in payment and auth.",
        overall_risk="high",
        findings=findings,
        team_conventions_applied=["Use repository pattern"],
        memory_influence_summary=["Recalled repository rule"],
        uncertainty_notes=[],
    )

    res = await service.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )

    assert res["id"] is not None
    assert res["event"] == "COMMENT"
    assert res["inline_count"] == 2
    assert res["unplaced_count"] == 0
    assert res["fallback_to_general"] is False

    # Check the recorded review in MockGitHubClient
    reviews = await gh.list_reviews("test-owner", "test-repo", 101)
    assert len(reviews) == 1
    assert "CodeDNA Review" in reviews[0]["body"]
    assert "Direct DB Access" in reviews[0]["body"]
    assert len(reviews[0]["comments"]) == 2
    assert reviews[0]["comments"][0]["path"] == "services/payment.py"
    assert reviews[0]["comments"][0]["line"] == 12
    assert "```suggestion" in reviews[0]["comments"][0]["body"]


@pytest.mark.asyncio
async def test_publish_review_prioritizes_severity_and_caps_inline(diff_context, sample_memories):
    gh = MockGitHubClient()
    # Limit to 2 inline comments
    service = PublishingService(client=gh, max_inline_comments=2)

    findings = [
        ReviewFinding(
            severity="low",
            category="maintainability",
            confidence=0.7,
            path="services/payment.py",
            line=10,
            side="RIGHT",
            title="Rename variable",
            message="Use snake_case.",
            rationale="Convention",
        ),
        ReviewFinding(
            severity="critical",
            category="security",
            confidence=0.99,
            path="services/payment.py",
            line=11,
            side="RIGHT",
            title="SQL Injection",
            message="Sanitize input before query.",
            rationale="Critical vulnerability",
        ),
        ReviewFinding(
            severity="high",
            category="correctness",
            confidence=0.9,
            path="services/payment.py",
            line=12,
            side="RIGHT",
            title="Missing transaction rollback",
            message="Wrap in try/except with rollback.",
            rationale="Reliability",
        ),
        ReviewFinding(
            severity="medium",
            category="performance",
            confidence=0.8,
            path="services/auth.py",
            line=50,
            side="RIGHT",
            title="N+1 query",
            message="Eager load roles.",
            rationale="Performance",
        ),
    ]

    review_result = ReviewResult(
        summary="Multiple findings with varying severity.",
        overall_risk="critical",
        findings=findings,
        team_conventions_applied=[],
        memory_influence_summary=[],
        uncertainty_notes=[],
    )

    res = await service.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )

    assert res["inline_count"] == 2
    assert res["unplaced_count"] == 2

    reviews = await gh.list_reviews("test-owner", "test-repo", 101)
    posted_comments = reviews[0]["comments"]
    assert len(posted_comments) == 2
    # Verify the 2 comments placed inline are CRITICAL and HIGH
    severities_posted = [c["body"] for c in posted_comments]
    assert any("[CRITICAL]" in s for s in severities_posted)
    assert any("[HIGH]" in s for s in severities_posted)
    assert not any("[LOW]" in s for s in severities_posted)


@pytest.mark.asyncio
async def test_publish_review_line_out_of_hunk_filtering(diff_context, sample_memories):
    gh = MockGitHubClient()
    service = PublishingService(client=gh, max_inline_comments=5)

    findings = [
        # Line 999 is outside valid_lines ([10, 11, 12, 13, 14, 15])
        ReviewFinding(
            severity="high",
            category="correctness",
            confidence=0.9,
            path="services/payment.py",
            line=999,
            side="RIGHT",
            title="Out of hunk line finding",
            message="Bug outside modified lines",
            rationale="Rationale",
        ),
        # Path not in PR
        ReviewFinding(
            severity="high",
            category="correctness",
            confidence=0.9,
            path="nonexistent/file.py",
            line=10,
            side="RIGHT",
            title="File not in PR",
            message="Bug in unmodified file",
            rationale="Rationale",
        ),
        # Line is None (general file finding)
        ReviewFinding(
            severity="medium",
            category="architecture",
            confidence=0.85,
            path="services/auth.py",
            line=None,
            side="RIGHT",
            title="Module architecture issue",
            message="Whole module needs refactor",
            rationale="Rationale",
        ),
    ]

    review_result = ReviewResult(
        summary="Findings that cannot be anchored to diff lines.",
        overall_risk="high",
        findings=findings,
        team_conventions_applied=[],
        memory_influence_summary=[],
        uncertainty_notes=[],
    )

    res = await service.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )

    # 0 inline comments placed, all 3 unplaced
    assert res["inline_count"] == 0
    assert res["unplaced_count"] == 3

    # But review body still contains all 3 findings!
    reviews = await gh.list_reviews("test-owner", "test-repo", 101)
    body = reviews[0]["body"]
    assert "Out of hunk line finding" in body
    assert "File not in PR" in body
    assert "Module architecture issue" in body


@pytest.mark.asyncio
async def test_publish_review_422_fallback_to_general(diff_context, sample_memories):
    gh = MockGitHubClient()
    gh.simulate_422_on_inline = True  # Triggers 422 error on review with comments

    service = PublishingService(client=gh, max_inline_comments=5)

    findings = [
        ReviewFinding(
            severity="high",
            category="architecture",
            confidence=0.95,
            path="services/payment.py",
            line=12,
            side="RIGHT",
            title="Direct DB Access",
            message="Use repository pattern",
            rationale="Rationale",
        )
    ]

    review_result = ReviewResult(
        summary="PR review needing fallback.",
        overall_risk="medium",
        findings=findings,
        team_conventions_applied=[],
        memory_influence_summary=[],
        uncertainty_notes=[],
    )

    res = await service.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )

    # Successfully fell back to top-level review without inline comments
    assert res["fallback_to_general"] is True
    assert res["inline_count"] == 0
    assert res["unplaced_count"] == 1

    reviews = await gh.list_reviews("test-owner", "test-repo", 101)
    assert len(reviews) == 1
    assert reviews[0]["comments"] == []
    assert "Direct DB Access" in reviews[0]["body"]


@pytest.mark.asyncio
async def test_publish_review_zero_findings(diff_context, sample_memories):
    gh = MockGitHubClient()
    service = PublishingService(client=gh)

    review_result = ReviewResult(
        summary="Clean PR with no defects.",
        overall_risk="low",
        findings=[],
        team_conventions_applied=["Follows repository pattern"],
        memory_influence_summary=["Verified against past memories"],
        uncertainty_notes=[],
    )

    res = await service.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )

    assert res["inline_count"] == 0
    assert res["unplaced_count"] == 0
    assert res["fallback_to_general"] is False

    reviews = await gh.list_reviews("test-owner", "test-repo", 101)
    assert len(reviews) == 1
    assert "No high-signal defects or team convention violations identified" in reviews[0]["body"]


@pytest.mark.asyncio
async def test_publish_review_permission_error_fails_fast(diff_context, sample_memories):
    gh = MockGitHubClient()
    gh.simulate_permission_error = True

    service = PublishingService(client=gh)

    review_result = ReviewResult(
        summary="Review.",
        overall_risk="low",
        findings=[],
        team_conventions_applied=[],
        memory_influence_summary=[],
        uncertainty_notes=[],
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await service.publish_review(
            owner="test-owner",
            repo="test-repo",
            pr_number=101,
            head_sha="sha_head_12345",
            review_result=review_result,
            diff_context=diff_context,
            memories=sample_memories,
        )

    assert "403 Forbidden" in str(exc_info.value)
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_publish_review_request_changes_behavior(diff_context, sample_memories):
    gh = MockGitHubClient()

    findings = [
        ReviewFinding(
            severity="critical",
            category="security",
            confidence=0.99,
            path="services/payment.py",
            line=11,
            side="RIGHT",
            title="Remote code execution",
            message="Insecure eval usage",
            rationale="Critical security vulnerability",
        )
    ]

    review_result = ReviewResult(
        summary="Critical security defect detected.",
        overall_risk="critical",
        findings=findings,
        team_conventions_applied=[],
        memory_influence_summary=[],
        uncertainty_notes=[],
    )

    # 1. When request_changes_on_critical is False (default) -> event is COMMENT
    service_default = PublishingService(client=gh, request_changes_on_critical=False)
    res1 = await service_default.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )
    assert res1["event"] == "COMMENT"

    # 2. When request_changes_on_critical is True -> event is REQUEST_CHANGES
    service_request_changes = PublishingService(client=gh, request_changes_on_critical=True)
    res2 = await service_request_changes.publish_review(
        owner="test-owner",
        repo="test-repo",
        pr_number=101,
        head_sha="sha_head_12345",
        review_result=review_result,
        diff_context=diff_context,
        memories=sample_memories,
    )
    assert res2["event"] == "REQUEST_CHANGES"
