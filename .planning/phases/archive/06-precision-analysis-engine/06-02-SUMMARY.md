---
phase: 06-precision-analysis-engine
plan: "02"
subsystem: pipeline-analysis
tags: [essentia, librosa, hpss, tuning-detection, bpm-detection, tdd-green]
dependency_graph:
  requires: [06-01]
  provides: [detect-tuning-impl, detect-bpm-essentia-impl]
  affects: [pipeline.py, tests/test_pipeline.py]
tech_stack:
  added: []
  patterns:
    - "HPSS gate com margin=2.0 para discriminar ruído branco de sinal harmônico"
    - "Essentia RhythmExtractor2013(method=multifeature) — BPM resistente a octave errors"
    - "float() defensivo em todos os retornos Essentia (T-06-02-01 mitigation)"
key_files:
  created: []
  modified:
    - pipeline.py
    - tests/test_pipeline.py
decisions:
  - "HPSS margin=2.0 (não padrão 1.0) — ruído branco uniforme tem ratio ~0.26 com margin=1.0 (acima do gate 0.2); com margin=2.0 cai para 0.048 (abaixo do gate), enquanto sinal harmônico mantém ratio ~1.0"
  - "detect_bpm() remove argumento total_duration — Essentia RhythmExtractor2013 não precisa de offset; assinatura simplificada"
  - "test_detect_key_uses_tuning_hz permanece RED (stub Plan 01) — não é escopo do Plan 02; será GREEN no Plan 03"
metrics:
  duration: "8min"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 06 Plan 02: detect_tuning() + Essentia BPM Summary

Implementar `detect_tuning()` com HPSS gate e substituir `detect_bpm()` por Essentia RhythmExtractor2013 multifeature. Stubs RED do Plan 01 ficaram GREEN.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implementar detect_tuning() com HPSS gate | bf1f3d1 | pipeline.py |
| 2 | Substituir detect_bpm() por Essentia RhythmExtractor2013 | 61585a7 | pipeline.py, tests/test_pipeline.py |

---

## What Was Built

**Task 1 — detect_tuning() com HPSS gate (TUNING-01, TUNING-02):**

Função adicionada a `pipeline.py` antes de `detect_bpm()`:
- Carrega WAV com `librosa.load(sr=None, mono=True)` — taxa nativa preservada
- Aplica HPSS com `librosa.effects.hpss(y, margin=2.0)` — margin elevado para discriminação adequada
- Calcula `ratio = harm_energy / (total_energy + 1e-10)`
- Se `ratio < 0.2`: retorna `None` (beat percussivo — tuning seria ruído)
- Caso contrário: retorna `float(librosa.tuning_to_A4(librosa.estimate_tuning(y=y_harmonic, sr=sr, resolution=0.01)))`
- `import essentia.standard as es` adicionado ao bloco de imports

**Task 2 — detect_bpm() Essentia (PREC-01):**

Função `detect_bpm(wav_path: Path, total_duration: float)` (librosa) substituída por `detect_bpm(wav_path: Path) -> float` (Essentia):
- `es.MonoLoader(filename=str(wav_path), sampleRate=44100)()` carrega o áudio
- `es.RhythmExtractor2013(method="multifeature")(audio)` extrai o BPM
- `float(bpm)` — wrapping defensivo aplicado (T-06-02-01)
- `analyze_audio()` atualizado: `detect_bpm(wav_path)` sem `total_duration`
- `test_bpm_accuracy` atualizado: assinatura nova sem `total_duration=5.0`

---

## Test Results

```
tests/test_pipeline.py::test_detect_tuning_harmonic  PASSED  (TUNING-01 GREEN)
tests/test_pipeline.py::test_detect_tuning_percussive PASSED  (TUNING-02 GREEN)
tests/test_pipeline.py::test_bpm_accuracy             PASSED  (PREC-01 GREEN)
```

Suite não-e2e final: **11 passed, 1 failed (stub RED Plan 03), 1 skipped, 3 deselected**

O único teste falhando (`test_detect_key_uses_tuning_hz`) é o stub RED intencional criado no Plan 01 — escopo do Plan 03.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HPSS margin=2.0 em vez de padrão 1.0**
- **Found during:** Task 1 — primeira execução de `test_detect_tuning_percussive`
- **Issue:** Ruído branco com `np.random.default_rng(seed=42).uniform(-1.0, 1.0)` produz ratio harmônico ~0.26 com `margin=1.0` (padrão), acima do gate 0.2 — `detect_tuning()` retornava float em vez de None
- **Root cause:** HPSS com margin padrão é suave demais para discriminar ruído uniforme de sinal harmônico. O research foi feito com "noise bursts" (sinais de impacto transitório) que têm ratio ~0.0; o teste usa ruído branco estacionário que tem ratio ~0.26
- **Fix:** `librosa.effects.hpss(y, margin=2.0)` — com margin=2.0, ruído branco cai para ratio ~0.048; sinal harmônico 440Hz mantém ratio ~1.0; ambos discriminados corretamente pelo gate 0.2
- **Files modified:** pipeline.py
- **Commit:** bf1f3d1

---

## Known Stubs

`test_detect_key_uses_tuning_hz` — stub RED intencional (Plan 01). `detect_key()` atual não aceita `tuning_hz` como argumento. Será implementado no Plan 03 junto com a substituição de `detect_key()` por Essentia KeyExtractor.

---

## Threat Flags

Nenhuma surface nova além das previstas no threat model do plan.

**T-06-02-01 mitigado:** `float()` defensivo aplicado no retorno de `detect_bpm()` — numpy.float32 no dict quebra o Celery JSON serializer silenciosamente. Confirmado via `return float(bpm)`.

---

## Self-Check: PASSED

- `grep "def detect_tuning" pipeline.py` retorna match: FOUND
- `grep "RhythmExtractor2013" pipeline.py` retorna match: FOUND
- `grep "sampleRate=44100" pipeline.py` retorna match: FOUND
- `grep "def _pick_best_tempo" pipeline.py` retorna vazio: CONFIRMED (removido)
- `grep "detect_bpm(wav_path, total_duration" pipeline.py` retorna vazio: CONFIRMED
- Commit bf1f3d1 existe: FOUND
- Commit 61585a7 existe: FOUND
- 3 integration tests (tuning_harmonic, tuning_percussive, bpm_accuracy) PASSED: CONFIRMED
- Suite unit sem novas falhas: CONFIRMED (mesmo 1 failed do Plan 01)
