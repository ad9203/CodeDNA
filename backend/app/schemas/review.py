"""Schemas for structured code review results and findings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal[
        "correctness",
        "security",
        "performance",
        "architecture",
        "maintainability",
        "testing",
        "team_convention",
        "other",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    path: str
    line: int | None = None
    side: Literal["RIGHT", "LEFT"] | None = None
    title: str
    message: str
    rationale: str
    suggestion: str | None = None


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    overall_risk: Literal["low", "medium", "high", "critical"]
    findings: list[ReviewFinding]
    team_conventions_applied: list[str] = Field(default_factory=list)
    memory_influence_summary: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
