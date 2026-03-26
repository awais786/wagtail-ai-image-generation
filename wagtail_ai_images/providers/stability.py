"""
Stability AI SDXL provider (REST API v1).

No extra SDK required — uses httpx (a core dependency).

Config key: WAGTAIL_AI_IMAGES["PROVIDERS"]["stability"]
  API_KEY_ENV_VAR   env var that holds the Stability API key  (default: STABILITY_API_KEY)
  MODEL             engine ID                                  (default: stable-diffusion-xl-1024-v1-0)
  DEFAULT_SIZE      WxH dimensions                            (default: 1024x1024)
  API_HOST          base URL for the Stability REST API       (default: https://api.stability.ai)
  TIMEOUT_SECONDS   request timeout                           (default: 60)
"""
from __future__ import annotations

import base64
import os

import httpx

from .base import ImageProvider, ProviderCapabilities
from ..exceptions import (
    AuthenticationError,
    GenerationError,
    InvalidPromptError,
    ProviderUnavailableError,
    RateLimitError,
)


class StabilityProvider(ImageProvider):
    """Stability AI SDXL via the v1 REST API."""

    _DEFAULT_API_HOST = "https://api.stability.ai"
    _DEFAULT_ENGINE = "stable-diffusion-xl-1024-v1-0"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_sizes=[
                "1024x1024",
                "1152x896",
                "896x1152",
                "1216x832",
                "832x1216",
                "1344x768",
                "768x1344",
            ],
            supported_styles=None,
            max_prompt_length=2000,
            supports_negative_prompt=True,
        )

    def _get_api_key(self) -> str:
        api_key_env = self.config.get("API_KEY_ENV_VAR", "STABILITY_API_KEY")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise AuthenticationError(
                f"Stability AI API key not found in environment variable '{api_key_env}'."
            )
        return api_key

    def generate(self, prompt: str, size: str, style: str | None = None, **kwargs) -> bytes:
        api_key = self._get_api_key()
        api_host = self.config.get("API_HOST", self._DEFAULT_API_HOST)
        engine_id = self.config.get("MODEL", self._DEFAULT_ENGINE)
        size = size or self.config.get("DEFAULT_SIZE", "1024x1024")
        timeout = self.config.get("TIMEOUT_SECONDS", 60)

        width, height = (int(d) for d in size.split("x"))

        text_prompts = [{"text": prompt, "weight": 1}]
        if kwargs.get("negative_prompt"):
            text_prompts.append({"text": kwargs["negative_prompt"], "weight": -1})

        url = f"{api_host}/v1/generation/{engine_id}/text-to-image"
        payload = {
            "text_prompts": text_prompts,
            "width": width,
            "height": height,
            "samples": 1,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(f"Cannot reach Stability AI: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Stability AI request timed out: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("Invalid or revoked Stability AI API key.")
        if response.status_code == 400:
            message = response.json().get("message", response.text[:200])
            raise InvalidPromptError(f"Stability AI rejected the prompt: {message}")
        if response.status_code == 429:
            raise RateLimitError("Stability AI rate limit exceeded.")
        if not response.is_success:
            raise GenerationError(
                f"Stability AI error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        artifact = data["artifacts"][0]
        if artifact.get("finishReason") != "SUCCESS":
            raise GenerationError(f"Stability AI generation failed: {artifact.get('finishReason')}")

        return base64.b64decode(artifact["base64"])

    def validate_config(self) -> bool:
        api_key_env = self.config.get("API_KEY_ENV_VAR", "STABILITY_API_KEY")
        return bool(os.environ.get(api_key_env))
