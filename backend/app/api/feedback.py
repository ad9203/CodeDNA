"""API endpoints for human reviewer feedback and learning loop integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger, set_trace_context
from app.db.repositories import (
    ReviewFeedbackRepo,
    ReviewFindingRepo,
    ReviewRunRepo,
)
from app.schemas.feedback import (
    FindingFeedbackRequest,
    ReviewFeedbackListItem,
    ReviewFeedbackResponse,
)
from app.services.learning_service import LearningService

logger = get_logger("app.api.feedback")
router = APIRouter(prefix="/reviews", tags=["Feedback"])


@router.post(
    "/{review_id}/findings/{finding_id}/feedback",
    response_model=ReviewFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_finding_feedback(
    review_id: str,
    finding_id: str,
    payload: FindingFeedbackRequest,
    session: AsyncSession = Depends(get_db),
) -> ReviewFeedbackResponse:
    """Submits human reviewer feedback for an individual review finding."""
    set_trace_context(stage="feedback_intake")

    # 1. Verify review run and repository context
    review_run = await ReviewRunRepo.get_with_repository(session, review_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    # 2. Verify finding exists and belongs to this review run
    finding = await ReviewFindingRepo.get_by_id(session, finding_id)
    if not finding or finding.review_run_id != review_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found for review run '{review_id}'",
        )

    # 3. Record feedback in relational persistence
    feedback_record = await ReviewFeedbackRepo.record_feedback(
        session=session,
        review_run_id=review_id,
        finding_id=finding_id,
        actor_login=payload.actor_login,
        outcome=payload.outcome,
        feedback_text=payload.feedback_text,
        source_url=payload.source_url,
    )

    # 4. Process into Hindsight memory via LearningService
    owner = review_run.pull_request.repository.owner
    repo = review_run.pull_request.repository.name
    learning_service = LearningService()
    try:
        retained = await learning_service.process_feedback_outcome(
            owner=owner,
            repo=repo,
            finding=finding,
            outcome=payload.outcome,
            feedback_text=payload.feedback_text,
            actor_login=payload.actor_login,
        )
    finally:
        await learning_service.aclose()

    await session.commit()

    logger.info(
        "finding_feedback_submitted",
        review_id=review_id,
        finding_id=finding_id,
        outcome=payload.outcome,
        retained_in_hindsight=retained,
    )

    return ReviewFeedbackResponse(
        id=feedback_record.id,
        review_run_id=feedback_record.review_run_id,
        finding_id=feedback_record.finding_id,
        actor_login=feedback_record.actor_login,
        outcome=feedback_record.outcome,
        feedback_text=feedback_record.feedback_text,
        source_url=feedback_record.source_url,
        created_at=feedback_record.created_at,
        retained_in_hindsight=retained,
        message=f"Feedback recorded and {'retained to Hindsight memory' if retained else 'processed'}",
    )


@router.post(
    "/{review_id}/feedback",
    response_model=ReviewFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_general_review_feedback(
    review_id: str,
    payload: FindingFeedbackRequest,
    session: AsyncSession = Depends(get_db),
) -> ReviewFeedbackResponse:
    """Submits general feedback for an entire review run."""
    set_trace_context(stage="general_feedback_intake")

    # 1. Verify review run and repository context
    review_run = await ReviewRunRepo.get_with_repository(session, review_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    # 2. Record feedback in relational persistence
    feedback_record = await ReviewFeedbackRepo.record_feedback(
        session=session,
        review_run_id=review_id,
        finding_id=None,
        actor_login=payload.actor_login,
        outcome=payload.outcome,
        feedback_text=payload.feedback_text,
        source_url=payload.source_url,
    )

    # 3. Process into Hindsight memory via LearningService
    owner = review_run.pull_request.repository.owner
    repo = review_run.pull_request.repository.name
    learning_service = LearningService()
    try:
        retained = await learning_service.process_feedback_outcome(
            owner=owner,
            repo=repo,
            finding=None,
            outcome=payload.outcome,
            feedback_text=payload.feedback_text,
            actor_login=payload.actor_login,
        )
    finally:
        await learning_service.aclose()

    await session.commit()

    logger.info(
        "general_review_feedback_submitted",
        review_id=review_id,
        outcome=payload.outcome,
        retained_in_hindsight=retained,
    )

    return ReviewFeedbackResponse(
        id=feedback_record.id,
        review_run_id=feedback_record.review_run_id,
        finding_id=None,
        actor_login=feedback_record.actor_login,
        outcome=feedback_record.outcome,
        feedback_text=feedback_record.feedback_text,
        source_url=feedback_record.source_url,
        created_at=feedback_record.created_at,
        retained_in_hindsight=retained,
        message=f"Review feedback recorded and {'retained to Hindsight memory' if retained else 'processed'}",
    )


@router.get(
    "/{review_id}/feedback",
    response_model=list[ReviewFeedbackListItem],
    status_code=status.HTTP_200_OK,
)
async def list_review_feedback(
    review_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[ReviewFeedbackListItem]:
    """Lists all feedback entries recorded for a given review run."""
    review_run = await ReviewRunRepo.get_by_id(session, review_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found",
        )

    records = await ReviewFeedbackRepo.list_by_run(session, review_id)
    return [
        ReviewFeedbackListItem(
            id=r.id,
            review_run_id=r.review_run_id,
            finding_id=r.finding_id,
            actor_login=r.actor_login,
            outcome=r.outcome,
            feedback_text=r.feedback_text,
            source_url=r.source_url,
            created_at=r.created_at,
        )
        for r in records
    ]
