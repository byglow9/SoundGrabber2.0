"""Tests for Phase 10.1 auth migration (AUTH-01) + gap closure plan 06 (hybrid auth).

Verifica arquitetura híbrida (plan 06):
- Com BGUTIL_BASE_URL setado: ydl_opts contem getpot_bgutil_baseurl E cookiefile (híbrido)
- Com BGUTIL_BASE_URL vazio: ydl_opts NAO contem getpot_bgutil_baseurl (fallback degradado)
- cookiefile continua presente quando cache_dir/cookies.txt existe (Volume path preservado)
- _check_oauth_cache loga CRITICAL nos casos esperados
- BgutilUnavailable nao existe em pipeline.py (probe Wave 2 mantido removido)
- import httpx ausente em pipeline.py (probe mantido removido)
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


def _assert_writable_cookie_copy(captured_opts: dict, original: Path) -> None:
    cookiefile = captured_opts.get("cookiefile")
    assert cookiefile, "cookiefile deveria estar presente nos ydl_opts"
    assert cookiefile != str(original), (
        "cookiefile deve ser copia temporaria gravavel, nao o cookies.txt original montado :ro"
    )
    assert Path(cookiefile).name.startswith("sg_cookies_")
    assert str(cookiefile).startswith("/tmp/")
    assert original.exists(), "cookies.txt original deve permanecer intacto"


def test_check_duration_uses_cookiefile_from_cache_dir(tmp_path, monkeypatch):
    """AUTH-01/plan-06: check_duration deve usar cookiefile=cache_dir/cookies.txt quando existir.

    Sem BGUTIL_BASE_URL: cookiefile presente, getpot_bgutil_baseurl ausente (fallback degradado).
    """
    monkeypatch.delenv("BGUTIL_BASE_URL", raising=False)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", str(tmp_path))

    _assert_writable_cookie_copy(captured_opts, cookies)
    assert "username" not in captured_opts, (
        "AUTH-01: username=oauth2 nao deve estar presente nos ydl_opts. "
        "OAuth2 foi removido do yt-dlp 2026.3.17."
    )
    # Sem BGUTIL_BASE_URL: bgutil NAO deve estar presente (fallback degradado)
    assert "getpot_bgutil_baseurl" not in str(captured_opts.get("extractor_args", "")), (
        "plan-06: sem BGUTIL_BASE_URL, getpot_bgutil_baseurl nao deve estar em extractor_args."
    )


def test_check_duration_hybrid_with_bgutil_and_cookies(tmp_path, monkeypatch):
    """plan-06: check_duration deve conter AMBOS cookiefile E getpot_bgutil_baseurl quando bgutil presente.

    Verifica convivencia hibrida: cookies do Volume (identidade) + bgutil (PO Token JS challenge).
    """
    monkeypatch.setenv("BGUTIL_BASE_URL", "https://bgutil-test.example.com")
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", str(tmp_path))

    _assert_writable_cookie_copy(captured_opts, cookies)
    youtube_args = captured_opts.get("extractor_args", {}).get("youtube", {})
    assert youtube_args.get("getpot_bgutil_baseurl") == ["https://bgutil-test.example.com"], (
        f"plan-06: getpot_bgutil_baseurl deveria estar em extractor_args.youtube. "
        f"extractor_args obtido: {captured_opts.get('extractor_args')!r}"
    )
    assert youtube_args.get("player_client") == ["web_safari", "web"], (
        "plan-06: player_client=web_safari,web deve ser usado quando bgutil presente."
    )


def test_check_duration_no_bgutil_when_env_empty(monkeypatch, tmp_path):
    """plan-06: check_duration sem BGUTIL_BASE_URL nao deve incluir getpot_bgutil_baseurl."""
    monkeypatch.setenv("BGUTIL_BASE_URL", "")
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        pipeline.check_duration("https://www.youtube.com/watch?v=test", str(tmp_path))

    assert "getpot_bgutil_baseurl" not in str(captured_opts.get("extractor_args", "")), (
        "plan-06: sem BGUTIL_BASE_URL, getpot_bgutil_baseurl nao deve estar presente."
    )
    youtube_args = captured_opts.get("extractor_args", {}).get("youtube", {})
    assert youtube_args.get("player_client") == ["android"], (
        "plan-06: player_client=android (fallback degradado) deve ser usado quando bgutil ausente."
    )


def test_check_duration_no_oauth2_in_ydl_opts(tmp_path, monkeypatch):
    """AUTH-01: check_duration nao deve conter parametros OAuth2 (removido em yt-dlp 2026.3.17)."""
    monkeypatch.delenv("BGUTIL_BASE_URL", raising=False)
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


def test_check_duration_no_cookiefile_when_cache_dir_empty(monkeypatch):
    """AUTH-01: check_duration sem cache_dir nao deve tentar settar cookiefile."""
    monkeypatch.delenv("BGUTIL_BASE_URL", raising=False)
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


def test_download_audio_uses_cookiefile_from_cache_dir(tmp_path, monkeypatch):
    """AUTH-01/plan-06: download_audio deve usar cookiefile=cache_dir/cookies.txt quando existir.

    Sem BGUTIL_BASE_URL: cookiefile presente, getpot_bgutil_baseurl ausente (fallback degradado).
    """
    monkeypatch.delenv("BGUTIL_BASE_URL", raising=False)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        try:
            pipeline.download_audio("https://www.youtube.com/watch?v=test", str(tmp_path))
        except (FileNotFoundError, RuntimeError, OSError):
            pass  # FakeYDL cria WAV stub mas validate_wav pode falhar — irrelevante para este teste

    _assert_writable_cookie_copy(captured_opts, cookies)
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
    # Sem BGUTIL_BASE_URL: bgutil NAO deve estar presente
    extractor_args_str = str(captured_opts.get("extractor_args", ""))
    assert "getpot_bgutil_baseurl" not in extractor_args_str, (
        "plan-06: sem BGUTIL_BASE_URL, getpot_bgutil_baseurl nao deve estar em extractor_args de download_audio."
    )


def test_download_audio_hybrid_with_bgutil_and_cookies(tmp_path, monkeypatch):
    """plan-06: download_audio deve conter AMBOS cookiefile E getpot_bgutil_baseurl quando bgutil presente."""
    monkeypatch.setenv("BGUTIL_BASE_URL", "https://bgutil-test.example.com")
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    captured_opts: dict = {}
    FakeYDL = _make_fake_ydl(captured_opts, {"duration": 180, "title": "test"})

    with patch("pipeline.yt_dlp.YoutubeDL", FakeYDL):
        try:
            pipeline.download_audio("https://www.youtube.com/watch?v=test", str(tmp_path))
        except (FileNotFoundError, RuntimeError, OSError):
            pass

    _assert_writable_cookie_copy(captured_opts, cookies)
    youtube_args = captured_opts.get("extractor_args", {}).get("youtube", {})
    assert youtube_args.get("getpot_bgutil_baseurl") == ["https://bgutil-test.example.com"], (
        f"plan-06: getpot_bgutil_baseurl deveria estar em extractor_args.youtube de download_audio. "
        f"extractor_args obtido: {captured_opts.get('extractor_args')!r}"
    )
    assert youtube_args.get("player_client") == ["web_safari", "web"], (
        "plan-06: player_client=web_safari,web deve ser usado em download_audio quando bgutil presente."
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


def test_requirements_has_bgutil():
    """plan-06: bgutil-ytdlp-pot-provider==0.8.1 deve estar em requirements.txt (alinhado ao servidor)."""
    req_path = Path(__file__).parent.parent / "requirements.txt"
    assert req_path.exists(), (
        f"requirements.txt nao encontrado em {req_path}. "
        "O arquivo deve existir na raiz do projeto."
    )
    content = req_path.read_text()
    assert "bgutil-ytdlp-pot-provider==0.8.1" in content, (
        "plan-06: bgutil-ytdlp-pot-provider==0.8.1 deve estar em requirements.txt. "
        "Re-adicionado no gap closure plan 06 para arquitetura hibrida (cookies + bgutil)."
    )


def test_bgutil_unavailable_class_removed():
    """plan-06: BgutilUnavailable NAO deve existir em pipeline.py.

    O probe PIPE-06 (httpx.get) e a classe BgutilUnavailable foram removidos na Wave 2
    e permanecem removidos no gap closure plan 06. bgutil e re-introduzido apenas via
    extractor_args (getpot_bgutil_baseurl) — sem probe de disponibilidade, sem exception class.
    """
    assert not hasattr(pipeline, "BgutilUnavailable"), (
        "plan-06: BgutilUnavailable nao deve existir em pipeline.py. "
        "Wave 2 removeu o probe e a classe; gap closure plan 06 mantem removidos. "
        "bgutil e usado via extractor_args, sem classe de exception dedicada."
    )


def test_no_httpx_import_in_pipeline():
    """plan-06: import httpx nao deve estar em pipeline.py (probe mantido removido).

    O probe bgutil original usava httpx.get. Wave 2 removeu; gap closure plan 06 mantem removido.
    bgutil e configurado via extractor_args — sem probe de disponibilidade.
    """
    pipeline_src = inspect.getsource(pipeline)
    # Verificar ausencia de 'import httpx' no nivel do modulo
    lines = pipeline_src.split("\n")
    top_level_httpx = [l for l in lines if l.strip() == "import httpx"]
    assert not top_level_httpx, (
        "plan-06: 'import httpx' nao deve estar em pipeline.py. "
        "Wave 2 removeu o probe httpx.get; gap closure plan 06 mantem removido."
    )
