"""SQLAlchemy models for CodeDNA review lifecycle and memory audit."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_number", name="uq_repo_pr_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_login: Mapped[str] = mapped_column(String(100), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    review_runs: Mapped[list["ReviewRun"]] = relationship(
        "ReviewRun", back_populates="pull_request", cascade="all, delete-orphan"
    )


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    pull_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )  # pending | processing | reviewed | failed | degraded
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_recalled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="review_runs")
    findings: Mapped[list["ReviewFinding"]] = relationship(
        "ReviewFinding", back_populates="review_run", cascade="all, delete-orphan"
    )
    memory_audits: Mapped[list["MemoryAudit"]] = relationship(
        "MemoryAudit", back_populates="review_run", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["ReviewFeedback"]] = relationship(
        "ReviewFeedback", back_populates="review_run", cascade="all, delete-orphan"
    )


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # critical | high | medium | low | info
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # correctness | security | performance | architecture | maintainability | testing | team_convention | other
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)  # RIGHT | LEFT
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_comment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    feedback_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # accepted | rejected | modified | ignored | unknown

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship("ReviewRun", back_populates="findings")
    feedback: Mapped[list["ReviewFeedback"]] = relationship(
        "ReviewFeedback", back_populates="finding"
    )


class MemoryAudit(Base):
    __tablename__ = "memory_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    memory_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # team_rule | review_decision | architecture_pattern | incident_context | learning_outcome
    memory_text_sanitized: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recall_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship("ReviewRun", back_populates="memory_audits")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="received", nullable=False
    )  # received | processing | processed | ignored | duplicate | failed


class ReviewFeedback(Base):
    __tablename__ = "review_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("review_findings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_login: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # accepted | rejected | modified | ignored | unknown
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship("ReviewRun", back_populates="feedback")
    finding: Mapped[Optional["ReviewFinding"]] = relationship(
        "ReviewFinding", back_populates="feedback"
    )
