"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./codedna.db"
    frontend_origin: AnyHttpUrl = AnyHttpUrl("http://localhost:3000")
    backend_public_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    api_v1_prefix: str = "/api"

    # Required external services (SecretStr ensures safe logging/repr)
    github_token: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    hindsight_api_key: SecretStr | None = None

    # External service endpoints
    github_api_base_url: AnyHttpUrl = AnyHttpUrl("https://api.github.com")
    hindsight_base_url: AnyHttpUrl = AnyHttpUrl("https://api.hindsight.vectorize.io")

    # LLM & Model Configuration
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.0
    groq_max_tokens: int = 6000

    # Hindsight Memory Configuration
    hindsight_bank_prefix: str = "codedna"
    hindsight_recall_budget: str = "mid"
    hindsight_max_recall_tokens: int = 4096

    # Optional GitHub App credentials
    github_app_id: str | None = None
    github_private_key_path: str | None = None
    github_installation_id: str | None = None

    # Worker & Retry controls
    max_external_retries: int = 3
    initial_retry_delay_seconds: float = 0.5
    max_retry_delay_seconds: float = 8.0

    # Publishing controls
    max_inline_comments: int = 15
    request_changes_on_critical: bool = False

    # Security limits
    max_pr_files: int = 100
    max_diff_chars: int = 150000
    max_memory_chars: int = 40000

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"Invalid log_level: {v}. Must be one of {valid}")
        return upper

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        """Enforces that required secrets are present in production."""
        if self.environment == "production":
            missing = []
            if not self.github_token:
                missing.append("GITHUB_TOKEN")
            if not self.github_webhook_secret:
                missing.append("GITHUB_WEBHOOK_SECRET")
            if not self.groq_api_key:
                missing.append("GROQ_API_KEY")
            if not self.hindsight_api_key:
                missing.append("HINDSIGHT_API_KEY")

            if missing:
                raise ValueError(
                    f"Production environment requires the following secret settings: {', '.join(missing)}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Returns cached application settings."""
    return Settings()


settings = get_settings()
