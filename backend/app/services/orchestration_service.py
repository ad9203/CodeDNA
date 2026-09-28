"""Master review orchestrator: connects diff, memory, LLM, persistence, publishing, and learning."""

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalServiceError
from app.core.logging import get_logger, set_trace_context
from app.db.repositories import (
    MemoryAuditRepo,
    PullRequestRepo,
    RepositoryRepo,
    ReviewFindingRepo,
    ReviewRunRepo,
)
from app.integrations.github_client import BaseGitHubClient, PyGitHubClient
from app.integrations.groq_client import BaseGroqClient, OfficialGroqClient
from app.integrations.hindsight_client import BaseHindsightClient, OfficialHindsightClient
from app.schemas.memory import MemoryRecallResult
from app.schemas.review import ReviewResult
from app.services.diff_service import DiffService
from app.services.learning_service import LearningService
from app.services.memory_service import MemoryService
from app.services.publishing_service import PublishingService
from app.services.review_service import ReviewService

logger = get_logger("app.services.orchestration")


class OrchestrationService:
    """End-to-end pull request review pipeline with persistent memory and graceful failure handling."""

    def __init__(
        self,
        github_client: BaseGitHubClient | None = None,
        hindsight_client: BaseHindsightClient | None = None,
        groq_client: BaseGroqClient | None = None,
    ):
        self.github_client = github_client or PyGitHubClient()
        self.memory_service = MemoryService(client=hindsight_client or OfficialHindsightClient())
        self.review_service = ReviewService(client=groq_client or OfficialGroqClient())
        self.publishing_service = PublishingService(client=self.github_client)
        self.learning_service = LearningService(memory_service=self.memory_service)

    async def process_pull_request_review(
        self,
        session: AsyncSession,
        owner: str,
        repo: str,
        pr_number: int,
        delivery_id: str,
        head_sha: str | None = None,
        publish_to_github: bool = True,
    ) -> dict[str, Any]:
        """Executes the full review lifecycle."""
        start_time = time.perf_counter()
        set_trace_context(delivery_id=delivery_id, repo=f"{owner}/{repo}", pr_number=pr_number)

        # Stage 1: Ensure repository and PR records exist
        repo_record = await RepositoryRepo.get_or_create(session, owner=owner, name=repo)
        pr_record = await PullRequestRepo.get_by_repo_and_number(session, repo_record.id, pr_number)

        # Stage 2: Create or retrieve ReviewRun record
        review_run = await ReviewRunRepo.get_by_delivery_id(session, delivery_id)
        if not review_run:
            if not pr_record:
                # Fetch metadata to create PR record if missing
                pr_meta = await self.github_client.get_pull_request(owner, repo, pr_number)
                pr_record = await PullRequestRepo.get_or_create(
                    session,
                    repository_id=repo_record.id,
                    github_pr_number=pr_number,
                    title=pr_meta.title,
                    author_login=pr_meta.author_login,
                    head_sha=pr_meta.head_sha,
                    base_sha=pr_meta.base_sha,
                    html_url=pr_meta.html_url,
                )
            review_run = await ReviewRunRepo.create(
                session, pull_request_id=pr_record.id, delivery_id=delivery_id, status="processing"
            )
            await session.commit()
        else:
            review_run.status = "processing"
            await session.commit()

        # Stage 3: Fetch PR changed files from GitHub
        set_trace_context(stage="github_fetch")
        try:
            pr_metadata = await self.github_client.get_pull_request(owner, repo, pr_number)
            changed_files = await self.github_client.get_pull_request_files(owner, repo, pr_number)
        except ExternalServiceError as ese:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            await ReviewRunRepo.complete_run(
                session,
                review_run_id=review_run.id,
                status="failed",
                total_duration_ms=duration_ms,
                error_code="GITHUB_FETCH_FAILED",
                error_message_safe=ese.message,
            )
            await session.commit()
            return {"status": "failed", "error": ese.message}

        effective_head_sha = head_sha or pr_metadata.head_sha

        # Stage 4: Normalize, sanitize, and bound the diff
        set_trace_context(stage="diff_extraction")
        diff_context = DiffService.build_diff_context(pr_metadata, changed_files)

        # Stage 5: Recall persistent memory from Hindsight
        set_trace_context(stage="memory_recall")
        recall_result: MemoryRecallResult = await self.memory_service.recall_for_pr(
            owner, repo, diff_context
        )
        is_degraded = recall_result.status == "degraded"

        # Stage 6: Generate structured review via Groq LLM
        set_trace_context(stage="groq_review")
        try:
            review_result: ReviewResult = await self.review_service.generate_review(
                diff_context=diff_context,
                memories=recall_result.memories,
            )
        except ExternalServiceError as ese:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            await ReviewRunRepo.complete_run(
                session,
                review_run_id=review_run.id,
                status="failed",
                total_duration_ms=duration_ms,
                error_code="GROQ_GENERATION_FAILED",
                error_message_safe=ese.message,
            )
            await session.commit()
            return {"status": "failed", "error": ese.message}

        # Stage 7: Persist review findings and memory audits to DB
        set_trace_context(stage="db_persistence")
        findings_payload = [
            {
                "severity": f.severity,
                "category": f.category,
                "confidence": f.confidence,
                "path": f.path,
                "line": f.line,
                "side": f.side,
                "title": f.title,
                "message": f.message,
                "rationale": f.rationale,
                "suggestion": f.suggestion,
            }
            for f in review_result.findings
        ]
        created_findings = await ReviewFindingRepo.create_many(
            session, review_run.id, findings_payload
        )

        memories_payload = [
            {
                "memory_source_id": m.memory_id,
                "memory_type": m.source_type,
                "memory_text_sanitized": m.text,
                "relevance_score": m.relevance,
                "rank_order": idx,
            }
            for idx, m in enumerate(recall_result.memories)
        ]
        await MemoryAuditRepo.create_many(session, review_run.id, memories_payload)
        await session.commit()

        # Stage 8: Publish to GitHub
        published_meta = None
        if publish_to_github:
            set_trace_context(stage="github_publish")
            try:
                published_meta = await self.publishing_service.publish_review(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    head_sha=effective_head_sha,
                    review_result=review_result,
                    diff_context=diff_context,
                    memories=recall_result.memories,
                )
            except ExternalServiceError as ese:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                await ReviewRunRepo.complete_run(
                    session,
                    review_run_id=review_run.id,
                    status="failed",
                    total_duration_ms=duration_ms,
                    finding_count=len(created_findings),
                    memory_recalled_count=len(recall_result.memories),
                    error_code="PUBLISH_FAILED",
                    error_message_safe=ese.message,
                )
                await session.commit()
                return {"status": "publish_failed", "error": ese.message}

        # Stage 9: Learning Loop (Reinforce conventions if applied)
        set_trace_context(stage="learning_loop")
        if review_result.team_conventions_applied:
            try:
                await self.learning_service.retain_review_applied_conventions(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    conventions=review_result.team_conventions_applied,
                )
            except Exception as e:
                logger.warn("learning_loop_reinforce_failed", error=str(e))

        # Stage 10: Complete Run
        final_status = "degraded" if is_degraded else "reviewed"
        total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        await ReviewRunRepo.complete_run(
            session,
            review_run_id=review_run.id,
            status=final_status,
            total_duration_ms=total_duration_ms,
            finding_count=len(created_findings),
            memory_recalled_count=len(recall_result.memories),
        )
        await session.commit()

        logger.info(
            "review_completed",
            delivery_id=delivery_id,
            repo=f"{owner}/{repo}",
            pr=pr_number,
            status=final_status,
            duration_ms=total_duration_ms,
            memory_recalled=len(recall_result.memories),
            findings=len(created_findings),
        )

        return {
            "status": final_status,
            "review_run_id": review_run.id,
            "findings_count": len(created_findings),
            "memory_recalled_count": len(recall_result.memories),
            "total_duration_ms": total_duration_ms,
            "published": published_meta is not None,
            "review_result": review_result.model_dump(),
        }
