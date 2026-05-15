---
phase: 14-pipeline-e2e-on-notebook
plan: "01"
subsystem: tests
tags:
  - tdd
  - deploy
  - cookies
  - wave-0
dependency_graph:
  requires: []
  provides:
    - tests/test_deploy_sh.py (8 RED stubs)
  affects:
    - Plans 02 and 03 (GREEN targets defined)
tech_stack:
  added: []
  patterns:
    - file-content testing with yaml.safe_load
    - pytest stdlib-only stubs (no integration markers)
key_files:
  created:
    - tests/test_deploy_sh.py
  modified: []
decisions:
  - Tests 3-4 (sg_tmp preservation) check for BOTH volumes simultaneously so they are RED until Plan 02 adds the bind mount, ensuring sg_tmp was not removed when bind mount was added
  - No @pytest.mark.integration markers used — file-content tests run in the quick suite
metrics:
  duration: "~10 minutes"
  completed: "2026-05-15"
---

# Phase 14 Plan 01: TDD RED Stubs for deploy.sh Security Gate — Summary

Wave 0 stubs locking AUTH-04 (bind mount :ro, .env.example values) and AUTH-05 (deploy.sh: set -e, chmod 750, git pull, docker compose up, no eval) as 8 RED tests that Plans 02 and 03 must turn GREEN.

## What Was Built

Created `tests/test_deploy_sh.py` with 8 RED stubs. All 8 tests fail against the current repo state with concrete `AssertionError` messages. No `ImportError`, `SyntaxError`, or `FileNotFoundError` from fixtures — only assertion failures pointing exactly at what needs to change.

**File created:** `tests/test_deploy_sh.py` (153 lines)

## pytest Output (8 failed — RED gate confirmed)

```
FAILED tests/test_deploy_sh.py::test_bind_mount_in_compose_api - AssertionError: Expected bind mount '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in api service, got ['sg_tmp:/tmp']
FAILED tests/test_deploy_sh.py::test_bind_mount_in_compose_worker - AssertionError: Expected bind mount '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in worker service, got ['sg_tmp:/tmp']
FAILED tests/test_deploy_sh.py::test_compose_preserves_sg_tmp_in_api - AssertionError: Expected BOTH 'sg_tmp:/tmp' AND '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in api service (Pitfall 1: bind mount não deve substituir sg_tmp), got ['sg_tmp:/tmp']
FAILED tests/test_deploy_sh.py::test_compose_preserves_sg_tmp_in_worker - AssertionError: Expected BOTH 'sg_tmp:/tmp' AND '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in worker service (Pitfall 1: bind mount não deve substituir sg_tmp), got ['sg_tmp:/tmp']
FAILED tests/test_deploy_sh.py::test_env_example_ytdlp_cache_dir - AssertionError: Expected 'YTDLP_CACHE_DIR=/data/yt-dlp-cache' in .env.example, but found: ['YTDLP_CACHE_DIR=']
FAILED tests/test_deploy_sh.py::test_env_example_bgutil_empty - AssertionError: Expected 'BGUTIL_BASE_URL=' with empty value in .env.example, got 'BGUTIL_BASE_URL=http://bgutil:4416' (value after '=' is 'http://bgutil:4416')
FAILED tests/test_deploy_sh.py::test_deploy_sh_exists_and_has_set_e - AssertionError: scripts/deploy.sh não existe
FAILED tests/test_deploy_sh.py::test_deploy_sh_security_gate_and_commands - AssertionError: scripts/deploy.sh não existe
8 failed in 0.10s
```

## Test → Decision Mapping

| Test | Decision | Requirement | Failure Reason |
|------|----------|-------------|----------------|
| `test_bind_mount_in_compose_api` | D-01/D-04 | AUTH-04 | Bind mount `/data/yt-dlp-cache:ro` ausente em `api` |
| `test_bind_mount_in_compose_worker` | D-01/D-05 | AUTH-04 | Bind mount `/data/yt-dlp-cache:ro` ausente em `worker` |
| `test_compose_preserves_sg_tmp_in_api` | D-06/Pitfall-1 | AUTH-04 | Bind mount ausente → condição AND falha |
| `test_compose_preserves_sg_tmp_in_worker` | D-07/Pitfall-1 | AUTH-04 | Bind mount ausente → condição AND falha |
| `test_env_example_ytdlp_cache_dir` | D-02 | AUTH-04 | `.env.example` tem `YTDLP_CACHE_DIR=` (vazio) |
| `test_env_example_bgutil_empty` | D-09 | AUTH-04 | `.env.example` tem `BGUTIL_BASE_URL=http://bgutil:4416` (não vazio) |
| `test_deploy_sh_exists_and_has_set_e` | AUTH-05/Security Gate | AUTH-05 | `scripts/deploy.sh` não existe |
| `test_deploy_sh_security_gate_and_commands` | AUTH-05/Security Gate | AUTH-05 | `scripts/deploy.sh` não existe |

## Deviations from Plan

**1. [Rule 1 - Design] Tests 3-4 assertion logic adjusted for correct RED state**

- **Found during:** Task 1 verification
- **Issue:** Tests `test_compose_preserves_sg_tmp_in_api` and `test_compose_preserves_sg_tmp_in_worker` initially checked only that `sg_tmp:/tmp` exists (which it already does), making them GREEN unexpectedly. The plan requires all 8 tests to be RED.
- **Fix:** Changed assertion to require BOTH `sg_tmp:/tmp` AND the bind mount simultaneously. This makes them RED now (bind mount missing) and GREEN after Plan 02 adds both — which is exactly the Pitfall 1 guard (verify bind mount did not replace sg_tmp).
- **Files modified:** `tests/test_deploy_sh.py`
- **Commit:** 7e46423

## TDD Gate Compliance

- RED gate commit: `7e46423` (test(14-01): add 8 RED stubs...)
- GREEN gate: Pending — Plan 02 (compose + .env.example) and Plan 03 (deploy.sh) own the GREEN phase

## Self-Check: PASSED

- `tests/test_deploy_sh.py` exists: FOUND
- Task commit `7e46423`: FOUND
- 8 tests collected: CONFIRMED
- 8 failed (RED): CONFIRMED
- Full suite: 110 tests collected (was 102)
