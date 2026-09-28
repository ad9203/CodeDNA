"""Unit tests for Hindsight memory integration and graceful degradation."""

import pytest

from app.integrations.hindsight_client import MockHindsightClient
from app.schemas.diff import ChangedFile, PRDiffContext
from app.services.memory_service import MemoryService


@pytest.fixture
def mock_hindsight():
    client = MockHindsightClient()
    # Seed memories for repository "acme/commerce"
    bank_id = "codedna:acme:commerce"
    client.seed_memory(
        bank_id=bank_id,
        text="All service methods must validate incoming request boundaries before repository access.",
        source_type="team_rule",
        tags=["architecture", "validation"],
        relevance=0.94,
    )
    client.seed_memory(
        bank_id=bank_id,
        text="INC-12 Postmortem: Payment timeout caused by unpooled DB connection acquisition.",
        source_type="incident_context",
        tags=["incident", "payments"],
        relevance=0.89,
    )
    return client


@pytest.fixture
def sample_diff_context():
    return PRDiffContext(
        repo="acme/commerce",
        pr_number=42,
        title="Refactor payment gateway interface",
        base_sha="base_sha_123",
        head_sha="head_sha_456",
        files=[
            ChangedFile(
                path="services/payment_service.py",
                status="modified",
                additions=15,
                deletions=2,
                patch="@@ -1,5 +1,6 @@\n+import gateway\n",
                language="python",
            )
        ],
        total_files=1,
        total_additions=15,
        total_deletions=2,
    )


def test_bank_id_generation_and_tenant_isolation():
    # Single tenant / local
    bank1 = MemoryService.get_bank_id("Acme", "Commerce")
    assert bank1 == "codedna:acme:commerce"

    # Multi-tenant / enterprise isolation
    bank2 = MemoryService.get_bank_id("Acme", "Commerce", tenant_id="tenant_alpha")
    bank3 = MemoryService.get_bank_id("Acme", "Commerce", tenant_id="tenant_beta")
    assert bank2 != bank3
    assert bank2 == "codedna:tenant_alpha:acme:commerce"
    assert bank3 == "codedna:tenant_beta:acme:commerce"


def test_sanitize_memory_text_strips_html_and_collapses_whitespace():
    raw_html_text = (
        "<script>alert('xss')</script><b>Team rule:</b> Always use Decimal.\n\n\n\nExtra lines"
    )
    sanitized = MemoryService.sanitize_memory_text(raw_html_text)
    assert "<script>" not in sanitized
    assert "<b>" not in sanitized
    assert "alert('xss')" in sanitized
    assert "Team rule: Always use Decimal." in sanitized
    assert "\n\n\n\n" not in sanitized


def test_build_recall_query_contains_paths_and_architecture_hints(sample_diff_context):
    query = MemoryService.build_recall_query(sample_diff_context)
    assert "Repository: acme/commerce" in query
    assert "Changed files: services/payment_service.py" in query
    assert "service-layer" in query
    assert "billing/payments" in query
    assert "Current PR Title: Refactor payment gateway interface" in query


@pytest.mark.asyncio
async def test_recall_for_pr_success(mock_hindsight: MockHindsightClient, sample_diff_context):
    service = MemoryService(client=mock_hindsight)
    result = await service.recall_for_pr("acme", "commerce", sample_diff_context)

    assert result.status == "ok"
    assert len(result.memories) == 2
    assert result.memories[0].source_type == "team_rule"
    assert "validate incoming request boundaries" in result.memories[0].text
    assert "INC-12" in result.memories[1].text
    assert "RECALLED TEAM MEMORY" in result.formatted_context


@pytest.mark.asyncio
async def test_recall_for_different_repo_isolated(
    mock_hindsight: MockHindsightClient, sample_diff_context
):
    # Repo with no memories in its bank
    service = MemoryService(client=mock_hindsight)
    result = await service.recall_for_pr("other_org", "other_repo", sample_diff_context)

    assert result.status == "empty"
    assert len(result.memories) == 0
    assert "No previous team memories found" in result.formatted_context


@pytest.mark.asyncio
async def test_graceful_degradation_on_hindsight_failure(
    mock_hindsight: MockHindsightClient, sample_diff_context
):
    mock_hindsight.should_fail = True
    service = MemoryService(client=mock_hindsight)

    # Should not raise exception; must degrade cleanly to stateless mode
    result = await service.recall_for_pr("acme", "commerce", sample_diff_context)

    assert result.status == "degraded"
    assert len(result.memories) == 0
    assert (
        "degraded" in result.formatted_context.lower()
        or "stateless" in result.formatted_context.lower()
    )


@pytest.mark.asyncio
async def test_retain_review_learning_and_incident_context(mock_hindsight: MockHindsightClient):
    service = MemoryService(client=mock_hindsight)

    # Retain team rule
    ok1 = await service.retain_review_learning(
        owner="acme",
        repo="commerce",
        content="Team decision: do not suggest Optional in Java billing classes.",
        context="PR #41 review decision",
        memory_type="review_decision",
        tags=["java", "billing"],
    )
    assert ok1 is True
    assert len(mock_hindsight.calls_retain) == 1
    call = mock_hindsight.calls_retain[0]
    assert call["bank_id"] == "codedna:acme:commerce"
    assert "review_decision" in call["tags"]

    # Retain incident context
    ok2 = await service.retain_incident_context(
        owner="acme",
        repo="commerce",
        incident_id="INC-99",
        summary="Redis memory exhaustion caused login outage",
        postmortem_notes="Configure maxmemory policy to allkeys-lru",
    )
    assert ok2 is True
    assert len(mock_hindsight.calls_retain) == 2
    call_inc = mock_hindsight.calls_retain[1]
    assert "incident" in call_inc["tags"]
    assert "INC-99" in call_inc["tags"]
