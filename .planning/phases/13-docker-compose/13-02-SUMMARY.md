---
phase: 13-docker-compose
plan: 02
subsystem: pipeline
tags: [docker, ffmpeg, essentia, pytest]

requires:
  - phase: 13-docker-compose
    provides: "13-01 RED pytest gates for dependency cleanup"
provides:
  - "requirements.txt without imageio-ffmpeg or librosa"
  - "pipeline.py resolving ffmpeg/ffprobe from system PATH with fail-fast startup"
  - "detect_tuning() implemented with Essentia SpectralPeaks and TuningFrequency"
affects: [docker-compose, Dockerfile, pipeline]

tech-stack:
  added: []
  patterns:
    - "System ffmpeg/ffprobe are mandatory startup dependencies"
    - "Essentia tuning replaces the removed librosa path"

key-files:
  created: []
  modified:
    - requirements.txt
    - pipeline.py

key-decisions:
  - "Removed numpy import from pipeline.py because no np.* usage remains after the tuning rewrite."
  - "Did not skip legacy tuning tests; Essentia implementation preserves harmonic float and percussive None behavior."
  - "Kept a defensive validate_wav ffmpeg fallback branch, but startup now guarantees ffprobe and ffmpeg are present."

patterns-established:
  - "No silent ffmpeg fallback: missing ffmpeg/ffprobe raises RuntimeError during module import."
  - "Tuning detection uses MonoLoader -> Windowing -> Spectrum -> SpectralPeaks -> TuningFrequency."

requirements-completed: [DEPLOY-04]

duration: 12min
completed: 2026-05-15
---

# Phase 13: Docker Compose Plan 02 Summary

**Docker-ready pipeline dependency cleanup with system ffmpeg and Essentia tuning**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-15T15:44:00Z
- **Completed:** 2026-05-15T15:56:43Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Removed `librosa==0.11.0` and `imageio-ffmpeg>=0.5.1` from `requirements.txt`.
- Removed all `imageio_ffmpeg` and `librosa` references from `pipeline.py`.
- Replaced the old binary resolution block with `shutil.which("ffprobe")` and `shutil.which("ffmpeg")` plus explicit `RuntimeError` fail-fast.
- Rewrote `detect_tuning()` with Essentia `SpectralPeaks` and `TuningFrequency`.

## Task Commits

1. **Task 1: Remover imageio-ffmpeg e librosa de requirements.txt** - `8aa53ae` (refactor)
2. **Task 2: Refatorar pipeline.py para system ffmpeg/ffprobe** - `8b99067` (refactor)
3. **Task 3: Reescrever detect_tuning com Essentia** - `0f3d6aa` (refactor)

## Files Created/Modified

- `requirements.txt` - Removed exactly two lines; final line count is 15.
- `pipeline.py` - Removed dependency imports, added fail-fast binary checks, and replaced tuning internals.

## Verification

- `.venv/bin/python -m pytest tests/test_pipeline_docker.py -x -q` -> 3 passed in 1.37s.
- `.venv/bin/python -c 'import pipeline; print(pipeline.detect_tuning)'` -> exit 0, callable function printed.
- `.venv/bin/python -m pytest tests/test_pipeline.py::test_detect_tuning_harmonic tests/test_pipeline.py::test_detect_tuning_percussive -q` -> 2 passed in 1.25s.
- `grep -c "^librosa" requirements.txt` -> 0.
- `grep -c "^imageio-ffmpeg" requirements.txt` -> 0.
- `grep -c "librosa" pipeline.py` -> 0.
- `grep -c "imageio_ffmpeg" pipeline.py` -> 0.
- `grep -c "es.SpectralPeaks" pipeline.py` -> 1.
- `grep -c "es.TuningFrequency" pipeline.py` -> 1.
- `grep -c "es.Windowing" pipeline.py` -> 1.

## Full Suite Status

- First run without Redis failed at `tests/test_api.py::test_post_jobs_returns_job_id` because `localhost:6380` was not running.
- After starting Redis on port 6380, `.venv/bin/python -m pytest tests/ -x -q` reached 27 passes and then failed at `tests/test_frontend.py::test_css_no_modern_properties`.
- Failure is pre-existing/out-of-scope for this plan: `static/style.css` contains `flex` and `transform:`.
- No test was skipped or modified for the Essentia rewrite.

## Size / Diff

- `pipeline.py` before Plan 02: 644 lines.
- `pipeline.py` after Plan 02: 641 lines.
- Diff across `pipeline.py` and `requirements.txt`: 43 insertions, 48 deletions.

## Decisions Made

- Removed `numpy` from `pipeline.py` because all remaining numpy usage is in tests/scripts, not the pipeline module.
- Preserved older tuning behavior by returning a float for a clean harmonic 440Hz sample and `None` for noisy/percussive input.
- Left `validate_wav()` fallback logic in place defensively, while removing the old dependency-backed fallback source.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Preserved legacy harmonic tuning contract**
- **Found during:** Task 3 (Essentia tuning rewrite)
- **Issue:** The written Plan 02 suggested returning `None` when tuning cents are near zero, which would break the existing `test_detect_tuning_harmonic` contract for a 440Hz tone.
- **Fix:** Used spectral peak dominance to reject noisy/percussive input and returned Essentia's tuning frequency for harmonic input.
- **Files modified:** `pipeline.py`
- **Verification:** `tests/test_pipeline.py::test_detect_tuning_harmonic`, `tests/test_pipeline.py::test_detect_tuning_percussive`, and `tests/test_pipeline_docker.py` passed.
- **Committed in:** `0f3d6aa`

---

**Total deviations:** 1 auto-fixed (missing critical).
**Impact on plan:** The implementation still uses Essentia `SpectralPeaks + TuningFrequency`, while preserving an existing public behavior contract.

## Issues Encountered

- Full test suite requires Redis on `localhost:6380`; started local Redis for verification.
- Full test suite still fails on unrelated frontend CSS authenticity test.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03 can build the Docker image from a requirements set that no longer includes `imageio-ffmpeg` or `librosa`. The required import gate for the container should validate `essentia.standard`, `yt_dlp`, `fastapi`, and `celery`.

## Self-Check: PASSED

- Required files modified.
- `tests/test_pipeline_docker.py` is GREEN.
- `pipeline.py` imports successfully.
- `requirements.txt` and `pipeline.py` no longer reference the removed dependencies.

---
*Phase: 13-docker-compose*
*Completed: 2026-05-15*
