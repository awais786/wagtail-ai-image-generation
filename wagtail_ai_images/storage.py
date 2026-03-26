"""
Image storage helpers for wagtail-ai-images.

save_image() is the single entry point used by views after a provider returns
raw image bytes.  It is kept in its own module so that test_storage.py can
exercise it independently without going through the HTTP stack.
"""
from __future__ import annotations

import logging
from uuid import uuid4

from django.core.files.base import ContentFile

logger = logging.getLogger("ai_images")


def get_or_create_collection(name: str):
    """Return the named Wagtail Collection, creating it under root if absent.

    Uses a simple filter-then-create approach.  The window for a race
    condition is tiny in practice; if two requests collide, the second call
    to add_child() will raise an IntegrityError which Django will surface as
    a 500 — acceptable for a rare edge case in v0.1.
    """
    from wagtail.models import Collection

    collection = Collection.objects.filter(name=name).first()
    if collection is None:
        root = Collection.get_first_root_node()
        collection = root.add_child(name=name)
    return collection


def save_image(image_bytes: bytes, prompt: str, collection_name: str):
    """Persist raw image bytes as a Wagtail Image and return the instance.

    The image is:
    - titled with the prompt text (truncated to 255 chars)
    - stored in the collection named by collection_name (created if absent)
    - tagged "ai-generated" via django-taggit

    Returns the saved Image instance.
    """
    from wagtail.images import get_image_model

    Image = get_image_model()
    collection = get_or_create_collection(collection_name)

    filename = f"ai-{uuid4().hex[:12]}.png"
    image_file = ContentFile(image_bytes, name=filename)

    image = Image(title=prompt[:255], collection=collection)
    image.file = image_file
    image.save()
    image.tags.add("ai-generated")

    return image
