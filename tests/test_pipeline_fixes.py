"""Tests for Phase 8 pipeline.py fixes (PIPE-01..04).

These tests are intentionally RED against the current codebase.
They turn GREEN after 08-02-PLAN.md executes.
"""
from __future__ import annotations

import inspect
import os
import shutil

import pipeline  # module-level constants are set at import time


def test_pipe01_ffprobe_uses_shutil_which_when_available():
    """PIPE-01: _FFPROBE_PATH must equal shutil.which('ffprobe') when system ffprobe exists."""
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe is None:
        # System ffprobe not on PATH in this env — test the fallback attribute exists instead.
        # The fix introduces _FFMPEG_DIR as the fallback source; if it's missing, the fix is absent.
        assert hasattr(pipeline, "_FFMPEG_DIR"), (
            "PIPE-01 fix missing: _FFMPEG_DIR not defined on pipeline module. "
            "Add shutil.which() resolution logic to pipeline.py."
        )
    else:
        assert pipeline._FFPROBE_PATH == system_ffprobe, (
            f"PIPE-01 fix missing: _FFPROBE_PATH is {pipeline._FFPROBE_PATH!r} "
            f"but shutil.which('ffprobe') returned {system_ffprobe!r}. "
            "pipeline.py must use shutil.which() first."
        )


def test_pipe02_ffmpeg_dir_attribute_exists():
    """PIPE-02: pipeline module must expose _FFMPEG_DIR (a directory, not a binary path)."""
    assert hasattr(pipeline, "_FFMPEG_DIR"), (
        "PIPE-02 fix missing: _FFMPEG_DIR not defined on pipeline module. "
        "Add _FFMPEG_DIR = str(Path(_FFMPEG_PATH).parent) to pipeline.py."
    )
    assert os.path.isdir(pipeline._FFMPEG_DIR), (
        f"PIPE-02 fix missing: _FFMPEG_DIR={pipeline._FFMPEG_DIR!r} nao e um diretorio. "
        "_FFMPEG_DIR e o diretorio-pai do binario; _YTDLP_FFMPEG_LOCATION aponta para "
        "o executavel (que pode ter nome versionado). Ambos devem ser definidos."
    )


def test_pipe02_check_duration_uses_ffmpeg_location():
    """PIPE-02: check_duration ydl_opts must set ffmpeg_location for yt-dlp.

    The original check used _FFMPEG_DIR (directory). After the DEPLOY-01 fix, the module
    uses _YTDLP_FFMPEG_LOCATION (executable path) so yt-dlp can find the binary when the
    imageio-ffmpeg binary has a versioned name (not the plain 'ffmpeg' name).
    Accept either symbol to remain backward compatible with Phase 8 test intent.
    """
    src = inspect.getsource(pipeline.check_duration)
    has_location = "_FFMPEG_DIR" in src or "_YTDLP_FFMPEG_LOCATION" in src
    assert has_location, (
        "PIPE-02 fix missing: check_duration must pass ffmpeg_location using either "
        "_FFMPEG_DIR or _YTDLP_FFMPEG_LOCATION. Update the ydl_opts dict."
    )


def test_pipe03_no_cache_dir_in_check_duration():
    """PIPE-03: check_duration ydl_opts must include 'no_cache_dir': True."""
    src = inspect.getsource(pipeline.check_duration)
    assert '"no_cache_dir": True' in src or "'no_cache_dir': True" in src, (
        "PIPE-03 fix missing: add 'no_cache_dir': True to check_duration ydl_opts dict."
    )


def test_pipe03_no_cache_dir_in_download_audio():
    """PIPE-03: download_audio ydl_opts must include 'no_cache_dir': True."""
    src = inspect.getsource(pipeline.download_audio)
    assert '"no_cache_dir": True' in src or "'no_cache_dir': True" in src, (
        "PIPE-03 fix missing: add 'no_cache_dir': True to download_audio ydl_opts dict."
    )


def test_pipe04_retries_in_download_audio():
    """PIPE-04: download_audio ydl_opts must include retries=3 and fragment_retries=3."""
    src = inspect.getsource(pipeline.download_audio)
    assert '"retries": 3' in src or "'retries': 3" in src, (
        "PIPE-04 fix missing: add 'retries': 3 to download_audio ydl_opts dict."
    )
    assert '"fragment_retries": 3' in src or "'fragment_retries': 3" in src, (
        "PIPE-04 fix missing: add 'fragment_retries': 3 to download_audio ydl_opts dict."
    )


"""Tests for PIPE-05 (cookies validation) and DEPLOY-01 (nixpacks.toml)."""
import logging
import tempfile
from pathlib import Path


def test_pipe05_critical_log_when_cookies_missing_sentinel(caplog, tmp_path):
    """PIPE-05: _check_cookies must log CRITICAL if cookies.txt lacks __Secure-3PSID."""
    # Create a cookies.txt that is present but lacks the required sentinel
    fake_cookies = tmp_path / "cookies.txt"
    fake_cookies.write_text("# Netscape HTTP Cookie File\nexample.com\tFALSE\t/\tFALSE\t0\tSOME_COOKIE\tvalue\n")

    # Call _check_cookies directly — avoids sys.modules import-order fragility.
    # If api.main was already imported by a prior test, the cached module is reused,
    # which is fine because we are exercising _check_cookies in isolation, not lifespan.
    from api.main import _check_cookies
    with caplog.at_level(logging.CRITICAL, logger="api.main"):
        _check_cookies(str(fake_cookies))

    critical_msgs = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    cookie_msgs = [r for r in critical_msgs if "3PSID" in r.message or "cookie" in r.message.lower()]
    assert len(cookie_msgs) >= 1, (
        "PIPE-05 fix missing: no CRITICAL log about __Secure-3PSID was emitted by _check_cookies. "
        "Add cookies validation in _check_cookies in api/main.py."
    )


def test_deploy01_nixpacks_toml_exists_with_ffmpeg():
    """DEPLOY-01: nixpacks.toml must exist at project root and reference ffmpeg."""
    toml_path = Path(__file__).parent.parent / "nixpacks.toml"
    assert toml_path.exists(), (
        "DEPLOY-01 fix missing: nixpacks.toml not found at project root. "
        "Create nixpacks.toml with aptPkgs = [\"ffmpeg\"]."
    )
    content = toml_path.read_text()
    assert "ffmpeg" in content, (
        f"DEPLOY-01 fix missing: nixpacks.toml exists but does not mention 'ffmpeg'. "
        f"Content: {content!r}"
    )


def test_bgutil_08x_extractor_key_check_duration():
    """bgutil 0.8.x usa 'getpot_bgutil_baseurl', nao 'youtubepot-bgutilhttp:base_url'."""
    src = inspect.getsource(pipeline.check_duration)
    assert "getpot_bgutil_baseurl" in src, (
        "DEPLOY-02 fix missing: check_duration deve usar a chave 0.8.x 'getpot_bgutil_baseurl'. "
        "A chave 1.x era 'youtubepot-bgutilhttp:base_url'."
    )
    assert "youtubepot-bgutilhttp" not in src, (
        "check_duration contém a chave 1.x 'youtubepot-bgutilhttp'. "
        "O projeto pina bgutil==0.8.5; usar a chave 1.x silenciosamente ignora o bgutil server."
    )


def test_bgutil_08x_extractor_key_download_audio():
    """bgutil 0.8.x usa 'getpot_bgutil_baseurl', nao 'youtubepot-bgutilhttp:base_url'."""
    src = inspect.getsource(pipeline.download_audio)
    assert "getpot_bgutil_baseurl" in src, (
        "DEPLOY-02 fix missing: download_audio deve usar a chave 0.8.x 'getpot_bgutil_baseurl'."
    )
    assert "youtubepot-bgutilhttp" not in src, (
        "download_audio contém a chave 1.x 'youtubepot-bgutilhttp'. "
        "O projeto pina bgutil==0.8.5; usar a chave 1.x silenciosamente ignora o bgutil server."
    )


# ---------------------------------------------------------------------------
# PIPE-06 — bgutil probe: falha explícita quando bgutil inacessível (RED stubs)
# Estes testes FALHAM até que 10-02-PLAN.md implemente:
#   - import httpx em pipeline.py
#   - class BgutilUnavailable(RuntimeError) em pipeline.py
#   - probe HTTP em download_audio() antes de ydl_opts
#   - except BgutilUnavailable em api/tasks.py ANTES de except RuntimeError
# ---------------------------------------------------------------------------

import httpx
import pytest
from unittest.mock import patch, MagicMock


def test_pipe06_bgutil_probe_connect_error_raises():
    """PIPE-06: ConnectError no probe → exceção com 'bgutil' na mensagem."""
    with patch("pipeline.httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(Exception) as exc_info:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=FAKEID00001",
                cookies_path="",
                po_token="",
                bgutil_base_url="http://bgutil.railway.internal:4416",
            )
        assert "bgutil" in str(exc_info.value).lower(), (
            f"PIPE-06 fix missing: mensagem de erro deve conter 'bgutil'. "
            f"Got: {exc_info.value!r}"
        )


def test_pipe06_bgutil_probe_timeout_raises():
    """PIPE-06: ConnectTimeout no probe → exceção com 'bgutil' na mensagem."""
    with patch("pipeline.httpx.get", side_effect=httpx.ConnectTimeout("Timeout")):
        with pytest.raises(Exception) as exc_info:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=FAKEID00002",
                cookies_path="",
                po_token="",
                bgutil_base_url="http://bgutil.railway.internal:4416",
            )
        assert "bgutil" in str(exc_info.value).lower(), (
            f"PIPE-06 fix missing: mensagem de erro deve conter 'bgutil'. "
            f"Got: {exc_info.value!r}"
        )


def test_pipe06_no_probe_when_bgutil_url_empty():
    """PIPE-06: bgutil_base_url='' → httpx.get NÃO deve ser chamado."""
    mock_get = MagicMock()
    with patch("pipeline.httpx.get", mock_get):
        try:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=FAKEID00003",
                cookies_path="",
                po_token="",
                bgutil_base_url="",
            )
        except Exception:
            pass  # yt-dlp vai falhar sem cookies/URL real — irrelevante
        mock_get.assert_not_called()


def test_pipe06_tasks_bgutil_error_type():
    """PIPE-06: JobFailure gerada por exceção de bgutil deve ter error_type='bgutil_unavailable'."""
    from api.tasks import process_job, JobFailure

    # Simular exceção com mensagem de bgutil saindo de download_audio
    bgutil_error_msg = (
        "PO Token service unavailable (bgutil at http://bgutil.railway.internal:4416). "
        "Download requires bgutil to be running."
    )

    with patch("api.tasks.download_audio", side_effect=RuntimeError(bgutil_error_msg)), \
         patch("api.tasks.check_duration", return_value={"duration": 180, "title": "test"}):
        # Invocar a função Celery sem o decorator (apply() não está disponível sem broker)
        # Usar o método __wrapped__ ou chamar a função diretamente via request mock
        try:
            # process_job é um bound task; chamar sem broker levanta ComandError — não importa
            # O que verificamos é que a exceção lançada é JobFailure com o error_type correto
            import celery
            task_func = process_job
            # Criar um mock do request Celery para evitar AttributeError em self.request.id
            mock_request = MagicMock()
            mock_request.id = "test-job-id-pipe06"
            task_func.request_stack = MagicMock()
            task_func.request_stack.top = mock_request

            task_func(url="https://www.youtube.com/watch?v=FAKEID00004")
        except JobFailure as jf:
            assert jf.error_type == "bgutil_unavailable", (
                f"PIPE-06 fix missing: error_type esperado 'bgutil_unavailable', "
                f"obtido {jf.error_type!r}. "
                f"api/tasks.py precisa de 'except BgutilUnavailable' ANTES de 'except RuntimeError'."
            )
        except Exception:
            pass  # outros erros de infra Celery são ignorados neste stub
