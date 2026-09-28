"""Hindsight client integration adapter with retry policies and mock support."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.schemas.memory import RecalledMemory

logger = get_logger("app.integrations.hindsight")


class BaseHindsightClient(ABC):
    """Abstract interface for Hindsight memory operations."""

    @abstractmethod
    async def aretain(
        self,
        bank_id: str,
        content: str,
        context: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def arecall(
        self,
        bank_id: str,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: list[str] | None = None,
    ) -> list[RecalledMemory]:
        pass

    @abstractmethod
    async def healthcheck(self, bank_id: str | None = None) -> bool:
        pass


class OfficialHindsightClient(BaseHindsightClient):
    """Production client wrapping the official hindsight-client SDK with tenacity retries."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = base_url or str(settings.hindsight_base_url).rstrip("/")
        self.api_key = api_key or (
            settings.hindsight_api_key.get_secret_value() if settings.hindsight_api_key else ""
        )
        self._client = None

    def _get_sdk_client(self):
        if not self._client:
            from hindsight_client import Hindsight

            self._client = Hindsight(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        reraise=True,
    )
    async def aretain(
        self,
        bank_id: str,
        content: str,
        context: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            client = self._get_sdk_client()
            res = await asyncio.wait_for(
                client.aretain(
                    bank_id=bank_id,
                    content=content,
                    context=context,
                    metadata=metadata,
                    tags=tags,
                ),
                timeout=settings.hindsight_timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info("hindsight_retain_success", bank_id=bank_id, duration_ms=duration_ms)
            return {"status": "success", "response": str(res)}
        except Exception as e:
            logger.error("hindsight_retain_failed", bank_id=bank_id, error=str(e))
            raise ExternalServiceError(
                "hindsight", f"Failed to retain memory: {e}", retryable=True
            ) from e

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        reraise=True,
    )
    async def arecall(
        self,
        bank_id: str,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: list[str] | None = None,
    ) -> list[RecalledMemory]:
        start = time.perf_counter()
        try:
            client = self._get_sdk_client()
            res = await asyncio.wait_for(
                client.arecall(
                    bank_id=bank_id,
                    query=query,
                    max_tokens=max_tokens,
                    budget=budget,
                    tags=tags,
                ),
                timeout=settings.hindsight_timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            recalled_list: list[RecalledMemory] = []

            # Normalize Hindsight SDK recall response
            # Hindsight returns memories/results with text and relevance scores
            results = getattr(res, "results", None) or getattr(res, "memories", None) or []
            for item in results:
                text = getattr(item, "text", "") or getattr(item, "content", "")
                relevance = getattr(item, "relevance", None) or getattr(item, "score", None)
                source_type = getattr(item, "type", "team_rule")
                item_tags = getattr(item, "tags", []) or []
                item_id = getattr(item, "id", None)
                if text:
                    recalled_list.append(
                        RecalledMemory(
                            memory_id=str(item_id) if item_id else None,
                            text=str(text),
                            source_type=str(source_type),
                            tags=list(item_tags),
                            relevance=float(relevance) if relevance is not None else None,
                        )
                    )

            logger.info(
                "hindsight_recall_success",
                bank_id=bank_id,
                count=len(recalled_list),
                duration_ms=duration_ms,
            )
            return recalled_list
        except Exception as e:
            logger.error("hindsight_recall_failed", bank_id=bank_id, error=str(e))
            raise ExternalServiceError(
                "hindsight", f"Failed to recall memory: {e}", retryable=True
            ) from e

    async def healthcheck(self, bank_id: str | None = None) -> bool:
        """Verifies Hindsight service availability."""
        try:
            client = self._get_sdk_client()
            target_bank = bank_id or f"{settings.hindsight_bank_prefix}:healthcheck"
            await client.aget_bank_config(bank_id=target_bank)
            return True
        except Exception:
            return False


class MockHindsightClient(BaseHindsightClient):
    """In-memory deterministic mock of Hindsight with bank isolation and failure injection."""

    def __init__(self):
        # Bank isolation: Dict[bank_id, List[Dict[str, Any]]]
        self.banks: dict[str, list[dict[str, Any]]] = {}
        self.should_fail: bool = False
        self.fail_count: int = 0
        self.calls_retain: list[dict[str, Any]] = []
        self.calls_recall: list[dict[str, Any]] = []

    def seed_memory(
        self,
        bank_id: str,
        text: str,
        source_type: str = "team_rule",
        tags: list[str] | None = None,
        relevance: float = 0.9,
    ) -> None:
        """Helper to preload memories into a specific bank."""
        self.banks.setdefault(bank_id, []).append(
            {
                "id": f"mem-{len(self.banks.get(bank_id, [])) + 1}",
                "text": text,
                "type": source_type,
                "tags": tags or [],
                "relevance": relevance,
            }
        )

    async def aretain(
        self,
        bank_id: str,
        content: str,
        context: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        self.calls_retain.append({"bank_id": bank_id, "content": content, "tags": tags})
        if self.should_fail:
            self.fail_count += 1
            raise ExternalServiceError(
                "hindsight", "Mock Hindsight connection timeout", retryable=True
            )

        mem_id = f"mem-{len(self.banks.setdefault(bank_id, [])) + 1}"
        record = {
            "id": mem_id,
            "text": content,
            "context": context,
            "metadata": metadata or {},
            "tags": tags or [],
            "type": metadata.get("type", "team_rule") if metadata else "team_rule",
            "relevance": 0.85,
        }
        self.banks[bank_id].append(record)
        return {"status": "retained", "id": mem_id}

    async def arecall(
        self,
        bank_id: str,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: list[str] | None = None,
    ) -> list[RecalledMemory]:
        self.calls_recall.append({"bank_id": bank_id, "query": query, "tags": tags})
        if self.should_fail:
            self.fail_count += 1
            raise ExternalServiceError(
                "hindsight", "Mock Hindsight connection timeout", retryable=True
            )

        bank_memories = self.banks.get(bank_id, [])
        if not bank_memories:
            return []

        # Return seeded memories for this bank with relevance scores
        results: list[RecalledMemory] = []
        for item in bank_memories:
            results.append(
                RecalledMemory(
                    memory_id=item["id"],
                    text=item["text"],
                    source_type=item.get("type", "team_rule"),
                    tags=item.get("tags", []),
                    relevance=item.get("relevance", 0.88),
                )
            )
        return results

    async def healthcheck(self, bank_id: str | None = None) -> bool:
        return not self.should_fail
