---
phase: 01-processing-pipeline
reviewed: 2026-04-30T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - pipeline.py
  - tests/test_pipeline.py
  - tests/conftest.py
  - requirements.txt
  - .env.example
  - scripts/generate_sample_wav.py
  - README.md
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-30
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The processing pipeline is well-structured and demonstrates careful attention to known pitfalls (numpy ndarray coercion, yt-dlp extractor_args format, ffprobe injection prevention). Security posture is solid: subprocess calls use list form throughout, no hardcoded secrets, `.gitignore` correctly excludes `cookies.txt` and `.env`.

Three warnings are worth addressing before Phase 2 integration: a silent incorrect result on zero-variance chroma (silence passed through `validate_wav`), an incomplete cleanup path for non-`DownloadError` yt-dlp exceptions, and a CWD-dependent path in the e2e test runner that will fail if pytest is not invoked from the project root.

Four informational items cover dependency pinning, test isolation, stage comment numbering, and a duplicate env-var lookup.

---

## Warnings

### WR-01: Silent wrong key result on zero-variance chroma (silence passed as audio)

**File:** `pipeline.py:299-313`
**Issue:** `_detect_key_from_chroma` uses `np.corrcoef` to correlate each of 24 tone profiles against the mean chroma vector. When the input audio is silence (or a DC-only signal), `chroma_mean` is a constant array with zero variance, making every correlation coefficient `NaN`. `np.argmax` on an all-`NaN` array returns `0` without raising an error, which silently maps to `"C major"`. `validate_wav` only checks that `duration >= 1.0s` — a 1-second silent WAV passes validation and reaches `detect_key` with no protection.

A user who downloads a video whose audio track is silence (content creator error, or a muted re-upload) will receive `"C major" / "8B"` with no indication that detection failed.

**Fix:**
```python
def _detect_key_from_chroma(chroma: "np.ndarray") -> str:
    chroma_mean = chroma.mean(axis=1)

    # Guard: zero-variance chroma (silence, DC-only) produces NaN correlations.
    if np.std(chroma_mean) < 1e-6:
        return "unknown"  # caller can surface this to the user

    major_corrs = [
        float(np.corrcoef(np.roll(_MAJOR_PROFILE, i), chroma_mean)[0, 1])
        for i in range(12)
    ]
    minor_corrs = [
        float(np.corrcoef(np.roll(_MINOR_PROFILE, i), chroma_mean)[0, 1])
        for i in range(12)
    ]
    ...
```
Also update `key_to_camelot` to return `"?"` for `"unknown"` (already handled by the `dict.get` default) and update `analyze_audio`'s docstring to list `"unknown"` as a possible `key` value.

---

### WR-02: Partial .wav file left on disk when yt-dlp raises ExtractorError

**File:** `pipeline.py:126-154`
**Issue:** The `except` block on line 129 catches only `yt_dlp.utils.DownloadError`. `yt_dlp.utils.ExtractorError` is a sibling class (both inherit from `YoutubeDLError`, but `ExtractorError` is NOT a subclass of `DownloadError`). If yt-dlp raises `ExtractorError` mid-download (geo-restriction, unsupported format discovered during extraction), the `except` block is skipped, the `finally` block removes only non-`.wav` intermediates, and any partial `.wav` written by the FFmpeg postprocessor is left in `/tmp`.

In `__main__`, the `ExtractorError` propagates to the bare `except Exception` handler and is surfaced as `internal_error` rather than `download_error`, which is also a misleading error type.

**Fix:**
```python
except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
    for f in WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*"):
        try:
            f.unlink()
        except OSError:
            pass
    raise RuntimeError(f"yt-dlp download failed: {e}") from e
```
This also causes `__main__` to surface the error as `download_error` (via the `except RuntimeError` handler on line 491), which is the correct type for geo-restriction and extraction failures.

---

### WR-03: CWD-dependent path in e2e test runner

**File:** `tests/test_pipeline.py:240-241`
**Issue:** `_run_pipeline_e2e` invokes `[sys.executable, "pipeline.py", url]`. The string `"pipeline.py"` is a relative path resolved against the process's current working directory at the time `subprocess.run` is called. If pytest is run from any directory other than the project root (e.g., `cd tests && pytest` or a CI configuration that changes CWD), the subprocess will raise `FileNotFoundError: [Errno 2] No such file or directory: 'pipeline.py'`, failing with a confusing error message.

**Fix:**
```python
# At module level in test_pipeline.py:
_PROJECT_ROOT = Path(__file__).parent.parent

# In _run_pipeline_e2e:
result = subprocess.run(
    [sys.executable, str(_PROJECT_ROOT / "pipeline.py"), url],
    capture_output=True,
    text=True,
    timeout=300,
)
```

---

## Info

### IN-01: scipy upper bound not pinned in requirements.txt

**File:** `requirements.txt:5`
**Issue:** `scipy>=1.10` has no upper bound, unlike `numpy>=2.0,<3.0`. scipy is a transitive dependency of librosa. A future breaking scipy release (e.g., 2.x removing a deprecated API that librosa uses) could silently break the environment on a fresh install. Given that `yt-dlp` and `librosa` are pinned to exact versions, the asymmetry is surprising.

**Fix:**
```
scipy>=1.10,<2.0
```
Adjust the upper bound when upgrading librosa intentionally.

---

### IN-02: E2E tests do not clean up WAV files after assertions

**File:** `tests/test_pipeline.py:269-271`
**Issue:** `_run_pipeline_e2e` asserts that `wav_path.exists()` and checks file size, but never deletes the WAV file after the test. Successful e2e runs leave `/tmp/sg_*.wav` files (potentially hundreds of MB each) on the CI/dev machine. `tmp_path` is passed to the e2e test functions but not used by `_run_pipeline_e2e`.

**Fix:**
Add cleanup after the size assertion:
```python
wav_path = Path(data["wav_path"])
assert wav_path.exists(), f"WAV not on disk: {wav_path}"
assert wav_path.stat().st_size > 1024, f"WAV suspiciously small: {wav_path.stat().st_size} bytes"
# Cleanup
try:
    wav_path.unlink()
except OSError:
    pass  # already gone, not a test failure
```

---

### IN-03: Stage comment numbering skips Stage 5

**File:** `pipeline.py:395`
**Issue:** Stage comments label the pipeline stages 0 through 4 and then jump to "Stage 6" for `analyze_audio`. Stage 5 (the Camelot lookup, `key_to_camelot`) is never labeled. This is a minor documentation inconsistency that could cause confusion when cross-referencing the CONTEXT.md pipeline description.

**Fix:** Either label `key_to_camelot` as `# Stage 5: Camelot lookup` or renumber `analyze_audio` to `# Stage 5: Top-level analysis orchestrator`.

---

### IN-04: Duplicate env-var lookup in _e2e_skip_if_no_creds

**File:** `tests/test_pipeline.py:220-221`
**Issue:** `os.environ.get("YTDLP_COOKIES_FILE")` is called twice on the same line — once for the truthiness check and once as the default argument to `Path()`:
```python
if not os.environ.get("YTDLP_COOKIES_FILE") or not Path(os.environ.get("YTDLP_COOKIES_FILE", "")).exists():
```
This is redundant. If the first `get` returns a non-empty string, the second `get` re-reads the same key. Not a bug (env vars are immutable in-process), but needlessly verbose.

**Fix:**
```python
def _e2e_skip_if_no_creds():
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE", "")
    if not cookies_file or not Path(cookies_file).exists():
        pytest.skip("YTDLP_COOKIES_FILE not set or file missing — e2e requires real cookies")
    if not os.environ.get("YTDLP_PO_TOKEN"):
        pytest.skip("YTDLP_PO_TOKEN not set — e2e requires real PO Token")
```

---

_Reviewed: 2026-04-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
