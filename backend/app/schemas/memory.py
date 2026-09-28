"""Schemas for Hindsight memory representation, queries, and audits."""

from pydantic import BaseModel, ConfigDict, Field


class RecalledMemory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memory_id: str | None = None
    text: str
    source_type: str | None = "team_rule"
    tags: list[str] = Field(default_factory=list)
    relevance: float | None = None


class MemoryRetainPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str
    context: str | None = None
    memory_type: str = "team_rule"
    source_reference: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryRecallResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bank_id: str
    query: str
    memories: list[RecalledMemory]
    status: str = "ok"  # ok | degraded | empty
    duration_ms: int = 0
    formatted_context: str = ""
