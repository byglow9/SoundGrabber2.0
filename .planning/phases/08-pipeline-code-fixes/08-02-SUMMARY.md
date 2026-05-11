---
phase: 08-pipeline-code-fixes
plan: "02"
subsystem: pipeline
tags: [yt-dlp, ffprobe, ffmpeg, imageio-ffmpeg, shutil, pipeline-fixes]

# Dependency graph
requires:
  - phase: 08-01
    provides: 08-01-red-tests
provides:
  - pipeline-ffprobe-resolution-fix
  - pipeline-ffmpeg-dir-fix
  - pipeline-no-cache-dir
  - pipeline-retries
affects: [pipeline.py, tests/test_pipeline_fixes.py]

# Tech tracking
tech-stack:
  added: []
  patterns: [shutil-which-system-first-fallback, module-level-path-resolution]

key-files:
  created: []
  modified:
    - pipeline.py

key-decisions:
  - "shutil.which('ffprobe') as primary source for _FFPROBE_PATH with imageio-ffmpeg fallback (D-01)"
  - "_FFMPEG_DIR as module-level directory constant for ffmpeg_location in yt-dlp (D-02)"
  - "no_cache_dir: True in both check_duration and download_audio ydl_opts (D-04)"
  - "retries/fragment_retries only in download_audio (check_duration uses skip_download=True so retries irrelevant)"

patterns-established:
  - "Module-level path resolution: system binary first via shutil.which(), imageio-ffmpeg fallback with WARNING log"
  - "ffmpeg_location in yt-dlp must be a directory path, not a binary path"

requirements-completed: [PIPE-01, PIPE-02, PIPE-03, PIPE-04]

# Metrics
duration: 3min
completed: 2026-05-11
---

# Phase 8 Plan 02: Pipeline Code Fixes — Summary

**Fixed 4 bugs in pipeline.py: shutil.which() for ffprobe resolution, _FFMPEG_DIR directory for yt-dlp ffmpeg_location, no_cache_dir to prevent nsig stale cache, retries=3 for download resilience.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-11T13:52:13Z
- **Completed:** 2026-05-11T13:55:14Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Fixed `_FFPROBE_PATH` to use `shutil.which("ffprobe")` as primary source with imageio-ffmpeg fallback and WARNING log when system ffprobe is absent (PIPE-01)
- Added `_FFMPEG_DIR` module-level variable as the directory containing ffmpeg binary; fixed `ffmpeg_location` in both `check_duration` and `download_audio` ydl_opts to pass this directory instead of the binary path (PIPE-02)
- Added `"no_cache_dir": True` to both `check_duration` and `download_audio` ydl_opts to prevent stale nsig cache between Railway deploys (PIPE-03)
- Added `"retries": 3` and `"fragment_retries": 3` to `download_audio` ydl_opts only — tolerates transient network failures (PIPE-04)
- All 6 pipeline tests from Plan 01 (RED) now GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix module-level constants and add shutil import (PIPE-01, PIPE-02)** - `a888245` (feat)
2. **Task 2: Fix ffmpeg_location and add no_cache_dir + retries (PIPE-02, PIPE-03, PIPE-04)** - `08e1385` (feat)

## Files Created/Modified

- `pipeline.py` — Added `import logging`, `import shutil`, `logger = logging.getLogger(__name__)`, `_FFMPEG_DIR`, shutil.which() resolution for `_FFPROBE_PATH`, `no_cache_dir` and `retries` in ydl_opts, `ffmpeg_location` changed to `_FFMPEG_DIR` in both functions

## Decisions Made

- `shutil.which()` as primary resolution for ffprobe — system-installed ffprobe is more reliable than imageio-ffmpeg's bundled binary on Railway (where ffmpeg system package is available via nixpacks.toml)
- `retries` only in `download_audio` — `check_duration` uses `skip_download=True` which means no actual download happens, so retries are not meaningful there
- WARNING log (not CRITICAL, not exception) for missing system ffprobe — it's an operator hint, not a fatal condition since imageio-ffmpeg fallback works

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — pipeline.py changes are complete functional fixes. No placeholder values, no hardcoded empty structures.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. Changes are internal to pipeline.py module-level constants and yt-dlp opts dicts. Trust boundary analysis per plan threat model: both `shutil.which()` and `imageio_ffmpeg.get_ffmpeg_exe()` read from OS/installed packages, no user-controlled input.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PIPE-01..04 complete; pipeline.py correctly resolves ffprobe and configures yt-dlp for Railway
- Plan 08-03 (PIPE-05 cookies validation + DEPLOY-01 nixpacks.toml) is ready to execute
- No blockers

---
*Phase: 08-pipeline-code-fixes*
*Completed: 2026-05-11*
