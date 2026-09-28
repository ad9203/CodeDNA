"""GitHub client abstraction and implementation using PyGithub."""

from abc import ABC, abstractmethod
from typing import Any

import httpx
from github import Auth, Github, GithubException

from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.integrations.github_auth import GitHubAuthProvider, PersonalAccessTokenProvider
from app.schemas.diff import ChangedFile, PullRequestMetadata

logger = get_logger("app.integrations.github_client")


class BaseGitHubClient(ABC):
    """Abstract interface for all GitHub API interactions."""

    @abstractmethod
    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequestMetadata:
        pass

    @abstractmethod
    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        pass

    @abstractmethod
    async def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        pass

    @abstractmethod
    async def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        commit_id: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def list_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def list_review_comments(
        self, owner: str, repo: str, number: int
    ) -> list[dict[str, Any]]:
        pass


class PyGitHubClient(BaseGitHubClient):
    """Production GitHub client using PyGithub and async HTTP for raw diff streaming."""

    def __init__(self, auth_provider: GitHubAuthProvider | None = None):
        self.auth_provider = auth_provider or PersonalAccessTokenProvider()

    def _get_pygithub(self) -> Github:
        token = self.auth_provider.get_token()
        auth = Auth.Token(token)
        return Github(
            auth=auth,
            base_url=str(settings.github_api_base_url).rstrip("/"),
            timeout=int(settings.external_timeout_seconds),
        )

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequestMetadata:
        try:
            gh = self._get_pygithub()
            repo_obj = gh.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(number)
            return PullRequestMetadata(
                owner=owner,
                repo=repo,
                number=pr.number,
                title=pr.title,
                body=pr.body or "",
                head_sha=pr.head.sha,
                base_sha=pr.base.sha,
                author_login=pr.user.login,
                html_url=pr.html_url,
            )
        except GithubException as ge:
            logger.error("github_get_pr_failed", error=str(ge), status=ge.status)
            raise ExternalServiceError(
                "github", f"Failed to fetch PR #{number}: {ge.data}", retryable=(ge.status >= 500)
            ) from ge
        except Exception as e:
            logger.error("github_unknown_error", error=str(e))
            raise ExternalServiceError("github", f"GitHub error: {e}") from e

    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        try:
            gh = self._get_pygithub()
            repo_obj = gh.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(number)
            files: list[ChangedFile] = []
            for f in pr.get_files():
                files.append(
                    ChangedFile(
                        path=f.filename,
                        status=f.status,
                        additions=f.additions,
                        deletions=f.deletions,
                        patch=f.patch,
                    )
                )
            return files
        except GithubException as ge:
            raise ExternalServiceError(
                "github", f"Failed to fetch files for PR #{number}: {ge.data}"
            ) from ge
        except Exception as e:
            raise ExternalServiceError("github", f"GitHub error: {e}") from e

    async def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        """Fetches raw unified diff directly via HTTP accept header."""
        token = self.auth_provider.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        url = f"{str(settings.github_api_base_url).rstrip('/')}/repos/{owner}/{repo}/pulls/{number}"
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                raise ExternalServiceError(
                    "github", f"Failed to fetch diff: {res.status_code} {res.text}"
                )
            return res.text

    async def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        commit_id: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            gh = self._get_pygithub()
            repo_obj = gh.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(number)
            commit = repo_obj.get_commit(commit_id)

            # PyGithub review creation
            pygithub_comments = []
            if comments:
                for c in comments:
                    pygithub_comments.append(
                        {
                            "path": c["path"],
                            "line": c["line"],
                            "side": c.get("side", "RIGHT"),
                            "body": c["body"],
                        }
                    )

            from github.GithubObject import NotSet

            review = pr.create_review(
                commit=commit,
                body=body,
                event=event,
                comments=pygithub_comments if pygithub_comments else NotSet,  # type: ignore[arg-type]
            )
            return {
                "id": review.id,
                "html_url": review.html_url,
                "state": review.state,
                "body": review.body,
            }
        except GithubException as ge:
            raise ExternalServiceError("github", f"Failed to create review: {ge.data}") from ge
        except Exception as e:
            raise ExternalServiceError("github", f"GitHub error: {e}") from e

    async def list_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        try:
            gh = self._get_pygithub()
            pr = gh.get_repo(f"{owner}/{repo}").get_pull(number)
            return [
                {
                    "id": r.id,
                    "user": r.user.login,
                    "state": r.state,
                    "body": r.body,
                    "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                }
                for r in pr.get_reviews()
            ]
        except Exception as e:
            raise ExternalServiceError("github", f"Failed to list reviews: {e}") from e

    async def list_review_comments(
        self, owner: str, repo: str, number: int
    ) -> list[dict[str, Any]]:
        try:
            gh = self._get_pygithub()
            pr = gh.get_repo(f"{owner}/{repo}").get_pull(number)
            return [
                {
                    "id": c.id,
                    "user": c.user.login,
                    "body": c.body,
                    "path": c.path,
                    "line": c.line,
                    "side": c.side,
                }
                for c in pr.get_review_comments()
            ]
        except Exception as e:
            raise ExternalServiceError("github", f"Failed to list review comments: {e}") from e


class MockGitHubClient(BaseGitHubClient):
    """Deterministic in-memory mock GitHub client for tests and offline evaluation."""

    def __init__(self):
        self.prs: dict[str, PullRequestMetadata] = {}
        self.pr_files: dict[str, list[ChangedFile]] = {}
        self.pr_diffs: dict[str, str] = {}
        self.reviews: dict[str, list[dict[str, Any]]] = {}
        self.comments: dict[str, list[dict[str, Any]]] = {}
        self.should_fail: bool = False
        self.simulate_422_on_inline: bool = False
        self.simulate_permission_error: bool = False

    def _key(self, owner: str, repo: str, number: int) -> str:
        return f"{owner}/{repo}#{number}"

    def seed_pr(
        self,
        owner: str,
        repo: str,
        number: int,
        title: str,
        files: list[ChangedFile],
        diff_text: str = "",
        head_sha: str = "mock_head_sha",
        base_sha: str = "mock_base_sha",
    ):
        key = self._key(owner, repo, number)
        self.prs[key] = PullRequestMetadata(
            owner=owner,
            repo=repo,
            number=number,
            title=title,
            body="Mock PR description",
            head_sha=head_sha,
            base_sha=base_sha,
            author_login="mock_user",
            html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        )
        self.pr_files[key] = files
        self.pr_diffs[key] = diff_text
        self.reviews[key] = []
        self.comments[key] = []

    async def get_pull_request(self, owner: str, repo: str, number: int) -> PullRequestMetadata:
        if self.should_fail:
            raise ExternalServiceError("github", "Mock GitHub API unavailable", retryable=True)
        key = self._key(owner, repo, number)
        if key not in self.prs:
            raise ExternalServiceError("github", f"PR {key} not found")
        return self.prs[key]

    async def get_pull_request_files(self, owner: str, repo: str, number: int) -> list[ChangedFile]:
        if self.should_fail:
            raise ExternalServiceError("github", "Mock GitHub API unavailable", retryable=True)
        key = self._key(owner, repo, number)
        return self.pr_files.get(key, [])

    async def get_pull_request_diff(self, owner: str, repo: str, number: int) -> str:
        if self.should_fail:
            raise ExternalServiceError("github", "Mock GitHub API unavailable", retryable=True)
        key = self._key(owner, repo, number)
        return self.pr_diffs.get(key, "")

    async def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        commit_id: str,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.should_fail:
            raise ExternalServiceError("github", "Mock GitHub API unavailable", retryable=True)
        if self.simulate_permission_error:
            raise ExternalServiceError(
                "github", "Resource not accessible by integration (403 Forbidden)", retryable=False
            )
        if self.simulate_422_on_inline and comments:
            raise ExternalServiceError(
                "github",
                "Validation Failed (422 Unprocessable Entity): Line number is outside changed hunk",
                retryable=False,
            )
        key = self._key(owner, repo, number)
        review_record = {
            "id": 99000 + len(self.reviews.get(key, [])),
            "commit_id": commit_id,
            "body": body,
            "event": event,
            "comments": comments or [],
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}#pullrequestreview",
        }
        self.reviews.setdefault(key, []).append(review_record)
        return review_record

    async def list_reviews(self, owner: str, repo: str, number: int) -> list[dict[str, Any]]:
        key = self._key(owner, repo, number)
        return self.reviews.get(key, [])

    async def list_review_comments(
        self, owner: str, repo: str, number: int
    ) -> list[dict[str, Any]]:
        key = self._key(owner, repo, number)
        return self.comments.get(key, [])
