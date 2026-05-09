---
phase: 06-precision-analysis-engine
plan: "01"
subsystem: pipeline-testing
tags: [essentia, tdd, red-stubs, tuning-detection, key-detection]
dependency_graph:
  requires: []
  provides: [essentia-dependency, tdd-red-stubs-tuning, tdd-red-stubs-key]
  affects: [tests/test_pipeline.py, requirements.txt]
tech_stack:
  added: [essentia==2.1b6.dev1389]
  patterns: [TDD-RED stubs via importorskip + hasattr guard, pytest.mark.integration for HPSS tests]
key_files:
  created: []
  modified:
    - requirements.txt
    - tests/test_pipeline.py
decisions:
  - "essentia pinned with == (not >=) per project convention — prevents silent breakage from upstream releases"
  - "test_detect_key_uses_tuning_hz has no @pytest.mark.integration — it uses only mocks, runs on every commit"
  - "essentia-tensorflow excluded — RhythmExtractor2013 does not require TF; avoids 2GB dependency chain"
metrics:
  duration: "2min"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 06 Plan 01: Essentia Install + TDD RED Stubs Summary

Instalar `essentia==2.1b6.dev1389` no venv e criar 3 stubs TDD RED que definem o contrato de implementação para os plans 02 e 03.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar essentia ao requirements.txt e verificar import | b02eeeb | requirements.txt |
| 2 | Criar stubs TDD RED — test_detect_tuning_harmonic, test_detect_tuning_percussive, test_detect_key_uses_tuning_hz | 7361d5b | tests/test_pipeline.py |

---

## What Was Built

**Task 1 — Dependência Essentia:**
- Linha `essentia==2.1b6.dev1389` adicionada ao final de `requirements.txt`
- Já estava instalada no venv (confirmado: `pip install` retornou "Requirement already satisfied")
- Import verificado: `import essentia.standard` retorna sem exceção (apenas INFO log do MusicExtractorSVM)
- `essentia-tensorflow` ausente (confirmado por grep negativo)

**Task 2 — Stubs TDD RED:**
Inseridos em `tests/test_pipeline.py` após o bloco `# ANALYSIS-04: Camelot mapping`, 3 novos testes:

1. `test_detect_tuning_harmonic` (`@pytest.mark.integration`) — Chama `pipeline.detect_tuning(sample_wav_path)` e espera `float` entre 400-480 Hz. Falha RED com `pytest.fail("pipeline.detect_tuning não existe — implementar no Plan 02")`.

2. `test_detect_tuning_percussive` (`@pytest.mark.integration`) — Cria WAV de ruído branco (numpy, seed=42, 2s@22050Hz), chama `detect_tuning()` e espera `None`. Falha RED com mesmo motivo.

3. `test_detect_key_uses_tuning_hz` (sem marcador — unit test) — Usa `unittest.mock.patch` para capturar os kwargs de instanciação de `essentia.standard.KeyExtractor`. Verifica `tuningFrequency=432.0` e `profileType="edma"`. Falha RED com `TypeError: detect_key() got an unexpected keyword argument 'tuning_hz'` — a assinatura atual não aceita o parâmetro ainda.

---

## RED Confirmation

```
3 failed, 13 deselected in 1.14s
FAILED tests/test_pipeline.py::test_detect_tuning_harmonic
FAILED tests/test_pipeline.py::test_detect_tuning_percussive
FAILED tests/test_pipeline.py::test_detect_key_uses_tuning_hz
```

Suite pré-existente (não-integration, excluindo novos stubs) permanece verde: **6 passed**.

---

## Deviations from Plan

None — plano executado exatamente como escrito.

---

## Known Stubs

Os 3 testes adicionados são intencionalmente stubs RED. Serão implementados nos plans subsequentes:
- `detect_tuning()` — Plan 02
- `detect_key(wav_path, tuning_hz)` — Plan 03

---

## Threat Flags

Nenhuma surface nova identificada. Os arquivos modificados (`requirements.txt`, `tests/test_pipeline.py`) estão dentro das fronteiras de confiança previstas no threat model do plan.

---

## Self-Check: PASSED

- requirements.txt existe e contém `essentia==2.1b6.dev1389`: FOUND
- tests/test_pipeline.py contém os 3 stubs: FOUND (grep count = 3)
- Commit b02eeeb existe: FOUND
- Commit 7361d5b existe: FOUND
- 3 stubs em RED: CONFIRMED (3 failed)
- 6 testes pré-existentes passando: CONFIRMED (6 passed)
