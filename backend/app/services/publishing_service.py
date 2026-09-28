"""GitHub review publishing service with safe inline comment filtering."""

from typing import Any

from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.integrations.github_client import BaseGitHubClient, PyGitHubClient
from app.schemas.diff import PRDiffContext
from app.schemas.memory import RecalledMemory
from app.schemas.review import ReviewResult
from app.security.prompt_defense import PromptDefense

logger = get_logger("app.services.publishing_service")

MAX_INLINE_COMMENTS = 15


class PublishingService:
    """Publishes structured reviews and validated inline comments back to GitHub."""

    def __init__(self, client: BaseGitHubClient | None = None):
        self.client = client or PyGitHubClient()

    async def publish_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        review_result: ReviewResult,
        diff_context: PRDiffContext,
        memories: list[RecalledMemory],
    ) -> dict[str, Any]:
        """Publishes the overarching review comment and line-level suggestions to GitHub."""
        # 1. Render overall review body through the immutable fixed template (Layer C)
        memory_bullets = [m.text for m in memories]
        review_body = PromptDefense.compose_github_review_comment(
            review_result=review_result,
            memory_bullets=memory_bullets,
            team_conventions=review_result.team_conventions_applied,
        )

        # 2. Compile and validate inline comments
        inline_comments: list[dict[str, Any]] = []
        valid_files = {f.path: f for f in diff_context.files}

        for finding in review_result.findings:
            if len(inline_comments) >= MAX_INLINE_COMMENTS:
                break

            # An inline comment requires a valid path, line number, and diff hunk presence
            if finding.line is not None and finding.path in valid_files:
                file_obj = valid_files[finding.path]
                if finding.line in file_obj.valid_lines:
                    comment_body = (
                        f"**[{finding.severity.upper()}] {finding.title}**\n\n"
                        f"{finding.message}\n\n"
                        f"*Rationale*: {finding.rationale}"
                    )
                    if finding.suggestion:
                        comment_body += f"\n\n```suggestion\n{finding.suggestion}\n```"

                    inline_comments.append(
                        {
                            "path": finding.path,
                            "line": finding.line,
                            "side": finding.side or "RIGHT",
                            "body": comment_body,
                        }
                    )

        # 3. Publish to GitHub using PyGithub adapter
        try:
            published = await self.client.create_review(
                owner=owner,
                repo=repo,
                number=pr_number,
                commit_id=head_sha,
                body=review_body,
                event="COMMENT",  # Safe default: never auto-approve
                comments=inline_comments if inline_comments else None,
            )
            logger.info(
                "github_review_published",
                repo=f"{owner}/{repo}",
                pr=pr_number,
                review_id=published.get("id"),
                inline_count=len(inline_comments),
            )
            return published
        except Exception as e:
            logger.error(
                "github_publish_failed", repo=f"{owner}/{repo}", pr=pr_number, error=str(e)
            )
            raise ExternalServiceError("github", f"Failed to publish review to GitHub: {e}") from e
