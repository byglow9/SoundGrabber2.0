"""Frontend integration tests — Phase 4 (CORE-01, UX-01, UX-02)."""
from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    assert 'href="/sobre"' in html_text, "Home deve linkar para a pagina Sobre"


def test_about_page_served_with_legal_and_privacy_sections(api_client):
    """Pagina Sobre publica reune proposito, aviso legal e privacidade."""
    response = api_client.get("/sobre")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/html")
    html_text = response.text
    assert "O que é o SoundGrabber" in html_text
    assert 'id="aviso-legal"' in html_text
    assert 'id="privacidade"' in html_text
    assert "Google Analytics 4" in html_text
    assert "google.com/policies/privacy/partners" in html_text


def test_privacy_legacy_page_still_served(api_client):
    """URL antiga de privacidade continua acessivel para compatibilidade."""
    response = api_client.get("/static/privacy.html")

    assert response.status_code == 200
    assert "Política de Privacidade" in response.text
    assert "/sobre#privacidade" in response.text


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


def test_open_graph_meta_tags_present():
    """Home deve declarar preview social para WhatsApp/Open Graph."""
    html_text = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'property="og:title" content="SoundGrabber"' in html_text
    assert 'property="og:image" content="https://soundgrabber.com.br/static/og-image.png"' in html_text
    assert 'property="og:image:width" content="1221"' in html_text
    assert 'property="og:image:height" content="562"' in html_text
    assert 'name="twitter:card" content="summary_large_image"' in html_text


def test_open_graph_image_served(api_client):
    """Imagem de preview social usada por WhatsApp/Open Graph deve estar publica."""
    response = api_client.get("/static/og-image.png")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/png")


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


def test_css_no_unapproved_modern_properties(api_client):
    """style.css evita APIs modernas que quebram o contrato visual atual."""
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
        "grid",
        "var(--",
        "border-radius",
        "box-shadow",
        "transition:",
        "animation:",
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


# ---------------------------------------------------------------------------
# Phase 11: Som da Semana public sidebar static contract
# ---------------------------------------------------------------------------

def test_public_page_does_not_link_yonkou(api_client):
    """D-01e/T-11-04: pagina publica nao revela o painel operador /yonkou."""
    response = api_client.get("/")

    assert response.status_code == 200, (
        f"GET / deveria retornar HTML publico, recebeu {response.status_code}: {response.text}"
    )
    assert "/yonkou" not in response.text
    assert "yonkou" not in response.text.lower()
    assert "Entrar no painel" not in response.text


def test_featured_sidebar_static_contract():
    """D-02/D-05: HTML e JS declaram sidebar injetada somente com conteudo."""
    index_html = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="featured-sidebar"' in index_html or "featured-sidebar" in app_js
    assert 'id="featured-card"' in index_html or "featured-card" in app_js
    assert 'id="featured-title"' in index_html or "featured-title" in app_js
    assert 'id="featured-separator"' in index_html or "featured-separator" in app_js
    assert "featured-link" in index_html or "featured-link" in app_js
    assert "fetch('/featured')" in app_js or 'fetch("/featured")' in app_js
    assert "SOM DA SEMANA" in app_js or "SOM DA SEMANA" in index_html
    assert "----" in app_js or "featured-separator" in app_js
    assert "textContent" in app_js
    assert "innerHTML" not in app_js, (
        "static/app.js nao deve usar innerHTML; conteudo featured deve ser renderizado com textContent"
    )


def test_featured_links_are_noopener_blank():
    """D-04/T-11-05: links featured abrem em nova aba sem opener."""
    app_js = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "featured-link" in app_js
    assert ".target" in app_js or "setAttribute('target'" in app_js or 'setAttribute("target"' in app_js
    assert "_blank" in app_js
    assert ".rel" in app_js or "setAttribute('rel'" in app_js or 'setAttribute("rel"' in app_js
    assert "noopener" in app_js
    assert "textContent" in app_js


def test_featured_sidebar_css_contract():
    """D-05: CSS adiciona sidebar 220px, paleta phpBB e sem propriedades modernas."""
    css = (PROJECT_ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "#featured-sidebar" in css
    assert "#featured-card" in css
    assert ".featured-link" in css
    assert "#ff8800" in css
    assert "#804400" in css
    assert "220px" in css
    assert "1px solid #ff8800" in css

    forbidden = [
        "display: grid",
        "display:grid",
        "var(--",
        "border-radius",
        "box-shadow",
        "transition:",
        "animation:",
    ]
    found = [prop for prop in forbidden if prop in css]
    assert not found, (
        f"Propriedades CSS modernas encontradas em style.css: {found}. "
        "A sidebar deve preservar a estetica Y2K/CSS2."
    )
