---
phase: 07-infrastructure-security
plan: 02
subsystem: api-security
tags: [security, infrastructure, fastapi, redis, hsts]
dependency_graph:
  requires:
    - 07-01 (RED stubs para SEC-INFRA-01 e SEC-INFRA-04 + DEV_MODE em conftest.py)
  provides:
    - Settings.dev_mode field (lido de DEV_MODE env var)
    - _check_redis_auth(redis_url, dev_mode) em api/main.py
    - HSTS header em _security_headers middleware
  affects:
    - api/config.py
    - api/main.py
tech_stack:
  added: []
  patterns:
    - Fail-early at startup: RuntimeError se Redis sem senha em producao
    - DEV_MODE bypass: env var bool com default seguro (false = producao)
    - HSTS via middleware global: single point of maintenance para security headers
key_files:
  created: []
  modified:
    - api/config.py
    - api/main.py
decisions:
  - "Settings.dev_mode com default_factory (nao default) para leitura runtime de env (consistente com WR-02)"
  - ".lower() == 'true' em vez de bool cast: apenas 'true' (case-insensitive) ativa bypass, default seguro"
  - "HSTS integrado em _security_headers existente em vez de middleware separado: single point of maintenance"
  - "RuntimeError em vez de logger.warning: fail-early garante que producao sem senha nao passa do lifespan"
metrics:
  duration: "2 minutes"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 7 Plan 02: Infrastructure Security — Redis Auth Enforcement + HSTS Summary

Implementacao GREEN dos 4 stubs RED do Plan 01: `_check_redis_auth` com DEV_MODE bypass em `api/main.py`, campo `dev_mode` em `Settings` (api/config.py), e header `Strict-Transport-Security` injetado em todas as respostas via `_security_headers` middleware.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar campo dev_mode ao Settings em api/config.py | 36ed82b | api/config.py |
| 2 | Adicionar _check_redis_auth e HSTS em api/main.py | bd312a3 | api/main.py |

---

## What Was Built

### Task 1 — Campo `dev_mode` em `api/config.py`

Adicionado como ultimo campo do dataclass `Settings`:

```python
dev_mode: bool = field(default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true")
```

- Default `"false"` (string) garante que ausencia da variavel em producao = `False` = validacao ativa
- `.lower() == "true"` normaliza case; apenas `"true"` (qualquer caixa) ativa bypass
- `default_factory` garante leitura no momento de instanciacao (WR-02), nao no import time

### Task 2 — `_check_redis_auth` e HSTS em `api/main.py`

**Mudanca 1 — funcao `_check_redis_auth`** (inserida entre `_run_sweeper_loop` e `lifespan`):

```python
def _check_redis_auth(redis_url: str, dev_mode: bool) -> None:
    if dev_mode:
        return
    if "@" not in redis_url:
        raise RuntimeError(
            "REDIS_URL does not contain a password. "
            "Set a Redis URL with credentials: redis://:password@host:port/db. "
            "For local development only, set DEV_MODE=true."
        )
```

**Mudanca 2 — lifespan** substituiu `logger.warning` por `_check_redis_auth(settings.redis_url, settings.dev_mode)`, garantindo fail-early no startup.

**Mudanca 3 — `_security_headers`** recebeu linha extra antes do `return response`:

```python
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

---

## Verification Results

```
# 4 stubs RED viraram GREEN:
pytest tests/test_security.py::test_redis_auth_required
pytest tests/test_security.py::test_redis_auth_bypass_dev_mode
pytest tests/test_security.py::test_redis_auth_passes_with_password
pytest tests/test_security.py::test_hsts_header
4 passed in 1.80s

# Suite completa de seguranca:
pytest tests/test_security.py -q
16 passed in 2.04s
```

---

## Deviations from Plan

### Pre-existing Failure (Out of Scope)

`tests/test_frontend.py::test_html_required_ids_present` falha com `AssertionError: IDs ausentes no HTML: ['download-area']`. Verificado que esta falha existia ANTES das mudancas deste plano (confirmado com `git stash` + re-run). Nenhuma relacao com SEC-INFRA-01 ou SEC-INFRA-04. Registrado em deferred-items para resolucao futura.

Nenhuma outra desvio — plano executado conforme especificado.

---

## Known Stubs

Nenhum. Todas as implementacoes estao completas e funcionais.

---

## Threat Flags

Nenhuma nova superficie de ataque introduzida. As mudancas fecham ameacas pre-existentes T-7-01 e T-7-04 conforme o threat register do plano.

---

## Self-Check

### Files exist:
- api/config.py: FOUND
- api/main.py: FOUND

### Commits exist:
- 36ed82b (Task 1): FOUND
- bd312a3 (Task 2): FOUND

## Self-Check: PASSED
