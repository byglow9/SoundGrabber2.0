---
phase: 3
slug: hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (existente) |
| **Quick run command** | `pytest tests/test_api.py -x -q` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api.py -x -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | UX-03, UX-04 | — | Test stubs e slowapi instalado | setup | `pytest tests/test_api.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 3-02-01 | 02 | 1 | UX-03 | T-info-disclosure | 422 body normalizado sem stack trace | unit | `pytest tests/test_api.py::test_validation_error_format -x` | ❌ Wave 0 | ⬜ pending |
| 3-03-01 | 03 | 2 | UX-04 | T-dos-flood | 4ª req em 60s retorna 429 | unit | `pytest tests/test_api.py::test_rate_limit_returns_429 -x` | ❌ Wave 0 | ⬜ pending |
| 3-03-02 | 03 | 2 | UX-04 | T-dos-flood | Retry-After presente no 429 | unit | `pytest tests/test_api.py::test_rate_limit_retry_after_header -x` | ❌ Wave 0 | ⬜ pending |
| 3-02-02 | 02 | 1 | SC-4 | T-dos-disk | Sweeper deleta .part e .ytdl expirados | unit | `pytest tests/test_api.py::test_sweeper_deletes_partial_files -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_api.py::test_validation_error_format` — verifica body `{error, error_type}` na resposta 422
- [ ] `tests/test_api.py::test_rate_limit_returns_429` — verifica que 4ª requisição em 60s retorna 429
- [ ] `tests/test_api.py::test_rate_limit_retry_after_header` — verifica header `Retry-After` presente no 429
- [ ] `tests/test_api.py::test_sweeper_deletes_partial_files` — verifica deleção de `.part` e `.ytdl` expirados
- [ ] `requirements.txt` — adicionar `slowapi==0.1.9`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rate limit com múltiplos workers Celery (Redis backend) | UX-04 | Requer ambiente multi-worker; in-memory não replica | `celery -A api.tasks worker --concurrency=2` + submeter 4 jobs rápidos |
| IP real via X-Forwarded-For atrás de nginx | UX-04 | Requer proxy configurado | Verificar `get_ipaddr` lê header em staging/prod |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
