"""
Tests for wagtail_ai_images.storage.

Covers collection creation, image metadata (title truncation, tags,
collection assignment) without going through the HTTP stack.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image as PILImage


def _make_png() -> bytes:
    """Return bytes for a valid 1×1 red PNG that Wagtail/Willow can parse."""
    buf = io.BytesIO()
    PILImage.new("RGB", (1, 1), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


FAKE_PNG = _make_png()


@pytest.mark.django_db
class TestGetOrCreateCollection:
    def test_creates_collection_when_absent(self):
        from wagtail.models import Collection

        from wagtail_ai_images.storage import get_or_create_collection

        name = "My AI Images"
        assert not Collection.objects.filter(name=name).exists()

        collection = get_or_create_collection(name)

        assert collection.pk is not None
        assert collection.name == name
        assert Collection.objects.filter(name=name).exists()

    def test_returns_existing_collection(self):
        from wagtail.models import Collection

        from wagtail_ai_images.storage import get_or_create_collection

        name = "Existing Collection"
        # Create it first.
        root = Collection.get_first_root_node()
        existing = root.add_child(name=name)

        # Should return the same object, not create a duplicate.
        result = get_or_create_collection(name)

        assert result.pk == existing.pk
        assert Collection.objects.filter(name=name).count() == 1


@pytest.mark.django_db
class TestSaveImage:
    def test_saves_image_with_correct_title(self):
        from wagtail.images import get_image_model

        from wagtail_ai_images.storage import save_image

        Image = get_image_model()
        prompt = "A golden sunset over the ocean"
        image = save_image(FAKE_PNG, prompt, "AI Generated")

        assert image.pk is not None
        assert Image.objects.filter(pk=image.pk).exists()
        assert image.title == prompt

    def test_truncates_long_titles_to_255_chars(self):
        from wagtail_ai_images.storage import save_image

        long_prompt = "x" * 400
        image = save_image(FAKE_PNG, long_prompt, "AI Generated")

        assert len(image.title) == 255
        assert image.title == long_prompt[:255]

    def test_assigns_ai_generated_tag(self):
        from wagtail_ai_images.storage import save_image

        image = save_image(FAKE_PNG, "a tagged image", "AI Generated")

        tag_names = [tag.name for tag in image.tags.all()]
        assert "ai-generated" in tag_names

    def test_assigns_correct_collection(self):
        from wagtail_ai_images.storage import save_image

        collection_name = "Test AI Collection"
        image = save_image(FAKE_PNG, "a cat", collection_name)

        assert image.collection.name == collection_name

    def test_creates_collection_if_absent(self):
        from wagtail.models import Collection

        from wagtail_ai_images.storage import save_image

        name = "Brand New Collection"
        assert not Collection.objects.filter(name=name).exists()

        save_image(FAKE_PNG, "a dog", name)

        assert Collection.objects.filter(name=name).exists()

    def test_image_file_is_stored(self):
        from wagtail_ai_images.storage import save_image

        image = save_image(FAKE_PNG, "stored image", "AI Generated")

        assert image.file
        assert image.file.name  # non-empty storage path
