---
phase: 5
slug: visual-identity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` (raiz do projeto) |
| **Quick run command** | `.venv/bin/pytest tests/test_frontend.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_frontend.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 0 | VISUAL-01, VISUAL-02, VISUAL-03, VISUAL-04 | — | N/A | unit | `.venv/bin/pytest tests/test_frontend.py -v -x` | ❌ Wave 0 | ⬜ pending |
| 5-02-01 | 02 | 1 | VISUAL-03 | — | N/A | unit (filesystem) | `.venv/bin/pytest tests/test_frontend.py::test_fonts_selfhosted -x` | ❌ Wave 0 | ⬜ pending |
| 5-03-01 | 03 | 2 | VISUAL-01, VISUAL-02, VISUAL-04 | — | N/A | unit (content) | `.venv/bin/pytest tests/test_frontend.py::test_style_css_served tests/test_frontend.py::test_css_no_modern_properties -x` | ❌ Wave 0 | ⬜ pending |
| 5-04-01 | 04 | 3 | VISUAL-01, VISUAL-04 | — | N/A | unit (HTTP) | `.venv/bin/pytest tests/test_frontend.py::test_html_table_layout tests/test_frontend.py::test_html_required_ids_present -x` | ❌ W0 (expand) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_frontend.py::test_style_css_served` — GET /static/style.css retorna 200 com Content-Type text/css; body contém `#000000` e `#ff8800`; não contém `var(`
- [ ] `tests/test_frontend.py::test_css_no_modern_properties` — lê static/style.css diretamente e verifica ausência de `flex`, `grid`, `var(--`, `border-radius`, `box-shadow`, `transition`, `animation`, `transform`
- [ ] `tests/test_frontend.py::test_fonts_selfhosted` — GET /static/fonts/DelaGothicOne-Regular.woff2 e /static/fonts/Sligoil-Micro.woff2 retornam 200
- [ ] `tests/test_frontend.py::test_html_table_layout` — HTML de GET / contém `<table` e não contém `display: flex` nem `display: grid`
- [ ] Expandir `test_html_required_ids_present` — cobrir todos os 27 IDs obrigatórios (atualmente verifica apenas 16)

*Todos os 5 stubs acima devem ser criados no Wave 0 (estado RED inicial).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Autenticidade visual — desenvolvedor desconhecido deve acreditar que o HTML foi escrito em 2002 | VISUAL-01 | Julgamento estético subjetivo; nenhum grep pode verificar "parece Y2K" | Abrir `/static/index.html` raw source num browser; observar: (1) table layout visível, (2) atributos HTML de época (`align`, `cellpadding`), (3) hex colors brutas no CSS, (4) ausência de classes utilitárias modernas |
| Renderização das fontes (Dela Gothic One + Sligoil) sem font-smoothing | VISUAL-03 | Requer inspeção visual no browser | Abrir a página no browser; inspecionar título e valores de BPM para confirmar renderização pixel/bitmap sem suavização |
| Estados hover/focus funcionando (borda laranja no input, botão escurece) | VISUAL-01 | Requer interação manual | Focar o `#url-input` e confirmar borda muda para `#ff6600`; hover em `#submit-btn` e confirmar bg muda para `#ff6600` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
