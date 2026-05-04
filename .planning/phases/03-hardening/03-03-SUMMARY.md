---
phase: 03-hardening
plan: 03
subsystem: api
tags: [fastapi, slowapi, rate-limiting, redis, 429, retry-after]

# Dependency graph
requires:
  - phase: 03-hardening
    plan: 01
    provides: slowapi installed, stubs RED (test_rate_limit_returns_429, test_rate_limit_retry_after_header)
  - phase: 03-hardening
    plan: 02
    provides: rate_limit_per_minute em settings, RateLimitExceeded importado, handler 422
provides:
  - limiter = Limiter(key_func=get_ipaddr, storage_uri=settings.redis_url, headers_enabled=True)
  - _rate_limit_handler com Retry-After dinamico (D-04)
  - decorator @limiter.limit em POST /jobs
  - todos os 4 success criteria do ROADMAP Phase 3 atendidos
affects: [04-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Limiter(storage_uri=redis_url): Redis backend compartilhado entre workers Uvicorn"
    - "response: Response em submit_job: necessario para slowapi injetar X-RateLimit-* em 2xx"
    - "exc.limit.limit.get_expiry(): exc.limit e wrapper Limit do slowapi; .limit e RateLimitItem da lib limits"
    - "flush LIMITS:LIMITER* antes de cada teste: isola contadores de rate limit entre testes"

key-files:
  created: []
  modified:
    - api/main.py
    - tests/conftest.py

key-decisions:
  - "response: Response adicionado como parametro de submit_job — slowapi exige objeto Response nos kwargs para injetar headers X-RateLimit-* em respostas 2xx (sync_wrapper linha 771)"
  - "exc.limit.limit.get_expiry() em vez de exc.limit.get_expiry() — exc.limit e Limit (wrapper slowapi), .limit e RateLimitItem (lib limits) que tem o metodo get_expiry()"
  - "LIMITS:LIMITER* flushed no fixture api_client — contadores Redis persistem entre testes sem flush, causando 429 espurio na segunda suite"

requirements-completed: [UX-03, UX-04]

# Metrics
duration: 7min
completed: 2026-05-04
---

# Phase 3 Plan 03: Rate Limiting slowapi — Limiter, Handler 429, Decorator na Rota

**slowapi Limiter com Redis backend integrado em POST /jobs; handler 429 customizado com Retry-After dinamico; todos os 4 success criteria do ROADMAP Phase 3 atendidos**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-04T18:57:00Z
- **Completed:** 2026-05-04T19:04:09Z
- **Tasks:** 1
- **Files modified:** 2 (api/main.py, tests/conftest.py)

## Accomplishments

- `Limiter` inicializado em nivel de modulo em `api/main.py`:
  - `key_func=get_ipaddr` — le X-Forwarded-For; fallback para client.host
  - `storage_uri=settings.redis_url` — Redis compartilhado entre todos os workers Uvicorn
  - `headers_enabled=True` — injeta Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining automaticamente
- `app.state.limiter = limiter` registrado apos `app = FastAPI(...)`
- `_rate_limit_handler` registrado via `app.add_exception_handler(RateLimitExceeded, ...)`:
  - Retorna `{"error": "Too many requests. Try again in N seconds.", "error_type": "rate_limit_error"}`
  - Segundos calculados com `exc.limit.limit.get_expiry()` — valor real da janela de tempo (D-04)
  - `_inject_headers` adiciona header `Retry-After` no response 429
- `submit_job` atualizado:
  - `@app.post("/jobs", status_code=202)` ACIMA de `@limiter.limit(...)` — ordem critica para slowapi
  - Parametro `request: Request` adicionado como primeiro parametro (obrigatorio para slowapi)
  - Parametro body renomeado de `request` para `request_body` (evita colisao de nomes)
  - Parametro `response: Response` adicionado (necessario para injecao de headers X-RateLimit-* em 2xx)
- `app = FastAPI(...)` atualizado para `version="0.3.0"`
- `tests/conftest.py` atualizado: flush de chaves `LIMITS:LIMITER*` antes de cada teste

## Task Commits

1. **Task 1: slowapi integration** — `61b08c1` (feat)

**Plan metadata:** (este commit — docs)

## Test Results

| Teste | Estado antes | Estado depois |
|-------|-------------|---------------|
| test_rate_limit_returns_429 | RED | GREEN |
| test_rate_limit_retry_after_header | RED | GREEN |
| test_post_jobs_returns_job_id | GREEN | GREEN (sem regressao) |
| test_validation_error_format | GREEN | GREEN (sem regressao) |
| test_invalid_url_rejected (6 params) | GREEN | GREEN (sem regressao) |
| test_valid_youtube_url_accepted (4 params) | GREEN | GREEN (sem regressao) |

**Suite completa (not e2e):** 21 passed, 0 failed

## ROADMAP Phase 3 — Todos os 4 Success Criteria Atendidos

| SC | Criterio | Plano |
|----|----------|-------|
| SC-1 | URL invalida retorna 422 com mensagem humana (sem internals Pydantic) | Plan 02 |
| SC-2 | Video >15min rejeitado antes do download (check_duration) | Phase 1 |
| SC-3 | 4a requisicao do mesmo IP retorna 429 com mensagem humana | Plan 03 (este) |
| SC-4 | Sweeper limpa .part e .ytdl dentro de 20 minutos | Plan 02 |

## Files Created/Modified

- `api/main.py` — ~30 linhas inseridas:
  - Import `Limiter`, `get_ipaddr`, `Response` adicionados
  - `limiter = Limiter(...)` inserido apos `JOB_REGISTRY_KEY`
  - `app.state.limiter`, `_rate_limit_handler`, `app.add_exception_handler` inseridos apos `app = FastAPI(...)`
  - `version="0.3.0"` atualizado
  - `submit_job` atualizado: decorator `@limiter.limit`, parametros `request`, `request_body`, `response`
- `tests/conftest.py` — 5 linhas inseridas no fixture `api_client`:
  - Flush de chaves `LIMITS:LIMITER*` no Redis antes de cada teste

## Decisions Made

- `response: Response` adicionado como parametro de `submit_job` — slowapi `sync_wrapper` tenta `kwargs.get("response")` para injetar headers X-RateLimit-* em respostas 2xx; sem esse parametro, `_inject_headers(None, ...)` lanca `Exception`
- `exc.limit.limit.get_expiry()` (dois niveis de `.limit`) — `exc.limit` e o wrapper `Limit` do slowapi (wrappers.py), cujo atributo `.limit` e o `RateLimitItem` da lib `limits` que tem o metodo `get_expiry()`
- Flush `LIMITS:LIMITER*` no conftest — contadores de rate limit persistem no Redis entre execucoes; sem flush, o segundo teste que usa `api_client` recebe 429 no primeiro request

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] response: Response necessario em submit_job**
- **Found during:** Task 1, primeira execucao dos testes
- **Issue:** slowapi `sync_wrapper` chama `_inject_headers(kwargs.get("response"), ...)` para injetar headers X-RateLimit-* em respostas normais (nao-429). Sem `response: Response` na assinatura, `kwargs.get("response")` retorna `None` e `_inject_headers` lanca `Exception: parameter response must be an instance of starlette.responses.Response`
- **Fix:** Adicionado `response: Response` como terceiro parametro de `submit_job`; `Response` importado de `fastapi`
- **Files modified:** api/main.py
- **Commit:** 61b08c1

**2. [Rule 1 - Bug] exc.limit.get_expiry() -> exc.limit.limit.get_expiry()**
- **Found during:** Task 1, segunda execucao dos testes (apos fix #1)
- **Issue:** O plano especificou `exc.limit.get_expiry()` mas `exc.limit` e o wrapper `Limit` do slowapi que nao tem `get_expiry()`. O metodo existe em `RateLimitItem` (lib `limits`), acessivel via `exc.limit.limit`
- **Fix:** Corrigido para `exc.limit.limit.get_expiry()`; docstring do handler atualizada para explicar a hierarquia
- **Files modified:** api/main.py
- **Commit:** 61b08c1

**3. [Rule 2 - Missing critical functionality] Flush LIMITS:LIMITER* no fixture api_client**
- **Found during:** Task 1, terceira execucao dos testes (apos fixes #1 e #2)
- **Issue:** Contadores de rate limit no Redis persistem entre testes. Apos `test_rate_limit_returns_429` esgotar o limite (3 requests), `test_post_jobs_returns_job_id` recebia 429 no primeiro request, quebrando o teste de regressao
- **Fix:** Adicionado flush de chaves `LIMITS:LIMITER*` no Redis no inicio do fixture `api_client`
- **Files modified:** tests/conftest.py
- **Commit:** 61b08c1

## Threat Model Compliance

| Threat | Mitigation implementada |
|--------|------------------------|
| T-dos-flood: POST /jobs flood | slowapi 3/min por IP com Redis backend; confirmado por test_rate_limit_returns_429 |
| T-info-disclosure: _rate_limit_handler | Body 429 expoe apenas segundos ate reset — sem internals do slowapi nem limite exato |
| T-ip-spoof: get_ipaddr / X-Forwarded-For | Accept — documentado em STATE.md; mitigacao completa adiada para v1.1 |

## Next Phase Readiness

- **Phase 4 (Frontend):** Todos os 4 success criteria do Phase 3 atendidos. API pronta para exposicao ao frontend.
- Sem bloqueadores.

---

## Self-Check: PASSED

- `api/main.py` contem `limiter = Limiter` — FOUND
- `api/main.py` contem `storage_uri=settings.redis_url` — FOUND
- `api/main.py` contem `request: Request, request_body: JobRequest` — FOUND
- `api/main.py` contem `exc.limit.limit.get_expiry()` — FOUND
- `api/main.py` contem `_inject_headers` — FOUND
- `@app.post` linha 154 < `@limiter.limit` linha 155 — FOUND (ordem correta)
- `tests/conftest.py` contem flush `LIMITS:LIMITER*` — FOUND
- Commit `61b08c1` existe — FOUND
- `pytest tests/test_api.py -x -q -m "not e2e"` — 21 passed, 0 failed — PASSED

---
*Phase: 03-hardening*
*Completed: 2026-05-04*
