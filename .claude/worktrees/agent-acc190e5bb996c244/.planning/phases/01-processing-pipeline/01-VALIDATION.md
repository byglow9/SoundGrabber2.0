---
phase: 1
slug: processing-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (Wave 0 cria) |
| **Quick run command** | `pytest tests/ -x -q -m "not integration and not e2e" --tb=short` |
| **Full suite command** | `pytest tests/ -v --tb=long -m "not e2e"` |
| **Estimated runtime** | ~5 seconds (unit), ~30s (integration), ~3min (e2e com YouTube real) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q -m "not integration and not e2e" --tb=short`
- **After every plan wave:** Run `pytest tests/ -v --tb=long -m "not e2e"`
- **Before `/gsd-verify-work`:** Full suite (including e2e com cookies.txt válido) deve estar verde
- **Max feedback latency:** 5 seconds (unit tests)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | CORE-05 | — | Duration check rejeita > 15min | unit | `pytest tests/test_pipeline.py::test_duration_check_rejects_long_video -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | CORE-05 | — | Duration check aceita <= 15min | unit | `pytest tests/test_pipeline.py::test_duration_check_accepts_short_video -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | CORE-03 | path traversal | ydl_opts contém cookiefile + po_token; sem shell=True | unit | `pytest tests/test_pipeline.py::test_download_opts_include_auth -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | CORE-04 | — | download_audio retorna Path .wav existente | integration | `pytest tests/test_pipeline.py::test_wav_file_created -x -m integration` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | CORE-04 | — | ffprobe valida WAV gerado como áudio válido | integration | `pytest tests/test_pipeline.py::test_ffprobe_validates_wav -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | ANALYSIS-03 | — | bpm_half == bpm/2 e bpm_double == bpm*2 | unit | `pytest tests/test_pipeline.py::test_bpm_half_double_calculation -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | ANALYSIS-04 | — | Camelot retorna código correto para key conhecida | unit | `pytest tests/test_pipeline.py::test_camelot_mapping -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | ANALYSIS-01 | — | BPM dentro de 30% do feel-tempo (sample WAV) | integration | `pytest tests/test_pipeline.py::test_bpm_accuracy -x -m integration` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | ANALYSIS-02 | — | Key correta para sample com tonalidade conhecida | integration | `pytest tests/test_pipeline.py::test_key_detection -x -m integration` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | D-05 | — | JSON output contém todos os campos obrigatórios | unit | `pytest tests/test_pipeline.py::test_json_output_shape -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 3 | D-07 | — | E2E: pipeline completo no URL rock/lo-fi | e2e | `pytest tests/test_pipeline.py::test_e2e_rock -x -m e2e` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 3 | D-07 | — | E2E: pipeline completo no URL trap | e2e | `pytest tests/test_pipeline.py::test_e2e_trap -x -m e2e` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 3 | D-07 | — | E2E: pipeline completo no URL house/lo-fi | e2e | `pytest tests/test_pipeline.py::test_e2e_house -x -m e2e` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline.py` — stubs para todos os testes listados acima
- [ ] `tests/conftest.py` — fixtures: `sample_wav_path`, `mock_yt_info`
- [ ] `tests/fixtures/sample.wav` — WAV de 5 segundos (A440, 440Hz) para testes de análise offline
- [ ] `pytest.ini` — markers: `integration`, `e2e`
- [ ] Install: `pip install pytest==9.0.3 pytest-subprocess`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Download bem-sucedido de IP de datacenter com cookies reais | CORE-03 | Requer VPS com IP dedicado + cookies.txt válido — não pode ser simulado em CI | No VPS: `YTDLP_COOKIES_FILE=./cookies.txt YTDLP_PO_TOKEN=TOKEN python pipeline.py https://www.youtube.com/watch?v=b1f6o0GMT8c` → verificar stdout JSON sem erro |
| PO Token funciona após 24h de geração | D-02 | Duração de expiração de token GVS não pode ser testada em CI isolado | Gerar token, aguardar 24h, executar pipeline novamente — confirmar que download não retorna erro "Sign in" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (unit tests)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
