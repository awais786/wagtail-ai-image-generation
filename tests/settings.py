"""
Minimal Django/Wagtail settings for the test suite.
"""
import os
import tempfile

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "wagtail",
    "wagtail.admin",
    "wagtail.images",
    "wagtail.documents",
    "wagtail.snippets",
    "wagtail.users",
    "wagtail.sites",
    "wagtail.search",
    "taggit",
    "wagtail_ai_images",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# Use a temp directory so image files don't litter the source tree.
MEDIA_ROOT = os.path.join(tempfile.gettempdir(), "wagtail_ai_images_test_media")
MEDIA_URL = "/media/"

# Faster password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

WAGTAIL_SITE_NAME = "Test Site"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAGTAIL_AI_IMAGES = {
    "ENABLED": True,
    "PROVIDER": "openai",
    "MAX_PROMPT_LENGTH": 1000,
    "DEFAULT_COLLECTION": "AI Generated",
    "TIMEOUT_SECONDS": 30,
    "PROVIDERS": {
        "openai": {
            "API_KEY_ENV_VAR": "OPENAI_API_KEY",
            "MODEL": "dall-e-3",
            "DEFAULT_SIZE": "1024x1024",
            "DEFAULT_STYLE": "natural",
            "DEFAULT_QUALITY": "standard",
        },
        "stability": {
            "API_KEY_ENV_VAR": "STABILITY_API_KEY",
            "MODEL": "stable-diffusion-xl-1024-v1-0",
            "DEFAULT_SIZE": "1024x1024",
        },
        "google": {
            "PROJECT_ID": "test-project",
            "LOCATION": "us-central1",
            "MODEL": "imagegeneration@006",
            "DEFAULT_SIZE": "1024x1024",
        },
        "azure_openai": {
            "API_KEY_ENV_VAR": "AZURE_OPENAI_API_KEY",
            "ENDPOINT_ENV_VAR": "AZURE_OPENAI_ENDPOINT",
            "DEPLOYMENT": "dall-e-3",
            "API_VERSION": "2024-02-01",
            "DEFAULT_SIZE": "1024x1024",
            "DEFAULT_STYLE": "natural",
            "DEFAULT_QUALITY": "standard",
        },
        "custom": {
            "ENDPOINT": "https://api.example.com/generate",
            "API_KEY_ENV_VAR": "CUSTOM_AI_API_KEY",
            "RESPONSE_IMAGE_PATH": "data.image",
            "IMAGE_FORMAT": "base64",
            "DEFAULT_SIZE": "1024x1024",
        },
    },
}
