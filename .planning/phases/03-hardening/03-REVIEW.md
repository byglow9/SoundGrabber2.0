---
phase: 03-hardening
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - api/config.py
  - api/main.py
  - requirements.txt
  - tests/conftest.py
  - tests/test_api.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The five files reviewed cover the Phase 3 hardening additions: Redis-backed rate limiting via slowapi, 422 normalization, sweeper extension (.part/.ytdl cleanup), and the accompanying test suite. The implementation is well-structured overall — good separation of concerns, clear error contracts, and solid path-traversal defense in `GET /files/{id}`. However, one critical security gap exists (X-Forwarded-For header spoofing), and four warnings cover reliability and correctness risks in the rate limiter wiring, config evaluation, Redis key TTL logic, and test isolation. Three informational items flag minor maintainability concerns.

---

## Critical Issues

### CR-01: Rate limiter trusts X-Forwarded-For without proxy verification — IP spoofing allows unlimited requests

**File:** `api/main.py:36-40`

**Issue:** `Limiter(key_func=get_ipaddr, ...)` uses slowapi's `get_ipaddr`, which reads `X-Forwarded-For` unconditionally. Any client can send `X-Forwarded-For: 1.2.3.4` and the limiter will use `1.2.3.4` as the key, making it trivial to bypass the 3/minute limit by rotating this header. This is the canonical slowapi rate-limit bypass when the app is deployed behind a single-hop reverse proxy (nginx) that appends but does not strip the client-supplied header.

**Fix:** Either (a) configure a trusted proxy count so slowapi takes only the Nth-from-right address, or (b) use `request.client.host` directly when running behind a known single reverse proxy (where the real IP is always in `client.host` after nginx sets it). For a single nginx proxy the simplest safe approach is:

```python
# Replace get_ipaddr with a function that reads client.host,
# which is set by the trusted nginx proxy — not spoofable by the client.
def _real_ip(request: Request) -> str:
    return request.client.host  # set by the WSGI/ASGI layer from the TCP connection

limiter = Limiter(
    key_func=_real_ip,
    storage_uri=settings.redis_url,
    headers_enabled=True,
)
```

If there is an intermediate load balancer that sets `X-Forwarded-For` reliably and strips the client value, configure `forwarded_for_depth=1` (slowapi ≥0.1.9 supports it via limits library options) or use Uvicorn's `--proxy-headers --forwarded-allow-ips` with `ProxyHeadersMiddleware` and then read `request.client.host`.

---

## Warnings

### WR-01: `app.add_exception_handler` used instead of `@app.exception_handler` for `RateLimitExceeded` — handler may not fire on older FastAPI middleware ordering

**File:** `api/main.py:108, 133`

**Issue:** `app.state.limiter = limiter` is set after `app` is created, and `app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)` is called imperatively. slowapi's standard integration requires `app.add_exception_handler` AND registering the `SlowAPIMiddleware` or calling `app.state.limiter`. The current code omits `app.add_middleware(SlowAPIMiddleware)` — it relies on the decorator-based `@limiter.limit(...)` which internally registers the rate-check. Without the middleware, the `request.state.view_rate_limit` attribute written by slowapi may be absent when `_inject_headers` is called, raising `AttributeError` on a 429 response.

The canonical slowapi wiring is:

```python
from slowapi import Limiter, _rate_limit_handler
from slowapi.middleware import SlowAPIMiddleware

app = FastAPI(...)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
```

**Fix:** Add `app.add_middleware(SlowAPIMiddleware)` after the exception handler registration. Also confirm `request.state.view_rate_limit` is available before calling `_inject_headers` to avoid `AttributeError`:

```python
from slowapi.middleware import SlowAPIMiddleware
# ...after app creation and exception handler registration:
app.add_middleware(SlowAPIMiddleware)
```

And guard the inject call:

```python
if hasattr(request.state, "view_rate_limit"):
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
```

### WR-02: `Settings` dataclass fields evaluated at module import time — `os.environ.get` calls run once, not per-access

**File:** `api/config.py:10-14`

**Issue:** Default values for all `Settings` fields are computed via `os.environ.get(...)` at **class definition time** (Python evaluates default expressions when the class body is executed). This means environment variables set after `api.config` is first imported are silently ignored. In tests, `os.environ.setdefault("REDIS_URL", ...)` in `conftest.py` (line 13) must run before any `api.*` import — this is a fragile ordering requirement that is easy to break (e.g., a test file importing `api.main` at module level would bypass the env setup).

More concretely: `Settings()` at line 17 also freezes the values at import time. Any test that sets `os.environ["RATE_LIMIT_PER_MINUTE"] = "10"` after the module loads will have no effect.

**Fix:** Use `field(default_factory=...)` with `os.environ.get` inside the factory, or switch to a `@classmethod` constructor, or use `pydantic.BaseSettings` which re-reads at instantiation. Minimum safe change:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    cookies_path: str = field(default_factory=lambda: os.environ.get("YTDLP_COOKIES_FILE", ""))
    po_token: str = field(default_factory=lambda: os.environ.get("YTDLP_PO_TOKEN", ""))
    wav_ttl: int = field(default_factory=lambda: int(os.environ.get("WAV_TTL_SECONDS", "900")))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MINUTE", "3")))
```

### WR-03: `_redis.expire(JOB_REGISTRY_KEY, settings.wav_ttl)` resets the TTL of the entire job registry set on every submit — jobs submitted early are evicted before their TTL expires

**File:** `api/main.py:158-159`

**Issue:** `JOB_REGISTRY_KEY` (`sg:jobs`) is a single Redis Set shared by all jobs. Every call to `POST /jobs` calls `_redis.expire(JOB_REGISTRY_KEY, settings.wav_ttl)` (900 seconds). This resets the TTL of the **entire set** to 900 seconds from now. A job submitted 14 minutes ago (840 seconds) is in its last 60 seconds of legitimate life — but a new job submission resets the set TTL to 900 seconds, which is harmless for the old job. However, the reverse is also true: if the system is idle for >900 seconds (15 minutes), the set expires and is deleted — all job-ID membership knowledge is lost. A client polling an old job will then get 404 immediately even if the Celery result is still alive in Redis (Celery `result_expires=wav_ttl` is a separate key).

More importantly, per-job membership in `sg:jobs` is the only guard against the PENDING-ambiguity described in the code comment (Pitfall 1 / D-02). If the set key expires, all in-progress jobs whose Celery result still says PENDING will return 404 even though they are still running.

**Fix:** Use per-job keys instead of one shared set, or extend the set TTL to at least `2 * wav_ttl` to give headroom. The simplest correct fix:

```python
# Use a per-job key with individual TTL instead of a shared set
_redis.set(f"sg:job:{task.id}", "1", ex=settings.wav_ttl)

# In get_job():
if not _redis.exists(f"sg:job:{job_id}"):
    raise HTTPException(status_code=404, detail="Job not found")
```

### WR-04: `conftest.py` flushes all `LIMITS:LIMITER*` keys without filtering by test-specific prefix — parallel test runs will interfere with each other

**File:** `tests/conftest.py:85-87`

**Issue:** The fixture uses `_r.keys("LIMITS:LIMITER*")` to enumerate and delete rate-limit keys. `KEYS` is an O(N) Redis command that blocks the server while scanning all keys — in a real Redis instance this can cause latency spikes. More critically, if two pytest processes run concurrently (e.g., `-n auto` with pytest-xdist), the flush in one process will delete rate-limit counters being used by the other, producing false test results.

Additionally, `_r.keys(...)` returns a list of byte strings when `decode_responses` is not set on this client (line 85 constructs the client without `decode_responses=True`), so `_r.delete(key)` may fail silently or pass raw bytes as the key name.

**Fix:**

```python
# Use SCAN instead of KEYS, and add decode_responses=True
_r = redis_lib.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6380/0"),
    decode_responses=True,
)
cursor = 0
while True:
    cursor, keys = _r.scan(cursor, match="LIMITS:LIMITER*", count=100)
    if keys:
        _r.delete(*keys)
    if cursor == 0:
        break
```

---

## Info

### IN-01: `download_file` endpoint lacks Redis membership check — any valid Celery SUCCESS result is servable regardless of registration

**File:** `api/main.py:217-248`

**Issue:** `GET /files/{job_id}` does not call `_redis.sismember(JOB_REGISTRY_KEY, job_id)` before serving the file, unlike `GET /jobs/{job_id}` which does (line 169). A forged or externally-crafted Celery task ID whose result happens to be SUCCESS and contains a `wav_path` would be served. Given the path-traversal defense is solid (`/tmp` + `sg_` prefix), the practical impact is very low — but the inconsistency is a maintenance hazard: if the path defense is relaxed later, the missing registry check becomes a real gap.

**Fix:** Add the same registry check used in `get_job`:

```python
@app.get("/files/{job_id}")
def download_file(job_id: str):
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="File not ready or job not found")
    if not _redis.sismember(JOB_REGISTRY_KEY, job_id):
        raise HTTPException(status_code=404, detail="File not ready or job not found")
    # ... rest unchanged
```

### IN-02: `test_file_streaming` writes to `/tmp/sg_testfileXX.wav` — hardcoded path with no randomness may collide in parallel runs

**File:** `tests/test_api.py:121`

**Issue:** `target = Path("/tmp") / "sg_testfileXX.wav"` is a fixed filename. If two test runs execute this test simultaneously (or if the file is left over from a crashed test), the second run will silently overwrite the file and both may read unexpected content. The `tmp_path` fixture (available in the function signature) already provides a unique directory.

**Fix:** Use `tmp_path` for test isolation — but since the endpoint resolves the path against `/tmp`, use `tmp_path` only for intermediate work and copy to a unique `/tmp/sg_<uuid>.wav`:

```python
import uuid
target = Path("/tmp") / f"sg_test_{uuid.uuid4().hex[:8]}.wav"
```

### IN-03: `requirements.txt` pins `pytest==9.0.3` but `httpx>=0.27` is a range — httpx version drift can silently change `TestClient` behavior

**File:** `requirements.txt:6,13`

**Issue:** All production and most test dependencies are pinned to exact versions, but `httpx` is pinned only as `>=0.27`. `httpx` drives `fastapi.testclient.TestClient` in the test suite. A new httpx release with breaking changes (e.g., header handling, redirect behavior) would affect tests without any visible change in the requirements file. Given that `fastapi==0.136.1` ships its own `httpx` constraint, this may not matter in practice — but it is inconsistent with the pinning discipline applied to every other package.

**Fix:** Pin to a specific version:

```
httpx==0.28.1
```

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
