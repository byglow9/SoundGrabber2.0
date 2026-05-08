---
phase: 04-frontend
plan: 01
subsystem: testing
tags: [pytest, frontend, tdd, red-stubs, html-parser, wav-size-formula]

# Dependency graph
requires:
  - phase: 03-hardening
    provides: "api/main.py com rotas POST /jobs, GET /jobs/{id}, GET /files/{id} e conftest.py com fixture api_client"
provides:
  - "tests/test_frontend.py com 4 testes RED stub cobrindo CORE-01, UX-01, UX-02"
  - "test_wav_size_formula passa imediatamente (puro Python, sem HTTP)"
  - "Tests 1-3 falham RED aguardando Plans 02-04 adicionarem static/index.html, static/app.js e GET / + StaticFiles"
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED-stub pattern: testes escritos antes da implementação, falham com ConnectionError/404, não com SyntaxError/ImportError"
    - "Reutilização de api_client fixture de conftest.py sem redefinição"
    - "Verificação de IDs HTML via loop: assert f'id=\"{element_id}\"' in html_text"
    - "Equivalente Python da fórmula JS de estimativa WAV: duration_sec * 44100 * 2 * 2 / 1_000_000"

key-files:
  created:
    - tests/test_frontend.py
  modified: []

key-decisions:
  - "Fórmula WAV em Python: duration_sec * 44100 * 2 * 2 / 1_000_000 (16-bit PCM, 2 canais, 44100 Hz) — equivalente exato do D-08 do CONTEXT.md"
  - "Verificação de IDs via string contains (sem BeautifulSoup) — html.parser stdlib é suficiente; a abordagem de string simples é menos frágil e mais direta para este caso"
  - "16 IDs obrigatórios do UI-SPEC cobertos em test_html_required_ids_present via loop"

patterns-established:
  - "Pattern RED-stub: testes de Phase 4 definidos em Plan 01 (Wave 1) antes de qualquer HTML/JS existir; viram GREEN em Plans 02-04"
  - "Fixture api_client reutilizada diretamente de conftest.py — não redefinida em arquivos de teste downstream"

requirements-completed: [CORE-01, UX-01, UX-02]

# Metrics
duration: 12min
completed: 2026-05-08
---

# Phase 4 Plan 01: Frontend Test Stubs Summary

**4 testes RED stub cobrindo CORE-01/UX-01/UX-02 — fórmula WAV size em Python GREEN imediatamente; 3 testes HTTP falham RED aguardando Plans 02-04**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-08T14:31:00Z
- **Completed:** 2026-05-08T14:43:09Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Criado `tests/test_frontend.py` com 4 testes nomeados exatamente conforme o plano
- `test_wav_size_formula` passa imediatamente (puro Python, sem dependência de rede ou servidor)
- `test_index_html_served`, `test_app_js_served`, `test_html_required_ids_present` falham RED com `ConnectionError` (Redis indisponível em dev) — não com `SyntaxError` ou `ImportError`
- Fórmula WAV verificada: `300s → 52.92 MB`, `60s → 10.584 MB`, `0s → 0`, `600s → 105.84 MB`
- 16 IDs do UI-SPEC cobertos em `test_html_required_ids_present` via loop explícito

## Task Commits

1. **Task 1: Create tests/test_frontend.py with RED stubs** - `5013aaf` (test)

**Plan metadata:** (a ser adicionado)

## Files Created/Modified

- `tests/test_frontend.py` — 4 testes RED stub para frontend Phase 4 (CORE-01, UX-01, UX-02)

## Decisions Made

- Usada verificação via `f'id="{element_id}"' in html_text` (string simples) em vez de `html.parser` para verificar IDs — mais direta e menos frágil para o padrão exato de atributos HTML gerado pelo template do UI-SPEC
- A fórmula Python `duration_sec * 44100 * 2 * 2 / 1_000_000` é o equivalente exato da fórmula JS do D-08 do CONTEXT.md (`Math.round(duration_sec * 44100 * 2 * 2 / 1_000_000)`) — sem arredondamento no teste para permitir `pytest.approx`
- `test_wav_size_formula` não usa o fixture `api_client` (correto — função pura, sem HTTP)

## Deviations from Plan

Nenhum — plano executado exatamente conforme escrito.

## Issues Encountered

- Redis não está rodando em dev (`localhost:6380` recusa conexão) — isso causa `ConnectionError` nos 3 testes HTTP, que é o comportamento RED esperado. `test_wav_size_formula` não depende de Redis e passa normalmente.

## Known Stubs

Nenhum stub que impeça o objetivo do plano. Os 3 testes RED (`test_index_html_served`, `test_app_js_served`, `test_html_required_ids_present`) são intencionalmente falhos neste estágio — Plans 02-04 os tornarão GREEN ao criar `static/index.html`, `static/app.js` e adicionar `GET /` + `StaticFiles` ao `api/main.py`.

## User Setup Required

Nenhum — sem serviços externos necessários neste plano.

## Next Phase Readiness

- `tests/test_frontend.py` pronto para ser usado pelos Plans 02, 03 e 04 como gate de verificação
- Plans 02-04 devem usar `pytest tests/test_frontend.py -x -q` como verificação por commit
- Sem bloqueadores

## Self-Check: PASSED

- [x] `tests/test_frontend.py` existe: FOUND
- [x] Commit `5013aaf` existe: FOUND
- [x] 4 funções de teste presentes (grep -c "def test_" = 4): VERIFIED
- [x] `test_wav_size_formula` passa: 1 passed in 0.07s
- [x] 3 outros testes falham RED (ConnectionError, não SyntaxError): VERIFIED

---
*Phase: 04-frontend*
*Completed: 2026-05-08*
