"""Unit tests for structured logging and sensitive data redaction."""

from app.core.logging import (
    clear_trace_context,
    inject_correlation_context,
    redact_sensitive_data,
    set_trace_context,
)


def test_redact_sensitive_fields_in_logs():
    event = {
        "event": "user_action",
        "github_token": "ghp_secret_token_12345",  # pragma: allowlist secret
        "api_key": "groq_super_secret",  # pragma: allowlist secret
        "password": "my_password_xyz",
        "safe_field": "visible_value",
    }
    cleaned = redact_sensitive_data(None, "info", event)
    assert cleaned["github_token"] == "[REDACTED_SECRET]"
    assert cleaned["api_key"] == "[REDACTED_SECRET]"
    assert cleaned["password"] == "[REDACTED_SECRET]"
    assert cleaned["safe_field"] == "visible_value"


def test_truncate_oversized_diff_in_logs():
    long_diff = "diff --git a/file.py b/file.py\n" + ("+ line of code\n" * 50)
    event = {
        "event": "diff_fetched",
        "raw_diff": long_diff,
    }
    cleaned = redact_sensitive_data(None, "info", event)
    assert "[DIFF_TRUNCATED_LEN_" in cleaned["raw_diff"]


def test_inject_correlation_context():
    set_trace_context(
        request_id="req-999",
        delivery_id="deliv-888",
        repo="octocat/Hello-World",
        pr_number=42,
        stage="memory_recall",
    )
    try:
        event: dict = {"event": "stage_completed"}
        enriched = inject_correlation_context(None, "info", event)
        assert enriched["service"] == "codedna-backend"
        assert enriched["request_id"] == "req-999"
        assert enriched["delivery_id"] == "deliv-888"
        assert enriched["repo"] == "octocat/Hello-World"
        assert enriched["pr_number"] == 42
        assert enriched["stage"] == "memory_recall"
    finally:
        clear_trace_context()
