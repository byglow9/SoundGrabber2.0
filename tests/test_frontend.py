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
    ]

    missing = []
    for element_id in required_ids:
        if f'id="{element_id}"' not in html_text:
            missing.append(element_id)

    assert not missing, (
        f"IDs ausentes no HTML: {missing}. "
        "Certifique-se de que static/index.html contém todos os IDs do UI-SPEC (Plan 02)."
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
