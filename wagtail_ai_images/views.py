"""
Admin view for AI image generation.

GET  /admin/ai-images/generate/  — renders the prompt form
POST /admin/ai-images/generate/  — validates prompt, calls provider, saves image,
                                   returns JSON so generate.js can show a preview
                                   without a full page reload.

Access control (checked on every request):
  1. User must be authenticated.
  2. WAGTAIL_AI_IMAGES["ENABLED"] must be True (default).
  3. User must have the wagtailimages.add_image permission.

Error → HTTP status mapping:
  AuthenticationError   → 500  (bad API key, logged at CRITICAL)
  RateLimitError        → 429  (provider-side limit)
  InvalidPromptError    → 400  (content policy / length)
  GenerationError       → 502  (provider accepted but failed)
  ProviderUnavailableError → 503
  ConfigurationError    → 500
"""
from __future__ import annotations

import logging
import time

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views import View

# Module-level imports so tests can patch at the consumption point.
from .registry import get_provider
from .storage import save_image

logger = logging.getLogger("ai_images")

# Maps exception class name → HTTP status code.
_ERROR_STATUS: dict[str, int] = {
    "AuthenticationError": 500,
    "RateLimitError": 429,
    "InvalidPromptError": 400,
    "GenerationError": 502,
    "ProviderUnavailableError": 503,
    "ConfigurationError": 500,
}


def _settings() -> dict:
    from django.conf import settings

    return getattr(settings, "WAGTAIL_AI_IMAGES", {})


class GenerateImageView(LoginRequiredMixin, View):
    """Standalone admin view — prompt form + AJAX generation endpoint."""

    template_name = "wagtail_ai_images/generate.html"

    def dispatch(self, request, *args, **kwargs):
        # ENABLED check runs before the permission check so that disabling the
        # feature returns 403 even for users who hold add_image.
        if not _settings().get("ENABLED", True):
            if request.method == "POST":
                return JsonResponse(
                    {"success": False, "error": "AI image generation is disabled."},
                    status=403,
                )
            return HttpResponseForbidden("AI image generation is disabled.")
        return super().dispatch(request, *args, **kwargs)

    def _check_permission(self, request):
        """Return an HttpResponseForbidden if the user lacks add_image, else None.

        Called at the top of get() and post() rather than in dispatch() so
        that LoginRequiredMixin can redirect unauthenticated users before we
        check permissions (avoiding a 403 when a 302 is more helpful).
        """
        if not request.user.has_perm("wagtailimages.add_image"):
            return HttpResponseForbidden("You do not have permission to generate images.")
        return None

    # ------------------------------------------------------------------
    # GET — render the prompt form
    # ------------------------------------------------------------------

    def get(self, request):
        denied = self._check_permission(request)
        if denied:
            return denied

        from .exceptions import ConfigurationError

        ai_settings = _settings()
        provider_name = ai_settings.get("PROVIDER", "openai")

        capabilities = None
        try:
            provider = get_provider(provider_name)
            capabilities = provider.get_capabilities()
        except ConfigurationError as exc:
            logger.error(
                "ai_images.generate provider_config_error provider=%s error=%s",
                provider_name,
                exc,
            )

        context = {
            "max_prompt_length": ai_settings.get("MAX_PROMPT_LENGTH", 1000),
            "provider_name": provider_name,
            "capabilities": capabilities,
        }
        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # POST — validate → generate → save → JSON
    # ------------------------------------------------------------------

    def post(self, request):
        denied = self._check_permission(request)
        if denied:
            return JsonResponse({"success": False, "error": "Permission denied."}, status=403)

        from django.urls import reverse

        from .exceptions import AuthenticationError, ProviderError

        ai_settings = _settings()
        provider_name = ai_settings.get("PROVIDER", "openai")
        settings_max_length = ai_settings.get("MAX_PROMPT_LENGTH", 1000)
        collection_name = ai_settings.get("DEFAULT_COLLECTION", "AI Generated")

        # --- server-side prompt validation (empty check before provider call) ---
        prompt = request.POST.get("prompt", "").strip()
        if not prompt:
            return JsonResponse({"success": False, "error": "Prompt is required."}, status=400)

        start = time.monotonic()
        try:
            provider = get_provider(provider_name)
            capabilities = provider.get_capabilities()

            # Enforce the tighter of the settings limit and the provider's own limit.
            effective_max = min(settings_max_length, capabilities.max_prompt_length)
            if len(prompt) > effective_max:
                return JsonResponse(
                    {"success": False, "error": f"Prompt exceeds {effective_max} characters."},
                    status=400,
                )

            # Use the provider's configured default size/style for v0.1.
            # Size/style selectors in the UI are a v0.2 feature.
            provider_config = ai_settings.get("PROVIDERS", {}).get(provider_name, {})
            size = provider_config.get("DEFAULT_SIZE") or capabilities.supported_sizes[0]
            if size not in capabilities.supported_sizes:
                logger.warning(
                    "ai_images.generate: DEFAULT_SIZE '%s' not in supported sizes %s for provider '%s'; "
                    "falling back to '%s'.",
                    size,
                    capabilities.supported_sizes,
                    provider_name,
                    capabilities.supported_sizes[0],
                )
                size = capabilities.supported_sizes[0]
            style = provider_config.get("DEFAULT_STYLE")
            if style and (
                capabilities.supported_styles is None
                or style not in capabilities.supported_styles
            ):
                style = None

            image_bytes = provider.generate(prompt=prompt, size=size, style=style)
            image = save_image(image_bytes, prompt, collection_name)

        except ProviderError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            exc_type = type(exc).__name__
            log_level = logging.CRITICAL if isinstance(exc, AuthenticationError) else logging.ERROR
            logger.log(
                log_level,
                "ai_images.generate user=%s provider=%s status=error error=%s duration_ms=%d",
                request.user,
                provider_name,
                exc,
                duration_ms,
            )
            http_status = _ERROR_STATUS.get(exc_type, 500)
            return JsonResponse({"success": False, "error": str(exc)}, status=http_status)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "ai_images.generate user=%s prompt=%r provider=%s status=200 image_id=%d duration_ms=%d",
            request.user,
            prompt,
            provider_name,
            image.pk,
            duration_ms,
        )

        return JsonResponse(
            {
                "success": True,
                "image_id": image.pk,
                "image_url": image.file.url,
                "image_title": image.title,
                "image_edit_url": reverse("wagtailimages:edit", args=[image.pk]),
            }
        )
