"""
Provider unit tests.

All tests mock external HTTP calls and SDK calls — no real API traffic.
Each provider is tested for:
  - happy path: generate() returns bytes
  - authentication failure → AuthenticationError
  - bad request → InvalidPromptError
  - connectivity failure → ProviderUnavailableError (where applicable)
  - validate_config() logic
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from wagtail_ai_images.exceptions import (
    AuthenticationError,
    ConfigurationError,
    GenerationError,
    InvalidPromptError,
    ProviderUnavailableError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # minimal PNG-ish bytes
FAKE_B64 = base64.b64encode(FAKE_PNG).decode()


def _make_openai_mock_sdk():
    """Return a MagicMock whose exception attributes are real Exception subclasses.

    The provider does ``except _openai_sdk.SomeError:`` which requires the
    attribute to be an actual class inheriting from BaseException — a plain
    MagicMock() attribute raises TypeError at runtime.
    """
    mock = MagicMock()
    mock.AuthenticationError = type("AuthenticationError", (Exception,), {})
    mock.BadRequestError = type("BadRequestError", (Exception,), {})
    mock.RateLimitError = type("RateLimitError", (Exception,), {})
    mock.APIConnectionError = type("APIConnectionError", (Exception,), {})
    mock.APIError = type("APIError", (Exception,), {})
    return mock


def _make_httpx_response(status_code: int, json_body=None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


@pytest.fixture
def openai_config():
    return {
        "API_KEY_ENV_VAR": "OPENAI_API_KEY",
        "MODEL": "dall-e-3",
        "DEFAULT_SIZE": "1024x1024",
        "DEFAULT_STYLE": "natural",
        "DEFAULT_QUALITY": "standard",
    }


class TestOpenAIProvider:
    def test_generate_returns_bytes(self, openai_config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_sdk = _make_openai_mock_sdk()
        mock_sdk.OpenAI.return_value.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=FAKE_B64)]
        )
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            result = OpenAIProvider(openai_config).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_generate_uses_b64_json_format(self, openai_config, monkeypatch):
        """generate() must request b64_json, not url, to avoid expiry."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_sdk = _make_openai_mock_sdk()
        mock_sdk.OpenAI.return_value.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=FAKE_B64)]
        )
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            OpenAIProvider(openai_config).generate("a cat", "1024x1024")

        call_kwargs = mock_sdk.OpenAI.return_value.images.generate.call_args.kwargs
        assert call_kwargs["response_format"] == "b64_json"

    def test_auth_error_wraps_to_provider_error(self, openai_config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "bad-key")
        mock_sdk = _make_openai_mock_sdk()
        mock_sdk.OpenAI.return_value.images.generate.side_effect = mock_sdk.AuthenticationError(
            "invalid key"
        )
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            with pytest.raises(AuthenticationError):
                OpenAIProvider(openai_config).generate("a cat", "1024x1024")

    def test_bad_request_wraps_to_invalid_prompt(self, openai_config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_sdk = _make_openai_mock_sdk()
        mock_sdk.OpenAI.return_value.images.generate.side_effect = mock_sdk.BadRequestError(
            "content policy"
        )
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            with pytest.raises(InvalidPromptError):
                OpenAIProvider(openai_config).generate("bad prompt", "1024x1024")

    def test_missing_api_key_raises_auth_error(self, openai_config, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_sdk = _make_openai_mock_sdk()
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            with pytest.raises(AuthenticationError, match="OPENAI_API_KEY"):
                OpenAIProvider(openai_config).generate("a cat", "1024x1024")

    def test_sdk_not_installed_raises_config_error(self, openai_config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", None):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            provider = OpenAIProvider(openai_config)
            with pytest.raises(ConfigurationError, match="openai SDK"):
                provider.generate("a cat", "1024x1024")

    def test_validate_config_true_when_key_set(self, openai_config, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_sdk = _make_openai_mock_sdk()
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            assert OpenAIProvider(openai_config).validate_config() is True

    def test_validate_config_false_when_key_missing(self, openai_config, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_sdk = _make_openai_mock_sdk()
        from wagtail_ai_images.providers import openai as openai_mod

        with patch.object(openai_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.openai import OpenAIProvider

            assert OpenAIProvider(openai_config).validate_config() is False


# ---------------------------------------------------------------------------
# Stability provider
# ---------------------------------------------------------------------------


@pytest.fixture
def stability_config():
    return {
        "API_KEY_ENV_VAR": "STABILITY_API_KEY",
        "MODEL": "stable-diffusion-xl-1024-v1-0",
        "DEFAULT_SIZE": "1024x1024",
    }


class TestStabilityProvider:
    def _mock_success_response(self):
        return _make_httpx_response(
            200,
            json_body={"artifacts": [{"base64": FAKE_B64, "finishReason": "SUCCESS"}]},
        )

    def test_generate_returns_bytes(self, stability_config, monkeypatch):
        monkeypatch.setenv("STABILITY_API_KEY", "sk-stability")

        from wagtail_ai_images.providers.stability import StabilityProvider

        with patch("wagtail_ai_images.providers.stability.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                self._mock_success_response()
            )
            result = StabilityProvider(stability_config).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_401_raises_auth_error(self, stability_config, monkeypatch):
        monkeypatch.setenv("STABILITY_API_KEY", "bad")

        from wagtail_ai_images.providers.stability import StabilityProvider

        with patch("wagtail_ai_images.providers.stability.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                _make_httpx_response(401)
            )
            with pytest.raises(AuthenticationError):
                StabilityProvider(stability_config).generate("a cat", "1024x1024")

    def test_400_raises_invalid_prompt(self, stability_config, monkeypatch):
        monkeypatch.setenv("STABILITY_API_KEY", "sk-stability")

        from wagtail_ai_images.providers.stability import StabilityProvider

        with patch("wagtail_ai_images.providers.stability.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                _make_httpx_response(400, json_body={"message": "prompt too long"})
            )
            with pytest.raises(InvalidPromptError, match="prompt too long"):
                StabilityProvider(stability_config).generate("x" * 3000, "1024x1024")

    def test_connect_error_raises_unavailable(self, stability_config, monkeypatch):
        monkeypatch.setenv("STABILITY_API_KEY", "sk-stability")
        import httpx as _httpx

        from wagtail_ai_images.providers.stability import StabilityProvider

        with patch("wagtail_ai_images.providers.stability.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                _httpx.ConnectError("connection refused")
            )
            with pytest.raises(ProviderUnavailableError):
                StabilityProvider(stability_config).generate("a cat", "1024x1024")

    def test_missing_api_key_raises_auth_error(self, stability_config, monkeypatch):
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)

        from wagtail_ai_images.providers.stability import StabilityProvider

        with pytest.raises(AuthenticationError, match="STABILITY_API_KEY"):
            StabilityProvider(stability_config).generate("a cat", "1024x1024")

    def test_validate_config(self, stability_config, monkeypatch):
        from wagtail_ai_images.providers.stability import StabilityProvider

        monkeypatch.setenv("STABILITY_API_KEY", "sk-stability")
        assert StabilityProvider(stability_config).validate_config() is True

        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        assert StabilityProvider(stability_config).validate_config() is False


# ---------------------------------------------------------------------------
# Google provider
# ---------------------------------------------------------------------------


@pytest.fixture
def google_config():
    return {
        "PROJECT_ID": "my-project",
        "LOCATION": "us-central1",
        "MODEL": "imagegeneration@006",
        "DEFAULT_SIZE": "1024x1024",
    }


class TestGoogleProvider:
    def test_generate_returns_bytes(self, google_config):
        mock_google = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_google.auth.default.return_value = (mock_creds, "project")

        from wagtail_ai_images.providers import google as google_mod

        with patch.object(google_mod, "google", mock_google):
            with patch("wagtail_ai_images.providers.google.httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = (
                    _make_httpx_response(
                        200,
                        json_body={"predictions": [{"bytesBase64Encoded": FAKE_B64}]},
                    )
                )
                from wagtail_ai_images.providers.google import GoogleProvider

                result = GoogleProvider(google_config).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_missing_project_id_raises_config_error(self):
        mock_google = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_google.auth.default.return_value = (mock_creds, "project")

        from wagtail_ai_images.providers import google as google_mod

        with patch.object(google_mod, "google", mock_google):
            from wagtail_ai_images.providers.google import GoogleProvider

            provider = GoogleProvider({})  # no PROJECT_ID
            with pytest.raises(ConfigurationError, match="PROJECT_ID"):
                provider.generate("a cat", "1024x1024")

    def test_sdk_not_installed_raises_config_error(self, google_config):
        from wagtail_ai_images.providers import google as google_mod

        with patch.object(google_mod, "google", None):
            from wagtail_ai_images.providers.google import GoogleProvider

            provider = GoogleProvider(google_config)
            with pytest.raises(ConfigurationError, match="google-auth"):
                provider.generate("a cat", "1024x1024")

    def test_401_raises_auth_error(self, google_config):
        mock_google = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "bad-token"
        mock_google.auth.default.return_value = (mock_creds, "project")

        from wagtail_ai_images.providers import google as google_mod

        with patch.object(google_mod, "google", mock_google):
            with patch("wagtail_ai_images.providers.google.httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = (
                    _make_httpx_response(401)
                )
                from wagtail_ai_images.providers.google import GoogleProvider

                with pytest.raises(AuthenticationError):
                    GoogleProvider(google_config).generate("a cat", "1024x1024")

    def test_empty_predictions_raises_generation_error(self, google_config):
        mock_google = MagicMock()
        mock_creds = MagicMock()
        mock_creds.token = "access-token"
        mock_google.auth.default.return_value = (mock_creds, "project")

        from wagtail_ai_images.providers import google as google_mod

        with patch.object(google_mod, "google", mock_google):
            with patch("wagtail_ai_images.providers.google.httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = (
                    _make_httpx_response(200, json_body={"predictions": []})
                )
                from wagtail_ai_images.providers.google import GoogleProvider

                with pytest.raises(GenerationError, match="no predictions"):
                    GoogleProvider(google_config).generate("a cat", "1024x1024")


# ---------------------------------------------------------------------------
# Azure OpenAI provider
# ---------------------------------------------------------------------------


@pytest.fixture
def azure_config():
    return {
        "API_KEY_ENV_VAR": "AZURE_OPENAI_API_KEY",
        "ENDPOINT_ENV_VAR": "AZURE_OPENAI_ENDPOINT",
        "DEPLOYMENT": "dall-e-3",
        "API_VERSION": "2024-02-01",
        "DEFAULT_SIZE": "1024x1024",
        "DEFAULT_STYLE": "natural",
        "DEFAULT_QUALITY": "standard",
    }


class TestAzureOpenAIProvider:
    def test_generate_returns_bytes(self, azure_config, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://myendpoint.openai.azure.com/")
        mock_sdk = _make_openai_mock_sdk()
        mock_sdk.AzureOpenAI.return_value.images.generate.return_value = MagicMock(
            data=[MagicMock(b64_json=FAKE_B64)]
        )
        from wagtail_ai_images.providers import azure_openai as az_mod

        with patch.object(az_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.azure_openai import AzureOpenAIProvider

            result = AzureOpenAIProvider(azure_config).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_missing_endpoint_raises_config_error(self, azure_config, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-key")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        mock_sdk = _make_openai_mock_sdk()
        from wagtail_ai_images.providers import azure_openai as az_mod

        with patch.object(az_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.azure_openai import AzureOpenAIProvider

            with pytest.raises(ConfigurationError, match="AZURE_OPENAI_ENDPOINT"):
                AzureOpenAIProvider(azure_config).generate("a cat", "1024x1024")

    def test_validate_config_requires_both_env_vars(self, azure_config, monkeypatch):
        mock_sdk = _make_openai_mock_sdk()
        from wagtail_ai_images.providers import azure_openai as az_mod

        with patch.object(az_mod, "_openai_sdk", mock_sdk):
            from wagtail_ai_images.providers.azure_openai import AzureOpenAIProvider

            monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
            monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
            assert AzureOpenAIProvider(azure_config).validate_config() is False

            monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
            assert AzureOpenAIProvider(azure_config).validate_config() is False

            monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://endpoint/")
            assert AzureOpenAIProvider(azure_config).validate_config() is True


# ---------------------------------------------------------------------------
# Custom provider
# ---------------------------------------------------------------------------


@pytest.fixture
def custom_config():
    return {
        "ENDPOINT": "https://api.example.com/generate",
        "API_KEY_ENV_VAR": "CUSTOM_AI_API_KEY",
        "RESPONSE_IMAGE_PATH": "data.image",
        "IMAGE_FORMAT": "base64",
        "DEFAULT_SIZE": "1024x1024",
    }


class TestCustomProvider:
    def test_generate_base64_format(self, custom_config, monkeypatch):
        monkeypatch.setenv("CUSTOM_AI_API_KEY", "custom-key")

        from wagtail_ai_images.providers.custom import CustomProvider

        with patch("wagtail_ai_images.providers.custom.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                _make_httpx_response(200, json_body={"data": {"image": FAKE_B64}})
            )
            result = CustomProvider(custom_config).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_generate_url_format_downloads_image(self, custom_config, monkeypatch):
        monkeypatch.delenv("CUSTOM_AI_API_KEY", raising=False)

        cfg = dict(custom_config)
        cfg["IMAGE_FORMAT"] = "url"
        cfg["RESPONSE_IMAGE_PATH"] = "url"

        from wagtail_ai_images.providers.custom import CustomProvider

        download_response = MagicMock()
        download_response.content = FAKE_PNG
        download_response.raise_for_status = MagicMock()

        with patch("wagtail_ai_images.providers.custom.httpx.Client") as mock_client:
            generate_resp = _make_httpx_response(
                200, json_body={"url": "https://cdn.example.com/image.png"}
            )
            download_client = MagicMock()
            download_client.__enter__ = MagicMock(return_value=download_client)
            download_client.__exit__ = MagicMock(return_value=False)
            download_client.get.return_value = download_response

            mock_client.return_value.__enter__.return_value.post.return_value = generate_resp
            mock_client.return_value = MagicMock()
            mock_client.return_value.__enter__ = MagicMock(
                side_effect=[
                    mock_client.return_value.__enter__.return_value,
                    download_client,
                ]
            )
            mock_client.return_value.__exit__ = MagicMock(return_value=False)

            # Simpler: patch both calls separately.
            with patch("wagtail_ai_images.providers.custom.httpx.Client") as mc:
                post_ctx = MagicMock()
                post_ctx.__enter__ = MagicMock(return_value=post_ctx)
                post_ctx.__exit__ = MagicMock(return_value=False)
                post_ctx.post.return_value = _make_httpx_response(
                    200, json_body={"url": "https://cdn.example.com/image.png"}
                )

                get_ctx = MagicMock()
                get_ctx.__enter__ = MagicMock(return_value=get_ctx)
                get_ctx.__exit__ = MagicMock(return_value=False)
                get_ctx.get.return_value = download_response

                mc.side_effect = [post_ctx, get_ctx]

                result = CustomProvider(cfg).generate("a cat", "1024x1024")

        assert result == FAKE_PNG

    def test_missing_endpoint_raises_config_error(self):
        from wagtail_ai_images.providers.custom import CustomProvider

        cfg = {"RESPONSE_IMAGE_PATH": "data.image", "IMAGE_FORMAT": "base64"}
        with pytest.raises(ConfigurationError, match="ENDPOINT"):
            CustomProvider(cfg).generate("a cat", "1024x1024")

    def test_bad_response_path_raises_generation_error(self, custom_config, monkeypatch):

        from wagtail_ai_images.providers.custom import CustomProvider

        with patch("wagtail_ai_images.providers.custom.httpx.Client") as mock_client:
            # Response has no "data.image" path.
            mock_client.return_value.__enter__.return_value.post.return_value = (
                _make_httpx_response(200, json_body={"result": "oops"})
            )
            with pytest.raises(GenerationError, match="data"):
                CustomProvider(custom_config).generate("a cat", "1024x1024")

    def test_unknown_image_format_raises_config_error(self, custom_config, monkeypatch):
        cfg = dict(custom_config)
        cfg["IMAGE_FORMAT"] = "invalid"
        cfg["RESPONSE_IMAGE_PATH"] = "img"

        from wagtail_ai_images.providers.custom import CustomProvider

        with patch("wagtail_ai_images.providers.custom.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                _make_httpx_response(200, json_body={"img": "abc"})
            )
            with pytest.raises(ConfigurationError, match="IMAGE_FORMAT"):
                CustomProvider(cfg).generate("a cat", "1024x1024")

    def test_validate_config(self, custom_config):
        from wagtail_ai_images.providers.custom import CustomProvider

        assert CustomProvider(custom_config).validate_config() is True

        cfg = dict(custom_config)
        del cfg["ENDPOINT"]
        assert CustomProvider(cfg).validate_config() is False


# ---------------------------------------------------------------------------
# ProviderCapabilities
# ---------------------------------------------------------------------------


class TestProviderCapabilities:
    def test_capabilities_dataclass(self):
        from wagtail_ai_images.providers.base import ProviderCapabilities

        caps = ProviderCapabilities(
            supported_sizes=["1024x1024"],
            supported_styles=["natural"],
            max_prompt_length=4000,
            supports_negative_prompt=False,
        )
        assert caps.supported_sizes == ["1024x1024"]
        assert caps.supports_negative_prompt is False
