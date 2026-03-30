"""
Base classes for wagtail-ai-images providers.

Every built-in and third-party provider must subclass ImageProvider and
implement the three abstract methods.  ProviderCapabilities is a plain
dataclass — no business logic — so views and templates can inspect it
without importing provider-specific code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    """Describes what a provider can do.

    The UI reads this at runtime to decide which controls to render.
    Never hard-code provider-specific sizes or styles in templates.
    """

    supported_sizes: list[str]
    # None means the provider has no style concept (e.g. Stability SDXL).
    supported_styles: list[str] | None
    max_prompt_length: int
    supports_negative_prompt: bool


class ImageProvider(ABC):
    """Abstract base for all image-generation providers.

    Subclasses receive their section of WAGTAIL_AI_IMAGES["PROVIDERS"] as
    `config` in __init__.  They must read API keys exclusively from
    environment variables; the config dict stores only the *name* of the env
    var, never the value itself.
    """

    def __init__(self, config: dict) -> None:
        self.config = config

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return a ProviderCapabilities describing this provider's options."""

    @abstractmethod
    def generate(self, prompt: str, size: str, style: str | None = None, **kwargs) -> bytes:
        """Generate an image and return its raw bytes.

        Must download any remote URL before returning — never store an
        expiring provider URL.  Raise a ProviderError subclass on failure.
        """

    @abstractmethod
    def validate_config(self) -> bool:
        """Return True if the minimum required configuration is present.

        Called at startup (AppConfig.ready) to emit early warning log lines.
        Should not raise; return False instead.
        """
