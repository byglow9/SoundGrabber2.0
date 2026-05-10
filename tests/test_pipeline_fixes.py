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
        f"PIPE-02 fix missing: _FFMPEG_DIR={pipeline._FFMPEG_DIR!r} is not a directory. "
        "ffmpeg_location passed to yt-dlp must be the directory containing the binary."
    )


def test_pipe02_check_duration_uses_ffmpeg_dir():
    """PIPE-02: check_duration ydl_opts must use _FFMPEG_DIR (directory), not _FFMPEG_PATH."""
    src = inspect.getsource(pipeline.check_duration)
    assert "_FFMPEG_DIR" in src, (
        "PIPE-02 fix missing: check_duration must pass ffmpeg_location=_FFMPEG_DIR "
        "(directory), not _FFMPEG_PATH (binary). Update the ydl_opts dict."
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
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_pipe05_critical_log_when_cookies_missing_sentinel(caplog, tmp_path):
    """PIPE-05: lifespan must log CRITICAL if cookies.txt lacks __Secure-3PSID."""
    # Create a cookies.txt that is present but lacks the required sentinel
    fake_cookies = tmp_path / "cookies.txt"
    fake_cookies.write_text("# Netscape HTTP Cookie File\nexample.com\tFALSE\t/\tFALSE\t0\tSOME_COOKIE\tvalue\n")

    # Patch settings so lifespan reads our fake cookies file
    # Also set DEV_MODE to avoid Redis auth check raising RuntimeError
    with patch("api.main.settings") as mock_settings:
        mock_settings.redis_url = "redis://:password@localhost:6379/0"
        mock_settings.dev_mode = True
        mock_settings.cookies_path = str(fake_cookies)
        mock_settings.wav_ttl = 900

        with caplog.at_level(logging.CRITICAL, logger="api.main"):
            # Import app after patching — the lifespan runs on TestClient context entry
            from api.main import app
            with TestClient(app, raise_server_exceptions=False):
                pass

    critical_msgs = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    cookie_msgs = [r for r in critical_msgs if "3PSID" in r.message or "cookie" in r.message.lower()]
    assert len(cookie_msgs) >= 1, (
        "PIPE-05 fix missing: no CRITICAL log about __Secure-3PSID was emitted during lifespan. "
        "Add cookies validation to the lifespan function in api/main.py."
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
