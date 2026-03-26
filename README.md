# wagtail-ai-images

A Wagtail plugin that lets admin users generate images from text prompts and save them directly into the Wagtail image library — without leaving the CMS.

**Compatibility:** Wagtail ≥ 6.0 · Django ≥ 5.2 · Python ≥ 3.13

---

## Installation

```bash
# Core (includes Stability AI and custom HTTP providers)
pip install wagtail-ai-images

# With OpenAI DALL·E / Azure OpenAI
pip install "wagtail-ai-images[openai]"

# With Google Imagen (Vertex AI)
pip install "wagtail-ai-images[google]"

# Everything
pip install "wagtail-ai-images[all]"
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "wagtail_ai_images",
]
```

No migrations are required for v0.1.

---

## Configuration

Add `WAGTAIL_AI_IMAGES` to your Django settings. Only the keys you need are required — all others have sensible defaults.

```python
WAGTAIL_AI_IMAGES = {
    "ENABLED": True,
    "PROVIDER": "openai",          # openai | stability | google | azure_openai | custom
    "MAX_PROMPT_LENGTH": 1000,
    "DEFAULT_COLLECTION": "AI Generated",
    "TIMEOUT_SECONDS": 30,
    "PROVIDERS": {
        "openai": {
            "API_KEY_ENV_VAR": "OPENAI_API_KEY",   # name of the env var, not the key itself
            "MODEL": "dall-e-3",
            "DEFAULT_SIZE": "1024x1024",            # 1024x1024 | 1024x1792 | 1792x1024
            "DEFAULT_STYLE": "natural",             # natural | vivid
            "DEFAULT_QUALITY": "standard",          # standard | hd
        },
    },
}
```

Set your API key as an environment variable (never in settings files):

```bash
export OPENAI_API_KEY="sk-..."
```

Switching providers requires changing only `"PROVIDER"`. All provider configs can coexist in the `"PROVIDERS"` dict.

---

## Provider Setup

### OpenAI DALL·E 3

```python
"openai": {
    "API_KEY_ENV_VAR": "OPENAI_API_KEY",
    "MODEL": "dall-e-3",
    "DEFAULT_SIZE": "1024x1024",
    "DEFAULT_STYLE": "natural",
    "DEFAULT_QUALITY": "standard",
}
```

### Stability AI (SDXL)

```python
"stability": {
    "API_KEY_ENV_VAR": "STABILITY_API_KEY",
    "MODEL": "stable-diffusion-xl-1024-v1-0",
    "DEFAULT_SIZE": "1024x1024",
}
```

### Google Imagen (Vertex AI)

Requires a GCP project and [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).

```bash
gcloud auth application-default login
```

```python
"google": {
    "PROJECT_ID": "my-gcp-project",
    "LOCATION": "us-central1",
    "MODEL": "imagegeneration@006",
    "DEFAULT_SIZE": "1024x1024",
}
```

### Azure OpenAI

```python
"azure_openai": {
    "API_KEY_ENV_VAR": "AZURE_OPENAI_API_KEY",
    "ENDPOINT_ENV_VAR": "AZURE_OPENAI_ENDPOINT",   # e.g. https://my-resource.openai.azure.com/
    "DEPLOYMENT": "dall-e-3",
    "API_VERSION": "2024-02-01",
    "DEFAULT_SIZE": "1024x1024",
    "DEFAULT_STYLE": "natural",
    "DEFAULT_QUALITY": "standard",
}
```

### Custom HTTP provider

For any REST API that accepts a prompt and returns an image.

```python
"custom": {
    "ENDPOINT": "https://my-api.example.com/generate",
    "API_KEY_ENV_VAR": "CUSTOM_AI_API_KEY",        # optional
    "AUTH_HEADER": "Authorization",                # default
    "AUTH_PREFIX": "Bearer",                       # default
    "REQUEST_TEMPLATE": {},                        # merged into the POST body
    "RESPONSE_IMAGE_PATH": "data.image",           # dot-path to image data in the JSON response
    "IMAGE_FORMAT": "base64",                      # base64 | url | bytes
    "DEFAULT_SIZE": "1024x1024",
}
```

The provider POSTs `{"prompt": "...", "size": "...", ...REQUEST_TEMPLATE}` and extracts the image using `RESPONSE_IMAGE_PATH`. If `IMAGE_FORMAT` is `"url"`, the image is downloaded immediately so no expiring URLs are stored.

---

## Usage

Navigate to **Generate Image** in the Wagtail sidebar, or go directly to `/admin/ai-images/generate/`.

1. Enter a text prompt describing the image you want.
2. Click **Generate Image** — the image is generated and a preview appears.
3. The image is automatically saved to the Wagtail image library in the configured collection, tagged `ai-generated`.
4. Click **View in image library** to use it in pages, rich text, or the image chooser.

**Required permission:** users must have `wagtailimages.add_image` to access the view.

---

## Security

- API keys are **never** stored in the database or exposed to the browser. The settings dict stores only the *name* of the environment variable.
- All prompt validation runs server-side even when client-side checks pass.
- Set `"ENABLED": False` to disable the feature entirely — the view returns HTTP 403 before reaching any provider.

---

## Development

```bash
uv sync
uv run pytest --cov=wagtail_ai_images --cov-report=term-missing
```

Provider tests use mocked responses — no real API calls are made in CI.

---

## Roadmap

| Version | Features |
|---------|----------|
| **v0.1** | Standalone admin view, five built-in providers, image save to library, permission gating ✓ |
| v0.2 | Style/size selectors in UI, per-user rate limiting, audit log, image chooser integration |
| v0.3 | Third-party provider API, background generation, batch mode, prompt moderation, usage dashboard |
