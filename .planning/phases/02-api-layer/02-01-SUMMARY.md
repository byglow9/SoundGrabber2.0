---
phase: 02-api-layer
plan: 01
subsystem: api
tags: [api, scaffolding, celery, fastapi, redis, wave-1]
dependency_graph:
  requires: [pipeline.py (Phase 1 — check_duration, download_audio, analyze_audio)]
  provides: [api/ package (config, tasks, main), test stubs for all Phase 2 requirements]
  affects: [02-02-PLAN.md (Wave 2 — implements routes), 02-03-PLAN.md (Wave 3 — fills stubs)]
tech_stack:
  added: [fastapi==0.136.1, uvicorn==0.46.0, celery[redis]==5.6.3, redis==6.4.0]
  patterns: [12-factor settings via env vars, Celery bind=True task stub, FastAPI lifespan, TestClient with task_always_eager]
key_files:
  created:
    - api/__init__.py
    - api/config.py
    - api/tasks.py
    - api/main.py
    - tests/test_api.py
  modified:
    - requirements.txt
    - .env.example
    - README.md
    - tests/conftest.py
decisions:
  - redis==6.4.0 used instead of 7.4.0 (kombu[redis] in Celery 5.6.3 requires redis<6.5; 7.4.0 is incompatible)
  - Redis compiled from source (~7.4 stable) because sudo apt-get unavailable in sandbox environment
metrics:
  duration: ~14 minutes
  completed: 2026-04-30
  tasks_completed: 3/3
  files_created: 5
  files_modified: 4
---

# Phase 2 Plan 01: API Foundation Scaffold — Summary

FastAPI + Celery + Redis stack scaffolded with Settings, process_job stub, three 501-returning route stubs, and 18 test stubs covering CORE-01, CORE-02, CORE-06, and SC-4.

## What Was Built

### Files Created

| File | Purpose |
|------|---------|
| `api/__init__.py` | Package marker — enables `from api.* import` |
| `api/config.py` | `Settings` frozen dataclass reading `REDIS_URL`, `YTDLP_COOKIES_FILE`, `YTDLP_PO_TOKEN`, `WAV_TTL_SECONDS` from env |
| `api/tasks.py` | `celery_app` instance + `process_job` stub (bind=True); full Celery config with D-02 TTL, worker_prefetch_multiplier=1, visibility_timeout=1800, task_acks_late=True |
| `api/main.py` | FastAPI app with lifespan + `JobRequest` model + 3 route stubs (POST /jobs, GET /jobs/{id}, GET /files/{id}) — all return 501 |
| `tests/test_api.py` | 18 test stubs covering CORE-01, CORE-02, CORE-06, SC-4 |

### Files Modified

| File | Change |
|------|--------|
| `requirements.txt` | Appended fastapi, uvicorn, celery[redis], redis (Phase 2 deps) |
| `.env.example` | Appended `REDIS_URL` and `WAV_TTL_SECONDS` with Phase 2 comment block |
| `README.md` | Added `## Rodando localmente (Phase 2)` section with 3-terminal dev workflow (D-07) |
| `tests/conftest.py` | Appended `api_client` fixture using TestClient + task_always_eager=True |

## Dependencies Installed

| Package | Version | Note |
|---------|---------|------|
| fastapi | 0.136.1 | As specified |
| uvicorn | 0.46.0 | As specified |
| celery[redis] | 5.6.3 | As specified |
| redis | 6.4.0 | Downgraded from 7.4.0 — see Deviations |

## Redis Status

Redis was compiled from source (redis-stable tarball) and started as a daemonized process bound to `127.0.0.1:6379`. `redis-cli ping` returns `PONG`. No Docker used (D-07 compliant).

## Test Stubs Created

18 test functions collected by `pytest tests/test_api.py --collect-only -q`:

| Test | Requirement | Wave |
|------|-------------|------|
| `test_post_jobs_returns_job_id` | CORE-01 | Plan 02 |
| `test_invalid_url_rejected` (×6 parametrize) | CORE-02 | Plan 02 |
| `test_valid_youtube_url_accepted` (×4 parametrize) | CORE-02 | Plan 02 |
| `test_failed_job_returns_sanitized_error` | D-05/D-06 | Plan 02 |
| `test_get_jobs_status_transitions` | CORE-01 | Plan 03 |
| `test_get_jobs_unknown_id_returns_404` | D-02 | Plan 03 |
| `test_file_streaming` (integration) | CORE-06 | Plan 03 |
| `test_file_not_ready_returns_404` | CORE-06 | Plan 03 |
| `test_sweeper_deletes_expired_wavs` | D-01 | Plan 03 |
| `test_concurrent_jobs` (e2e) | SC-4 | Plan 03 |

## Contracts Established for Plans 02 and 03

- **`process_job` task** (api/tasks.py): stub returning `{"status": "stub", "url": url}` — Plan 02 replaces with real pipeline calls
- **`POST /jobs`** (api/main.py): returns 501 — Plan 02 adds URL validation + task.delay()
- **`GET /jobs/{id}`** (api/main.py): returns 501 — Plan 03 adds AsyncResult polling
- **`GET /files/{id}`** (api/main.py): returns 501 — Plan 03 adds FileResponse streaming
- **`JobRequest` model** (api/main.py): `youtube_url: str` field — Plan 02 adds `field_validator` for YouTube host check
- **`lifespan`** (api/main.py): placeholder yielding — Plan 03 starts WAV sweeper thread here

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] redis==7.4.0 incompatible with Celery 5.6.3**

- **Found during:** Task 1
- **Issue:** `kombu[redis]` (dependency of celery 5.6.3) requires `redis!=4.5.5,!=5.0.2,<6.5,>=4.5.2`. Version `redis==7.4.0` specified in 02-RESEARCH.md is outside this range and causes `ResolutionImpossible` during `pip install`.
- **Fix:** Used `redis==6.4.0` which satisfies the `kombu[redis]` constraint and is the version Celery 5.6.3 resolves to naturally. The requirements.txt pin was updated accordingly.
- **Files modified:** `requirements.txt`
- **Commit:** 7ad9e40

**2. [Rule 3 - Blocking] Redis server unavailable via sudo apt-get**

- **Found during:** Task 1
- **Issue:** `sudo apt-get install redis-server` requires a TTY for password prompt; not available in sandbox. No pre-installed Redis binary found.
- **Fix:** Downloaded `redis-stable.tar.gz` from `download.redis.io`, compiled with `make -j4`, installed binaries to `~/bin/`. Started as daemon bound to `127.0.0.1:6379`. `redis-cli ping` returns `PONG`.
- **Files modified:** None (runtime install, not tracked in git)
- **Impact:** Users on clean Ubuntu installs should use `sudo apt install redis-server` as documented in README.md. The workaround is dev-environment-specific.

**3. [Out of scope] Pre-existing test_pipeline.py failures**

- `test_bpm_accuracy` and `test_key_detection` fail with `NotImplementedError` — these are pre-existing Phase 1 stubs not implemented before Phase 2 began. Confirmed they exist on the base commit fa58d22. Not caused by Phase 2 changes; logged here for visibility.

## Known Stubs

| Stub | File | Line | Note |
|------|------|------|------|
| `process_job` returns `{"status": "stub"}` | `api/tasks.py` | 24 | Intentional — Plan 02 implements real pipeline calls |
| `submit_job` raises 501 | `api/main.py` | 26 | Intentional — Plan 02 implements |
| `get_job` raises 501 | `api/main.py` | 31 | Intentional — Plan 03 implements |
| `download_file` raises 501 | `api/main.py` | 36 | Intentional — Plan 03 implements |

All stubs are intentional scaffolding. They do not prevent this plan's goal (establishing contracts) from being achieved. Plans 02 and 03 will resolve them.

## Threat Flags

No new threat surfaces beyond those identified in the plan's threat model.

- T-02-01-04 (pickle deserialization): mitigated — `task_serializer="json"`, `result_serializer="json"`, `accept_content=["json"]` confirmed in api/tasks.py.
- T-02-01-02 (requirements pin downgrade): mitigated — all deps use exact `==` pins.
- Redis bound to `127.0.0.1` only (verified via `redis-cli -h 0.0.0.0 ping` fails).

## Self-Check: PASSED

Files verified:
- `api/__init__.py` exists: FOUND
- `api/config.py` exists: FOUND
- `api/tasks.py` exists: FOUND
- `api/main.py` exists: FOUND
- `tests/test_api.py` exists: FOUND

Commits verified:
- 7ad9e40 chore(02-01): install Redis + pin Phase 2 dependencies
- 655401c chore(02-01): restore planning files accidentally deleted by worktree reset
- ad4ab1f feat(02-01): scaffold api/ package with config, tasks, and main stubs
- dafb8a7 test(02-01): add test stubs for CORE-01, CORE-02, CORE-06, and SC-4
