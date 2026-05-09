---
phase: 07-infrastructure-security
plan: 01
subsystem: test-infrastructure
tags: [security, tdd, redis-auth, hsts, infrastructure]
dependency_graph:
  requires:
    - 06-application-security/06-03 (tests/test_security.py Phase 6 suite — base existente)
  provides:
    - RED stubs para SEC-INFRA-01 e SEC-INFRA-04 (Plan 02 implementa o GREEN)
    - DEV_MODE=true em conftest.py (precondição para Plan 02 não quebrar suite)
  affects:
    - tests/conftest.py
    - tests/test_security.py
tech_stack:
  added: []
  patterns:
    - Nyquist TDD protocol: stubs RED criados antes da implementacao
    - os.environ.setdefault para preservar override manual do dev
key_files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_security.py
decisions:
  - "Testar _check_redis_auth como funcao auxiliar (nao o lifespan inteiro) — evita overhead de sweeper thread em testes unitarios"
  - "setdefault em vez de atribuicao direta para DEV_MODE — preserva override manual do desenvolvedor"
  - "4 stubs ao inves de 3 — test_redis_auth_passes_with_password cobre o caminho positivo (URL com @)"
metrics:
  duration: "8 minutes"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 7 Plan 01: Infrastructure Security — TDD RED Stubs Summary

Wave 0 TDD setup: DEV_MODE bypass em conftest.py + 4 stubs RED para SEC-INFRA-01 (Redis auth enforcement via `_check_redis_auth`) e SEC-INFRA-04 (HSTS header), garantindo que Plan 02 pode implementar sem quebrar a suite Phase 6 existente.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar DEV_MODE=true em conftest.py | 3c7ee47 | tests/conftest.py |
| 2 | Adicionar 4 stubs RED em test_security.py | abb3159 | tests/test_security.py |

---

## What Was Built

### Task 1 — DEV_MODE=true em conftest.py

Adicionada linha `os.environ.setdefault("DEV_MODE", "true")` na linha 14 de `tests/conftest.py`, imediatamente após o `REDIS_URL` setdefault existente e antes de qualquer import de `api.*`.

**Por que é necessário:** Plan 02 vai substituir o `logger.warning` do lifespan por `raise RuntimeError` quando a URL Redis não tem senha. Sem esse bypass, todos os testes que usam `api_client` fixture quebrariam simultaneamente ao aplicar Plan 02, porque a URL de teste (`redis://localhost:6380/0`) não tem senha.

### Task 2 — 4 stubs RED em test_security.py

Adicionados ao final de `tests/test_security.py`:

1. **`test_redis_auth_required`** — Espera `RuntimeError` com mensagens "REDIS_URL" e "password" quando URL não tem `@` e `dev_mode=False`. Estado RED: `ImportError: cannot import name '_check_redis_auth'`.

2. **`test_redis_auth_bypass_dev_mode`** — Espera que `dev_mode=True` bypasse o check sem levantar. Estado RED: mesmo `ImportError`.

3. **`test_redis_auth_passes_with_password`** — Caminho positivo: URL com formato `redis://default:senha@host:6379` não deve levantar. Estado RED: mesmo `ImportError`.

4. **`test_hsts_header`** — GET / deve retornar header `Strict-Transport-Security: max-age=31536000; includeSubDomains`. Estado RED: `AssertionError: Header Strict-Transport-Security ausente`.

---

## Verification Results

```
# RED state confirmado:
FAILED tests/test_security.py::test_redis_auth_required - ImportError: cannot import name '_check_redis_auth'
FAILED tests/test_security.py::test_hsts_header - AssertionError: Header Strict-Transport-Security ausente

# Suite Phase 6 verde:
12 passed, 4 deselected in 2.16s
```

---

## Deviations from Plan

None — plano executado exatamente como escrito.

---

## Known Stubs

Os 4 testes adicionados são stubs intencionais em estado RED. Eles serão implementados (GREEN) em Plan 02 via:
- `_check_redis_auth(redis_url, dev_mode)` em `api/main.py`
- `Strict-Transport-Security` header em `_security_headers` middleware

---

## Self-Check

### Files exist:
- tests/conftest.py: FOUND
- tests/test_security.py: FOUND

### Commits exist:
- 3c7ee47 (Task 1): FOUND
- abb3159 (Task 2): FOUND

## Self-Check: PASSED
