---
phase: 08-pipeline-code-fixes
plan: "03"
subsystem: api
tags: [fastapi, lifespan, cookies, nixpacks, railway, deploy, yt-dlp]

requires:
  - phase: 08-01
    provides: RED tests test_pipe05 and test_deploy01 that this plan turns GREEN

provides:
  - _check_cookies() function in api/main.py (PIPE-05)
  - nixpacks.toml at project root (DEPLOY-01)

affects:
  - 08-02
  - pipeline.py (nixpacks.toml enables shutil.which("ffprobe") to resolve on Railway)

tech-stack:
  added: []
  patterns:
    - non-blocking-startup-log: CRITICAL log in lifespan without raising, operator visible but not fatal
    - nixpacks-apt-declaration: aptPkgs in nixpacks.toml for Railway system package installation

key-files:
  created:
    - nixpacks.toml
  modified:
    - api/main.py

key-decisions:
  - "_check_cookies is non-blocking: logs CRITICAL and returns, never raises (D-06, D-07, D-08)"
  - "nixpacks.toml uses aptPkgs = [ffmpeg] without Python version pin — requirements.txt manages Python"

patterns-established:
  - "Startup check pattern: _check_X(settings.X) after _check_redis_auth, before sweeper thread"

requirements-completed:
  - PIPE-05
  - DEPLOY-01

duration: ~2min
completed: 2026-05-11
---

# Phase 8 Plan 03: Cookies Validation and nixpacks.toml — Summary

**CRITICAL-level startup log for missing/invalid cookies.txt via _check_cookies() in FastAPI lifespan, plus nixpacks.toml declaring ffmpeg as a Railway apt package.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-11T13:52:26Z
- **Completed:** 2026-05-11T13:55:00Z
- **Tasks:** 2
- **Files modified:** 2 (api/main.py modified, nixpacks.toml created)

## Accomplishments

- Added `_check_cookies(cookies_path)` private function to `api/main.py`, placed after `_check_redis_auth` and before the sweeper thread start in lifespan
- Function handles 4 cases: empty path, file not found, OSError on read, missing `__Secure-3PSID` sentinel — all log CRITICAL without raising
- Called `_check_cookies(settings.cookies_path)` in lifespan with comment referencing D-06/D-07/D-08
- Created `nixpacks.toml` at project root with `aptPkgs = ["ffmpeg"]` so Railway installs system ffmpeg+ffprobe on build

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _check_cookies function and call it in lifespan (PIPE-05)** - `33a1461` (feat)
2. **Task 2: Create nixpacks.toml at project root (DEPLOY-01)** - `56df68a` (feat)

**Plan metadata:** committed with SUMMARY.md (docs: complete plan)

## Files Created/Modified

- `api/main.py` — Added `_check_cookies()` function (50 lines) after `_check_redis_auth`; added call in lifespan with PIPE-05 comment
- `nixpacks.toml` — New file at project root; declares `aptPkgs = ["ffmpeg"]` for Railway build system

## Decisions Made

- `_check_cookies` is intentionally non-blocking per D-06/D-07/D-08: rotating cookies during a live deploy should not cause downtime. The CRITICAL log is an operator warning in Railway dashboard, not a startup gate.
- `nixpacks.toml` does not pin Python version — `requirements.txt` already handles Python dependencies; adding a Python pin here would create a second source of truth.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- When running pytest from the worktree working directory, the venv is at the main project path `/home/glow/Documentos/SoundGrabber2.0/.venv` — used absolute venv path to invoke pytest correctly.
- `essentia` and `imageio-ffmpeg` were missing from the venv (same environment issue as in Plan 01). Installed both to unblock test collection. These packages are already in `requirements.txt` so this is a local environment setup artifact, not a code issue.

## Known Stubs

None — production code changes are fully functional. No UI data flows involved.

## Threat Flags

None — changes are within the already-analyzed threat boundaries:
- `_check_cookies` reads from `settings.cookies_path` (operator-configured, not user-supplied)
- No cookie values are logged, only the file path and presence/absence of `__Secure-3PSID` key name
- `nixpacks.toml` directives are in source control and reference only a well-known system package

## Self-Check

- FOUND: `api/main.py` with `_check_cookies` function and call in lifespan
- FOUND: `nixpacks.toml` at project root with `aptPkgs = ["ffmpeg"]`
- FOUND: commit `33a1461` — feat(08-03): add _check_cookies validation in lifespan (PIPE-05)
- FOUND: commit `56df68a` — feat(08-03): create nixpacks.toml with ffmpeg aptPkg (DEPLOY-01)
- test_pipe05_critical_log_when_cookies_missing_sentinel: PASSED (GREEN)
- test_deploy01_nixpacks_toml_exists_with_ffmpeg: PASSED (GREEN)

## Self-Check: PASSED

---
*Phase: 08-pipeline-code-fixes*
*Completed: 2026-05-11*
