"""
OpenAI DALL·E 3 provider.

Install:  pip install wagtail-ai-images[openai]

Config key: WAGTAIL_AI_IMAGES["PROVIDERS"]["openai"]
  API_KEY_ENV_VAR   env var that holds the OpenAI API key  (default: OPENAI_API_KEY)
  MODEL             model name                              (default: dall-e-3)
  DEFAULT_SIZE      image dimensions                        (default: 1024x1024)
  DEFAULT_STYLE     "natural" | "vivid"                     (default: natural)
  DEFAULT_QUALITY   "standard" | "hd"                      (default: standard)
"""
from __future__ import annotations

import base64
import os

from .base import ImageProvider, ProviderCapabilities
from ..exceptions import (
    AuthenticationError,
    ConfigurationError,
    GenerationError,
    InvalidPromptError,
    ProviderUnavailableError,
    RateLimitError,
)

try:
    import openai as _openai_sdk
except ImportError:
    _openai_sdk = None  # type: ignore[assignment]


class OpenAIProvider(ImageProvider):
    """DALL·E 3 via the official openai Python SDK."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_sizes=["1024x1024", "1024x1792", "1792x1024"],
            supported_styles=["natural", "vivid"],
            max_prompt_length=4000,
            supports_negative_prompt=False,
        )

    def _get_client(self):
        if _openai_sdk is None:
            raise ConfigurationError(
                "openai SDK is not installed. "
                "Run: pip install wagtail-ai-images[openai]"
            )
        api_key_env = self.config.get("API_KEY_ENV_VAR", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise AuthenticationError(
                f"OpenAI API key not found in environment variable '{api_key_env}'."
            )
        return _openai_sdk.OpenAI(api_key=api_key)

    def generate(self, prompt: str, size: str, style: str | None = None, **kwargs) -> bytes:
        client = self._get_client()
        model = self.config.get("MODEL", "dall-e-3")
        size = size or self.config.get("DEFAULT_SIZE", "1024x1024")
        style = style or self.config.get("DEFAULT_STYLE", "natural")
        quality = self.config.get("DEFAULT_QUALITY", "standard")

        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                style=style,
                quality=quality,
                response_format="b64_json",
                n=1,
            )
        except _openai_sdk.AuthenticationError as exc:
            raise AuthenticationError(str(exc)) from exc
        except _openai_sdk.BadRequestError as exc:
            raise InvalidPromptError(str(exc)) from exc
        except _openai_sdk.RateLimitError as exc:
            raise RateLimitError(str(exc)) from exc
        except _openai_sdk.APIConnectionError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except _openai_sdk.APIError as exc:
            raise GenerationError(str(exc)) from exc

        b64_data = response.data[0].b64_json
        return base64.b64decode(b64_data)

    def validate_config(self) -> bool:
        if _openai_sdk is None:
            return False
        api_key_env = self.config.get("API_KEY_ENV_VAR", "OPENAI_API_KEY")
        return bool(os.environ.get(api_key_env))
