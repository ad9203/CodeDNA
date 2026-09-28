"""GitHub review publishing service with safe inline comment filtering."""

from typing import Any

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.integrations.github_client import BaseGitHubClient, PyGitHubClient
from app.schemas.diff import PRDiffContext
from app.schemas.memory import RecalledMemory
from app.schemas.review import ReviewFinding, ReviewResult
from app.security.prompt_defense import PromptDefense

logger = get_logger("app.services.publishing_service")

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class PublishingService:
    """Publishes structured reviews and validated inline comments back to GitHub."""

    def __init__(
        self,
        client: BaseGitHubClient | None = None,
        max_inline_comments: int | None = None,
        request_changes_on_critical: bool | None = None,
    ):
        self.client = client or PyGitHubClient()
        self.max_inline_comments = (
            max_inline_comments
            if max_inline_comments is not None
            else getattr(settings, "max_inline_comments", 15)
        )
        self.request_changes_on_critical = (
            request_changes_on_critical
            if request_changes_on_critical is not None
            else getattr(settings, "request_changes_on_critical", False)
        )

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

        # 2. Compile and validate inline comments prioritizing highest severity
        inline_comments: list[dict[str, Any]] = []
        placed_findings: list[ReviewFinding] = []
        unplaced_findings: list[ReviewFinding] = []
        valid_files = {f.path: f for f in diff_context.files}

        sorted_findings = sorted(
            review_result.findings,
            key=lambda f: SEVERITY_ORDER.get(f.severity.lower(), 0),
            reverse=True,
        )

        for finding in sorted_findings:
            # Inline comment requires: space under budget, valid path, non-null line, and line inside hunk
            if (
                len(inline_comments) < self.max_inline_comments
                and finding.line is not None
                and finding.path in valid_files
                and finding.line in valid_files[finding.path].valid_lines
            ):
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
                placed_findings.append(finding)
            else:
                unplaced_findings.append(finding)

        # 3. Determine review event (Never auto-approve)
        event = "COMMENT"
        if self.request_changes_on_critical and any(
            f.severity.lower() == "critical" for f in review_result.findings
        ):
            event = "REQUEST_CHANGES"

        # 4. Attempt publishing to GitHub with fallback on 422 inline line rejections
        try:
            published = await self.client.create_review(
                owner=owner,
                repo=repo,
                number=pr_number,
                commit_id=head_sha,
                body=review_body,
                event=event,
                comments=inline_comments if inline_comments else None,
            )
            logger.info(
                "github_review_published",
                repo=f"{owner}/{repo}",
                pr=pr_number,
                review_id=published.get("id"),
                inline_count=len(inline_comments),
                unplaced_count=len(unplaced_findings),
                review_event=event,
            )
            return {
                "id": published.get("id"),
                "html_url": published.get("html_url"),
                "state": published.get("state") or event,
                "event": event,
                "inline_count": len(inline_comments),
                "unplaced_count": len(unplaced_findings),
                "fallback_to_general": False,
            }
        except ExternalServiceError as ese:
            # If rejected because of line placement (422 Unprocessable Entity), fall back to general comment
            err_msg = str(ese).lower()
            if inline_comments and (
                "422" in err_msg or "unprocessable" in err_msg or "hunk" in err_msg
            ):
                logger.warn(
                    "github_review_inline_rejected_falling_back_to_general",
                    repo=f"{owner}/{repo}",
                    pr=pr_number,
                    error=str(ese),
                )
                try:
                    fallback_published = await self.client.create_review(
                        owner=owner,
                        repo=repo,
                        number=pr_number,
                        commit_id=head_sha,
                        body=review_body,
                        event=event,
                        comments=None,
                    )
                    logger.info(
                        "github_review_published_fallback",
                        repo=f"{owner}/{repo}",
                        pr=pr_number,
                        review_id=fallback_published.get("id"),
                        review_event=event,
                    )
                    return {
                        "id": fallback_published.get("id"),
                        "html_url": fallback_published.get("html_url"),
                        "state": fallback_published.get("state") or event,
                        "event": event,
                        "inline_count": 0,
                        "unplaced_count": len(review_result.findings),
                        "fallback_to_general": True,
                    }
                except Exception as fallback_err:
                    logger.error(
                        "github_publish_fallback_failed",
                        repo=f"{owner}/{repo}",
                        pr=pr_number,
                        error=str(fallback_err),
                    )
                    raise ExternalServiceError(
                        "github", f"Failed to publish review after fallback: {fallback_err}"
                    ) from fallback_err

            # Non-422 or other unrecoverable error
            logger.error(
                "github_publish_failed", repo=f"{owner}/{repo}", pr=pr_number, error=str(ese)
            )
            raise
        except Exception as e:
            logger.error(
                "github_publish_failed_unexpected",
                repo=f"{owner}/{repo}",
                pr=pr_number,
                error=str(e),
            )
            raise ExternalServiceError("github", f"Failed to publish review to GitHub: {e}") from e
