---
phase: 10-failure-hardening-and-e2e-validation
plan: "01"
subsystem: tests
tags: [tdd, pipe-06, bgutil, red-stubs]
dependency_graph:
  requires: []
  provides: [pipe06-red-stubs]
  affects: [tests/test_pipeline_fixes.py]
tech_stack:
  added: []
  patterns: [unittest.mock.patch, pytest.raises, RED stubs TDD]
key_files:
  created: []
  modified:
    - tests/test_pipeline_fixes.py
decisions:
  - "Mock path correto: 'pipeline.httpx.get' (não 'httpx.get') — httpx só existe como atributo do módulo pipeline após import"
  - "Stub 4 (tasks bgutil error_type) falha com 'internal_error' via Redis ConnectionError — aceito como RED válido porque verifica exatamente o ponto de falha que 10-02 irá corrigir"
metrics:
  duration_seconds: 115
  completed_date: "2026-05-11"
  tasks_completed: 1
  files_modified: 1
---

# Phase 10 Plan 01: RED Stubs para PIPE-06 (bgutil Probe)

**One-liner:** 4 stubs RED para PIPE-06 em test_pipeline_fixes.py validando que pipeline.httpx não existe e BgutilUnavailable não existe ainda.

---

## Summary

O plano 10-01 estabelece os contratos de comportamento para PIPE-06 (probe HTTP explícito de bgutil em `download_audio`) ANTES de qualquer implementação. Isso garante que o plano 10-02 valida comportamento real, não apenas passa por coincidência.

Os 4 stubs foram adicionados ao final de `tests/test_pipeline_fixes.py` sem modificar nenhum dos 10 testes existentes. Nenhum arquivo de produção foi tocado.

---

## Tasks

### Task 1: Escrever 4 stubs RED para PIPE-06

**Commit:** `65ed34a`
**Arquivos:** `tests/test_pipeline_fixes.py` (+98 linhas)

**Stubs criados:**

| Stub | Nome | Estado RED | Motivo da Falha |
|------|------|------------|-----------------|
| 1 | `test_pipe06_bgutil_probe_connect_error_raises` | RED | `AttributeError: module 'pipeline' has no attribute 'httpx'` |
| 2 | `test_pipe06_bgutil_probe_timeout_raises` | RED | `AttributeError: module 'pipeline' has no attribute 'httpx'` |
| 3 | `test_pipe06_no_probe_when_bgutil_url_empty` | RED | `AttributeError: module 'pipeline' has no attribute 'httpx'` |
| 4 | `test_pipe06_tasks_bgutil_error_type` | RED | `AssertionError: error_type esperado 'bgutil_unavailable', obtido 'internal_error'` |

**Testes anteriores (regressão zero):**

| Contagem | Estado |
|----------|--------|
| 10 testes pré-existentes | GREEN (zero regressões) |
| 4 novos stubs PIPE-06 | RED (conforme esperado) |

---

## Verification Results

```
# grep -c "def test_pipe06_" tests/test_pipeline_fixes.py
4

# pytest tests/test_pipeline_fixes.py -k "test_pipe06" -q
4 failed (RED — conforme esperado)

# pytest tests/test_pipeline_fixes.py -k "not test_pipe06" -q
10 passed (zero regressões)

# grep "pipeline.httpx.get" tests/test_pipeline_fixes.py
3 ocorrências (stubs 1, 2, 3)

# grep "bgutil_unavailable" tests/test_pipeline_fixes.py
2 ocorrências (stub 4)
```

---

## Deviations from Plan

Nenhuma — plano executado exatamente como escrito.

Nota: O plano menciona "11 testes existentes" mas o arquivo tinha 10 testes pré-existentes. Não é uma discrepância funcional — todos os testes pré-existentes continuam passando.

---

## Known Stubs

Todos os 4 stubs são intencionalmente RED e serão resolvidos em 10-02-PLAN.md que irá:
- Adicionar `import httpx` em `pipeline.py`
- Adicionar `class BgutilUnavailable(RuntimeError)` em `pipeline.py`
- Adicionar probe HTTP em `download_audio()` antes de `ydl_opts`
- Adicionar `except BgutilUnavailable` em `api/tasks.py` ANTES de `except RuntimeError`

---

## Threat Flags

Nenhum — arquivo de teste sem lógica de produção, sem dados sensíveis, sem novos endpoints HTTP.

---

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `tests/test_pipeline_fixes.py` existe | FOUND |
| `10-01-SUMMARY.md` existe | FOUND |
| Commit `65ed34a` existe | FOUND |
