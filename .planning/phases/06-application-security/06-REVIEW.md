---
phase: 06-application-security
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - CLAUDE.md
  - README.md
  - api/config.py
  - api/main.py
  - pipeline.py
  - start.sh
  - tests/test_security.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 06 introduces application security controls across five layers: WAV file permission hardening (`pipeline.py`), script self-chmod (`start.sh`), two new rate-limit settings (`api/config.py`), rate-limit decorators and a `/health` endpoint (`api/main.py`), and a 12-test security suite (`tests/test_security.py`). The implementation is solid and well-structured. No critical vulnerabilities were found. Four warnings and three info items require attention before merge.

The most significant warnings are: (1) the `/health` endpoint has no rate-limit decorator despite the CLAUDE.md Security Gate mandating `@limiter.limit` on every new endpoint; (2) the `_limit_body_size` middleware silently passes through non-numeric `Content-Length` headers, creating a body-size bypass avenue; (3) `test_startsh_permissions` mutates the live filesystem artifact, making it unsuitable as a pure test and creating a CI reliability risk; and (4) `start.sh` calls `log` before defining it, which will crash on certain `set -e` configurations.

---

## Warnings

### WR-01: `/health` endpoint missing `@limiter.limit` — violates Security Gate

**File:** `api/main.py:336`
**Issue:** `GET /health` was added in this phase without a `@limiter.limit` decorator. CLAUDE.md Security Gate states explicitly: "qualquer rota nova (GET, POST, PUT, DELETE) DEVE ter `@limiter.limit('<N>/minute')`." An unauthenticated probe endpoint with no rate limit allows resource exhaustion: an attacker can hammer Redis with `ping()` calls at unrestricted rate, saturating the connection pool and indirectly DoS-ing the API workers.

**Fix:**
```python
@app.get("/health")
@limiter.limit("60/minute")   # add this line
def health_check(request: Request, response: Response) -> JSONResponse:
    """SEC-API-03: liveness probe — 200 se Redis OK, 503 se offline."""
    try:
        _redis.ping()
        return JSONResponse(status_code=200, content={"status": "ok"})
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
```
Also add `request: Request, response: Response` to the signature per the Security Gate rule for sync routes with slowapi.

---

### WR-02: `_limit_body_size` silently bypasses size check on non-numeric `Content-Length`

**File:** `api/main.py:144-155`
**Issue:** When `Content-Length` is present but non-numeric (e.g., `Content-Length: abc`), the `except ValueError: pass` branch falls through and the request proceeds to `call_next` unchecked. A client that sends a 10 MB body with `Content-Length: abc` will bypass the 4 KB guard entirely because the middleware never reads the actual body stream — it only checks the declared header.

```python
# current code
try:
    if int(cl) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, ...)
except ValueError:
    pass   # <-- malformed header → falls through unchecked
return await call_next(request)
```

**Fix:** Treat a malformed `Content-Length` header as a 400 Bad Request rather than passing it through:
```python
async def _limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request body too large.", "error_type": "request_error"},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid Content-Length header.", "error_type": "request_error"},
            )
    return await call_next(request)
```

---

### WR-03: `start.sh` calls `log` before it is defined — crashes under `set -e`

**File:** `start.sh:23`
**Issue:** `log()` is defined on line 33. On line 23, the script calls `log "Instalando essentia..."` inside the `if` branch that runs when `essentia.standard` is not importable. Because `set -e` is active (line 2), invoking an undefined function (`log`) causes the shell to exit immediately with a non-zero status code, preventing essentia from being installed and leaving the service unable to start.

```bash
# line 22-25 — log() not yet defined
if ! python -c "import essentia.standard" &>/dev/null; then
    log "Instalando essentia (necessário para BPM/key Essentia)..."   # crash: log undefined
    pip install -q essentia==2.1b6.dev1389
fi

# line 33 — log() defined here, too late
log() { echo -e "${C_START}[start]${C_RESET} $1"; }
```

**Fix:** Move the `log` function definition (and its color variable dependencies) to before the essentia check:
```bash
#!/usr/bin/env bash
set -e
chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"
cd "$PROJECT_DIR"
source "$VENV/bin/activate"

# Load .env early — before any log call that might need env vars
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
fi

# Define colors and log BEFORE first use
C_RESET='\033[0m'
C_CELERY='\033[36m'
C_SERVER='\033[32m'
C_START='\033[33m'
log() { echo -e "${C_START}[start]${C_RESET} $1"; }

# Now safe to use log
if ! python -c "import essentia.standard" &>/dev/null; then
    log "Instalando essentia..."
    pip install -q essentia==2.1b6.dev1389
fi
```

---

### WR-04: `test_startsh_permissions` mutates the live `start.sh` file — not a pure test

**File:** `tests/test_security.py:84`
**Issue:** The test calls `os.chmod(startsh, 0o750)` on the real `start.sh` path in the working tree. This is a side-effecting test: it changes the actual file's permissions on disk rather than asserting an observable property. Two concrete problems:

1. If `start.sh` already has `chmod 750` applied at startup (as intended by SEC-FILE-02), this test is redundant and the chmod call is a no-op. But if run in a CI environment where `start.sh` was checked out with `0o755` (git only tracks execute bit, not exact octal), the test will silently `chmod` it to `0o750` and then pass — masking the real question of whether the _script itself_ applies the chmod on execution.
2. The test does not verify the property that SEC-FILE-02 is supposed to guarantee: that running `start.sh` results in the script having mode `0o750`. It verifies only that `os.chmod(0o750)` works on the OS, which is always true.

**Fix:** Either (a) assert the current mode without mutating, or (b) make the test explicit about its side-effect with a docstring note and reset to the original mode after:
```python
def test_startsh_permissions():
    """SEC-FILE-02: verifica que start.sh tem modo 0o750 apos a execucao do auto-chmod.

    NOTA: este teste aplica o chmod para simular a primeira execucao do script.
    Em producao, qualquer execucao de start.sh garante 0o750 via auto-chmod na linha 5.
    """
    project_root = Path(__file__).resolve().parent.parent
    startsh = project_root / "start.sh"
    assert startsh.exists(), f"start.sh nao encontrado em {startsh}"
    original_mode = stat.S_IMODE(os.stat(startsh).st_mode)
    os.chmod(startsh, 0o750)
    try:
        st = os.stat(startsh)
        assert (st.st_mode & 0o777) == 0o750, (
            f"start.sh deve ter modo 0o750, obtido {oct(st.st_mode & 0o777)}"
        )
    finally:
        os.chmod(startsh, original_mode)  # restore — do not leave side effect
```

---

## Info

### IN-01: `settings` module-level singleton created at import time — breaks parallel test isolation

**File:** `api/config.py:37`
**Issue:** `settings = Settings()` is evaluated at module import. In tests that set environment variables after `import api.config`, the singleton captures the pre-test environment. The comment on line 19 explains this was intentional for correct env-var reading, but the singleton is still shared across the entire test session. Tests that need to override individual settings fields (e.g., `job_poll_rate_limit_per_minute`) cannot do so without patching `api.config.settings` at the attribute level.

This is an existing pattern documented in the codebase and not introduced by this phase, but Phase 6 adds two new settings fields (`job_poll_rate_limit_per_minute`, `file_download_rate_limit_per_minute`) that tests for SEC-API-01/02 depend on having correct values. The conftest sets `REDIS_URL` via `os.environ.setdefault` before any import, so this is working correctly for now. No code change required — flagged for awareness.

**Suggestion:** If future tests need to vary `job_poll_rate_limit_per_minute` (e.g., test with limit=1 to avoid 60 iterations), patch via `patch("api.config.settings", Settings(job_poll_rate_limit_per_minute=1, ...))` rather than env-var manipulation.

---

### IN-02: `test_rate_limit_get_jobs` makes 61 actual HTTP requests — slow and fragile

**File:** `tests/test_security.py:109-117`
**Issue:** The test fires 61 sequential requests inside a single test function. With `TestClient` (synchronous HTTPX) this is fast locally, but adds measurable latency in resource-constrained CI. More importantly, if the rate-limit counter leaks from a previous test (the conftest SCAN/flush pattern covers `LIMITS:LIMITER*` keys but might miss variations), the first request could already be `429`, causing the assertion on line 111 to fail with a confusing message. The existing guard is good but the test is fragile by design when the counter starts at a non-zero value.

**Suggestion:** Set `job_poll_rate_limit_per_minute=2` via settings patch and loop only 3 iterations to verify the boundary, rather than relying on the production default of 60.

---

### IN-03: `download_file` in `api/main.py` does not validate `job_id` against the Redis registry before calling `AsyncResult`

**File:** `api/main.py:293-333`
**Issue:** `GET /files/{job_id}` validates the pattern via `JOB_ID_PATTERN` (line 297) but does not check `_redis.exists(f"sg:job:{job_id}")` before querying `AsyncResult`. This is inconsistent with `get_job` (line 244), which does check Redis existence. An attacker who knows or guesses a valid UUID-hex job ID that has already expired from Redis (TTL elapsed) can still get a Celery `AsyncResult` response if the Celery backend TTL has not also expired, potentially learning about past job states.

In practice, `result_expires=settings.wav_ttl` (api/tasks.py line 38) and `_redis.set(..., ex=settings.wav_ttl)` (api/main.py line 232) have the same TTL, so the window is narrow. But the inconsistency is worth closing for defence-in-depth.

**Fix:**
```python
@app.get("/files/{job_id}")
@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")
def download_file(job_id: str, request: Request, response: Response):
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="File not ready or job not found")

    # Add Redis existence check — consistent with get_job, closes TTL race window.
    if not _redis.exists(f"sg:job:{job_id}"):
        raise HTTPException(status_code=404, detail="File not ready or job not found")

    result = AsyncResult(job_id, app=celery_app)
    # ... rest unchanged
```

---

_Reviewed: 2026-05-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
