"""Synthetic GitHub webhook payloads for unit and integration testing."""

import hashlib
import hmac
from typing import Any


def compute_signature(secret: str, body: bytes) -> str:
    """Computes standard GitHub HMAC-SHA256 signature."""
    digest = hmac.new(key=secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_pr_opened_payload(
    owner: str = "acme",
    repo: str = "commerce",
    number: int = 42,
    head_sha: str = "abc123head",
    base_sha: str = "def456base",
) -> dict[str, Any]:
    return {
        "action": "opened",
        "number": number,
        "pull_request": {
            "id": 1000 + number,
            "number": number,
            "title": "Refactor payment service architecture",
            "body": "Implements service layer isolation for billing.",
            "head": {"sha": head_sha, "ref": "feature/payments"},
            "base": {"sha": base_sha, "ref": "main"},
            "user": {"login": "aditya", "id": 101, "html_url": "https://github.com/aditya"},
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
        },
        "repository": {
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": {"login": owner, "id": 1},
            "default_branch": "main",
        },
        "sender": {"login": "aditya", "id": 101},
    }


def make_pr_sync_payload(
    owner: str = "acme",
    repo: str = "commerce",
    number: int = 42,
    head_sha: str = "new_head_789",
) -> dict[str, Any]:
    payload = make_pr_opened_payload(owner=owner, repo=repo, number=number, head_sha=head_sha)
    payload["action"] = "synchronize"
    return payload


def make_pr_review_submitted_payload(
    owner: str = "acme", repo: str = "commerce", number: int = 42
) -> dict[str, Any]:
    return {
        "action": "submitted",
        "review": {
            "id": 8801,
            "user": {"login": "senior_reviewer", "id": 202},
            "state": "changes_requested",
            "body": "Team convention: do not use raw SQL in services, use repository methods.",
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}#pullrequestreview-8801",
        },
        "pull_request": {
            "id": 1000 + number,
            "number": number,
            "title": "Refactor payment service architecture",
            "head": {"sha": "abc123head", "ref": "feature/payments"},
            "base": {"sha": "def456base", "ref": "main"},
            "user": {"login": "aditya", "id": 101},
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
        },
        "repository": {
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": {"login": owner, "id": 1},
            "default_branch": "main",
        },
        "sender": {"login": "senior_reviewer", "id": 202},
    }


def make_review_comment_created_payload(
    owner: str = "acme", repo: str = "commerce", number: int = 42
) -> dict[str, Any]:
    return {
        "action": "created",
        "comment": {
            "id": 9901,
            "user": {"login": "lead_architect", "id": 303},
            "body": "Rejected: this microservice uses strict read consistency, no caching allowed.",
            "path": "services/payment.py",
            "line": 45,
            "side": "RIGHT",
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}#discussion_r9901",
        },
        "pull_request": {
            "id": 1000 + number,
            "number": number,
            "title": "Refactor payment service architecture",
            "head": {"sha": "abc123head", "ref": "feature/payments"},
            "base": {"sha": "def456base", "ref": "main"},
            "user": {"login": "aditya", "id": 101},
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
        },
        "repository": {
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": {"login": owner, "id": 1},
            "default_branch": "main",
        },
        "sender": {"login": "lead_architect", "id": 303},
    }


def make_issue_comment_payload(
    owner: str = "acme",
    repo: str = "commerce",
    number: int = 42,
    is_pr: bool = True,
) -> dict[str, Any]:
    return {
        "action": "created",
        "issue": {
            "id": 7000 + number,
            "number": number,
            "title": "Refactor payment service architecture",
            "pull_request": {"url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"}
            if is_pr
            else None,
        },
        "comment": {
            "id": 12345,
            "user": {"login": "engineer", "id": 404},
            "body": "Acknowledged, switching to Decimal.",
        },
        "repository": {
            "name": repo,
            "full_name": f"{owner}/{repo}",
            "owner": {"login": owner, "id": 1},
            "default_branch": "main",
        },
        "sender": {"login": "engineer", "id": 404},
    }
