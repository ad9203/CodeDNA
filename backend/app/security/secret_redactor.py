"""Regex-based secret redactor for diffs, memories, and logs."""

import re

REDACTION_TOKEN = "[REDACTED_SECRET]"

# Compiled regex patterns for known secret signatures
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Private Key blocks (RSA, EC, OPENSSH, DSA, PGP)
    (
        "private_key",
        re.compile(
            r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
    ),
    # GitHub Tokens (Personal, OAuth, User-to-Server, Server-to-Server, Fine-grained PAT)
    (
        "github_token",
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{50,100}"),
    ),
    # AWS Access Key ID
    ("aws_access_key", re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")),
    # Groq API Key
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{40,}\b")),
    # Hindsight API Key
    ("hindsight_key", re.compile(r"\bhs_[A-Za-z0-9_-]{20,}\b")),
    # JSON Web Token (JWT)
    (
        "jwt_token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    # Generic Authorization Bearer header
    (
        "bearer_token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{20,}\b"),
    ),
    # Generic API Key / Secret assignments: KEY = "xyz..."
    (
        "generic_secret_assignment",
        re.compile(
            r"""(?i)\b(api_key|apikey|secret_key|secret|password|access_token|client_secret)\s*[:=]\s*['"][A-Za-z0-9_\-\.\+/=]{12,}['"]"""
        ),
    ),
]


class SecretRedactor:
    """Detects and redacts credentials from diffs, PR descriptions, and memory before external transmission."""

    @classmethod
    def redact(cls, text: str) -> str:
        """Replaces detected credentials with [REDACTED_SECRET]."""
        if not text:
            return ""

        redacted = text
        for _name, pattern in SECRET_PATTERNS:
            redacted = pattern.sub(REDACTION_TOKEN, redacted)

        return redacted

    @classmethod
    def contains_secrets(cls, text: str) -> bool:
        """Returns True if any secret pattern is matched."""
        if not text:
            return False
        return any(pattern.search(text) is not None for _name, pattern in SECRET_PATTERNS)
