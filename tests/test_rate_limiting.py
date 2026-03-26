"""
Placeholder for Phase 2 rate-limiting tests.

Per-user rate limiting (RATE_LIMIT setting, HTTP 429 + Retry-After header)
is introduced in v0.2.  Tests will cover:
  - requests within the limit succeed
  - requests exceeding the limit return 429 with Retry-After header
  - limits are scoped per user, not globally
"""
# No tests yet — rate limiting is a v0.2 feature.
