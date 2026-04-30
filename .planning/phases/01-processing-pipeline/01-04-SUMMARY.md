---
phase: 01-processing-pipeline
plan: 04
subsystem: cli-integration
tags: [integration, cli, e2e, pipeline, python, readme]
status: partial — paused at checkpoint:human-verify (Task 3)

dependency_graph:
  requires: [01-01, 01-02, 01-03]
  provides:
    - pipeline.py __main__ CLI entry point (D-04)
    - JSON envelope contract: usage_error, config_error, validation_error, download_error, internal_error
    - 3 wired e2e tests driving subprocess CLI (D-07)
    - README.md with full user setup documentation
  affects:
    - Phase 2: import check_duration, download_audio, analyze_audio from pipeline
    - Phase 2: CLI contract is the reference for FastAPI response shapes

tech_stack:
  added: []
  patterns:
    - if __name__ == '__main__' guard for importable CLI scripts
    - JSON error envelopes to stdout (not stderr) for machine-readable error handling
    - subprocess.run with [sys.executable, 'pipeline.py', url] (no shell=True) for e2e tests
    - _e2e_skip_if_no_creds() pattern for credential-gated tests

key_files:
  created:
    - README.md
  modified:
    - pipeline.py
    - tests/test_pipeline.py

decisions:
  - "All error envelopes go to stdout (not stderr): machine consumers don't split stdout/stderr"
  - "po_token warning goes to stderr: does not pollute JSON output on stdout"
  - "FileNotFoundError mapped to download_error (not internal_error): it is a download outcome"
  - "info['duration'] used to override ffprobe's duration_sec: YouTube's reported duration is the user-facing value"
  - "_run_pipeline_e2e as shared helper: 3 e2e tests share assertion logic, reducing duplication"

metrics:
  duration: ~3 min (Tasks 1+2 only — Task 3 is human checkpoint)
  started: 2026-04-30T03:30:21Z
  tasks_completed: 2
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 01 Plan 04: CLI Entry Point + E2E Tests + README Summary

**CLI contract wired: `python3 pipeline.py URL` emits D-05 JSON success or typed error envelopes; 3 e2e tests drive the subprocess CLI against the D-07 reference URLs; README.md documents the full user setup path.**

## Status

**Partial — paused at Task 3 (checkpoint:human-verify).**

Tasks 1 and 2 are complete and committed. Task 3 is the manual e2e validation on the production VPS — a human checkpoint that cannot be automated.

## Completed Tasks

### Task 1: `if __name__ == '__main__'` CLI entry point

Added the CLI entry point block to `pipeline.py`. The block:

- Reads `YTDLP_COOKIES_FILE` and `YTDLP_PO_TOKEN` from `os.environ`.
- Performs up-front config validation: emits `usage_error` (no arg), `config_error` (missing env var or absent cookies file).
- Warns to stderr if `YTDLP_PO_TOKEN` is empty — warning does NOT appear in stdout JSON.
- Runs the pipeline inside a `try/except` chain mapping `ValueError` -> `validation_error`, `RuntimeError` -> `download_error`, `FileNotFoundError` -> `download_error`, `Exception` -> `internal_error`.
- Exit code 0 on success, 1 on any error. Stdout is always valid JSON.

Verified:
- `python3 pipeline.py` (no args) -> `{"error": "...", "type": "usage_error"}` exit 1
- `python3 pipeline.py URL` with unset `YTDLP_COOKIES_FILE` -> `{"error": "...", "type": "config_error"}` exit 1
- `python3 pipeline.py URL` with `YTDLP_COOKIES_FILE=/nonexistent` -> `config_error` with "does not exist" exit 1
- `python3 -c "import pipeline; ..."` still works (import not polluted by `__main__` block)
- All 9 non-e2e tests pass; 1 intentional skip; 3 e2e deselected

**Commit:** `49eaf5b`

### Task 2: Wire 3 e2e tests + write README.md

Replaced the 3 `pytest.skip("Wired in Plan 04...")` stubs in `tests/test_pipeline.py` with real subprocess-driven implementations. Added `_run_pipeline_e2e()` helper that:

- Calls `subprocess.run([sys.executable, "pipeline.py", url], ...)` (no `shell=True`).
- Asserts exit code 0.
- Parses stdout as JSON.
- Asserts all 7 D-05 fields present: `bpm`, `bpm_half`, `bpm_double`, `key`, `camelot`, `duration_sec`, `wav_path`.
- Asserts `bpm` in range 30..300.
- Asserts `duration_sec <= expected_max_duration`.
- Asserts `wav_path` exists on disk with size > 1024 bytes.

`test_e2e_trap` additionally verifies D-06: `abs(bpm_half - bpm/2) < 0.2` and `abs(bpm_double - bpm*2) < 0.2`.

All 3 e2e tests call `_e2e_skip_if_no_creds()` — they skip cleanly without credentials.

`README.md` created at repo root (158 lines) with:
- Full user setup: cookies.txt generation + PO Token acquisition.
- Install instructions (system + Python deps).
- Usage example with output shapes for all 4 error types.
- File layout table.
- Known limitations by phase.
- ASCII architecture diagram.

**Commit:** `f2a7e24`

## Task 3: Pending (checkpoint:human-verify)

Task 3 is the manual e2e validation on the production VPS. See checkpoint details below for exact steps.

## Deviations from Plan

None — both tasks executed exactly as planned. The CLI block matches the plan's template verbatim. The e2e helper and test bodies match the plan's specified implementations.

## Threat Mitigations Applied

| Threat | Mitigation Verified |
|--------|---------------------|
| T-01-04-01: Stack traceback leaks to stdout | All exceptions caught in `__main__`; `Exception` catch-all converts to `internal_error` envelope; no traceback ever reaches stdout |
| T-01-04-02: Non-YouTube URL via argv | yt-dlp internally rejects; `check_duration` raises `ValueError` -> `validation_error` envelope |
| T-01-04-03: Shell metacharacters in URL | URL is Python string passed to yt_dlp (no shell); e2e tests use list form subprocess (no `shell=True`) |
| T-01-04-04: cookies.txt exfiltration via README | README explicitly says `chmod 600 cookies.txt`; confirms `.gitignore` exclusion |

## Known Stubs

None — all stubs from Plans 01-03 are resolved. The e2e tests are real implementations that require credentials to run (they skip cleanly without them, which is correct behavior, not a stub).

## Self-Check: PASSED (Tasks 1+2)

| Item | Status |
|------|--------|
| pipeline.py contains `if __name__ == "__main__":` | FOUND |
| pipeline.py reads YTDLP_COOKIES_FILE and YTDLP_PO_TOKEN | FOUND |
| usage_error, config_error, validation_error, download_error literals in pipeline.py | FOUND |
| README.md exists at repo root (158 lines, >= 80) | FOUND |
| README.md contains YTDLP_COOKIES_FILE, YTDLP_PO_TOKEN, pipeline.py, validation_error, download_error, Get cookies.txt LOCALLY | FOUND |
| tests/test_pipeline.py contains _run_pipeline_e2e (4 occurrences: def + 3 calls) | FOUND |
| tests/test_pipeline.py no longer contains "Wired in Plan 04" | CONFIRMED (0 matches) |
| 13 tests collected by pytest | FOUND |
| 9 pass + 1 intentional skip (not e2e) | FOUND |
| commit 49eaf5b exists | FOUND |
| commit f2a7e24 exists | FOUND |
