---
phase: 06-precision-analysis-engine
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - pipeline.py
  - requirements.txt
  - tests/test_pipeline.py
  - api/tasks.py
findings:
  critical: 1
  warning: 2
  info: 4
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-09
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the four files changed in Phase 6 (Precision Analysis Engine): the core pipeline
module, requirements, integration tests, and Celery task. The Phase 6 additions — Essentia
RhythmExtractor2013, KeyExtractor with edma profile, and detect_tuning via HPSS gating —
are structurally sound and the HPSS gate logic is correct (verified: white-noise ratio ~0.05,
well below the 0.2 threshold).

One critical bug was found: `download_audio` only catches `yt_dlp.utils.DownloadError` in its
cleanup except block, but a large set of common yt-dlp error types (`ExtractorError`,
`GeoRestrictedError`, `PostProcessingError`, `UnsupportedError`, etc.) are NOT subclasses of
`DownloadError`. When these errors fire, partial `/tmp/sg_*.wav` files leak and the exceptions
are misclassified as `internal_error` in the API layer instead of `download_error`.

Two warnings cover: an e2e test helper that does not assert the Phase-6-added `tuning_hz`
field (creating a regression blind spot), and a bare `except Exception: pass` in a test that
silently swallows unexpected errors.

---

## Critical Issues

### CR-01: Non-DownloadError yt-dlp exceptions bypass cleanup and leak /tmp files

**File:** `pipeline.py:136`
**Issue:** The `except yt_dlp.utils.DownloadError` block is the only place where partial
`/tmp/sg_*.wav` files are cleaned up on failure. However, many common yt-dlp exception
types are NOT subclasses of `DownloadError` and therefore bypass this block entirely:

- `ExtractorError` — private/unavailable video
- `GeoRestrictedError` — geo-blocked content
- `PostProcessingError` — FFmpeg WAV conversion failure (most likely to leave a partial .wav)
- `UnsupportedError` — unsupported URL format
- `DownloadCancelled`, `ThrottledDownload`, and others

When these exceptions fire, only the `finally` block runs. The `finally` block deletes
non-.wav intermediates, but does NOT delete partial `.wav` files — leaking `/tmp/sg_*.wav`
on disk. Additionally, because these exceptions are not wrapped in `RuntimeError`, they
propagate to `api/tasks.py` as bare yt-dlp exceptions and fall into the catch-all
`except Exception` handler, where they are misreported as `internal_error` instead of
`download_error`.

The 60-second WAV sweeper in `api/main.py` will eventually clean up the leaked files, but
only after `settings.wav_ttl` seconds — under high load or repeated failures this could
fill `/tmp`.

**Fix:** Catch `yt_dlp.utils.YoutubeDLError` (the common base of all yt-dlp errors) instead
of the narrow `DownloadError`, and re-raise as `RuntimeError` with an appropriate message:

```python
# pipeline.py — replace the except block (lines 136-142)
    except yt_dlp.utils.YoutubeDLError as e:
        for f in WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*"):
            try:
                f.unlink()
            except OSError:
                pass
        raise RuntimeError(f"yt-dlp failed: {e}") from e
```

This ensures all yt-dlp failures (geo-block, post-processing, unsupported URL, etc.)
produce consistent `RuntimeError` → `download_error` mapping in `api/tasks.py`, and that
no partial files are left behind.

---

## Warnings

### WR-01: e2e test helper does not assert `tuning_hz` — Phase 6 field has no e2e coverage

**File:** `tests/test_pipeline.py:380`
**Issue:** `_run_pipeline_e2e()` defines the required output fields as a 7-element set that
matches the Phase 1-5 contract. Phase 6 added `tuning_hz` to the `analyze_audio` output,
and `test_json_output_shape` (unit) and `test_json_output_shape_integration` (integration)
both assert it. However, the e2e helper that drives all three e2e tests (`test_e2e_rock`,
`test_e2e_trap`, `test_e2e_house`) does NOT include `tuning_hz` in `required`:

```python
# line 380 — current (missing tuning_hz):
required = {"bpm", "key", "camelot", "bpm_half", "bpm_double", "wav_path", "duration_sec"}
```

If `tuning_hz` is accidentally dropped from the pipeline output or the Celery task result,
all three e2e tests will still pass, giving a false green. This is a regression blind spot
introduced by Phase 6.

**Fix:** Add `tuning_hz` to the required set in `_run_pipeline_e2e`:

```python
# line 380 — corrected:
required = {"bpm", "key", "camelot", "bpm_half", "bpm_double", "wav_path",
            "duration_sec", "tuning_hz"}
```

Note: The e2e subprocess reads the JSON output of `pipeline.py __main__`, which prints
`analyze_audio()`'s return dict directly. The `tuning_hz` key is present there, so the
assertion will pass on a correct build and catch future regressions correctly.

---

### WR-02: Bare `except Exception: pass` in test swallows unexpected errors silently

**File:** `tests/test_pipeline.py:87`
**Issue:** `test_download_opts_include_auth` calls `pipeline.download_audio(...)` inside a
`try/except Exception: pass` block with the intent of capturing only the ydl_opts, ignoring
all exceptions. The comment explains the intent: "We only care about the captured opts."

However, if `download_audio` raises before the `FakeYDL.__init__` runs (e.g., an
`AttributeError` from a bad import, or if the function signature changes and the mock is
never invoked), `captured_opts` stays empty and the assertions below produce confusing
failures like `"cookiefile not wired to ydl_opts"` — not because the wiring is wrong, but
because the function never ran far enough to call `yt_dlp.YoutubeDL`.

**Fix:** Catch only the specific exception that is expected (the `FileNotFoundError` or
`RuntimeError` raised after the download completes without a real WAV), not all exceptions:

```python
# tests/test_pipeline.py — replace lines 85-87
    try:
        pipeline.download_audio(
            "https://www.youtube.com/watch?v=abc123",
            "cookies.txt",
            "TESTTOKEN",
        )
    except (FileNotFoundError, RuntimeError):
        pass  # Expected: FakeYDL.download() creates a stub WAV but the path check may fail
```

---

## Info

### IN-01: `essentia==2.1b6.dev1389` pins a pre-release dev build

**File:** `requirements.txt:14`
**Issue:** The Essentia dependency is pinned to a development snapshot
(`2.1b6.dev1389`). Pre-release dev builds may have API changes, undocumented behavior, or
missing features compared to stable releases. If this exact wheel is unavailable on a
target platform or a future pip install resolves a different dev build, the RhythmExtractor2013
and KeyExtractor APIs used in `pipeline.py` may behave differently.

**Fix:** If `essentia-tensorflow` or a stable `essentia` release (e.g., `2.1b6`) provides
the required `RhythmExtractor2013(method="multifeature")` and `KeyExtractor(profileType="edma")`,
prefer the stable pin. If only the dev build has these features, document this explicitly in
a `# NOTE: stable build lacks multifeature/edma — dev build required` comment in
`requirements.txt`.

---

### IN-02: Redundant `str()` wrapping an f-string in `detect_key`

**File:** `pipeline.py:332`
**Issue:** `str(f"{key} {scale}")` applies `str()` to an f-string, which is always already
`str`. This is a no-op.

**Fix:**
```python
# line 332 — current:
return str(f"{key} {scale}"), float(strength)

# fixed:
return f"{key} {scale}", float(strength)
```

---

### IN-03: `result.get("tuning_hz")` inconsistent with direct key access for all other fields

**File:** `api/tasks.py:80`
**Issue:** All other fields from `analyze_audio()`'s result dict are accessed with direct
indexing (`result["bpm"]`, `result["key"]`, etc. on lines 72-79), which would raise
`KeyError` if a field were missing — a clear, detectable failure. Only `tuning_hz` is
accessed with `.get()`, which returns `None` silently if the key is absent. This inconsistency
means a regression where `tuning_hz` is dropped from `analyze_audio()`'s output would be
invisible at the task layer.

**Fix:** Use direct indexing for consistency, since `tuning_hz` is always present in the
`analyze_audio()` return dict:

```python
# api/tasks.py line 80 — current:
"tuning_hz": result.get("tuning_hz"),

# fixed:
"tuning_hz": result["tuning_hz"],
```

---

### IN-04: `wav_path` is included in the Celery task result dict but is an internal field

**File:** `api/tasks.py:79`
**Issue:** The task result dict returned by `process_job` includes `"wav_path"` (line 79),
annotated with a comment that it is internal and not for API consumers. The API layer in
`api/main.py` correctly strips it before responding to `GET /jobs/{id}`. This is safe as
implemented, but creates a subtle convention where the security boundary is maintained by a
rule in a different file (`api/main.py`) with no enforcement at the source.

If a future API endpoint returns the raw task result dict without stripping `wav_path`, it
would expose the server filesystem path to clients. The current design works, but the
coupling is fragile.

**Fix:** Consider returning a separate internal struct and a public struct from `process_job`,
or using a Pydantic model for the task result to make the field visibility explicit. As a
minimum, keep the existing comment and add a note in the Phase 7 plan to audit all new
endpoints that consume `AsyncResult.result`.

---

_Reviewed: 2026-05-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
