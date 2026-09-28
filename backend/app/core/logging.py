"""Structured JSON logging configuration using structlog."""

import contextvars
import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# Context variables for request tracing
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
delivery_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "delivery_id", default=None
)
repo_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("repo", default=None)
pr_number_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "pr_number", default=None
)
stage_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("stage", default=None)

SENSITIVE_KEY_SUBSTRINGS = {
    "secret",
    "token",
    "key",
    "password",
    "auth",
    "credential",
    "private",
}


def redact_sensitive_data(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Redacts sensitive credentials and bounds large diff payloads in logs."""
    for key in list(event_dict.keys()):
        lower_key = key.lower()
        if any(substr in lower_key for substr in SENSITIVE_KEY_SUBSTRINGS):
            event_dict[key] = "[REDACTED_SECRET]"
        elif "diff" in lower_key or "patch" in lower_key:
            val = event_dict[key]
            if isinstance(val, str) and len(val) > 200:
                event_dict[key] = f"[DIFF_TRUNCATED_LEN_{len(val)}]"
    return event_dict


def inject_correlation_context(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Injects tracing contextvars into each log entry if set."""
    if "service" not in event_dict:
        event_dict["service"] = "codedna-backend"

    req_id = request_id_var.get()
    if req_id and "request_id" not in event_dict:
        event_dict["request_id"] = req_id

    deliv_id = delivery_id_var.get()
    if deliv_id and "delivery_id" not in event_dict:
        event_dict["delivery_id"] = deliv_id

    repo = repo_var.get()
    if repo and "repo" not in event_dict:
        event_dict["repo"] = repo

    pr_num = pr_number_var.get()
    if pr_num is not None and "pr_number" not in event_dict:
        event_dict["pr_number"] = pr_num

    stage = stage_var.get()
    if stage and "stage" not in event_dict:
        event_dict["stage"] = stage

    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configures structured JSON logging with safe field redaction."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            inject_correlation_context,
            redact_sensitive_data,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def set_trace_context(
    request_id: str | None = None,
    delivery_id: str | None = None,
    repo: str | None = None,
    pr_number: int | None = None,
    stage: str | None = None,
) -> None:
    """Helper to populate correlation contextvars."""
    if request_id is not None:
        request_id_var.set(request_id)
    if delivery_id is not None:
        delivery_id_var.set(delivery_id)
    if repo is not None:
        repo_var.set(repo)
    if pr_number is not None:
        pr_number_var.set(pr_number)
    if stage is not None:
        stage_var.set(stage)


def clear_trace_context() -> None:
    """Clears tracing contextvars."""
    request_id_var.set(None)
    delivery_id_var.set(None)
    repo_var.set(None)
    pr_number_var.set(None)
    stage_var.set(None)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Returns a structured logger instance."""
    return structlog.get_logger(name or "codedna")
