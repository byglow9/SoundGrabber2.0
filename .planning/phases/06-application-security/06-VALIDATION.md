---
phase: 6
slug: application-security
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | pytest.ini (raiz do projeto) |
| **Quick run command** | `pytest tests/test_security.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_security.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | SEC-FILE-01, SEC-FILE-02, SEC-API-01/02/03, SEC-TEST-01..06 | T-6-01..08 | Stubs RED | unit | `pytest tests/test_security.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | SEC-FILE-01 | T-6-01 | WAV criado com 0o600 | unit | `pytest tests/test_security.py::test_wav_file_permissions -x` | ✅ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | SEC-FILE-02 | T-6-02 | start.sh com 750 | unit | `pytest tests/test_security.py::test_startsh_permissions -x` | ✅ W0 | ⬜ pending |
| 06-02-03 | 02 | 1 | SEC-API-01 | T-6-03 | GET /jobs/{id} 429 após 60/min | unit | `pytest tests/test_security.py::test_rate_limit_get_jobs -x` | ✅ W0 | ⬜ pending |
| 06-02-04 | 02 | 1 | SEC-API-02 | T-6-04 | GET /files/{id} 429 após 10/min | unit | `pytest tests/test_security.py::test_rate_limit_get_files -x` | ✅ W0 | ⬜ pending |
| 06-02-05 | 02 | 1 | SEC-API-03 | — | GET /health 200/503 | unit | `pytest tests/test_security.py::test_health_redis_ok tests/test_security.py::test_health_redis_down -x` | ✅ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | SEC-TEST-01 | — | 413 body > 4KB | unit | `pytest tests/test_security.py::test_body_size_limit -x` | ✅ W0 | ⬜ pending |
| 06-03-02 | 03 | 2 | SEC-TEST-02 | — | 4 security headers presentes | unit | `pytest tests/test_security.py::test_security_headers -x` | ✅ W0 | ⬜ pending |
| 06-03-03 | 03 | 2 | SEC-TEST-03 | T-6-06 | /docs /redoc /openapi.json → 404 | unit | `pytest tests/test_security.py::test_docs_routes_disabled -x` | ✅ W0 | ⬜ pending |
| 06-03-04 | 03 | 2 | SEC-TEST-04 | T-6-08 | Queue depth → 503 | unit | `pytest tests/test_security.py::test_queue_depth_limit -x` | ✅ W0 | ⬜ pending |
| 06-03-05 | 03 | 2 | SEC-TEST-05 | T-6-03..04 | Rate limit GET /jobs e GET /files | unit | (coberto por SEC-API-01/02) | ✅ W0 | ⬜ pending |
| 06-03-06 | 03 | 2 | SEC-TEST-06 | — | pip-audit documentado em README | manual | `grep -q "pip-audit" README.md` | — | ⬜ pending |
| 06-03-07 | 03 | 2 | SEC-POLICY-01 | — | Security Gate em CLAUDE.md | manual | `grep -q "Security Gate" CLAUDE.md` | — | ⬜ pending |
| 06-03-08 | 03 | 2 | SEC-POLICY-02 | — | SECURITY-CHECKLIST.md existe | manual | `test -f .planning/SECURITY-CHECKLIST.md` | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_security.py` — stubs RED para SEC-FILE-01/02, SEC-API-01/02/03, SEC-TEST-01..06

*Nota: `tests/conftest.py` e `api_client` fixture já existem com flush de `LIMITS:LIMITER*` — nenhuma modificação necessária.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| pip-audit documentado em README | SEC-TEST-06 | Verificação de conteúdo de documento | `grep "pip-audit" README.md` — verificar presença do comando |
| Security Gate em CLAUDE.md | SEC-POLICY-01 | Verificação de conteúdo de documento | `grep "Security Gate" CLAUDE.md` — verificar seção presente |
| SECURITY-CHECKLIST.md criado | SEC-POLICY-02 | Criação de arquivo de policy | `test -f .planning/SECURITY-CHECKLIST.md && cat .planning/SECURITY-CHECKLIST.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
