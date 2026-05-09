---
phase: 6
slug: precision-analysis-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | pytest.ini (raiz do projeto) |
| **Quick run command** | `.venv/bin/python3 -m pytest tests/test_pipeline.py -m "not e2e" -q` |
| **Full suite command** | `.venv/bin/python3 -m pytest tests/ -m "not e2e" -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python3 -m pytest tests/test_pipeline.py -m "not e2e" -q`
- **After every plan wave:** Run `.venv/bin/python3 -m pytest tests/ -m "not e2e" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | PREC-01, PREC-02, PREC-03, TUNING-01, TUNING-02, TUNING-03, QUAL-01 | — | N/A | unit | `pytest tests/test_pipeline.py -k "not e2e" -x -q` | ❌ W0 | ⬜ pending |
| 6-02-01 | 02 | 1 | PREC-01 | — | N/A | integration | `pytest tests/test_pipeline.py::test_bpm_accuracy -m integration -x` | ✅ (atualizar) | ⬜ pending |
| 6-02-02 | 02 | 1 | PREC-02, PREC-03 | — | N/A | integration | `pytest tests/test_pipeline.py::test_key_detection -m integration -x` | ✅ (atualizar) | ⬜ pending |
| 6-02-03 | 02 | 1 | PREC-03 | — | N/A | unit | `pytest tests/test_pipeline.py::test_detect_key_uses_tuning_hz -x` | ❌ W0 | ⬜ pending |
| 6-02-04 | 02 | 1 | PREC-04 | — | N/A | unit | `pytest tests/test_pipeline.py::test_json_output_shape -x` | ✅ (atualizar) | ⬜ pending |
| 6-02-05 | 02 | 1 | PREC-05 | — | N/A | unit | `pytest tests/test_pipeline.py::test_camelot_mapping -x` | ✅ (inalterado) | ⬜ pending |
| 6-03-01 | 03 | 1 | TUNING-01 | — | N/A | integration | `pytest tests/test_pipeline.py::test_detect_tuning_harmonic -x` | ❌ W0 | ⬜ pending |
| 6-03-02 | 03 | 1 | TUNING-02 | — | N/A | integration | `pytest tests/test_pipeline.py::test_detect_tuning_percussive -x` | ❌ W0 | ⬜ pending |
| 6-03-03 | 03 | 1 | TUNING-03, QUAL-01 | — | N/A | integration | `pytest tests/test_pipeline.py::test_json_output_shape -m integration -x` | ✅ (atualizar) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline.py::test_detect_tuning_harmonic` — stub RED para TUNING-01 (sinal 440Hz WAV fixture)
- [ ] `tests/test_pipeline.py::test_detect_tuning_percussive` — stub RED para TUNING-02 (sinal percussivo / mock)
- [ ] `tests/test_pipeline.py::test_detect_key_uses_tuning_hz` — stub RED para PREC-03 (mock KeyExtractor, captura tuningFrequency)

*Infraestrutura existente (pytest.ini, conftest.py, fixtures/sample.wav) cobre o restante.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HPSS threshold 0.2 adequado em beats reais | TUNING-02 | Validação empírica em 15-20 beats reais de produção | Rodar detect_tuning() em beats trap, house, lo-fi; verificar que puramente percussivos retornam None e harmônicos retornam Hz plausível |
| `import essentia.standard` sem exceção no venv | PREC-01 | Verificação de ambiente pós-install | `.venv/bin/python3 -c "import essentia.standard; print('OK')"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
