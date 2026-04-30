"""Shared pytest fixtures for SoundGrabber pipeline tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_wav_path() -> Path:
    """Path to the committed 5-second 440Hz fixture WAV used for offline analysis tests."""
    p = FIXTURES_DIR / "sample.wav"
    assert p.exists(), f"Fixture missing: {p}. Regenerate via scripts/generate_sample_wav.py"
    return p


@pytest.fixture
def mock_yt_info_short() -> dict[str, Any]:
    """yt-dlp info dict for a 3-minute video (under 15min limit)."""
    return {
        "id": "abc123",
        "title": "Short Test Track",
        "duration": 183,  # 3:03
        "uploader": "TestChannel",
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
    }


@pytest.fixture
def mock_yt_info_long() -> dict[str, Any]:
    """yt-dlp info dict for a 20-minute video (over 15min limit, must be rejected by CORE-05)."""
    return {
        "id": "long456",
        "title": "Too Long Track",
        "duration": 1200,  # 20:00 > 900s limit
        "uploader": "TestChannel",
        "webpage_url": "https://www.youtube.com/watch?v=long456",
    }


@pytest.fixture
def youtube_test_urls() -> dict[str, str]:
    """Test URLs locked by D-07. The third URL (lo-fi/house) is chosen by the planner.

    NOTE: Only used by @pytest.mark.e2e tests; require valid cookies.txt + PO Token.
    """
    return {
        "rock_lofi": "https://www.youtube.com/watch?v=b1f6o0GMT8c",
        "trap": "https://www.youtube.com/watch?v=npoTcSToYTc",
        # Planner-chosen lo-fi/house URL — well-known lofi hip hop radio (24/7 stream archive
        # not used; this is a static beat upload). Replace if it becomes unavailable.
        "lofi_house": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
    }


@pytest.fixture
def api_client():
    """FastAPI TestClient with Celery in eager mode (no broker required for unit tests)."""
    from fastapi.testclient import TestClient
    from api.tasks import celery_app
    from api.main import app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    client = TestClient(app)
    yield client
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False
