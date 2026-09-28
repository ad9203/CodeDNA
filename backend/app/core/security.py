"""Security utilities: HMAC-SHA256 signature verification and payload validation."""

import hashlib
import hmac

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.core.security")


def verify_github_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str | None = None,
) -> bool:
    """Validates GitHub X-Hub-Signature-256 header against the raw body bytes.

    Uses constant-time comparison to prevent timing attacks.
    If no secret is configured (e.g. In local development/test), verification is skipped.
    """
    configured_secret = secret
    if configured_secret is None and settings.github_webhook_secret:
        configured_secret = settings.github_webhook_secret.get_secret_value()

    # If secret is configured, signature must be present and valid
    if configured_secret:
        if not signature_header:
            logger.warning("webhook_missing_signature")
            return False

        if not signature_header.startswith("sha256="):
            logger.warning("webhook_malformed_signature_header")
            return False

        expected = (
            "sha256="
            + hmac.new(
                key=configured_secret.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).hexdigest()
        )

        is_valid = hmac.compare_digest(expected, signature_header)
        if not is_valid:
            logger.warning("webhook_signature_mismatch")
        return is_valid

    # In development/test without a configured secret, allow requests
    return True


def enforce_github_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str | None = None,
) -> None:
    """Raises HTTP 403 Forbidden if signature verification fails."""
    if not verify_github_signature(raw_body, signature_header, secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing webhook signature",
        )
