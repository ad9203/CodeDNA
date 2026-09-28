"""Common response and parameter schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: T | None = None
    message: str | None = None
    error_code: str | None = None


class WebhookIntakeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_id: str
    event: str
    action: str | None = None
    status: str  # enqueued | duplicate | ignored | error
    message: str
