---
phase: 03-hardening
plan: 02
subsystem: api
tags: [fastapi, validation, sweeper, exception-handler, pydantic-v2, yt-dlp]

# Dependency graph
requires:
  - phase: 03-hardening
    plan: 01
    provides: slowapi installed, 4 RED stubs (test_validation_error_format, test_sweeper_deletes_partial_files)
provides:
  - _validation_exception_handler registrado em api/main.py (D-07)
  - sweep_expired_wavs estendido para sg_*.part e sg_*.ytdl (D-05/D-06)
  - rate_limit_per_minute em api/config.py (configuravel via RATE_LIMIT_PER_MINUTE)
affects: [03-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "exception_handler(RequestValidationError): converte 422 Pydantic para formato canonico sem internals"
    - "removeprefix('Value error, '): remove prefixo automatico do Pydantic v2 em field_validator"
    - "sweep multi-pattern: loop sobre tupla de globs em vez de glob unico"

key-files:
  created: []
  modified:
    - api/config.py
    - api/main.py

key-decisions:
  - "RateLimitExceeded importado neste plano mesmo sem uso imediato — necessario para que o handler 429 do Plan 03 nao precise modificar a linha de imports novamente"
  - "Variavel interna renomeada de wav para f no sweeper — evita nome enganoso apos adicao de .part/.ytdl"
  - "Loop sobre tupla de 3 strings (nao lista) para sweep — consistente com estilo funcional puro existente"

requirements-completed: [UX-03, UX-04]

# Metrics
duration: 2min
completed: 2026-05-04
---

# Phase 3 Plan 02: Handler 422 Normalizado + Sweeper Estendido

**Handler 422 customizado elimina internals Pydantic v2 dos erros de URL; sweeper estendido para sg_*.part e sg_*.ytdl; rate_limit_per_minute configuravel via env**

## Performance

- **Duration:** 2 min (~93s)
- **Started:** 2026-05-04T18:57:02Z
- **Completed:** 2026-05-04T18:58:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `rate_limit_per_minute: int` adicionado em `api/config.py` com default 3 e override via `RATE_LIMIT_PER_MINUTE`
- `_validation_exception_handler` registrado em `api/main.py` via `@app.exception_handler(RequestValidationError)`:
  - Extrai `errors[0]["msg"]` e remove prefixo `"Value error, "` com `removeprefix()`
  - Retorna `JSONResponse(422, {"error": msg, "error_type": "validation_error"})`
  - Elimina chave `detail` do body (formato canonico do projeto)
- `sweep_expired_wavs` estendido com loop `for pattern in ("sg_*.wav", "sg_*.part", "sg_*.ytdl")`:
  - Limpa arquivos parciais de yt-dlp deixados por workers SIGKILL'd (D-05/D-06)
  - Assinatura e logica de TTL inalteradas; apenas variavel interna renomeada de `wav` para `f`
- Novos imports em `api/main.py`: `Request`, `RequestValidationError`, `JSONResponse`, `RateLimitExceeded`

## Task Commits

1. **Task 1: rate_limit_per_minute em api/config.py** — `bc4ce74` (feat)
2. **Task 2: handler 422 + sweeper estendido em api/main.py** — `fcd1357` (feat)

**Plan metadata:** (este commit — docs)

## Test Results

| Teste | Estado antes | Estado depois |
|-------|-------------|---------------|
| test_validation_error_format | RED (AssertionError: body sem chave 'error') | GREEN |
| test_sweeper_deletes_partial_files | RED (AssertionError: sg_*.part nao deletado) | GREEN |
| test_invalid_url_rejected (6 params) | GREEN | GREEN (sem regressao) |
| test_rate_limit_returns_429 | RED | RED (aguarda Plan 03) |
| test_rate_limit_retry_after_header | RED | RED (aguarda Plan 03) |

**Suite completa (not e2e):** 19 passed, 2 failed (rate limit stubs — esperado)

## Files Created/Modified

- `api/config.py` — linha 14 adicionada: `rate_limit_per_minute: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "3"))`
- `api/main.py` — 36 linhas inseridas, 11 removidas/substituidas:
  - Imports expandidos (linhas 14-17)
  - `sweep_expired_wavs` substituida pela versao com loop de 3 patterns (linhas 49-69)
  - `_validation_exception_handler` inserido apos `app = FastAPI(...)` (linhas 99-114)

## Decisions Made

- `RateLimitExceeded` importado agora (sem uso imediato) para que Plan 03 nao precise re-abrir o bloco de imports
- Variavel `wav` renomeada para `f` no sweeper — evita nome semanticamente errado apos multi-pattern
- Loop sobre tupla `("sg_*.wav", "sg_*.part", "sg_*.ytdl")` — imutavel e consistente com estilo existente

## Deviations from Plan

None — plano executado exatamente como especificado.

## Threat Model Compliance

| Threat | Mitigation implementada |
|--------|------------------------|
| T-hardening-02-01: Information Disclosure via 422 | `removeprefix("Value error, ")` + apenas `errors[0]["msg"]` — sem stack trace |
| T-hardening-02-02: DoS via disco (.part/.ytdl) | Glob `sg_*.part` e `sg_*.ytdl` com prefixo `sg_` — apenas arquivos do SoundGrabber |
| T-hardening-02-03: Tampering /tmp | Accept — prefixo `sg_` suficiente para v1 |

## Next Phase Readiness

- **03-03-PLAN**: `test_rate_limit_returns_429` e `test_rate_limit_retry_after_header` aguardam implementacao.
  O campo `rate_limit_per_minute` em `settings` e `RateLimitExceeded` ja importado — Plan 03 so precisa
  adicionar `Limiter`, `get_ipaddr`, o decorator `@limiter.limit` em POST /jobs e o handler 429.
- Sem bloqueadores.

---

## Self-Check: PASSED

- `api/config.py` existe e contem `rate_limit_per_minute` — FOUND
- `api/main.py` existe e contem `_validation_exception_handler` e loops `sg_*.part`/`sg_*.ytdl` — FOUND
- Commit `bc4ce74` existe — FOUND
- Commit `fcd1357` existe — FOUND

---
*Phase: 03-hardening*
*Completed: 2026-05-04*
