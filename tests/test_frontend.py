"""Frontend integration tests — Phase 4 (CORE-01, UX-01, UX-02)."""
from __future__ import annotations

import pytest


def test_index_html_served(api_client):
    """CORE-01: GET / retorna 200 com HTML contendo os IDs obrigatórios de input."""
    response = api_client.get("/")
    assert response.status_code == 200, (
        f"GET / esperava 200, recebeu {response.status_code}. "
        "Certifique-se de que GET / está montado em api/main.py (Plan 04)."
    )
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/html"), (
        f"Content-Type esperado 'text/html', recebeu '{content_type}'"
    )
    html_text = response.text
    assert 'id="url-input"' in html_text, "HTML deve conter id=\"url-input\""
    assert 'id="submit-btn"' in html_text, "HTML deve conter id=\"submit-btn\""


def test_app_js_served(api_client):
    """CORE-01: GET /static/app.js retorna 200 com Content-Type JavaScript."""
    response = api_client.get("/static/app.js")
    assert response.status_code == 200, (
        f"GET /static/app.js esperava 200, recebeu {response.status_code}. "
        "Certifique-se de que StaticFiles está montado e static/app.js existe (Plans 02 e 04)."
    )
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("application/javascript") or content_type.startswith("text/javascript"), (
        f"Content-Type esperado application/javascript ou text/javascript, recebeu '{content_type}'"
    )


def test_html_required_ids_present(api_client):
    """CORE-01: HTML de GET / contém todos os IDs obrigatórios do UI-SPEC."""
    response = api_client.get("/")
    assert response.status_code == 200, (
        f"GET / esperava 200, recebeu {response.status_code}. "
        "Certifique-se de que GET / está montado em api/main.py (Plan 04)."
    )
    html_text = response.text

    required_ids = [
        # IDs originais Phase 4 (16)
        "url-input",
        "submit-btn",
        "progress-area",
        "progress-label",
        "result-card",
        "bpm-value",
        "bpm-half-value",
        "bpm-double-value",
        "key-value",
        "camelot-value",
        "size-value",
        "download-link",
        "error-area",
        "error-message",
        "retry-btn",
        "validation-error",
        # IDs adicionais Phase 5 (11) — ausentes no HTML atual, RED até Plan 05-04
        "app",
        "header",
        "site-title",
        "site-tagline",
        "form-area",
        "duration-hint",
        "input-group",
        "result-bpm",
        "result-key",
        "result-size",
        "download-area",
    ]

    missing = []
    for element_id in required_ids:
        if f'id="{element_id}"' not in html_text:
            missing.append(element_id)

    assert not missing, (
        f"IDs ausentes no HTML: {missing}. "
        "Certifique-se de que static/index.html contém todos os 27 IDs do UI-SPEC (Plans 02 e 05-04)."
    )


def test_wav_size_formula():
    """UX-02: Fórmula de estimativa de tamanho WAV — pure Python, sem HTTP.

    Equivalente Python da fórmula JS: duration_sec * 44100 * 2 * 2 / 1_000_000
    Fonte: CONTEXT.md D-08 — 44100 Hz × 2 canais × 2 bytes (16-bit PCM).
    """

    def estimate_size_mb(duration_sec: float) -> float:
        return duration_sec * 44100 * 2 * 2 / 1_000_000

    # 5 minutos = 300s → 52.92 MB exatos
    assert abs(estimate_size_mb(300) - 52.92) < 0.01, (
        f"300s deve produzir ~52.92 MB, obteve {estimate_size_mb(300)}"
    )

    # 1 minuto = 60s → 10.584 MB
    assert estimate_size_mb(60) == pytest.approx(10.584, rel=1e-3), (
        f"60s deve produzir ~10.584 MB, obteve {estimate_size_mb(60)}"
    )

    # 0 segundos → 0 MB
    assert estimate_size_mb(0) == 0, (
        f"0s deve produzir 0 MB, obteve {estimate_size_mb(0)}"
    )

    # 10 minutos = 600s → 105.84 MB
    assert estimate_size_mb(600) == pytest.approx(105.84, rel=1e-3), (
        f"600s deve produzir ~105.84 MB, obteve {estimate_size_mb(600)}"
    )


def test_style_css_served(api_client):
    """VISUAL-02: GET /static/style.css retorna 200, Content-Type CSS.
    Contém paleta hex (#000000, #ff8800). Não contém CSS custom properties.
    RED antes do Plan 05-03. GREEN depois de static/style.css criado.
    """
    r = api_client.get("/static/style.css")
    assert r.status_code == 200, (
        f"GET /static/style.css esperava 200, recebeu {r.status_code}. "
        "Crie static/style.css (Plan 05-03)."
    )
    assert "text/css" in r.headers.get("content-type", ""), (
        f"Content-Type esperado text/css, recebeu '{r.headers.get('content-type')}'"
    )
    assert "#000000" in r.text, "style.css deve conter a cor de background #000000"
    assert "#ff8800" in r.text, "style.css deve conter a cor de acento #ff8800"
    assert "var(" not in r.text, (
        "style.css não deve conter CSS custom properties (var(--...)). "
        "Use hex brutas conforme CONTEXT.md §1."
    )


def test_css_no_modern_properties(api_client):
    """VISUAL-04: style.css não contém propriedades CSS modernas.
    Verifica ausência de: flex, grid, var(--, border-radius, box-shadow,
    transition:, animation:, transform:.
    RED antes do Plan 05-03. GREEN depois de static/style.css criado sem essas propriedades.
    """
    import os
    css_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static", "style.css"
    )
    if not os.path.exists(css_path):
        pytest.skip("static/style.css não criado ainda — aguardando Plan 05-03")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    forbidden = [
        "flex",
        "grid",
        "var(--",
        "border-radius",
        "box-shadow",
        "transition:",
        "animation:",
        "transform:",
    ]
    found = [prop for prop in forbidden if prop in css]
    assert not found, (
        f"Propriedades CSS modernas encontradas em style.css: {found}. "
        "Este projeto usa CSS Level 2 apenas (Y2K authenticity — CONTEXT.md §6)."
    )


def test_fonts_selfhosted(api_client):
    """VISUAL-03: Ambos os arquivos woff2 de fonte são servidos de /static/fonts/.
    RED antes do Plan 05-02. GREEN depois de static/fonts/*.woff2 existirem.
    """
    r1 = api_client.get("/static/fonts/DelaGothicOne-Regular.woff2")
    assert r1.status_code == 200, (
        f"GET /static/fonts/DelaGothicOne-Regular.woff2 esperava 200, recebeu {r1.status_code}. "
        "Execute o download da fonte (Plan 05-02)."
    )
    r2 = api_client.get("/static/fonts/Sligoil-Micro.woff2")
    assert r2.status_code == 200, (
        f"GET /static/fonts/Sligoil-Micro.woff2 esperava 200, recebeu {r2.status_code}. "
        "Execute o download da fonte (Plan 05-02)."
    )


def test_html_table_layout(api_client):
    """VISUAL-01 / VISUAL-04: HTML usa table layout.
    Contém <table. Não contém display: flex nem display: grid inline.
    RED antes do Plan 05-04. GREEN depois de static/index.html convertido.
    """
    r = api_client.get("/")
    assert r.status_code == 200, (
        f"GET / esperava 200, recebeu {r.status_code}."
    )
    html = r.text
    assert "<table" in html, (
        "HTML deve conter <table para layout Y2K autêntico (Plan 05-04). "
        "Atualmente usa div-based layout da Phase 4."
    )
    assert "display: flex" not in html, (
        "HTML não deve conter 'display: flex' inline — viola autenticidade Y2K (CONTEXT.md §3)."
    )
    assert "display: grid" not in html, (
        "HTML não deve conter 'display: grid' inline — viola autenticidade Y2K (CONTEXT.md §3)."
    )
