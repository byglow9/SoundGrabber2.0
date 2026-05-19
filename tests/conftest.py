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
    import fakeredis
    from limits.storage import MemoryStorage

    from fastapi.testclient import TestClient
    from api.tasks import celery_app
    import api.main as _main
    from api.main import app, limiter as _api_limiter

    # fakeredis: substitui _redis por Redis em memória — sem rede, sem Docker.
    # Necessário porque alguns endpoints chamam _redis.set/get/llen diretamente,
    # e REDIS_URL no servidor aponta para hostname Docker-only (redis:6379).
    _fake = fakeredis.FakeRedis(decode_responses=True)
    _orig_redis = _main._redis
    _main._redis = _fake

    # Os decorators @limiter.limit() capturam o objeto module-level `limiter` diretamente
    # e chamam limiter._limiter.storage.incr(). Patchar o storage no objeto existente
    # é necessário — trocar app.state.limiter não afeta os decorators.
    _mem = MemoryStorage()
    _orig_storage = _api_limiter._storage
    _api_limiter._storage = _mem
    _api_limiter._limiter.storage = _mem

    # settings é frozen dataclass: usa object.__setattr__ para forçar valores de teste.
    # ADMIN_PASSWORD/ADMIN_SESSION_SECRET podem vir do .env de produção quando predeploy
    # faz source .env antes do pytest, tornando os setdefault do topo do conftest ineficazes.
    _orig_admin_pw = _main.settings.admin_password
    _orig_admin_secret = _main.settings.admin_session_secret
    object.__setattr__(_main.settings, "admin_password", "correct horse")
    object.__setattr__(_main.settings, "admin_session_secret", "test-secret-for-signed-cookie")

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False  # exceptions stored, not propagated
    celery_app.conf.task_store_eager_result = True  # persist results to backend so AsyncResult works

    client = TestClient(app)
    # Prevent real yt-dlp network calls during unit tests; individual tests that need a
    # specific failure (ValidationError, etc.) patch check_duration themselves.
    with patch("api.tasks.check_duration", side_effect=RuntimeError("mock: no network in unit tests")):
        yield client

    _main._redis = _orig_redis
    _api_limiter._storage = _orig_storage
    _api_limiter._limiter.storage = _orig_storage
    object.__setattr__(_main.settings, "admin_password", _orig_admin_pw)
    object.__setattr__(_main.settings, "admin_session_secret", _orig_admin_secret)
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False
