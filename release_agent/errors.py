class ReleaseAgentError(Exception):
    """Base exception for release-agent collector failures."""


class ReleaseRequestError(ReleaseAgentError):
    """Raised when release intake parameters are invalid."""


class GitHubClientError(ReleaseAgentError):
    """Raised when GitHub evidence cannot be retrieved."""
