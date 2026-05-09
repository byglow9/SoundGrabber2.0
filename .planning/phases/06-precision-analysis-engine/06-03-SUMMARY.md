---
phase: 06-precision-analysis-engine
plan: "03"
subsystem: pipeline-analysis
tags: [essentia, key-detection, tuning-hz, tdd-green, json-safety, tasks-propagation]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [detect-key-essentia-impl, tuning-hz-in-analyze-audio, tuning-hz-in-tasks]
  affects: [pipeline.py, api/tasks.py, tests/test_pipeline.py]
tech_stack:
  added: []
  patterns:
    - "Essentia KeyExtractor(profileType='edma', tuningFrequency=freq) para key detection"
    - "freq = tuning_hz if tuning_hz is not None else 440.0 — fallback defensivo para beats percussivos"
    - "result.get('tuning_hz') em tasks.py — defesa contra regressao sem KeyError"
    - "float() defensivo em strength retornado pelo KeyExtractor (T-06-03-01)"
key_files:
  created: []
  modified:
    - pipeline.py
    - api/tasks.py
    - tests/test_pipeline.py
decisions:
  - "detect_key() recebe tuning_hz como argumento explícito (não lê de estado global) — pureza funcional e testabilidade por mock"
  - "freq = tuning_hz if tuning_hz is not None else 440.0 antes da instanciação do KeyExtractor — None invalida tuningFrequency em C++"
  - "result.get('tuning_hz') em tasks.py (não result['tuning_hz']) — defesa contra regressão futura sem KeyError"
  - "test_json_output_shape_integration usa @pytest.mark.integration com WAV real — QUAL-01 requer validação sem mocks"
metrics:
  duration: "5min"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 06 Plan 03: detect_key() Essentia + tuning_hz propagation Summary

Substituir detect_key() por Essentia KeyExtractor(profileType="edma") com tuning_hz como argumento, atualizar analyze_audio() com nova sequência de execução e campo tuning_hz, propagar tuning_hz para api/tasks.py, e fechar o ciclo TDD: o stub RED test_detect_key_uses_tuning_hz (criado no Plan 01) ficou GREEN.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Substituir detect_key() por Essentia KeyExtractor e limpar código legado | 06cdad4 | pipeline.py, tests/test_pipeline.py |
| 2 | Propagar tuning_hz para api/tasks.py e executar suite completa | 2c0cee3 | api/tasks.py, tests/test_pipeline.py |

---

## What Was Built

**Task 1 — Migração detect_key() para Essentia:**

Removido de `pipeline.py`:
- Constantes `_MAJOR_PROFILE`, `_MINOR_PROFILE`, `_NOTES` (perfis Krumhansl-Schmuckler)
- Função `_detect_key_from_chroma(chroma)` (implementação manual de correlação)
- Função `detect_key(wav_path)` sem tuning_hz (assinatura legada librosa/chroma_cqt)

Adicionado em `pipeline.py`:
- `detect_key(wav_path: Path, tuning_hz: float | None) -> tuple[str, float]`
  - `es.MonoLoader(filename=str(wav_path), sampleRate=44100)()`
  - `freq = tuning_hz if tuning_hz is not None else 440.0` (fallback defensivo — Pitfall 3)
  - `es.KeyExtractor(profileType="edma", tuningFrequency=freq)(audio)`
  - Retorna `(str(f"{key} {scale}"), float(strength))`

Atualizado `analyze_audio()` com nova sequência:
1. `validate_wav(wav_path)` — ffprobe (inalterado)
2. `detect_tuning(wav_path)` — librosa HPSS (ANTES de detect_key — PREC-03)
3. `detect_bpm(wav_path)` — Essentia
4. `detect_key(wav_path, tuning_hz)` — Essentia com tuning_hz calculado
5. `key_to_camelot(key)` — lookup O(1)

Adicionados campos ao dict de retorno de `analyze_audio()`:
- `tuning_hz` (float | None) — TUNING-03
- `key_confidence` (float) — confiança do KeyExtractor

Testes atualizados em `tests/test_pipeline.py`:
- `test_key_detection`: `detect_key(sample_wav_path)` → `detect_key(sample_wav_path, tuning_hz=None)`
- `test_bpm_half_double_calculation`: adicionado `patch.object(pipeline, "detect_tuning", return_value=440.0)`
- `test_json_output_shape`: adicionado mock de `detect_tuning`; `"tuning_hz"` adicionado ao set `required`

**Task 2 — Propagação tuning_hz para tasks.py + QUAL-01:**

Em `api/tasks.py`, dict de retorno de `process_job()` recebeu:
```python
"tuning_hz": result.get("tuning_hz"),   # float ou None — TUNING-03
```

Adicionado em `tests/test_pipeline.py`:
- `test_json_output_shape_integration` (`@pytest.mark.integration`) — chama `analyze_audio(sample_wav_path)` com WAV real, verifica campo `tuning_hz`, e confirma `json.dumps()` sem TypeError (QUAL-01)

---

## Test Results

```
Suite não-e2e final: 13 passed, 1 skipped (intencional), 3 deselected (e2e), 0 failed

Testes RED do Plan 01 que viraram GREEN neste plan:
  tests/test_pipeline.py::test_detect_key_uses_tuning_hz  PASSED  (PREC-03 GREEN)

Testes atualizados que permanecem GREEN:
  tests/test_pipeline.py::test_key_detection              PASSED  (PREC-02 GREEN)
  tests/test_pipeline.py::test_json_output_shape          PASSED  (PREC-04, TUNING-03 GREEN)
  tests/test_pipeline.py::test_bpm_half_double_calculation PASSED

Testes novos adicionados neste plan:
  tests/test_pipeline.py::test_json_output_shape_integration PASSED (QUAL-01 GREEN)

Serialização direta verificada:
  tuning_hz: 440.25422738288415
  json ok: 232 chars (sem TypeError)
```

---

## Deviations from Plan

None — plano executado exatamente como escrito.

---

## Known Stubs

Nenhum. Todos os stubs RED da fase (Plans 01-03) foram implementados:
- `detect_tuning()` — Plan 02 (GREEN)
- `detect_bpm()` Essentia — Plan 02 (GREEN)
- `detect_key(wav_path, tuning_hz)` — Plan 03 (GREEN) ← este plan

---

## Threat Flags

Nenhuma surface nova além das previstas no threat model do plan.

**T-06-03-01 mitigado:** `float(strength)` aplicado no retorno de `detect_key()` — wrapping defensivo contra numpy types em versões futuras do binding Essentia.

**T-06-03-02 aceito:** `wav_path` no dict de retorno de `tasks.py` já era exposto desde Phase 2 — sem mudança de superfície.

---

## Self-Check: PASSED

- `grep "def detect_key(wav_path: Path, tuning_hz" pipeline.py`: FOUND (linha 309)
- `grep "es.KeyExtractor(" pipeline.py`: FOUND (linha 328)
- `grep 'profileType="edma"' pipeline.py`: FOUND (linha 329)
- `grep "tuningFrequency=freq" pipeline.py`: FOUND (linha 330)
- `grep "_detect_key_from_chroma" pipeline.py`: VAZIO (removida) — CONFIRMED
- `grep "_MAJOR_PROFILE" pipeline.py`: VAZIO (removida) — CONFIRMED
- `grep '"tuning_hz":' pipeline.py`: FOUND (linha 436)
- `grep "tuning_hz = detect_tuning" pipeline.py`: FOUND (linha 424)
- `grep "detect_key(wav_path, tuning_hz)" pipeline.py`: FOUND (linha 426)
- `grep "tuning_hz" api/tasks.py`: FOUND (linha 80)
- `grep "def test_json_output_shape_integration" tests/test_pipeline.py`: FOUND (linha 315)
- Suite não-e2e: 13 passed, 0 failed — CONFIRMED
- Commit 06cdad4 existe: FOUND
- Commit 2c0cee3 existe: FOUND
