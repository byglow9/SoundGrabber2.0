---
phase: 02-api-layer
plan: 03
subsystem: api
tags: [api, file-streaming, sweeper, path-traversal, wave-3, checkpoint]
dependency_graph:
  requires: [api/ Plans 01+02, api/tasks.py JobFailure]
  provides: [GET /jobs/{id} state mapping, GET /files/{id} WAV streaming, sweep_expired_wavs daemon]
  affects: [Phase 3 hardening — rate limiting will build on this HTTP contract]
tech_stack:
  added: [threading, time, pathlib]
  patterns: [FileResponse streaming, daemon thread sweeper, path traversal defense (resolve+relative_to+sg_ prefix)]
key_files:
  modified:
    - api/main.py
decisions:
  - Two independent path traversal checks: resolve().relative_to(/tmp) AND name.startswith("sg_")
  - 410 (Gone) for expired/invalid WAV path, 404 for not-done jobs
  - daemon=True thread: no explicit join needed, dies with uvicorn process
  - sweep_expired_wavs is a pure standalone function (testable without threads)
metrics:
  duration: ~15 minutes (implemented together with Plan 02 in same commit)
  completed: 2026-05-04
  tasks_completed: 2/3 automated (Task 3 is human checkpoint — pending)
  files_modified: 1
---

# Phase 2 Plan 03: GET /jobs + GET /files + Sweeper — Summary

Closes the Phase 2 HTTP contract: state polling, WAV streaming, and lifecycle infrastructure.

## What Was Built

### GET /jobs/{id} State Mapping

| Celery State | API Status | Notes |
|---|---|---|
| PENDING + NOT in sg:jobs | 404 | D-02: never existed or expired |
| PENDING + in sg:jobs | queued | |
| STARTED | queued | |
| DOWNLOADING | downloading | includes stage metadata |
| CONVERTING | converting | includes stage metadata |
| ANALYZING | analyzing | includes stage metadata |
| SUCCESS | done | wav_path stripped (D-05) |
| FAILURE | failed | JobFailure.error + .error_type unpacked |

### GET /files/{id} Path Traversal Defense

Two independent guards before FileResponse:
1. `wav_path.resolve().relative_to(Path("/tmp").resolve())` → 410 if outside /tmp
2. `wav_path.name.startswith("sg_")` → 410 if wrong prefix
3. `wav_path.exists()` → 410 if file expired/deleted

### WAV Sweeper Infrastructure

- `sweep_expired_wavs(directory, ttl_seconds) → int`: pure function, testable directly
- `_run_sweeper_loop()`: infinite daemon loop, survives individual sweep errors
- `lifespan`: starts `threading.Thread(daemon=True, name="wav-sweeper")` on startup

## Tests Turned Green (Wave 3)

| Test | Status |
|------|--------|
| test_get_jobs_status_transitions | ✓ PASS |
| test_get_jobs_unknown_id_returns_404 | ✓ PASS |
| test_failed_job_returns_sanitized_error | ✓ PASS |
| test_file_streaming (integration) | ✓ PASS |
| test_file_not_ready_returns_404 | ✓ PASS |
| test_sweeper_deletes_expired_wavs | ✓ PASS |

## Task 3: Manual Concurrency UAT — PENDING

**Status:** Checkpoint presented to user — awaiting human verification.

ROADMAP success criteria #4 requires real Redis + real Celery worker + real uvicorn + live YouTube cookies. This cannot be tested with TestClient.

Instructions for manual UAT are in `02-03-PLAN.md` Task 3 (terminals: Redis, worker, uvicorn, curl).

## Self-Check: PASSED (automated)

- `pytest tests/test_api.py -m "not e2e"` → 17 passed ✓
- sweep_expired_wavs smoke test: deletes old, preserves new ✓  
- Path traversal: GET /files/../etc/passwd → 404 ✓
- wav_path not leaked in SUCCESS response ✓
