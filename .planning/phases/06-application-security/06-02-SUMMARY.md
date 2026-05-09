---
phase: 06-application-security
plan: 02
subsystem: security
tags: [security, rate-limit, file-permissions, health-check, hardening]
dependency_graph:
  requires: [06-01]
  provides: [SEC-FILE-01, SEC-FILE-02, SEC-API-01, SEC-API-02, SEC-API-03]
  affects: [pipeline.py, start.sh, api/config.py, api/main.py]
tech_stack:
  added: []
  patterns:
    - os.chmod cirurgico apos verificacao de existencia do arquivo
    - slowapi @limiter.limit com request+response obrigatorios em sync endpoints
    - self-chmod 750 em shell script via realpath
    - health check minimalista — apenas ping, sem expor versao ou metricas
key_files:
  created: []
  modified:
    - pipeline.py
    - start.sh
    - api/config.py
    - api/main.py
    - tests/test_security.py
decisions:
  - "os.chmod aplicado apos wav_path.exists() check — garante que o arquivo existe antes de tentar chmod"
  - "start.sh usa realpath($0) para auto-chmod robusto contra symlinks e invocacoes relativas"
  - "GET /health sem @limiter.limit — health checks de monitoring podem rodar a cada 5-10s"
  - "max_queue_depth e middlewares de hardening adicionados ao worktree (estavam faltando do base commit)"
metrics:
  duration: "~25min"
  completed: "2026-05-09"
  tasks_total: 2
  tasks_completed: 2
  files_modified: 5
---

# Phase 06 Plan 02: Application Security Controls — Implementation Summary

**One-liner:** Implementacao cirurgica de 5 controles ASVS L1: chmod 0o600 em WAV, chmod 750 em start.sh, rate limit 60/min em GET /jobs, rate limit 10/min em GET /files, e endpoint GET /health com Redis liveness check.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | chmod 0o600 em WAV + chmod 750 em start.sh | `1d89074` | pipeline.py, start.sh, tests/test_security.py |
| 2 | Rate-limit config + decorators GET + /health | `e89581d` | api/config.py, api/main.py |

---

## Changes by File

### pipeline.py

- Linha 20: `import os` adicionado ao topo do modulo (antes estava apenas dentro de `if __name__ == "__main__":`)
- Linha 165-169: `os.chmod(wav_path, 0o600)` adicionado imediatamente antes de `return wav_path` em `download_audio()`, apos confirmar existencia do arquivo via `.exists()`

```python
    # SEC-FILE-01: WAV criado pelo subprocess ffmpeg com modo padrao (0o644 ou 0o664).
    # Aplicar chmod 0o600 explicito apos confirmar existencia...
    os.chmod(wav_path, 0o600)
    return wav_path
```

### start.sh

- Linhas 4-6: Bloco `chmod 750` adicionado apos `set -e`, antes de `PROJECT_DIR=`:

```bash
# SEC-FILE-02: garantir permissoes 750 (rwxr-x---) a cada execucao do script.
# Auto-chmod nao quebra a execucao em andamento — kernel verifica execve() apenas no inicio.
chmod 750 "$(realpath "$0")"
```

### api/config.py

Campos adicionados a classe `Settings`:
- Linha 19: `max_queue_depth: int` — default 50 via `MAX_QUEUE_DEPTH` env var (necessario para DoS protection)
- Linha 20: `job_poll_rate_limit_per_minute: int` — default 60 via `JOB_POLL_RATE_LIMIT_PER_MINUTE` (SEC-API-01)
- Linha 22: `file_download_rate_limit_per_minute: int` — default 10 via `FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE` (SEC-API-02)

### api/main.py

- Linha 5: `import os as _os` adicionado
- Linha 122-136: `FastAPI()` atualizado com `_debug` flag e `docs_url/redoc_url/openapi_url` condicionais (SEC-TEST-03)
- Linhas 134-171: Middlewares `_limit_body_size` (4KB cap, SEC-TEST-01) e `_security_headers` (X-Frame-Options, CSP, etc., SEC-TEST-02) adicionados
- Linha 219: `if _redis.llen("celery") >= settings.max_queue_depth: raise HTTPException(503)` em `submit_job` (SEC-TEST-04)
- Linha 230: `@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")` + parametros `request: Request, response: Response` em `get_job` (SEC-API-01)
- Linha 247-253: `@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")` + parametros em `download_file` (SEC-API-02)
- Linhas 285-309: Rota `GET /health` com `_redis.ping()` e tratamento de `ConnectionError`/`TimeoutError` (SEC-API-03)

---

## Test Results

### pytest tests/test_security.py -v

```
tests/test_security.py::test_wav_file_permissions PASSED
tests/test_security.py::test_startsh_permissions PASSED
tests/test_security.py::test_rate_limit_get_jobs PASSED
tests/test_security.py::test_rate_limit_get_files PASSED
tests/test_security.py::test_health_redis_ok PASSED
tests/test_security.py::test_health_redis_down PASSED
tests/test_security.py::test_body_size_limit PASSED
tests/test_security.py::test_security_headers PASSED
tests/test_security.py::test_docs_routes_disabled[/docs] PASSED
tests/test_security.py::test_docs_routes_disabled[/redoc] PASSED
tests/test_security.py::test_docs_routes_disabled[/openapi.json] PASSED
tests/test_security.py::test_queue_depth_limit PASSED
12 passed in 1.21s
```

### pytest tests/ -m "not e2e and not integration"

```
45 passed, 2 failed (pre-existentes), 11 deselected in 2.58s
```

Pre-existentes falhando (fora do escopo deste plano):
- `test_html_required_ids_present` — ID `download-area` faltando em index.html (falha no repo principal tambem)
- `test_detect_key_uses_tuning_hz` — `detect_key()` sem argumento `tuning_hz` no worktree base

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Middlewares de hardening ausentes no worktree base**
- **Found during:** Task 2 — ao rodar `pytest tests/test_security.py`, 6 testes falharam
- **Issue:** O commit base `36641ce` (docs de planejamento) nao tinha os middlewares de Phase 3 (body size limit, security headers, docs disabled, queue depth check) nem a `_debug` flag no `FastAPI()`. O worktree foi criado desse commit, portanto `api/main.py` estava sem esses controles.
- **Fix:** Adicionados os middlewares `_limit_body_size`, `_security_headers`, a `_debug` flag com docs condicionais, e o check `llen >= max_queue_depth` em `submit_job`. Tambem adicionado `max_queue_depth` em `api/config.py`.
- **Files modified:** api/main.py, api/config.py
- **Commit:** `e89581d`

**2. [Rule 3 - Blocking Issue] tests/test_security.py nao existia no worktree**
- **Found during:** Inicio da execucao — Plan 01 (Wave 0) cria o arquivo, mas o worktree nao tinha
- **Fix:** Criado `tests/test_security.py` com todos os 10 stubs (codigo exato do Plan 01) para que os testes pudessem ser executados
- **Files modified:** tests/test_security.py (novo)
- **Commit:** `1d89074`

---

## Deferred Issues

- `test_detect_key_uses_tuning_hz`: falha porque `pipeline.detect_key()` no worktree nao aceita `tuning_hz`. Isso e relacionado a refatoracao de precisao de outra fase/plano. Pre-existente, fora do escopo deste plano.
- `test_html_required_ids_present`: falha porque `download-area` ID nao existe em `static/index.html`. Pre-existente no repo principal tambem. Fora do escopo.

---

## Runtime Behavior Confirmed

- **WAV 0o600:** `os.chmod(wav_path, 0o600)` aplicado em `download_audio()` apos confirmar `wav_path.exists()`. Verificado via test `test_wav_file_permissions` (cria WAV com 0o664, aplica chmod, verifica bits).
- **start.sh 0o750:** `chmod 750 "$(realpath "$0")"` na linha 6 do script. `bash -n start.sh` retorna 0. Verificado via test `test_startsh_permissions`.
- **GET /jobs/{id} rate limit 60/min:** `@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")`. 61a requisicao retorna 429.
- **GET /files/{id} rate limit 10/min:** `@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")`. 11a requisicao retorna 429.
- **GET /health Redis up:** `_redis.ping()` retorna True → 200 `{"status": "ok"}`.
- **GET /health Redis down:** `ConnectionError` → 503 `{"status": "unavailable"}`.

---

## Threat Surface Scan

Nenhuma nova superficie nao documentada no threat model do plano. A rota `/health` ja estava no threat register (T-6-W1-05, T-6-W1-07) com disposicao `accept`.

## Self-Check: PASSED

Arquivos verificados:
- pipeline.py: `import os` na linha 20, `os.chmod(wav_path, 0o600)` na linha 165 — FOUND
- start.sh: `chmod 750` na linha 6 — FOUND
- api/config.py: `job_poll_rate_limit_per_minute`, `file_download_rate_limit_per_minute`, `max_queue_depth` — FOUND
- api/main.py: `/health` rota, `_redis.ping()`, `@limiter.limit` em get_job e download_file — FOUND

Commits verificados:
- `1d89074` feat(06-02): add os.chmod(0o600)... — FOUND
- `e89581d` feat(06-02): add rate-limit config... — FOUND
