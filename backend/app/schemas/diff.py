"""Schemas for normalized changed files, diffs, and inline line validations."""

from pydantic import BaseModel, ConfigDict, Field


class ChangedFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    status: str  # modified | added | removed | renamed
    additions: int = 0
    deletions: int = 0
    patch: str | None = None
    language: str = "unknown"
    is_binary: bool = False
    valid_lines: list[int] = Field(default_factory=list)


class PullRequestMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str
    repo: str
    number: int
    title: str
    body: str | None = None
    head_sha: str
    base_sha: str
    author_login: str
    html_url: str


class PRDiffContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    repo: str
    pr_number: int
    title: str
    base_sha: str
    head_sha: str
    files: list[ChangedFile]
    total_files: int
    total_additions: int
    total_deletions: int
    diff_truncated: bool = False
    skipped_binary_files: list[str] = Field(default_factory=list)
    unexamined_files: list[str] = Field(default_factory=list)
    formatted_diff: str = ""
