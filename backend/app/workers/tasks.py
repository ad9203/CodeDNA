"""Background worker tasks for executing review orchestration outside request loop."""

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.orchestration_service import OrchestrationService

logger = get_logger("app.workers.tasks")


async def run_review_orchestration_task(
    owner: str,
    repo: str,
    pr_number: int,
    delivery_id: str,
    head_sha: str,
    orchestrator: OrchestrationService | None = None,
) -> None:
    """Async background task to execute pull request review with persistent memory."""
    active_orchestrator = orchestrator or OrchestrationService()
    async with AsyncSessionLocal() as session:
        try:
            logger.info(
                "starting_background_review_task",
                repo=f"{owner}/{repo}",
                pr=pr_number,
                delivery_id=delivery_id,
            )
            await active_orchestrator.process_pull_request_review(
                session=session,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                delivery_id=delivery_id,
                head_sha=head_sha,
                publish_to_github=True,
            )
        except Exception as e:
            logger.error(
                "background_review_task_failed",
                repo=f"{owner}/{repo}",
                pr=pr_number,
                error=str(e),
            )
