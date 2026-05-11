---
phase: 10-failure-hardening-and-e2e-validation
plan: "02"
subsystem: pipeline+tasks
tags: [pipe06, bgutil, httpx, exception-handling, tdd]
dependency_graph:
  requires: [10-01-PLAN.md]
  provides: [BgutilUnavailable, bgutil-probe, bgutil_unavailable-error-type]
  affects: [pipeline.py, api/tasks.py, tests/test_pipeline_fixes.py]
tech_stack:
  added: []
  patterns: [httpx-probe, typed-exception-hierarchy, celery-exception-chain]
key_files:
  created: []
  modified:
    - pipeline.py
    - api/tasks.py
    - tests/test_pipeline_fixes.py
decisions:
  - "Probe verifica apenas conectividade TCP (qualquer resposta HTTP = up); sem resp.is_success para evitar falsos negativos (D-06)"
  - "BgutilUnavailable é subclasse direta de RuntimeError — callers existentes que só capturam RuntimeError ainda funcionam, mas tasks.py captura BgutilUnavailable primeiro para error_type distinto"
  - "Teste unitário de tasks.py mocka update_state para evitar conexão Redis em ambiente sem broker"
metrics:
  duration_seconds: 286
  completed_date: "2026-05-11"
  tasks_completed: 2
  files_modified: 3
  commits: 3
---

# Phase 10 Plan 02: PIPE-06 bgutil Probe Hardening Summary

**One-liner:** Probe HTTP httpx em download_audio + exceção tipada BgutilUnavailable(RuntimeError) + captura em tasks.py com error_type="bgutil_unavailable" — sem silent fallback para android client.

## What Was Built

Implementação completa do PIPE-06: quando `bgutil_base_url` está configurado mas o serviço bgutil está inacessível, o pipeline falha **imediatamente** com mensagem explícita — sem tentar silenciosamente trocar para android client (D-06, STATE.md Key Decisions).

### pipeline.py — 3 adições

1. **`import httpx`** adicionado ao bloco de imports (posição alfabética entre `es` e `imageio_ffmpeg`)

2. **`class BgutilUnavailable(RuntimeError)`** definida após imports, antes de `logger`:
   - Subclasse direta de `RuntimeError` para compatibilidade retroativa
   - Docstring explicando hierarquia de captura em tasks.py

3. **Probe HTTP** inserido em `download_audio` após `extractor_args` config, antes de `ydl_opts`:
   ```python
   if bgutil_base_url:
       logger.info("Probing bgutil availability at %s", bgutil_base_url)
       try:
           httpx.get(f"{bgutil_base_url}/", timeout=2.0)
           logger.info("bgutil probe OK — server responded")
       except httpx.RequestError as exc:
           logger.warning("bgutil probe failed: %s", exc)
           raise BgutilUnavailable(
               f"PO Token service unavailable (bgutil at {bgutil_base_url}). "
               f"Download requires bgutil to be running."
           ) from exc
   ```
   - Captura apenas `httpx.RequestError` (ConnectError, ConnectTimeout, etc.)
   - **Sem verificação de `resp.is_success`** — qualquer resposta HTTP = servidor up (D-06)
   - Timeout de 2.0s (D-04)

### api/tasks.py — 2 adições

1. **Import estendido:** `from pipeline import check_duration, download_audio, analyze_audio, BgutilUnavailable`

2. **Novo `except BgutilUnavailable`** inserido ANTES de `except RuntimeError` (linha 104 vs 111):
   ```python
   except BgutilUnavailable as e:
       logger.warning("Job %s bgutil_unavailable: %s", self.request.id, e)
       raise JobFailure(
           error=str(e),
           error_type="bgutil_unavailable",
       ) from e
   ```
   Ordem final dos excepts: ValueError → FileNotFoundError → **BgutilUnavailable** → RuntimeError → Exception

### tests/test_pipeline_fixes.py — 4 novos testes GREEN

| Teste | Comportamento testado | Status |
|-------|----------------------|--------|
| `test_pipe06_bgutil_probe_connect_error_raises` | ConnectError → exceção com "bgutil" na mensagem | GREEN |
| `test_pipe06_bgutil_probe_timeout_raises` | ConnectTimeout → exceção com "bgutil" na mensagem | GREEN |
| `test_pipe06_no_probe_when_bgutil_url_empty` | bgutil_base_url="" → httpx.get NÃO chamado | GREEN |
| `test_pipe06_tasks_bgutil_error_type` | BgutilUnavailable → JobFailure error_type="bgutil_unavailable" | GREEN |

## Test Results

```
pytest tests/test_pipeline_fixes.py -q
14 passed in 3.29s
```

Todos os 14 testes passando (10 anteriores + 4 novos PIPE-06). Zero regressões.

## Commits

| Hash | Tipo | Descrição |
|------|------|-----------|
| `6c3f6d2` | test | 4 stubs RED para PIPE-06 (wave 0 — pré-condição) |
| `9e06692` | feat | BgutilUnavailable + probe HTTP em pipeline.py |
| `84aee97` | feat | BgutilUnavailable catch em api/tasks.py + fix teste |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stub `test_pipe06_tasks_bgutil_error_type` incompatível com ambiente sem Redis**

- **Found during:** Task 2, fase GREEN
- **Issue:** O stub do plano 10-01 usava `RuntimeError` genérico como side_effect de `download_audio` e não mockava `process_job.update_state`. Na execução, `self.update_state()` na primeira linha de `process_job` tenta conectar ao Redis (porta 6380, não rodando), levantando `redis.exceptions.ConnectionError` antes de chegar no `download_audio` mockado. A exceção cai no `except Exception` genérico → `error_type="internal_error"`, não `"bgutil_unavailable"`.
- **Fix:**
  1. Trocado `side_effect=RuntimeError(msg)` por `side_effect=BgutilUnavailable(msg)` (o tipo correto que `except BgutilUnavailable` captura)
  2. Adicionado `patch.object(process_job, "update_state")` para evitar conexão Redis em teste unitário
  3. Refatorado para capturar `JobFailure` explicitamente antes do `except Exception` genérico do stub
- **Files modified:** `tests/test_pipeline_fixes.py`
- **Commit:** `84aee97`

### Out-of-scope issues noted

- `tests/test_security.py` — 38 errors por `redis.exceptions.ConnectionError` (Redis não rodando localmente). Pré-existente — confirmado em baseline antes das mudanças deste plano.
- `tests/test_pipeline.py::test_json_output_shape_integration` — 1 falha pré-existente. Confirmado via `git stash` que falha mesmo sem as mudanças do plano.

## Known Stubs

Nenhum. Toda a funcionalidade PIPE-06 foi implementada e verificada por testes automatizados.

## Threat Flags

Nenhum. Sem novos endpoints HTTP, arquivos em /tmp, ou scripts shell introduzidos.

Os controles do Security Gate CLAUDE.md mantidos:
- `os.chmod(wav_path, 0o600)` em `download_audio` permanece inalterado (SEC-FILE-01)
- Rate limiting nos endpoints existentes inalterado
- `BGUTIL_BASE_URL` é env var do operador, não input de usuário — sem vetor de injection

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `pipeline.py` existe | FOUND |
| `api/tasks.py` existe | FOUND |
| `tests/test_pipeline_fixes.py` existe | FOUND |
| `10-02-SUMMARY.md` existe | FOUND |
| commit `6c3f6d2` existe | FOUND |
| commit `9e06692` existe | FOUND |
| commit `84aee97` existe | FOUND |
| `pytest tests/test_pipeline_fixes.py` → 14 passed | PASSED |
