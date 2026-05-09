---
phase: 7
slug: infrastructure-security
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_security.py -x -q` |
| **Full suite command** | `pytest tests/ -v -m "not e2e and not integration"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_security.py -x -q`
- **After every plan wave:** Run `pytest tests/ -v -m "not e2e and not integration"`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | SEC-INFRA-01 | T-7-01 | `conftest.py` define `DEV_MODE=true` via `setdefault` | unit | `pytest tests/test_security.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 0 | SEC-INFRA-01 | T-7-01 | `test_redis_auth_required` stub RED | unit | `pytest tests/test_security.py::test_redis_auth_required -x` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 0 | SEC-INFRA-01 | T-7-01 | `test_redis_auth_bypass_dev_mode` stub RED | unit | `pytest tests/test_security.py::test_redis_auth_bypass_dev_mode -x` | ❌ W0 | ⬜ pending |
| 7-01-04 | 01 | 0 | SEC-INFRA-04 | T-7-04 | `test_hsts_header` stub RED | unit | `pytest tests/test_security.py::test_hsts_header -x` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | SEC-INFRA-01 | T-7-01 | `api/config.py` tem `dev_mode: bool` field | unit | `grep -n "dev_mode" api/config.py` | ✅ | ⬜ pending |
| 7-02-02 | 02 | 1 | SEC-INFRA-01 | T-7-01 | Lifespan levanta `RuntimeError` quando sem `@` no redis_url e `dev_mode=False` | unit | `pytest tests/test_security.py::test_redis_auth_required -x` | ❌ W0 | ⬜ pending |
| 7-02-03 | 02 | 1 | SEC-INFRA-01 | T-7-01 | DEV_MODE=true bypassa validação sem RuntimeError | unit | `pytest tests/test_security.py::test_redis_auth_bypass_dev_mode -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 1 | SEC-INFRA-04 | T-7-04 | `_security_headers` entrega `Strict-Transport-Security: max-age=31536000; includeSubDomains` | unit | `pytest tests/test_security.py::test_hsts_header -x` | ❌ W0 | ⬜ pending |
| 7-04-01 | 04 | 2 | SEC-INFRA-02 | — | `railway.toml` tem `startCommand` com `0.0.0.0` e `$PORT` | manual | `grep "0.0.0.0" railway.toml && grep "PORT" railway.toml` | ❌ novo | ⬜ pending |
| 7-04-02 | 04 | 2 | — | — | `SECURITY-CHECKLIST.md` tem seção SEC-INFRA-01..04 | manual | `grep "SEC-INFRA" .planning/SECURITY-CHECKLIST.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — adicionar `os.environ.setdefault("DEV_MODE", "true")` antes dos imports de `api.*`
- [ ] `tests/test_security.py::test_redis_auth_required` — stub RED para SEC-INFRA-01 (startup falha sem senha)
- [ ] `tests/test_security.py::test_redis_auth_bypass_dev_mode` — stub RED para SEC-INFRA-01 (DEV_MODE=true bypassa)
- [ ] `tests/test_security.py::test_hsts_header` — stub RED para SEC-INFRA-04 (header HSTS presente)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTTP→HTTPS 301 redirect | SEC-INFRA-03 | Railway faz automaticamente; não há código local para testar | `curl -s -o /dev/null -w "%{http_code}" http://<app>.up.railway.app/` → esperado `301` |
| Uvicorn isolado da internet | SEC-INFRA-02 | Garantido pela arquitetura Railway PaaS; sem código local | Verificar que `railway.toml` usa `0.0.0.0:$PORT` e que deploy Railway não expõe porta uvicorn diretamente |
| Celery worker conectado ao Redis | D-15 | Requer deploy Railway ativo | No Railway dashboard, verificar que o serviço Celery está em estado "Active" e processando tarefas |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
