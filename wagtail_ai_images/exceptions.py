"""
Provider error hierarchy for wagtail-ai-images.

All provider-specific exceptions must be a subclass of ProviderError so that
views can catch the entire family in a single except clause and translate each
sub-type into the correct HTTP status code.
"""


class ProviderError(Exception):
    """Base class for all provider-related failures."""


class AuthenticationError(ProviderError):
    """API key is missing, invalid, or has insufficient permissions.

    Views map this to HTTP 500 (configuration problem, not user error).
    Log at CRITICAL level.
    """


class RateLimitError(ProviderError):
    """The upstream provider has rate-limited this request.

    Distinct from our own per-user rate limiting (v0.2).  Views map this to
    HTTP 429 with a Retry-After header when the provider supplies one.
    """


class InvalidPromptError(ProviderError):
    """The prompt was rejected by the provider (content policy, length, etc.).

    Views map this to HTTP 400 so the user can revise and resubmit.
    """


class GenerationError(ProviderError):
    """The provider accepted the request but failed to produce an image.

    Views map this to HTTP 502 (bad gateway — upstream error).
    """


class ProviderUnavailableError(ProviderError):
    """The provider endpoint is unreachable or timed out.

    Views map this to HTTP 503.
    """


class ConfigurationError(ProviderError):
    """Required settings or SDK are missing.

    Views map this to HTTP 500.  Raised at startup when validate_config()
    returns False, and at request time when a required SDK is not installed.
    """
