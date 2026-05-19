"""Shared pytest fixtures for SoundGrabber pipeline tests."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Point Celery and the api module-level Redis client to the local dev Redis
# (no auth, started on port 6380). Must run before any api.* import.
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("DEV_MODE", "true")  # SEC-INFRA-01: bypassa Redis auth check em testes (D-06)
os.environ.setdefault("ADMIN_PASSWORD", "correct horse")
os.environ.setdefault("ADMIN_SESSION_SECRET", "test-secret-for-signed-cookie")


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
    """FastAPI TestClient with Celery in eager mode (no broker required for unit tests).

    task_eager_propagates=False: task exceptions are stored in the result backend so
    POST /jobs always returns 202 even if the task fails immediately.  Individual tests
    that want a specific failure mode (e.g. test_failed_job_returns_sanitized_error)
    patch api.tasks.check_duration themselves, which overrides this fixture's mock.

    Rate limit keys (LIMITS:LIMITER*) are flushed before each test so that slowapi
    counters do not leak across tests and cause 429s on the first request.
    """
    import redis as redis_lib
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    from fastapi.testclient import TestClient
    from api.tasks import celery_app
    from api.main import app

    # Flush rate-limit keys before each test to prevent cross-test contamination.
    # WR-04: usa SCAN (não-bloqueante, O(1) por iteração) em vez de KEYS (O(N) bloqueante).
    # Silencia erros de conexão — Redis pode estar indisponível no host (predeploy fora do Docker).
    try:
        _r = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6380/0"),
            decode_responses=True,
            socket_connect_timeout=1,
        )
        cursor = 0
        while True:
            cursor, keys = _r.scan(cursor, match="LIMITS:LIMITER*", count=100)
            if keys:
                _r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass  # Redis indisponível no host durante predeploy — sem estado residual a limpar

    # Troca o limiter para memory storage — REDIS_URL pode apontar para hostname
    # Docker-only (redis:6379) que não resolve no host durante predeploy.
    # O middleware do slowapi usa request.app.state.limiter em cada request, então
    # trocar aqui é suficiente; os @limiter.limit() decorators continuam funcionando.
    _orig_limiter = app.state.limiter
    app.state.limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False  # exceptions stored, not propagated
    celery_app.conf.task_store_eager_result = True  # persist results to backend so AsyncResult works

    client = TestClient(app)
    # Prevent real yt-dlp network calls during unit tests; individual tests that need a
    # specific failure (ValidationError, etc.) patch check_duration themselves.
    with patch("api.tasks.check_duration", side_effect=RuntimeError("mock: no network in unit tests")):
        yield client

    app.state.limiter = _orig_limiter
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False
