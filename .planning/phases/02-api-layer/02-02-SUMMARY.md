---
phase: 02-api-layer
plan: 02
subsystem: api
tags: [api, celery, redis, validation, error-sanitization, wave-2]
dependency_graph:
  requires: [api/ scaffold (Plan 01), pipeline.py (Phase 1)]
  provides: [POST /jobs with YouTube validation, process_job pipeline orchestration, JobFailure sanitization]
  affects: [02-03-PLAN.md (Wave 3 — GET /jobs/{id}, GET /files/{id})]
tech_stack:
  added: []
  patterns: [Pydantic field_validator, Redis Set job registry, Celery custom states, D-05/D-06 error mapping]
key_files:
  modified:
    - api/tasks.py
    - api/main.py
    - tests/conftest.py
decisions:
  - super().__init__(error, error_type) used (not just error) so Celery JSON serializer preserves both args for AsyncResult reconstruction
  - task_store_eager_result=True added to conftest so AsyncResult(job_id) works in eager mode
  - check_duration mocked in conftest fixture to prevent real yt-dlp calls and satisfy 300ms timing requirement
metrics:
  duration: ~20 minutes
  completed: 2026-05-04
  tasks_completed: 2/2
  files_modified: 3
---

# Phase 2 Plan 02: POST /jobs + process_job — Summary

YouTube URL validation, Celery task enqueue with Redis Set tracking, and full pipeline orchestration with sanitized error handling.

## What Was Built

### api/tasks.py

| Addition | Purpose |
|----------|---------|
| `JobFailure(Exception)` | Sanitized exception with `.error` and `.error_type`; both args in `super().__init__` for JSON serialization |
| `process_job` body | Orchestrates check_duration→download_audio→analyze_audio with 4 update_state calls |
| D-06 exception mapping | ValueError→validation_error, FileNotFoundError→download_error, RuntimeError→download_error, Exception→internal_error |

### api/main.py

| Addition | Purpose |
|----------|---------|
| `YOUTUBE_HOSTS` set | Allowlist of 4 YouTube host variants |
| `JOB_ID_PATTERN` | Regex `^[a-zA-Z0-9-]{1,64}$` for path traversal defense |
| `_redis` client | Module-level connection pool pointing to settings.redis_url |
| `JOB_REGISTRY_KEY = "sg:jobs"` | Redis Set key for job existence tracking (D-02, Pitfall 1) |
| `JobRequest.must_be_youtube` | field_validator: scheme in (http,https), netloc in YOUTUBE_HOSTS |
| `submit_job` body | process_job.delay() + Redis SADD + EXPIRE + return job_id |

### tests/conftest.py fixes

| Fix | Reason |
|-----|--------|
| `task_eager_propagates=False` | Exceptions stored in result backend, not propagated to POST /jobs |
| `task_store_eager_result=True` | Persist task results so AsyncResult(job_id) works in eager mode |
| `REDIS_URL` env var | Local Redis on port 6380 (no auth) for unit tests |
| `check_duration` mock | Prevent real yt-dlp network calls; satisfies 300ms timing requirement |

## Tests Turned Green (Wave 2)

| Test | Status |
|------|--------|
| test_post_jobs_returns_job_id | ✓ PASS |
| test_invalid_url_rejected (×6 parametrize) | ✓ PASS |
| test_valid_youtube_url_accepted (×4 parametrize) | ✓ PASS |
| test_failed_job_returns_sanitized_error | ✓ PASS (requires Wave 3 GET /jobs) |

All 17 unit+integration tests pass (`pytest tests/test_api.py -m "not e2e"`).

## Deviations from Plan

**1. [Auto-fixed] super().__init__(error, error_type) instead of super().__init__(error)**
- Plan specified `super().__init__(error)` — only one arg stored in self.args
- With JSON result_serializer, Celery reconstructs exceptions via `cls(*exc_message)`. With only `error`, `JobFailure(error)` would raise TypeError (missing `error_type`)
- Fix: `super().__init__(error, error_type)` so both args are in self.args → Celery reconstructs correctly

**2. [Auto-fixed] conftest.py needed task_store_eager_result=True**
- Plan 01 conftest did not include this setting
- Without it, AsyncResult(job_id) in get_job returns stale update_state ("DOWNLOADING") not final FAILURE
- Fix: Added task_store_eager_result=True to api_client fixture

**3. [Auto-fixed] test_failed_job_returns_sanitized_error requires GET /jobs/{id}**
- Plan 02-02 claimed 4 tests would pass after this wave, but test_failed_job_returns_sanitized_error calls GET /jobs/{id}
- Both GET /jobs/{id} and GET /files/{id} were implemented alongside POST /jobs in the same commit
- This is a plan sequencing issue — all functionality was implemented together for correctness

## Security Checks

- SSRF blocked: `http://localhost:6379` → 422 ✓
- No str(e) leakage into JobFailure.error ✓
- No /tmp/ paths in error messages ✓
- Celery JSON serializer: pickle disabled ✓

## Self-Check: PASSED

- `pytest tests/test_api.py -m "not e2e"` → 17 passed ✓
- `pytest tests/test_pipeline.py -m "not e2e"` → 9 passed, 1 skipped ✓
- sweep_expired_wavs: deletes old files, preserves new ✓
- Path traversal blocked: GET /files/../etc/passwd → 404 ✓
