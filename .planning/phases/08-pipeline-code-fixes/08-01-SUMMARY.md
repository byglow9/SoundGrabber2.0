---
phase: 08-pipeline-code-fixes
plan: "01"
subsystem: pipeline-tests
tags: [tdd, red-tests, pipeline, yt-dlp, deploy]
dependency_graph:
  requires: []
  provides: [08-01-red-tests]
  affects: [tests/test_pipeline_fixes.py]
tech_stack:
  added: []
  patterns: [tdd-red-first, inspect.getsource-source-inspection, caplog-logging-assertion]
key_files:
  created:
    - tests/test_pipeline_fixes.py
  modified: []
decisions:
  - Use inspect.getsource() to assert ydl_opts contents without mocking yt-dlp
  - PIPE-01 test branches on shutil.which() result (system ffprobe present vs absent)
  - PIPE-05 test uses caplog at CRITICAL level with patched settings to isolate lifespan logic
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 8 Plan 01: RED Tests for Pipeline Fixes — Summary

**One-liner:** 8 failing TDD tests in test_pipeline_fixes.py specifying expected behaviors for PIPE-01..05 and DEPLOY-01 fixes.

---

## Objective

Write 6–8 intentionally failing (RED) tests in `tests/test_pipeline_fixes.py` that define the expected behaviors for Phase 8 pipeline fixes. These tests MUST fail against the current codebase and will turn GREEN after 08-02-PLAN.md and 08-03-PLAN.md execute.

---

## What Was Built

Created `tests/test_pipeline_fixes.py` with 8 RED tests:

| Test | Requirement | What it checks |
|------|-------------|----------------|
| `test_pipe01_ffprobe_uses_shutil_which_when_available` | PIPE-01 | `_FFPROBE_PATH == shutil.which("ffprobe")` when system ffprobe is on PATH |
| `test_pipe02_ffmpeg_dir_attribute_exists` | PIPE-02 | `_FFMPEG_DIR` attribute exists on pipeline module and is a directory |
| `test_pipe02_check_duration_uses_ffmpeg_dir` | PIPE-02 | `check_duration` source references `_FFMPEG_DIR` (not `_FFMPEG_PATH`) |
| `test_pipe03_no_cache_dir_in_check_duration` | PIPE-03 | `"no_cache_dir": True` present in `check_duration` ydl_opts |
| `test_pipe03_no_cache_dir_in_download_audio` | PIPE-03 | `"no_cache_dir": True` present in `download_audio` ydl_opts |
| `test_pipe04_retries_in_download_audio` | PIPE-04 | `"retries": 3` and `"fragment_retries": 3` in `download_audio` ydl_opts |
| `test_pipe05_critical_log_when_cookies_missing_sentinel` | PIPE-05 | lifespan emits CRITICAL log when `cookies.txt` lacks `__Secure-3PSID` |
| `test_deploy01_nixpacks_toml_exists_with_ffmpeg` | DEPLOY-01 | `nixpacks.toml` exists at project root and contains "ffmpeg" |

---

## Verification

```
$ pytest tests/test_pipeline_fixes.py -v
8 failed, 0 passed in 3.93s
```

All 8 tests fail with AssertionError messages naming the specific missing fix. No ImportError or SyntaxError. The file is syntactically valid and all imports resolve.

---

## Decisions Made

1. **inspect.getsource() for ydl_opts assertions** — avoids needing to mock yt-dlp or instrument its internals; reads the actual function source text and asserts the expected key strings are present. Simpler and more durable than patching ydl instantiation.

2. **PIPE-01 branches on shutil.which()** — the test is environment-aware: when system ffprobe is present (as in this environment, `/usr/bin/ffprobe`), the test asserts `_FFPROBE_PATH == system_ffprobe`. When absent (e.g., Railway without system ffmpeg), it falls back to checking `hasattr(pipeline, "_FFMPEG_DIR")`. Both branches fail against current code.

3. **PIPE-05 uses caplog at CRITICAL level** — `caplog.at_level(logging.CRITICAL, logger="api.main")` captures only critical logs from the lifespan, with `settings` patched to point to a controlled temp cookies file. `raise_server_exceptions=False` prevents TestClient from masking startup exceptions.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing dependency] imageio-ffmpeg not installed in test environment**
- **Found during:** Task 1 verification — `ModuleNotFoundError: No module named 'imageio_ffmpeg'` on first pytest run
- **Fix:** Installed `imageio-ffmpeg>=0.5.1` via `pip install imageio-ffmpeg --break-system-packages` (system Python without venv in this environment)
- **Files modified:** None (runtime dependency, already in requirements.txt)
- **Commit:** pre-commit environment setup (not part of task commit)

---

## Known Stubs

None — this plan produces only test files. No production code was modified. No data flows to UI.

---

## Threat Flags

None — test files only. No new network endpoints, auth paths, or file access patterns introduced.

---

## Self-Check: PASSED

- FOUND: `tests/test_pipeline_fixes.py`
- FOUND: commit `a9635b1` — test(08-01): add 8 RED failing tests for pipeline fixes
