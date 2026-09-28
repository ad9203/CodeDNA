"""Dashboard read API routes for UI inspection, memory audit trails, and metrics."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger, set_trace_context
from app.db.repositories import (
    DashboardStatsRepo,
    MemoryAuditRepo,
    RepositoryRepo,
    ReviewFindingRepo,
    ReviewRunRepo,
)
from app.schemas.dashboard import (
    DashboardOverviewStats,
    MemoryAuditDetail,
    RepositoryListItem,
    ReviewFindingDetail,
    ReviewRunDetailResponse,
    ReviewRunListItem,
    ReviewRunListResponse,
)

logger = get_logger("app.api.dashboard")
router = APIRouter(tags=["Dashboard"])


@router.get(
    "/repositories",
    response_model=list[RepositoryListItem],
    status_code=status.HTTP_200_OK,
)
async def list_repositories(
    session: AsyncSession = Depends(get_db),
) -> list[RepositoryListItem]:
    """Lists all monitored repositories with PR and review counts."""
    items = await RepositoryRepo.list_with_metrics(session)
    return [
        RepositoryListItem(
            id=item["id"],
            owner=item["owner"],
            name=item["name"],
            full_name=item["full_name"],
            default_branch=item["default_branch"],
            pr_count=item["pr_count"],
            review_count=item["review_count"],
            created_at=item["created_at"],
            last_active_at=item["last_active_at"],
        )
        for item in items
    ]


@router.get(
    "/reviews",
    response_model=ReviewRunListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_reviews(
    repository_id: str | None = Query(None, description="Filter by repository ID"),
    status_filter: str | None = Query(None, alias="status", description="Filter by review status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    session: AsyncSession = Depends(get_db),
) -> ReviewRunListResponse:
    """Lists reviews with pagination, PR metadata, and status filtering."""
    runs = await ReviewRunRepo.list_filtered(
        session=session,
        repository_id=repository_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    total = await ReviewRunRepo.count_filtered(
        session=session,
        repository_id=repository_id,
        status=status_filter,
    )

    items: list[ReviewRunListItem] = []
    for r in runs:
        pr = r.pull_request
        repo = pr.repository if pr else None
        items.append(
            ReviewRunListItem(
                id=r.id,
                delivery_id=r.delivery_id,
                status=r.status,
                started_at=r.started_at,
                completed_at=r.completed_at,
                total_duration_ms=r.total_duration_ms,
                finding_count=r.finding_count,
                memory_recalled_count=r.memory_recalled_count,
                repository_id=repo.id if repo else "",
                repository_name=repo.full_name if repo else "unknown",
                pr_number=pr.github_pr_number if pr else 0,
                pr_title=pr.title if pr else "Unknown PR",
                pr_author=pr.author_login if pr else "unknown",
                pr_html_url=pr.html_url if pr else "",
                head_sha=pr.head_sha if pr else "",
            )
        )

    return ReviewRunListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewRunDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_review_detail(
    review_id: str,
    session: AsyncSession = Depends(get_db),
) -> ReviewRunDetailResponse:
    """Fetches full review details including findings, memories recalled, and PR context."""
    run = await ReviewRunRepo.get_detailed_by_id(session, review_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    pr = run.pull_request
    repo = pr.repository if pr else None

    findings_detail = [
        ReviewFindingDetail(
            id=f.id,
            review_run_id=f.review_run_id,
            severity=f.severity,
            category=f.category,
            confidence=f.confidence,
            path=f.path,
            line=f.line,
            side=f.side,
            title=f.title,
            message=f.message,
            rationale=f.rationale,
            suggestion=f.suggestion,
            feedback_status=f.feedback_status,
        )
        for f in run.findings
    ]

    memories_detail = [
        MemoryAuditDetail(
            id=m.id,
            review_run_id=m.review_run_id,
            memory_source_id=m.memory_source_id,
            memory_type=m.memory_type,
            memory_text_sanitized=m.memory_text_sanitized,
            relevance_score=m.relevance_score,
            rank_order=m.rank_order,
            recall_timestamp=m.recall_timestamp,
        )
        for m in run.memory_audits
    ]

    return ReviewRunDetailResponse(
        id=run.id,
        delivery_id=run.delivery_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_ms=run.total_duration_ms,
        finding_count=run.finding_count,
        memory_recalled_count=run.memory_recalled_count,
        error_code=run.error_code,
        error_message_safe=run.error_message_safe,
        repository={
            "id": repo.id if repo else "",
            "owner": repo.owner if repo else "",
            "name": repo.name if repo else "",
            "full_name": repo.full_name if repo else "",
            "default_branch": repo.default_branch if repo else "",
        },
        pull_request={
            "id": pr.id if pr else "",
            "pr_number": pr.github_pr_number if pr else 0,
            "title": pr.title if pr else "",
            "author_login": pr.author_login if pr else "",
            "head_sha": pr.head_sha if pr else "",
            "base_sha": pr.base_sha if pr else "",
            "html_url": pr.html_url if pr else "",
        },
        findings=findings_detail,
        memories=memories_detail,
        feedback_count=len(run.feedback),
    )


@router.get(
    "/reviews/{review_id}/findings",
    response_model=list[ReviewFindingDetail],
    status_code=status.HTTP_200_OK,
)
async def list_review_findings(
    review_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[ReviewFindingDetail]:
    """Lists all findings identified for a specific review run."""
    run = await ReviewRunRepo.get_by_id(session, review_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    findings = await ReviewFindingRepo.list_by_run(session, review_id)
    return [
        ReviewFindingDetail(
            id=f.id,
            review_run_id=f.review_run_id,
            severity=f.severity,
            category=f.category,
            confidence=f.confidence,
            path=f.path,
            line=f.line,
            side=f.side,
            title=f.title,
            message=f.message,
            rationale=f.rationale,
            suggestion=f.suggestion,
            feedback_status=f.feedback_status,
        )
        for f in findings
    ]


@router.get(
    "/reviews/{review_id}/memory",
    response_model=list[MemoryAuditDetail],
    status_code=status.HTTP_200_OK,
)
async def list_review_memory_audits(
    review_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[MemoryAuditDetail]:
    """Lists all recalled memories that influenced this review run."""
    run = await ReviewRunRepo.get_by_id(session, review_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    memories = await MemoryAuditRepo.list_by_run(session, review_id)
    return [
        MemoryAuditDetail(
            id=m.id,
            review_run_id=m.review_run_id,
            memory_source_id=m.memory_source_id,
            memory_type=m.memory_type,
            memory_text_sanitized=m.memory_text_sanitized,
            relevance_score=m.relevance_score,
            rank_order=m.rank_order,
            recall_timestamp=m.recall_timestamp,
        )
        for m in memories
    ]


@router.get(
    "/stats/overview",
    response_model=DashboardOverviewStats,
    status_code=status.HTTP_200_OK,
)
async def get_overview_statistics(
    session: AsyncSession = Depends(get_db),
) -> DashboardOverviewStats:
    """Computes aggregate review metrics, severity breakdown, and feedback stats."""
    set_trace_context(stage="stats_overview")
    stats = await DashboardStatsRepo.get_overview_stats(session)
    return DashboardOverviewStats(**stats)
