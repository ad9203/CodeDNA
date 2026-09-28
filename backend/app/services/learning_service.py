"""Learning loop service: maps reviewer outcomes into persistent Hindsight team conventions."""

from app.core.logging import get_logger
from app.db.models import ReviewFinding
from app.services.memory_service import MemoryService

logger = get_logger("app.services.learning_service")


class LearningService:
    """Closes the feedback loop by translating human review decisions into durable Hindsight memories."""

    def __init__(self, memory_service: MemoryService | None = None):
        self.memory_service = memory_service or MemoryService()

    async def process_feedback_outcome(
        self,
        owner: str,
        repo: str,
        finding: ReviewFinding | None,
        outcome: str,  # accepted | rejected | modified | ignored
        feedback_text: str,
        actor_login: str,
    ) -> bool:
        """Translates human review feedback into a categorized Hindsight memory."""
        clean_feedback = feedback_text.strip()
        if not clean_feedback:
            logger.info("learning_empty_feedback_skipped", repo=f"{owner}/{repo}")
            return False

        finding_title = finding.title if finding else "General PR review feedback"
        finding_cat = finding.category if finding else "general"

        if outcome == "rejected":
            # Synthesize negative constraint memory so model avoids this in future reviews
            content = (
                f"Team convention (rejected suggestion):\n"
                f"Reviewer {actor_login} rejected suggestion '{finding_title}'.\n"
                f"Reason: {clean_feedback}"
            )
            memory_type = "review_decision"
            tags = ["feedback:rejected", finding_cat, actor_login]

        elif outcome == "accepted":
            # Synthesize confirmed convention memory
            content = (
                f"Team convention confirmed:\n"
                f"Reviewer {actor_login} accepted standard '{finding_title}'.\n"
                f"Guideline: {clean_feedback}"
            )
            memory_type = "team_rule"
            tags = ["feedback:accepted", finding_cat, actor_login]

        elif outcome == "modified":
            content = (
                f"Team standard refinement for '{finding_title}':\n"
                f"Reviewer {actor_login} refined the implementation: {clean_feedback}"
            )
            memory_type = "learning_outcome"
            tags = ["feedback:modified", finding_cat, actor_login]

        else:
            logger.info("learning_outcome_unhandled", outcome=outcome)
            return False

        retained = await self.memory_service.retain_review_learning(
            owner=owner,
            repo=repo,
            content=content,
            context=f"reviewer_feedback:{actor_login}",
            memory_type=memory_type,
            tags=tags,
        )

        logger.info(
            "feedback_retained_to_hindsight",
            repo=f"{owner}/{repo}",
            outcome=outcome,
            memory_type=memory_type,
            retained=retained,
        )
        return retained

    async def retain_review_applied_conventions(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        conventions: list[str],
    ) -> int:
        """Reinforces existing applied conventions from a completed review."""
        retained_count = 0
        for conv in conventions:
            content = f"Convention observed in PR #{pr_number}: {conv}"
            ok = await self.memory_service.retain_review_learning(
                owner=owner,
                repo=repo,
                content=content,
                context=f"pr:{pr_number}",
                memory_type="learning_outcome",
                tags=["applied_convention", f"pr_{pr_number}"],
            )
            if ok:
                retained_count += 1
        return retained_count
