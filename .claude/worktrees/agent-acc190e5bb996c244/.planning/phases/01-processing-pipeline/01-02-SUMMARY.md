---
phase: 01-processing-pipeline
plan: 02
subsystem: pipeline
tags: [download, ytdlp, ffmpeg, pipeline, python, wav, duration-check, validation]
requirements: [CORE-03, CORE-04, CORE-05]

dependency_graph:
  requires: [01-01]
  provides: [pipeline.check_duration, pipeline.download_audio, pipeline.convert_to_wav, pipeline.validate_wav, pipeline.key_to_camelot, pipeline.analyze_audio (routing skeleton)]
  affects: [01-03, 01-04, 02-*]

tech_stack:
  added: []
  patterns:
    - yt_dlp.YoutubeDL with download=False for pre-download duration check
    - extractor_args as list-of-strings (not nested dict) for PO Token injection
    - FFmpegExtractAudio postprocessor for in-process WAV conversion
    - subprocess.run list form (no shell=True) for ffprobe validation
    - try/finally for intermediate file cleanup

key_files:
  created:
    - pipeline.py
  modified: []

decisions:
  - http_chunk_size=10485760 (10MB) chosen to avoid YouTube throttling on datacenter IPs per RESEARCH Pattern 2
  - ffprobe subprocess timeout=10s chosen as safe limit for local disk reads
  - validate_wav rejects files with duration < 1.0s as corrupt (conservative threshold)
  - analyze_audio routing skeleton added in Plan 02 (not Plan 03) to allow Plan 03 test fixtures to patch sub-functions via patch.object
  - _CAMELOT table implemented in Plan 02 (not Plan 03) as pure static data needed by test_camelot_mapping which runs in unit suite
  - glob fallback in download_audio handles outtmpl extension edge case (Assumption A2 / Pitfall 2)

metrics:
  duration: 5m21s
  completed: 2026-04-29
  tasks_completed: 3
  files_created: 1
  files_modified: 0
---

# Phase 1 Plan 02: Download + Conversion + Validation Summary

**One-liner:** yt-dlp download pipeline with cookies + PO Token auth, FFmpegExtractAudio WAV conversion, ffprobe integrity validation, and Camelot wheel lookup table.

## What Was Built

`pipeline.py` now contains the complete download + validation half of the pipeline:

| Function | Signature | Status |
|----------|-----------|--------|
| `check_duration` | `(url: str, cookies_path: str) -> dict` | Implemented (Plan 02) |
| `download_audio` | `(url: str, cookies_path: str, po_token: str) -> Path` | Implemented (Plan 02) |
| `convert_to_wav` | `(audio_path: Path) -> Path` | Implemented (Plan 02) — thin pass-through |
| `validate_wav` | `(wav_path: Path) -> float` | Implemented (Plan 02) |
| `key_to_camelot` | `(key: str) -> str` | Implemented (Plan 02) — static dict |
| `analyze_audio` | `(wav_path: Path) -> dict` | Routing skeleton (Plan 02); fills in Plan 03 |
| `detect_bpm` | `(wav_path: Path, total_duration: float) -> float` | Stub (Plan 03) |
| `detect_key` | `(wav_path: Path) -> str` | Stub (Plan 03) |

## Function Signatures (D-03 Contract)

```python
def check_duration(url: str, cookies_path: str) -> dict[str, Any]
def download_audio(url: str, cookies_path: str, po_token: str) -> Path
def convert_to_wav(audio_path: Path) -> Path
def validate_wav(wav_path: Path) -> float
def key_to_camelot(key: str) -> str
def analyze_audio(wav_path: Path) -> dict
```

## Test Results

| Test | Type | Status |
|------|------|--------|
| test_duration_check_rejects_long_video | unit | GREEN |
| test_duration_check_accepts_short_video | unit | GREEN |
| test_download_opts_include_auth | unit | GREEN |
| test_ffprobe_validates_wav | integration | GREEN |
| test_bpm_half_double_calculation | unit | GREEN (patches analyze_audio sub-functions) |
| test_camelot_mapping | unit | GREEN (Camelot table implemented early) |
| test_json_output_shape | unit | GREEN (routing skeleton + mocks) |
| test_bpm_accuracy | integration | SKIPPED (Plan 03 — needs real WAV + librosa) |
| test_key_detection | integration | SKIPPED (Plan 03 — needs librosa) |
| test_e2e_* | e2e | SKIPPED (Plan 04 — needs cookies.txt) |

**Total green after Plan 02:** 7/13 unit+integration tests (3 unit Plan 03 tests now green because routing skeleton + Camelot table were added early as Rule 3 fixes).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan 03 unit tests fail with AttributeError after pipeline.py is created**
- **Found during:** Task 3 verification
- **Issue:** `test_bpm_half_double_calculation`, `test_camelot_mapping`, and `test_json_output_shape` use `importorskip("pipeline")` guards written when `pipeline.py` didn't exist. Once Plan 02 creates `pipeline.py`, those tests run immediately and fail: `patch.object` raises `AttributeError` because `detect_bpm`, `analyze_audio`, etc. don't exist yet.
- **Fix:** Added `detect_bpm` and `detect_key` stubs (raise `NotImplementedError`), implemented the full `_CAMELOT` dict + `key_to_camelot()` as a pure static lookup (no algorithm, just data), and implemented the `analyze_audio` routing skeleton that calls the patchable sub-functions.
- **Why not Rule 4:** No architectural change — the structure matches the plan exactly; only the timing moved the static data and routing wiring from Plan 03 to Plan 02.
- **Files modified:** `pipeline.py`
- **Commit:** `d8032a3`

**2. [Rule 2 - Comment cleanup] `shell=True` appeared in docstring triggering acceptance criterion grep**
- **Found during:** Task 3 acceptance criteria verification
- **Issue:** `grep -c "shell=True" pipeline.py` returned 1 due to docstring phrase "no shell=True — prevents injection"; acceptance criterion required 0.
- **Fix:** Rewrote docstring phrase to "list form, not shell string — prevents injection".
- **Commit:** Part of `d8032a3`

## Key Decisions Made Within Claude's Discretion

| Decision | Rationale |
|----------|-----------|
| `http_chunk_size = 10485760` (10MB) | RESEARCH Pattern 2 recommendation; avoids YouTube's adaptive throttling on datacenter IPs |
| `ffprobe timeout = 10s` | Sufficient for local disk I/O; prevents hung validation on corrupt files |
| `validate_wav` min duration = 1.0s | Rejects YouTube HTML error pages (typically 0-byte or <1s stub audio) as corrupt |
| `extractor_args` only populated when `po_token` is non-empty | Allows testing with empty token without injecting empty extractor_args |
| `analyze_audio` routing skeleton in Plan 02 | Unblocks Plan 03 test stubs that need patchable attributes; zero algorithmic code added |
| `_CAMELOT` table in Plan 02 | Pure static data (no algorithm); needed to unblock `test_camelot_mapping` which runs in the unit suite |

## Operational Note for Plan 03 Executor

The analysis functions are completely independent of the download machinery. Plan 03 only needs to:

1. Replace `detect_bpm` stub body with `librosa.feature.tempo()` implementation.
2. Replace `detect_key` stub body with Krumhansl-Schmuckler chroma correlation.
3. The `_CAMELOT` table and `key_to_camelot` are already complete — do not modify.
4. The `analyze_audio` routing is already wired — do not rewrite, just fill in the stubs.
5. `validate_wav` is already called by `analyze_audio` — no changes needed.

The 3 Plan 03 unit tests (`test_bpm_half_double_calculation`, `test_camelot_mapping`, `test_json_output_shape`) are already GREEN from Plan 02; Plan 03 must keep them green while also turning green `test_bpm_accuracy` and `test_key_detection` (integration tests requiring the real librosa implementations).

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `detect_bpm` raises NotImplementedError | pipeline.py | ~252 | Implemented in Plan 03 (requires librosa) |
| `detect_key` raises NotImplementedError | pipeline.py | ~257 | Implemented in Plan 03 (requires librosa) |

These stubs do not prevent Plan 02's goal (download + convert + validate) from being achieved. Plans 03 and 04 resolve them.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| pipeline.py exists | FOUND |
| commit b57df19 (Task 1) exists | FOUND |
| commit 7698c64 (Task 2) exists | FOUND |
| commit d8032a3 (Task 3) exists | FOUND |
| 01-02-SUMMARY.md exists | FOUND |
