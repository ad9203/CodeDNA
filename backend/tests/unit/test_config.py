"""Unit tests for configuration validation and secret hygiene."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_default_values():
    cfg = Settings(
        environment="development",
        database_url="sqlite+aiosqlite:///./test.db",
    )
    assert cfg.environment == "development"
    assert cfg.log_level == "INFO"
    assert "sqlite" in cfg.database_url


def test_settings_rejects_invalid_log_level():
    with pytest.raises(ValidationError):
        Settings(log_level="SUPER_VERBOSE")


def test_settings_rejects_malformed_url():
    with pytest.raises(ValidationError):
        Settings(frontend_origin="not-a-valid-url")


def test_settings_enforces_production_secrets():
    # In production, missing secrets must raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            github_token=None,
            github_webhook_secret=None,
            groq_api_key=None,
            hindsight_api_key=None,
        )
    err_msg = str(exc_info.value)
    assert "Production environment requires the following secret settings" in err_msg


def test_settings_secret_str_masks_repr():
    cfg = Settings(
        github_token="ghp_super_secret_token_12345",  # pragma: allowlist secret
        groq_api_key="gsk_secret_groq_key_67890",  # pragma: allowlist secret
    )
    repr_str = repr(cfg)
    assert "ghp_super_secret_token_12345" not in repr_str
    assert "gsk_secret_groq_key_67890" not in repr_str
    assert "**********" in repr_str
