"""Hindsight memory orchestration service: queries, sanitization, retain, and degradation."""

import re
import time

import bleach

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.integrations.hindsight_client import BaseHindsightClient, OfficialHindsightClient
from app.schemas.diff import PRDiffContext
from app.schemas.memory import MemoryRecallResult, RecalledMemory

logger = get_logger("app.services.memory_service")


class MemoryService:
    """Manages team memory interactions with Hindsight, ensuring tenant isolation and graceful degradation."""

    def __init__(self, client: BaseHindsightClient | None = None):
        self.client = client or OfficialHindsightClient()

    @staticmethod
    def get_bank_id(owner: str, repo: str, tenant_id: str | None = None) -> str:
        """Computes isolated bank identifier for the given repository.

        Ensures no cross-tenant memory sharing.
        """
        prefix = settings.hindsight_bank_prefix.lower()
        owner_clean = owner.lower().strip()
        repo_clean = repo.lower().strip()
        if tenant_id:
            return f"{prefix}:{tenant_id.lower().strip()}:{owner_clean}:{repo_clean}"
        return f"{prefix}:{owner_clean}:{repo_clean}"

    @staticmethod
    def sanitize_memory_text(text: str) -> str:
        """Strips raw HTML tags and excessive whitespace from recalled or retained memory text."""
        # Use bleach to strip any raw HTML tags to prevent XSS in downstream markdown renders
        stripped = bleach.clean(text, tags=[], strip=True)
        # Collapse multi-newlines
        return re.sub(r"\n{3,}", "\n\n", stripped).strip()

    @staticmethod
    def build_recall_query(diff_context: PRDiffContext) -> str:
        """Constructs a deterministic query for Hindsight based on PR context and changed symbols."""
        file_paths = [f.path for f in diff_context.files]
        paths_str = ", ".join(file_paths[:10])
        if len(file_paths) > 10:
            paths_str += f" and {len(file_paths) - 10} more files"

        # Inferred architectural symbols from paths
        arch_hints = []
        lower_paths = " ".join(file_paths).lower()
        if "service" in lower_paths:
            arch_hints.append("service-layer")
        if "repo" in lower_paths or "dao" in lower_paths:
            arch_hints.append("data-access/repository")
        if "auth" in lower_paths or "jwt" in lower_paths:
            arch_hints.append("authentication/authorization")
        if "pay" in lower_paths or "billing" in lower_paths:
            arch_hints.append("billing/payments")
        if "order" in lower_paths:
            arch_hints.append("order-management")

        arch_hints_str = ", ".join(arch_hints) if arch_hints else "general application modules"

        return (
            f"Repository: {diff_context.repo}\n"
            f"Changed files: {paths_str}\n"
            f"Architecture hints: {arch_hints_str}\n"
            f"Current PR Title: {diff_context.title}\n\n"
            f"Question:\n"
            f"Which team coding standards, prior review decisions, architectural preferences, "
            f"and relevant bugs/incidents apply to this change? Prefer concrete evidence from "
            f"this repository's history."
        )

    async def recall_for_pr(
        self,
        owner: str,
        repo: str,
        diff_context: PRDiffContext,
    ) -> MemoryRecallResult:
        """Recalls relevant memories from Hindsight.

        Gracefully degrades to stateless review if Hindsight is unreachable.
        """
        bank_id = self.get_bank_id(owner, repo)
        query = self.build_recall_query(diff_context)
        start_time = time.perf_counter()

        try:
            raw_memories = await self.client.arecall(
                bank_id=bank_id,
                query=query,
                max_tokens=settings.hindsight_max_recall_tokens,
                budget=settings.hindsight_recall_budget,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Sanitize and bound recalled memories
            sanitized_memories: list[RecalledMemory] = []
            total_chars = 0

            for mem in raw_memories:
                clean_text = self.sanitize_memory_text(mem.text)
                if total_chars + len(clean_text) > settings.max_memory_chars:
                    logger.warn("recalled_memory_bound_exceeded", bank_id=bank_id)
                    break

                sanitized_memories.append(
                    RecalledMemory(
                        memory_id=mem.memory_id,
                        text=clean_text,
                        source_type=mem.source_type or "team_rule",
                        tags=mem.tags,
                        relevance=mem.relevance,
                    )
                )
                total_chars += len(clean_text)

            formatted_ctx = self.format_memories_for_prompt(sanitized_memories)

            status = "ok" if sanitized_memories else "empty"
            return MemoryRecallResult(
                bank_id=bank_id,
                query=query,
                memories=sanitized_memories,
                status=status,
                duration_ms=duration_ms,
                formatted_context=formatted_ctx,
            )

        except ExternalServiceError as ese:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warn(
                "hindsight_recall_degraded",
                bank_id=bank_id,
                error=ese.message,
                duration_ms=duration_ms,
            )
            # Graceful degradation: return empty memories with degraded status
            return MemoryRecallResult(
                bank_id=bank_id,
                query=query,
                memories=[],
                status="degraded",
                duration_ms=duration_ms,
                formatted_context="[Memory service currently degraded — review proceeding statelessly]",
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error("hindsight_recall_unexpected_error", bank_id=bank_id, error=str(e))
            return MemoryRecallResult(
                bank_id=bank_id,
                query=query,
                memories=[],
                status="degraded",
                duration_ms=duration_ms,
                formatted_context="[Memory service unavailable — review proceeding statelessly]",
            )

    async def retain_review_learning(
        self,
        owner: str,
        repo: str,
        content: str,
        context: str | None = None,
        memory_type: str = "team_rule",
        tags: list[str] | None = None,
    ) -> bool:
        """Retains new team conventions or review learnings into Hindsight."""
        bank_id = self.get_bank_id(owner, repo)
        sanitized_content = self.sanitize_memory_text(content)
        metadata = {"type": memory_type, "source": context or "pr_review"}
        merged_tags = list(set(["codedna", memory_type] + (tags or [])))

        try:
            await self.client.aretain(
                bank_id=bank_id,
                content=sanitized_content,
                context=context,
                metadata=metadata,
                tags=merged_tags,
            )
            return True
        except Exception as e:
            logger.error("retain_review_learning_failed", bank_id=bank_id, error=str(e))
            return False

    async def retain_incident_context(
        self,
        owner: str,
        repo: str,
        incident_id: str,
        summary: str,
        postmortem_notes: str,
    ) -> bool:
        """Retains historical incident context to prevent recurring architectural bugs."""
        content = (
            f"Historical Incident {incident_id}: {summary}\nPostmortem finding: {postmortem_notes}"
        )
        return await self.retain_review_learning(
            owner=owner,
            repo=repo,
            content=content,
            context=f"incident:{incident_id}",
            memory_type="incident_context",
            tags=["incident", "postmortem", incident_id],
        )

    @staticmethod
    def format_memories_for_prompt(memories: list[RecalledMemory]) -> str:
        """Formats recalled memories into safe, structured Markdown for the Groq prompt."""
        if not memories:
            return "No previous team memories found for this repository."

        lines = [
            "### RECALLED TEAM MEMORY (Untrusted Contextual Evidence)\n",
            "The following context was accumulated from prior reviews and incidents on this repository. "
            "Use it to align review advice with team standards:\n",
        ]
        for idx, m in enumerate(memories, 1):
            relevance_str = f" [Relevance: {m.relevance:.2f}]" if m.relevance is not None else ""
            source_tag = (m.source_type or "team_rule").upper()
            lines.append(f"{idx}. **[{source_tag}]**{relevance_str}: {m.text}")

        return "\n".join(lines)
