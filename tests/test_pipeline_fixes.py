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
    """PIPE-05 (migrado a AUTH): _check_oauth_cache deve logar CRITICAL se cookies.txt nao tem __Secure-3PSID.

    Adaptado na Phase 10.1 Wave 2: _check_cookies foi substituida por _check_oauth_cache.
    O comportamento PIPE-05 (log CRITICAL quando sentinel ausente) e preservado na nova funcao.
    """
    # Create a cookies.txt that is present but lacks the required sentinel
    fake_cookies = tmp_path / "cookies.txt"
    fake_cookies.write_text("# Netscape HTTP Cookie File\nexample.com\tFALSE\t/\tFALSE\t0\tSOME_COOKIE\tvalue\n")

    # Call _check_oauth_cache directly — _check_cookies foi substituida na Phase 10.1 D-08.
    from api.main import _check_oauth_cache
    with caplog.at_level(logging.CRITICAL, logger="api.main"):
        _check_oauth_cache(str(tmp_path))

    critical_msgs = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    cookie_msgs = [r for r in critical_msgs if "3PSID" in r.message or "cookie" in r.message.lower() or "expirado" in r.message.lower()]
    assert len(cookie_msgs) >= 1, (
        "AUTH (ex-PIPE-05): nenhum log CRITICAL sobre __Secure-3PSID emitido por _check_oauth_cache. "
        "A funcao deve logar CRITICAL quando cookies.txt nao contem o sentinel __Secure-3PSID."
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


def test_bgutil_present_in_check_duration():
    """plan-06: check_duration deve conter getpot_bgutil_baseurl (reintroduzido no gap closure).

    A Wave 2 removeu bgutil; o gap closure plan 06 reintroduz via extractor_args para
    arquitetura hibrida (cookies do Volume + bgutil PO Token).
    """
    src = inspect.getsource(pipeline.check_duration)
    assert "getpot_bgutil_baseurl" in src, (
        "plan-06: getpot_bgutil_baseurl deve estar em check_duration. "
        "Gap closure plan 06 reintroduz bgutil via extractor_args para arquitetura hibrida."
    )


def test_bgutil_present_in_download_audio():
    """plan-06: download_audio deve conter getpot_bgutil_baseurl (reintroduzido no gap closure).

    Probe PIPE-06 (httpx.get) e BgutilUnavailable permanecem removidos — apenas
    o extractor_args com getpot_bgutil_baseurl e reintroduzido.
    """
    src = inspect.getsource(pipeline.download_audio)
    assert "getpot_bgutil_baseurl" in src, (
        "plan-06: getpot_bgutil_baseurl deve estar em download_audio. "
        "Gap closure plan 06 reintroduz bgutil via extractor_args."
    )
    assert "BgutilUnavailable" not in src, (
        "plan-06: BgutilUnavailable nao deve estar em download_audio. "
        "Probe Wave 2 mantido removido — apenas extractor_args e re-introduzido."
    )
    assert "httpx.get" not in src, (
        "plan-06: probe httpx.get nao deve estar em download_audio. "
        "Wave 2 removeu; gap closure plan 06 mantem removido."
    )


# ---------------------------------------------------------------------------
# PIPE-06 (plan-06) — verificar que o probe bgutil permanece removido em download_audio
# O probe httpx.get e BgutilUnavailable foram removidos na Wave 2 e permanecem
# removidos no gap closure plan 06. bgutil e re-introduzido apenas via extractor_args.
# ---------------------------------------------------------------------------
import pytest
from unittest.mock import patch, MagicMock


def test_pipe06_no_bgutil_probe_in_download_audio():
    """plan-06: probe bgutil (httpx.get) permanece removido em download_audio.

    Gap closure plan 06 reintroduz bgutil via extractor_args (getpot_bgutil_baseurl),
    mas NAO reintroduz o probe httpx.get nem a classe BgutilUnavailable.
    download_audio nao deve:
    - Fazer httpx.get para verificar disponibilidade do bgutil
    - Levantar BgutilUnavailable
    """
    src = inspect.getsource(pipeline.download_audio)
    assert "httpx.get" not in src, (
        "probe httpx.get nao deve estar em download_audio — Wave 2 removeu, plan 06 mantem removido. "
        "bgutil e configurado via extractor_args, sem probe de disponibilidade."
    )
    assert "BgutilUnavailable" not in src, (
        "BgutilUnavailable nao deve estar em download_audio. "
        "Wave 2 removeu a classe; gap closure plan 06 mantem removida."
    )
