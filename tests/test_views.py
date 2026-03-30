"""
Tests for the GenerateImageView.

Covers:
  - GET renders the form for an authorised user
  - GET is denied when ENABLED=False
  - GET is denied without add_image permission
  - GET redirects to login for anonymous users
  - POST with valid prompt returns JSON success
  - POST with empty prompt returns 400
  - POST with prompt exceeding max_length returns 400
  - POST when provider raises GenerationError returns 502
  - POST when provider raises AuthenticationError returns 500
  - POST when plugin is disabled returns 403
  - POST without permission returns 403
"""
from __future__ import annotations

import base64
import io
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image as PILImage

from tests.factories import StaffUserFactory, StaffUserNoImagePermFactory, SuperuserFactory, UserFactory


def _make_png() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (1, 1), color=(0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


FAKE_PNG = _make_png()
FAKE_B64 = base64.b64encode(FAKE_PNG).decode()

GENERATE_URL = "/admin/ai-images/generate/"


def _mock_provider(image_bytes=FAKE_PNG):
    """Return a mock provider that generates FAKE_PNG."""
    provider = MagicMock()
    provider.get_capabilities.return_value = MagicMock(
        supported_sizes=["1024x1024"],
        supported_styles=["natural"],
    )
    provider.generate.return_value = image_bytes
    return provider


@pytest.mark.django_db
class TestGenerateImageViewGet:
    def test_authenticated_user_with_permission_gets_200(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        with patch("wagtail_ai_images.views.get_provider", return_value=_mock_provider()):
            response = client.get(GENERATE_URL)

        assert response.status_code == 200

    def test_anonymous_user_is_redirected(self):
        client = Client()
        response = client.get(GENERATE_URL)
        assert response.status_code == 302

    def test_user_without_permission_gets_403(self):
        # Staff user (Wagtail admin access) but no add_image permission.
        user = StaffUserNoImagePermFactory()
        client = Client()
        client.force_login(user)

        with patch("wagtail_ai_images.views.get_provider", return_value=_mock_provider()):
            response = client.get(GENERATE_URL)

        assert response.status_code == 403

    @override_settings(WAGTAIL_AI_IMAGES={"ENABLED": False})
    def test_disabled_plugin_returns_403(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = client.get(GENERATE_URL)

        assert response.status_code == 403


@pytest.mark.django_db
class TestGenerateImageViewPost:
    def _post(self, client, prompt, **extra_settings):
        settings_patch = {
            "ENABLED": True,
            "PROVIDER": "openai",
            "MAX_PROMPT_LENGTH": 1000,
            "DEFAULT_COLLECTION": "AI Generated",
            "TIMEOUT_SECONDS": 30,
            "PROVIDERS": {
                "openai": {
                    "API_KEY_ENV_VAR": "OPENAI_API_KEY",
                    "DEFAULT_SIZE": "1024x1024",
                    "DEFAULT_STYLE": "natural",
                }
            },
        }
        settings_patch.update(extra_settings)
        with override_settings(WAGTAIL_AI_IMAGES=settings_patch):
            with patch(
                "wagtail_ai_images.views.get_provider", return_value=_mock_provider()
            ):
                return client.post(
                    GENERATE_URL,
                    data={"prompt": prompt},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

    def test_valid_prompt_returns_json_success(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = self._post(client, "a beautiful sunset")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "image_id" in data
        assert "image_url" in data

    def test_empty_prompt_returns_400(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = self._post(client, "")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "Prompt is required" in data["error"]

    def test_whitespace_only_prompt_returns_400(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = self._post(client, "   ")

        assert response.status_code == 400

    def test_prompt_exceeding_max_length_returns_400(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = self._post(client, "x" * 1001)

        assert response.status_code == 400
        data = response.json()
        assert "1000" in data["error"]

    def test_generation_error_returns_502(self):
        from wagtail_ai_images.exceptions import GenerationError

        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        failing_provider = _mock_provider()
        failing_provider.generate.side_effect = GenerationError("upstream failed")

        with override_settings(
            WAGTAIL_AI_IMAGES={
                "ENABLED": True,
                "PROVIDER": "openai",
                "MAX_PROMPT_LENGTH": 1000,
                "DEFAULT_COLLECTION": "AI Generated",
                "PROVIDERS": {"openai": {"DEFAULT_SIZE": "1024x1024"}},
            }
        ):
            with patch("wagtail_ai_images.views.get_provider", return_value=failing_provider):
                response = client.post(
                    GENERATE_URL,
                    data={"prompt": "a cat"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        assert response.status_code == 502
        assert response.json()["success"] is False

    def test_authentication_error_returns_500(self):
        from wagtail_ai_images.exceptions import AuthenticationError

        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        failing_provider = _mock_provider()
        failing_provider.generate.side_effect = AuthenticationError("bad key")

        with override_settings(
            WAGTAIL_AI_IMAGES={
                "ENABLED": True,
                "PROVIDER": "openai",
                "MAX_PROMPT_LENGTH": 1000,
                "DEFAULT_COLLECTION": "AI Generated",
                "PROVIDERS": {"openai": {"DEFAULT_SIZE": "1024x1024"}},
            }
        ):
            with patch("wagtail_ai_images.views.get_provider", return_value=failing_provider):
                response = client.post(
                    GENERATE_URL,
                    data={"prompt": "a cat"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        assert response.status_code == 500

    @override_settings(WAGTAIL_AI_IMAGES={"ENABLED": False})
    def test_disabled_plugin_returns_403_on_post(self):
        user = SuperuserFactory()
        client = Client()
        client.force_login(user)

        response = client.post(GENERATE_URL, data={"prompt": "a cat"})

        assert response.status_code == 403

    def test_user_without_permission_post_returns_403(self):
        user = StaffUserNoImagePermFactory()
        client = Client()
        client.force_login(user)

        response = self._post(client, "a cat")

        assert response.status_code == 403
