"""Groq review client adapter with structured output and retry policies."""

import json
import time
from abc import ABC, abstractmethod
from typing import Any

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger("app.integrations.groq")


def is_retryable_groq_error(exc: BaseException) -> bool:
    """Retries only on transient network failures, 429 rate limits, and 5xx errors."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, ExternalServiceError) and exc.retryable:
        return True
    # Check for Groq APIStatusError status codes
    status_code = getattr(exc, "status_code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True
    return False


class BaseGroqClient(ABC):
    """Abstract interface for Groq LLM operations."""

    @abstractmethod
    async def generate_review(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Invokes Groq and returns raw JSON string adhering to ReviewResult schema."""
        pass


class OfficialGroqClient(BaseGroqClient):
    """Production client wrapping Groq SDK with strict JSON schema outputs and retries."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or (
            settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        )
        self._client = None

    def _get_client(self):
        if not self._client:
            from groq import AsyncGroq

            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    @retry(
        retry=retry_if_exception(is_retryable_groq_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=6.0),
        reraise=True,
    )
    async def generate_review(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        selected_model = model or settings.groq_model
        temp = temperature if temperature is not None else settings.groq_temperature
        start = time.perf_counter()

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=selected_model,
                temperature=temp,
                max_tokens=settings.groq_max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            raw_content = response.choices[0].message.content or "{}"

            logger.info(
                "groq_review_generated",
                model=selected_model,
                duration_ms=duration_ms,
                prompt_tokens=getattr(response.usage, "prompt_tokens", None),
                completion_tokens=getattr(response.usage, "completion_tokens", None),
            )
            return raw_content

        except Exception as e:
            status_code = getattr(e, "status_code", None)
            retryable = status_code in (429, 500, 502, 503, 504) or isinstance(
                e, (TimeoutError, ConnectionError)
            )
            logger.error(
                "groq_request_failed", model=selected_model, error=str(e), status=status_code
            )
            raise ExternalServiceError(
                "groq", f"Groq review failed: {e}", retryable=retryable
            ) from e


class MockGroqClient(BaseGroqClient):
    """Deterministic in-memory mock Groq client for testing and offline evaluation."""

    def __init__(self, predefined_response: dict[str, Any] | None = None):
        self.predefined_response = predefined_response
        self.should_fail: bool = False
        self.fail_with_retryable: bool = True
        self.calls: list[dict[str, Any]] = []

    def set_response(self, response_dict: dict[str, Any]) -> None:
        self.predefined_response = response_dict

    async def generate_review(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "temperature": temperature,
            }
        )

        if self.should_fail:
            raise ExternalServiceError(
                "groq",
                "Mock Groq service error",
                retryable=self.fail_with_retryable,
            )

        if self.predefined_response:
            return json.dumps(self.predefined_response)

        # Default fallback response adhering to ReviewResult
        default_result = {
            "summary": "Mock review completed successfully.",
            "overall_risk": "low",
            "findings": [
                {
                    "severity": "medium",
                    "category": "team_convention",
                    "confidence": 0.9,
                    "path": "services/payment_service.py",
                    "line": 42,
                    "side": "RIGHT",
                    "title": "Service boundary validation missing",
                    "message": "Validate parameters before invoking repository methods.",
                    "rationale": "Team standard requires service-layer parameter boundary checks.",
                    "suggestion": "if not amount:\n    raise ValueError('Amount required')",
                }
            ],
            "team_conventions_applied": [
                "Service layer validation required before repository calls"
            ],
            "memory_influence_summary": [
                "Recalled Team Rule #1 directly shaped finding on services/payment_service.py"
            ],
            "uncertainty_notes": [],
        }
        return json.dumps(default_result)
