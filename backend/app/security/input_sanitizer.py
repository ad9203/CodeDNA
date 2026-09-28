"""Input sanitizer: HTML stripping, length caps, and markdown link validation."""

import re

import bleach

# Allowed schemes for hyperlinks in GitHub markdown
ALLOWED_PROTOCOLS = {"http", "https"}

# Regex to detect dangerous pseudo-protocols in markdown links [text](javascript:...)
DANGEROUS_LINK_REGEX = re.compile(
    r"""\[([^\]]+)\]\(\s*(?:javascript|data|vbscript|file):[^\)]*\)""",
    re.IGNORECASE,
)


class InputSanitizer:
    """Multi-layer input and output sanitizer for pull request data, model responses, and comments."""

    @staticmethod
    def strip_html(text: str) -> str:
        """Removes all raw HTML elements to prevent HTML/XSS injection while preserving code."""
        if not text:
            return ""
        return bleach.clean(text, tags=[], strip=True)

    @staticmethod
    def sanitize_markdown_links(text: str) -> str:
        """Neutralizes javascript:, data:, and file: URI targets in markdown links."""
        if not text:
            return ""
        # Replaces [label](javascript:...) with [label](#unsafe-link-blocked)
        return DANGEROUS_LINK_REGEX.sub(r"[\1](#unsafe-link-blocked)", text)

    @classmethod
    def sanitize_text(cls, text: str, max_length: int | None = None) -> str:
        """Full sanitization: strips HTML, neutralizes dangerous links, and enforces length bounds."""
        if not text:
            return ""

        cleaned = cls.strip_html(text)
        cleaned = cls.sanitize_markdown_links(cleaned)

        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + " [TRUNCATED]"

        return cleaned

    @classmethod
    def sanitize_pr_metadata(cls, title: str, body: str | None) -> tuple[str, str]:
        """Sanitizes PR title and body with appropriate length limits."""
        clean_title = cls.sanitize_text(title, max_length=250)
        clean_body = cls.sanitize_text(body or "", max_length=8000)
        return clean_title, clean_body
