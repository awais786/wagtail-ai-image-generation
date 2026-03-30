"""
Google Imagen provider (Vertex AI REST API).

Uses google-auth for Application Default Credentials instead of the heavy
google-cloud-aiplatform SDK, keeping the dependency footprint small.

Install:  pip install wagtail-ai-images[google]

Config key: WAGTAIL_AI_IMAGES["PROVIDERS"]["google"]
  PROJECT_ID        GCP project ID                  (required)
  LOCATION          Vertex AI region                (default: us-central1)
  MODEL             Imagen model version            (default: imagegeneration@006)
  DEFAULT_SIZE      WxH dimensions                  (default: 1024x1024)
  TIMEOUT_SECONDS   request timeout                 (default: 60)

Authentication: set GOOGLE_APPLICATION_CREDENTIALS env var to a service-account
key file, or rely on Application Default Credentials (gcloud auth application-default login).
"""
from __future__ import annotations

import base64
import os

import httpx

from .base import ImageProvider, ProviderCapabilities
from ..exceptions import (
    AuthenticationError,
    ConfigurationError,
    GenerationError,
    InvalidPromptError,
    ProviderUnavailableError,
)

try:
    import google.auth  # type: ignore[import-untyped]
    import google.auth.transport.requests  # type: ignore[import-untyped]
except ImportError:
    google = None  # type: ignore[assignment]

# Maps WxH → Imagen aspect-ratio string.
_ASPECT_RATIOS = {
    (1, 1): "1:1",
    (4, 3): "4:3",
    (3, 4): "3:4",
    (16, 9): "16:9",
    (9, 16): "9:16",
}


def _size_to_aspect_ratio(size: str) -> str:
    """Convert "1024x1024" → "1:1" (best-effort, falls back to "1:1")."""
    try:
        w, h = (int(d) for d in size.split("x"))
        from math import gcd

        divisor = gcd(w, h)
        ratio = (w // divisor, h // divisor)
        return _ASPECT_RATIOS.get(ratio, "1:1")
    except (ValueError, ZeroDivisionError):
        return "1:1"


class GoogleProvider(ImageProvider):
    """Google Imagen via the Vertex AI predict REST endpoint."""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported_sizes=["1024x1024", "1365x768", "768x1365", "1536x640", "640x1536"],
            supported_styles=None,
            max_prompt_length=2048,
            supports_negative_prompt=False,
        )

    def _get_access_token(self) -> str:
        if google is None:
            raise ConfigurationError(
                "google-auth is not installed. "
                "Run: pip install wagtail-ai-images[google]"
            )
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_request = google.auth.transport.requests.Request()
            credentials.refresh(auth_request)
            return credentials.token
        except google.auth.exceptions.DefaultCredentialsError as exc:
            raise AuthenticationError(
                f"Google Application Default Credentials not found: {exc}"
            ) from exc

    def generate(self, prompt: str, size: str, style: str | None = None, **kwargs) -> bytes:
        token = self._get_access_token()

        project_id = self.config.get("PROJECT_ID", "")
        if not project_id:
            raise ConfigurationError(
                "Google provider requires PROJECT_ID in WAGTAIL_AI_IMAGES['PROVIDERS']['google']."
            )

        location = self.config.get("LOCATION", "us-central1")
        model = self.config.get("MODEL", "imagegeneration@006")
        size = size or self.config.get("DEFAULT_SIZE", "1024x1024")
        timeout = self.config.get("TIMEOUT_SECONDS", 60)

        url = (
            f"https://{location}-aiplatform.googleapis.com/v1"
            f"/projects/{project_id}/locations/{location}"
            f"/publishers/google/models/{model}:predict"
        )
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": _size_to_aspect_ratio(size),
                "outputMimeType": "image/png",
            },
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(f"Cannot reach Vertex AI: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Vertex AI request timed out: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired Google credentials.")
        if response.status_code == 400:
            detail = response.json().get("error", {}).get("message", response.text[:200])
            raise InvalidPromptError(f"Google Imagen rejected the prompt: {detail}")
        if not response.is_success:
            raise GenerationError(
                f"Google Imagen error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        predictions = data.get("predictions", [])
        if not predictions:
            raise GenerationError("Google Imagen returned no predictions.")

        b64 = predictions[0].get("bytesBase64Encoded")
        if not b64:
            raise GenerationError("Google Imagen response is missing image data.")

        return base64.b64decode(b64)

    def validate_config(self) -> bool:
        if google is None:
            return False
        return bool(self.config.get("PROJECT_ID"))
