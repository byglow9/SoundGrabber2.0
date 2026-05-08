---
phase: 04-frontend
fixed_at: 2026-05-08T16:30:00Z
review_path: .planning/phases/04-frontend/04-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-05-08T16:30:00Z
**Source review:** .planning/phases/04-frontend/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, WR-04)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `request.client` pode ser `None` — crash em producao no rate limiter

**Files modified:** `api/main.py`
**Commit:** f6f73c6
**Applied fix:** Adicionado guard `if request.client is None: return "unknown"` em `_real_ip()` antes de acessar `.host`. Isso evita `AttributeError` e crash 500 em conexoes sem peer address (proxies mal configurados, certos setups ASGI, TestClient).

---

### WR-01: `showSubmitting()` nao oculta painel de resultado, erro e progresso anteriores

**Files modified:** `static/app.js`
**Commit:** 1c9ee50
**Applied fix:** Adicionadas quatro linhas `.hidden = true` ao final de `showSubmitting()` para ocultar `progress-area`, `result-card`, `error-area` e `validation-error` durante o envio, eliminando UI inconsistente ao reenviar apos DONE/ERROR.

---

### WR-02: `showErrorJob()` nao remove a classe de erro do input — borda vermelha persiste

**Files modified:** `static/app.js`
**Commit:** 1c9ee50
**Applied fix:** Adicionada chamada `$('url-input').classList.remove('sg-url-input--error')` como primeira linha de `showErrorJob()`, garantindo que a borda vermelha de validacao seja removida quando o erro e de job e nao de URL.

---

### WR-03: `pollStatus()` pode executar concorrentemente — race condition de estado

**Files modified:** `static/app.js`
**Commit:** 1c9ee50
**Applied fix:** Adicionada variavel `isPolling = false` na secao de state variables (linha 12). `pollStatus()` agora retorna imediatamente se `isPolling` for `true`, seta para `true` ao iniciar e usa bloco `finally` para sempre liberar a flag. `stopPolling()` tambem reseta `isPolling = false` para garantir consistencia.

---

### WR-04: `data.job_id` nao e validado antes de ser passado a `startPolling()`

**Files modified:** `static/app.js`
**Commit:** 1c9ee50
**Applied fix:** Adicionada validacao `if (!data.job_id)` imediatamente apos parsear o JSON do response 202. Resposta malformada sem `job_id` agora transita para `ERROR_JOB` em vez de chamar `startPolling(undefined)` e prender o usuario em `/jobs/undefined` ate o timeout de 3 minutos.

---

_Fixed: 2026-05-08T16:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
