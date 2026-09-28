"""Repository pattern for database access and review lifecycle persistence."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    MemoryAudit,
    PullRequest,
    Repository,
    ReviewFeedback,
    ReviewFinding,
    ReviewRun,
    WebhookDelivery,
    utcnow,
)


class RepositoryRepo:
    @staticmethod
    async def get_by_full_name(session: AsyncSession, full_name: str) -> Repository | None:
        stmt = select(Repository).where(Repository.full_name == full_name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        owner: str,
        name: str,
        default_branch: str = "main",
    ) -> Repository:
        full_name = f"{owner}/{name}"
        repo = await RepositoryRepo.get_by_full_name(session, full_name)
        if not repo:
            repo = Repository(
                owner=owner,
                name=name,
                full_name=full_name,
                default_branch=default_branch,
            )
            session.add(repo)
            await session.flush()
        return repo

    @staticmethod
    async def list_all(session: AsyncSession) -> Sequence[Repository]:
        stmt = select(Repository).order_by(Repository.full_name)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_with_metrics(session: AsyncSession) -> list[dict[str, Any]]:
        stmt = (
            select(
                Repository,
                func.count(func.distinct(PullRequest.id)).label("pr_count"),
                func.count(func.distinct(ReviewRun.id)).label("review_count"),
                func.max(ReviewRun.started_at).label("last_active_at"),
            )
            .outerjoin(PullRequest, PullRequest.repository_id == Repository.id)
            .outerjoin(ReviewRun, ReviewRun.pull_request_id == PullRequest.id)
            .group_by(Repository.id)
            .order_by(Repository.full_name)
        )
        result = await session.execute(stmt)
        items: list[dict[str, Any]] = []
        for repo, pr_count, review_count, last_active in result.all():
            items.append(
                {
                    "id": repo.id,
                    "owner": repo.owner,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "default_branch": repo.default_branch,
                    "pr_count": pr_count,
                    "review_count": review_count,
                    "created_at": repo.created_at,
                    "last_active_at": last_active or repo.created_at,
                }
            )
        return items


class PullRequestRepo:
    @staticmethod
    async def get_by_repo_and_number(
        session: AsyncSession, repository_id: str, pr_number: int
    ) -> PullRequest | None:
        stmt = select(PullRequest).where(
            PullRequest.repository_id == repository_id,
            PullRequest.github_pr_number == pr_number,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        repository_id: str,
        github_pr_number: int,
        title: str,
        author_login: str,
        head_sha: str,
        base_sha: str,
        html_url: str,
    ) -> PullRequest:
        pr = await PullRequestRepo.get_by_repo_and_number(session, repository_id, github_pr_number)
        if not pr:
            pr = PullRequest(
                repository_id=repository_id,
                github_pr_number=github_pr_number,
                title=title,
                author_login=author_login,
                head_sha=head_sha,
                base_sha=base_sha,
                html_url=html_url,
            )
            session.add(pr)
            await session.flush()
        else:
            # Update latest head sha and title if PR synchronized
            pr.head_sha = head_sha
            pr.base_sha = base_sha
            pr.title = title
            pr.updated_at = utcnow()
            await session.flush()
        return pr


class WebhookDeliveryRepo:
    @staticmethod
    async def is_duplicate(session: AsyncSession, delivery_id: str) -> bool:
        stmt = select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def record_delivery(
        session: AsyncSession,
        delivery_id: str,
        event_name: str,
        action: str | None = None,
    ) -> WebhookDelivery:
        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            event_name=event_name,
            action=action,
            received_at=utcnow(),
            status="received",
        )
        session.add(delivery)
        await session.flush()
        return delivery

    @staticmethod
    async def update_status(
        session: AsyncSession, delivery_id: str, status: str
    ) -> WebhookDelivery | None:
        stmt = select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
        result = await session.execute(stmt)
        delivery = result.scalar_one_or_none()
        if delivery:
            delivery.status = status
            delivery.processed_at = utcnow()
            await session.flush()
        return delivery


class ReviewRunRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        pull_request_id: str,
        delivery_id: str,
        status: str = "pending",
    ) -> ReviewRun:
        run = ReviewRun(
            pull_request_id=pull_request_id,
            delivery_id=delivery_id,
            status=status,
            started_at=utcnow(),
        )
        session.add(run)
        await session.flush()
        return run

    @staticmethod
    async def get_by_id(session: AsyncSession, review_run_id: str) -> ReviewRun | None:
        stmt = select(ReviewRun).where(ReviewRun.id == review_run_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_with_repository(session: AsyncSession, review_run_id: str) -> ReviewRun | None:
        stmt = (
            select(ReviewRun)
            .options(selectinload(ReviewRun.pull_request).selectinload(PullRequest.repository))
            .where(ReviewRun.id == review_run_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_delivery_id(session: AsyncSession, delivery_id: str) -> ReviewRun | None:
        stmt = select(ReviewRun).where(ReviewRun.delivery_id == delivery_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_recent(
        session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> Sequence[ReviewRun]:
        stmt = select(ReviewRun).order_by(desc(ReviewRun.started_at)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def list_filtered(
        session: AsyncSession,
        repository_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ReviewRun]:
        stmt = (
            select(ReviewRun)
            .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
            .options(selectinload(ReviewRun.pull_request).selectinload(PullRequest.repository))
        )
        if repository_id:
            stmt = stmt.where(PullRequest.repository_id == repository_id)
        if status:
            stmt = stmt.where(ReviewRun.status == status)

        stmt = stmt.order_by(desc(ReviewRun.started_at)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def count_filtered(
        session: AsyncSession,
        repository_id: str | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count(ReviewRun.id)).join(
            PullRequest, ReviewRun.pull_request_id == PullRequest.id
        )
        if repository_id:
            stmt = stmt.where(PullRequest.repository_id == repository_id)
        if status:
            stmt = stmt.where(ReviewRun.status == status)
        result = await session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_detailed_by_id(session: AsyncSession, review_run_id: str) -> ReviewRun | None:
        stmt = (
            select(ReviewRun)
            .options(
                selectinload(ReviewRun.pull_request).selectinload(PullRequest.repository),
                selectinload(ReviewRun.findings),
                selectinload(ReviewRun.memory_audits),
                selectinload(ReviewRun.feedback),
            )
            .where(ReviewRun.id == review_run_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def complete_run(
        session: AsyncSession,
        review_run_id: str,
        status: str,
        total_duration_ms: int | None = None,
        finding_count: int = 0,
        memory_recalled_count: int = 0,
        error_code: str | None = None,
        error_message_safe: str | None = None,
    ) -> ReviewRun | None:
        run = await ReviewRunRepo.get_by_id(session, review_run_id)
        if run:
            run.status = status
            run.completed_at = utcnow()
            run.total_duration_ms = total_duration_ms
            run.finding_count = finding_count
            run.memory_recalled_count = memory_recalled_count
            run.error_code = error_code
            run.error_message_safe = error_message_safe
            await session.flush()
        return run


class ReviewFindingRepo:
    @staticmethod
    async def create_many(
        session: AsyncSession,
        review_run_id: str,
        findings_data: list[dict[str, Any]],
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        for item in findings_data:
            finding = ReviewFinding(
                review_run_id=review_run_id,
                severity=item["severity"],
                category=item["category"],
                confidence=item.get("confidence", 1.0),
                path=item["path"],
                line=item.get("line"),
                side=item.get("side"),
                title=item["title"],
                message=item["message"],
                rationale=item["rationale"],
                suggestion=item.get("suggestion"),
                published_comment_id=item.get("published_comment_id"),
                feedback_status=item.get("feedback_status"),
            )
            session.add(finding)
            findings.append(finding)
        await session.flush()
        return findings

    @staticmethod
    async def list_by_run(session: AsyncSession, review_run_id: str) -> Sequence[ReviewFinding]:
        stmt = select(ReviewFinding).where(ReviewFinding.review_run_id == review_run_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, finding_id: str) -> ReviewFinding | None:
        stmt = select(ReviewFinding).where(ReviewFinding.id == finding_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_feedback_status(
        session: AsyncSession, finding_id: str, feedback_status: str
    ) -> ReviewFinding | None:
        stmt = select(ReviewFinding).where(ReviewFinding.id == finding_id)
        result = await session.execute(stmt)
        finding = result.scalar_one_or_none()
        if finding:
            finding.feedback_status = feedback_status
            await session.flush()
        return finding


class MemoryAuditRepo:
    @staticmethod
    async def create_many(
        session: AsyncSession,
        review_run_id: str,
        memories_data: list[dict[str, Any]],
    ) -> list[MemoryAudit]:
        audits: list[MemoryAudit] = []
        for idx, item in enumerate(memories_data):
            audit = MemoryAudit(
                review_run_id=review_run_id,
                memory_source_id=item.get("memory_source_id") or item.get("id"),
                memory_type=item.get("memory_type") or item.get("type"),
                memory_text_sanitized=item["memory_text_sanitized"]
                if "memory_text_sanitized" in item
                else item.get("text", ""),
                relevance_context=item.get("relevance_context"),
                relevance_score=item.get("relevance")
                if "relevance" in item
                else item.get("relevance_score"),
                rank_order=item.get("rank_order", idx),
            )
            session.add(audit)
            audits.append(audit)
        await session.flush()
        return audits

    @staticmethod
    async def list_by_run(session: AsyncSession, review_run_id: str) -> Sequence[MemoryAudit]:
        stmt = (
            select(MemoryAudit)
            .where(MemoryAudit.review_run_id == review_run_id)
            .order_by(MemoryAudit.rank_order)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


class ReviewFeedbackRepo:
    @staticmethod
    async def record_feedback(
        session: AsyncSession,
        review_run_id: str,
        actor_login: str,
        outcome: str,
        feedback_text: str,
        finding_id: str | None = None,
        source_url: str | None = None,
    ) -> ReviewFeedback:
        fb = ReviewFeedback(
            review_run_id=review_run_id,
            finding_id=finding_id,
            actor_login=actor_login,
            outcome=outcome,
            feedback_text=feedback_text,
            source_url=source_url,
            created_at=utcnow(),
        )
        session.add(fb)
        if finding_id:
            await ReviewFindingRepo.update_feedback_status(session, finding_id, outcome)
        await session.flush()
        return fb

    @staticmethod
    async def list_by_run(session: AsyncSession, review_run_id: str) -> Sequence[ReviewFeedback]:
        stmt = (
            select(ReviewFeedback)
            .where(ReviewFeedback.review_run_id == review_run_id)
            .order_by(ReviewFeedback.created_at)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


class DashboardStatsRepo:
    @staticmethod
    async def get_overview_stats(session: AsyncSession) -> dict[str, Any]:
        # 1. Total repos
        repo_count_res = await session.execute(select(func.count(Repository.id)))
        total_repos = repo_count_res.scalar() or 0

        # 2. Total reviews & duration & memories
        review_stats_res = await session.execute(
            select(
                func.count(ReviewRun.id),
                func.avg(ReviewRun.total_duration_ms),
                func.sum(ReviewRun.memory_recalled_count),
            )
        )
        total_reviews, avg_duration, total_memories = review_stats_res.one()
        total_reviews = total_reviews or 0
        total_memories = int(total_memories or 0)

        # 3. Findings total & breakdown by severity
        findings_count_res = await session.execute(
            select(ReviewFinding.severity, func.count(ReviewFinding.id)).group_by(
                ReviewFinding.severity
            )
        )
        findings_by_sev = {str(sev): int(count) for sev, count in findings_count_res.all()}
        total_findings = sum(findings_by_sev.values())

        # 4. Feedback metrics
        feedback_res = await session.execute(
            select(ReviewFeedback.outcome, func.count(ReviewFeedback.id)).group_by(
                ReviewFeedback.outcome
            )
        )
        feedback_by_outcome = {str(outcome): int(count) for outcome, count in feedback_res.all()}
        total_feedback = sum(feedback_by_outcome.values())
        accepted_count = feedback_by_outcome.get("accepted", 0)
        acceptance_rate = (
            round((accepted_count / total_feedback) * 100, 1) if total_feedback > 0 else 0.0
        )

        return {
            "total_repositories": total_repos,
            "total_reviews": total_reviews,
            "total_findings": total_findings,
            "total_memories_recalled": total_memories,
            "findings_by_severity": findings_by_sev,
            "feedback_metrics": {
                "total": total_feedback,
                "by_outcome": feedback_by_outcome,
                "acceptance_rate": acceptance_rate,
            },
            "avg_duration_ms": round(float(avg_duration), 1) if avg_duration else None,
        }
