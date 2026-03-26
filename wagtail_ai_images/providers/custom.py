"""
Generic HTTP provider for any REST-based image generation API.

No extra SDK required — uses httpx (a core dependency).

Config key: WAGTAIL_AI_IMAGES["PROVIDERS"]["custom"]
  ENDPOINT              full URL of the generate endpoint        (required)
  API_KEY_ENV_VAR       env var for the API key (optional)       (default: CUSTOM_AI_API_KEY)
  AUTH_HEADER           header name for the API key              (default: Authorization)
  AUTH_PREFIX           value prefix, e.g. "Bearer" or "Token"  (default: Bearer)
  REQUEST_TEMPLATE      dict merged into the POST body; override (default: {})
                        default prompt/size keys if needed
  RESPONSE_IMAGE_PATH   dot-separated path to image data in the  (default: data)
                        JSON response, e.g. "result.image"
  IMAGE_FORMAT          how the image is encoded in the response (default: base64)
                        "base64" | "url" | "bytes"
  DEFAULT_SIZE          dimensions string                        (default: 1024x1024)
  SUPPORTED_SIZES       list of supported size strings           (default: ["1024x1024"])
  SUPPORTED_STYLES      list of supported style strings or None  (default: None)
  SUPPORTS_NEGATIVE_PROMPT  bool                                 (default: False)
  MAX_PROMPT_LENGTH     int                                      (default: 2000)
  TIMEOUT_SECONDS       request timeout                          (default: 60)
"""
from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from .base import ImageProvider, ProviderCapabilities
from ..exceptions import (
    AuthenticationError,
    ConfigurationError,
    GenerationError,
    InvalidPromptError,
    ProviderUnavailableError,
)


def _extract_nested(data: dict, path: str) -> Any:
    """Traverse a dot-separated key path in a nested dict.

    Example: _extract_nested({"a": {"b": "value"}}, "a.b") → "value"
    Raises GenerationError if any key is missing.
    """
    current: Any = data
    for key in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                raise GenerationError(
                    f"Custom provider response has no index '{key}' at path '{path}'. "
                    f"Check RESPONSE_IMAGE_PATH in your provider config."
                )
        elif isinstance(current, dict):
            if key not in current:
                raise GenerationError(
                    f"Custom provider response has no key '{key}' at path '{path}'. "
                    f"Check RESPONSE_IMAGE_PATH in your provider config."
                )
            current = current[key]
        else:
            raise GenerationError(
                f"Custom provider response cannot traverse '{key}' at path '{path}': "
                f"expected dict or list, got {type(current).__name__}."
            )
    return current


class CustomProvider(ImageProvider):
    """Generic HTTP adapter — configure once, works with any REST image API."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_sizes=self.config.get("SUPPORTED_SIZES", ["1024x1024"]),
            supported_styles=self.config.get("SUPPORTED_STYLES", None),
            max_prompt_length=self.config.get("MAX_PROMPT_LENGTH", 2000),
            supports_negative_prompt=self.config.get("SUPPORTS_NEGATIVE_PROMPT", False),
        )

    def _resolve_endpoint_and_key(self) -> tuple[str, str | None]:
        endpoint = self.config.get("ENDPOINT")
        if not endpoint:
            raise ConfigurationError(
                "Custom provider requires an 'ENDPOINT' key in its config."
            )

        api_key_env = self.config.get("API_KEY_ENV_VAR", "CUSTOM_AI_API_KEY")
        api_key = os.environ.get(api_key_env)
        return endpoint, api_key

    def generate(self, prompt: str, size: str, style: str | None = None, **kwargs) -> bytes:
        endpoint, api_key = self._resolve_endpoint_and_key()
        size = size or self.config.get("DEFAULT_SIZE", "1024x1024")
        timeout = self.config.get("TIMEOUT_SECONDS", 60)

        # Merge the config template then apply defaults for prompt/size/style.
        body: dict[str, Any] = dict(self.config.get("REQUEST_TEMPLATE", {}))
        body.setdefault("prompt", prompt)
        body.setdefault("size", size)
        if style:
            body.setdefault("style", style)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            auth_header = self.config.get("AUTH_HEADER", "Authorization")
            auth_prefix = self.config.get("AUTH_PREFIX", "Bearer")
            headers[auth_header] = f"{auth_prefix} {api_key}"

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(endpoint, headers=headers, json=body)
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(f"Cannot reach custom provider: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Custom provider request timed out: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("Custom provider authentication failed.")
        if response.status_code == 400:
            raise InvalidPromptError(
                f"Custom provider rejected the request: {response.text[:200]}"
            )
        if not response.is_success:
            raise GenerationError(
                f"Custom provider error {response.status_code}: {response.text[:200]}"
            )

        image_format = self.config.get("IMAGE_FORMAT", "base64")
        response_path = self.config.get("RESPONSE_IMAGE_PATH", "data")

        try:
            payload = response.json()
            image_data = _extract_nested(payload, response_path)
        except (ValueError, KeyError) as exc:
            raise GenerationError(
                f"Failed to parse custom provider response: {exc}"
            ) from exc

        if image_format == "base64":
            return base64.b64decode(image_data)

        if image_format == "url":
            try:
                with httpx.Client(timeout=30) as client:
                    img_response = client.get(image_data)
                    img_response.raise_for_status()
                    return img_response.content
            except httpx.HTTPError as exc:
                raise GenerationError(
                    f"Failed to download image from URL '{image_data}': {exc}"
                ) from exc

        if image_format == "bytes":
            return bytes(image_data) if not isinstance(image_data, bytes) else image_data

        raise ConfigurationError(
            f"Unknown IMAGE_FORMAT '{image_format}'. "
            "Supported values: 'base64', 'url', 'bytes'."
        )

    def validate_config(self) -> bool:
        return bool(self.config.get("ENDPOINT"))
