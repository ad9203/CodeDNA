import json
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger, set_trace_context
from app.core.security import verify_github_signature
from app.db.repositories import (
    PullRequestRepo,
    RepositoryRepo,
    ReviewRunRepo,
    WebhookDeliveryRepo,
)
from app.schemas.common import WebhookIntakeResponse
from app.schemas.github import (
    WebhookIssueCommentEvent,
    WebhookPullRequestEvent,
    WebhookPullRequestReviewEvent,
    WebhookReviewCommentEvent,
)
from app.workers.tasks import run_review_orchestration_task

logger = get_logger("app.api.webhook")
router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.post(
    "/github",
    response_model=WebhookIntakeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def handle_github_webhook(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    session: AsyncSession = Depends(get_db),
) -> WebhookIntakeResponse:
    """Secure endpoint for receiving and processing GitHub Webhook events."""
    raw_body = await request.body()
    delivery_id = x_github_delivery or str(uuid.uuid4())
    event_name = x_github_event or "unknown"

    set_trace_context(delivery_id=delivery_id, stage="webhook_intake")

    # Step 1: Signature Verification (HMAC-SHA256 over raw_body)
    configured_secret = (
        settings.github_webhook_secret.get_secret_value()
        if settings.github_webhook_secret
        else None
    )

    if configured_secret is not None:
        if not x_hub_signature_256 or not verify_github_signature(
            raw_body, x_hub_signature_256, configured_secret
        ):
            logger.warning(
                "webhook_unauthorized",
                delivery_id=delivery_id,
                github_event=event_name,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing webhook signature",
            )

    # Step 2: Parse raw JSON body
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except Exception as e:
        logger.error("webhook_invalid_json", delivery_id=delivery_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in request body",
        ) from e

    action = payload.get("action")

    # Step 3: Delivery Idempotency Check
    if await WebhookDeliveryRepo.is_duplicate(session, delivery_id):
        logger.info(
            "webhook_duplicate_delivery",
            delivery_id=delivery_id,
            github_event=event_name,
        )
        response.status_code = status.HTTP_200_OK
        return WebhookIntakeResponse(
            delivery_id=delivery_id,
            event=event_name,
            action=action,
            status="duplicate",
            message="Event delivery already received",
        )

    # Record delivery
    await WebhookDeliveryRepo.record_delivery(
        session,
        delivery_id=delivery_id,
        event_name=event_name,
        action=action,
    )

    # Step 4: Handle ping event
    if event_name == "ping":
        await WebhookDeliveryRepo.update_status(session, delivery_id, "processed")
        await session.commit()
        response.status_code = status.HTTP_200_OK
        return WebhookIntakeResponse(
            delivery_id=delivery_id,
            event="ping",
            action="ping",
            status="processed",
            message="Webhook ping acknowledged successfully",
        )

    # Step 5: Handle pull_request events
    if event_name == "pull_request":
        if action in {"opened", "synchronize"}:
            try:
                pr_event = WebhookPullRequestEvent.model_validate(payload)
            except ValidationError as ve:
                logger.error("webhook_pr_validation_failed", error=str(ve))
                await WebhookDeliveryRepo.update_status(session, delivery_id, "failed")
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pull_request payload: {ve.errors()}",
                ) from ve

            repo_data = pr_event.repository
            pr_data = pr_event.pull_request

            # Upsert Repository
            repo_record = await RepositoryRepo.get_or_create(
                session,
                owner=repo_data.owner_login,
                name=repo_data.name,
                default_branch=repo_data.default_branch,
            )

            # Upsert Pull Request
            pr_record = await PullRequestRepo.get_or_create(
                session,
                repository_id=repo_record.id,
                github_pr_number=pr_data.number,
                title=pr_data.title,
                author_login=pr_data.user.login,
                head_sha=pr_data.head.sha,
                base_sha=pr_data.base.sha,
                html_url=pr_data.html_url,
            )

            # Create Pending Review Run
            await ReviewRunRepo.create(
                session,
                pull_request_id=pr_record.id,
                delivery_id=delivery_id,
                status="pending",
            )

            await WebhookDeliveryRepo.update_status(session, delivery_id, "enqueued")
            await session.commit()

            # Schedule background review task
            background_tasks.add_task(
                run_review_orchestration_task,
                owner=repo_data.owner_login,
                repo=repo_data.name,
                pr_number=pr_data.number,
                delivery_id=delivery_id,
                head_sha=pr_data.head.sha,
            )

            logger.info(
                "webhook_pr_enqueued",
                delivery_id=delivery_id,
                repo=repo_record.full_name,
                pr=pr_data.number,
                action=action,
            )

            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="enqueued",
                message=f"Pull request #{pr_data.number} {action} enqueued for review",
            )
        else:
            await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
            await session.commit()
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="ignored",
                message=f"Pull request action '{action}' is not supported for automatic review",
            )

    # Step 6: Handle pull_request_review (Learning Loop)
    if event_name == "pull_request_review":
        if action == "submitted":
            try:
                review_event = WebhookPullRequestReviewEvent.model_validate(payload)
            except ValidationError as ve:
                logger.error("webhook_review_validation_failed", error=str(ve))
                await WebhookDeliveryRepo.update_status(session, delivery_id, "failed")
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid pull_request_review payload",
                ) from ve

            await WebhookDeliveryRepo.update_status(session, delivery_id, "enqueued")
            await session.commit()
            logger.info(
                "webhook_review_enqueued",
                delivery_id=delivery_id,
                pr=review_event.pull_request.number,
                state=review_event.review.state,
            )
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="enqueued",
                message="Review submission enqueued for learning loop",
            )
        else:
            await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
            await session.commit()
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="ignored",
                message=f"Review action '{action}' ignored",
            )

    # Step 7: Handle pull_request_review_comment (Learning Loop)
    if event_name == "pull_request_review_comment":
        if action in {"created", "edited", "deleted"}:
            try:
                WebhookReviewCommentEvent.model_validate(payload)
            except ValidationError as ve:
                logger.error("webhook_review_comment_validation_failed", error=str(ve))
                await WebhookDeliveryRepo.update_status(session, delivery_id, "failed")
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid review comment payload",
                ) from ve

            await WebhookDeliveryRepo.update_status(session, delivery_id, "enqueued")
            await session.commit()
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="enqueued",
                message="Review comment captured for learning loop",
            )
        else:
            await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
            await session.commit()
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="ignored",
                message=f"Comment action '{action}' ignored",
            )

    # Step 8: Handle issue_comment (Only if on PR)
    if event_name == "issue_comment":
        if action == "created":
            try:
                issue_event = WebhookIssueCommentEvent.model_validate(payload)
            except ValidationError as ve:
                logger.error("webhook_issue_comment_validation_failed", error=str(ve))
                await WebhookDeliveryRepo.update_status(session, delivery_id, "failed")
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid issue comment payload",
                ) from ve

            if issue_event.issue.pull_request is not None:
                await WebhookDeliveryRepo.update_status(session, delivery_id, "enqueued")
                await session.commit()
                return WebhookIntakeResponse(
                    delivery_id=delivery_id,
                    event=event_name,
                    action=action,
                    status="enqueued",
                    message="PR conversation comment captured for learning loop",
                )
            else:
                await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
                await session.commit()
                return WebhookIntakeResponse(
                    delivery_id=delivery_id,
                    event=event_name,
                    action=action,
                    status="ignored",
                    message="Issue comment is on an issue, not a pull request",
                )
        else:
            await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
            await session.commit()
            return WebhookIntakeResponse(
                delivery_id=delivery_id,
                event=event_name,
                action=action,
                status="ignored",
                message=f"Issue comment action '{action}' ignored",
            )

    # Unsupported events
    await WebhookDeliveryRepo.update_status(session, delivery_id, "ignored")
    await session.commit()
    return WebhookIntakeResponse(
        delivery_id=delivery_id,
        event=event_name,
        action=action,
        status="ignored",
        message=f"Event '{event_name}' is not handled",
    )
