---
phase: 2
slug: api-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (raiz do projeto) |
| **Quick run command** | `pytest tests/test_api.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds (unit), ~60 seconds (integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q -m "not e2e"`
- **Before `/gsd-verify-work`:** Full suite must be green (including `-m integration`)
- **Max feedback latency:** 15 seconds (unit), 60 seconds (integration)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | CORE-01 | — | N/A | unit | `pytest tests/test_api.py::test_post_jobs_returns_job_id -x` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 0 | CORE-02 | — | URL não-YouTube rejeitada 422 | unit | `pytest tests/test_api.py::test_invalid_url_rejected -x` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 0 | CORE-02 | — | URL YouTube válida aceita | unit | `pytest tests/test_api.py::test_valid_youtube_url_accepted -x` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 1 | CORE-06 | — | WAV streaming sem carregar em memória | integration | `pytest tests/test_api.py::test_file_streaming -x -m integration` | ❌ W0 | ⬜ pending |
| 2-01-05 | 01 | 2 | SC-4 | — | 3 jobs concorrentes completam sem travar | e2e | `pytest tests/test_api.py::test_concurrent_jobs -x -m e2e` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api.py` — stubs para CORE-01, CORE-02, CORE-06 (unit + integration + e2e)
- [ ] `api/__init__.py` — package vazio
- [ ] `api/config.py` — settings via env vars
- [ ] `api/tasks.py` — Celery app + task process_job (stub)
- [ ] `api/main.py` — FastAPI app + 3 rotas (stub)
- [ ] Redis instalado: `sudo apt install redis-server`

*Infraestrutura existente reutilizável sem modificação: `pytest.ini`, `tests/conftest.py`, `tests/fixtures/sample.wav`*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3 jobs concorrentes via curl real | SC-4 | Requer Redis + worker real rodando | `curl -X POST http://localhost:8000/jobs -d '{"url":"..."}' &` (3×), monitorar GET /jobs/{id} |
| WAV stream auditável no browser/curl | CORE-06 | Verificação perceptual do download | `curl -o test.wav http://localhost:8000/files/{id}` e abrir no audacity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
