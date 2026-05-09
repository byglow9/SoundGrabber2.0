---
phase: 06-precision-analysis-engine
fixed_at: 2026-05-09T04:57:26Z
review_path: .planning/phases/06-precision-analysis-engine/06-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-09T04:57:26Z
**Source review:** .planning/phases/06-precision-analysis-engine/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Non-DownloadError yt-dlp exceptions bypass cleanup and leak /tmp files

**Files modified:** `pipeline.py`
**Commit:** 4dc1978
**Applied fix:** Replaced `except yt_dlp.utils.DownloadError` with `except yt_dlp.utils.YoutubeDLError` (the common base class for all yt-dlp errors). Also updated the error message from `"yt-dlp download failed: {e}"` to `"yt-dlp failed: {e}"` to be accurate for non-download errors (e.g. geo-block, post-processing, unsupported URL). This ensures partial `/tmp/sg_*.wav` files are cleaned up for all yt-dlp failure modes, and that all yt-dlp exceptions are consistently re-raised as `RuntimeError` → `download_error` in the API layer.

### WR-01: e2e test helper does not assert `tuning_hz` — Phase 6 field has no e2e coverage

**Files modified:** `tests/test_pipeline.py`
**Commit:** 24252e9
**Applied fix:** Added `"tuning_hz"` to the `required` set in `_run_pipeline_e2e()` (line 380), expanding the 7-element Phase 1-5 contract to the 8-element Phase 6 contract. The field is wrapped to a second line for readability. All three e2e tests (`test_e2e_rock`, `test_e2e_trap`, `test_e2e_house`) now assert `tuning_hz` presence, closing the regression blind spot.

### WR-02: Bare `except Exception: pass` in test swallows unexpected errors silently

**Files modified:** `tests/test_pipeline.py`
**Commit:** 093332d
**Applied fix:** Replaced `except Exception: pass` with `except (FileNotFoundError, RuntimeError): pass` in `test_download_opts_include_auth()`. Updated the comment to explain what is expected: `FakeYDL.download()` creates a stub WAV but the subsequent path/validation check may raise one of these specific exceptions. Unexpected errors (e.g. `AttributeError` from import issues or signature mismatch) will now propagate and surface as clear test failures instead of being silently swallowed.

---

_Fixed: 2026-05-09T04:57:26Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
