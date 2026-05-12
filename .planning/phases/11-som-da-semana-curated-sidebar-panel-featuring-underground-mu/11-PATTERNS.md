# Phase 11: Som da Semana - Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/main.py` | controller/service/model | request-response + CRUD + file-I/O fallback | `api/main.py` existing `/jobs`, `/health`, validation, Redis, static routes | exact |
| `api/config.py` | config | request-response setup | `api/config.py` existing `Settings` dataclass env fields | exact |
| `static/index.html` | component | request-response static document | `static/index.html` existing table root, modal, external links | exact |
| `static/app.js` | component/utility | request-response + DOM event-driven | `static/app.js` existing fetch, state, safe DOM updates | exact |
| `static/style.css` | component style | transform/static rendering | `static/style.css` existing Y2K palette, table/button/modal styles | exact |
| `tests/test_security.py` | test | request-response + security | `tests/test_security.py` existing rate-limit, validation, headers tests | exact |
| `tests/test_frontend.py` | test | request-response + static assertions | `tests/test_frontend.py` existing HTML/CSS/JS assertions | exact |
| `requirements.txt` | config | dependency declaration | `requirements.txt` existing pinned backend stack | exact |

## Pattern Assignments

### `api/main.py` (controller/service/model, request-response + CRUD + file-I/O fallback)

**Analog:** `api/main.py`

**Imports pattern** (`api/main.py:2-25`):
```python
from __future__ import annotations

import logging
import os as _os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import redis as redis_lib
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter

from api.config import settings
```

Apply this style for Phase 11 additions: standard-library helpers first (`json`, `hmac`/`secrets` or `itsdangerous`, `datetime`), then third-party imports, then local `settings`.

**Rate-limit/IP pattern** (`api/main.py:43-56`):
```python
def _real_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


limiter = Limiter(
    key_func=_real_ip,
    storage_uri=settings.redis_url,
    headers_enabled=True,
)
```

Every new route must use `@limiter.limit(...)` and include `request: Request, response: Response` in the function signature.

**Validation pattern** (`api/main.py:59-72`):
```python
class JobRequest(BaseModel):
    youtube_url: str

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")
        if parsed.netloc not in YOUTUBE_HOSTS:
            raise ValueError("URL must be a YouTube link")
        return v
```

Copy this for `FeaturedLink`, `FeaturedRelease`, and login payload models. Validate HTTP/HTTPS links with `urlparse`; enforce max 3 links with a Pydantic validator or model validator.

**Error handling pattern** (`api/main.py:255-294`):
```python
def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    seconds = int(exc.limit.limit.get_expiry())
    response = JSONResponse(
        status_code=429,
        content={
            "error": f"Too many requests. Try again in {seconds} seconds.",
            "error_type": "rate_limit_error",
        },
    )
    if hasattr(request.state, "view_rate_limit"):
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
    return response


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request") if errors else "Invalid request"
    msg = msg.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"error": msg, "error_type": "validation_error"},
    )
```

New validation failures should flow through the centralized 422 handler. Return explicit `401`/`403` JSON errors for missing/invalid operator cookies and avoid leaking auth internals.

**Route pattern** (`api/main.py:303-320`, `api/main.py:417-424`):
```python
@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest, response: Response) -> dict:
    ...


@app.get("/health")
@limiter.limit("60/minute")
def health_check(request: Request, response: Response) -> JSONResponse:
    try:
        _redis.ping()
        return JSONResponse(status_code=200, content={"status": "ok"})
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
```

Add `GET /featured`, `POST /yonkou/login`, `GET /yonkou`, and `POST /featured` before `serve_index()` and before `app.mount("/static", ...)`.

**Redis pattern** (`api/main.py:28-29`, `api/main.py:305-313`):
```python
_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)

_redis.set(f"sg:job:{task.id}", "1", ex=settings.wav_ttl)
```

Use the existing module-level Redis client. Store `featured:current` as one JSON string; catch `redis_lib.exceptions.ConnectionError` and `TimeoutError` for fallback JSON file reads/writes.

**Static mount placement** (`api/main.py:433-445`):
```python
STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
```

Route order matters: all API and `/yonkou` routes must be declared before the static mount.

---

### `api/config.py` (config, request-response setup)

**Analog:** `api/config.py`

**Settings pattern** (`api/config.py:21-55`):
```python
def _safe_int(env_key: str, default: int) -> int:
    raw = os.environ.get(env_key, str(default))
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Invalid value for {env_key}={raw!r} — expected an integer. "
            f"Check your .env file."
        )


@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    rate_limit_per_minute: int = field(default_factory=lambda: _safe_int("RATE_LIMIT_PER_MINUTE", 3))
    dev_mode: bool = field(default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true")


settings = Settings()
```

Add `admin_password`, `admin_session_secret`, and `featured_fallback_path` as `field(default_factory=...)` fields. Keep env reads lazy so tests can set env vars before importing `api.*`.

---

### `static/index.html` (component, request-response static document)

**Analog:** `static/index.html`

**Table layout pattern** (`static/index.html:10-33`):
```html
<div id="wrapper">
  <table id="app" width="640" align="center" cellpadding="0" cellspacing="0">
    <tr>
      <td id="header">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:none">
```

Keep the root Y2K table idiom. For the sidebar, either add a JS insertion target adjacent to `#app` or let `app.js` inject a right-side table column only after `/featured` returns content.

**External link pattern** (`static/index.html:238-239`):
```html
<a id="gh-corner" href="https://github.com/byglow9/SoundGrabber" target="_blank" rel="noopener" title="Ver no GitHub">
```

Featured links must match `target="_blank" rel="noopener"`.

**No public admin affordance:** There is no existing link to `/yonkou`; preserve that. Do not add a button, menu item, or copy exposing the operator route.

---

### `static/app.js` (component/utility, request-response + DOM event-driven)

**Analog:** `static/app.js`

**DOM and state pattern** (`static/app.js:7-32`):
```javascript
let state = 'IDLE';
let jobId = null;

const $ = id => document.getElementById(id);

function setState(newState, payload = {}) {
  state = newState;
  switch (newState) {
    case 'IDLE': showIdle(); break;
    ...
  }
}
```

Add featured-sidebar helpers as plain functions in the same file. Do not introduce modules, bundlers, frameworks, or global dependencies.

**Fetch pattern** (`static/app.js:47-101`):
```javascript
const response = await fetch('/jobs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ youtube_url: url })
});

if (response.status === 422) {
  const data = await response.json();
  setState('ERROR_VALIDATION', { message });
  return;
}
```

Use this style for `fetch('/featured')` on `DOMContentLoaded`: handle `204` and `{}` as no-op, parse JSON only when content exists, and keep visitor fetch failures silent.

**Safe rendering pattern** (`static/app.js:210-231`, `static/app.js:235-245`):
```javascript
$('bpm-value').textContent = data.bpm ?? '';
$('key-value').textContent = data.key ?? '';
$('size-value').textContent = formatSizeMB(estimateSizeMB(data.duration_sec ?? 0));

const downloadHref = (data.download_url && data.download_url.startsWith('/files/'))
  ? data.download_url
  : '/files/' + jobId;
$('download-link').href = downloadHref;

$('validation-error').textContent = msg;
```

Render all featured text with `textContent`. For featured anchors, set `href`, `target`, and `rel` attributes directly after backend validation; never use `innerHTML`.

**Init/event pattern** (`static/app.js:339-391`):
```javascript
function init() {
  $('submit-btn').addEventListener('click', () => {
    const url = $('url-input').value.trim();
    if (!url) return;
    setState('SUBMITTING');
    submitJob(url);
  });
}

document.addEventListener('DOMContentLoaded', init);
```

Call `loadFeatured()` from `init()` without blocking the existing downloader event wiring.

---

### `static/style.css` (component style, transform/static rendering)

**Analog:** `static/style.css`

**Global Y2K pattern** (`static/style.css:15-44`, `static/style.css:100-108`):
```css
body {
  background-color: #000000;
  color: #ff8800;
  font-family: 'Sligoil', 'Courier New', monospace;
  font-size: 13px;
  margin: 0;
  padding: 235px 0 32px 0;
}

table {
  border-collapse: collapse;
}

td {
  color: #ff8800;
  padding: 8px;
  border: 1px solid #ff8800;
}
```

Use raw selectors and raw hex colors. Do not add flexbox, grid, CSS variables, border radius, shadows, transitions, animations, or transforms.

**Button pattern** (`static/style.css:171-211`, `static/style.css:219-233`):
```css
#submit-btn {
  display: inline-block;
  margin-top: 6px;
  background-color: #ff8800;
  color: #000000;
  border: 1px solid #ff8800;
  font-family: 'Dela Gothic One', sans-serif;
  font-size: 16px;
  padding: 8px 16px;
  cursor: pointer;
}

#retry-btn {
  background-color: #000000;
  color: #ff8800;
  border: 1px solid #ff8800;
  font-family: 'Sligoil', 'Courier New', monospace;
  font-size: 13px;
  padding: 8px 16px;
  cursor: pointer;
}
```

Featured link buttons should reuse the black/orange secondary button pattern unless the UI spec explicitly calls for primary inversion.

**Label and modal panel pattern** (`static/style.css:250-255`, `static/style.css:327-376`):
```css
.label {
  font-size: 13px;
  color: #ff8800;
}

#info-modal {
  position: fixed;
  width: 240px;
  border: 2px solid #ff8800;
  background-color: #000000;
  z-index: 100;
}
```

Use `.label` semantics for `:: SOM DA SEMANA ::` and admin form labels. Sidebar width should be about `220px`, with left divider `1px solid #ff8800`.

---

### `tests/test_security.py` (test, request-response + security)

**Analog:** `tests/test_security.py`

**Rate-limit pattern** (`tests/test_security.py:101-125`, `tests/test_security.py:130-153`):
```python
def test_rate_limit_get_jobs(api_client):
    from api.main import _redis
    with patch.object(_redis, "exists", return_value=1), \
         patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        for i in range(60):
            r = api_client.get("/jobs/test-job-id")
            assert r.status_code == 200
        r = api_client.get("/jobs/test-job-id")
        assert r.status_code == 429
```

Add Phase 11 tests for `GET /featured` 60/min, `POST /featured` 10/min, and `POST /yonkou/login` 5/min. Patch storage/auth dependencies so endpoint behavior is reached before unrelated failures.

**Validation and security response pattern** (`tests/test_security.py:199-236`, `tests/test_security.py:258-272`):
```python
def test_body_size_limit(api_client):
    r = api_client.post("/jobs", content=large, headers={"Content-Length": "5000"})
    assert r.status_code == 413
    body = r.json()
    assert body.get("error_type") == "request_error"


def test_queue_depth_limit(api_client):
    from api.main import _redis
    with patch.object(_redis, "llen", return_value=51):
        r = api_client.post("/jobs", json={"youtube_url": "https://www.youtube.com/watch?v=abc123"})
    assert r.status_code == 503
```

Use direct `api_client` requests and assert exact HTTP statuses. Add tests for missing operator session, invalid link schemes, too many links, valid login cookie flags, and Redis fallback behavior.

**Fixture pattern source** (`tests/conftest.py:13-14`, `tests/conftest.py:68-108`):
```python
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("DEV_MODE", "true")


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    yield client
```

If tests need `ADMIN_PASSWORD` or `ADMIN_SESSION_SECRET`, set defaults before importing `api.main`, mirroring the existing env setup.

---

### `tests/test_frontend.py` (test, request-response + static assertions)

**Analog:** `tests/test_frontend.py`

**Served asset pattern** (`tests/test_frontend.py:7-31`, `tests/test_frontend.py:119-136`):
```python
def test_index_html_served(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/html")
    assert 'id="url-input"' in response.text


def test_style_css_served(api_client):
    r = api_client.get("/static/style.css")
    assert r.status_code == 200
    assert "#000000" in r.text
    assert "#ff8800" in r.text
    assert "var(" not in r.text
```

Add static assertions for `#featured-sidebar`, `#featured-card`, `#featured-title`, `.featured-link`, and absence of public `/yonkou` links in `GET /`.

**No-modern-CSS pattern** (`tests/test_frontend.py:140-183`, `tests/test_frontend.py:188-204`):
```python
forbidden = [
    "flex",
    "grid",
    "var(--",
    "border-radius",
    "box-shadow",
    "transition:",
    "animation:",
    "transform:",
]
found = [prop for prop in forbidden if prop in css]
assert not found
```

Preserve these constraints when adding sidebar CSS tests. Add checks that featured links use `rel="noopener"`/`target="_blank"` via JS source or fixture HTML if the DOM is injected.

---

### `requirements.txt` (config, dependency declaration)

**Analog:** `requirements.txt`

**Pinned stack pattern** (`requirements.txt:6-16`):
```text
pytest==9.0.3
fastapi==0.136.1
slowapi==0.1.9
uvicorn==0.46.0
celery[redis]==5.6.3
redis==6.4.0
httpx>=0.27
```

Only add `itsdangerous==2.2.0` if the implementation chooses the recommended serializer. If using stdlib HMAC, do not modify this file.

## Shared Patterns

### Security Gate

**Source:** `api/main.py:303-320`, `api/main.py:374-424`
**Apply to:** `GET /featured`, `POST /featured`, `POST /yonkou/login`, and any `/yonkou` endpoint that handles requests.

```python
@app.get("/health")
@limiter.limit("60/minute")
def health_check(request: Request, response: Response) -> JSONResponse:
    ...
```

Use read limit `60/minute`, write/operator limit `10/minute`, and login limit `5/minute` per phase decisions.

### Request Validation

**Source:** `api/main.py:59-72`, `api/main.py:282-294`
**Apply to:** Login body and featured payload body.

```python
class JobRequest(BaseModel):
    youtube_url: str

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        ...
```

Use Pydantic models; do not parse POST bodies with raw `request.json()`.

### Redis With Graceful Fallback

**Source:** `api/main.py:28-29`, `api/main.py:417-424`
**Apply to:** `featured:current` storage helpers.

```python
_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)

try:
    _redis.ping()
except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
    return JSONResponse(status_code=503, content={"status": "unavailable"})
```

Catch Redis connection/timeout errors and use a local JSON fallback path from settings.

### Safe DOM Rendering

**Source:** `static/app.js:210-245`
**Apply to:** Featured card rendering and admin status/error copy.

```javascript
$('bpm-value').textContent = data.bpm ?? '';
$('validation-error').textContent = msg;
$('download-link').href = downloadHref;
```

Use `textContent`; set anchor attributes directly; never use `innerHTML` for operator-provided values.

### Y2K Static Styling

**Source:** `static/style.css:36-44`, `static/style.css:100-108`, `static/style.css:171-233`
**Apply to:** Public sidebar and `/yonkou` operator UI.

```css
body {
  background-color: #000000;
  color: #ff8800;
  font-family: 'Sligoil', 'Courier New', monospace;
  font-size: 13px;
}
```

Keep table layout and raw hex palette. Do not add flexbox, grid, CSS variables, rounded corners, shadows, transitions, animations, or transforms.

### Test Fixture Isolation

**Source:** `tests/conftest.py:13-14`, `tests/conftest.py:68-108`
**Apply to:** All new security tests.

```python
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("DEV_MODE", "true")
```

Set Phase 11 auth env defaults before importing `api.main`; patch `_redis` methods or storage helpers to avoid depending on live external services beyond the existing local test Redis convention.

## No Analog Found

All proposed Phase 11 files have close in-repo analogs. No file needs planner fallback to research-only patterns.

## Metadata

**Analog search scope:** `api/`, `static/`, `tests/`, `requirements.txt`, phase artifacts under `.planning/phases/11-som-da-semana-curated-sidebar-panel-featuring-underground-mu/`
**Files scanned:** 16
**Pattern extraction date:** 2026-05-12

