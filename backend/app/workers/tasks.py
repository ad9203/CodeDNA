"""Background worker tasks for executing review orchestration outside request loop."""

from typing import Any

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
    should_close = orchestrator is None
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
        finally:
            if should_close and hasattr(active_orchestrator, "aclose"):
                await active_orchestrator.aclose()


async def run_comment_learning_task(
    owner: str,
    repo: str,
    comment_body: str,
    actor_login: str,
    pr_number: int,
    outcome: str = "rejected",
    learning_service: Any = None,
) -> bool:
    """Async background task to process human review comments into Hindsight persistent memory."""
    from app.services.learning_service import LearningService

    active_service = learning_service or LearningService()
    should_close = learning_service is None
    try:
        logger.info(
            "starting_comment_learning_task",
            repo=f"{owner}/{repo}",
            pr=pr_number,
            actor=actor_login,
        )
        retained = await active_service.process_feedback_outcome(
            owner=owner,
            repo=repo,
            finding=None,
            outcome=outcome,
            feedback_text=comment_body,
            actor_login=actor_login,
        )
        logger.info(
            "comment_learning_task_completed",
            repo=f"{owner}/{repo}",
            pr=pr_number,
            actor=actor_login,
            retained=retained,
        )
        return retained
    except Exception as e:
        logger.error(
            "comment_learning_task_failed",
            repo=f"{owner}/{repo}",
            pr=pr_number,
            actor=actor_login,
            error=str(e),
        )
        return False
    finally:
        if should_close and hasattr(active_service, "aclose"):
            await active_service.aclose()
