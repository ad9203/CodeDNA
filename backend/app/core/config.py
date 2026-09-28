"""Application configuration using Pydantic Settings."""

from typing import Literal

from pydantic import AnyHttpUrl, SecretStr
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

    # External service secrets (optional in local development/tests)
    github_token: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    hindsight_api_key: SecretStr | None = None

    # Service endpoints
    github_api_base_url: AnyHttpUrl = AnyHttpUrl("https://api.github.com")
    hindsight_base_url: AnyHttpUrl = AnyHttpUrl("https://api.hindsight.vectorize.io")

    # LLM & Memory defaults
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.0
    groq_max_tokens: int = 6000
    hindsight_bank_prefix: str = "codedna"
    hindsight_recall_budget: str = "mid"
    hindsight_max_recall_tokens: int = 4096

    # Worker controls
    max_external_retries: int = 3
    initial_retry_delay_seconds: float = 0.5
    max_retry_delay_seconds: float = 8.0

    # Security limits
    max_pr_files: int = 100
    max_diff_chars: int = 150000
    max_memory_chars: int = 40000


settings = Settings()
