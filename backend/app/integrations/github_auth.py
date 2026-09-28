"""GitHub authentication provider abstraction."""

from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.errors import ConfigurationError


class GitHubAuthProvider(ABC):
    """Abstract provider for obtaining GitHub authentication tokens."""

    @abstractmethod
    def get_token(self) -> str:
        """Returns a valid GitHub bearer token."""
        pass


class PersonalAccessTokenProvider(GitHubAuthProvider):
    """Provides GitHub personal access token from configuration."""

    def __init__(self, token: str | None = None):
        self._token = token

    def get_token(self) -> str:
        if self._token:
            return self._token
        if settings.github_token:
            return settings.github_token.get_secret_value()
        raise ConfigurationError("GITHUB_TOKEN is not configured")


class GitHubAppTokenProvider(GitHubAuthProvider):
    """Stub for GitHub App enterprise authentication."""

    def __init__(self, app_id: str | None = None, installation_id: str | None = None):
        self.app_id = app_id or settings.github_app_id
        self.installation_id = installation_id or settings.github_installation_id

    def get_token(self) -> str:
        # In full App mode, generates a short-lived installation token using RS256 JWT
        if settings.github_token:
            return settings.github_token.get_secret_value()
        raise ConfigurationError("GitHub App private key / installation token not configured")
