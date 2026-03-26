"""
AppConfig for wagtail-ai-images.

Registers built-in providers in ready().  Providers whose SDK is not
installed are silently skipped at registration time; a ConfigurationError
is raised later when the missing provider is actually requested.

The active provider's validate_config() is called at startup to emit early
warning log messages when API key environment variables are absent.
"""
import logging

from django.apps import AppConfig

logger = logging.getLogger("ai_images")


class WagtailAiImagesConfig(AppConfig):
    name = "wagtail_ai_images"
    label = "wagtail_ai_images"
    verbose_name = "Wagtail AI Images"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        self._register_providers()
        self._validate_active_provider()

    # ------------------------------------------------------------------
    # Provider registration
    # ------------------------------------------------------------------

    def _register_providers(self) -> None:
        from .registry import register_provider

        # Providers that always register (httpx is a core dependency).
        from .providers.stability import StabilityProvider
        from .providers.azure_openai import AzureOpenAIProvider
        from .providers.custom import CustomProvider

        register_provider("stability", StabilityProvider)
        register_provider("azure_openai", AzureOpenAIProvider)
        register_provider("custom", CustomProvider)

        # Providers that require optional SDK extras.
        try:
            from .providers.openai import OpenAIProvider

            register_provider("openai", OpenAIProvider)
        except ImportError:
            logger.debug(
                "ai_images.startup: openai SDK not installed; 'openai' provider unavailable."
            )

        try:
            from .providers.google import GoogleProvider

            register_provider("google", GoogleProvider)
        except ImportError:
            logger.debug(
                "ai_images.startup: google-auth not installed; 'google' provider unavailable."
            )

    # ------------------------------------------------------------------
    # Startup validation
    # ------------------------------------------------------------------

    def _validate_active_provider(self) -> None:
        from django.conf import settings

        from .registry import _registry, get_provider

        ai_settings = getattr(settings, "WAGTAIL_AI_IMAGES", {})
        if not ai_settings.get("ENABLED", True):
            return

        provider_name = ai_settings.get("PROVIDER", "openai")

        if provider_name not in _registry:
            logger.warning(
                "ai_images.startup: configured provider '%s' is not registered. "
                "Is the required SDK extra installed?",
                provider_name,
            )
            return

        try:
            provider = get_provider(provider_name)
            if not provider.validate_config():
                logger.warning(
                    "ai_images.startup: provider '%s' validate_config() returned False. "
                    "Check that the required API key environment variable is set.",
                    provider_name,
                )
        except Exception as exc:
            logger.error(
                "ai_images.startup: error validating provider '%s': %s",
                provider_name,
                exc,
            )
