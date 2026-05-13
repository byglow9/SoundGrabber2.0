"""Tests for Phase 10.1 auth migration (AUTH-01).

Verifica que apos a migracao:
- ydl_opts usa cookiefile do Railway Volume (cache_dir/cookies.txt) quando existir
- ydl_opts NAO contem username=oauth2, extractor_args de bgutil, cookiefile hardcoded
- _check_oauth_cache loga CRITICAL nos casos esperados
- bgutil-ytdlp-pot-provider nao esta em requirements.txt
- BgutilUnavailable nao existe mais em pipeline.py

Todos os testes neste arquivo sao RED na Wave 0 — Wave 2 (Plan 03) os tornara GREEN.
"""
from __future__ import annotations

import inspect
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pipeline


def _make_fake_ydl(captured_opts: dict, info: dict):
    """Factory: retorna classe FakeYDL que captura ydl_opts e retorna info mockado."""
    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return info

        def download(self, urls):
            outtmpl = captured_opts["outtmpl"]
            Path(f"{outtmpl}.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
            return 0

    return FakeYDL


def test_check_duration_uses_cookiefile_from_cache_dir(tmp_path):
    """AUTH-01: check_duration deve usar cookiefile=cache_dir/cookies.txt quando existir."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", str(tmp_path))

    assert captured_opts.get("cookiefile") == str(cookies), (
        f"AUTH-01: cookiefile deveria ser {cookies!s}, obtido {captured_opts.get('cookiefile')!r}. "
        "check_duration deve usar cache_dir/cookies.txt como cookiefile."
    )
    assert "username" not in captured_opts, (
        "AUTH-01: username=oauth2 nao deve estar presente nos ydl_opts. "
        "OAuth2 foi removido do yt-dlp 2026.3.17."
    )
    assert "getpot_bgutil_baseurl" not in str(captured_opts.get("extractor_args", "")), (
        "AUTH-01: extractor_args de bgutil nao deve estar presente. "
        "Remover getpot_bgutil_baseurl conforme D-03/D-04."
    )


def test_check_duration_no_oauth2_in_ydl_opts(tmp_path):
    """AUTH-01: check_duration nao deve conter parametros OAuth2 (removido em yt-dlp 2026.3.17)."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", str(tmp_path))

    assert "username" not in captured_opts, (
        "AUTH-01: username nao deve estar em ydl_opts. "
        "OAuth2 (username=oauth2) foi removido do yt-dlp 2026.3.17 e levanta RuntimeError em runtime."
    )
    assert "password" not in captured_opts, (
        "AUTH-01: password nao deve estar em ydl_opts. "
        "OAuth2 foi removido do yt-dlp 2026.3.17."
    )
    # cachedir nao deve ser misturado com o path de cookies (D-02)
    assert captured_opts.get("cachedir") != str(tmp_path), (
        "AUTH-01: cachedir nao deve ser igual ao cache_dir do Volume. "
        "cookiefile e cachedir sao configuracoes distintas em yt-dlp."
    )


def test_check_duration_no_cookiefile_when_cache_dir_empty():
    """AUTH-01: check_duration sem cache_dir nao deve tentar settar cookiefile."""
    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", "")

    assert "cookiefile" not in captured_opts, (
        "AUTH-01: cookiefile nao deve ser setado quando cache_dir esta vazio. "
        "check_duration deve verificar cache_dir antes de construir o path do cookie."
    )
    assert "username" not in captured_opts, (
        "AUTH-01: username nao deve estar em ydl_opts mesmo quando cache_dir esta vazio."
    )


def test_download_audio_uses_cookiefile_from_cache_dir(tmp_path):
    """AUTH-01: download_audio deve usar cookiefile=cache_dir/cookies.txt quando existir."""
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        try:
            pipeline.download_audio("https://www.youtube.com/watch?v=test", str(tmp_path))
        except (FileNotFoundError, RuntimeError, OSError):
            pass  # FakeYDL cria WAV stub mas validate_wav pode falhar — irrelevante para este teste

    assert captured_opts.get("cookiefile") == str(cookies), (
        f"AUTH-01: cookiefile deveria ser {cookies!s}, obtido {captured_opts.get('cookiefile')!r}. "
        "download_audio deve usar cache_dir/cookies.txt como cookiefile."
    )
    assert (
        "retries" in captured_opts and captured_opts["retries"] == 3
    ), (
        f"AUTH-01: retries=3 deve estar preservado em ydl_opts. "
        f"Obtido: {captured_opts.get('retries')!r}"
    )
    assert (
        "fragment_retries" in captured_opts and captured_opts["fragment_retries"] == 3
    ), (
        f"AUTH-01: fragment_retries=3 deve estar preservado em ydl_opts. "
        f"Obtido: {captured_opts.get('fragment_retries')!r}"
    )
    extractor_args_str = str(captured_opts.get("extractor_args", ""))
    assert "getpot_bgutil_baseurl" not in extractor_args_str, (
        "AUTH-01: getpot_bgutil_baseurl nao deve estar em extractor_args de download_audio. "
        "Remover conforme D-03/D-04."
    )


def test_check_oauth_cache_critical_when_cache_dir_empty(caplog):
    """AUTH-01: _check_oauth_cache deve logar CRITICAL quando YTDLP_CACHE_DIR esta vazio."""
    try:
        from api.main import _check_oauth_cache
    except ImportError as exc:
        pytest.fail(
            f"AUTH-01: cannot import _check_oauth_cache from api.main: {exc}. "
            "Wave 2 (Plan 03) deve adicionar esta funcao em api/main.py."
        )

    with caplog.at_level(logging.CRITICAL, logger="api.main"):
        _check_oauth_cache("")

    critical_msgs = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    matching = [
        r for r in critical_msgs
        if "YTDLP_CACHE_DIR" in r.message or "cache_dir" in r.message.lower()
    ]
    assert len(matching) >= 1, (
        "AUTH-01: _check_oauth_cache deve logar CRITICAL mencionando 'YTDLP_CACHE_DIR' ou 'cache_dir' "
        "quando o argumento esta vazio. Nenhum log CRITICAL encontrado."
    )


def test_check_oauth_cache_critical_when_no_file(caplog, tmp_path):
    """AUTH-01: _check_oauth_cache deve logar CRITICAL quando cookies.txt nao existe no cache_dir."""
    try:
        from api.main import _check_oauth_cache
    except ImportError as exc:
        pytest.fail(
            f"AUTH-01: cannot import _check_oauth_cache from api.main: {exc}. "
            "Wave 2 (Plan 03) deve adicionar esta funcao em api/main.py."
        )

    # tmp_path existe mas nao contem cookies.txt
    with caplog.at_level(logging.CRITICAL, logger="api.main"):
        _check_oauth_cache(str(tmp_path))

    critical_msgs = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    matching = [
        r for r in critical_msgs
        if "cookies.txt" in r.message or "nao encontrado" in r.message.lower() or "not found" in r.message.lower()
    ]
    assert len(matching) >= 1, (
        "AUTH-01: _check_oauth_cache deve logar CRITICAL mencionando 'cookies.txt' ou 'nao encontrado' "
        "quando o arquivo nao existe no cache_dir. "
        f"Logs CRITICAL encontrados: {[r.message for r in critical_msgs]}"
    )


def test_requirements_no_bgutil():
    """AUTH-01: bgutil-ytdlp-pot-provider nao deve estar em requirements.txt (D-05)."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    assert req_path.exists(), (
        f"requirements.txt nao encontrado em {req_path}. "
        "O arquivo deve existir na raiz do projeto."
    )
    content = req_path.read_text()
    assert "bgutil-ytdlp-pot-provider" not in content, (
        "AUTH-01 D-05: bgutil-ytdlp-pot-provider ainda presente em requirements.txt. "
        "Remover a linha conforme D-05 (Wave 2, Plan 03)."
    )
    assert "bgutil" not in content.lower(), (
        "AUTH-01 D-05: referencia a 'bgutil' encontrada em requirements.txt. "
        "Remover completamente conforme D-05."
    )


def test_bgutil_unavailable_class_removed():
    """AUTH-01: BgutilUnavailable nao deve existir em pipeline.py apos a migracao (D-04)."""
    assert not hasattr(pipeline, "BgutilUnavailable"), (
        "AUTH-01 D-04: BgutilUnavailable ainda existe em pipeline.py. "
        "Remover a classe conforme D-04 (Wave 2, Plan 03). "
        "Testes PIPE-06 que dependiam desta classe foram substituidos por testes de ausencia."
    )
