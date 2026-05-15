---
phase: 13-docker-compose
plan: 01
subsystem: testing
tags: [pytest, docker, pipeline, red-tests]

requires: []
provides:
  - "RED pytest coverage for Docker dependency cleanup in pipeline.py"
  - "Import-inspection tests for imageio_ffmpeg and librosa removal"
  - "Synthetic WAV smoke test for detect_tuning()"
affects: [docker-compose, pipeline, requirements]

tech-stack:
  added: []
  patterns:
    - "AST-based source import inspection for dependency removal gates"
    - "tmp_path-generated WAV fixture for tuning smoke tests"

key-files:
  created:
    - tests/test_pipeline_docker.py
  modified: []

key-decisions:
  - "Kept the tuning smoke test marked as integration because pytest.ini already registers the marker."

patterns-established:
  - "Docker dependency tests inspect pipeline.py imports without importing the module first."
  - "Plan 02 can use pytest tests/test_pipeline_docker.py -x -q as its fast feedback loop."

requirements-completed: [DEPLOY-04]

duration: 4min
completed: 2026-05-15
---

# Phase 13: Docker Compose Plan 01 Summary

**RED pytest gates for Docker-safe pipeline dependencies and future Essentia tuning behavior**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-15T15:48:00Z
- **Completed:** 2026-05-15T15:52:29Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_pipeline_docker.py` with exactly 3 tests.
- Added RED import gates for `imageio_ffmpeg` and `librosa` in `pipeline.py`.
- Added a synthetic WAV tuning smoke test that will exercise `detect_tuning()` after Plan 02 rewrites it to Essentia.

## Task Commits

1. **Task 1: Criar tests/test_pipeline_docker.py com 3 stubs RED para DEPLOY-04 / D-02 / D-03** - `7b580e9` (test)

## Files Created/Modified

- `tests/test_pipeline_docker.py` - AST import inspection plus synthetic WAV tuning smoke test.

## Verification

- `grep -c "^def test_" tests/test_pipeline_docker.py` -> `3`
- `grep -c "test_no_imageio_ffmpeg_import" tests/test_pipeline_docker.py` -> `2`
- `grep -c "test_no_librosa_import" tests/test_pipeline_docker.py` -> `2`
- `grep -c "test_detect_tuning_essentia" tests/test_pipeline_docker.py` -> `2`
- `grep -c "import ast" tests/test_pipeline_docker.py` -> `1`
- `grep -v '^#' tests/test_pipeline_docker.py | grep -c "imageio_ffmpeg"` -> `5`
- Header contains `Phase 13` and `DEPLOY-04`.

## RED Status

- `.venv/bin/python -m pytest tests/test_pipeline_docker.py::test_no_imageio_ffmpeg_import -x -q` -> exit 1, expected RED because `pipeline.py` still imports `imageio_ffmpeg`.
- `.venv/bin/python -m pytest tests/test_pipeline_docker.py::test_no_librosa_import -x -q` -> exit 1, expected RED because `pipeline.py` still imports `librosa`.
- `.venv/bin/python -m pytest tests/test_pipeline_docker.py -x -q` -> exit 1 in 0.03s, stopping at `test_no_imageio_ffmpeg_import`.

## Decisions Made

- Used AST parsing rather than string scanning so removal gates are tied to real import declarations.
- Kept the integration marker on `test_detect_tuning_essentia` because `pytest.ini` already registers `integration`.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02 can now remove `imageio-ffmpeg` and `librosa` from `requirements.txt` and `pipeline.py`, then run `.venv/bin/python -m pytest tests/test_pipeline_docker.py -x -q` until all 3 tests are GREEN.

## Self-Check: PASSED

- `tests/test_pipeline_docker.py` exists.
- Required test functions exist.
- Expected RED checks fail before the refactor.
- Task commit exists for `13-01`.

---
*Phase: 13-docker-compose*
*Completed: 2026-05-15*
