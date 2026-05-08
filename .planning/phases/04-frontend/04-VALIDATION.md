---
phase: 4
slug: frontend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (existente) |
| **Quick run command** | `pytest tests/test_frontend.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q -m "not e2e"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_frontend.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q -m "not e2e"`
- **Before `/gsd-verify-work`:** Full suite must be green + manual browser smoke test
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | CORE-01, UX-01, UX-02 | — | N/A | tdd-stub | `pytest tests/test_frontend.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | CORE-01 | T-XSS | textContent only | unit | `pytest tests/test_frontend.py::test_html_ids_present -x -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 3 | CORE-01, UX-01, UX-02 | T-XSS, T-Redirect | textContent, /files/ prefix check | unit | `pytest tests/test_frontend.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 4 | CORE-01 | — | N/A | unit | `pytest tests/test_frontend.py::test_index_html_served -x -q` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 4 | CORE-01, UX-01, UX-02 | — | Full flow | manual | Browser smoke test | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_frontend.py` — stubs RED para: test_index_html_served, test_app_js_served, test_html_ids_present, test_wav_size_formula
- [ ] `tests/conftest.py` — fixture `api_client` existente é reutilizada; nenhuma fixture nova necessária

*Framework (pytest + httpx TestClient) já operacional — nenhuma instalação adicional.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fluxo completo: submit → polling → done → result card | UX-01, UX-02 | Sem Playwright instalado; state machine JS não é testada por pytest | Abrir browser em `http://localhost:8000`, colar URL válida do YouTube (< 15 min), clicar "Baixar Beat", observar labels mudando, verificar card com BPM/key/Camelot/size, clicar "Baixar WAV" |
| Rate limit countdown ao vivo | CORE-01 | Requer 3 submits reais em 1 minuto | Submeter 4 jobs consecutivos; 4º deve mostrar countdown decrementando de `Retry-After` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
