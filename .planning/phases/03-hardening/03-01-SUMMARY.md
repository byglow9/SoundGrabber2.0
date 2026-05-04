---
phase: 03-hardening
plan: 01
subsystem: testing
tags: [slowapi, pytest, tdd, rate-limiting, sweeper, validation]

# Dependency graph
requires:
  - phase: 02-api-layer
    provides: api.main (sweep_expired_wavs), POST /jobs endpoint, api_client fixture
provides:
  - slowapi==0.1.9 pinned in requirements.txt and installed in .venv
  - Four RED stubs covering UX-03 (422 normalization) and UX-04 (rate limiting)
  - test_validation_error_format, test_rate_limit_returns_429, test_rate_limit_retry_after_header, test_sweeper_deletes_partial_files
affects: [03-02-PLAN, 03-03-PLAN]

# Tech tracking
tech-stack:
  added: [slowapi==0.1.9]
  patterns: [TDD RED stubs appended at end of test_api.py without modifying existing tests]

key-files:
  created: []
  modified:
    - requirements.txt
    - tests/test_api.py

key-decisions:
  - "slowapi pinned com == como dependencia de aplicacao (nao >=) seguindo convencao do projeto"
  - "Quatro stubs adicionados ao final de tests/test_api.py sem modificar os 10 testes pre-existentes"
  - "import os dentro da funcao test_sweeper_deletes_partial_files seguindo padrao existente (linha 162)"

patterns-established:
  - "RED stubs: stubs de fase posterior sao adicionados ao final do arquivo de testes e falham com AssertionError (nunca ImportError/SyntaxError)"
  - "Posicionamento de dependencias: dependencias de aplicacao inseridas apos fastapi, antes de uvicorn"

requirements-completed: [UX-03, UX-04]

# Metrics
duration: 2min
completed: 2026-05-04
---

# Phase 3 Plan 01: Hardening Setup Summary

**slowapi==0.1.9 instalado e quatro stubs TDD RED criados cobrindo 422 normalization (UX-03) e rate limiting 429 (UX-04)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-04T18:52:57Z
- **Completed:** 2026-05-04T18:54:44Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- slowapi==0.1.9 adicionado em requirements.txt e instalado no .venv do projeto
- Quatro stubs RED adicionados ao final de tests/test_api.py (total: 14 testes)
- Stubs falham com AssertionError (RED correto) — nao com ImportError ou SyntaxError
- 17 testes pre-existentes continuam passando sem regressao

## Task Commits

Cada tarefa commitada atomicamente:

1. **Task 1: Adicionar slowapi==0.1.9 em requirements.txt** - `3b39159` (chore)
2. **Task 2: Adicionar quatro stubs de Phase 3 em tests/test_api.py** - `dda7783` (test)

**Plan metadata:** (este commit — docs)

## Files Created/Modified
- `requirements.txt` - slowapi==0.1.9 inserido apos fastapi==0.136.1, antes de uvicorn==0.46.0
- `tests/test_api.py` - Quatro stubs RED adicionados ao final (linhas 204-282): test_validation_error_format, test_rate_limit_returns_429, test_rate_limit_retry_after_header, test_sweeper_deletes_partial_files

## Decisions Made
- slowapi pinado com `==` (nao `>=`) seguindo convencao de dependencias de aplicacao do projeto
- `import os` colocado dentro da funcao de teste seguindo padrao existente na linha 162 do arquivo
- Stubs nao recebem `@pytest.mark` (apenas testes e2e recebem marker)

## Deviations from Plan

None — plano executado exatamente como especificado.

## Issues Encountered
- `pip install slowapi==0.1.9` falhou com "externally-managed-environment" (PEP 668) no Python do sistema. Resolvido usando `.venv` do projeto em `/home/glow/Documentos/SoundGrabber2.0/.venv/bin/activate` — comportamento normal no ambiente, nao e desvio.

## User Setup Required
None — nenhuma configuracao de servico externo necessaria.

## Next Phase Readiness
- **03-02-PLAN**: `test_validation_error_format` e `test_sweeper_deletes_partial_files` aguardam implementacao. O plano 02 implementara o handler 422 normalizado (D-07) e o sweeper estendido para .part/.ytdl (D-05/D-06).
- **03-03-PLAN**: `test_rate_limit_returns_429` e `test_rate_limit_retry_after_header` aguardam implementacao com slowapi Limiter + Redis backend.
- Sem bloqueadores — slowapi ja instalado, stubs coletados sem erro de sintaxe.

---
*Phase: 03-hardening*
*Completed: 2026-05-04*
