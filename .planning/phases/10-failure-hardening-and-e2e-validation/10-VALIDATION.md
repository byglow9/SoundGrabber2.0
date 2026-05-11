---
phase: 10
slug: failure-hardening-and-e2e-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-11
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` / `pyproject.toml` |
| **Quick run command** | `pytest tests/test_pipeline_fixes.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline_fixes.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | PIPE-06 | — | bgutil probe raises BgutilUnavailable before yt-dlp | unit (RED stub) | `pytest tests/test_pipeline_fixes.py::test_bgutil_probe_unavailable -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 0 | PIPE-06 | — | probe does not call yt-dlp when bgutil unreachable | unit (RED stub) | `pytest tests/test_pipeline_fixes.py::test_bgutil_probe_no_ytdlp_on_failure -x -q` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 0 | PIPE-06 | — | tasks.py sets error_type=bgutil_unavailable | unit (RED stub) | `pytest tests/test_pipeline_fixes.py::test_bgutil_error_type -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | PIPE-06 | — | BgutilUnavailable raised with correct message | unit (GREEN) | `pytest tests/test_pipeline_fixes.py -x -q` | ✅ | ⬜ pending |
| 10-02-02 | 02 | 1 | PIPE-06 | — | tasks.py catches BgutilUnavailable → JobFailure(error_type="bgutil_unavailable") | unit (GREEN) | `pytest tests/test_pipeline_fixes.py -x -q` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 2 | PIPE-07 | — | start-all.sh starts both Uvicorn and Celery | manual | `bash -n start-all.sh` (syntax check) + Railway deploy checkpoint | ✅ | ⬜ pending |
| 10-03-02 | 03 | 3 | PIPE-07 | — | 3 beat URLs reach status=done with WAV, BPM, key | manual (E2E) | Human checkpoint — curl smoke test | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_fixes.py` — RED stubs for PIPE-06 (test_bgutil_probe_unavailable, test_bgutil_probe_no_ytdlp_on_failure, test_bgutil_error_type)
- [ ] Existing `conftest.py` — check DEV_MODE=true fixture covers bgutil tests

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3 beat URLs complete E2E on Railway (status=done, WAV, BPM, key) | PIPE-07 | Requires live Railway deployment with real YouTube URLs | Operator submits 3 beats via POST /jobs, polls to done, downloads WAV, confirms BPM plausible and key in standard notation — document in 10-SMOKE-TEST.md |
| bgutil GET / probe works against live Railway bgutil service | PIPE-06 | Requires live bgutil container on Railway private network | Operator runs `curl http://bgutil.railway.internal:4416/` from Railway shell and confirms response |
| start-all.sh SIGTERM propagates correctly | PIPE-07 | Railway shutdown behavior cannot be fully unit-tested | Operator deploys single-service container, stops service via Railway dashboard, confirms graceful shutdown in logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
