# CLAUDE.md — wagtail-ai-images

## Project Overview

`wagtail-ai-images` is a Wagtail CMS plugin that embeds AI image generation directly into the admin interface. Users enter a text prompt and the generated image is saved straight into the Wagtail image library. The plugin ships with adapters for OpenAI DALL·E, Stability AI, Google Imagen, Azure OpenAI, and a generic custom HTTP provider.

**Target compatibility:** Wagtail ≥ 6.0, Django ≥ 5.2, Python ≥ 3.13  
**Install:** `pip install wagtail-ai-images`

---

## Repository Layout

```
wagtail_ai_images/
├── __init__.py
├── apps.py
├── wagtail_hooks.py          # Registers admin URLs and menu items
├── views.py                  # Admin generation view
├── models.py                 # AIGeneratedImage metadata model (Phase 2)
├── registry.py               # Provider registration and lookup
├── exceptions.py             # ProviderError hierarchy
├── providers/
│   ├── base.py               # ImageProvider ABC + ProviderCapabilities dataclass
│   ├── openai.py
│   ├── stability.py
│   ├── google.py
│   ├── azure_openai.py
│   └── custom.py             # Generic HTTP adapter
├── static/wagtail_ai_images/
│   └── js/generate.js        # Frontend — fetch, loading state, preview
└── templates/wagtail_ai_images/
    └── generate.html

tests/
├── factories.py
├── test_providers.py
├── test_models.py
├── test_views.py
├── test_storage.py
├── test_rate_limiting.py
└── test_integration.py
```

---

## Core Architecture

### Provider Adapter Pattern

Every provider implements the `ImageProvider` ABC defined in `providers/base.py`. **The UI reads capabilities from the active provider at runtime** — never hard-code provider-specific sizes, styles, or feature flags in templates or views.

```python
# providers/base.py
@dataclass
class ProviderCapabilities:
    supported_sizes: list[str]
    supported_styles: list[str] | None
    max_prompt_length: int
    supports_negative_prompt: bool

class ImageProvider(ABC):
    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    def generate(self, prompt: str, size: str, style: str | None, **kwargs) -> bytes: ...

    @abstractmethod
    def validate_config(self) -> bool: ...
```

`generate()` must return **raw image bytes**, not a URL — download immediately to avoid expiry.

### Provider Registry

```python
# registry.py
def register_provider(name: str, cls: type[ImageProvider]) -> None: ...
def get_provider(name: str) -> ImageProvider: ...
```

Third-party packages register providers in their `AppConfig.ready()`. Built-in providers are auto-registered at app startup.

### Error Handling

All provider-specific errors must be caught and re-raised as subclasses of `ProviderError` (defined in `exceptions.py`). Views translate `ProviderError` subclasses into the user-facing messages listed in the spec. Never let raw API exceptions reach the template.

---

## Settings

All configuration lives under `WAGTAIL_AI_IMAGES` in Django settings. **API keys are read exclusively from environment variables** — the setting stores the env var name, not the key value.

```python
WAGTAIL_AI_IMAGES = {
    "ENABLED": True,
    "PROVIDER": "openai",          # must match a registered provider ID
    "RATE_LIMIT": "10/h",
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
        # stability, google, azure_openai, custom — see spec Section 7
    },
}
```

Switching providers requires changing only `"PROVIDER"` — all provider configs coexist.

---

## Permissions & Security

- Gate every view on `wagtailimages.add_image` permission. Staff flag alone is not sufficient.
- API keys **must never** reach the frontend or be stored in the database or settings files.
- Validate prompt server-side (non-empty, ≤ `MAX_PROMPT_LENGTH` chars) even if client-side validation already blocks it.
- Rate limiting is enforced per-user. Return HTTP 429 with a `Retry-After` header when the limit is exceeded.
- When `ENABLED` is `False`, return HTTP 403 immediately — don't reach the provider at all.

---

## Image Storage

Generated images are saved as standard `wagtail.images.models.Image` instances:

| Field | Value |
|---|---|
| `title` | Prompt text, truncated to 255 chars |
| `file` | Written to Wagtail's configured storage backend |
| `collection` | `DEFAULT_COLLECTION` setting (created if absent) |
| tags | Auto-tagged `ai-generated` |

Phase 2 adds `AIGeneratedImage` (one-to-one with `Image`) storing prompt, provider, model, style, size, requesting user, timestamp, and API response status.

---

## Admin Integration

| Phase | Integration point | Mechanism |
|---|---|---|
| 1 | Standalone view at `/admin/ai-images/generate/` | `wagtail_hooks.py` → `register_admin_urls` |
| 2 | "Generate" tab in image chooser modal | Custom chooser viewset |
| 2 | Image library action button | `construct_main_menu` hook |

---

## Built-in Providers

| ID | API | Transport |
|---|---|---|
| `openai` | OpenAI DALL·E 3 | `openai` Python SDK |
| `stability` | Stability AI SDXL/SD3 | `httpx` (REST) |
| `google` | Google Imagen / Vertex AI | `google-cloud-aiplatform` |
| `azure_openai` | Azure OpenAI DALL·E | `openai` SDK with Azure config |
| `custom` | Any REST API | `httpx` with configurable request/response mapping |

Install only the SDKs you need via extras, e.g. `pip install wagtail-ai-images[openai]`. The `custom` and `azure_openai` providers have no extra SDK dependency.

---

## Development Phases

- **v0.1 (MVP):** Standalone admin view, provider adapter layer, all five built-in providers, image save to library, basic error handling, staff-only gating, loading state.
- **v0.2:** Style/size/provider selectors in UI, `AIGeneratedImage` metadata model, per-user rate limiting, audit logging, image chooser integration.
- **v0.3:** Custom provider registration API for third parties, background tasks (Celery/Django-Q), batch generation, prompt moderation, admin dashboard with usage stats and cost tracking.

---

## Package Management

Use **`uv`** for all Python package and environment management. Do not use `pip`, `pip-compile`, or `virtualenv` directly.

```bash
# Create/sync the environment
uv sync

# Add a dependency
uv add httpx
uv add --optional openai openai        # provider extras
uv add --dev pytest pytest-cov factory-boy

# Run commands inside the managed environment
uv run pytest
uv run django-admin ...

# Install the package itself in editable mode (first-time setup)
uv pip install -e ".[openai]"
```

The `pyproject.toml` is the single source of truth for dependencies. Do not edit `requirements*.txt` files by hand — let `uv` manage the lockfile (`uv.lock`).

---

## Testing

```bash
uv run pytest --cov=wagtail_ai_images --cov-report=term-missing
```

**Rules:**
- All provider tests use mocked responses — **no real API calls in CI**.
- Target ≥ 80% code coverage via `pytest-cov`.
- Use `factory_boy` factories from `tests/factories.py` for model setup.
- Integration tests (`test_integration.py`) cover the full prompt → generate → save → library flow using Wagtail's test infrastructure.

Test files map to modules: `test_providers.py`, `test_models.py`, `test_views.py`, `test_storage.py`, `test_rate_limiting.py`, `test_integration.py`.

---

## Logging

Phase 1 uses structured log lines — always include `user`, `prompt`, `provider`, `status`, and `duration_ms` (or `error`):

```
INFO  ai_images.generate user=admin prompt="..." provider=openai status=200 image_id=142 duration_ms=8430
ERROR ai_images.generate user=admin prompt="..." provider=openai status=429 error="rate_limit_exceeded"
```

Log invalid API key errors at `CRITICAL` level. Phase 2 adds database audit logging via `AIGeneratedImage`.

---

## Key Conventions

- **Never expose API keys** to templates, JS, or the database. Read from env vars only.
- **Provider capabilities drive the UI** — sizes, styles, and optional fields (e.g. negative prompt) are determined by `get_capabilities()` at runtime, not hard-coded.
- **`generate()` returns bytes** — download remote URLs before returning; never store a provider URL.
- **Raise `ProviderError` subclasses** from all provider code — never let SDK exceptions bubble into views.
- **Register providers in `AppConfig.ready()`** — third-party providers follow the same pattern as built-ins.
- **One settings key to switch providers** — `WAGTAIL_AI_IMAGES["PROVIDER"]` is the only required change.