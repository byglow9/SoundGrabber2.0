"""SoundGrabber API tests — Phase 2.

Stubs created in Plan 01 (Wave 1). Implementations turn these green:
  - Plan 02 (Wave 2): test_post_jobs_returns_job_id, test_invalid_url_rejected,
                      test_valid_youtube_url_accepted, test_failed_job_returns_sanitized_error
  - Plan 03 (Wave 3): test_get_jobs_status_transitions, test_get_jobs_unknown_id_returns_404,
                      test_file_streaming, test_file_not_ready_returns_404,
                      test_sweeper_deletes_expired_wavs, test_concurrent_jobs

Markers:
  - (no marker): unit tests, run on every commit (~5s)
  - integration: requires real WAV file on disk; no network
  - e2e: requires running Redis + worker + live YouTube (manual / CI)
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# -----------------------------------------------------------------------
# CORE-01: POST /jobs returns job_id immediately (Plan 02, Wave 2)
# -----------------------------------------------------------------------

def test_post_jobs_returns_job_id(api_client):
    """POST /jobs with valid YouTube URL returns job_id in < 300ms."""
    start = time.perf_counter()
    response = api_client.post("/jobs", json={"youtube_url": "https://www.youtube.com/watch?v=abc123"})
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert response.status_code == 202, f"expected 202, got {response.status_code}: {response.text}"
    body = response.json()
    assert "job_id" in body, f"response missing job_id: {body}"
    assert isinstance(body["job_id"], str) and len(body["job_id"]) >= 8
    assert elapsed_ms < 300, f"POST /jobs took {elapsed_ms}ms — must be under 300ms"


# -----------------------------------------------------------------------
# CORE-02: URL validation (Plan 02, Wave 2)
# -----------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "not-a-url",
    "ftp://example.com/file.mp4",
    "https://vimeo.com/12345",
    "https://soundcloud.com/artist/track",
    "http://localhost:6379",                    # SSRF attempt
    "https://www.example.com/watch?v=abc",      # non-YouTube host
])
def test_invalid_url_rejected(api_client, url):
    """Non-YouTube or malformed URLs return 422 (Pydantic validation)."""
    response = api_client.post("/jobs", json={"youtube_url": url})
    assert response.status_code == 422, f"URL {url!r} should be rejected; got {response.status_code}: {response.text}"


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123",
    "https://youtube.com/watch?v=abc123",
    "https://youtu.be/abc123",
    "https://m.youtube.com/watch?v=abc123",
])
def test_valid_youtube_url_accepted(api_client, url):
    """All four YouTube hosts are accepted by the validator."""
    response = api_client.post("/jobs", json={"youtube_url": url})
    assert response.status_code == 202, f"URL {url!r} should be accepted; got {response.status_code}: {response.text}"


# -----------------------------------------------------------------------
# D-05 / D-06: Failed job error contract (Plan 02, Wave 2)
# -----------------------------------------------------------------------

def test_failed_job_returns_sanitized_error(api_client):
    """When the worker raises ValueError (validation), GET /jobs/{id} returns
    status='failed' with sanitized error and error_type='validation_error'."""
    with patch("api.tasks.check_duration", side_effect=ValueError("Video too long: 1200s exceeds the 15-minute limit")):
        r = api_client.post("/jobs", json={"youtube_url": "https://www.youtube.com/watch?v=long"})
        job_id = r.json()["job_id"]
    status = api_client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "failed"
    assert status["error_type"] == "validation_error"
    assert "too long" in status["error"].lower() or "15 minutes" in status["error"]
    # Sanitization: yt-dlp internals MUST NOT leak through
    assert "Traceback" not in status["error"]
    assert "/tmp/" not in status["error"]


# -----------------------------------------------------------------------
# GET /jobs/{id} — Status transitions and unknown ID (Plan 03, Wave 3)
# -----------------------------------------------------------------------

def test_get_jobs_status_transitions(api_client):
    """GET /jobs/{id} returns one of the contract statuses: queued, downloading,
    converting, analyzing, done, failed."""
    valid = {"queued", "downloading", "converting", "analyzing", "done", "failed"}
    r = api_client.post("/jobs", json={"youtube_url": "https://www.youtube.com/watch?v=abc123"})
    job_id = r.json()["job_id"]
    status = api_client.get(f"/jobs/{job_id}").json()
    assert status["status"] in valid, f"unexpected status {status['status']!r}"


def test_get_jobs_unknown_id_returns_404(api_client):
    """Per D-02, an unknown / expired job_id returns 404 (NOT 'queued')."""
    response = api_client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404, f"unknown job_id must return 404, got {response.status_code}"


# -----------------------------------------------------------------------
# CORE-06: GET /files/{id} streams WAV (Plan 03, Wave 3)
# -----------------------------------------------------------------------

@pytest.mark.integration
def test_file_streaming(api_client, sample_wav_path, tmp_path):
    """GET /files/{id} returns WAV bytes with Content-Type audio/wav and a
    Content-Disposition: attachment header (so browser triggers download)."""
    from api.tasks import celery_app

    # Copy the fixture WAV to /tmp/sg_*.wav so the endpoint can read it
    target = Path("/tmp") / "sg_testfileXX.wav"
    target.write_bytes(sample_wav_path.read_bytes())

    # Forge an AsyncResult that the endpoint will inspect
    with patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "SUCCESS"
        mock_ar.return_value.result = {"wav_path": str(target)}
        response = api_client.get("/files/forged-job-id")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert "attachment" in response.headers.get("content-disposition", "").lower()
    assert response.content[:4] == b"RIFF"   # WAV magic bytes
    target.unlink(missing_ok=True)


def test_file_not_ready_returns_404(api_client):
    """GET /files/{id} for a job that has not completed returns 404."""
    with patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        response = api_client.get("/files/some-id")
    assert response.status_code == 404


# -----------------------------------------------------------------------
# D-01 sweeper: WAVs older than wav_ttl are deleted (Plan 03, Wave 3)
# -----------------------------------------------------------------------

def test_sweeper_deletes_expired_wavs(tmp_path, monkeypatch):
    """The sweeper helper deletes /tmp/sg_*.wav files older than wav_ttl."""
    sweeper_module = pytest.importorskip("api.main", reason="api.main not available")
    sweep_once = getattr(sweeper_module, "sweep_expired_wavs", None)
    if sweep_once is None:
        pytest.skip("sweep_expired_wavs not yet implemented (Plan 03)")

    old = tmp_path / "sg_oldfile.wav"
    new = tmp_path / "sg_newfile.wav"
    old.write_bytes(b"RIFFold ")
    new.write_bytes(b"RIFFnew ")
    # Set old file's mtime to 20 minutes ago
    past = time.time() - 1200
    import os
    os.utime(old, (past, past))

    sweep_once(tmp_path, ttl_seconds=900)

    assert not old.exists(), "sweeper must delete WAVs older than ttl"
    assert new.exists(), "sweeper must NOT delete fresh WAVs"


# -----------------------------------------------------------------------
# SC-4: 3 concurrent jobs complete without server hang (Plan 03, Wave 3)
# -----------------------------------------------------------------------

@pytest.mark.e2e
def test_concurrent_jobs(api_client, youtube_test_urls):
    """Three concurrent POST /jobs submissions all return job_ids, and all three
    GET /jobs/{id} eventually report 'done' or 'failed' — none hang."""
    import concurrent.futures

    urls = list(youtube_test_urls.values())[:3]

    def submit(url: str) -> str:
        r = api_client.post("/jobs", json={"youtube_url": url})
        assert r.status_code == 202
        return r.json()["job_id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        job_ids = list(pool.map(submit, urls))

    assert len(job_ids) == 3 and len(set(job_ids)) == 3, "expected 3 distinct job_ids"

    # Poll each up to 5 minutes; status MUST eventually be done or failed
    terminal = {"done", "failed"}
    deadline = time.time() + 300
    for jid in job_ids:
        while time.time() < deadline:
            status = api_client.get(f"/jobs/{jid}").json()["status"]
            if status in terminal:
                break
            time.sleep(2)
        else:
            pytest.fail(f"job {jid} did not reach terminal state in 5 min")


# -----------------------------------------------------------------------
# UX-03: 422 body normalizado — Phase 3, Plan 02 torna verde
# -----------------------------------------------------------------------

def test_validation_error_format(api_client):
    """422 body segue formato {error, error_type: 'validation_error'} sem prefixo Pydantic v2 (D-07)."""
    response = api_client.post("/jobs", json={"youtube_url": "https://vimeo.com/12345"})
    assert response.status_code == 422
    body = response.json()
    assert "error" in body, f"body deve ter chave 'error': {body}"
    assert body.get("error_type") == "validation_error", f"error_type errado: {body}"
    assert "detail" not in body, f"chave 'detail' nao deve existir no body: {body}"
    assert not body["error"].startswith("Value error,"), (
        f"prefixo Pydantic v2 nao deve vazar no body: {body['error']!r}"
    )


# -----------------------------------------------------------------------
# UX-04: Rate limiting 429 — Phase 3, Plan 03 torna verde
# -----------------------------------------------------------------------

def test_rate_limit_returns_429(api_client):
    """4a requisicao em 60s pelo mesmo IP retorna 429 com error_type rate_limit_error (D-01/D-03)."""
    url = "https://www.youtube.com/watch?v=abc123"
    for i in range(3):
        r = api_client.post("/jobs", json={"youtube_url": url})
        assert r.status_code == 202, f"requisicao {i+1}/3 esperada 202: {r.status_code} {r.text}"
    r = api_client.post("/jobs", json={"youtube_url": url})
    assert r.status_code == 429, f"4a requisicao deve retornar 429: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("error_type") == "rate_limit_error", f"error_type errado: {body}"
    assert "error" in body, f"body deve ter chave 'error': {body}"


def test_rate_limit_retry_after_header(api_client):
    """429 inclui header Retry-After com valor inteiro em segundos (D-04 / RFC 9110)."""
    url = "https://www.youtube.com/watch?v=abc123"
    for _ in range(3):
        api_client.post("/jobs", json={"youtube_url": url})
    r = api_client.post("/jobs", json={"youtube_url": url})
    assert r.status_code == 429
    assert "retry-after" in r.headers, (
        f"header Retry-After ausente no 429: {dict(r.headers)}"
    )
    retry_val = r.headers["retry-after"]
    assert retry_val.isdigit(), (
        f"Retry-After deve ser inteiro em segundos (ex: '60'): {retry_val!r}"
    )


# -----------------------------------------------------------------------
# SC-4 / D-05/D-06: Sweeper limpa .part e .ytdl — Phase 3, Plan 02 torna verde
# -----------------------------------------------------------------------

def test_sweeper_deletes_partial_files(tmp_path):
    """sweep_expired_wavs deleta sg_*.part e sg_*.ytdl mais velhos que ttl; nao deleta frescos (D-05/D-06)."""
    import os
    from api.main import sweep_expired_wavs

    old_part = tmp_path / "sg_abc.part"
    old_ytdl = tmp_path / "sg_abc.ytdl"
    new_part = tmp_path / "sg_xyz.part"

    old_part.write_bytes(b"partial")
    old_ytdl.write_bytes(b"state")
    new_part.write_bytes(b"inprogress")

    past = time.time() - 1200  # 20 min atras > ttl de 900s
    os.utime(old_part, (past, past))
    os.utime(old_ytdl, (past, past))
    # new_part: mtime atual (fresco — nao deve ser deletado)

    sweep_expired_wavs(tmp_path, ttl_seconds=900)

    assert not old_part.exists(), "sweeper deve deletar sg_*.part expirado"
    assert not old_ytdl.exists(), "sweeper deve deletar sg_*.ytdl expirado"
    assert new_part.exists(), "sweeper NAO deve deletar sg_*.part fresco"
