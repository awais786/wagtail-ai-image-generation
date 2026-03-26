"""
Integration tests — full prompt → generate → save → library flow.

The provider is mocked so no real API calls are made, but the rest of the
stack (view, storage, Wagtail image model, DB) runs for real.
"""
from __future__ import annotations

import base64
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage
from django.test import Client, override_settings
from django.urls import reverse
from wagtail.images import get_image_model

from tests.factories import SuperuserFactory

def _make_png() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (1, 1), color=(0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


FAKE_PNG = _make_png()
GENERATE_URL = "/admin/ai-images/generate/"

_AI_SETTINGS = {
    "ENABLED": True,
    "PROVIDER": "openai",
    "MAX_PROMPT_LENGTH": 500,
    "DEFAULT_COLLECTION": "AI Generated",
    "TIMEOUT_SECONDS": 10,
    "PROVIDERS": {
        "openai": {
            "API_KEY_ENV_VAR": "OPENAI_API_KEY",
            "DEFAULT_SIZE": "1024x1024",
            "DEFAULT_STYLE": "natural",
        }
    },
}


def _mock_provider(image_bytes=FAKE_PNG):
    provider = MagicMock()
    provider.get_capabilities.return_value = MagicMock(
        supported_sizes=["1024x1024"],
        supported_styles=["natural"],
    )
    provider.generate.return_value = image_bytes
    return provider


@pytest.mark.django_db
class TestFullGenerationFlow:
    def test_prompt_to_library_creates_image_record(self):
        Image = get_image_model()
        count_before = Image.objects.count()

        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        with override_settings(WAGTAIL_AI_IMAGES=_AI_SETTINGS):
            with patch("wagtail_ai_images.views.get_provider", return_value=_mock_provider()):
                response = client.post(
                    GENERATE_URL,
                    data={"prompt": "a dog playing in a field"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert Image.objects.count() == count_before + 1

        image = Image.objects.get(pk=data["image_id"])
        assert image.title == "a dog playing in a field"
        assert "ai-generated" in [t.name for t in image.tags.all()]
        assert image.collection.name == "AI Generated"

    def test_image_url_is_accessible(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        with override_settings(WAGTAIL_AI_IMAGES=_AI_SETTINGS):
            with patch("wagtail_ai_images.views.get_provider", return_value=_mock_provider()):
                response = client.post(
                    GENERATE_URL,
                    data={"prompt": "a mountain view"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        data = response.json()
        assert data["image_url"]  # non-empty URL string

    def test_provider_generate_called_with_correct_args(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        mock_provider = _mock_provider()

        with override_settings(WAGTAIL_AI_IMAGES=_AI_SETTINGS):
            with patch("wagtail_ai_images.views.get_provider", return_value=mock_provider):
                client.post(
                    GENERATE_URL,
                    data={"prompt": "a beach at night"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        mock_provider.generate.assert_called_once()
        call_kwargs = mock_provider.generate.call_args.kwargs
        assert call_kwargs["prompt"] == "a beach at night"
        assert call_kwargs["size"] == "1024x1024"

    def test_consecutive_generations_create_separate_images(self):
        Image = get_image_model()
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        with override_settings(WAGTAIL_AI_IMAGES=_AI_SETTINGS):
            with patch("wagtail_ai_images.views.get_provider", return_value=_mock_provider()):
                r1 = client.post(
                    GENERATE_URL,
                    data={"prompt": "first image"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                r2 = client.post(
                    GENERATE_URL,
                    data={"prompt": "second image"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        assert r1.json()["image_id"] != r2.json()["image_id"]
        assert Image.objects.filter(title="first image").exists()
        assert Image.objects.filter(title="second image").exists()
