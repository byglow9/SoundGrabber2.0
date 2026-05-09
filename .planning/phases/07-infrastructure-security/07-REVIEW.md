---
phase: 07-infrastructure-security
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - api/config.py
  - api/main.py
  - tests/conftest.py
  - tests/test_security.py
  - railway.toml
  - Procfile
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-09
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This phase adds three deliverables: (1) `_check_redis_auth` enforcing Redis authentication at startup, (2) the HSTS `Strict-Transport-Security` header in the `_security_headers` middleware, and (3) Railway deployment configuration via `railway.toml` and `Procfile`. The test suite covers all new behaviors with both positive and negative paths.

The core security controls are correctly implemented and the test coverage is solid. However, there is one critical correctness bug in the Redis auth check (a URL with an empty username/password still passes the `"@"` detection), four warnings covering logic gaps and missing test guards, and three informational items.

---

## Critical Issues

### CR-01: `_check_redis_auth` accepts URLs with `@` but no actual credentials

**File:** `api/main.py:130`

**Issue:** The check `if "@" not in redis_url` only confirms the presence of the `@` character, not that actual credentials are present. A URL such as `redis://@localhost:6379` (empty userinfo) or `redis://:@localhost:6379` (empty password only) will satisfy the check and pass the gate, but Redis will receive no authentication. An operator who sets a malformed `REDIS_URL` — or who makes a copy-paste error — will get a false sense of security: startup succeeds, but Redis is effectively unauthenticated.

**Fix:** Parse the URL with `urllib.parse.urlparse` (already imported in `main.py`) and verify that `parsed.password` is a non-empty string:

```python
from urllib.parse import urlparse

def _check_redis_auth(redis_url: str, dev_mode: bool) -> None:
    if dev_mode:
        return
    parsed = urlparse(redis_url)
    if not parsed.password:
        raise RuntimeError(
            "REDIS_URL does not contain a password. "
            "Set a Redis URL with credentials: redis://:password@host:port/db. "
            "For local development only, set DEV_MODE=true."
        )
```

This also correctly handles `redis://:@host` (password is empty string, which is falsy) and `redis://@host` (password is `None`). The existing positive test `test_redis_auth_passes_with_password` passes unmodified because that URL has a real password.

---

## Warnings

### WR-01: `test_security_headers` does not assert HSTS — new behavior has no dedicated assertion in the headers test

**File:** `tests/test_security.py:216-234`

**Issue:** `test_security_headers` (SEC-TEST-02) tests `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Content-Security-Policy`. The new HSTS header (`Strict-Transport-Security`) is tested in the separate `test_hsts_header` test, which is correct. However, `test_security_headers` does not assert HSTS at all, so if the header is removed it will not cause `test_security_headers` to fail — only `test_hsts_header` catches it. This creates divergence between "what the security-headers middleware is supposed to inject" and "what the headers test verifies." Future maintainers editing the middleware may not realize HSTS is covered elsewhere.

**Fix:** Add the HSTS assertion to `test_security_headers` as well (belt-and-suspenders), or add an inline comment explicitly calling out that HSTS is asserted by `test_hsts_header`:

```python
# HSTS is asserted separately in test_hsts_header (SEC-INFRA-04).
```

### WR-02: `conftest.py` uses `os.environ.setdefault` — does not override an already-set `DEV_MODE=false` in the shell environment

**File:** `tests/conftest.py:14`

**Issue:** `os.environ.setdefault("DEV_MODE", "true")` only sets the variable if it is absent. If a CI environment or a developer's shell already exports `DEV_MODE=false` (e.g., to simulate production), the `setdefault` silently does nothing, and the Redis auth check will raise `RuntimeError` at app startup during every test run — causing the entire test suite to crash with an opaque error rather than a clear explanation. The bug is especially hard to diagnose because it depends on the external shell state.

**Fix:** Use a direct assignment in `conftest.py` for the test-specific overrides:

```python
# Force dev mode for tests — bypasses Redis auth check (SEC-INFRA-01).
# setdefault is intentionally NOT used here: an inherited DEV_MODE=false from
# the shell would cause app startup to fail for every test.
os.environ["DEV_MODE"] = "true"
```

This is safe because `conftest.py` is test-only code and the variable is only authoritative for the test process lifetime.

### WR-03: `railway.toml` `startCommand` has no `--workers` flag — single-process Uvicorn in production

**File:** `railway.toml:12`

**Issue:** The production `startCommand` starts Uvicorn without `--workers N`, which means Railway runs a single OS process. Under concurrent load this limits throughput significantly and means CPU-bound phases of the Celery task (librosa analysis) block the single event loop. More importantly, this conflicts with the rate limiter's Redis backend rationale (comment on line 37-38 of `main.py`): the comment explicitly justifies the Redis backend by saying "in-memory falha com múltiplos workers", implying multi-process was intended. If a single process is acceptable for v1, the comment in `main.py` should be updated to reflect this. If multiple workers are desired, `--workers 2` (or however many Railway's plan allows) should be added.

**Fix (choose one):**
- If single-process is intentional for v1: Add a comment to `railway.toml` documenting the decision.
- If multi-process is desired:
```toml
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2 --limit-concurrency 100 --timeout-keep-alive 5"
```

Note: with `--workers`, Celery workers are separate processes (via `Procfile` or a separate Railway service) and do not share the Uvicorn process — this is already the correct architecture.

### WR-04: `_real_ip` returns `"unknown"` for all requests when `request.client is None` — collapses all affected clients into a single rate-limit bucket

**File:** `api/main.py:45-49`

**Issue:** When `request.client` is `None` (documented as "rare, proxy misconfigured"), the fallback returns the literal string `"unknown"`. This means every request from a `None`-client shares the same rate-limit counter in Redis. If a correctly configured reverse proxy sends a burst of concurrent requests to the production app before the ASGI connection metadata is set, or if Railway's edge proxy occasionally produces `None` clients, all those requests count against a single shared bucket — and could trigger a 429 for all such clients simultaneously. It also makes it trivially easy for a misconfigured upstream to accidentally exhaust the shared bucket.

**Fix:** Log a warning and return a unique-per-request fallback (e.g., using the request's `scope` hash or a random ID) to avoid bucket collapse. Alternatively, reject these requests with a 400 rather than silently grouping them:

```python
if request.client is None:
    logger.warning("request.client is None — cannot determine client IP for rate limiting")
    # Unique-per-request fallback: prevents bucket collapse while still throttling.
    import secrets
    return f"unknown-{secrets.token_hex(8)}"
```

Using a random ID effectively disables rate limiting for that request, but avoids the worse outcome of all `None`-client requests sharing one bucket. The trade-off should be documented.

---

## Info

### IN-01: HSTS header missing `preload` directive

**File:** `api/main.py:201`

**Issue:** The `Strict-Transport-Security` value is `max-age=31536000; includeSubDomains`. For maximum protection, the `preload` directive should be added so browsers that support HSTS preload lists recognize the site even on first visit (before the header is ever received). This is a hardening enhancement, not a bug.

**Fix:**
```python
response.headers["Strict-Transport-Security"] = (
    "max-age=31536000; includeSubDomains; preload"
)
```

Note: `preload` requires submitting the domain to the HSTS preload list (hstspreload.org). If that submission is not planned, the directive can be omitted without security impact for an already-deployed site.

### IN-02: `Procfile` duplicates `railway.toml` `startCommand` — single source of truth risk

**File:** `Procfile:1`

**Issue:** `Procfile` and `railway.toml` both specify the exact same `uvicorn` command. Railway uses `railway.toml` for deployments; `Procfile` is a Heroku convention that Railway also supports as a fallback. Having both means that if the command is updated in one file but not the other, they diverge silently. There is currently no comment in either file explaining the relationship.

**Fix:** Add a comment to `Procfile` clarifying its role (fallback or legacy), or remove it if `railway.toml` is the definitive deployment config:

```
# Fallback for environments that read Procfile (Heroku, etc.).
# Production target: see railway.toml [deploy] startCommand.
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 100 --timeout-keep-alive 5
```

### IN-03: `test_wav_file_permissions` does not exercise `pipeline.download_audio` directly — only tests `os.chmod` behavior

**File:** `tests/test_security.py:39-61`

**Issue:** The test creates a file, manually calls `os.chmod`, and verifies the result. It does not import or call `pipeline.download_audio`, so it does not actually confirm that the production code path applies `0o600`. If `download_audio` is refactored and the `os.chmod` call is accidentally removed, this test continues to pass. The comment in the test (`# ESTA linha eh o que pipeline.py vai fazer apos download_audio()`) acknowledges this implicitly.

This is a testing-design limitation rather than a production code bug. For the current phase scope it is acceptable, but a future phase should add an integration test that patches `ffmpeg` and verifies the WAV permissions set by the real `download_audio` function.

---

_Reviewed: 2026-05-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
