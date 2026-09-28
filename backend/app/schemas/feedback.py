"""Schemas for human feedback and learning loop outcomes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FeedbackOutcome = Literal[
    "accepted",
    "rejected",
    "modified",
    "ignored",
]


class FindingFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outcome: FeedbackOutcome = Field(
        ...,
        description="Reviewer feedback outcome: accepted, rejected, modified, or ignored",
    )
    feedback_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Context or rationale explaining the feedback",
    )
    actor_login: str = Field(
        default="reviewer",
        max_length=100,
        description="GitHub username of the reviewer providing feedback",
    )
    source_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL of the comment or review on GitHub",
    )


class ReviewFeedbackResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    review_run_id: str
    finding_id: str | None = None
    actor_login: str
    outcome: str
    feedback_text: str
    source_url: str | None = None
    created_at: datetime
    retained_in_hindsight: bool = False
    message: str = "Feedback processed successfully"


class ReviewFeedbackListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    review_run_id: str
    finding_id: str | None = None
    actor_login: str
    outcome: str
    feedback_text: str
    source_url: str | None = None
    created_at: datetime
