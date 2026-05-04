# Phase 2: API Layer - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 5 (api/config.py, api/tasks.py, api/main.py, api/__init__.py, tests/test_api.py)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/config.py` | config | request-response | `pipeline.py` (env-var reads at module level, lines 30-33) | role-match |
| `api/tasks.py` | service | event-driven (task queue) | `pipeline.py` (pipeline orchestrator, lines 396-438) | role-match |
| `api/main.py` | controller | request-response | `pipeline.py` `__main__` block (lines 442-499) | partial-match |
| `api/__init__.py` | config | — | `tests/__init__.py` (empty package marker) | exact |
| `tests/test_api.py` | test | request-response | `tests/test_pipeline.py` (pytest stubs, lines 1-50) | exact |

---

## Pattern Assignments

### `api/config.py` (config, request-response)

**Analog:** `pipeline.py` (env-var module-level reads) — file already scaffolded as a stub.

**Current stub** (`api/config.py` lines 1-16) — this is the COMPLETE target implementation; the scaffold is already correct and must NOT be changed:

```python
"""Settings via environment variables (12-factor). D-04 — single requirements.txt; D-07 — no Docker."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    cookies_path: str = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token: str = os.environ.get("YTDLP_PO_TOKEN", "")
    wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))


settings = Settings()
```

**Key conventions from `pipeline.py` lines 30-33 (env-var pattern):**
```python
cookies_path = os.environ.get("YTDLP_COOKIES_FILE", "")
po_token = os.environ.get("YTDLP_PO_TOKEN", "")
```
- All config from `os.environ.get()` with safe defaults — never crash on missing var.
- `YTDLP_COOKIES_FILE` and `YTDLP_PO_TOKEN` names already established; `api/config.py` reuses them exactly.
- `frozen=True` dataclass: immutable at runtime (no accidental mutation).

---

### `api/tasks.py` (service, event-driven)

**Analog:** `pipeline.py` orchestrator (`analyze_audio`, `__main__`, lines 396-499) — file already has Celery app stub; body of `process_job` needs filling in.

**Celery app scaffold** (`api/tasks.py` lines 1-27) — keep exactly, already correct:

```python
from celery import Celery
from api.config import settings

celery_app = Celery("soundgrabber")
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=settings.wav_ttl,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 1800},
    task_acks_late=True,
)
```

**Import pattern** (copy from `pipeline.py` lines 1-10, adapt for Celery context):
```python
from __future__ import annotations

from celery import Celery
from api.config import settings
from pipeline import check_duration, download_audio, analyze_audio
```

**Task body pattern** — copy structure from `pipeline.py` `__main__` block (lines 475-499), mapped to `self.update_state()`:

```python
@celery_app.task(bind=True, name="soundgrabber.process_job")
def process_job(self, url: str) -> dict:
    try:
        self.update_state(state="DOWNLOADING", meta={"stage": "checking_duration"})
        check_duration(url, settings.cookies_path)          # raises ValueError if too long

        self.update_state(state="DOWNLOADING", meta={"stage": "downloading"})
        wav_path = download_audio(url, settings.cookies_path, settings.po_token)

        self.update_state(state="CONVERTING", meta={"stage": "converting"})
        # download_audio already produces WAV — convert_to_wav is pass-through

        self.update_state(state="ANALYZING", meta={"stage": "analyzing"})
        result = analyze_audio(wav_path)

        return {
            **result,                                         # bpm, key, camelot, etc.
            "download_url": f"/files/{self.request.id}",
        }
    except ValueError as e:
        # pipeline.py __main__ line 487-489: ValueError = validation_error
        self.update_state(state="FAILURE", meta={
            "error": "Video is too long (max 15 minutes)." if "too long" in str(e).lower()
                     else "Could not validate audio file.",
            "error_type": "validation_error",
        })
        raise
    except RuntimeError as e:
        # pipeline.py __main__ line 491-493: RuntimeError = download_error
        self.update_state(state="FAILURE", meta={
            "error": "Download failed. The video may be unavailable or blocked.",
            "error_type": "download_error",
        })
        raise
    except Exception:
        # pipeline.py __main__ line 495-498: catch-all = internal_error
        self.update_state(state="FAILURE", meta={
            "error": "An internal error occurred. Please try again.",
            "error_type": "internal_error",
        })
        raise
```

**Error type mapping** — mirrors exactly the `except` chain in `pipeline.py` `__main__` (lines 486-498):
- `ValueError` → `"validation_error"` (duration check, WAV corruption)
- `RuntimeError` → `"download_error"` (yt-dlp failure, network)
- `FileNotFoundError` → map to `"download_error"` (WAV not produced)
- `Exception` → `"internal_error"`

---

### `api/main.py` (controller, request-response)

**Analog:** `pipeline.py` `__main__` block (lines 442-499) for error handling structure; `tests/test_api.py` for the expected request/response contract; file already scaffolded.

**Imports pattern** (expand the current stub imports):
```python
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from api.config import settings
from api.tasks import celery_app, process_job
```

**URL validation pattern** — Pydantic `field_validator`, mirrors the input-guard pattern in `pipeline.py` `check_duration` (lines 38-74) but at HTTP boundary:
```python
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}

class JobRequest(BaseModel):
    youtube_url: str

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")
        if parsed.netloc not in YOUTUBE_HOSTS:
            raise ValueError(f"URL must be a YouTube link (got: {parsed.netloc!r})")
        return v
```
Note: Tests in `tests/test_api.py` lines 44-55 enumerate the exact URLs that must return 422 (validates SSRF via `localhost:6379` is blocked by netloc allowlist).

**POST /jobs pattern** — copy the `.delay()` fire-and-forget shape; test expectation at `test_api.py` line 33:
```python
@app.post("/jobs", status_code=202)
def submit_job(request: JobRequest) -> dict:
    task = process_job.delay(request.youtube_url)
    # Also SADD task.id to Redis Set (Pitfall 1 mitigation — see RESEARCH.md)
    return {"job_id": task.id}
```

**GET /jobs/{id} pattern** — state mapping mirrors `pipeline.py` `__main__` exit codes (0 = done, 1 = error); test contract at `test_api.py` lines 93-106:
```python
STATE_MAP = {
    "PENDING":     "queued",
    "STARTED":     "queued",
    "DOWNLOADING": "downloading",
    "CONVERTING":  "converting",
    "ANALYZING":   "analyzing",
    "SUCCESS":     "done",
    "FAILURE":     "failed",
}

@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    result = AsyncResult(job_id, app=celery_app)
    if result.state == "PENDING":
        # Pitfall 1: PENDING is ambiguous — unknown ID also returns PENDING
        # Resolve via Redis Set membership check (SADD in POST /jobs)
        raise HTTPException(status_code=404, detail="Job not found or expired")
    if result.state == "FAILURE":
        info = result.info if isinstance(result.info, dict) else {}
        return {
            "status": "failed",
            "error": info.get("error", "An error occurred."),
            "error_type": info.get("error_type", "internal_error"),
        }
    if result.state == "SUCCESS":
        data = result.result
        return {
            "status": "done",
            "bpm": data["bpm"],
            "bpm_half": data["bpm_half"],
            "bpm_double": data["bpm_double"],
            "key": data["key"],
            "camelot": data["camelot"],
            "duration_sec": data["duration_sec"],
            "download_url": data["download_url"],
            # wav_path intentionally excluded (Pitfall 4 — never expose filesystem path)
        }
    meta = result.info if isinstance(result.info, dict) else {}
    return {"status": STATE_MAP.get(result.state, "queued"), "stage": meta.get("stage")}
```

**GET /files/{id} pattern** — `FileResponse` (not streaming generator); test contract at `test_api.py` lines 113-133:
```python
@app.get("/files/{job_id}")
def download_file(job_id: str):
    result = AsyncResult(job_id, app=celery_app)
    if result.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="File not ready or job not found")
    wav_path = Path(result.result["wav_path"])
    if not wav_path.exists():
        raise HTTPException(status_code=410, detail="File expired")
    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=f"soundgrabber_{job_id[:8]}.wav",
    )
```

**Sweeper pattern** — background thread in lifespan; test at `test_api.py` lines 148-167 expects a standalone `sweep_expired_wavs(directory, ttl_seconds)` callable:
```python
WAV_TMP_DIR = Path("/tmp")

def sweep_expired_wavs(directory: Path = WAV_TMP_DIR, ttl_seconds: int = settings.wav_ttl) -> None:
    """Single sweep pass — also called by test_sweeper_deletes_expired_wavs."""
    now = time.time()
    for wav in directory.glob("sg_*.wav"):
        try:
            if now - wav.stat().st_mtime > ttl_seconds:
                wav.unlink()
        except OSError:
            pass

def _run_sweeper() -> None:
    while True:
        sweep_expired_wavs()
        time.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_run_sweeper, daemon=True, name="wav-sweeper")
    t.start()
    yield
```
Note: The test calls `sweep_expired_wavs(tmp_path, ttl_seconds=900)` with a custom directory — the standalone function signature is required, not just the daemon thread.

---

### `api/__init__.py` (config, —)

**Analog:** `tests/__init__.py` (empty package marker).

**Current stub** (`api/__init__.py` line 1) — already complete:
```python
"""SoundGrabber API package — Phase 2."""
```
No changes needed. One-liner docstring marking the package.

---

### `tests/test_api.py` (test, request-response)

**Analog:** `tests/test_pipeline.py` — same project test conventions (stubs, markers, fixtures).

**Test file already scaffolded** (`tests/test_api.py` lines 1-203). All test bodies are written. The implementation fills in the source files until these tests pass.

**Test conventions to copy from `tests/test_pipeline.py`:**

Module docstring + marker legend (lines 1-13):
```python
"""SoundGrabber API tests — Phase 2.

Stubs created in Plan 01 (Wave 1). Implementations turn these green:
  ...

Markers:
  - (no marker): unit tests, run on every commit (~5s)
  - integration: requires ...
  - e2e: requires ...
"""
```

`patch.object` + `pytest.importorskip` + `pytest.raises` pattern (lines 161-167 of `test_pipeline.py`):
```python
with patch.object(pipeline, "detect_bpm", return_value=140.0), \
     patch.object(pipeline, "detect_key", return_value="C major"), \
     patch.object(pipeline, "validate_wav", return_value=180.0):
    result = pipeline.analyze_audio(Path("/tmp/fake.wav"))
```

`api_client` fixture in `tests/conftest.py` (lines 61-72) — use `task_always_eager=True` to avoid Redis for unit tests:
```python
@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from api.tasks import celery_app
    from api.main import app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    client = TestClient(app)
    yield client
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False
```

---

## Shared Patterns

### from\_future + type annotations
**Source:** Every existing `.py` file (line 1 of each)
**Apply to:** All `api/` files and `tests/test_api.py`
```python
from __future__ import annotations
```

### Exception hierarchy → error type mapping
**Source:** `pipeline.py` `__main__` lines 486-498
**Apply to:** `api/tasks.py` task body, `api/main.py` GET /jobs/{id}

```python
# pipeline.py lines 486-498 — the canonical mapping this project uses:
except ValueError as e:
    _emit_error("validation_error", str(e))
except RuntimeError as e:
    _emit_error("download_error", str(e))
except FileNotFoundError as e:
    _emit_error("download_error", str(e))
except Exception as e:
    _emit_error("internal_error", f"{type(e).__name__}: {e}")
```
In `api/tasks.py`: map same exception types to `error_type` strings in `update_state()` meta.
In `api/main.py`: read `result.info` dict for `error` and `error_type` keys when `state == "FAILURE"`.

### WAV path convention
**Source:** `pipeline.py` lines 32-34
**Apply to:** `api/tasks.py` (return value), `api/main.py` (sweeper glob, FileResponse)
```python
TMP_PREFIX = "sg_"   # /tmp/sg_{12hex}.wav
WAV_TMP_DIR = Path("/tmp")
```
Sweeper must use `glob("sg_*.wav")` — same prefix; `FileResponse` reads `result.result["wav_path"]` (string from `analyze_audio` return dict).

### Celery eager mode for unit tests
**Source:** `tests/conftest.py` lines 61-72
**Apply to:** All unit tests in `tests/test_api.py` that use `api_client` fixture
```python
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
```
Allows tests to run without a Redis broker; task executes synchronously in the same process.

### `from __future__ import annotations` + dataclass frozen settings
**Source:** `api/config.py` lines 1-16 (the scaffold)
**Apply to:** `api/config.py` (already done); serves as reference for any future settings additions.

---

## No Analog Found

None. All five files have clear analogs in the existing codebase. The `api/` scaffold files themselves are the strongest analogs — they are partially implemented stubs that define the exact structure the implementations must follow.

---

## Metadata

**Analog search scope:** `/home/glow/Documentos/SoundGrabber2.0/` (root Python files + `api/` + `tests/`)
**Files scanned:** 7 (pipeline.py, api/config.py, api/tasks.py, api/main.py, api/__init__.py, tests/test_pipeline.py, tests/test_api.py, tests/conftest.py)
**Pattern extraction date:** 2026-05-04

**Key observation:** Phase 2 is a greenfield addition on top of Phase 1. The `api/` scaffold (created in Phase 2 Plan 01) is already the most relevant analog — it defines module structure, Celery config, FastAPI route signatures, and test expectations. The primary job of Plans 02/03 is to replace the `raise HTTPException(status_code=501)` stubs with real implementations that copy patterns from `pipeline.py` (error handling, exception hierarchy, env-var config) and from `tests/test_api.py` (the already-written test contracts that drive the implementation).
