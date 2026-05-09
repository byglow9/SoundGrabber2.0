---
phase: 06-application-security
fixed_at: 2026-05-09T00:00:00Z
review_path: .planning/phases/06-application-security/06-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-05-09T00:00:00Z
**Source review:** .planning/phases/06-application-security/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: `/health` endpoint missing `@limiter.limit` — violates Security Gate

**Files modified:** `api/main.py`
**Commit:** 7d42004
**Applied fix:** Adicionado `@limiter.limit("60/minute")` acima de `health_check()` e os parâmetros `request: Request, response: Response` à assinatura da função, conforme exigido pelo Security Gate para todas as rotas novas com slowapi.

---

### WR-02: `_limit_body_size` silently bypasses size check on non-numeric `Content-Length`

**Files modified:** `api/main.py`
**Commit:** 7d42004
**Applied fix:** Substituído o `except ValueError: pass` por um retorno de `JSONResponse(status_code=400, content={"error": "Invalid Content-Length header.", "error_type": "request_error"})`, fechando o bypass de body-size via header malformado.

---

### WR-03: `start.sh` calls `log` before it is defined — crashes under `set -e`

**Files modified:** `start.sh`
**Commit:** 271e1f2
**Applied fix:** Movidos o bloco de variáveis de cor (`C_RESET`, `C_CELERY`, `C_SERVER`, `C_START`) e a definição de `log()` para imediatamente após o carregamento do `.env` e antes do bloco de verificação de `essentia`. O bloco do essentia agora pode chamar `log` sem risco de crash sob `set -e`.

---

### WR-04: `test_startsh_permissions` mutates live `start.sh` without restoring

**Files modified:** `tests/test_security.py`
**Commit:** 452d345
**Applied fix:** Adicionado `original_mode = stat.S_IMODE(os.stat(startsh).st_mode)` antes do `os.chmod`, e o assert movido para dentro de um bloco `try`/`finally` com `os.chmod(startsh, original_mode)` no `finally`. O modo original é sempre restaurado após a execução do teste, eliminando o efeito colateral no filesystem.

---

_Fixed: 2026-05-09T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
