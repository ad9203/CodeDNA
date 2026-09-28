"""Unit tests for GitHub integration adapter and diff extraction service."""

import pytest

from app.core.errors import ExternalServiceError, SecurityValidationError
from app.integrations.github_client import MockGitHubClient
from app.schemas.diff import ChangedFile, PullRequestMetadata
from app.services.diff_service import DiffService


@pytest.fixture
def mock_gh():
    client = MockGitHubClient()
    files = [
        ChangedFile(
            path="services/payment_service.py",
            status="modified",
            additions=10,
            deletions=2,
            patch="@@ -1,5 +1,7 @@\n def process_payment(amount):\n+    if amount <= 0:\n+        raise ValueError('Invalid amount')\n     return gateway.charge(amount)\n",
        ),
        ChangedFile(
            path="assets/logo.png",
            status="added",
            additions=0,
            deletions=0,
            patch=None,
        ),
        ChangedFile(
            path="docs/architecture.md",
            status="modified",
            additions=5,
            deletions=0,
            patch="@@ -10,3 +10,5 @@\n ## Overview\n+New architecture section\n",
        ),
    ]
    client.seed_pr(
        owner="acme",
        repo="commerce",
        number=42,
        title="Payment refactor and asset addition",
        files=files,
    )
    return client


@pytest.mark.asyncio
async def test_fetch_pr_metadata_and_files(mock_gh: MockGitHubClient):
    pr = await mock_gh.get_pull_request("acme", "commerce", 42)
    assert pr.owner == "acme"
    assert pr.repo == "commerce"
    assert pr.number == 42
    assert pr.title == "Payment refactor and asset addition"

    files = await mock_gh.get_pull_request_files("acme", "commerce", 42)
    assert len(files) == 3
    assert files[0].path == "services/payment_service.py"


@pytest.mark.asyncio
async def test_github_api_failure_maps_to_safe_internal_error(mock_gh: MockGitHubClient):
    mock_gh.should_fail = True
    with pytest.raises(ExternalServiceError) as exc_info:
        await mock_gh.get_pull_request("acme", "commerce", 42)
    assert exc_info.value.service == "github"
    assert "Mock GitHub API unavailable" in exc_info.value.message


def test_normalize_line_endings():
    crlf_text = "line1\r\nline2\rline3\n"
    normalized = DiffService.normalize_line_endings(crlf_text)
    assert "\r" not in normalized
    assert normalized == "line1\nline2\nline3\n"


def test_path_sanitization_and_traversal_rejection():
    # Valid relative paths
    assert DiffService.sanitize_path("services/payment.py") == "services/payment.py"
    assert DiffService.sanitize_path("src\\utils\\helper.ts") == "src/utils/helper.ts"

    # Traversal attempts must raise SecurityValidationError
    with pytest.raises(SecurityValidationError):
        DiffService.sanitize_path("../../etc/passwd")

    with pytest.raises(SecurityValidationError):
        DiffService.sanitize_path("/absolute/path/file.py")

    with pytest.raises(SecurityValidationError):
        DiffService.sanitize_path("C:\\Windows\\system32\\calc.exe")


def test_binary_file_detection_and_language_detection():
    assert DiffService.is_binary_file("assets/image.png") is True
    assert DiffService.is_binary_file("bin/app.wasm") is True
    assert DiffService.is_binary_file("services/payment.py") is False

    assert DiffService.detect_language("app.py") == "python"
    assert DiffService.detect_language("index.tsx") == "typescript"
    assert DiffService.detect_language("unknown.xyz") == "unknown"


def test_extract_valid_lines_from_patch():
    patch = (
        "@@ -10,4 +20,5 @@\n"
        " context line\n"  # target line 20
        "+added line 1\n"  # target line 21
        "+added line 2\n"  # target line 22
        "-removed line\n"  # (no target line)
        " final context\n"  # target line 23
    )
    valid_lines = DiffService.extract_valid_lines(patch)
    assert 20 in valid_lines
    assert 21 in valid_lines
    assert 22 in valid_lines
    assert 23 in valid_lines
    assert 10 not in valid_lines  # 10 was old line


def test_build_diff_context_binary_filtering_and_truncation():
    pr_meta = PullRequestMetadata(
        owner="acme",
        repo="commerce",
        number=42,
        title="Refactor",
        head_sha="head1",
        base_sha="base1",
        author_login="aditya",
        html_url="https://github.com/acme/commerce/pull/42",
    )

    files = [
        ChangedFile(
            path="services/service_a.py",
            status="modified",
            additions=5,
            deletions=1,
            patch="@@ -1,2 +1,3 @@\n+line A\n",
        ),
        ChangedFile(
            path="assets/logo.png",
            status="added",
            additions=0,
            deletions=0,
            patch=None,
        ),
        ChangedFile(
            path="services/service_b.py",
            status="modified",
            additions=100,
            deletions=20,
            patch="@@ -1,2 +1,3 @@\n+" + ("x" * 200) + "\n",
        ),
    ]

    # Without truncation
    ctx = DiffService.build_diff_context(pr_meta, files, max_diff_chars=50000)
    assert len(ctx.files) == 2  # binary logo.png excluded
    assert "assets/logo.png" in ctx.skipped_binary_files
    assert ctx.diff_truncated is False

    # With strict truncation limit (e.g. 150 chars)
    ctx_truncated = DiffService.build_diff_context(pr_meta, files, max_diff_chars=120)
    assert ctx_truncated.diff_truncated is True
    assert len(ctx_truncated.unexamined_files) > 0
    assert "DIFF TRUNCATED" in ctx_truncated.formatted_diff
