"""Schemas for Dashboard Read APIs and statistics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositoryListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    owner: str
    name: str
    full_name: str
    default_branch: str
    pr_count: int = 0
    review_count: int = 0
    created_at: datetime
    last_active_at: datetime | None = None


class ReviewRunListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    delivery_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: int | None = None
    finding_count: int = 0
    memory_recalled_count: int = 0
    repository_id: str
    repository_name: str
    pr_number: int
    pr_title: str
    pr_author: str
    pr_html_url: str
    head_sha: str


class ReviewRunListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ReviewRunListItem]
    total: int
    limit: int
    offset: int


class ReviewFindingDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    review_run_id: str
    severity: str
    category: str
    confidence: float
    path: str
    line: int | None = None
    side: str | None = None
    title: str
    message: str
    rationale: str
    suggestion: str | None = None
    feedback_status: str | None = None


class MemoryAuditDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    review_run_id: str
    memory_source_id: str | None = None
    memory_type: str | None = None
    memory_text_sanitized: str
    relevance_score: float | None = None
    rank_order: int = 0
    recall_timestamp: datetime


class ReviewRunDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    delivery_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: int | None = None
    finding_count: int = 0
    memory_recalled_count: int = 0
    error_code: str | None = None
    error_message_safe: str | None = None
    repository: dict[str, Any]
    pull_request: dict[str, Any]
    findings: list[ReviewFindingDetail] = Field(default_factory=list)
    memories: list[MemoryAuditDetail] = Field(default_factory=list)
    feedback_count: int = 0


class DashboardOverviewStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_repositories: int = 0
    total_reviews: int = 0
    total_findings: int = 0
    total_memories_recalled: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    feedback_metrics: dict[str, Any] = Field(default_factory=dict)
    avg_duration_ms: float | None = None
