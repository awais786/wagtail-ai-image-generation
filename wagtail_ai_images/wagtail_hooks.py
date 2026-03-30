"""
Wagtail hooks for wagtail-ai-images.

Phase 1 registers:
  - An admin URL at /admin/ai-images/generate/
  - A sidebar menu item so users can discover the feature
"""
from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.menu import MenuItem


@hooks.register("register_admin_urls")
def register_ai_images_urls():
    from .views import GenerateImageView

    return [
        path(
            "ai-images/generate/",
            GenerateImageView.as_view(),
            name="wagtail_ai_images_generate",
        ),
    ]


@hooks.register("register_admin_menu_item")
def register_ai_images_menu_item():
    from django.urls import reverse

    return MenuItem(
        label=_("Generate Image"),
        url=reverse("wagtail_ai_images_generate"),
        icon_name="image",
        order=10000,
    )
