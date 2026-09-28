"""Pydantic schemas for GitHub webhook event payloads."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class WebhookUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    login: str
    id: int | None = None
    html_url: str | None = None
    type: str | None = None


class WebhookRepository(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    full_name: str
    owner: WebhookUser | dict[str, Any] | str
    default_branch: str = "main"

    @property
    def owner_login(self) -> str:
        if isinstance(self.owner, WebhookUser):
            return self.owner.login
        if isinstance(self.owner, dict):
            return str(self.owner.get("login", "unknown"))
        return str(self.owner)


class WebhookCommitRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str
    ref: str | None = None


class WebhookPullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    number: int
    title: str
    head: WebhookCommitRef
    base: WebhookCommitRef
    user: WebhookUser
    html_url: str
    body: str | None = None


class WebhookPullRequestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    number: int
    pull_request: WebhookPullRequest
    repository: WebhookRepository
    sender: WebhookUser | None = None


class WebhookReview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    user: WebhookUser
    state: str  # approved | changes_requested | commented | dismissed
    body: str | None = None
    html_url: str | None = None


class WebhookPullRequestReviewEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str  # submitted | edited | dismissed
    review: WebhookReview
    pull_request: WebhookPullRequest
    repository: WebhookRepository
    sender: WebhookUser | None = None


class WebhookComment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    user: WebhookUser
    body: str
    path: str | None = None
    line: int | None = None
    side: str | None = None
    html_url: str | None = None


class WebhookReviewCommentEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str  # created | edited | deleted
    comment: WebhookComment
    pull_request: WebhookPullRequest
    repository: WebhookRepository
    sender: WebhookUser | None = None


class WebhookIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    number: int
    title: str
    pull_request: dict[str, Any] | None = None  # None if plain issue, dict if PR


class WebhookIssueCommentEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str  # created | edited | deleted
    issue: WebhookIssue
    comment: WebhookComment
    repository: WebhookRepository
    sender: WebhookUser | None = None
