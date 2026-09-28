"""Core application error definitions."""

from typing import Any


class CodeDNAError(Exception):
    """Base exception for all CodeDNA errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ConfigurationError(CodeDNAError):
    """Raised when environment or settings are invalid."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class SecurityValidationError(CodeDNAError):
    """Raised when an untrusted payload violates security bounds."""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message, code="SECURITY_ERROR", details=details)


class ExternalServiceError(CodeDNAError):
    """Raised when an external service fails."""

    def __init__(self, service: str, message: str, retryable: bool = False, details: Any = None):
        super().__init__(f"[{service}] {message}", code=f"{service.upper()}_ERROR", details=details)
        self.service = service
        self.retryable = retryable
