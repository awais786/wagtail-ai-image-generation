"""
Provider registry for wagtail-ai-images.

Built-in providers are registered in WagtailAiImagesConfig.ready().
Third-party packages register their providers the same way — call
register_provider() inside their own AppConfig.ready().

get_provider() instantiates a fresh provider on every call.  No caching is
intentional: providers are cheap to construct, and caching would make it
harder to pick up settings changes in tests.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .providers.base import ImageProvider

# Maps provider ID → provider class (not instance).
_registry: dict[str, type] = {}


def register_provider(name: str, cls: type) -> None:
    """Register a provider class under the given name.

    Overwrites any existing registration with the same name, so third-party
    packages can replace built-in providers when needed.
    """
    _registry[name] = cls


def get_provider(name: str) -> "ImageProvider":
    """Return an instantiated provider for the given name.

    Reads the provider's config from WAGTAIL_AI_IMAGES["PROVIDERS"][name].
    Raises ConfigurationError if the provider is not registered or if the
    required SDK is not installed.
    """
    from django.conf import settings

    from .exceptions import ConfigurationError

    if name not in _registry:
        raise ConfigurationError(
            f"Provider '{name}' is not registered. "
            "Check that the required SDK extra is installed "
            "(e.g. pip install wagtail-ai-images[openai]) "
            "and that WAGTAIL_AI_IMAGES['PROVIDER'] matches a registered provider ID."
        )

    ai_settings = getattr(settings, "WAGTAIL_AI_IMAGES", {})
    config = ai_settings.get("PROVIDERS", {}).get(name, {})
    return _registry[name](config)
